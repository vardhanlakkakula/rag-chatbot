import uuid
import json
import re
import os

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user

from backend.database.connection import get_db

from backend.database.models import (
    User,
    Document,
    Conversation,
    Message,
)

from backend.rag.embeddings import create_embeddings
from backend.rag.loader import load_pdf
from backend.rag.chunker import chunk_documents

from backend.rag.generator import (
    generate_conversation_answer,
    generate_rag_answer,
)

from backend.rag.qdrant_retriever import (
    retrieve_from_qdrant,
    retrieve_document_fallback,
)


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


# ============================================================
# Direct local-PDF fallback
# ============================================================

def retrieve_document_from_local_pdf(document, user_id, max_chunks=20):
    """
    Read the selected PDF directly when Qdrant has no usable chunks.

    This is the last-resort safety net for cases where indexing was
    interrupted or a remote Qdrant write timed out. It guarantees that a
    selected document request such as "explain about pdf" does not fall
    back to generic knowledge about the PDF file format.
    """
    if not document:
        return []

    filename = str(getattr(document, "filename", "") or "").strip()
    if not filename:
        return []

    path = os.path.join(
        "backend",
        "data",
        "pdfs",
        f"user_{user_id}_{filename}",
    )

    if not os.path.exists(path):
        print("LOCAL PDF FALLBACK: file not found:", path)
        return []

    try:
        pages = load_pdf(path) or []
        chunks = chunk_documents(pages) or []
    except Exception as exc:
        print("LOCAL PDF FALLBACK ERROR:", str(exc))
        return []

    results = []
    for index, chunk in enumerate(chunks[:max_chunks]):
        metadata = getattr(chunk, "metadata", {}) or {}
        text = str(getattr(chunk, "page_content", "") or "").strip()
        if not text:
            continue

        results.append({
            "text": text,
            "source": metadata.get("source", path),
            "filename": filename,
            "document_id": str(getattr(document, "document_id", "")),
            "page": metadata.get("page", index + 1),
            "chunk_id": f"local-{index}",
            "score": 1.0,
        })

    print("LOCAL PDF FALLBACK: loaded", len(results), "chunks from", filename)
    return results


# ============================================================
# Request Models
# ============================================================


class CreateConversationRequest(BaseModel):

    title: str = "New Conversation"

    document_id: str | None = None


class UpdateConversationRequest(BaseModel):

    title: str


class CreateMessageRequest(BaseModel):

    role: str

    content: str


class AskConversationRequest(BaseModel):

    question: str

    document_id: str | None = None


class ChatMessageRequest(BaseModel):

    question: str

    conversation_id: str | None = None

    document_id: str | None = None


# ============================================================
# Helper
# ============================================================


def get_user_conversation(
    conversation_id: str,
    current_user: User,
    db: Session,
):

    conversation = (

        db.query(Conversation)

        .filter(

            Conversation.conversation_id ==
            conversation_id,

            Conversation.user_id ==
            current_user.id,

        )

        .first()
    )


    if not conversation:

        raise HTTPException(

            status_code=404,

            detail="Conversation not found.",
        )


    return conversation


# ============================================================
# Local retrieval-query builder
# ============================================================

def build_retrieval_query(question, previous_messages):
    """
    Build a semantic retrieval query without making an extra Gemini
    generation call. The current request is always first, followed by
    a small amount of recent conversation so follow-ups such as
    "what about its objectives?" still retrieve the correct PDF chunks.
    """

    current = (question or "").strip()

    recent = []

    for message in (previous_messages or [])[-6:]:
        role = str(getattr(message, "role", "") or "").strip().lower()
        content = str(getattr(message, "content", "") or "").strip()

        if not content:
            continue

        if role in {"user", "assistant"}:
            recent.append(f"{role}: {content}")

    context = "\n".join(recent)

    if context:
        return f"Current request: {current}\nRecent conversation:\n{context}"[:5000]

    return current


# ============================================================
# Document-intent detection
# ============================================================

def looks_like_document_request(question, previous_messages=None):
    """
    Decide whether a message should be answered using the selected
    document. This is deliberately conservative for general questions,
    but explicit references such as "this PDF", "the document",
    "about the pdf", and follow-ups to document answers are treated as
    document requests.

    This prevents a message such as "explain about pdf" from being
    interpreted as a generic question about the PDF file format.
    """
    q = (question or "").strip().lower()
    q = re.sub(r"\s+", " ", q)

    if not q:
        return False

    # Explicit document references. Include common informal/spelling
    # variants because these are user-facing intent signals, not facts.
    explicit_patterns = (
        r"\bpdf\b",
        r"\bpdfs\b",
        r"\bdocument\b",
        r"\bdoc\b",
        r"\bfile\b",
        r"\bthis file\b",
        r"\bthat file\b",
        r"\bthis document\b",
        r"\bthat document\b",
        r"\bthis pdf\b",
        r"\bthat pdf\b",
        r"\bthe pdf\b",
        r"\bthe document\b",
        r"\bfrom the pdf\b",
        r"\bin the pdf\b",
        r"\bfrom this pdf\b",
        r"\bin this pdf\b",
        r"\baccording to the pdf\b",
        r"\babout the pdf\b",
        r"\babout this pdf\b",
        r"\bfrom the document\b",
        r"\bin the document\b",
        r"\baccording to the document\b",
        r"\babout the document\b",
        r"\babout this document\b",
        r"\bfrom the file\b",
        r"\bin the file\b",
    )

    if any(re.search(pattern, q) for pattern in explicit_patterns):
        # "what is a PDF?" is normally a general file-format question,
        # not a question about the selected uploaded PDF.
        if re.search(r"\bwhat is (a|an) pdf\b", q) and not re.search(
            r"\b(this|the|my|that) pdf\b", q
        ):
            return False
        return True

    # Document transformations are document-grounded when a document
    # is selected.
    transformation_words = (
        "summarize", "summary", "main points", "key points",
        "extract", "convert", "turn into", "generate questions",
        "make questions", "create questions", "queries", "quiz",
        "mcq", "study questions", "notes", "outline",
    )

    if any(word in q for word in transformation_words):
        return True

    # Short follow-ups such as "explain that" or "what about the second
    # point?" should return to the document when the recent conversation
    # has already established a document topic.
    followup_patterns = (
        r"\bexplain (it|that|this|the first one|the second one)\b",
        r"\bwhat about (it|that|this|the first one|the second one)\b",
        r"\bwhat was (it|that|this|the first|the second)\b",
        r"\bthe (first|second|third) (point|topic|section|question)\b",
        r"\bgo back to (it|that|the document|the pdf)\b",
        r"\bfrom (it|that|this)\b",
    )

    if any(re.search(pattern, q) for pattern in followup_patterns):
        return True

    return False



# ============================================================
# Health
# ============================================================


@router.get("/health")
def chat_health():

    return {

        "status":
            "healthy",

        "service":
            "chat",
    }


# ============================================================
# Create Conversation
# ============================================================


@router.post("/conversations")
def create_conversation(

    request: CreateConversationRequest,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # --------------------------------------------------------
    # Validate document
    # --------------------------------------------------------

    if request.document_id:

        document = (

            db.query(Document)

            .filter(

                Document.document_id ==
                request.document_id,

                Document.user_id ==
                current_user.id,

            )

            .first()
        )


        if not document:

            raise HTTPException(

                status_code=404,

                detail=(
                    "Document not found or does not "
                    "belong to the current user."
                ),
            )


    # --------------------------------------------------------
    # Create conversation ID
    # --------------------------------------------------------

    conversation_id = str(
        uuid.uuid4()
    )


    title = request.title.strip()


    if not title:

        title = "New Conversation"


    # --------------------------------------------------------
    # Create conversation
    # --------------------------------------------------------

    conversation = Conversation(

        conversation_id=
            conversation_id,

        user_id=
            current_user.id,

        document_id=
            request.document_id,

        title=
            title,

        pinned=
            False,

        created_at=
            datetime.utcnow(),

        updated_at=
            datetime.utcnow(),
    )


    db.add(
        conversation
    )

    db.commit()

    db.refresh(
        conversation
    )


    return {

        "conversation_id":
            conversation.conversation_id,

        "title":
            conversation.title,

        "user_id":
            conversation.user_id,

        "document_id":
            conversation.document_id,

        "pinned":
            conversation.pinned,

        "created_at":
            conversation.created_at,

        "updated_at":
            conversation.updated_at,

        "messages":
            [],
    }


# ============================================================
# Get Conversations
# ============================================================


@router.get("/conversations")
def get_conversations(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversations = (

        db.query(Conversation)

        .filter(

            Conversation.user_id ==
            current_user.id
        )

        .order_by(

            Conversation.updated_at.desc()
        )

        .all()
    )


    result = []


    for conversation in conversations:

        last_message = (

            db.query(Message)

            .filter(

                Message.conversation_id ==
                conversation.id
            )

            .order_by(

                Message.created_at.desc()
            )

            .first()
        )


        result.append({

            "conversation_id":
                conversation.conversation_id,

            "title":
                conversation.title,

            "document_id":
                conversation.document_id,

            "pinned":
                conversation.pinned,

            "created_at":
                conversation.created_at,

            "updated_at":
                conversation.updated_at,

            "last_message":

                (
                    last_message.content
                    if last_message
                    else None
                ),

            "last_message_role":

                (
                    last_message.role
                    if last_message
                    else None
                ),
        })


    return {

        "conversations":
            result
    }


# ============================================================
# Get Conversation
# ============================================================


@router.get(
    "/conversations/{conversation_id}"
)
def get_conversation(

    conversation_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    messages = (

        db.query(Message)

        .filter(

            Message.conversation_id ==
            conversation.id
        )

        .order_by(

            Message.created_at.asc()
        )

        .all()
    )


    conversation_document = None

    if conversation.document_id:
        conversation_document = (
            db.query(Document)
            .filter(
                Document.document_id == conversation.document_id,
                Document.user_id == current_user.id,
            )
            .first()
        )

    return {

        "conversation_id":
            conversation.conversation_id,

        "title":
            conversation.title,

        "user_id":
            conversation.user_id,

        "document_id":
            conversation.document_id,

        "document": (
            {
                "document_id": conversation_document.document_id,
                "filename": conversation_document.filename,
                "user_id": conversation_document.user_id,
                "pages": getattr(conversation_document, "pages", None),
                "chunks": getattr(conversation_document, "chunks", None),
                "created_at": conversation_document.created_at,
            }
            if conversation_document
            else None
        ),

        "created_at":
            conversation.created_at,

        "updated_at":
            conversation.updated_at,

        "messages": [

            {

                "id":
                    message.id,

                "role":
                    message.role,

                "content":
                    message.content,

                "created_at":
                    message.created_at,

            }

            for message in messages
        ],
    }


# ============================================================
# Rename Conversation
# ============================================================


@router.patch(
    "/conversations/{conversation_id}"
)
def update_conversation(

    conversation_id: str,

    request: UpdateConversationRequest,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    title = request.title.strip()


    if not title:

        raise HTTPException(

            status_code=400,

            detail=(
                "Conversation title cannot be empty."
            ),
        )


    conversation.title = title

    conversation.updated_at = datetime.utcnow()


    db.commit()

    db.refresh(
        conversation
    )


    return {

        "conversation_id":
            conversation.conversation_id,

        "title":
            conversation.title,

        "updated_at":
            conversation.updated_at,
    }


# ============================================================
# Pin / Unpin Conversation
# ============================================================


@router.patch(
    "/conversations/{conversation_id}/pin"
)
def toggle_pin_conversation(

    conversation_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # --------------------------------------------------------
    # Get conversation belonging to current user
    # --------------------------------------------------------

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )

    # --------------------------------------------------------
    # Toggle pinned status
    # --------------------------------------------------------

    conversation.pinned = not conversation.pinned

    conversation.updated_at = datetime.utcnow()

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    db.commit()

    db.refresh(
        conversation
    )

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {

        "conversation_id":
            conversation.conversation_id,

        "title":
            conversation.title,

        "pinned":
            conversation.pinned,

        "updated_at":
            conversation.updated_at,
    }


# ============================================================
# Delete Conversation
# ============================================================


@router.delete(
    "/conversations/{conversation_id}"
)
def delete_conversation(

    conversation_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    db.delete(
        conversation
    )

    db.commit()


    return {

        "message":
            "Conversation deleted successfully.",

        "conversation_id":
            conversation_id,
    }


# ============================================================
# Add Message
# ============================================================


@router.post(
    "/conversations/{conversation_id}/messages"
)
def add_message(

    conversation_id: str,

    request: CreateMessageRequest,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    if request.role not in {
        "user",
        "assistant",
    }:

        raise HTTPException(

            status_code=400,

            detail=(
                "Role must be 'user' or 'assistant'."
            ),
        )


    # --------------------------------------------------------
    # Validate content
    # --------------------------------------------------------

    if not request.content.strip():

        raise HTTPException(

            status_code=400,

            detail=(
                "Message content cannot be empty."
            ),
        )


    # --------------------------------------------------------
    # Save message
    # --------------------------------------------------------

    message = Message(

        conversation_id=
            conversation.id,

        role=
            request.role,

        content=
            request.content,

        created_at=
            datetime.utcnow(),
    )


    db.add(
        message
    )


    conversation.updated_at = datetime.utcnow()


    db.commit()

    db.refresh(
        message
    )


    return {

        "id":
            message.id,

        "conversation_id":
            conversation.conversation_id,

        "role":
            message.role,

        "content":
            message.content,

        "created_at":
            message.created_at,
    }


# ============================================================
# ASK QUESTION INSIDE CONVERSATION
# ============================================================


@router.post(
    "/conversations/{conversation_id}/ask"
)
def ask_conversation(

    conversation_id: str,

    request: AskConversationRequest,

    http_request: Request,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # ========================================================
    # 1. Get conversation
    # ========================================================

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    # ========================================================
    # 2. Validate question
    # ========================================================

    question = request.question.strip()


    if not question:

        raise HTTPException(

            status_code=400,

            detail="Question cannot be empty.",
        )


    # ========================================================
    # 3. Determine document
    #
    # Existing conversation: its stored document is authoritative.
    # A request cannot switch an existing chat to another PDF.
    # New-document selection belongs to the conversation itself.
    # ========================================================

    document_id = conversation.document_id


    selected_document = None


    if document_id:

        selected_document = (

            db.query(Document)

            .filter(

                Document.document_id ==
                document_id,

                Document.user_id ==
                current_user.id,

            )

            .first()
        )


        if not selected_document:

            raise HTTPException(

                status_code=404,

                detail=(
                    "Document not found or does not "
                    "belong to the current user."
                ),
            )


    # ========================================================
    # 4. Save user message
    # ========================================================

    user_message = Message(

        conversation_id=
            conversation.id,

        role=
            "user",

        content=
            question,

        created_at=
            datetime.utcnow(),
    )


    db.add(
        user_message
    )


    conversation.updated_at = datetime.utcnow()


    db.commit()

    db.refresh(
        user_message
    )


    # ========================================================
    # 5. Get shared clients
    # ========================================================

    gemini_client = getattr(

        http_request.app.state,

        "gemini_client",

        None
    )


    qdrant_client = getattr(

        http_request.app.state,

        "qdrant_client",

        None
    )


    if gemini_client is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "Gemini client is not configured."
            ),
        )


    if qdrant_client is None:

        raise HTTPException(

            status_code=500,

            detail=(
                "Qdrant client is not configured."
            ),
        )


    try:

        # ====================================================
        # 6. Create question embedding
        # ====================================================

        from langchain_core.documents import (
            Document as LangChainDocument
        )


        question_document = LangChainDocument(

            page_content=
                question
        )


        question_embeddings = create_embeddings(

            [question_document],

            gemini_client
        )


        if not question_embeddings:

            raise ValueError(
                "Question embedding was not generated."
            )


        query_embedding = (

            question_embeddings[0]
        )


        # ====================================================
        # 7. Retrieve relevant chunks
        # ====================================================

        retrieved_chunks = (

            retrieve_from_qdrant(

                query_embedding,

                qdrant_client,

                user_id=str(
                    current_user.id
                ),

                document_id=document_id,

                k=4,
            )
        )


        # ====================================================
        # 8. Generate answer
        # ====================================================

        if not retrieved_chunks:

            answer = (
                "I couldn't find relevant information "
                "in the provided document."
            )

            sources = []

        else:

            answer = generate_rag_answer(

                question,

                retrieved_chunks,

                gemini_client
            )


            # =================================================
            # 9. Build sources
            # =================================================

            sources = []

            seen_sources = set()


            for result in retrieved_chunks:

                source_key = (

                    result.get("source"),

                    result.get("page"),

                    result.get("chunk_id"),
                )


                if source_key in seen_sources:

                    continue


                seen_sources.add(
                    source_key
                )


                sources.append({

                    "source":
                        result.get(
                            "source",
                            "Unknown"
                        ),

                    "filename":
                        result.get(
                            "filename",
                            "Unknown"
                        ),

                    "document_id":
                        result.get(
                            "document_id"
                        ),

                    "page":
                        result.get(
                            "page",
                            0
                        ),

                    "chunk_id":
                        result.get(
                            "chunk_id"
                        ),

                    "score":
                        result.get(
                            "score"
                        ),
                })


        # ====================================================
        # 10. Save assistant message
        # ====================================================

        assistant_message = Message(

            conversation_id=
                conversation.id,

            role=
                "assistant",

            content=
                answer,

            created_at=
                datetime.utcnow(),
        )


        db.add(
            assistant_message
        )


        conversation.updated_at = datetime.utcnow()


        db.commit()

        db.refresh(
            assistant_message
        )


        # ====================================================
        # 11. Return complete response
        # ====================================================

        return {

            "conversation_id":
                conversation.conversation_id,

            "question":
                question,

            "answer":
                answer,

            "document_id":
                document_id,

            "filename":

                (
                    selected_document.filename
                    if selected_document
                    else None
                ),

            "message_id":
                assistant_message.id,

            "sources":
                sources,
        }


    except HTTPException:

        raise


    except Exception as e:

        # ----------------------------------------------------
        # Roll back database changes
        # ----------------------------------------------------

        try:

            db.rollback()

        except Exception:

            pass


        print(
            "CHAT RAG ERROR:",
            str(e)
        )


        raise HTTPException(

            status_code=500,

            detail=
                f"Error answering question: {str(e)}",
        )



# ============================================================
# COMPATIBILITY CHAT ENDPOINT
#
# This endpoint supports the frontend call:
# POST /chat/message
#
# It creates a conversation automatically for the first message.
# Casual messages and spelling mistakes are sent to Gemini.
# Document questions additionally use Qdrant retrieval.
# ============================================================

@router.post("/message")
def send_chat_message(

    request: ChatMessageRequest,

    http_request: Request,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # ========================================================
    # 1. Validate question
    # ========================================================

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    # ========================================================
    # 2. Find existing conversation or create one
    # ========================================================

    conversation = None

    if request.conversation_id:
        conversation = get_user_conversation(
            request.conversation_id,
            current_user,
            db,
        )

    if conversation is None:

        selected_document = None

        if request.document_id:
            selected_document = (
                db.query(Document)
                .filter(
                    Document.document_id == request.document_id,
                    Document.user_id == current_user.id,
                )
                .first()
            )

            if not selected_document:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Document not found or does not "
                        "belong to the current user."
                    ),
                )

        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            user_id=current_user.id,
            document_id=(
                selected_document.document_id
                if selected_document
                else None
            ),
            title=question[:60],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(conversation)
        db.flush()

    # ========================================================
    # 3. Determine document
    # ========================================================

    # Conversation document isolation:
    # - Existing conversation: its stored document is authoritative.
    # - New conversation: the request document can be attached.
    # Never allow a stale frontend document ID to switch an existing chat
    # to another chat's PDF.
    if conversation.document_id:
        document_id = conversation.document_id
    else:
        document_id = request.document_id
        if document_id:
            conversation.document_id = document_id
            conversation.updated_at = datetime.utcnow()
            db.flush()

    selected_document = None

    if document_id:
        selected_document = (
            db.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.user_id == current_user.id,
            )
            .first()
        )

        if not selected_document:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail=(
                    "Document not found or does not "
                    "belong to the current user."
                ),
            )

        # Keep the selected document attached to this conversation. This
        # prevents a later message from falling back to an older PDF.
        if conversation.document_id != document_id:
            conversation.document_id = document_id

    try:

        # ====================================================
        # 4. Get Gemini client
        # ====================================================

        gemini_client = getattr(
            http_request.app.state,
            "gemini_client",
            None,
        )

        if gemini_client is None:
            raise HTTPException(
                status_code=500,
                detail="Gemini client is not configured.",
            )

        # ====================================================
        # 5. Load conversation history BEFORE saving the current
        #    user message. This keeps the history clean and lets
        #    the answer model see only genuinely previous turns.
        # ====================================================

        previous_messages = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id
            )
            .order_by(Message.created_at.asc())
            .all()
        )

        # ====================================================
        # 6. Save the current user message
        # ====================================================

        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=question,
            created_at=datetime.utcnow(),
        )

        db.add(user_message)
        db.flush()

        # ====================================================
        # 7. Retrieve PDF context when a document is selected
        #
        #    There is intentionally NO separate Gemini intent-analysis
        #    call here. The answer itself is generated with one Gemini
        #    generation request. Retrieval uses embeddings + Qdrant,
        #    while the answer model decides whether the retrieved PDF
        #    information is relevant to the current request.
        # ====================================================

        retrieved_chunks = []

        if document_id:

            qdrant_client = getattr(
                http_request.app.state,
                "qdrant_client",
                None,
            )

            if qdrant_client is None:
                raise HTTPException(
                    status_code=500,
                    detail="Qdrant client is not configured.",
                )

            document_request = looks_like_document_request(
                question,
                previous_messages,
            )

            # General questions should remain general even when a PDF is
            # selected. Explicit document requests are grounded in the
            # selected document.
            if document_request:
                search_query = build_retrieval_query(
                    question,
                    previous_messages,
                )

                from langchain_core.documents import (
                    Document as LangChainDocument
                )

                query_document = LangChainDocument(
                    page_content=search_query
                )

                query_embeddings = create_embeddings(
                    [query_document],
                    gemini_client,
                )

                if not query_embeddings:
                    raise ValueError(
                        "Question embedding was not generated."
                    )

                retrieved_chunks = retrieve_from_qdrant(
                    query_embeddings[0],
                    qdrant_client,
                    user_id=str(current_user.id),
                    document_id=document_id,
                    k=8,
                )

                normalized_request = question.lower()
                broad_document_request = (
                    "pdf" in normalized_request
                    or "document" in normalized_request
                    or "file" in normalized_request
                    or any(
                        verb in normalized_request
                        for verb in (
                            "summarize", "summary", "main points",
                            "key points", "convert", "turn into",
                            "generate questions", "make questions",
                            "create questions", "queries", "quiz", "mcq",
                            "extract", "outline", "notes",
                        )
                    )
                )

                # Broad questions cannot be reliably answered from only the
                # nearest semantic chunks. Pull representative chunks from
                # the EXACT selected document. This is the critical fix for
                # questions such as "explain about pdf".
                if broad_document_request or len(retrieved_chunks) < 2:
                    fallback_chunks = retrieve_document_fallback(
                        qdrant_client,
                        user_id=str(current_user.id),
                        document_id=document_id,
                        max_chunks=20,
                    )

                    if fallback_chunks:
                        if broad_document_request:
                            retrieved_chunks = fallback_chunks[:20]
                        else:
                            seen_chunk_ids = {
                                str(item.get("chunk_id"))
                                for item in retrieved_chunks
                            }
                            for item in fallback_chunks:
                                if str(item.get("chunk_id")) not in seen_chunk_ids:
                                    retrieved_chunks.append(item)

                # FINAL SAFETY NET: if the selected PDF has no Qdrant
                # context, read the actual selected PDF from disk.
                if document_request and not retrieved_chunks and selected_document:
                    retrieved_chunks = retrieve_document_from_local_pdf(
                        selected_document,
                        user_id=str(current_user.id),
                        max_chunks=20,
                    )

        # ====================================================
        # 8. Generate conversational answer
        #
        #    Exactly ONE Gemini text-generation request is made here.
        #    Previous conversation + retrieved PDF context are supplied
        #    together so follow-ups, spelling mistakes and informal
        #    wording are handled by the same answer model.
        # ====================================================

        # ====================================================
        # Generate conversational answer
        # ====================================================

        answer = generate_conversation_answer(
            question=question,
            retrieved_chunks=retrieved_chunks,
            previous_messages=previous_messages,
            client=gemini_client,
        )

        # ====================================================
        # 9. Save assistant message
        # ====================================================

        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            created_at=datetime.utcnow(),
        )

        db.add(assistant_message)
        conversation.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(assistant_message)

        # ====================================================
        # 10. Build sources
        # ====================================================

        sources = []
        seen_sources = set()

        for result in retrieved_chunks:

            source_key = (
                result.get("source"),
                result.get("page"),
                result.get("chunk_id"),
            )

            if source_key in seen_sources:
                continue

            seen_sources.add(source_key)

            sources.append({
                "source": result.get(
                    "source",
                    "Unknown"
                ),
                "filename": result.get(
                    "filename",
                    "Unknown"
                ),
                "document_id": result.get(
                    "document_id"
                ),
                "page": result.get(
                    "page",
                    0
                ),
                "chunk_id": result.get(
                    "chunk_id"
                ),
                "score": result.get(
                    "score"
                ),
            })

        # ====================================================
        # 11. Return
        # ====================================================

        return {
            "conversation_id": conversation.conversation_id,
            "question": question,
            "answer": answer,
            "document_id": document_id,
            "filename": (
                selected_document.filename
                if selected_document
                else None
            ),
            "message_id": assistant_message.id,
            "sources": sources,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()

        import traceback

        print(
            "CHAT MESSAGE ERROR:",
            str(e)
        )

        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Error answering question: {str(e)}"
            ),
        )



# ============================================================
# LOW-LATENCY STREAMING CHAT ENDPOINT
# ============================================================

@router.post("/message/stream")
def send_chat_message_stream(
    request: ChatMessageRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streaming version of /chat/message.

    The frontend can show its thinking state immediately and then
    display Gemini tokens as soon as they arrive instead of waiting
    for the complete answer.
    """

    question = (request.question or "").strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    gemini_client = getattr(
        http_request.app.state,
        "gemini_client",
        None,
    )

    if gemini_client is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini client is not configured.",
        )

    # --------------------------------------------------------
    # Resolve/create conversation before streaming starts.
    # --------------------------------------------------------

    conversation = None

    if request.conversation_id:
        conversation = get_user_conversation(
            request.conversation_id,
            current_user,
            db,
        )

    if conversation is None:
        selected_document = None

        if request.document_id:
            selected_document = (
                db.query(Document)
                .filter(
                    Document.document_id == request.document_id,
                    Document.user_id == current_user.id,
                )
                .first()
            )

            if not selected_document:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Document not found or does not "
                        "belong to the current user."
                    ),
                )

        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            user_id=current_user.id,
            document_id=(
                selected_document.document_id
                if selected_document
                else None
            ),
            title=question[:60],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.add(conversation)
        db.flush()

    # Existing conversations are permanently scoped to their stored PDF.
    # A request from the frontend can only supply the document for a brand
    # new conversation; it cannot switch an existing chat to another PDF.
    if conversation.document_id:
        document_id = conversation.document_id
    else:
        document_id = request.document_id
        if document_id:
            conversation.document_id = document_id
            conversation.updated_at = datetime.utcnow()
            db.flush()

    selected_document = None

    if document_id:
        selected_document = (
            db.query(Document)
            .filter(
                Document.document_id == document_id,
                Document.user_id == current_user.id,
            )
            .first()
        )

        if not selected_document:
            db.rollback()
            raise HTTPException(
                status_code=404,
                detail=(
                    "Document not found or does not "
                    "belong to the current user."
                ),
            )

    previous_messages = (
        db.query(Message)
        .filter(
            Message.conversation_id == conversation.id
        )
        .order_by(Message.created_at.asc())
        .all()
    )

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=question,
        created_at=datetime.utcnow(),
    )

    db.add(user_message)
    db.commit()
    db.refresh(conversation)

    conversation_id_value = conversation.conversation_id

    def event_stream():
        retrieved_chunks = []
        answer_parts = []

        try:
            # Send conversation metadata immediately. The frontend does
            # not have to wait for retrieval or Gemini to know the chat ID.
            yield json.dumps(
                {
                    "type": "meta",
                    "conversation_id": conversation_id_value,
                    "document_id": document_id,
                    "filename": (
                        selected_document.filename
                        if selected_document
                        else None
                    ),
                },
                ensure_ascii=False,
            ) + "\n"

            # ----------------------------------------------------
            # PDF retrieval only when a document is selected.
            # ----------------------------------------------------

            if document_id:
                qdrant_client = getattr(
                    http_request.app.state,
                    "qdrant_client",
                    None,
                )

                if qdrant_client is None:
                    raise RuntimeError(
                        "Qdrant client is not configured."
                    )

                from langchain_core.documents import Document as LangChainDocument

                search_query = build_retrieval_query(
                    question,
                    previous_messages,
                )

                query_document = LangChainDocument(
                    page_content=search_query
                )

                query_embeddings = create_embeddings(
                    [query_document],
                    gemini_client,
                )

                if not query_embeddings:
                    raise RuntimeError(
                        "Question embedding was not generated."
                    )

                retrieved_chunks = retrieve_from_qdrant(
                    query_embeddings[0],
                    qdrant_client,
                    user_id=str(current_user.id),
                    document_id=document_id,
                    k=8,
                )

                normalized_request = question.lower()
                broad_document_request = (
                    "pdf" in normalized_request
                    or "document" in normalized_request
                    or "file" in normalized_request
                    or any(
                        verb in normalized_request
                        for verb in (
                            "summarize", "summary", "main points",
                            "key points", "convert", "turn into",
                            "generate questions", "make questions",
                            "create questions", "queries", "quiz", "mcq",
                            "extract", "outline", "notes",
                        )
                    )
                )

                if broad_document_request or len(retrieved_chunks) < 2:
                    fallback_chunks = retrieve_document_fallback(
                        qdrant_client,
                        user_id=str(current_user.id),
                        document_id=document_id,
                        max_chunks=20,
                    )

                    if fallback_chunks:
                        if broad_document_request:
                            retrieved_chunks = fallback_chunks[:20]
                        else:
                            seen_chunk_ids = {
                                str(item.get("chunk_id"))
                                for item in retrieved_chunks
                            }
                            for item in fallback_chunks:
                                if str(item.get("chunk_id")) not in seen_chunk_ids:
                                    retrieved_chunks.append(item)

                if not retrieved_chunks and selected_document:
                    retrieved_chunks = retrieve_document_from_local_pdf(
                        selected_document,
                        user_id=str(current_user.id),
                        max_chunks=20,
                    )

            # ----------------------------------------------------
            # Stream Gemini output.
            # ----------------------------------------------------

            stream = generate_conversation_answer(
                question=question,
                retrieved_chunks=retrieved_chunks,
                previous_messages=previous_messages,
                client=gemini_client,
                stream=True,
            )

            for chunk in stream:
                text = getattr(chunk, "text", None) or ""

                if not text:
                    continue

                answer_parts.append(text)

                yield json.dumps(
                    {
                        "type": "chunk",
                        "text": text,
                    },
                    ensure_ascii=False,
                ) + "\n"

            answer = "".join(answer_parts).strip()

            if not answer:
                answer = "I couldn't generate an answer."

            assistant_message = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                created_at=datetime.utcnow(),
            )

            db.add(assistant_message)
            conversation.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(assistant_message)

            sources = []
            seen_sources = set()

            for result in retrieved_chunks:
                source_key = (
                    result.get("source"),
                    result.get("page"),
                    result.get("chunk_id"),
                )

                if source_key in seen_sources:
                    continue

                seen_sources.add(source_key)

                sources.append({
                    "source": result.get("source", "Unknown"),
                    "filename": result.get("filename", "Unknown"),
                    "document_id": result.get("document_id"),
                    "page": result.get("page", 0),
                    "chunk_id": result.get("chunk_id"),
                    "score": result.get("score"),
                })

            yield json.dumps(
                {
                    "type": "done",
                    "message_id": assistant_message.id,
                    "sources": sources,
                    "conversation_id": conversation_id_value,
                    "document_id": document_id,
                    "filename": (
                        selected_document.filename
                        if selected_document
                        else None
                    ),
                },
                ensure_ascii=False,
            ) + "\n"

        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass

            import traceback
            traceback.print_exc()

            yield json.dumps(
                {
                    "type": "error",
                    "error": str(e),
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# Delete Message
# ============================================================


@router.delete(
    "/conversations/{conversation_id}/messages/{message_id}"
)
def delete_message(

    conversation_id: str,

    message_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    conversation = get_user_conversation(

        conversation_id,

        current_user,

        db,
    )


    message = (

        db.query(Message)

        .filter(

            Message.id ==
            message_id,

            Message.conversation_id ==
            conversation.id,
        )

        .first()
    )


    if not message:

        raise HTTPException(

            status_code=404,

            detail="Message not found.",
        )


    db.delete(
        message
    )


    conversation.updated_at = datetime.utcnow()


    db.commit()


    return {

        "message":
            "Message deleted successfully.",

        "message_id":
            message_id,
    }