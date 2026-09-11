import os
import uuid

from dotenv import load_dotenv

from fastapi import (
    FastAPI,
    HTTPException,
    UploadFile,
    File,
    Depends
)

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from sqlalchemy.orm import Session

from qdrant_client.models import (
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)


from backend.rag.embeddings import (
    create_gemini_client,
    create_embeddings
)

from backend.rag.loader import load_pdf

from backend.rag.chunker import (
    chunk_documents
)

from backend.rag.generator import (
    generate_rag_answer
)

from backend.rag.qdrant_store import (
    create_qdrant_client,
    COLLECTION_NAME
)

from backend.rag.qdrant_retriever import (
    retrieve_from_qdrant
)


from backend.auth.routes import (
    router as auth_router
)

from backend.auth.dependencies import (
    get_current_user
)


from backend.database.connection import (
    get_db,
    Base,
    engine
)

from backend.database.models import (
    User,
    Document,
    Conversation,
    Message
)


from backend.documents import (
    router as documents_router
)


# ============================================================
# CHAT ROUTER
# ============================================================

from backend.chat import (
    router as chat_router
)


# ============================================================
# 1. Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# 2. Create FastAPI application
# ============================================================

app = FastAPI(

    title="Multi-User RAG Application",

    description=(
        "Multi-user PDF RAG using "
        "Gemini, Qdrant and PostgreSQL"
    ),

    version="8.0.0"
)


# ============================================================
# Initialize database tables
# ============================================================

Base.metadata.create_all(
    bind=engine
)


# ============================================================
# 3. CORS
# ============================================================

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://rag-chatbot-1-9ld0.onrender.com",

    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# 4. Register routers
# ============================================================

app.include_router(
    auth_router
)


app.include_router(
    documents_router
)


app.include_router(
    chat_router,
    prefix=""
)


# ============================================================
# 5. Create Gemini client
# ============================================================

client = create_gemini_client()


# ============================================================
# 6. Create Qdrant client
# ============================================================

qdrant_client = create_qdrant_client()


# ============================================================
# Shared clients for Chat router
# ============================================================

app.state.gemini_client = client

app.state.qdrant_client = qdrant_client


# ============================================================
# 7. PDF directory
# ============================================================

PDF_DIRECTORY = "backend/data/pdfs"

os.makedirs(
    PDF_DIRECTORY,
    exist_ok=True
)


# ============================================================
# 8. Question request model
# ============================================================

class QuestionRequest(BaseModel):

    question: str

    document_id: str | None = None


# ============================================================
# 9. Root endpoint
# ============================================================

@app.get("/")
def root():

    return {

        "message":
            "Multi-User RAG API is running",

        "vector_database":
            "Qdrant",

        "llm":
            "Gemini",

        "authentication":
            "JWT",

        "database":
            "PostgreSQL"

    }


# ============================================================
# 10. Health endpoint
# ============================================================

@app.get("/health")
def health():

    try:

        collection_info = (
            qdrant_client.get_collection(
                COLLECTION_NAME
            )
        )

        qdrant_vectors = (
            collection_info.points_count
        )

        qdrant_connected = True

    except Exception:

        qdrant_vectors = 0

        qdrant_connected = False


    return {

        "status":
            "healthy",

        "vector_database":
            "Qdrant",

        "qdrant_connected":
            qdrant_connected,

        "qdrant_vectors":
            qdrant_vectors,

        "authentication":
            "JWT",

        "database":
            "PostgreSQL"

    }


# ============================================================
# 11. Upload PDF
# ============================================================

@app.post("/upload_pdf")
async def upload_pdf(

    file: UploadFile = File(...),

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )

):

    user_id = current_user.id


    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(

            status_code=400,

            detail="No file was provided."

        )


    # --------------------------------------------------------
    # Validate PDF
    # --------------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):

        raise HTTPException(

            status_code=400,

            detail="Only PDF files are allowed."

        )


    # --------------------------------------------------------
    # Check duplicate
    # --------------------------------------------------------

    existing_document = (

        db.query(Document)

        .filter(

            Document.user_id == user_id,

            Document.filename == file.filename

        )

        .first()

    )


    # A previous upload may have created the PostgreSQL row but failed
    # before Qdrant finished writing the vectors.  In that case we MUST
    # re-index instead of returning the broken document as "already uploaded".
    reindex_existing = False

    if existing_document:
        existing_vector_count = 0

        try:
            existing_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=str(user_id)),
                    ),
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(existing_document.document_id)),
                    ),
                ]
            )

            existing_points, _ = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=existing_filter,
                limit=1,
                with_payload=False,
                with_vectors=False,
                timeout=30,
            )
            existing_vector_count = len(existing_points or [])
        except Exception as exc:
            print("EXISTING DOCUMENT INDEX CHECK WARNING:", str(exc))

        if existing_vector_count > 0:
            return {
                "message": "This PDF is already uploaded.",
                "filename": existing_document.filename,
                "document_id": existing_document.document_id,
                "user_id": user_id,
                "pages": existing_document.pages,
                "chunks": existing_document.chunks,
            }

        print(
            "Existing document has no Qdrant vectors. Re-indexing:",
            existing_document.filename,
        )
        reindex_existing = True

    # --------------------------------------------------------
    # Create/reuse document ID
    # --------------------------------------------------------

    document_id = (
        existing_document.document_id
        if reindex_existing
        else str(uuid.uuid4())
    )


    safe_filename = (
        f"user_{user_id}_{file.filename}"
    )


    pdf_path = os.path.join(

        PDF_DIRECTORY,

        safe_filename

    )


    try:

        # ====================================================
        # Save PDF
        # ====================================================

        file_content = await file.read()


        if not file_content:

            raise HTTPException(

                status_code=400,

                detail="Uploaded PDF is empty."

            )


        with open(

            pdf_path,

            "wb"

        ) as output_file:

            output_file.write(
                file_content
            )


        print(

            f"PDF uploaded by user {user_id}: "
            f"{file.filename}"

        )


        print(

            f"File size: "
            f"{len(file_content) / (1024 * 1024):.2f} MB"

        )


        # ====================================================
        # Load PDF
        # ====================================================

        print(
            "Loading PDF..."
        )


        documents = load_pdf(
            pdf_path
        )


        print(

            "Number of pages:",

            len(documents)

        )


        if not documents:

            raise ValueError(

                "No pages could be extracted from the PDF."

            )


        # ====================================================
        # Chunk
        # ====================================================

        print(
            "Chunking document..."
        )


        new_chunks = chunk_documents(
            documents
        )


        print(

            "Number of chunks:",

            len(new_chunks)

        )


        if not new_chunks:

            raise ValueError(

                "No chunks were created from the PDF."

            )


        # ====================================================
        # Embeddings
        # ====================================================

        print(
            "Creating embeddings..."
        )


        new_embeddings = create_embeddings(

            new_chunks,

            client

        )


        print(

            "Number of embeddings:",

            len(new_embeddings)

        )


        if not new_embeddings:

            raise ValueError(

                "No embeddings were generated."

            )


        print(

            "Embedding dimensions:",

            len(new_embeddings[0])

        )


        # ====================================================
        # Qdrant points
        # ====================================================

        points = []


        for i, (
            chunk,
            embedding
        ) in enumerate(

            zip(

                new_chunks,

                new_embeddings

            )

        ):

            metadata = (
                chunk.metadata or {}
            )


            source = metadata.get(

                "source",

                pdf_path

            )


            page = metadata.get(

                "page",

                0

            )


            payload = {

                "user_id":
                    str(user_id),

                "document_id":
                    document_id,

                "filename":
                    file.filename,

                "source":
                    source,

                "page":
                    page,

                "chunk_id":
                    i,

                "text":
                    chunk.page_content

            }


            points.append(

                PointStruct(

                    id=str(
                        uuid.uuid4()
                    ),

                    vector=embedding,

                    payload=payload

                )

            )


        # ====================================================
        # Prepare PostgreSQL metadata
        #
        # IMPORTANT: do NOT commit the document row before Qdrant
        # succeeds. A failed Qdrant write must not leave a broken
        # "already uploaded" document behind.
        # ====================================================

        if reindex_existing:
            database_document = existing_document
            database_document.pages = len(documents)
            database_document.chunks = len(new_chunks)
        else:
            database_document = Document(
                user_id=user_id,
                document_id=document_id,
                filename=file.filename,
                pages=len(documents),
                chunks=len(new_chunks),
            )
            db.add(database_document)

        # ====================================================
        # Upload vectors
        # ====================================================

        print(

            f"Uploading {len(points)} vectors "
            f"to Qdrant..."

        )


        # Remote Qdrant instances can time out when a large PDF is sent as
        # one giant write. Upload in small batches with a long request
        # timeout so one slow batch does not fail the entire PDF.
        # Smaller batches are much safer for Qdrant Cloud / remote Qdrant.
        BATCH_SIZE = 8
        total_uploaded = 0

        for batch_start in range(0, len(points), BATCH_SIZE):
            batch = points[batch_start:batch_start + BATCH_SIZE]

            print(
                f"Uploading Qdrant batch {batch_start + 1}-"
                f"{batch_start + len(batch)} of {len(points)}..."
            )

            qdrant_client.upsert(
                collection_name=COLLECTION_NAME,
                points=batch,
                wait=True,
                timeout=180,
            )

            total_uploaded += len(batch)

        print(
            f"Vectors uploaded successfully: {total_uploaded}/{len(points)}"
        )

        # Only now is the document considered successfully indexed.
        db.commit()
        db.refresh(database_document)

        print("Document metadata committed after Qdrant indexing.")

        total_vectors = total_uploaded

        # ====================================================
        # Response
        # ====================================================

        return {

            "message":
                "PDF uploaded and indexed successfully.",

            "user_id":
                user_id,

            "filename":
                file.filename,

            "document_id":
                document_id,

            "pages":
                len(documents),

            "chunks":
                len(new_chunks),

            "total_vectors":
                total_vectors

        }


    except HTTPException:

        if os.path.exists(pdf_path):

            try:

                os.remove(
                    pdf_path
                )

            except Exception:

                pass


        raise


    except Exception as e:

        print(
            "UPLOAD ERROR:",
            str(e)
        )


        try:

            db.rollback()

        except Exception:

            pass


        # Keep the local PDF on indexing failure so a retry can re-index
        # the same file instead of losing the source document.

        # ----------------------------------------------------
        # Remove Qdrant vectors if necessary
        # ----------------------------------------------------

        try:

            qdrant_client.delete(

                collection_name=
                    COLLECTION_NAME,

                points_selector=Filter(

                    must=[

                        FieldCondition(

                            key="document_id",

                            match=MatchValue(

                                value=document_id

                            )

                        ),

                        FieldCondition(

                            key="user_id",

                            match=MatchValue(

                                value=str(user_id)

                            )

                        )

                    ]

                ),

                wait=True

            )

        except Exception:

            pass


        raise HTTPException(

            status_code=500,

            detail=
                f"Error processing PDF: {str(e)}"

        )


# ============================================================
# 12. Ask Question
# ============================================================

@app.post("/ask")
def ask_question(

    request: QuestionRequest,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )

):

    user_id = str(
        current_user.id
    )


    # --------------------------------------------------------
    # Validate question
    # --------------------------------------------------------

    if not request.question.strip():

        raise HTTPException(

            status_code=400,

            detail="Question cannot be empty."

        )


    # --------------------------------------------------------
    # Validate document if provided
    # --------------------------------------------------------

    selected_document = None


    if request.document_id:

        selected_document = (

            db.query(Document)

            .filter(

                Document.document_id ==
                    request.document_id,

                Document.user_id ==
                    current_user.id

            )

            .first()

        )


        if not selected_document:

            raise HTTPException(

                status_code=404,

                detail=
                    "Document not found or does not belong to the current user."

            )


    try:

        from langchain_core.documents import (
            Document as LangChainDocument
        )


        # ----------------------------------------------------
        # Question document
        # ----------------------------------------------------

        question_document = LangChainDocument(

            page_content=
                request.question

        )


        # ----------------------------------------------------
        # Create question embedding
        # ----------------------------------------------------

        question_embeddings = create_embeddings(

            [question_document],

            client

        )


        query_embedding = (

            question_embeddings[0]

        )


        # ----------------------------------------------------
        # Retrieve chunks
        # ----------------------------------------------------

        retrieved_chunks = (

            retrieve_from_qdrant(

                query_embedding,

                qdrant_client,

                user_id=user_id,

                document_id=request.document_id,

                k=4

            )

        )


        # ----------------------------------------------------
        # No results
        # ----------------------------------------------------

        if not retrieved_chunks:

            return {

                "question":
                    request.question,

                "user_id":
                    current_user.id,

                "document_id":
                    request.document_id,

                "answer":
                    "I could not find relevant information in the selected document.",

                "sources":
                    []

            }


        # ----------------------------------------------------
        # Generate answer
        # ----------------------------------------------------

        answer = generate_rag_answer(

            request.question,

            retrieved_chunks,

            client

        )


        # ----------------------------------------------------
        # Sources
        # ----------------------------------------------------

        sources = []

        seen_sources = set()


        for result in retrieved_chunks:

            source_key = (

                result.get("source"),

                result.get("page"),

                result.get("score")

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

                "page":
                    result.get(

                        "page",

                        0

                    ),

                "score":
                    result.get(
                        "score"
                    )

            })


        return {

            "question":
                request.question,

            "user_id":
                current_user.id,

            "document_id":
                request.document_id,

            "filename":
                (
                    selected_document.filename
                    if selected_document
                    else None
                ),

            "answer":
                answer,

            "sources":
                sources

        }


    except HTTPException:

        raise


    except Exception as e:

        import traceback


        print(
            "\n================ QUESTION ERROR ================"
        )


        print(
            "QUESTION ERROR:",
            str(e)
        )


        traceback.print_exc()


        print(
            "=================================================\n"
        )


        raise HTTPException(

            status_code=500,

            detail=
                f"Error answering question: {str(e)}"

        )