"""add_hwid_device_tracking

Revision ID: d5f13b4c722f
Revises: 2b231de97dc3
Create Date: 2026-03-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5f13b4c722f'
down_revision = '2b231de97dc3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_devices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('hwid', sa.String(length=256), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=64), nullable=True),
        sa.Column('os_version', sa.String(length=64), nullable=True),
        sa.Column('device_model', sa.String(length=128), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('hwid', 'user_id'),
    )
    op.create_index(op.f('ix_user_devices_hwid'), 'user_devices', ['hwid'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('device_limit', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('device_limit')

    op.drop_index(op.f('ix_user_devices_hwid'), table_name='user_devices')
    op.drop_table('user_devices')
