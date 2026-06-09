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
from typing import Optional
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class AuthService:
    """Сервис для авторизации пользователей по email"""

    def __init__(self):
        domains_str = os.getenv('ALLOWED_DOMAINS', '')
        self.allowed_domains = domains_str.split(',')
        self.whitelist = self._load_whitelist()

        # Коды верификации живут только в памяти (10 мин — этого достаточно)
        self.verification_codes: dict = {}

        # Настройки email
        self.sender_email = os.getenv('VERIFICATION_EMAIL')
        self.sender_password = os.getenv('VERIFICATION_EMAIL_PASSWORD')
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.yandex.ru')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))

        logger.info("=" * 50)
        logger.info("🔧 НАСТРОЙКИ EMAIL:")
        logger.info(f"📧 EMAIL: {self.sender_email}")
        logger.info(f"🔑 PASSWORD: {'✅ установлен' if self.sender_password else '❌ НЕ УСТАНОВЛЕН'}")
        logger.info(f"🔌 SMTP: {self.smtp_server}:{self.smtp_port}")
        logger.info("=" * 50)

    # ------------------------------------------------------------------
    # Whitelist (файл остаётся — это список разрешённых email, не сессии)
    # ------------------------------------------------------------------

    def _load_whitelist(self) -> list:
        whitelist_file = Path('data/whitelist.json')
        if whitelist_file.exists():
            try:
                import json
                with open(whitelist_file, 'r') as f:
                    content = f.read().strip()
                    return json.loads(content) if content else []
            except Exception:
                return []
        return []

    # ------------------------------------------------------------------
    # Проверки email
    # ------------------------------------------------------------------

    def is_allowed_domain(self, email: str) -> bool:
        domain = email.split('@')[-1].lower()
        return domain in self.allowed_domains

    def is_in_whitelist(self, email: str) -> bool:
        return email.lower() in [e.lower() for e in self.whitelist]

    def is_email_authorized(self, email: str) -> bool:
        return self.is_allowed_domain(email) or self.is_in_whitelist(email)

    # ------------------------------------------------------------------
    # Проверка сессии — теперь через БД
    # ------------------------------------------------------------------

    def is_user_verified(self, user_id: int) -> bool:
        from bot.utils.database import SessionLocal
        from bot.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(
                User.telegram_id == str(user_id),
                User.is_verified == True
            ).first()
            return user is not None
        finally:
            db.close()

    def get_user_email(self, user_id: int) -> Optional[str]:
        from bot.utils.database import SessionLocal
        from bot.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()
            return user.email if user else None
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Коды верификации
    # ------------------------------------------------------------------

    def generate_verification_code(self) -> str:
        return ''.join(random.choices(string.digits, k=6))

    def send_verification_email(self, recipient: str, code: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = recipient
            msg['Subject'] = 'Код подтверждения для бота ФКН'

            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #333;">Подтверждение email для бота ФКН</h2>
                <p>Ваш код подтверждения:</p>
                <div style="background-color: #f0f0f0; padding: 15px; font-size: 24px;
                          font-weight: bold; text-align: center; letter-spacing: 5px;
                          border-radius: 5px;">
                    {code}
                </div>
                <p>Код действителен в течение 10 минут.</p>
                <p>Если вы не запрашивали этот код, просто проигнорируйте это письмо.</p>
                <hr>
                <p style="color: #666; font-size: 12px;">Бот расписания ФКН</p>
            </body>
            </html>
            """

            msg.attach(MIMEText(html, 'html'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"Verification code sent to {recipient}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}")
            return False

    def start_verification(self, user_id: int, email: str) -> tuple:
        if not self.is_email_authorized(email):
            return False, "❌ Этот email не разрешён.", None

        code = self.generate_verification_code()
        expires = datetime.now() + timedelta(minutes=10)

        self.verification_codes[email] = {
            "code": code,
            "expires": expires,
            "user_id": user_id,
        }

        if self.send_verification_email(email, code):
            return True, f"✅ Код отправлен на {email}\n⏰ Действителен 10 минут.", code
        else:
            return False, "❌ Не удалось отправить код.", None

    def verify_code(self, user_id: int, email: str, code: str) -> tuple:
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

        # Код верный — сохраняем/обновляем пользователя в БД
        self._upsert_user(user_id, email)
        del self.verification_codes[email]
        return True, f"✅ Email {email} подтверждён!"

    # ------------------------------------------------------------------
    # Запись в БД
    # ------------------------------------------------------------------

    def _upsert_user(self, user_id: int, email: str) -> None:
        from bot.utils.database import SessionLocal
        from bot.models import User
        now = datetime.now()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()
            if user:
                user.email = email
                user.is_verified = True
                user.verified_at = now
                user.last_login = now
                user.updated_at = now
            else:
                user = User(
                    telegram_id=str(user_id),
                    email=email,
                    is_verified=True,
                    verified_at=now,
                    last_login=now,
                )
                db.add(user)
            db.commit()
            logger.info(f"✅ Пользователь {user_id} ({email}) сохранён в БД")
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка сохранения пользователя {user_id}: {e}")
            raise
        finally:
            db.close()

    def delete_user(self, user_id: int) -> None:
        """Выход — помечаем как not verified (данные не удаляем)"""
        from bot.utils.database import SessionLocal
        from bot.models import User
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == str(user_id)).first()
            if user:
                user.is_verified = False
                user.updated_at = datetime.now()
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Ошибка при logout пользователя {user_id}: {e}")
        finally:
            db.close()
