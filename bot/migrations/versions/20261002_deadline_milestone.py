"""deadlines.kind: add 'milestone' (этапы ВКР)

Revision ID: 20261002_deadline_milestone
Revises: 20261001_deadline_exam
Create Date: 2026-10-02

"""
from alembic import op

revision = '20261002_deadline_milestone'
down_revision = '20261001_deadline_exam'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines',
                               "kind IN ('hw', 'quiz', 'test', 'exam', 'milestone')")


def downgrade() -> None:
    op.execute("DELETE FROM deadlines WHERE kind = 'milestone'")
    op.drop_constraint('ck_deadlines_kind', 'deadlines', type_='check')
    op.create_check_constraint('ck_deadlines_kind', 'deadlines', "kind IN ('hw', 'quiz', 'test', 'exam')")
