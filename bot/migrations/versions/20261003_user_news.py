"""users.news_enabled: подписка на «📣 Новое в боте»

Revision ID: 20261003_user_news
Revises: 20261002_deadline_milestone
Create Date: 2026-10-03

"""
from alembic import op
import sqlalchemy as sa

revision = '20261003_user_news'
down_revision = '20261002_deadline_milestone'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('news_enabled', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('users', 'news_enabled')
