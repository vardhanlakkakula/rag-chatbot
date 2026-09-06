"""add conversation and message tables

Revision ID: c852f73aabbb
Revises:
Create Date: 2026-08-21 21:40:18.809235

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# Revision identifiers
# ============================================================

revision: str = "c852f73aabbb"

down_revision: Union[
    str,
    Sequence[str],
    None
] = None

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

    # --------------------------------------------------------
    # 1. Make document_id unique
    #
    # This allows conversations.document_id to reference
    # documents.document_id.
    # --------------------------------------------------------

    op.drop_index(
        "ix_documents_document_id",
        table_name="documents"
    )

    op.create_index(
        "ix_documents_document_id",
        "documents",
        ["document_id"],
        unique=True
    )


    # --------------------------------------------------------
    # 2. Create conversations table
    # --------------------------------------------------------

    op.create_table(

        "conversations",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "conversation_id",
            sa.String(length=36),
            nullable=False
        ),

        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "document_id",
            sa.String(length=36),
            nullable=False
        ),

        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE"
        ),

        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.document_id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint(
            "id"
        )
    )


    # --------------------------------------------------------
    # Conversation indexes
    # --------------------------------------------------------

    op.create_index(
        "ix_conversations_id",
        "conversations",
        ["id"],
        unique=False
    )

    op.create_index(
        "ix_conversations_conversation_id",
        "conversations",
        ["conversation_id"],
        unique=True
    )

    op.create_index(
        "ix_conversations_user_id",
        "conversations",
        ["user_id"],
        unique=False
    )

    op.create_index(
        "ix_conversations_document_id",
        "conversations",
        ["document_id"],
        unique=False
    )


    # --------------------------------------------------------
    # 3. Create messages table
    # --------------------------------------------------------

    op.create_table(

        "messages",

        sa.Column(
            "id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "conversation_id",
            sa.Integer(),
            nullable=False
        ),

        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False
        ),

        sa.Column(
            "content",
            sa.Text(),
            nullable=False
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False
        ),

        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE"
        ),

        sa.PrimaryKeyConstraint(
            "id"
        )
    )


    # --------------------------------------------------------
    # Message indexes
    # --------------------------------------------------------

    op.create_index(
        "ix_messages_id",
        "messages",
        ["id"],
        unique=False
    )

    op.create_index(
        "ix_messages_conversation_id",
        "messages",
        ["conversation_id"],
        unique=False
    )


# ============================================================
# Downgrade
# ============================================================

def downgrade() -> None:

    # --------------------------------------------------------
    # Remove messages
    # --------------------------------------------------------

    op.drop_index(
        "ix_messages_conversation_id",
        table_name="messages"
    )

    op.drop_index(
        "ix_messages_id",
        table_name="messages"
    )

    op.drop_table(
        "messages"
    )


    # --------------------------------------------------------
    # Remove conversations
    # --------------------------------------------------------

    op.drop_index(
        "ix_conversations_document_id",
        table_name="conversations"
    )

    op.drop_index(
        "ix_conversations_user_id",
        table_name="conversations"
    )

    op.drop_index(
        "ix_conversations_conversation_id",
        table_name="conversations"
    )

    op.drop_index(
        "ix_conversations_id",
        table_name="conversations"
    )

    op.drop_table(
        "conversations"
    )


    # --------------------------------------------------------
    # Restore normal document_id index
    # --------------------------------------------------------

    op.drop_index(
        "ix_documents_document_id",
        table_name="documents"
    )

    op.create_index(
        "ix_documents_document_id",
        "documents",
        ["document_id"],
        unique=False
    )