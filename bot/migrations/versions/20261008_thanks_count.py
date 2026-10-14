"""Сердечки: users.thanks_count (жать можно много раз)

Revision ID: 20261008_thanks_count
Revises: 20261007_feedback
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa

revision = '20261008_thanks_count'
down_revision = '20261007_feedback'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('thanks_count', sa.Integer(), nullable=False, server_default='0',
                                     comment='Сколько раз студент нажал сердечко в «💬 Обратной связи»'))
    op.execute("UPDATE users SET thanks_count = 1 WHERE thanked_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column('users', 'thanks_count')
