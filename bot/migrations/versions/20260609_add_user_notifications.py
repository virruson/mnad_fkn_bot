"""add stream_id and notifications_enabled to users

Revision ID: 20260609_add_user_notifications
Revises: 20260609_add_users
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa

revision = '20260609_add_user_notifications'
down_revision = '20260609_add_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users',
        sa.Column('stream_id', sa.Integer(),
                  sa.ForeignKey('streams.id', ondelete='SET NULL', name='fk_users_stream'),
                  nullable=True)
    )
    op.add_column('users',
        sa.Column('notifications_enabled', sa.Boolean(),
                  nullable=False, server_default='false')
    )
    op.create_index('idx_users_notifications', 'users',
                    ['notifications_enabled', 'stream_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_users_notifications', table_name='users')
    op.drop_column('users', 'notifications_enabled')
    op.drop_column('users', 'stream_id')
