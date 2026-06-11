"""profile_facts: allowed_scenarios (EPIC-003 B2)

Revision ID: b3c41f09d2e7
Revises: a8a80e02231d
Create Date: 2026-06-11 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b3c41f09d2e7'
down_revision: Union[str, None] = 'a8a80e02231d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'profile_facts',
        sa.Column(
            'allowed_scenarios',
            sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'),
            nullable=False,
            server_default='[]',
        ),
    )


def downgrade() -> None:
    op.drop_column('profile_facts', 'allowed_scenarios')
