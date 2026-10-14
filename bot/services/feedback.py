"""
«💬 Обратная связь»: настройки и тексты (Telegram HTML). Макет — docs/ui_feedback.md,
задача — docs/feedback_developer.md. Чистые функции — без БД и Telegram.
"""
import logging
import os
from datetime import datetime, timedelta
from html import escape

logger = logging.getLogger(__name__)

FEEDBACK_MAX_LEN = 1000
DAILY_LIMIT = 5
QUOTE_LEN = 50
LIMIT_WINDOW = timedelta(hours=24)
DEFAULT_CHAT_ID = -5024604118   # группа автора для обращений; FEEDBACK_CHAT_ID в .env переопределяет

TITLE = "💬 <b>Обратная связь</b>"
INTRO = "Нашли ошибку в сроках или есть идея? Напишите — автор бота прочитает и ответит прямо здесь."
NAME_WARNING = "Автор увидит ваше имя и почту."
SENT = "✅ <b>Отправлено</b>\nСпасибо! Ответ автора придёт сюда, в этот чат."
THANKS_FIRST = "Спасибо дошло до автора ❤️"
THANKS_FIVE = "И тебе спасибо 😊"
# Пасхалки на 10, 15, 20 … сердечек: одно эмодзи крупно, исчезает через CELEBRATION_TTL секунд
CELEBRATION = ["🤩", "😍", "🥰", "💖", "😻", "🫶", "💞", "🎉", "🏆"]
CELEBRATION_TTL = 4
AUTHOR_MILESTONES = {1, 10, 25, 50, 100}   # на какое по счёту сердечко студента писать автору
NOT_DELIVERED_BLOCKED = "⚠️ Не доставлено: студент заблокировал бота"
DELIVERED = "✓ доставлено"


def chat_id():
    """Куда приходят обращения: FEEDBACK_CHAT_ID из .env, иначе DEFAULT_CHAT_ID.
    FEEDBACK_CHAT_ID=off — раздел выключен."""
    raw = (os.getenv('FEEDBACK_CHAT_ID') or '').strip()
    if not raw:
        return DEFAULT_CHAT_ID
    if raw.lower() == 'off':
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning(f"FEEDBACK_CHAT_ID={raw!r} — не число, «Обратная связь» выключена")
        return None


def enabled() -> bool:
    return chat_id() is not None


# ---------------------------------------------------------------------------
# Экраны студента
# ---------------------------------------------------------------------------

def thanks_label(my_count: int, total: int) -> str:
    """🤍 — студент ещё не нажимал, ❤️ — нажимал; total — всего сердечек у всех студентов."""
    icon = "❤️" if my_count else "🤍"
    return f"{icon} Спасибо · {total}" if total else f"{icon} Спасибо"


def thanks_toast(n: int) -> str:
    """Подсказка после n-го нажатия студента."""
    if n == 1:
        return THANKS_FIRST
    if n == 5:
        return THANKS_FIVE
    return f"❤️ ×{n}"


def celebration(n: int):
    """Эмодзи на 10, 15, 20 …; после 🏆 (50) — по кругу с 😍. Иначе None."""
    if n < 10 or n % 5:
        return None
    k = n // 5 - 2
    if k < len(CELEBRATION):
        return CELEBRATION[k]
    loop = CELEBRATION[1:]
    return loop[(k - len(CELEBRATION)) % len(loop)]


def notify_author(n: int) -> bool:
    return n in AUTHOR_MILESTONES


def screen_text() -> str:
    return f"{TITLE}\n{INTRO}"


def input_title(kind: str, subject_name: str = "", feedback_id: int = 0) -> str:
    if kind == 'subject':
        return f"✏️ <b>Неточность: {escape(subject_name)}</b>"
    if kind == 'reply':
        return f"✏️ <b>Ответ на обращение №{feedback_id}</b>"
    return "✏️ <b>Сообщение автору</b>"


def input_prompt(kind: str, title: str) -> str:
    if kind == 'subject':
        body = ("Что не так в сроках или заданиях? Напишите одним сообщением, до 1000 символов. Например:\n"
                "<i>«Срок ДЗ №1 перенесли на 21.10, 23:59»</i>")
    elif kind == 'reply':
        body = "Напишите одним сообщением, до 1000 символов."
    else:
        body = ("Напишите одним сообщением, до 1000 символов. Например:\n"
                "<i>«По RecSys срок ДЗ №1 перенесли на 21.10, 23:59»</i>")
    return f"{title}\n{body}\n\n{NAME_WARNING}"


def too_long(title: str, length: int) -> str:
    return (f"{title}\nСлишком длинно: {length} из {FEEDBACK_MAX_LEN} символов. "
            f"Сократите и отправьте ещё раз.")


def not_text(title: str) -> str:
    return f"{title}\nПринимается только текст. Если хотели показать скриншот — опишите словами, что на нём."


def limit_until(recent: list, now: datetime):
    """recent — created_at обращений за последние 24 ч. Когда можно снова или None (лимита нет)."""
    window = sorted(t for t in recent if t > now - LIMIT_WINDOW)
    if len(window) < DAILY_LIMIT:
        return None
    return window[-DAILY_LIMIT] + LIMIT_WINDOW


def limit_text(until: datetime, now: datetime) -> str:
    when = f"после {until:%H:%M}" if until.date() == now.date() else f"завтра после {until:%H:%M}"
    return f"{TITLE}\nЗа сутки можно отправить {DAILY_LIMIT} сообщений, лимит исчерпан. Следующее — {when}."


# ---------------------------------------------------------------------------
# Сообщения автору и ответ студенту
# ---------------------------------------------------------------------------

def person(name: str, username: str | None, email: str | None, sep: str = " · ") -> str:
    parts = [escape(name or "Без имени")]
    if username:
        parts.append(f"@{escape(username)}")
    if email:
        parts.append(escape(email))
    return sep.join(parts)


def author_message(feedback_id: int, name: str, username, email, context, text: str) -> str:
    return (f"💬 <b>Обращение №{feedback_id}</b>\n"
            f"{person(name, username, email)}\n"
            f"Откуда: {escape(context or 'Обратная связь')}\n\n"
            f"<blockquote>{escape(text)}</blockquote>\n"
            f"<i>Ответьте на это сообщение (reply), чтобы ответить студенту.</i>")


def thanks_message(name: str, username, total: int, n: int = 1) -> str:
    who = escape(name or "Без имени") + (f" (@{escape(username)})" if username else "")
    head = "❤️ Спасибо" if n == 1 else f"❤️ ×{n}"
    return f"{head} · {who} · всего {total}"


def quote(text: str, limit: int = QUOTE_LEN) -> str:
    """Первые limit символов в одну строку, обрезка по слову с «…»."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    if flat[limit] != " " and " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut.rstrip(" ,.:;—-!?") + "…"


def answer_message(created_at: datetime, original: str, reply: str) -> str:
    return (f"💬 <b>Ответ автора</b>\n"
            f"На ваше сообщение от {created_at:%d.%m}: <i>«{escape(quote(original))}»</i>\n\n"
            f"<blockquote>{escape(reply)}</blockquote>")
