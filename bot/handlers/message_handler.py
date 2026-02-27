"""
Глобальный обработчик сообщений
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.auth import get_email, get_code, EMAIL, CODE
from bot.services.auth_service import AuthService

logger = logging.getLogger(__name__)
auth_service = AuthService()

async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все текстовые сообщения"""
    user_id = update.effective_user.id
    text = update.message.text
    
    logger.info(f"📨 Получено сообщение от {user_id}: '{text}'")
    
    # Проверяем, есть ли ожидаемое состояние в user_data
    expected_state = context.user_data.get('expected_state')
    
    if expected_state == EMAIL:
        logger.info(f"📧 Обрабатываем как EMAIL для {user_id}")
        result = await get_email(update, context)
        if result == CODE:
            context.user_data['expected_state'] = CODE
        elif result == -1:
            context.user_data.pop('expected_state', None)
        return
    
    elif expected_state == CODE:
        logger.info(f"🔑 Обрабатываем как CODE для {user_id}")
        result = await get_code(update, context)
        if result == -1:
            context.user_data.pop('expected_state', None)
        return
    
    else:
        # Нет активного состояния
        await update.message.reply_text(
            "Используйте /start для начала работы"
        )