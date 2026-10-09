# 系统相关模型
from pydantic import BaseModel, Field


class SystemInfo(BaseModel):
    """系统信息"""
    name: str = Field(description="系统名称", examples=["刑事法律服务助手"])
    version: str = Field(description="版本号", examples=["1.0.0"])
    description: str = Field(description="系统描述", examples=["基于智能体的刑事法律服务助手"])
    status: str = Field(description="运行状态", examples=["running"])
