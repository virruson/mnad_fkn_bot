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
from bot.handlers.notifications import notify_menu, notify_toggle
from bot.handlers import my_subjects
from bot.handlers import feedback as fb
from bot.services import feedback as feedback_config
from bot.handlers.deadlines import show_deadlines, show_subject_card, open_deadlines_from_digest, open_section, show_deadline_chart
from bot.handlers import progress
from bot.services.scheduler import setup_scheduler

# Импортируем обработчики расписания
from bot.handlers.schedule import (
    show_schedule,
    show_schedule_callback,
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

    # 1b. «📈 Мой прогресс»: ввод оценки вручную («✏️ Другая»)
    progress_input_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(progress.progress_input_start, pattern="^prog_input_\\d+$")],
        states={
            progress.GRADE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, progress.progress_input_text)],
        },
        fallbacks=[CommandHandler("cancel", progress.progress_input_cancel)],
        per_message=False,
        allow_reentry=True,
        conversation_timeout=600,  # ушёл в другой раздел и не ввёл число — через 10 мин текст снова обычный
    )
    application.add_handler(progress_input_handler)

    # 1c. «💬 Обратная связь»: ввод обращения (текст, до 1000 символов)
    feedback_input_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(fb.write_start, pattern="^fb_write(_s_\\d+|_r_\\d+)?$")],
        states={
            fb.FB_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, fb.write_text),
                MessageHandler(~filters.TEXT & ~filters.COMMAND, fb.write_not_text),
            ],
        },
        fallbacks=[CommandHandler("cancel", fb.write_cancel)],
        per_message=False,
        allow_reentry=True,
        conversation_timeout=600,
    )
    application.add_handler(feedback_input_handler)
    author_chat = feedback_config.chat_id()
    if author_chat is None:
        logger.warning("FEEDBACK_CHAT_ID не задан — «💬 Обратная связь» выключена")
    else:
        # ответ автора reply'ем на «Обращение №N» — раньше всех остальных обработчиков
        application.add_handler(MessageHandler(filters.Chat(author_chat) & filters.REPLY & filters.TEXT
                                               & ~filters.COMMAND, fb.author_reply), group=-1)

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
    application.add_handler(CommandHandler(["deadlines", "tasks"], show_deadlines))  # /tasks — старый алиас
    application.add_handler(CommandHandler(["progress", "subjects"], progress.show_progress))  # /subjects — старый алиас
    application.add_handler(CommandHandler("feedback", fb.show_feedback))

    # 4. Callback-кнопки (порядок важен)
    application.add_handler(CallbackQueryHandler(auth.login_start, pattern="^login$"))
    application.add_handler(CallbackQueryHandler(show_schedule_callback, pattern="^schedule$"))
    application.add_handler(CallbackQueryHandler(schedule_today_callback, pattern="^schedule_today$"))
    application.add_handler(CallbackQueryHandler(schedule_tomorrow_callback, pattern="^schedule_tomorrow$"))
    application.add_handler(CallbackQueryHandler(schedule_week_callback, pattern="^schedule_week$"))
    application.add_handler(CallbackQueryHandler(schedule_next_week_callback, pattern="^schedule_next_week$"))
    application.add_handler(CallbackQueryHandler(schedule_month_callback, pattern="^schedule_month$"))
    # Уведомления
    application.add_handler(CallbackQueryHandler(notify_menu,      pattern="^notify_menu$"))
    application.add_handler(CallbackQueryHandler(notify_menu,      pattern="^notify$"))
    application.add_handler(CallbackQueryHandler(notify_toggle,    pattern="^notify_toggle_\\w+$"))
    # Мои предметы (маголего)
    application.add_handler(CallbackQueryHandler(my_subjects.open_my_subjects,
                                                 pattern="^mysubj(_from_(deadlines|progress))?$"))
    application.add_handler(CallbackQueryHandler(my_subjects.toggle, pattern="^mysubj_(common|el_\\d+)$"))
    # Дедлайны
    application.add_handler(CallbackQueryHandler(show_deadlines,             pattern="^deadlines$"))
    application.add_handler(CallbackQueryHandler(show_subject_card,          pattern="^deadlines_subj_\\d+$"))
    application.add_handler(CallbackQueryHandler(show_deadline_chart,        pattern="^deadlines_chart$"))
    application.add_handler(CallbackQueryHandler(open_deadlines_from_digest, pattern="^deadlines_open$"))
    application.add_handler(CallbackQueryHandler(open_section, pattern="^open_(deadlines|schedule|notify|progress|mysubj)$"))
    # Обратная связь
    application.add_handler(CallbackQueryHandler(fb.show_feedback, pattern="^fb$"))
    application.add_handler(CallbackQueryHandler(fb.thanks,        pattern="^fb_thanks$"))
    # Мой прогресс
    application.add_handler(CallbackQueryHandler(progress.show_progress,     pattern="^progress$"))
    application.add_handler(CallbackQueryHandler(progress.progress_subject,  pattern="^prog_s_\\d+$"))
    application.add_handler(CallbackQueryHandler(progress.progress_action,
                                                 pattern="^prog_(d|skip|undo|clr|edit)_\\d+$|^prog_g_\\d+_\\d+$"))
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