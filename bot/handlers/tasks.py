"""
Обработчик команд для заданий
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задания (обработчик команды /tasks)"""
    await update.message.reply_text("Функция заданий в разработке 🚧")

async def show_tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задания (обработчик нажатия на кнопку)"""
    query = update.callback_query
    
    tasks_text = "📚 Текущие задания:\n\n"
    tasks_text += "📊 Математический анализ:\n"
    tasks_text += "  • ДЗ №5 - до 28.02\n"
    tasks_text += "  • Контрольная работа - 05.03\n\n"
    tasks_text += "🐍 Python:\n"
    tasks_text += "  • Проект 1 - до 15.03\n"
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(tasks_text, reply_markup=reply_markup)
