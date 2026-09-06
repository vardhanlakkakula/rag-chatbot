import os
import pickle

import faiss
import numpy as np


def create_vector_store(embeddings):
    embedding_matrix = np.array(
        embeddings,
        dtype="float32"
    )

    dimension = embedding_matrix.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embedding_matrix)

    return index


def save_vector_store(index, chunks, folder_path):
    os.makedirs(folder_path, exist_ok=True)

    index_path = os.path.join(
        folder_path,
        "index.faiss"
    )

    chunks_path = os.path.join(
        folder_path,
        "chunks.pkl"
    )

    faiss.write_index(index, index_path)

    with open(chunks_path, "wb") as file:
        pickle.dump(chunks, file)


def load_vector_store(folder_path):
    index_path = os.path.join(
        folder_path,
        "index.faiss"
    )

    chunks_path = os.path.join(
        folder_path,
        "chunks.pkl"
    )

    index = faiss.read_index(index_path)

    with open(chunks_path, "rb") as file:
        chunks = pickle.load(file)

    return index, chunks
def add_embeddings_to_index(index, embeddings):
    import numpy as np

    embedding_matrix = np.array(
        embeddings,
        dtype="float32"
    )

    index.add(embedding_matrix)

    return index