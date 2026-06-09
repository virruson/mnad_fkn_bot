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
    
    # Связи
    schedules = relationship("Schedule", back_populates="subject")
    
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
    zoom_link = Column(Text, comment='Ссылка на Zoom')
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
        
        if self.zoom_link:
            lines.append(f"🔗 {self.zoom_link}")
        else:
            lines.append("📍 Очное занятие")
            
        return '\n'.join(lines)
    
    def __repr__(self):
        return f"<Schedule {self.subject.name} {self.lesson_date}>"
# bot/models/__init__.py (добавить в конец, перед __all__)

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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User {self.telegram_id}: {self.email}>"

# Экспортируем все модели
__all__ = ['Stream', 'Subject', 'Teacher', 'LessonType', 'Schedule', 'User']