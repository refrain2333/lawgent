# Agent 接口请求/响应模型
from typing import Literal

from pydantic import BaseModel, Field


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


class ChecklistItem(BaseModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    question: str = Field(min_length=1)
    importance: Literal["high", "medium", "low"]


class SentencingChecklist(BaseModel):
    crime: str = Field(min_length=1)
    checklist: list[ChecklistItem] = Field(min_length=1)


class LegalBasis(BaseModel):
    article: str
    content: str
    applicability: str


class SentencingFactor(BaseModel):
    item: str
    detail: str
    basis: str
    effect: str


class SentencingFactors(BaseModel):
    favorable: list[SentencingFactor]
    unfavorable: list[SentencingFactor]


class SentenceEstimate(BaseModel):
    range: str
    basis: str
    probation_chance: Literal["高", "中", "低"]
    probation_basis: str


class RiskAssessment(BaseModel):
    level: Literal["高", "中", "低"]
    basis: str


class SimilarCase(BaseModel):
    accusations: str
    sentence_months: int | None = Field(default=None, ge=0)
    death_penalty: bool = False
    life_imprisonment: bool = False
    reference: str


class DefenseSuggestion(BaseModel):
    direction: str
    basis: str
    priority: Literal["high", "medium", "low"]


class DataQuality(BaseModel):
    level: Literal["高", "中", "低"]
    missing: list[str]
    note: str


class RiskReport(BaseModel):
    crime: str = Field(min_length=1)
    crime_basis: str = Field(min_length=1)
    legal_basis: list[LegalBasis]
    sentence_range: str
    factors: SentencingFactors
    sentence_estimate: SentenceEstimate
    conviction_risk: RiskAssessment
    similar_cases: list[SimilarCase]
    defense_suggestions: list[DefenseSuggestion]
    data_quality: DataQuality
    disclaimer: str
