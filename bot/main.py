"""
Главный модуль бота
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from telegram.error import BadRequest  # Добавляем импорт для обработки ошибок
from bot.handlers.commands import start, help_command, button_callback
from bot.handlers import auth
from bot.handlers.message_handler import handle_all_messages

# Импортируем обработчики расписания
from bot.handlers.schedule import (
    show_schedule,
    show_schedule_callback,
    show_today_schedule,
    schedule_today_callback,
    schedule_tomorrow_callback,
    schedule_week_callback,
    schedule_next_week_callback,
    schedule_month_callback
)

env_path = Path('.env')
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✅ Загружен .env из {env_path.absolute()}")

logging.basicConfig(
    level=logging.WARNING,  # WARNING, чтобы не выводить токен
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
    
    # 1. ConversationHandler для авторизации (ВАЖНО: должен быть первым)
    auth_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("login", auth.login_start),
            CallbackQueryHandler(auth.login_start, pattern="^login$")
        ],
        states={
            auth.EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.get_email)],
            auth.CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth.get_code)]
        },
        fallbacks=[CommandHandler("cancel", auth.cancel)],
        per_message=False  # Добавляем для устранения warning
    )
    application.add_handler(auth_conv_handler)
    
    # 2. Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("logout", auth.logout))
    
    # 2.1 Команды расписания
    application.add_handler(CommandHandler("schedule", show_schedule))
    application.add_handler(CommandHandler("today", schedule_today_callback))
    
    # 3. Callback-обработчики (кнопки) - ВАЖНО: порядок имеет значение!
    
    # 3.1 Сначала специфичные обработчики (с конкретными паттернами)
    application.add_handler(CallbackQueryHandler(auth.login_start, pattern="^login$"))
    
    # 3.2 Кнопки расписания с конкретными паттернами
    application.add_handler(CallbackQueryHandler(show_schedule_callback, pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(schedule_today_callback, pattern="^schedule_today$"))
    application.add_handler(CallbackQueryHandler(schedule_tomorrow_callback, pattern="^schedule_tomorrow$"))
    application.add_handler(CallbackQueryHandler(schedule_week_callback, pattern="^schedule_week$"))
    application.add_handler(CallbackQueryHandler(schedule_next_week_callback, pattern="^schedule_next_week$"))
    application.add_handler(CallbackQueryHandler(schedule_month_callback, pattern="^schedule_month$"))
    application.add_handler(CallbackQueryHandler(show_schedule_callback, pattern="^schedule_choose_stream$"))
    application.add_handler(CallbackQueryHandler(show_today_schedule, pattern="^stream_\\d+$"))
    
    # 3.3 УНИВЕРСАЛЬНЫЙ обработчик для всех остальных кнопок (menu, back_to_menu, notify, tasks, subjects)
    # Этот обработчик поймает все кнопки, которые не подошли под паттерны выше
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 4. Глобальный обработчик сообщений (должен быть последним)
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)
    )
    
    logger.info("🚀 Бот запущен...")
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()