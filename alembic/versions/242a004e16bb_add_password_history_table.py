"""add password history table

Revision ID: 242a004e16bb
Revises: 3d92d00f6258
Create Date: 2026-09-14 23:03:55.139182

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "242a004e16bb"
down_revision: Union[str, Sequence[str], None] = "3d92d00f6258"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The password_history table already exists in the database.
    # No schema change is required here.


def downgrade() -> None:
    """Downgrade schema."""
    # No schema change is required here.