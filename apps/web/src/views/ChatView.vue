<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div class="messages-container" ref="msgContainer">
      <div v-if="messages.length === 0 && !loadingSession" class="empty-state">
        <div class="logo">MES 运维助手</div>
        <p class="empty-desc">用自然语言管理 PCB MES系统</p>
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
          <ProcessPanel
            v-if="msg.role === 'assistant' && msg.process?.length"
            :items="msg.process"
            :collapsed="msg.processCollapsed !== false"
            :duration-text="msg.meta?.durationText || ''"
            @update:collapsed="(v) => { msg.processCollapsed = v }"
          />
          <div class="msg-body" v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
          <WriteConfirmCard
            v-for="card in (msg.confirms || [])"
            :key="card.action_id"
            :card="card"
            @resolved="(payload) => onConfirmResolved(msg, payload)"
          />
          <div class="msg-actions" v-if="msg.content || (msg.confirms || []).length">
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
          <ProcessPanel
            v-if="streamProcess.length"
            :items="streamProcess"
            :collapsed="streamProcessCollapsed"
            :duration-text="streamDurationText"
            @update:collapsed="(v) => { streamProcessCollapsed = v }"
          />
          <!-- 生成态立刻出气泡（打点），过程区本身无气泡 -->
          <div
            v-if="streamContent || streamAnswerPending || (!streamProcess.length && streaming)"
            class="msg-body"
            :class="{ thinking: !streamContent }"
          >
            <span v-if="!streamContent" class="thinking-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </span>
            <span v-else v-html="renderMarkdown(streamContent)"></span>
          </div>
          <WriteConfirmCard
            v-for="card in streamConfirms"
            :key="card.action_id"
            :card="card"
            @resolved="(payload) => onStreamConfirmResolved(payload)"
          />
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
import { streamMessage, uploadFile, saveHistory, getHistoryDetail, fetchPendingWrites } from '../api.js'
import ProcessPanel from '../components/ProcessPanel.vue'
import WriteConfirmCard from '../components/WriteConfirmCard.vue'

const route = useRoute()
const router = useRouter()

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamContent = ref('')
const streamProcess = ref([])
const streamProcessCollapsed = ref(false)
const streamDurationText = ref('')
const streamStartedAt = ref(0)
const streamAnswerPending = ref(false)
const streamConfirms = ref([])
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

// 首页快捷问法：对齐 docs/平台业务能力理解测试用例.md（表结构能力，非模拟查/导）
const suggestions = [
  '平台能干什么？给我一个功能总览',
  '仓储能管哪些事？相关表有哪些？',
  '工单从下达到入库涉及哪些表？按流程串一下',
  '导出一份摸底报告，Markdown 和 Excel 都要',
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

function pendingItemToCard(item) {
  const preview = item?.preview || {}
  return {
    action_id: item.action_id,
    status: 'pending',
    tool: item.tool,
    thread_id: item.thread_id,
    summary: preview.summary || `待确认写入：${item.tool || '写操作'}`,
    preview,
    message: '',
  }
}

function mergeConfirmCards(existing, incoming) {
  const map = new Map()
  for (const c of existing || []) {
    if (c?.action_id) map.set(c.action_id, c)
  }
  for (const c of incoming || []) {
    if (!c?.action_id) continue
    const prev = map.get(c.action_id)
    map.set(c.action_id, prev ? { ...prev, ...c } : c)
  }
  return Array.from(map.values())
}

function looksLikePendingImportMessage(content) {
  const t = String(content || '')
  if (!t.trim()) return false
  return (
    /尚未写入平台/.test(t) ||
    /确认卡片/.test(t) ||
    /待导入/.test(t) ||
    /确认写入/.test(t) ||
    /写操作确认/.test(t) ||
    /pending_confirmation/.test(t) ||
    /文件预览[：:]/.test(t) ||
    /文件摘要[：:]/.test(t) ||
    /目标实体/.test(t)
  )
}

/** 确认/取消后：删掉相邻的「尚未写入」重复助手气泡，只留一条结果 */
function collapseImportDuplicateMessages(keepMsg) {
  if (!keepMsg) return
  const keepIdx = messages.value.indexOf(keepMsg)
  if (keepIdx < 0) return
  const removeIdx = []
  for (let i = 0; i < messages.value.length; i++) {
    if (i === keepIdx) continue
    const m = messages.value[i]
    if (m.role !== 'assistant') continue
    if ((m.confirms || []).length) continue
    if (!looksLikePendingImportMessage(m.content)) continue
    // 只收紧 keep 附近的导入草稿（避免误删更早无关回复）
    if (Math.abs(i - keepIdx) <= 2) removeIdx.push(i)
  }
  if (!removeIdx.length) return
  for (const i of removeIdx.sort((a, b) => b - a)) {
    messages.value.splice(i, 1)
  }
}

async function attachPendingConfirms(targetThread) {
  if (!targetThread) return
  try {
    const res = await fetchPendingWrites(targetThread)
    const items = res.data?.items || []
    if (!items.length) return
    const cards = items.map(pendingItemToCard)
    const actionIds = new Set(cards.map((c) => c.action_id).filter(Boolean))
    const stable = buildImportSummaryMarkdown(cards[0]?.preview)

    // 1) 已挂过该 action 的消息：合并卡片；若正文仍是「尚未写入」则换成稳定摘要
    let mergedIntoExisting = false
    for (const msg of messages.value) {
      if (msg.role !== 'assistant') continue
      const owned = (msg.confirms || []).some((c) => actionIds.has(c.action_id))
      if (!owned) continue
      msg.confirms = mergeConfirmCards(msg.confirms || [], cards)
      if (stable && /尚未写入平台|确认卡片/.test(msg.content || '')) {
        msg.content = stable
      }
      mergedIntoExisting = true
    }
    if (mergedIntoExisting) {
      await persistSession()
      scrollToBottom()
      return
    }

    // 2) 流式中：挂到 streamConfirms，并用稳定摘要替换模型「尚未写入」散文
    if (streaming.value) {
      streamConfirms.value = mergeConfirmCards(streamConfirms.value, cards)
      if (stable) {
        streamContent.value = stable
        streamAnswerPending.value = true
      }
      scrollToBottom()
      return
    }

    // 3) 最近一条助手消息已是导入/待确认文案：合并进同一条，避免「模型一句 + 卡片一句」拆成两条
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg.role !== 'assistant') continue
      if ((msg.confirms || []).length || looksLikePendingImportMessage(msg.content)) {
        msg.confirms = mergeConfirmCards(msg.confirms || [], cards)
        if (stable) msg.content = stable
        await persistSession()
        scrollToBottom()
        return
      }
      break
    }

    // 4) 确实没有可合并对象时，再单独插一条
    messages.value.push({
      role: 'assistant',
      content: stable || '有待确认的写操作，请确认或取消：',
      confirms: cards,
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
  } catch (e) {
    console.warn('拉取待确认写操作失败', e)
  }
}

function persistableMessages() {
  return messages.value.map(m => ({
    role: m.role,
    content: m.content,
    ...(m.meta ? { meta: m.meta } : {}),
    ...(m.process?.length ? { process: m.process } : {}),
    ...(m.confirms?.length ? { confirms: m.confirms } : {}),
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
  streamProcess.value = []
  streamConfirms.value = []
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  attachedFiles.value = []
  streaming.value = false
  editingFromIndex.value = -1
  copiedIndex.value = -1
  try {
    const resp = await getHistoryDetail(id)
    messages.value = (resp.data.messages || []).map(m => {
      let content = m.content || ''
      const confirms = (m.confirms || [])
        .filter((c) => !c.status || c.status === 'pending' || c.status === 'pending_confirmation')
        .map((c) => ({ ...c }))
      // 正文已有最终结果时，清掉过期的「请去点确认卡」提示
      if (
        /已确认写入|已取消写入|\[已确认写入\]|\[已取消\]/.test(content) &&
        !confirms.length
      ) {
        content = scrubPendingConfirmHints(content)
      }
      return {
        role: m.role,
        content,
        meta: m.meta,
        process: m.process || [],
        confirms,
        processCollapsed: true,
      }
    })
    scrollToBottom()
  } catch {
    // 新会话或尚未入库：空消息即可继续聊
    messages.value = []
  } finally {
    loadingSession.value = false
    nextTick(() => inputEl.value?.focus())
    await attachPendingConfirms(id)
  }
}

function startNewChat() {
  if (streaming.value) return
  activeRequestId += 1
  const id = createThreadId()
  threadId.value = id
  messages.value = []
  streamContent.value = ''
  streamProcess.value = []
  streamConfirms.value = []
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
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
    streamProcess.value = []
    streamConfirms.value = []
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
  streamAnswerPending.value = false
  streamConfirms.value = []
  // 本地先挂一条「分析中」，后续真实步骤会替换掉
  streamProcess.value = [{ id: 'boot', type: 'step', state: 'running', title: '分析问题…' }]
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamStartedAt.value = Date.now()
  scrollToBottom()

  let stepRevealChain = Promise.resolve()
  let flushStepsNow = false
  const STEP_GAP_MS = 150

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

  const applyStep = (event) => {
    const id = event.id || `tool-${event.tool || event.title}`
    const steps = streamProcess.value.filter((i) => i.type === 'step' && i.id !== 'boot')
    const idx = steps.findIndex(
      (i) => i.id === id || (event.tool && i.tool === event.tool && i.state === 'running')
    )
    const prev = idx >= 0 ? steps[idx] : null
    const item = {
      id,
      type: 'step',
      tool: event.tool,
      phase: event.phase,
      state: event.state || (event.phase === 'end' ? (event.ok === false ? 'error' : 'done') : 'running'),
      title: event.title,
      args: event.args || prev?.args || '',
      detail: event.detail || prev?.detail || '',
      preview: Array.isArray(event.preview) ? event.preview : (prev?.preview || []),
      ok: event.ok,
    }
    if (idx >= 0) steps[idx] = { ...steps[idx], ...item }
    else steps.push(item)
    streamProcess.value = steps
  }

  const enqueueStep = (event) => {
    // start：错峰露出；end：立刻更新同一条，不再额外等待
    const gap = event.phase === 'start' || event.state === 'running' ? STEP_GAP_MS : 0
    stepRevealChain = stepRevealChain.then(async () => {
      if (requestId !== activeRequestId || threadId.value !== currentThread) return
      applyStep(event)
      if (!streamAnswerPending.value) streamProcessCollapsed.value = false
      await nextTick()
      scrollToBottom()
      if (!flushStepsNow && gap > 0) await sleep(gap)
    })
    return stepRevealChain
  }

  const upsertConfirm = (event) => {
    if (!event?.action_id) return
    const card = {
      action_id: event.action_id,
      status: 'pending',
      tool: event.tool,
      thread_id: event.thread_id || currentThread,
      summary: event.summary || '待确认写入平台',
      preview: event.preview || {},
      message: event.message || '',
    }
    const idx = streamConfirms.value.findIndex((c) => c.action_id === card.action_id)
    if (idx >= 0) streamConfirms.value[idx] = { ...streamConfirms.value[idx], ...card }
    else streamConfirms.value = [...streamConfirms.value, card]
    // 用确认卡预览生成稳定表格正文，避免模型散文/表格来回变
    const stable = buildImportSummaryMarkdown(card.preview)
    if (stable) {
      streamContent.value = stable
      streamAnswerPending.value = true
    }
  }

  try {
    const filePaths = files.map(f => f.path).filter(Boolean)
    await streamMessage(
      content,
      currentThread,
      async (event) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        const type = event?.type
        if (type === 'status') {
          const text = event.text || ''
          if (event.phase === 'generating' || /正在组织|正在生成/.test(text)) {
            const rest = streamProcess.value.filter(
              (i) => i.type === 'step' && i.id !== 'boot'
            )
            streamProcess.value = [
              ...rest,
              {
                id: 'status-generating',
                type: 'status',
                phase: 'generating',
                text: text || '正在组织最终回答…',
              },
            ]
            streamAnswerPending.value = true
            streamProcessCollapsed.value = false
            if (!streamDurationText.value) {
              const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
              streamDurationText.value = `${sec}s`
            }
            scrollToBottom()
            return
          }
          if (event.phase === 'waiting' || /继续|确认/.test(text)) {
            const rest = streamProcess.value.filter(
              (i) =>
                i.id !== 'boot' &&
                !(i.type === 'status' && (i.phase === 'waiting' || i.phase === 'generating'))
            )
            streamProcess.value = [
              ...rest,
              {
                id: 'status-waiting',
                type: 'status',
                phase: 'waiting',
                text: text || '继续分析与整理…',
              },
            ]
            streamAnswerPending.value = true
            streamProcessCollapsed.value = false
            scrollToBottom()
            return
          }
          if (/分析|处理/.test(text) && streamProcess.value.some((i) => i.id === 'boot')) {
            streamProcess.value = [{ id: 'boot', type: 'step', state: 'running', title: text }]
          }
        } else if (type === 'step') {
          if (event.phase === 'start' || event.state === 'running') {
            streamAnswerPending.value = false
            streamProcessCollapsed.value = false
            streamProcess.value = streamProcess.value.filter(
              (i) => !(i.type === 'status' && (i.phase === 'waiting' || i.phase === 'generating'))
            )
          }
          await enqueueStep(event)
          const stillRunning = streamProcess.value.some((i) => i.state === 'running')
          if (!stillRunning && (event.phase === 'end' || event.state === 'done' || event.state === 'error' || event.state === 'waiting')) {
            streamAnswerPending.value = true
            streamProcessCollapsed.value = false
            scrollToBottom()
          }
        } else if (type === 'confirm') {
          upsertConfirm(event)
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          scrollToBottom()
        } else if (type === 'token') {
          const text = event.text != null ? event.text : event.token
          if (!text) return
          // 已有写确认预览表时，忽略模型后续散文 token，保持表格稳定
          if (streamConfirms.value.length) return
          flushStepsNow = true
          await stepRevealChain
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          if (!streamDurationText.value) {
            const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
            streamDurationText.value = `${sec}s`
          }
          streamProcess.value = streamProcess.value.filter(
            (i) => !(i.type === 'status' && i.phase === 'generating')
          )
          streamContent.value += text
          scrollToBottom()
        }
      },
      async () => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        flushStepsNow = true
        await stepRevealChain
        const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
        const durationText = streamDurationText.value || `${sec}s`
        const processItems = (streamProcess.value || []).filter(
          (i) => i.type === 'step' && i.id !== 'boot'
        )
        const confirms = (streamConfirms.value || []).map((c) => ({ ...c }))
        let finalContent = streamContent.value
        if (confirms.length) {
          const stable = buildImportSummaryMarkdown(confirms[0].preview)
          if (stable) finalContent = stable
        }
        if (finalContent || processItems.length || confirms.length) {
          messages.value.push({
            role: 'assistant',
            content: finalContent,
            process: processItems,
            confirms,
            processCollapsed: true,
            meta: {
              time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
              durationText,
            },
          })
        }
        streamContent.value = ''
        streamProcess.value = []
        streamConfirms.value = []
        streamProcessCollapsed.value = false
        streamDurationText.value = ''
        streamAnswerPending.value = false
        streaming.value = false
        scrollToBottom()
        await persistSession()
        await attachPendingConfirms(currentThread)
      },
      async (err) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        flushStepsNow = true
        await stepRevealChain
        const errText = typeof err === 'string' ? err : (err?.message || err)
        messages.value.push({
          role: 'assistant',
          content: '[错误] 请求失败：' + errText,
          process: (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
          confirms: (streamConfirms.value || []).map((c) => ({ ...c })),
          processCollapsed: true,
        })
        streamContent.value = ''
        streamProcess.value = []
        streamConfirms.value = []
        streamProcessCollapsed.value = false
        streamDurationText.value = ''
        streamAnswerPending.value = false
        streaming.value = false
        scrollToBottom()
        await persistSession()
        await attachPendingConfirms(currentThread)
      },
      filePaths
    )
  } catch (err) {
    if (requestId !== activeRequestId || threadId.value !== currentThread) return
    messages.value.push({
      role: 'assistant',
      content: '[错误] 连接服务器失败，请确认服务端已启动',
      process: (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
      confirms: (streamConfirms.value || []).map((c) => ({ ...c })),
      processCollapsed: true,
    })
    streamContent.value = ''
    streamProcess.value = []
    streamConfirms.value = []
    streamProcessCollapsed.value = false
    streamDurationText.value = ''
    streamAnswerPending.value = false
    streaming.value = false
    scrollToBottom()
    await persistSession()
    await attachPendingConfirms(currentThread)
  }
}

function applyConfirmResolved(list, payload) {
  if (!Array.isArray(list) || !payload?.action_id) return list || []
  const status = payload.status
  // 确认成功或取消：移除卡片
  if (status === 'confirmed' || status === 'cancelled') {
    return list.filter((c) => c.action_id !== payload.action_id)
  }
  // 失败：保留 pending 以便重试，并带上错误信息
  return list.map((c) => {
    if (c.action_id !== payload.action_id) return c
    if (status === 'failed') {
      return {
        ...c,
        status: 'pending',
        result: payload.result,
        error: payload.error || payload.result?.error,
      }
    }
    return {
      ...c,
      status: status || c.status,
      result: payload.result,
      error: payload.error,
    }
  })
}

const IMPORT_COL_LABELS = {
  order_no: '工单号',
  product_name: '产品名称',
  product_code: '产品编码',
  plan_quantity: '计划数量',
  status: '状态',
  remark: '备注',
  production_line: '产线',
  priority: '优先级',
  assignee: '负责人',
}

const ENTITY_LABELS = {
  'work-orders': '工单',
  'production-plans': '生产计划',
  products: '产品',
  devices: '设备',
}

/**
 * 固定导入预览正文为「图二」格式：
 * 文件预览：N 条XX记录，字段与 `entity` 实体匹配。
 * 文件摘要：`file.csv`，共 **N 条XX**，目标实体 `entity`（中文名）。
 * + markdown 表格
 */
function buildImportSummaryMarkdown(preview) {
  if (!preview || typeof preview !== 'object') return ''
  const file = preview.file || ''
  const entity = preview.target_entity || ''
  const entityLabel = ENTITY_LABELS[entity] || '记录'
  const rowCount = preview.row_count
  const n = rowCount != null ? Number(rowCount) : null
  const sample = Array.isArray(preview.sample_rows)
    ? preview.sample_rows.filter((r) => r && typeof r === 'object')
    : []
  const cols = (
    Array.isArray(preview.columns) && preview.columns.length
      ? preview.columns
      : sample[0]
        ? Object.keys(sample[0])
        : []
  ).slice(0, 8)

  const recordWord = entityLabel === '记录' ? '记录' : `${entityLabel}记录`
  const countWord = entityLabel === '记录' ? '记录' : entityLabel

  let md = ''
  if (n != null && entity) {
    md += `文件预览：**${n}** 条${recordWord}，字段与 \`${entity}\` 实体匹配。`
  } else if (n != null) {
    md += `文件预览：**${n}** 条${recordWord}。`
  } else {
    md += '文件预览完成。'
  }

  const summaryBits = []
  if (file) summaryBits.push(`\`${file}\``)
  if (n != null) summaryBits.push(`共 **${n} 条${countWord}**`)
  if (entity) {
    summaryBits.push(
      entityLabel !== '记录'
        ? `目标实体 \`${entity}\`（${entityLabel}）`
        : `目标实体 \`${entity}\``
    )
  }
  if (summaryBits.length) {
    md += `\n\n文件摘要：${summaryBits.join('，')}。`
  }

  if (sample.length && cols.length) {
    const labels = cols.map((c) => IMPORT_COL_LABELS[c] || c)
    const esc = (v) => String(v ?? '').replace(/\|/g, '\\|').replace(/\n/g, ' ')
    md += '\n\n| ' + labels.join(' | ') + ' |\n'
    md += '| ' + cols.map(() => '---').join(' | ') + ' |\n'
    for (const row of sample.slice(0, 8)) {
      md += '| ' + cols.map((c) => esc(row[c])).join(' | ') + ' |\n'
    }
  }
  return md.trim()
}

/** 去掉「请去确认卡片操作」等误导文案 */
function scrubPendingConfirmHints(text) {
  if (!text) return ''
  let out = String(text)

  // 整行/整段含「尚未写入」的直接丢掉（含 emoji、加粗）
  out = out
    .split('\n')
    .filter((line) => !/尚未写入平台|请在下方确认卡片|请在确认卡片中点/.test(line))
    .join('\n')

  const dropSentence = (s) => {
    const t = s.trim()
    if (!t) return false
    if (/^已确认写入|^已取消写入|^写入失败|已取消写入，平台数据未变更|^文件预览[：:]|^文件摘要[：:]/.test(t)) {
      return false
    }
    // 保留已有 markdown 表格行
    if (/^\|/.test(t)) return false
    return (
      /确认卡片/.test(t) ||
      /请点击.*确认写入/.test(t) ||
      /点击[「"']?确认写入/.test(t) ||
      /放弃本次操作/.test(t) ||
      /写操作已挂起/.test(t) ||
      /尚未写入平台/.test(t) ||
      /等待你(?:在界面)?确认/.test(t) ||
      /等待用户(?:在界面)?确认/.test(t) ||
      /导入请求已提交/.test(t) ||
      /现在执行导入/.test(t) ||
      /不要再次调用导入/.test(t) ||
      /确认前(?:我)?不会重复发起导入/.test(t) ||
      /不会重复发起导入/.test(t) ||
      /确认前[^\n。]{0,20}不会[^\n。]{0,20}导入/.test(t) ||
      /列名\s*`?[a-z_]+`?/.test(t) ||
      /文件预览正常/.test(t) ||
      /共\s*\d+\s*条工单待导入/.test(t)
    )
  }

  const parts = out.split(/([。！？\n]+)/)
  let result = ''
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    if (/^[。！？\n]+$/.test(part)) continue
    if (dropSentence(part)) {
      i += 1
      continue
    }
    result += part
    if (i + 1 < parts.length && /^[。！？\n]+$/.test(parts[i + 1])) {
      result += parts[i + 1]
      i += 1
    }
  }
  out = result

  const phrasePatterns = [
    /系统已生成确认卡片[，,]?[^\n。]*/g,
    /请在弹出的确认卡片中[^\n。]*/g,
    /请在确认卡片中[^\n。]*/g,
    /请点击界面中的[「"']?确认写入[」"']?按钮[^\n。]*/g,
    /请点击[「"']?确认写入[」"']?[^\n。]*/g,
    /或点击[「"']?取消[」"']?放弃本次操作[。.]?/g,
    /⚠️\s*\*?\*?尚未写入平台\*?\*?[^\n]*/g,
  ]
  for (const re of phrasePatterns) {
    out = out.replace(re, '')
  }

  return out
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[，,]\s*[。.]/g, '。')
    .trim()
}

function finalizeWriteMessage(content, tip, preview) {
  // 有预览数据时：只用「摘要 + 表格 + 结果」一条，丢掉模型「尚未写入」散文
  const stable = buildImportSummaryMarkdown(preview)
  if (stable) {
    if (!tip) return stable
    if (stable.includes(tip)) return stable
    return `${stable}\n\n${tip}`
  }
  const base = scrubPendingConfirmHints(content || '')
  if (!tip) return base
  if (base.includes(tip)) return base
  return base ? `${base}\n\n${tip}` : tip
}

function onConfirmResolved(msg, payload) {
  if (!msg) return
  const card = (msg.confirms || []).find((c) => c.action_id === payload.action_id)
  const preview = card?.preview || payload?.preview || null
  msg.confirms = applyConfirmResolved(msg.confirms || [], payload)
  if (payload?.status === 'confirmed' && payload?.result) {
    const r = payload.result
    const tip = r.error
      ? `写入失败：${r.error}`
      : `已确认写入：${r.target_entity || ''} ${r.rows_imported != null ? r.rows_imported + ' 行' : ''}`.trim()
    msg.content = finalizeWriteMessage(msg.content, tip, preview)
    collapseImportDuplicateMessages(msg)
  } else if (payload?.status === 'cancelled') {
    msg.content = finalizeWriteMessage(msg.content, '已取消写入，平台数据未变更。', preview)
    collapseImportDuplicateMessages(msg)
  } else if (payload?.status === 'failed' && payload?.error) {
    const tip = `写入失败：${payload.error}（可重试）`
    if (msg.content && !msg.content.includes(tip)) {
      msg.content = `${msg.content}\n\n${tip}`
    } else if (!msg.content) {
      msg.content = tip
    }
  }
  persistSession()
}

function onStreamConfirmResolved(payload) {
  // 流未结束：更新 streamConfirms
  const inStream = (streamConfirms.value || []).some((c) => c.action_id === payload.action_id)
  if (inStream && streaming.value) {
    const card = (streamConfirms.value || []).find((c) => c.action_id === payload.action_id)
    const preview = card?.preview || payload?.preview || null
    streamConfirms.value = applyConfirmResolved(streamConfirms.value, payload)
    if (payload?.status === 'confirmed' && payload?.result && !payload.result.error) {
      const r = payload.result
      const tip = `已确认写入：${r.target_entity || ''} ${r.rows_imported != null ? r.rows_imported + ' 行' : ''}`.trim()
      streamContent.value = finalizeWriteMessage(streamContent.value, tip, preview)
    } else if (payload?.status === 'cancelled') {
      streamContent.value = finalizeWriteMessage(streamContent.value, '已取消写入，平台数据未变更。', preview)
    } else if (payload?.status === 'failed') {
      const tip = `写入失败：${payload.error || ''}（可重试）`
      streamContent.value = (streamContent.value || '') + (streamContent.value ? `\n\n${tip}` : tip)
    }
    return
  }

  // 流已结束、卡片已落入 messages：按 action_id 更新，避免确认结果丢失导致二次写入
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role !== 'assistant') continue
    if (!(msg.confirms || []).some((c) => c.action_id === payload.action_id)) continue
    onConfirmResolved(msg, payload)
    return
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
  box-sizing: border-box;
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

/* 确认卡与同条消息体同宽（跟随较宽的表格气泡拉伸） */
.message.assistant .msg-content :deep(.write-confirm) {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
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
