<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import ArticleCard from '@/components/legal/ArticleCard.vue'
import CaseCard from '@/components/legal/CaseCard.vue'
import NavBar from '@/components/ui/NavBar.vue'
import Pagination from '@/components/ui/Pagination.vue'

const route = useRoute()

// --- Tab ---
const activeTab = ref<'articles' | 'cases'>(
  route.query.tab === 'cases' ? 'cases' : 'articles'
)

// --- Articles ---
const articleQuery = ref('')
const articleChapter = ref('')
const articlePage = ref(1)
const articlePageSize = 20
const articleTotal = ref(0)
const articleItems = ref<any[]>([])
const articleLoading = ref(false)

async function fetchArticles() {
  articleLoading.value = true
  try {
    const params = new URLSearchParams({
      q: articleQuery.value,
      chapter: articleChapter.value,
      page: String(articlePage.value),
      page_size: String(articlePageSize),
    })
    const res = await fetch(`/api/v1/data/articles?${params}`)
    const data = await res.json()
    articleItems.value = data.items || []
    articleTotal.value = data.total || 0
  } catch (e) {
    articleItems.value = []
  } finally {
    articleLoading.value = false
  }
}

const articleTotalPages = computed(() => Math.ceil(articleTotal.value / articlePageSize) || 1)

function articleSearch() {
  articlePage.value = 1
  fetchArticles()
}

// --- Cases ---
const caseQuery = ref('')
const casePage = ref(1)
const casePageSize = 20
const caseTotal = ref(0)
const caseItems = ref<any[]>([])
const caseLoading = ref(false)

async function fetchCases() {
  caseLoading.value = true
  try {
    const params = new URLSearchParams({
      q: caseQuery.value,
      page: String(casePage.value),
      page_size: String(casePageSize),
    })
    const res = await fetch(`/api/v1/data/cases?${params}`)
    const data = await res.json()
    caseItems.value = data.items || []
    caseTotal.value = data.total || 0
  } catch (e) {
    caseItems.value = []
  } finally {
    caseLoading.value = false
  }
}

const caseTotalPages = computed(() => Math.ceil(caseTotal.value / casePageSize) || 1)

function caseSearch() {
  casePage.value = 1
  fetchCases()
}

// --- Graph article IDs ---
const graphArticleIds = ref<Set<number>>(new Set())

async function fetchGraphArticleIds() {
  try {
    const res = await fetch('/api/v1/graph/article_ids')
    const data = await res.json()
    graphArticleIds.value = new Set(data.ids || [])
  } catch (e) {}
}

// --- Init ---
onMounted(() => {
  fetchArticles()
  fetchCases()
  fetchGraphArticleIds()
})

watch(activeTab, (tab) => {
  if (tab === 'articles' && articleItems.value.length === 0) fetchArticles()
  if (tab === 'cases' && caseItems.value.length === 0) fetchCases()
})
</script>

<template>
  <div class="min-h-screen bg-background">
    <NavBar />
    <div class="max-w-6xl mx-auto px-4 py-8">

      <!-- Header -->
      <div class="mb-6">
        <h1 class="text-2xl font-bold text-foreground">数据浏览</h1>
        <p class="text-sm text-muted-foreground mt-1">浏览刑法法条与典型案例数据</p>
      </div>

      <!-- Tabs -->
      <div class="flex gap-1 mb-6 border-b border-border">
        <button
          v-for="tab in [{ key: 'articles', label: '法条' }, { key: 'cases', label: '案例' }]"
          :key="tab.key"
          @click="activeTab = tab.key as any"
          class="px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px"
          :class="activeTab === tab.key
            ? 'border-primary text-foreground'
            : 'border-transparent text-muted-foreground hover:text-foreground'"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Articles Tab -->
      <div v-if="activeTab === 'articles'">
        <div class="flex gap-2 mb-4">
          <input v-model="articleQuery" @keyup.enter="articleSearch" placeholder="搜索法条内容..."
            class="flex-1 h-9 px-3 text-sm rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
          <input v-model="articleChapter" @keyup.enter="articleSearch" placeholder="章节筛选"
            class="w-36 h-9 px-3 text-sm rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
          <button @click="articleSearch"
            class="h-9 px-4 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">搜索</button>
        </div>

        <div v-if="articleLoading" class="text-center py-12 text-muted-foreground text-sm">加载中...</div>

        <div v-else>
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <ArticleCard
              v-for="item in articleItems"
              :key="item.article_number"
              :article-number="item.article_number"
              :title="item.title"
              :chapter="item.chapter"
              :content="item.content"
              :show-graph-btn="graphArticleIds.has(item.article_number)"
            />
            <div v-if="articleItems.length === 0" class="col-span-2 text-center py-10 text-muted-foreground text-sm">暂无数据</div>
          </div>

          <Pagination :page="articlePage" :total-pages="articleTotalPages" :total="articleTotal"
            @change="p => { articlePage = p; fetchArticles() }" />
        </div>
      </div>

      <!-- Cases Tab -->
      <div v-if="activeTab === 'cases'">
        <div class="flex gap-2 mb-4">
          <input v-model="caseQuery" @keyup.enter="caseSearch" placeholder="搜索罪名或案件事实..."
            class="flex-1 h-9 px-3 text-sm rounded-md border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring" />
          <button @click="caseSearch"
            class="h-9 px-4 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">搜索</button>
        </div>

        <div v-if="caseLoading" class="text-center py-12 text-muted-foreground text-sm">加载中...</div>

        <div v-else>
          <div class="space-y-3">
            <CaseCard
              v-for="item in caseItems"
              :key="item.case_id"
              :case-id="item.case_id"
              :accusations="item.accusations"
              :fact="item.fact"
              :relevant-articles="item.relevant_articles"
              :criminals="item.criminals"
              :imprisonment-months="item.imprisonment_months"
              :fine-amount="item.fine_amount"
              :death-penalty="item.death_penalty"
              :life-imprisonment="item.life_imprisonment"
            />
            <div v-if="caseItems.length === 0" class="text-center py-10 text-muted-foreground text-sm">暂无数据</div>
          </div>

          <Pagination :page="casePage" :total-pages="caseTotalPages" :total="caseTotal"
            @change="p => { casePage = p; fetchCases() }" />
        </div>
      </div>

    </div>
  </div>
</template>
