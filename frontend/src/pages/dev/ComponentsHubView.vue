<script setup lang="ts">
interface ComponentItem {
  key: string
  name: string
  summary: string
}

const components: ComponentItem[] = [
  { key: 'button', name: 'Button', summary: '按钮样式、尺寸和禁用态。' },
  { key: 'input', name: 'Input', summary: '单行输入框、禁用态和占位符。' },
  { key: 'textarea', name: 'Textarea', summary: '多行输入、行数和状态展示。' },
  { key: 'card', name: 'Card', summary: '容器类组件，展示区块布局。' },
  { key: 'badge', name: 'Badge', summary: '状态标签和语义色展示。' },
]
</script>

<template>
  <main class="min-h-screen bg-muted/20 p-6 md:p-10">
    <section class="mx-auto w-full max-w-6xl space-y-6">
      <div class="space-y-2">
        <h1 class="text-2xl font-bold md:text-3xl">组件展示中心</h1>
        <p class="text-sm text-muted-foreground">
          先选择组件，再进入详情页进行样式和交互微调。
        </p>
      </div>

      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="item in components"
          :key="item.key"
          class="flex min-h-44 flex-col justify-between rounded-lg border bg-card p-5 text-card-foreground shadow-sm"
        >
          <div class="space-y-2">
            <h2 class="text-lg font-semibold">{{ item.name }}</h2>
            <p class="text-sm text-muted-foreground">{{ item.summary }}</p>
          </div>

          <div class="pt-4">
            <router-link :to="`/dev/components/${item.key}`">
              <span
                class="inline-flex h-10 w-full items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
              >
                进入详情
              </span>
            </router-link>
          </div>
        </div>
      </div>
    </section>
  </main>
</template>
