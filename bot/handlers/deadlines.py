"""
Раздел «⏳ Дедлайны»: список предметов текущего модуля и карточка предмета.
Макеты — docs/ui_deadlines.md.
"""
import asyncio

from sqlalchemy.orm import joinedload
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.models import Deadline, Subject
from bot.services import deadline_chart
from bot.services.selection import (
    get_available_electives, get_selection_by_telegram_id, visible_deadlines, visible_subjects,
)
from bot.services.deadlines import (
    build_subject_buttons,
    get_done_for_telegram_id,
    without_done,
    get_screen_subjects,
    get_subject_deadlines,
    now_msk,
    render_deadlines_screen,
    render_subject_card,
)
from bot.utils.database import SessionLocal
from bot.services import modules as M
from bot.utils.ui import answer, show_photo_screen, show_screen

MAIN_MENU_BUTTON = [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
CHART_BUTTON = [InlineKeyboardButton("📊 Все на графике", callback_data="deadlines_chart")]
_chart_file_ids: dict[str, str] = {}  # cache_key (дата + хэш данных) → file_id фото в Telegram


async def _answer(update: Update, context=None, text: str = None):
    if update.callback_query:
        if context is None:
            await update.callback_query.answer(text)
        else:
            await answer(update, context, text)


async def show_deadlines(update: Update, context: ContextTypes.DEFAULT_TYPE, new_message: bool = False):
    """Список предметов смотримого модуля (кнопка «⏳ Дедлайны», /deadlines, /tasks)."""
    await _answer(update, context)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.", new_message=new_message)
        return

    from bot.handlers.my_subjects import choose_electives_hint, empty_text, entry_button

    now = now_msk()
    db = SessionLocal()
    try:
        selection = get_selection_by_telegram_id(db, update.effective_user.id)
        view = M.get_view_by_telegram_id(db, update.effective_user.id, now.date())
        subjects = visible_subjects(get_screen_subjects(db, view.view, now.date()), selection)
        deadlines = get_subject_deadlines(db, [s.id for s in subjects])
        done = get_done_for_telegram_id(db, update.effective_user.id)   # сданное не делает предмет срочным
        # в нетекущем модуле — без «❗», по названию, ВКР последней
        buttons = build_subject_buttons(subjects, deadlines, now, done=done, by_name=not view.is_current)
        hint = choose_electives_hint(selection, get_available_electives(db, view.view, now.date()))
    finally:
        db.close()

    if selection.is_empty:
        text, keyboard = empty_text("⏳ <b>Дедлайны</b>"), [entry_button('deadlines')]
    else:
        text = render_deadlines_screen(bool(buttons), view.is_current)
        chart = [CHART_BUTTON] if buttons and view.is_current else []   # график — только в текущем
        keyboard = chart + [
            [InlineKeyboardButton(t, callback_data=f"deadlines_subj_{sid}")] for sid, t in buttons]
        if hint:
            keyboard.append(entry_button('deadlines', "📚 Выбрать маголего"))
    text = M.with_banner(text, view.banner)
    if back := view.back_button('deadlines'):
        keyboard.append(back)
    keyboard.append(MAIN_MENU_BUTTON)
    await show_screen(update, context, text, new_message=new_message,
                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def open_deadlines_from_digest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «⏳ Открыть дедлайны» под утренним сообщением: само сообщение оставляем в чате."""
    await update.callback_query.edit_message_reply_markup(reply_markup=None)
    await show_deadlines(update, context, new_message=True)


async def open_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «Открыть …» под объявлением 📣: объявление остаётся, раздел открывается новым экраном."""
    from bot.handlers.notifications import notify_menu
    from bot.handlers.progress import show_progress
    from bot.handlers.my_subjects import open_my_subjects
    from bot.handlers.schedule import show_schedule
    from bot.utils.ui import FORCE_NEW_KEY

    query = update.callback_query
    section = query.data.removeprefix("open_")
    await query.edit_message_reply_markup(reply_markup=None)
    context.chat_data[FORCE_NEW_KEY] = True
    if section == "deadlines":
        await show_deadlines(update, context)
    elif section == "notify":
        await notify_menu(update, context)
    elif section == "progress":
        await show_progress(update, context)
    elif section == "mysubj":
        await open_my_subjects(update, context, origin='main')
    elif section == "feedback":
        from bot.handlers.feedback import show_feedback
        await show_feedback(update, context)
    else:  # schedule
        await query.answer()
        await show_schedule(update, context)


async def show_subject_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Карточка предмета: deadlines_subj_<id>."""
    await _answer(update, context)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
        return

    await render_subject_card_screen(update, context, int(update.callback_query.data.rsplit("_", 1)[-1]))


async def render_subject_card_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, subject_id: int):
    """Карточка предмета по id — из кнопки и после /cancel в «✏️ Неточность?»."""
    from bot.services import feedback

    db = SessionLocal()
    try:
        subject = db.get(Subject, subject_id)
        if subject is None:
            text = "<i>нет информации</i>"
        else:
            deadlines = get_subject_deadlines(db, [subject_id])[subject_id]
            done = get_done_for_telegram_id(db, update.effective_user.id)
            text = render_subject_card(subject, deadlines, now_msk(), done=done)
    finally:
        db.close()

    keyboard = []
    if feedback.enabled() and subject is not None:
        keyboard.append([InlineKeyboardButton("✏️ Неточность?", callback_data=f"fb_write_s_{subject_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="deadlines")])
    await show_screen(update, context, text,
                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')


async def show_deadline_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """«📊 Все на графике»: фото на 2 недели + подпись; пустое окно — текстовый экран.
    В нетекущем модуле графика нет: подсказка и список дедлайнов (старая кнопка в чате)."""
    if not auth_service.is_user_verified(update.effective_user.id):
        await _answer(update, context)
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
        return

    now = now_msk()
    today = now.date()
    db = SessionLocal()
    try:
        is_current = M.get_view_by_telegram_id(db, update.effective_user.id, today).is_current
    finally:
        db.close()
    if not is_current:
        await _answer(update, context, M.CHART_ONLY_CURRENT)
        await show_deadlines(update, context)
        return
    await _answer(update, context)

    db = SessionLocal()
    try:
        deadlines = db.query(Deadline).options(joinedload(Deadline.subject)).all()
        deadlines = visible_deadlines(deadlines, get_selection_by_telegram_id(db, update.effective_user.id))
        had_in_window = bool(deadline_chart.split_items(deadlines, now)[0])
        # сданное (и жёсткий срок к нему) — ни на картинке, ни в подписи
        deadlines = without_done(deadlines, get_done_for_telegram_id(db, update.effective_user.id))
        in_window, later = deadline_chart.split_items(deadlines, now)
        if in_window:
            caption = deadline_chart.render_caption(in_window, later, today)
            key = deadline_chart.cache_key(in_window, today)
        else:
            empty_text = deadline_chart.render_empty(later, all_done=had_in_window)
    finally:
        db.close()

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("◀️ К предметам", callback_data="deadlines")],
        MAIN_MENU_BUTTON,
    ])
    if not in_window:
        await show_screen(update, context, empty_text, reply_markup=markup, parse_mode='HTML')
        return

    photo = _chart_file_ids.get(key)
    if photo is None:
        photo = await asyncio.to_thread(deadline_chart.render, in_window, today)
    sent = await show_photo_screen(update, context, photo, caption=caption,
                                   parse_mode='HTML', reply_markup=markup)
    if key not in _chart_file_ids and sent.photo:
        for old in [k for k in _chart_file_ids if not k.startswith(f"{today}:")]:
            del _chart_file_ids[old]  # вчерашние картинки больше не нужны
        _chart_file_ids[key] = sent.photo[-1].file_id
