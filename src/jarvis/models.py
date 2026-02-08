from typing import Any, Literal, Optional
from pydantic import BaseModel


class UserMessage(BaseModel):
    id: str
    role: Literal["user"]
    agent: str


class AssistantMessage(BaseModel):
    id: str
    role: Literal["assistant"]
    parentID: Optional[str] = None


class TextPart(BaseModel):
    id: str
    type: Literal["text"]
    text: str


class PermissionRequest(BaseModel):
    id: str
    sessionID: str
    permission: str
    patterns: list[str]
    always: list[str]
    metadata: dict[str, Any]


class Session(BaseModel):
    id: str
    title: Optional[str] = None


class OutboundMessage(BaseModel):
    message_id: str
    chat_id: int
    session_id: str
    text: str
    is_command: bool = False
    command: Optional[str] = None
    arguments: str = ""
    agent: str = "plan"
    model: Optional[str] = None


class BridgeState(BaseModel):
    last_update_id: int = 0
    active_session_id: Optional[str] = None
    active_agent: str = "plan"
    active_model: Optional[str] = None
