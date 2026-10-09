<script setup lang="ts">
import { cn } from '../../lib/utils'
const props = defineProps<{ class?: string }>()
</script>

<template>
  <div :class="cn('rounded-xl border border-border/60 bg-card text-card-foreground shadow-sm shadow-foreground/5 transition-shadow duration-200', props.class)">
    <slot />
  </div>
</template>
