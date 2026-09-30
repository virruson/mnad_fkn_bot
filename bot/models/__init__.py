# bot/models/__init__.py
from sqlalchemy import Column, Integer, String, Date, Time, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from bot.utils.database import Base

class Stream(Base):
    __tablename__ = 'streams'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, comment='Название потока')
    
    # Связи
    schedules = relationship("Schedule", back_populates="stream", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Stream {self.name}>"

class Subject(Base):
    __tablename__ = 'subjects'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, comment='Название предмета')
    short_name = Column(String(50), nullable=True, comment='Короткое имя для кнопок, до 25 символов')
    grading_formula = Column(Text, nullable=True, comment='Правая часть: 0.3·ДЗ + 0.2·Квизы + 0.5·КР')
    
    # Связи
    schedules = relationship("Schedule", back_populates="subject")
    deadlines = relationship("Deadline", back_populates="subject")
    
    def __repr__(self):
        return f"<Subject {self.name}>"

class Teacher(Base):
    __tablename__ = 'teachers'
    
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100))
    last_name = Column(String(100), nullable=False)
    middle_name = Column(String(100), comment='Отчество')
    department = Column(String(255), comment='Кафедра')
    
    # Связи
    schedules = relationship("Schedule", back_populates="teacher")
    
    @property
    def full_name(self):
        """Полное имя преподавателя"""
        parts = [self.last_name, self.first_name, self.middle_name]
        return ' '.join(p for p in parts if p)
    
    @property
    def short_name(self):
        """Короткое имя (Фамилия И.О.)"""
        if self.first_name and self.middle_name:
            return f"{self.last_name} {self.first_name[0]}.{self.middle_name[0]}."
        elif self.first_name:
            return f"{self.last_name} {self.first_name[0]}."
        return self.last_name
    
    def __repr__(self):
        return f"<Teacher {self.full_name}>"

class LessonType(Base):
    __tablename__ = 'lesson_types'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True, comment='Тип занятия')
    
    # Связи
    schedules = relationship("Schedule", back_populates="lesson_type")
    
    def __repr__(self):
        return f"<LessonType {self.name}>"

class Schedule(Base):
    __tablename__ = 'schedule'
    
    id = Column(Integer, primary_key=True)
    stream_id = Column(Integer, ForeignKey('streams.id', ondelete='CASCADE'), nullable=False)
    subject_id = Column(Integer, ForeignKey('subjects.id', ondelete='RESTRICT'), nullable=False)
    teacher_id = Column(Integer, ForeignKey('teachers.id', ondelete='RESTRICT'), nullable=False)
    lesson_type_id = Column(Integer, ForeignKey('lesson_types.id', ondelete='RESTRICT'), nullable=False)
    lesson_date = Column(Date, nullable=False, comment='Дата занятия')
    lesson_time = Column(Time, nullable=False, comment='Время занятия')
    meeting_link = Column(Text, comment='Ссылка на встречу (MTS-Link)')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Связи
    stream = relationship("Stream", back_populates="schedules")
    subject = relationship("Subject", back_populates="schedules")
    teacher = relationship("Teacher", back_populates="schedules")
    lesson_type = relationship("LessonType", back_populates="schedules")
    
    @property
    def datetime_obj(self):
        """Объединяет дату и время"""
        from datetime import datetime
        return datetime.combine(self.lesson_date, self.lesson_time)
    
    def format_for_telegram(self):
        """Форматирование для Telegram сообщения"""
        # Форматируем дату и время
        date_str = self.lesson_date.strftime('%d.%m.%Y')
        time_str = self.lesson_time.strftime('%H:%M')
        
        # День недели по-русски
        days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
        weekday = days[self.lesson_date.weekday()]
        
        lines = [
            f"📅 {date_str} ({weekday}) {time_str}",
            f"📚 {self.subject.name} ({self.lesson_type.name})",
            f"👨‍🏫 {self.teacher.short_name}",
            f"👥 {self.stream.name}",
        ]
        
        if self.meeting_link:
            lines.append(f"🔗 {self.meeting_link}")
        else:
            lines.append("📍 Очное занятие")
            
        return '\n'.join(lines)
    
    def __repr__(self):
        return f"<Schedule {self.subject.name} {self.lesson_date}>"


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False, comment='ID пользователя в Telegram')
    email = Column(String(255), nullable=False, comment='Email пользователя')
    full_name = Column(String(255), comment='Полное имя из Telegram')
    first_name = Column(String(100), comment='Имя')
    last_name = Column(String(100), comment='Фамилия')
    username = Column(String(100), comment='Username в Telegram')
    is_verified = Column(Boolean, default=True, comment='Верифицирован ли пользователь')
    verified_at = Column(DateTime, comment='Дата верификации')
    last_login = Column(DateTime, comment='Последний вход')
    stream_id = Column(Integer, ForeignKey('streams.id', ondelete='SET NULL'), nullable=True)
    digest_enabled = Column(Boolean, default=False, nullable=False, comment='Расписание на день в 10:00')
    reminders_enabled = Column(Boolean, default=False, nullable=False, comment='Напоминание за 15 мин')
    deadlines_enabled = Column(Boolean, default=False, nullable=False, comment='Дедлайны за 4, 2, 1 дн')
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    stream = relationship("Stream", foreign_keys=[stream_id])

    def __repr__(self):
        return f"<User {self.telegram_id}: {self.email}>"

class Module(Base):
    """Учебный модуль. Текущий — тот, в диапазон дат которого попадает сегодня."""
    __tablename__ = 'modules'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    def __repr__(self):
        return f"<Module {self.name} {self.start_date}..{self.end_date}>"


class Deadline(Base):
    """Дедлайн по предмету, общий для всех групп."""
    __tablename__ = 'deadlines'

    KINDS = ('hw', 'quiz', 'test')

    id = Column(Integer, primary_key=True)
    subject_id = Column(Integer, ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    kind = Column(String(10), nullable=False, comment='hw | quiz | test')
    title = Column(String(255), nullable=False)
    due_date = Column(Date, nullable=False)
    due_time = Column(Time, nullable=True, comment='NULL = 23:59')

    subject = relationship("Subject", back_populates="deadlines")

    def __repr__(self):
        return f"<Deadline {self.kind} {self.title} {self.due_date}>"


# Экспортируем все модели
__all__ = ['Stream', 'Subject', 'Teacher', 'LessonType', 'Schedule', 'User', 'Module', 'Deadline']