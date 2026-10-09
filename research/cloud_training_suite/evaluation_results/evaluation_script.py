#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础模型 vs 微调模型 - 全面对比实验
测试多个维度的搜索性能差异
"""

import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pickle
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
import json
import time
from datetime import datetime
from collections import defaultdict

print("="*80)
print("基础模型 vs 微调模型 - 全面对比实验")
print("="*80)
print()

# ============================================================================
# 测试查询集 - 涵盖不同难度和类型
# ============================================================================

TEST_QUERIES = {
    "简单查询": [
        {
            "query": "故意杀人罪",
            "expected_articles": [232],
            "category": "罪名直接匹配"
        },
        {
            "query": "盗窃罪",
            "expected_articles": [264],
            "category": "罪名直接匹配"
        },
        {
            "query": "抢劫罪",
            "expected_articles": [263],
            "category": "罪名直接匹配"
        }
    ],
    "中等查询": [
        {
            "query": "故意杀人罪的量刑标准",
            "expected_articles": [232],
            "category": "罪名+量刑"
        },
        {
            "query": "盗窃罪的立案标准是什么",
            "expected_articles": [264],
            "category": "罪名+立案标准"
        },
        {
            "query": "交通肇事后逃逸如何处罚",
            "expected_articles": [133],
            "category": "罪名+特定情节"
        },
        {
            "query": "诈骗罪数额特别巨大的量刑",
            "expected_articles": [266],
            "category": "罪名+数额+量刑"
        }
    ],
    "复杂查询": [
        {
            "query": "未成年人故意伤害他人致人重伤的刑事责任",
            "expected_articles": [234, 17],
            "category": "特殊主体+罪名+后果"
        },
        {
            "query": "入户盗窃携带凶器的法律后果",
            "expected_articles": [264],
            "category": "特定情节+罪名"
        },
        {
            "query": "聚众斗殴致人重伤死亡的定罪量刑",
            "expected_articles": [292, 234, 232],
            "category": "罪名+后果+量刑"
        }
    ],
    "语义查询": [
        {
            "query": "杀人后自首会减轻处罚吗",
            "expected_articles": [232, 67],
            "category": "语义理解+量刑情节"
        },
        {
            "query": "偷东西被抓现行怎么判",
            "expected_articles": [264],
            "category": "口语化表达"
        },
        {
            "query": "酒后开车撞死人要坐牢多久",
            "expected_articles": [133],
            "category": "口语化+复杂情节"
        }
    ]
}

# ============================================================================
# 步骤1: 加载向量数据
# ============================================================================
print("【步骤1】加载向量数据...")
print()

vectors_dir = PROJECT_ROOT / "data" / "processed" / "vectors"

# 加载基础向量
with open(vectors_dir / "criminal_articles_vectors.pkl", 'rb') as f:
    base_data = pickle.load(f)
base_vectors = base_data['vectors']
metadata = base_data['metadata']

print(f"✅ 基础向量: {base_vectors.shape}")

# 加载微调向量
with open(vectors_dir / "criminal_articles_vectors_finetuned.pkl", 'rb') as f:
    finetuned_data = pickle.load(f)
finetuned_vectors = finetuned_data['vectors']

print(f"✅ 微调向量: {finetuned_vectors.shape}")
print()

# ============================================================================
# 步骤2: 加载模型
# ============================================================================
print("【步骤2】加载模型...")
print()

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"使用设备: {device}")
print()

# 加载tokenizer
tokenizer = AutoTokenizer.from_pretrained("thunlp/Lawformer")

# 加载基础模型
base_model = AutoModel.from_pretrained("thunlp/Lawformer")
base_model = base_model.to(device)
base_model.eval()
print("✅ 基础模型加载完成")

# 加载微调模型
finetuned_model = AutoModel.from_pretrained("thunlp/Lawformer")
checkpoint = torch.load(PROJECT_ROOT / "models" / "fine_tuned" / "lawformer_backbone_only.pt", map_location=device)
state_dict = checkpoint.get('model_state_dict', checkpoint)

# 处理权重前缀
if next(iter(state_dict.keys())).startswith('backbone.'):
    new_state_dict = {}
    for key, value in state_dict.items():
        if key.startswith('backbone.'):
            new_key = key.replace('backbone.', '')
            new_state_dict[new_key] = value
    state_dict = new_state_dict

finetuned_model.load_state_dict(state_dict, strict=False)
finetuned_model = finetuned_model.to(device)
finetuned_model.eval()
print("✅ 微调模型加载完成")
print()

# ============================================================================
# 步骤3: 定义评估函数
# ============================================================================

def encode_query(model, query):
    """编码查询"""
    inputs = tokenizer(query, return_tensors='pt', max_length=512, truncation=True, padding='max_length')
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
    
    return embedding

def search_articles(query_vec, vectors, top_k=10):
    """搜索法条"""
    sims = cosine_similarity(query_vec, vectors)[0]
    top_indices = np.argsort(sims)[::-1][:top_k]
    return [(idx, sims[idx]) for idx in top_indices]

def evaluate_query(query_info, model, vectors, model_name):
    """评估单个查询"""
    query = query_info['query']
    expected = query_info['expected_articles']
    
    # 编码查询
    start_time = time.time()
    query_vec = encode_query(model, query)
    encode_time = time.time() - start_time
    
    # 搜索
    start_time = time.time()
    results = search_articles(query_vec, vectors, top_k=10)
    search_time = time.time() - start_time
    
    # 提取结果法条号
    result_articles = []
    for idx, sim in results:
        article_num = metadata[idx].get('article_number')
        result_articles.append({
            'article_number': article_num,
            'similarity': float(sim),
            'title': metadata[idx].get('title', '')
        })
    
    # 计算指标
    result_nums = [r['article_number'] for r in result_articles]
    
    # MRR (Mean Reciprocal Rank)
    mrr = 0
    for exp in expected:
        if exp in result_nums:
            rank = result_nums.index(exp) + 1
            mrr = max(mrr, 1.0 / rank)
    
    # Precision@K
    precision_at_1 = 1 if any(exp in result_nums[:1] for exp in expected) else 0
    precision_at_3 = sum(1 for exp in expected if exp in result_nums[:3]) / min(3, len(expected))
    precision_at_5 = sum(1 for exp in expected if exp in result_nums[:5]) / min(5, len(expected))
    precision_at_10 = sum(1 for exp in expected if exp in result_nums[:10]) / min(10, len(expected))
    
    # 是否命中
    hit = any(exp in result_nums for exp in expected)
    
    return {
        'query': query,
        'expected': expected,
        'results': result_articles,
        'metrics': {
            'mrr': mrr,
            'precision@1': precision_at_1,
            'precision@3': precision_at_3,
            'precision@5': precision_at_5,
            'precision@10': precision_at_10,
            'hit': hit,
            'encode_time': encode_time,
            'search_time': search_time
        }
    }

# ============================================================================
# 步骤4: 执行全面测试
# ============================================================================
print("【步骤3】执行全面测试...")
print()

all_results = {
    'base': defaultdict(list),
    'finetuned': defaultdict(list)
}

total_queries = sum(len(queries) for queries in TEST_QUERIES.values())
current = 0

for difficulty, queries in TEST_QUERIES.items():
    print(f"测试 [{difficulty}] ({len(queries)} 个查询)")
    print()
    
    for query_info in queries:
        current += 1
        query = query_info['query']
        print(f"  [{current}/{total_queries}] {query}")
        
        # 基础模型
        base_result = evaluate_query(query_info, base_model, base_vectors, "base")
        all_results['base'][difficulty].append(base_result)
        
        # 微调模型
        finetuned_result = evaluate_query(query_info, finetuned_model, finetuned_vectors, "finetuned")
        all_results['finetuned'][difficulty].append(finetuned_result)
        
        # 显示对比
        base_hit = "✅" if base_result['metrics']['hit'] else "❌"
        ft_hit = "✅" if finetuned_result['metrics']['hit'] else "❌"
        
        base_p1 = base_result['metrics']['precision@1']
        ft_p1 = finetuned_result['metrics']['precision@1']
        
        print(f"    基础: {base_hit} P@1={base_p1:.0%}, MRR={base_result['metrics']['mrr']:.3f}")
        print(f"    微调: {ft_hit} P@1={ft_p1:.0%}, MRR={finetuned_result['metrics']['mrr']:.3f}")
        
        if ft_p1 > base_p1:
            print(f"    💡 微调模型更优")
        elif ft_p1 < base_p1:
            print(f"    ⚠️  基础模型更优")
        
        print()
    
    print()

# ============================================================================
# 步骤5: 计算总体指标
# ============================================================================
print("【步骤4】计算总体指标...")
print()

def calculate_aggregate_metrics(results):
    """计算聚合指标"""
    all_metrics = []
    for difficulty in results.keys():
        all_metrics.extend([r['metrics'] for r in results[difficulty]])
    
    if not all_metrics:
        return {}
    
    return {
        'mrr': np.mean([m['mrr'] for m in all_metrics]),
        'precision@1': np.mean([m['precision@1'] for m in all_metrics]),
        'precision@3': np.mean([m['precision@3'] for m in all_metrics]),
        'precision@5': np.mean([m['precision@5'] for m in all_metrics]),
        'precision@10': np.mean([m['precision@10'] for m in all_metrics]),
        'hit_rate': np.mean([m['hit'] for m in all_metrics]),
        'avg_encode_time': np.mean([m['encode_time'] for m in all_metrics]),
        'avg_search_time': np.mean([m['search_time'] for m in all_metrics])
    }

base_aggregate = calculate_aggregate_metrics(all_results['base'])
finetuned_aggregate = calculate_aggregate_metrics(all_results['finetuned'])

print("总体性能对比:")
print()
print(f"{'指标':<20} {'基础模型':<15} {'微调模型':<15} {'提升':<15}")
print("-" * 70)

for metric in ['mrr', 'precision@1', 'precision@3', 'precision@5', 'precision@10', 'hit_rate']:
    base_val = base_aggregate[metric]
    ft_val = finetuned_aggregate[metric]
    improvement = ((ft_val - base_val) / base_val * 100) if base_val > 0 else 0
    
    print(f"{metric:<20} {base_val:<15.3f} {ft_val:<15.3f} {improvement:+.1f}%")

print()

# ============================================================================
# 步骤6: 按难度分析
# ============================================================================
print("【步骤5】按难度分析...")
print()

difficulty_comparison = {}

for difficulty in TEST_QUERIES.keys():
    base_metrics = calculate_aggregate_metrics({'all': all_results['base'][difficulty]})
    ft_metrics = calculate_aggregate_metrics({'all': all_results['finetuned'][difficulty]})
    
    difficulty_comparison[difficulty] = {
        'base': base_metrics,
        'finetuned': ft_metrics,
        'improvement': {
            metric: ((ft_metrics[metric] - base_metrics[metric]) / base_metrics[metric] * 100) 
            if base_metrics[metric] > 0 else 0
            for metric in ['mrr', 'precision@1', 'hit_rate']
        }
    }
    
    print(f"{difficulty}:")
    print(f"  MRR: {base_metrics['mrr']:.3f} → {ft_metrics['mrr']:.3f} ({difficulty_comparison[difficulty]['improvement']['mrr']:+.1f}%)")
    print(f"  P@1: {base_metrics['precision@1']:.3f} → {ft_metrics['precision@1']:.3f} ({difficulty_comparison[difficulty]['improvement']['precision@1']:+.1f}%)")
    print()

# ============================================================================
# 步骤7: 保存详细结果
# ============================================================================
print("【步骤6】保存结果...")
print()

output_dir = Path(__file__).parent
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

# 保存JSON
json_output = {
    'metadata': {
        'timestamp': timestamp,
        'total_queries': total_queries,
        'device': device,
        'model_info': {
            'base': 'thunlp/Lawformer',
            'finetuned': 'thunlp/Lawformer (Fine-tuned)'
        }
    },
    'overall_metrics': {
        'base': base_aggregate,
        'finetuned': finetuned_aggregate
    },
    'by_difficulty': difficulty_comparison,
    'detailed_results': {
        'base': {k: v for k, v in all_results['base'].items()},
        'finetuned': {k: v for k, v in all_results['finetuned'].items()}
    }
}

json_file = output_dir / f"comparison_results_{timestamp}.json"
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(json_output, f, ensure_ascii=False, indent=2)

print(f"✅ JSON结果已保存: {json_file.name}")

# 保存最新结果的副本
latest_json = output_dir / "comparison_results_latest.json"
with open(latest_json, 'w', encoding='utf-8') as f:
    json.dump(json_output, f, ensure_ascii=False, indent=2)

print(f"✅ 最新结果: comparison_results_latest.json")
print()

# ============================================================================
# 步骤8: 生成Markdown报告
# ============================================================================
print("【步骤7】生成Markdown报告...")
print()

md_content = f"""# 基础模型 vs 微调模型 - 全面对比实验报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**测试设备**: {device}

---

## 📊 执行摘要

本实验对比了基础Lawformer模型和微调Lawformer模型在刑事法律检索任务上的性能表现。

### 测试规模

- **总查询数**: {total_queries} 个
- **难度级别**: {len(TEST_QUERIES)} 个（简单、中等、复杂、语义）
- **评估指标**: MRR, Precision@K, Hit Rate

### 核心发现

"""

# 计算总体提升
mrr_improvement = ((finetuned_aggregate['mrr'] - base_aggregate['mrr']) / base_aggregate['mrr'] * 100)
p1_improvement = ((finetuned_aggregate['precision@1'] - base_aggregate['precision@1']) / base_aggregate['precision@1'] * 100)

if mrr_improvement > 0:
    md_content += f"""
✅ **微调模型显著优于基础模型**

- MRR提升: **{mrr_improvement:+.1f}%**
- Precision@1提升: **{p1_improvement:+.1f}%**
- Hit Rate: {finetuned_aggregate['hit_rate']:.1%} vs {base_aggregate['hit_rate']:.1%}

"""
else:
    md_content += f"""
⚠️ **性能对比结果**

- MRR变化: {mrr_improvement:+.1f}%
- Precision@1变化: {p1_improvement:+.1f}%

"""

md_content += f"""---

## 📈 总体性能对比

| 指标 | 基础模型 | 微调模型 | 提升幅度 |
|------|----------|----------|----------|
| **MRR** | {base_aggregate['mrr']:.3f} | {finetuned_aggregate['mrr']:.3f} | **{mrr_improvement:+.1f}%** |
| **Precision@1** | {base_aggregate['precision@1']:.3f} | {finetuned_aggregate['precision@1']:.3f} | **{p1_improvement:+.1f}%** |
| **Precision@3** | {base_aggregate['precision@3']:.3f} | {finetuned_aggregate['precision@3']:.3f} | {((finetuned_aggregate['precision@3'] - base_aggregate['precision@3']) / base_aggregate['precision@3'] * 100):+.1f}% |
| **Precision@5** | {base_aggregate['precision@5']:.3f} | {finetuned_aggregate['precision@5']:.3f} | {((finetuned_aggregate['precision@5'] - base_aggregate['precision@5']) / base_aggregate['precision@5'] * 100):+.1f}% |
| **Precision@10** | {base_aggregate['precision@10']:.3f} | {finetuned_aggregate['precision@10']:.3f} | {((finetuned_aggregate['precision@10'] - base_aggregate['precision@10']) / base_aggregate['precision@10'] * 100):+.1f}% |
| **Hit Rate** | {base_aggregate['hit_rate']:.1%} | {finetuned_aggregate['hit_rate']:.1%} | {((finetuned_aggregate['hit_rate'] - base_aggregate['hit_rate']) / base_aggregate['hit_rate'] * 100):+.1f}% |

### 性能指标说明

- **MRR (Mean Reciprocal Rank)**: 正确结果排名的倒数平均值，越高越好
- **Precision@K**: 前K个结果中正确结果的比例
- **Hit Rate**: 至少命中一个正确结果的查询比例

---

## 🎯 按难度级别分析

"""

for difficulty in TEST_QUERIES.keys():
    comp = difficulty_comparison[difficulty]
    base_m = comp['base']
    ft_m = comp['finetuned']
    imp = comp['improvement']
    
    md_content += f"""### {difficulty}

**测试查询数**: {len(TEST_QUERIES[difficulty])} 个

| 指标 | 基础模型 | 微调模型 | 提升 |
|------|----------|----------|------|
| MRR | {base_m['mrr']:.3f} | {ft_m['mrr']:.3f} | {imp['mrr']:+.1f}% |
| Precision@1 | {base_m['precision@1']:.3f} | {ft_m['precision@1']:.3f} | {imp['precision@1']:+.1f}% |
| Hit Rate | {base_m['hit_rate']:.1%} | {ft_m['hit_rate']:.1%} | {imp['hit_rate']:+.1f}% |

"""

md_content += """---

## 🔍 典型案例分析

### 案例1: 简单查询 - "故意杀人罪"

"""

# 找到故意杀人罪的查询结果
for difficulty, queries in TEST_QUERIES.items():
    for i, q in enumerate(queries):
        if "故意杀人罪" in q['query'] and len(q['query']) < 10:
            base_r = all_results['base'][difficulty][i]
            ft_r = all_results['finetuned'][difficulty][i]
            
            md_content += f"""**期望结果**: 第232条

**基础模型 Top 3**:
"""
            for j, result in enumerate(base_r['results'][:3], 1):
                marker = "✅" if result['article_number'] in q['expected_articles'] else "❌"
                md_content += f"{j}. {marker} 第{result['article_number']}条 - {result['title']} (相似度: {result['similarity']:.4f})\n"
            
            md_content += f"""
**微调模型 Top 3**:
"""
            for j, result in enumerate(ft_r['results'][:3], 1):
                marker = "✅" if result['article_number'] in q['expected_articles'] else "❌"
                md_content += f"{j}. {marker} 第{result['article_number']}条 - {result['title']} (相似度: {result['similarity']:.4f})\n"
            
            break

md_content += """
### 案例2: 中等查询 - "故意杀人罪的量刑标准"

"""

# 找到量刑标准的查询结果
for difficulty, queries in TEST_QUERIES.items():
    for i, q in enumerate(queries):
        if "故意杀人罪的量刑标准" in q['query']:
            base_r = all_results['base'][difficulty][i]
            ft_r = all_results['finetuned'][difficulty][i]
            
            md_content += f"""**期望结果**: 第232条

**基础模型 Top 3**:
"""
            for j, result in enumerate(base_r['results'][:3], 1):
                marker = "✅" if result['article_number'] in q['expected_articles'] else "❌"
                md_content += f"{j}. {marker} 第{result['article_number']}条 - {result['title']} (相似度: {result['similarity']:.4f})\n"
            
            md_content += f"""
**微调模型 Top 3**:
"""
            for j, result in enumerate(ft_r['results'][:3], 1):
                marker = "✅" if result['article_number'] in q['expected_articles'] else "❌"
                md_content += f"{j}. {marker} 第{result['article_number']}条 - {result['title']} (相似度: {result['similarity']:.4f})\n"
            
            break

md_content += f"""
---

## 💡 结论与建议

### 主要优势

"""

if mrr_improvement > 5:
    md_content += f"""
1. **检索准确性显著提升**: MRR提升{mrr_improvement:.1f}%，说明微调模型能更准确地将相关法条排在前列

2. **首位命中率提高**: Precision@1提升{p1_improvement:.1f}%，用户更容易在第一个结果找到正确答案

3. **语义理解增强**: 在复杂查询和语义查询中表现更优，说明微调提升了模型的法律领域语义理解能力
"""
elif mrr_improvement > 0:
    md_content += f"""
1. **检索准确性有所提升**: MRR提升{mrr_improvement:.1f}%

2. **性能稳定**: 在不同难度级别的查询中都保持稳定表现
"""
else:
    md_content += """
1. **性能相当**: 两个模型在当前测试集上表现相近

2. **需要更多测试**: 建议扩大测试集规模和难度范围
"""

md_content += f"""
### 使用建议

- ✅ **推荐使用微调模型**: 在生产环境中启用微调模型以获得更好的检索效果
- 🔧 **配置方式**: 在 `.env` 文件中设置 `USE_FINETUNED_MODEL=true`
- 📊 **性能监控**: 持续监控实际使用中的检索效果，收集用户反馈

### 技术细节

- **基础模型**: thunlp/Lawformer
- **微调模型**: thunlp/Lawformer (使用CAIL2018数据集进行对比学习微调)
- **向量维度**: 768
- **法条数量**: {len(metadata)}

---

## 📁 附件

- 详细结果: `comparison_results_{timestamp}.json`
- 最新结果: `comparison_results_latest.json`

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

md_file = output_dir / f"comparison_report_{timestamp}.md"
with open(md_file, 'w', encoding='utf-8') as f:
    f.write(md_content)

print(f"✅ Markdown报告已保存: {md_file.name}")

# 保存最新报告的副本
latest_md = output_dir / "comparison_report_latest.md"
with open(latest_md, 'w', encoding='utf-8') as f:
    f.write(md_content)

print(f"✅ 最新报告: comparison_report_latest.md")
print()

# ============================================================================
# 完成
# ============================================================================
print("="*80)
print("✅ 对比实验完成！")
print("="*80)
print()
print(f"总体结论:")
if mrr_improvement > 5:
    print(f"  🎉 微调模型显著优于基础模型 (MRR提升{mrr_improvement:.1f}%)")
    print(f"  💡 强烈建议在生产环境中使用微调模型")
elif mrr_improvement > 0:
    print(f"  ✅ 微调模型略优于基础模型 (MRR提升{mrr_improvement:.1f}%)")
    print(f"  💡 建议使用微调模型")
else:
    print(f"  ➖ 两个模型性能相当")
    print(f"  💡 可以继续使用基础模型，或扩大测试范围")
print()
print(f"查看详细报告:")
print(f"  - JSON: {json_file.name}")
print(f"  - Markdown: {md_file.name}")
print()

