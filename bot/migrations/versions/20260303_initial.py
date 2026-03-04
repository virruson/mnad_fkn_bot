# migrations/versions/20260303_initial_schema.py
"""initial schema for mnad_fkn_bot

Revision ID: 20260303_initial
Revises: 
Create Date: 2026-03-03 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TEXT

# revision identifiers
revision = '20260303_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Создание таблицы streams (потоки)
    op.create_table('streams',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),  # Явно указываем Identity
        sa.Column('name', sa.String(length=100), nullable=False, comment='Например, "1 поток"'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_streams_name', 'streams', ['name'], unique=False)
    
    # Создание таблицы subjects (предметы)
    op.create_table('subjects',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False, comment='Например, "ТВиМС"'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_subjects_name', 'subjects', ['name'], unique=False)
    
    # Создание таблицы teachers (преподаватели)
    op.create_table('teachers',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('middle_name', sa.String(length=100), nullable=True, comment='Отчество (опционально)'),
        sa.Column('department', sa.String(length=255), nullable=True, comment='Кафедра'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_teachers_last_name', 'teachers', ['last_name'], unique=False)
    op.create_index('idx_teachers_full_name', 'teachers', ['last_name', 'first_name', 'middle_name'], unique=False)
    
    # Создание таблицы lesson_types (типы занятий)
    op.create_table('lesson_types',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False, comment='Лекция, Семинар, КР и т.д.'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_lesson_types_name')
    )
    
    # Создание основной таблицы schedule (расписание)
    op.create_table('schedule',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('stream_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('lesson_type_id', sa.Integer(), nullable=False),
        sa.Column('lesson_date', sa.Date(), nullable=False, comment='Дата занятия'),
        sa.Column('lesson_time', sa.Time(), nullable=False, comment='Время занятия'),
        sa.Column('zoom_link', sa.Text(), nullable=True, comment='Ссылка на Zoom (NULL для очных занятий)'),  # nullable=True
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        
        # Внешние ключи
        sa.ForeignKeyConstraint(['stream_id'], ['streams.id'], ondelete='CASCADE', name='fk_schedule_stream'),
        sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], ondelete='RESTRICT', name='fk_schedule_subject'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='RESTRICT', name='fk_schedule_teacher'),
        sa.ForeignKeyConstraint(['lesson_type_id'], ['lesson_types.id'], ondelete='RESTRICT', name='fk_schedule_lesson_type'),
        
        sa.PrimaryKeyConstraint('id')
    )
    
    # Индексы для быстрого поиска по расписанию
    op.create_index('idx_schedule_date', 'schedule', ['lesson_date'], unique=False)
    op.create_index('idx_schedule_stream_date', 'schedule', ['stream_id', 'lesson_date'], unique=False)
    op.create_index('idx_schedule_teacher_date', 'schedule', ['teacher_id', 'lesson_date'], unique=False)
    op.create_index('idx_schedule_subject_date', 'schedule', ['subject_id', 'lesson_date'], unique=False)
    
    # Добавление начальных данных (используем более безопасный способ)
    
    # Типы занятий
    op.bulk_insert(
        sa.table('lesson_types',
            sa.column('name', sa.String)
        ),
        [
            {'name': 'Лекция'},
            {'name': 'Семинар'},
            {'name': 'Контрольная работа'}
        ]
    )
    
    # Предметы
    op.bulk_insert(
        sa.table('subjects',
            sa.column('name', sa.String)
        ),
        [
            {'name': 'Теория вероятностей'},
            {'name': 'Машинное обучение'},
            {'name': 'НИС "Продуктовый подход в аналитике данных"'},
            {'name': 'Базы и хранилища данных'},
            {'name': 'Семинар наставника'}
        ]
    )
    
    # Преподаватели
    op.bulk_insert(
        sa.table('teachers',
            sa.column('first_name', sa.String),
            sa.column('last_name', sa.String)
        ),
        [
            {'first_name': 'Глеб', 'last_name': 'Карпов'},
            {'first_name': 'Юрий', 'last_name': 'Саночкин'},
            {'first_name': 'Данила', 'last_name': 'Яценко'},
            {'first_name': 'Леонид', 'last_name': 'Смелов'},
            {'first_name': 'Кирилл', 'last_name': 'Гоменюк'},
            {'first_name': 'Руслан', 'last_name': 'Каюмов'}
        ]
    )
    
    # Добавим несколько потоков для примера
    op.bulk_insert(
        sa.table('streams',
            sa.column('name', sa.String)
        ),
        [
            {'name': '1 поток'},
            {'name': '2 поток'}
        ]
    )

def downgrade() -> None:
    # Удаление в обратном порядке (сначала зависимые таблицы)
    op.drop_table('schedule')
    op.drop_table('lesson_types')
    op.drop_table('teachers')
    op.drop_table('subjects')
    op.drop_table('streams')