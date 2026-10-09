# Agent 开发进度

## 当前状态：全链路实现完成，待联调测试

---

## 已完成

### 基础架构
- 技术选型：FastAPI + DB 状态机（不使用 LangGraph）
- 七状态枚举：`s1_collecting → s1_confirming → s2_searching → s3_collecting → s3_confirming → s4_generating → s4_done`
- 数据模型：`Conversation`（thread_id + title）、`Message`（含stage）、`StageConfirmation`（各阶段输入输出）
- AI 调用日志：`logs/ai/ai_{startup_ts}.jsonl` + `ai_log_to_md.py` 转换工具

### 数据库 Migrations（按顺序）
| revision | 内容 |
|---|---|
| e3f1a2b4c5d6 | 更新 stage 枚举值 |
| f4a2b3c1d5e6 | 删除 facts_json，清空测试数据 |
| a1b2c3d4e5f6 | messages 表加 stage 字段 |
| b2c3d4e5f6a1 | conversations 表加 thread_id，title 留给可读标题 |

### StageConfirmation 记录类型
| stage | 内容 |
|---|---|
| s1_confirm | output_data.summary = S1案情摘要 |
| s2_search | output_data = {queries, fused, paths, elapsed_ms} |
| s2_checklist | output_data = {crime, checklist[{key,label,question,importance}]} |
| s3_confirm | output_data.facts = S3量刑情节摘要 |
| s4_report | output_data = 完整风险评估报告JSON |

### S1 阶段（完成）
- `service/s1.py`：`chat_s1`、`chat_s1_confirming`、`generate_title`
- 提示词：`prompts/s1.md`、`prompts/s1_confirming.md`
- 确认后写入 StageConfirmation(s1_confirm)，异步生成会话标题

### S2 阶段（完成）
- `service/s2.py`：`run_s2`（5路检索）、`gen_checklist`（量刑要素清单）
- 提示词：`prompts/s2.md`（动态注入crime.txt罪名列表+少样本示例）、`prompts/s2_checklist.md`
- 写入 StageConfirmation(s2_search) + StageConfirmation(s2_checklist)
- 自动推进到 s3_collecting

### S3 阶段（完成）
- `service/s3.py`：`chat_s3`（注入S2清单，按importance优先级追问）
- 提示词：`prompts/s3.md`（注入summary + search_context + checklist）
- 确认后写入 StageConfirmation(s3_confirm)

### S4 阶段（完成）
- `service/s4.py`：`gen_report`（结构化风险报告，每项含basis依据）
- 提示词：`prompts/s4.md`
- 写入 StageConfirmation(s4_report)

### 接口清单（已实现）
- `POST /sessions` - 创建会话
- `GET /sessions/{thread_id}/state` - 查询当前阶段
- `POST /sessions/{thread_id}/message` - 发送消息（SSE，支持S1/S1_confirming/S3）
- `POST /sessions/{thread_id}/advance` - 推进阶段（s1_collecting → s1_confirming）
- `POST /sessions/{thread_id}/confirm` - 卡点确认（S1/S3）
- `GET /conversations` - 会话列表
- `GET /conversations/{thread_id}/messages` - 消息历史

---

## 待完成

### 联调测试
- 启动服务，走完完整 S1→S2→S3→S4 流程
- 验证 S2 向量检索在服务启动后有实际结果（当前测试数据为空）
- 验证 S3 advance 接口（s3_collecting → s3_confirming）

### S3 advance 接口
- 当前 ADVANCE_MAP 只有 s1_collecting → s1_confirming
- 需要补充 s3_collecting → s3_confirming

### 报告查询接口
- `GET /sessions/{thread_id}/report` - 获取S4报告

---

## 关键文件索引

| 文件 | 说明 |
|---|---|
| `app/agent/service/s1.py` | S1 对话 + 标题生成 |
| `app/agent/service/s2.py` | S2 检索 + 清单生成 |
| `app/agent/service/s3.py` | S3 量刑情节对话 |
| `app/agent/service/s4.py` | S4 风险报告生成 |
| `app/agent/service/utils.py` | LLM 流式调用、提示词加载 |
| `app/api/v1/agent.py` | 所有 Agent 接口 |
| `app/services/conversation_service.py` | 会话/消息/确认 DB 操作 |
| `app/models/models.py` | 数据模型定义 |
| `tools/ai_log_to_md.py` | AI日志转Markdown工具 |
