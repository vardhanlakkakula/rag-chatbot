# ============================================================
# Imports
# ============================================================

import json
import time


# ============================================================
# Configuration
# ============================================================

MODEL_NAME = "gemini-3.6-flash"


# ============================================================
# Gemini generation with automatic retry
# ============================================================

def _generate_with_retry(
    client,
    prompt,
    max_retries=4
):
    """
    Generate content using Gemini with automatic retries.

    Temporary Gemini service errors such as:

        503 UNAVAILABLE
        429 RESOURCE_EXHAUSTED

    can happen during temporary high demand.

    This function retries only temporary service errors.

    It does NOT contain any question-specific logic.
    """

    last_error = None

    for attempt in range(max_retries):

        try:

            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )

            return response

        except Exception as exc:

            last_error = exc

            error_text = str(exc).lower()

            temporary_error = any(
                marker in error_text
                for marker in (
                    "503",
                    "unavailable",
                    "service unavailable",
                    "temporarily",
                    "high demand",
                    "429",
                    "resource exhausted",
                    "too many requests"
                )
            )

            # ------------------------------------------------
            # Non-temporary error
            # ------------------------------------------------

            if not temporary_error:
                raise

            # ------------------------------------------------
            # Temporary error
            # ------------------------------------------------

            if attempt < max_retries - 1:

                wait_seconds = 2 ** (attempt + 1)

                time.sleep(
                    wait_seconds
                )

    # --------------------------------------------------------
    # All retries failed
    # --------------------------------------------------------

    raise last_error


# ============================================================
# Helper: build document context
# ============================================================

def _build_document_context(
    retrieved_chunks
):
    """
    Convert retrieved Qdrant results into a clean document
    context for Gemini.

    Metadata such as filename and page are included so the
    model can understand where information came from.
    """

    context_parts = []

    for result in retrieved_chunks or []:

        # ----------------------------------------------------
        # Qdrant dictionary
        # ----------------------------------------------------

        if isinstance(
            result,
            dict
        ):

            text = result.get(
                "text",
                ""
            )

            filename = result.get(
                "filename",
                ""
            )

            page = result.get(
                "page",
                0
            )

            score = result.get(
                "score",
                None
            )

        # ----------------------------------------------------
        # LangChain Document
        # ----------------------------------------------------

        else:

            text = getattr(
                result,
                "page_content",
                ""
            )

            metadata = getattr(
                result,
                "metadata",
                {}
            ) or {}

            filename = metadata.get(
                "filename",
                ""
            )

            page = metadata.get(
                "page",
                0
            )

            score = metadata.get(
                "score",
                None
            )

        if not text:
            continue

        text = str(
            text
        ).strip()

        if not text:
            continue

        # ----------------------------------------------------
        # Page numbering
        #
        # Backend normally stores pages starting from 0.
        # Display pages starting from 1.
        # ----------------------------------------------------

        try:

            display_page = int(
                page
            ) + 1

        except (
            TypeError,
            ValueError
        ):

            display_page = page

        # ----------------------------------------------------
        # Context block
        # ----------------------------------------------------

        source_label = (
            filename
            or
            "Document"
        )

        context_parts.append(
            f"""
SOURCE: {source_label}
PAGE: {display_page}

{text}
"""
        )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# Helper: build conversation history
# ============================================================

def _build_conversation_history(
    previous_messages
):
    """
    Convert database conversation messages into a clean
    conversation history for Gemini.
    """

    conversation_parts = []

    for message in previous_messages or []:

        # ----------------------------------------------------
        # SQLAlchemy Message object
        # ----------------------------------------------------

        role = getattr(
            message,
            "role",
            ""
        )

        content = getattr(
            message,
            "content",
            ""
        )

        # ----------------------------------------------------
        # Dictionary support
        # ----------------------------------------------------

        if isinstance(
            message,
            dict
        ):

            role = message.get(
                "role",
                ""
            )

            content = message.get(
                "content",
                ""
            )

        if not content:
            continue

        content = str(
            content
        ).strip()

        if not content:
            continue

        if role == "user":

            conversation_parts.append(
                f"USER:\n{content}"
            )

        elif role == "assistant":

            conversation_parts.append(
                f"ASSISTANT:\n{content}"
            )

    return "\n\n".join(
        conversation_parts
    )


# ============================================================
# Gemini request analysis for retrieval
# ============================================================

def analyze_user_request(
    question,
    previous_messages,
    client
):
    """
    Ask Gemini to understand the user's request before PDF
    retrieval.

    This is intentionally language-based rather than a list
    of hard-coded keywords.

    It handles:

        - spelling mistakes
        - repeated letters
        - abbreviations
        - bad grammar
        - informal wording
        - incomplete sentences
        - follow-ups
        - summaries
        - transformations
        - question generation
        - query generation

    Returns:

        {
            "needs_document": bool,
            "search_query": str
        }
    """

    history = _build_conversation_history(
        previous_messages
    )

    if not history.strip():

        history = (
            "[No previous conversation.]"
        )

    prompt = f"""
You are the request-understanding layer of a conversational
PDF assistant.

Understand the user's CURRENT request even when it contains:

- spelling mistakes
- repeated letters such as hiii or hellooo
- abbreviations such as u, ur, hw r u
- bad grammar
- incomplete sentences
- informal wording
- typing mistakes
- poor sentence formation

Use the previous conversation to resolve references such as:

- it
- this
- that
- above
- previous answer
- previous question
- previous topic
- that information
- the first one
- the second one

Your job is ONLY to decide whether the user's request needs
information from the selected PDF and, if so, create a clean
semantic search query for the PDF retriever.

============================================================
IMPORTANT
============================================================

Do NOT answer the user.

Do NOT use a hard-coded list of specific questions.

Understand the meaning of the request.

A greeting, casual conversation, or normal general-knowledge
question does NOT need the PDF.

A question explicitly or implicitly asking about the selected
PDF DOES need the PDF.

A request to summarize, explain, convert, transform, extract,
compare, simplify, rewrite, generate questions, generate
queries, or expand information from a previous PDF answer
needs the PDF when the referenced information came from
the PDF.

If the user asks for a broad overview of the PDF, create a
broad semantic search query containing concepts such as:

- document purpose
- main topics
- key concepts
- important sections
- major findings

If the user asks for a specific topic, create a focused
semantic query.

If the user asks for a transformation of information from
the previous answer, make the search query retrieve the
source information required for that transformation.

============================================================
IMPORTANT FOLLOW-UP RULE
============================================================

If the current request refers to information already present
in the previous conversation, understand the reference.

For example:

USER:
What is the primary mirror?

ASSISTANT:
The primary mirror is 6.5 meters across.

USER:
Why is it so large?

The word "it" refers to the primary mirror.

Return a search query that retrieves information needed to
answer the follow-up.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON in this exact shape:

{{
    "needs_document": true,
    "search_query": "clean semantic search query"
}}

For a casual or general request:

{{
    "needs_document": false,
    "search_query": ""
}}

============================================================
PREVIOUS CONVERSATION
============================================================

{history}

============================================================
CURRENT USER REQUEST
============================================================

{question}
"""

    response = _generate_with_retry(
        client=client,
        prompt=prompt
    )

    raw = getattr(
        response,
        "text",
        ""
    ) or ""

    raw = raw.strip()

    # --------------------------------------------------------
    # Gemini may wrap JSON in markdown fences
    # --------------------------------------------------------

    if "```" in raw:

        raw = (
            raw
            .replace(
                "```json",
                ""
            )
            .replace(
                "```",
                ""
            )
            .strip()
        )

    try:

        data = json.loads(
            raw
        )

    except Exception:

        # ----------------------------------------------------
        # If Gemini returned malformed JSON, do not crash.
        #
        # Use the original user wording as the retrieval query.
        # ----------------------------------------------------

        return {
            "needs_document": True,
            "search_query": str(
                question or ""
            ).strip()
        }

    return {
        "needs_document": bool(
            data.get(
                "needs_document",
                False
            )
        ),
        "search_query": str(
            data.get(
                "search_query",
                ""
            )
        ).strip()
    }


# ============================================================
# Basic RAG answer
# ============================================================

def generate_rag_answer(
    question,
    retrieved_chunks,
    client
):
    """
    Generate an answer using retrieved document information.

    The user's instruction controls:

        - length
        - format
        - depth
        - style
        - transformation

    The retrieved document remains the factual source.
    """

    context = _build_document_context(
        retrieved_chunks
    )

    # ========================================================
    # No context
    # ========================================================

    if not context.strip():

        return (
            "I couldn't find that information in the "
            "provided document."
        )

    # ========================================================
    # Prompt
    # ========================================================

    prompt = f"""
You are an intelligent, accurate and helpful
document-grounded AI assistant.

Your task is to answer the user's request using
the provided document information.

The USER QUESTION is the instruction you must follow.

The DOCUMENT INFORMATION is the factual source
for document-related answers.

============================================================
CORE RULE
============================================================

Use the provided document information as the primary
and authoritative source.

Do NOT invent facts.

Do NOT make unsupported claims.

Do NOT pretend that information is present in the
document when it is not.

If the document does not contain enough information
to answer the requested question, clearly say:

"I couldn't find that information in the provided document."

If only part of the requested information is available,
answer the supported part and clearly explain what
information is unavailable.

============================================================
FOLLOW THE USER'S INSTRUCTION
============================================================

Understand the user's requested task dynamically.

The user may ask for:

- a factual answer
- an explanation
- a detailed explanation
- a summary
- bullet points
- numbered points
- questions
- queries
- study questions
- information extraction
- comparison
- simplification
- notes
- an outline
- a short answer
- a detailed answer
- a specific number of items
- a specific length
- a transformation
- a rewrite

Do NOT force every request into the same answer format.

============================================================
RESPONSE LENGTH
============================================================

Respect explicit length instructions from the user.

If the user asks:

"Give me a short answer"

Keep the response concise.

If the user asks:

"Explain in detail"

Provide a substantially detailed explanation.

If the user asks for a specific approximate length,
follow that request when the document contains enough
supported information.

Do NOT artificially repeat information just to make
the answer longer.

If the document does not contain enough information,
do not invent additional facts.

============================================================
NUMBER OF ITEMS
============================================================

Respect explicit quantities.

For example:

"Give me 5 questions"

Generate 5 meaningful questions.

"Give me 10 key points"

Generate 10 useful points if enough information exists.

Do not repeat the same idea merely to reach the requested
number.

If there is not enough information, provide fewer
meaningful items rather than inventing information.

============================================================
TRANSFORMATION TASKS
============================================================

If the user asks to transform information, perform the
requested transformation.

Examples include:

- convert information into questions
- convert information into queries
- create study questions
- create small queries
- convert information into bullet points
- make notes
- simplify information
- rewrite information
- create an outline

Do not automatically summarize unless the user asks
for a summary.

============================================================
SUMMARIZATION
============================================================

If the user asks for a summary:

- identify important information
- remove unnecessary repetition
- preserve important facts
- preserve important terminology
- organize the summary clearly
- do not introduce unsupported information

============================================================
EXPLANATIONS
============================================================

If the user asks:

- explain
- why
- how
- what does this mean
- tell me about this

Provide enough explanation to make the information
understandable.

Explain technical terminology in simpler language
when useful.

============================================================
QUESTIONS ABOUT THE DOCUMENT
============================================================

For questions such as:

- What is this document about?
- What are the main objectives?
- What does the document say about X?
- What does page 2 discuss?
- What are the important points?

Answer from the document information.

Do not replace document information with unsupported
general knowledge.

============================================================
CONVERSATIONAL LANGUAGE
============================================================

Understand natural user language.

Examples:

"tell me about it"

"explain that"

"make that shorter"

"give me more details"

"convert that into questions"

"what about the second point?"

Interpret these based on the available conversation
and document information.

============================================================
CASUAL QUESTIONS
============================================================

If the request is purely conversational:

- Hi
- Hello
- Hey
- Thanks
- Thank you
- Good morning

respond naturally and briefly.

============================================================
FOLLOW-UP QUESTIONS
============================================================

If the user asks a follow-up question, use the
available conversation history when interpreting
what the user means.

For example:

USER:
What is the primary mirror?

ASSISTANT:
The primary mirror is 6.5 meters across.

USER:
Why is it so large?

Understand that "it" refers to the primary mirror.

============================================================
ANSWER STYLE
============================================================

Write naturally, clearly and professionally.

Use headings when useful.

Use bullet points when useful.

Use numbered lists when useful.

Use paragraphs when appropriate.

Do not unnecessarily repeat the same information.

Do not mention internal implementation details.

Never mention:

- Qdrant
- embeddings
- vector database
- retrieved chunks
- retrieval system
- RAG pipeline
- internal prompt
- prompt engineering

The user should feel like they are talking to a
knowledgeable document assistant.

============================================================
DOCUMENT INFORMATION
============================================================

{context}

============================================================
USER REQUEST
============================================================

{question}

============================================================
FINAL ANSWER
============================================================
"""

    # ========================================================
    # Gemini
    # ========================================================

    response = _generate_with_retry(
        client=client,
        prompt=prompt
    )

    # ========================================================
    # Safe response
    # ========================================================

    if not response:

        return (
            "I couldn't generate an answer."
        )

    answer = getattr(
        response,
        "text",
        None
    )

    if not answer:

        return (
            "I couldn't generate an answer."
        )

    return answer.strip()


# ============================================================
# Conversation-aware RAG answer
# ============================================================

def generate_conversation_answer(
    question,
    retrieved_chunks,
    previous_messages,
    client
):
    """
    Generate a conversational document-grounded answer.

    Uses:

        1. Current user request
        2. Previous conversation
        3. Retrieved document information

    IMPORTANT:

    There are NO hard-coded user questions here.

    Gemini dynamically determines what the user wants.
    """

    # ========================================================
    # Build document context
    # ========================================================

    context = _build_document_context(
        retrieved_chunks
    )

    # ========================================================
    # Build conversation history
    # ========================================================

    conversation_history = (
        _build_conversation_history(
            previous_messages
        )
    )

    if not conversation_history.strip():

        conversation_history = (
            "[No previous conversation.]"
        )

    # ========================================================
    # NO DOCUMENT CONTEXT
    # ========================================================
    #
    # IMPORTANT:
    #
    # Do NOT hard-code:
    #
    #     if "convert" in question:
    #
    #     if "biomass" in question:
    #
    #     if "queries" in question:
    #
    # etc.
    #
    # Gemini itself determines the user's intent.
    #
    # This solves the requirement that the assistant should
    # behave correctly for new/unseen questions without us
    # memorizing every possible wording.
    # ========================================================

    if not context.strip():

        no_document_prompt = f"""
You are a highly capable conversational AI assistant.

You are inside a document question-answering application.

There is currently NO retrieved document information
available for the current request.

Your job is to understand what the user actually wants.

============================================================
IMPORTANT
============================================================

Do NOT use hard-coded questions.

Do NOT use a fixed keyword list.

Do NOT assume a particular topic.

Do NOT invent document information.

Understand the meaning of the user's request dynamically.

The user may have:

- spelling mistakes
- typing mistakes
- grammar mistakes
- abbreviations
- informal wording
- incomplete sentences
- repeated letters
- conversational language
- follow-up references
- transformation requests

============================================================
AVAILABLE INFORMATION
============================================================

You have:

1. The current user request
2. Previous conversation

You do NOT currently have retrieved document information.

============================================================
DECIDE WHAT THE USER WANTS
============================================================

Determine the user's actual intent.

------------------------------------------------------------
GENERAL KNOWLEDGE
------------------------------------------------------------

If the request is a normal general-knowledge question
that does not depend on a particular uploaded document,
answer it normally.

For example, a question about a country's capital,
basic science, mathematics, common knowledge, etc. can
be answered normally when it does not depend on the
user's document.

------------------------------------------------------------
CASUAL CONVERSATION
------------------------------------------------------------

If the user is greeting you, thanking you, or having
normal conversation, respond naturally.

------------------------------------------------------------
DOCUMENT-DEPENDENT REQUEST
------------------------------------------------------------

If the user is asking for information that should come
from a particular PDF/document and that information is
not available in the current chat context, politely ask
the user to upload the relevant PDF/document.

Do NOT invent the answer.

Do NOT claim that information was missing from a
"provided document" because no usable document context
is available.

Instead, naturally explain that you need the relevant
PDF/document.

------------------------------------------------------------
TRANSFORMATION REQUEST
------------------------------------------------------------

If the user asks to transform, convert, summarize,
extract, compare, rewrite, simplify, generate questions,
generate queries, create notes, or perform another task
on information that is not currently available, understand
the requested operation and ask for the source PDF/document.

Do NOT invent the source information.

For example, if the user says they want to convert
information into queries but has not provided the
information, acknowledge that you can perform the task
and ask them to upload the relevant document.

Do not memorize a particular wording for this response.
Generate the response naturally according to the user's
actual request.

------------------------------------------------------------
FOLLOW-UP REQUEST
------------------------------------------------------------

Use previous conversation to understand references such as:

- it
- this
- that
- these
- those
- above
- previous answer
- previous question
- that information
- first one
- second one

If the previous conversation already contains enough
information to answer the request, use that conversation.

Do NOT unnecessarily ask for a PDF when the required
information is already present in the conversation.

============================================================
VERY IMPORTANT
============================================================

Never invent information from an unavailable document.

Never pretend that a document was uploaded.

Never claim that information was missing from a provided
document when there is no document context.

Never use a hard-coded list of possible user questions.

Understand the user's intent based on meaning.

============================================================
PREVIOUS CONVERSATION
============================================================

{conversation_history}

============================================================
CURRENT USER REQUEST
============================================================

{question}

============================================================
FINAL ANSWER
============================================================

Return only the answer that should be shown to the user.
"""

        response = _generate_with_retry(
            client=client,
            prompt=no_document_prompt
        )

        if not response:

            return (
                "I need the relevant PDF or document "
                "to answer that request accurately."
            )

        answer = getattr(
            response,
            "text",
            None
        )

        if not answer:

            return (
                "I need the relevant PDF or document "
                "to answer that request accurately."
            )

        return answer.strip()

    # ========================================================
    # Document context exists
    # ========================================================

    document_context = context.strip()

    # ========================================================
    # Conversation context
    # ========================================================

    conversation_context = (
        conversation_history.strip()
        if conversation_history.strip()
        else
        "[No previous conversation.]"
    )

    # ========================================================
    # Main conversational RAG prompt
    # ========================================================

    prompt = f"""
You are a highly capable conversational AI assistant
inside a document question-answering application.

Your job is to understand what the user wants and
produce the most appropriate response.

You have three possible information sources:

1. Current user request
2. Previous conversation
3. Information from the selected document

============================================================
IMPORTANT GENERAL-CHAT RULE
============================================================

If the current request is a normal/general question,
casual conversation, or a request unrelated to the
selected document, answer it normally using your general
knowledge and previous conversation when useful.

Do NOT force the selected document into a general question
merely because document information is available.

If the current request is about the selected document,
or is a follow-up whose subject was established from the
document, use the document information as the factual
source.

============================================================
MOST IMPORTANT RULE
============================================================

Understand the user's request by meaning.

Do NOT rely on a fixed list of questions.

Do NOT rely on hard-coded phrases.

The user may make:

- spelling mistakes
- grammar mistakes
- typing mistakes
- abbreviations
- informal wording
- incomplete sentences
- repeated letters
- conversational references

Understand what the user actually means.

============================================================
DOCUMENT QUESTIONS
============================================================

For questions that ask about the user's document,
use the provided document information as the factual
source.

Never invent information that is not supported by
the document.

If the requested information cannot be found in the
provided document information, say:

"I couldn't find that information in the provided document."

Do not pretend to know something from the document
when the document information does not support it.

============================================================
USER INTENT
============================================================

The user can ask for ANY reasonable task.

Determine the user's requested task dynamically.

Possible tasks include:

- question answering
- explanation
- detailed explanation
- summary
- short summary
- long answer
- study notes
- bullet points
- numbered points
- question generation
- query generation
- small query generation
- information extraction
- comparison
- simplification
- rewriting
- outlining
- specific page information
- specific topic information
- follow-up questions
- transformation
- casual conversation

These are examples only.

Do NOT restrict the assistant to this list.

Follow the user's actual request.

Do not automatically summarize everything.

Do not automatically give a short answer.

Do not automatically give a long answer.

============================================================
TRANSFORMATION
============================================================

If the user asks to transform available document
information, perform the requested transformation.

Examples include:

- converting information into queries
- creating questions
- creating study questions
- creating notes
- simplifying information
- rewriting information
- converting information into bullet points
- extracting information
- comparing information
- creating an outline

Follow exactly what the user requests.

Do not automatically summarize unless requested.

============================================================
REQUESTED LENGTH
============================================================

If the user explicitly asks for a length, follow it.

Examples:

"Give me a short answer"
→ concise.

"Explain in detail"
→ detailed.

"Give me 500 words"
→ approximately 500 useful words when enough
supported information exists.

Never add invented information simply to reach a
requested length.

============================================================
REQUESTED QUANTITY
============================================================

Respect requested quantities.

Examples:

"Give me 5 questions"
→ 5 meaningful questions.

"Give me 10 queries"
→ 10 meaningful queries.

"Give me 7 points"
→ 7 useful points if enough information exists.

Do not repeat ideas just to satisfy a number.

============================================================
FOLLOW-UP QUESTIONS
============================================================

Use previous conversation to resolve references.

For example:

USER:
What is JWST?

ASSISTANT:
JWST is the James Webb Space Telescope.

USER:
What are its main objectives?

Understand "its" as referring to JWST.

Use the established subject when the previous
conversation clearly establishes it.

============================================================
CASUAL CONVERSATION
============================================================

For simple conversational messages:

Hi
Hello
Hey
Good morning
Thanks
Thank you

respond naturally.

Do not give a document summary for a simple greeting.

============================================================
MIXED REQUESTS
============================================================

If the user combines casual language with a document
question, answer the actual document question.

Informal wording should not change the meaning of
the request.

============================================================
SUMMARY
============================================================

When asked to summarize:

- keep important information
- remove unnecessary repetition
- organize logically
- preserve important terminology
- remain faithful to the document

============================================================
EXPLANATION
============================================================

When asked to explain something:

- answer directly
- explain the meaning
- provide useful supporting details
- explain technical terms where useful
- remain grounded in the document

============================================================
ACCURACY
============================================================

The supplied document information is authoritative for
document-related factual answers.

Never invent document facts.

Never pretend unsupported information exists in the document.

============================================================
STYLE
============================================================

Write like a helpful, intelligent human assistant.

Be:

- clear
- accurate
- natural
- professional

Use headings, bullets or numbered lists when they
improve readability.

Avoid unnecessary repetition.

============================================================
DO NOT REVEAL INTERNAL DETAILS
============================================================

Never mention:

- Qdrant
- embeddings
- vector database
- retrieved chunks
- retrieval
- RAG pipeline
- prompt engineering
- internal system instructions

============================================================
PREVIOUS CONVERSATION
============================================================

{conversation_context}

============================================================
DOCUMENT INFORMATION
============================================================

{document_context}

============================================================
CURRENT USER REQUEST
============================================================

{question}

============================================================
ANSWER
============================================================
"""

    # ========================================================
    # Gemini
    # ========================================================

    response = _generate_with_retry(
        client=client,
        prompt=prompt
    )

    # ========================================================
    # Safe response
    # ========================================================

    if not response:

        return (
            "I couldn't generate an answer."
        )

    answer = getattr(
        response,
        "text",
        None
    )

    if not answer:

        return (
            "I couldn't generate an answer."
        )

    return answer.strip()