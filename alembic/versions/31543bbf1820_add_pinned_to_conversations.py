"""add pinned to conversations

Revision ID: 86136745150c
Revises: 61905d350142
Create Date: 2026-08-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# Revision identifiers
# ============================================================

revision: str = "86136745150c"

down_revision: Union[
    str,
    Sequence[str],
    None
] = "61905d350142"

branch_labels: Union[
    str,
    Sequence[str],
    None
] = None

depends_on: Union[
    str,
    Sequence[str],
    None
] = None


# ============================================================
# Upgrade
# ============================================================

def upgrade() -> None:

    op.add_column(
        "conversations",
        sa.Column(
            "pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "conversations",
        "pinned",
        server_default=None,
    )


# ============================================================
# Downgrade
# ============================================================

def downgrade() -> None:

    op.drop_column(
        "conversations",
        "pinned",
    )