# 第三方组件与资源声明

本项目代码采用 MIT License 开源。项目在运行中依赖或引用了下列第三方资源，
其版权与许可归属各自作者，**不在**本项目 MIT 许可覆盖范围内。
使用前请自行确认并遵守其许可条款。

## 数据集

| 名称 | 用途 | 来源 | 说明 |
| --- | --- | --- | --- |
| CAIL2018 | 刑事案例数据 | [github.com/thunlp/CAIL](https://github.com/thunlp/CAIL) | 大规模中文法律判决预测数据集，含案件事实、罪名标注与适用法条。本项目的案例检索库与 Lawformer 微调均基于此数据集。 |
| LawRefBook/Laws | 刑法条文 | [github.com/LawRefBook/Laws](https://github.com/LawRefBook/Laws) | 开源法律文本库，提供结构化的刑法条文（条文号、标题、内容）。 |

> 本项目**不再分发**上述数据集。案例与法条数据（`data/cases/`、`data/processed/`）需自行从上游获取，
> 并按各自的许可与使用条款处理。本仓库仅保留少量用于展示的示例文件。

## 模型

| 名称 | 来源 | 说明 |
| --- | --- | --- |
| thunlp/Lawformer | [huggingface.co/thunlp/Lawformer](https://huggingface.co/thunlp/Lawformer) | 中文法律长文本预训练模型（基于 Longformer），用作向量检索的底座模型，输出 768 维向量。仓库不包含权重，请从上游获取。 |

微调权重（`lawformer_backbone_only.pt`）由本项目在刑事案例数据上通过三元组对比学习训练得到，
仓库不包含该文件。

## 引用

- Chaojun Xiao, et al. **CAIL2018: A Large-Scale Legal Dataset for Judgment Prediction.** arXiv:1807.02478, 2018. https://arxiv.org/abs/1807.02478
- Haoxi Zhong, et al. **How Does NLP Benefit Legal System: A Summary of Legal Artificial Intelligence.** ACL 2020.
- Haoxi Zhong, et al. **Lawformer: A Pre-trained Language Model for Chinese Legal Long Documents.** 2021. https://huggingface.co/thunlp/Lawformer

## Python / 前端依赖

后端与前端第三方依赖（FastAPI、SQLAlchemy、LangChain、Transformers、Vue、Vite 等）
各自遵循其开源许可证，详见 `backend/pyproject.toml`、`backend/uv.lock` 与 `frontend/package.json`。

## 免责声明

本项目输出内容仅供学习、研究与辅助参考，不构成正式法律意见。

