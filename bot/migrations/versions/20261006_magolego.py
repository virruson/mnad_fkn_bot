"""Маголего: subjects.is_elective, users.common_enabled, user_electives

Выбор студента вместо одного потока: «Общие предметы» вкл/выкл + набор маголего.
users.stream_id не удаляется (код его больше не читает) — откат без потери данных.

Перенос текущего выбора (чтобы после выкатки никто ничего не потерял):
  «Общий поток» / группа не выбрана → общие
  «Маголего»                        → все текущие маголего, без общих
  «все потоки»                      → общие + все текущие маголего
Текущие маголего — с занятиями в текущем модуле или будущими дедлайнами.

Revision ID: 20261006_magolego
Revises: 20261005_progress
Create Date: 2026-10-12

"""
from alembic import op
import sqlalchemy as sa

revision = '20261006_magolego'
down_revision = '20261005_progress'
branch_labels = None
depends_on = None

ELECTIVE_STREAM = 'Маголего'
ALL_STREAMS = 'все потоки'


def upgrade() -> None:
    op.add_column('subjects', sa.Column('is_elective', sa.Boolean(), nullable=False,
                                        server_default=sa.false(), comment='Маголего'))
    op.add_column('users', sa.Column('common_enabled', sa.Boolean(), nullable=False,
                                     server_default=sa.true(), comment='«Общие предметы» в «📚 Мои предметы»'))
    op.create_table(
        'user_electives',
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_user_electives_user'), nullable=False),
        sa.Column('subject_id', sa.Integer(),
                  sa.ForeignKey('subjects.id', ondelete='CASCADE', name='fk_user_electives_subject'), nullable=False),
        sa.PrimaryKeyConstraint('user_id', 'subject_id', name='pk_user_electives'),
    )

    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE subjects SET is_elective = true
        WHERE id IN (SELECT s.subject_id FROM schedule s JOIN streams st ON st.id = s.stream_id
                     WHERE st.name = :stream)
    """), {'stream': ELECTIVE_STREAM})

    current_electives = """
        SELECT sub.id FROM subjects sub
        WHERE sub.is_elective AND (
            EXISTS (SELECT 1 FROM schedule s JOIN modules m
                      ON CURRENT_DATE BETWEEN m.start_date AND m.end_date
                    WHERE s.subject_id = sub.id AND s.lesson_date BETWEEN m.start_date AND m.end_date)
            OR EXISTS (SELECT 1 FROM deadlines d WHERE d.subject_id = sub.id AND d.due_date >= CURRENT_DATE))
    """
    bind.execute(sa.text(f"""
        INSERT INTO user_electives (user_id, subject_id)
        SELECT u.id, e.id FROM users u JOIN streams st ON st.id = u.stream_id, ({current_electives}) e
        WHERE st.name IN (:elective, :all)
    """), {'elective': ELECTIVE_STREAM, 'all': ALL_STREAMS})
    bind.execute(sa.text("""
        UPDATE users SET common_enabled = false
        WHERE stream_id IN (SELECT id FROM streams WHERE name = :elective)
    """), {'elective': ELECTIVE_STREAM})


def downgrade() -> None:
    op.drop_table('user_electives')
    op.drop_column('users', 'common_enabled')
    op.drop_column('subjects', 'is_elective')
