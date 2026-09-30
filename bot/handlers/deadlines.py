"""
Раздел «⏳ Дедлайны»: список предметов текущего модуля и карточка предмета.
Макеты — docs/ui_deadlines.md.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.models import Subject
from bot.services.deadlines import (
    build_subject_buttons,
    get_current_module,
    get_module_subjects,
    get_subject_deadlines,
    now_msk,
    render_deadlines_screen,
    render_subject_card,
)
from bot.utils.database import SessionLocal
from bot.utils.ui import show_screen

MAIN_MENU_BUTTON = [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]


async def _answer(update: Update):
    if update.callback_query:
        await update.callback_query.answer()


async def show_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE, new_message: bool = False):
    """Список предметов текущего модуля (кнопка «⏳ Дедлайны», /deadlines, /tasks)."""
    await _answer(update)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.", new_message=new_message)
        return

    now = now_msk()
    db = SessionLocal()
    try:
        module = get_current_module(db, now.date())
        subjects = get_module_subjects(db, module) if module else []
        deadlines = get_subject_deadlines(db, [s.id for s in subjects])
        buttons = build_subject_buttons(subjects, deadlines, now)
    finally:
        db.close()

    keyboard = [[InlineKeyboardButton(text, callback_data=f"deadlines_subj_{sid}")]
                for sid, text in buttons]
    keyboard.append(MAIN_MENU_BUTTON)
    await show_screen(update, context, render_deadlines_screen(bool(buttons)),
                      new_message=new_message,
                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def open_deadlines_from_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «⏳ Все дедлайны» под утренним сообщением: само сообщение оставляем в чате."""
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await show_deadlines(update, context, new_message=True)


async def show_subject_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка предмета: deadlines_subj_<id>."""
    await _answer(update)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
        return

    subject_id = int(update.callback_query.data.rsplit("_", 1)[-1])
    db = SessionLocal()
    try:
        subject = db.get(Subject, subject_id)
        if subject is None:
            text = "<i>нет информации</i>"
        else:
            deadlines = get_subject_deadlines(db, [subject_id])[subject_id]
            text = render_subject_card(subject, deadlines, now_msk())
    finally:
        db.close()

    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="deadlines")]]
    await show_screen(update, context, text,
                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
