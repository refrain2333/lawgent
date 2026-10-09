# 数据库模型
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import JSON, Column, DateTime, Text
from sqlmodel import AutoString, Field, Relationship, SQLModel


def utc_now() -> datetime:
    """获取当前 UTC 时间"""
    return datetime.now(timezone.utc)


class BaseModel(SQLModel):
    """基础模型：包含主键和创建时间"""
    id: int | None = Field(default=None, primary_key=True, sa_column_kwargs={"comment": "主键，自增"})
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True), sa_column_kwargs={"comment": "创建时间"})


class ConversationStage(StrEnum):
    """Agent 阶段"""
    S1_COLLECTING = "s1_collecting"  # 案情收集中
    S1_CONFIRMING = "s1_confirming"  # 等待用户确认案情概述
    S2_SEARCHING  = "s2_searching"   # 罪名检索中（自动）
    S2_FAILED     = "s2_failed"      # S2 检索失败
    S3_COLLECTING = "s3_collecting"  # 量刑情节收集中
    S3_CONFIRMING = "s3_confirming"  # 等待用户确认量刑情节
    S4_GENERATING = "s4_generating"  # 风险报告生成中
    S4_DONE       = "s4_done"        # 报告已生成
    S4_FAILED     = "s4_failed"      # S4 报告生成失败


class StageType(StrEnum):
    """阶段类型"""
    S1_CONFIRM   = "s1_confirm"    # S1 案情确认
    S2_SEARCH    = "s2_search"     # S2 检索结果
    S2_CHECKLIST = "s2_checklist"  # S2 量刑要素清单
    S3_CONFIRM   = "s3_confirm"    # S3 量刑确认
    S4_REPORT    = "s4_report"     # S4 风险报告


class MessageRole(StrEnum):
    """消息角色"""
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"


class User(BaseModel, table=True):
    """用户表"""
    __tablename__ = "users"

    email: str = Field(unique=True, index=True, max_length=255, sa_column_kwargs={"comment": "用户邮箱"})
    password: str = Field(max_length=255, sa_column_kwargs={"comment": "密码哈希"})
    nickname: str | None = Field(default=None, max_length=100, sa_column_kwargs={"comment": "用户昵称"})
    avatar: str | None = Field(default=None, max_length=500, sa_column_kwargs={"comment": "头像URL"})
    updated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True, onupdate=utc_now, comment="更新时间"))

    conversations: list["Conversation"] = Relationship(back_populates="user")


class Conversation(BaseModel, table=True):
    """会话表"""
    __tablename__ = "conversations"

    user_id: int = Field(foreign_key="users.id", index=True, ondelete="CASCADE", sa_column_kwargs={"comment": "用户ID"})
    thread_id: str = Field(unique=True, index=True, max_length=255, sa_column_kwargs={"comment": "会话唯一标识"})
    title: str | None = Field(default=None, max_length=255, sa_column_kwargs={"comment": "会话标题（S1确认后生成）"})
    stage: ConversationStage = Field(default=ConversationStage.S1_COLLECTING, sa_type=AutoString, sa_column_kwargs={"comment": "当前阶段"})
    updated_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True, onupdate=utc_now, comment="更新时间"))

    user: Optional["User"] = Relationship(back_populates="conversations")
    messages: list["Message"] = Relationship(back_populates="conversation", cascade_delete=True)
    stage_confirmations: list["StageConfirmation"] = Relationship(back_populates="conversation", cascade_delete=True)


class Message(BaseModel, table=True):
    """消息表"""
    __tablename__ = "messages"

    conversation_id: int = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE", sa_column_kwargs={"comment": "会话ID"})
    role: MessageRole = Field(sa_type=AutoString, sa_column_kwargs={"comment": "消息角色"})
    content: str = Field(sa_column=Column(Text, nullable=False, comment="消息内容"))
    stage: ConversationStage = Field(default=ConversationStage.S1_COLLECTING, sa_type=AutoString, sa_column_kwargs={"comment": "消息所属阶段"})

    conversation: Optional["Conversation"] = Relationship(back_populates="messages")


class StageConfirmation(BaseModel, table=True):
    """阶段确认表：记录每个阶段的输入输出"""
    __tablename__ = "stage_confirmations"

    conversation_id: int = Field(foreign_key="conversations.id", index=True, ondelete="CASCADE", sa_column_kwargs={"comment": "会话ID"})
    stage: StageType = Field(sa_type=AutoString, sa_column_kwargs={"comment": "阶段类型"})
    input_data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, comment="输入数据（用户确认的内容/检索结果等）"))
    output_data: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, comment="输出数据（生成的摘要/报告等）"))
    is_confirmed: bool = Field(default=True, sa_column_kwargs={"comment": "是否已确认"})

    conversation: Optional["Conversation"] = Relationship(back_populates="stage_confirmations")


# 构建前向引用
User.model_rebuild()
Conversation.model_rebuild()
StageConfirmation.model_rebuild()
