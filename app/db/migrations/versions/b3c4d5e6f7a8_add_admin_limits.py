"""add admin user_limit and traffic_limit

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c4d5e6f7a8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('admins', sa.Column('user_limit', sa.Integer(), nullable=True))
    op.add_column('admins', sa.Column('traffic_limit', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('admins', 'traffic_limit')
    op.drop_column('admins', 'user_limit')
