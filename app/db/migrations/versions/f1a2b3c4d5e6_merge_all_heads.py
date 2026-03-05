"""merge all migration heads

Revision ID: f1a2b3c4d5e6
Revises: 07f9bbb3db4e, 305943d779c4, 54c4b8c525fc, 5a4446e7b165, 852d951c9c08, a0d3d400ea75, adda2dd4a741, b3378dc6de01, d02dcfbf1517, d0a3960f5dad, d6e7f8a9b0c1, e3f0e888a563, ece13c4c6f65, fad8b1997c3a, fe7796f840a4
Create Date: 2026-03-05 13:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = (
    '07f9bbb3db4e',
    '305943d779c4',
    '54c4b8c525fc',
    '5a4446e7b165',
    '852d951c9c08',
    'a0d3d400ea75',
    'adda2dd4a741',
    'b3378dc6de01',
    'd02dcfbf1517',
    'd0a3960f5dad',
    'd6e7f8a9b0c1',
    'e3f0e888a563',
    'ece13c4c6f65',
    'fad8b1997c3a',
    'fe7796f840a4',
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
