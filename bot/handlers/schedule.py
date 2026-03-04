"""
Обработчик команд для расписания
"""
from datetime import datetime, timedelta
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.handlers.auth import auth_required, auth_service
from bot.utils.database import (
    SessionLocal, 
    get_today_schedule, 
    get_schedule_by_date, 
    get_week_schedule, 
    get_streams, 
    format_schedule_message, 
    format_schedule_simple
)
from bot.models import Stream, Subject, Teacher, LessonType, Schedule

@auth_required
async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрая команда для показа расписания на сегодня"""
    user_id = update.effective_user.id
    
    db = SessionLocal()
    try:
        today = datetime.now().date()
        schedules = get_today_schedule(db)
        
        if not schedules:
            await update.message.reply_text(f"📅 На {today.strftime('%d.%m.%Y')} занятий нет 🎉")
            return
        
        # Используем форматирование для всех потоков
        # Группируем по потокам
        streams_dict = {}
        for sch in schedules:
            stream_name = sch.stream_name
            if stream_name not in streams_dict:
                streams_dict[stream_name] = []
            streams_dict[stream_name].append(sch)
        
        message = f"📅 **Расписание на {today.strftime('%d.%m.%Y')}**\n\n"
        
        for stream_name, lessons in streams_dict.items():
            message += f"**{stream_name}:**\n"
            for sch in lessons:
                lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
                teacher_name = f"{sch.last_name} {sch.first_name}"
                if hasattr(sch, 'middle_name') and sch.middle_name:
                    teacher_name += f" {sch.middle_name}"
                
                message += (
                    f"  ⏰ **{lesson_time}** – {sch.subject_name} ({sch.lesson_type_name})\n"
                    f"     👨‍🏫 {teacher_name}\n"
                )
                if sch.Schedule.zoom_link:
                    message += f"     🔗 [Zoom]({sch.Schedule.zoom_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

@auth_required
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик команды /schedule)"""
    
    # Создаем клавиатуру с кнопками в один столбик
    keyboard = [
        [InlineKeyboardButton("📅 Сегодня", callback_data="schedule_today")],
        [InlineKeyboardButton("📆 Завтра", callback_data="schedule_tomorrow")],
        [InlineKeyboardButton("📅 На эту неделю", callback_data="schedule_week")],
        [InlineKeyboardButton("📅 На следующую неделю", callback_data="schedule_next_week")],
        [InlineKeyboardButton("📆 На месяц", callback_data="schedule_month")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")]
    ]   
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📅 **Выберите период для просмотра расписания:**"
    
    # Определяем, откуда пришел вызов
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            message, 
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def show_schedule_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание (обработчик нажатия на кнопку)"""
    # Перенаправляем на show_schedule
    await show_schedule(update, context)

@auth_required
async def show_today_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на сегодня для конкретного потока"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    # Извлекаем stream_id из callback_data
    stream_id = int(query.data.split('_')[1])
    
    db = SessionLocal()
    try:
        # Получаем название потока
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        
        # Получаем расписание на сегодня для этого потока
        today = datetime.now().date()
        schedules = db.query(
            Schedule,
            Subject.name.label('subject_name'),
            Teacher.last_name,
            Teacher.first_name,
            Teacher.middle_name,
            LessonType.name.label('lesson_type_name')
        ).join(
            Subject, Schedule.subject_id == Subject.id
        ).join(
            Teacher, Schedule.teacher_id == Teacher.id
        ).join(
            LessonType, Schedule.lesson_type_id == LessonType.id
        ).filter(
            Schedule.stream_id == stream_id,
            Schedule.lesson_date == today
        ).order_by(Schedule.lesson_time).all()
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На {today.strftime('%d.%m.%Y')} для потока {stream.name} занятий нет 🎉"
            )
            return
        
        # Формируем сообщение
        message = f"📅 **Расписание на {today.strftime('%d.%m.%Y')}**\n"
        message += f"👥 Поток: {stream.name}\n\n"
        
        for sch in schedules:
            lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
            teacher_name = f"{sch.last_name} {sch.first_name}"
            if sch.middle_name:
                teacher_name += f" {sch.middle_name}"
            
            message += (
                f"⏰ **{lesson_time}**\n"
                f"📚 {sch.subject_name} ({sch.lesson_type_name})\n"
                f"👨‍🏫 {teacher_name}\n"
            )
            if sch.Schedule.zoom_link:
                message += f"🔗 [Ссылка на Zoom]({sch.Schedule.zoom_link})\n"
            else:
                message += f"📍 Очное занятие\n"
            message += "───────────────────\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="schedule")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    finally:
        db.close()

async def schedule_today_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать расписание на сегодня для всех потоков"""
    query = update.callback_query
    user_id = update.effective_user.id
    
    if not auth_service.is_user_verified(user_id):
        await query.edit_message_text("🔐 Требуется авторизация")
        return
    
    db = SessionLocal()
    try:
        today = datetime.now().date()
        schedules = get_today_schedule(db)
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [InlineKeyboardButton("📅 К выбору периода", callback_data="schedule")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if not schedules:
            await query.edit_message_text(
                f"📅 На {today.strftime('%d.%m.%Y')} занятий нет 🎉",
                reply_markup=reply_markup
            )
            return
        
        message = format_schedule_message(schedules, f"📅 Расписание на {today.strftime('%d.%m.%Y')}")
        
        await query.edit_message_text(
            message,
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
        schedules = get_schedule_by_date(db, tomorrow)
        
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
        schedules = get_week_schedule(db)
        
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
        
        # Группируем по дням
        days = defaultdict(list)
        for sch in schedules:
            day = sch.Schedule.lesson_date.strftime('%d.%m.%Y')
            days[day].append(sch)
        
        message = f"📅 **Расписание на неделю {monday.strftime('%d.%m')} - {sunday.strftime('%d.%m.%Y')}**\n\n"
        
        for day, lessons in sorted(days.items()):
            message += f"**{day}:**\n"
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
                # Добавляем ссылку на Zoom, если есть
                if sch.Schedule.zoom_link:
                    message += f"     🔗 [Zoom]({sch.Schedule.zoom_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"
        
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
        
        schedules = db.query(
            Schedule,
            Subject.name.label('subject_name'),
            Teacher.last_name,
            Teacher.first_name,
            Teacher.middle_name,
            LessonType.name.label('lesson_type_name'),
            Stream.name.label('stream_name')
        ).join(
            Subject, Schedule.subject_id == Subject.id
        ).join(
            Teacher, Schedule.teacher_id == Teacher.id
        ).join(
            LessonType, Schedule.lesson_type_id == LessonType.id
        ).join(
            Stream, Schedule.stream_id == Stream.id
        ).filter(
            Schedule.lesson_date.between(next_monday, next_sunday)
        ).order_by(Schedule.lesson_date, Schedule.lesson_time).all()
        
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
        
        # Группируем по дням
        days = defaultdict(list)
        for sch in schedules:
            day = sch.Schedule.lesson_date.strftime('%d.%m.%Y')
            days[day].append(sch)
        
        message = f"📅 **Расписание на следующую неделю {next_monday.strftime('%d.%m')} - {next_sunday.strftime('%d.%m.%Y')}**\n\n"
        
        for day, lessons in sorted(days.items()):
            message += f"**{day}:**\n"
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
                # Добавляем ссылку на Zoom, если есть
                if sch.Schedule.zoom_link:
                    message += f"     🔗 [Zoom]({sch.Schedule.zoom_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"
        
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
        
        schedules = db.query(
            Schedule,
            Subject.name.label('subject_name'),
            Teacher.last_name,
            Teacher.first_name,
            Teacher.middle_name,
            LessonType.name.label('lesson_type_name'),
            Stream.name.label('stream_name')
        ).join(
            Subject, Schedule.subject_id == Subject.id
        ).join(
            Teacher, Schedule.teacher_id == Teacher.id
        ).join(
            LessonType, Schedule.lesson_type_id == LessonType.id
        ).join(
            Stream, Schedule.stream_id == Stream.id
        ).filter(
            Schedule.lesson_date.between(month_start, month_end)
        ).order_by(Schedule.lesson_date, Schedule.lesson_time).all()
        
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
        
        # Группируем по дням
        days = defaultdict(list)
        for sch in schedules:
            day = sch.Schedule.lesson_date.strftime('%d.%m.%Y')
            days[day].append(sch)
        
        message = f"📅 **Расписание на {month_str}.{year_str}**\n\n"
        
        for day, lessons in sorted(days.items()):
            message += f"**{day}:**\n"
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
                # Добавляем ссылку на Zoom, если есть
                if sch.Schedule.zoom_link:
                    message += f"     🔗 [Zoom]({sch.Schedule.zoom_link})\n"
                else:
                    message += f"     📍 Очное занятие\n"
            message += "\n"
        
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