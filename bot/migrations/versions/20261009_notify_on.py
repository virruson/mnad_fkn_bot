"""users: «Дедлайны» и «Расписание на день» — включить всем и по умолчанию для новых

Revision ID: 20261009_notify_on
Revises: 20261008_thanks_count
Create Date: 2026-10-19

"""
from alembic import op
import sqlalchemy as sa

revision = '20261009_notify_on'
down_revision = '20261008_thanks_count'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET deadlines_enabled = true, digest_enabled = true")
    op.alter_column('users', 'deadlines_enabled', server_default=sa.true(), existing_type=sa.Boolean())
    op.alter_column('users', 'digest_enabled', server_default=sa.true(), existing_type=sa.Boolean())


def downgrade() -> None:
    # подписки не трогаем — возвращаем только значения по умолчанию
    op.alter_column('users', 'deadlines_enabled', server_default=sa.false(), existing_type=sa.Boolean())
    op.alter_column('users', 'digest_enabled', server_default=sa.false(), existing_type=sa.Boolean())
