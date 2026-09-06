from backend.rag.qdrant_store import COLLECTION_NAME

try:
    from qdrant_client.models import Filter, FieldCondition, MatchValue
except Exception:
    Filter = FieldCondition = MatchValue = None


# ============================================================
# Retrieval configuration
# ============================================================

# Normal retrieval size
DEFAULT_K = 6

# Maximum chunks that can be requested for a detailed answer
MAX_K = 12

# Retrieve extra candidates first, then filter/rank them
CANDIDATE_MULTIPLIER = 2

# Minimum similarity score
#
# We use a slightly lower threshold than before because
# detailed questions sometimes have relevant chunks with
# lower individual similarity scores.
MIN_SCORE = 0.40


# ============================================================
# Helper: validate k
# ============================================================

def _validate_k(k):
    """
    Make sure k is a safe and reasonable value.
    """

    try:

        k = int(k)

    except (
        TypeError,
        ValueError
    ):

        k = DEFAULT_K


    if k <= 0:

        k = DEFAULT_K


    if k > MAX_K:

        k = MAX_K


    return k


# ============================================================
# Retrieve chunks from Qdrant
# ============================================================

def retrieve_from_qdrant(
    query_embedding,
    client,
    user_id="default_user",
    document_id=None,
    k=DEFAULT_K
):
    """
    Retrieve relevant document chunks from Qdrant.

    The retrieval is always restricted to the authenticated
    user's documents.

    If document_id is supplied, retrieval is restricted to
    that specific document.

    Parameters
    ----------
    query_embedding:
        Embedding vector generated from the user's question.

    client:
        Qdrant client.

    user_id:
        Authenticated user's ID.

    document_id:
        Optional document ID. If supplied, only chunks from
        this document are returned.

    k:
        Number of final chunks to return.

    Returns
    -------
    list[dict]

        Each result contains:

        text
        source
        filename
        document_id
        page
        chunk_id
        score
    """


    # ========================================================
    # Validate k
    # ========================================================

    k = _validate_k(k)


    # ========================================================
    # Candidate retrieval
    #
    # We retrieve more candidates than we finally return.
    #
    # Example:
    #
    # k = 6
    #
    # candidate_limit = 24
    #
    # Then we:
    #
    # Qdrant
    #   ↓
    # 24 candidates
    #   ↓
    # remove weak/empty/duplicate results
    #   ↓
    # sort by score
    #   ↓
    # return best 6
    # ========================================================

    candidate_limit = max(
        k * CANDIDATE_MULTIPLIER,
        k
    )


    # ========================================================
    # Build Qdrant filter
    # ========================================================

    must_conditions = [

        {
            "key": "user_id",

            "match": {

                "value":
                    str(user_id)

            }
        }

    ]


    # ========================================================
    # Restrict to selected document
    # ========================================================

    if document_id:

        must_conditions.append(

            {
                "key": "document_id",

                "match": {

                    "value":
                        str(document_id)

                }

            }

        )


    # ========================================================
    # Search Qdrant
    # ========================================================

    search_result = client.query_points(

        collection_name=
            COLLECTION_NAME,

        query=
            query_embedding,

        query_filter={

            "must":
                must_conditions

        },

        limit=
            candidate_limit,

        with_payload=True,

        timeout=30,

    )


    # ========================================================
    # Process results
    # ========================================================

    results = []

    seen_chunks = set()


    for point in search_result.points:

        # ----------------------------------------------------
        # Payload
        # ----------------------------------------------------

        payload = (
            point.payload or {}
        )


        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        score = point.score


        if score is None:

            continue


        try:

            score = float(score)

        except (
            TypeError,
            ValueError
        ):

            continue


        # ----------------------------------------------------
        # Remove weak results
        # ----------------------------------------------------

        if score < MIN_SCORE:

            continue


        # ----------------------------------------------------
        # Text
        # ----------------------------------------------------

        text = payload.get(
            "text",
            ""
        )


        if not isinstance(
            text,
            str
        ):

            text = str(text)


        text = text.strip()


        # ----------------------------------------------------
        # Ignore empty chunks
        # ----------------------------------------------------

        if not text:

            continue


        # ----------------------------------------------------
        # Metadata
        # ----------------------------------------------------

        source = payload.get(
            "source",
            "Unknown"
        )


        filename = payload.get(
            "filename",
            "Unknown"
        )


        stored_document_id = payload.get(
            "document_id",
            document_id or "Unknown"
        )


        page = payload.get(
            "page",
            0
        )


        chunk_id = payload.get(
            "chunk_id",
            str(point.id)
        )


        # ----------------------------------------------------
        # Normalize page
        #
        # Different ingestion pipelines sometimes store
        # page as int/string.
        # ----------------------------------------------------

        try:

            page = int(page)

        except (
            TypeError,
            ValueError
        ):

            page = 0


        # ----------------------------------------------------
        # Remove duplicate chunks
        # ----------------------------------------------------

        chunk_key = (

            str(stored_document_id),

            str(chunk_id)

        )


        if chunk_key in seen_chunks:

            continue


        seen_chunks.add(
            chunk_key
        )


        # ----------------------------------------------------
        # Store result
        # ----------------------------------------------------

        results.append(

            {

                "text":
                    text,

                "source":
                    source,

                "filename":
                    filename,

                "document_id":
                    stored_document_id,

                "page":
                    page,

                "chunk_id":
                    chunk_id,

                "score":
                    score

            }

        )


    # ========================================================
    # Sort by similarity
    # ========================================================

    results.sort(

        key=lambda item:
            item["score"],

        reverse=True

    )


    # ========================================================
    # Return best results
    # ========================================================

    return results[:k]


# ============================================================
# Detailed retrieval
# ============================================================

def retrieve_detailed_from_qdrant(
    query_embedding,
    client,
    user_id="default_user",
    document_id=None
):
    """
    Retrieve a larger context window for requests such as:

        - Explain in detail
        - Give me a long answer
        - Give me a 2-page answer
        - Explain everything about X
        - Give me comprehensive information

    This keeps the normal retrieval function simple while
    allowing the generator/router to explicitly request
    broader context.
    """

    return retrieve_from_qdrant(

        query_embedding=
            query_embedding,

        client=
            client,

        user_id=
            user_id,

        document_id=
            document_id,

        k=
            MAX_K

    )


# ============================================================
# Retrieve with custom k
# ============================================================

def retrieve_with_k(
    query_embedding,
    client,
    user_id="default_user",
    document_id=None,
    k=DEFAULT_K
):
    """
    Explicit retrieval helper.

    Useful when the caller knows how much context is required.

    Examples:

        k=4
            Short/simple question

        k=6
            Normal question

        k=8
            Detailed question

        k=12
            Long/comprehensive question
    """

    return retrieve_from_qdrant(

        query_embedding=
            query_embedding,

        client=
            client,

        user_id=
            user_id,

        document_id=
            document_id,

        k=
            k

    )

# ============================================================
# Retrieve representative chunks from one exact document
# ============================================================

def retrieve_document_fallback(
    client,
    user_id="default_user",
    document_id=None,
    max_chunks=30,
):
    """
    Return chunks from the exact selected document when semantic
    retrieval is weak. This is especially useful for transformation
    requests such as "convert the PDF into questions", where the user
    wants information spread across the document rather than one topic.
    """

    if not document_id:
        return []

    try:
        if Filter is not None:
            scroll_filter = Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=str(user_id)),
                    ),
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=str(document_id)),
                    ),
                ]
            )
        else:
            scroll_filter = {
                "must": [
                    {"key": "user_id", "match": {"value": str(user_id)}},
                    {"key": "document_id", "match": {"value": str(document_id)}},
                ]
            }

        scroll_result, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=max_chunks,
            with_payload=True,
            with_vectors=False,
            timeout=60,
        )
    except Exception as exc:
        print("QDRANT DOCUMENT FALLBACK ERROR:", exc)
        return []

    results = []

    for point in scroll_result or []:
        payload = point.payload or {}
        text = str(payload.get("text", "") or "").strip()
        if not text:
            continue

        try:
            page = int(payload.get("page", 0))
        except (TypeError, ValueError):
            page = 0

        results.append({
            "text": text,
            "source": payload.get("source", "Unknown"),
            "filename": payload.get("filename", "Unknown"),
            "document_id": payload.get("document_id", str(document_id)),
            "page": page,
            "chunk_id": payload.get("chunk_id", str(point.id)),
            "score": 1.0,
        })

    return results[:max_chunks]
