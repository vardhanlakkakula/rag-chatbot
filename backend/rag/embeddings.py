import os

from google import genai


def create_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured.")

    return genai.Client(api_key=api_key)


def create_embeddings(chunks, client):
    embeddings = []

    for chunk in chunks:
        result = client.models.embed_content(
            model="gemini-embedding-2",
            contents=chunk.page_content
        )

        embeddings.append(
            result.embeddings[0].values
        )

    return embeddings