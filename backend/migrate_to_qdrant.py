import os

from dotenv import load_dotenv

from backend.rag.qdrant_store import (
    create_qdrant_client,
    COLLECTION_NAME
)

from backend.rag.vector_store import (
    load_vector_store
)

from qdrant_client.models import PointStruct


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# Paths
# ============================================================

VECTOR_DB_PATH = "backend/data/vector_db"


# ============================================================
# Load existing FAISS data
# ============================================================

print("Loading existing FAISS data...")

index, chunks = load_vector_store(
    VECTOR_DB_PATH
)

print(
    "Number of FAISS vectors:",
    index.ntotal
)

print(
    "Number of chunks:",
    len(chunks)
)


# ============================================================
# Create Qdrant client
# ============================================================

print("\nConnecting to Qdrant...")

client = create_qdrant_client()

print("Connected successfully.")


# ============================================================
# Prepare vectors
# ============================================================

print("\nReading vectors from FAISS...")

vectors = index.reconstruct_n(
    0,
    index.ntotal
)

print(
    "Vectors loaded:",
    len(vectors)
)


# ============================================================
# Prepare Qdrant points
# ============================================================

points = []


for i, (vector, chunk) in enumerate(
    zip(vectors, chunks)
):

    source = chunk.metadata.get(
        "source",
        "unknown"
    )

    page = chunk.metadata.get(
        "page",
        0
    )


    payload = {

        "document_id":
            os.path.basename(source),

        "filename":
            os.path.basename(source),

        "source":
            source,

        "page":
            page,

        "chunk_id":
            i,

        "text":
            chunk.page_content,

        # Temporary user ID.
        # We will replace this with
        # real authenticated user IDs later.
        "user_id":
            "default_user"
    }


    points.append(

        PointStruct(

            id=i,

            vector=vector.tolist(),

            payload=payload
        )
    )


# ============================================================
# Upload to Qdrant
# ============================================================

print(
    f"\nUploading {len(points)} vectors to Qdrant..."
)


client.upsert(

    collection_name=COLLECTION_NAME,

    points=points
)


print(
    "\nMigration completed successfully!"
)


# ============================================================
# Verify
# ============================================================

collection_info = client.get_collection(
    COLLECTION_NAME
)


print(
    "Qdrant vectors:",
    collection_info.points_count
)