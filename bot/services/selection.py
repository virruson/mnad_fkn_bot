"""
«📚 Мои предметы»: какие предметы видит студент. Задача — docs/magolego_developer.md.

Маголего — свойство предмета (subjects.is_elective). Выбор студента — набор:
«Общие предметы» вкл/выкл (users.common_enabled) + его маголего (user_electives).

Правило видимости:
  маголего виден, если студент его отметил;
  любой другой предмет (ВКР, «Семинар наставника», встречи) — если включены «Общие предметы».

Вся фильтрация (рассылки, расписание, дедлайны, график, прогресс) идёт только через этот модуль.
"""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, false, literal, or_, true

from bot.models import Deadline, Subject, User, UserElective


@dataclass(frozen=True)
class Selection:
    common: bool
    elective_ids: frozenset = field(default_factory=frozenset)
    everything: bool = False   # неавторизованный / нет записи users — без фильтра

    @property
    def is_empty(self) -> bool:
        return not self.everything and not self.common and not self.elective_ids


EVERYTHING = Selection(common=True, everything=True)


def get_selection(db, user) -> Selection:
    if user is None:
        return EVERYTHING
    ids = db.query(UserElective.subject_id).filter(UserElective.user_id == user.id).all()
    return Selection(common=bool(user.common_enabled), elective_ids=frozenset(i for (i,) in ids))


def get_selection_by_telegram_id(db, telegram_id) -> Selection:
    user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
    return get_selection(db, user)


def is_visible(subject, sel: Selection) -> bool:
    if sel.everything:
        return True
    if subject.is_elective:
        return subject.id in sel.elective_ids
    return sel.common


def visible_subjects(subjects, sel: Selection) -> list:
    return [s for s in subjects if is_visible(s, sel)]


def visible_deadlines(deadlines, sel: Selection) -> list:
    return [d for d in deadlines if is_visible(d.subject, sel)]


def subject_filter(sel: Selection):
    """SQLAlchemy-условие на Subject — для запросов по Schedule / Deadline (с join на Subject)."""
    if sel.everything:
        return true()
    elective = Subject.id.in_(list(sel.elective_ids)) if sel.elective_ids else false()
    return or_(and_(Subject.is_elective.is_(False), literal(sel.common)), elective)


def available_electives(module_subjects, upcoming_subjects) -> list:
    """Маголего текущего модуля или с будущими дедлайнами, по алфавиту короткого имени."""
    from bot.services.deadlines import display_name
    found = {s.id: s for s in [*module_subjects, *upcoming_subjects] if s.is_elective}
    return sorted(found.values(), key=lambda s: display_name(s).casefold())


def get_available_electives(db, today: date) -> list:
    """Маголего для выбора: занятия в текущем модуле или будущие дедлайны (как get_screen_subjects).
    Маголего прошлых модулей не предлагаются, но и из выбора не удаляются."""
    from bot.services.deadlines import get_current_module, get_module_subjects
    module = get_current_module(db, today)
    module_subjects = get_module_subjects(db, module) if module else []
    upcoming = (db.query(Subject).join(Deadline, Deadline.subject_id == Subject.id)
                .filter(Deadline.due_date >= today, Subject.is_elective.is_(True)).distinct().all())
    return available_electives(module_subjects, upcoming)


def toggle_elective(db, user, subject_id: int) -> bool:
    """Переключает маголего у студента. Возвращает новое состояние (True — отмечено)."""
    row = db.get(UserElective, (user.id, subject_id))
    if row is not None:
        db.delete(row)
        return False
    db.add(UserElective(user_id=user.id, subject_id=subject_id))
    return True


def describe(sel: Selection, electives) -> str:
    """Строка для меню уведомлений: «Предметы: общие + RecSys, DevOps-2»."""
    from bot.services.deadlines import display_name
    if sel.is_empty:
        return "Предметы не выбраны"
    names = sorted((display_name(s) for s in electives if s.id in sel.elective_ids), key=str.casefold)
    if len(names) > 2:
        names = [f"{len(names)} маголего"]
    parts = (["общие"] if sel.common else []) + ([", ".join(names)] if names else [])
    return "Предметы: " + " + ".join(parts)
