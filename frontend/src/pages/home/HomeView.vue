<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import NavBar from '@/components/ui/NavBar.vue'
import Badge from '@/components/ui/Badge.vue'
import { MessageSquare, Search, Scale, FileText } from 'lucide-vue-next'

const auth = useAuthStore()

interface Stats {
  total_crimes: number
  total_articles: number
  total_relations: number
  total_cases: number
}

const stats = ref<Stats | null>(null)

onMounted(async () => {
  try {
    const res = await fetch('/api/v1/stats')
    stats.value = await res.json()
  } catch {}
})

const stages = [
  { num: '01', title: '案情收集', desc: 'LLM 多轮对话提取涉嫌罪名与基本案情，结构化存储', icon: MessageSquare },
  { num: '02', title: '并发检索', desc: '向量 + BM25 + 知识图谱 + Query2Doc + HyDE 5路并行，RRF 融合相关法条与类案', icon: Search },
  { num: '03', title: '情节补充', desc: '基于检索结果追问量刑情节，Human-in-the-loop 确认', icon: Scale },
  { num: '04', title: '报告生成', desc: 'LLM 综合案情与检索结果，生成结构化刑事风险评估报告', icon: FileText },
]

const activeStage = ref(-1)
const lastStage = ref(0)
</script>

<template>
  <div class="min-h-screen bg-background">
    <NavBar />

    <main class="max-w-6xl mx-auto px-4 py-16 space-y-20">

      <!-- Hero -->
      <section class="text-center space-y-6">
        <div class="inline-flex items-center gap-2 text-xs font-medium text-primary bg-primary/10 border border-primary/20 px-3 py-1 rounded-full">
          <span class="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
          毕业设计项目 · 刑事法律智能助手
        </div>
        <h1 class="text-4xl md:text-5xl font-bold font-serif tracking-tight">
          LawGent
          <span class="block text-2xl md:text-3xl text-muted-foreground font-normal mt-2">基于 LangChain 的刑事法律风险评估系统</span>
        </h1>
        <p class="text-muted-foreground max-w-2xl mx-auto leading-relaxed">
          融合知识图谱、向量检索与大语言模型，通过四阶段智能体工作流，为用户提供专业的刑事法律风险评估与量刑预测服务。
        </p>
        <div class="flex items-center justify-center gap-3 pt-2">
          <router-link to="/chat" v-if="auth.token">
            <button class="bg-primary text-primary-foreground px-6 py-2.5 rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-sm shadow-primary/20">开始咨询</button>
          </router-link>
          <router-link to="/login" v-else>
            <button class="bg-primary text-primary-foreground px-6 py-2.5 rounded-lg font-medium hover:bg-primary/90 transition-colors shadow-sm shadow-primary/20">开始咨询</button>
          </router-link>
          <router-link to="/search">
            <button class="border border-border px-6 py-2.5 rounded-lg font-medium hover:bg-muted transition-colors text-sm">检索演示</button>
          </router-link>
        </div>
      </section>

      <!-- Stats -->
      <section>
        <h2 class="text-center text-sm font-medium text-muted-foreground uppercase tracking-widest mb-8">数据规模</h2>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <router-link v-for="item in [
            { label: '刑法罪名', value: stats?.total_crimes ?? '—', unit: '个', to: '/graph' },
            { label: '法律条文', value: stats?.total_articles ?? '—', unit: '条', to: '/data?tab=articles' },
            { label: '知识图谱关系', value: stats?.total_relations?.toLocaleString() ?? '—', unit: '条', to: '/graph' },
            { label: '参考案例', value: stats?.total_cases?.toLocaleString() ?? '—', unit: '份', to: '/data?tab=cases' },
          ]" :key="item.label" :to="item.to"
            class="bg-card border border-border/60 rounded-xl p-5 text-center shadow-sm hover:border-primary/40 hover:shadow-md transition-all duration-200 cursor-pointer">
            <div class="text-3xl font-bold font-mono text-primary">{{ item.value }}</div>
            <div class="text-xs text-muted-foreground mt-1">{{ item.label }}</div>
          </router-link>
        </div>
      </section>

      <!-- Workflow -->
      <section>
        <h2 class="text-center text-sm font-medium text-muted-foreground uppercase tracking-widest mb-10">工作流程</h2>
        <div class="relative">
          <!-- 贯穿线底色 (desktop) -->
          <div class="hidden md:block absolute top-7 left-[10%] right-[10%] h-[2px] bg-border"></div>
          <!-- 竖线连接 (mobile) -->
          <div class="absolute left-[27px] top-6 bottom-6 w-[2px] bg-border md:hidden"></div>

          <div class="grid grid-cols-1 md:grid-cols-4 gap-8 md:gap-6 relative z-10">
            <div v-for="(stage, idx) in stages" :key="stage.num"
                 class="relative flex flex-col items-start md:items-center group"
                 @mouseenter="activeStage = idx; lastStage = idx"
                 @mouseleave="activeStage = -1">

              <!-- 图标节点 -->
              <div class="relative flex-shrink-0 w-14 h-14 rounded-full border-2 bg-background flex items-center justify-center z-10 transition-all duration-300"
                   :class="lastStage === idx ? 'border-primary text-primary shadow-md' : 'border-border text-muted-foreground'">
                <component :is="stage.icon" class="w-6 h-6" />
                <span class="absolute -top-2 -right-3 px-1.5 py-0.5 rounded-full text-[10px] font-bold shadow-sm transition-all duration-300"
                      :class="lastStage === idx ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'">
                  {{ stage.num }}
                </span>
              </div>

              <!-- 卡片内容 -->
              <div class="ml-16 md:ml-0 md:mt-6 w-full p-5 rounded-xl border bg-card shadow-sm transition-all duration-300 flex flex-col flex-1"
                   :class="activeStage === idx ? '-translate-y-2 shadow-lg border-primary/40' : 'border-border/60'">
                <div class="text-[10px] font-bold uppercase tracking-wider mb-2 transition-colors duration-300"
                     :class="activeStage === idx ? 'text-primary' : 'text-muted-foreground/70'">Stage {{ stage.num }}</div>
                <div class="font-semibold text-sm text-foreground mb-2">{{ stage.title }}</div>
                <div class="text-xs text-muted-foreground leading-relaxed">{{ stage.desc }}</div>
              </div>

            </div>
          </div>
        </div>
      </section>

    </main>

    <!-- 技术栈 -->
    <section class="border-t border-border/60 py-8">
      <div class="max-w-6xl mx-auto px-4">
        <p class="text-xs text-center text-muted-foreground uppercase tracking-widest mb-6">技术栈</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="space-y-2">
            <p class="text-xs text-muted-foreground font-medium">后端框架</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge variant="default">FastAPI</Badge>
              <Badge variant="default">SSE</Badge>
<Badge variant="default">Python</Badge>
            </div>
          </div>
          <div class="space-y-2">
            <p class="text-xs text-muted-foreground font-medium">前端框架</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge class="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400">Vue 3</Badge>
              <Badge class="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400">Tailwind CSS</Badge>
              <Badge class="bg-emerald-500/10 text-emerald-600 border-emerald-500/20 dark:text-emerald-400">ECharts</Badge>
            </div>
          </div>
          <div class="space-y-2">
            <p class="text-xs text-muted-foreground font-medium">AI / 模型</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge class="bg-violet-500/10 text-violet-600 border-violet-500/20 dark:text-violet-400">LangChain</Badge>
              <Badge class="bg-violet-500/10 text-violet-600 border-violet-500/20 dark:text-violet-400">DeepSeek</Badge>
              <Badge class="bg-violet-500/10 text-violet-600 border-violet-500/20 dark:text-violet-400">Lawformer</Badge>
            </div>
          </div>
          <div class="space-y-2">
            <p class="text-xs text-muted-foreground font-medium">检索 / 数据</p>
            <div class="flex flex-wrap gap-1.5">
              <Badge class="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400">向量检索</Badge>
              <Badge class="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400">BM25</Badge>
              <Badge class="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400">知识图谱</Badge>
              <Badge class="bg-amber-500/10 text-amber-600 border-amber-500/20 dark:text-amber-400">RRF 融合</Badge>
            </div>
          </div>
        </div>
      </div>
    </section>

    <footer class="border-t border-border/60 py-6 text-center text-xs text-muted-foreground">
      内容由 AI 生成，仅供参考，不构成正式法律意见
    </footer>
  </div>
</template>
