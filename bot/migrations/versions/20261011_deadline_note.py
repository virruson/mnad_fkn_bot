"""deadlines.note — срок текстом, пока дата уточняется

Revision ID: 20261011_deadline_note
Revises: 20261010_view_module
Create Date: 2026-10-30

"""
from alembic import op
import sqlalchemy as sa

revision = '20261011_deadline_note'
down_revision = '20261010_view_module'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('deadlines', sa.Column('note', sa.Text(), nullable=True,
                                         comment='Срок текстом, если дата уточняется (due_date = 2099-12-31)'))


def downgrade() -> None:
    op.drop_column('deadlines', 'note')
