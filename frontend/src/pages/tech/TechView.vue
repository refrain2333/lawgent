<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import NavBar from '@/components/ui/NavBar.vue'
import MarkdownViewer from '@/components/ui/MarkdownViewer.vue'
import {
  BrainCircuit,
  Check,
  ChevronRight,
  Cpu,
  Database,
  FileCode2,
  GitBranch,
  Menu,
  Network,
  Search,
  Sparkles,
  TrendingUp,
  Unplug,
  UserCog,
  Waypoints,
  X,
} from 'lucide-vue-next'

interface TocChild {
  id: string
  title: string
}

interface TocSection {
  id: string
  title: string
  children: TocChild[]
}

const tocTree: TocSection[] = [
  {
    id: 'agent',
    title: 'LangChain Agent 设计',
    children: [
      { id: 'agent-overview', title: '设计概述' },
      { id: 'agent-state', title: '状态机设计' },
      { id: 'agent-timeline', title: 'Stage 1~4 时间线' },
      { id: 'agent-realtime', title: 'HITL & SSE' },
      { id: 'agent-route', title: '阶段路由机制' },
      { id: 'agent-async', title: '后台异步任务' },
    ],
  },
  {
    id: 'search-system',
    title: '智能检索系统',
    children: [
      { id: 'search-overview', title: '检索架构' },
      { id: 'search-paths', title: '五路核心检索' },
      { id: 'search-rrf', title: 'RRF 融合' },
    ],
  },
  {
    id: 'lawformer-finetune',
    title: 'Lawformer 微调',
    children: [
      { id: 'finetune-background', title: '微调背景' },
      { id: 'finetune-data', title: '训练数据' },
      { id: 'finetune-method', title: '对比学习方法' },
      { id: 'finetune-metrics', title: '评估结果对比' },
    ],
  },
  {
    id: 'knowledge-graph',
    title: '知识图谱构建',
    children: [
      { id: 'kg-overview', title: '核心流程' },
      { id: 'kg-process', title: '构建路径' },
      { id: 'kg-example', title: '检索示例' },
      { id: 'kg-boundary', title: '边界说明' },
      { id: 'kg-stats', title: '图谱统计' },
    ],
  },
]

const flatAnchors = tocTree.flatMap(section =>
  section.children.map(child => ({ ...child, sectionId: section.id })),
)

const activeAnchor = ref(flatAnchors[0]?.id ?? 'agent-overview')
const isTocOpen = ref(false)

const activeSectionId = computed(() => {
  return flatAnchors.find(item => item.id === activeAnchor.value)?.sectionId ?? tocTree[0]?.id ?? 'agent'
})

const stageTimeline = [
  {
    stage: 'Stage 1 · 案情收集',
    summary: '多轮对话提取核心案情，信息足够时触发确认流程。',
    nodes: ['chat_s1', 'case_ready_tool', 'check_sufficient', 'generate_title'],
    description: '用户发送消息后路由到 chat_s1 流式对话；AI 判断信息充足后调用 case_ready_tool 触发 s1_confirming；用户也可手动点击推进，后端调用 check_sufficient 判断。',
  },
  {
    stage: 'Stage 2 · 并发检索',
    summary: '用户确认案情后，后台异步执行检索与清单生成。',
    nodes: ['run_s2', 'gen_checklist', 'gen_s3_opener'],
    description: '以案情摘要为输入，5 路并行检索 + RRF 融合；完成后调用 gen_checklist 生成量刑要素清单，再由 gen_s3_opener 生成 S3 开场白，写库后推进到 s3_collecting。',
  },
  {
    stage: 'Stage 3 · 情节补充',
    summary: '基于检索结果与量刑清单继续追问，二次确认后进入报告生成。',
    nodes: ['chat_s3', 's3_ready_tool', 'advance (手动兜底)'],
    description: '对话上下文仅取 s3_collecting 阶段消息，防止 S1 历史污染；AI 收集完毕后调用 s3_ready_tool 自动推进到 s3_confirming，用户也可手动点击推进。',
  },
  {
    stage: 'Stage 4 · 报告生成',
    summary: '整合 S1/S2/S3 数据，生成结构化风险评估报告。',
    nodes: ['gen_report', 'chat_s4'],
    description: '后台异步调用 gen_report，读取 S1 摘要、S2 检索结果、S2 量刑清单、S3 情节，输出 JSON 报告写入 StageConfirmation；报告生成后支持通过 chat_s4 继续追问。',
  },
]

const stateFields = [
  { name: 'Conversation.stage', type: 'ConversationStage', desc: '当前阶段枚举（s1_collecting / s1_confirming / s2_searching / s2_failed / s3_collecting / s3_confirming / s4_generating / s4_done / s4_failed），驱动 API 路由分发。' },
  { name: 'Conversation.thread_id', type: 'str', desc: '会话唯一标识，前端用于标识同一会话的所有请求与消息。' },
  { name: 'Conversation.title', type: 'str | None', desc: 'S1 确认后由 LLM 自动生成的会话标题，写入后展示于左侧列表。' },
  { name: 'Message', type: 'role + content + stage', desc: '每条对话消息独立存储，含角色（user/assistant）与所属阶段，用于各 Stage 恢复上下文。' },
  { name: 'StageConfirmation', type: 'stage + output_data', desc: '各阶段关键产物（案情摘要 / 检索结果 / 量刑清单 / 风险报告）持久化为 JSON，供后续阶段读取复用。' },
]

const realtimeCards = [
  {
    title: 'Human-in-the-Loop',
    icon: UserCog,
    desc: 'S1 / S3 阶段通过 REST 卡点实现人工确认：/advance 触发 AI 判断信息是否充足，/confirm 由用户决定接受或拒绝，拒绝则回退重新收集，接受则推进到下一阶段。',
  },
  {
    title: 'SSE 事件推送',
    icon: Unplug,
    desc: '通过 FastAPI StreamingResponse 以 text/event-stream 格式推送事件，前端 ReadableStream 逐行解析。token 事件驱动打字机效果，case_ready / s3_ready 事件触发阶段推进，end / error 事件结束流。',
  },
]

const sseEvents = [
  { type: 'token', when: 'AI 流式输出每个字符片段', note: '前端打字机队列消费' },
  { type: 'stage_changed', when: '确认阶段补充案情，撤回到收集阶段', note: '更新当前阶段并撤下旧确认卡' },
  { type: 'case_ready', when: 'S1 信息收集完毕，携带 summary', note: '触发 s1_confirming + 存库' },
  { type: 's3_ready', when: 'S3 情节收集完毕，携带 facts', note: '触发 s3_confirming + 存库' },
  { type: 'end', when: 'AI 正常输出结束', note: '关闭流式消息气泡' },
  { type: 'error', when: '处理异常', note: '前端展示错误提示' },
]

const routeRules = [
  { stage: 's1_collecting', fn: 'chat_s1', note: 'S1 正常收集对话' },
  { stage: 's1_confirming', fn: 'chat_s1_confirming', note: 'S1 确认阶段补充说明' },
  { stage: 's3_collecting', fn: 'chat_s3', note: 'S3 对话，历史只取 s3_collecting 阶段消息，防止早期对话污染 LLM 上下文' },
  { stage: 's4_done', fn: 'chat_s4', note: 'S4 报告已落库后支持继续追问' },
  { stage: '其他', fn: 'HTTP 400', note: '不支持发送消息的阶段直接拒绝' },
]

const asyncTasks = [
  {
    title: 'S2 检索任务',
    trigger: '用户确认 S1 案情（/confirm accepted=true）',
    fn: '_run_s2_and_save',
    steps: ['run_s2 执行 5 路并行检索 + RRF 融合', 'gen_checklist 生成量刑要素清单', 'gen_s3_opener 生成 S3 开场白并写入消息表', '推进 stage → s3_collecting'],
    poll: '前端每 3s 轮询 /state，等待检索与开场引导就绪；超时后可手动刷新',
  },
  {
    title: 'S4 报告任务',
    trigger: '用户确认 S3 情节（/confirm accepted=true）',
    fn: '_run_s4_and_save',
    steps: ['切换 stage → s4_generating', '读取 S1 摘要、S2 检索结果、S2 量刑清单、S3 情节', 'gen_report 综合生成结构化 JSON 报告', '写入 StageConfirmation（s4_report）后切换 stage → s4_done'],
    poll: '前端每 3s 轮询 /report，成功返回 200 则展示报告；超时后可刷新状态继续等待',
  },
]

const retrievalCards = [
  {
    title: '向量检索',
    api: 'GET /api/v1/search/vector',
    icon: Search,
    desc: '基于微调 Lawformer 的 768 维语义向量召回，覆盖长文本语义匹配场景。',
    badge: 'Semantic',
  },
  {
    title: 'BM25 检索',
    api: 'GET /api/v1/search/bm25',
    icon: Database,
    desc: '结合关键词与 n-gram 分词，对罪名、法条号、关键事实具备高精度匹配能力。',
    badge: 'Sparse',
  },
  {
    title: '知识图谱检索',
    api: 'GET /api/v1/search/kg',
    icon: Network,
    desc: '利用 AC 自动机命中罪名实体，再按罪名-法条关系频次返回高置信候选法条。',
    badge: 'Graph',
  },
  {
    title: 'Query2Doc 检索',
    api: 'POST /api/v1/search · body.query2doc',
    icon: FileCode2,
    desc: '先做查询扩写生成检索友好文本，再进入向量召回，提升短查询表达能力。',
    badge: 'Expansion',
  },
  {
    title: 'HyDE 检索',
    api: 'POST /api/v1/search · body.hyde',
    icon: Sparkles,
    desc: '先生成假设性法律回答作为检索锚点，再进行向量匹配以提高召回稳健性。',
    badge: 'Hypothetical',
  },
]

const retrievalFlow = [
  { key: 'vector', label: 'Vector', hint: '概述语义召回', icon: Search },
  { key: 'bm25', label: 'BM25', hint: '关键词稀疏匹配', icon: Database },
  { key: 'kg', label: 'KG', hint: '可能罪名映射法条', icon: Network },
  { key: 'query2doc', label: 'Query2Doc', hint: '查询扩写检索', icon: FileCode2 },
  { key: 'hyde', label: 'HyDE', hint: '假设答案检索', icon: Sparkles },
]

const retrievalWhyFive = [
  {
    title: '单一路径盲区明显',
    detail: '仅用向量会漏关键词与条号精确命中；仅用关键词又难覆盖语义改写。',
  },
  {
    title: '法律检索是多约束任务',
    detail: '需要同时兼顾语义相似、关键词精度、罪名-法条结构关系与可解释性。',
  },
  {
    title: '多路互补 + RRF 更稳',
    detail: '5 路并行后按排名融合，可降低单一路径偏差，提升结果稳定性。',
  },
]

const retrievalInputMapping = [
  {
    source: 'queries.vector',
    routes: 'vector',
    usage: '语义概述文本，用于向量余弦相似度召回，覆盖核心案情事实。',
  },
  {
    source: 'queries.bm25',
    routes: 'bm25',
    usage: '关键词提取文本，强化罪名术语、法条号等精确匹配。',
  },
  {
    source: 'queries.kg',
    routes: 'kg',
    usage: '可能罪名词组，供 AC 自动机匹配后映射到知识图谱法条。',
  },
  {
    source: 'queries.query2doc',
    routes: 'query2doc',
    usage: 'LLM 扩写后的检索友好文本，补全法律表达，提升短查询召回。',
  },
  {
    source: 'queries.hyde',
    routes: 'hyde',
    usage: 'LLM 生成的假设性法律回答，作为检索锚点增强复杂语义匹配。',
  },
]

const rrfMarkdown = `### RRF 融合公式

$$
score(d) = \\sum_i \\frac{1}{k + rank_i(d)}, \\quad k = 60
$$

- \`rank_i(d)\`：文档 \`d\` 在第 \`i\` 路检索中的位置（当前实现从 0 开始）
- 若某一路未命中 \`d\`，则该路贡献记为 0
- 文档在更多检索器中排名越靠前，累积分越高
- RRF 仅依赖”排名”而非”原始分数”，可缓解多检索器分数尺度不一致问题
`

const rrfImplNotes = [
  {
    title: '多取候选再裁剪',
    detail: '每路检索各取 top_k = count × 3 个候选，融合排序后再截取最终 count 条，保证召回覆盖度不因单路数量不足而损失。',
  },
  {
    title: '融合分与相似度的区别',
    detail: '融合结果的 similarity 字段保存 RRF 分，咨询页按 RRF 展示；单路检索保存该路原始得分。两者均用于排序，不代表法律结论的置信度。',
  },
  {
    title: 'KG 路仅参与法条融合',
    detail: '知识图谱路只返回法条，不涉及案例，因此案例融合列表中只有 vector / bm25 / query2doc / hyde 四路参与 RRF。',
  },
]

const finetuneNotes = [
  {
    id: 'finetune-background',
    title: '微调背景',
    summary: '为什么要微调',
    text: '原始 Lawformer 偏向通用法律语料。为提升刑事语境下的事实-法条匹配能力，LawGent 采用面向刑事场景的再训练策略。',
  },
  {
    id: 'finetune-data',
    title: '训练数据',
    summary: '样本如何组织',
    text: '基于 CAIL2018 构建三元组样本（案件事实、相关法条、负样本法条），按 8:1:1 划分训练/验证/测试集。',
  },
  {
    id: 'finetune-method',
    title: '对比学习方法',
    summary: '如何拉近与拉远',
    text: '采用 Triplet Loss 约束语义空间，使同案情与正确法条距离更近，错误法条距离更远，从而提升检索判别力。',
  },
]

const finetuneConfig = [
  { key: '训练目标', value: 'Triplet Loss 对比学习' },
  { key: '样本构造', value: '案件事实 / 正法条 / 负法条' },
  { key: '数据划分', value: 'Train:Val:Test = 8:1:1' },
  { key: '向量表示', value: 'Lawformer [CLS] 句向量（768维）' },
]

const finetuneDataPipeline = [
  {
    step: 'Step 1',
    title: '原始数据来源',
    detail: '使用 CAIL2018 刑事案件数据，提取案件事实、罪名与适用法条标注。',
  },
  {
    step: 'Step 2',
    title: '样本清洗与标准化',
    detail: '统一法条编号格式，去除缺失标签与异常文本，保留可对齐的案件-法条样本。',
  },
  {
    step: 'Step 3',
    title: '三元组构建',
    detail: '以案件事实为 Anchor，真实适用法条为 Positive，不适用法条为 Negative；其中与案情表面相似但标注不匹配的法条作为难负样本。',
  },
  {
    step: 'Step 4',
    title: '训练集切分',
    detail: '按 8:1:1 划分 Train/Val/Test，保证评估指标来自未参与训练的数据。',
  },
]

const finetuneExample = {
  query: '深夜持刀抢劫并致轻伤',
  beforeTop3: ['故意伤害相关法条', '寻衅滋事相关法条', '盗窃罪相关法条'],
  afterTop3: ['抢劫罪相关法条', '加重情节相关法条', '共同犯罪相关法条'],
  note: '微调后，模型更容易将“暴力 + 非法占有”联合语义映射到抢劫罪及其加重情节。',
}

const finetuneInsight = '从指标与样例可见，微调主要提升了复杂案情下的“正确法条前排率”，尤其对多要素联合语义更稳定。（以上指标来自 13 条构造查询的小规模评估，用于观察趋势，样本量有限；更大规模的结论需用 CAIL 留出集验证。）'

const metricRows = [
  { metric: 'Top-1 准确率 (P@1)', before: '46.2%', after: '84.6%', uplift: '+38.4pp' },
  { metric: 'Top-5 精确率 (P@5)', before: '50.0%', after: '100.0%', uplift: '+50.0pp' },
  { metric: 'MRR', before: '0.527', after: '0.910', uplift: '+0.383' },
  { metric: 'Hit Rate', before: '84.6%', after: '100.0%', uplift: '+15.4pp' },
]

const kgProcess = [
  {
    title: '图谱设计',
    desc: '以“罪名-法条”二部图为核心结构，节点可解释、关系可追溯。',
    icon: GitBranch,
  },
  {
    title: '关系抽取',
    desc: '从案例标注中抽取 accusation 与 relevant_articles，统计罪名-法条共现频次。',
    icon: FileCode2,
  },
  {
    title: '规则清洗',
    desc: '过滤超范围法条与明显异常关联，统一罪名与法条编号格式。',
    icon: Check,
  },
  {
    title: '图谱持久化',
    desc: '将 crime_article_mapping 与 article_crime_mapping 持久化为 knowledge_graph.pkl。',
    icon: Database,
  },
  {
    title: 'AC 自动机构建',
    desc: '基于罪名词表构建自动机，并加入去“罪”后缀别名以提升召回。',
    icon: Waypoints,
  },
  {
    title: '检索融合使用',
    desc: '问句命中实体后返回候选法条，并作为 kg 路参与 5 路并行融合排序。',
    icon: Search,
  },
]

const kgBuildPipeline = [
  {
    step: 'Step 1',
    title: '原始案例入库',
    detail: '读取案例中的罪名（accusation）与法条（relevant_articles）字段。',
  },
  {
    step: 'Step 2',
    title: '关系计数',
    detail: '按“罪名-法条”共现次数建立边权，形成 crime_article_mapping。',
  },
  {
    step: 'Step 3',
    title: '双向索引',
    detail: '同步构建 article_crime_mapping，支持法条反查罪名。',
  },
  {
    step: 'Step 4',
    title: '质量校验',
    detail: '执行法条范围、关系合理性、异常样本过滤等规则，保证图谱质量。',
  },
  {
    step: 'Step 5',
    title: '落盘与加载',
    detail: '导出 knowledge_graph.pkl + meta，系统启动后加载并初始化 AC 自动机。',
  },
]

const kgUseFlow = [
  {
    phase: '实体识别',
    detail: '用 AC 自动机在用户问句中做多模式匹配，识别罪名实体。',
  },
  {
    phase: '候选生成',
    detail: '按命中罪名在图谱中映射候选法条，并累计边频次。',
  },
  {
    phase: '分数归一化',
    detail: '将频次归一化到 (0,1]，形成 kg 路法条分数。',
  },
  {
    phase: '多路融合',
    detail: '将 kg 路结果与 vector / bm25 / query2doc / hyde 一并做 RRF 融合。',
  },
]

const kgStats = [
  {
    title: '罪名节点',
    value: '202',
    icon: Network,
    glow: 'from-cyan-400/60 via-sky-500/40 to-transparent',
  },
  {
    title: '法条节点',
    value: '183',
    icon: FileCode2,
    glow: 'from-indigo-400/60 via-violet-500/40 to-transparent',
  },
  {
    title: '关联边数',
    value: '23,561',
    icon: Database,
    glow: 'from-emerald-400/60 via-teal-500/40 to-transparent',
  },
]

const kgExample = {
  query: '多人持械抢劫并致一人轻伤',
  matchedEntities: ['抢劫罪'],
  graphLinks: ['抢劫罪 → 刑法第263条', '关系权重来自历史案件共现次数'],
  output: '根据罪名—法条共现频次返回相关法条；持械、伤情等事实由后续阶段结合案情与法条文本分析。',
}

const kgBoundaryNotes = [
  '知识图谱检索强调可解释性与稳定规则命中，不替代向量语义召回。',
  '当 AC 自动机在问句中未命中任何已建罪名实体时，自动降级为子串模糊匹配作为兜底，尽量返回候选法条。',
  '当查询完全无法匹配时，KG 路返回为空，此时依赖其他检索路补足结果。',
  '图谱关系来源于已标注数据统计，存在语料分布偏差，需要与多路融合共同使用。',
]

const isSectionActive = (sectionId: string) => activeSectionId.value === sectionId
const isAnchorActive = (anchorId: string) => activeAnchor.value === anchorId

function scrollToAnchor(id: string) {
  const target = document.getElementById(id)
  if (!target) return
  activeAnchor.value = id
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  isTocOpen.value = false
}

function syncActiveAnchor() {
  const triggerOffset = 160
  for (let i = flatAnchors.length - 1; i >= 0; i -= 1) {
    const anchor = flatAnchors[i]
    if (!anchor) continue
    const el = document.getElementById(anchor.id)
    if (el && el.getBoundingClientRect().top <= triggerOffset) {
      activeAnchor.value = anchor.id
      return
    }
  }
  activeAnchor.value = flatAnchors[0]?.id ?? activeAnchor.value
}

let ticking = false
function handleScroll() {
  if (ticking) return
  ticking = true
  requestAnimationFrame(() => {
    syncActiveAnchor()
    ticking = false
  })
}

function handleEsc(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    isTocOpen.value = false
  }
}

watch(isTocOpen, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  window.addEventListener('keydown', handleEsc)
  nextTick(syncActiveAnchor)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
  window.removeEventListener('keydown', handleEsc)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <NavBar />

    <div class="max-w-6xl mx-auto flex px-4 lg:px-6 pb-24 pt-10 lg:pt-14">
      <!-- Desktop TOC -->
      <aside class="w-52 shrink-0 sticky top-24 hidden lg:block h-[calc(100vh-7rem)] overflow-y-auto border-r border-border/60 pr-4">
        <div>
          <p class="text-[11px] tracking-[0.18em] uppercase text-muted-foreground">On this page</p>
          <nav class="mt-4 space-y-2">
            <div v-for="section in tocTree" :key="section.id" class="space-y-1">
              <button
                class="group w-full flex items-center justify-between rounded-lg px-2 py-1.5 text-left transition-colors"
                :class="isSectionActive(section.id)
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground'"
                @click="section.children[0] && scrollToAnchor(section.children[0].id)"
              >
                <span class="text-sm" :class="isSectionActive(section.id) ? 'font-semibold' : 'font-medium'">
                  {{ section.title }}
                </span>
                <ChevronRight
                  class="w-3.5 h-3.5 transition-transform"
                  :class="isSectionActive(section.id) ? 'rotate-90 opacity-100' : 'opacity-40'"
                />
              </button>

              <div
                class="ml-3 border-l pl-2 transition-all"
                :class="isSectionActive(section.id)
                  ? 'opacity-100 border-border'
                  : 'opacity-35 border-border/40'"
              >
                <button
                  v-for="item in section.children"
                  :key="item.id"
                  class="w-full text-left rounded-md px-2 py-1 text-xs transition-colors"
                  :class="isAnchorActive(item.id)
                    ? 'text-primary font-semibold bg-primary/10'
                    : 'text-muted-foreground hover:text-foreground'"
                  @click="scrollToAnchor(item.id)"
                >
                  {{ item.title }}
                </button>
              </div>
            </div>
          </nav>
        </div>
      </aside>

      <!-- Main -->
      <main class="flex-1 max-w-3xl ml-0 lg:ml-12 space-y-16">
        <!-- Header -->
        <header class="space-y-5">
          <div class="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card px-3 py-1 text-xs text-muted-foreground shadow-sm">
            <FileCode2 class="w-3.5 h-3.5" />
            技术文档
          </div>

          <div class="space-y-3">
            <h1 class="text-4xl lg:text-5xl font-semibold tracking-tight bg-gradient-to-r from-slate-950 via-slate-700 to-slate-500 dark:from-white dark:via-cyan-100 dark:to-slate-400 bg-clip-text text-transparent">
              核心技术详解
            </h1>
            <p class="text-base lg:text-lg text-muted-foreground">
              LawGent 背后的底层架构与算法实现
            </p>
          </div>

        <div class="h-px border-t border-dashed border-border/60" />
        </header>

        <!-- Module 1 -->
        <section class="space-y-8">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl border border-primary/40 bg-primary/10 text-primary flex items-center justify-center">
              <BrainCircuit class="w-5 h-5" />
            </div>
            <div>
              <h2 class="text-2xl font-semibold tracking-tight">模块一 · LangChain Agent 设计</h2>
          <p class="mt-1 text-sm text-muted-foreground">四阶段状态机 + PostgreSQL 持久化 + 可中断确认链路</p>
            </div>
          </div>

          <article id="agent-overview" class="scroll-mt-28 rounded-2xl border border-primary/30 bg-primary/5 p-6">
            <div class="flex items-start gap-3">
              <div class="mt-0.5 w-7 h-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
                <Sparkles class="w-4 h-4" />
              </div>
              <div>
                <p class="text-sm font-medium text-primary">设计概述</p>
                <p class="mt-2 text-sm leading-7 text-muted-foreground">
                  LawGent 将法律咨询流程拆分为 Stage 1~4 状态机，每个阶段对应独立的 service 函数处理对话与业务逻辑。
                  会话状态与各阶段产物持久化到 PostgreSQL，支持断点恢复；确认卡点（/confirm）允许用户拒绝后回退到当前阶段重新收集。
                </p>
              </div>
            </div>
          </article>

          <article id="agent-state" class="scroll-mt-28 space-y-3">
            <div class="flex items-center gap-2">
              <GitBranch class="w-4 h-4 text-muted-foreground" />
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">状态机设计</h3>
            </div>

            <div class="rounded-2xl border border-border/60 bg-card p-3 shadow-sm">
              <div class="grid grid-cols-12 gap-2 px-3 py-2 text-[11px] uppercase tracking-wider text-muted-foreground">
                <span class="col-span-3">字段名</span>
                <span class="col-span-3">类型</span>
                <span class="col-span-6">说明</span>
              </div>

              <div class="space-y-2">
                <div
                  v-for="field in stateFields"
                  :key="field.name"
                  class="grid grid-cols-12 gap-2 rounded-xl border border-border/60 bg-muted/40 px-3 py-3"
                >
                  <span class="col-span-12 md:col-span-3 inline-flex items-center text-xs font-mono font-semibold text-primary">
                    {{ field.name }}
                  </span>
                  <span class="col-span-12 md:col-span-3 text-xs font-mono text-muted-foreground">
                    {{ field.type }}
                  </span>
                  <span class="col-span-12 md:col-span-6 text-xs text-muted-foreground">
                    {{ field.desc }}
                  </span>
                </div>
              </div>
            </div>
          </article>

          <article id="agent-timeline" class="scroll-mt-28 space-y-4">
            <div class="flex items-center gap-2">
              <Waypoints class="w-4 h-4 text-muted-foreground" />
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">Stage 1~4 垂直时间线</h3>
            </div>

            <ol class="relative ml-3 border-l border-dashed border-border/60 pl-8 space-y-6">
              <li v-for="item in stageTimeline" :key="item.stage" class="relative">
                <span class="absolute -left-[37px] top-1 w-5 h-5 rounded-full border border-primary/40 bg-primary/10 text-primary flex items-center justify-center">
                  <Check class="w-3 h-3" />
                </span>

                <div class="rounded-2xl border border-border/60 bg-card p-4 shadow-sm">
                  <p class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {{ item.stage }}
                  </p>
                  <p class="mt-2 text-sm text-muted-foreground">{{ item.summary }}</p>

                  <div class="mt-3 flex flex-wrap gap-2">
                    <span
                      v-for="node in item.nodes"
                      :key="node"
                      class="inline-flex items-center rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 text-[11px] font-mono font-semibold tracking-wide text-primary"
                    >
                      {{ node }}
                    </span>
                  </div>

                  <p class="mt-3 text-xs leading-6 text-muted-foreground">{{ item.description }}</p>
                </div>
              </li>
            </ol>
          </article>

          <article id="agent-realtime" class="scroll-mt-28 space-y-4">
            <div class="grid gap-4 md:grid-cols-2">
              <div
                v-for="card in realtimeCards"
                :key="card.title"
                class="rounded-2xl border border-border/60 bg-card p-5 shadow-sm"
              >
                <div class="w-8 h-8 rounded-lg bg-muted text-muted-foreground flex items-center justify-center">
                  <component :is="card.icon" class="w-4 h-4" />
                </div>
                <h4 class="mt-3 text-sm font-semibold">{{ card.title }}</h4>
                <p class="mt-2 text-xs leading-6 text-muted-foreground">{{ card.desc }}</p>
              </div>
            </div>

            <!-- SSE 事件类型表 -->
            <div class="rounded-2xl border border-border/60 bg-card p-5">
              <h4 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">SSE 事件类型</h4>
              <div class="space-y-2">
                <div class="grid grid-cols-12 gap-2 px-3 py-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <span class="col-span-3">事件类型</span>
                  <span class="col-span-5">触发时机</span>
                  <span class="col-span-4">前端处理</span>
                </div>
                <div
                  v-for="ev in sseEvents"
                  :key="ev.type"
                  class="grid grid-cols-12 gap-2 rounded-xl border border-border/60 bg-muted/40 px-3 py-3"
                >
                  <span class="col-span-12 md:col-span-3 font-mono text-xs font-semibold text-primary">{{ ev.type }}</span>
                  <span class="col-span-12 md:col-span-5 text-xs text-muted-foreground">{{ ev.when }}</span>
                  <span class="col-span-12 md:col-span-4 text-xs text-muted-foreground">{{ ev.note }}</span>
                </div>
              </div>
            </div>
          </article>

          <!-- 阶段路由机制 -->
          <article id="agent-route" class="scroll-mt-28 space-y-3">
            <div class="flex items-center gap-2">
              <GitBranch class="w-4 h-4 text-muted-foreground" />
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">阶段路由机制</h3>
            </div>
            <div class="rounded-2xl border border-border/60 bg-card p-5 space-y-3">
              <p class="text-xs leading-6 text-muted-foreground">
                <code class="text-primary font-mono">/message</code> 接口接收用户消息后，读取当前
                <code class="text-primary font-mono">conv.stage</code>，路由到对应 service 函数处理，不同阶段上下文构建策略各不相同。
              </p>
              <div class="space-y-2">
                <div class="grid grid-cols-12 gap-2 px-3 py-1.5 text-[11px] uppercase tracking-wider text-muted-foreground">
                  <span class="col-span-3">当前阶段</span>
                  <span class="col-span-3">路由函数</span>
                  <span class="col-span-6">说明</span>
                </div>
                <div
                  v-for="rule in routeRules"
                  :key="rule.stage"
                  class="grid grid-cols-12 gap-2 rounded-xl border border-border/60 bg-muted/40 px-3 py-3"
                >
                  <span class="col-span-12 md:col-span-3 font-mono text-xs font-semibold text-primary">{{ rule.stage }}</span>
                  <span class="col-span-12 md:col-span-3 font-mono text-xs text-muted-foreground">{{ rule.fn }}</span>
                  <span class="col-span-12 md:col-span-6 text-xs text-muted-foreground">{{ rule.note }}</span>
                </div>
              </div>
            </div>
          </article>

          <!-- 后台异步任务 -->
          <article id="agent-async" class="scroll-mt-28 space-y-3">
            <div class="flex items-center gap-2">
              <Waypoints class="w-4 h-4 text-muted-foreground" />
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">后台异步任务</h3>
            </div>
            <div class="space-y-4">
              <div
                v-for="task in asyncTasks"
                :key="task.title"
                class="rounded-2xl border border-border/60 bg-card p-5 shadow-sm space-y-3"
              >
                <div class="flex items-center justify-between">
                  <h4 class="text-sm font-semibold text-foreground">{{ task.title }}</h4>
                  <span class="font-mono text-[11px] text-primary bg-primary/10 border border-primary/20 px-2 py-0.5 rounded-md">{{ task.fn }}</span>
                </div>
                <p class="text-xs text-muted-foreground">
                  <span class="font-medium text-foreground">触发时机：</span>{{ task.trigger }}
                </p>
                <div class="space-y-1.5">
                  <div
                    v-for="(step, idx) in task.steps"
                    :key="idx"
                    class="flex items-start gap-2 text-xs text-muted-foreground"
                  >
                    <span class="mt-0.5 shrink-0 inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary/10 text-[10px] font-mono font-semibold text-primary">{{ idx + 1 }}</span>
                    <span>{{ step }}</span>
                  </div>
                </div>
                <p class="text-xs text-muted-foreground border-t border-border/60 pt-3">
                  <span class="font-medium text-foreground">前端感知：</span>{{ task.poll }}
                </p>
              </div>
            </div>
          </article>
        </section>

        <div class="h-px border-t border-dashed border-border/60" />

        <!-- Module 2 -->
        <section class="space-y-8">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl border border-indigo-300/60 bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 dark:border-indigo-700/70 dark:bg-indigo-500/10 flex items-center justify-center">
              <Search class="w-5 h-5" />
            </div>
            <div>
              <h2 class="text-2xl font-semibold tracking-tight">模块二 · 智能检索系统</h2>
              <p class="mt-1 text-sm text-muted-foreground">5 路并行检索架构，按需启用并通过 RRF 统一排序</p>
            </div>
          </div>

          <article id="search-overview" class="scroll-mt-28 space-y-4">
            <div class="rounded-2xl border border-border/60 bg-card p-5">
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">为什么需要 5 路检索</h3>
              <div class="mt-3 grid gap-3 md:grid-cols-3">
                <div
                  v-for="item in retrievalWhyFive"
                  :key="item.title"
                  class="rounded-xl border border-border/60 bg-muted/40 p-3"
                >
                  <p class="text-xs font-semibold text-foreground">{{ item.title }}</p>
                  <p class="mt-1.5 text-xs leading-6 text-muted-foreground">{{ item.detail }}</p>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-indigo-200/70 bg-indigo-50/60 p-5 dark:border-indigo-900/70 dark:bg-indigo-950/20">
              <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">搜索词来源（Stage 1 → Stage 2）</h3>
              <p class="mt-2 text-xs leading-6 text-muted-foreground">
                S2 启动时，<code class="text-primary font-mono">_gen_queries(summary)</code> 一次调用 LLM，传入 S1 案情摘要，返回包含 5 个字段的 JSON，各路检索器分别取对应字段作为查询文本，避免直接使用原始长对话带来的噪声。
              </p>
              <div class="mt-3 space-y-2">
                <div
                  v-for="item in retrievalInputMapping"
                  :key="item.source"
                  class="rounded-lg border border-border/60 bg-card px-3 py-2.5"
                >
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="text-[11px] font-semibold text-indigo-700 dark:text-indigo-300">{{ item.source }}</span>
                    <span class="text-[10px] font-mono rounded-md border border-indigo-300/50 bg-indigo-500/10 px-1.5 py-0.5 text-indigo-700 dark:text-indigo-300">→ {{ item.routes }}</span>
                  </div>
                  <p class="mt-1 text-xs leading-6 text-muted-foreground">{{ item.usage }}</p>
                </div>
              </div>
            </div>

            <div class="rounded-xl border border-border/60 bg-muted/40 px-3 py-3">
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-2">
                <div
                  v-for="(item, idx) in retrievalFlow"
                  :key="item.key"
                  class="relative rounded-lg border border-border/60 bg-card px-3 py-2.5"
                >
                  <div class="flex items-center gap-2">
                    <span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-mono font-semibold text-primary">
                      {{ idx + 1 }}
                    </span>
                    <component :is="item.icon" class="w-3.5 h-3.5 text-muted-foreground" />
                    <span class="text-[11px] font-semibold tracking-wide text-foreground">{{ item.label }}</span>
                  </div>
                  <p class="mt-1.5 text-[11px] text-muted-foreground">{{ item.hint }}</p>
                </div>
              </div>
            </div>
          </article>

          <article id="search-paths" class="scroll-mt-28 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div
              v-for="card in retrievalCards"
              :key="card.title"
              class="group rounded-2xl border border-border/60 bg-card p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-lg"
            >
              <div class="flex items-center justify-between">
                <div class="w-8 h-8 rounded-lg bg-muted text-muted-foreground flex items-center justify-center">
                  <component :is="card.icon" class="w-4 h-4" />
                </div>
                <span class="text-[10px] font-mono tracking-wider uppercase text-muted-foreground">{{ card.badge }}</span>
              </div>

              <h4 class="mt-4 text-sm font-semibold text-foreground">{{ card.title }}</h4>
              <p class="mt-1 text-[11px] font-mono text-primary">{{ card.api }}</p>
              <p class="mt-2 text-xs leading-6 text-muted-foreground">{{ card.desc }}</p>
            </div>
          </article>

          <article id="search-rrf" class="scroll-mt-28 space-y-3">
            <div class="rounded-2xl border border-border/60 bg-card p-5">
              <MarkdownViewer :content="rrfMarkdown" />
            </div>
            <div class="grid gap-3 md:grid-cols-3">
              <div
                v-for="item in rrfImplNotes"
                :key="item.title"
                class="rounded-xl border border-border/60 bg-muted/40 p-4"
              >
                <p class="text-xs font-semibold text-foreground">{{ item.title }}</p>
                <p class="mt-1.5 text-xs leading-6 text-muted-foreground">{{ item.detail }}</p>
              </div>
            </div>
          </article>
        </section>

        <div class="h-px border-t border-dashed border-border/60" />

        <!-- Module 3 -->
        <section class="space-y-8">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl border border-emerald-300/60 bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 dark:border-emerald-700/70 dark:bg-emerald-500/10 flex items-center justify-center">
              <Cpu class="w-5 h-5" />
            </div>
            <div>
              <h2 class="text-2xl font-semibold tracking-tight">模块三 · Lawformer 微调</h2>
              <p class="mt-1 text-sm text-muted-foreground">面向刑事语境的语义表示优化</p>
            </div>
          </div>

          <article
            v-for="note in finetuneNotes"
            :id="note.id"
            :key="note.id"
            class="scroll-mt-28 rounded-2xl border border-border/60 bg-card p-5"
          >
            <div class="border-l-2 border-emerald-400/70 pl-4">
              <p class="text-[11px] uppercase tracking-wider text-emerald-600 dark:text-emerald-400">{{ note.summary }}</p>
              <p class="mt-1 text-sm font-semibold text-foreground">{{ note.title }}</p>
              <p class="mt-2 text-sm leading-7 text-muted-foreground">{{ note.text }}</p>
            </div>
          </article>

          <article class="rounded-2xl border border-emerald-200/70 bg-emerald-50/60 p-5 dark:border-emerald-900/70 dark:bg-emerald-950/20">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">训练数据来源与构建流程</h3>
            <div class="mt-3 space-y-2">
              <div
                v-for="item in finetuneDataPipeline"
                :key="item.step"
                class="rounded-lg border border-border/60 bg-card px-3 py-3"
              >
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-emerald-500/15 px-1.5 text-[10px] font-mono font-semibold text-emerald-700 dark:text-emerald-300">
                    {{ item.step }}
                  </span>
                  <p class="text-xs font-semibold text-foreground">{{ item.title }}</p>
                </div>
                <p class="mt-1.5 text-xs leading-6 text-muted-foreground">{{ item.detail }}</p>
              </div>
            </div>
          </article>

          <article class="rounded-2xl border border-emerald-200/70 bg-emerald-50/60 p-5 dark:border-emerald-900/70 dark:bg-emerald-950/20">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">实验配置摘要</h3>
            <div class="mt-3 grid gap-2 sm:grid-cols-2">
              <div
                v-for="item in finetuneConfig"
                :key="item.key"
                class="rounded-lg border border-border/60 bg-card px-3 py-3"
              >
                <p class="text-[11px] text-muted-foreground">{{ item.key }}</p>
                <p class="mt-1 text-xs font-medium text-foreground">{{ item.value }}</p>
              </div>
            </div>
          </article>

          <article class="rounded-2xl border border-border/60 bg-card p-5">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">抽象示例：排序前后变化</h3>
            <div class="mt-3 rounded-xl border border-border/60 bg-muted/40 p-4">
              <p class="text-xs text-muted-foreground">示例案情</p>
              <p class="mt-1 text-sm font-medium text-foreground">{{ finetuneExample.query }}</p>

              <div class="mt-4 grid gap-3 md:grid-cols-2">
                <div class="rounded-lg border border-border/60 bg-card p-3">
                  <p class="text-[11px] uppercase tracking-wider text-muted-foreground">微调前 Top-3</p>
                  <ul class="mt-2 space-y-1 text-xs text-muted-foreground">
                    <li v-for="item in finetuneExample.beforeTop3" :key="item">• {{ item }}</li>
                  </ul>
                </div>
                <div class="rounded-lg border border-emerald-200/80 bg-emerald-50/70 p-3 dark:border-emerald-800/70 dark:bg-emerald-950/30">
                  <p class="text-[11px] uppercase tracking-wider text-emerald-700 dark:text-emerald-300">微调后 Top-3</p>
                  <ul class="mt-2 space-y-1 text-xs text-emerald-800 dark:text-emerald-200">
                    <li v-for="item in finetuneExample.afterTop3" :key="item">• {{ item }}</li>
                  </ul>
                </div>
              </div>

              <p class="mt-4 text-xs leading-6 text-muted-foreground">{{ finetuneExample.note }}</p>
            </div>
          </article>

          <article id="finetune-metrics" class="scroll-mt-28 space-y-3">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">评估结果对比</h3>
            <div class="overflow-hidden rounded-2xl border border-border/60 bg-card p-5">
              <div class="grid grid-cols-12 gap-2 px-4 py-3 text-[11px] uppercase tracking-wider text-muted-foreground border-b border-border/60">
                <span class="col-span-5">指标</span>
                <span class="col-span-2 text-center">原始</span>
                <span class="col-span-2 text-center">微调后</span>
                <span class="col-span-3 text-center">提升</span>
              </div>

              <div
                v-for="row in metricRows"
                :key="row.metric"
                class="grid grid-cols-12 gap-2 items-center px-4 py-4 border-b border-border/40"
              >
                <span class="col-span-12 md:col-span-5 text-sm font-medium text-foreground">{{ row.metric }}</span>
                <span class="col-span-4 md:col-span-2 text-sm text-center text-muted-foreground">{{ row.before }}</span>
                <span class="col-span-4 md:col-span-2 text-sm text-center text-foreground font-semibold">{{ row.after }}</span>
                <span class="col-span-4 md:col-span-3 inline-flex items-center justify-center gap-1 text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                  <TrendingUp class="w-4 h-4" />
                  {{ row.uplift }}
                </span>
              </div>
            </div>

            <div class="mt-4 rounded-xl border border-emerald-200/70 bg-emerald-50/70 px-4 py-3 dark:border-emerald-900/70 dark:bg-emerald-950/20">
              <p class="text-xs leading-6 text-emerald-800 dark:text-emerald-200">{{ finetuneInsight }}</p>
            </div>
          </article>
        </section>

        <div class="h-px border-t border-dashed border-border/60" />

        <!-- Module 4 -->
        <section class="space-y-8">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl border border-sky-300/60 bg-sky-500/10 text-sky-600 dark:text-sky-300 dark:border-sky-700/70 dark:bg-sky-500/10 flex items-center justify-center">
              <Network class="w-5 h-5" />
            </div>
            <div>
              <h2 class="text-2xl font-semibold tracking-tight">模块四 · 知识图谱构建</h2>
              <p class="mt-1 text-sm text-muted-foreground">罪名—法条关系网络与快速实体匹配</p>
            </div>
          </div>

          <article id="kg-overview" class="scroll-mt-28 rounded-2xl border border-sky-200/70 bg-sky-50/70 p-6 dark:border-sky-900/70 dark:bg-sky-950/20">
            <p class="text-sm leading-7 text-muted-foreground">
              该知识图谱基于案件标注数据构建：先抽取 accusation（罪名）与 relevant_articles（法条）关系，
              再做规则清洗与双向索引，最终生成可持久化图谱并在检索阶段作为可解释路径参与 5 路融合。
            </p>
          </article>

          <article id="kg-process" class="scroll-mt-28 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <div
              v-for="step in kgProcess"
              :key="step.title"
              class="rounded-2xl border border-border/60 bg-card p-5 shadow-sm"
            >
              <div class="w-8 h-8 rounded-lg bg-muted text-muted-foreground flex items-center justify-center">
                <component :is="step.icon" class="w-4 h-4" />
              </div>
              <h4 class="mt-3 text-sm font-semibold">{{ step.title }}</h4>
              <p class="mt-2 text-xs leading-6 text-muted-foreground">{{ step.desc }}</p>
            </div>
          </article>

          <article class="rounded-2xl border border-border/60 bg-card p-5">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">构建流程</h3>
            <div class="mt-3 space-y-2">
              <div
                v-for="item in kgBuildPipeline"
                :key="item.step"
                class="rounded-lg border border-border/60 bg-muted/40"
              >
                <div class="flex items-center gap-2">
                  <span class="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-sky-500/12 px-1.5 text-[10px] font-mono font-semibold text-sky-700 dark:text-sky-300">{{ item.step }}</span>
                  <p class="text-xs font-semibold text-foreground">{{ item.title }}</p>
                </div>
                <p class="mt-1.5 text-xs leading-6 text-muted-foreground">{{ item.detail }}</p>
              </div>
            </div>
          </article>

          <article id="kg-example" class="scroll-mt-28 rounded-2xl border border-border/60 bg-card p-5">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">检索示例（从问句到法条）</h3>
            <div class="mt-3 rounded-xl border border-border/60 bg-muted/40 p-4">
              <p class="text-xs text-muted-foreground">用户问句</p>
              <p class="mt-1 text-sm font-medium text-foreground">{{ kgExample.query }}</p>

              <div class="mt-4 grid gap-3 md:grid-cols-3">
                <div class="rounded-lg border border-border/60 bg-card p-3">
                  <p class="text-[11px] uppercase tracking-wider text-muted-foreground">实体命中</p>
                  <ul class="mt-2 space-y-1 text-xs text-muted-foreground">
                    <li v-for="item in kgExample.matchedEntities" :key="item">• {{ item }}</li>
                  </ul>
                </div>

                <div class="rounded-lg border border-border/60 bg-card p-3">
                  <p class="text-[11px] uppercase tracking-wider text-muted-foreground">图谱关系追踪</p>
                  <ul class="mt-2 space-y-1 text-xs text-muted-foreground">
                    <li v-for="item in kgExample.graphLinks" :key="item">• {{ item }}</li>
                  </ul>
                </div>

                <div class="rounded-lg border border-sky-200/80 bg-sky-50/70 p-3 dark:border-sky-800/70 dark:bg-sky-950/30">
                  <p class="text-[11px] uppercase tracking-wider text-sky-700 dark:text-sky-300">检索输出</p>
                  <p class="mt-2 text-xs leading-6 text-sky-800 dark:text-sky-200">{{ kgExample.output }}</p>
                </div>
              </div>
            </div>
          </article>

          <article id="kg-boundary" class="scroll-mt-28 rounded-2xl border border-sky-200/70 bg-sky-50/60 p-5 dark:border-sky-900/70 dark:bg-sky-950/20 space-y-4">
            <h3 class="text-sm font-semibold tracking-wide uppercase text-muted-foreground">使用方式与边界说明</h3>

            <div class="rounded-xl border border-border/60 bg-card p-4">
              <p class="text-[11px] uppercase tracking-wider text-sky-700 dark:text-sky-300">在线检索流程</p>
              <div class="mt-2 grid gap-2 sm:grid-cols-2">
                <div
                  v-for="item in kgUseFlow"
                  :key="item.phase"
                  class="rounded-lg border border-sky-200/70 bg-sky-50/70 px-3 py-2 dark:border-sky-800/70 dark:bg-sky-950/30"
                >
                  <p class="text-xs font-semibold text-sky-800 dark:text-sky-200">{{ item.phase }}</p>
                  <p class="mt-1 text-[11px] leading-5 text-muted-foreground">{{ item.detail }}</p>
                </div>
              </div>
            </div>

            <ul class="space-y-2">
              <li
                v-for="item in kgBoundaryNotes"
                :key="item"
                class="flex items-start gap-2 text-xs leading-6 text-muted-foreground"
              >
                <span class="mt-2 h-1.5 w-1.5 rounded-full bg-sky-500/70 shrink-0" />
                <span>{{ item }}</span>
              </li>
            </ul>
          </article>

          <article id="kg-stats" class="scroll-mt-28 space-y-3">
            <p class="text-[11px] text-muted-foreground">数据来源：knowledge_graph.meta.json（当前版本）</p>
            <div class="grid gap-4 sm:grid-cols-2 md:grid-cols-3">
              <div
                v-for="item in kgStats"
                :key="item.title"
                class="rounded-2xl bg-gradient-to-br p-[1px]"
                :class="item.glow"
              >
                <div class="rounded-2xl border border-border/60 bg-card p-4 shadow-sm">
                  <div class="flex items-center justify-between">
                    <span class="text-xs uppercase tracking-[0.12em] text-muted-foreground">{{ item.title }}</span>
                    <component :is="item.icon" class="w-4 h-4 text-muted-foreground" />
                  </div>
                  <p class="mt-4 text-3xl font-semibold tracking-tight">{{ item.value }}</p>
                </div>
              </div>
            </div>
          </article>
        </section>
      </main>
    </div>

    <!-- Mobile floating TOC trigger -->
    <button
      class="fixed bottom-6 right-6 z-40 lg:hidden inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/95 px-4 py-2.5 text-sm font-medium shadow-lg backdrop-blur dark:bg-card/90"
      @click="isTocOpen = true"
    >
      <Menu class="w-4 h-4" />
      目录
    </button>

    <!-- Mobile TOC Drawer -->
    <div v-if="isTocOpen" class="fixed inset-0 z-50 lg:hidden">
      <div class="absolute inset-0 bg-black/45 backdrop-blur-sm" @click="isTocOpen = false" />

      <Transition
        enter-active-class="transition duration-300 ease-out"
        enter-from-class="translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition duration-200 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="translate-x-full"
      >
        <aside class="absolute right-0 top-0 h-full w-[84%] max-w-sm border-l border-border/60 bg-card p-4 dark:bg-card">
          <div class="flex items-center justify-between pb-3 border-b border-border/60">
            <p class="text-sm font-semibold">页面目录</p>
            <button class="rounded-md p-1.5 hover:bg-muted" @click="isTocOpen = false">
              <X class="w-4 h-4" />
            </button>
          </div>

          <div class="mt-4 space-y-4 overflow-y-auto h-[calc(100%-3.5rem)]">
            <div v-for="section in tocTree" :key="section.id" class="space-y-1">
              <p
                class="text-xs uppercase tracking-wider"
                :class="isSectionActive(section.id)
                  ? 'text-foreground font-semibold'
                  : 'text-muted-foreground'"
              >
                {{ section.title }}
              </p>

              <button
                v-for="item in section.children"
                :key="item.id"
                class="w-full flex items-center justify-between rounded-lg px-2 py-2 text-left text-sm transition-colors"
                :class="isAnchorActive(item.id)
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted/70'"
                @click="scrollToAnchor(item.id)"
              >
                <span>{{ item.title }}</span>
                <ChevronRight class="w-4 h-4" />
              </button>
            </div>
          </div>
        </aside>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
/* Tailwind-first：视觉样式主要由原子类完成 */
</style>
