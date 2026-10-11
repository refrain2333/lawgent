# 运行所需的外部资源

本仓库只包含**代码**。要让系统完整跑起来，还需要自行准备下面这些数据与模型文件。
它们体积较大或涉及第三方版权，因此没有放进仓库。

准备完成后，在 `backend/.env` 中把对应路径填好（可参考 `backend/.env.example`）。

## 一、检索数据（data/）

系统启动时会加载这几类数据，缺失时对应能力不可用（服务仍能启动，只是检索无结果）。
默认目录可通过 `.env` 的 `DATA_*_PATH` 调整。

| 文件 | 默认路径 | 来源 | 说明 |
| --- | --- | --- | --- |
| `criminal_articles.pkl` | `data/processed/criminal/` | [LawRefBook/Laws](https://github.com/LawRefBook/Laws) | 结构化刑法条文（条文号、标题、内容），约 416 条。 |
| `criminal_cases.pkl` | `data/processed/criminal/` | [CAIL2018](https://github.com/thunlp/CAIL) | 刑事案例（案件事实、罪名、适用法条），约 1.7 万条。 |
| `criminal_articles_vectors_finetuned.pkl` | `data/processed/vectors/` | 由上面的法条数据向量化得到 | 768 维法条向量及元数据。 |
| `criminal_cases_vectors_finetuned.pkl` | `data/processed/vectors/` | 由上面的案例数据向量化得到 | 768 维案例向量及元数据。 |
| `knowledge_graph.pkl` | `data/processed/knowledge_graph/` | 由案例中的罪名-法条共现关系构建 | 罪名与法条的关联图谱。 |

数据记录规模示例：法条约 416 条、案例约 17,131 条。字段结构可参考 `research/cloud_training_suite/` 下的说明与示例脚本。

> 处理流程（原始文本 → 结构化 → 向量化 → 图谱）见 `research/cloud_training_suite/data_pipeline/`。

## 二、罪名词表（已包含）

`data/cases/crime.txt` 是 202 行的罪名名称清单，供 S2 阶段作为罪名候选词使用。
它是纯标签词表、不涉及数据集版权，因此**已包含在仓库中**，无需另行准备。

## 三、模型

| 文件 / 目录 | 默认路径 | 来源 | 说明 |
| --- | --- | --- | --- |
| Lawformer 基础模型 | `models/lawformer/` 或 HF 缓存目录 | [thunlp/Lawformer](https://huggingface.co/thunlp/Lawformer) | 中文法律长文本预训练模型，输出 768 维向量。通过 `LOCAL_MODEL_PATH` 指定。 |
| 微调权重 | `models/lawformer_backbone_only.pt` | 本项目自行训练 | 在刑事案例数据上做三元组对比学习得到的 backbone 权重，约 482MB。通过 `FINETUNED_MODEL_PATH` 指定。 |

> `MODEL_OFFLINE_MODE=True` 时只读本地文件、不联网下载，请确保上面的文件已就位。

## 四、LLM

系统默认调用 DeepSeek（OpenAI 兼容接口）。在 `backend/.env` 中设置：

```
LLM_API_KEY=你的密钥
LLM_API_BASE=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

也可换成其他 OpenAI 兼容服务，相应修改 `LLM_API_BASE` 与 `LLM_MODEL` 即可。

## 五、数据库

PostgreSQL + pgvector，通过 `research/lawgent-db/docker-compose.yml` 启动。
默认连接串写在 `backend/.env.example` 的 `DATABASE_URL` 中。

## 六、缺失时的表现

| 缺失项 | 影响 |
| --- | --- |
| 向量文件 | 向量检索不可用 |
| 原始数据（法条/案例 pkl） | BM25 索引与内容检索不可用 |
| 知识图谱 | 图谱检索不可用 |
| Lawformer 模型 | 无法编码查询，向量检索不可用 |
| LLM 密钥 | 对话与报告生成不可用 |

各项在启动日志里都会给出加载状态，便于定位缺了哪一项。

