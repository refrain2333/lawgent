<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

defineProps<{
  articleNumber: number
  title?: string
  chapter?: string
  content?: string
  showGraphBtn?: boolean
  similarity?: number
}>()

const router = useRouter()
const expanded = ref(false)
const PREVIEW_LEN = 120

const preview = (s: string) => s.length > PREVIEW_LEN ? s.slice(0, PREVIEW_LEN) + '...' : s
</script>

<template>
  <div class="rounded-2xl border border-border bg-card shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden border-l-4 border-l-primary">
    <!-- Header -->
    <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3 bg-muted/30 border-b border-border/50">
      <div class="flex items-center gap-2 flex-wrap min-w-0">
        <span class="text-lg font-bold text-primary font-mono tracking-wide shrink-0">第{{ articleNumber }}条</span>
        <span
          v-if="chapter"
          class="text-xs px-2 py-0.5 rounded-md bg-primary/10 text-primary font-medium border border-primary/15 truncate max-w-[200px]"
          :title="chapter"
        >{{ chapter }}</span>
      </div>
      <button
        v-if="showGraphBtn"
        @click="router.push({ path: '/graph', query: { q: String(articleNumber) } })"
        class="shrink-0 text-xs px-2.5 py-1 rounded-lg border border-border text-muted-foreground hover:text-primary hover:border-primary/50 hover:bg-primary/5 transition-all"
      >图谱</button>
      <span v-if="similarity !== undefined"
        class="shrink-0 text-xs font-mono text-muted-foreground">{{ (similarity * 100).toFixed(1) }}%</span>
    </div>

    <!-- Body -->
    <div class="px-4 py-3">
      <p v-if="title" class="text-sm font-medium text-foreground mb-2">{{ title }}</p>
      <div v-if="content" class="text-sm text-muted-foreground leading-relaxed">
        <span>{{ expanded ? content : preview(content) }}</span>
        <button
          v-if="content.length > PREVIEW_LEN"
          @click="expanded = !expanded"
          class="ml-1.5 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
        >{{ expanded ? '收起' : '展开全文' }}</button>
      </div>
    </div>
  </div>
</template>
