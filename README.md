# Document Intelligence 

Document Intelligence is a full-stack AI application that allows users to interact with documents using Large Language Models. The system processes documents, stores embeddings in a vector database, and enables intelligent querying and analysis through an AI-powered backend.

The project combines **LLM capabilities, vector search, and a modern web interface** to create an intelligent document understanding system.

---

# 🚀 Features

- 📄 Intelligent document processing
- 🤖 AI-powered document querying
- 🔍 Semantic search using vector embeddings
- 🧠 LLM integration for intelligent responses
- 🔐 User authentication system
- ⚡ Modern React frontend interface
- 💾 Vector database for efficient retrieval

---

# 🏗️ Project Architecture

```
User
│
▼
Frontend (React + Vite)
│
▼
Backend API (Python)
│
├── Authentication
├── LLM Client
├── Document Services
│
▼
Vector Database (ChromaDB)
│
▼
LLM Response
```
---

# 📂 Project Structure

```
Document_Intelligence
│
├── backend
│ ├── app
│ │ ├── services
│ │ ├── auth.py
│ │ ├── llm_client.py
│ │ ├── main.py
│ │ ├── schemas.py
│ │ └── settings.py
│ │
│ ├── chroma_data
│ ├── create_user.py
│ └── requirements.txt
│
├── frontend
│ ├── public
│ ├── src
│ ├── index.html
│ ├── package.json
│ └── vite.config.js
│
└── README.md
```

---

# 🛠️ Tech Stack

### Backend
- Python
- FastAPI
- ChromaDB
- LLM API Integration

### Frontend
- React
- Vite
- JavaScript

### AI / Data Processing
- Vector Embeddings
- Retrieval Augmented Generation (RAG)

---

# ⚙️ Installation

## 1️⃣ Clone the repository

```bash
git clone https://github.com/krishnasbaral/Document_Intelligence.git
cd Document_Intelligence
Backend Setup

Install dependencies:

cd backend
pip install -r requirements.txt

Run the backend server:

python app/main.py
Frontend Setup

Install dependencies:

cd frontend
npm install

Run the frontend:

npm run dev
🔑 Environment Configuration

Create a .env file in the backend and add required API keys:

OPENAI_API_KEY=your_api_key

(or the LLM provider you are using)

📌 Example Workflow

1️⃣ User logs into the system
2️⃣ Uploads or selects documents
3️⃣ Documents are converted into embeddings
4️⃣ Embeddings are stored in ChromaDB
5️⃣ User asks questions about the documents
6️⃣ The system retrieves relevant chunks and sends them to the LLM
7️⃣ The LLM generates an intelligent answer
