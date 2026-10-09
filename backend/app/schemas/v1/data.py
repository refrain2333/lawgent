# 数据浏览接口模型
from typing import Optional

from pydantic import BaseModel, Field


class ArticleItem(BaseModel):
    """法条条目"""
    article_number: int = Field(description="法条编号", examples=[264])
    title: str = Field(default="", description="法条标题")
    chapter: str = Field(default="", description="所属章节")
    content: str = Field(default="", description="法条内容摘要")


class CaseItem(BaseModel):
    """案例条目"""
    case_id: str = Field(default="", description="案例ID")
    accusations: list[str] = Field(default=[], description="罪名列表")
    fact: str = Field(default="", description="案件事实摘要")
    relevant_articles: list[str] = Field(default=[], description="相关法条")
    criminals: list[str] = Field(default=[], description="涉案人员")
    imprisonment_months: Optional[int] = Field(default=None, description="刑期月数")
    fine_amount: Optional[float] = Field(default=None, description="罚金")
    death_penalty: bool = Field(default=False, description="死刑")
    life_imprisonment: bool = Field(default=False, description="无期徒刑")


class ArticleListResponse(BaseModel):
    """法条列表"""
    items: list[ArticleItem]
    total: int
    page: int
    page_size: int


class CaseListResponse(BaseModel):
    """案例列表"""
    items: list[CaseItem]
    total: int
    page: int
    page_size: int
