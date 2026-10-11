"""«Мой прогресс»: user_progress, subjects.grading_weights, deadlines.progress_role, тип project

Revision ID: 20261005_progress
Revises: 20261004_news_default_on
Create Date: 2026-10-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20261005_progress'
down_revision = '20261004_news_default_on'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines',
                               "kind IN ('hw', 'quiz', 'test', 'exam', 'milestone', 'project')")

    op.add_column('deadlines', sa.Column('progress_role', sa.String(10), nullable=False,
                                         server_default='item', comment='item | bonus | hidden'))
    op.create_check_constraint('ck_deadlines_progress_role', 'deadlines',
                               "progress_role IN ('item', 'bonus', 'hidden')")

    op.add_column('subjects', sa.Column('grading_weights', postgresql.JSONB(), nullable=True,
                                        comment='{"hw": 0.5, "quiz": 0.2, "exam": 0.3}'))

    op.create_table(
        'user_progress',
        sa.Column('id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_user_progress_user'),
                  nullable=False),
        sa.Column('deadline_id', sa.Integer(),
                  sa.ForeignKey('deadlines.id', ondelete='CASCADE', name='fk_user_progress_deadline'),
                  nullable=False),
        sa.Column('done_at', sa.DateTime(), nullable=True, comment='NULL = не сдано'),
        sa.Column('grade', sa.Numeric(3, 1), nullable=True, comment='0–10'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('grade IS NULL OR (grade >= 0 AND grade <= 10)', name='ck_user_progress_grade'),
        sa.UniqueConstraint('user_id', 'deadline_id', name='uq_user_progress_user_deadline'),
    )
    op.create_index('idx_user_progress_deadline', 'user_progress', ['deadline_id'])


def downgrade() -> None:
    op.drop_index('idx_user_progress_deadline', table_name='user_progress')
    op.drop_table('user_progress')
    op.drop_column('subjects', 'grading_weights')
    op.drop_constraint('ck_deadlines_progress_role', 'deadlines', type_='check')
    op.drop_column('deadlines', 'progress_role')
    op.execute("DELETE FROM deadlines WHERE kind = 'project'")
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines',
                               "kind IN ('hw', 'quiz', 'test', 'exam', 'milestone')")
