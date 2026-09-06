import os

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue
)

from backend.database.connection import get_db
from backend.database.models import User, Document

from backend.auth.dependencies import get_current_user

from backend.rag.qdrant_store import (
    create_qdrant_client,
    COLLECTION_NAME
)


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/documents",
    tags=["Documents"]
)


# ============================================================
# Qdrant client
# ============================================================

qdrant_client = create_qdrant_client()


# ============================================================
# PDF storage directory
# ============================================================

PDF_DIRECTORY = "backend/data/pdfs"


# ============================================================
# GET /documents
#
# PostgreSQL is now the source of truth.
# ============================================================

@router.get("")
def list_documents(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    # --------------------------------------------------------
    # Get current user's documents from PostgreSQL
    # --------------------------------------------------------

    documents = (

        db.query(Document)

        .filter(
            Document.user_id == current_user.id
        )

        .order_by(
            Document.created_at.desc()
        )

        .all()
    )


    # --------------------------------------------------------
    # Format response
    # --------------------------------------------------------

    result = []


    for document in documents:

        result.append({

            "document_id":
                document.document_id,

            "filename":
                document.filename,

            "user_id":
                str(document.user_id),

            "pages":
                document.pages,

            "chunks":
                document.chunks,

            "created_at":
                document.created_at
        })


    # --------------------------------------------------------
    # Return response
    # --------------------------------------------------------

    return {

        "user_id":
            current_user.id,

        "documents":
            result
    }


# ============================================================
# DELETE /documents/{document_id}
#
# PostgreSQL:
#   1. Find document
#   2. Verify ownership
#   3. Delete metadata
#
# Qdrant:
#   Delete all vectors belonging to document
#
# Storage:
#   Delete local PDF
# ============================================================

@router.delete("/{document_id}")
def delete_document(

    document_id: str,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    # --------------------------------------------------------
    # Find document in PostgreSQL
    # --------------------------------------------------------

    document = (

        db.query(Document)

        .filter(
            Document.document_id == document_id
        )

        .first()
    )


    # --------------------------------------------------------
    # Document doesn't exist
    # --------------------------------------------------------

    if not document:

        raise HTTPException(

            status_code=404,

            detail="Document not found."
        )


    # --------------------------------------------------------
    # SECURITY CHECK
    #
    # Make sure the document belongs to the
    # currently authenticated user.
    # --------------------------------------------------------

    if document.user_id != current_user.id:

        raise HTTPException(

            status_code=403,

            detail=
                "You do not have permission to delete this document."
        )


    # --------------------------------------------------------
    # Store information before deletion
    # --------------------------------------------------------

    filename = document.filename

    stored_document_id = document.document_id

    user_id = str(
        current_user.id
    )


    # --------------------------------------------------------
    # Delete vectors from Qdrant
    #
    # We use BOTH:
    #
    # user_id
    # document_id
    #
    # so another user's vectors cannot be touched.
    # --------------------------------------------------------

    try:

        qdrant_client.delete(

            collection_name=
                COLLECTION_NAME,

            points_selector=Filter(

                must=[

                    FieldCondition(

                        key="user_id",

                        match=MatchValue(

                            value=user_id
                        )
                    ),

                    FieldCondition(

                        key="document_id",

                        match=MatchValue(

                            value=stored_document_id
                        )
                    )
                ]
            ),

            wait=True
        )

        print(
            f"Deleted Qdrant vectors for "
            f"document {stored_document_id}"
        )


    except Exception as e:

        print(
            "Qdrant deletion error:",
            str(e)
        )


        raise HTTPException(

            status_code=500,

            detail=
                "Failed to delete document vectors from Qdrant."
        )


    # --------------------------------------------------------
    # Delete document from PostgreSQL
    # --------------------------------------------------------

    try:

        db.delete(
            document
        )

        db.commit()

        print(
            f"Deleted document {stored_document_id} "
            f"from PostgreSQL"
        )


    except Exception as e:

        db.rollback()

        print(
            "PostgreSQL deletion error:",
            str(e)
        )


        raise HTTPException(

            status_code=500,

            detail=
                "Failed to delete document metadata."
        )


    # --------------------------------------------------------
    # Delete local PDF
    # --------------------------------------------------------

    local_filename = (
        f"user_{user_id}_{filename}"
    )


    pdf_path = os.path.join(

        PDF_DIRECTORY,

        local_filename
    )


    pdf_deleted = False


    if os.path.exists(pdf_path):

        try:

            os.remove(
                pdf_path
            )

            pdf_deleted = True

            print(
                f"Deleted local PDF: "
                f"{pdf_path}"
            )

        except Exception as e:

            print(
                "PDF deletion error:",
                str(e)
            )


    # --------------------------------------------------------
    # Return success
    # --------------------------------------------------------

    return {

        "message":
            "Document deleted successfully.",

        "document_id":
            stored_document_id,

        "filename":
            filename,

        "user_id":
            current_user.id,

        "chunks":
            document.chunks,

        "pdf_deleted":
            pdf_deleted
    }