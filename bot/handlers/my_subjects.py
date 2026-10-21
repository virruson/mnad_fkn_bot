"""
Экран «📚 Мои предметы»: «Общие предметы» + маголего, множественный выбор.
Задача — docs/magolego_developer.md, п. 4.

callback_data:
  mysubj                    открыть из «🔔 Уведомлений» (◀️ Назад → уведомления)
  mysubj_from_deadlines     открыть из «⏳ Дедлайнов»   (◀️ Назад → дедлайны)
  mysubj_from_progress      открыть из «📈 Моего прогресса» (◀️ Назад → прогресс)
  open_mysubj               кнопка под объявлением 📣 (◀️ Назад → главное меню), см. open_section
  mysubj_common             переключить «Общие предметы»
  mysubj_el_<subject_id>    переключить маголего
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.handlers.auth import auth_service
from bot.models import Subject, User
from bot.services.deadlines import display_name, get_screen_subjects, now_msk
from bot.services.scheduler import replan_reminders_for_user
from bot.services.selection import get_available_electives, get_selection, toggle_elective
from bot.utils.database import SessionLocal
from bot.services import modules as M
from bot.utils.ui import answer, show_screen

BACK_KEY = "mysubj_back"
BACK_TARGETS = {'notify': "notify_menu", 'deadlines': "deadlines", 'progress': "progress", 'main': "back_to_menu"}
TITLE = "📚 <b>Мои предметы</b>"
NO_INFO = "<i>нет информации</i>"
TEXT = ("📚 <b>Мои предметы</b>\n"
        "Уведомления, расписание, дедлайны, график и прогресс — только по отмеченным.\n"
        "Маголего отметьте те, на которые записаны.")
NO_ELECTIVES = "<i>маголего в этом модуле нет</i>"
COMMON_LABEL = "Общие предметы"


def entry_button(origin: str, label: str = "📚 Мои предметы") -> list:
    """Кнопка-ряд для других разделов: откроет экран и вернёт обратно в origin."""
    data = "mysubj" if origin == 'notify' else f"mysubj_from_{origin}"
    return [InlineKeyboardButton(label, callback_data=data)]


def _user(db, telegram_id):
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


async def render(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        if user is None:
            await show_screen(update, context, "❌ Пользователь не найден. Авторизуйтесь заново.")
            return
        sel = get_selection(db, user)
        today = now_msk().date()
        view = M.get_view(db, user, today)
        electives = get_available_electives(db, view.view, today)
        # будущий модуль, где ещё нет ни занятий, ни дедлайнов, — «нет информации» без переключателей
        unknown = not view.is_current and not get_screen_subjects(db, view.view, today)
        rows = [] if unknown else [[InlineKeyboardButton(f"{'✅' if sel.common else '☐'} {COMMON_LABEL}",
                                                         callback_data="mysubj_common")]]
        rows += [[InlineKeyboardButton(f"{'✅' if s.id in sel.elective_ids else '☐'} {display_name(s)}",
                                       callback_data=f"mysubj_el_{s.id}")] for s in electives]
    finally:
        db.close()

    back = BACK_TARGETS.get(context.user_data.get(BACK_KEY), "notify_menu")
    if back_now := view.back_button('mysubj'):
        rows.append(back_now)
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data=back)])
    if unknown:
        text = f"{TITLE}\n{NO_INFO}"
    else:
        text = TEXT if electives else f"{TEXT}\n\n{NO_ELECTIVES}"
    text = M.with_banner(text, view.banner)
    await show_screen(update, context, text, reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')


async def open_my_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE, origin: str = None):
    """mysubj / mysubj_from_<deadlines|progress>; из объявления — origin='main'."""
    query = update.callback_query
    if origin is None:
        data = query.data
        origin = data.removeprefix("mysubj_from_") if data.startswith("mysubj_from_") else 'notify'
    await answer(update, context)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
        return
    context.user_data[BACK_KEY] = origin
    await render(update, context)


async def toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """mysubj_common / mysubj_el_<id>: переключить и сразу перерисовать экран."""
    query = update.callback_query
    if not auth_service.is_user_verified(update.effective_user.id):
        await query.answer()
        await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
        return

    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        if user is None:
            await query.answer()
            return
        if query.data == "mysubj_common":
            user.common_enabled = not user.common_enabled
            label, on = COMMON_LABEL, user.common_enabled
        else:
            subject = db.get(Subject, int(query.data.rsplit("_", 1)[-1]))
            if subject is None or not subject.is_elective:
                await query.answer()
                await render(update, context)
                return
            label, on = display_name(subject), toggle_elective(db, user, subject.id)
        db.commit()
    finally:
        db.close()

    # напоминания на сегодня — под новый выбор
    replan_reminders_for_user(context.job_queue, update.effective_user.id)
    await query.answer(f"{label}: {'вкл' if on else 'выкл'}")
    await render(update, context)


def choose_electives_hint(sel, available) -> bool:
    """Показывать ли «📚 Выбрать маголего»: общие есть, маголего не выбраны, а выбрать есть из чего."""
    return sel.common and not sel.elective_ids and not sel.everything and bool(available)


def empty_text(title: str) -> str:
    return f"{title}\n<i>предметы не выбраны</i>"
