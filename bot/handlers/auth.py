"""
Обработчик авторизации пользователей
"""
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import logging
from bot.services.auth_service import AuthService

# Состояния для ConversationHandler
EMAIL, CODE = range(2)

logger = logging.getLogger(__name__)
auth_service = AuthService()

# Декоратор для проверки авторизации
def auth_required(func):
    """Декоратор для команд, требующих авторизации"""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if auth_service.is_user_verified(user_id):
            return await func(update, context)

        text = "🔐 Для доступа к боту необходимо подтвердить email.\nИспользуйте /login для входа."
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    return wrapper

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало процесса авторизации"""
    user_id = update.effective_user.id
    
    logger.info(f"🔐 login_start для пользователя {user_id}")
    logger.info(f"📝 Тип update: {type(update)}")
    logger.info(f"📝 Есть callback_query: {update.callback_query is not None}")
    logger.info(f"📝 Есть message: {update.message is not None}")
    
    # Проверяем, авторизован ли уже
    if auth_service.is_user_verified(user_id):
        email = auth_service.get_user_email(user_id)
        text = f"✅ Вы уже авторизованы как {email}"
        
        # Определяем, откуда пришел вызов
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END
    
    # Отправляем запрос email
    text = "📧 Введите ваш корпоративный email (@edu.hse.ru или @hse.ru):\nИли отправьте /cancel для отмены."
    
    # ВАЖНО: При вызове из кнопки, update.message = None
    # Поэтому используем callback_query для ответа
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
    
    # Базовая валидация
    if '@' not in email or '.' not in email:
        await update.message.reply_text(
            "❌ Неверный формат email. Попробуйте снова:\n"
            "Или отправьте /cancel для отмены."
        )
        return EMAIL
    
    # Проверяем, разрешён ли email
    if not auth_service.is_email_authorized(email):
        await update.message.reply_text(
            f"❌ Домен {email.split('@')[-1]} не разрешён.\n"
            f"Используйте корпоративную почту (@edu.hse.ru или @hse.ru)\n"
            "или /cancel для отмены."
        )
        return EMAIL
    
    # Сохраняем email в контексте
    context.user_data['verification_email'] = email
    
    # Отправляем код
    success, message, code = auth_service.start_verification(user_id, email)
    
    await update.message.reply_text(message)
    
    if success:
        # Для отладки можно показывать код (убрать в продакшене)
        logger.info(f"Verification code for {email}: {code}")
        
        await update.message.reply_text(
            "🔢 Введите 6-значный код из письма:\n"
            "Или отправьте /cancel для отмены."
        )
        return CODE
    else:
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
        # ИЗМЕНЕНИЕ: показываем меню с кнопками вместо текстового меню
        from bot.handlers.commands import show_main_menu
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        logger.warning(f"❌ Неверный код для {email}")
        return CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена авторизации"""
    await update.message.reply_text(
        "❌ Авторизация отменена.\n"
        "Для доступа к боту необходимо подтвердить email.\n"
        "Используйте /login когда будете готовы."
    )
    context.user_data.clear()
    return ConversationHandler.END

# async def show_authorized_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Показывает меню для авторизованного пользователя"""
#     user_id = update.effective_user.id
#     email = auth_service.get_user_email(user_id)
    
#     menu_text = (
#         f"👋 Добро пожаловать!\n"
#         f"✅ Авторизован: {email}\n\n"
#         f"Доступные команды:\n"
#         f"/schedule - Расписание\n"
#         f"/notify - Уведомления\n"
#         f"/tasks - Задания\n"
#         f"/subjects - Предметы\n"
#         f"/logout - Выйти"
#     )
#     await update.message.reply_text(menu_text)

async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выход из аккаунта"""
    user_id = update.effective_user.id
    
    if auth_service.is_user_verified(user_id):
        auth_service.delete_user(user_id)
        logger.info(f"👋 Пользователь {user_id} вышел из аккаунта")
        
        # Определяем, откуда пришел вызов
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "👋 Вы успешно вышли из аккаунта.\n"
                "До свидания!"
            )
        else:
            await update.message.reply_text(
                "👋 Вы успешно вышли из аккаунта.\n"
                "До свидания!"
            )
    else:
        text = "❌ Вы не авторизованы."
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        else:
            await update.message.reply_text(text)