<script setup lang="ts">
import { apiUrl } from '@/lib/api'
import { computed, ref, onMounted } from 'vue'
import NavBar from '@/components/ui/NavBar.vue'
import Badge from '@/components/ui/Badge.vue'
import { useRouter } from 'vue-router'
import {
  Scale,
  BookOpen,
  BrainCircuit,
  Search,
  Cpu,
  Network,
  ArrowRight,
  Database,
  Users,
  Lightbulb,
} from 'lucide-vue-next'

const router = useRouter()

interface Stats {
  total_crimes: number
  total_articles: number
  total_relations: number
  total_cases: number
  top_crimes: [string, number][]
  top_articles: [string, number][]
  kg_loaded: boolean
  vectors_loaded: boolean
}

const stats = ref<Stats | null>(null)

onMounted(async () => {
  try {
    const res = await fetch(apiUrl('/stats'))
    stats.value = await res.json()
  } catch {}
})

const topCrimeMax = computed(() => stats.value?.top_crimes?.[0]?.[1] ?? 1)
const topArticleMax = computed(() => stats.value?.top_articles?.[0]?.[1] ?? 1)

const philosophyItems = [
  {
    icon: Scale,
    title: '检索先于生成',
    desc: '法律问题不能靠模型"凭感觉"回答。LawGent 强制先检索真实案例与法条，再由 LLM 基于证据推理，而非凭空生成。',
    color: 'text-primary bg-primary/10 border-primary/30',
  },
  {
    icon: Users,
    title: '人在回路中',
    desc: '关键节点由用户确认，而非 AI 自动推进。系统在 Stage 1 和 Stage 3 主动暂停，等待用户核实案情事实后再继续。',
    color: 'text-violet-600 dark:text-violet-300 bg-violet-500/10 border-violet-200 dark:border-violet-800',
  },
  {
    icon: Lightbulb,
    title: '可解释优先',
    desc: '每一条检索结果都有来源路径（向量/BM25/知识图谱/Query2Doc/HyDE），每一份报告都附有引用法条，让用户知道结论从何而来。',
    color: 'text-orange-600 dark:text-orange-300 bg-orange-500/10 border-orange-200 dark:border-orange-800',
  },
  {
    icon: Scale,
    title: '辅助而非替代',
    desc: 'LawGent 的定位是风险提示工具，不是律师替代品。系统输出基于历史案例统计，不构成正式法律意见，复杂案情仍需专业律师介入。',
    color: 'text-primary bg-primary/10 border-primary/30',
  },
]

const flowSteps = [
  { step: '01', title: '多轮对话收集案情', desc: 'Agent 通过对话提取涉嫌罪名、伤情、作案方式等核心事实，用户确认后进入下一阶段。' },
  { step: '02', title: '5路并行检索', desc: '以案情摘要为输入，同时触发向量、BM25、知识图谱、Query2Doc、HyDE 五路检索，RRF 融合排序。' },
  { step: '03', title: '量刑细节补充', desc: '基于检索结果追问自首、赔偿、前科等量刑变量，二次确认后进入报告生成。' },
  { step: '04', title: '生成风险评估报告', desc: '整合事实与检索证据，输出结构化 JSON 报告，通过 SSE 实时推送到前端展示。' },
]

const dataSources = [
  {
    name: 'CAIL2018',
    label: '案例数据',
    desc: '17,547 条刑事裁判文书，含案件事实、罪名标注与适用法条，由清华大学 NLP 实验室发布。',
    url: 'https://github.com/thunlp/CAIL',
    color: 'text-primary bg-primary/10 border-primary/30',
  },
  {
    name: 'LawRefBook/Laws',
    label: '法条数据',
    desc: '446 条刑法条文，结构化法条文本，包含条文号、标题与内容，来源于开源法律数据库。',
    url: 'https://github.com/LawRefBook/Laws',
    color: 'text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-200 dark:border-emerald-800',
  },
  {
    name: 'thunlp/Lawformer',
    label: '预训练模型',
    desc: '清华大学 NLP 实验室发布的法律领域长文本预训练模型，基于 Longformer 架构，768 维向量表示。',
    url: 'https://huggingface.co/thunlp/Lawformer',
    color: 'text-violet-600 dark:text-violet-300 bg-violet-500/10 border-violet-200 dark:border-violet-800',
  },
]

const citations = [
  {
    label: 'CAIL2018 数据集',
    text: 'Chaojun Xiao et al. CAIL2018: A Large-Scale Legal Dataset for Judgment Prediction. arXiv:1807.02478, 2018.',
    url: 'https://arxiv.org/abs/1807.02478',
  },
  {
    label: 'Lawformer 模型',
    text: 'Haoxi Zhong et al. How Does NLP Benefit Legal System: A Summary of Legal Artificial Intelligence. ACL 2020.',
    url: 'https://huggingface.co/thunlp/Lawformer',
  },
]

const techEntries = [
  { title: 'LangChain Agent 设计', desc: '四阶段状态机、HITL 确认、SSE 流式推送', to: '/tech#agent', icon: BrainCircuit, color: 'text-primary bg-primary/10 border-primary/30' },
  { title: '智能检索系统', desc: '5路并行 + RRF 融合，覆盖向量、BM25、KG、Query2Doc、HyDE', to: '/tech#search-system', icon: Search, color: 'text-indigo-600 dark:text-indigo-300 bg-indigo-500/10 border-indigo-200 dark:border-indigo-800' },
  { title: 'Lawformer 微调', desc: 'CAIL2018 对比学习微调，768维法律语义向量', to: '/tech#lawformer-finetune', icon: Cpu, color: 'text-emerald-600 dark:text-emerald-300 bg-emerald-500/10 border-emerald-200 dark:border-emerald-800' },
  { title: '知识图谱构建', desc: '202罪名 · 183法条 · 23,561关联边，AC自动机实体匹配', to: '/tech#knowledge-graph', icon: Network, color: 'text-orange-600 dark:text-orange-300 bg-orange-500/10 border-orange-200 dark:border-orange-800' },
]
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <NavBar />

    <main class="max-w-4xl mx-auto px-4 lg:px-6 pb-16 pt-8 lg:pt-12 space-y-12">

      <!-- 页面标题 -->
      <header class="space-y-5">
        <div class="inline-flex items-center gap-2 rounded-full border border-border/60 bg-card px-3 py-1 text-xs text-muted-foreground shadow-sm">
          <BookOpen class="w-3.5 h-3.5" />
          项目介绍
        </div>
        <div class="space-y-3">
          <h1 class="text-4xl lg:text-5xl font-semibold tracking-tight bg-gradient-to-r from-slate-950 via-slate-700 to-slate-500 dark:from-white dark:via-cyan-100 dark:to-slate-400 bg-clip-text text-transparent">
            关于 LawGent
          </h1>
          <p class="text-base lg:text-lg text-muted-foreground max-w-2xl">
            一个面向刑事法律咨询场景的智能 Agent 系统，将检索增强与多轮对话结合，辅助用户理解案情风险。
          </p>
        </div>
        <div class="h-px border-t border-dashed border-border/60" />
      </header>

      <!-- 项目背景 -->
      <section class="space-y-4">
        <h2 class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">项目背景</h2>
        <div class="rounded-2xl border border-border/60 bg-card p-6 space-y-4">
          <div class="flex items-start gap-3">
            <div class="mt-0.5 w-8 h-8 rounded-lg bg-primary/10 text-primary border border-primary/30 flex items-center justify-center shrink-0">
              <Scale class="w-4 h-4" />
            </div>
            <div class="space-y-3 text-sm leading-7 text-muted-foreground">
              <p>
                刑事法律咨询门槛高、专业性强，普通用户面对复杂案情时难以快速判断风险。
                现有 LLM 直接回答法律问题存在幻觉风险，缺乏真实案例与法条支撑。
              </p>
              <p>
                LawGent 以 CAIL2018 刑事裁判文书数据集为基础，构建了覆盖 17,547 条案例的检索库，
                结合微调后的 Lawformer 向量模型与罪名-法条知识图谱，通过 LangChain Agent 驱动多轮对话，
                最终输出有据可查的风险评估报告。
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- 设计理念 -->
      <section class="space-y-4">
        <h2 class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">设计理念</h2>
        <div class="grid gap-4 md:grid-cols-2">
          <div
            v-for="item in philosophyItems"
            :key="item.title"
            class="rounded-2xl border border-border/60 bg-card p-5 shadow-sm"
          >
            <div class="w-9 h-9 rounded-xl border flex items-center justify-center" :class="item.color">
              <component :is="item.icon" class="w-4 h-4" />
            </div>
            <h3 class="mt-4 text-sm font-semibold text-foreground">{{ item.title }}</h3>
            <p class="mt-2 text-xs leading-6 text-muted-foreground">{{ item.desc }}</p>
          </div>
        </div>
      </section>

      <!-- 数据集说明 -->
      <section class="space-y-4">
        <h2 class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">数据集说明</h2>
        <div class="rounded-2xl border border-border/60 bg-card p-6 space-y-5">
          <div class="flex items-start gap-3">
            <div class="mt-0.5 w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center shrink-0">
              <Database class="w-4 h-4" />
            </div>
            <div class="space-y-2 text-sm leading-7 text-muted-foreground">
              <p>
                核心数据来源于 <span class="font-semibold text-foreground">CAIL2018</span>（中国法律智能技术评测），
                包含真实刑事裁判文书，每条记录含案件事实、罪名标注与适用法条。
              </p>
              <p>
                经清洗与向量化后，系统共索引 <span class="font-semibold text-foreground">17,547 条</span>案例文档，
                并从中抽取罪名-法条共现关系构建知识图谱。
                Lawformer 微调同样基于此数据集，采用三元组对比学习提升刑事语境下的语义匹配能力。
              </p>
            </div>
          </div>

          <!-- 数据来源卡片 -->
          <div class="grid gap-3 md:grid-cols-3 pt-1">
            <a
              v-for="src in dataSources"
              :key="src.name"
              :href="src.url"
              target="_blank"
              rel="noopener noreferrer"
              class="group rounded-xl border border-border/60 bg-muted/40 p-4 hover:border-border transition-colors"
            >
              <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] font-semibold px-2 py-0.5 rounded-md border" :class="src.color">{{ src.label }}</span>
                <ArrowRight class="w-3 h-3 text-muted-foreground group-hover:text-foreground group-hover:translate-x-0.5 transition-all" />
              </div>
              <p class="text-xs font-mono font-semibold text-foreground mb-1.5">{{ src.name }}</p>
              <p class="text-[11px] leading-5 text-muted-foreground">{{ src.desc }}</p>
            </a>
          </div>

          <!-- 数据分布 -->
          <div v-if="stats?.top_crimes?.length || stats?.top_articles?.length" class="grid md:grid-cols-2 gap-5 pt-2">

            <div v-if="stats?.top_crimes?.length">
              <h3 class="text-xs font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-primary inline-block"></span>
                高频罪名 Top 10
              </h3>
              <div class="rounded-xl border border-border/60 overflow-hidden">
                <div
                  v-for="(item, idx) in stats.top_crimes"
                  :key="item[0]"
                  class="flex items-center gap-3 px-4 py-2.5 border-b border-border/40 last:border-0 hover:bg-muted/40 transition-colors"
                >
                  <span class="text-xs font-mono text-muted-foreground w-4 text-right shrink-0">{{ idx + 1 }}</span>
                  <span class="flex-1 text-xs font-medium truncate">{{ item[0] }}</span>
                  <div class="flex items-center gap-2 shrink-0">
                    <div class="h-1 rounded-full bg-primary/20 w-16 overflow-hidden">
                      <div class="h-full bg-primary rounded-full" :style="{ width: (item[1] / topCrimeMax * 100) + '%' }"></div>
                    </div>
                    <span class="text-[11px] text-muted-foreground font-mono w-10 text-right">{{ item[1].toLocaleString() }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="stats?.top_articles?.length">
              <h3 class="text-xs font-semibold text-muted-foreground mb-3 flex items-center gap-1.5">
                <span class="w-2 h-2 rounded-full bg-orange-500 inline-block"></span>
                高频引用法条 Top 10
              </h3>
              <div class="rounded-xl border border-border/60 overflow-hidden">
                <div
                  v-for="(item, idx) in stats.top_articles"
                  :key="item[0]"
                  class="flex items-center gap-3 px-4 py-2.5 border-b border-border/40 last:border-0 hover:bg-muted/40 transition-colors"
                >
                  <span class="text-xs font-mono text-muted-foreground w-4 text-right shrink-0">{{ idx + 1 }}</span>
                  <span class="flex-1 text-xs font-medium">第 {{ item[0] }} 条</span>
                  <div class="flex items-center gap-2 shrink-0">
                    <div class="h-1 rounded-full bg-orange-500/20 w-16 overflow-hidden">
                      <div class="h-full bg-orange-500 rounded-full" :style="{ width: (item[1] / topArticleMax * 100) + '%' }"></div>
                    </div>
                    <span class="text-[11px] text-muted-foreground font-mono w-10 text-right">{{ item[1].toLocaleString() }}</span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </section>

      <!-- 系统工作流程 -->
      <section class="space-y-4">
        <h2 class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">系统工作流程</h2>
        <ol class="relative ml-3 border-l border-dashed border-border/60 pl-8 space-y-5">
          <li v-for="item in flowSteps" :key="item.step" class="relative">
            <span class="absolute -left-[37px] top-1 w-5 h-5 rounded-full border border-primary/40 bg-primary/10 text-primary flex items-center justify-center text-[10px] font-mono font-bold">
              {{ item.step }}
            </span>
            <div class="rounded-2xl border border-border/60 bg-card px-5 py-4 shadow-sm">
              <p class="text-sm font-semibold text-foreground">{{ item.title }}</p>
              <p class="mt-1.5 text-xs leading-6 text-muted-foreground">{{ item.desc }}</p>
            </div>
          </li>
        </ol>
      </section>

      <!-- 技术亮点入口 -->
      <section class="space-y-4">
        <div class="flex items-center justify-between">
          <h2 class="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">技术实现</h2>
          <button
            class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
            @click="router.push('/tech')"
          >
            查看完整技术文档
            <ArrowRight class="w-3.5 h-3.5" />
          </button>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <button
            v-for="entry in techEntries"
            :key="entry.title"
            class="group flex gap-4 p-5 bg-card border border-border/60 rounded-2xl shadow-sm hover:shadow-md hover:border-border transition-all duration-200 text-left"
            @click="router.push(entry.to)"
          >
            <div class="shrink-0 w-9 h-9 rounded-xl border flex items-center justify-center" :class="entry.color">
              <component :is="entry.icon" class="w-4 h-4" />
            </div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{{ entry.title }}</p>
              <p class="mt-1 text-xs text-muted-foreground leading-relaxed">{{ entry.desc }}</p>
            </div>
            <ArrowRight class="w-4 h-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0 self-center" />
          </button>
        </div>
      </section>

    </main>

    <!-- 引用声明 -->
    <div class="border-t border-border/60 bg-muted/30">
      <div class="max-w-4xl mx-auto px-4 lg:px-6 py-8 space-y-3">
        <p class="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-4">引用声明</p>
        <div v-for="cite in citations" :key="cite.label" class="flex items-start gap-3">
          <Badge variant="secondary" class="shrink-0 mt-0.5">{{ cite.label }}</Badge>
          <p class="text-[11px] leading-5 text-muted-foreground flex-1">
            {{ cite.text }}
            <a :href="cite.url" target="_blank" rel="noopener noreferrer" class="ml-1 text-primary hover:underline">↗</a>
          </p>
        </div>
      </div>
    </div>

    <footer class="border-t border-border/60 py-6 text-center text-xs text-muted-foreground">
      内容由 AI 生成，仅供参考，不构成正式法律意见
    </footer>
  </div>
</template>
