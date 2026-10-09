<script setup lang="ts">
const props = defineProps<{
  page: number
  totalPages: number
  total: number
}>()

const emit = defineEmits<{
  (e: 'change', page: number): void
}>()

function jump(e: Event) {
  const val = Math.min(Math.max(1, Number((e.target as HTMLInputElement).value)), props.totalPages)
  emit('change', val)
}
</script>

<template>
  <div class="flex items-center justify-between mt-4 text-sm text-muted-foreground">
    <span>共 {{ total }} 条</span>
    <div class="flex items-center gap-1">
      <button @click="emit('change', page - 1)" :disabled="page <= 1"
        class="h-8 px-3 rounded-md border border-border hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-xs">上一页</button>
      <div class="flex items-center gap-1 px-2 text-xs">
        <input
          type="number" min="1" :max="totalPages" :value="page"
          class="w-10 h-8 px-1 text-xs text-center rounded-md border border-input bg-background focus:outline-none focus:ring-1 focus:ring-ring"
          @keyup.enter="jump"
        />
        <span class="text-muted-foreground/60">/ {{ totalPages }}</span>
      </div>
      <button @click="emit('change', page + 1)" :disabled="page >= totalPages"
        class="h-8 px-3 rounded-md border border-border hover:bg-muted transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-xs">下一页</button>
    </div>
  </div>
</template>
