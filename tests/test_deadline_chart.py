"""
График дедлайнов: склейка штрафных пар, окно 2 недели, подпись к фото, PNG.
Запуск: python -m pytest tests/test_deadline_chart.py   (или python tests/test_deadline_chart.py)
"""
import sys
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services import deadline_chart as C

NOW = datetime(2026, 10, 6, 12, 0)
TS = NS(id=1, name="Анализ и прогнозирование временных рядов", short_name="Временные ряды")
PMO = NS(id=2, name="Продвинутое машинное обучение", short_name="Продвинутое МО")
VKR = NS(id=3, name="ВКР", short_name="📜 ВКР")
DL = NS(id=4, name="Глубинное обучение и нейронные сети", short_name="Глубинное обучение")
_ids = iter(range(1, 1000))


def dl(subject, kind, title, day, due_time=None):
    return NS(id=next(_ids), subject_id=subject.id, subject=subject, kind=kind, title=title,
              due_date=date(2026, *day), due_time=due_time)


DATA = [
    dl(TS, 'quiz', '№7–8', (10, 7)),
    dl(PMO, 'hw', '№1', (10, 4)), dl(PMO, 'hw', '№1 жёсткий (−1 балл/сутки после 04.10)', (10, 11)),
    dl(PMO, 'hw', '№2', (10, 20)), dl(PMO, 'hw', '№2 жёсткий (−1 балл/сутки после 20.10)', (10, 25)),
    dl(VKR, 'milestone', 'Выбор научных руководителей', (10, 20)),
    dl(DL, 'hw', '№1', (10, 25)),
    dl(PMO, 'exam', '', (10, 31), time(14, 40)),
    dl(TS, 'quiz', '№5–6', (10, 4)),  # прошёл — не показываем
]


def test_penalty_pair_is_one_row_and_window():
    in_window, later = C.split_items(DATA, NOW)
    rows = [(C.subject_label(it), C.what_label(it), C.date_label(it, NOW.date())[0]) for it in in_window]
    assert rows == [
        ("Временные ряды", "квиз/КР №7–8", "завтра"),
        ("Продвинутое МО", "ДЗ №1", "04.10 → 11.10"),
        ("ВКР", "выбор научных руководителей", "20.10"),
        ("Продвинутое МО", "ДЗ №2", "20.10 → 25.10"),
    ]
    assert [C.what_label(it) for it in later] == ["ДЗ №1", "экзамен"]


def test_caption():
    in_window, later = C.split_items(DATA, NOW)
    assert C.render_caption(in_window, later, NOW.date()) == (
        "❗ <b>Ближайший:</b> Временные ряды — квиз/КР №7–8, завтра\n"
        "<b>Позже:</b>\n"
        "Глубинное обучение — ДЗ №1 · 25.10\n"
        "Продвинутое МО — экзамен · 31.10, 14:40")


def test_empty_window():
    in_window, later = C.split_items([DATA[7]], NOW)   # только экзамен 31.10 — за окном
    assert in_window == []
    assert C.render_empty(later) == (
        "⏳ <b>Дедлайны на 2 недели</b>\n<i>нет информации</i>\n\n"
        "<b>Позже:</b>\nПродвинутое МО — экзамен · 31.10, 14:40")


def test_render_png_and_cache_key():
    in_window, _ = C.split_items(DATA, NOW)
    png = C.render(in_window, NOW.date())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(png[16:20], "big") == 1080
    assert int.from_bytes(png[20:24], "big") == 720       # 4 строки → минимальная высота
    key = C.cache_key(in_window, NOW.date())
    assert key == C.cache_key(in_window, NOW.date()) and key.startswith("2026-10-06:")
    in_window[0].deadline.due_date = date(2026, 10, 8)
    assert C.cache_key(in_window, NOW.date()) != key       # данные поменялись — новая картинка


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"ok  {name}")
