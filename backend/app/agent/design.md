# Agent 服务设计

## 技术选型决策

### 框架：不使用 LangGraph，使用纯 FastAPI + DB 状态机

**决策原因：**
- 流程严格线性，无多 Agent 协作、无动态分支，不需要 LangGraph 的图调度能力
- LangGraph checkpointer 会引入第二套状态存储，与现有 `conversations.stage` 字段重复
- SSE 流式输出与 LangGraph 集成有额外复杂度
- 用 DB `stage` 字段驱动状态机，实现最简、调试最易

**仍然使用 LangChain 的部分：**
- `langchain_core.messages`：消息格式封装（HumanMessage / AIMessage / SystemMessage）
- `langchain_core.prompts`：提示词模板管理
- LangChain 社区工具链（如检索器封装、向量检索集成等）

---

## 整体架构

```
用户输入 → FastAPI → 查询 stage → 路由到对应处理函数 → LLM/检索 → 更新 stage → 返回
```

---

## 六状态流程

```
s1_collecting → s1_confirming → s2_searching → s3_collecting → s3_confirming → s4_generating → s4_done
```

### S1：案情收集（s1_collecting）
- LLM 引导用户描述刑事案件，每次只问一个问题
- 信息足够后，生成客观案情概述
- 进入 s1_confirming，等待用户确认

### [卡点1] S1 确认（s1_confirming）
- 展示案情概述，询问用户是否有误
- 用户确认无误 → 进入 s2_searching
- 用户指出有误 → 回到 s1_collecting 继续补充

### S2：罪名检索（s2_searching）
- 自动执行，无对话
- 输入：S1 案情概述
- 生成 5 种检索词：vector / bm25 / kg / query2doc / hyde
- 执行混合检索，返回：可能罪名 + 相关法条 + 类似案例
- 完成后自动进入 s3_collecting

### S3：量刑情节收集（s3_collecting）
- LLM 根据 S2 检索结果，针对性追问量刑相关细节
- 聚焦对量刑影响最大的情节（自首、赔偿、受害者过错等）
- 信息足够后，生成量刑情节摘要
- 进入 s3_confirming，等待用户确认

### [卡点2] S3 确认（s3_confirming）
- 展示量刑情节摘要，询问用户是否有遗漏或偏差
- 用户确认无误 → 进入 s4_generating（触发报告生成）
- 用户指出有误 → 回到 s3_collecting 继续补充

### S4：风险报告（s4_generating / s4_done）
- 自动执行，无对话
- 输入：S1 概述 + S2 检索结果 + S3 量刑情节
- 生成完整风险评估报告

---

## 数据库表

### conversations
- id, user_id, title
- stage: s1_collecting / s1_confirming / s2_searching / s3_collecting / s3_confirming / s4_generating / s4_done
- facts_json

### messages
- id, conversation_id, role, content

### stage_confirmations
- id, conversation_id
- stage: s1_confirm / s2_search / s3_confirm / s4_report
- input_data, output_data
- is_confirmed

---

## 对话管理

- 线性对话，消息按顺序存储
- 撤回：删除该消息及之后的所有消息

---

## 接口

- POST /sessions - 创建会话
- GET /sessions/{id}/state - 查询状态
- POST /sessions/{id}/message - 发送消息（SSE）
- POST /sessions/{id}/confirm - 用户确认卡点
- POST /sessions/{id}/recall - 撤回
- GET /conversations - 会话列表
- GET /conversations/{id}/messages - 消息历史
