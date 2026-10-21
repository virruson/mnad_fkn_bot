"""
Модули: какой текущий и какой студент смотрит. Задача — docs/module_switch_developer.md, макет — docs/ui_module.md.

Текущий модуль — по дате (уведомления и рассылки работают только по нему).
Смотримый модуль — выбор студента в «🗂 Модуль»: переключает дедлайны, прогресс,
«Мои предметы» и расписание. Рассылки и напоминания get_view_module НЕ вызывают.

Чистые функции (current_of, view_of, module_status, module_subject_ids, weeks…) — без БД, для тестов.
"""
from datetime import date, timedelta
from typing import Literal

from bot.models import Module

ICON = "🗂"
STATUS_WORDS = {'current': "текущий", 'archive': "архив", 'upcoming': "скоро"}
SECTIONS = ('deadlines', 'progress', 'mysubj', 'schedule')   # module_now_<section>
WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']


# ---------------------------------------------------------------------------
# Текущий и смотримый модуль
# ---------------------------------------------------------------------------

def list_modules(db) -> list:
    return db.query(Module).order_by(Module.start_date).all()


def current_of(modules, today: date):
    """Модуль, куда попадает today; каникулы — ближайший будущий; после последнего — последний прошедший."""
    inside = [m for m in modules if m.start_date <= today <= m.end_date]
    if inside:
        return max(inside, key=lambda m: m.start_date)
    future = [m for m in modules if m.start_date > today]
    if future:
        return min(future, key=lambda m: m.start_date)
    return max(modules, key=lambda m: m.end_date, default=None)


def view_of(modules, current, view_id, base_id):
    """Выбор студента действует, пока не сменился текущий модуль (base_id) — иначе текущий."""
    if view_id is None or current is None or base_id != current.id:
        return current
    return next((m for m in modules if m.id == view_id), current)


def get_current_module(db, today: date):
    return current_of(list_modules(db), today)


def get_view_module(db, user, today: date):
    modules = list_modules(db)
    current = current_of(modules, today)
    if user is None:
        return current
    return view_of(modules, current, user.view_module_id, user.view_module_base_id)


def module_status(module, today: date, current=None) -> Literal['current', 'archive', 'upcoming']:
    """current — текущий модуль (в каникулы это ближайший будущий, а не «скоро»)."""
    if current is not None and module.id == current.id:
        return 'current'
    if current is None and module.start_date <= today <= module.end_date:
        return 'current'
    return 'archive' if module.end_date < today else 'upcoming'


def status_word(module, today: date, current) -> str:
    return STATUS_WORDS[module_status(module, today, current)]


class View:
    """Что открыто у студента: view — смотримый модуль, current — текущий (оба могут быть None)."""

    def __init__(self, modules, current, view, today):
        self.modules, self.current, self.view, self.today = modules, current, view, today

    @property
    def is_current(self) -> bool:
        return self.view is None or self.current is None or self.view.id == self.current.id

    @property
    def banner(self):
        return module_banner(self.view, self.current, self.today)

    def back_button(self, section: str):
        """[ 🗂 Вернуться в 6 модуль ] — только в нетекущем модуле."""
        from telegram import InlineKeyboardButton
        if self.is_current:
            return None
        return [InlineKeyboardButton(f"{ICON} Вернуться в {self.current.name}",
                                     callback_data=f"module_now_{section}")]


def get_view(db, user, today: date) -> View:
    modules = list_modules(db)
    current = current_of(modules, today)
    view = current if user is None else view_of(modules, current, user.view_module_id,
                                                user.view_module_base_id)
    return View(modules, current, view, today)


def get_view_by_telegram_id(db, telegram_id, today: date) -> View:
    from bot.models import User
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    return get_view(db, user, today)


def set_view(user, module, current):
    """Записать выбор: текущий — NULL/NULL, иначе id и база для автосброса."""
    if current is None or module.id == current.id:
        user.view_module_id, user.view_module_base_id = None, None
    else:
        user.view_module_id, user.view_module_base_id = module.id, current.id


# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

def module_banner(view, current, today: date):
    """«🗂 Открыт <b>5 модуль</b> · архив» — только для нетекущего модуля, иначе None."""
    if view is None or current is None or view.id == current.id:
        return None
    return f"{ICON} Открыт <b>{view.name}</b> · {status_word(view, today, current)}"


def with_banner(text: str, banner) -> str:
    return f"{banner}\n{text}" if banner else text


def menu_label(view, current, today: date) -> str:
    return f"{ICON} {view.name} · {status_word(view, today, current)}"


def dates_label(module) -> str:
    return f"{module.start_date:%d.%m} – {module.end_date:%d.%m}"


def choose_screen_text(modules) -> str:
    lines = [f"{m.name} · {dates_label(m)}" for m in modules]
    return (f"{ICON} <b>Модуль</b>\n"
            "Переключает дедлайны, прогресс, «Мои предметы» и расписание. "
            "Уведомления всегда приходят по текущему модулю.\n\n" + "\n".join(lines))


def toast_opened(module, today: date, current) -> str:
    return f"Открыт {module.name} · {status_word(module, today, current)}"


def toast_already(module) -> str:
    return f"{module.name} уже открыт"


CHART_ONLY_CURRENT = "График — только в текущем модуле"


# ---------------------------------------------------------------------------
# Предметы модуля
# ---------------------------------------------------------------------------

def module_subject_ids(module, today: date, is_current: bool, lesson_subject_ids, deadlines) -> set:
    """Предметы модуля: занятия в его датах + дедлайны в его датах;
    у текущего — ещё всё с будущими дедлайнами (ВКР и т. п.)."""
    ids = set(lesson_subject_ids)
    for d in deadlines:
        in_module = module is not None and module.start_date <= d.due_date <= module.end_date
        if in_module or (is_current and d.due_date >= today):
            ids.add(d.subject_id)
    return ids


def is_latin(name: str) -> bool:
    first = next((ch for ch in name if ch.isalpha()), '')
    return first.isascii()


def name_key(name: str):
    """Сортировка по названию: сначала кириллица, потом латиница."""
    return is_latin(name), name.casefold()


# ---------------------------------------------------------------------------
# Расписание по неделям
# ---------------------------------------------------------------------------

def week_count(module) -> int:
    first = module.start_date - timedelta(days=module.start_date.weekday())
    last = module.end_date - timedelta(days=module.end_date.weekday())
    return (last - first).days // 7 + 1


def week_bounds(module, n: int):
    """Неделя n (с 1): понедельник недели начала модуля + 7·(n−1); (пн, вс)."""
    monday = module.start_date - timedelta(days=module.start_date.weekday()) + timedelta(weeks=n - 1)
    return monday, monday + timedelta(days=6)


def nearest_week(module, today: date) -> int:
    """Неделя модуля, ближайшая к today: в архиве — последняя, в будущем — первая."""
    total = week_count(module)
    first_monday, _ = week_bounds(module, 1)
    n = (today - first_monday).days // 7 + 1
    return min(max(n, 1), total)


def weeks_word(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} неделя"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return f"{n} недели"
    return f"{n} недель"


def schedule_screen_text(module, banner, has_lessons: bool) -> str:
    head = with_banner("📅 <b>Расписание</b>", banner)
    if not has_lessons:
        return f"{head}\n{module.name} · {dates_label(module)}\n<i>нет информации</i>"
    return f"{head}\n{module.name} · {dates_label(module)} · {weeks_word(week_count(module))}"


def render_week(module, n: int, lessons, banner) -> str:
    """lessons — [(дата, время, короткое название, тип)] по порядку. Пустые дни не выводятся."""
    monday, sunday = week_bounds(module, n)
    head = with_banner(f"📅 <b>Неделя {n} из {week_count(module)}</b> · {monday:%d.%m} – {sunday:%d.%m}",
                       banner)
    if not lessons:
        return f"{head}\n<i>занятий нет</i>"
    days, order = {}, []
    for day, at, name, kind in lessons:
        if day not in days:
            days[day] = []
            order.append(day)
        days[day].append(f"{at:%H:%M} {name} · {(kind or '').lower()}".rstrip(" ·"))
    blocks = [f"<b>{WEEKDAYS[d.weekday()]} {d:%d.%m}</b>\n" + "\n".join(days[d]) for d in order]
    return head + "\n\n" + "\n\n".join(blocks)
