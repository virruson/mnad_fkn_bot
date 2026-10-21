"""
«🗂 Модуль»: текущий и смотримый модуль, предметы модуля, недели — без БД.
Макет — docs/ui_module.md. Запуск: python -m pytest tests/test_modules.py
"""
import sys
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services import modules as M
from bot.services.deadlines import build_subject_buttons, render_deadlines_screen

M5 = NS(id=5, name="5 модуль", start_date=date(2026, 9, 5), end_date=date(2026, 11, 1))
M6 = NS(id=6, name="6 модуль", start_date=date(2026, 11, 2), end_date=date(2026, 12, 20))
M7 = NS(id=7, name="7 модуль", start_date=date(2027, 1, 11), end_date=date(2027, 3, 14))
ALL = [M5, M6, M7]


def test_current_module():
    assert M.current_of(ALL, date(2026, 10, 20)) is M5
    assert M.current_of(ALL, date(2026, 11, 1)) is M5            # последний день 5 модуля — ещё он
    assert M.current_of(ALL, date(2026, 11, 2)) is M6            # архивным 5 становится только со 02.11
    assert M.current_of(ALL, date(2026, 12, 30)) is M7           # каникулы — ближайший будущий
    assert M.current_of(ALL, date(2027, 6, 1)) is M7             # после последнего — последний
    assert M.current_of([], date(2026, 10, 20)) is None
    assert M.current_of([M5], date(2026, 8, 1)) is M5


def test_view_and_auto_reset():
    assert M.view_of(ALL, M6, None, None) is M6                  # не выбирал — текущий
    assert M.view_of(ALL, M6, 5, 6) is M5                        # выбрал 5, пока идёт 6
    assert M.view_of(ALL, M7, 5, 6) is M7                        # начался 7 — выбор сброшен
    assert M.view_of(ALL, M6, 99, 6) is M6                       # модуль удалили — текущий
    user = NS(view_module_id=None, view_module_base_id=None)
    M.set_view(user, M5, M6)
    assert (user.view_module_id, user.view_module_base_id) == (5, 6)
    M.set_view(user, M6, M6)
    assert (user.view_module_id, user.view_module_base_id) == (None, None)


def test_status_and_texts():
    today = date(2026, 11, 5)
    assert [M.module_status(m, today, M6) for m in ALL] == ['archive', 'current', 'upcoming']
    assert M.module_status(M7, date(2026, 12, 30), M7) == 'current'   # каникулы: ближайший — текущий
    assert M.menu_label(M5, M6, today) == "🗂 5 модуль · архив"
    assert M.menu_label(M6, M6, today) == "🗂 6 модуль · текущий"
    assert M.module_banner(M5, M6, today) == "🗂 Открыт <b>5 модуль</b> · архив"
    assert M.module_banner(M7, M6, today) == "🗂 Открыт <b>7 модуль</b> · скоро"
    assert M.module_banner(M6, M6, today) is None
    assert M.choose_screen_text(ALL) == (
        "🗂 <b>Модуль</b>\nПереключает дедлайны, прогресс, «Мои предметы» и расписание. "
        "Уведомления всегда приходят по текущему модулю.\n\n"
        "5 модуль · 05.09 – 01.11\n6 модуль · 02.11 – 20.12\n7 модуль · 11.01 – 14.03")
    assert M.toast_opened(M5, today, M6) == "Открыт 5 модуль · архив"
    assert M.toast_already(M5) == "5 модуль уже открыт"
    assert len(M.menu_label(M5, M6, today)) <= 28


def test_view_back_button():
    v = M.View(ALL, M6, M5, date(2026, 11, 5))
    assert not v.is_current
    btn = v.back_button('deadlines')[0]
    assert (btn.text, btn.callback_data) == ("🗂 Вернуться в 6 модуль", "module_now_deadlines")
    assert M.View(ALL, M6, M6, date(2026, 11, 5)).back_button('deadlines') is None
    assert M.View([], None, None, date(2026, 11, 5)).is_current


def test_module_subjects_rule():
    DL, VKR, RECSYS, AI = 1, 2, 3, 4
    deadlines = [NS(subject_id=DL, due_date=date(2026, 11, 1)),      # ДЗ №1 DL — в 5 модуле
                 NS(subject_id=DL, due_date=date(2026, 11, 8)),      # жёсткий — уже в 6
                 NS(subject_id=VKR, due_date=date(2026, 10, 20)),
                 NS(subject_id=VKR, due_date=date(2027, 3, 12)),
                 NS(subject_id=RECSYS, due_date=date(2026, 10, 31))]
    today = date(2026, 11, 5)
    # архив 5: занятия RecSys в его датах + дедлайны в датах (DL, ВКР); будущие сроки не добавляют
    assert M.module_subject_ids(M5, today, False, [RECSYS], deadlines) == {DL, VKR, RECSYS}
    # текущий 6: занятия AI, DL + дедлайн DL в датах + будущая ВКР
    assert M.module_subject_ids(M6, today, True, [AI, DL], deadlines) == {AI, DL, VKR}
    # будущий 7: ничего не загружено, кроме этапа ВКР в его датах
    assert M.module_subject_ids(M7, today, False, [], deadlines) == {VKR}


def test_archive_order_without_urgency():
    def subj(i, name, short=None):
        return NS(id=i, name=name, short_name=short)
    ts, dl, rl, pmo = subj(1, "АПВР", "Временные ряды"), subj(2, "ГО", "Глубинное обучение"), \
        subj(3, "Обучение с подкреплением"), subj(4, "ПМО", "Продвинутое МО")
    rec, vkr = subj(5, "RecSys"), subj(6, "ВКР", "📜 ВКР")
    now = datetime(2026, 11, 5, 12)
    deadlines = {2: [NS(id=1, subject_id=2, kind='hw', title='№1', due_date=date(2026, 11, 6), due_time=None)],
                 6: [NS(id=2, subject_id=6, kind='milestone', title='Тема', due_date=date(2026, 11, 9),
                        due_time=None)]}
    order = build_subject_buttons([rec, vkr, pmo, rl, dl, ts], deadlines, now, by_name=True)
    assert [t for _, t in order] == ["Временные ряды", "Глубинное обучение", "Обучение с подкреплением",
                                     "Продвинутое МО", "RecSys", "📜 ВКР"]   # без «❗» у DL, ВКР последней
    assert render_deadlines_screen(True, is_current=False) == "⏳ <b>Дедлайны</b>\nВыберите предмет"
    assert render_deadlines_screen(True) == "⏳ <b>Дедлайны</b>\nВыберите предмет · ❗ — меньше 2 дней"


def test_weeks_of_module():
    assert M.week_count(M5) == 9
    assert M.week_bounds(M5, 1) == (date(2026, 8, 31), date(2026, 9, 6))
    assert M.week_bounds(M5, 4) == (date(2026, 9, 21), date(2026, 9, 27))
    assert M.week_bounds(M5, 9) == (date(2026, 10, 26), date(2026, 11, 1))
    assert M.nearest_week(M5, date(2026, 11, 5)) == 9            # архив — последняя
    assert M.nearest_week(M7, date(2026, 11, 5)) == 1            # будущий — первая
    assert [M.weeks_word(n) for n in (1, 2, 5, 9, 11, 21, 22)] == [
        "1 неделя", "2 недели", "5 недель", "9 недель", "11 недель", "21 неделя", "22 недели"]


def test_schedule_screens():
    banner = M.module_banner(M5, M6, date(2026, 11, 5))
    assert M.schedule_screen_text(M5, banner, True) == (
        "🗂 Открыт <b>5 модуль</b> · архив\n📅 <b>Расписание</b>\n5 модуль · 05.09 – 01.11 · 9 недель")
    assert M.schedule_screen_text(M7, M.module_banner(M7, M6, date(2026, 11, 5)), False) == (
        "🗂 Открыт <b>7 модуль</b> · скоро\n📅 <b>Расписание</b>\n7 модуль · 11.01 – 14.03\n<i>нет информации</i>")
    lessons = [(date(2026, 9, 21), time(18, 10), "Временные ряды", "Лекция"),
               (date(2026, 9, 21), time(19, 40), "Временные ряды", "Семинар"),
               (date(2026, 9, 22), time(19, 40), "Обучение с подкреплением", "Лекция")]
    assert M.render_week(M5, 4, lessons, banner) == (
        "🗂 Открыт <b>5 модуль</b> · архив\n📅 <b>Неделя 4 из 9</b> · 21.09 – 27.09\n\n"
        "<b>пн 21.09</b>\n18:10 Временные ряды · лекция\n19:40 Временные ряды · семинар\n\n"
        "<b>вт 22.09</b>\n19:40 Обучение с подкреплением · лекция")
    assert M.render_week(M5, 8, [], banner) == (
        "🗂 Открыт <b>5 модуль</b> · архив\n📅 <b>Неделя 8 из 9</b> · 19.10 – 25.10\n<i>занятий нет</i>")
