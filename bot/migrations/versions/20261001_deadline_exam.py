"""deadlines.kind: add 'exam'

Revision ID: 20261001_deadline_exam
Revises: 20260930_deadlines
Create Date: 2026-10-01

"""
from alembic import op

revision = '20261001_deadline_exam'
down_revision = '20260930_deadlines'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines', "kind IN ('hw', 'quiz', 'test', 'exam')")


def downgrade() -> None:
    op.execute("DELETE FROM deadlines WHERE kind = 'exam'")
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines', "kind IN ('hw', 'quiz', 'test')")
