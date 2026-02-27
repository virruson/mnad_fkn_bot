"""
Обработчик авторизации пользователей
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters
from bot.services.auth_service import AuthService

# Состояния для ConversationHandler
EMAIL, CODE = range(2)

logger = logging.getLogger(__name__)
auth_service = AuthService()

# Декоратор для проверки авторизации
def auth_required(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if auth_service.is_user_verified(user_id):
            return await func(update, context)
        else:
            # Определяем, откуда пришел вызов
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "🔐 Для доступа к этой функции необходимо авторизоваться.\n"
                    "Используйте /login для входа."
                )
            else:
                await update.message.reply_text(
                    "🔐 Для доступа к этой функции необходимо авторизоваться.\n"
                    "Используйте /login для входа."
                )
            return ConversationHandler.END
    return wrapper

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса авторизации"""
    user_id = update.effective_user.id
    
    logger.info(f"🔐 login_start для пользователя {user_id}")
    logger.info(f"📝 Тип update: {type(update)}")
    logger.info(f"📝 Есть callback_query: {update.callback_query is not None}")
    
    # Проверяем, авторизован ли уже
    if auth_service.is_user_verified(user_id):
        email = auth_service.get_user_email(user_id)
        text = f"✅ Вы уже авторизованы как {email}"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    
    # Отправляем запрос email
    text = "📧 Введите ваш корпоративный email (@edu.hse.ru или @hse.ru):\nИли отправьте /cancel для отмены."
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text)
        # ПРИНУДИТЕЛЬНО устанавливаем состояние через user_data
        context.user_data['expected_state'] = EMAIL
        logger.info(f"📝 Установлено ожидание EMAIL для пользователя {user_id}")
    else:
        await update.message.reply_text(text)
    
    return EMAIL

async def get_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение email от пользователя"""
    email = update.message.text.strip().lower()
    user_id = update.effective_user.id
    
    logger.info(f"📧 get_email вызван для пользователя {user_id}")
    logger.info(f"📧 Получен email: {email}")
    
    # Базовая валидация
    if '@' not in email or '.' not in email:
        await update.message.reply_text("❌ Неверный формат email. Попробуйте снова:")
        return EMAIL
    
    # Проверяем домен
    if not auth_service.is_email_authorized(email):
        await update.message.reply_text(
            f"❌ Домен {email.split('@')[-1]} не разрешён.\n"
            "Используйте @edu.hse.ru или @hse.ru"
        )
        return EMAIL
    
    # Сохраняем email
    context.user_data['verification_email'] = email
    
    # Отправляем код
    logger.info(f"📧 Вызываем start_verification для {email}")
    success, message, code = auth_service.start_verification(user_id, email)
    
    await update.message.reply_text(message)
    
    if success:
        logger.info(f"✅ Код отправлен на {email}")
        logger.info(f"🔑 Код: {code}")
        await update.message.reply_text("🔢 Введите 6-значный код из письма:")
        # Устанавливаем следующее состояние
        context.user_data['expected_state'] = CODE
        return CODE
    else:
        logger.error(f"❌ Не удалось отправить код на {email}")
        # Очищаем состояние
        context.user_data.pop('expected_state', None)
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение кода подтверждения"""
    code = update.message.text.strip()
    user_id = update.effective_user.id
    email = context.user_data.get('verification_email')
    
    logger.info(f"🔑 get_code вызван для пользователя {user_id}")
    logger.info(f"🔑 Получен код: {code}, email: {email}")
    
    if not email:
        await update.message.reply_text("❌ Ошибка. Начните заново с /login")
        context.user_data.pop('expected_state', None)
        return ConversationHandler.END
    
    # Проверка формата кода
    if not code.isdigit() or len(code) != 6:
        await update.message.reply_text("❌ Код должен быть 6-значным числом. Попробуйте снова:")
        return CODE
    
    # Проверяем код
    logger.info(f"🔍 Проверяем код {code} для {email}")
    success, message = auth_service.verify_code(user_id, email, code)
    await update.message.reply_text(message)
    
    if success:
        logger.info(f"✅ Пользователь {user_id} успешно авторизован")
        # Очищаем временные данные
        context.user_data.clear()
        # После успешной авторизации показываем меню
        from bot.handlers.commands import show_main_menu
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        logger.warning(f"❌ Неверный код для {email}")
        return CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена авторизации"""
    user_id = update.effective_user.id
    logger.info(f"❌ Авторизация отменена пользователем {user_id}")
    
    await update.message.reply_text("❌ Авторизация отменена.")
    context.user_data.clear()
    return ConversationHandler.END

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из аккаунта"""
    user_id = update.effective_user.id
    
    if auth_service.is_user_verified(user_id):
        # Удаляем пользователя из верифицированных
        del auth_service.verified_users[str(user_id)]
        auth_service._save_verified_users()
        logger.info(f"👋 Пользователь {user_id} вышел из аккаунта")
        await update.message.reply_text("👋 Вы вышли из аккаунта.")
    else:
        await update.message.reply_text("❌ Вы не авторизованы.")

def get_auth_conversation_handler():
    """Возвращает ConversationHandler"""
    # Мы используем упрощенный ConversationHandler, так как основная логика
    # будет обрабатываться через глобальный message_handler
    return ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_email)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )