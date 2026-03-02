"""add_disabled_field_to_user_devices

Revision ID: a1b2c3d4e5f6
Revises: d5f13b4c722f
Create Date: 2026-03-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'd5f13b4c722f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('user_devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('disabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('user_devices', schema=None) as batch_op:
        batch_op.drop_column('disabled')
