"""users.view_module_id / view_module_base_id — «🗂 Модуль»: какой модуль смотрит студент

Revision ID: 20261010_view_module
Revises: 20261009_notify_on
Create Date: 2026-10-21

"""
from alembic import op
import sqlalchemy as sa

revision = '20261010_view_module'
down_revision = '20261009_notify_on'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('view_module_id', sa.Integer(), nullable=True,
                                     comment='Выбранный в «🗂 Модуль» (NULL — текущий)'))
    op.add_column('users', sa.Column('view_module_base_id', sa.Integer(), nullable=True,
                                     comment='Текущий модуль в момент выбора — для автосброса'))
    op.create_foreign_key('fk_users_view_module', 'users', 'modules',
                          ['view_module_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_users_view_module_base', 'users', 'modules',
                          ['view_module_base_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_users_view_module_base', 'users', type_='foreignkey')
    op.drop_constraint('fk_users_view_module', 'users', type_='foreignkey')
    op.drop_column('users', 'view_module_base_id')
    op.drop_column('users', 'view_module_id')
