<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue'
import { useRoute } from 'vue-router'

const Button = defineAsyncComponent(() => import('@/components/ui/Button.vue') as any)
const Input = defineAsyncComponent(() => import('@/components/ui/Input.vue') as any)
const Textarea = defineAsyncComponent(() => import('@/components/ui/Textarea.vue') as any)
const Card = defineAsyncComponent(() => import('@/components/ui/Card.vue') as any)
const Badge = defineAsyncComponent(() => import('@/components/ui/Badge.vue') as any)

type ComponentKey = 'button' | 'input' | 'textarea' | 'card' | 'badge'

const route = useRoute()
const inputValue = ref('示例输入内容')
const textareaValue = ref('这是 Textarea 的示例文本。')

const titleMap: Record<ComponentKey, string> = {
  button: 'Button 组件详情',
  input: 'Input 组件详情',
  textarea: 'Textarea 组件详情',
  card: 'Card 组件详情',
  badge: 'Badge 组件详情',
}

const componentKey = computed<ComponentKey | null>(() => {
  const name = route.params.name
  if (typeof name !== 'string') return null
  if (['button', 'input', 'textarea', 'card', 'badge'].includes(name)) {
    return name as ComponentKey
  }
  return null
})

const pageTitle = computed(() => {
  if (!componentKey.value) return '组件不存在'
  return titleMap[componentKey.value]
})
</script>

<template>
  <main class="min-h-screen bg-muted/20 p-6 md:p-10">
    <section class="mx-auto w-full max-w-5xl space-y-6">
      <div class="flex flex-wrap items-center gap-3">
        <router-link to="/dev/components">
          <Button variant="outline">返回组件列表</Button>
        </router-link>
        <h1 class="text-2xl font-bold md:text-3xl">{{ pageTitle }}</h1>
      </div>

      <Card v-if="!componentKey" class="p-6">
        <p class="text-sm text-muted-foreground">
          未找到对应组件，请返回列表重新选择。
        </p>
      </Card>

      <template v-else-if="componentKey === 'button'">
        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">样式 Variants</h2>
          <div class="flex flex-wrap gap-3">
            <Button variant="default">Default</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
          </div>
        </Card>

        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">尺寸 Sizes</h2>
          <div class="flex flex-wrap items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="default">Default</Button>
            <Button size="lg">Large</Button>
            <Button size="icon">★</Button>
          </div>
        </Card>
      </template>

      <template v-else-if="componentKey === 'input'">
        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">基础输入</h2>
          <Input v-model="inputValue" placeholder="请输入文本" />
          <p class="text-sm text-muted-foreground">当前值：{{ inputValue }}</p>
        </Card>

        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">禁用状态</h2>
          <Input model-value="不可编辑" disabled />
        </Card>
      </template>

      <template v-else-if="componentKey === 'textarea'">
        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">基础输入</h2>
          <Textarea v-model="textareaValue" :rows="5" placeholder="请输入多行内容" />
          <p class="text-sm text-muted-foreground">当前值：{{ textareaValue }}</p>
        </Card>

        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">禁用状态</h2>
          <Textarea model-value="只读示例文本" :rows="4" disabled />
        </Card>
      </template>

      <template v-else-if="componentKey === 'card'">
        <Card class="p-6">
          <h2 class="mb-2 text-lg font-semibold">标准卡片</h2>
          <p class="text-sm text-muted-foreground">
            这是默认 Card 容器，适合承载一个信息区块或表单区块。
          </p>
        </Card>

        <Card class="space-y-3 p-6">
          <h2 class="text-lg font-semibold">带操作区块</h2>
          <p class="text-sm text-muted-foreground">
            可以在 Card 内自由组合按钮、输入框和标签。
          </p>
          <div class="flex gap-2">
            <Button>确认</Button>
            <Button variant="outline">取消</Button>
          </div>
        </Card>
      </template>

      <template v-else-if="componentKey === 'badge'">
        <Card class="space-y-4 p-6">
          <h2 class="text-lg font-semibold">标签样式</h2>
          <div class="flex flex-wrap gap-2">
            <Badge variant="default">Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="destructive">Destructive</Badge>
          </div>
        </Card>
      </template>
    </section>
  </main>
</template>
