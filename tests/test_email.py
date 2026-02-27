#!/usr/bin/env python
"""
Тестовый скрипт для проверки отправки email
Запуск: python test_email.py
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

def test_smtp_connection(server: str, port: int) -> bool:
    """Тестирует соединение с SMTP сервером"""
    try:
        logger.info(f"🔄 Тестируем соединение с {server}:{port}...")
        server = smtplib.SMTP(server, port, timeout=10)
        server.quit()
        logger.info(f"✅ Соединение с {server}:{port} успешно")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка соединения: {e}")
        return False

def test_smtp_auth(server: str, port: int, email: str, password: str) -> bool:
    """Тестирует аутентификацию на SMTP сервере"""
    try:
        logger.info(f"🔄 Тестируем аутентификацию для {email}...")
        
        # Подключаемся
        smtp = smtplib.SMTP(server, port, timeout=10)
        smtp.starttls()  # Включаем шифрование
        
        # Пробуем залогиниться
        smtp.login(email, password)
        
        logger.info(f"✅ Аутентификация успешна для {email}")
        smtp.quit()
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ Ошибка аутентификации: {e}")
        logger.error("   Возможные причины:")
        logger.error("   - Неправильный пароль")
        logger.error("   - Для Gmail нужен пароль приложения (App Password)")
        logger.error("   - Включена двухфакторная аутентификация")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False

def test_send_email(server: str, port: int, sender: str, password: str, recipient: str) -> bool:
    """Тестирует отправку тестового письма"""
    try:
        logger.info(f"🔄 Отправляем тестовое письмо с {sender} на {recipient}...")
        
        # Создаём сообщение
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = recipient
        msg['Subject'] = 'Тестовое письмо от бота ФКН'
        
        # Текст письма
        body = """
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2 style="color: #4CAF50;">✅ Тестовое письмо</h2>
            <p>Если вы видите это письмо, значит SMTP настроен правильно!</p>
            <p>Бот расписания ФКН сможет отправлять коды подтверждения.</p>
            <hr>
            <p style="color: #666;">Отправлено: тестовым скриптом</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        # Подключаемся и отправляем
        smtp = smtplib.SMTP(server, port, timeout=10)
        smtp.starttls()
        smtp.login(sender, password)
        
        text = msg.as_string()
        smtp.sendmail(sender, recipient, text)
        
        smtp.quit()
        logger.info(f"✅ Письмо успешно отправлено на {recipient}!")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке: {e}")
        return False

def test_gmail_app_password_needed(email: str, password: str) -> bool:
    """Проверяет, нужен ли для Gmail пароль приложения"""
    try:
        # Пробуем подключиться с обычным паролем
        smtp = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        smtp.starttls()
        smtp.login(email, password)
        smtp.quit()
        return False  # Обычный пароль работает
    except smtplib.SMTPAuthenticationError as e:
        error_str = str(e)
        if 'Application-specific password required' in error_str:
            logger.info("🔐 Gmail требует пароль приложения (App Password)")
            return True
        return False
    except Exception:
        return False

def main():
    """Основная функция тестирования"""
    print("\n" + "="*60)
    print("🔧 ТЕСТИРОВАНИЕ SMTP НАСТРОЕК")
    print("="*60 + "\n")
    
    # Получаем настройки из .env
    sender = os.getenv('VERIFICATION_EMAIL')
    password = os.getenv('VERIFICATION_EMAIL_PASSWORD')
    server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    port = int(os.getenv('SMTP_PORT', '587'))
    
    # Запрашиваем тестовый email
    test_recipient = input(f"📧 Введите email для тестовой отправки (Enter для {sender}): ").strip()
    if not test_recipient:
        test_recipient = sender
    
    print("\n" + "-"*60)
    
    # Проверяем наличие настроек
    if not sender or not password:
        logger.error("❌ Не найдены настройки в .env файле!")
        logger.info("   Убедитесь, что в .env есть:")
        logger.info("   VERIFICATION_EMAIL=your-email@gmail.com")
        logger.info("   VERIFICATION_EMAIL_PASSWORD=your-password")
        return
    
    logger.info(f"📧 Отправитель: {sender}")
    logger.info(f"📧 Получатель: {test_recipient}")
    logger.info(f"🔌 Сервер: {server}:{port}")
    print("-"*60 + "\n")
    
    # Тест 1: Соединение
    logger.info("ТЕСТ 1: Проверка соединения с сервером")
    if not test_smtp_connection(server, port):
        logger.error("❌ Не удалось соединиться с сервером")
        logger.info("   Возможные причины:")
        logger.info("   - Нет интернета")
        logger.info("   - Сервер заблокирован")
        logger.info("   - Неправильный порт")
        return
    print()
    
    # Тест 2: Аутентификация
    logger.info("ТЕСТ 2: Проверка аутентификации")
    if not test_smtp_auth(server, port, sender, password):
        logger.error("❌ Аутентификация не удалась")
        
        # Дополнительная проверка для Gmail
        if 'gmail.com' in server:
            logger.info("\n🔍 Дополнительная диагностика для Gmail:")
            needs_app_password = test_gmail_app_password_needed(sender, password)
            if needs_app_password:
                logger.info("   ✅ Вам нужен пароль приложения (App Password)")
                logger.info("   Создайте его здесь: https://myaccount.google.com/apppasswords")
            else:
                logger.info("   ⚠️ Возможно, не включён IMAP или другая проблема")
                logger.info("   Проверьте: https://myaccount.google.com/lesssecureapps")
        return
    print()
    
    # Тест 3: Отправка письма
    logger.info("ТЕСТ 3: Отправка тестового письма")
    if test_send_email(server, port, sender, password, test_recipient):
        print("\n" + "="*60)
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("="*60)
        print("\n✅ Email настроен правильно!")
        print("✅ Бот сможет отправлять коды подтверждения")
    else:
        logger.error("❌ Не удалось отправить письмо")

if __name__ == "__main__":
    main()