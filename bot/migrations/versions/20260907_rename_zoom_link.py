"""rename schedule.zoom_link to meeting_link (Zoom -> MTS-Link)

Revision ID: 20260907_rename_meeting_link
Revises: 20260609_add_user_notifications
Create Date: 2026-09-07

"""
from alembic import op
import sqlalchemy as sa

revision = '20260907_rename_meeting_link'
down_revision = '20260609_add_user_notifications'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'schedule', 'zoom_link',
        new_column_name='meeting_link',
        existing_type=sa.Text(),
        existing_comment='Ссылка на Zoom',
        comment='Ссылка на встречу (MTS-Link)',
    )


def downgrade() -> None:
    op.alter_column(
        'schedule', 'meeting_link',
        new_column_name='zoom_link',
        existing_type=sa.Text(),
        existing_comment='Ссылка на встречу (MTS-Link)',
        comment='Ссылка на Zoom',
    )
