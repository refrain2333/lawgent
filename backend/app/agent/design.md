# Agent 服务设计

## 技术选型

### 不使用 LangGraph，改用 FastAPI + 数据库状态机

原因：

- 流程是严格线性的，没有多 Agent 协作或动态分支，用不到 LangGraph 的图调度能力。
- LangGraph 的 checkpointer 会引入第二套状态存储，和已有的 `conversations.stage` 字段重复。
- SSE 流式输出与 LangGraph 集成会额外增加复杂度。

因此直接用数据库的 `stage` 字段驱动状态机，实现更简单，调试也更直接。

仍然沿用 LangChain 的部分：

- `langchain_core.messages`：消息格式封装（HumanMessage / AIMessage / SystemMessage）
- `langchain_core.prompts`：提示词模板管理

## 整体流程

```text
用户输入 → FastAPI → 查询 stage → 路由到对应处理函数 → LLM / 检索 → 更新 stage → 返回
```

## 状态流转

```text
s1_collecting → s1_confirming → s2_searching → s3_collecting → s3_confirming → s4_generating → s4_done
```

出错分支：`s2_failed`、`s4_failed`。

### S1 案情收集（s1_collecting）

- LLM 引导用户描述案情，每次只问一个问题。
- 信息足够后生成客观的案情概述，进入 `s1_confirming` 等待确认。

### 卡点一：S1 确认（s1_confirming）

- 展示案情概述，请用户核对。
- 确认无误 → `s2_searching`；用户指出问题 → 回到 `s1_collecting` 继续补充。

### S2 罪名检索（s2_searching）

- 自动执行，无对话。
- 输入为 S1 的案情概述，生成多种检索词（vector / bm25 / kg / query2doc / hyde）。
- 混合检索后返回：可能罪名、相关法条、相似案例，以及量刑要素清单。
- 完成后进入 `s3_collecting`。

### S3 量刑情节收集（s3_collecting）

- LLM 结合 S2 的检索结果与清单，追问量刑相关细节（自首、赔偿、受害人过错等）。
- 信息足够后生成量刑情节摘要，进入 `s3_confirming` 等待确认。

### 卡点二：S3 确认（s3_confirming）

- 展示量刑情节摘要，请用户核对是否有遗漏或偏差。
- 确认无误 → `s4_generating`（触发报告生成）；用户指出问题 → 回到 `s3_collecting`。

### S4 风险报告（s4_generating / s4_done）

- 自动执行，无对话。
- 输入为 S1 概述、S2 检索结果、S3 量刑情节，生成结构化风险评估报告。

## 数据库表

- `conversations`：`id`、`user_id`、`title`、`stage`
- `messages`：`id`、`conversation_id`、`role`、`content`、`stage`
- `stage_confirmations`：`id`、`conversation_id`、`stage`、`input_data`、`output_data`

## 对话管理

- 线性对话，消息按顺序存储。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/sessions` | 创建会话 |
| GET | `/sessions/{thread_id}/state` | 查询会话状态 |
| POST | `/sessions/{thread_id}/message` | 发送消息（SSE） |
| POST | `/sessions/{thread_id}/advance` | 推进阶段 |
| POST | `/sessions/{thread_id}/confirm` | 确认当前阶段 |
| GET | `/sessions/{thread_id}/report` | 获取 S4 风险评估报告 |
| GET | `/conversations` | 会话列表 |
| GET | `/conversations/{thread_id}/messages` | 会话历史消息 |
| DELETE | `/conversations/{thread_id}` | 删除会话 |

