"""
Меню «🔔 Уведомления»: три независимых переключателя и выбор группы.
Макет — docs/ui_deadlines.md, раздел 3.
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.models import User
from bot.services.scheduler import replan_reminders_for_user
from bot.utils.database import SessionLocal, get_streams
from bot.utils.ui import show_screen

logger = logging.getLogger(__name__)

# ключ callback → (поле User, подпись кнопки, нужна ли группа)
TOGGLES = {
    'digest':    ('digest_enabled',    "Расписание на день · 10:00", True),
    'reminders': ('reminders_enabled', "Напоминание за 15 мин",      True),
    'deadlines': ('deadlines_enabled', "Дедлайны · за 4, 2, 1 дн",   False),
    'news':      ('news_enabled',      "Новости бота",               False),
}
PENDING_KEY = "notify_pending_toggle"


def _get_user(db, user_id: int):
    return db.query(User).filter(User.telegram_id == str(user_id)).first()


async def _require_auth(update: Update, context) -> bool:
    if auth_service.is_user_verified(update.effective_user.id):
        return True
    await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
    return False


def _status_line(user) -> str:
    if not user.stream:
        return "Группа не выбрана"
    enabled = sum(getattr(user, field) for field, _, _ in TOGGLES.values())
    if not enabled:
        return "🔕 Все уведомления выключены"
    return f"Включено {enabled} из {len(TOGGLES)}"


async def _render_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        user = _get_user(db, update.effective_user.id)
        if not user:
            await show_screen(update, context, "❌ Пользователь не найден. Авторизуйтесь заново.")
            return
        text = f"🔔 <b>Уведомления</b>\n{_status_line(user)}"
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if getattr(user, field) else '☐'} {label}",
                                  callback_data=f"notify_toggle_{key}")]
            for key, (field, label, _) in TOGGLES.items()
        ]
        group = user.stream.name if user.stream else "не выбрана"
        keyboard.append([InlineKeyboardButton(f"👥 Группа: {group}", callback_data="notify_setup")])
        keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")])
    finally:
        db.close()

    await show_screen(update, context, text,
                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


# ---------------------------------------------------------------------------
# Меню
# ---------------------------------------------------------------------------

async def notify_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.pop(PENDING_KEY, None)
    if await _require_auth(update, context):
        await _render_menu(update, context)


# ---------------------------------------------------------------------------
# Переключатели: notify_toggle_<digest|reminders|deadlines>
# ---------------------------------------------------------------------------

async def notify_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.removeprefix("notify_toggle_")
    if key not in TOGGLES or not auth_service.is_user_verified(update.effective_user.id):
        await query.answer()
        return
    field, label, needs_group = TOGGLES[key]

    db = SessionLocal()
    try:
        user = _get_user(db, update.effective_user.id)
        if not user:
            await query.answer()
            return
        new_value = not getattr(user, field)
        if new_value and needs_group and not user.stream_id:
            # Сначала группа, флаг включится после её выбора
            context.user_data[PENDING_KEY] = key
            await query.answer("Сначала выберите группу")
            await _show_group_picker(update, context)
            return
        setattr(user, field, new_value)
        user.updated_at = datetime.now()
        db.commit()
    finally:
        db.close()

    if key == 'reminders':
        replan_reminders_for_user(context.job_queue, update.effective_user.id)
    await query.answer(f"{label}: {'вкл' if new_value else 'выкл'}")
    await _render_menu(update, context)


# ---------------------------------------------------------------------------
# Выбор группы: notify_setup → notify_stream_<id> → обратно в меню
# ---------------------------------------------------------------------------

async def _show_group_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        streams = get_streams(db)
    finally:
        db.close()
    if not streams:
        await show_screen(update, context, "❌ Группы не найдены в БД.")
        return
    keyboard = [[InlineKeyboardButton(s.name, callback_data=f"notify_stream_{s.id}")] for s in streams]
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="notify_menu")])
    await show_screen(update, context, "👥 Выберите вашу группу:",
                      reply_markup=InlineKeyboardMarkup(keyboard))


async def notify_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if await _require_auth(update, context):
        await _show_group_picker(update, context)


async def notify_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not auth_service.is_user_verified(update.effective_user.id):
        await query.answer()
        return
    stream_id = int(query.data.rsplit("_", 1)[-1])  # notify_stream_<id>
    pending = context.user_data.pop(PENDING_KEY, None)

    db = SessionLocal()
    try:
        user = _get_user(db, update.effective_user.id)
        if not user:
            await query.answer()
            await show_screen(update, context, "❌ Пользователь не найден. Авторизуйтесь заново.")
            return
        user.stream_id = stream_id
        if pending in TOGGLES:
            setattr(user, TOGGLES[pending][0], True)
        user.updated_at = datetime.now()
        db.commit()
        db.refresh(user)
        stream_name = user.stream.name if user.stream else "—"
    finally:
        db.close()

    # Группа влияет на напоминания, уже поставленные на сегодня
    replan_reminders_for_user(context.job_queue, update.effective_user.id)
    toast = f"Группа: {stream_name}"
    if pending in TOGGLES:
        toast += f" · {TOGGLES[pending][1]}: вкл"
    await query.answer(toast)
    await _render_menu(update, context)
