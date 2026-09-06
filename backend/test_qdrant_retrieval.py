from dotenv import load_dotenv
from langchain_core.documents import Document

from backend.rag.qdrant_store import (
    create_qdrant_client
)

from backend.rag.qdrant_retriever import (
    retrieve_from_qdrant
)

from backend.rag.embeddings import (
    create_gemini_client,
    create_embeddings
)


# ============================================================
# Load environment
# ============================================================

load_dotenv()


# ============================================================
# Create clients
# ============================================================

print("Creating Gemini client...")

gemini_client = create_gemini_client()


print("Connecting to Qdrant...")

qdrant_client = create_qdrant_client()


print("Connected successfully.")


# ============================================================
# Test question
# ============================================================

question = (
    "What is the main idea of the "
    "Transformer architecture?"
)


# ============================================================
# Convert question into a Document
# ============================================================

question_document = Document(
    page_content=question
)


# ============================================================
# Create question embedding
# ============================================================

print("\nCreating question embedding...")

question_embeddings = create_embeddings(
    [question_document],
    gemini_client
)

query_embedding = question_embeddings[0]


print(
    "Embedding dimensions:",
    len(query_embedding)
)


# ============================================================
# Search Qdrant
# ============================================================

print("\nSearching Qdrant...")

results = retrieve_from_qdrant(

    query_embedding,

    qdrant_client,

    user_id="default_user",

    k=4
)


# ============================================================
# Display results
# ============================================================

print(
    "\nNumber of results:",
    len(results)
)


for i, result in enumerate(
    results,
    start=1
):

    print("\n" + "=" * 60)

    print(
        f"Result {i}"
    )

    print(
        "Filename:",
        result["filename"]
    )

    print(
        "Page:",
        result["page"]
    )

    print(
        "Score:",
        result["score"]
    )

    print(
        "Text:",
        result["text"][:500]
    )