"""
Главный модуль бота расписания ФКН
"""
import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler


# Импортируем обработчики
from bot.handlers.commands import start, help_command, button_callback
from bot.handlers.schedule import show_group_schedule
from bot.handlers.commands import back_to_menu

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

# Токен бота из .env файла
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("BOT_TOKEN не найден в .env файле!")
    logger.error("Создайте файл .env и добавьте строку: BOT_TOKEN=ваш_токен")
    exit(1)

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Обработчик для inline кнопок
    application.add_handler(CallbackQueryHandler(button_callback))

    # Запускаем бота
    logger.info("Бот запущен... Нажмите Ctrl+C для остановки")
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()
