"""
Обработчик команд для предметов
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def show_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать предметы (обработчик команды /subjects)"""
    await update.message.reply_text("Функция предметов в разработке 🚧")

async def show_subjects_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать предметы (обработчик нажатия на кнопку)"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("📊 Математический анализ", callback_data="subject_math")],
        [InlineKeyboardButton("🐍 Python", callback_data="subject_python")],
        [InlineKeyboardButton("📐 Линейная алгебра", callback_data="subject_linear")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📖 Выберите предмет для просмотра материалов:",
        reply_markup=reply_markup
    )
