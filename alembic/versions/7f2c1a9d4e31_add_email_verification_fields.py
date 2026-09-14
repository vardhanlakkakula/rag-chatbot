"""add email verification fields

Revision ID: 7f2c1a9d4e31
Revises: 86136745150c
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f2c1a9d4e31"
down_revision: Union[str, Sequence[str], None] = "86136745150c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.alter_column(
        "users",
        "email_verified",
        server_default=None,
    )

    op.add_column(
        "users",
        sa.Column(
            "email_verification_token_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "email_verification_expires_at",
            sa.DateTime(),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_users_email_verification_token_hash",
        "users",
        ["email_verification_token_hash"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_users_email_verification_token_hash",
        table_name="users",
    )

    op.drop_column(
        "users",
        "email_verification_expires_at",
    )

    op.drop_column(
        "users",
        "email_verification_token_hash",
    )

    op.drop_column(
        "users",
        "email_verified",
    )