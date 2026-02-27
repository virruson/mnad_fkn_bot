"""
Главный модуль бота
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler

from bot.handlers.commands import start, help_command, button_callback
from bot.handlers import auth
from bot.handlers.message_handler import handle_all_messages

env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ Загружен .env из {env_path.absolute()}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("BOT_TOKEN не найден!")
    exit(1)

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # 1. Сначала ConversationHandler для авторизации (если используется)
    # Раскомментируйте, если хотите использовать ConversationHandler
    # application.add_handler(auth.get_auth_conversation_handler())
    
    # 2. Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("logout", auth.logout))
    
    # 3. Кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 4. Глобальный обработчик сообщений (должен быть последним)
    # Ловит все текстовые сообщения, не обработанные выше
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)
    )
    
    logger.info("🚀 Бот запущен...")
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()