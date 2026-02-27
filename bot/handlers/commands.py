"""
Базовые команды бота
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot.handlers.schedule import show_schedule_callback
from bot.handlers.auth import auth_service, login_start

logger = logging.getLogger(__name__)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать главное меню"""
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    if auth_service.is_user_verified(user_id):
        email = auth_service.get_user_email(user_id)
        text = f"👋 С возвращением, {first_name}!\n✅ Авторизован: {email}"
        keyboard = [
            [InlineKeyboardButton("📅 Расписание", callback_data="schedule")],
            [InlineKeyboardButton("🔔 Уведомления", callback_data="notify")],
            [InlineKeyboardButton("📚 Задания", callback_data="tasks")],
            [InlineKeyboardButton("📖 Предметы", callback_data="subjects")]
        ]
    else:
        text = (
            f"👋 Привет, {first_name}!\n\n"
            "Я бот расписания МНАД ФКН ВШЭ.\n"
            "Для доступа к функциям авторизуйтесь через корпоративную почту."
        )
        keyboard = [[InlineKeyboardButton("🔐 Авторизоваться", callback_data="login")]]
    
    # Определяем, куда отправлять
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

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
        # Для кнопки логина нужно передать update с callback_query
        await login_start(update, context)
        return
    
    # Проверка авторизации для остальных кнопок
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Сначала авторизуйтесь через кнопку выше")
        return
    
    if query.data == "schedule":
        await show_schedule_callback(update, context)
    else:
        await query.edit_message_text(f"⚙️ Функция {query.data} в разработке")