<script setup lang="ts">
import { defineAsyncComponent, ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import { useChatStore, STAGE_MAP, type Stage } from '@/stores/chat'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { Send, Bot, User, Loader2, Check, X, FileText, Plus, Clock, ChevronRight, Trash2, RefreshCw, Search, Zap, AlertTriangle, Scale, BookOpen, Gavel, BadgeCheck } from 'lucide-vue-next'
import NavBar from '@/components/ui/NavBar.vue'
import MarkdownViewer from '@/components/ui/MarkdownViewer.vue'

const Button = defineAsyncComponent(() => import('@/components/ui/Button.vue') as any)
const Input = defineAsyncComponent(() => import('@/components/ui/Input.vue') as any)
const Card = defineAsyncComponent(() => import('@/components/ui/Card.vue') as any)

const chatStore = useChatStore()
const authStore = useAuthStore()
const router = useRouter()

const inputMessage = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const inputRef = ref<{ focus: () => void } | null>(null)
const deletingId = ref<string | null>(null)
const pendingDeleteId = ref<string | null>(null)
const isEnteringS3 = ref(false)
let enteringS3Version = 0

async function deleteConversation(threadId: string) {
  pendingDeleteId.value = threadId
  try {
    await chatStore.deleteConversation(threadId)
  } finally {
    pendingDeleteId.value = null
    deletingId.value = null
  }
}

async function sendMessage() {
  const isS1Collecting = chatStore.dbStage === 's1_collecting' && chatStore.viewStage === 'S1'
  const isS3Collecting = chatStore.dbStage === 's3_collecting' && chatStore.viewStage === 'S3'
  const isS4Done = chatStore.dbStage === 's4_done' && chatStore.viewStage === 'S4'
  const canChatNow = isS1Collecting || isS3Collecting || isS4Done

  if (!inputMessage.value.trim() || chatStore.isThinking || !canChatNow) return
  if (!chatStore.isConnected && !await chatStore.connect()) return
  const text = inputMessage.value
  const threadId = chatStore.conversationId
  inputMessage.value = ''
  const accepted = await chatStore.send(text)
  if (!accepted && chatStore.conversationId === threadId && !inputMessage.value) inputMessage.value = text
  await nextTick()
  inputRef.value?.focus()
}

// 强制推进确认弹窗状态
const showAdvanceConfirm = ref(false)

function handleAdvance() {
  showAdvanceConfirm.value = false
  chatStore.advance()
}

async function goToS3() {
  const threadId = chatStore.conversationId
  if (!threadId || isEnteringS3.value) return
  const version = ++enteringS3Version
  const isCurrentEntry = () => version === enteringS3Version && chatStore.conversationId === threadId

  isEnteringS3.value = true
  try {
    chatStore.viewStage = 'S3'
    await chatStore.fetchMessages(threadId)
    if (!isCurrentEntry()) return

    const hasS3AssistantMsg = () =>
      chatStore.messages.some(m => m.role === 'assistant' && m.stage === 's3_collecting')

    if (hasS3AssistantMsg()) return

    for (let i = 0; i < 8; i++) {
      const state = await chatStore.syncState(threadId)
      if (!isCurrentEntry()) return
      if (state?.s3_opener_ready) {
        await chatStore.fetchMessages(threadId)
        return
      }
      await new Promise(r => setTimeout(r, 1200))
      if (!isCurrentEntry()) return
    }

    // 兜底：即便 opener 仍未到，也至少同步一次最新消息
    if (isCurrentEntry()) await chatStore.fetchMessages(threadId)
  } finally {
    if (version === enteringS3Version) isEnteringS3.value = false
  }
}

function handleConfirm(accepted: boolean) {
  if (accepted && chatStore.dbStage === 's3_confirming' && chatStore.conversationId) {
    pendingAutoOpenReportThreadId.value = chatStore.conversationId
  }
  chatStore.confirm(accepted)
}

const SIDEBAR_MIN_WIDTH = 200
const SIDEBAR_MAX_WIDTH = 600
const defaultWidth = parseInt(localStorage.getItem('sidebarWidth') || '288')
const sidebarWidth = ref(defaultWidth)
const isDragging = ref(false)

function startDrag() {
  isDragging.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
}

function onDrag(e: MouseEvent) {
  if (!isDragging.value) return
  let newWidth = e.clientX
  if (newWidth < SIDEBAR_MIN_WIDTH) newWidth = SIDEBAR_MIN_WIDTH
  if (newWidth > SIDEBAR_MAX_WIDTH) newWidth = SIDEBAR_MAX_WIDTH
  sidebarWidth.value = newWidth
}

function stopDrag() {
  isDragging.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  localStorage.setItem('sidebarWidth', sidebarWidth.value.toString())
}

const isStartingNewChat = ref(false)
const newChatCooldown = ref(0)
let cooldownTimer: number | null = null

function updateCooldown() {
  const lastTime = localStorage.getItem('lastNewChatTime')
  if (lastTime) {
    const elapsed = Date.now() - parseInt(lastTime, 10)
    if (elapsed < 60000) {
      newChatCooldown.value = Math.ceil((60000 - elapsed) / 1000)
    } else {
      newChatCooldown.value = 0
    }
  } else {
    newChatCooldown.value = 0
  }
}

function startCooldownTimer() {
  if (cooldownTimer) window.clearInterval(cooldownTimer)
  cooldownTimer = window.setInterval(() => {
    updateCooldown()
    if (newChatCooldown.value <= 0 && cooldownTimer) {
      window.clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

async function startNewChat() {
  if (newChatCooldown.value > 0 || isStartingNewChat.value) return
  isStartingNewChat.value = true
  pendingAutoOpenReportThreadId.value = null
  showReport.value = false
  try {
    chatStore.disconnect()
    chatStore.reset()
    if (!await chatStore.connect()) return
    await chatStore.fetchConversations()
    localStorage.setItem('lastNewChatTime', Date.now().toString())
    updateCooldown()
    startCooldownTimer()
  } finally {
    isStartingNewChat.value = false
  }
}

async function openConversation(threadId: string) {
  chatStore.disconnect()
  chatStore.reset()
  if (await chatStore.connect(threadId)) await chatStore.fetchMessages(threadId)
}

function stageLabel(stage: string) {
  const map: Record<string, string> = {
    s1_collecting: '案情收集', s1_confirming: '案情确认',
    s2_searching: '检索分析', s2_failed: '检索失败',
    s3_collecting: '情节补充', s3_confirming: '情节确认',
    s4_generating: '报告生成中', s4_done: '报告完成', s4_failed: '报告失败',
  }
  return map[stage] ?? stage
}

function formatAsTitle(iso: string | null) {
  if (!iso) return '新咨询'
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${min} 咨询`
}

function formatDate(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  const hh = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${mm}-${dd} ${hh}:${min}`
}

const expandedItems = ref<Set<string>>(new Set())
function toggleExpand(key: string) {
  if (expandedItems.value.has(key)) {
    expandedItems.value.delete(key)
  } else {
    expandedItems.value.add(key)
  }
}

const searchQuery = ref('')
const currentFilter = ref('all')

const filteredConversations = computed(() => {
  return chatStore.conversations.filter(c => {
    const matchSearch = !searchQuery.value || (c.title || '').toLowerCase().includes(searchQuery.value.toLowerCase())
    let matchFilter = true
    if (currentFilter.value === 'ongoing') {
      matchFilter = c.stage !== 's4_done'
    } else if (currentFilter.value === 'done') {
      matchFilter = c.stage === 's4_done'
    }
    return matchSearch && matchFilter
  })
})

// 是否显示"完成收集"按钮（S1 手动兜底 / S3 信号失效兜底）
const canAdvance = computed(() => {
  const userMsgCount = chatStore.messages.filter(m => m.role === 'user' && STAGE_MAP[m.stage ?? ''] === chatStore.viewStage).length

  // 仅在符合以下所有条件时显示常驻按钮:
  // 1. 当前数据库真实阶段是在收集阶段 (s1_collecting 或 s3_collecting)
  // 2. 只有在试图看当前正在进行的真实阶段时才显示 (避免看历史回顾时出现按钮)
  // 3. 用户至少说了 5 句话，防止一上来就点击
  // 4. 当前 AI 没在思考中
  return (chatStore.dbStage === 's1_collecting' || chatStore.dbStage === 's3_collecting')
    && chatStore.viewStage === (chatStore.dbStage === 's1_collecting' ? 'S1' : 'S3')
    && userMsgCount >= 5
    && !chatStore.isThinking
    && !chatStore.isLoading
})

// 输入框是否禁用
const inputDisabled = computed(() => {
  const canChatInS1 = chatStore.dbStage === 's1_collecting' && chatStore.viewStage === 'S1'
  const canChatInS3 = chatStore.dbStage === 's3_collecting' && chatStore.viewStage === 'S3'
  const canChatInS4 = chatStore.dbStage === 's4_done' && chatStore.viewStage === 'S4'
  const canChatNow = canChatInS1 || canChatInS3 || canChatInS4

  return (
    chatStore.conversationId == null
    || chatStore.isLoading
    || chatStore.isConfirming
    || isEnteringS3.value
    || chatStore.isThinking
    || !canChatNow
    || !!chatStore.confirmRequest
  )
})

// 报告弹窗显示状态（与 report 数据分离，关闭后仍可重开）
const showReport = ref(false)
const pendingAutoOpenReportThreadId = ref<string | null>(null)
const s4WasWaiting = ref(false)
// 仅在“本次会话内由 S3 确认触发的 S4 生成”完成后自动弹一次；恢复历史/切换会话不自动弹

watch(() => chatStore.isThinking, async (val) => {
  if (!val) {
    await nextTick()
    inputRef.value?.focus()
  }
})

watch(() => chatStore.viewStage, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
})

watch(() => chatStore.messages, async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}, { deep: true })

watch(() => chatStore.conversationId, () => {
  enteringS3Version++
  isEnteringS3.value = false
  inputMessage.value = ''
  showReport.value = false
  showAdvanceConfirm.value = false
  pendingAutoOpenReportThreadId.value = null
  s4WasWaiting.value = false
})

watch(() => authStore.token, token => {
  if (!token) router.replace({ name: 'login' })
})

watch(() => chatStore.isS4Waiting, (waiting) => {
  const currentThreadId = chatStore.conversationId
  const shouldAutoOpen =
    !waiting
    && s4WasWaiting.value
    && !!currentThreadId
    && pendingAutoOpenReportThreadId.value === currentThreadId
    && chatStore.dbStage === 's4_done'
    && !!chatStore.report

  if (shouldAutoOpen) {
    showReport.value = true
    pendingAutoOpenReportThreadId.value = null
  }

  s4WasWaiting.value = waiting
})

onMounted(async () => {
  updateCooldown()
  if (newChatCooldown.value > 0) startCooldownTimer()
  await Promise.all([chatStore.fetchConversations(), chatStore.conversationId ? chatStore.refreshState() : Promise.resolve()])
})

onUnmounted(() => {
  enteringS3Version++
  chatStore.disconnect()
  if (cooldownTimer) window.clearInterval(cooldownTimer)
  if (isDragging.value) stopDrag()
})

// 当前在 viewStage 下应该展示的消息
const currentStageMessages = computed(() => {
  return chatStore.messages.filter(m => {
    if (m.streaming) return true  // 正在流式输出的消息始终显示
    if (!m.stage) return true
    const mapped = STAGE_MAP[m.stage]
    return mapped === chatStore.viewStage
  })
})

const stages: { id: Stage; label: string }[] = [
  { id: 'S1', label: '案情询问' },
  { id: 'S2', label: '检索分析' },
  { id: 'S3', label: '情节收集' },
  { id: 'S4', label: '报告生成' },
]

const steps = [
  { title: '案情描述', desc: '用自然语言描述事件经过，AI 引导补全关键信息' },
  { title: '法条检索', desc: '自动检索相关法条与类似案例，生成量刑要素清单' },
  { title: '情节收集', desc: '逐项确认影响量刑的关键情节，如自首、赔偿等' },
  { title: '风险评估', desc: '生成结构化报告，涵盖罪名认定、量刑预估与辩护建议' },
]
</script>

<template>
  <div class="h-screen flex flex-col bg-background">
    <NavBar />

    <div class="md:hidden flex gap-2 p-2 border-b border-border/60">
      <Button size="sm" :disabled="isStartingNewChat || newChatCooldown > 0" @click="startNewChat">
        {{ isStartingNewChat ? '创建中...' : newChatCooldown > 0 ? `等待 ${newChatCooldown}s` : '新咨询' }}
      </Button>
      <select :value="chatStore.conversationId ?? ''" aria-label="历史咨询" class="min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-sm"
              @change="openConversation(($event.target as HTMLSelectElement).value)">
        <option disabled value="">选择历史咨询</option>
        <option v-for="conv in chatStore.conversations" :key="conv.thread_id" :value="conv.thread_id">
          {{ conv.title || formatAsTitle(conv.created_at) }}
        </option>
      </select>
    </div>

    <main class="flex-1 overflow-hidden flex flex-row">

      <!-- Left Sidebar -->
      <div
        class="relative border-r border-border/60 bg-gradient-to-b from-muted/55 via-muted/35 to-muted/20 shrink-0 hidden md:flex flex-col transition-[width] duration-0"
        :style="{ width: sidebarWidth + 'px' }"
      >

        <!-- 侧边栏头部区域 -->
        <div class="p-4 md:p-5 flex flex-col gap-4 border-b border-border/60 bg-gradient-to-b from-card/90 to-muted/45 backdrop-blur-[1px]">
          <!-- 新对话 -->
          <button @click="startNewChat"
            :disabled="isStartingNewChat || newChatCooldown > 0"
            class="w-full flex items-center justify-center md:justify-start gap-2 px-3 py-2.5 rounded-lg text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm">
            <Loader2 v-if="isStartingNewChat" class="w-4 h-4 shrink-0 animate-spin" />
            <Plus v-else class="w-4 h-4 shrink-0" />
            <span class="hidden md:inline">
              {{ isStartingNewChat ? '创建中...' : newChatCooldown > 0 ? `等待 ${newChatCooldown}s` : '开启新咨询' }}
            </span>
          </button>

          <!-- 搜索与筛选区域 -->
          <div class="flex flex-col gap-3">
            <!-- 搜索历史记录框 (占位) -->
            <div class="relative group hidden md:block">
              <div class="absolute inset-y-0 left-0 flex items-center pl-2.5 pointer-events-none">
                <Search class="w-3.5 h-3.5 text-muted-foreground/50 group-hover:text-primary/50 transition-colors" />
              </div>
              <input
                type="text"
                v-model="searchQuery"
                placeholder="搜索历史记录..."
                class="w-full h-8 pl-8 pr-3 text-xs rounded-md bg-card/80 border border-border/70 text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-primary/30 transition-all hover:bg-card shadow-sm/20"
              />
            </div>

            <!-- 快捷过滤器标签 -->
            <div class="hidden md:flex items-center gap-1.5 flex-wrap">
              <button
                @click="currentFilter = 'all'"
                class="px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors"
                :class="currentFilter === 'all' ? 'bg-primary/12 text-primary border border-primary/25 shadow-sm/20' : 'bg-muted/70 text-muted-foreground border border-border/60 hover:bg-muted cursor-pointer'">
                全部案件
              </button>
              <button
                @click="currentFilter = 'done'"
                class="px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors"
                :class="currentFilter === 'done' ? 'bg-primary/12 text-primary border border-primary/25 shadow-sm/20' : 'bg-muted/70 text-muted-foreground border border-border/60 hover:bg-muted cursor-pointer'">
                已完结
              </button>
              <button
                @click="currentFilter = 'ongoing'"
                class="px-2.5 py-1 rounded-full text-[10px] font-medium transition-colors"
                :class="currentFilter === 'ongoing' ? 'bg-primary/12 text-primary border border-primary/25 shadow-sm/20' : 'bg-muted/70 text-muted-foreground border border-border/60 hover:bg-muted cursor-pointer'">
                进行中
              </button>
            </div>
          </div>
        </div>

        <!-- 历史会话 -->
        <div class="flex-1 overflow-y-auto py-3 px-2 md:px-3 space-y-1">
          <div class="hidden md:flex items-center justify-between px-2 mb-2">
            <p class="text-[11px] font-bold uppercase tracking-wider text-foreground/80">历史记录</p>
            <button @click="chatStore.fetchConversations"
                    class="p-1 rounded hover:bg-muted text-muted-foreground transition-colors"
                    title="刷新历史会话">
              <RefreshCw class="w-3 h-3" :class="{ 'animate-spin': chatStore.isFetchingConversations }" />
            </button>
          </div>

          <div v-if="chatStore.isFetchingConversations" class="hidden md:block px-2 py-4 space-y-2">
            <div class="h-8 bg-muted animate-pulse rounded-lg"></div>
            <div class="h-8 bg-muted animate-pulse rounded-lg"></div>
            <div class="h-8 bg-muted animate-pulse rounded-lg"></div>
          </div>
          <template v-else>
            <div v-if="chatStore.conversations.length === 0"
                 class="hidden md:block text-[10px] text-muted-foreground/50 px-2">暂无历史</div>
            <div v-else-if="filteredConversations.length === 0"
                 class="hidden md:block text-[10px] text-muted-foreground/50 px-2">未搜到符合记录的案情</div>
            <div v-for="conv in filteredConversations" :key="conv.id"
               class="group relative flex items-start gap-2 px-2 py-2 rounded-lg hover:bg-muted/70 transition-colors cursor-pointer border border-transparent hover:border-border/40"
               :class="chatStore.conversationId === conv.thread_id ? 'bg-primary/12 border-primary/25 border-l-4 text-primary font-medium shadow-sm' : ''"
               @click="deletingId !== conv.thread_id && openConversation(conv.thread_id)">
            <Clock class="w-3 h-3 shrink-0 mt-0.5 text-muted-foreground/50" />
            <div class="hidden md:flex flex-col min-w-0 flex-1">
              <span class="text-[11px] font-medium text-foreground truncate">
                {{ conv.title || formatAsTitle(conv.created_at) }}
              </span>
              <span class="text-[10px] text-muted-foreground/60">{{ formatDate(conv.updated_at || conv.created_at) }}</span>
            </div>
            <!-- 删除按钮（仅宽屏 hover 时显示） -->
            <div v-if="deletingId !== conv.thread_id"
                 class="hidden md:flex items-center opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
              <button @click.stop="deletingId = conv.thread_id"
                class="p-0.5 rounded text-muted-foreground/50 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/30 transition-colors">
                <Trash2 class="w-3 h-3" />
              </button>
            </div>
            <!-- 确认删除 -->
            <div v-if="deletingId === conv.thread_id"
                 class="hidden md:flex items-center gap-1 shrink-0" @click.stop>
              <button @click.stop="deleteConversation(conv.thread_id)"
                :disabled="pendingDeleteId === conv.thread_id"
                class="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-rose-500 text-white hover:bg-rose-600 transition-colors disabled:opacity-50">
                <Loader2 v-if="pendingDeleteId === conv.thread_id" class="w-2.5 h-2.5 animate-spin" />
                <span>{{ pendingDeleteId === conv.thread_id ? '删除中' : '删除' }}</span>
              </button>
              <button @click.stop="deletingId = null"
                :disabled="pendingDeleteId === conv.thread_id"
                class="text-[10px] px-1.5 py-0.5 rounded border border-border/60 text-muted-foreground hover:bg-muted transition-colors disabled:opacity-50">
                取消
              </button>
            </div>
          </div>
          </template>
        </div>

        <!-- 拖拽手柄 -->
        <div
          class="absolute right-0 top-0 bottom-0 w-1 cursor-col-resize z-50 hover:bg-primary/50 transition-colors"
          :class="{ 'bg-primary/50': isDragging }"
          @mousedown.prevent="startDrag"
        ></div>
      </div>

      <!-- Chat Area -->
      <div class="flex-1 flex flex-col min-w-0">

        <!-- 会话头部 / Navbar -->
        <div v-if="chatStore.conversationId" class="h-14 border-b border-border/60 bg-muted/30 flex items-center justify-between px-4 shrink-0">
          <div class="text-[13px] font-medium text-foreground/80 truncate max-w-[30%] hidden sm:block">
            {{ chatStore.conversations.find(c => c.thread_id === chatStore.conversationId)?.title || formatAsTitle(chatStore.conversations.find(c => c.thread_id === chatStore.conversationId)?.created_at || null) }}
          </div>
          <div class="flex-1 sm:hidden"></div>

          <div class="flex items-center justify-end gap-3 cursor-pointer">
            <!-- S4 查看报告按钮 (仅在处于最终阶段或通过历史查看S4阶段且已有报告时在顶部显示) -->
            <button v-if="chatStore.viewStage === 'S4' && chatStore.dbStage === 's4_done' && chatStore.report && !showReport"
              @click="showReport = true"
              title="查看风险评估报告"
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-bold bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 transition-all hover:scale-105">
              <FileText class="w-3.5 h-3.5" />
              <span class="hidden sm:inline">查看风险评估报告</span>
            </button>
            <div class="h-4 w-px bg-border/60 mx-1 hidden sm:block" v-if="chatStore.viewStage === 'S4' && chatStore.dbStage === 's4_done' && chatStore.report && !showReport"></div>

            <!-- 强制推进评估的入口按钮 -->
            <button v-if="canAdvance"
              @click="showAdvanceConfirm = true"
              title="强制提交评估"
              class="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-amber-500/10 text-amber-600 border border-amber-500/20 hover:bg-amber-500/20 transition-colors">
              <Zap class="w-3.5 h-3.5 fill-current" />
              <span class="hidden sm:inline">强制提交评估</span>
            </button>
            <div class="h-4 w-px bg-border/60 mx-1 hidden sm:block" v-if="canAdvance"></div>

            <template v-for="(s, idx) in stages" :key="s.id">
              <div
                @click="!chatStore.isThinking && !isEnteringS3 && (s.id === 'S3' ? goToS3() : (chatStore.viewStage = stages[idx].id))"
                class="flex items-center gap-1.5 transition-all group relative px-2 py-1 rounded-md"
                :class="[
                  chatStore.stageIndex >= idx ? 'text-primary' : 'text-muted-foreground/40',
                  (chatStore.isThinking || isEnteringS3) ? 'cursor-not-allowed opacity-60' :  'cursor-pointer',
                  chatStore.viewStage === s.id
                    ? 'bg-primary/15 ring-1 ring-primary/35'
                    : !chatStore.isThinking && 'hover:bg-muted/60'
                ]">
                <div class="w-5 h-5 rounded-full border flex items-center justify-center text-[10px] font-medium shrink-0 transition-colors"
                     :class="{
                       'border-primary bg-primary text-primary-foreground shadow-sm': chatStore.stageIndex === idx,
                       'border-primary bg-primary/10 text-primary': chatStore.stageIndex > idx,
                       'border-border/60 bg-background': chatStore.stageIndex < idx,
                     }">
                  <Check v-if="chatStore.stageIndex > idx" class="w-3 h-3" />
                  <span v-else>{{ idx + 1 }}</span>
                </div>
                <span class="text-[11px] sm:text-xs"
                      :class="chatStore.viewStage === s.id ? 'font-semibold text-primary' : 'font-medium'">
                  {{ s.label }}
                </span>
              </div>
              <div v-if="idx < stages.length - 1" class="w-2 sm:w-4 h-px bg-border/60 mx-1.5 sm:mx-2 hidden sm:block"></div>
              <div v-if="idx < stages.length - 1" class="w-1.5 h-px bg-border/60 mx-1 sm:hidden"></div>
            </template>
          </div>
        </div>

        <div ref="messagesContainer" class="flex-1 overflow-y-auto p-4 space-y-6">

          <div v-if="chatStore.requestError" role="alert" class="max-w-3xl mx-auto rounded-xl border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {{ chatStore.requestError }}
          </div>
          <div v-if="chatStore.dbStage === 's2_failed' || chatStore.dbStage === 's4_failed'" class="max-w-3xl mx-auto flex justify-end">
            <Button :disabled="chatStore.isConfirming" @click="chatStore.retry()">
              {{ chatStore.isConfirming ? '提交中...' : chatStore.dbStage === 's2_failed' ? '重新检索' : '重新生成报告' }}
            </Button>
          </div>
          <div v-else-if="(chatStore.dbStage === 's4_generating' && !chatStore.isS4Waiting) || (chatStore.dbStage === 's2_searching' && !chatStore.isS2Waiting)" class="max-w-3xl mx-auto flex justify-end">
            <Button variant="outline" @click="chatStore.refreshState()">刷新处理状态</Button>
          </div>

          <!-- 加载中骨架屏 -->
          <div v-if="chatStore.isLoading" class="space-y-5 max-w-3xl mx-auto w-full">
            <div v-for="i in 6" :key="i" class="flex gap-3" :class="i % 3 === 0 ? 'flex-row-reverse' : ''">
              <div class="w-7 h-7 rounded-full bg-muted animate-pulse shrink-0 mt-0.5" />
              <div class="flex flex-col gap-1.5" :class="i % 3 === 0 ? 'items-end' : 'items-start'"
                   :style="`width: ${40 + (i * 11) % 38}%`">
                <div class="h-3 rounded bg-muted animate-pulse w-10" />
                <div class="rounded-2xl bg-muted animate-pulse w-full"
                     :style="`height: ${i % 2 === 0 ? '56px' : '36px'}; animation-delay: ${i * 60}ms`" />
                <div v-if="i % 2 === 0" class="h-3 rounded bg-muted animate-pulse"
                     :style="`width: 60%; animation-delay: ${i * 60 + 30}ms`" />
              </div>
            </div>
          </div>

          <!-- 引导首页：未进入任何会话时显示 -->
          <div v-if="!chatStore.isLoading && !chatStore.isConnected" class="h-full flex flex-col items-center justify-center animate-fade-in">
            <div class="w-full max-w-xl mx-auto px-4 space-y-8">

              <!-- Logo + 标题 -->
              <div class="text-center space-y-3">
                <div class="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto shadow-sm">
                  <Bot class="w-8 h-8 text-primary/70" />
                </div>
                <div>
                  <h1 class="text-xl font-bold text-foreground">LawGent 刑事法律助手</h1>
                  <p class="text-sm text-muted-foreground mt-1">通过智能对话，为您提供专业的刑事案件风险评估</p>
                </div>
              </div>

              <!-- 流程说明 -->
              <div class="grid grid-cols-2 gap-3">
                <div v-for="(step, i) in steps" :key="i"
                     class="bg-card border border-border/60 rounded-xl p-3 flex gap-3 items-start">
                  <div class="w-6 h-6 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-[10px] font-bold text-primary shrink-0 mt-0.5">
                    {{ i + 1 }}
                  </div>
                  <div>
                    <div class="text-xs font-semibold text-foreground">{{ step.title }}</div>
                    <div class="text-[11px] text-muted-foreground mt-0.5">{{ step.desc }}</div>
                  </div>
                </div>
              </div>

              <!-- 操作入口 -->
              <div class="space-y-3">
                <button @click="startNewChat"
                  class="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl text-sm font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm">
                  <Plus class="w-4 h-4" />
                  开始新咨询
                </button>

                <!-- 最近会话 -->
                <div v-if="chatStore.conversations.length > 0" class="space-y-1.5">
                  <p class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground px-1">最近咨询</p>
                  <button v-for="conv in chatStore.conversations.slice(0, 3)" :key="conv.id"
                    @click="openConversation(conv.thread_id)"
                    class="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left bg-card border border-border/60 hover:border-primary/30 hover:bg-primary/5 transition-colors group">
                    <Clock class="w-3.5 h-3.5 text-muted-foreground/50 shrink-0" />
                    <div class="flex-1 min-w-0">
                      <div class="text-xs font-medium text-foreground truncate">
                        {{ conv.title || formatAsTitle(conv.created_at) }}
                      </div>
                      <div class="text-[10px] text-muted-foreground">{{ formatDate(conv.updated_at || conv.created_at) }}</div>
                    </div>
                    <ChevronRight class="w-3.5 h-3.5 text-muted-foreground/30 group-hover:text-primary/50 transition-colors shrink-0" />
                  </button>
                </div>
              </div>

              <p class="text-center text-[10px] text-muted-foreground/50">
                内容由 AI 生成，仅供参考，不作为正式法律意见
              </p>
            </div>
          </div>

          <!-- 空状态：已进入会话但无消息 -->
          <div v-if="!chatStore.isLoading && chatStore.messages.length === 0 && chatStore.isConnected"
               class="h-full flex flex-col items-center justify-center text-muted-foreground space-y-3">
            <div class="w-16 h-16 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
              <Bot class="w-8 h-8 text-primary/60" />
            </div>
            <div class="text-center space-y-1">
              <p class="font-medium text-foreground/70 text-sm">你好，我是 LawGent</p>
              <p class="text-xs text-muted-foreground">请描述您的案情，我将为您提供法律风险评估</p>
            </div>
          </div>

          <!-- 消息列表 -->
          <div v-if="!chatStore.isLoading" v-for="msg in currentStageMessages" :key="msg.id"
               class="flex gap-3 max-w-3xl mx-auto w-full"
               :class="[msg.role === 'user' ? 'flex-row-reverse bubble-right' : 'bubble-left']">
            <div class="shrink-0 mt-0.5">
              <div v-if="msg.role === 'user'" class="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-primary-foreground shadow-sm">
                <User class="w-3.5 h-3.5" />
              </div>
              <div v-else class="w-7 h-7 rounded-full border border-border/60 bg-card flex items-center justify-center text-primary shadow-sm">
                <Bot class="w-3.5 h-3.5" />
              </div>
            </div>
            <div class="flex flex-col gap-1 max-w-[78%]">
              <span class="text-[10px] font-medium text-muted-foreground px-1" :class="msg.role === 'user' ? 'text-right' : ''">
                {{ msg.role === 'user' ? '您' : 'LawGent' }}
              </span>
              <div class="rounded-2xl px-4 py-2.5 text-sm leading-relaxed break-words"
                   :class="msg.role === 'user'
                     ? 'bg-primary text-primary-foreground shadow-sm rounded-tr-sm whitespace-pre-wrap'
                     : 'bg-card border border-border/60 shadow-sm rounded-tl-sm prose prose-sm prose-slate dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:my-0'">
                <!-- 如果是用户消息，保持纯文本渲染 -->
                <template v-if="msg.role === 'user'">
                  {{ msg.content }}
                </template>
                <!-- 如果是 AI 消息，使用 MarkdownViewer 渲染 -->
                <template v-else>
                  <MarkdownViewer :content="msg.content" />
                </template>
                <span v-if="msg.streaming" class="typing-cursor"></span>
              </div>
            </div>
          </div>

          <!-- 思考中 -->
          <div v-if="chatStore.isThinking && !chatStore.messages.some(m => m.streaming)"
               class="flex gap-3 max-w-3xl mx-auto w-full">
            <div class="w-7 h-7 rounded-full border border-border/60 bg-card flex items-center justify-center text-primary shrink-0 mt-0.5">
              <Bot class="w-3.5 h-3.5" />
            </div>
            <div class="rounded-2xl rounded-tl-sm px-4 py-2.5 bg-card border border-border/60 shadow-sm flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 class="w-3.5 h-3.5 animate-spin text-primary" />
              <span>思考中...</span>
            </div>
          </div>

          <!-- S2 检索等待 -->
          <div v-if="chatStore.isS2Waiting && chatStore.viewStage === 'S2' && !chatStore.s2SearchOutput" class="max-w-2xl mx-auto w-full">
            <div class="relative bg-card border border-indigo-200/60 rounded-2xl p-5 overflow-hidden shadow-sm">
              <div class="absolute inset-0 bg-gradient-to-br from-indigo-50/60 via-transparent to-blue-50/40 pointer-events-none" />

              <div class="relative flex items-center gap-3 mb-4">
                <div class="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center shadow-md shrink-0">
                  <Scale class="w-4.5 h-4.5 text-white" style="width:18px;height:18px" />
                </div>
                <div class="flex-1">
                  <p class="text-sm font-semibold text-foreground">AI 正在检索相关法律与案例</p>
                  <p class="text-[11px] text-muted-foreground mt-0.5">预计需要 10–20 秒，请稍候</p>
                </div>
                <Loader2 class="w-4 h-4 animate-spin text-indigo-500 shrink-0" />
              </div>

              <!-- 呼吸感进度条 -->
              <div class="relative h-1.5 bg-indigo-100 rounded-full overflow-hidden">
                <div class="absolute inset-y-0 left-0 bg-indigo-500 rounded-full animate-s2-bar" />
              </div>
              <p class="text-[10px] text-indigo-400 mt-2 text-right">正在匹配法条与判例库...</p>
            </div>
          </div>

          <!-- S3 进入中提示 -->
          <div v-if="isEnteringS3 && chatStore.viewStage === 'S3' && !chatStore.messages.some(m => m.stage === 's3_collecting')" class="max-w-2xl mx-auto w-full">
            <div class="bg-card border border-indigo-200/60 rounded-2xl px-4 py-3 flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 class="w-4 h-4 animate-spin text-indigo-600 shrink-0" />
              <div>
                <p class="font-medium text-foreground">正在加载 S3 开场引导...</p>
                <p class="text-xs mt-0.5">已进入 S3，正在同步最新消息</p>
              </div>
            </div>
          </div>

          <!-- S4 报告生成等待 -->
          <div v-if="chatStore.isS4Waiting && chatStore.viewStage === 'S4'" class="max-w-2xl mx-auto w-full">
            <div class="bg-card border border-primary/20 rounded-2xl px-4 py-3 flex items-center gap-3 text-sm text-muted-foreground">
              <Loader2 class="w-4 h-4 animate-spin text-primary shrink-0" />
              <div>
                <p class="font-medium text-foreground">正在生成法律风险评估报告...</p>
                <p class="text-xs mt-0.5">AI 正在综合分析，请稍候</p>
              </div>
            </div>
          </div>

          <!-- 确认卡片 -->
          <Card v-if="chatStore.confirmRequest" class="max-w-2xl mx-auto w-full border-primary/30 shadow-lg shadow-primary/10 p-4 space-y-3 animate-fade-in">
            <div class="flex items-center gap-2 font-semibold text-sm text-primary">
              <div class="w-6 h-6 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Check class="w-3.5 h-3.5" />
              </div>
              {{ chatStore.confirmRequest.type === 'facts' ? '请确认案情摘要' : '请确认量刑情节' }}
            </div>
            <div class="text-sm text-foreground bg-muted/60 border border-border/60 p-3 rounded-lg whitespace-pre-wrap leading-relaxed">
              {{ chatStore.confirmRequest.summary }}
            </div>
            <div class="flex gap-2 justify-end pt-1">
              <Button variant="outline" size="sm" :disabled="chatStore.isConfirming || chatStore.isThinking || chatStore.isLoading" @click="handleConfirm(false)">
                <X class="w-3.5 h-3.5 mr-1" /> 需要补充
              </Button>
              <Button size="sm" :disabled="chatStore.isConfirming || chatStore.isThinking || chatStore.isLoading" @click="handleConfirm(true)">
                <Check class="w-3.5 h-3.5 mr-1" /> 确认无误
              </Button>
            </div>
          </Card>
          <!-- 阶段专属底部结果卡片 (随着聊天消息滚动在最底部) -->
          <div class="max-w-3xl mx-auto w-full pt-4 pb-2 animate-fade-in">
            <!-- S1 案情结果卡片 -->
            <div v-if="chatStore.viewStage === 'S1' && chatStore.s1ConfirmedSummary"
                 class="bg-blue-50/50 border border-blue-200/60 rounded-xl p-4 relative overflow-hidden group">
              <div class="absolute top-0 right-0 w-16 h-16 bg-blue-100/50 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
              <div class="flex items-center gap-2 mb-2 relative z-10">
                <div class="w-6 h-6 rounded-full bg-blue-100/80 flex items-center justify-center text-blue-600">
                  <Check class="w-3.5 h-3.5" />
                </div>
                <span class="text-xs font-bold text-blue-700 tracking-wide">本阶段已确认结论：案情摘要</span>
              </div>
              <div class="text-sm text-foreground/80 leading-relaxed pl-8 relative z-10 whitespace-pre-wrap">
                {{ chatStore.s1ConfirmedSummary }}
              </div>
            </div>

            <!-- S2 检索结果卡片 -->
            <div v-if="chatStore.viewStage === 'S2' && chatStore.s2SearchOutput"
                 class="relative bg-gradient-to-b from-indigo-50/40 to-card border border-indigo-200/70 rounded-2xl overflow-hidden shadow-sm">

              <!-- 顶部 Header -->
              <div class="flex items-center gap-3 px-5 py-3.5 border-b border-indigo-100/80 bg-indigo-50/60">
                <div class="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center shadow-sm shrink-0">
                  <BadgeCheck class="w-4 h-4 text-white" />
                </div>
                <div class="flex-1 min-w-0">
                  <p class="text-xs font-bold text-indigo-800 tracking-wide">检索分析完成</p>
                  <p class="text-[10px] text-indigo-500 mt-0.5">已匹配相关法条与类似判例，供参考</p>
                </div>
                <div class="flex items-center gap-1.5 text-[10px] font-medium text-indigo-600 bg-indigo-100/70 border border-indigo-200/60 px-2 py-0.5 rounded-full shrink-0">
                  <Check class="w-3 h-3" />
                  <span>S2 完成</span>
                </div>
              </div>

              <!-- 双列内容区 -->
              <div class="p-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 items-start">

                  <!-- 法条面板 -->
                  <div v-if="(chatStore.s2SearchOutput as any).articles?.length"
                       class="flex flex-col rounded-xl border border-indigo-100 bg-white/80 shadow-sm overflow-hidden">
                    <!-- 面板头 -->
                    <div class="flex items-center gap-2 px-3.5 py-2.5 border-b border-indigo-100/60 bg-indigo-50/50">
                      <div class="w-6 h-6 rounded-md bg-indigo-100 flex items-center justify-center shrink-0">
                        <BookOpen class="w-3.5 h-3.5 text-indigo-600" />
                      </div>
                      <span class="text-xs font-bold text-indigo-800">匹配法条</span>
                      <span class="ml-auto text-[10px] font-medium text-indigo-500 bg-indigo-100/80 px-1.5 py-0.5 rounded-full">
                        {{ (chatStore.s2SearchOutput as any).articles.length }} 条
                      </span>
                    </div>
                    <!-- 法条列表 -->
                    <div class="divide-y divide-indigo-50/80 max-h-[55vh] overflow-y-auto custom-scrollbar">
                      <div v-for="law in (chatStore.s2SearchOutput as any).articles" :key="law.id"
                           class="px-3.5 py-3 hover:bg-indigo-50/40 transition-colors cursor-pointer"
                           @click="toggleExpand('law-' + law.id)">
                        <!-- 标题行 -->
                        <div class="flex items-start justify-between gap-2 mb-1.5">
                          <span class="text-[13px] font-semibold text-indigo-900 leading-snug">{{ law.title }}</span>
                          <span class="shrink-0 text-[10px] font-medium text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded-md whitespace-nowrap">
                            RRF {{ law.similarity.toFixed(4) }}
                          </span>
                        </div>
                        <!-- 章节 -->
                        <div class="flex items-center gap-1 mb-2">
                          <Scale class="w-3 h-3 text-indigo-400 shrink-0" />
                          <span class="text-[11px] text-indigo-500">{{ law.chapter }}</span>
                        </div>
                        <!-- 内容 -->
                        <p class="text-[12px] text-slate-600 leading-relaxed" :class="expandedItems.has('law-' + law.id) ? '' : 'line-clamp-3'">
                          {{ law.content }}
                        </p>
                      </div>
                    </div>
                  </div>

                  <!-- 判例面板 -->
                  <div v-if="(chatStore.s2SearchOutput as any).cases?.length"
                       class="flex flex-col rounded-xl border border-indigo-100 bg-white/80 shadow-sm overflow-hidden">
                    <!-- 面板头 -->
                    <div class="flex items-center gap-2 px-3.5 py-2.5 border-b border-indigo-100/60 bg-indigo-50/50">
                      <div class="w-6 h-6 rounded-md bg-indigo-100 flex items-center justify-center shrink-0">
                        <Gavel class="w-3.5 h-3.5 text-indigo-600" />
                      </div>
                      <span class="text-xs font-bold text-indigo-800">相关判例</span>
                      <span class="ml-auto text-[10px] font-medium text-indigo-500 bg-indigo-100/80 px-1.5 py-0.5 rounded-full">
                        {{ (chatStore.s2SearchOutput as any).cases.length }} 篇
                      </span>
                    </div>
                    <!-- 判例列表 -->
                    <div class="divide-y divide-indigo-50/80 max-h-[55vh] overflow-y-auto custom-scrollbar">
                      <div v-for="c in (chatStore.s2SearchOutput as any).cases" :key="c.id"
                           class="px-3.5 py-3 hover:bg-indigo-50/40 transition-colors cursor-pointer"
                           @click="toggleExpand('case-' + c.id)">
                        <!-- 罪名 + 关联度 -->
                        <div class="flex items-start justify-between gap-2 mb-2">
                          <span class="text-[13px] font-semibold text-indigo-900 leading-snug">{{ c.accusations?.join('、') }}案</span>
                          <span class="shrink-0 text-[10px] font-medium text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded-md whitespace-nowrap">
                            RRF {{ c.similarity.toFixed(4) }}
                          </span>
                        </div>
                        <!-- 量刑标签 -->
                        <div class="flex flex-wrap gap-1.5 mb-2">
                          <span v-if="c.death_penalty" class="text-[10px] font-medium text-destructive">死刑</span>
                          <span v-else-if="c.life_imprisonment" class="text-[10px] font-medium text-destructive">无期徒刑</span>
                          <span v-else-if="c.sentence_months != null"
                                class="inline-flex items-center gap-1 text-[10px] font-medium text-slate-600 bg-slate-50 border border-slate-200/70 px-1.5 py-0.5 rounded-md">
                            刑期 {{ c.sentence_months }}个月
                          </span>
                          <span v-if="c.fine_amount != null"
                                class="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200/70 px-1.5 py-0.5 rounded-md">
                            罚金 {{ c.fine_amount }}元
                          </span>
                          <span v-if="c.criminals?.length"
                                class="inline-flex items-center gap-1 text-[10px] font-medium text-slate-500 bg-slate-50 border border-slate-200/70 px-1.5 py-0.5 rounded-md truncate max-w-[90px]"
                                :title="c.criminals.join(', ')">
                            被告 {{ c.criminals.join('、') }}
                          </span>
                        </div>
                        <!-- 案情摘要 -->
                        <p class="text-[12px] text-slate-600 leading-relaxed" :class="expandedItems.has('case-' + c.id) ? '' : 'line-clamp-3'">
                          {{ c.fact }}
                        </p>
                      </div>
                    </div>
                  </div>

                </div>
              </div>

              <!-- 底部操作栏 -->
              <div v-if="chatStore.dbStage === 's3_collecting'"
                   class="flex items-center justify-between px-5 py-3 border-t border-indigo-100/80 bg-indigo-50/40">
                <p class="text-[11px] text-indigo-500">已完成检索，可进入下一步补充量刑情节</p>
                <button @click="goToS3()"
                        :disabled="isEnteringS3"
                        class="flex items-center gap-1.5 px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 disabled:cursor-not-allowed text-white rounded-lg text-xs font-semibold transition-colors shadow-sm cursor-pointer">
                  <Loader2 v-if="isEnteringS3" class="w-3.5 h-3.5 animate-spin" />
                  {{ isEnteringS3 ? '加载中...' : '完善量刑情节' }}
                  <ChevronRight v-if="!isEnteringS3" class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <!-- S3 情节结果卡片 -->
            <div v-if="chatStore.viewStage === 'S3' && chatStore.s3ConfirmedFacts"
                 class="bg-emerald-50/50 border border-emerald-200/60 rounded-xl p-4 relative overflow-hidden group">
              <div class="absolute top-0 right-0 w-16 h-16 bg-emerald-100/50 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
              <div class="flex items-center gap-2 mb-2 relative z-10">
                <div class="w-6 h-6 rounded-full bg-emerald-100/80 flex items-center justify-center text-emerald-600">
                  <Check class="w-3.5 h-3.5" />
                </div>
                <span class="text-xs font-bold text-emerald-700 tracking-wide">本阶段已确认结论：量刑情节汇总</span>
              </div>
              <div class="text-sm text-foreground/80 leading-relaxed pl-8 relative z-10 whitespace-pre-wrap">
                {{ chatStore.s3ConfirmedFacts }}
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area -->
        <div class="p-4 bg-card/50 border-t border-border/60 backdrop-blur-sm">
          <div class="max-w-3xl mx-auto space-y-2">
            <form @submit.prevent="sendMessage" class="flex items-end gap-2">
              <Input ref="inputRef"
                     type="textarea"
                     rows="1"
                     v-model="inputMessage"
                     :placeholder="
                       chatStore.conversationId == null ? '请先选择或新建一个会话'
                       : chatStore.dbStage === 's1_confirming' ? '案情待确认，确认后继续...'
                       : chatStore.dbStage === 's2_searching' ? '检索分析中，请稍候...'
                       : chatStore.dbStage === 's3_confirming' ? '情节待确认，确认后继续...'
                       : chatStore.dbStage === 's4_generating' ? '风险评估报告生成中，请稍候...'
                       : chatStore.dbStage === 's4_done' ? '可继续提问，了解报告细节...'
                       : chatStore.dbStage === 's4_failed' ? '报告生成失败，请稍后重试'
                       : chatStore.viewStage === 'S1' ? '输入案情或回复...'
                       : chatStore.viewStage === 'S3' ? '补充量刑情节信息...'
                       : '当前阶段不可输入'
                     "
                     :disabled="inputDisabled"
                     class="flex-1 bg-background max-h-[120px]"
                     @keydown.enter.exact.prevent="sendMessage" />
              <Button type="submit" :disabled="!inputMessage.trim() || inputDisabled" class="shrink-0 h-10">
                <Send class="w-4 h-4" />
              </Button>
            </form>
            <p class="text-center text-[10px] text-muted-foreground/60">
              内容由 AI 生成，仅供参考，不作为正式法律意见
            </p>
          </div>
        </div>
      </div>

    </main>

    <!-- Report Modal -->
    <div v-if="showReport && chatStore.report" class="fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm flex items-center justify-center p-4 md:p-8 animate-fade-in">
      <Card class="w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl border-border/60">
        <div class="px-5 py-4 border-b border-border/60 flex justify-between items-center shrink-0">
          <h2 class="text-base font-bold flex items-center gap-2">
            <div class="w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center">
              <FileText class="w-4 h-4 text-primary" />
            </div>
            法律风险评估报告
          </h2>
          <Button variant="ghost" size="icon" @click="showReport = false">
            <X class="w-4 h-4" />
          </Button>
        </div>
        <div class="p-6 overflow-y-auto flex-1 bg-muted/10 space-y-4 text-sm">

          <!-- 数据质量提示 -->
          <div v-if="(chatStore.report.data_quality as any)?.level"
               class="rounded-xl p-3 flex items-start gap-2 text-xs"
               :class="(chatStore.report.data_quality as any).level === '高'
                 ? 'bg-emerald-50 border border-emerald-200/60 text-emerald-700 dark:bg-emerald-950/20 dark:border-emerald-800/40 dark:text-emerald-400'
                 : (chatStore.report.data_quality as any).level === '中'
                   ? 'bg-amber-50 border border-amber-200/60 text-amber-700 dark:bg-amber-950/20 dark:border-amber-800/40 dark:text-amber-400'
                   : 'bg-rose-50 border border-rose-200/60 text-rose-700 dark:bg-rose-950/20 dark:border-rose-800/40 dark:text-rose-400'">
            <span class="font-semibold shrink-0">数据质量：{{ (chatStore.report.data_quality as any).level }}</span>
            <span>{{ (chatStore.report.data_quality as any).note }}</span>
          </div>

          <!-- 罪名 -->
          <div class="bg-card border border-border/60 rounded-xl p-4">
            <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">罪名认定</div>
            <div class="font-bold text-base text-primary">{{ chatStore.report.crime }}</div>
            <div class="text-xs text-muted-foreground mt-1">{{ chatStore.report.crime_basis }}</div>
          </div>

          <!-- 量刑幅度 -->
          <div class="bg-card border border-border/60 rounded-xl p-4">
            <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">法定量刑幅度</div>
            <div class="font-medium">{{ chatStore.report.sentence_range }}</div>
          </div>

          <!-- 有利/不利情节 -->
          <div class="grid grid-cols-2 gap-3">
            <div class="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-800/40 rounded-xl p-4">
              <div class="text-[10px] font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 mb-2">有利情节</div>
              <div v-for="f in (chatStore.report.factors as any)?.favorable" :key="f.item" class="mb-2">
                <div class="font-medium text-xs">{{ f.item }}</div>
                <div class="text-[11px] text-muted-foreground">{{ f.basis }}</div>
              </div>
            </div>
            <div class="bg-rose-50 dark:bg-rose-950/20 border border-rose-200/60 dark:border-rose-800/40 rounded-xl p-4">
              <div class="text-[10px] font-semibold uppercase tracking-wider text-rose-600 dark:text-rose-400 mb-2">不利情节</div>
              <div v-for="f in (chatStore.report.factors as any)?.unfavorable" :key="f.item" class="mb-2">
                <div class="font-medium text-xs">{{ f.item }}</div>
                <div class="text-[11px] text-muted-foreground">{{ f.basis }}</div>
              </div>
            </div>
          </div>

          <!-- 量刑预估 -->
          <div class="bg-card border border-border/60 rounded-xl p-4">
            <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">量刑预估</div>
            <div class="flex items-center gap-3 mb-2">
              <span class="text-lg font-bold text-primary">{{ (chatStore.report.sentence_estimate as any)?.range }}</span>
              <span class="text-xs px-2 py-0.5 rounded-full border"
                :class="(chatStore.report.sentence_estimate as any)?.probation_chance === '高'
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-950/20 dark:border-emerald-800/40 dark:text-emerald-400'
                  : 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-950/20 dark:border-amber-800/40 dark:text-amber-400'">
                缓刑可能性：{{ (chatStore.report.sentence_estimate as any)?.probation_chance }}
              </span>
            </div>
            <div class="text-xs text-muted-foreground">{{ (chatStore.report.sentence_estimate as any)?.basis }}</div>
          </div>

          <!-- 辩护建议 -->
          <div class="bg-card border border-border/60 rounded-xl p-4">
            <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">辩护建议</div>
            <div v-for="s in (chatStore.report.defense_suggestions as any[])" :key="s.direction" class="mb-2 flex gap-2">
              <span class="text-[10px] px-1.5 py-0.5 rounded border shrink-0 h-fit"
                :class="s.priority === 'high' ? 'bg-primary/10 border-primary/20 text-primary' : 'bg-muted border-border/60 text-muted-foreground'">
                {{ s.priority === 'high' ? '重要' : '建议' }}
              </span>
              <div>
                <div class="font-medium text-xs">{{ s.direction }}</div>
                <div class="text-[11px] text-muted-foreground">{{ s.basis }}</div>
              </div>
            </div>
          </div>

          <p class="text-[10px] text-muted-foreground/60 text-center">{{ chatStore.report.disclaimer }}</p>
        </div>
        <div class="px-5 py-3 border-t border-border/60 flex justify-end gap-2 shrink-0">
          <Button variant="outline" size="sm" @click="showReport = false">关闭</Button>
        </div>
      </Card>
    </div>
    <!-- Advance Confirm Modal -->
    <div v-if="showAdvanceConfirm" class="fixed inset-0 z-50 bg-foreground/20 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in">
      <Card class="w-full max-w-sm flex flex-col shadow-2xl border-border/60">
        <div class="px-5 py-4 border-b border-border/60 flex items-center gap-3">
          <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
               :class="chatStore.viewStage === 'S1' ? 'bg-amber-500/10 text-amber-500' : 'bg-primary/10 text-primary'">
            <AlertTriangle v-if="chatStore.viewStage === 'S1'" class="w-4 h-4" />
            <Check v-else class="w-4 h-4" />
          </div>
          <h2 class="text-base font-bold text-foreground">
             {{ chatStore.viewStage === 'S1' ? '确认强行提交评估？' : '确认结束情节收集？' }}
          </h2>
        </div>
        <div class="p-5 bg-muted/10 text-sm text-muted-foreground leading-relaxed">
          <template v-if="chatStore.viewStage === 'S1'">
            您正试图手动结束收集。如果案情关键要素缺失，极有可能被评估引擎<strong class="text-rose-500 dark:text-rose-400">打回并要求补充</strong>。建议充分描述后再提交。
          </template>
          <template v-else>
            提前结束情节收集<strong class="text-amber-600 dark:text-amber-500">可能导致系统遗漏对您有利的量刑事实</strong>，并直接影响最终评估报告的准确性，确定要结束收集并生成报告吗？
          </template>
        </div>
        <div class="px-5 py-4 border-t border-border/60 flex justify-end gap-2 shrink-0 bg-muted/5">
          <Button variant="outline" size="sm" @click="showAdvanceConfirm = false">取消，继续补充</Button>
          <Button size="sm" @click="handleAdvance"
                  :class="chatStore.viewStage === 'S1' ? 'bg-amber-500 hover:bg-amber-600 text-white' : ''">
            <Zap class="w-3.5 h-3.5 mr-1 fill-current" /> 确认提交
          </Button>
        </div>
      </Card>
    </div>
  </div>
</template>

<style scoped>
@keyframes s2-bar {
  0%   { width: 0%;   opacity: 1; }
  60%  { width: 85%;  opacity: 1; }
  85%  { width: 92%;  opacity: 1; }
  100% { width: 92%;  opacity: 0.7; }
}
.animate-s2-bar {
  animation: s2-bar 18s ease-out forwards;
}
</style>
