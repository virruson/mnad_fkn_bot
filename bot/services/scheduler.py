"""
Фоновые джобы (PTB JobQueue), все флаги пользователя независимы:
  - daily_digest     10:00 МСК — расписание на день        (users.digest_enabled)
  - plan_reminders   00:05 МСК — ставит run_once за 15 мин  (users.reminders_enabled)
  - deadline_digest  10:00 МСК — дедлайны за 4, 2 и 1 день  (users.deadlines_enabled)
  - plan_reminders   и через 5 с после старта — восстановить напоминания на остаток дня.
"""
import logging
from datetime import datetime, timedelta, time

import pytz

from sqlalchemy.orm import joinedload

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.database import SessionLocal, get_schedule_by_date
from bot.models import User
from bot.services.deadlines import get_digest_deadlines, render_deadline_digest

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
    if sch.Schedule.meeting_link:
        lines.append(f"🔗 {sch.Schedule.meeting_link}")
    else:
        lines.append("📍 Очное занятие")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Джоб напоминания (вызывается run_once в точное время)
# ---------------------------------------------------------------------------

async def _send_reminder(context):
    """Отправляет напоминание одному пользователю об одном занятии."""
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
    """Отправляет расписание на сегодня (напоминания ставит plan_reminders)."""
    today = datetime.now(MOSCOW_TZ).date()

    db = SessionLocal()
    try:
        # joinedload — загружаем stream сразу, без lazy load
        users = db.query(User).options(joinedload(User.stream)).filter(
            User.digest_enabled == True,
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

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("OK  •  Открыть меню", callback_data="reminder_ok")
                ]])
                await context.bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)
                logger.warning(f"[NOTIFY] digest sent → {telegram_id} | lessons={len(schedules)}")

            except Exception as e:
                logger.error(f"daily_digest: {telegram_id}: {e}", exc_info=True)
            finally:
                db2.close()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Джоб 2: напоминания за 15 минут (в начале дня и при старте бота)
# ---------------------------------------------------------------------------

def _reminder_users_query(db):
    return db.query(User).options(joinedload(User.stream)).filter(
        User.reminders_enabled == True,
        User.is_verified == True,
        User.stream_id != None,
    )


def _plan_reminders(jq, users, today) -> int:
    count = 0
    for user in users:
        db2 = SessionLocal()
        try:
            schedules = get_schedule_by_date(db2, today, stream_name=_stream_filter(user))
            if schedules:
                _schedule_reminders_for_user(jq, user, schedules, today)
                count += len(schedules)
        except Exception as e:
            logger.error(f"plan reminders: {user.telegram_id}: {e}", exc_info=True)
        finally:
            db2.close()
    return count


async def plan_reminders(context):
    """Ставит напоминания на сегодня всем с reminders_enabled.

    Запускается в 00:05 МСК и один раз при старте бота (на случай рестарта
    контейнера в течение дня) — прошедшие занятия пропускаются.
    """
    today = datetime.now(MOSCOW_TZ).date()
    db = SessionLocal()
    try:
        users = _reminder_users_query(db).all()
        count = _plan_reminders(context.job_queue, users, today)
        logger.warning(f"[NOTIFY] plan_reminders {today}: пользователей={len(users)} занятий={count}")
    finally:
        db.close()



def replan_reminders_for_user(jq, telegram_id):
    """Снимает напоминания пользователя на сегодня и ставит заново по текущим настройкам.

    Вызывается при переключении «За 15 мин до пары» и смене группы.
    """
    if jq is None:
        return
    prefix = f"reminder_{telegram_id}_"
    for job in jq.jobs():
        if job.name and job.name.startswith(prefix):
            job.schedule_removal()

    db = SessionLocal()
    try:
        users = _reminder_users_query(db).filter(User.telegram_id == str(telegram_id)).all()
        _plan_reminders(jq, users, datetime.now(MOSCOW_TZ).date())
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Джоб 3: Дедлайны в 10:00 МСК — только за 4, 2 и 1 день
# ---------------------------------------------------------------------------

async def send_deadline_digest(bot, today) -> int:
    """Рассылает утреннее сообщение о дедлайнах на дату today. Возвращает число отправок."""
    db = SessionLocal()
    try:
        deadlines = get_digest_deadlines(db, today)
        for d in deadlines:
            _ = d.subject  # подгружаем предмет, пока сессия открыта
        text = render_deadline_digest(deadlines, today)
        if text is None:
            logger.warning(f"[NOTIFY] deadline_digest {today}: дедлайнов на 4/2/1 день нет")
            return 0
        chat_ids = [u.telegram_id for u in db.query(User).filter(
            User.deadlines_enabled == True,
            User.is_verified == True,
        ).all()]
    finally:
        db.close()

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⏳ Все дедлайны", callback_data="deadlines_open")
    ]])
    sent = 0
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=keyboard)
            sent += 1
        except Exception as e:
            logger.error(f"[NOTIFY] deadline_digest FAILED → {chat_id}: {e}")
    logger.warning(f"[NOTIFY] deadline_digest {today}: отправлено {sent} из {len(chat_ids)}")
    return sent


async def deadline_digest(context):
    await send_deadline_digest(context.bot, datetime.now(MOSCOW_TZ).date())


# ---------------------------------------------------------------------------
# Регистрация джобов
# ---------------------------------------------------------------------------

def setup_scheduler(application):
    """Вызвать из main() после создания application."""
    jq = application.job_queue

    morning = time(hour=10, minute=0, second=0, tzinfo=MOSCOW_TZ)
    jq.run_daily(daily_digest, time=morning, name="daily_digest")
    jq.run_daily(deadline_digest, time=morning, name="deadline_digest")
    jq.run_daily(plan_reminders, time=time(hour=0, minute=5, tzinfo=MOSCOW_TZ), name="plan_reminders")

    # Один раз при старте — восстановить напоминания если бот перезапустился
    jq.run_once(plan_reminders, when=5, name="on_startup")  # через 5 сек после старта

    logger.warning("[NOTIFY] Планировщик запущен (10:00 дайджест + дедлайны, 00:05 напоминания, восстановление при старте)")
