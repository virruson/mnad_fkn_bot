"""
Обработчик команд для уведомлений
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

async def manage_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление уведомлениями (обработчик команды /notify)"""
    await update.message.reply_text("Функция уведомлений в разработке 🚧")

async def manage_notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление уведомлениями (обработчик нажатия на кнопку)"""
    query = update.callback_query
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Группа 1", callback_data="subscribe_1"),
            InlineKeyboardButton("✅ Группа 2", callback_data="subscribe_2")
        ],
        [
            InlineKeyboardButton("❌ Отписаться", callback_data="unsubscribe"),
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🔔 Настройка уведомлений о начале пар:\n\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )
