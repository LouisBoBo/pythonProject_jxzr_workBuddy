import axios from 'axios'
import { authHeaders, clearSession } from './auth.js'
import { getPageContext } from './embed.js'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

api.interceptors.request.use((config) => {
  const headers = authHeaders()
  config.headers = { ...config.headers, ...headers }
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err?.response?.status === 401 && !String(err?.config?.url || '').includes('/auth/login')) {
      clearSession()
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
      }
    }
    return Promise.reject(err)
  }
)

export function login({ username, password, enterprise_code = '' }) {
  return api.post('/auth/login', { username, password, enterprise_code })
}

export function fetchMe() {
  return api.get('/auth/me')
}

export function sendMessage(message, threadId = 'default', filePaths = [], pageContext = null) {
  const body = { message, thread_id: threadId, file_paths: filePaths || [] }
  if (pageContext && Object.keys(pageContext).length) {
    body.page_context = pageContext
  }
  return api.post('/chat', body)
}

/**
 * 流式对话。
 * onEvent(data) 可 async；status / step 每条后让出一帧，保证处理过程逐步上屏。
 *
 * 一律走同源 `/api`（开发态由 Vite 代理到 :8765，已关缓冲），
 * 避免直连 :8765 时 localhost/127.0.0.1 Origin 不一致导致 CORS 静默失败。
 */
function streamEndpoint() {
  return '/api/chat/stream'
}

function paintFrame() {
  return new Promise((resolve) => {
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => resolve())
    } else {
      setTimeout(resolve, 16)
    }
  })
}

export function streamMessage(
  message,
  threadId,
  onEvent,
  onDone,
  onError,
  filePaths = [],
  extraPageContext = null,
  signal = null,
) {
  const handleEvent = typeof onEvent === 'function' ? onEvent : async () => {}
  const pageContext = {
    ...(getPageContext() || {}),
    ...(extraPageContext && typeof extraPageContext === 'object' ? extraPageContext : {}),
  }
  const body = { message, thread_id: threadId, file_paths: filePaths }
  if (Object.keys(pageContext).length) {
    body.page_context = pageContext
  }

  return fetch(streamEndpoint(), {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
    signal: signal || undefined,
  }).then(async (response) => {
    if (response.status === 401) {
      clearSession()
      if (typeof window !== 'undefined') {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
      }
      throw new Error('登录已过期，请重新登录')
    }
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(text || `HTTP ${response.status}`)
    }
    if (!response.body) {
      throw new Error('响应不支持流式读取')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        if (signal?.aborted) {
          try {
            await reader.cancel()
          } catch {
            /* ignore */
          }
          break
        }
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          const lines = part.split('\n')
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))
              const type = data.type || (
                data.done ? 'done'
                  : data.error ? 'error'
                    : data.token != null ? 'token'
                      : null
              )

              if (type === 'done' || data.done) {
                await handleEvent({ ...data, type: 'done' })
                if (typeof onDone === 'function') await onDone(data.thread_id)
              } else if (type === 'error' || data.error) {
                const msg =
                  data.message ||
                  data.error ||
                  data.text ||
                  (typeof data.error === 'string' ? data.error : '') ||
                  '未知错误'
                await handleEvent({ ...data, type: 'error', message: msg })
                if (typeof onError === 'function') await onError(msg)
              } else if (type === 'token' || data.token != null) {
                const text = data.text != null ? data.text : data.token
                await handleEvent({ type: 'token', text, token: text })
              } else if (type === 'status' || type === 'step' || type === 'confirm') {
                await handleEvent(data)
                await paintFrame()
                if (type === 'step' || type === 'confirm') {
                  await new Promise((r) => setTimeout(r, 40))
                }
              } else {
                await handleEvent(data)
              }
            } catch (e) {
              // ignore parse errors
            }
          }
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError' || signal?.aborted) {
        return { aborted: true }
      }
      throw err
    }
    if (signal?.aborted) return { aborted: true }
    return { aborted: false }
  }).catch((err) => {
    if (err?.name === 'AbortError' || signal?.aborted) {
      return { aborted: true }
    }
    if (typeof onError === 'function') {
      const msg =
        typeof err === 'string'
          ? err
          : (err?.message || String(err) || '网络请求失败')
      // 浏览器直连 API 失败时常见 Failed to fetch
      if (/failed to fetch|networkerror|load failed/i.test(msg)) {
        return onError(
          `${msg}（连不上 API，请确认已启动 ./scripts/dev.sh）`
        )
      }
      return onError(msg)
    }
    throw err
  })
}

export function uploadFile(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export function getHistoryList() {
  return api.get('/history')
}

export function getHistoryDetail(id) {
  return api.get(`/history/${id}`)
}

export function saveHistory(threadId, messages, title) {
  return api.post('/history/save', { thread_id: threadId, messages, title })
}

export function deleteHistory(threadId) {
  return api.delete(`/history/${threadId}`)
}

export function convertDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return api.post('/convert', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000,
  })
}

export function confirmWrite(actionId) {
  return api.post(`/writes/actions/${encodeURIComponent(actionId)}/confirm`)
}

export function cancelWrite(actionId) {
  return api.post(`/writes/actions/${encodeURIComponent(actionId)}/cancel`)
}

export function fetchPendingWrites(threadId) {
  return api.get('/writes/pending', {
    params: threadId ? { thread_id: threadId } : undefined,
  })
}

export function fetchWriteAudit({ threadId, tool, limit = 50 } = {}) {
  return api.get('/writes/audit', {
    params: {
      thread_id: threadId || undefined,
      tool: tool || undefined,
      limit,
    },
  })
}

/** M1：本地代码载体（IDE Bridge）在线状态 */
export function fetchIdeBridgeStatus() {
  return api.get('/ide/bridge/status')
}

/** 网页签发 VS Code 配对码 */
export function createIdeBridgePairing() {
  return api.post('/ide/bridge/pairing/create')
}

/** Cursor 研发写码旁路：可用性 */
export function fetchCursorDevStatus() {
  return api.get('/cursor-dev/status')
}

/** Cursor 研发写码旁路：白名单仓库 */
export function fetchCursorDevRepos() {
  return api.get('/cursor-dev/repos')
}

/** 现场读取仓库结构摘要（已有项目衔接，不落库） */
export function fetchCursorDevRepoInspect(repo, ref = '') {
  return api.get('/cursor-dev/repos/inspect', { params: { repo, ref: ref || undefined } })
}

/** 创建写码会话 job（落盘，D4；执行在 D5） */
export function createCursorDevJob(body) {
  return api.post('/cursor-dev/jobs', body)
}

/** 查询写码 job */
export function getCursorDevJob(jobId) {
  return api.get(`/cursor-dev/jobs/${encodeURIComponent(jobId)}`)
}

/** 取消写码任务 */
export function cancelCursorDevJob(jobId, reason = '用户取消') {
  return api.post(`/cursor-dev/jobs/${encodeURIComponent(jobId)}/cancel`, { reason })
}

/** 续聊：入队后需再调 streamCursorDevJob */
export function followupCursorDevJob(jobId, body) {
  return api.post(`/cursor-dev/jobs/${encodeURIComponent(jobId)}/messages`, body)
}

/** 写码审计列表 */
export function fetchCursorDevAudit(params = {}) {
  return api.get('/cursor-dev/audit', { params })
}

/** 项目画像：列表 / 最近一次 */
export function fetchCursorDevProfiles(limit = 20) {
  return api.get('/cursor-dev/profiles', { params: { limit } })
}

export function fetchCursorDevLastProfile() {
  return api.get('/cursor-dev/profiles/last')
}

export function upsertCursorDevProfile(body) {
  return api.put('/cursor-dev/profiles', body)
}

/**
 * 订阅写码 job SSE（仅 Cursor Cloud 旁路，不经过 Deep Agents）。
 * 事件：status|step|token|pr|done|error|review_hint
 */
export function streamCursorDevJob(jobId, onEvent, onDone, onError, signal = null) {
  const handleEvent = typeof onEvent === 'function' ? onEvent : async () => {}
  const url = `/api/cursor-dev/jobs/${encodeURIComponent(jobId)}/stream`

  return fetch(url, {
    method: 'GET',
    headers: authHeaders(),
    signal: signal || undefined,
  }).then(async (response) => {
    if (response.status === 401) {
      clearSession()
      if (typeof window !== 'undefined') {
        window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
      }
      throw new Error('登录已过期，请重新登录')
    }
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      let detail = text
      try {
        const j = JSON.parse(text)
        detail = j.detail || text
      } catch {
        /* keep text */
      }
      throw new Error(detail || `HTTP ${response.status}`)
    }
    if (!response.body) {
      throw new Error('响应不支持流式读取')
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let sawTerminal = false

    try {
      while (true) {
        if (signal?.aborted) {
          try {
            await reader.cancel()
          } catch {
            /* ignore */
          }
          break
        }
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          const lines = part.split('\n')
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const data = JSON.parse(line.slice(6))
              const type = data.type || null

              if (type === 'done') {
                sawTerminal = true
                await handleEvent({ ...data, type: 'done' })
                if (typeof onDone === 'function') await onDone(data)
              } else if (type === 'error') {
                sawTerminal = true
                const msg = data.message || data.error || data.text || '未知错误'
                await handleEvent({ ...data, type: 'error', message: msg })
                if (typeof onError === 'function') await onError(msg)
              } else if (type === 'token') {
                const text = data.text != null ? data.text : data.token
                await handleEvent({ type: 'token', text, token: text })
                await paintFrame()
              } else if (type === 'pr') {
                await handleEvent(data)
                await paintFrame()
              } else if (type === 'review_hint') {
                await handleEvent(data)
                await paintFrame()
              } else if (type === 'status' || type === 'step') {
                await handleEvent(data)
                await paintFrame()
                if (type === 'step') {
                  await new Promise((r) => setTimeout(r, 40))
                }
              } else {
                await handleEvent(data)
              }
            } catch {
              // ignore parse errors
            }
          }
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError' || signal?.aborted) {
        return { aborted: true }
      }
      throw err
    }
    if (signal?.aborted) return { aborted: true }
    if (!sawTerminal && typeof onDone === 'function') {
      await onDone({})
    }
    return { aborted: false }
  }).catch((err) => {
    if (err?.name === 'AbortError' || signal?.aborted) {
      return { aborted: true }
    }
    if (typeof onError === 'function') {
      const msg =
        typeof err === 'string'
          ? err
          : (err?.message || String(err) || '网络请求失败')
      if (/failed to fetch|networkerror|load failed/i.test(msg)) {
        return onError(`${msg}（连不上 API，请确认已启动 ./scripts/dev.sh）`)
      }
      return onError(msg)
    }
    throw err
  })
}
