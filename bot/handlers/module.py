"""
«🗂 Модуль»: какой модуль смотреть. Макет — docs/ui_module.md, задача — docs/module_switch_developer.md.

callback_data:
  module                     экран выбора
  module_set_<id>            выбрать модуль → подсказка и главное меню
  module_now_<section>       «🗂 Вернуться в <текущий>» → тот же раздел
                             (section: deadlines | progress | mysubj | schedule)
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.models import Module, User
from bot.services import modules as M
from bot.services.deadlines import now_msk
from bot.utils.database import SessionLocal
from bot.utils.ui import answer, show_screen


def _user(db, telegram_id):
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


async def _not_authorized(update: Update, context) -> bool:
    if auth_service.is_user_verified(update.effective_user.id):
        return False
    await answer(update, context)
    await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
    return True


async def show_module_screen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """module: список модулей с датами, кнопки «<name> · <статус>», ✅ у открытого."""
    if await _not_authorized(update, context):
        return
    await answer(update, context)
    db = SessionLocal()
    try:
        v = M.get_view(db, _user(db, update.effective_user.id), now_msk().date())
        text = M.choose_screen_text(v.modules)
        rows = [[InlineKeyboardButton(
            f"{'✅ ' if v.view and m.id == v.view.id else ''}{m.name} · {M.status_word(m, v.today, v.current)}",
            callback_data=f"module_set_{m.id}")] for m in v.modules]
    finally:
        db.close()
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
    await show_screen(update, context, text, reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')


async def module_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """module_set_<id>: записать выбор, подсказка, главное меню (повторное нажатие — только подсказка)."""
    from bot.handlers.commands import show_main_menu

    if await _not_authorized(update, context):
        return
    module_id = int(update.callback_query.data.rsplit("_", 1)[-1])
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        v = M.get_view(db, user, now_msk().date())
        module = db.get(Module, module_id)
        if user is None or module is None:
            toast = None
        elif v.view is not None and module.id == v.view.id:
            await answer(update, context, M.toast_already(module))
            return
        else:
            M.set_view(user, module, v.current)
            db.commit()
            toast = M.toast_opened(module, v.today, v.current)
    finally:
        db.close()
    await answer(update, context, toast)
    await show_main_menu(update, context)


async def module_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """module_now_<section>: вернуться в текущий модуль и перерисовать тот же раздел."""
    if await _not_authorized(update, context):
        return
    section = update.callback_query.data.removeprefix("module_now_")
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        v = M.get_view(db, user, now_msk().date())
        if user is not None and v.current is not None:
            M.set_view(user, v.current, v.current)
            db.commit()
            toast = M.toast_opened(v.current, v.today, v.current)
        else:
            toast = None
    finally:
        db.close()
    await answer(update, context, toast)
    await open_section(update, context, section)


async def open_section(update: Update, context, section: str):
    if section == 'deadlines':
        from bot.handlers.deadlines import show_deadlines
        await show_deadlines(update, context)
    elif section == 'progress':
        from bot.handlers.progress import show_progress
        await show_progress(update, context)
    elif section == 'mysubj':
        from bot.handlers.my_subjects import render
        await render(update, context)
    elif section == 'schedule':
        from bot.handlers.schedule import show_schedule
        await show_schedule(update, context)
    else:
        from bot.handlers.commands import show_main_menu
        await show_main_menu(update, context)
