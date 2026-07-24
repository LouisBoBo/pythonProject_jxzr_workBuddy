<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div class="messages-container" ref="msgContainer">
      <div v-if="messages.length === 0 && !loadingSession" class="empty-state">
        <div class="logo">MES 运维助手</div>
        <p class="empty-desc">用自然语言管理 PCB 工单数据</p>
        <div class="suggestions">
          <button v-for="s in suggestions" :key="s" class="suggest-btn" @click="send(s)">
            {{ s }}
          </button>
        </div>
      </div>
      <div v-if="loadingSession" class="empty-state">
        <p class="empty-desc">正在加载会话...</p>
      </div>

      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="msg-avatar assistant-avatar" v-if="msg.role === 'assistant'">
          <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="14" fill="var(--ui-accent)"/>
            <circle cx="10.5" cy="12" r="1.6" fill="#fff"/>
            <circle cx="17.5" cy="12" r="1.6" fill="#fff"/>
            <path d="M10 18c2-1.6 6-1.6 8 0" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="msg-content">
          <div class="msg-body" v-html="renderMarkdown(msg.content)"></div>
          <div class="msg-actions">
            <el-tooltip
              :content="copiedIndex === i ? '已复制' : '复制'"
              placement="bottom"
              :hide-after="copiedIndex === i ? 800 : 0"
            >
              <button
                class="msg-action-btn"
                type="button"
                @click="copyMessage(msg.content, i)"
              >
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <rect x="5" y="5" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.4"/>
                  <path d="M3.5 10V3.5A1.5 1.5 0 0 1 5 2h6.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
                </svg>
              </button>
            </el-tooltip>
            <el-tooltip v-if="msg.role === 'user'" content="编辑" placement="bottom">
              <button
                class="msg-action-btn"
                type="button"
                :disabled="streaming"
                @click="editUserMessage(i)"
              >
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <path d="M11.2 2.3a1.4 1.4 0 0 1 2 2L5.4 12.1 2 13l.9-3.4L11.2 2.3z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
                </svg>
              </button>
            </el-tooltip>
          </div>
        </div>
        <div class="msg-avatar user-avatar" v-if="msg.role === 'user'">
          <div class="avatar-letter">U</div>
        </div>
      </div>

      <div v-if="streaming" class="message assistant">
        <div class="msg-avatar assistant-avatar">
          <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="14" fill="var(--ui-accent)"/>
            <circle cx="10.5" cy="12" r="1.6" fill="#fff"/>
            <circle cx="17.5" cy="12" r="1.6" fill="#fff"/>
            <path d="M10 18c2-1.6 6-1.6 8 0" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="msg-content">
          <div class="msg-body" :class="{ thinking: !streamContent }">
            <span v-if="!streamContent" class="thinking-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </span>
            <span v-html="renderMarkdown(streamContent)"></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Prompt bar: 1:1 CloudPromptBar style -->
    <div class="prompt-area">
      <div class="prompt-bar-wrapper">
        <div class="prompt-bar">
          <div v-if="attachedFiles.length" class="attached-files">
            <div
              v-for="(file, index) in attachedFiles"
              :key="file.id"
              class="file-chip"
              :class="{ uploading: file.status === 'uploading', error: file.status === 'error' }"
            >
              <span class="file-name">{{ file.name }}</span>
              <span v-if="file.status === 'uploading'" class="file-status">上传中…</span>
              <span v-if="file.status === 'error'" class="file-status">失败</span>
              <button
                v-if="file.status !== 'uploading'"
                class="file-remove"
                @click="removeAttachedFile(index)"
                title="删除"
              >×</button>
            </div>
          </div>
          <textarea
            ref="inputEl"
            v-model="input"
            class="prompt-input"
            :placeholder="streaming ? '等待回复中...' : '描述你想做的事情，例如：把 test_data/new_orders.csv 导入到工单系统'"
            rows="1"
            :disabled="streaming"
            @keydown.enter.exact.prevent="send(input)"
            @keydown.enter.shift.exact="input += '\n'"
            @input="autoResize"
          ></textarea>
          <div class="prompt-actions">
            <input
              ref="fileInput"
              type="file"
              accept=".csv,.xlsx,.xls,.json,.txt"
              style="display: none"
              @change="handleFileUpload"
            />
            <button
              class="new-chat-btn"
              @click="fileInput.click()"
              title="上传文件"
              :disabled="streaming"
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M7.5 1v13M1 7.5h13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            </button>
            <button
              class="send-btn"
              :disabled="(!input.trim() && attachedFiles.length === 0) || streaming"
              @click="send(input)"
              title="发送"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 13L13 7L1 1L3.67 7L1 13Z" fill="currentColor" stroke="currentColor" stroke-width="0.5" stroke-linejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { streamMessage, uploadFile, saveHistory, getHistoryDetail } from '../api.js'

const route = useRoute()
const router = useRouter()

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamContent = ref('')
const msgContainer = ref(null)
const inputEl = ref(null)
const fileInput = ref(null)
const attachedFiles = ref([])
const threadId = ref('')
const loadingSession = ref(false)
const copiedIndex = ref(-1)
const editingFromIndex = ref(-1)
let activeRequestId = 0
let copiedTimer = null

const suggestions = [
  '帮我看看平台有哪些工单',
  '导入 test_data/new_orders.csv',
  '导出全部工单为 Excel',
  '查一下待排产的工单',
]

function createThreadId() {
  return 'session-' + Date.now()
}

function notifyHistoryUpdated() {
  window.dispatchEvent(new CustomEvent('mes-history-updated'))
}

async function copyMessage(content, index) {
  const text = (content || '').trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copiedIndex.value = index
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedIndex.value = -1
  }, 1500)
}

function editUserMessage(index) {
  if (streaming.value) return
  const msg = messages.value[index]
  if (!msg || msg.role !== 'user') return
  editingFromIndex.value = index
  input.value = msg.content || ''
  nextTick(() => {
    if (inputEl.value) {
      inputEl.value.focus()
      autoResize()
      // 光标移到末尾
      const len = inputEl.value.value.length
      inputEl.value.setSelectionRange(len, len)
    }
  })
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 200) + 'px'
}

function scrollToBottom() {
  nextTick(() => {
    if (msgContainer.value) {
      msgContainer.value.scrollTop = msgContainer.value.scrollHeight
    }
  })
}

function persistableMessages() {
  return messages.value.map(m => ({
    role: m.role,
    content: m.content,
    ...(m.meta ? { meta: m.meta } : {}),
  }))
}

async function persistSession() {
  if (!threadId.value || messages.value.length === 0) return
  try {
    await saveHistory(threadId.value, persistableMessages())
    notifyHistoryUpdated()
  } catch (e) {
    console.warn('保存会话失败', e)
  }
}

function syncThreadQuery(id) {
  if (route.query.thread === id) return
  router.replace({ path: '/', query: { thread: id } })
}

async function loadSession(id) {
  activeRequestId += 1
  loadingSession.value = true
  threadId.value = id
  streamContent.value = ''
  attachedFiles.value = []
  streaming.value = false
  editingFromIndex.value = -1
  copiedIndex.value = -1
  try {
    const resp = await getHistoryDetail(id)
    messages.value = (resp.data.messages || []).map(m => ({
      role: m.role,
      content: m.content,
      meta: m.meta,
    }))
    scrollToBottom()
  } catch {
    // 新会话或尚未入库：空消息即可继续聊
    messages.value = []
  } finally {
    loadingSession.value = false
    nextTick(() => inputEl.value?.focus())
  }
}

function startNewChat() {
  if (streaming.value) return
  activeRequestId += 1
  const id = createThreadId()
  threadId.value = id
  messages.value = []
  streamContent.value = ''
  attachedFiles.value = []
  streaming.value = false
  editingFromIndex.value = -1
  copiedIndex.value = -1
  syncThreadQuery(id)
  nextTick(() => inputEl.value?.focus())
}

async function initFromRoute() {
  const id = route.query.thread
  if (typeof id === 'string' && id) {
    await loadSession(id)
  } else {
    startNewChat()
  }
}

watch(
  () => route.query.thread,
  async (id) => {
    if (typeof id !== 'string' || !id) return
    if (id === threadId.value) return
    // 切换会话时中断当前流式状态，加载目标会话
    streaming.value = false
    streamContent.value = ''
    await loadSession(id)
  }
)

async function send(text) {
  const content = text || input.value.trim()
  const files = attachedFiles.value
  if ((!content && files.length === 0) || streaming.value) return
  if (!threadId.value) {
    threadId.value = createThreadId()
    syncThreadQuery(threadId.value)
  }

  // 编辑重发：截断该条及之后的消息，再作为新一轮发送
  if (editingFromIndex.value >= 0) {
    messages.value = messages.value.slice(0, editingFromIndex.value)
    editingFromIndex.value = -1
  }

  const requestId = ++activeRequestId
  const currentThread = threadId.value

  input.value = ''
  if (inputEl.value) {
    inputEl.value.style.height = 'auto'
  }

  const displayContent = buildUserDisplayContent(content, files)
  messages.value.push({ role: 'user', content: displayContent, files: [...files] })
  attachedFiles.value = []
  scrollToBottom()
  await persistSession()

  streaming.value = true
  streamContent.value = ''

  try {
    const filePaths = files.map(f => f.path).filter(Boolean)
    await streamMessage(
      content,
      currentThread,
      (token) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        streamContent.value += token
        scrollToBottom()
      },
      async () => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        if (streamContent.value) {
          messages.value.push({
            role: 'assistant',
            content: streamContent.value,
            meta: { time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) },
          })
        }
        streamContent.value = ''
        streaming.value = false
        scrollToBottom()
        await persistSession()
      },
      async (err) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        messages.value.push({
          role: 'assistant',
          content: '[错误] 请求失败：' + (err.message || err),
        })
        streamContent.value = ''
        streaming.value = false
        scrollToBottom()
        await persistSession()
      },
      filePaths
    )
  } catch (err) {
    if (requestId !== activeRequestId || threadId.value !== currentThread) return
    messages.value.push({
      role: 'assistant',
      content: '[错误] 连接服务器失败，请确认服务端已启动',
    })
    streamContent.value = ''
    streaming.value = false
    scrollToBottom()
    await persistSession()
  }
}

function buildUserDisplayContent(text, files) {
  if (!files.length) return text
  const fileList = files.map(f => `[附件: ${f.name}]`).join(' ')
  return text ? `${text} ${fileList}` : fileList
}

function removeAttachedFile(index) {
  attachedFiles.value.splice(index, 1)
}

async function handleFileUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return

  const tempId = Date.now()
  attachedFiles.value.push({ id: tempId, name: file.name, status: 'uploading', path: null })

  try {
    const res = await uploadFile(file)
    const saved = res.data
    const index = attachedFiles.value.findIndex(f => f.id === tempId)
    if (index !== -1) {
      attachedFiles.value[index] = {
        id: tempId,
        name: saved.filename || file.name,
        status: 'done',
        path: saved.path || saved.filename || file.name,
        size: saved.size,
      }
    }
  } catch (err) {
    const index = attachedFiles.value.findIndex(f => f.id === tempId)
    if (index !== -1) {
      attachedFiles.value[index].status = 'error'
    }
  }

  // 重置 input 以便重新选择同一文件
  e.target.value = ''
}

function renderMarkdown(text) {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  html = html.replace(/([\w\-~.:/\\]+[\\/])([\w\-]+\.(xlsx|csv|json))/g, (match, dir, filename) => {
    return `<a class="file-link" href="/api/download/${encodeURIComponent(filename)}" download target="_blank">${match}</a>`
  })

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>')

  html = html.replace(/^\|(.+)\|$/gm, (match) => {
    const cells = match.split('|').filter(c => c.trim())
    const isHeader = /^[-:\s|]+$/.test(match.replace(/\|/g, ''))
    if (isHeader) return ''
    return `<tr>${cells.map(c => {
      const isBold = /^\*\*(.+)\*\*$/.test(c.trim())
      const text = c.trim().replace(/\*\*/g, '')
      return isBold ? `<th>${text}</th>` : `<td>${text}</td>`
    }).join('')}</tr>`
  })
  html = html.replace(/(<tr>.*?<\/tr>)\n(<tr>)/g, '$1$2')
  html = html.replace(/(<tr>[\s\S]*?<\/tr>)/g, (match) => {
    if (match.includes('<table')) return match
    return `<table class="md-table">${match}</table>`
  })
  html = html.replace(/<\/table>\s*<table[^>]*>/g, '')

  html = html.replace(/^- (.+)$/gm, '<li class="md-li">$1</li>')
  html = html.replace(/(<li class="md-li">[\s\S]*?<\/li>)/g, (match) => {
    if (match.includes('<ul')) return match
    return `<ul class="md-ul">${match}</ul>`
  })
  html = html.replace(/^---$/gm, '<hr class="md-hr">')
  html = html.replace(/\n/g, '<br>')
  return html
}

onMounted(async () => {
  await initFromRoute()
  if (inputEl.value) inputEl.value.focus()
})
</script>

<style scoped>
/* ─── Design tokens (matches agents-ui theme) ─── */
.chat-view {
  --ui-bg: oklch(0.99 0.002 197.1);
  --ui-surface: oklch(1 0 0);
  --ui-panel: oklch(0.985 0.002 197.1);
  --ui-panel-2: oklch(0.967 0.001 286.375);
  --ui-border: oklch(0.925 0.005 214.3);
  --ui-text: oklch(0.148 0.004 228.8);
  --ui-text-muted: oklch(0.45 0.017 213.2);
  --ui-text-dim: oklch(0.56 0.021 213.5);
  --ui-accent: oklch(0.52 0.105 223.128);
  --ui-accent-bubble: oklch(0.955 0.015 223);

  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  max-width: 800px;
  margin: 0 auto;
  background: var(--ui-bg);
  color: var(--ui-text);
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.5;
  position: relative;
  overflow: hidden;
}

/* ─── Messages ─── */
.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 32px 24px 16px;
  scrollbar-width: thin;
  scrollbar-color: oklch(0.85 0.01 214) transparent;
}

/* Empty state — centered hero */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 16px;
  padding: 24px;
  text-align: center;
}

.logo {
  font-size: 36px;
  font-weight: 600;
  letter-spacing: -0.5px;
  color: var(--ui-text);
}

.empty-desc {
  font-size: 15px;
  color: var(--ui-text-dim);
  margin: 0;
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 100%;
  margin-top: 8px;
}

.suggest-btn {
  padding: 6px 14px;
  font-size: 13px;
  color: var(--ui-text-muted);
  background: transparent;
  border: 1px solid var(--ui-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
}

.suggest-btn:hover {
  background: var(--ui-panel);
  border-color: var(--ui-accent);
  color: var(--ui-accent);
}

/* Message bubbles */
.message {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 24px;
}

.message.user {
  justify-content: flex-end;
}

.message.assistant {
  justify-content: flex-start;
}

.msg-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  margin-top: 2px;
}

.user-avatar .avatar-letter {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: oklch(0.6 0.18 25);
  color: #fff;
  font-size: 16px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.msg-content {
  display: flex;
  flex-direction: column;
  max-width: calc(100% - 52px);
  align-items: flex-start;
}

.message.user .msg-content {
  align-items: flex-end;
}

.msg-body {
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.65;
  color: var(--ui-text);
  word-break: break-word;
  width: fit-content;
  max-width: 100%;
  min-width: 44px;
}

.message.user .msg-body {
  background: var(--ui-accent-bubble);
  color: var(--ui-text);
  border: 1px solid oklch(0.88 0.02 223);
  border-radius: 18px;
}

.message.assistant .msg-body {
  background: var(--ui-surface);
  border: 1px solid var(--ui-border);
  border-radius: 16px 16px 16px 4px;
}

.msg-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  max-height: 0;
  margin-top: 0;
  padding-right: 2px;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
  transition: opacity 0.15s, max-height 0.15s, margin-top 0.15s;
}

.message.user .msg-actions {
  justify-content: flex-end;
}

.message.assistant .msg-actions {
  justify-content: flex-start;
}

.message:hover .msg-actions,
.message:focus-within .msg-actions {
  max-height: 32px;
  margin-top: 4px;
  opacity: 1;
  pointer-events: auto;
}

.msg-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #8b95a5;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, color 0.15s;
}

.msg-action-btn:hover:not(:disabled) {
  background: oklch(0.94 0.01 223);
  color: #4b5563;
}

.msg-action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Markdown rendering */
:deep(.code-block) {
  background: #1e293b;
  color: #e2e8f0;
  padding: 12px 16px;
  border-radius: 8px;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  max-width: 100%;
  margin: 8px 0;
}

:deep(.inline-code) {
  background: var(--ui-panel-2);
  color: var(--ui-accent);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 12px;
}

:deep(.md-table) {
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  display: block;
  overflow-x: auto;
}

:deep(.md-table td),
:deep(.md-table th) {
  padding: 6px 10px;
  border: 1px solid var(--ui-border);
  text-align: left;
}

:deep(.md-table th) {
  background: var(--ui-panel);
  font-weight: 500;
}

:deep(.md-h1) { font-size: 15px; font-weight: 600; margin: 12px 0 6px; }
:deep(.md-h2) { font-size: 14px; font-weight: 600; margin: 10px 0 4px; }
:deep(.md-h3) { font-size: 13px; font-weight: 600; margin: 8px 0 4px; }
:deep(.md-hr) { border: none; border-top: 1px solid var(--ui-border); margin: 10px 0; }
:deep(.md-ul) { padding-left: 18px; margin: 4px 0; }
:deep(.md-li) { margin: 2px 0; }
:deep(strong) { font-weight: 600; }

:deep(.file-link) {
  color: var(--ui-accent);
  text-decoration: none;
  border-bottom: 1px solid var(--ui-accent-bubble);
  padding-bottom: 1px;
}

:deep(.file-link:hover) {
  border-bottom-color: var(--ui-accent);
}

/* ─── Thinking indicator ─── */
.thinking {
  min-width: 52px;
  width: fit-content;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.thinking-indicator {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}

.thinking-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ui-text-dim);
  animation: dot-bounce 1.4s infinite ease-in-out;
}

.thinking-indicator .dot:nth-child(2) { animation-delay: 0.15s; }
.thinking-indicator .dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ─── Prompt bar area ─── */
.prompt-area {
  flex-shrink: 0;
  padding: 16px 24px 24px;
  background: linear-gradient(180deg, transparent 0%, var(--ui-bg) 30%);
}

.prompt-bar-wrapper {
  max-width: 100%;
  margin: 0 auto;
}

.attached-files {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 2px 2px 8px;
}

.file-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: var(--ui-panel-2);
  border: 1px solid var(--ui-border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--ui-text);
  max-width: 100%;
}

.file-chip.uploading {
  opacity: 0.7;
}

.file-chip.error {
  border-color: oklch(0.65 0.15 25);
  background: oklch(0.97 0.02 25);
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 220px;
}

.file-status {
  color: var(--ui-text-muted);
  font-size: 11px;
}

.file-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ui-text-muted);
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  margin-left: 2px;
}

.file-remove:hover {
  background: var(--ui-border);
  color: var(--ui-text);
}

.prompt-bar {
  display: flex;
  flex-direction: column;
  min-height: 106px;
  background: var(--ui-surface);
  border: 1px solid var(--ui-border);
  border-radius: 16px;
  padding: 10px 12px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.prompt-bar:focus-within {
  border-color: var(--ui-accent);
  box-shadow: 0 0 0 3px oklch(0.52 0.105 223.128 / 0.1);
}

.prompt-input {
  flex: 1;
  min-height: 52px;
  width: 100%;
  resize: none;
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  font-size: 15px;
  line-height: 1.6;
  color: var(--ui-text);
  outline: none;
  padding: 4px 0;
  overflow-y: hidden;
}

.prompt-input::placeholder {
  color: var(--ui-text-dim);
}

.prompt-input:disabled {
  opacity: 0.6;
  cursor: default;
}

.prompt-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  padding-top: 8px;
  margin-top: auto;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ui-text-muted);
  cursor: pointer;
  transition: all 0.15s;
}

.new-chat-btn:hover {
  background: var(--ui-panel-2);
  color: var(--ui-text);
}

.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: var(--ui-accent);
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.send-btn:active:not(:disabled) {
  transform: scale(0.96);
}

.send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Responsive */
@media (max-width: 820px) {
  .chat-view {
    max-width: 100%;
  }
  .logo {
    font-size: 28px;
  }
}
</style>
