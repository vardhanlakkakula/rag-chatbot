import os

from dotenv import load_dotenv

from backend.rag.loader import load_pdf
from backend.rag.chunker import chunk_documents
from backend.rag.embeddings import (
    create_gemini_client,
    create_embeddings
)
from backend.rag.vector_store import (
    create_vector_store,
    save_vector_store
)


# Load .env
load_dotenv()


# Paths
PDF_PATH = "backend/data/pdfs/attention.pdf"

VECTOR_DB_PATH = "backend/data/vector_db"


print("Loading PDF...")

documents = load_pdf(PDF_PATH)

print("Number of pages:", len(documents))


print("\nChunking document...")

chunks = chunk_documents(documents)

print("Number of chunks:", len(chunks))


print("\nCreating Gemini client...")

client = create_gemini_client()


print("\nCreating embeddings...")

embeddings = create_embeddings(
    chunks,
    client
)

print("Number of embeddings:", len(embeddings))
print("Embedding dimensions:", len(embeddings[0]))


print("\nCreating FAISS index...")

index = create_vector_store(
    embeddings
)

print("Number of vectors:", index.ntotal)


print("\nSaving vector database...")

save_vector_store(
    index,
    chunks,
    VECTOR_DB_PATH
)

print("\nVector database saved successfully!")
print("Location:", VECTOR_DB_PATH)