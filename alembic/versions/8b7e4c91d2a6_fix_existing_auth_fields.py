"""fix existing auth fields

Revision ID: 8b7e4c91d2a6
Revises: 242a004e16bb
Create Date: 2026-09-16

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8b7e4c91d2a6"

down_revision: Union[str, Sequence[str], None] = "242a004e16bb"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --------------------------------------------------------
    # Email verification fields
    # --------------------------------------------------------

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email_verified BOOLEAN
        """
    )

    op.execute(
        """
        UPDATE users
        SET email_verified = FALSE
        WHERE email_verified IS NULL
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN email_verified SET NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email_verification_token_hash VARCHAR(64)
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS email_verification_expires_at
        TIMESTAMP WITHOUT TIME ZONE
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_users_email_verification_token_hash
        ON users (email_verification_token_hash)
        """
    )

    # --------------------------------------------------------
    # Password reset fields
    # --------------------------------------------------------

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(64)
        """
    )

    op.execute(
        """
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS password_reset_expires_at
        TIMESTAMP WITHOUT TIME ZONE
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS
        ix_users_password_reset_token_hash
        ON users (password_reset_token_hash)
        """
    )


def downgrade() -> None:
    # This migration repairs an existing database.
    # Do not remove the authentication fields automatically.
    pass