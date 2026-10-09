# 统计相关模型

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """数据统计概览"""
    total_crimes: int = Field(description="罪名总数", examples=[202])
    total_articles: int = Field(description="法条总数", examples=[183])
    total_relations: int = Field(description="知识图谱关系总数", examples=[23561])
    total_cases: int = Field(description="案例总数", examples=[5000])
    top_crimes: list[tuple[str, int]] = Field(default=[], description="高频罪名 Top10")
    top_articles: list[tuple[str, int]] = Field(default=[], description="高频引用法条 Top10")
    kg_loaded: bool = Field(description="知识图谱是否已加载")
    vectors_loaded: bool = Field(description="向量数据是否已加载")
