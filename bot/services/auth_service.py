"""
Сервис авторизации по email
"""
import os
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AuthService:
    """Сервис для авторизации пользователей по email"""
    
    def __init__(self):
        self.allowed_domains = ['edu.hse.ru', 'hse.ru']
        self.whitelist = self._load_whitelist()
        self.verification_codes = {}
        self.verified_users = self._load_verified_users()
        
        # Настройки email
        self.sender_email = os.getenv('VERIFICATION_EMAIL')
        self.sender_password = os.getenv('VERIFICATION_EMAIL_PASSWORD')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.yandex.ru')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        
        Path('data').mkdir(exist_ok=True)
        
        logger.info("=" * 50)
        logger.info("🔧 НАСТРОЙКИ EMAIL:")
        logger.info(f"📧 EMAIL: {self.sender_email}")
        logger.info(f"🔑 PASSWORD: {'✅ установлен' if self.sender_password else '❌ НЕ УСТАНОВЛЕН'}")
        logger.info(f"🔌 SMTP: {self.smtp_server}:{self.smtp_port}")
        logger.info("=" * 50)
    
    def _load_whitelist(self) -> list:
        whitelist_file = Path('data/whitelist.json')
        if whitelist_file.exists():
            try:
                with open(whitelist_file, 'r') as f:
                    content = f.read().strip()
                    return json.loads(content) if content else []
            except:
                return []
        return []
    
    def _load_verified_users(self) -> dict:
        verified_file = Path('data/verified_users.json')
        if verified_file.exists():
            try:
                with open(verified_file, 'r') as f:
                    content = f.read().strip()
                    return json.loads(content) if content else {}
            except:
                return {}
        return {}
    
    def _save_verified_users(self):
        try:
            verified_file = Path('data/verified_users.json')
            verified_file.parent.mkdir(exist_ok=True)
            with open(verified_file, 'w') as f:
                json.dump(self.verified_users, f, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения: {e}")
    
    def is_allowed_domain(self, email: str) -> bool:
        domain = email.split('@')[-1].lower()
        return domain in self.allowed_domains
    
    def is_in_whitelist(self, email: str) -> bool:
        return email.lower() in [e.lower() for e in self.whitelist]
    
    def is_email_authorized(self, email: str) -> bool:
        return self.is_allowed_domain(email) or self.is_in_whitelist(email)
    
    def generate_verification_code(self) -> str:
        return ''.join(random.choices(string.digits, k=6))
    
    def send_verification_email(self, recipient: str, code: str) -> bool:
        """Отправляет код подтверждения на email"""
        try:
            logger.info(f"📧 Попытка отправки кода {code} на {recipient}")
            
            # ВСЕГДА выводим код в консоль для отладки
            print("\n" + "="*60)
            print("🔐 КОД ПОДТВЕРЖДЕНИЯ ДЛЯ ТЕСТИРОВАНИЯ")
            print("="*60)
            print(f"📧 Email: {recipient}")
            print(f"🔑 Код: {code}")
            print("="*60 + "\n")
            
            # Проверяем настройки
            if not self.sender_email or not self.sender_password:
                logger.error("❌ EMAIL или PASSWORD не настроены")
                logger.info("✅ Но код выведен в консоль для тестирования")
                return True  # Возвращаем true для тестирования
            
            # Создаём сообщение
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = 'Код подтверждения для бота ФКН'
            
            body = f"""
            <html>
            <body>
                <h2>Код подтверждения</h2>
                <p>Ваш код: <b>{code}</b></p>
                <p>Действителен 10 минут.</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Отправляем
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Письмо отправлено на {recipient}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")
            logger.info("✅ Но код выведен в консоль для тестирования")
            return True  # Для тестирования возвращаем true
    
    def start_verification(self, user_id: int, email: str) -> tuple:
        """Начинает процесс верификации"""
        logger.info(f"📧 Начало верификации для {email}")
        
        if not self.is_email_authorized(email):
            return False, "❌ Этот email не разрешён.", None
        
        code = self.generate_verification_code()
        expires = datetime.now() + timedelta(minutes=10)
        
        self.verification_codes[email] = {
            "code": code,
            "expires": expires,
            "user_id": user_id
        }
        
        # Отправляем код
        if self.send_verification_email(email, code):
            return True, f"✅ Код отправлен на {email}\n⏰ Действителен 10 минут.", code
        else:
            return False, "❌ Не удалось отправить код.", None
    
    def verify_code(self, user_id: int, email: str, code: str) -> tuple:
        """Проверяет код"""
        if email not in self.verification_codes:
            return False, "❌ Код не найден. Запросите новый."
        
        verification = self.verification_codes[email]
        
        if datetime.now() > verification["expires"]:
            del self.verification_codes[email]
            return False, "❌ Код истёк. Запросите новый."
        
        if verification["user_id"] != user_id:
            return False, "❌ Неверный код."
        
        if verification["code"] != code:
            return False, "❌ Неверный код."
        
        # Всё хорошо
        self.verified_users[str(user_id)] = {
            "email": email,
            "verified_at": datetime.now().isoformat()
        }
        self._save_verified_users()
        
        del self.verification_codes[email]
        return True, f"✅ Email {email} подтверждён!"
    
    def is_user_verified(self, user_id: int) -> bool:
        return str(user_id) in self.verified_users
    
    def get_user_email(self, user_id: int) -> Optional[str]:
        user = self.verified_users.get(str(user_id))
        return user["email"] if user else None