<script setup lang="ts">
import { apiUrl } from '@/lib/api'
import { ref, onMounted, onUnmounted, watch } from 'vue'
import NavBar from '@/components/ui/NavBar.vue'
import Badge from '@/components/ui/Badge.vue'
import MarkdownViewer from '@/components/ui/MarkdownViewer.vue'
import ArticleCard from '@/components/legal/ArticleCard.vue'
import CaseCard from '@/components/legal/CaseCard.vue'

const query = ref('')
const loading = ref(false)
const result = ref<any>(null)
const activeTab = ref<'vector' | 'bm25' | 'kg'>('vector')
const elapsed = ref<number | null>(null)
const graphArticleIds = ref<Set<number>>(new Set())
let searchRequest = 0

watch(activeTab, () => {
  searchRequest++
  result.value = null
  elapsed.value = null
  loading.value = false
})
onUnmounted(() => { searchRequest++ })

async function fetchGraphArticleIds() {
  try {
    const res = await fetch(apiUrl('/graph/article_ids'))
    const data = await res.json()
    graphArticleIds.value = new Set(data.ids || [])
  } catch (e) {}
}

onMounted(() => { fetchGraphArticleIds() })

async function doSearch() {
  if (!query.value.trim()) return
  loading.value = true
  result.value = null
  elapsed.value = null
  const requestId = ++searchRequest
  try {
    const t0 = performance.now()
    const res = await fetch(apiUrl(`/search/${activeTab.value}?q=${encodeURIComponent(query.value)}`))
    const data = await res.json()
    if (requestId !== searchRequest) return
    result.value = res.ok ? data : { error: typeof data.detail === 'string' ? data.detail : `请求失败（${res.status}）` }
    elapsed.value = Math.round(performance.now() - t0)
  } catch (e) {
    if (requestId === searchRequest) result.value = { error: '请求失败' }
  } finally {
    if (requestId === searchRequest) loading.value = false
  }
}

const examples = ['故意伤害', '盗窃罪', '诈骗', '交通肇事', '职务侵占']

const methodInfo = {
  vector: {
    name: '向量语义检索 (Dense Retrieval)',
    color: 'text-blue-600 dark:text-blue-400',
    bg: 'bg-blue-500/5 border-blue-500/20',
    pipeline: ['查询文本', 'Lawformer 编码', '768维稠密向量', '余弦相似度', 'Top-K 排序'],
    principle: `Lawformer 基于 RoBERTa 在海量法律文书上预训练，将文本映射为 768 维稠密向量，计算查询与文档的余弦相似度：\n\n$$\\text{sim}(q, d) = \\frac{q \\cdot d}{\\|q\\| \\cdot \\|d\\|}$$\n\n值域 $[-1, 1]$，越接近 1 语义越相近。`,
    detail: `预存向量库启动时从 pkl 加载到内存，检索时用 sklearn cosine_similarity 批量计算，复杂度 $O(n \\cdot d)$，$n$ 为文档数，$d=768$。`,
    pros: '能理解语义，"被人用刀划伤" 可匹配 "故意伤害罪"，不依赖关键词精确匹配',
    cons: '依赖模型质量，计算开销较大，对专有名词可能理解偏差',
    example: '朋友被人用刀划伤了手臂',
  },
  bm25: {
    name: 'BM25 稀疏关键词检索 (Sparse Retrieval)',
    color: 'text-emerald-600 dark:text-emerald-400',
    bg: 'bg-emerald-500/5 border-emerald-500/20',
    pipeline: ['查询文本', 'jieba 分词', '2/3-gram 扩充', 'BM25 评分', '归一化排序'],
    principle: `$$\\text{BM25}(q,d) = \\sum_{i} \\text{IDF}(t_i) \\cdot \\frac{tf(t_i,d) \\cdot (k_1+1)}{tf(t_i,d) + k_1 \\cdot \\left(1 - b + b \\cdot \\frac{|d|}{avgdl}\\right)}$$\n\n$$\\text{IDF}(t) = \\log\\left(\\frac{N - df + 0.5}{df + 0.5} + 1\\right)$$\n\n其中 $k_1=1.5$，$b=0.75$，$N$ 为文档总数，$df$ 为含词 $t$ 的文档数。`,
    detail: '罪名/法条标题开启字符级 n-gram（"故意伤害"→"故意","伤害","故意伤","意伤害","故意伤害"），案件事实仅用 jieba 分词避免 token 爆炸。索引构建后缓存到 bm25_index.pkl，重启直接加载。',
    pros: '精确词汇命中率高，速度快，可解释性强，对法条编号、罪名等专有名词效果好',
    cons: '无法理解语义，"刀伤" 无法匹配 "故意伤害"，同义词需手动扩展',
    example: '故意伤害 轻伤 第234条',
  },
  kg: {
    name: '知识图谱检索 (Graph-based Retrieval)',
    color: 'text-violet-600 dark:text-violet-400',
    bg: 'bg-violet-500/5 border-violet-500/20',
    pipeline: ['查询文本', 'AC 自动机匹配罪名', '图谱频次聚合', '归一化评分', 'Top-K 法条'],
    principle: `从 17,131 份判决书统计罪名-法条共现频次构建二部图，用 Aho-Corasick 自动机（$O(|query|)$）识别罪名后归一化：\n\n$$\\text{score}(art) = \\frac{\\text{freq}(crime \\to art)}{\\max_{art'} \\text{freq}(crime \\to art')}$$\n\n最高频法条得分为 1.0。`,
    detail: 'AC 自动机同时索引原始罪名和去"罪"后缀形式（"盗窃罪"+"盗窃"），未命中时降级为子串模糊匹配（q in crime），保证短词也能召回。',
    pros: '基于真实司法数据，结果反映司法实践规律，速度极快（纯内存查表）',
    cons: '仅返回法条（无案例），依赖罪名识别，描述性自然语言输入效果差',
    example: '盗窃罪 / 故意伤害',
  },
}

const infoExpanded = ref(false)
</script>

<template>
  <div class="min-h-screen bg-background">
    <!-- Nav -->
    <NavBar />

    <main class="max-w-6xl mx-auto px-4 py-10 space-y-6">

      <!-- Header -->
      <div class="space-y-1">
        <h1 class="text-xl font-bold">多路检索演示</h1>
        <p class="text-sm text-muted-foreground">支持向量语义检索、BM25 关键词检索、知识图谱检索，实时展示各路结果</p>
      </div>

      <!-- Search Box -->
      <div class="bg-card border border-border/60 rounded-xl p-5 shadow-sm space-y-4">
        <!-- Mode Tabs -->
        <div class="flex gap-1 bg-muted p-1 rounded-lg w-fit">
          <button v-for="tab in [
            { key: 'vector', label: '向量检索' },
            { key: 'bm25',   label: 'BM25' },
            { key: 'kg',     label: '知识图谱' },
          ]" :key="tab.key"
            class="px-3 py-1.5 text-xs font-medium rounded-md transition-all"
            :class="activeTab === tab.key ? 'bg-card shadow-sm text-foreground' : 'text-muted-foreground hover:text-foreground'"
            @click="activeTab = tab.key as any">
            {{ tab.label }}
          </button>
        </div>

        <!-- Method Info Panel -->
        <div class="rounded-lg border transition-all duration-200" :class="methodInfo[activeTab].bg">
          <!-- 折叠头部 -->
          <button class="w-full flex items-center justify-between px-4 py-2.5 text-left" @click="infoExpanded = !infoExpanded">
            <div class="flex items-center gap-3">
              <span class="text-xs font-semibold" :class="methodInfo[activeTab].color">{{ methodInfo[activeTab].name }}</span>
              <div class="flex items-center gap-1">
                <template v-for="(step, i) in methodInfo[activeTab].pipeline" :key="step">
                  <span class="text-[10px] px-1.5 py-0.5 rounded bg-background/70 border border-border/40 font-mono text-muted-foreground">{{ step }}</span>
                  <span v-if="i < methodInfo[activeTab].pipeline.length - 1" class="text-[10px] text-muted-foreground">→</span>
                </template>
              </div>
            </div>
            <Badge variant="outline" class="shrink-0 ml-2 cursor-pointer hover:border-primary/50 hover:text-primary transition-colors">{{ infoExpanded ? '收起 ↑' : '算法详情 ↓' }}</Badge>
          </button>

          <!-- 展开内容 -->
          <div v-if="infoExpanded" class="px-4 pb-4 space-y-3 border-t border-border/30 pt-3">
            <MarkdownViewer :content="methodInfo[activeTab].principle" />
            <p class="text-xs text-muted-foreground/70 leading-relaxed border-l-2 border-border pl-2">{{ methodInfo[activeTab].detail }}</p>
            <div class="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span class="text-emerald-600 dark:text-emerald-400 font-medium">优势：</span>
                <span class="text-muted-foreground">{{ methodInfo[activeTab].pros }}</span>
              </div>
              <div>
                <span class="text-destructive font-medium">局限：</span>
                <span class="text-muted-foreground">{{ methodInfo[activeTab].cons }}</span>
              </div>
            </div>
            <div class="text-xs text-muted-foreground">
              推荐输入：<span class="font-mono text-foreground cursor-pointer hover:text-primary transition-colors"
                @click="query = methodInfo[activeTab].example.split(' / ')[0]; doSearch()">{{ methodInfo[activeTab].example }}</span>
            </div>
          </div>
        </div>

        <!-- Input -->
        <div class="flex gap-2">
          <input v-model="query" @keydown.enter="doSearch"
            placeholder="输入罪名或案情描述，如：故意伤害、盗窃..."
            class="flex-1 bg-background border border-border/60 rounded-lg px-4 py-2.5 text-sm outline-none focus:border-primary/60 transition-colors" />
          <button @click="doSearch" :disabled="loading || !query.trim()"
            class="bg-primary text-primary-foreground px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shrink-0">
            {{ loading ? '检索中...' : '检索' }}
          </button>
        </div>

        <!-- Examples -->
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs text-muted-foreground">示例：</span>
          <button v-for="ex in examples" :key="ex"
            @click="query = ex; doSearch()"
            class="text-xs px-2.5 py-1 rounded-full border border-border/60 hover:border-primary/40 hover:text-primary transition-colors">
            {{ ex }}
          </button>
        </div>
      </div>

      <!-- Results -->
      <div v-if="loading" class="text-center py-16 text-muted-foreground text-sm">检索中...</div>

      <div v-else-if="result && !result.error" class="space-y-6">
        <!-- Meta -->
        <div class="flex items-center gap-4 text-xs text-muted-foreground">
          <span>法条 <strong class="text-foreground">{{ result.total_articles }}</strong> 条</span>
          <span>案例 <strong class="text-foreground">{{ result.total_cases }}</strong> 条</span>
          <span v-if="elapsed">耗时 <strong class="text-foreground">{{ elapsed }}ms</strong></span>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <!-- Articles -->
          <div v-if="result.articles?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">相关法条</h3>
            <div class="space-y-3">
              <ArticleCard
                v-for="art in result.articles" :key="art.id"
                :article-number="art.article_number"
                :title="art.title"
                :chapter="art.chapter"
                :content="art.content"
                :show-graph-btn="graphArticleIds.has(art.article_number)"
                :similarity="art.similarity"
              />
            </div>
          </div>

          <!-- Cases -->
          <div v-if="result.cases?.length">
            <h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">相关案例</h3>
            <div class="space-y-3">
              <CaseCard
                v-for="c in result.cases" :key="c.id"
                :case-id="c.case_id"
                :accusations="c.accusations"
                :fact="c.fact"
                :relevant-articles="c.relevant_articles?.map((a: number) => String(a))"
                :criminals="c.criminals"
                :imprisonment-months="c.sentence_months"
                :fine-amount="c.fine_amount"
                :death-penalty="c.death_penalty"
                :life-imprisonment="c.life_imprisonment"
                :similarity="c.similarity"
              />
            </div>
          </div>
        </div>

        <!-- No results -->
        <div v-if="!result.articles?.length && !result.cases?.length"
          class="text-center py-12 text-muted-foreground text-sm">未找到相关结果</div>
      </div>

      <div v-else-if="result?.error" class="text-center py-12 text-destructive text-sm">{{ result.error }}</div>

    </main>
  </div>
</template>
