"""
Базовые команды бота
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.schedule import show_schedule_callback
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
                InlineKeyboardButton("🚪 Выйти", callback_data="logout")  # Кнопка выхода на отдельной строке, но на том же уровне
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
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка"""
    await update.message.reply_text(
        "/start - Начать\n"
        "/login - Авторизация\n"
        "/logout - Выйти"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    logger.info(f"🔘 Нажата кнопка: {query.data}")
    
    if query.data == "login":
        # Передаем update как есть - функция login_start сама разберется
        await login_start(update, context)
        return
    
    # Обработка кнопки выхода
    if query.data == "logout":
        await auth_logout(update, context)
        await show_main_menu(update, context)
        return
    
    # Проверка авторизации для остальных кнопок
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Сначала авторизуйтесь через кнопку выше")
        return
    
    if query.data == "schedule":
        await show_schedule_callback(update, context)
    elif query.data == "notify":
        await query.edit_message_text("🔔 Функция уведомлений в разработке")
    elif query.data == "tasks":
        await query.edit_message_text("📚 Функция заданий в разработке")
    elif query.data == "subjects":
        await query.edit_message_text("📖 Функция предметов в разработке")
    else:
        await query.edit_message_text(f"⚙️ Функция {query.data} в разработке")