"""
Раздел «📈 Мой прогресс»: отметки «сдано», оценки и накоп по формуле предмета.
Макет — docs/ui_progress.md, задача — docs/progress_developer.md.

callback_data:
  progress                      список предметов
  prog_s_<subject_id>           прогресс по предмету
  prog_d_<deadline_id>          нажатие на активность
  prog_g_<deadline_id>_<g×10>   оценка с клавиатуры
  prog_skip_<deadline_id>       «Пока нет»
  prog_undo_<deadline_id>       «↩️ Отменить» / «↩️ Не сдано»
  prog_clr_<deadline_id>        «🗑 Убрать оценку»
  prog_edit_<deadline_id>       «✏️ Изменить / Поставить оценку»
  prog_input_<deadline_id>      «✏️ Другая» — вход в ConversationHandler (ввод числа)
"""
import logging
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy.orm import joinedload
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.auth import auth_service
from bot.models import Deadline, Subject, User, UserProgress
from bot.services import progress as P
from bot.services.deadlines import build_subject_buttons, get_screen_subjects, get_subject_deadlines, now_msk
from bot.services.selection import get_available_electives, get_selection, is_visible
from bot.utils.database import SessionLocal
from bot.services import modules as M
from bot.utils.ui import answer, show_screen

logger = logging.getLogger(__name__)

GRADE_INPUT = 0
INPUT_KEY = "prog_input_deadline"
BACK_TO_LIST = [InlineKeyboardButton("◀️ Назад", callback_data="progress")]


def _id(query, index: int = -1) -> int:
    return int(query.data.split("_")[index])


def _user(db, telegram_id: int):
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


def _deadline(db, deadline_id: int):
    """Снимок дедлайна, видимого в прогрессе, или None (удалён при импорте / служебная строка).

    Снимок, а не ORM-объект: после commit/close сессии его можно спокойно рендерить.
    """
    d = db.get(Deadline, deadline_id, options=[joinedload(Deadline.subject)])
    if d is None or d.progress_role == 'hidden':
        return None
    subject = SimpleNamespace(name=d.subject.name, short_name=d.subject.short_name)
    return SimpleNamespace(id=d.id, subject_id=d.subject_id, kind=d.kind, title=d.title,
                           due_date=d.due_date, due_time=d.due_time, progress_role=d.progress_role,
                           subject=subject)


def _marks(db, user_id: int, deadline_ids) -> dict:
    if not deadline_ids:
        return {}
    rows = db.query(UserProgress).filter(UserProgress.user_id == user_id,
                                         UserProgress.deadline_id.in_(list(deadline_ids))).all()
    return {r.deadline_id: r for r in rows}


def _mark_row(db, user_id: int, deadline_id: int) -> UserProgress:
    row = db.query(UserProgress).filter_by(user_id=user_id, deadline_id=deadline_id).first()
    if row is None:
        row = UserProgress(user_id=user_id, deadline_id=deadline_id)
        db.add(row)
    return row


def _set_done(db, user_id: int, deadline_id: int, grade=None, keep_grade: bool = True):
    row = _mark_row(db, user_id, deadline_id)
    row.done_at = row.done_at or datetime.now()
    if not keep_grade or grade is not None:
        row.grade = grade
    row.updated_at = datetime.now()


def _unset(db, user_id: int, deadline_id: int):
    db.query(UserProgress).filter_by(user_id=user_id, deadline_id=deadline_id).delete()


async def _not_authorized(update: Update, context) -> bool:
    if auth_service.is_user_verified(update.effective_user.id):
        return False
    if update.callback_query:
        await update.callback_query.answer()
    await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
    return True


async def _missing(update: Update, context, toast: bool = True):
    if update.callback_query and toast:
        await update.callback_query.answer()
    await show_screen(update, context, "<i>нет информации</i>",
                      reply_markup=InlineKeyboardMarkup([BACK_TO_LIST]), parse_mode='HTML')


# ---------------------------------------------------------------------------
# Экраны
# ---------------------------------------------------------------------------

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Список предметов: кнопка «📈 Мой прогресс», /progress, /subjects."""
    if await _not_authorized(update, context):
        return
    await answer(update, context)

    from bot.handlers.my_subjects import choose_electives_hint, empty_text, entry_button

    now = now_msk()
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        selection = get_selection(db, user)
        view = M.get_view(db, user, now.date())
        # Набор — как в «Дедлайнах» смотримого модуля (прошедший модуль — через «🗂 Модуль»),
        # только отмеченные в «📚 Мои предметы»; отметки по снятым маголего не удаляются
        subjects = {s.id: s for s in get_screen_subjects(db, view.view, now.date())
                    if is_visible(s, selection)}
        hint = choose_electives_hint(selection, get_available_electives(db, view.view, now.date()))
        deadlines = get_subject_deadlines(db, subjects)
        order = build_subject_buttons(subjects.values(), deadlines, now, mark_urgent=False,
                                      by_name=not view.is_current)
        all_ids = [d.id for ds in deadlines.values() for d in ds]
        marks = _marks(db, user.id, all_ids) if user else {}
        lines = [P.render_list_line(subjects[sid], deadlines.get(sid, []), marks) for sid, _ in order]
        buttons = [[InlineKeyboardButton(P.subject_label(subjects[sid]), callback_data=f"prog_s_{sid}")]
                   for sid, _ in order]
    finally:
        db.close()

    text = P.render_list_screen(lines)
    if selection.is_empty:
        text, buttons = empty_text("📈 <b>Мой прогресс</b>"), [entry_button('progress')]
    elif hint:
        buttons.append(entry_button('progress', "📚 Выбрать маголего"))
    text = M.with_banner(text, view.banner)
    if back := view.back_button('progress'):
        buttons.append(back)
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")])
    await show_screen(update, context, text,
                      reply_markup=InlineKeyboardMarkup(buttons), parse_mode='HTML')


async def _show_subject(update: Update, context, subject_id: int, notice: str = ""):
    db = SessionLocal()
    try:
        subject = db.get(Subject, subject_id)
        user = _user(db, update.effective_user.id)
        if subject is None or user is None:
            await _missing(update, context, toast=False)
            return
        deadlines = get_subject_deadlines(db, [subject_id])[subject_id]
        marks = _marks(db, user.id, [d.id for d in deadlines])
        text = P.render_subject_screen(subject, deadlines, marks, notice)
        rows = [[InlineKeyboardButton(t, callback_data=f"prog_d_{did}") for t, did in row]
                for row in P.activity_buttons(deadlines, marks)]
    finally:
        db.close()
    rows.append(BACK_TO_LIST)
    await show_screen(update, context, text, reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')


def _grade_keyboard(deadline_id: int, edit: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(str(g), callback_data=f"prog_g_{deadline_id}_{g * 10}") for g in row]
            for row in P.GRADE_BUTTONS]
    rows[-1].append(InlineKeyboardButton("✏️ Другая", callback_data=f"prog_input_{deadline_id}"))
    if edit:
        rows.append([InlineKeyboardButton("◀️ Назад", callback_data=f"prog_d_{deadline_id}")])
    else:
        rows.append([InlineKeyboardButton("Пока нет", callback_data=f"prog_skip_{deadline_id}"),
                     InlineKeyboardButton("↩️ Отменить", callback_data=f"prog_undo_{deadline_id}")])
    return InlineKeyboardMarkup(rows)


async def _show_activity(update: Update, context, d: Deadline, grade):
    rows = []
    if grade is not None:
        rows.append([InlineKeyboardButton("✏️ Изменить оценку", callback_data=f"prog_edit_{d.id}")])
        rows.append([InlineKeyboardButton("🗑 Убрать оценку", callback_data=f"prog_clr_{d.id}")])
    else:
        rows.append([InlineKeyboardButton("✏️ Поставить оценку", callback_data=f"prog_edit_{d.id}")])
    rows.append([InlineKeyboardButton("↩️ Не сдано", callback_data=f"prog_undo_{d.id}")])
    rows.append([InlineKeyboardButton("◀️ Назад", callback_data=f"prog_s_{d.subject_id}")])
    await show_screen(update, context, P.render_activity_screen(d, grade),
                      reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')


# ---------------------------------------------------------------------------
# Callback'и
# ---------------------------------------------------------------------------

async def progress_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """prog_s_<subject_id>"""
    if await _not_authorized(update, context):
        return
    await update.callback_query.answer()
    await _show_subject(update, context, _id(update.callback_query))


async def progress_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """prog_d / prog_g / prog_skip / prog_undo / prog_clr / prog_edit — одна точка входа."""
    if await _not_authorized(update, context):
        return
    query = update.callback_query
    action = query.data.split("_")[1]
    deadline_id = _id(query, 2)

    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        d = _deadline(db, deadline_id)
        if user is None or d is None:
            await _missing(update, context)
            return
        label = P.short_label(d)
        row = db.query(UserProgress).filter_by(user_id=user.id, deadline_id=d.id).first()
        done = row is not None and row.done_at is not None
        grade = row.grade if row is not None else None
        screen, toast = "subject", None

        if action == "d":
            if d.kind == 'milestone':          # этапы ВКР — только переключатель
                if done:
                    _unset(db, user.id, d.id)
                else:
                    _set_done(db, user.id, d.id)
                toast = "Отметка снята" if done else "Отмечено"
            elif done:
                screen = "activity"
            else:
                _set_done(db, user.id, d.id)
                screen = "grade"
        elif action == "g":
            grade = Decimal(_id(query)) / 10
            _set_done(db, user.id, d.id, grade)
            toast = f"{label}: {P.fmt_grade(grade)}"
        elif action == "skip":
            _set_done(db, user.id, d.id)
            toast = f"{label}: сдано"
        elif action == "undo":
            _unset(db, user.id, d.id)
            toast = f"{label}: не сдано"
        elif action == "clr":
            _set_done(db, user.id, d.id, None, keep_grade=False)
            grade, screen = None, "activity"
        elif action == "edit":
            screen = "edit"
        db.commit()
    finally:
        db.close()

    await query.answer(toast)
    if screen == "grade":
        await show_screen(update, context, P.render_grade_screen(d),
                          reply_markup=_grade_keyboard(d.id, edit=False), parse_mode='HTML')
    elif screen == "edit":
        await show_screen(update, context, P.render_grade_screen(d, grade, edit=True),
                          reply_markup=_grade_keyboard(d.id, edit=True), parse_mode='HTML')
    elif screen == "activity":
        await _show_activity(update, context, d, grade)
    else:
        await _show_subject(update, context, d.subject_id)


# ---------------------------------------------------------------------------
# Ввод оценки вручную: prog_input_<id> → число → экран предмета
# ---------------------------------------------------------------------------

async def progress_input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _not_authorized(update, context):
        return ConversationHandler.END
    query = update.callback_query
    db = SessionLocal()
    try:
        d = _deadline(db, _id(query))
    finally:
        db.close()
    if d is None:
        await _missing(update, context)
        return ConversationHandler.END
    await query.answer()
    context.user_data[INPUT_KEY] = d.id
    await show_screen(update, context, P.render_input_prompt(d), parse_mode='HTML')
    return GRADE_INPUT


async def progress_input_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    deadline_id = context.user_data.get(INPUT_KEY)
    grade = P.parse_grade(update.message.text)
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        d = _deadline(db, deadline_id) if deadline_id else None
        if user is None or d is None:
            context.user_data.pop(INPUT_KEY, None)
            await _missing(update, context)
            return ConversationHandler.END
        if grade is not None:
            _set_done(db, user.id, d.id, grade)
            db.commit()
    finally:
        db.close()

    if grade is None:
        await show_screen(update, context, P.render_input_prompt(d, error=True), parse_mode='HTML')
        return GRADE_INPUT
    context.user_data.pop(INPUT_KEY, None)
    notice = f"Сохранено: {P.short_label(d)} — {P.fmt_grade(grade)}"
    await _show_subject(update, context, d.subject_id, notice=notice)
    return ConversationHandler.END


async def progress_input_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cancel — экран предмета без «Сохранено», отметка «сдано» остаётся."""
    deadline_id = context.user_data.pop(INPUT_KEY, None)
    db = SessionLocal()
    try:
        d = _deadline(db, deadline_id) if deadline_id else None
        subject_id = d.subject_id if d is not None else None
    finally:
        db.close()
    if subject_id is None:
        await _missing(update, context)
    else:
        await _show_subject(update, context, subject_id)
    return ConversationHandler.END
