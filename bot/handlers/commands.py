"""
Базовые команды бота
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.schedule import (
    show_schedule_callback,
    schedule_today_callback,
    schedule_tomorrow_callback,
    schedule_week_callback,
    schedule_next_week_callback,
    schedule_month_callback,
    show_today_schedule
)
from bot.handlers.auth import auth_service, login_start, logout as auth_logout

logger = logging.getLogger(__name__)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if auth_service.is_user_verified(user_id):
        email = auth_service.get_user_email(user_id)
        text = f"👋 С возвращением, {first_name}!\n✅ Авторизован: {email}\n\nВыберите действие:"
        
        # Меню для авторизованных - все кнопки на одном уровне
        keyboard = [
            [
                InlineKeyboardButton("📅 Расписание", callback_data="schedule"),
                InlineKeyboardButton("🔔 Уведомления", callback_data="notify")
            ],
            [
                InlineKeyboardButton("📚 Задания", callback_data="tasks"),
                InlineKeyboardButton("📖 Предметы", callback_data="subjects")
            ],
            [
                InlineKeyboardButton("🚪 Выйти", callback_data="logout")
            ]
        ]
    else:
        text = (
            f"👋 Привет, {first_name}!\n\n"
            "Я бот расписания МНАД ФКН ВШЭ.\n"
            "Для доступа к функциям авторизуйтесь через корпоративную почту."
        )
        keyboard = [[InlineKeyboardButton("🔐 Авторизоваться", callback_data="login")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Определяем, куда отправлять
    if update.callback_query:
        # Просто отвечаем на callback, чтобы убрать "часики"
        await update.callback_query.answer()
        
        # Всегда отправляем новое сообщение вместо редактирования
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    help_text = (
        "/start - Начать\n"
        "/schedule - Расписание\n"
        "/today - Расписание на сегодня\n"
        "/login - Авторизация\n"
        "/logout - Выйти\n\n"
        "📅 **Доступные периоды расписания:**\n"
        "• Сегодня\n"
        "• Завтра\n"
        "• Текущая неделя\n"
        "• Следующая неделя\n"
        "• Месяц"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"🔘 Нажата кнопка: {query.data}")
    
    # Кнопки, не требующие авторизации
    if query.data == "login":
        await login_start(update, context)
        return
    
    if query.data == "logout":
        await auth_logout(update, context)
        await show_main_menu(update, context)
        return
    
    # Кнопка возврата в главное меню
    if query.data == "back_to_menu":
        await show_main_menu(update, context)
        return
    
    # Проверка авторизации для остальных кнопок
    if not auth_service.is_user_verified(user_id):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔐 Сначала авторизуйтесь через кнопку выше"
        )
        return
    
    # Обработка кнопок расписания
    if query.data == "schedule":
        await show_schedule_callback(update, context)
    elif query.data == "schedule_today":
        await schedule_today_callback(update, context)
    elif query.data == "schedule_tomorrow":
        await schedule_tomorrow_callback(update, context)
    elif query.data == "schedule_week":
        await schedule_week_callback(update, context)
    elif query.data == "schedule_next_week":
        await schedule_next_week_callback(update, context)
    elif query.data == "schedule_month":
        await schedule_month_callback(update, context)
    elif query.data == "schedule_choose_stream":
        await show_schedule_callback(update, context)
    elif query.data.startswith("stream_"):
        await show_today_schedule(update, context)
    
    # Другие функции с кнопкой "Главное меню"
    elif query.data == "notify":
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔔 **Уведомления**\n\n"
                 "Здесь вы сможете настроить уведомления о занятиях.\n"
                 "Функция в разработке.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif query.data == "tasks":
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📚 **Задания**\n\n"
                 "Здесь будут отображаться домашние задания.\n"
                 "Функция в разработке.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    elif query.data == "subjects":
        keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="📖 **Предметы**\n\n"
                 "Список предметов и преподавателей.\n"
                 "Функция в разработке.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚙️ Функция {query.data} в разработке"
        )