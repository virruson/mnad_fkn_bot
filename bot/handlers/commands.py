"""
Базовые команды бота
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Импортируем функции из других модулей
from bot.handlers.schedule import show_schedule_callback, show_group_schedule
from bot.handlers.notifications import manage_notifications_callback
from bot.handlers.tasks import show_tasks_callback
from bot.handlers.subjects import show_subjects_callback


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "Я бот расписания МНАД ФКН ВШЭ. Я помогу тебе:\n"
        "📅 Посмотреть расписание (+ссылки на Zoom)\n"
        "🔔 Подписаться на уведомления о парах\n"
        "📚 Узнать о ДЗ и контрольных работах\n"
        "📖 Найти материалы по предметам\n\n"
        "Используй /help чтобы узнать все команды"
    )
    
    # Создаем клавиатуру с основными командами
    keyboard = [
        [
            InlineKeyboardButton("📅 Расписание", callback_data="schedule"),
            InlineKeyboardButton("🔔 Уведомления", callback_data="notify")
        ],
        [
            InlineKeyboardButton("📚 Задания", callback_data="tasks"),
            InlineKeyboardButton("📖 Предметы", callback_data="subjects")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📋 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать это сообщение\n"
        "/schedule - Показать расписание\n"
        "/notify - Настроить уведомления\n"
        "/tasks - Список ДЗ и КР\n"
        "/subjects - Материалы по предметам\n"
    )
    await update.message.reply_text(help_text)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на inline кнопки"""
    query = update.callback_query
    await query.answer()
    
    # Перенаправляем в соответствующие обработчики
    if query.data == "schedule":
        await show_schedule_callback(update, context)
    elif query.data == "notify":
        await manage_notifications_callback(update, context)
    elif query.data == "tasks":
        await show_tasks_callback(update, context)
    elif query.data == "subjects":
        await show_subjects_callback(update, context)
    elif query.data == "back_to_menu":
        await back_to_menu(update, context)
    elif query.data in ["group1", "group2"]:
        await show_group_schedule(update, context)

async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вернуться в главное меню"""
    query = update.callback_query
    
    # Создаем главное меню как в /start
    keyboard = [
        [
            InlineKeyboardButton("📅 Расписание", callback_data="schedule"),
            InlineKeyboardButton("🔔 Уведомления", callback_data="notify")
        ],
        [
            InlineKeyboardButton("📚 Задания", callback_data="tasks"),
            InlineKeyboardButton("📖 Предметы", callback_data="subjects")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "Главное меню:",
        reply_markup=reply_markup
    )