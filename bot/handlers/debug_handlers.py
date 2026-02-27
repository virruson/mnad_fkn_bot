#!/usr/bin/env python
"""
Диагностика обработчиков
"""
import os
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from telegram import Update
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Простые обработчики для теста
async def start(update: Update, context):
    await update.message.reply_text("Start")
    return 0  # Переходим в состояние EMAIL

async def get_email(update: Update, context):
    logger.info(f"🔥🔥🔥 get_email ВЫЗВАН! Текст: {update.message.text}")
    await update.message.reply_text(f"Получил: {update.message.text}")
    return -1  # Завершаем

async def cancel(update: Update, context):
    await update.message.reply_text("Cancel")
    return -1

def main():
    # Просто тестовое приложение
    app = Application.builder().token("TEST_TOKEN").build()
    
    # Создаем простой ConversationHandler
    test_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            0: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(test_handler)
    
    print("✅ Диагностический обработчик создан")
    print("Порядок handlers в тесте:")
    for i, handler in enumerate(app.handlers[0]):
        print(f"  {i}: {type(handler).__name__}")
    
    print("\n" + "="*60)
    print("Теперь запустите основное приложение и проверьте логи")
    print("="*60)

if __name__ == "__main__":
    main()