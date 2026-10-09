# Agent 接口请求/响应模型
from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    conversation_id: str | None = None


class MessageRequest(BaseModel):
    content: str


class ConfirmRequest(BaseModel):
    accepted: bool


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    stage: str | None = None
