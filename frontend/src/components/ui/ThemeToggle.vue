<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { cn } from '../../lib/utils'

const props = defineProps<{ class?: string }>()

const isDark = ref(false)

onMounted(() => {
  isDark.value = document.documentElement.classList.contains('dark')
})

function toggle() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
}
</script>

<template>
  <button
    :class="cn(
      'inline-flex items-center justify-center h-9 w-9 rounded-md border border-input bg-background',
      'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
      'transition-all duration-200 active:scale-[0.96] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer',
      props.class
    )"
    :aria-label="isDark ? '切换亮色模式' : '切换暗色模式'"
    @click="toggle"
  >
    <!-- 太阳 -->
    <svg v-if="isDark" xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
    </svg>
    <!-- 月亮 -->
    <svg v-else xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
    </svg>
  </button>
</template>
