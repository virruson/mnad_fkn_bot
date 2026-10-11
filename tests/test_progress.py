"""
«Мой прогресс»: расчёт накопа и тексты экранов — без БД и Telegram.
Кейсы и тексты — из docs/ui_progress.md.
Запуск: python -m pytest tests/test_progress.py   (или python tests/test_progress.py)
"""
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services import progress as P
from bot.services.deadlines import without_done

PMO_FORMULA = "0.5·ДЗ + 0.2·КР + 0.3·ЭКЗ · автомат (макс. 7), если ДЗ и каждый тест ≥ 6"
PMO = NS(id=1, name="Продвинутое машинное обучение", short_name="Продвинутое МО",
         grading_formula=PMO_FORMULA, grading_weights={"hw": 0.5, "quiz": 0.2, "exam": 0.3})
RECSYS = NS(id=2, name="RecSys", short_name="",
            grading_formula="0.29·ДЗ_1 + 0.29·ДЗ_2 + 0.42·ЭКЗ · округление арифметическое",
            grading_weights={"hw:№1": 0.29, "hw:№2": 0.29, "exam": 0.42})
RL = NS(id=3, name="Обучение с подкреплением", short_name="", grading_formula="",
        grading_weights={"hw": 0.3, "quiz": 0.3, "project": 0.4})
VKR = NS(id=4, name="ВКР", short_name="📜 ВКР", grading_formula="", grading_weights=None)
TS = NS(id=5, name="Анализ и прогнозирование временных рядов", short_name="Временные ряды",
        grading_formula="0.4·ДЗ + 0.2·Квизы + 0.4·ЭКЗ", grading_weights=None)
_ids = iter(range(1, 1000))


def dl(subject, kind, title, day, due_time=None, role='item'):
    return NS(id=next(_ids), subject_id=subject.id, subject=subject, kind=kind, title=title,
              due_date=date(2026, *day), due_time=due_time, progress_role=role)


def mark(grade=None, done=True):
    return NS(done_at=datetime(2026, 10, 1) if done else None,
              grade=Decimal(str(grade)) if grade is not None else None)


PMO_DL = [
    dl(PMO, 'hw', '№1', (10, 4), time(23, 59)),
    dl(PMO, 'hw', '№1 жёсткий (−1 балл/сутки после 04.10)', (10, 11), role='hidden'),
    dl(PMO, 'hw', '№2', (10, 20), time(23, 59)),
    dl(PMO, 'hw', 'Practice 3 (бонус)', (10, 4), role='bonus'),
    dl(PMO, 'quiz', 'Тест №1', (9, 26)),
    dl(PMO, 'quiz', 'Пересдача теста №1 (по спискам)', (10, 3), time(17, 40), role='hidden'),
    dl(PMO, 'quiz', 'Тест №2 (на занятии)', (10, 17)),
    dl(PMO, 'exam', '', (10, 31), time(14, 40)),
]
HW1, _, HW2, PRACTICE, TEST1, _, TEST2, EXAM = PMO_DL
MID = {HW1.id: mark(8), PRACTICE.id: mark(), TEST1.id: mark(7)}
END = {HW1.id: mark(8), HW2.id: mark(9), PRACTICE.id: mark(10), TEST1.id: mark(7),
       TEST2.id: mark(8), EXAM.id: mark(7)}


def test_pmo_mid_module():
    score = P.compute(PMO.grading_weights, PMO_DL, MID)
    assert (P.fmt_accum(score.accum), P.fmt_avg(score.max_accum), score.total) == ("2.70", "7.0", None)
    assert P.render_list_line(PMO, PMO_DL, MID) == "Продвинутое МО — ✅ 2/5 · <b>2.70</b> из 7.0"
    assert P.render_subject_screen(PMO, PMO_DL, MID) == (
        "📈 <b>Продвинутое машинное обучение</b>\n\n"
        "📝 <b>ДЗ</b>\n✅ <b>8</b> · №1 · 04.10\n☐ №2 · 20.10\n✅ Practice 3 · <i>бонус</i>\n\n"
        "🧠 <b>Квизы/КР</b>\n✅ <b>7</b> · Тест №1 · 26.09\n☐ Тест №2 (на занятии) · 17.10\n\n"
        "🎓 <b>Экзамен</b>\n☐ Экзамен · 31.10, 14:40\n\n"
        "🧮 <b>Накоп</b>\n"
        f"<code>Итог = {PMO_FORMULA}</code>\n"
        "<pre>ДЗ        8.0 · 1 из 2\nКвизы/КР  7.0 · 1 из 2\nЭкзамен     — · 0 из 1</pre>\n"
        "<b>Накоп: 2.70</b> из 7.0\n<i>неоценённое = 0, особые правила не учтены</i>")
    buttons = [[t for t, _ in row] for row in P.activity_buttons(PMO_DL, MID)]
    assert buttons == [["✅ ДЗ №1", "☐ ДЗ №2"], ["✅ Practice 3", "✅ Тест №1"], ["☐ Тест №2", "☐ Экзамен"]]


def test_pmo_end_of_module_with_exam():
    score = P.compute(PMO.grading_weights, PMO_DL, END)
    assert (P.fmt_accum(score.accum), P.fmt_accum(score.total)) == ("5.75", "7.85")
    text = P.render_subject_screen(PMO, PMO_DL, END)
    assert "<pre>ДЗ        8.5 · 2 из 2\nКвизы/КР  7.5 · 2 из 2\nЭкзамен   7.0 · 1 из 1</pre>" in text
    assert text.endswith("<b>Накоп: 5.75</b> из 7.0\n<b>Итог: 7.85</b>\n"
                         "<i>особые правила и округление — по правилам курса</i>")
    assert "✅ <b>9</b> · №2 · 20.10\n✅ <b>10</b> · Practice 3 · <i>бонус</i>" in text


def test_recsys_per_item_weights():
    hw1 = dl(RECSYS, 'hw', '№1', (10, 14), time(23, 59))
    marks = {hw1.id: mark(9)}
    score = P.compute(RECSYS.grading_weights, [hw1], marks)
    assert (P.fmt_accum(score.accum), P.fmt_avg(score.max_accum)) == ("2.61", "5.8")
    assert P.render_subject_screen(RECSYS, [hw1], marks).endswith(
        "<pre>ДЗ №1     9.0\nДЗ №2       — · нет в списке\nЭкзамен     — · нет в списке</pre>\n"
        "<b>Накоп: 2.61</b> из 5.8\n<i>неоценённое = 0, особые правила не учтены</i>")
    assert P.render_list_line(RECSYS, [hw1], marks) == "RecSys — ✅ 1/1 · <b>2.61</b> из 5.8"


def test_rl_without_exam():
    hw1 = dl(RL, 'hw', '№1', (10, 14))
    score = P.compute(RL.grading_weights, [hw1], {})
    assert (P.fmt_accum(score.accum), P.fmt_avg(score.max_accum), score.total) == ("0.00", "10.0", None)
    assert P.render_list_line(RL, [hw1], {}) == "Обучение с подкреплением — ✅ 0/1 · <b>0.00</b> из 10.0"
    score = P.compute(RL.grading_weights, [hw1], {hw1.id: mark(10)})
    assert P.fmt_accum(score.accum) == "3.00" and score.total is None


def test_partially_graded_component():
    hws = [dl(PMO, 'hw', f'№{i}', (10, i)) for i in range(1, 5)]
    marks = {hws[0].id: mark(10), hws[1].id: mark(6), hws[2].id: mark()}
    score = P.compute({"hw": 1.0}, hws, marks)
    comp = score.components[0]
    assert (P.fmt_avg(comp.average), len(comp.graded), comp.total) == ("8.0", 2, 4)
    assert P.fmt_accum(score.accum) == "4.00"   # (10 + 6 + 0 + 0) / 4


def test_subject_without_weights():
    hw1 = dl(TS, 'hw', '№1', (10, 11))
    marks = {hw1.id: mark()}
    assert P.compute(None, [hw1], marks) is None
    assert P.render_list_line(TS, [hw1], marks) == "Временные ряды — ✅ 1/1 · формула не задана"
    assert P.render_subject_screen(TS, [hw1], marks) == (
        "📈 <b>Анализ и прогнозирование временных рядов</b>\n\n📝 <b>ДЗ</b>\n✅ №1 · 11.10\n\n"
        "🧮 <b>Накоп</b>\n<code>Итог = 0.4·ДЗ + 0.2·Квизы + 0.4·ЭКЗ</code>\n"
        "<i>формула не задана — накоп не считается</i>")


def test_vkr_milestones():
    ms = [dl(VKR, 'milestone', 'Выбор научных руководителей', (10, 20)),
          dl(VKR, 'milestone', 'Внесение тем ВКР в систему', (11, 9))]
    marks = {ms[0].id: mark()}
    assert P.render_list_line(VKR, ms, marks) == "ВКР — ✅ 1/2"
    assert P.render_subject_screen(VKR, ms, marks) == (
        "📈 <b>ВКР</b>\nОтмечено 1 из 2 этапов\n\n"
        "✅ 20.10 · Выбор научных руководителей\n☐ 09.11 · Внесение тем ВКР в систему")
    assert [t for row in P.activity_buttons(ms, marks) for t, _ in row] == [
        "✅ 20.10 · Выбор научных руков…", "☐ 09.11 · Внесение тем ВКР в…"]


def test_labels_and_grade_parsing():
    assert P.short_label(dl(TS, 'quiz', '№1–4', (9, 27))) == "Квиз №1–4"
    assert P.short_label(EXAM) == "Экзамен"
    assert P.short_label(dl(PMO, 'hw', 'Очень длинное название задания', (10, 1))) == "Очень длинное…"
    assert [P.parse_grade(s) for s in ("7,5", "7.5", "10", "8.25", "11", "-1", "abc", "nan")] == [
        Decimal("7.5"), Decimal("7.5"), Decimal("10.0"), Decimal("8.3"), None, None, None, None]
    assert P.fmt_grade(Decimal("8.0")) == "8" and P.fmt_grade(Decimal("7.5")) == "7.5"


def test_screens_text():
    assert P.render_grade_screen(HW2) == (
        "✅ <b>ДЗ №2</b> отмечено сданным\nПродвинутое МО · срок 20.10\n\nОценка известна?")
    assert P.render_grade_screen(PRACTICE).split("\n")[1] == "Продвинутое МО · бонус, в накоп не входит"
    assert P.render_grade_screen(HW1, Decimal(8), edit=True).startswith("<b>ДЗ №1</b> · сейчас <b>8</b>")
    assert P.render_activity_screen(TEST2, None) == (
        "✅ <b>Тест №2</b> · оценки нет\nПродвинутое МО · срок 17.10")
    assert P.render_activity_screen(HW1, Decimal(8)).startswith("✅ <b>ДЗ №1</b> · оценка <b>8</b>")


def test_weights_parsing():
    assert P.parse_weights("hw=0.5; quiz=0,2; exam=0.3") == {"hw": 0.5, "quiz": 0.2, "exam": 0.3}
    assert P.parse_weights({"hw:№1": 0.29}) == {"hw:№1": 0.29}
    for bad in ("ДЗ=0.5", "hw=x", "hw:=0.1", "hw"):
        try:
            P.parse_weights(bad)
        except ValueError:
            continue
        raise AssertionError(bad)
    assert P.weights_sum_ok({"hw": 0.29, "x": 0.29, "exam": 0.42}) and not P.weights_sum_ok({"hw": 0.5})


def test_digest_skips_done_and_its_hard_deadline():
    hard2 = dl(PMO, 'hw', '№2 жёсткий (−1 балл/сутки после 20.10)', (10, 25), role='hidden')
    all_dl = PMO_DL + [hard2]
    assert without_done(all_dl, [HW2, HW1]) == [d for d in all_dl if d not in (HW1, HW2, PMO_DL[1], hard2)]


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print(f"ok  {name}")
