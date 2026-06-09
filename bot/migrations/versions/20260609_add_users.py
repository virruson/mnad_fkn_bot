"""add users table

Revision ID: 20260609_add_users
Revises: 20260303_initial
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa

revision = '20260609_add_users'
down_revision = '20260303_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('telegram_id', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('username', sa.String(length=100), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id', name='uq_users_telegram_id')
    )
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'], unique=True)
    op.create_index('idx_users_email', 'users', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_telegram_id', table_name='users')
    op.drop_table('users')
