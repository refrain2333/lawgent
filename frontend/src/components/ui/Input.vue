<script setup lang="ts">
import { ref } from 'vue'
import { cn } from '../../lib/utils'

const props = defineProps<{
  modelValue?: string
  placeholder?: string
  type?: string
  disabled?: boolean
  class?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const inputEl = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

defineExpose({ focus: () => inputEl.value?.focus() })
</script>

<template>
  <component
    :is="type === 'textarea' ? 'textarea' : 'input'"
    ref="inputEl"
    :value="modelValue"
    :type="type !== 'textarea' ? (type ?? 'text') : undefined"
    :placeholder="placeholder"
    :disabled="disabled"
    :class="cn(
      'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm transition-colors placeholder:text-muted-foreground/60 hover:border-primary/40 focus-visible:outline-none focus-visible:border-primary focus-visible:ring-2 focus-visible:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-50',
      type === 'textarea' ? 'min-h-[40px] resize-none overflow-y-auto' : 'h-10',
      props.class
    )"
    v-bind="$attrs"
    @input="onInput"
  />
</template>
