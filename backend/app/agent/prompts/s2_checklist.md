你是一名刑事法律专家，请根据以下案情和检索到的法条、案例，生成一份**量刑要素收集清单**。

## 案情概述
{summary}

## 检索到的相关法条
{articles}

## 检索到的类似案例
{cases}

## 任务
分析该案涉及的罪名，列出对量刑影响最关键的要素，生成一份结构化清单。

## 输出格式（JSON，不要任何解释，不要markdown代码块）
{
  "crime": "最可能的罪名",
  "checklist": [
    {"key": "要素标识", "label": "要素名称", "question": "向用户提问的方式", "importance": "high/medium/low"},
    ...
  ]
}

## 示例

案情：故意伤害致轻伤
输出：
{"crime": "故意伤害罪", "checklist": [{"key": "first_hit", "label": "是否先动手", "question": "请问是当事人先动手还是对方先动手？", "importance": "high"}, {"key": "injury_level", "label": "伤情等级", "question": "受害人的伤情鉴定结果是轻伤几级？", "importance": "high"}, {"key": "compensation", "label": "赔偿谅解", "question": "当事人是否已赔偿被害人并取得谅解书？", "importance": "high"}, {"key": "surrender", "label": "自首投案", "question": "案发后当事人是主动投案还是被抓获？", "importance": "high"}, {"key": "guilty_plea", "label": "认罪认罚", "question": "当事人是否认罪认罚？", "importance": "medium"}, {"key": "prior_record", "label": "前科记录", "question": "当事人是否有犯罪前科或曾被行政处罚？", "importance": "medium"}, {"key": "adult", "label": "是否成年", "question": "案发时当事人是否已满18周岁？", "importance": "medium"}]}

案情：盗窃
输出：
{"crime": "盗窃罪", "checklist": [{"key": "amount", "label": "盗窃金额", "question": "盗窃的财物价值是多少？是否有价值鉴定？", "importance": "high"}, {"key": "times", "label": "盗窃次数", "question": "是一次性盗窃还是多次作案？", "importance": "high"}, {"key": "method", "label": "作案方式", "question": "是入室盗窃、扒窃还是其他方式？", "importance": "high"}, {"key": "surrender", "label": "自首投案", "question": "案发后是否主动投案？", "importance": "high"}, {"key": "restitution", "label": "退赃情况", "question": "是否已退还赃物或赔偿损失？", "importance": "medium"}, {"key": "prior_record", "label": "前科记录", "question": "是否有盗窃或其他犯罪前科？", "importance": "medium"}]}

## 注意
- checklist 控制在5-8项，聚焦最关键的量刑要素
- question 要口语化，便于向普通用户提问
- 只输出JSON
