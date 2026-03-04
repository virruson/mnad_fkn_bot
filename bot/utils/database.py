# bot/utils/database.py
import os
from datetime import datetime
from sqlalchemy import create_engine, and_
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool

# Получаем URL из переменной окружения
DATABASE_URL = os.getenv(
    'DATABASE_URL', 
    'postgresql://mnad_bot:mnad_password@localhost:5432/mnad_schedule'
)

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False  # В продакшене выключить
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===== Функции для работы с расписанием =====

def get_today_schedule(db, stream_name=None):
    """
    Получить расписание на сегодня
    Если stream_name указан - только для конкретного потока
    Если stream_name не указан - для всех потоков
    """
    from bot.models import Schedule, Subject, Teacher, LessonType, Stream
    
    today = datetime.now().date()
    
    query = db.query(
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
        Schedule.lesson_date == today
    )
    
    if stream_name:
        query = query.filter(Stream.name == stream_name)
    
    return query.order_by(Schedule.lesson_time).all()

def get_schedule_by_date(db, date, stream_name=None):
    """
    Получить расписание на указанную дату
    date: объект date или строка в формате 'YYYY-MM-DD'
    """
    from bot.models import Schedule, Subject, Teacher, LessonType, Stream
    
    query = db.query(
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
        Schedule.lesson_date == date
    )
    
    if stream_name:
        query = query.filter(Stream.name == stream_name)
    
    return query.order_by(Schedule.lesson_time).all()

def get_week_schedule(db, stream_name=None):
    """
    Получить расписание на текущую неделю (пн-вс)
    """
    from bot.models import Schedule, Subject, Teacher, LessonType, Stream
    from datetime import timedelta
    
    today = datetime.now().date()
    # Находим понедельник текущей недели
    monday = today - timedelta(days=today.weekday())
    # Находим воскресенье
    sunday = monday + timedelta(days=6)
    
    query = db.query(
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
        Schedule.lesson_date.between(monday, sunday)
    )
    
    if stream_name:
        query = query.filter(Stream.name == stream_name)
    
    return query.order_by(Schedule.lesson_date, Schedule.lesson_time).all()

def get_streams(db):
    """Получить список всех потоков"""
    from bot.models import Stream
    return db.query(Stream).order_by(Stream.name).all()

def format_schedule_message(schedules, title=None):
    """
    Форматирует расписание для отправки в Telegram
    Возвращает строку с отформатированным расписанием
    """
    if not schedules:
        return "📅 На этот день занятий нет 🎉"
    
    if not title:
        title = f"📅 Расписание на {datetime.now().strftime('%d.%m.%Y')}"
    
    # Группируем по потокам
    streams_dict = {}
    for sch in schedules:
        stream_name = sch.stream_name
        if stream_name not in streams_dict:
            streams_dict[stream_name] = []
        streams_dict[stream_name].append(sch)
    
    message = f"{title}\n\n"
    
    for stream_name, lessons in streams_dict.items():
        message += f"**{stream_name}:**\n"
        for sch in lessons:
            lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
            teacher_name = f"{sch.last_name} {sch.first_name}"
            if sch.middle_name:
                teacher_name += f" {sch.middle_name}"
            
            message += (
                f"  ⏰ **{lesson_time}** – {sch.subject_name} ({sch.lesson_type_name})\n"
                f"     👨‍🏫 {teacher_name}\n"
            )
            if sch.Schedule.zoom_link:
                # Сокращаем длинные ссылки для красоты
                short_link = sch.Schedule.zoom_link[:30] + "..." if len(sch.Schedule.zoom_link) > 30 else sch.Schedule.zoom_link
                message += f"     🔗 [Zoom]({sch.Schedule.zoom_link})\n"
            else:
                message += f"     📍 Очное занятие\n"
        message += "\n"
    
    return message

def format_schedule_simple(schedules, title=None):
    """
    Упрощенное форматирование (без группировки по потокам)
    """
    if not schedules:
        return "📅 На этот день занятий нет 🎉"
    
    if not title:
        title = f"📅 Расписание на {datetime.now().strftime('%d.%m.%Y')}"
    
    message = f"{title}\n\n"
    
    for sch in schedules:
        lesson_time = sch.Schedule.lesson_time.strftime('%H:%M')
        teacher_name = f"{sch.last_name} {sch.first_name}"
        
        message += (
            f"⏰ **{lesson_time}**\n"
            f"📚 {sch.subject_name} ({sch.lesson_type_name})\n"
            f"👨‍🏫 {teacher_name}\n"
            f"👥 {sch.stream_name}\n"
        )
        if sch.Schedule.zoom_link:
            message += f"🔗 [Ссылка на Zoom]({sch.Schedule.zoom_link})\n"
        else:
            message += f"📍 Очное занятие\n"
        message += "───────────────────\n\n"
    
    return message

# Для отладки - можно выполнить прямой SQL запрос
def execute_raw_sql(query, params=None):
    """Выполнить сырой SQL запрос (только для отладки)"""
    with engine.connect() as conn:
        if params:
            result = conn.execute(query, params)
        else:
            result = conn.execute(query)
        return result.fetchall()