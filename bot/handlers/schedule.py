"""
Обработчик команд для расписания
"""
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from bot.handlers.auth import auth_required, auth_service
from bot.utils.database import (
    SessionLocal,
    get_today_schedule,
    get_schedule_between,
    get_schedule_by_date,
    get_week_schedule,
    format_schedule_message,
)
from bot.services.selection import get_selection_by_telegram_id
from bot.utils.ui import answer, show_screen

# Состояния ConversationHandler для ввода произвольного периода
CUSTOM_FROM = 10
CUSTOM_TO   = 11


def _selection(db, update):
    """Выбор студента из «📚 Мои предметы» — расписание только по отмеченным предметам."""
    return get_selection_by_telegram_id(db, update.effective_user.id)

@auth_required
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик команды /schedule)"""
    if await _show_module_schedule(update, context):
        return   # открыт нетекущий модуль — свой экран (по неделям)

    # Создаем клавиатуру с кнопками в один столбик
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="schedule_today")],
        [InlineKeyboardButton("📆 Завтра", callback_data="schedule_tomorrow")],
        [InlineKeyboardButton("📅 На эту неделю", callback_data="schedule_week")],
        [InlineKeyboardButton("📅 На следующую неделю", callback_data="schedule_next_week")],
        [InlineKeyboardButton("📆 На месяц", callback_data="schedule_month")],
        [InlineKeyboardButton("🗓 Указать период", callback_data="schedule_custom")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
    ]   
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📅 **Выберите период для просмотра расписания:**"

    # show_screen: правит текущее сообщение (кнопка) или удаляет предыдущий
    # экран и шлёт новое (команда /schedule) — история в чате не копится
    await show_screen(update, context, message, reply_markup=reply_markup, parse_mode='Markdown')

async def show_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик нажатия на кнопку)"""
    # Перенаправляем на show_schedule
    await show_schedule(update, context)

async def schedule_today_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на сегодня для всех потоков (кнопка "Сегодня" или команда /today)"""
    user_id = update.effective_user.id

    if not auth_service.is_user_verified(user_id):
        await show_screen(update, context, "🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        today = datetime.now().date()
        schedules = get_today_schedule(db, _selection(db, update))
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not schedules:
            await show_screen(
                update, context,
                f"📅 На {today.strftime('%d.%m.%Y')} занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        message = format_schedule_message(schedules, f"📅 Расписание на {today.strftime('%d.%m.%Y')}")
        
        await show_screen(
            update, context, message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

async def schedule_tomorrow_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на завтра"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        tomorrow = datetime.now().date() + timedelta(days=1)
        schedules = get_schedule_by_date(db, tomorrow, _selection(db, update))
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На {tomorrow.strftime('%d.%m.%Y')} занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        message = format_schedule_message(schedules, f"📅 Расписание на {tomorrow.strftime('%d.%m.%Y')}")
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

async def schedule_week_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на текущую неделю"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        schedules = get_week_schedule(db, _selection(db, update))
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Определяем начало и конец недели
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На неделю {monday.strftime('%d.%m')} - {sunday.strftime('%d.%m.%Y')} занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        # Группируем по дням: ключ — реальная дата (не строка!), иначе при
        # сортировке "01.10.2026" оказывается раньше "28.09.2026" по алфавиту
        # и период, пересекающий границу месяца, показывается вперемешку
        days = defaultdict(list)
        for sch in schedules:
            days[sch.Schedule.lesson_date].append(sch)
        
        message = f"📅 **Расписание на неделю {monday.strftime('%d.%m')} - {sunday.strftime('%d.%m.%Y')}**\n\n"
        
        for day in sorted(days):
            lessons = days[day]
            message += f"**{day.strftime('%d.%m.%Y')}:**\n"
            for sch in lessons:
                lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
                teacher_name = f"{sch.last_name} {sch.first_name}"
                if hasattr(sch, 'middle_name') and sch.middle_name:
                    teacher_name += f" {sch.middle_name}"
                
                message += (
                    f"  ⏰ {lesson_time} – {sch.subject_name} ({sch.lesson_type_name})\n"
                    f"     👨‍🏫 {teacher_name}\n"
                    f"     👥 {sch.stream_name}\n"
                )
                # Добавляем ссылку на встречу, если есть
                if sch.Schedule.meeting_link:
                    message += f"     🔗 [MTS-Link]({sch.Schedule.meeting_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"

        # Telegram ограничивает сообщение 4096 символами
        if len(message) > 4000:
            message = message[:3950] + "\n\n_...список обрезан, уточните период_"

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

async def schedule_next_week_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на следующую неделю"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        # Рассчитываем следующую неделю
        today = datetime.now().date()
        next_monday = today + timedelta(days=(7 - today.weekday()))
        next_sunday = next_monday + timedelta(days=6)
        
        schedules = get_schedule_between(db, next_monday, next_sunday, _selection(db, update))
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На следующей неделе ({next_monday.strftime('%d.%m')} - {next_sunday.strftime('%d.%m.%Y')}) занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        # Группируем по дням: ключ — реальная дата (не строка!), иначе при
        # сортировке "01.10.2026" оказывается раньше "28.09.2026" по алфавиту
        # и период, пересекающий границу месяца, показывается вперемешку
        days = defaultdict(list)
        for sch in schedules:
            days[sch.Schedule.lesson_date].append(sch)
        
        message = f"📅 **Расписание на следующую неделю {next_monday.strftime('%d.%m')} - {next_sunday.strftime('%d.%m.%Y')}**\n\n"
        
        for day in sorted(days):
            lessons = days[day]
            message += f"**{day.strftime('%d.%m.%Y')}:**\n"
            for sch in lessons:
                lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
                teacher_name = f"{sch.last_name} {sch.first_name}"
                if hasattr(sch, 'middle_name') and sch.middle_name:
                    teacher_name += f" {sch.middle_name}"
                
                message += (
                    f"  ⏰ {lesson_time} – {sch.subject_name} ({sch.lesson_type_name})\n"
                    f"     👨‍🏫 {teacher_name}\n"
                    f"     👥 {sch.stream_name}\n"
                )
                # Добавляем ссылку на встречу, если есть
                if sch.Schedule.meeting_link:
                    message += f"     🔗 [MTS-Link]({sch.Schedule.meeting_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"

        # Telegram ограничивает сообщение 4096 символами
        if len(message) > 4000:
            message = message[:3950] + "\n\n_...список обрезан, уточните период_"

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

async def schedule_month_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на месяц"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        # Рассчитываем начало и конец месяца
        today = datetime.now().date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year+1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month+1, day=1) - timedelta(days=1)
        
        schedules = get_schedule_between(db, month_start, month_end, _selection(db, update))
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Форматируем месяц как число (03, 04 и т.д.)
        month_str = month_start.strftime('%m')
        year_str = month_start.strftime('%Y')
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На {month_str}.{year_str} занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        # Группируем по дням: ключ — реальная дата (не строка!), иначе при
        # сортировке "01.10.2026" оказывается раньше "28.09.2026" по алфавиту
        # и период, пересекающий границу месяца, показывается вперемешку
        days = defaultdict(list)
        for sch in schedules:
            days[sch.Schedule.lesson_date].append(sch)
        
        message = f"📅 **Расписание на {month_str}.{year_str}**\n\n"
        
        for day in sorted(days):
            lessons = days[day]
            message += f"**{day.strftime('%d.%m.%Y')}:**\n"
            for sch in lessons:
                lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
                teacher_name = f"{sch.last_name} {sch.first_name}"
                if hasattr(sch, 'middle_name') and sch.middle_name:
                    teacher_name += f" {sch.middle_name}"
                
                message += (
                    f"  ⏰ {lesson_time} – {sch.subject_name} ({sch.lesson_type_name})\n"
                    f"     👨‍🏫 {teacher_name}\n"
                    f"     👥 {sch.stream_name}\n"
                )
                # Добавляем ссылку на встречу, если есть
                if sch.Schedule.meeting_link:
                    message += f"     🔗 [MTS-Link]({sch.Schedule.meeting_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"

        # Telegram ограничивает сообщение 4096 символами
        if len(message) > 4000:
            message = message[:3950] + "\n\n_...список обрезан, уточните период_"

        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

# Обновляем функцию show_group_schedule - больше не нужна, но оставим для совместимости
async def show_group_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устаревшая функция, перенаправляет на show_schedule"""
    await show_schedule(update, context)


# ── Произвольный период ──────────────────────────────────────────────────────

async def schedule_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Кнопка «Указать период» — запрашиваем дату начала."""
    query = update.callback_query
    user_id = update.effective_user.id

    if not auth_service.is_user_verified(user_id):
        await query.answer()
        await query.edit_message_text("🔐 Требуется авторизация")
        return ConversationHandler.END

    await query.answer()
    await query.edit_message_text(
        "🗓 *Введите дату начала периода* в формате ДД.ММ.ГГГГ\n"
        "Например: `01.06.2026`\n\n"
        "Для отмены введите /cancel",
        parse_mode='Markdown'
    )
    return CUSTOM_FROM


async def schedule_custom_from(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем дату начала, спрашиваем дату конца."""
    text = update.message.text.strip()
    try:
        date_from = datetime.strptime(text, '%d.%m.%Y').date()
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите дату как ДД.ММ.ГГГГ, например `09.06.2026`",
            parse_mode='Markdown'
        )
        return CUSTOM_FROM

    context.user_data['custom_from'] = date_from
    await update.message.reply_text(
        f"✅ Начало: *{date_from.strftime('%d.%m.%Y')}*\n\n"
        "🗓 Теперь введите *дату конца* периода (ДД.ММ.ГГГГ):",
        parse_mode='Markdown'
    )
    return CUSTOM_TO


async def schedule_custom_to(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получаем дату конца, показываем расписание."""
    text = update.message.text.strip()
    date_from = context.user_data.get('custom_from')

    try:
        date_to = datetime.strptime(text, '%d.%m.%Y').date()
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Введите дату как ДД.ММ.ГГГГ, например `15.06.2026`",
            parse_mode='Markdown'
        )
        return CUSTOM_TO

    if date_to < date_from:
        await update.message.reply_text(
            "❌ Дата конца не может быть раньше даты начала. Введите дату конца заново:",
        )
        return CUSTOM_TO

    if (date_to - date_from).days > 90:
        await update.message.reply_text(
            "❌ Период не может быть больше 90 дней. Введите дату конца заново:",
        )
        return CUSTOM_TO

    keyboard = [
        [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    db = SessionLocal()
    try:
        schedules = get_schedule_between(db, date_from, date_to, _selection(db, update))

        title = (f"📅 Расписание {date_from.strftime('%d.%m.%Y')} "
                 f"– {date_to.strftime('%d.%m.%Y')}")

        if not schedules:
            await update.message.reply_text(
                f"{title}\n\nЗанятий в этот период нет 🎉",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Группируем по дням
        days = defaultdict(list)
        for sch in schedules:
            days[sch.Schedule.lesson_date].append(sch)

        message = f"*{title}*\n\n"
        for day in sorted(days):
            message += f"*{day.strftime('%d.%m.%Y')}:*\n"
            for sch in days[day]:
                lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
                teacher_name = f"{sch.last_name} {sch.first_name or ''}".strip()
                message += (
                    f"  ⏰ {lesson_time} – {sch.subject_name} ({sch.lesson_type_name})\n"
                    f"     👨‍🏫 {teacher_name} | 👥 {sch.stream_name}\n"
                )
                if sch.Schedule.meeting_link:
                    message += f"     🔗 [MTS-Link]({sch.Schedule.meeting_link})\n"
            message += "\n"

        # Telegram ограничивает сообщение 4096 символами
        if len(message) > 4000:
            message = message[:3950] + "\n\n_...список обрезан, уточните период_"

        await update.message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    finally:
        db.close()

    return ConversationHandler.END


async def schedule_custom_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена ввода периода."""
    keyboard = [[InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")]]
    await update.message.reply_text(
        "Отменено.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END

# ── Нетекущий модуль: расписание по неделям (docs/ui_module.md, п. 5) ─────────

def _module_lessons(db, update, monday, sunday):
    """[(дата, время, короткое название, тип)] за неделю — только «Мои предметы»."""
    from types import SimpleNamespace
    from bot.services.deadlines import display_name
    rows = get_schedule_between(db, monday, sunday, _selection(db, update))
    return [(r.Schedule.lesson_date, r.Schedule.lesson_time,
             display_name(SimpleNamespace(name=r.subject_name, short_name=r.subject_short_name)),
             r.lesson_type_name) for r in rows]


def _has_lessons(db, module) -> bool:
    from bot.models import Schedule
    return db.query(Schedule.id).filter(
        Schedule.lesson_date.between(module.start_date, module.end_date)).first() is not None


async def _show_module_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Экран «📅 Расписание» в нетекущем модуле. False — модуль текущий, показать обычный экран."""
    from bot.services import modules as M
    from bot.services.deadlines import now_msk

    db = SessionLocal()
    try:
        v = M.get_view_by_telegram_id(db, update.effective_user.id, now_msk().date())
        if v.is_current:
            return False
        module = v.view
        has_lessons = _has_lessons(db, module)
    finally:
        db.close()

    await answer(update, context)
    rows = []
    if has_lessons:
        n = M.nearest_week(module, v.today)
        rows += [[InlineKeyboardButton("📅 По неделям", callback_data=f"schedule_mw_{module.id}_{n}")],
                 [InlineKeyboardButton("🗓 Указать период", callback_data="schedule_custom")]]
    rows += [v.back_button('schedule'), [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]]
    await show_screen(update, context, M.schedule_screen_text(module, v.banner, has_lessons),
                      reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')
    return True


async def schedule_module_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """schedule_mw_<module_id>_<n>: неделя n модуля. module_id в callback — чтобы кнопка работала,
    даже если модуль переключили в другом окне."""
    from bot.models import Module
    from bot.services import modules as M
    from bot.services.deadlines import now_msk

    await answer(update, context)
    if not auth_service.is_user_verified(update.effective_user.id):
        await show_screen(update, context, "🔐 Требуется авторизация")
        return
    _, _, module_id, n = update.callback_query.data.split("_")
    db = SessionLocal()
    try:
        module = db.get(Module, int(module_id))
        if module is None:
            db.close()
            await show_schedule(update, context)
            return
        total = M.week_count(module)
        n = min(max(int(n), 1), total)
        monday, sunday = M.week_bounds(module, n)
        lessons = _module_lessons(db, update, monday, sunday)
        today = now_msk().date()
        current = M.get_current_module(db, today)
        banner = M.module_banner(module, current, today)
    finally:
        db.close()

    nav = []
    if n > 1:
        nav.append(InlineKeyboardButton(f"◀️ Неделя {n - 1}", callback_data=f"schedule_mw_{module.id}_{n - 1}"))
    if n < total:
        nav.append(InlineKeyboardButton(f"Неделя {n + 1} ▶️", callback_data=f"schedule_mw_{module.id}_{n + 1}"))
    rows = ([nav] if nav else []) + [
        [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")],
    ]
    await show_screen(update, context, M.render_week(module, n, lessons, banner),
                      reply_markup=InlineKeyboardMarkup(rows), parse_mode='HTML')
