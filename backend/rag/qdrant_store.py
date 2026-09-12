import os 

from qdrant_client import QdrantClient 
from qdrant_client.models import ( 
    Distance, 
    VectorParams, 
    PayloadSchemaType 
) 


COLLECTION_NAME = "rag_documents" 


def create_qdrant_client(): 

    url = os.getenv("QDRANT_URL") 
    api_key = os.getenv("QDRANT_API_KEY") 

    if not url: 
        raise ValueError( 
            "QDRANT_URL is not configured." 
        ) 

    if not api_key: 
        raise ValueError( 
            "QDRANT_API_KEY is not configured." 
        ) 

    client = QdrantClient( 
        url=url, 
        api_key=api_key 
    ) 

    return client 


def create_collection( 
    client, 
    vector_size=3072 
): 

    collections = client.get_collections() 

    existing_names = [ 
        collection.name 
        for collection in collections.collections 
    ] 

    if COLLECTION_NAME not in existing_names: 

        client.create_collection( 
            collection_name=COLLECTION_NAME, 

            vectors_config=VectorParams( 
                size=vector_size, 
                distance=Distance.COSINE 
            ) 
        ) 

        print( 
            f"Created Qdrant collection: {COLLECTION_NAME}" 
        ) 

    else: 

        print( 
            f"Qdrant collection already exists: " 
            f"{COLLECTION_NAME}" 
        ) 


    # -------------------------------------------------------- 
    # Create index for user_id 
    # -------------------------------------------------------- 

    client.create_payload_index( 
        collection_name=COLLECTION_NAME, 

        field_name="user_id", 

        field_schema=PayloadSchemaType.KEYWORD 
    ) 

    print( 
        "user_id payload index is ready." 
    ) 


    # -------------------------------------------------------- 
    # Create index for document_id 
    # Required for PDF/document RAG filtering 
    # -------------------------------------------------------- 

    client.create_payload_index( 
        collection_name=COLLECTION_NAME, 

        field_name="document_id", 

        field_schema=PayloadSchemaType.KEYWORD 
    ) 

    print( 
        "document_id payload index is ready." 
    ) 
