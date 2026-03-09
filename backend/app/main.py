import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from app.settings import settings
from app.schemas import (
    LoginRequest,
    ChatRequest,
    ChatResponse,
    UploadResponse,
    DocListResponse,
    WorkspaceCreateResponse,
    WorkspaceUploadResponse,
    ConversationSummary,
    ConversationDetail,
    MessageItem,
    ConversationRenameRequest,
    FeedbackRequest,
)
from app.auth import authenticate_user, create_access_token, require_role, resolve_collections
from app.services.chroma_store import (
    get_persistent_collection,
    get_workspace_collection,
    chroma_client,
    _sanitize_collection_name,
)
from app.services.ingest import parse_with_llamaparse, chunk_text, build_chunk_ids
from app.services.bm25_sqlite import BM25SQLite
from app.services.retrieval import hybrid_retrieve_persistent, retrieve_workspace
from app.services.analytics import append_to_csv
from app.services.conversations import ConversationStore
from app.services.feedback import FeedbackStore
from app.llm_client import get_azure_client

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    logger.info("IntelliDoc API starting — %d collections configured", len(settings.COLLECTIONS))
    yield
    logger.info("IntelliDoc API shutting down")


app = FastAPI(
    title="INTELLIDOC API",
    version="1.2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Shared service instances
# ---------------------------------------------------------------------------

bm25 = BM25SQLite(settings.BM25_SQLITE_PATH)
conv_store = ConversationStore(settings.CONVERSATIONS_DB_PATH)
feedback_store = FeedbackStore(settings.FEEDBACK_DB_PATH)


# ---------------------------------------------------------------------------
# Reusable dependencies
# ---------------------------------------------------------------------------

def valid_collection(
    collection: str = Query(...),
    user=Depends(require_role("user", "admin")),
) -> str:
    allowed = resolve_collections(user)
    if collection not in allowed:
        raise HTTPException(status_code=403, detail="Access to this collection is not allowed")
    return collection


def valid_collection_form(
    collection: str = Form(...),
    user=Depends(require_role("admin")),  # upload/delete stays admin-only
) -> str:
    allowed = resolve_collections(user)
    if collection not in allowed:
        raise HTTPException(status_code=403, detail="Access to this collection is not allowed")
    return collection


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/auth/login")
def login(body: LoginRequest):
    user = authenticate_user(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=user["username"], role=user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

@app.get("/collections")
def list_collections(user=Depends(require_role("user", "admin"))):
    return {"collections": resolve_collections(user)}


# ---------------------------------------------------------------------------
# Documents (persistent)
# ---------------------------------------------------------------------------

@app.get("/documents", response_model=DocListResponse)
def list_documents(
    collection: str = Depends(valid_collection),
    user=Depends(require_role("user", "admin")),
):
    col = get_persistent_collection(collection)
    metas = col.get(include=["metadatas"]).get("metadatas", [])
    sources = sorted(
        {(m or {}).get("source") for m in metas if (m or {}).get("source")}
    )
    return DocListResponse(documents=sources)


@app.post("/documents", response_model=UploadResponse)
async def upload_documents(
    collection: str = Depends(valid_collection_form),
    files: List[UploadFile] = File(...),
    user=Depends(require_role("admin")),
):
    col = get_persistent_collection(collection)
    safe_collection = _sanitize_collection_name(collection)
    ingested: list[str] = []

    existing = col.get(include=["metadatas"])
    existing_ids = existing.get("ids", [])
    existing_metas = existing.get("metadatas", [])

    for f in files:
        data = await f.read()
        text = await parse_with_llamaparse(data, f.filename)
        chunks = chunk_text(text)
        ids = build_chunk_ids(f.filename, len(chunks))
        metadatas = [{"source": f.filename, "type": f.filename} for _ in chunks]

        to_del = [
            i
            for i, m in zip(existing_ids, existing_metas)
            if (m or {}).get("source") == f.filename
        ]
        if to_del:
            col.delete(ids=to_del)
            bm25.delete_by_source(safe_collection, f.filename)

        col.add(documents=chunks, metadatas=metadatas, ids=ids)

        for doc_id, chunk in zip(ids, chunks):
            bm25.upsert_document(safe_collection, doc_id, chunk, source=f.filename)

        ingested.append(f.filename)
        logger.info("Ingested %s → %d chunks into [%s]", f.filename, len(chunks), collection)

    return UploadResponse(status="ok", ingested_files=ingested)


@app.delete("/documents/{doc_name}")
def delete_document(
    doc_name: str,
    collection: str = Depends(valid_collection),
    user=Depends(require_role("admin")),
):
    col = get_persistent_collection(collection)
    safe_collection = _sanitize_collection_name(collection)
    got = col.get(include=["metadatas"])

    ids = [
        i
        for i, m in zip(got.get("ids", []), got.get("metadatas", []))
        if (m or {}).get("source") == doc_name
    ]
    if ids:
        col.delete(ids=ids)
    bm25.delete_by_source(safe_collection, doc_name)
    logger.info("Deleted %d chunks for '%s' from [%s]", len(ids), doc_name, collection)
    return {"status": "ok", "deleted_chunks": len(ids)}


# ---------------------------------------------------------------------------
# Workspaces (temporary)
# ---------------------------------------------------------------------------

@app.post("/workspaces", response_model=WorkspaceCreateResponse)
def create_workspace(user=Depends(require_role("user", "admin"))):
    workspace_id = uuid.uuid4().hex
    get_workspace_collection(workspace_id)
    return WorkspaceCreateResponse(workspace_id=workspace_id)


@app.post("/workspaces/{workspace_id}/documents", response_model=WorkspaceUploadResponse)
async def upload_workspace_documents(
    workspace_id: str,
    files: List[UploadFile] = File(...),
    user=Depends(require_role("user", "admin")),
):
    col = get_workspace_collection(workspace_id)
    ingested: list[str] = []

    for f in files:
        data = await f.read()
        text = await parse_with_llamaparse(data, f.filename)
        chunks = chunk_text(text)
        ids = build_chunk_ids(f.filename, len(chunks))
        metadatas = [
            {"source": f.filename, "type": f.filename, "workspace_id": workspace_id}
            for _ in chunks
        ]

        got = col.get(include=["metadatas"])
        to_del = [
            i
            for i, m in zip(got.get("ids", []), got.get("metadatas", []))
            if (m or {}).get("source") == f.filename
        ]
        if to_del:
            col.delete(ids=to_del)

        col.add(documents=chunks, metadatas=metadatas, ids=ids)
        ingested.append(f.filename)

    return WorkspaceUploadResponse(
        status="ok", workspace_id=workspace_id, ingested_files=ingested,
    )


@app.delete("/workspaces/{workspace_id}")
def delete_workspace(
    workspace_id: str,
    user=Depends(require_role("user", "admin")),
):
    name = f"temp__{workspace_id}"
    try:
        chroma_client().delete_collection(name)
    except Exception:
        pass
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

@app.get("/conversations", response_model=List[ConversationSummary])
def list_conversations(user=Depends(require_role("user", "admin"))):
    """List all conversations for the current user, newest first."""
    return conv_store.list_conversations(user["username"])


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    user=Depends(require_role("user", "admin")),
):
    """Get a single conversation with its full message history."""
    if not conv_store.verify_ownership(conversation_id, user["username"]):
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = conv_store.get_conversation(conversation_id)
    messages = conv_store.get_messages(conversation_id)
    return {**conv, "messages": messages}


@app.patch("/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: str,
    body: ConversationRenameRequest,
    user=Depends(require_role("user", "admin")),
):
    """Rename a conversation."""
    if not conv_store.verify_ownership(conversation_id, user["username"]):
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv_store.update_conversation_title(conversation_id, body.title)
    return {"status": "ok"}


@app.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user=Depends(require_role("user", "admin")),
):
    """Delete a conversation and all its messages."""
    if not conv_store.verify_ownership(conversation_id, user["username"]):
        raise HTTPException(status_code=404, detail="Conversation not found")
    deleted = conv_store.delete_conversation(conversation_id)
    return {"status": "ok" if deleted else "not_found"}



# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

@app.post("/feedback")
def submit_feedback(
    body: FeedbackRequest,
    user=Depends(require_role("user", "admin")),
):
    """Store thumbs-up / thumbs-down feedback for an AI response."""
    record = feedback_store.add_feedback(
        query               = body.query,
        answer              = body.answer,
        rating              = body.rating,
        username            = user["username"],
        role                = user["role"],
        sources             = body.sources,
        collection          = body.collection,
        workspace_id        = body.workspace_id,
        conversation_id     = body.conversation_id,
        allowed_collections = user.get("allowed_collections"),
    )
    return {"status": "ok", **record}


@app.get("/feedback")
def list_feedback(
    collection: str | None = Query(None),
    rating: str | None     = Query(None),
    limit: int             = Query(100, le=500),
    user=Depends(require_role("admin")),
):
    """Admin-only: retrieve stored feedback records."""
    return feedback_store.get_feedback(
        collection=collection,
        rating=rating,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def _build_answer(question: str, context_str: str, history: list[dict] | None = None) -> str:
    """
    Call Azure OpenAI with context + optional conversation history.
    History messages are injected before the current user question so the
    model can follow multi-turn conversations.
    """
    prompt = settings.QA_PROMPT_STR.format(
        query_str=question, context_str=context_str,
    )
    azure_client, deployment_name = get_azure_client()

    messages = [{"role": "system", "content": settings.LLM_INSTRUCTION}]

    # Inject prior turns (up to last 10 messages) for conversational context
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": prompt})

    resp = azure_client.chat.completions.create(
        model=deployment_name,
        temperature=0,
        messages=messages,
    )
    return resp.choices[0].message.content or ""


def _auto_title(question: str) -> str:
    """Generate a short conversation title from the first question."""
    return question[:60] + ("…" if len(question) > 60 else "")


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user=Depends(require_role("user", "admin"))):

    # ---- Resolve or create conversation ----
    if req.conversation_id:
        # Validate ownership
        if not conv_store.verify_ownership(req.conversation_id, user["username"]):
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation_id = req.conversation_id
    else:
        # Auto-create a new conversation
        conv = conv_store.create_conversation(
            username=user["username"],
            title=_auto_title(req.question),
            collection=req.collection,
            workspace_id=req.workspace_id,
        )
        conversation_id = conv["id"]

    # Load recent history for multi-turn context (last 10 messages)
    history = conv_store.get_recent_messages(conversation_id, limit=10)

    # ---- Workspace mode ----
    if req.workspace_id:
        results = retrieve_workspace(req.workspace_id, req.question)
        context_str = "\n\n".join(r["text"][:2000] for r in results[:6])
        sources = [
            {
                "id": r["id"],
                "source": (r["metadata"] or {}).get("source"),
                "score": r["score"],
            }
            for r in results[:6]
        ]
        meta_join = ", ".join(s["id"] for s in sources) if sources else "NO_METADATA"

        answer = _build_answer(req.question, context_str, history)

        # Persist user question + assistant answer
        conv_store.add_message(conversation_id, "user", req.question)
        conv_store.add_message(
            conversation_id, "assistant", answer,
            sources=json.dumps(sources),
        )

        append_to_csv(
            f"workspace:{req.workspace_id}",
            req.question, context_str, answer, meta_join,
        )
        return ChatResponse(
            answer=answer,
            sources=sources,
            workspace_id=req.workspace_id,
            conversation_id=conversation_id,
        )

    # ---- Persistent collection mode ----
    if not req.collection or req.collection not in resolve_collections(user):
        raise HTTPException(status_code=403, detail="Access to this collection is not allowed")

    results = hybrid_retrieve_persistent(req.collection, req.question, bm25)
    context_str = "\n\n".join(r["text"][:2000] for r in results[:6])

    answer = _build_answer(req.question, context_str, history)

    sources = [
        {
            "id": r["id"],
            "source": (r["metadata"] or {}).get("source"),
            "score": r["score"],
        }
        for r in results[:6]
    ]
    meta_join = ", ".join(s["id"] for s in sources) if sources else "NO_METADATA"

    # Persist user question + assistant answer
    conv_store.add_message(conversation_id, "user", req.question)
    conv_store.add_message(
        conversation_id, "assistant", answer,
        sources=json.dumps(sources),
    )

    append_to_csv(req.collection, req.question, context_str, answer, meta_join)

    return ChatResponse(
        answer=answer,
        sources=sources,
        workspace_id=None,
        conversation_id=conversation_id,
    )
