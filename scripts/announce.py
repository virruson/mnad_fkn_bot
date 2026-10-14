#!/usr/bin/env python
"""
Объявление «📣 Новое в боте» — всем, у кого включены «Новости бота».

Использование (в контейнере бота):
    python -m scripts.announce --text "В разделе «Дедлайны» появилась <b>ВКР</b>:\\nвсе этапы и сроки в одном месте." --button deadlines --dry-run
    python -m scripts.announce --text "..." --button deadlines
    python -m scripts.announce --text "Напоминание за 15 мин теперь можно\\nвыключить отдельно от расписания."
    python -m scripts.announce --text "..." --subject "Обучение с подкреплением" --button deadlines --dry-run

--text    1–2 строки (~80 символов), Telegram HTML; жирным — одно ключевое слово, без эмодзи.
          «\\n» в тексте — перенос строки.
--button  необязательная кнопка: deadlines | schedule | notify | progress | mysubj | feedback
--subject только тем, кому предмет виден в «📚 Мои предметы» (маголего — кто его отметил,
          общий предмет — у кого включены «Общие предметы»). Название или короткое имя предмета.
--silent  без звука (сообщение придёт, но телефон не зазвонит)
--dry-run показать текст и число получателей, ничего не отправлять
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from bot.models import Subject, User
from bot.services.selection import get_selection, is_visible
from bot.utils.database import SessionLocal

logger = logging.getLogger(__name__)

HEADER = "📣 <b>Новое в боте</b>"
BUTTONS = {
    'deadlines': "⏳ Открыть дедлайны",
    'schedule':  "📅 Открыть расписание",
    'notify':    "🔔 Открыть уведомления",
    'progress':  "📈 Открыть прогресс",
    'mysubj':    "📚 Мои предметы",
    'feedback':  "💬 Обратная связь",
}


def build_message(text: str) -> str:
    return f"{HEADER}\n\n{text.replace(chr(92) + 'n', chr(10)).strip()}"


def find_subject(db, name: str):
    """Предмет по полному или короткому имени (без учёта регистра)."""
    key = name.strip().casefold()
    matches = [s for s in db.query(Subject).all()
               if key in {(s.name or '').strip().casefold(), (s.short_name or '').strip().casefold()}]
    if len(matches) != 1:
        sys.exit(f"Предмет «{name}» {'не найден' if not matches else 'найден несколько раз'}")
    return matches[0]


def recipients(subject_name: str | None = None) -> list:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.news_enabled == True, User.is_verified == True).all()
        if subject_name:
            subject = find_subject(db, subject_name)
            users = [u for u in users if is_visible(subject, get_selection(db, u))]
        return [u.telegram_id for u in users]
    finally:
        db.close()


async def send(text: str, button: str | None, chat_ids: list, silent: bool = False) -> int:
    markup = (InlineKeyboardMarkup([[InlineKeyboardButton(BUTTONS[button], callback_data=f"open_{button}")]])
              if button else None)
    sent = 0
    async with Bot(os.environ["BOT_TOKEN"]) as bot:
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode='HTML', reply_markup=markup,
                                       disable_notification=silent)
                sent += 1
            except Exception as e:  # один заблокировавший бота пользователь не должен остановить рассылку
                logger.error(f"[NEWS] FAILED → {chat_id}: {e}")
            await asyncio.sleep(0.05)
    return sent


def main():
    parser = argparse.ArgumentParser(description="Объявление «📣 Новое в боте»")
    parser.add_argument('--text', required=True, help="текст объявления (Telegram HTML)")
    parser.add_argument('--button', choices=sorted(BUTTONS), help="кнопка перехода в раздел")
    parser.add_argument('--subject', help="только тем, у кого предмет отмечен в «Моих предметах»")
    parser.add_argument('--silent', action='store_true', help="отправить без звука")
    parser.add_argument('--dry-run', action='store_true', help="ничего не отправлять")
    args = parser.parse_args()

    text = build_message(args.text)
    chat_ids = recipients(args.subject)
    print(text)
    if args.button:
        print(f"[ {BUTTONS[args.button]} ]")
    scope = f" · только «{args.subject}»" if args.subject else ""
    print(f"\nПолучателей: {len(chat_ids)}{scope}{' · без звука' if args.silent else ''}")
    if args.dry_run:
        print("[dry-run] ничего не отправлено")
        return
    sent = asyncio.run(send(text, args.button, chat_ids, silent=args.silent))
    print(f"Отправлено: {sent} из {len(chat_ids)}")


if __name__ == '__main__':
    main()
