from pydantic import BaseModel, model_validator
from typing import List, Dict, Any, Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    collection: Optional[str] = None
    question: str
    workspace_id: Optional[str] = None
    conversation_id: Optional[str] = None  # if provided, appends to existing conversation

    @model_validator(mode="after")
    def require_collection_or_workspace(self):
        if not self.collection and not self.workspace_id:
            raise ValueError("Either 'collection' or 'workspace_id' must be provided.")
        return self


class SourceItem(BaseModel):
    id: str
    source: Optional[str] = None
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    workspace_id: Optional[str] = None
    conversation_id: Optional[str] = None  # always returned so frontend can track it


class UploadResponse(BaseModel):
    status: str
    ingested_files: List[str]


class DocListResponse(BaseModel):
    documents: List[str]


class WorkspaceCreateResponse(BaseModel):
    workspace_id: str


class WorkspaceUploadResponse(BaseModel):
    status: str
    workspace_id: str
    ingested_files: List[str]


# ---------------------------------------------------------------------------
# Conversation schemas
# ---------------------------------------------------------------------------

class ConversationSummary(BaseModel):
    id: str
    title: str
    collection: Optional[str] = None
    workspace_id: Optional[str] = None
    created_at: str
    updated_at: str
    last_message: Optional[str] = None  # snippet of last message for sidebar preview


class MessageItem(BaseModel):
    id: str
    conversation_id: str
    role: str          # "user" | "assistant"
    content: str
    sources: Optional[str] = None  # JSON string of sources list
    created_at: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    collection: Optional[str] = None
    workspace_id: Optional[str] = None
    created_at: str
    updated_at: str
    messages: List[MessageItem]


class ConversationRenameRequest(BaseModel):
    title: str


class FeedbackRequest(BaseModel):
    query: str
    answer: str
    rating: str                         # "up" or "down"
    sources: Optional[List[Dict[str, Any]]] = None
    collection: Optional[str] = None
    workspace_id: Optional[str] = None
    conversation_id: Optional[str] = None
