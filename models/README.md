# 模型目录说明

项目所需的预训练模型文件。

## 目录结构

```
models/
├── lawformer/                    # thunlp/Lawformer 基础模型
│   ├── config.json
│   ├── pytorch_model.bin
│   ├── tokenizer.json
│   ├── tokenizer_config.json
│   └── special_tokens_map.json
└── lawformer_backbone_only.pt    # 对比学习微调权重（backbone only）
```

## 说明

- 基础模型来源：[thunlp/Lawformer](https://huggingface.co/thunlp/Lawformer)
- 微调权重：基于对比学习在刑事案例数据上微调，提升法律语义检索效果
- 向量维度：768
- 加载方式：通过 `backend/app/infrastructure/lawformer.py` 统一管理

## 配置

在 `backend/.env` 中指定路径：

```
LOCAL_MODEL_PATH=...\models\lawformer
FINETUNED_MODEL_PATH=...\models\lawformer_backbone_only.pt
```
