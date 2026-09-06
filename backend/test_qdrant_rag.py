from dotenv import load_dotenv
from langchain_core.documents import Document

from backend.rag.embeddings import (
    create_gemini_client,
    create_embeddings
)

from backend.rag.qdrant_store import (
    create_qdrant_client
)

from backend.rag.qdrant_retriever import (
    retrieve_from_qdrant
)


load_dotenv()


print("Creating Gemini client...")

gemini_client = create_gemini_client()


print("Connecting to Qdrant...")

qdrant_client = create_qdrant_client()


question = (
    "What is the main idea of "
    "the Transformer architecture?"
)


question_document = Document(
    page_content=question
)


print("Creating question embedding...")

embeddings = create_embeddings(
    [question_document],
    gemini_client
)

query_embedding = embeddings[0]


print(
    "Embedding dimensions:",
    len(query_embedding)
)


print("Searching Qdrant...")

results = retrieve_from_qdrant(
    query_embedding,
    qdrant_client,
    user_id="default_user",
    k=4
)


print(
    "\nRetrieved:",
    len(results),
    "chunks"
)


for i, result in enumerate(
    results,
    start=1
):

    print("\n" + "=" * 60)

    print(
        "Result:",
        i
    )

    print(
        "File:",
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
        result["text"][:300]
    )