# 搜索相关模型
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ArticleResult(BaseModel):
    """法条搜索结果"""
    id: str = Field(description="法条ID", examples=["article_234"])
    article_number: Optional[int] = Field(default=None, description="法条编号", examples=[234])
    title: str = Field(description="法条标题", examples=["中华人民共和国刑法 第234条"])
    chapter: Optional[str] = Field(default=None, description="所属章节", examples=["第二章 危害人身安全罪"])
    content: Optional[str] = Field(default=None, description="法条完整内容")
    similarity: float = Field(description="相似度/得分", examples=[0.85])


class CaseResult(BaseModel):
    """案例搜索结果"""
    id: str = Field(description="案例ID", examples=["case_000001"])
    case_id: Optional[str] = Field(default=None, description="案例编号", examples=["000001"])
    accusations: list[str] = Field(default=[], description="指控罪名列表", examples=[["故意伤害罪"]])
    relevant_articles: list[int] = Field(default=[], description="相关法条编号列表", examples=[[234, 233]])
    criminals: list[str] = Field(default=[], description="涉案人员", examples=[["张某某"]])
    sentence_months: Optional[int] = Field(default=None, description="刑期(月)", examples=[12])
    fine_amount: Optional[int] = Field(default=None, description="罚金(元)", examples=[5000])
    death_penalty: bool = Field(default=False, description="是否死刑")
    life_imprisonment: bool = Field(default=False, description="是否无期徒刑")
    fact: Optional[str] = Field(default=None, description="案件事实摘要")
    similarity: float = Field(description="相似度/得分", examples=[0.78])


class SearchPathResult(BaseModel):
    """单路搜索结果"""
    articles: list[ArticleResult] = Field(default=[], description="法条结果列表")
    cases: list[CaseResult] = Field(default=[], description="案例结果列表")


class SearchRequest(BaseModel):
    """融合搜索请求体：每路独立传入查询文本，空字符串表示跳过该路"""
    vector: str = Field(default="", description="向量语义检索文本（原始查询）", examples=["我朋友被人拿刀划伤了"])
    bm25: str = Field(default="", description="BM25关键词检索文本（提取的关键词）", examples=["故意伤害 刀伤"])
    kg: str = Field(default="", description="知识图谱检索文本（识别出的罪名）", examples=["故意伤害罪"])
    query2doc: str = Field(default="", description="Query2Doc检索文本（原查询+增强片段拼接）", examples=["故意伤害罪 使用器械造成轻伤"])
    hyde: str = Field(default="", description="HyDE检索文本（假设性法律回答）", examples=["依据第234条，故意伤害他人身体处三年以下有期徒刑"])
    count: int = Field(default=5, ge=1, le=20, description="每路及最终融合结果各返回的最大数量")

    @model_validator(mode="after")
    def at_least_one_path(self) -> "SearchRequest":
        if not any([self.vector, self.bm25, self.kg, self.query2doc, self.hyde]):
            raise ValueError("至少需要提供一条路的查询文本")
        return self


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str = Field(description="搜索关键词", examples=["故意伤害"])
    articles: list[ArticleResult] = Field(default=[], description="RRF融合后的法条结果列表")
    cases: list[CaseResult] = Field(default=[], description="RRF融合后的案例结果列表")
    total_articles: int = Field(description="法条数量", examples=[5])
    total_cases: int = Field(description="案例数量", examples=[5])
    elapsed_ms: float = Field(description="搜索耗时(毫秒)", examples=[120.5])
    paths: dict[str, SearchPathResult] = Field(
        default={},
        description="各路独立搜索结果（保留字段，当前版本为空）",
    )
