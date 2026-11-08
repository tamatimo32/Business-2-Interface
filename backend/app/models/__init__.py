"""Import every model so Alembic and SQLAlchemy see the complete metadata."""

from app.models.administration import AppSetting, AuditEvent, Backup
from app.models.conversation import Conversation, ConversationDocument
from app.models.document import Document, DocumentChunk
from app.models.generation import GenerationRun
from app.models.job import Job
from app.models.message import Message, MessageSource
from app.models.search import WebSearchRequest, WebSearchResult
from app.models.session import AuthSession
from app.models.user import User

__all__ = [
    "AppSetting",
    "AuditEvent",
    "AuthSession",
    "Backup",
    "Conversation",
    "ConversationDocument",
    "Document",
    "DocumentChunk",
    "GenerationRun",
    "Job",
    "Message",
    "MessageSource",
    "User",
    "WebSearchRequest",
    "WebSearchResult",
]
