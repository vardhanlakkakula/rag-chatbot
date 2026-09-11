import uuid

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

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

from backend.rag.generator import (
    generate_conversation_answer,
    generate_rag_answer,
    analyze_user_request,
)

from backend.rag.qdrant_retriever import retrieve_from_qdrant

from backend.rag.qdrant_store import COLLECTION_NAME


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


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


    return {

        "conversation_id":
            conversation.conversation_id,

        "title":
            conversation.title,

        "user_id":
            conversation.user_id,

        "document_id":
            conversation.document_id,

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
    # Request document takes priority.
    # Otherwise use conversation document.
    # ========================================================

    document_id = (

        request.document_id

        if request.document_id

        else conversation.document_id
    )


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


# ============================================================
# Fallback: retrieve document chunks directly
# ============================================================

def retrieve_document_fallback(
    qdrant_client,
    user_id,
    document_id,
    max_chunks=12,
):
    """
    Fallback retrieval used when semantic search returns no
    usable chunks or Gemini reports that the document context
    was insufficient.

    This does NOT answer the question. It only fetches actual
    chunks belonging to the selected user/document so Gemini
    can inspect them.

    This is especially useful for:
        - broad document questions
        - spelling mistakes
        - badly formed sentences
        - very short questions
        - "what is this PDF about?"
        - overview requests
    """

    if not qdrant_client:
        return []

    must_conditions = [
        {
            "key": "user_id",
            "match": {
                "value": str(user_id)
            }
        },
        {
            "key": "document_id",
            "match": {
                "value": str(document_id)
            }
        }
    ]

    all_points = []
    next_offset = None

    try:

        # --------------------------------------------------------
        # Read document points directly from Qdrant.
        # We only need payloads, not vectors.
        # --------------------------------------------------------

        while True:

            points, next_offset = qdrant_client.scroll(

                collection_name=COLLECTION_NAME,

                scroll_filter={
                    "must": must_conditions
                },

                limit=256,

                offset=next_offset,

                with_payload=True,

                with_vectors=False,
            )

            if not points:
                break

            all_points.extend(points)

            if next_offset is None:
                break

            # Safety limit so an unexpectedly huge document
            # cannot cause an unlimited loop.
            if len(all_points) >= 2048:
                break

        if not all_points:
            return []

        # --------------------------------------------------------
        # Convert Qdrant points into the same structure used by
        # the normal retriever.
        # --------------------------------------------------------

        chunks = []

        seen = set()

        for point in all_points:

            payload = point.payload or {}

            chunk_id = payload.get(
                "chunk_id",
                str(point.id)
            )

            key = (
                str(payload.get(
                    "document_id",
                    document_id
                )),
                str(chunk_id),
            )

            if key in seen:
                continue

            seen.add(key)

            raw_text = payload.get(
                "text",
                ""
            )

            if not raw_text:
                continue

            text_value = str(
                raw_text
            ).strip()

            if not text_value:
                continue

            page = payload.get(
                "page",
                0
            )

            try:
                page = int(page)
            except (
                TypeError,
                ValueError
            ):
                page = 0

            chunks.append(
                {
                    "text": text_value,

                    "source": payload.get(
                        "source",
                        "Unknown"
                    ),

                    "filename": payload.get(
                        "filename",
                        "Unknown"
                    ),

                    "document_id": payload.get(
                        "document_id",
                        document_id
                    ),

                    "page": page,

                    "chunk_id": chunk_id,

                    # Direct fallback retrieval does not have
                    # a semantic score.
                    "score": 0.0,
                }
            )

        if not chunks:
            return []

        # --------------------------------------------------------
        # Sort by chunk number when possible.
        # --------------------------------------------------------

        def chunk_sort_key(item):

            value = item.get(
                "chunk_id",
                0
            )

            try:
                return int(value)
            except (
                TypeError,
                ValueError
            ):
                return 0

        chunks.sort(
            key=chunk_sort_key
        )

        # --------------------------------------------------------
        # If the document is small, use all chunks.
        #
        # For a larger document, sample across the document
        # rather than taking only the first 12 chunks.
        # --------------------------------------------------------

        if len(chunks) <= max_chunks:
            return chunks

        selected = []

        for index in range(max_chunks):

            position = round(
                index *
                (len(chunks) - 1) /
                (max_chunks - 1)
            )

            selected.append(
                chunks[position]
            )

        return selected

    except Exception as error:

        print(
            "DOCUMENT FALLBACK RETRIEVAL ERROR:",
            str(error)
        )

        return []


@router.post("/message")
async def send_chat_message(

    http_request: Request,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # ========================================================
    # 0. Parse JSON or multipart/form-data
    #
    # FastAPI must not validate the uploaded image as a request
    # body field. We read multipart data manually so the raw image
    # bytes never enter FastAPI's validation-error encoder.
    # ========================================================

    image = None

    content_type = http_request.headers.get(
        "content-type",
        ""
    ).lower()

    if content_type.startswith(
        "multipart/form-data"
    ):
        form = await http_request.form()

        chat_request = ChatMessageRequest(
            question=str(
                form.get("question") or ""
            ),
            conversation_id=(
                str(form.get("conversation_id"))
                if form.get("conversation_id")
                else None
            ),
            document_id=(
                str(form.get("document_id"))
                if form.get("document_id")
                else None
            ),
        )

        uploaded_image = form.get("image")

        if (
            uploaded_image is not None
            and hasattr(uploaded_image, "read")
        ):
            image_data = await uploaded_image.read()

            if image_data:
                image = (
                    image_data,
                    getattr(
                        uploaded_image,
                        "content_type",
                        None,
                    )
                    or "application/octet-stream",
                )

    else:
        payload = await http_request.json()

        chat_request = ChatMessageRequest(
            **payload
        )

    # Keep the existing request variable name below so the
    # remainder of the chat/RAG logic stays unchanged.
    request = chat_request

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

    document_id = (
        request.document_id
        if request.document_id
        else conversation.document_id
    )

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
        # 5. Save user message
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
        # 6. Load conversation history BEFORE retrieval
        #
        # Gemini first understands the user's meaning. This is important
        # because a selected PDF must not force every message (for example
        # "hiiii" or "how are u") through Qdrant.
        # ====================================================

        previous_messages = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id
            )
            .order_by(Message.created_at.asc())
            .all()
        )

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

            # Gemini understands spelling mistakes, abbreviations, bad
            # grammar and follow-up references before we search the PDF.
            request_analysis = analyze_user_request(
                question=question,
                previous_messages=previous_messages,
                client=gemini_client,
            )

            if request_analysis.get("needs_document"):

                search_query = (
                    request_analysis.get("search_query")
                    or question
                ).strip()

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

                # More candidates are useful for broad requests such as
                # "what is this PDF about?" and long-answer requests.
                retrieval_k = 8

                retrieved_chunks = retrieve_from_qdrant(
                    query_embeddings[0],
                    qdrant_client,
                    user_id=str(current_user.id),
                    document_id=document_id,
                    k=retrieval_k,
                )

        # ====================================================
        # 7. Generate conversational answer
        # ====================================================
        # ====================================================
        # 7. Load conversation history
        # ====================================================

        # ====================================================
        # 8. Generate conversational answer
        #
        #    IMPORTANT:
        #    This is NOT generate_rag_answer().
        #    Gemini decides whether the request is casual,
        #    misspelled, a follow-up, or document-related.
        # ====================================================

        answer = generate_conversation_answer(
            question=question,
            retrieved_chunks=retrieved_chunks,
            previous_messages=previous_messages,
            client=gemini_client,
            image=image,
        )

        # ====================================================
        # 8A. Document fallback
        # ====================================================
        #
        # If Gemini says that the document information was not
        # found, do one more retrieval pass using the actual
        # chunks stored for this document.
        #
        # This protects against:
        #
        # - spelling mistakes
        # - bad sentence formation
        # - broad questions
        # - weak semantic similarity
        # - Gemini's request-analysis choosing no retrieval
        #
        # The fallback still sends the final response through
        # Gemini. We never generate a hard-coded document answer.
        # ====================================================

        fallback_message = (
            "I couldn't find that information in the "
            "provided document."
        )

        if (
            document_id
            and (
                not retrieved_chunks
                or answer.strip() == fallback_message
            )
        ):

            fallback_chunks = retrieve_document_fallback(
                qdrant_client=qdrant_client,
                user_id=current_user.id,
                document_id=document_id,
                max_chunks=12,
            )

            if fallback_chunks:

                answer = generate_conversation_answer(
                    question=question,
                    retrieved_chunks=fallback_chunks,
                    previous_messages=previous_messages,
                    client=gemini_client,
                    image=image,
                )

                # Keep the fallback chunks as the sources shown
                # to the frontend.
                retrieved_chunks = fallback_chunks

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