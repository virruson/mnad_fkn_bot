"""
Управление «экраном» бота — одно активное сообщение на чат.

Нажатие на инлайн-кнопку правит текст текущего сообщения (query.edit_message_text) —
новое сообщение не создаётся. Команда (/start, /schedule, /today) не имеет
сообщения для правки, поэтому предыдущий «экран» удаляется, а новый текст
отправляется новым сообщением — так в чате не копится история открытых экранов.

Утренний дайджест и напоминания за 15 минут (bot/services/scheduler.py) в этот
механизм не входят — это отдельные фоновые сообщения, они всегда остаются в чате.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

logger = logging.getLogger(__name__)

SCREEN_MSG_KEY = "screen_msg_id"


async def show_screen(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    """
    Показывает «экран» пользователю.

    Если update пришёл от нажатия инлайн-кнопки — редактирует текущее сообщение.
    Если update пришёл от команды/текста — удаляет предыдущий экран (если он есть
    и ещё не удалён) и отправляет новое сообщение.

    kwargs пробрасываются в edit_message_text/send_message
    (reply_markup, parse_mode, disable_web_page_preview и т.п.).
    """
    query = update.callback_query
    chat_id = update.effective_chat.id

    if query is not None:
        try:
            await query.edit_message_text(text, **kwargs)
            context.chat_data[SCREEN_MSG_KEY] = query.message.message_id
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
            # Сообщение нельзя отредактировать (слишком старое / медиа) — шлём новое
            sent = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
            context.chat_data[SCREEN_MSG_KEY] = sent.message_id
        return

    # Пришли из команды/текстового сообщения
    old_id = context.chat_data.get(SCREEN_MSG_KEY)
    if old_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=old_id)
        except BadRequest:
            pass  # уже удалено / слишком старое / нет доступа — не критично

    sent = await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
    context.chat_data[SCREEN_MSG_KEY] = sent.message_id
