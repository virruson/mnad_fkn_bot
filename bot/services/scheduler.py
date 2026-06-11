"""
Фоновые джобы: утренний дайджест + точечные напоминания за 15 минут до занятия.
Используем PTB JobQueue.

Логика напоминаний:
  - Утренний дайджест (10:00 МСК) знает расписание на день и
    сразу ставит run_once на каждое занятие минус 15 мин.
  - При старте бота (on_startup) — то же самое, для занятий которые ещё не начались.
"""
import logging
from datetime import datetime, timedelta, time

import pytz

from sqlalchemy.orm import joinedload

from bot.utils.database import SessionLocal, get_schedule_by_date
from bot.models import User

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone('Europe/Moscow')
REMINDER_BEFORE = timedelta(minutes=15)
ALL_STREAMS_NAME = "все потоки"  # специальный поток — без фильтрации


def _stream_filter(user) -> str | None:
    """Возвращает stream_name для фильтра или None (все потоки)."""
    if not user.stream or user.stream.name == ALL_STREAMS_NAME:
        return None
    return user.stream.name


# ---------------------------------------------------------------------------
# Форматирование
# ---------------------------------------------------------------------------

def _format_lesson(sch) -> str:
    t = sch.Schedule.lesson_time.strftime('%H:%M')
    teacher = f"{sch.last_name} {sch.first_name[0]}." if sch.first_name else sch.last_name
    lines = [f"⏰ {t}  {sch.subject_name} ({sch.lesson_type_name})", f"👨‍🏫 {teacher}"]
    if sch.Schedule.zoom_link:
        lines.append(f"🔗 {sch.Schedule.zoom_link}")
    else:
        lines.append("📍 Очное занятие")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Джоб напоминания (вызывается run_once в точное время)
# ---------------------------------------------------------------------------

async def _send_reminder(context):
    """Отправляет напоминание одному пользователю об одном занятии."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    data = context.job.data  # {'chat_id': str, 'text': str}
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("OK  •  Открыть меню", callback_data="reminder_ok")
    ]])
    try:
        await context.bot.send_message(
            chat_id=data['chat_id'],
            text=data['text'],
            reply_markup=keyboard,
        )
        logger.warning(f"[NOTIFY] reminder sent → {data['chat_id']} | {data.get('lesson_time', '?')}")
    except Exception as e:
        logger.error(f"[NOTIFY] reminder FAILED → {data['chat_id']}: {e}")


# ---------------------------------------------------------------------------
# Постановка напоминаний для одного пользователя на один день
# ---------------------------------------------------------------------------

def _schedule_reminders_for_user(jq, user, schedules, today):
    """
    Ставит run_once для каждого занятия пользователя,
    если время напоминания ещё в будущем.
    """
    now_msk = datetime.now(MOSCOW_TZ)

    for sch in schedules:
        lesson_time = sch.Schedule.lesson_time  # time объект
        lesson_dt = MOSCOW_TZ.localize(
            datetime.combine(today, lesson_time)
        )
        remind_at = lesson_dt - REMINDER_BEFORE

        if remind_at <= now_msk:
            continue  # время уже прошло — пропускаем

        text = f"🔔 Напоминание — через 15 минут:\n\n{_format_lesson(sch)}"
        job_name = f"reminder_{user.telegram_id}_{sch.Schedule.id}"

        # Снимаем старый джоб с тем же именем (на случай переназначения)
        for old in jq.get_jobs_by_name(job_name):
            old.schedule_removal()

        jq.run_once(
            _send_reminder,
            when=remind_at,
            data={
                'chat_id': user.telegram_id,
                'text': text,
                'lesson_time': lesson_time.strftime('%H:%M'),
            },
            name=job_name,
        )
        logger.warning(f"[NOTIFY] reminder scheduled → {user.telegram_id} at {remind_at.strftime('%H:%M')} MSK (lesson {lesson_time.strftime('%H:%M')})")


# ---------------------------------------------------------------------------
# Джоб 1: Утренний дайджест в 10:00 МСК
# ---------------------------------------------------------------------------

async def daily_digest(context):
    """Отправляет расписание на сегодня и ставит напоминания."""
    jq = context.job_queue
    today = datetime.now(MOSCOW_TZ).date()

    db = SessionLocal()
    try:
        # joinedload — загружаем stream сразу, без lazy load
        users = db.query(User).options(joinedload(User.stream)).filter(
            User.notifications_enabled == True,
            User.is_verified == True,
            User.stream_id != None,
        ).all()

        for user in users:
            stream_name = _stream_filter(user)
            display_name = user.stream.name if user.stream else "все потоки"
            telegram_id = user.telegram_id

            # Отдельная сессия для расписания — избегаем конфликта identity map
            db2 = SessionLocal()
            try:
                schedules = get_schedule_by_date(db2, today, stream_name=stream_name)

                if not schedules:
                    text = f"📅 {today.strftime('%d.%m.%Y')} — занятий нет 🎉"
                else:
                    day_names = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
                    weekday = day_names[today.weekday()]
                    header = f"📅 Расписание на {today.strftime('%d.%m')} ({weekday})\nГруппа: {display_name}"
                    lessons = "\n\n".join(_format_lesson(s) for s in schedules)
                    text = f"{header}\n\n{lessons}"

                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("OK  •  Открыть меню", callback_data="reminder_ok")
                ]])
                await context.bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)
                logger.warning(f"[NOTIFY] digest sent → {telegram_id} | lessons={len(schedules)}")

                if schedules:
                    _schedule_reminders_for_user(jq, user, schedules, today)

            except Exception as e:
                logger.error(f"daily_digest: {telegram_id}: {e}", exc_info=True)
            finally:
                db2.close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Джоб 2: Старт бота — назначить напоминания на оставшуюся часть дня
# ---------------------------------------------------------------------------

async def on_startup(context):
    """
    Запускается один раз при старте бота.
    Назначает напоминания для занятий, которые ещё не начались сегодня.
    Нужно на случай рестарта контейнера в течение дня.
    """
    jq = context.job_queue
    today = datetime.now(MOSCOW_TZ).date()
    logger.warning(f"[NOTIFY] on_startup запущен, today={today}")

    db = SessionLocal()
    try:
        users = db.query(User).options(joinedload(User.stream)).filter(
            User.notifications_enabled == True,
            User.is_verified == True,
            User.stream_id != None,
        ).all()

        count = 0
        for user in users:
            stream_name = _stream_filter(user)
            db2 = SessionLocal()
            try:
                schedules = get_schedule_by_date(db2, today, stream_name=stream_name)
                if schedules:
                    _schedule_reminders_for_user(jq, user, schedules, today)
                    count += len(schedules)
            except Exception as e:
                logger.error(f"on_startup reminders: {user.telegram_id}: {e}", exc_info=True)
            finally:
                db2.close()

        logger.warning(f"[NOTIFY] on_startup: пользователей={len(users)} занятий_запланировано={count}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Регистрация джобов
# ---------------------------------------------------------------------------

def setup_scheduler(application):
    """Вызвать из main() после создания application."""
    jq = application.job_queue

    # Дайджест + назначение напоминаний каждый день в 10:00 МСК
    digest_time = time(hour=10, minute=0, second=0, tzinfo=MOSCOW_TZ)
    jq.run_daily(daily_digest, time=digest_time, name="daily_digest")

    # Один раз при старте — восстановить напоминания если бот перезапустился
    jq.run_once(on_startup, when=5, name="on_startup")  # через 5 сек после старта

    logger.warning("[NOTIFY] Планировщик запущен (дайджест 10:00 МСК + восстановление при старте)")
