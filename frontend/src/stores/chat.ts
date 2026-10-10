import { apiUrl } from '@/lib/api'
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useAuthStore } from './auth'

export type Stage = 'S1' | 'S2' | 'S3' | 'S4'

export const STAGE_MAP: Record<string, Stage> = {
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
  const isConfirming = ref(false)
  const requestError = ref<string | null>(null)
  const conversationId = ref<string | null>(null)
  const conversations = ref<ConversationItem[]>([])

  let streamingMsgId: string | null = null
  let abortController: AbortController | null = null
  let s2PollTimer: ReturnType<typeof setTimeout> | null = null
  let s4PollToken = 0
  let sessionVersion = 0
  let stateVersion = 0
  let historyRequest = 0
  let conversationsRequest = 0
  let s2PollToken = 0

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

  function _finishStreaming() {
    const msg = messages.value.find(m => m.id === (_typewriterMsgId ?? streamingMsgId))
    if (msg) {
      msg.content += _tokenQueue
      msg.streaming = false
    }
    _stopTypewriter()
    streamingMsgId = null
    isThinking.value = false
  }

  function _isCurrent(threadId: string, version: number) {
    return version === sessionVersion && conversationId.value === threadId
  }

  async function _responseError(res: Response): Promise<string> {
    if (res.status === 401) {
      useAuthStore().logout()
      return '登录已失效，请重新登录。'
    }
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') return body.detail
    } catch {}
    return `请求失败（${res.status}），请稍后重试。`
  }

  const stageIndex = computed(() => ({ S1: 0, S2: 1, S3: 2, S4: 3 }[stage.value] ?? 0))
  const isConnected = computed(() => conversationId.value !== null)

  function _token() { return useAuthStore().token ?? '' }
  function _apiBase() { return apiUrl('/agent') }
  function _authHeaders(): Record<string, string> {
    const t = _token()
    return t ? { Authorization: `Bearer ${t}` } : {}
  }

  async function connect(convId?: string): Promise<boolean> {
    reset()
    const version = sessionVersion
    const token = _token()
    requestError.value = null
    isLoading.value = true
    try {
      const res = convId
        ? await fetch(`${_apiBase()}/sessions/${convId}/state`, { headers: _authHeaders() })
        : await fetch(`${_apiBase()}/sessions`, {
          method: 'POST', headers: { 'Content-Type': 'application/json', ..._authHeaders() },
          body: JSON.stringify({}),
        })
      if (version !== sessionVersion || token !== _token()) return false
      if (!res.ok) {
        const error = await _responseError(res)
        if (version === sessionVersion && token === _token()) requestError.value = error
        return false
      }
      const data = await res.json()
      if (version !== sessionVersion || token !== _token()) return false
      conversationId.value = data.thread_id
      _applyState(data)
      viewStage.value = stage.value
      if (data.stage === 's2_searching' || (data.stage === 's3_collecting' && !data.s3_opener_ready)) {
        _startS2Poll()
      }
      if (data.stage === 's4_done' || data.stage === 's4_generating') {
        isS4Waiting.value = true
        void _pollReport(data.thread_id)
      }
      return true
    } catch {
      if (version === sessionVersion) requestError.value = '连接失败，请检查网络后重试。'
      return false
    } finally {
      if (version === sessionVersion) isLoading.value = false
    }
  }

  function disconnect() {
    sessionVersion++
    stateVersion++
    historyRequest++
    abortController?.abort()
    abortController = null
    _stopS2Poll()
    _finishStreaming()
    s4PollToken++
    isConfirming.value = false
    isLoading.value = false
  }

  function _applyState(data: any) {
    dbStage.value = data.stage
    stage.value = STAGE_MAP[data.stage] ?? 'S1'
    s1ConfirmedSummary.value = data.s1_summary || null
    s2SearchOutput.value = data.s2_search || null
    s3ConfirmedFacts.value = data.s3_facts || null
    s3OpenerReady.value = !!data.s3_opener_ready
    confirmRequest.value = data.stage === 's1_confirming' && data.summary
      ? { type: 'facts', summary: data.summary }
      : data.stage === 's3_confirming' && data.facts
        ? { type: 'final', summary: data.facts }
        : null
  }

  function _handleEvent(data: Record<string, unknown>) {
    const type = data.type
    if (type === 'token' && typeof data.content === 'string') {
      if (!streamingMsgId) {
        const msg: Message = { id: crypto.randomUUID(), role: 'assistant', content: '', stage: dbStage.value, streaming: true }
        messages.value.push(msg)
        streamingMsgId = msg.id
      }
      _tokenQueue += data.content
      _startTypewriter(streamingMsgId)
    } else if (type === 'stage_changed' && typeof data.stage === 'string' && STAGE_MAP[data.stage]) {
      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage]
      confirmRequest.value = null
    } else if (type === 'case_ready' && typeof data.summary === 'string') {
      _finishStreaming()
      dbStage.value = 's1_confirming'
      stage.value = 'S1'
      confirmRequest.value = { type: 'facts', summary: data.summary }
    } else if (type === 's3_ready' && typeof data.facts === 'string') {
      _finishStreaming()
      dbStage.value = 's3_confirming'
      stage.value = 'S3'
      confirmRequest.value = { type: 'final', summary: data.facts }
    } else if (type === 'done' || type === 'end') {
      _finishStreaming()
    } else if (type === 'error') {
      _finishStreaming()
      requestError.value = typeof data.message === 'string' ? data.message : '响应生成失败，请稍后重试。'
    }
  }

  async function _readStream(url: string, body: object): Promise<boolean> {
    const threadId = conversationId.value
    if (!threadId) return false
    const version = sessionVersion
    const controller = new AbortController()
    abortController?.abort()
    abortController = controller
    const isCurrentStream = () => _isCurrent(threadId, version) && abortController === controller
    isThinking.value = true
    requestError.value = null
    let accepted = false
    let completed = false
    try {
      const res = await fetch(url, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ..._authHeaders() },
        body: JSON.stringify(body), signal: controller.signal,
      })
      if (!isCurrentStream()) return false
      if (!res.ok || !res.body) {
        const error = await _responseError(res)
        if (isCurrentStream()) requestError.value = error
        return false
      }
      accepted = true
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      const processEvent = (block: string) => {
        const payload = block.split(/\r?\n/)
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).trimStart()).join('\n')
        if (!payload || !isCurrentStream()) return
        try {
          const data = JSON.parse(payload)
          if (['end', 'done', 'error', 'case_ready', 's3_ready'].includes(data.type)) completed = true
          _handleEvent(data)
        } catch {}
      }
      while (isCurrentStream()) {
        const { done, value } = await reader.read()
        if (!isCurrentStream()) return accepted
        if (done) {
          buf += decoder.decode()
          if (buf.trim()) processEvent(buf)
          break
        }
        buf += decoder.decode(value, { stream: true })
        const events = buf.split(/\r?\n\r?\n/)
        buf = events.pop() ?? ''
        for (const event of events) processEvent(event)
      }
      if (isCurrentStream() && !completed) {
        requestError.value = '响应连接已中断，已保留收到的内容；请刷新会话后再试。'
      }
    } catch (e: unknown) {
      if (isCurrentStream() && !(e instanceof Error && e.name === 'AbortError')) {
        requestError.value = '请求中断，请检查网络后重试。'
      }
    } finally {
      if (isCurrentStream()) {
        _finishStreaming()
        abortController = null
      }
    }
    return accepted
  }

  async function send(text: string) {
    const threadId = conversationId.value
    if (!threadId || isThinking.value || isConfirming.value || isLoading.value || !text.trim()) return false
    stateVersion++
    historyRequest++
    _stopS2Poll()
    const version = sessionVersion
    const msg: Message = { id: crypto.randomUUID(), role: 'user', content: text, stage: dbStage.value }
    messages.value.push(msg)
    const accepted = await _readStream(`${_apiBase()}/sessions/${threadId}/message`, { content: text })
    if (!accepted && _isCurrent(threadId, version)) {
      messages.value = messages.value.filter(m => m.id !== msg.id)
    }
    return accepted
  }

  async function advance() {
    const threadId = conversationId.value
    if (!threadId || isThinking.value || isConfirming.value || isLoading.value) return
    stateVersion++
    historyRequest++
    _stopS2Poll()
    const version = sessionVersion
    isThinking.value = true
    requestError.value = null
    try {
      const res = await fetch(`${_apiBase()}/sessions/${threadId}/advance`, {
        method: 'POST', headers: _authHeaders(),
      })
      if (!_isCurrent(threadId, version)) return
      if (!res.ok) {
        const error = await _responseError(res)
        if (_isCurrent(threadId, version)) requestError.value = error
        return
      }
      const data = await res.json()
      if (!_isCurrent(threadId, version)) return
      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage] ?? stage.value
      if (!data.sufficient) {
        await fetchMessages(threadId)
        return
      }
      confirmRequest.value = { type: data.stage.startsWith('s3') ? 'final' : 'facts', summary: data.summary ?? '' }
    } catch {
      if (_isCurrent(threadId, version)) requestError.value = '提交失败，请检查网络后重试。'
    } finally {
      if (_isCurrent(threadId, version)) isThinking.value = false
    }
  }

  async function confirm(accepted: boolean) {
    const threadId = conversationId.value
    if (!threadId || isConfirming.value || isThinking.value || isLoading.value) return
    stateVersion++
    historyRequest++
    _stopS2Poll()
    const version = sessionVersion
    const summaryToSave = confirmRequest.value?.summary
    isConfirming.value = true
    requestError.value = null
    try {
      const res = await fetch(`${_apiBase()}/sessions/${threadId}/confirm`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ..._authHeaders() },
        body: JSON.stringify({ accepted }),
      })
      if (!_isCurrent(threadId, version)) return
      if (!res.ok) {
        const error = await _responseError(res)
        if (_isCurrent(threadId, version)) requestError.value = error
        return
      }
      const data = await res.json()
      if (!_isCurrent(threadId, version)) return
      confirmRequest.value = null
      dbStage.value = data.stage
      stage.value = STAGE_MAP[data.stage] ?? stage.value
      if (!accepted) return
      if (data.stage === 's2_searching') {
        if (summaryToSave) s1ConfirmedSummary.value = summaryToSave
        setTimeout(() => {
          if (_isCurrent(threadId, version)) void fetchConversations()
        }, 5000)
        viewStage.value = 'S2'
        _startS2Poll()
      } else if (data.stage === 's4_generating') {
        if (summaryToSave) s3ConfirmedFacts.value = summaryToSave
        viewStage.value = 'S4'
        isS4Waiting.value = true
        void _pollReport(threadId)
      }
    } catch {
      if (_isCurrent(threadId, version)) requestError.value = '确认失败，请检查网络后重试。'
    } finally {
      if (_isCurrent(threadId, version)) isConfirming.value = false
    }
  }

  async function retry() {
    if (dbStage.value === 's2_failed' || dbStage.value === 's4_failed') await confirm(true)
  }

  // 轮询 S2 是否完成（推进到 s3_collecting）
  function _startS2Poll() {
    _stopS2Poll()
    const threadId = conversationId.value
    if (!threadId) return
    const version = sessionVersion
    const pollToken = s2PollToken
    let tries = 0
    isS2Waiting.value = dbStage.value === 's2_searching'
    const isCurrentPoll = () => _isCurrent(threadId, version) && pollToken === s2PollToken
    const poll = async () => {
      if (!isCurrentPoll()) return
      tries++
      try {
        const res = await fetch(`${_apiBase()}/sessions/${threadId}/state`, { headers: _authHeaders() })
        if (!isCurrentPoll()) return
        if (res.status === 401) { await _responseError(res); return }
        if (res.ok) {
          const data = await res.json()
          if (!isCurrentPoll()) return
          _applyState(data)
          isS2Waiting.value = data.stage === 's2_searching'
          if (data.stage !== 's2_searching' && !(data.stage === 's3_collecting' && !data.s3_opener_ready)) {
            _stopS2Poll()
            if ((data.stage === 's3_collecting' || data.stage === 's3_confirming') && data.s3_opener_ready) {
              await fetchMessages(threadId)
            } else if (data.stage === 's2_failed') {
              requestError.value = '检索分析失败，可点击重新检索。'
            }
            return
          }
        }
      } catch {}
      if (isCurrentPoll() && tries >= 40) {
        _stopS2Poll()
        isS2Waiting.value = false
        requestError.value = dbStage.value === 's3_collecting'
          ? '检索已完成，可进入情节收集继续咨询。'
          : '检索暂未完成，可刷新状态继续等待。'
        return
      }
      if (isCurrentPoll()) s2PollTimer = setTimeout(poll, 3000)
    }
    s2PollTimer = setTimeout(poll, 3000)
  }

  function _stopS2Poll() {
    s2PollToken++
    if (s2PollTimer) { clearTimeout(s2PollTimer); s2PollTimer = null }
  }

  // 有限轮询；超时后允许用户刷新状态，避免停在没有活动请求的 spinner。
  async function _pollReport(threadId: string) {
    const pollToken = ++s4PollToken
    const version = sessionVersion
    const isCurrentPoll = () => pollToken === s4PollToken && _isCurrent(threadId, version)
    for (let i = 0; i < 20; i++) {
      if (!isCurrentPoll()) return
      if (i > 0) await new Promise(r => setTimeout(r, 3000))
      if (!isCurrentPoll()) return
      try {
        const res = await fetch(`${_apiBase()}/sessions/${threadId}/report`, { headers: _authHeaders() })
        if (!isCurrentPoll()) return
        if (res.status === 401) { await _responseError(res); return }
        if (res.ok) {
          const data = await res.json()
          if (!isCurrentPoll()) return
          report.value = data
          dbStage.value = 's4_done'
          stage.value = 'S4'
          isS4Waiting.value = false
          return
        }
        const stateRes = await fetch(`${_apiBase()}/sessions/${threadId}/state`, { headers: _authHeaders() })
        if (!isCurrentPoll()) return
        if (stateRes.status === 401) { await _responseError(stateRes); return }
        if (stateRes.ok) {
          const data = await stateRes.json()
          if (!isCurrentPoll()) return
          _applyState(data)
          if (data.stage === 's4_failed') {
            isS4Waiting.value = false
            requestError.value = '报告生成失败，可点击重新生成。'
            return
          }
        }
      } catch {}
    }
    if (isCurrentPoll()) {
      isS4Waiting.value = false
      requestError.value = '报告暂未就绪，可刷新状态继续等待。'
    }
  }

  async function refreshState() {
    const threadId = conversationId.value
    if (!threadId) return
    requestError.value = null
    const data = await syncState(threadId)
    if (conversationId.value !== threadId || !data) return
    if (data.stage === 's2_searching' || (data.stage === 's3_collecting' && !data.s3_opener_ready)) _startS2Poll()
    if (data.stage === 's4_generating' || data.stage === 's4_done') {
      isS4Waiting.value = true
      void _pollReport(threadId)
    }
    await fetchMessages(threadId)
  }

  async function deleteConversation(threadId: string) {
    const auth = useAuthStore()
    if (!auth.token) return false
    const token = auth.token
    const version = sessionVersion
    try {
      const res = await fetch(`${_apiBase()}/conversations/${threadId}`, {
        method: 'DELETE',
        headers: _authHeaders(),
      })
      if (auth.token !== token) return false
      if (!res.ok) {
        const error = await _responseError(res)
        if (auth.token === token && sessionVersion === version) requestError.value = error
        return false
      }
      conversations.value = conversations.value.filter(c => c.thread_id !== threadId)
      // 若删除的是当前会话，重置状态
      if (conversationId.value === threadId) {
        disconnect()
        reset()
      }
      return true
    } catch {
      if (auth.token === token && sessionVersion === version) requestError.value = '删除失败，请检查网络后重试。'
      return false
    }
  }

  async function syncState(threadId?: string) {
    const targetThreadId = threadId ?? conversationId.value
    if (!targetThreadId) return null
    const version = sessionVersion
    const currentStateVersion = stateVersion
    const isCurrentState = () => _isCurrent(targetThreadId, version) && currentStateVersion === stateVersion
    try {
      const res = await fetch(`${_apiBase()}/sessions/${targetThreadId}/state`, { headers: _authHeaders() })
      if (!isCurrentState()) return null
      if (!res.ok) {
        const error = await _responseError(res)
        if (isCurrentState()) requestError.value = error
        return null
      }
      const data = await res.json()
      if (!isCurrentState()) return null
      _applyState(data)
      return data
    } catch {
      if (isCurrentState()) requestError.value = '状态同步失败，请稍后重试。'
      return null
    }
  }

  async function fetchConversations() {
    const token = _token()
    if (!token) return
    const requestId = ++conversationsRequest
    isFetchingConversations.value = true
    try {
      const res = await fetch(`${_apiBase()}/conversations`, { headers: _authHeaders() })
      if (requestId !== conversationsRequest || token !== _token()) return
      if (!res.ok) {
        const error = await _responseError(res)
        if (requestId === conversationsRequest && token === _token()) requestError.value = error
        return
      }
      const data = await res.json()
      if (requestId === conversationsRequest && token === _token() && Array.isArray(data)) conversations.value = data
    } catch {
      if (requestId === conversationsRequest && token === _token()) requestError.value = '会话列表加载失败，请重试。'
    } finally {
      if (requestId === conversationsRequest) isFetchingConversations.value = false
    }
  }

  async function fetchMessages(threadId: string) {
    if (!_token() || conversationId.value !== threadId) return
    const version = sessionVersion
    const requestId = ++historyRequest
    const isCurrentRequest = () => _isCurrent(threadId, version) && requestId === historyRequest
    isLoading.value = true
    try {
      const res = await fetch(`${_apiBase()}/conversations/${threadId}/messages`, { headers: _authHeaders() })
      if (!isCurrentRequest()) return
      if (!res.ok) {
        const error = await _responseError(res)
        if (isCurrentRequest()) requestError.value = error
        return
      }
      const data: { role: string; content: string; stage?: string }[] = await res.json()
      if (!isCurrentRequest() || !Array.isArray(data)) return
      messages.value = data.map(m => ({
        id: crypto.randomUUID(), role: m.role as 'user' | 'assistant', content: m.content, stage: m.stage,
      }))
    } catch {
      if (isCurrentRequest()) requestError.value = '消息加载失败，请重试。'
    } finally {
      if (isCurrentRequest()) isLoading.value = false
    }
  }

  function reset(clearConversations = false) {
    disconnect()
    messages.value = []
    stage.value = 'S1'
    viewStage.value = 'S1'
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
    requestError.value = null
    conversationId.value = null
    if (clearConversations) {
      conversationsRequest++
      conversations.value = []
      isFetchingConversations.value = false
    }
  }

  return {
    messages, stage, viewStage, dbStage, stageIndex, facts, searchResults, report,
    confirmRequest, s1ConfirmedSummary, s2SearchOutput, s3ConfirmedFacts, s3OpenerReady, isConnected, isThinking, isS2Waiting, isS4Waiting, isLoading, isFetchingConversations, isConfirming, requestError, conversationId, conversations,
    connect, send, advance, confirm, retry, refreshState, disconnect, reset, syncState, fetchConversations, fetchMessages, deleteConversation,
  }
})
