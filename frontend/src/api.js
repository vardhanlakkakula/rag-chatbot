// ============================================================
// RAG ASSISTANT FRONTEND API
// ============================================================

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";


// ============================================================
// COMMON REQUEST FUNCTION
// ============================================================

async function request(
  path,
  {
    method = "GET",
    token = null,
    body = undefined,
    formData = false,
  } = {}
) {

  const headers = {};


  // ==========================================================
  // JWT AUTHENTICATION
  // ==========================================================

  if (token) {

    headers.Authorization =
      `Bearer ${token}`;

  }


  // ==========================================================
  // JSON REQUEST
  // ==========================================================

  if (
    !formData &&
    body !== undefined
  ) {

    headers["Content-Type"] =
      "application/json";

  }


  // ==========================================================
  // SEND REQUEST
  // ==========================================================

  let response;

  try {

    response =
      await fetch(
        `${API_BASE_URL}${path}`,
        {
          method,
          headers,

          body:
            body === undefined
              ? undefined
              : formData
                ? body
                : JSON.stringify(body),
        }
      );

  } catch (error) {

    const networkError =
      new Error(
        `Cannot connect to backend at ${API_BASE_URL}. ` +
        `Make sure FastAPI is running.`
      );

    networkError.originalError =
      error;

    throw networkError;

  }


  // ==========================================================
  // READ RESPONSE
  // ==========================================================

  let data = null;

  const contentType =
    response.headers.get(
      "content-type"
    ) || "";


  if (
    contentType.includes(
      "application/json"
    )
  ) {

    try {

      data =
        await response.json();

    } catch {

      data = null;

    }

  } else {

    const text =
      await response.text();

    data =
      text || null;

  }


  // ==========================================================
  // BACKEND ERROR
  // ==========================================================

  if (!response.ok) {

    let errorMessage =
      `Request failed with status ${response.status}`;


    if (
      data &&
      typeof data === "object"
    ) {

      errorMessage =
        data.detail ||
        data.message ||
        errorMessage;

    }

    else if (
      typeof data === "string" &&
      data.trim()
    ) {

      errorMessage =
        data;

    }


    const error =
      new Error(
        errorMessage
      );


    error.response = {

      status:
        response.status,

      data,

    };


    throw error;

  }


  return data;

}


// ============================================================
// AUTHENTICATION
// ============================================================


// ------------------------------------------------------------
// REGISTER USER
// ------------------------------------------------------------

export async function registerUser(
  email,
  password
) {

  return request(
    "/auth/register",
    {

      method: "POST",

      body: {

        email:
          email.trim(),

        password,

      },

    }
  );

}


// ------------------------------------------------------------
// LOGIN USER
// ------------------------------------------------------------

export async function loginUser(
  email,
  password
) {

  return request(
    "/auth/login",
    {

      method: "POST",

      body: {

        email:
          email.trim(),

        password,

      },

    }
  );

}


// ------------------------------------------------------------
// CURRENT USER
// ------------------------------------------------------------

export async function getCurrentUser(
  token
) {

  return request(
    "/auth/me",
    {

      method: "GET",

      token,

    }
  );

}


// ============================================================
// DOCUMENTS
// ============================================================


// ------------------------------------------------------------
// GET DOCUMENTS
// ------------------------------------------------------------

export async function getDocuments(
  token
) {

  return request(
    "/documents",
    {

      method: "GET",

      token,

    }
  );

}


// ------------------------------------------------------------
// UPLOAD PDF
// ------------------------------------------------------------

export async function uploadPDF(
  file,
  token
) {

  const form =
    new FormData();


  form.append(
    "file",
    file
  );


  return request(
    "/upload_pdf",
    {

      method: "POST",

      token,

      body:
        form,

      formData:
        true,

    }
  );

}


// ------------------------------------------------------------
// DELETE DOCUMENT
// ------------------------------------------------------------

export async function deleteDocument(
  documentId,
  token
) {

  return request(
    `/documents/${encodeURIComponent(
      documentId
    )}`,
    {

      method: "DELETE",

      token,

    }
  );

}


// ============================================================
// LEGACY ASK ENDPOINT
// ============================================================

export async function askQuestion(
  question,
  documentId,
  token
) {

  return request(
    "/ask",
    {

      method: "POST",

      token,

      body: {

        question,

        document_id:
          documentId,

      },

    }
  );

}


// ============================================================
// CHAT HEALTH
// ============================================================

export async function getChatHealth() {

  return request(
    "/chat/health",
    {

      method: "GET",

    }
  );

}


// ============================================================
// CONVERSATIONS
// ============================================================


// ------------------------------------------------------------
// GET CONVERSATIONS
// ------------------------------------------------------------

export async function getConversations(
  token
) {

  return request(
    "/chat/conversations",
    {

      method: "GET",

      token,

    }
  );

}


// ------------------------------------------------------------
// CREATE CONVERSATION
// ------------------------------------------------------------

export async function createConversation(
  title = "New Conversation",
  documentId = null,
  token
) {

  return request(
    "/chat/conversations",
    {

      method: "POST",

      token,

      body: {

        title:
          title?.trim() ||
          "New Conversation",

        document_id:
          documentId || null,

      },

    }
  );

}


// ------------------------------------------------------------
// GET CONVERSATION
// ------------------------------------------------------------

export async function getConversation(
  conversationId,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}`,
    {

      method: "GET",

      token,

    }
  );

}


// ------------------------------------------------------------
// UPDATE CONVERSATION
// ------------------------------------------------------------

export async function updateConversation(
  conversationId,
  title,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}`,
    {

      method: "PATCH",

      token,

      body: {

        title:
          title?.trim() ||
          "New Conversation",

      },

    }
  );

}


// ------------------------------------------------------------
// DELETE CONVERSATION
// ------------------------------------------------------------

export async function deleteConversation(
  conversationId,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}`,
    {

      method: "DELETE",

      token,

    }
  );

}


// ============================================================
// CONVERSATION MESSAGES
// ============================================================


// ------------------------------------------------------------
// ADD CONVERSATION MESSAGE
// ------------------------------------------------------------

export async function addConversationMessage(
  conversationId,
  role,
  content,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}/messages`,
    {

      method: "POST",

      token,

      body: {

        role,

        content,

      },

    }
  );

}


// ------------------------------------------------------------
// DELETE CONVERSATION MESSAGE
// ------------------------------------------------------------

export async function deleteConversationMessage(
  conversationId,
  messageId,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}/messages/${encodeURIComponent(
      messageId
    )}`,
    {

      method: "DELETE",

      token,

    }
  );

}


// ============================================================
// OLD CONVERSATION ASK
// ============================================================

export async function askConversation(
  conversationId,
  question,
  documentId = null,
  token
) {

  return request(
    `/chat/conversations/${encodeURIComponent(
      conversationId
    )}/ask`,
    {

      method: "POST",

      token,

      body: {

        question,

        document_id:
          documentId || null,

      },

    }
  );

}


// ============================================================
// NEW CONVERSATIONAL CHAT
// ============================================================
//
// POST /chat/message
//
// Used by App.jsx for:
//
// - Hi
// - Hello
// - Thanks
// - Normal document questions
// - Follow-up questions
// - Summaries
// - Detailed answers
// - Question generation
// - Query generation
//
// document_id is optional.
// conversation_id is optional.
//
// ============================================================

export async function sendChatMessage(
  question,
  conversationId = null,
  documentId = null,
  token,
  imageFile = null
) {

  // Use multipart/form-data when an image is attached.
  // Keep the existing JSON request unchanged for normal chat.
  if (imageFile) {

    const form =
      new FormData();

    form.append(
      "question",
      question?.trim() || ""
    );

    if (conversationId) {
      form.append(
        "conversation_id",
        conversationId
      );
    }

    if (documentId) {
      form.append(
        "document_id",
        documentId
      );
    }

    form.append(
      "image",
      imageFile
    );

    return request(
      "/chat/message",
      {
        method: "POST",
        token,
        body: form,
        formData: true,
      }
    );
  }

  return request(
    "/chat/message",
    {

      method: "POST",

      token,

      body: {

        question:
          question?.trim() || "",

        conversation_id:
          conversationId || null,

        document_id:
          documentId || null,

      },

    }
  );

}