# 第三方组件与资源声明

本项目代码采用 MIT License 开源。但项目在运行**依赖或引用**下列第三方资源，
其版权与许可归属各自作者，**不在**本项目 MIT 许可覆盖范围内。使用前请自行确认并遵守其许可条款。

## 模型

| 名称 | 来源 | 说明 |
| --- | --- | --- |
| Lawformer | [thunlp/Lawformer](https://huggingface.co/thunlp/Lawformer) | 中文法律长文本预训练语言模型，用作向量检索的底座模型。仓库不包含权重，请从上游获取。 |

微调权重（`lawformer_backbone_only.pt`）由本项目在刑事案例数据上通过对比学习训练得到，
仓库不包含该文件。

## 数据

| 名称 | 说明 |
| --- | --- |
| 裁判文书语料 | 用于构建案例检索与知识图谱的刑事案件文本。仓库不包含原始数据，请通过公开渠道自行获取。 |
| 法律法规文本 | 用于构建法条检索的法条文本。仓库不包含原始数据。 |

## Python / 前端依赖

后端与前端第三方依赖（FastAPI、SQLAlchemy、LangChain、Transformers、Vue、Vite 等）
各自遵循其开源许可证，详见 `backend/pyproject.toml`、`backend/uv.lock` 与 `frontend/package.json`。

## 免责声明

本项目输出内容仅供学习、研究与辅助参考，不构成正式法律意见。

