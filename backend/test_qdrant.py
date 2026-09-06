import os

from dotenv import load_dotenv

from qdrant_client import QdrantClient

from qdrant_client.models import (
    VectorParams,
    Distance,
    PayloadSchemaType
)


# ============================================================
# 1. Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# 2. Qdrant configuration
# ============================================================

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

COLLECTION_NAME = "rag_documents"

VECTOR_SIZE = 3072


if not QDRANT_URL:
    raise ValueError(
        "QDRANT_URL is not configured in .env"
    )


if not QDRANT_API_KEY:
    raise ValueError(
        "QDRANT_API_KEY is not configured in .env"
    )


# ============================================================
# 3. Connect to Qdrant Cloud
# ============================================================

print("Connecting to Qdrant Cloud...")


qdrant_client = QdrantClient(
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY
)


print("Connection successful!")


# ============================================================
# 4. Check collection
# ============================================================

collections = qdrant_client.get_collections()

collection_names = [
    collection.name
    for collection in collections.collections
]


if COLLECTION_NAME not in collection_names:

    print(
        f"Creating Qdrant collection: "
        f"{COLLECTION_NAME}"
    )

    qdrant_client.create_collection(

        collection_name=COLLECTION_NAME,

        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )

    print(
        "Collection created successfully!"
    )

else:

    print(
        f"Qdrant collection already exists: "
        f"{COLLECTION_NAME}"
    )


# ============================================================
# 5. Create user_id index
# ============================================================

print("Creating/checking user_id index...")


try:

    qdrant_client.create_payload_index(

        collection_name=COLLECTION_NAME,

        field_name="user_id",

        field_schema=PayloadSchemaType.KEYWORD
    )

    print(
        "user_id payload index is ready."
    )

except Exception as e:

    if "already exists" in str(e).lower():

        print(
            "user_id payload index already exists."
        )

    else:

        raise


# ============================================================
# 6. Create filename index
# ============================================================

print("Creating/checking filename index...")


try:

    qdrant_client.create_payload_index(

        collection_name=COLLECTION_NAME,

        field_name="filename",

        field_schema=PayloadSchemaType.KEYWORD
    )

    print(
        "filename payload index is ready."
    )

except Exception as e:

    if "already exists" in str(e).lower():

        print(
            "filename payload index already exists."
        )

    else:

        raise


# ============================================================
# 7. Create document_id index
# ============================================================

print(
    "Creating/checking document_id index..."
)


try:

    qdrant_client.create_payload_index(

        collection_name=COLLECTION_NAME,

        field_name="document_id",

        field_schema=PayloadSchemaType.KEYWORD
    )

    print(
        "document_id payload index is ready."
    )

except Exception as e:

    if "already exists" in str(e).lower():

        print(
            "document_id payload index already exists."
        )

    else:

        raise


# ============================================================
# 8. Verify collection
# ============================================================

print()
print(
    "Checking Qdrant collection..."
)


collection_info = (
    qdrant_client.get_collection(
        COLLECTION_NAME
    )
)


print(
    "Collection:",
    COLLECTION_NAME
)


print(
    "Vector count:",
    collection_info.points_count
)


# ============================================================
# 9. Finished
# ============================================================

print()
print(
    "=============================================="
)

print(
    "Qdrant setup completed successfully!"
)

print(
    "=============================================="
)