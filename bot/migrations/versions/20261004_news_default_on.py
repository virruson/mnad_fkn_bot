"""users.news_enabled: включить всем и по умолчанию для новых

Revision ID: 20261004_news_default_on
Revises: 20261003_user_news
Create Date: 2026-10-04

"""
from alembic import op
import sqlalchemy as sa

revision = '20261004_news_default_on'
down_revision = '20261003_user_news'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET news_enabled = true")
    op.alter_column('users', 'news_enabled', server_default=sa.true(), existing_type=sa.Boolean())


def downgrade() -> None:
    # подписки не трогаем — возвращаем только значение по умолчанию
    op.alter_column('users', 'news_enabled', server_default=sa.false(), existing_type=sa.Boolean())
