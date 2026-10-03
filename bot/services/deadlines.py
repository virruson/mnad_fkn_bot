"""
Дедлайны: выборки из БД и тексты экранов (Telegram HTML).

Макеты — docs/ui_deadlines.md. Всё, что зависит от «сегодня», принимает now/today
параметром, чтобы экраны и рассылку можно было проверить на любой дате.
"""
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from html import escape

import pytz

from bot.models import Deadline, LessonType, Module, Schedule, Subject

MOSCOW_TZ = pytz.timezone('Europe/Moscow')
END_OF_DAY = time(23, 59)
URGENT_DAYS = 2          # «❗», если осталось меньше 2 дней (сегодня или завтра)
DIGEST_OFFSETS = (1, 2, 4)
BLOCK_MAX_LINES = 4
NAME_LIMIT = 25
NO_INFO = "<i>нет информации</i>"
WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
NOT_A_SUBJECT = ('Встреча',)  # типы занятий, которые не делают запись предметом

KIND_BLOCKS = (          # порядок блоков в карточке
    ('hw', '📝', 'ДЗ'),
    ('quiz', '🧠', 'Квизы/КР'),   # в таблице курса квизы и КР в одной колонке
    ('test', '📋', 'КР'),
    ('exam', '🎓', 'Экзамен'),
    ('milestone', '📌', 'Этапы'),  # ВКР и прочие этапы без ДЗ/экзамена
)
KIND_IN_DIGEST = {'hw': 'ДЗ', 'quiz': 'квиз/КР', 'test': 'КР', 'exam': 'экзамен', 'milestone': ''}
OPTIONAL_KINDS = {'test', 'milestone'}  # блок показываем, только если в нём что-то есть


def now_msk() -> datetime:
    """Текущее время МСК без tzinfo — в БД даты и время хранятся «наивными»."""
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Свойства одного дедлайна
# ---------------------------------------------------------------------------

def due_at(d: Deadline) -> datetime:
    return datetime.combine(d.due_date, d.due_time or END_OF_DAY)


def is_past(d: Deadline, now: datetime) -> bool:
    return due_at(d) < now


def days_left(d: Deadline, today: date) -> int:
    return (d.due_date - today).days


def is_urgent(d: Deadline, now: datetime) -> bool:
    return not is_past(d, now) and days_left(d, now.date()) < URGENT_DAYS


def display_name(subject: Subject) -> str:
    """Имя для кнопок и утреннего сообщения: short_name, полное или обрезка по слову."""
    if subject.short_name:
        return subject.short_name.strip()
    name = subject.name.strip()
    if len(name) <= NAME_LIMIT:
        return name
    cut = name[:NAME_LIMIT - 1]
    if name[NAME_LIMIT - 1] != ' ' and ' ' in cut:
        cut = cut[:cut.rfind(' ')]
    return cut.rstrip(' ,.:;—-') + '…'


# ---------------------------------------------------------------------------
# Выборки
# ---------------------------------------------------------------------------

def get_current_module(db, today: date):
    return (db.query(Module)
            .filter(Module.start_date <= today, Module.end_date >= today)
            .order_by(Module.start_date.desc())
            .first())


def get_module_subjects(db, module: Module) -> list:
    """Предметы модуля: DISTINCT subject из schedule в пределах дат модуля (без встреч)."""
    subject_ids = (db.query(Schedule.subject_id)
                   .join(LessonType, Schedule.lesson_type_id == LessonType.id)
                   .filter(Schedule.lesson_date.between(module.start_date, module.end_date),
                           LessonType.name.notin_(NOT_A_SUBJECT))
                   .distinct())
    return db.query(Subject).filter(Subject.id.in_(subject_ids)).all()


def get_screen_subjects(db, today: date) -> list:
    """Предметы экрана «Дедлайны»: текущий модуль + всё, где есть будущие дедлайны (ВКР и т.п.)."""
    module = get_current_module(db, today)
    subjects = {s.id: s for s in (get_module_subjects(db, module) if module else [])}
    with_upcoming = (db.query(Subject).join(Deadline, Deadline.subject_id == Subject.id)
                     .filter(Deadline.due_date >= today).distinct().all())
    for s in with_upcoming:
        subjects.setdefault(s.id, s)
    return list(subjects.values())


def get_subject_deadlines(db, subject_ids) -> dict:
    """{subject_id: [Deadline, ...]} отсортировано по сроку."""
    result = defaultdict(list)
    if not subject_ids:
        return result
    rows = (db.query(Deadline)
            .filter(Deadline.subject_id.in_(list(subject_ids)))
            .all())
    for d in sorted(rows, key=due_at):
        result[d.subject_id].append(d)
    return result


# ---------------------------------------------------------------------------
# Экран «⏳ Дедлайны»: список предметов
# ---------------------------------------------------------------------------

def build_subject_buttons(subjects, deadlines_by_subject: dict, now: datetime) -> list:
    """
    [(subject_id, текст_кнопки), ...] в порядке: срочные, дальше по ближайшему
    дедлайну, предметы без будущих дедлайнов — в конце. ВКР (только этапы) всегда
    последняя: «❗» получает, но место не меняет.
    """
    items = []
    for s in subjects:
        own = deadlines_by_subject.get(s.id, [])
        pinned_last = bool(own) and all(d.kind == 'milestone' for d in own)
        upcoming = [d for d in own if not is_past(d, now)]
        nearest = min((due_at(d) for d in upcoming), default=None)
        urgent = any(is_urgent(d, now) for d in upcoming)
        items.append((pinned_last, not urgent, nearest is None, nearest or datetime.max,
                      display_name(s), s.id, urgent))
    items.sort()
    return [(sid, f"❗ {name}" if urgent else name) for *_, name, sid, urgent in items]


def render_deadlines_screen(has_subjects: bool) -> str:
    hint = "Выберите предмет · ❗ — меньше 2 дней" if has_subjects else NO_INFO
    return f"⏳ <b>Дедлайны</b>\n{hint}"


# ---------------------------------------------------------------------------
# Карточка предмета
# ---------------------------------------------------------------------------

def _format_due(d: Deadline) -> str:
    s = d.due_date.strftime('%d.%m')
    if d.due_time and d.due_time != END_OF_DAY:
        s += f", {d.due_time.strftime('%H:%M')}"
    return s


def format_deadline_line(d: Deadline, now: datetime) -> str:
    parts = [escape(d.title), f"<b>{_format_due(d)}</b>"]
    if d.kind == 'milestone':
        parts.reverse()  # у этапов ВКР длинные названия — дата впереди
    base = " · ".join(filter(None, parts))
    if is_past(d, now):
        return f"<s>{base}</s>"
    left = days_left(d, now.date())
    remain = "сегодня" if left == 0 else f"осталось {left} дн"
    line = f"{base} · <i>{remain}</i>"
    return f"❗ {line}" if left < URGENT_DAYS else line


def _render_block(deadlines: list, now: datetime) -> list:
    if not deadlines:
        return [NO_INFO]
    past = [d for d in deadlines if is_past(d, now)]
    hidden = max(0, min(len(past), len(deadlines) - BLOCK_MAX_LINES))
    shown = deadlines[hidden:]  # список отсортирован, самые старые прошедшие — в начале
    lines = [format_deadline_line(d, now) for d in shown]
    if hidden:
        lines.append(f"<i>ещё {hidden} прошедших</i>")
    return lines


def render_subject_card(subject: Subject, deadlines: list, now: datetime) -> str:
    title = f"<b>{escape(subject.name)}</b>"
    if not deadlines:  # все блоки пусты — одна строка (+ формула, если есть)
        parts = [title, NO_INFO]
        if subject.grading_formula:
            parts.append(_render_formula(subject))
        return "\n\n".join(parts)

    by_kind = defaultdict(list)
    for d in sorted(deadlines, key=due_at):
        by_kind[d.kind].append(d)

    only_milestones = bool(deadlines) and set(by_kind) == {'milestone'}
    parts = [title]
    for kind, icon, label in KIND_BLOCKS:
        if kind in OPTIONAL_KINDS and not by_kind[kind]:
            continue
        if only_milestones and kind != 'milestone':
            continue  # у ВКР нет ДЗ/квизов/экзамена — пустые блоки не нужны
        parts.append("\n".join([f"{icon} <b>{label}</b>", *_render_block(by_kind[kind], now)]))

    if subject.grading_formula or not only_milestones:
        parts.append(_render_formula(subject))
    return "\n\n".join(parts)


def _render_formula(subject: Subject) -> str:
    formula = (f"<code>Итог = {escape(subject.grading_formula.strip())}</code>"
               if subject.grading_formula else NO_INFO)
    return f"🧮 <b>Формула</b>\n{formula}"


def _digest_title(d: Deadline) -> str:
    """Этап ВКР в рассылке — со строчной буквы («ВКР — выбор …»), аббревиатуры не трогаем."""
    title = d.title.strip()
    first_word = title.split(' ', 1)[0]
    if d.kind == 'milestone' and title and not first_word.isupper():
        title = title[0].lower() + title[1:]
    return title


# ---------------------------------------------------------------------------
# Утреннее сообщение (за 4, 2 и 1 день)
# ---------------------------------------------------------------------------

def get_digest_deadlines(db, today: date) -> list:
    dates = [today + timedelta(days=n) for n in DIGEST_OFFSETS]
    return db.query(Deadline).filter(Deadline.due_date.in_(dates)).all()


def render_deadline_digest(deadlines: list, today: date):
    """Текст сообщения или None, если в этот день напоминать не о чем."""
    groups = defaultdict(list)
    for d in deadlines:
        n = days_left(d, today)
        if n in DIGEST_OFFSETS:
            groups[n].append(d)
    if not groups:
        return None

    titles = {1: "❗ <b>Завтра</b>", 2: "<b>Через 2 дня</b>", 4: "<b>Через 4 дня</b>"}
    parts = ["⏳ <b>Дедлайны</b>"]
    for n in DIGEST_OFFSETS:
        if not groups[n]:
            continue
        day = today + timedelta(days=n)
        lines = [f"{titles[n]} · {WEEKDAYS[day.weekday()]} {day.strftime('%d.%m')}"]
        for d in sorted(groups[n], key=lambda x: (display_name(x.subject), due_at(x))):
            what = " ".join(filter(None, [KIND_IN_DIGEST[d.kind], escape(_digest_title(d))]))
            lines.append(f"{escape(display_name(d.subject))} — {what}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)
