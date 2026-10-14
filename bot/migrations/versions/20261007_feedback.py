"""Обратная связь: users.thanked_at, feedback

Revision ID: 20261007_feedback
Revises: 20261006_magolego
Create Date: 2026-10-14

"""
from alembic import op
import sqlalchemy as sa

revision = '20261007_feedback'
down_revision = '20261006_magolego'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('thanked_at', sa.DateTime(), nullable=True,
                                     comment='Сказал «спасибо» в «💬 Обратной связи» (один раз)'))
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column('user_id', sa.Integer(),
                  sa.ForeignKey('users.id', ondelete='CASCADE', name='fk_feedback_user'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('context', sa.String(100), nullable=True, comment='Откуда: «Дедлайны · RecSys», «ответ на №12»'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('admin_message_id', sa.BigInteger(), nullable=True, comment='id сообщения у автора — для ответа reply'),
        sa.Column('answered_at', sa.DateTime(), nullable=True),
    )
    op.create_index('idx_feedback_user_created', 'feedback', ['user_id', 'created_at'])
    op.create_index('idx_feedback_admin_message', 'feedback', ['admin_message_id'])


def downgrade() -> None:
    op.drop_index('idx_feedback_admin_message', table_name='feedback')
    op.drop_index('idx_feedback_user_created', table_name='feedback')
    op.drop_table('feedback')
    op.drop_column('users', 'thanked_at')
