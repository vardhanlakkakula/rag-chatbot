# 🤖 RAG Chatbot

An AI-powered conversational document assistant that uses **Retrieval-Augmented Generation (RAG)** to answer questions from uploaded documents while maintaining conversational context.

Users can upload documents, ask questions, continue conversations with follow-up questions, and interact with the assistant through a modern web interface.

---

## 🚀 Live Demo

👉 **[Try the RAG Chatbot](https://rag-chatbot-1-9ld0.onrender.com)**

## 📂 GitHub Repository

👉 **[View Source Code](https://github.com/vardhanlakkakula/rag-chatbot)**

---

## ✨ Features

- 📄 Upload and process PDF documents
- 🔎 Semantic document search
- 🤖 AI-powered document question answering
- 💬 Conversational chat with conversation history
- 🔄 Context-aware follow-up questions
- 🧠 Handles informal language, spelling mistakes, and abbreviations
- 📚 Document-grounded responses
- 👤 User registration and authentication
- 🔐 JWT-based authentication
- 🔑 Google authentication
- ✉️ Email verification
- 🔁 Forgot-password and password-reset functionality
- 🛡️ Password history and password-reuse prevention
- 💾 Persistent conversations and messages
- 📌 Pin conversations
- 🌐 Deployed frontend and backend
- 📧 Transactional emails using Brevo

---

## 🏗️ System Architecture

```text
                         ┌─────────────────────┐
                         │      User           │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ React + Vite        │
                         │ Frontend            │
                         └──────────┬──────────┘
                                    │
                               REST API
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ FastAPI Backend     │
                         └──────────┬──────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
      ┌─────────────┐       ┌──────────────┐       ┌──────────────┐
      │ PostgreSQL  │       │ Document     │       │ Authentication│
      │ Database    │       │ Processing   │       │ & Security    │
      └─────────────┘       └──────┬───────┘       └──────────────┘
                                    │
                                    ▼
                              ┌──────────────┐
                              │ Embeddings   │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   Qdrant     │
                              │ Vector DB    │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │    Gemini    │
                              │     LLM      │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │ AI Response  │
                              └──────────────┘
```

## 🔄 How It Works

### 1. User Authentication

Users can create an account or sign in using:

- Email and password
- Google authentication

Authentication is handled using JWT-based security.

### 2. Document Upload

Users upload PDF documents through the web interface.

The backend processes the document and extracts its text using **PyMuPDF**.

### 3. Text Processing

Extracted document text is cleaned and divided into smaller chunks suitable for semantic retrieval.

### 4. Embeddings

The document chunks and user queries are converted into vector representations.

### 5. Vector Search

The generated vectors are stored and searched using **Qdrant** to retrieve the most relevant document information.

### 6. AI Generation

Relevant document context is provided to **Google Gemini**, which generates the final response.

### 7. Conversational Context

Previous messages are used to understand follow-up questions such as:

> "Why is it important?"

or

> "Explain the second point."

This allows the chatbot to maintain a natural conversation instead of treating every question independently.

---

## 🧰 Tech Stack

### Frontend

- React
- Vite
- JavaScript
- HTML
- CSS

### Backend

- Python
- FastAPI
- REST APIs
- Pydantic
- PyMuPDF

### AI / Machine Learning

- Google Gemini
- Embeddings
- Retrieval-Augmented Generation (RAG)
- Semantic Search

### Vector Database

- Qdrant

### Database

- PostgreSQL
- SQLAlchemy
- Alembic

### Authentication & Security

- JWT
- Google OAuth / Google Identity Services
- Password hashing
- Email verification
- Password reset
- Password history

### Email

- Brevo Email API

### Deployment

- Render

### Version Control

- Git
- GitHub

---

## 📁 Project Structure

```text
rag-chatbot/
│
├── backend/
│   ├── auth/
│   ├── chat/
│   ├── database/
│   ├── documents/
│   ├── rag/
│   ├── migrations/
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── index.html
│   └── package.json
│
├── alembic.ini
├── .gitignore
└── README.md
```

---

## 🔐 Authentication Flow

The application provides a complete authentication system.

```text
Registration
     │
     ▼
Email Verification
     │
     ▼
Account Login
     │
     ├──────────────► Google Authentication
     │
     ▼
JWT Authentication
     │
     ▼
Protected Application
```

### Password Recovery

```text
Forgot Password
      │
      ▼
Reset Email
      │
      ▼
Secure Reset Token
      │
      ▼
Reset Password
      │
      ▼
Password History Validation
      │
      ▼
Password Updated
```

---

## 💬 Conversational RAG

The chatbot is designed to understand natural conversational language.

For example:

```text
User:
What is the primary mirror?

Assistant:
The primary mirror is ...

User:
Why is it so large?

Assistant:
"It" is understood as referring to the primary mirror.
```

The system can also handle:

- Spelling mistakes
- Informal wording
- Abbreviations
- Repeated letters
- Incomplete sentences
- Follow-up questions
- Summaries
- Explanations
- Transformations
- Question generation

---

## 📄 Document Grounding

For document-related questions, the assistant uses information retrieved from the selected document as the factual source.

The system is designed to avoid inventing information that is not supported by the available document context.

If the required information cannot be found, the assistant can indicate that the information is unavailable in the provided document.

---

## ⚙️ Local Development

### Prerequisites

Make sure you have installed:

- Python 3.11+
- Node.js
- npm
- PostgreSQL
- Git

---

## 🔧 Backend Setup

### Clone the Repository

```bash
git clone https://github.com/vardhanlakkakula/rag-chatbot.git
cd rag-chatbot
```

### Create and Activate a Virtual Environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### Run the Backend

```bash
uvicorn backend.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

---

## 🌐 Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

## 🔑 Environment Variables

Create your environment configuration locally.

Example:

```env
DATABASE_URL=your_database_url

GEMINI_API_KEY=your_gemini_api_key

QDRANT_URL=your_qdrant_url
QDRANT_API_KEY=your_qdrant_api_key

JWT_SECRET_KEY=your_secret_key

GOOGLE_CLIENT_ID=your_google_client_id

BREVO_API_KEY=your_brevo_api_key

SMTP_FROM_EMAIL=your_verified_sender_email

FRONTEND_URL=http://localhost:5173
```

> ⚠️ Never commit `.env` files, API keys, passwords, database credentials, or other secrets to GitHub.

For production deployment, configure environment variables directly in your hosting platform.

---

## 🔌 API Overview

### Authentication

```text
POST /auth/register
POST /auth/login
POST /auth/google
GET  /auth/me
GET  /auth/verify-email
POST /auth/forgot-password
POST /auth/reset-password
```

### Documents

```text
GET  /documents
POST /documents
```

### Conversations

```text
GET  /chat/conversations
```

Additional chat and document endpoints are available in the backend implementation.

---

## ☁️ Deployment

The application is deployed using:

- **Frontend:** Render
- **Backend:** Render
- **Database:** PostgreSQL
- **Vector Database:** Qdrant
- **LLM:** Google Gemini
- **Transactional Email:** Brevo

### Live Application

👉 [**Open RAG Chatbot**](https://rag-chatbot-1-9ld0.onrender.com)

---

## 🛡️ Security

The application includes several security mechanisms:

- JWT authentication
- Password hashing
- Email verification
- Secure password-reset tokens
- Password-reset token expiration
- Password history validation
- Password-reuse prevention
- Protected API endpoints
- Environment-based secret management

---

## 🎯 Project Goals

The project demonstrates how modern AI application components can be combined to build a production-style conversational document assistant.

The main focus areas are:

- Generative AI
- Retrieval-Augmented Generation
- Semantic search
- Vector databases
- Conversational AI
- REST API development
- Authentication and authorization
- Cloud deployment

---

## 🔮 Future Improvements

Possible future enhancements include:

- ⚡ Faster response generation
- 🔄 Streaming AI responses
- 📊 Improved retrieval evaluation
- 📑 Support for additional document formats
- 🧠 Advanced conversation memory
- 📈 Usage analytics
- 🗂️ Improved document management
- 🔍 Advanced search and filtering
- 📱 Improved mobile experience

---

## 👨‍💻 Author

**Vardhan Lakkakula**

B.Tech — Computer Science & Engineering (AI & ML)

### Connect

- GitHub: [vardhanlakkakula](https://github.com/vardhanlakkakula)

---

## ⭐ If You Find This Project Useful

Consider giving the repository a ⭐ on GitHub.

### Repository

[https://github.com/vardhanlakkakula/rag-chatbot](https://github.com/vardhanlakkakula/rag-chatbot)
