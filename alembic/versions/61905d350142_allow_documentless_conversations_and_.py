"""allow documentless conversations and image messages

Revision ID: 61905d350142
Revises: c852f73aabbb
Create Date: 2026-08-26 00:52:41.605111

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# Revision identifiers
# ============================================================

revision: str = "61905d350142"

down_revision: Union[
    str,
    Sequence[str],
    None
] = "c852f73aabbb"

branch_labels = None

depends_on = None


# ============================================================
# Upgrade
# ============================================================

def upgrade() -> None:

    # --------------------------------------------------------
    # 1. Allow conversations without a PDF
    # --------------------------------------------------------

    op.alter_column(
        "conversations",
        "document_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=True
    )

    # --------------------------------------------------------
    # 2. Add optional image information to messages
    # --------------------------------------------------------

    op.add_column(
        "messages",
        sa.Column(
            "image_filename",
            sa.String(length=500),
            nullable=True
        )
    )


# ============================================================
# Downgrade
# ============================================================

def downgrade() -> None:

    # --------------------------------------------------------
    # 1. Remove image information
    # --------------------------------------------------------

    op.drop_column(
        "messages",
        "image_filename"
    )

    # --------------------------------------------------------
    # 2. Restore document requirement
    # --------------------------------------------------------

    op.alter_column(
        "conversations",
        "document_id",
        existing_type=sa.VARCHAR(length=36),
        nullable=False
    )