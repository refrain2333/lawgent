# 知识图谱接口模型
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """图谱节点"""
    id: str = Field(description="节点唯一ID", examples=["crime_盗窃"])
    label: str = Field(description="显示标签", examples=["盗窃"])
    type: str = Field(description="节点类型: crime | article | center", examples=["crime"])
    weight: int = Field(default=1, description="节点权重（关联边数）", examples=[100])
    confidence: float = Field(default=0.0, description="置信度", examples=[0.85])


class GraphEdge(BaseModel):
    """图谱边"""
    source: str = Field(description="源节点ID", examples=["crime_盗窃"])
    target: str = Field(description="目标节点ID", examples=["article_264"])
    weight: int = Field(default=1, description="边权重（共现频次）", examples=[50])
    label: str = Field(default="", description="边标签", examples=["50案例"])


class GraphResponse(BaseModel):
    """知识图谱数据（全局 top-N）"""
    nodes: list[GraphNode] = Field(description="节点列表")
    edges: list[GraphEdge] = Field(description="边列表")
    total_crimes: int = Field(description="罪名节点总数", examples=[20])
    total_articles: int = Field(description="法条节点总数", examples=[30])
    total_edges: int = Field(description="边总数", examples=[100])


class GraphStatsResponse(BaseModel):
    """知识图谱统计信息"""
    total_crimes: int = Field(description="罪名总数", examples=[150])
    total_articles: int = Field(description="法条总数", examples=[200])
    total_relations: int = Field(description="关系总数", examples=[5000])


class GraphRelationsResponse(BaseModel):
    """实体关系图谱（ego network）"""
    center_node: GraphNode = Field(description="中心节点")
    nodes: list[GraphNode] = Field(description="所有节点（含中心节点）")
    edges: list[GraphEdge] = Field(description="边列表")
    entity_type: str = Field(description="实体类型: crime | article", examples=["crime"])


class CaseItem(BaseModel):
    """案例简要信息"""
    case_id: str = Field(default="", description="案例ID")
    fact: str = Field(default="", description="案件事实摘要")
    accusations: list[str] = Field(default=[], description="罪名列表")
    relevant_articles: list[str] = Field(default=[], description="相关法条")
    criminals: list[str] = Field(default=[], description="涉案人员")
    imprisonment_months: int | None = Field(default=None, description="刑期（月）")
    fine_amount: float | None = Field(default=None, description="罚金金额")
    death_penalty: bool = Field(default=False, description="是否死刑")
    life_imprisonment: bool = Field(default=False, description="是否无期徒刑")


class RelationCasesResponse(BaseModel):
    """罪名-法条关系案例"""
    crime: str = Field(description="罪名")
    article: str = Field(description="法条编号")
    total_found: int = Field(description="找到的案例数")
    cases: list[CaseItem] = Field(description="案例列表")
