"""deadlines: modules, deadlines, subjects.grading_formula/short_name,
split users.notifications_enabled into digest/reminders + deadlines flag

Revision ID: 20260930_deadlines
Revises: 20260907_rename_meeting_link
Create Date: 2026-09-30

"""
from alembic import op
import sqlalchemy as sa

revision = '20260930_deadlines'
down_revision = '20260907_rename_meeting_link'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'modules',
        sa.Column('id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.UniqueConstraint('name', name='uq_modules_name'),
    )

    op.create_table(
        'deadlines',
        sa.Column('id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('subject_id', sa.Integer(),
                  sa.ForeignKey('subjects.id', ondelete='CASCADE', name='fk_deadlines_subject'),
                  nullable=False),
        sa.Column('kind', sa.String(10), nullable=False, comment="hw | quiz | test"),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('due_time', sa.Time(), nullable=True, comment='NULL = 23:59'),
        sa.CheckConstraint("kind IN ('hw', 'quiz', 'test')", name='ck_deadlines_kind'),
        sa.UniqueConstraint('subject_id', 'kind', 'title', name='uq_deadlines_subject_kind_title'),
    )
    op.create_index('idx_deadlines_due_date', 'deadlines', ['due_date'])

    op.add_column('subjects', sa.Column('grading_formula', sa.Text(), nullable=True))
    op.add_column('subjects', sa.Column('short_name', sa.String(50), nullable=True,
                                        comment='Короткое имя для кнопок, до 25 символов'))

    # notifications_enabled -> digest_enabled + reminders_enabled (оба берут старое значение)
    op.add_column('users', sa.Column('digest_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('reminders_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('deadlines_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.execute("UPDATE users SET digest_enabled = notifications_enabled, reminders_enabled = notifications_enabled")
    op.drop_index('idx_users_notifications', table_name='users')
    op.drop_column('users', 'notifications_enabled')


def downgrade() -> None:
    op.add_column('users', sa.Column('notifications_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.execute("UPDATE users SET notifications_enabled = (digest_enabled OR reminders_enabled)")
    op.create_index('idx_users_notifications', 'users', ['notifications_enabled', 'stream_id'], unique=False)
    op.drop_column('users', 'deadlines_enabled')
    op.drop_column('users', 'reminders_enabled')
    op.drop_column('users', 'digest_enabled')

    op.drop_column('subjects', 'short_name')
    op.drop_column('subjects', 'grading_formula')

    op.drop_index('idx_deadlines_due_date', table_name='deadlines')
    op.drop_table('deadlines')
    op.drop_table('modules')
