"""
«📚 Мои предметы»: кто какие предметы видит — без БД.
Запуск: python -m pytest tests/test_selection.py   (или python tests/test_selection.py)
"""
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services.selection import (
    EVERYTHING, Selection, available_electives, describe, is_visible, visible_deadlines,
)

PMO = NS(id=1, name="Продвинутое машинное обучение", short_name="Продвинутое МО", is_elective=False)
VKR = NS(id=2, name="ВКР", short_name="📜 ВКР", is_elective=False)
RECSYS = NS(id=3, name="RecSys", short_name="", is_elective=True)
RL = NS(id=4, name="Обучение с подкреплением", short_name="", is_elective=True)
DEVOPS = NS(id=5, name="DevOps-2", short_name="", is_elective=True)
OLD = NS(id=6, name="Маголего прошлого модуля", short_name="", is_elective=True)
ALL = [PMO, VKR, RECSYS, RL, DEVOPS, OLD]


def visible(sel):
    return [s.name for s in ALL if is_visible(s, sel)]


def test_common_on_no_electives():
    assert visible(Selection(True, frozenset())) == ["Продвинутое машинное обучение", "ВКР"]


def test_common_on_with_elective():
    assert visible(Selection(True, frozenset({RECSYS.id}))) == [
        "Продвинутое машинное обучение", "ВКР", "RecSys"]


def test_common_off_with_elective():
    assert visible(Selection(False, frozenset({RECSYS.id}))) == ["RecSys"]


def test_nothing_selected():
    sel = Selection(False, frozenset())
    assert visible(sel) == [] and sel.is_empty
    assert not EVERYTHING.is_empty and visible(EVERYTHING) == [s.name for s in ALL]


def test_past_module_elective_stays_selected_but_not_offered():
    sel = Selection(True, frozenset({OLD.id}))
    assert "Маголего прошлого модуля" in visible(sel)          # отметка не теряется
    offered = available_electives([PMO, RL, RECSYS], [DEVOPS, RECSYS])
    assert [s.name for s in offered] == ["DevOps-2", "RecSys", "Обучение с подкреплением"]  # по алфавиту
    assert OLD not in offered


def test_deadlines_filtered_by_subject():
    deadlines = [NS(subject=PMO, title="№1"), NS(subject=RL, title="№1"), NS(subject=RECSYS, title="№1")]
    own = visible_deadlines(deadlines, Selection(True, frozenset({RECSYS.id})))
    assert [d.subject.name for d in own] == ["Продвинутое машинное обучение", "RecSys"]


def test_describe():
    chosen = [RECSYS, DEVOPS, RL]
    assert describe(Selection(True, frozenset()), chosen) == "Предметы: общие"
    assert describe(Selection(True, frozenset({3, 5})), chosen) == "Предметы: общие + DevOps-2, RecSys"
    assert describe(Selection(False, frozenset({3})), chosen) == "Предметы: RecSys"
    assert describe(Selection(True, frozenset({3, 4, 5})), chosen) == "Предметы: общие + 3 маголего"
    assert describe(Selection(False, frozenset()), chosen) == "Предметы не выбраны"


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"ok  {name}")
