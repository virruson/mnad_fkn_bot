"""
Меню «🔔 Уведомления»: четыре независимых переключателя и «📚 Мои предметы».
Макет — docs/ui_deadlines.md, раздел 3; предметы — docs/magolego_developer.md, п. 5.
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.handlers.my_subjects import entry_button
from bot.models import Subject, User
from bot.services.scheduler import replan_reminders_for_user
from bot.services.selection import describe, get_selection
from bot.utils.database import SessionLocal
from bot.utils.ui import show_screen

logger = logging.getLogger(__name__)

# ключ callback → (поле User, подпись кнопки)
TOGGLES = {
    'digest':    ('digest_enabled',    "Расписание на день · 10:00"),
    'reminders': ('reminders_enabled', "Напоминание за 15 мин"),
    'deadlines': ('deadlines_enabled', "Дедлайны · сегодня и за 1, 2, 4 дн"),
    'news':      ('news_enabled',      "Новости бота"),
}


def _get_user(db, user_id: int):
    return db.query(User).filter(User.telegram_id == str(user_id)).first()


async def _require_auth(update: Update, context) -> bool:
    if auth_service.is_user_verified(update.effective_user.id):
        return True
    await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
    return False


def _status_line(user) -> str:
    enabled = sum(getattr(user, field) for field, _ in TOGGLES.values())
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
        sel = get_selection(db, user)
        chosen = db.query(Subject).filter(Subject.id.in_(list(sel.elective_ids))).all() if sel.elective_ids else []
        text = f"🔔 <b>Уведомления</b>\n{_status_line(user)}\n{describe(sel, chosen)}"
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if getattr(user, field) else '☐'} {label}",
                                  callback_data=f"notify_toggle_{key}")]
            for key, (field, label) in TOGGLES.items()
        ]
        keyboard.append(entry_button('notify'))
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
    if await _require_auth(update, context):
        await _render_menu(update, context)


# ---------------------------------------------------------------------------
# Переключатели: notify_toggle_<digest|reminders|deadlines|news>
# ---------------------------------------------------------------------------

async def notify_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    key = query.data.removeprefix("notify_toggle_")
    if key not in TOGGLES or not auth_service.is_user_verified(update.effective_user.id):
        await query.answer()
        return
    field, label = TOGGLES[key]

    db = SessionLocal()
    try:
        user = _get_user(db, update.effective_user.id)
        if not user:
            await query.answer()
            return
        new_value = not getattr(user, field)
        setattr(user, field, new_value)
        user.updated_at = datetime.now()
        db.commit()
        logger.warning(f"[NOTIFY] toggle {user.telegram_id} {user.email}: {field} → {new_value}")
    finally:
        db.close()

    if key == 'reminders':
        replan_reminders_for_user(context.job_queue, update.effective_user.id)
    await query.answer(f"{label}: {'вкл' if new_value else 'выкл'}")
    await _render_menu(update, context)
