#!/usr/bin/env python
"""
Тест подключения к Telegram API
"""
import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TimedOut, NetworkError

load_dotenv()

async def test_connection():
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("❌ BOT_TOKEN не найден в .env файле!")
        return
    
    print(f"🔍 Тестируем токен: {token[:10]}...")
    
    bot = Bot(token=token)
    
    try:
        # Пробуем получить информацию о боте
        me = await bot.get_me()
        print(f"✅ Подключение успешно!")
        print(f"✅ Бот: @{me.username}")
        print(f"✅ Имя: {me.first_name}")
    except TimedOut:
        print("❌ Таймаут подключения. Проверьте интернет или токен.")
    except NetworkError as e:
        print(f"❌ Сетевая ошибка: {e}")
    except Exception as e:
        print(f"❌ Неизвестная ошибка: {e}")

if __name__ == '__main__':
    asyncio.run(test_connection())