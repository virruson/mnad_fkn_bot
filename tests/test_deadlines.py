"""
Тексты раздела «Дедлайны» и отбор утренней рассылки — без БД и Telegram.
Запуск: python -m pytest tests/test_deadlines.py   (или python tests/test_deadlines.py)
"""
import sys
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services.deadlines import (
    build_subject_buttons, display_name, render_deadline_digest, render_subject_card,
)

NOW = datetime(2026, 9, 30, 12, 0)  # ср 30.09, как в docs/ui_deadlines.md


def subj(id, name, short=None, formula=None):
    return NS(id=id, name=name, short_name=short, grading_formula=formula)


def dl(subject, kind, title, day, due_time=None):
    return NS(subject_id=subject.id, subject=subject, kind=kind, title=title,
              due_date=date(2026, *day), due_time=due_time)


PMO = subj(1, "Продвинутое машинное обучение", "Продвинутое МО", "0.3·ДЗ + 0.2·Квизы + 0.5·КР")
TS = subj(2, "Анализ и прогнозирование временных рядов", "Временные ряды")
DB = subj(3, "Базы и хранилища данных")
RL = subj(4, "Обучение с подкреплением")

PMO_DEADLINES = [
    dl(PMO, 'hw', '№1', (9, 18)), dl(PMO, 'hw', '№2', (10, 1)), dl(PMO, 'hw', '№3', (10, 15)),
    dl(PMO, 'quiz', '№1', (9, 23)), dl(PMO, 'quiz', '№2', (9, 30), time(18, 0)),
    dl(PMO, 'quiz', '№3', (10, 7)),
]


def test_card_matches_mockup():
    assert render_subject_card(PMO, PMO_DEADLINES, NOW) == (
        "<b>Продвинутое машинное обучение</b>\n\n"
        "📝 <b>ДЗ</b>\n<s>№1 · <b>18.09</b></s>\n❗ №2 · <b>01.10</b> · <i>осталось 1 дн</i>\n№3 · <b>15.10</b> · <i>осталось 15 дн</i>\n\n"
        "🧠 <b>Квизы/КР</b>\n<s>№1 · <b>23.09</b></s>\n❗ №2 · <b>30.09, 18:00</b> · <i>сегодня</i>\n№3 · <b>07.10</b> · <i>осталось 7 дн</i>\n\n"
        "🎓 <b>Экзамен</b>\n<i>нет информации</i>\n\n"
        "🧮 <b>Формула</b>\n<code>Итог = 0.3·ДЗ + 0.2·Квизы + 0.5·КР</code>"
    )


def test_card_hides_old_past_and_empty_subject():
    hws = [dl(DB, 'hw', f"№{i}", (9, i)) for i in range(1, 7)] + [dl(DB, 'hw', '№7', (10, 20))]
    card = render_subject_card(DB, hws, NOW)
    assert "№3 · <b>03.09</b>" not in card and "<s>№4 · <b>04.09</b></s>" in card
    assert "<i>ещё 3 прошедших</i>" in card
    assert render_subject_card(RL, [], NOW) == "<b>Обучение с подкреплением</b>\n\n<i>нет информации</i>"


def test_card_past_after_due_time():
    card = render_subject_card(PMO, PMO_DEADLINES, datetime(2026, 9, 30, 18, 1))
    assert "<s>№2 · <b>30.09, 18:00</b></s>" in card


def test_subject_buttons_order():
    deadlines = {1: PMO_DEADLINES, 2: [dl(TS, 'hw', '№2', (10, 4))], 3: [dl(DB, 'hw', '№1', (9, 1))]}
    buttons = build_subject_buttons([DB, RL, TS, PMO], deadlines, NOW)
    assert [text for _, text in buttons] == [
        "❗ Продвинутое МО", "Временные ряды", "Базы и хранилища данных", "Обучение с подкреплением"]


def test_display_name():
    assert display_name(DB) == "Базы и хранилища данных"
    assert display_name(PMO) == "Продвинутое МО"
    assert display_name(subj(9, "Глубинное обучение и нейронные сети")) == "Глубинное обучение и…"


def test_milestone_only_card():
    vkr = subj(5, "ВКР", "📜 ВКР")
    card = render_subject_card(vkr, [dl(vkr, 'milestone', 'Защита ВКР', (10, 20))], NOW)
    assert card == "<b>ВКР</b>\n\n📌 <b>Этапы</b>\n<b>20.10</b> · Защита ВКР · <i>осталось 20 дн</i>"
    assert render_deadline_digest([dl(vkr, 'milestone', 'Защита ВКР', (10, 1))], NOW.date()).endswith(
        "📜 ВКР — Защита ВКР")


def test_digest_only_4_2_1_days():
    deadlines = [
        dl(PMO, 'hw', '№3', (10, 1)), dl(DB, 'test', '№1', (10, 2)),
        dl(TS, 'hw', '№2', (10, 4)), dl(RL, 'quiz', '№1', (10, 4)),
        dl(PMO, 'quiz', '№9', (10, 3)),   # за 3 дня — не шлём
        dl(PMO, 'quiz', '№2', (9, 30)),   # сегодня — не шлём
    ]
    assert render_deadline_digest(deadlines, NOW.date()) == (
        "⏳ <b>Дедлайны</b>\n\n"
        "❗ <b>Завтра</b> · чт 01.10\nПродвинутое МО — ДЗ №3\n\n"
        "<b>Через 2 дня</b> · пт 02.10\nБазы и хранилища данных — КР №1\n\n"
        "<b>Через 4 дня</b> · вс 04.10\nВременные ряды — ДЗ №2\nОбучение с подкреплением — квиз/КР №1"
    )
    assert render_deadline_digest(deadlines, date(2026, 9, 20)) is None


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"ok  {name}")
