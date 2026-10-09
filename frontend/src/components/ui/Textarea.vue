<script setup lang="ts">
import { cn } from '../../lib/utils'

const props = defineProps<{
  modelValue?: string
  placeholder?: string
  disabled?: boolean
  rows?: number
  class?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
}
</script>

<template>
  <textarea
    :value="modelValue"
    :placeholder="placeholder"
    :disabled="disabled"
    :rows="rows ?? 3"
    :class="cn(
      'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors placeholder:text-muted-foreground/60 hover:border-primary/40 focus-visible:outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50 resize-none',
      props.class
    )"
    v-bind="$attrs"
    @input="onInput"
  />
</template>
