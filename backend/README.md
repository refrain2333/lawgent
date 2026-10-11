# 后端服务

FastAPI 实现的 LawGent 后端，包含 Agent 流程、混合检索与数据服务。

## 技术栈

- Web 框架：FastAPI
- 向量检索：Lawformer（768 维向量）
- 关键词检索：BM25
- 知识图谱：NetworkX
- LLM：DeepSeek（OpenAI 兼容接口）
- Agent 编排：LangChain
- 数据库：PostgreSQL（pgvector）
- 数据存储：向量数据（pkl）+ 知识图谱（pkl）

## 目录结构

```text
backend/
├── app/
│   ├── api/            # 路由层（v1/ 下为业务接口）
│   ├── agent/          # S1-S4 业务逻辑与提示词
│   ├── services/       # 检索、会话、图谱等服务
│   ├── models/         # 数据模型
│   ├── schemas/        # 请求/响应模型
│   ├── db/             # 数据加载与数据库连接
│   ├── infrastructure/ # LLM、Lawformer 等外部组件封装
│   └── core/           # 配置、日志、依赖
├── alembic/            # 数据库迁移
├── tests/              # 测试
├── tools/              # 辅助脚本
├── pyproject.toml
└── main.py             # 启动入口
```

## 主要模块

**搜索服务**：向量检索（Lawformer）+ BM25 + 知识图谱增强，再做融合排序。

**Agent 服务**：四阶段流程，罪名识别、信息检索、信息收集、风险评估等按阶段组织。
设计与状态流转见 `app/agent/design.md`。

**LLM 客户端**：DeepSeek API 封装与提示词模板管理。

## 开发约定

- 使用类型标注。
- 数据库操作只在 service 层进行。
- 数据库查询使用 `select() + exec()`，不用旧版 query 写法。
- Service 返回 Schema，不直接返回 Model。
- HTTP 状态码用数字（400 / 401 / 404）。
- 非必要不创建 `__init__.py`。

## 测试

测试文件按开发结构组织，命名 `test_*.py`，使用 pytest + TestClient，测试库用内存数据库。

```bash
uv run pytest
```

## 数据说明

- 刑法条文：416 条 + 向量
- 刑事案例：17,131 个
- 知识图谱：500+ 节点

数据与模型权重不在仓库中，准备方式见根目录 README。

