import {
  useEffect,
  useRef,
  useState
} from "react";

import "./App.css";

import {
  loginUser,
  registerUser,
  getCurrentUser,
  getDocuments,
  uploadPDF,
  deleteDocument,

  getConversations,
  createConversation,
  getConversation,
  updateConversation,
  deleteConversation,
  askConversation,
  sendChatMessage
} from "./api";


// ============================================================
// DOCUMENT ID HELPERS
// ============================================================

function getDocumentId(document) {
  if (!document) {
    return null;
  }

  const id =
    document.document_id ??
    document.documentId ??
    document.id ??
    document.document?.document_id ??
    document.document?.documentId ??
    document.document?.id ??
    null;

  return id !== null && id !== undefined && String(id).trim()
    ? String(id)
    : null;
}


function normalizeDocument(document) {
  if (!document) {
    return null;
  }

  const documentId =
    getDocumentId(document);

  if (!documentId) {
    return {
      ...document,
      document_id: null
    };
  }

  return {
    ...document,
    document_id: documentId
  };
}


function getDocumentFromResponse(data) {
  if (!data) {
    return null;
  }

  const rawDocument =
    data.document ||
    data.document_data ||
    data;

  return normalizeDocument({
    ...rawDocument,
    document_id:
      data.document_id ??
      data.documentId ??
      data.id ??
      rawDocument?.document_id ??
      rawDocument?.documentId ??
      rawDocument?.id
  });
}

// ============================================================
// ASSISTANT ANSWER FORMATTING
// Dependency-free Markdown-style renderer.
// ============================================================

function renderInlineMarkdown(text, keyPrefix = "inline") {
  const parts = String(text ?? "").split(
    /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g
  );

  return parts.map((part, index) => {
    if (!part) return null;

    const key = `${keyPrefix}-${index}`;

    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }

    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={key}>{part.slice(1, -1)}</code>;
    }

    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }

    return <span key={key}>{part}</span>;
  });
}

function renderAssistantAnswer(answer) {
  const lines = String(answer ?? "")
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .split("\n");

  const blocks = [];
  let paragraph = [];
  let i = 0;

  const flushParagraph = () => {
    if (!paragraph.length) return;

    const content = paragraph.join(" ").replace(/\s+/g, " ").trim();

    if (content) {
      blocks.push(
        <p key={`paragraph-${i}`}>
          {renderInlineMarkdown(content, `paragraph-${i}`)}
        </p>
      );
    }

    paragraph = [];
  };

  while (i < lines.length) {
    const line = lines[i].trim();

    if (!line) {
      flushParagraph();
      i += 1;
      continue;
    }

    if (line.startsWith("```")) {
      flushParagraph();
      const code = [];
      i += 1;

      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        code.push(lines[i]);
        i += 1;
      }

      if (i < lines.length) i += 1;

      blocks.push(
        <pre key={`code-${i}`}>
          <code>{code.join("\n")}</code>
        </pre>
      );
      continue;
    }

    const heading = line.match(/^#{1,3}\s+(.+)$/);

    if (heading) {
      flushParagraph();

      const level = line.match(/^#+/)[0].length;
      const Tag = level === 1 ? "h3" : level === 2 ? "h4" : "h5";

      blocks.push(
        <Tag key={`heading-${i}`}>
          {renderInlineMarkdown(heading[1], `heading-${i}`)}
        </Tag>
      );

      i += 1;
      continue;
    }

    if (/^[-*•]\s+/.test(line)) {
      flushParagraph();
      const items = [];

      while (i < lines.length) {
        const match = lines[i].trim().match(/^[-*•]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        i += 1;
      }

      blocks.push(
        <ul key={`unordered-${i}`}>
          {items.map((item, itemIndex) => (
            <li key={`unordered-${i}-${itemIndex}`}>
              {renderInlineMarkdown(item, `unordered-${i}-${itemIndex}`)}
            </li>
          ))}
        </ul>
      );
      continue;
    }

    if (/^\d+[.)]\s+/.test(line)) {
      flushParagraph();
      const items = [];

      while (i < lines.length) {
        const match = lines[i].trim().match(/^\d+[.)]\s+(.+)$/);
        if (!match) break;
        items.push(match[1]);
        i += 1;
      }

      blocks.push(
        <ol key={`ordered-${i}`}>
          {items.map((item, itemIndex) => (
            <li key={`ordered-${i}-${itemIndex}`}>
              {renderInlineMarkdown(item, `ordered-${i}-${itemIndex}`)}
            </li>
          ))}
        </ol>
      );
      continue;
    }

    if (line.startsWith("> ")) {
      flushParagraph();
      const quote = [];

      while (i < lines.length && lines[i].trim().startsWith("> ")) {
        quote.push(lines[i].trim().replace(/^>\s?/, ""));
        i += 1;
      }

      blocks.push(
        <blockquote key={`quote-${i}`}>
          {renderInlineMarkdown(quote.join(" "), `quote-${i}`)}
        </blockquote>
      );
      continue;
    }

    paragraph.push(line);
    i += 1;
  }

  flushParagraph();

  return blocks.length ? blocks : <p />;
}

// ============================================================
// APP
// ============================================================

function App() {

  // ==========================================================
  // AUTH
  // ==========================================================

  const [token, setToken] = useState(
    localStorage.getItem("access_token")
  );

  const [userId, setUserId] = useState(
    localStorage.getItem("user_id")
  );

  const [userEmail, setUserEmail] =
    useState("");


  // ==========================================================
  // AUTH FORM
  // ==========================================================

  const [authMode, setAuthMode] =
    useState("login");

  const [email, setEmail] =
    useState("");

  const [password, setPassword] =
    useState("");

  const [confirmPassword, setConfirmPassword] =
    useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [authLoading, setAuthLoading] =
    useState(false);

  const [authError, setAuthError] =
    useState("");

  const [authMessage, setAuthMessage] =
    useState("");


  // ==========================================================
  // DOCUMENTS
  // ==========================================================

  const [documents, setDocuments] =
    useState([]);

  const [selectedDocument, setSelectedDocument] =
    useState(null);

  const [loadingDocuments, setLoadingDocuments] =
    useState(false);

  const [uploading, setUploading] =
    useState(false);

  const [uploadProgressText, setUploadProgressText] =
    useState("");


  // ==========================================================
  // CONVERSATIONS
  // ==========================================================

  const [conversations, setConversations] =
    useState([]);

  // UI-only pinned chats. Stored per logged-in user.
  const [pinnedConversationIds, setPinnedConversationIds] =
    useState(() => {
      try {
        const savedUserId = localStorage.getItem("user_id");
        const saved = savedUserId
          ? localStorage.getItem(`pinned_conversations_${savedUserId}`)
          : null;

        const parsed = saved ? JSON.parse(saved) : [];
        return Array.isArray(parsed) ? parsed.map(String) : [];
      } catch {
        return [];
      }
    });

  const [selectedConversationId, setSelectedConversationId] =
    useState(null);

  const [conversationTitle, setConversationTitle] =
    useState("New Chat");

  const [loadingConversations, setLoadingConversations] =
    useState(false);

  const [loadingConversation, setLoadingConversation] =
    useState(false);

  const [renamingConversation, setRenamingConversation] =
    useState(false);


  // ==========================================================
  // CHAT
  // ==========================================================

  const [question, setQuestion] =
    useState("");

  const [messages, setMessages] =
    useState([]);

  const [asking, setAsking] =
    useState(false);

  const chatQueueRef = useRef([]);
  const processingChatQueueRef = useRef(false);
  const conversationIdRef = useRef(selectedConversationId);
  const conversationCreationPromiseRef = useRef(null);
  const conversationQueuesRef = useRef(new Map());

  // Keep each conversation's document association separate.
  const conversationDocumentIdsRef = useRef(new Map());
  // Prevent responses from an old chat from changing the newly opened chat.
  const chatGenerationRef = useRef(0);

  const [chatError, setChatError] =
    useState("");

  const [sidebarOpen, setSidebarOpen] =
    useState(true);

  const [accountMenuOpen, setAccountMenuOpen] =
    useState(false);


  // ==========================================================
  // ATTACHMENTS
  // ==========================================================

  const [attachedFiles, setAttachedFiles] =
    useState([]);

  const [attachmentMenuOpen, setAttachmentMenuOpen] =
    useState(false);


  // ==========================================================
  // REFS
  // ==========================================================

  const pdfInputRef =
    useRef(null);

  const attachmentInputRef =
    useRef(null);

  const chatEndRef =
    useRef(null);

  const messagesContainerRef =
    useRef(null);


  // Close attachment popup when clicking anywhere outside it.
  useEffect(() => {
    if (!attachmentMenuOpen) {
      return;
    }

    const handleAttachmentOutsideClick = (event) => {
      if (!event.target?.closest?.(".plus-wrapper")) {
        setAttachmentMenuOpen(false);
      }
    };

    document.addEventListener(
      "mousedown",
      handleAttachmentOutsideClick
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleAttachmentOutsideClick
      );
    };
  }, [attachmentMenuOpen]);


  useEffect(() => {
    conversationIdRef.current = selectedConversationId;
  }, [selectedConversationId]);

  const rememberConversationDocument = (conversationId, documentId) => {
    if (!conversationId) return;

    const key = String(conversationId);

    if (documentId) {
      conversationDocumentIdsRef.current.set(key, String(documentId));
    } else {
      conversationDocumentIdsRef.current.delete(key);
    }

    if (!userId) return;

    try {
      const storageKey = `conversation_documents_${userId}`;
      const saved = localStorage.getItem(storageKey);
      const stored = saved ? JSON.parse(saved) : {};
      const next =
        stored && typeof stored === "object" && !Array.isArray(stored)
          ? stored
          : {};

      if (documentId) {
        next[key] = String(documentId);
      } else {
        delete next[key];
      }

      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch {
      // Ignore localStorage errors.
    }
  };

  const getRememberedConversationDocumentId = (conversationId) => {
    if (!conversationId) return null;

    const key = String(conversationId);
    const inMemory = conversationDocumentIdsRef.current.get(key);
    if (inMemory) return String(inMemory);

    if (!userId) return null;

    try {
      const saved = localStorage.getItem(`conversation_documents_${userId}`);
      const stored = saved ? JSON.parse(saved) : {};
      const documentId = stored?.[key];

      if (documentId) {
        conversationDocumentIdsRef.current.set(key, String(documentId));
        return String(documentId);
      }
    } catch {
      // Ignore localStorage errors.
    }

    return null;
  };


  // ==========================================================
  // LOGOUT
  // ==========================================================

  const switchAccount = () => {
    setAccountMenuOpen(false);
    setAuthMode("login");
    setAuthError("");
    setAuthMessage("");
    logout();
  };

  const logout = () => {

    setAccountMenuOpen(false);

    localStorage.removeItem(
      "access_token"
    );

    localStorage.removeItem(
      "user_id"
    );

    setToken(null);
    setUserId(null);
    setUserEmail("");

    setDocuments([]);
    setSelectedDocument(null);

    try {
      localStorage.removeItem(
        "selected_document"
      );
    } catch {
      // Ignore localStorage errors.
    }

    chatQueueRef.current = [];
    conversationIdRef.current = null;
    conversationDocumentIdsRef.current = new Map();
    chatGenerationRef.current += 1;

    setConversations([]);

    setPinnedConversationIds([]);

    setSelectedConversationId(null);
    setConversationTitle("New Chat");

    setMessages([]);
    setQuestion("");

    setAttachedFiles([]);

    setChatError("");

  };


  // ==========================================================
  // CURRENT USER
  // ==========================================================

  useEffect(() => {

    if (!token) {
      return;
    }


    const loadCurrentUser =
      async () => {

        try {

          const data =
            await getCurrentUser(token);


          setUserId(
            data.user_id
          );


          setUserEmail(
            data.email
          );

        } catch (error) {

          console.error(
            "AUTH ERROR:",
            error
          );

          logout();

        }

      };


    loadCurrentUser();

  }, [token]);


  // ==========================================================
  // LOAD DOCUMENTS
  // ==========================================================

  const loadDocuments =
    async () => {

      if (!token) {
        return;
      }


      try {

        setLoadingDocuments(true);


        const data =
          await getDocuments(token);


        const loadedDocuments =
          (data.documents || [])
            .map(normalizeDocument)
            .filter(document =>
              Boolean(
                getDocumentId(document)
              )
            );


        setDocuments(
          loadedDocuments
        );


        // Documents are loaded for the document list only.
        // The active document belongs to the current chat and
        // is never restored from global localStorage.

      } catch (error) {

        console.error(
          "DOCUMENT ERROR:",
          error
        );


        if (
          error.response?.status === 401
        ) {

          logout();

        }

      } finally {

        setLoadingDocuments(false);

      }

    };


  // ==========================================================
  // LOAD CONVERSATIONS
  // ==========================================================

  const loadConversations =
    async () => {

      if (!token) {
        return;
      }


      try {

        setLoadingConversations(true);


        const data =
          await getConversations(token);


        const loadedConversations = data.conversations || [];

        setConversations(loadedConversations);

        loadedConversations.forEach(conversation => {
          const conversationId = conversation?.conversation_id;
          const documentId =
            conversation?.document_id ??
            conversation?.documentId ??
            conversation?.document?.document_id ??
            conversation?.document?.documentId ??
            conversation?.document?.id ??
            null;

          if (conversationId && documentId) {
            rememberConversationDocument(conversationId, documentId);
          }
        });

      } catch (error) {

        console.error(
          "CONVERSATION LIST ERROR:",
          error
        );


        if (
          error.response?.status === 401
        ) {

          logout();

        }

      } finally {

        setLoadingConversations(false);

      }

    };


  // ==========================================================
  // LOAD DOCUMENTS + CONVERSATIONS AFTER LOGIN
  // ==========================================================

  useEffect(() => {

    if (!token) {
      return;
    }


    loadDocuments();

    loadConversations();

  }, [token]);


  // ==========================================================
  // AUTO SCROLL
  // ==========================================================

  useEffect(() => {

    const container =
      messagesContainerRef.current;

    if (!container) {
      return;
    }

    const frame =
      requestAnimationFrame(() => {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: "auto"
        });
      });

    return () =>
      cancelAnimationFrame(frame);

  }, [
    messages,
    asking
  ]);


  // ==========================================================
  // AUTH
  // ==========================================================

  const handleAuth =
    async (event) => {

      event.preventDefault();

      setAuthError("");
      setAuthMessage("");


      if (!email.trim()) {

        setAuthError(
          "Please enter your email."
        );

        return;

      }


      if (!password) {

        setAuthError(
          "Please enter your password."
        );

        return;

      }


      if (
        authMode === "register" &&
        password !== confirmPassword
      ) {

        setAuthError(
          "Passwords do not match."
        );

        return;

      }


      try {

        setAuthLoading(true);


        if (
          authMode === "register"
        ) {

          await registerUser(
            email,
            password
          );


          setAuthMessage(
            "Registration successful. You can now log in."
          );


          setAuthMode("login");

          setConfirmPassword("");


        } else {

          const data =
            await loginUser(
              email,
              password
            );


          localStorage.setItem(
            "access_token",
            data.access_token
          );


          localStorage.setItem(
            "user_id",
            data.user_id
          );


          setToken(
            data.access_token
          );


          setUserId(
            data.user_id
          );


          setUserEmail(
            email.trim()
          );

        }

      } catch (error) {

        console.error(
          "AUTH ERROR:",
          error
        );


        setAuthError(
          error.response?.data?.detail ||
          "Unable to connect to the backend."
        );

      } finally {

        setAuthLoading(false);

      }

    };


  // ==========================================================
  // RESET CHAT STATE
  // ==========================================================

  const clearChat =
    () => {

      setMessages([]);

      setQuestion("");

      setChatError("");

      setAttachedFiles([]);

      setAttachmentMenuOpen(false);

    };


  // ==========================================================
  // NEW CHAT
  // ==========================================================

  const handleNewChat =
    () => {

      chatGenerationRef.current += 1;
      chatQueueRef.current = [];
      conversationIdRef.current = null;
      conversationCreationPromiseRef.current = null;

      setSelectedConversationId(
        null
      );

      setSelectedDocument(null);

      try {
        localStorage.removeItem(
          "selected_document"
        );
      } catch {
        // Ignore localStorage errors.
      }

      setConversationTitle(
        "New Chat"
      );

      setMessages([]);

      setQuestion("");

      setChatError("");

      setAttachedFiles([]);

      setAttachmentMenuOpen(false);

    };


  // ==========================================================
  // SELECT DOCUMENT
  // ==========================================================

  const handleSelectDocument =
    (document) => {

      const normalizedDocument =
        normalizeDocument(document);

      const documentId =
        getDocumentId(
          normalizedDocument
        );


      if (!documentId) {

        console.error(
          "SELECT DOCUMENT ERROR: no document ID found.",
          document
        );

        return;
      }


      console.log(
        "SELECTED DOCUMENT ID:",
        documentId
      );

      chatGenerationRef.current += 1;
      chatQueueRef.current = [];
      conversationCreationPromiseRef.current = null;
      conversationIdRef.current = null;

      setSelectedDocument(
        normalizedDocument
      );


      // The selected document belongs to this chat only.
      // Do not persist it globally in localStorage.


      // Start a new conversation
      // when changing the document.

      setSelectedConversationId(
        null
      );


      setConversationTitle(
        "New Chat"
      );


      clearChat();

    };


  // ==========================================================
  // CREATE CONVERSATION
  // ==========================================================

  const createNewConversation =
    async () => {

      if (!token) {
        throw new Error(
          "You are not logged in."
        );
      }


      const firstTitle =
        question.trim()
          ? question.trim().slice(0, 60)
          : "New Conversation";


      const documentId = getDocumentId(selectedDocument) || null;

      const data =
        await createConversation(
          firstTitle,
          documentId,
          token
        );


      rememberConversationDocument(
        data.conversation_id,
        data.document_id ?? documentId
      );


      const newConversation = {
        conversation_id:
          data.conversation_id,

        title:
          data.title,

        document_id:
          data.document_id,

        created_at:
          data.created_at,

        updated_at:
          data.updated_at,

        last_message:
          null,

        last_message_role:
          null
      };


      setSelectedConversationId(
        data.conversation_id
      );


      setConversationTitle(
        data.title
      );


      setConversations(
        previous => [
          newConversation,
          ...previous
        ]
      );


      return data;

    };


  // ==========================================================
  // CONVERT DATABASE MESSAGES
  // TO FRONTEND MESSAGE PAIRS
  // ==========================================================

  const convertConversationMessages =
    (databaseMessages) => {

      const result = [];

      let currentUserMessage =
        null;


      for (
        const message
        of databaseMessages || []
      ) {

        if (
          message.role === "user"
        ) {

          currentUserMessage = {
            id:
              `user-${message.id}`,

            userMessageId:
              message.id,

            question:
              message.content,

            answer:
              "",

            assistantMessageId:
              null,

            sources:
              [],

            attachments:
              []
          };


          result.push(
            currentUserMessage
          );

        }


        else if (
          message.role === "assistant"
        ) {

          if (
            currentUserMessage
          ) {

            currentUserMessage.answer =
              message.content;

            currentUserMessage.assistantMessageId =
              message.id;

          } else {

            result.push({
              id:
                `assistant-${message.id}`,

              userMessageId:
                null,

              question:
                "",

              answer:
                message.content,

              assistantMessageId:
                message.id,

              sources:
                [],

              attachments:
                []
            });

          }

        }

      }


      return result;

    };


  // ==========================================================
  // PIN / UNPIN CONVERSATION
  // ==========================================================

  useEffect(() => {
    if (!userId) {
      setPinnedConversationIds([]);
      return;
    }

    try {
      const saved = localStorage.getItem(
        `pinned_conversations_${userId}`
      );

      const parsed = saved ? JSON.parse(saved) : [];

      setPinnedConversationIds(
        Array.isArray(parsed) ? parsed.map(String) : []
      );
    } catch {
      setPinnedConversationIds([]);
    }
  }, [userId]);

  const togglePinnedConversation =
    (event, conversationId) => {
      event.stopPropagation();

      const id = String(conversationId);

      setPinnedConversationIds(previous => {
        const next = previous.includes(id)
          ? previous.filter(item => item !== id)
          : [id, ...previous];

        if (userId) {
          try {
            localStorage.setItem(
              `pinned_conversations_${userId}`,
              JSON.stringify(next)
            );
          } catch {
            // Ignore localStorage errors.
          }
        }

        return next;
      });
    };


  // ==========================================================
  // OPEN CONVERSATION
  // ==========================================================

  const handleOpenConversation =
    async (conversation) => {

      if (!token) {
        return;
      }

      const targetConversationId = conversation?.conversation_id;

      if (!targetConversationId) {
        return;
      }

      if (
        targetConversationId ===
        selectedConversationId
      ) {
        return;
      }

      const openGeneration = ++chatGenerationRef.current;
      chatQueueRef.current = [];
      conversationCreationPromiseRef.current = null;
      conversationIdRef.current = targetConversationId;

      // Never carry the previously open chat's document into this chat.
      setSelectedDocument(null);
      setSelectedConversationId(targetConversationId);

      try {

        setLoadingConversation(
          true
        );

        setChatError("");

        const data =
          await getConversation(
            targetConversationId,
            token
          );

        if (openGeneration !== chatGenerationRef.current) {
          return;
        }

        const loadedConversationId =
          data?.conversation_id ?? targetConversationId;

        // The backend is the single source of truth when reopening a chat.
        // Never restore a document from the previously selected chat or from
        // stale sidebar/localStorage state.
        const conversationDocumentId =
          data?.document_id ??
          data?.documentId ??
          data?.document?.document_id ??
          data?.document?.documentId ??
          data?.document?.id ??
          null;

        rememberConversationDocument(
          loadedConversationId,
          conversationDocumentId
        );

        conversationIdRef.current = loadedConversationId;
        setSelectedConversationId(loadedConversationId);

        setConversationTitle(
          data?.title ||
          conversation?.title ||
          "New Chat"
        );

        setMessages(
          convertConversationMessages(
            data?.messages || []
          )
        );

        setSelectedDocument(null);

        if (conversationDocumentId) {
          const matchingDocument =
            documents.find(
              document =>
                getDocumentId(document) ===
                String(conversationDocumentId)
            );

          if (matchingDocument) {
            setSelectedDocument(matchingDocument);
          }
        }

        setQuestion("");
        setAttachedFiles([]);
        setAttachmentMenuOpen(false);

      } catch (error) {

        console.error(
          "LOAD CONVERSATION ERROR:",
          error
        );

        if (openGeneration !== chatGenerationRef.current) {
          return;
        }

        setChatError(
          error.response?.data?.detail ||
          "Unable to load conversation."
        );

        if (
          error.response?.status === 401
        ) {
          logout();
        }

      } finally {

        if (openGeneration === chatGenerationRef.current) {
          setLoadingConversation(
            false
          );
        }

      }

    };


  // ==========================================================
  // RENAME CONVERSATION
  // ==========================================================

  const handleRenameConversation =
    async () => {

      if (
        !selectedConversationId ||
        !token
      ) {

        return;

      }


      const newTitle =
        window.prompt(
          "Enter conversation name:",
          conversationTitle
        );


      if (
        newTitle === null
      ) {

        return;

      }


      const cleanTitle =
        newTitle.trim();


      if (!cleanTitle) {

        alert(
          "Conversation name cannot be empty."
        );

        return;

      }


      try {

        setRenamingConversation(
          true
        );


        const data =
          await updateConversation(
            selectedConversationId,
            cleanTitle,
            token
          );


        setConversationTitle(
          data.title
        );


        setConversations(
          previous =>
            previous.map(
              conversation =>
                conversation.conversation_id ===
                selectedConversationId
                  ? {
                      ...conversation,
                      title:
                        data.title,
                      updated_at:
                        data.updated_at
                    }
                  : conversation
            )
        );

      } catch (error) {

        console.error(
          "RENAME ERROR:",
          error
        );


        alert(
          error.response?.data?.detail ||
          "Unable to rename conversation."
        );

      } finally {

        setRenamingConversation(
          false
        );

      }

    };


  // ==========================================================
  // DELETE CONVERSATION
  // ==========================================================

  const handleDeleteConversation =
    async (
      event,
      conversationId
    ) => {

      event.stopPropagation();


      const confirmed =
        window.confirm(
          "Are you sure you want to delete this conversation?"
        );


      if (!confirmed) {
        return;
      }


      try {

        await deleteConversation(
          conversationId,
          token
        );


        setConversations(
          previous =>
            previous.filter(
              conversation =>
                conversation.conversation_id !==
                conversationId
            )
        );

        setPinnedConversationIds(previous => {
          const next = previous.filter(
            id => String(id) !== String(conversationId)
          );

          if (userId) {
            try {
              localStorage.setItem(
                `pinned_conversations_${userId}`,
                JSON.stringify(next)
              );
            } catch {
              // Ignore localStorage errors.
            }
          }

          return next;
        });


        if (
          selectedConversationId ===
          conversationId
        ) {

          handleNewChat();

        }

      } catch (error) {

        console.error(
          "DELETE CONVERSATION ERROR:",
          error
        );


        alert(
          error.response?.data?.detail ||
          "Unable to delete conversation."
        );

      }

    };


  // ==========================================================
  // PDF UPLOAD SELECTOR
  // ==========================================================

  const openPDFSelector =
    () => {

      if (uploading) {
        return;
      }


      pdfInputRef.current?.click();

    };


  // ==========================================================
  // PDF UPLOAD
  // ==========================================================

  const handlePDFSelected =
    async (event) => {

      const file =
        event.target.files?.[0];


      event.target.value = "";


      if (!file) {
        return;
      }


      if (
        !file.name
          .toLowerCase()
          .endsWith(".pdf")
      ) {

        alert(
          "Please select a PDF file."
        );

        return;

      }


      const maxSize =
        50 * 1024 * 1024;


      if (
        file.size > maxSize
      ) {

        alert(
          "PDF must be smaller than 50 MB."
        );

        return;

      }


      try {

        setUploading(true);

        setUploadProgressText(
          "Uploading PDF..."
        );


        const data =
          await uploadPDF(
            file,
            token
          );


        await loadDocuments();


        const uploadedDocument =
          getDocumentFromResponse(
            data
          );


        const uploadedDocumentId =
          getDocumentId(
            uploadedDocument
          );


        console.log(
          "UPLOAD RESPONSE:",
          data
        );

        console.log(
          "UPLOAD DOCUMENT ID:",
          uploadedDocumentId
        );


        if (!uploadedDocumentId) {

          throw new Error(
            "PDF upload succeeded, but the backend response does not contain a document ID."
          );

        }


        setDocuments(
          previous => [
            uploadedDocument,
            ...previous.filter(
              document =>
                getDocumentId(document) !==
                uploadedDocumentId
            )
          ]
        );


        chatGenerationRef.current += 1;
        chatQueueRef.current = [];
        conversationCreationPromiseRef.current = null;
        conversationIdRef.current = null;

        setSelectedDocument(
          uploadedDocument
        );


        // The uploaded document belongs to this chat only.
        // Do not persist it globally in localStorage.


        // New document =
        // new conversation.

        setSelectedConversationId(
          null
        );


        setConversationTitle(
          "New Chat"
        );


        clearChat();


        setUploadProgressText(
          "PDF indexed successfully."
        );


      } catch (error) {

        console.error(
          "UPLOAD ERROR:",
          error
        );


        if (
          error.response?.status === 401
        ) {

          logout();

          return;

        }


        alert(
          error.response?.data?.detail ||
          "Unable to upload the PDF."
        );

      } finally {

        setUploading(false);


        setTimeout(() => {

          setUploadProgressText("");

        }, 1500);

      }

    };


  // ==========================================================
  // ATTACHMENT SELECTOR
  // ==========================================================

  const openAttachmentSelector =
    () => {


      setAttachmentMenuOpen(
        false
      );


      attachmentInputRef.current?.click();

    };


  // ==========================================================
  // ATTACH FILES
  // ==========================================================

  const handleAttachmentsSelected =
    (event) => {

      const files =
        Array.from(
          event.target.files || []
        );


      event.target.value = "";


      if (
        files.length === 0
      ) {

        return;

      }


      const maxSize =
        50 * 1024 * 1024;


      const validFiles =
        files.filter(
          file =>
            file.size <= maxSize
        );


      const rejectedFiles =
        files.filter(
          file =>
            file.size > maxSize
        );


      if (
        rejectedFiles.length > 0
      ) {

        alert(
          `${rejectedFiles.length} file(s) were larger than 50 MB and were not added.`
        );

      }


      if (
        validFiles.length === 0
      ) {

        return;

      }


      setAttachedFiles(
        previous => [
          ...previous,
          ...validFiles
        ]
      );


      setChatError("");

    };


  // ==========================================================
  // REMOVE ATTACHMENT
  // ==========================================================

  const removeAttachment =
    (index) => {

      setAttachedFiles(
        previous =>
          previous.filter(
            (_, i) =>
              i !== index
          )
      );

    };


  // ==========================================================
  // FILE ICON
  // ==========================================================

  const getFileIcon =
    (file) => {

      const type =
        file.type || "";


      const extension =
        file.name
          ?.split(".")
          .pop()
          ?.toUpperCase();


      if (
        type.startsWith("image/")
      ) {

        return "IMG";

      }


      if (
        type.startsWith("video/")
      ) {

        return "VID";

      }


      if (
        type.startsWith("audio/")
      ) {

        return "AUD";

      }


      if (
        extension === "PDF"
      ) {

        return "PDF";

      }


      if (
        extension === "DOC" ||
        extension === "DOCX"
      ) {

        return "DOC";

      }


      if (
        extension === "XLS" ||
        extension === "XLSX" ||
        extension === "CSV"
      ) {

        return "DATA";

      }


      if (
        extension === "PPT" ||
        extension === "PPTX"
      ) {

        return "PPT";

      }


      if (
        extension === "TXT" ||
        extension === "MD"
      ) {

        return "TXT";

      }


      return "FILE";

    };


  // ==========================================================
  // TYPEWRITER ANIMATION
  // ==========================================================

  const animateAssistantAnswer =
    async (messageId, answer) => {
      if (!answer) return;

      const chunkSize =
        answer.length > 1600 ? 8 :
        answer.length > 800 ? 6 :
        answer.length > 300 ? 4 : 3;

      for (let index = 0; index < answer.length; index += chunkSize) {
        const visibleAnswer = answer.slice(0, Math.min(index + chunkSize, answer.length));

        setMessages(previous =>
          previous.map(message =>
            message.id === messageId
              ? { ...message, answer: visibleAnswer, status: "typing" }
              : message
          )
        );

        await new Promise(resolve =>
          setTimeout(resolve, answer.length > 1600 ? 6 : answer.length > 800 ? 8 : 10)
        );
      }

      setMessages(previous =>
        previous.map(message =>
          message.id === messageId
            ? { ...message, answer, status: "done" }
            : message
        )
      );
    };


  // ==========================================================
  // FAST CASUAL RESPONSE
  // ==========================================================

  const getFastCasualResponse = (text) => {
    // Keep very short social messages on the frontend so greetings do not
    // make a full Gemini/API round trip. This also handles stretched
    // spellings such as "hiii", "hellooo", and "hii hello".
    const normalized = text
      .toLowerCase()
      .trim()
      .replace(/[!?.,]+/g, "")
      .replace(/\s+/g, " ");

    const greetingToken = /^(?:h+i+|he+l+o+|hey+)$/;
    const greetingMessage = normalized
      .split(" ")
      .filter(Boolean);

    if (
      greetingMessage.length > 0 &&
      greetingMessage.length <= 3 &&
      greetingMessage.every(token => greetingToken.test(token))
    ) {
      return "Hi! How can I help you?";
    }

    const responses = {
      "good morning": "Good morning! How can I help you?",
      "good afternoon": "Good afternoon! How can I help you?",
      "good evening": "Good evening! How can I help you?",
      thanks: "You're welcome!",
      "thank you": "You're welcome!",
      thx: "You're welcome!"
    };

    return responses[normalized] || null;
  };


  // ==========================================================
  // PROCESS ONE CHAT REQUEST
  // ==========================================================

  const processChatRequest = async (request) => {
    const {
      currentQuestion,
      messageId,
      documentId,
      conversationId,
      imageFile,
      startedAt,
      chatGeneration
    } = request;

    const apiBaseUrl =
      import.meta.env.VITE_API_URL ||
      "http://127.0.0.1:8000";

    const authHeaders = {
      Authorization: `Bearer ${token}`
    };

    const buildChatRequest = () => {
      if (imageFile) {
        const form = new FormData();

        form.append(
          "question",
          currentQuestion
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

        return {
          headers: authHeaders,
          body: form
        };
      }

      return {
        headers: {
          ...authHeaders,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          question: currentQuestion,
          conversation_id: conversationId || null,
          document_id: documentId || null
        })
      };
    };

    const isCurrentChatRequest = () =>
      chatGeneration === chatGenerationRef.current &&
      String(conversationId || "") === String(conversationIdRef.current || "");

    const markTyping = () => {
      if (!isCurrentChatRequest()) return;

      setMessages(previous =>
        previous.map(message =>
          message.id === messageId
            ? {
                ...message,
                answer: "",
                status: "typing",
                error: ""
              }
            : message
        )
      );
    };

    const markDone = (answer, sources = []) => {
      if (!isCurrentChatRequest()) return;

      setMessages(previous =>
        previous.map(message =>
          message.id === messageId
            ? {
                ...message,
                answer,
                status: "done",
                sources: Array.isArray(sources) ? sources : []
              }
            : message
        )
      );
    };

    const markError = (error) => {
      if (!isCurrentChatRequest()) return;

      setMessages(previous =>
        previous.map(message =>
          message.id === messageId
            ? {
                ...message,
                status: "error",
                error: error || "Unable to get an answer."
              }
            : message
        )
      );

      setChatError(error || "Unable to get an answer.");
    };

    const waitForMinimumThinking = async () => {
      const elapsed = Date.now() - (startedAt || Date.now());
      const remaining = Math.max(0, 2000 - elapsed);

      if (remaining > 0) {
        await new Promise(resolve =>
          setTimeout(resolve, remaining)
        );
      }
    };

    try {
      setChatError("");

      /*
       * Try the streaming endpoint first. This gives the user the first
       * words as soon as Gemini produces them. If the currently running
       * backend has not been restarted yet and returns 404, automatically
       * fall back to the normal JSON endpoint so chat still works.
       */
      const chatRequest = buildChatRequest();

      let response = await fetch(
        `${apiBaseUrl}/chat/message/stream`,
        {
          method: "POST",
          headers: chatRequest.headers,
          body: chatRequest.body
        }
      );

      if (response.status === 404) {
        const fallbackRequest = buildChatRequest();

        response = await fetch(
          `${apiBaseUrl}/chat/message`,
          {
            method: "POST",
            headers: fallbackRequest.headers,
            body: fallbackRequest.body
          }
        );

        if (!response.ok) {
          let errorData = null;

          try {
            errorData = await response.json();
          } catch {
            errorData = null;
          }

          if (response.status === 401) {
            logout();
            return;
          }

          throw new Error(
            errorData?.detail ||
            errorData?.message ||
            `Request failed with status ${response.status}`
          );
        }

        const data = await response.json();

        if (data.conversation_id && isCurrentChatRequest()) {
          conversationIdRef.current = data.conversation_id;
          const responseDocumentId =
            data.document_id ?? documentId ?? null;

          if (responseDocumentId) {
            rememberConversationDocument(
              data.conversation_id,
              responseDocumentId
            );
          }
          setSelectedConversationId(data.conversation_id);
        }

        const answer =
          data.answer ||
          data.response ||
          data.content ||
          "I couldn't generate an answer.";

        await waitForMinimumThinking();
        markTyping();
        await animateAssistantAnswer(messageId, answer);
        markDone(answer, data.sources || []);

        void loadConversations().catch(() => {});
        return;
      }

      if (!response.ok) {
        let errorData = null;

        try {
          errorData = await response.json();
        } catch {
          errorData = null;
        }

        if (response.status === 401) {
          logout();
          return;
        }

        throw new Error(
          errorData?.detail ||
          errorData?.message ||
          `Request failed with status ${response.status}`
        );
      }

      const contentType =
        response.headers.get("content-type") || "";

      /*
       * If a proxy/server unexpectedly returns JSON from the stream route,
       * handle it safely instead of trying to read it as NDJSON.
       */
      if (!contentType.includes("application/x-ndjson")) {
        const data = await response.json();

        if (data.conversation_id && isCurrentChatRequest()) {
          conversationIdRef.current = data.conversation_id;
          const responseDocumentId =
            data.document_id ?? documentId ?? null;

          if (responseDocumentId) {
            rememberConversationDocument(
              data.conversation_id,
              responseDocumentId
            );
          }
          setSelectedConversationId(data.conversation_id);
        }

        const answer =
          data.answer ||
          data.response ||
          data.content ||
          "I couldn't generate an answer.";

        await waitForMinimumThinking();
        markTyping();
        await animateAssistantAnswer(messageId, answer);
        markDone(answer, data.sources || []);
        return;
      }

      if (!response.body) {
        throw new Error("The server did not return a readable response.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let streamedAnswer = "";
      let sources = [];
      let thinkingReleased = false;

      const releaseThinking = async () => {
        if (thinkingReleased) return;
        thinkingReleased = true;
        await waitForMinimumThinking();
        markTyping();
      };

      const handleEvent = async (rawLine) => {
        const line = rawLine.trim();

        if (!line) return;

        let payload;

        try {
          payload = JSON.parse(
            line.startsWith("data:")
              ? line.slice(5).trim()
              : line
          );
        } catch {
          return;
        }

        if (payload.type === "meta") {
          if (payload.conversation_id && isCurrentChatRequest()) {
            conversationIdRef.current = payload.conversation_id;
            if (documentId) {
              rememberConversationDocument(
                payload.conversation_id,
                documentId
              );
            }
            setSelectedConversationId(payload.conversation_id);
          }

          return;
        }

        if (payload.type === "chunk") {
          const text = payload.text || "";

          if (!text) return;

          streamedAnswer += text;

          await releaseThinking();

          if (!isCurrentChatRequest()) return;

          setMessages(previous =>
            previous.map(message =>
              message.id === messageId
                ? {
                    ...message,
                    answer: streamedAnswer,
                    status: "typing"
                  }
                : message
            )
          );

          return;
        }

        if (payload.type === "done") {
          if (payload.conversation_id && isCurrentChatRequest()) {
            conversationIdRef.current = payload.conversation_id;
            if (documentId) {
              rememberConversationDocument(
                payload.conversation_id,
                documentId
              );
            }
            setSelectedConversationId(payload.conversation_id);
          }

          sources = Array.isArray(payload.sources)
            ? payload.sources
            : [];

          return;
        }

        if (payload.type === "error") {
          throw new Error(
            payload.error || "Unable to get an answer."
          );
        }
      };

      while (true) {
        const { value, done } = await reader.read();

        if (done) break;

        buffer += decoder.decode(value, {
          stream: true
        });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          await handleEvent(line);
        }
      }

      buffer += decoder.decode();

      if (buffer.trim()) {
        await handleEvent(buffer);
      }

      if (!streamedAnswer) {
        await releaseThinking();
        streamedAnswer = "I couldn't generate an answer.";
      }

      markDone(streamedAnswer, sources);

      void loadConversations().catch(() => {});

    } catch (error) {
      console.error("CHAT ERROR:", error);
      markError(
        error?.message ||
        "Unable to get an answer."
      );
    }
  };

  // ==========================================================
  // PROCESS CHAT REQUEST IMMEDIATELY
  // ==========================================================

  const enqueueChatRequest = (request) => {
    const queueKey =
      request.conversationId ||
      "__pending_conversation__";

    const previous =
      conversationQueuesRef.current.get(queueKey) ||
      Promise.resolve();

    const next = previous
      .catch(() => {})
      .then(() => processChatRequest(request));

    conversationQueuesRef.current.set(queueKey, next);

    void next.finally(() => {
      if (conversationQueuesRef.current.get(queueKey) === next) {
        conversationQueuesRef.current.delete(queueKey);
      }
    });
  };


  const processChatQueue = () => {
    if (chatQueueRef.current.length === 0) {
      return;
    }

    const pendingRequests = [
      ...chatQueueRef.current
    ];

    chatQueueRef.current = [];

    pendingRequests.forEach(request => {
      enqueueChatRequest(request);
    });
  };


  // ==========================================================
  // ASK QUESTION
  // ==========================================================


  const copyAssistantResponse = async (text) => {
    try {
      await navigator.clipboard.writeText(text || "");
    } catch (error) {
      console.error("COPY ERROR:", error);
    }
  };

  const handleAskQuestion = async () => {
    const typedQuestion = question.trim();

    const hasAttachedPdf =
      attachedFiles.some(file =>
        file?.name?.toLowerCase().endsWith(".pdf")
      );

    const attachedImage = attachedFiles.find(file =>
      file?.type?.startsWith("image/")
    );

    const hasAttachedImage = Boolean(attachedImage);

    if (!typedQuestion && !hasAttachedPdf && !hasAttachedImage) return;

    // If a PDF is sent without new text, only continue a previous
    // instruction when the assistant's immediately preceding response
    // was specifically asking the user to upload/select/provide a document.
    //
    // Otherwise this is simply a PDF-only upload and should start with
    // a fresh document-reading request. Never reuse an unrelated prompt
    // such as "What is the capital of Japan?" from earlier in the chat.
    let pendingDocumentInstruction = "";

    if (!typedQuestion && hasAttachedPdf && messages.length > 0) {
      const lastMessage =
        messages[messages.length - 1];

      const lastAssistantAnswer =
        typeof lastMessage?.answer === "string"
          ? lastMessage.answer
          : "";

      const assistantAskedForDocument =
        /upload|select|provide|attach|document|pdf/i.test(
          lastAssistantAnswer
        ) &&
        /(upload|select|provide|attach)/i.test(
          lastAssistantAnswer
        );

      if (assistantAskedForDocument) {
        pendingDocumentInstruction =
          [...messages]
            .reverse()
            .find(
              message =>
                typeof message?.question === "string" &&
                message.question.trim()
            )?.question?.trim() || "";
      }
    }

    const currentQuestion =
      typedQuestion ||
      pendingDocumentInstruction ||
      (
        hasAttachedImage && !hasAttachedPdf
          ? "Analyze the uploaded image and tell me what you can see."
          : "Read the uploaded document and tell me how you can help me with it."
      );

    setChatError("");

    // Only the document explicitly selected/attached in THIS chat
    // can be used for this question.
    let activeDocument =
      normalizeDocument(selectedDocument) ||
      null;

    // If the user attached a PDF through the composer, upload/index that
    // exact file before sending the message. Previously attachedFiles were
    // only visual UI attachments, so the backend could silently keep using
    // an older selected document (for example webbfactsheet.pdf).
    const attachedPdf = attachedFiles.find(file =>
      file?.name?.toLowerCase().endsWith(".pdf")
    );

    let documentId = getDocumentId(activeDocument);
    const messageId = `chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    const attachmentsSnapshot = attachedFiles.map(file => ({
      name: file.name,
      type: file.type,
      size: file.size
    }));

    // Render immediately. The composer remains active while this request
    // and any previous request are being processed.
    setMessages(previous => [
      ...previous,
      {
        id: messageId,
        // Keep the visible user message faithful to what was actually typed.
        // currentQuestion can contain the previous prompt for backend processing,
        // but that reused prompt must remain invisible in the UI.
        question: typedQuestion,
        answer: "",
        status: "thinking",
        sources: [],
        attachments: attachmentsSnapshot
      }
    ]);

    setQuestion("");
    setAttachedFiles([]);
    setAttachmentMenuOpen(false);

    // A composer-attached PDF ALWAYS has priority over any stale selected
    // document. We deliberately send the actual File to the backend even
    // when PostgreSQL already has a document with the same filename.
    // The backend safely reuses the document_id when it is indexed, and
    // re-indexes it when the old record has missing Qdrant vectors.
    // This is critical: a frontend-only filename match must NEVER cause us
    // to skip sending the actual PDF bytes.
    if (attachedPdf) {
      try {
        setUploading(true);
        setUploadProgressText("Uploading and indexing attached PDF...");

        const uploadData = await uploadPDF(attachedPdf, token);

          if (!uploadData?.document_id) {
            throw new Error("The PDF was uploaded but no document ID was returned.");
          }

          const uploadedDocument = normalizeDocument({
            document_id: uploadData.document_id,
            filename: uploadData.filename || attachedPdf.name,
            user_id: uploadData.user_id || userId,
            pages: uploadData.pages,
            chunks: uploadData.chunks,
            created_at: new Date().toISOString()
          });

          activeDocument = uploadedDocument;
          documentId = getDocumentId(uploadedDocument);

          setSelectedDocument(uploadedDocument);

          // The uploaded document is scoped to the current conversation.
          // Do not persist it as a global selected document.

          setDocuments(previous => {
            const withoutDuplicate = previous.filter(
              document => getDocumentId(document) !== documentId
            );
            return [uploadedDocument, ...withoutDuplicate];
          });

          setUploadProgressText("PDF indexed successfully.");
        } catch (error) {
          console.error("ATTACHED PDF UPLOAD ERROR:", error);

          setMessages(previous =>
            previous.map(message =>
              message.id === messageId
                ? {
                    ...message,
                    status: "error",
                    error: error?.response?.data?.detail ||
                      error?.message ||
                      "Unable to upload and index the attached PDF."
                  }
                : message
            )
          );

          setChatError(
            error?.response?.data?.detail ||
            error?.message ||
            "Unable to upload and index the attached PDF."
          );

          setUploading(false);
          setTimeout(() => setUploadProgressText(""), 1500);
          return;
        } finally {
          setUploading(false);
          setTimeout(() => setUploadProgressText(""), 1500);
        }
    }

    // If this is the first message in a new chat, create the conversation
    // immediately so multiple questions sent quickly all share the same
    // conversation_id instead of creating separate chats.
    let activeConversationId = conversationIdRef.current || null;

    if (!activeConversationId) {
      if (!conversationCreationPromiseRef.current) {
        conversationCreationPromiseRef.current = createConversation(
          currentQuestion.slice(0, 60) || "New Conversation",
          documentId || null,
          token
        );
      }

      try {
        const data = await conversationCreationPromiseRef.current;
        activeConversationId = data.conversation_id;
        conversationIdRef.current = activeConversationId;
        rememberConversationDocument(
          activeConversationId,
          data.document_id ?? documentId ?? null
        );
        setSelectedConversationId(activeConversationId);
        setConversationTitle(data.title || currentQuestion.slice(0, 60) || "New Chat");

        // Refresh the sidebar in the background; do not delay the chat UI.
        void loadConversations().catch(() => {});
      } catch (error) {
        setMessages(previous =>
          previous.map(message =>
            message.id === messageId
              ? {
                  ...message,
                  status: "error",
                  error: error?.message || "Unable to create the conversation."
                }
              : message
          )
        );
        return;
      } finally {
        conversationCreationPromiseRef.current = null;
      }
    }

    const request = {
      currentQuestion,
      messageId,
      documentId,
      conversationId: activeConversationId,
      imageFile: attachedImage || null,
      startedAt: Date.now(),
      chatGeneration: chatGenerationRef.current
    };

    // Every message goes through the backend so Gemini can understand
    // spelling mistakes, informal wording, follow-ups, and conversation
    // references. The request is serialized per conversation so Q2 sees
    // Q1 + A1 before Q2 is answered.
    chatQueueRef.current.push(request);
    processChatQueue();
  };


  // ==========================================================
  // ENTER KEY
  // ==========================================================

  const handleQuestionKeyDown =
    (event) => {

      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {

        event.preventDefault();

        handleAskQuestion();

      }

    };


  // ==========================================================
  // DELETE DOCUMENT
  // ==========================================================

  const handleDelete =
    async (
      event,
      documentId
    ) => {

      event.stopPropagation();


      const confirmed =
        window.confirm(
          "Are you sure you want to delete this PDF?"
        );


      if (!confirmed) {
        return;
      }


      try {

        await deleteDocument(
          documentId,
          token
        );


        if (
          selectedDocument?.document_id ===
          documentId
        ) {

          setSelectedDocument(
            null
          );


          handleNewChat();

        }


        await loadDocuments();

      } catch (error) {

        console.error(
          "DELETE ERROR:",
          error
        );


        alert(
          error.response?.data?.detail ||
          "Unable to delete the PDF."
        );

      }

    };


  // ==========================================================
  // FORMAT DATE
  // ==========================================================

  const formatDate =
    (date) => {

      if (!date) {
        return "";
      }


      const parsed =
        new Date(date);


      if (
        Number.isNaN(
          parsed.getTime()
        )
      ) {

        return "";

      }


      return parsed.toLocaleDateString(
        "en-IN",
        {
          day: "2-digit",
          month: "short",
          year: "numeric"
        }
      );

    };


  // ==========================================================
  // FORMAT RECENT DATE
  // ==========================================================

  const formatRecentDate =
    (date) => {

      if (!date) {
        return "";
      }


      const parsed =
        new Date(date);


      if (
        Number.isNaN(
          parsed.getTime()
        )
      ) {

        return "";

      }


      const now =
        new Date();


      const difference =
        now.getTime() -
        parsed.getTime();


      const oneDay =
        24 * 60 * 60 * 1000;


      if (
        difference < oneDay &&
        parsed.getDate() ===
          now.getDate()
      ) {

        return "Today";

      }


      if (
        difference < 2 * oneDay
      ) {

        return "Yesterday";

      }


      return parsed.toLocaleDateString(
        "en-IN",
        {
          day: "2-digit",
          month: "short"
        }
      );

    };


  // ==========================================================
  // LOGIN PAGE
  // ==========================================================

  if (!token) {

    return (

      <div className="auth-page">

        <div className="auth-card">

          <h1>

            {authMode === "login"
              ? "Welcome back"
              : "Create account"
            }

          </h1>


          <p className="auth-subtitle">

            {authMode === "login"
              ? "Sign in to your RAG Assistant"
              : "Create your RAG Assistant account"
            }

          </p>


          <form
            onSubmit={handleAuth}
          >

            <label>
              Email
            </label>


            <input
              type="email"
              placeholder="Enter your email"
              value={email}
              onChange={
                event =>
                  setEmail(
                    event.target.value
                  )
              }
            />


            <label>
              Password
            </label>


            <div className="password-input-wrap">

              <input
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                value={password}
                onChange={
                  event =>
                    setPassword(
                      event.target.value
                    )
                }
              />

              <button
                type="button"
                className="password-toggle"
                aria-label={showPassword ? "Hide password" : "Show password"}
                onClick={() =>
                  setShowPassword(previous => !previous)
                }
              >
                <svg
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  {showPassword ? (
                    <>
                      <path
                        d="M3 3l18 18"
                      />
                      <path
                        d="M10.6 10.6a2 2 0 0 0 2.8 2.8"
                      />
                      <path
                        d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.2 0 9.2 3.4 10.5 8a11.7 11.7 0 0 1-3.2 5.1"
                      />
                      <path
                        d="M6.2 6.2A11.8 11.8 0 0 0 1.5 12c1.3 4.6 5.3 8 10.5 8 1.5 0 2.9-.3 4.1-.8"
                      />
                    </>
                  ) : (
                    <>
                      <path
                        d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z"
                      />
                      <circle
                        cx="12"
                        cy="12"
                        r="2.5"
                      />
                    </>
                  )}
                </svg>
              </button>

            </div>


            {authMode === "register" && (

              <>

                <label>
                  Confirm password
                </label>


                <div className="password-input-wrap">

                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    placeholder="Confirm your password"
                    value={confirmPassword}
                    onChange={
                      event =>
                        setConfirmPassword(
                          event.target.value
                        )
                    }
                  />

                  <button
                    type="button"
                    className="password-toggle"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    onClick={() =>
                      setShowConfirmPassword(previous => !previous)
                    }
                  >
                    <svg
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      {showConfirmPassword ? (
                        <>
                          <path
                            d="M3 3l18 18"
                          />
                          <path
                            d="M10.6 10.6a2 2 0 0 0 2.8 2.8"
                          />
                          <path
                            d="M9.9 4.2A10.7 10.7 0 0 1 12 4c5.2 0 9.2 3.4 10.5 8a11.7 11.7 0 0 1-3.2 5.1"
                          />
                          <path
                            d="M6.2 6.2A11.8 11.8 0 0 0 1.5 12c1.3 4.6 5.3 8 10.5 8 1.5 0 2.9-.3 4.1-.8"
                          />
                        </>
                      ) : (
                        <>
                          <path
                            d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z"
                          />
                          <circle
                            cx="12"
                            cy="12"
                            r="2.5"
                          />
                        </>
                      )}
                    </svg>
                  </button>

                </div>

              </>

            )}


            {authError && (

              <div className="error-message">
                {authError}
              </div>

            )}


            {authMessage && (

              <div className="success-message">
                {authMessage}
              </div>

            )}


            <button
              type="submit"
              className="login-button"
              disabled={authLoading}
            >

              {authLoading
                ? "Please wait..."
                : authMode === "login"
                  ? "Sign in"
                  : "Create account"
              }

            </button>

          </form>


          <div className="auth-divider" aria-hidden="true">
            <span></span>
            <em>or</em>
            <span></span>
          </div>


          <button
            type="button"
            className="google-auth-button"
            onClick={() => {}}
            aria-label="Continue with Google"
          >
            <span className="google-icon" aria-hidden="true">
              G
            </span>
            <span>
              Continue with Google
            </span>
          </button>


          <button
            type="button"
            className="auth-switch"
            onClick={() => {

              setAuthMode(
                authMode === "login"
                  ? "register"
                  : "login"
              );

              setAuthError("");

              setAuthMessage("");

            }}
          >

            {authMode === "login"
              ? "Don't have an account? Create one"
              : "Already have an account? Sign in"
            }

          </button>

        </div>

      </div>

    );

  }


  // ==========================================================
  // MAIN APPLICATION
  // ==========================================================

  return (

    <div className="rag-app">


      {/* ======================================================
          GLOBAL FILE INPUTS
          ====================================================== */}

      <input
        ref={pdfInputRef}
        type="file"
        accept=".pdf,application/pdf"
        className="hidden-input"
        onChange={handlePDFSelected}
      />


      <input
        ref={attachmentInputRef}
        type="file"
        multiple
        accept="*/*"
        className="hidden-input"
        onChange={handleAttachmentsSelected}
      />


      {/* ======================================================
          SIDEBAR
          ====================================================== */}

      <aside className="rag-sidebar">


        {/* ------------------------------------------------------
            BRAND
        ------------------------------------------------------ */}

        <div className="sidebar-header">

          <div className="brand-copy">

            <strong>
              RAG Assistant
            </strong>

            <span>
              AI Document Chat
            </span>

          </div>

        </div>


        <div className="sidebar-scroll">


        {/* ------------------------------------------------------
            NEW CHAT
        ------------------------------------------------------ */}

        <button
          className="new-chat-button"
          onClick={handleNewChat}
        >

          <span className="new-chat-plus">
            +
          </span>

          <span>
            New chat
          </span>

        </button>


        {/* ======================================================
            PINNED
            ====================================================== */}

        <section className="sidebar-section">

          <div className="section-heading">

            <span className="section-icon">
              ⌖
            </span>

            <span>
              PINNED
            </span>

          </div>


          <div className="chat-list">

            {!loadingConversations &&
              conversations
                .filter(conversation =>
                  pinnedConversationIds.includes(
                    String(conversation.conversation_id)
                  )
                )
                .map(conversation => (

                  <div
                    key={`pinned-${conversation.conversation_id}`}
                    className={
                      `recent-chat pinned-chat ${
                        selectedConversationId ===
                        conversation.conversation_id
                          ? "active"
                          : ""
                      }`
                    }
                    onClick={() =>
                      handleOpenConversation(conversation)
                    }
                  >

                    <div className="recent-chat-content">

                      <span className="recent-chat-title">
                        {conversation.title ||
                          "New Conversation"
                        }
                      </span>

                      <small>
                        {formatRecentDate(
                          conversation.updated_at
                        )}
                      </small>

                    </div>

                    <button
                      className="pin-chat-button pinned"
                      onClick={event =>
                        togglePinnedConversation(
                          event,
                          conversation.conversation_id
                        )
                      }
                      title="Unpin chat"
                      aria-label="Unpin chat"
                    >
                      📌
                    </button>

                  </div>

                ))
            }

            {!loadingConversations &&
              conversations.filter(conversation =>
                pinnedConversationIds.includes(
                  String(conversation.conversation_id)
                )
              ).length === 0 && (

                <div className="empty-sidebar-state">
                  No pinned chats
                </div>

              )
            }

          </div>

        </section>


        {/* ======================================================
            RECENTS
            ====================================================== */}

        <section className="sidebar-section recent-section">

          <div className="section-heading">

            <span className="section-icon">
              ◷
            </span>

            <span>
              RECENTS
            </span>

          </div>


          <div className="chat-list">

            {loadingConversations && (

              <div className="empty-sidebar-state">
                Loading chats...
              </div>

            )}


            {!loadingConversations &&
              conversations.length === 0 && (

                <div className="empty-sidebar-state">
                  No recent chats
                </div>

              )
            }


            {!loadingConversations &&
              conversations
                .filter(conversation =>
                  !pinnedConversationIds.includes(
                    String(conversation.conversation_id)
                  )
                )
                .map(
                  conversation => (

                  <div
                    key={
                      conversation.conversation_id
                    }
                    className={
                      `recent-chat ${
                        selectedConversationId ===
                        conversation.conversation_id
                          ? "active"
                          : ""
                      }`
                    }
                    onClick={() =>
                      handleOpenConversation(
                        conversation
                      )
                    }
                  >

                    <div className="recent-chat-content">

                      <span className="recent-chat-title">

                        {conversation.title ||
                          "New Conversation"
                        }

                      </span>


                      <small>

                        {formatRecentDate(
                          conversation.updated_at
                        )}

                      </small>

                    </div>


                    <button
                      className="pin-chat-button"
                      onClick={event =>
                        togglePinnedConversation(
                          event,
                          conversation.conversation_id
                        )
                      }
                      title="Pin chat"
                      aria-label="Pin chat"
                    >
                      📌
                    </button>

                    <button
                      className="recent-delete"
                      onClick={
                        event =>
                          handleDeleteConversation(
                            event,
                            conversation.conversation_id
                          )
                      }
                      title="Delete conversation"
                    >
                      ×
                    </button>

                  </div>

                )
              )
            }

          </div>

        </section>


        {/* ======================================================
            MY DOCUMENTS
            ====================================================== */}

        <section className="sidebar-section documents-section">

          <div className="section-heading documents-heading">

            <span className="section-icon">
              ▱
            </span>

            <span>
              MY DOCUMENTS
            </span>


            <button
              className="document-add-button"
              onClick={openPDFSelector}
              disabled={uploading}
              title="Upload PDF"
            >
              +
            </button>

          </div>


          {uploadProgressText && (

            <div className="upload-status">
              {uploadProgressText}
            </div>

          )}


          <div className="documents-list">

            {loadingDocuments && (

              <div className="empty-sidebar-state">
                Loading documents...
              </div>

            )}


            {!loadingDocuments &&
              documents.length === 0 && (

                <div className="empty-sidebar-state">
                  No documents yet
                </div>

              )
            }


            {!loadingDocuments &&
              documents.map(
                document => (

                  <div
                    key={
                      document.document_id
                    }
                    className={
                      `document-row ${
                        selectedDocument?.document_id ===
                        document.document_id
                          ? "active"
                          : ""
                      }`
                    }
                    onClick={() =>
                      handleSelectDocument(
                        document
                      )
                    }
                  >

                    <div className="document-file-icon">
                      PDF
                    </div>


                    <div className="document-details">

                      <strong>
                        {document.filename}
                      </strong>


                      <span>

                        {document.pages}{" "}

                        {document.pages === 1
                          ? "page"
                          : "pages"
                        }

                      </span>

                    </div>


                    <button
                      className="document-delete"
                      onClick={
                        event =>
                          handleDelete(
                            event,
                            document.document_id
                          )
                      }
                      title="Delete document"
                    >
                      ×
                    </button>

                  </div>

                )
              )
            }

          </div>

        </section>


        </div>


        {/* ======================================================
            USER
            ====================================================== */}

        <div
          className={`sidebar-user ${accountMenuOpen ? "account-open" : ""}`}
        >

          <div className="user-avatar">
            {userEmail
              ? userEmail.charAt(0).toUpperCase()
              : "U"
            }
          </div>

          <button
            className="user-details account-trigger"
            type="button"
            onClick={() => setAccountMenuOpen(previous => !previous)}
            aria-expanded={accountMenuOpen}
            title="Account options"
          >
            <strong title={userEmail || "User"}>
              {userEmail || "User"}
            </strong>

            <span>
              Account
            </span>
          </button>

          {accountMenuOpen && (
            <div
              className="account-actions"
              onClick={(event) => event.stopPropagation()}
            >
            <button
              className="account-action-button"
              type="button"
              onClick={switchAccount}
              title="Switch account"
            >
              Switch account
            </button>

            <button
              className="account-action-button logout"
              type="button"
              onClick={logout}
              title="Logout"
            >
              Logout
            </button>
            </div>
          )}

        </div>


      </aside>


      {/* ======================================================
          MAIN
          ====================================================== */}

      <main
        className={
          `rag-main ${
            sidebarOpen
              ? ""
              : "sidebar-collapsed"
          }`
        }
      >


        {/* ====================================================
            HEADER
            ==================================================== */}

        <header className="main-header">

          <div className="header-title-area">

            <h1>
              {conversationTitle}
            </h1>


            {selectedConversationId && (

              <button
                className="rename-button"
                onClick={
                  handleRenameConversation
                }
                disabled={
                  renamingConversation
                }
                title="Rename conversation"
              >
                ✎
              </button>

            )}

          </div>


        </header>


        {/* ====================================================
            LOADING OLD CONVERSATION
            ==================================================== */}

        {loadingConversation ? (

          <section className="new-chat-panel">

            <div className="welcome-content">

              <div className="welcome-chat-icon">
                •••
              </div>

              <h2>
                Loading conversation...
              </h2>

              <p>
                Please wait.
              </p>

            </div>

          </section>

        ) : messages.length === 0 ? (


          /* ==================================================
             NEW CHAT
             ================================================== */

          <section className="new-chat-panel">

            <div className="welcome-content">


              <div className="welcome-chat-icon">
                <span>
                  •••
                </span>
              </div>


              <h2>
                What's on your mind today?
              </h2>


              <p>
                Ask a question about your documents
                or upload files to get started.
              </p>


              {/* =================================================
                  INPUT
                  ================================================= */}

              <div className="main-input-area">


                {/* ATTACHMENT PREVIEW */}

                {attachedFiles.length > 0 && (

                  <div className="attachment-preview-list">

                    {attachedFiles.map(
                      (file, index) => (

                        <div
                          className="attachment-preview"
                          key={`${file.name}-${index}`}
                        >

                          <span className="attachment-type">
                            <span className="attachment-circle">
                              {getFileIcon(file)}
                            </span>
                          </span>

                          <span className="attachment-file-details">
                            <strong className="attachment-name">
                              {file.name}
                            </strong>

                            <small>
                              {file.type?.startsWith("image/")
                                ? "IMAGE"
                                : file.name?.toLowerCase().endsWith(".pdf")
                                  ? "PDF"
                                  : "FILE"}
                            </small>
                          </span>

                          <button
                            className="attachment-remove"
                            onClick={() =>
                              removeAttachment(
                                index
                              )
                            }
                            aria-label="Remove attachment"
                          >
                            ×
                          </button>

                        </div>

                      )
                    )}

                  </div>

                )}


                <div className="rag-input">


                  <div className="plus-wrapper">

                    <button
                      className="plus-button"
                      onClick={() =>
                        setAttachmentMenuOpen(
                          previous =>
                            !previous
                        )
                      }
                      title="Add photos or files"
                    >
                      +
                    </button>


                    {attachmentMenuOpen && (

                      <div className="attachment-popup">


                        <button
                          className="attachment-option"
                          onClick={
                            openAttachmentSelector
                          }
                        >

                          <span className="option-icon">
                            🖼
                          </span>


                          <span>

                            <strong>
                              Add photos
                            </strong>

                            <small>
                              Choose images from your computer
                            </small>

                          </span>

                        </button>


                        <button
                          className="attachment-option"
                          onClick={
                            openAttachmentSelector
                          }
                        >

                          <span className="option-icon">
                            📎
                          </span>


                          <span>

                            <strong>
                              Add files
                            </strong>

                            <small>
                              Upload from your computer
                            </small>

                          </span>

                        </button>


                      </div>

                    )}

                  </div>


                  <input
                    className="chat-text-input"
                    value={question}
                    onChange={
                      event =>
                        setQuestion(
                          event.target.value
                        )
                    }
                    onKeyDown={
                      handleQuestionKeyDown
                    }
                    placeholder="Ask anything..."
                    disabled={false}
                  />


                  <button
                    className={
                      `send-button ${
                        question.trim()
                          ? "active"
                          : ""
                      }`
                    }
                    onClick={
                      handleAskQuestion
                    }
                    disabled={
                      !question.trim() &&
                      !attachedFiles.some(file =>
                        file?.name?.toLowerCase().endsWith(".pdf") ||
                        file?.type?.startsWith("image/")
                      )
                    }
                  >
                    ➤
                  </button>


                </div>


                {chatError && (

                  <div className="main-chat-error">
                    {chatError}
                  </div>

                )}


              </div>


              {/* =================================================
                  QUICK ACTIONS
                  ================================================= */}

              <div className="quick-actions">


                <button
                  onClick={
                    openAttachmentSelector
                  }
                >

                  <span className="quick-icon">
                    ♧
                  </span>


                  <span>

                    <strong>
                      Upload files
                    </strong>

                    <small>
                      Add documents
                    </small>

                  </span>

                </button>


                <button
                  onClick={() =>
                    setQuestion(
                      "Ask a question about this document."
                    )
                  }
                >

                  <span className="quick-icon">
                    ?
                  </span>


                  <span>

                    <strong>
                      Ask question
                    </strong>

                    <small>
                      Get answers
                    </small>

                  </span>

                </button>


                <button
                  onClick={() =>
                    setQuestion(
                      "Summarize the document."
                    )
                  }
                >

                  <span className="quick-icon">
                    ▤
                  </span>


                  <span>

                    <strong>
                      Summarize
                    </strong>

                    <small>
                      Summarize content
                    </small>

                  </span>

                </button>


                <button
                  onClick={() =>
                    setQuestion(
                      "Extract the key information from the document."
                    )
                  }
                >

                  <span className="quick-icon">
                    ▦
                  </span>


                  <span>

                    <strong>
                      Extract info
                    </strong>

                    <small>
                      Find key info
                    </small>

                  </span>

                </button>


              </div>


            </div>


            <div className="welcome-footer">

              AI responses may not always be accurate.
              Please verify important information.

            </div>


          </section>


        ) : (


          /* ==================================================
             CONVERSATION
             ================================================== */

          <section className="conversation-screen">


            <div
              className="conversation-messages"
              ref={messagesContainerRef}
            >


              {messages.map(
                message => (

                  <div
                    className="conversation-block"
                    key={message.id}
                  >


                    {/* USER — show only text the user actually typed.
                        A previous prompt may be reused internally for a
                        PDF-only message, but it must never be displayed
                        as if the user typed it again. */}
                    {message.question && (
                      <div className="user-row">

                        <div className="user-avatar-chat">
                        </div>


                        <div className="user-message">
                          {message.question}
                        </div>

                        <button
                          className="user-copy-button"
                          onClick={() =>
                            copyAssistantResponse(
                              message.question
                            )
                          }
                          type="button"
                          title="Copy prompt"
                        >
<svg
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                              aria-hidden="true"
                            >
                              <rect
                                x="9"
                                y="9"
                                width="11"
                                height="11"
                                rx="2"
                                stroke="currentColor"
                                strokeWidth="2"
                              />
                              <path
                                d="M6 15H5C3.89543 15 3 14.1046 3 13V5C3 3.89543 3.89543 3 5 3H13C14.1046 3 15 3.89543 15 5V6"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                              />
                            </svg>
                          </button>

                      </div>
                    )}


                    {/* ASSISTANT */}

                    <div className="assistant-row">

                      <div className="assistant-icon">
                        R
                      </div>


                      <div className="assistant-content">


                        <div className="assistant-name">
                          RAG Assistant
                        </div>


                        {message.status === "thinking" ? (
                          <div className="thinking">
                            <div className="thinking-dots">
                              <span />
                              <span />
                              <span />
                            </div>
                            Thinking...
                          </div>
                        ) : message.status === "error" ? (
                          <div className="assistant-answer">
                            {message.error || "Unable to get an answer."}
                          </div>
                        ) : (
                          <div className={`assistant-answer ${message.status === "typing" ? "typing" : ""}`}>
                            {renderAssistantAnswer(message.answer)}
                          </div>
                        )}

                        {message.status !== "thinking" && (
                          <button
                            className="assistant-copy-button"
                            onClick={() =>
                              copyAssistantResponse(
                                message.status === "error"
                                  ? (message.error || "Unable to get an answer.")
                                  : (message.answer || "")
                              )
                            }
                            type="button"
                            title="Copy response"
                          >
<svg
                              width="16"
                              height="16"
                              viewBox="0 0 24 24"
                              fill="none"
                              xmlns="http://www.w3.org/2000/svg"
                              aria-hidden="true"
                            >
                              <rect
                                x="9"
                                y="9"
                                width="11"
                                height="11"
                                rx="2"
                                stroke="currentColor"
                                strokeWidth="2"
                              />
                              <path
                                d="M6 15H5C3.89543 15 3 14.1046 3 13V5C3 3.89543 3.89543 3 5 3H13C14.1046 3 15 3.89543 15 5V6"
                                stroke="currentColor"
                                strokeWidth="2"
                                strokeLinecap="round"
                              />
                            </svg>
                          </button>
                        )}


                        {/* ATTACHMENTS */}

                        {message.attachments?.length > 0 && (

                          <div className="message-attachments">

                            {message.attachments.map(
                              (file, index) => (

                                <div
                                  className="message-attachment"
                                  key={index}
                                >

                                  <span>
                                    {file.name}
                                  </span>

                                </div>

                              )
                            )}

                          </div>

                        )}


                        {/* SOURCES */}

                        {message.sources?.length > 0 && (

                          <div className="conversation-sources">


                            <strong>
                              Sources
                            </strong>


                            {message.sources.map(
                              (source, index) => (

                                <div
                                  className="conversation-source"
                                  key={index}
                                >

                                  <span>
                                    PDF
                                  </span>


                                  <div>

                                    <strong>
                                      {
                                        source.filename ||
                                        selectedDocument?.filename ||
                                        "Document"
                                      }
                                    </strong>


                                    <small>

                                      Page{" "}

                                      {(
                                        source.page ??
                                        0
                                      ) + 1}

                                    </small>

                                  </div>


                                  <small>

                                    {(
                                      (
                                        source.score ||
                                        0
                                      ) * 100
                                    ).toFixed(1)}

                                    %

                                  </small>

                                </div>

                              )
                            )}

                          </div>

                        )}

                      </div>

                    </div>


                  </div>

                )
              )}


              <div
                ref={chatEndRef}
              />


            </div>


            {/* ==================================================
                CONVERSATION INPUT
                ================================================== */}

            <div className="conversation-input-wrapper">


              {chatError && (

                <div className="main-chat-error">
                  {chatError}
                </div>

              )}


              {/* ATTACHMENTS */}

              {attachedFiles.length > 0 && (

                <div className="attachment-preview-list">

                  {attachedFiles.map(
                    (file, index) => (

                      <div
                          className="attachment-preview"
                          key={`${file.name}-${index}`}
                        >

                          <span className="attachment-type">
                            <span className="attachment-circle">
                              {getFileIcon(file)}
                            </span>
                          </span>

                          <span className="attachment-file-details">
                            <strong className="attachment-name">
                              {file.name}
                            </strong>

                            <small>
                              {file.type?.startsWith("image/")
                                ? "IMAGE"
                                : file.name?.toLowerCase().endsWith(".pdf")
                                  ? "PDF"
                                  : "FILE"}
                            </small>
                          </span>

                          <button
                            className="attachment-remove"
                            onClick={() =>
                              removeAttachment(
                                index
                              )
                            }
                            aria-label="Remove attachment"
                          >
                            ×
                          </button>

                        </div>

                    )
                  )}

                </div>

              )}


              <div className="rag-input">


                <div className="plus-wrapper">

                  <button
                    className="plus-button"
                    onClick={() =>
                      setAttachmentMenuOpen(
                        previous =>
                          !previous
                      )
                    }
                  >
                    +
                  </button>


                  {attachmentMenuOpen && (

                    <div className="attachment-popup">


                      <button
                        className="attachment-option"
                        onClick={
                          openAttachmentSelector
                        }
                      >

                        <span className="option-icon">
                          🖼
                        </span>

                        <span>

                          <strong>
                            Add photos
                          </strong>

                          <small>
                            Choose images from your computer
                          </small>

                        </span>

                      </button>


                      <button
                        className="attachment-option"
                        onClick={
                          openAttachmentSelector
                        }
                      >

                        <span className="option-icon">
                          📎
                        </span>

                        <span>

                          <strong>
                            Add files
                          </strong>

                          <small>
                            Upload from your computer
                          </small>

                        </span>

                      </button>


                    </div>

                  )}

                </div>


                <input
                  className="chat-text-input"
                  value={question}
                  onChange={
                    event =>
                      setQuestion(
                        event.target.value
                      )
                  }
                  onKeyDown={
                    handleQuestionKeyDown
                  }
                  placeholder="Ask anything..."
                  disabled={false}
                />


                <button
                  className={
                    `send-button ${
                      question.trim()
                        ? "active"
                        : ""
                    }`
                  }
                  onClick={
                    handleAskQuestion
                  }
                  disabled={
                      !question.trim() &&
                      !attachedFiles.some(file =>
                        file?.name?.toLowerCase().endsWith(".pdf") ||
                        file?.type?.startsWith("image/")
                      )
                    }
                >

                  ➤

                </button>


              </div>


            </div>


          </section>

        )}

      </main>

    </div>

  );

}


export default App;
