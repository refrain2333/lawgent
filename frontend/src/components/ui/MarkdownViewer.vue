<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import katex from '@traptitech/markdown-it-katex'
import 'katex/dist/katex.min.css'

const props = withDefaults(defineProps<{
  content: string
}>(), {
  content: '',
})

const md = new MarkdownIt({
  html: true,
  linkify: true,
  breaks: true,
}).use(katex, {
  throwOnError: false,
  errorColor: '#cc0000'
})

const safeHtml = computed(() => {
  if (!props.content) return ''
  const rawHtml = md.render(props.content)
  return DOMPurify.sanitize(rawHtml, {
    ADD_ATTR: ['style'],
  })
})
</script>

<template>
  <div
    class="markdown-content max-w-none text-sm text-gray-700 dark:text-gray-300"
    v-html="safeHtml"
  />
</template>

<style scoped>
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4),
.markdown-content :deep(h5),
.markdown-content :deep(h6) {
  font-weight: 600;
  color: rgb(17 24 39);
  margin-top: 0;
  margin-bottom: 0.75rem;
}

.dark .markdown-content :deep(h1),
.dark .markdown-content :deep(h2),
.dark .markdown-content :deep(h3),
.dark .markdown-content :deep(h4),
.dark .markdown-content :deep(h5),
.dark .markdown-content :deep(h6) {
  color: rgb(229 231 235);
}

.markdown-content :deep(p) {
  margin-top: 0;
  margin-bottom: 0.75rem;
  line-height: 1.75rem;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-top: 0.5rem;
  margin-bottom: 0.75rem;
  padding-left: 1.25rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.35rem;
  line-height: 1.7rem;
}

.markdown-content :deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 0.75rem;
  padding: 0.125rem 0.375rem;
  border-radius: 0.375rem;
  background: rgb(243 244 246);
  color: rgb(31 41 55);
}

.dark .markdown-content :deep(code) {
  background: rgb(31 41 55);
  color: rgb(229 231 235);
}

.markdown-content :deep(pre) {
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
  padding: 0.875rem 1rem;
  border-radius: 0.75rem;
  border: 1px solid rgb(229 231 235);
  background: rgb(249 250 251);
  overflow-x: auto;
}

.dark .markdown-content :deep(pre) {
  border-color: rgb(55 65 81);
  background: rgba(0, 0, 0, 0.35);
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-content :deep(a) {
  color: rgb(8 145 178);
  text-decoration: underline;
}

.dark .markdown-content :deep(a) {
  color: rgb(103 232 249);
}

.markdown-content :deep(blockquote) {
  margin: 0.75rem 0;
  padding: 0.5rem 0.875rem;
  border-left: 3px solid rgb(34 211 238);
  background: rgba(34, 211, 238, 0.08);
  border-radius: 0.5rem;
}

.markdown-content :deep(hr) {
  border: 0;
  border-top: 1px dashed rgb(209 213 219);
  margin: 1rem 0;
}

.dark .markdown-content :deep(hr) {
  border-top-color: rgb(55 65 81);
}
</style>
