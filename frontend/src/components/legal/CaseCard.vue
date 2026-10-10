<script setup lang="ts">
import { computed, ref } from 'vue'
import Badge from '@/components/ui/Badge.vue'

const props = defineProps<{
  caseId?: string
  accusations?: string[]
  fact?: string
  relevantArticles?: string[]
  criminals?: string[]
  imprisonmentMonths?: number | null
  fineAmount?: number | null
  deathPenalty?: boolean
  lifeImprisonment?: boolean
  similarity?: number
}>()

const expanded = ref(false)
const PREVIEW_LEN = 150

const preview = (s: string) => s.length > PREVIEW_LEN ? s.slice(0, PREVIEW_LEN) + '...' : s

function sentenceText(): string {
  if (props.deathPenalty) return '死刑'
  if (props.lifeImprisonment) return '无期徒刑'
  if (props.imprisonmentMonths != null) {
    const m = props.imprisonmentMonths
    return m >= 12
      ? `${Math.floor(m / 12)} 年${m % 12 ? m % 12 + ' 月' : ''}`
      : `${m} 个月`
  }
  return ''
}

const isSevere = computed(() => props.deathPenalty || props.lifeImprisonment)
</script>

<template>
  <div class="rounded-2xl border border-border bg-card shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden border-l-4 border-l-blue-500">
    <!-- Header -->
    <div class="flex items-start justify-between gap-3 px-4 pt-4 pb-3 bg-muted/30 border-b border-border/50">
      <div class="flex flex-wrap gap-1.5">
        <span
          v-for="acc in accusations" :key="acc"
          class="text-xs px-2.5 py-0.5 rounded-full font-medium border"
          :class="deathPenalty || lifeImprisonment
            ? 'bg-destructive/10 text-destructive border-destructive/20'
            : 'bg-primary/10 text-primary border-primary/20'"
        >{{ acc }}</span>
        <span v-if="!accusations?.length" class="text-xs text-muted-foreground">无罪名</span>
      </div>
      <span v-if="caseId" class="text-[10px] text-muted-foreground/50 font-mono tracking-tighter shrink-0 mt-0.5">{{ caseId }}</span>
      <span v-if="similarity !== undefined" class="text-xs font-mono text-muted-foreground shrink-0 mt-0.5">{{ (similarity * 100).toFixed(1) }}%</span>
    </div>

    <!-- Fact -->
    <div class="px-4 py-3">
      <div v-if="fact" class="text-sm text-foreground leading-relaxed">
        <span>{{ expanded ? fact : preview(fact) }}</span>
        <button
          v-if="fact.length > PREVIEW_LEN"
          @click="expanded = !expanded"
          class="ml-1.5 text-xs text-primary hover:text-primary/80 font-medium transition-colors"
        >{{ expanded ? '收起' : '展开全文' }}</button>
      </div>
    </div>

    <!-- Footer -->
    <div class="px-4 pb-3 flex flex-wrap items-center gap-2 pt-2 border-t border-border/40">
      <Badge v-if="sentenceText()" :variant="isSevere ? 'destructive' : 'default'">量刑：{{ sentenceText() }}</Badge>
      <Badge v-if="fineAmount != null" variant="outline">罚金：{{ fineAmount.toLocaleString() }} 元</Badge>
      <Badge v-for="a in relevantArticles" :key="a" variant="secondary">法条：第{{ a }}条</Badge>
      <Badge v-for="c in criminals" :key="c" variant="outline">涉案：{{ c }}</Badge>
    </div>
  </div>
</template>
