<script setup lang="ts">
import { cn } from '../../lib/utils'

const props = withDefaults(defineProps<{
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive'
  size?: 'default' | 'sm' | 'lg' | 'icon'
  disabled?: boolean
  class?: string
}>(), {
  variant: 'default',
  size: 'default',
})

const base = 'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-40 select-none cursor-pointer'

const variants: Record<string, string> = {
  default: 'bg-primary text-primary-foreground shadow-sm shadow-primary/30 hover:bg-primary/90 hover:shadow-md hover:shadow-primary/25 active:scale-[0.98]',
  secondary: 'bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/70 active:scale-[0.98]',
  outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground hover:border-primary/40 active:scale-[0.98]',
  ghost: 'hover:bg-accent hover:text-accent-foreground active:scale-[0.98]',
  destructive: 'bg-destructive text-destructive-foreground shadow-sm shadow-destructive/25 hover:bg-destructive/90 hover:shadow-md active:scale-[0.98]',
}

const sizes: Record<string, string> = {
  default: 'h-10 px-4 py-2',
  sm: 'h-8 rounded-md px-3 text-xs',
  lg: 'h-11 rounded-md px-8 text-base',
  icon: 'h-10 w-10',
}
</script>

<template>
  <button
    :class="cn(base, variants[variant], sizes[size], props.class)"
    :disabled="disabled"
    v-bind="$attrs"
  >
    <slot />
  </button>
</template>
