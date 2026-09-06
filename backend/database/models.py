from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Text,
    Boolean
)

from sqlalchemy.orm import relationship

from backend.database.connection import Base


# ============================================================
# User Model
# ============================================================

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    # --------------------------------------------------------
    # Relationship with documents
    # --------------------------------------------------------

    documents = relationship(
        "Document",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # --------------------------------------------------------
    # Relationship with conversations
    # --------------------------------------------------------

    conversations = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan"
    )


# ============================================================
# Document Model
# ============================================================

class Document(Base):

    __tablename__ = "documents"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # --------------------------------------------------------
    # User who owns this document
    # --------------------------------------------------------

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # --------------------------------------------------------
    # Unique document ID
    # --------------------------------------------------------

    document_id = Column(
        String(36),
        nullable=False,
        unique=True,
        index=True
    )

    # --------------------------------------------------------
    # Original PDF filename
    # --------------------------------------------------------

    filename = Column(
        String(500),
        nullable=False
    )

    # --------------------------------------------------------
    # PDF information
    # --------------------------------------------------------

    pages = Column(
        Integer,
        nullable=False,
        default=0
    )

    chunks = Column(
        Integer,
        nullable=False,
        default=0
    )

    # --------------------------------------------------------
    # Upload timestamp
    # --------------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # --------------------------------------------------------
    # Relationship with User
    # --------------------------------------------------------

    user = relationship(
        "User",
        back_populates="documents"
    )

    # --------------------------------------------------------
    # Relationship with conversations
    # --------------------------------------------------------

    conversations = relationship(
        "Conversation",
        back_populates="document",
        cascade="all, delete-orphan"
    )

    # --------------------------------------------------------
    # Prevent duplicate filename per user
    # --------------------------------------------------------

    __table_args__ = (

        UniqueConstraint(
            "user_id",
            "filename",
            name="uq_user_document_filename"
        ),

    )


# ============================================================
# Conversation Model
# ============================================================

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # --------------------------------------------------------
    # Unique conversation identifier
    # --------------------------------------------------------

    conversation_id = Column(
        String(36),
        unique=True,
        nullable=False,
        index=True
    )

    # --------------------------------------------------------
    # User who owns conversation
    # --------------------------------------------------------

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # --------------------------------------------------------
    # Optional document associated with conversation
    #
    # IMPORTANT:
    # nullable=True allows normal ChatGPT-style
    # conversations without a PDF.
    #
    # Example:
    #
    # "Explain Python decorators."
    #
    # This conversation does not need a document.
    # --------------------------------------------------------

    document_id = Column(
        String(36),
        ForeignKey(
            "documents.document_id",
            ondelete="CASCADE"
        ),
        nullable=True,
        index=True
    )

    # --------------------------------------------------------
    # Conversation title
    # --------------------------------------------------------

    title = Column(
        String(255),
        nullable=False,
        default="New Conversation"
    )

    # --------------------------------------------------------
    # Pinned status
    #
    # False = normal conversation
    # True  = pinned conversation
    #
    # This is used by the sidebar PINNED section.
    # --------------------------------------------------------

    pinned = Column(
        Boolean,
        nullable=False,
        default=False
    )

    # --------------------------------------------------------
    # Creation timestamp
    # --------------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # --------------------------------------------------------
    # Last updated timestamp
    # --------------------------------------------------------

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # --------------------------------------------------------
    # Relationship with User
    # --------------------------------------------------------

    user = relationship(
        "User",
        back_populates="conversations"
    )

    # --------------------------------------------------------
    # Relationship with Document
    # --------------------------------------------------------

    document = relationship(
        "Document",
        back_populates="conversations"
    )

    # --------------------------------------------------------
    # Relationship with Messages
    # --------------------------------------------------------

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


# ============================================================
# Message Model
# ============================================================

class Message(Base):

    __tablename__ = "messages"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # --------------------------------------------------------
    # Conversation
    # --------------------------------------------------------

    conversation_id = Column(
        Integer,
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE"
        ),
        nullable=False,
        index=True
    )

    # --------------------------------------------------------
    # Message role
    #
    # Possible values:
    #
    # user
    # assistant
    # --------------------------------------------------------

    role = Column(
        String(20),
        nullable=False
    )

    # --------------------------------------------------------
    # Message content
    # --------------------------------------------------------

    content = Column(
        Text,
        nullable=False
    )

    # --------------------------------------------------------
    # Optional image filename
    #
    # We'll use this when we add image support.
    # --------------------------------------------------------

    image_filename = Column(
        String(500),
        nullable=True
    )

    # --------------------------------------------------------
    # Message timestamp
    # --------------------------------------------------------

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # --------------------------------------------------------
    # Relationship with Conversation
    # --------------------------------------------------------

    conversation = relationship(
        "Conversation",
        back_populates="messages"
    )