# 微调模型评估结果

本目录包含 Lawformer 微调模型的评估数据、脚本与可视化图表。

这里的 `evaluation_results.json`、图表和下面的数字保留自历史实验，使用旧版 Precision@K 计算口径。脚本已修正为前 K 个结果中相关结果的比例；历史数据尚未重新评估，不能把历史 Precision 数字当作修正口径下的结果。

## 文件结构

```text
evaluation_results/
├── README.md
├── evaluation_results.json     # 评估数据
├── evaluation_script.py        # 评估脚本
└── charts/                     # 可视化图表
    ├── overall_comparison.png  # 总体性能对比
    ├── by_difficulty.png       # 按难度级别对比
    ├── improvement.png         # 性能提升幅度
    └── radar.png               # 雷达图对比
```

## 核心指标速览

| 指标 | 基础模型 | 微调模型 |
| --- | --- | --- |
| MRR | 0.527 | 0.910 |
| P@1 | 0.462 | 0.846 |
| P@3 | 0.423 | 0.897 |
| Hit Rate | 84.6% | 100.0% |

评估方法为 A/B 对比测试。完整数据见 `evaluation_results.json`，图表见 `charts/`。

## 重新运行评估

```bash
python cloud_training_suite/evaluation_results/evaluation_script.py
```

前提：已完成模型微调与数据向量化，且存在推理所需的模型与向量文件。

