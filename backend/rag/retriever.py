import numpy as np


def retrieve_chunks(
    query,
    index,
    chunks,
    client,
    k=4
):
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=query
    )

    query_vector = np.array(
        [result.embeddings[0].values],
        dtype="float32"
    )

    distances, indices = index.search(
        query_vector,
        k
    )

    retrieved_chunks = []

    for i, distance in zip(
        indices[0],
        distances[0]
    ):
        retrieved_chunks.append({
            "chunk": chunks[i],
            "distance": float(distance)
        })

    return retrieved_chunks