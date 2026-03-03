"""add smart_host_address to users

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('smart_host_address', sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'smart_host_address')
