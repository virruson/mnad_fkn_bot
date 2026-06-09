"""
Обработчики меню уведомлений
"""
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from bot.handlers.auth import auth_service
from bot.utils.database import SessionLocal, get_streams
from bot.models import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _get_user(db, user_id: int):
    return db.query(User).filter(User.telegram_id == str(user_id)).first()


async def _edit_or_send(query, text: str, reply_markup=None):
    try:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    except BadRequest:
        await query.message.reply_text(text=text, reply_markup=reply_markup)


# ---------------------------------------------------------------------------
# Главное меню уведомлений
# ---------------------------------------------------------------------------

async def notify_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not auth_service.is_user_verified(user_id):
        await _edit_or_send(query, "🔐 Сначала авторизуйтесь.")
        return

    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user and user.notifications_enabled and user.stream:
            status = f"✅ Уведомления включены\nГруппа: {user.stream.name}"
        else:
            status = "🔕 Уведомления отключены"
    finally:
        db.close()

    keyboard = [
        [InlineKeyboardButton("⚙️ Настроить уведомления", callback_data="notify_setup")],
        [InlineKeyboardButton("🔕 Отключить уведомления", callback_data="notify_disable")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")],
    ]
    await _edit_or_send(
        query,
        f"🔔 Уведомления\n\n{status}\n\n"
        "Каждое утро в 10:00 МСК вы получите расписание на день.\n"
        "За 15 минут до занятия придёт напоминание.",
        InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# Шаг 1: выбор группы
# ---------------------------------------------------------------------------

async def notify_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not auth_service.is_user_verified(user_id):
        await _edit_or_send(query, "🔐 Сначала авторизуйтесь.")
        return

    db = SessionLocal()
    try:
        streams = get_streams(db)
        if not streams:
            await _edit_or_send(query, "❌ Группы не найдены в БД.")
            return

        keyboard = [
            [InlineKeyboardButton(s.name, callback_data=f"notify_stream_{s.id}")]
            for s in streams
        ]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="notify_menu")])

        await _edit_or_send(
            query,
            "Выберите вашу группу:",
            InlineKeyboardMarkup(keyboard),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Шаг 2: подписка
# ---------------------------------------------------------------------------

async def notify_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    stream_id = int(query.data.split("_")[-1])  # notify_stream_<id>

    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if not user:
            await _edit_or_send(query, "❌ Пользователь не найден. Авторизуйтесь заново.")
            return

        user.stream_id = stream_id
        user.notifications_enabled = True
        user.updated_at = datetime.now()
        db.commit()
        db.refresh(user)
        stream_name = user.stream.name if user.stream else "—"
    finally:
        db.close()

    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
    await _edit_or_send(
        query,
        f"✅ Готово! Уведомления включены.\n"
        f"Группа: {stream_name}\n\n"
        "Каждое утро в 10:00 МСК придёт расписание на день,\n"
        "а за 15 минут до занятия — напоминание.",
        InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# Отписка
# ---------------------------------------------------------------------------

async def notify_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    db = SessionLocal()
    try:
        user = _get_user(db, user_id)
        if user:
            user.notifications_enabled = False
            user.updated_at = datetime.now()
            db.commit()
    finally:
        db.close()

    keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
    await _edit_or_send(
        query,
        "🔕 Уведомления отключены.",
        InlineKeyboardMarkup(keyboard),
    )
