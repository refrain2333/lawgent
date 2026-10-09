<script setup lang="ts">
import { cn } from '../../lib/utils'

const props = withDefaults(defineProps<{
  variant?: 'default' | 'secondary' | 'outline' | 'destructive'
  class?: string
}>(), { variant: 'default' })

const variants: Record<string, string> = {
  default: 'bg-primary/10 text-primary border border-primary/20',
  secondary: 'bg-secondary text-secondary-foreground border border-border/60',
  outline: 'border border-input text-foreground bg-background',
  destructive: 'bg-destructive/10 text-destructive border border-destructive/20',
}
</script>

<template>
  <span :class="cn('inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors', variants[variant], props.class)">
    <slot />
  </span>
</template>
