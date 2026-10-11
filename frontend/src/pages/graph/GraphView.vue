<script setup lang="ts">
import { apiUrl } from '@/lib/api'
import { ref, onMounted, onUnmounted, shallowRef } from 'vue'
import { useRoute } from 'vue-router'
import * as echarts from 'echarts'
import NavBar from '@/components/ui/NavBar.vue'
import CaseCard from '@/components/legal/CaseCard.vue'
import { Search, RefreshCw, Network as NetworkIcon, Maximize2 } from 'lucide-vue-next'

interface GraphNode { id: string; label: string; type: string; weight: number; confidence: number }
interface GraphEdge { source: string; target: string; weight: number; label: string }
interface RelationsData {
  center_node: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
  entity_type: string
}
interface Stats { total_crimes: number; total_articles: number; total_relations: number }
interface CaseItem {
  case_id: string
  accusations: string[]
  fact: string
  relevant_articles: string[]
  criminals: string[]
  imprisonment_months: number | null
  fine_amount: number | null
  death_penalty: boolean
  life_imprisonment: boolean
}

const container = ref<HTMLElement | null>(null)
const query = ref('')
const loading = ref(false)
const stats = ref<Stats | null>(null)
const selectedNode = ref<GraphNode | null>(null)
const currentData = ref<RelationsData | null>(null)
const chart = shallowRef<echarts.ECharts | null>(null)
const hasSearched = ref(false)
const errorMsg = ref('')
const topCrimes = ref(15)
const isGlobalMode = ref(true)
let graphRequest = 0
let articleRequest = 0
let casesRequest = 0
let globalData: { nodes: GraphNode[]; edges: GraphEdge[] } | null = null

function escapeHtml(value: unknown) {
  const escapes: Record<string, string> = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }
  return String(value).replace(/[&<>"']/g, char => escapes[char] ?? char)
}

// 选中法条详情
const selectedArticle = ref<{ title: string; chapter: string; content: string } | null>(null)

async function fetchArticleDetail(articleNum: string) {
  const requestId = ++articleRequest
  selectedArticle.value = null
  try {
    const res = await fetch(apiUrl(`/data/articles?article_number=${encodeURIComponent(articleNum)}&page=1&page_size=1`))
    const data = await res.json()
    if (requestId === articleRequest && res.ok && data.items?.length) selectedArticle.value = data.items[0]
  } catch (e) {}
}

// 案例弹窗
const caseModal = ref(false)
const caseModalTitle = ref('')
const caseModalLoading = ref(false)
const caseModalError = ref('')
const caseList = ref<CaseItem[]>([])

const EXAMPLES = ['盗窃', '故意伤害', '诈骗', '抢劫', '危险驾驶', '第264条', '第234条']

async function loadRelationCases(crimeId: string, articleId: string) {
  const requestId = ++casesRequest
  const crime = crimeId.replace('crime_', '')
  const article = articleId.replace('article_', '')
  caseModalTitle.value = `${crime.endsWith('罪') ? crime : crime + '罪'} · 第${article}条 · 关联案例`
  caseModal.value = true
  caseModalLoading.value = true
  caseModalError.value = ''
  caseList.value = []
  try {
    const res = await fetch(apiUrl(`/graph/relation_cases/${encodeURIComponent(crime)}/${article}?limit=5`))
    const data = await res.json()
    if (requestId !== casesRequest) return
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '关联案例加载失败')
    caseList.value = data.cases
  } catch (e) {
    if (requestId === casesRequest) caseModalError.value = e instanceof Error ? e.message : '关联案例加载失败'
  }
  finally { if (requestId === casesRequest) caseModalLoading.value = false }
}

async function loadGlobalGraph() {
  const requestId = ++graphRequest
  articleRequest++
  loading.value = true
  errorMsg.value = ''
  isGlobalMode.value = true
  hasSearched.value = true
  selectedNode.value = null
  selectedArticle.value = null
  try {
    const res = await fetch(apiUrl(`/graph?top_crimes=${topCrimes.value}`))
    const data = await res.json()
    if (requestId !== graphRequest) return
    if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '图谱加载失败')
    // 转换为 RelationsData 格式复用 renderGraph
    const fakeCenter: GraphNode = { id: 'global', label: `Top ${topCrimes.value} 罪名`, type: 'center', weight: 0, confidence: 1 }
    const relData: RelationsData = {
      center_node: fakeCenter,
      nodes: [fakeCenter, ...data.nodes],
      edges: data.edges,
      entity_type: 'global',
    }
    currentData.value = relData
    globalData = data
    renderGlobalGraph(data)
  } catch (e) {
    if (requestId === graphRequest) {
      errorMsg.value = e instanceof Error ? e.message : '图谱加载失败'
      clearChart()
    }
  } finally {
    if (requestId === graphRequest) loading.value = false
  }
}

function renderGlobalGraph(data: { nodes: GraphNode[]; edges: GraphEdge[] }) {
  if (!container.value) return
  if (!chart.value) {
    chart.value = echarts.init(container.value, undefined, { renderer: 'canvas' })
  }
  chart.value.off('click')
  chart.value.on('click', (params: any) => {
    if (params.dataType === 'node') {
      const found = data.nodes.find((n: GraphNode) => n.id === params.data.id)
      if (found) {
        const term = found.type === 'crime'
          ? found.label
          : found.label  // 法条标签已是"第264条"格式
        query.value = term
        isGlobalMode.value = false
        search(term)
      }
    }
    if (params.dataType === 'edge') {
      const src: string = typeof params.data.source === 'object' ? params.data.source.id : params.data.source
      const tgt: string = typeof params.data.target === 'object' ? params.data.target.id : params.data.target
      const crimeId = src.startsWith('crime_') ? src : tgt
      const articleId = src.startsWith('article_') ? src : tgt
      if (crimeId.startsWith('crime_') && articleId.startsWith('article_')) {
        loadRelationCases(crimeId, articleId)
      }
    }
  })

  const maxWeight = Math.max(...data.nodes.map((n: GraphNode) => n.weight), 1)
  const CRIME_COLOR = '#F79767'
  const ARTICLE_COLOR = '#57C7E3'

  const nodes = data.nodes.map((n: GraphNode) => {
    const isCrime = n.type === 'crime'
    const size = isCrime ? 14 + (n.weight / maxWeight) * 28 : 8 + (n.weight / maxWeight) * 14
    return {
      id: n.id,
      name: n.label,
      category: isCrime ? 0 : 1,
      symbolSize: size,
      value: n.weight,
      label: {
        show: isCrime,
        // echarts 6 的 label.position 类型定义未包含 'outside'，运行时有效，此处断言绕过
        position: 'outside' as never,
        fontSize: 10,
        color: '#e2e8f0',
        textBorderColor: '#1b1f2e',
        textBorderWidth: 2,
      },
      itemStyle: {
        color: isCrime ? CRIME_COLOR : ARTICLE_COLOR,
        borderColor: isCrime ? '#c9623a' : '#22a3c4',
        borderWidth: 1.5,
        shadowBlur: 4,
        shadowColor: isCrime ? 'rgba(247,151,103,0.3)' : 'rgba(87,199,227,0.2)',
      },
    }
  })

  const edges = data.edges.map((e: GraphEdge) => ({
    source: e.source,
    target: e.target,
    value: e.weight,
    lineStyle: { width: Math.max(0.5, Math.min(2, e.weight / 50)), opacity: 0.35, color: '#6b7a99' },
  }))

  const option: echarts.EChartsOption = {
    backgroundColor: '#1b1f2e',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(26,31,46,0.96)',
      borderColor: '#2d3748',
      borderWidth: 1,
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const color = params.data.category === 0 ? '#F79767' : '#57C7E3'
          const type = params.data.category === 0 ? '罪名' : '法条'
          return `<span style="color:${color};font-weight:bold">${escapeHtml(params.data.name)}</span><br/><span style="color:#94a3b8">${type} · 案例数：${params.data.value}</span>`
        }
        if (params.dataType === 'edge') return `<span style="color:#94a3b8">共现案例：${params.data.value}</span>`
        return ''
      },
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: edges,
      categories: [
        { name: '罪名', itemStyle: { color: CRIME_COLOR } },
        { name: '法条', itemStyle: { color: ARTICLE_COLOR } },
      ],
      roam: true,
      draggable: true,
      force: { repulsion: 200, gravity: 0.08, edgeLength: [60, 150], friction: 0.65, layoutAnimation: false },
      emphasis: { focus: 'adjacency', lineStyle: { width: 2, opacity: 0.8 } },
      blur: { itemStyle: { opacity: 0.1 }, lineStyle: { opacity: 0.05 }, label: { show: false } },
      lineStyle: { curveness: 0.05 },
      edgeSymbol: ['none', 'none'],
      scaleLimit: { min: 0.2, max: 5 },
    }],
  }
  chart.value.setOption(option, true)
}

async function loadStats() {
  try {
    const res = await fetch(apiUrl('/graph/stats'))
    if (res.ok) stats.value = await res.json()
  } catch (e) {}
}

async function search(q?: string) {
  const term = (q ?? query.value).trim()
  if (!term) return
  const requestId = ++graphRequest
  articleRequest++
  isGlobalMode.value = false
  query.value = term
  loading.value = true
  errorMsg.value = ''
  selectedNode.value = null
  selectedArticle.value = null
  hasSearched.value = true

  try {
    const res = await fetch(apiUrl(`/graph/relations/${encodeURIComponent(term)}?top_k=12`))
    if (!res.ok) {
      const err = await res.json()
      if (requestId !== graphRequest) return
      errorMsg.value = err.detail || '未找到相关数据'
      clearChart()
      return
    }
    const data: RelationsData = await res.json()
    if (requestId !== graphRequest) return
    currentData.value = data
    selectedNode.value = data.center_node
    if (data.center_node.id.startsWith('article_')) void fetchArticleDetail(data.center_node.id.replace('article_', ''))
    renderGraph(data)
  } catch (e) {
    if (requestId === graphRequest) {
      errorMsg.value = '请求失败，请检查后端服务'
      clearChart()
    }
  } finally {
    if (requestId === graphRequest) loading.value = false
  }
}

function clearChart() {
  if (chart.value) {
    chart.value.clear()
  }
  currentData.value = null
}

function renderGraph(data: RelationsData) {
  if (!container.value) return
  if (!chart.value) {
    chart.value = echarts.init(container.value, undefined, { renderer: 'canvas' })
  }

  // 每次重新绑定，避免旧闭包残留
  chart.value.off('click')
  chart.value.on('click', (params: any) => {
    if (params.dataType === 'node') {
      const d = currentData.value
      if (!d) return
      const found = d.nodes.find(n => n.id === params.data.id)
      if (found) {
        selectedNode.value = found
        selectedArticle.value = null
        if (found.type === 'article' || (found.type === 'center' && found.id.startsWith('article_'))) {
          const num = found.id.replace('article_', '')
          fetchArticleDetail(num)
        }
        if (found.type !== 'center') {
          const term = found.type === 'crime'
            ? found.label.replace('罪', '')
            : found.label.replace(/第|条/g, '')
          query.value = term
          search(term)
          return
        }
      }
    }
    if (params.dataType === 'edge') {
      const src: string = typeof params.data.source === 'object' ? params.data.source.id : params.data.source
      const tgt: string = typeof params.data.target === 'object' ? params.data.target.id : params.data.target
      const crimeId = src.startsWith('crime_') ? src : tgt
      const articleId = src.startsWith('article_') ? src : tgt
      if (crimeId.startsWith('crime_') && articleId.startsWith('article_')) {
        loadRelationCases(crimeId, articleId)
      }
    }
  })

  const CENTER_COLOR = '#F79767'   // 橙色 - 中心节点
  const CRIME_COLOR = '#4C8EDA'    // 蓝色 - 罪名
  const ARTICLE_COLOR = '#57C7E3' // 青色 - 法条

  const maxWeight = Math.max(...data.nodes.filter(n => n.type !== 'center').map(n => n.weight), 1)

  const cw = container.value.offsetWidth || 800
  const ch = container.value.offsetHeight || 520
  const cx = cw / 2
  const cy = ch / 2
  const total = data.nodes.filter(n => n.type !== 'center').length
  const radius = Math.min(cw, ch) * 0.35

  const nodes = data.nodes.map(n => {
    const isCenter = n.type === 'center'
    const isCrime = n.type === 'crime'
    const color = isCenter ? CENTER_COLOR : isCrime ? CRIME_COLOR : ARTICLE_COLOR
    const borderColor = isCenter ? '#c9623a' : isCrime ? '#2563ab' : '#22a3c4'
    const size = isCenter ? 48 : 14 + (n.weight / maxWeight) * 24

    const nonCenterIdx = data.nodes.filter(x => x.type !== 'center').indexOf(n)
    const angle = (nonCenterIdx / total) * 2 * Math.PI - Math.PI / 2
    const nx = isCenter ? cx : cx + Math.cos(angle) * radius
    const ny = isCenter ? cy : cy + Math.sin(angle) * radius

    return {
      id: n.id,
      name: n.label,
      category: isCenter ? 0 : isCrime ? 1 : 2,
      symbolSize: size,
      value: n.weight,
      x: nx,
      y: ny,
      label: {
        show: true,
        position: (isCenter ? 'inside' : 'outside') as never,
        fontSize: isCenter ? 13 : 10,
        fontWeight: isCenter ? 'bold' as const : 'normal' as const,
        color: isCenter ? '#ffffff' : '#e2e8f0',
        textBorderColor: '#1b1f2e',
        textBorderWidth: 2,
      },
      itemStyle: {
        color,
        borderColor,
        borderWidth: isCenter ? 3 : 2,
        shadowBlur: isCenter ? 16 : 6,
        shadowColor: isCenter ? 'rgba(247,151,103,0.6)' : isCrime ? 'rgba(76,142,218,0.4)' : 'rgba(87,199,227,0.3)',
      },
    }
  })

  const maxEdgeWeight = Math.max(...data.edges.map(e => e.weight), 1)
  const edges = data.edges.map(e => ({
    source: e.source,
    target: e.target,
    value: e.weight,
    lineStyle: {
      width: 1 + (e.weight / maxEdgeWeight) * 3,
      opacity: 0.6,
      color: '#6b7a99',
    },
  }))

  const option: echarts.EChartsOption = {
    backgroundColor: '#1b1f2e',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(26,31,46,0.96)',
      borderColor: '#2d3748',
      borderWidth: 1,
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          const node = data.nodes.find(n => n.id === params.data.id)
          if (!node) return ''
          const typeLabel = node.type === 'center' ? '查询焦点' : node.type === 'crime' ? '罪名' : '法条'
          const color = node.type === 'center' ? '#F79767' : node.type === 'crime' ? '#4C8EDA' : '#57C7E3'
          const conf = node.confidence > 0 && node.type !== 'center'
            ? `<br/><span style="color:#94a3b8">置信度：${(node.confidence * 100).toFixed(1)}%</span>` : ''
          return `<div style="line-height:1.8"><span style="color:${color};font-weight:bold">${escapeHtml(params.data.name)}</span><br/><span style="color:#94a3b8">${typeLabel} · 案例数：${node.weight}</span>${conf}</div>`
        }
        if (params.dataType === 'edge') {
          return `<span style="color:#94a3b8">共现案例：${params.data.value}</span>`
        }
        return ''
      },
    },
    series: [{
      type: 'graph',
      layout: 'none',
      data: nodes,
      links: edges,
      categories: [
        { name: '查询焦点', itemStyle: { color: CENTER_COLOR } },
        { name: '罪名', itemStyle: { color: CRIME_COLOR } },
        { name: '法条', itemStyle: { color: ARTICLE_COLOR } },
      ],
      roam: true,
      draggable: true,
      force: {
        repulsion: 260,
        gravity: 0.3,
        edgeLength: [80, 160],
        friction: 0.8,
        layoutAnimation: false,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 3, opacity: 0.9, color: '#a0aec0' },
        label: { show: true, fontSize: 11, color: '#ffffff' },
        itemStyle: { borderWidth: 3, shadowBlur: 16 },
      },
      blur: {
        itemStyle: { opacity: 0.1 },
        lineStyle: { opacity: 0.05 },
        label: { show: false },
      },
      lineStyle: { curveness: 0.1 },
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: 6,
      scaleLimit: { min: 0.3, max: 5 },
    }],
  }

  chart.value.setOption(option, true)
}

function resetView() {
  if (!chart.value || !currentData.value) return
  chart.value.dispatchAction({ type: 'restore' })
  if (isGlobalMode.value && globalData) renderGlobalGraph(globalData)
  else renderGraph(currentData.value)
  selectedNode.value = null
}

function handleResize() { chart.value?.resize() }

const route = useRoute()

onMounted(() => {
  loadStats()
  const q = route.query.q as string
  if (q) {
    query.value = q
    isGlobalMode.value = false
    search(q)
  } else {
    loadGlobalGraph()
  }
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  graphRequest++
  articleRequest++
  casesRequest++
  chart.value?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="min-h-screen bg-background text-foreground flex flex-col">
    <NavBar />

    <div class="max-w-7xl mx-auto w-full px-4 lg:px-6 pt-6 pb-4 flex-1 flex flex-col gap-4">

      <!-- 标题行 -->
      <div class="flex items-center justify-between flex-wrap gap-3">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-xl border border-primary/40 bg-primary/10 text-primary flex items-center justify-center">
            <NetworkIcon class="w-4 h-4" />
          </div>
          <div>
            <h1 class="text-lg font-semibold tracking-tight">知识图谱探索</h1>
            <p class="text-xs text-muted-foreground">搜索罪名或法条，探索关联关系网络</p>
          </div>
        </div>
        <div v-if="stats" class="flex items-center gap-4 text-xs text-muted-foreground">
          <span>罪名 <strong class="text-foreground tabular-nums">{{ stats.total_crimes }}</strong></span>
          <span>法条 <strong class="text-foreground tabular-nums">{{ stats.total_articles }}</strong></span>
          <span>关系 <strong class="text-foreground tabular-nums">{{ stats.total_relations }}</strong></span>
        </div>
      </div>

      <!-- 搜索栏 -->
      <div class="flex gap-2 flex-wrap items-center">
        <input
          v-model="query"
          @keydown.enter="search()"
          placeholder="输入罪名或法条，如：盗窃、第264条..."
          class="flex-1 min-w-48 bg-background border border-border/60 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary/60 transition-colors"
        />
        <button
          @click="search()"
          :disabled="loading"
          class="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1.5"
        >
          <RefreshCw v-if="loading" class="w-3.5 h-3.5 animate-spin" />
          <Search v-else class="w-3.5 h-3.5" />
          {{ loading ? '加载中' : '生成图谱' }}
        </button>
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <span>罪名数</span>
          <select
            v-model="topCrimes"
            @change="loadGlobalGraph()"
            class="bg-background border border-border/60 rounded-md px-2 py-1.5 text-xs outline-none focus:border-primary/60"
          >
            <option :value="10">10</option>
            <option :value="15">15</option>
            <option :value="20">20</option>
            <option :value="30">30</option>
            <option :value="50">50</option>
          </select>
        </div>
        <button
          @click="loadGlobalGraph()"
          :disabled="loading"
          class="border border-border/60 px-3 py-2 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:border-border transition-colors flex items-center gap-1.5"
        >
          <NetworkIcon class="w-3.5 h-3.5" />
          全局图
        </button>
        <button
          v-if="hasSearched"
          @click="resetView"
          class="border border-border/60 px-3 py-2 rounded-lg text-xs text-muted-foreground hover:text-foreground hover:border-border transition-colors flex items-center gap-1.5"
        >
          <Maximize2 class="w-3.5 h-3.5" />
          重置视图
        </button>
      </div>

      <!-- 示例按钮 -->
      <div class="flex gap-2 flex-wrap items-center">
        <span class="text-xs text-muted-foreground">示例：</span>
        <button
          v-for="ex in EXAMPLES"
          :key="ex"
          @click="search(ex)"
          class="text-xs px-2.5 py-1 rounded-md border border-border/60 text-muted-foreground hover:text-foreground hover:border-primary/40 hover:bg-primary/5 transition-colors"
        >
          {{ ex }}
        </button>
      </div>

      <!-- 主体 -->
      <div class="flex gap-4 flex-1 min-h-[640px]">

        <!-- 图谱区域 -->
        <div class="flex-1 rounded-2xl border border-border/60 overflow-hidden relative" style="background:#1b1f2e">

          <!-- 初始空状态 -->
          <div v-if="!hasSearched" class="absolute inset-0 flex flex-col items-center justify-center gap-3">
            <NetworkIcon class="w-12 h-12 opacity-20" style="color:#57C7E3" />
            <p class="text-sm opacity-40" style="color:#e2e8f0">搜索罪名或法条以生成关系图谱</p>
          </div>

          <!-- 错误状态 -->
          <div v-else-if="errorMsg && !loading" class="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <p class="text-sm opacity-60" style="color:#e2e8f0">{{ errorMsg }}</p>
            <p class="text-xs opacity-40" style="color:#94a3b8">请尝试其他罪名或法条</p>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="absolute inset-0 flex items-center justify-center z-10" style="background:rgba(27,31,46,0.8)">
            <div class="flex items-center gap-2 text-sm" style="color:#94a3b8">
              <RefreshCw class="w-4 h-4 animate-spin" />
              正在生成图谱...
            </div>
          </div>

          <div ref="container" class="w-full h-full min-h-[640px]" />
        </div>

        <!-- 侧边面板 -->
        <div class="w-48 shrink-0 flex flex-col gap-3">

          <!-- 图例 -->
          <div class="rounded-xl border border-border/60 bg-card p-4 space-y-2.5">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">图例</p>
            <div class="flex items-center gap-2 text-xs">
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#F79767"></span>
              <span class="text-muted-foreground">查询焦点</span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#4C8EDA"></span>
              <span class="text-muted-foreground">罪名节点</span>
            </div>
            <div class="flex items-center gap-2 text-xs">
              <span class="w-3 h-3 rounded-full shrink-0" style="background:#57C7E3"></span>
              <span class="text-muted-foreground">法条节点</span>
            </div>
            <div class="flex items-center gap-2 text-xs text-muted-foreground">
              <span class="w-6 h-px bg-border shrink-0"></span>
              连线粗细 = 案例数
            </div>
          </div>

          <!-- 操作提示 -->
          <div class="rounded-xl border border-border/60 bg-card p-4 space-y-2">
            <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">操作</p>
            <ul class="space-y-1.5 text-xs text-muted-foreground leading-relaxed">
              <li>点击节点 — 高亮关联</li>
              <li>滚轮 — 缩放</li>
              <li>拖拽背景 — 平移</li>
              <li>拖拽节点 — 调整布局</li>
            </ul>
          </div>

          <!-- 选中节点 -->
          <div v-if="selectedNode" class="rounded-xl border border-primary/30 bg-primary/5 p-4 space-y-1.5">
            <p class="text-xs font-semibold text-primary uppercase tracking-wider">选中节点</p>
            <p class="text-sm font-semibold text-foreground break-all">{{ selectedNode.label }}</p>
            <p class="text-xs text-muted-foreground">
              {{ selectedNode.type === 'center' ? '查询焦点' : selectedNode.type === 'crime' ? '罪名节点' : '法条节点' }}
            </p>
            <p class="text-xs text-muted-foreground">
              案例数：<strong class="text-foreground">{{ selectedNode.weight }}</strong>
            </p>
            <p v-if="selectedNode.confidence > 0 && selectedNode.type !== 'center'" class="text-xs text-muted-foreground">
              置信度：<strong class="text-foreground">{{ (selectedNode.confidence * 100).toFixed(1) }}%</strong>
            </p>
            <!-- 法条详情 -->
            <template v-if="selectedArticle">
              <div class="border-t border-primary/20 pt-2 mt-1 space-y-1">
                <p v-if="selectedArticle.chapter" class="text-xs px-2 py-0.5 rounded-md bg-primary/10 text-primary w-fit">{{ selectedArticle.chapter }}</p>
                <p class="text-xs text-foreground leading-relaxed">{{ selectedArticle.content }}</p>
              </div>
            </template>
          </div>
          <div v-else class="rounded-xl border border-border/60 bg-muted/20 p-4">
            <p class="text-xs text-muted-foreground text-center leading-relaxed">点击节点<br/>查看详情</p>
          </div>

        </div>
      </div>
    </div>

    <footer class="border-t border-border/60 py-4 text-center text-xs text-muted-foreground">
      内容由 AI 生成，仅供参考，不构成正式法律意见
    </footer>

    <!-- 案例弹窗 -->
    <Teleport to="body">
      <div v-if="caseModal" class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="caseModal = false">
        <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="caseModal = false" />
        <div class="relative bg-card border border-border/60 rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col shadow-2xl">
          <!-- 弹窗头部 -->
          <div class="flex items-center justify-between px-5 py-4 border-b border-border/60 shrink-0">
            <h3 class="text-sm font-semibold text-foreground">{{ caseModalTitle }}</h3>
            <button @click="caseModal = false" class="text-muted-foreground hover:text-foreground transition-colors text-lg leading-none">×</button>
          </div>
          <!-- 弹窗内容 -->
          <div class="overflow-y-auto flex-1 p-5 space-y-4">
            <div v-if="caseModalLoading" class="flex items-center justify-center py-8 gap-2 text-sm text-muted-foreground">
              <RefreshCw class="w-4 h-4 animate-spin" />
              加载案例中...
            </div>
            <div v-else-if="caseModalError" role="alert" class="text-center py-8 text-sm text-destructive">{{ caseModalError }}</div>
            <div v-else-if="caseList.length === 0" class="text-center py-8 text-sm text-muted-foreground">
              未找到相关案例
            </div>
            <div v-else class="space-y-3">
              <CaseCard
                v-for="(c, i) in caseList" :key="i"
                :case-id="c.case_id"
                :accusations="c.accusations"
                :fact="c.fact"
                :relevant-articles="c.relevant_articles"
                :criminals="c.criminals"
                :imprisonment-months="c.imprisonment_months"
                :fine-amount="c.fine_amount"
                :death-penalty="c.death_penalty"
                :life-imprisonment="c.life_imprisonment"
              />
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
