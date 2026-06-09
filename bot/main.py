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
from bot.handlers.notifications import notify_menu, notify_setup, notify_subscribe, notify_disable
from bot.services.scheduler import setup_scheduler

# Импортируем обработчики расписания
from bot.handlers.schedule import (
    show_schedule,
    show_schedule_callback,
    show_today_schedule,
    schedule_today_callback,
    schedule_tomorrow_callback,
    schedule_week_callback,
    schedule_next_week_callback,
    schedule_month_callback,
    schedule_custom_start,
    schedule_custom_from,
    schedule_custom_to,
    schedule_custom_cancel,
    CUSTOM_FROM,
    CUSTOM_TO,
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
    
    # 1. ConversationHandler для ввода произвольного периода расписания
    custom_period_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(schedule_custom_start, pattern="^schedule_custom$")
        ],
        states={
            CUSTOM_FROM: [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_custom_from)],
            CUSTOM_TO:   [MessageHandler(filters.TEXT & ~filters.COMMAND, schedule_custom_to)],
        },
        fallbacks=[CommandHandler("cancel", schedule_custom_cancel)],
        per_message=False
    )
    application.add_handler(custom_period_handler)

    # 2. ConversationHandler для авторизации
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
    
    # 3. Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("logout", auth.logout))
    application.add_handler(CommandHandler("schedule", show_schedule))
    application.add_handler(CommandHandler("today", schedule_today_callback))

    # 4. Callback-кнопки (порядок важен)
    application.add_handler(CallbackQueryHandler(auth.login_start, pattern="^login$"))
    application.add_handler(CallbackQueryHandler(show_schedule_callback, pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(schedule_today_callback, pattern="^schedule_today$"))
    application.add_handler(CallbackQueryHandler(schedule_tomorrow_callback, pattern="^schedule_tomorrow$"))
    application.add_handler(CallbackQueryHandler(schedule_week_callback, pattern="^schedule_week$"))
    application.add_handler(CallbackQueryHandler(schedule_next_week_callback, pattern="^schedule_next_week$"))
    application.add_handler(CallbackQueryHandler(schedule_month_callback, pattern="^schedule_month$"))
    application.add_handler(CallbackQueryHandler(show_schedule_callback, pattern="^schedule_choose_stream$"))
    application.add_handler(CallbackQueryHandler(show_today_schedule, pattern="^stream_\\d+$"))
    # Уведомления
    application.add_handler(CallbackQueryHandler(notify_menu,      pattern="^notify_menu$"))
    application.add_handler(CallbackQueryHandler(notify_setup,     pattern="^notify_setup$"))
    application.add_handler(CallbackQueryHandler(notify_subscribe, pattern="^notify_stream_\\d+$"))
    application.add_handler(CallbackQueryHandler(notify_disable,   pattern="^notify_disable$"))
    # универсальный — последним
    application.add_handler(CallbackQueryHandler(button_callback))

    # 5. Глобальный обработчик текстовых сообщений
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages)
    )
    
    # Планировщик уведомлений
    setup_scheduler(application)

    logger.info("🚀 Бот запущен...")
    application.run_polling(allowed_updates=['message', 'callback_query'])

if __name__ == '__main__':
    main()