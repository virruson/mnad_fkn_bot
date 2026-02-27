"""
Обработчик команд для расписания
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.auth import auth_required

@auth_required
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик команды /schedule)"""
    await update.message.reply_text("⏳ Schedule feature is under construction")

async def show_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик нажатия на кнопку) - 
       этот метод вызывается из кнопок, поэтому проверка авторизации 
       должна быть в вызывающем коде или здесь"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from bot.handlers.auth import auth_service
    
    # Проверяем авторизацию
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text(
            "🔐 Для доступа к этой функции необходимо авторизоваться.\n"
            "Используйте /login"
        )
        return
    
    keyboard = [
        [
            InlineKeyboardButton("Group 1", callback_data="group1"),
            InlineKeyboardButton("Group 2", callback_data="group2")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📅 Select your group:",
        reply_markup=reply_markup
    )

async def show_group_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show schedule for specific group"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Импортируем здесь, чтобы избежать циклических импортов
    from bot.handlers.auth import auth_service
    
    # Проверяем авторизацию
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text(
            "🔐 Для доступа к этой функции необходимо авторизоваться.\n"
            "Используйте /login"
        )
        return
    
    group = "1" if query.data == "group1" else "2"
    
    schedule_text = f"📅 Расписание для группы {group}\n\n"
    schedule_text += "Пока это тестовое расписание:\n"
    schedule_text += "09:00-10:30 - Математический анализ\n"
    schedule_text += "10:45-12:15 - Python для анализа данных\n"
    schedule_text += "12:30-14:00 - Линейная алгебра\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад к группам", callback_data="schedule")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(schedule_text, reply_markup=reply_markup)