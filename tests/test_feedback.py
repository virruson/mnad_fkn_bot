"""
«💬 Обратная связь»: тексты, лимит, цитата — без БД и Telegram. Макет — docs/ui_feedback.md.
Запуск: python -m pytest tests/test_feedback.py
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.services import feedback as F

LETTER = ("привет! во первых хотела сказать спасибо за бота мнад, правда очень удобно!! а во вторых у меня "
          "есть несколько предложений 👉🏻👈🏻\n1. квизы по временным рядам <b>не</b> одной строкой\n2. RecSys & co")


def test_thanks_label():
    assert F.thanks_label(0, 0) == "🤍 Спасибо"
    assert F.thanks_label(0, 23) == "🤍 Спасибо · 23"
    assert F.thanks_label(7, 312) == "❤️ Спасибо · 312"


def test_thanks_toasts_and_celebrations():
    assert [F.thanks_toast(n) for n in (1, 2, 4, 5, 6, 10, 15)] == [
        "Спасибо дошло до автора ❤️", "❤️ ×2", "❤️ ×4", "И тебе спасибо 😊", "❤️ ×6", "❤️ ×10", "❤️ ×15"]
    assert [F.celebration(n) for n in (5, 9, 10, 11, 15, 20, 50)] == [None, None, "🤩", None, "😍", "🥰", "🏆"]
    assert [F.celebration(n) for n in (55, 60, 90, 95)] == ["😍", "🥰", "🏆", "😍"]
    assert [n for n in range(1, 120) if F.notify_author(n)] == [1, 10, 25, 50, 100]


def test_quote_matches_mockup():
    assert F.quote(LETTER) == "привет! во первых хотела сказать спасибо за бота…"
    assert F.quote("коротко\nи ясно") == "коротко и ясно"


def test_author_message_escapes_and_keeps_text():
    msg = F.author_message(12, "Анна Смирнова", "anna_smr", "asmirnova@edu.hse.ru", "Дедлайны · RecSys", LETTER)
    assert msg.startswith("💬 <b>Обращение №12</b>\nАнна Смирнова · @anna_smr · asmirnova@edu.hse.ru\n"
                          "Откуда: Дедлайны · RecSys\n\n<blockquote>привет!")
    assert "&lt;b&gt;не&lt;/b&gt;" in msg and "RecSys &amp; co" in msg and "👉🏻👈🏻\n1." in msg
    assert msg.endswith("<i>Ответьте на это сообщение (reply), чтобы ответить студенту.</i>")
    assert "Откуда: Обратная связь" in F.author_message(1, "Анна", None, "a@hse.ru", None, "x")
    assert "\nАнна · a@hse.ru\n" in F.author_message(1, "Анна", None, "a@hse.ru", None, "x")


def test_thanks_and_answer_messages():
    assert F.thanks_message("Анна Смирнова", "anna_smr", 24) == "❤️ Спасибо · Анна Смирнова (@anna_smr) · всего 24"
    assert F.thanks_message("Анна", None, 1) == "❤️ Спасибо · Анна · всего 1"
    assert F.thanks_message("Анна Смирнова", "anna_smr", 312, 25) == "❤️ ×25 · Анна Смирнова (@anna_smr) · всего 312"
    ans = F.answer_message(datetime(2026, 10, 12, 9), LETTER, "Спасибо! <ок>")
    assert ans == ("💬 <b>Ответ автора</b>\nНа ваше сообщение от 12.10: "
                   "<i>«привет! во первых хотела сказать спасибо за бота…»</i>\n\n"
                   "<blockquote>Спасибо! &lt;ок&gt;</blockquote>")


def test_daily_limit():
    now = datetime(2026, 10, 14, 12, 0)
    four = [now - timedelta(hours=h) for h in (1, 2, 3, 4)]
    assert F.limit_until(four, now) is None
    five = four + [now - timedelta(hours=17, minutes=20)]             # самое старое — 13.10 18:40
    until = F.limit_until(five, now)
    assert until == datetime(2026, 10, 14, 18, 40)
    assert F.limit_text(until, now).endswith("Следующее — после 18:40.")
    late = datetime(2026, 10, 14, 23, 0)
    five_late = [late - timedelta(hours=h) for h in (1, 2, 3, 4, 20)]  # старое 14.10 03:00 → 15.10 03:00
    assert F.limit_text(F.limit_until(five_late, late), late).endswith("Следующее — завтра после 03:00.")
    old = five + [now - timedelta(hours=30)]                            # старше суток не считается
    assert F.limit_until(old, now) == until


def test_input_screens():
    title = F.input_title('subject', "RecSys")
    assert title == "✏️ <b>Неточность: RecSys</b>"
    assert F.input_prompt('subject', title).endswith("Автор увидит ваше имя и почту.")
    assert F.input_title('reply', feedback_id=12) == "✏️ <b>Ответ на обращение №12</b>"
    assert F.too_long("✏️ <b>Сообщение автору</b>", 1254) == (
        "✏️ <b>Сообщение автору</b>\nСлишком длинно: 1254 из 1000 символов. Сократите и отправьте ещё раз.")
