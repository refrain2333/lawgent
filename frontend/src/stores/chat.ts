import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './auth'

export type Stage = 'S1' | 'S2' | 'S3' | 'S4'

const STAGE_MAP: Record<string, Stage> = {
  s1_collecting: 'S1', s1_confirming: 'S1',
  s2_searching:  'S2', s2_failed: 'S2',
  s3_collecting: 'S3', s3_confirming: 'S3',
  s4_generating: 'S4', s4_done: 'S4', s4_failed: 'S4',
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  stage?: string
  streaming?: boolean
}

export interface ConfirmRequest {
  type: 'facts' | 'final'
  summary: string
}

export interface SearchResult {
  case_id: string
  accusations: string
  fact: string
  score: number
}

export interface Facts { [key: string]: string }

export interface ConversationItem {
  id: number
  thread_id: string
  title: string | null
  stage: string
  created_at: string | null
  updated_at: string | null
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref<Message[]>([])
  const stage = ref<Stage>('S1')
  const viewStage = ref<Stage>('S1')
  const dbStage = ref<string>('s1_collecting')
  const facts = ref<Facts>({})
  const searchResults = ref<SearchResult[]>([])
  const report = ref<Record<string, unknown> | null>(null)
  const confirmRequest = ref<ConfirmRequest | null>(null)
  const s1ConfirmedSummary = ref<string | null>(null)
  const s2SearchOutput = ref<any | null>(null)
  const s3ConfirmedFacts = ref<string | null>(null)
  const s3OpenerReady = ref(false)
  const isThinking = ref(false)
  const isS2Waiting = ref(false)
  const isS4Waiting = ref(false)
  const isLoading = ref(false)
  const isFetchingConversations = ref(false)
  const conversationId = ref<string | null>(null)
  const conversations = ref<ConversationItem[]>([])

  let streamingMsgId: string | null = null
  let abortController: AbortController | null = null
  let s2PollTimer: ReturnType<typeof setTimeout> | null = null
  let s4PollToken = 0

  // 打字机队列
  let _tokenQueue = ''
  let _rafId: number | null = null
  let _typewriterMsgId: string | null = null  // 打字机当前目标消息，独立于 streamingMsgId
  const CHARS_PER_FRAME = 4

  function _startTypewriter(msgId: string) {
    _typewriterMsgId = msgId
    if (_rafId !== null) return
    function tick() {
      if (_tokenQueue.length > 0) {
        const chunk = _tokenQueue.slice(0, CHARS_PER_FRAME)
        _tokenQueue = _tokenQueue.slice(CHARS_PER_FRAME)
        const msg = messages.value.find(m => m.id === _typewriterMsgId)
        if (msg) msg.content += chunk
      }
      if (_tokenQueue.length > 0) {
        _rafId = requestAnimationFrame(tick)
      } else {
        _rafId = null
        _typewriterMsgId = null
      }
    }
    _rafId = requestAnimationFrame(tick)
  }

  function _stopTypewriter() {
    if (_rafId !== null) { cancelAnimationFrame(_rafId); _rafId = null }
    _tokenQueue = ''
    _typewriterMsgId = null
  }

  const stageIndex = computed(() => ({ S1: 0, S2: 1, S3: 2, S4: 3 }[stage.value] ?? 0))
  const isConnected = computed(() => conversationId.value !== null)

  function _token() { return useAuthStore().token ?? '' }
  function _apiBase() { return '/api/v1/agent' }

  async function connect(convId?: string) {
    reset()
    if (convId) {
      // 恢复已有会话：查询状态
      const res = await fetch(`${_apiBase()}/sessions/${convId}/state?token=${_token()}`)
      if (!res.ok) return
      const data = await res.json()
      conversationId.value = data.thread_id
      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage] ?? 'S1'
      viewStage.value = stage.value
      // 恢复旧会话时，不再用 if 兜底，而是不管有没有都进行安全覆盖
      s1ConfirmedSummary.value = data.s1_summary || null
      s2SearchOutput.value = data.s2_search || null
      s3ConfirmedFacts.value = data.s3_facts || null
      s3OpenerReady.value = !!data.s3_opener_ready

      // 若 S2 还在检索中，启动轮询
      if (data.stage === 's2_searching') _startS2Poll()
      // 恢复确认卡片
      if (data.stage === 's1_confirming' && data.summary) {
        confirmRequest.value = { type: 'facts', summary: data.summary }
      } else if (data.stage === 's3_confirming' && data.facts) {
        confirmRequest.value = { type: 'final', summary: data.facts }
      }
      // 恢复 S4 报告 / 生成中状态
      if (data.stage === 's4_done') {
        try {
          const reportRes = await fetch(`${_apiBase()}/sessions/${convId}/report?token=${_token()}`)
          if (reportRes.ok) {
            report.value = await reportRes.json()
            isS4Waiting.value = false
          } else {
            isS4Waiting.value = true
            await _pollReport(conversationId.value)
          }
        } catch {
          isS4Waiting.value = true
          await _pollReport(conversationId.value)
        }
      } else if (data.stage === 's4_generating') {
        isS4Waiting.value = true
        await _pollReport(conversationId.value)
      } else {
        isS4Waiting.value = false
      }
    } else {
      // 新建会话
      const res = await fetch(`${_apiBase()}/sessions?token=${_token()}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (!res.ok) return
      const data = await res.json()
      conversationId.value = data.thread_id
      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage] ?? 'S1'
      viewStage.value = stage.value
    }
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
    _stopS2Poll()
    _stopTypewriter()
    s4PollToken++
  }

  function _handleEvent(data: Record<string, unknown>) {
    const type = data.type as string

    if (type === 'token') {
      const token = data.content as string
      if (!streamingMsgId) {
        const msg: Message = { id: crypto.randomUUID(), role: 'assistant', content: '', stage: dbStage.value, streaming: true }
        messages.value.push(msg)
        streamingMsgId = msg.id
      }
      _tokenQueue += token
      _startTypewriter(streamingMsgId)
      isThinking.value = false
    }

    if (type === 'case_ready') {
      const msgId = streamingMsgId
      const summary = data.summary as string
      streamingMsgId = null
      const finish = () => {
        const msg = messages.value.find(m => m.id === msgId)
        if (msg) {
          // 清除气泡中意外推送的信号文字及之后内容
          const sigIdx = msg.content.indexOf('[[CASE_READY]]')
          if (sigIdx !== -1) msg.content = msg.content.slice(0, sigIdx).trimEnd()
          msg.streaming = false
        }
        dbStage.value = 's1_confirming'
        stage.value = 'S1'
        confirmRequest.value = { type: 'facts', summary }
        isThinking.value = false
      }
      if (_tokenQueue.length > 0) {
        const wait = () => _tokenQueue.length === 0 ? finish() : requestAnimationFrame(wait)
        requestAnimationFrame(wait)
      } else {
        finish()
      }
    }

    if (type === 's3_ready') {
      const msgId = streamingMsgId
      const facts = data.facts as string
      streamingMsgId = null
      const finish = () => {
        const msg = messages.value.find(m => m.id === msgId)
        if (msg) {
          const sigIdx = msg.content.indexOf('[[S3_READY]]')
          if (sigIdx !== -1) msg.content = msg.content.slice(0, sigIdx).trimEnd()
          msg.streaming = false
        }
        dbStage.value = 's3_confirming'
        stage.value = 'S3'
        confirmRequest.value = { type: 'final', summary: facts }
        isThinking.value = false
      }
      if (_tokenQueue.length > 0) {
        const wait = () => _tokenQueue.length === 0 ? finish() : requestAnimationFrame(wait)
        requestAnimationFrame(wait)
      } else {
        finish()
      }
    }

    if (type === 'done' || type === 'end') {
      const msgId = streamingMsgId
      streamingMsgId = null
      const finish = () => {
        const msg = messages.value.find(m => m.id === msgId)
        if (msg) msg.streaming = false
        isThinking.value = false
      }
      if (_tokenQueue.length > 0) {
        const wait = () => _tokenQueue.length === 0 ? finish() : requestAnimationFrame(wait)
        requestAnimationFrame(wait)
      } else {
        finish()
      }
    }

    if (type === 'error') {
      isThinking.value = false
      if (streamingMsgId) {
        const msg = messages.value.find(m => m.id === streamingMsgId)
        if (msg) msg.streaming = false
        streamingMsgId = null
      }
      messages.value.push({
        id: crypto.randomUUID(), role: 'assistant',
        content: `系统错误：${data.message}`,
        stage: dbStage.value
      })
    }
  }

  async function _readStream(url: string, body: object) {
    abortController?.abort()
    abortController = new AbortController()
    isThinking.value = true

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortController.signal,
      })
      if (!res.ok || !res.body) { isThinking.value = false; return }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n\n')
        buf = lines.pop() ?? ''
        for (const line of lines) {
          const text = line.replace(/^data: /, '').trim()
          if (!text) continue
          try { _handleEvent(JSON.parse(text)) } catch {}
        }
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name !== 'AbortError') isThinking.value = false
    }
  }

  async function send(text: string) {
    if (!conversationId.value) return
    messages.value.push({ id: crypto.randomUUID(), role: 'user', content: text, stage: dbStage.value })
    await _readStream(
      `${_apiBase()}/sessions/${conversationId.value}/message?token=${_token()}`,
      { content: text },
    )
  }

  // 推进阶段（S1收集完 → AI判断 → S1确认 / S3收集完 → S3确认）
  async function advance() {
    if (!conversationId.value) return
    isThinking.value = true
    const res = await fetch(
      `${_apiBase()}/sessions/${conversationId.value}/advance?token=${_token()}`,
      { method: 'POST' },
    )
    isThinking.value = false
    if (!res.ok) return
    const data = await res.json()
    dbStage.value = data.stage
    stage.value = STAGE_MAP[data.stage] ?? stage.value

    if (!data.sufficient) {
      // 信息不足，AI 告知用户，后端已存入新消息，重新拉取以保持一致
      await fetchMessages(conversationId.value)
      return
    }

    // 信息足够，显示确认卡片
    confirmRequest.value = {
      type: data.stage.startsWith('s3') ? 'final' : 'facts',
      summary: data.summary ?? '',
    }
  }

  // 确认卡点
  async function confirm(accepted: boolean) {
    if (!conversationId.value) return
    const summaryToSave = confirmRequest.value?.summary
    confirmRequest.value = null

    const res = await fetch(
      `${_apiBase()}/sessions/${conversationId.value}/confirm?token=${_token()}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accepted }),
      },
    )
    if (!res.ok) return
    const data = await res.json()
    dbStage.value = data.stage
    stage.value = STAGE_MAP[data.stage] ?? stage.value

    if (!accepted) return

    // 如果确的是 S1 案情，将其保存供页面常驻显示
    if (data.stage === 's2_searching' && summaryToSave) {
      s1ConfirmedSummary.value = summaryToSave

      // S1确认后，后台可能已经异步生成了新的会话标题，通知左侧列表刷新以体现标题变更
      setTimeout(() => {
         fetchConversations()
      }, 5000)

      // 确认后，自动把前端视图切换到 S2
      viewStage.value = 'S2'
      isS2Waiting.value = true
      _startS2Poll()
    }
    // S3确认 → S4报告生成中
    else if (data.stage === 's4_generating') {
      s3ConfirmedFacts.value = summaryToSave || null
      // 确认后，自动把前端视图切换到 S4
      viewStage.value = 'S4'
      isS4Waiting.value = true
      await _pollReport(conversationId.value)
    }
  }

  // 轮询 S2 是否完成（推进到 s3_collecting）
  function _startS2Poll() {
    _stopS2Poll()
    s2PollTimer = setInterval(async () => {
      const currentThreadId = conversationId.value
      if (!currentThreadId) return
      try {
        const res = await fetch(`${_apiBase()}/sessions/${currentThreadId}/state?token=${_token()}`)
        if (!res.ok) return
        const data = await res.json()

        // 检索结果一旦可用，立即展示；清单/开场白继续后台运行
        if (data.s2_search) {
          s2SearchOutput.value = data.s2_search
        }
        s3OpenerReady.value = !!data.s3_opener_ready

        if (data.stage !== 's2_searching') {
          dbStage.value = data.stage
          stage.value = STAGE_MAP[data.stage] ?? stage.value
          isS2Waiting.value = false

          // 已进入 S3 但开场白尚未落库：继续轮询 state，直到 opener ready
          if (data.stage === 's3_collecting' && !data.s3_opener_ready) {
            return
          }

          _stopS2Poll()

          // 状态变更，检查是否进入 S3 阶段
          if ((data.stage === 's3_collecting' || data.stage === 's3_confirming') && data.s3_opener_ready) {
            // 预拉取 S3 消息（含开场白），用户点击按钮进入 S3 时直接可见
            if (conversationId.value === currentThreadId) {
              await fetchMessages(currentThreadId)
            }
          }
          if (data.stage === 's2_failed') {
            messages.value.push({
              id: crypto.randomUUID(), role: 'assistant',
              content: '检索分析失败，请重新确认案情或稍后再试。',
            })
          }
        }
      } catch {}
    }, 3000)
  }

  function _stopS2Poll() {
    if (s2PollTimer) { clearInterval(s2PollTimer); s2PollTimer = null }
  }

  // 轮询 S4 报告
  async function _pollReport(threadId: string) {
    const pollToken = ++s4PollToken
    const maxTries = 20
    for (let i = 0; i < maxTries; i++) {
      if (pollToken !== s4PollToken || conversationId.value !== threadId) return
      await new Promise(r => setTimeout(r, 3000))
      if (pollToken !== s4PollToken || conversationId.value !== threadId) return
      try {
        const res = await fetch(`${_apiBase()}/sessions/${threadId}/report?token=${_token()}`)
        if (pollToken !== s4PollToken || conversationId.value !== threadId) return
        if (res.ok) {
          report.value = await res.json()
          isS4Waiting.value = false
          dbStage.value = 's4_done'
          stage.value = 'S4'
          return
        }

        // 报告尚未就绪时，查询阶段判断是否失败或仍在生成
        const stateRes = await fetch(`${_apiBase()}/sessions/${threadId}/state?token=${_token()}`)
        if (pollToken !== s4PollToken || conversationId.value !== threadId) return
        if (stateRes.ok) {
          const stateData = await stateRes.json()
          dbStage.value = stateData.stage
          stage.value = STAGE_MAP[stateData.stage] ?? stage.value

          if (stateData.stage === 's4_failed') {
            isS4Waiting.value = false
            messages.value.push({
              id: crypto.randomUUID(), role: 'assistant',
              content: '报告生成失败，请稍后再试。',
            })
            return
          }

          if (stateData.stage === 's4_generating' || stateData.stage === 's4_done') {
            isS4Waiting.value = true
          }
        }
      } catch {}
    }

    // 超出轮询次数后，仍保留“生成中”提示，等待用户后续切回自动恢复
    if (pollToken === s4PollToken && conversationId.value === threadId) {
      isS4Waiting.value = true
    }
  }

  async function deleteConversation(threadId: string) {
    const auth = useAuthStore()
    if (!auth.token) return false
    try {
      const res = await fetch(`${_apiBase()}/conversations/${threadId}?token=${auth.token}`, {
        method: 'DELETE',
      })
      if (!res.ok) return false
      conversations.value = conversations.value.filter(c => c.thread_id !== threadId)
      // 若删除的是当前会话，重置状态
      if (conversationId.value === threadId) {
        disconnect()
        reset()
      }
      return true
    } catch { return false }
  }

  async function syncState(threadId?: string) {
    const targetThreadId = threadId ?? conversationId.value
    if (!targetThreadId) return null

    try {
      const res = await fetch(`${_apiBase()}/sessions/${targetThreadId}/state?token=${_token()}`)
      if (!res.ok) return null
      const data = await res.json()
      if (conversationId.value !== targetThreadId) return data

      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage] ?? stage.value
      s1ConfirmedSummary.value = data.s1_summary || null
      s2SearchOutput.value = data.s2_search || null
      s3ConfirmedFacts.value = data.s3_facts || null
      s3OpenerReady.value = !!data.s3_opener_ready

      if (data.stage === 's1_confirming' && data.summary) {
        confirmRequest.value = { type: 'facts', summary: data.summary }
      } else if (data.stage === 's3_confirming' && data.facts) {
        confirmRequest.value = { type: 'final', summary: data.facts }
      }

      return data
    } catch {
      return null
    }
  }

  async function fetchConversations() {
    const auth = useAuthStore()
    if (!auth.token) return
    isFetchingConversations.value = true
    try {
      const res = await fetch(`${_apiBase()}/conversations?token=${auth.token}`)
      if (res.ok) {
        conversations.value = await res.json()
      }
    } catch {}
    finally {
      isFetchingConversations.value = false
    }
  }

  async function fetchMessages(threadId: string) {
    const auth = useAuthStore()
    if (!auth.token) return
    isLoading.value = true
    try {
      const res = await fetch(`${_apiBase()}/conversations/${threadId}/messages?token=${auth.token}`)
      const data: { role: string; content: string; stage?: string }[] = await res.json()
      messages.value = data.map(m => ({
        id: crypto.randomUUID(),
        role: m.role as 'user' | 'assistant',
        content: m.content,
        stage: m.stage,
      }))
    } catch {}
    finally { isLoading.value = false }
  }

  function reset() {
    messages.value = []
    stage.value = 'S1'
    dbStage.value = 's1_collecting'
    facts.value = {}
    searchResults.value = []
    report.value = null
    confirmRequest.value = null
    s1ConfirmedSummary.value = null
    s2SearchOutput.value = null
    s3ConfirmedFacts.value = null
    s3OpenerReady.value = false
    isThinking.value = false
    isS2Waiting.value = false
    isS4Waiting.value = false
    streamingMsgId = null
    conversationId.value = null
    _stopS2Poll()
    _stopTypewriter()
  }

  return {
    messages, stage, viewStage, dbStage, stageIndex, facts, searchResults, report,
    confirmRequest, s1ConfirmedSummary, s2SearchOutput, s3ConfirmedFacts, s3OpenerReady, isConnected, isThinking, isS2Waiting, isS4Waiting, isLoading, isFetchingConversations, conversationId, conversations,
    connect, send, advance, confirm, disconnect, reset, syncState, fetchConversations, fetchMessages, deleteConversation,
  }
})
