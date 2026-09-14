"""add password reset fields

Revision ID: 3d92d00f6258
Revises: 7f2c1a9d4e31
Create Date: 2026-09-14 21:29:19.078813

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3d92d00f6258'
down_revision: Union[str, Sequence[str], None] = '7f2c1a9d4e31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'password_reset_token_hash',
            sa.String(length=64),
            nullable=True
        )
    )
    op.add_column(
        'users',
        sa.Column(
            'password_reset_expires_at',
            sa.DateTime(),
            nullable=True
        )
    )
    op.create_index(
        op.f('ix_users_password_reset_token_hash'),
        'users',
        ['password_reset_token_hash'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_users_password_reset_token_hash'),
        table_name='users'
    )
    op.drop_column('users', 'password_reset_expires_at')
    op.drop_column('users', 'password_reset_token_hash')
