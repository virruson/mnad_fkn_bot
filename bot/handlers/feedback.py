"""
Раздел «💬 Обратная связь»: спасибо автору, обращение, ответ автора reply'ем.
Макет — docs/ui_feedback.md, задача — docs/feedback_developer.md.

callback_data:
  fb                         экран
  fb_thanks                  «🤍 / ❤️ Спасибо»
  fb_write                   написать (вход в ConversationHandler)
  fb_write_s_<subject_id>    «✏️ Неточность?» из карточки предмета в дедлайнах
  fb_write_r_<feedback_id>   «✏️ Ответить» под ответом автора
  fb_cancel                  «✖️ Отмена» на экране ввода (то же, что /cancel)
  fb_close                   «✖️ Закрыть» под ответом автора — убрать сообщение из чата
Ответ автора — reply на обращение в чате FEEDBACK_CHAT_ID (author_reply, группа -1).
"""
import logging
import re
from datetime import timedelta

from sqlalchemy import func
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden
from telegram.ext import ApplicationHandlerStop, ContextTypes, ConversationHandler

from bot.handlers.auth import auth_service
from bot.models import Feedback, Subject, User
from bot.services import feedback as F
from bot.services.deadlines import now_msk
from bot.services.progress import subject_label
from bot.utils.database import SessionLocal
from bot.utils.ui import show_screen

logger = logging.getLogger(__name__)

FB_INPUT = 0
STATE_KEY = "fb_input"
MAIN_MENU = [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
CANCEL = InlineKeyboardMarkup([[InlineKeyboardButton("✖️ Отмена", callback_data="fb_cancel")]])


def _user(db, telegram_id):
    return db.query(User).filter(User.telegram_id == str(telegram_id)).first()


def _thanks_total(db) -> int:
    return db.query(func.count(User.id)).filter(User.thanked_at.isnot(None)).scalar() or 0


async def _not_authorized(update: Update, context) -> bool:
    if auth_service.is_user_verified(update.effective_user.id):
        return False
    if update.callback_query:
        await update.callback_query.answer()
    await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
    return True


# ---------------------------------------------------------------------------
# Экран «💬 Обратная связь» и «спасибо»
# ---------------------------------------------------------------------------

async def _render(update: Update, context, toast: str | None = None):
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        label = F.thanks_label(bool(user and user.thanked_at), _thanks_total(db))
    finally:
        db.close()
    if update.callback_query:
        await update.callback_query.answer(toast)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data="fb_thanks")],
        [InlineKeyboardButton("✏️ Написать", callback_data="fb_write")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")],
    ])
    await show_screen(update, context, F.screen_text(), reply_markup=keyboard, parse_mode='HTML')


async def show_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «💬 Обратная связь» (fb) и /feedback."""
    if not F.enabled():
        if update.callback_query:
            await update.callback_query.answer()
        return
    if await _not_authorized(update, context):
        return
    await _render(update, context)


async def thanks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """fb_thanks: первое нажатие — записать и сообщить автору без звука; повторное — только подсказка."""
    if await _not_authorized(update, context):
        return
    tg = update.effective_user
    db = SessionLocal()
    try:
        user = _user(db, tg.id)
        first = user is not None and user.thanked_at is None
        if first:
            user.thanked_at = now_msk()
            db.commit()
        total = _thanks_total(db)
    finally:
        db.close()

    if first:
        try:
            await context.bot.send_message(chat_id=F.chat_id(), text=F.thanks_message(tg.full_name, tg.username, total),
                                           parse_mode='HTML', disable_notification=True)
        except Exception as e:
            logger.error(f"[FEEDBACK] thanks → author FAILED: {e}")
    await _render(update, context, F.THANKS_FIRST if first else F.THANKS_AGAIN)


# ---------------------------------------------------------------------------
# Ввод обращения
# ---------------------------------------------------------------------------

def _back(state: dict) -> str:
    """Куда вести «◀️ Назад» на экране лимита."""
    if state['kind'] == 'subject':
        return f"deadlines_subj_{state['subject_id']}"
    return "fb" if state['kind'] == 'menu' else "back_to_menu"


async def write_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """fb_write / fb_write_s_<subject_id> / fb_write_r_<feedback_id>."""
    query = update.callback_query
    if not F.enabled():
        await query.answer()
        return ConversationHandler.END
    if await _not_authorized(update, context):
        return ConversationHandler.END

    m = re.fullmatch(r"fb_write(?:_(s|r)_(\d+))?", query.data)
    kind = {'s': 'subject', 'r': 'reply'}.get(m.group(1), 'menu')
    ref = int(m.group(2)) if m.group(2) else None
    state = {'kind': kind, 'subject_id': None, 'reply_to': None, 'context': None}

    now = now_msk()
    db = SessionLocal()
    try:
        user = _user(db, update.effective_user.id)
        if kind == 'subject':
            subject = db.get(Subject, ref)
            if subject is None:
                await query.answer()
                return ConversationHandler.END
            name = subject_label(subject)
            state.update(subject_id=ref, context=f"Дедлайны · {name}", title=F.input_title(kind, name))
        elif kind == 'reply':
            original = db.get(Feedback, ref)
            if original is None or user is None or original.user_id != user.id:
                await query.answer()          # чужое или удалённое обращение — игнорируем
                return ConversationHandler.END
            state.update(reply_to=ref, context=f"ответ на №{ref}", title=F.input_title(kind, feedback_id=ref))
        else:
            state['title'] = F.input_title(kind)
        recent = [t for (t,) in db.query(Feedback.created_at).filter(
            Feedback.user_id == user.id, Feedback.created_at > now - F.LIMIT_WINDOW)] if user else []
    finally:
        db.close()

    await query.answer()
    # «✏️ Ответить» стоит под фоновым ответом автора — его не трогаем, экран открываем новым сообщением
    new_message = kind == 'reply'
    until = F.limit_until(recent, now)
    if until is not None:
        await show_screen(update, context, F.limit_text(until, now), new_message=new_message, parse_mode='HTML',
                          reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data=_back(state))]]))
        return ConversationHandler.END

    context.user_data[STATE_KEY] = state
    await show_screen(update, context, F.input_prompt(kind, state['title']), new_message=new_message,
                      reply_markup=CANCEL, parse_mode='HTML')
    return FB_INPUT


async def write_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get(STATE_KEY)
    if state is None:
        return ConversationHandler.END
    text = update.message.text.strip()
    if len(text) > F.FEEDBACK_MAX_LEN:
        await show_screen(update, context, F.too_long(state['title'], len(text)), reply_markup=CANCEL, parse_mode='HTML')
        return FB_INPUT
    if not text:
        await show_screen(update, context, F.input_prompt(state['kind'], state['title']), reply_markup=CANCEL,
                          parse_mode='HTML')
        return FB_INPUT

    tg = update.effective_user
    db = SessionLocal()
    try:
        user = _user(db, tg.id)
        if user is None:
            context.user_data.pop(STATE_KEY, None)
            await show_screen(update, context, "🔐 Сначала авторизуйтесь.")
            return ConversationHandler.END
        item = Feedback(user_id=user.id, text=text, context=state['context'], created_at=now_msk())
        db.add(item)
        db.commit()
        message = F.author_message(item.id, tg.full_name, tg.username, user.email, state['context'], text)
        try:
            sent = await context.bot.send_message(chat_id=F.chat_id(), text=message, parse_mode='HTML')
            item.admin_message_id = sent.message_id
            db.commit()
        except Exception as e:   # обращение уже в БД — не теряется, студенту всё равно «Отправлено»
            logger.error(f"[FEEDBACK] №{item.id} → author FAILED: {e}")
    finally:
        db.close()

    context.user_data.pop(STATE_KEY, None)
    rows = []
    if state['kind'] == 'subject':
        rows.append([InlineKeyboardButton("◀️ К предмету", callback_data=f"deadlines_subj_{state['subject_id']}")])
    rows.append(MAIN_MENU)
    await show_screen(update, context, F.SENT, reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')
    return ConversationHandler.END


async def write_not_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Фото, стикер, голосовое, файл — подпись не берём, ждём текст."""
    state = context.user_data.get(STATE_KEY)
    if state is None:
        return ConversationHandler.END
    await show_screen(update, context, F.not_text(state['title']), reply_markup=CANCEL, parse_mode='HTML')
    return FB_INPUT


async def write_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/cancel и «✖️ Отмена» — туда, откуда пришли (ввод уже закрыт по таймауту — в главное меню)."""
    state = context.user_data.pop(STATE_KEY, None) or {'kind': 'reply'}
    if state['kind'] == 'subject':
        from bot.handlers.deadlines import render_subject_card_screen
        if update.callback_query:
            await update.callback_query.answer()   # меню и экран «Обратной связи» отвечают сами
        await render_subject_card_screen(update, context, state['subject_id'])
    elif state['kind'] == 'menu':
        await _render(update, context)
    else:
        from bot.handlers.commands import show_main_menu
        await show_main_menu(update, context)
    return ConversationHandler.END


async def close_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """fb_close: убрать «Ответ автора» из чата. Старше 48 ч Telegram удалить не даст — тогда снимаем кнопки."""
    query = update.callback_query
    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        await query.edit_message_reply_markup(reply_markup=None)


# ---------------------------------------------------------------------------
# Ответ автора: reply на «Обращение №N» в чате FEEDBACK_CHAT_ID
# ---------------------------------------------------------------------------

async def _react(bot, chat_id: int, message_id: int) -> bool:
    """Реакция 👍 (Bot API 7.0). В PTB 20.7 нет set_message_reaction — вызываем метод API напрямую."""
    try:
        await bot._post('setMessageReaction', {
            'chat_id': chat_id, 'message_id': message_id,
            'reaction': [{'type': 'emoji', 'emoji': '👍'}],
        })
        return True
    except Exception as e:
        logger.warning(f"[FEEDBACK] реакция недоступна: {e}")
        return False


async def author_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    target = message.reply_to_message
    db = SessionLocal()
    try:
        item = db.query(Feedback).filter(Feedback.admin_message_id == target.message_id).first()
        if item is None:
            if target.from_user and target.from_user.id == context.bot.id:
                raise ApplicationHandlerStop   # reply на другое сообщение бота — молчим
            return                             # обычное сообщение — пусть обработают другие хэндлеры
        student_chat = item.user.telegram_id
        text = F.answer_message(item.created_at, item.text, message.text)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("✏️ Ответить", callback_data=f"fb_write_r_{item.id}"),
                                        InlineKeyboardButton("✖️ Закрыть", callback_data="fb_close")]])
        try:
            await context.bot.send_message(chat_id=student_chat, text=text, parse_mode='HTML', reply_markup=markup)
        except Forbidden:
            await message.reply_text(F.NOT_DELIVERED_BLOCKED)
            raise ApplicationHandlerStop
        except Exception as e:
            logger.error(f"[FEEDBACK] ответ на №{item.id} FAILED: {e}")
            await message.reply_text(f"⚠️ Не доставлено: {e}")
            raise ApplicationHandlerStop
        if item.answered_at is None:
            item.answered_at = now_msk()
            db.commit()
    finally:
        db.close()

    if not await _react(context.bot, message.chat_id, message.message_id):
        await message.reply_text(F.DELIVERED)
    raise ApplicationHandlerStop
