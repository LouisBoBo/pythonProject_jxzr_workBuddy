<template>
  <div class="chat-view">
    <!-- Messages area -->
    <div class="messages-container" ref="msgContainer" @click="onMessagesClick">
      <div v-if="messages.length === 0 && !loadingSession" class="empty-state">
        <div class="empty-title">我能为您做些什么？</div>
        <div class="suggestions">
          <button v-for="s in suggestions" :key="s" class="suggest-btn" @click="send(s)">
            {{ s }}
          </button>
        </div>
      </div>
      <div v-if="loadingSession" class="empty-state">
        <p class="empty-loading">正在加载会话...</p>
      </div>

      <div v-for="(msg, i) in messages" :key="i" :class="['message', msg.role]">
        <div class="msg-content">
          <div v-if="msg.role === 'assistant'" class="msg-brand">
            <AiAvatarIcon />
            <span class="msg-brand-name">ZR WorkBuddy</span>
          </div>
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
          <IdeWorkspacePickCard
            v-if="msg.idePick"
            :card="msg.idePick"
            @resolved="(payload) => onIdePickResolved(msg, payload)"
            @retry="() => retryIdeReview(msg)"
          />
          <GitRepoPickCard
            v-if="msg.gitPick"
            :card="msg.gitPick"
            @resolved="(payload) => onGitPickResolved(msg, payload)"
            @retry="() => retryGitReview(msg)"
          />
          <div class="msg-actions" v-if="msg.content || (msg.confirms || []).length || msg.idePick || msg.gitPick">
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
      </div>

      <div v-if="streaming" class="message assistant">
        <div class="msg-content">
          <div class="msg-brand">
            <AiAvatarIcon spinning />
            <span class="msg-brand-name">ZR WorkBuddy</span>
          </div>
          <ProcessPanel
            v-if="streamProcess.length"
            :items="streamProcess"
            :collapsed="streamProcessCollapsed"
            :duration-text="streamDurationText"
            @update:collapsed="(v) => { streamProcessCollapsed = v }"
          />
          <!-- 生成态立刻出气泡（打点）；有过程面板时也显示，避免「选完工程像没开始」 -->
          <div
            v-if="streamContent || streamAnswerPending || streaming"
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
      <div class="audit-strip" v-if="threadId">
        <button type="button" class="audit-toggle" @click="toggleAudit">
          {{ auditOpen ? '收起本会话写操作记录' : '本会话写操作记录' }}
          <span v-if="!auditOpen && auditItems.length" class="audit-count">{{ auditItems.length }}</span>
        </button>
        <div v-if="auditOpen" class="audit-panel">
          <div v-if="auditLoading" class="audit-empty">加载中…</div>
          <div v-else-if="!auditItems.length" class="audit-empty">暂无写操作审计（确认/取消/过期会落在这里）</div>
          <ul v-else class="audit-list">
            <li v-for="(it, idx) in auditItems" :key="idx" class="audit-item">
              <span class="audit-event" :class="'ev-' + (it.event || '').replace('write_', '')">
                {{ auditEventLabel(it.event) }}
              </span>
              <span class="audit-main">{{ auditMainText(it) }}</span>
              <span class="audit-time">{{ formatAuditTime(it.ts) }}</span>
            </li>
          </ul>
        </div>
      </div>
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
            :placeholder="streaming ? '生成中可继续编辑下一条，或点右侧停止…' : '描述你想做的事情，例如：导入访问日志分析接口错误，或把 CSV 导入工单'"
            rows="1"
            @keydown.enter.exact.prevent="onEnterSend"
            @keydown.enter.shift.exact="input += '\n'"
            @input="autoResize"
            @paste="onPasteResize"
          ></textarea>
          <div class="prompt-actions">
            <input
              ref="fileInput"
              type="file"
              accept=".csv,.xlsx,.xls,.json,.jsonl,.log,.txt,.yaml,.yml,.md"
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
              v-if="streaming"
              class="stop-btn"
              type="button"
              title="停止生成"
              @click="stopStreaming"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <rect x="2" y="2" width="8" height="8" rx="1.5" fill="currentColor"/>
              </svg>
            </button>
            <button
              v-else
              class="send-btn"
              :disabled="!input.trim() && attachedFiles.length === 0"
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
import { streamMessage, uploadFile, saveHistory, getHistoryDetail, fetchPendingWrites, fetchWriteAudit, fetchIdeBridgeStatus } from '../api.js'
import ProcessPanel from '../components/ProcessPanel.vue'
import WriteConfirmCard from '../components/WriteConfirmCard.vue'
import IdeWorkspacePickCard from '../components/IdeWorkspacePickCard.vue'
import GitRepoPickCard from '../components/GitRepoPickCard.vue'
import AiAvatarIcon from '../components/AiAvatarIcon.vue'
import { getUsername, getUserId } from '../auth.js'

const route = useRoute()
const router = useRouter()

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamAbort = ref(null)
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
const auditOpen = ref(false)
const auditLoading = ref(false)
const auditItems = ref([])
let activeRequestId = 0
let copiedTimer = null

// 首页快捷问法：区分 WorkBuddy（平台）与 MES 系统
const suggestions = [
  '这个平台能帮我做什么？',
  '阻抗是什么？和线宽线距怎么配合？',
  'MES系统有什么功能？给我一个功能总览',
  '工单从下达到入库涉及哪些表？按流程串一下',
]

function createThreadId() {
  const u = (getUserId() || getUsername() || 'anon').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 24)
  return `session-${u || 'anon'}-${Date.now()}`
}

function notifyHistoryUpdated() {
  window.dispatchEvent(new CustomEvent('mes-history-updated'))
}

async function copyMessage(content, index) {
  const text = stripStoppedNote(content || '')
  if (!text) return
  const ok = await copyTextToClipboard(text)
  if (!ok) return
  copiedIndex.value = index
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedIndex.value = -1
  }, 1500)
}

async function copyTextToClipboard(text) {
  const value = text || ''
  if (!value) return false
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    try {
      const ta = document.createElement('textarea')
      ta.value = value
      ta.style.position = 'fixed'
      ta.style.left = '-9999px'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      return true
    } catch {
      return false
    }
  }
}

async function onMessagesClick(e) {
  const btn = e.target?.closest?.('[data-code-copy]')
  if (!btn) return
  e.preventDefault()
  const wrap = btn.closest('.code-block-wrap')
  const codeEl = wrap?.querySelector('code')
  const text = codeEl?.textContent || ''
  if (!text) return
  const ok = await copyTextToClipboard(text)
  if (!ok) return
  const prev = btn.textContent
  btn.textContent = '已复制'
  btn.classList.add('is-copied')
  setTimeout(() => {
    btn.textContent = prev || '复制'
    btn.classList.remove('is-copied')
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

function promptInputMaxHeight() {
  // 长文本先撑开输入杠（接近图二），再超出才内部滚动
  if (typeof window === 'undefined') return 480
  return Math.max(240, Math.min(Math.round(window.innerHeight * 0.55), 560))
}

function autoResize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  const max = promptInputMaxHeight()
  const scroll = el.scrollHeight
  const next = Math.min(Math.max(scroll, 52), max)
  el.style.height = `${next}px`
  el.style.overflowY = scroll > max ? 'auto' : 'hidden'
}

function onPasteResize() {
  // paste 后内容写入略晚于事件，多拍一次保证撑开
  nextTick(() => {
    autoResize()
    requestAnimationFrame(() => autoResize())
  })
}

watch(input, () => {
  nextTick(() => autoResize())
})

function onEnterSend() {
  if (streaming.value) return
  send(input.value)
}

function looksLikeContinueIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /^(继续|接着(?:写|说|生成|分析)?|往下(?:写|说)?|继续(?:写|生成|说|分析|完成)?|再来|接着来|go\s*on|continue)([吧啊呀呢]?[.。!！…]*)$/i.test(
    t,
  )
}

/** 停止后兑现承诺类短句（来吧/好的），也走续写 enrich */
function looksLikeResumeConfirm(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /^(来吧|好的|好|可以|行|要|要的|贴一下|改一版|完整版|完整类|ok|yes|y)([吧啊呀呢]?[.。!！…]*)$/i.test(
    t,
  )
}

function looksLikeResumeIntent(text) {
  return looksLikeContinueIntent(text) || looksLikeResumeConfirm(text)
}

function stripStoppedNote(text) {
  return String(text || '')
    .replace(/\n*（已停止生成）\s*$/u, '')
    .trim()
}

/** 取最近一条「已停止」助手气泡 + 其前第一条非续写短句的用户原任务 */
function findStoppedResumeContext() {
  const list = messages.value || []
  for (let i = list.length - 2; i >= 0; i--) {
    const m = list[i]
    if (!m || m.role !== 'assistant') continue
    const raw = String(m.content || '')
    const stopped = Boolean(m.meta?.stopped) || /（已停止生成）/.test(raw)
    // 跳过已完成的后续答复，继续往前找停止气泡（支持连续「继续」）
    if (!stopped) continue

    let task = ''
    for (let j = i - 1; j >= 0; j--) {
      if (list[j]?.role !== 'user') continue
      const ut = String(list[j].content || '')
      // 跳过「继续 / 来吧」等短句，避免第二次继续绑错原任务
      if (looksLikeResumeIntent(ut)) continue
      task = ut
      break
    }
    const partial = stripStoppedNote(raw)
    const trivial = partial.length < 40
    return {
      task,
      partial,
      index: i,
      mode: trivial ? 'restart' : 'append',
      trivial,
    }
  }
  return null
}

/** 界面仍显示用户原话；续写/兑现短句且存在停止半截时附带指令 */
function enrichMessageForAgent(userText, resumeCtx) {
  const text = String(userText || '').trim()
  const wantsResume = looksLikeResumeIntent(text)
  const ctx = resumeCtx || (wantsResume ? findStoppedResumeContext() : null)
  if (!ctx || !wantsResume) return text

  const task = (ctx.task || '').slice(0, 8000)
  const partial = (ctx.partial || '').slice(0, 12000)

  if (ctx.mode === 'restart' || !partial) {
    const parts = [
      '【完整重答指令】用户要求继续，但上一轮在几乎未产出有效正文时就被停止。',
      '请针对【用户原任务】从头给出完整答复。',
      '硬约束：禁止声称「上文已覆盖 / 前面已说」任何内容；禁止从中间条目（如反例5）跳着写；必须完整覆盖用户要的分析/修复。',
      '注意：上一轮停止气泡会保留在会话中，你本轮是「继续」之后的新答复，请完整作答。',
    ]
    if (task) parts.push(`【用户原任务】\n${task}`)
    parts.push(`【用户本轮】\n${text}`)
    return parts.join('\n\n')
  }

  const parts = [
    '【续写指令】用户要求继续。上一轮停止气泡会保留；你本轮在「继续」之后新开一条答复。',
    '请严格从【已生成片段】末尾接着写，只补片段中尚未出现的内容。',
    '硬约束：禁止写「上文应已覆盖…」；片段里没写到的条目一律视为未写，必须补全；不要重复片段已有大段原文；不要自我介绍。',
  ]
  if (task) parts.push(`【用户原任务】\n${task}`)
  parts.push(`【已生成片段（请续写，勿丢）】\n${partial}`)
  parts.push(`【用户本轮】\n${text}`)
  return parts.join('\n\n')
}

function pushAssistantMessage({
  content,
  processItems,
  confirms,
  durationText,
  stopped = false,
}) {
  messages.value.push({
    role: 'assistant',
    content,
    process: processItems || [],
    confirms: confirms || [],
    processCollapsed: true,
    meta: {
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      durationText,
      stopped: Boolean(stopped),
    },
  })
}

async function stopStreaming() {
  if (!streaming.value) return
  const ctrl = streamAbort.value
  streamAbort.value = null
  // 先抬 requestId，丢弃后续迟到事件，再 abort
  activeRequestId += 1
  try {
    ctrl?.abort()
  } catch {
    /* ignore */
  }

  const sec = Math.max(1, Math.round((Date.now() - (streamStartedAt.value || Date.now())) / 1000))
  const durationText = streamDurationText.value || `${sec}s`
  const processItems = (streamProcess.value || []).filter(
    (i) => i.type === 'step' && i.id !== 'boot'
  )
  const confirms = (streamConfirms.value || []).map((c) => ({ ...c }))
  let finalContent = (streamContent.value || '').trimEnd()
  if (confirms.length) {
    const stable = buildImportSummaryMarkdown(confirms[0].preview)
    if (stable) finalContent = stable
  }
  const stoppedNote = '（已停止生成）'
  if (finalContent) {
    finalContent = `${finalContent}\n\n${stoppedNote}`
  } else {
    finalContent = stoppedNote
  }
  pushAssistantMessage({
    content: finalContent,
    processItems,
    confirms,
    durationText,
    stopped: true,
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
  if (threadId.value) {
    await attachPendingConfirms(threadId.value)
    await loadWriteAudit(threadId.value)
  }
  nextTick(() => inputEl.value?.focus())
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
    expires_at: item.expires_at,
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
    const byId = new Map(cards.map((c) => [c.action_id, c]))
    const attached = new Set()

    // 1) 只把「该消息已拥有的 action」合并回去，避免一笔 pending 把整队都挂到同一条
    for (const msg of messages.value) {
      if (msg.role !== 'assistant') continue
      const ownedIds = (msg.confirms || []).map((c) => c.action_id).filter(Boolean)
      if (!ownedIds.length) continue
      const mine = ownedIds.map((id) => byId.get(id)).filter(Boolean)
      if (!mine.length) continue
      msg.confirms = mergeConfirmCards(msg.confirms || [], mine)
      mine.forEach((c) => attached.add(c.action_id))
      const stable = buildImportSummaryMarkdown(mine[0]?.preview)
      if (stable && /尚未写入平台|确认卡片/.test(msg.content || '')) {
        msg.content = stable
      }
    }

    const leftover = cards.filter((c) => c.action_id && !attached.has(c.action_id))
    if (!leftover.length) {
      await persistSession()
      scrollToBottom()
      return
    }

    const stable = buildImportSummaryMarkdown(leftover[0]?.preview)

    // 2) 流式中：剩余挂到 streamConfirms
    if (streaming.value) {
      streamConfirms.value = mergeConfirmCards(streamConfirms.value, leftover)
      if (stable) {
        streamContent.value = stable
        streamAnswerPending.value = true
      }
      scrollToBottom()
      return
    }

    // 3) 最近助手消息可合并（导入文案 / 已有确认卡）
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const msg = messages.value[i]
      if (msg.role !== 'assistant') continue
      if ((msg.confirms || []).length || looksLikePendingImportMessage(msg.content)) {
        msg.confirms = mergeConfirmCards(msg.confirms || [], leftover)
        if (stable) msg.content = stable
        await persistSession()
        scrollToBottom()
        return
      }
      break
    }

    // 4) 单独插一条（可含多张确认卡）
    messages.value.push({
      role: 'assistant',
      content:
        leftover.length > 1
          ? `有 ${leftover.length} 笔待确认写操作，请逐一确认或取消：`
          : stable || '有待确认的写操作，请确认或取消：',
      confirms: leftover,
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
    ...(m.idePick ? { idePick: m.idePick } : {}),
    ...(m.gitPick ? { gitPick: m.gitPick } : {}),
  }))
}

async function persistSession({ required = false } = {}) {
  if (!threadId.value || messages.value.length === 0) {
    return true
  }
  try {
    await saveHistory(threadId.value, persistableMessages())
    notifyHistoryUpdated()
    return true
  } catch (e) {
    console.warn('保存会话失败', e)
    if (required) {
      const tip = '会话保存失败，上下文可能不同步。请检查网络后重试发送。'
      try {
        window.alert(tip)
      } catch {
        /* ignore */
      }
    }
    return false
  }
}

function syncThreadQuery(id) {
  if (route.query.thread === id) return
  router.replace({ path: '/', query: { thread: id } })
}

async function loadSession(id) {
  activeRequestId += 1
  try {
    streamAbort.value?.abort()
  } catch {
    /* ignore */
  }
  streamAbort.value = null
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
        meta: m.meta || {},
        process: m.process || [],
        confirms,
        ...(m.idePick ? { idePick: { ...m.idePick } } : {}),
        ...(m.gitPick ? { gitPick: { ...m.gitPick } } : {}),
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
    await loadWriteAudit(id)
  }
}

async function loadWriteAudit(tid) {
  if (!tid) {
    auditItems.value = []
    return
  }
  auditLoading.value = true
  try {
    const res = await fetchWriteAudit({ threadId: tid, limit: 20 })
    auditItems.value = res.data?.items || []
  } catch (e) {
    console.warn('拉取写操作审计失败', e)
    auditItems.value = []
  } finally {
    auditLoading.value = false
  }
}

function toggleAudit() {
  auditOpen.value = !auditOpen.value
  if (auditOpen.value) loadWriteAudit(threadId.value)
}

function auditEventLabel(ev) {
  const map = {
    write_pending: '待确认',
    write_confirmed: '已写入',
    write_cancelled: '已取消',
    write_expired: '已过期',
    write_failed: '失败',
    write_executing: '执行中',
  }
  return map[ev] || (ev || '事件').replace(/^write_/, '')
}

function auditMainText(it) {
  const tool = it?.tool || '写操作'
  const file =
    it?.args_summary?.file ||
    it?.preview_summary?.file ||
    it?.result_summary?.file ||
    ''
  const entity =
    it?.preview_summary?.target_entity ||
    it?.result_summary?.target_entity ||
    ''
  const bits = [tool]
  if (entity) bits.push(String(entity))
  if (file) bits.push(String(file))
  if (it?.result_summary?.error) bits.push(String(it.result_summary.error).slice(0, 40))
  return bits.join(' · ')
}

function formatAuditTime(ts) {
  const n = Number(ts)
  if (!Number.isFinite(n) || n <= 0) return ''
  try {
    return new Date(n * 1000).toLocaleString()
  } catch {
    return ''
  }
}

function startNewChat() {
  activeRequestId += 1
  try {
    streamAbort.value?.abort()
  } catch {
    /* ignore */
  }
  streamAbort.value = null
  const id = createThreadId()
  threadId.value = id
  messages.value = []
  streamContent.value = ''
  streamProcess.value = []
  streamConfirms.value = []
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamAnswerPending.value = false
  auditOpen.value = false
  auditItems.value = []
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


function looksLikeCodeReview(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /审核代码|代码审核|代码审查|审查代码|检查代码|code\s*review|review\s+(this\s+)?code|帮我审(一下|下)?(代码|工程|项目)/i.test(
    t
  )
}

/** 消息里已有粘贴源码围栏：走贴码车道，不弹 Git/IDE 选卡 */
function hasPastedSourceFence(text) {
  return /```[\w.-]*\n[\s\S]{40,}?```/.test(String(text || ''))
}

/** 从自然语言中抽出干净的公开 HTTPS 仓库地址（去掉尾部中文/标点） */
function extractGitRepoUrl(text) {
  const t = String(text || '')
  // 仅匹配 URL 安全字符，避免「.git仓库代码」一类粘连
  const hostRe =
    /https:\/\/(?:github\.com|gitlab\.com|gitee\.com|bitbucket\.org)\/[A-Za-z0-9_.\-]+\/[A-Za-z0-9_.\-]+(?:\.git)?/i
  const genericRe = /https:\/\/[A-Za-z0-9.\-]+(?:\/[A-Za-z0-9_.\-]+)+\.git\b/i
  const m = t.match(hostRe) || t.match(genericRe)
  if (!m) return ''
  let url = String(m[0]).replace(/\/+$/, '')
  const gitIdx = url.toLowerCase().indexOf('.git')
  if (gitIdx >= 0) url = url.slice(0, gitIdx + 4)
  return url
}

function looksLikeGitRepoReview(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (extractGitRepoUrl(t)) return true
  return /(?:审|审核|审查|检查).{0,16}(?:git|Git|远程)?\s*仓库|(?:git|Git)\s*仓库.{0,12}(?:审|审核|审查)|review\s+(?:this\s+)?(?:git\s+)?repo|审核\s*https:\/\//i.test(
    t
  )
}

function hasPendingIdePick() {
  return messages.value.some((m) => m.idePick && m.idePick.status === 'pending')
}

function hasPendingGitPick() {
  return messages.value.some((m) => m.gitPick && m.gitPick.status === 'pending')
}

async function fetchIdeWorkspaces() {
  try {
    const resp = await fetchIdeBridgeStatus()
    const data = resp.data || {}
    if (!data.feature_enabled || !data.online) return []
    let list = Array.isArray(data.recent_workspaces)
      ? data.recent_workspaces.filter((w) => w?.path)
      : []
    if (!list.length && data.workspace_root) {
      const name =
        String(data.workspace_root).split(/[/\\]/).filter(Boolean).pop() || data.workspace_root
      list = [{ path: data.workspace_root, name, current: true }]
    }
    return list
  } catch {
    return []
  }
}

/** 强制清掉卡住的流，避免后续 startAssistantStream 被静默跳过 */
function forceResetStreaming() {
  try {
    streamAbort.value?.abort()
  } catch {
    /* ignore */
  }
  activeRequestId += 1
  streamAbort.value = null
  streaming.value = false
  streamContent.value = ''
  streamProcess.value = []
  streamConfirms.value = []
  streamAnswerPending.value = false
  streamDurationText.value = ''
}

function buildIdeReviewAgentMessage(content, selected) {
  const base = String(content || '').trim() || '请审核已选本机工程并输出代码审核报告'
  if (!selected) return base
  return `${base}\n\n【本机工程已确认】请立刻审核工程：${selected}`
}

async function beginIdeReviewStream(msg, { selected, content, files }) {
  // 正在跑就不要连点：并发会打坏 AsyncSqlite checkpointer，导致空报告
  if (streaming.value && streamAbort.value) {
    return false
  }
  if (msg?.idePick) {
    msg.idePick = { ...msg.idePick, status: 'confirmed', selected: selected || msg.idePick.selected }
  }
  // 仅清理卡死状态；有进行中的请求才 abort
  if (streamAbort.value) {
    forceResetStreaming()
    await nextTick()
  } else {
    streaming.value = false
    streamContent.value = ''
    streamProcess.value = []
    streamConfirms.value = []
    streamAnswerPending.value = false
  }
  // 先挂上 streaming UI，再 fetch
  streaming.value = true
  streamProcess.value = [{
    id: 'boot',
    type: 'step',
    state: 'running',
    title: selected ? `正在审核本机工程…` : '正在审核…',
  }]
  streamProcessCollapsed.value = false
  streamStartedAt.value = Date.now()
  scrollToBottom()
  await nextTick()

  const agentMessage = buildIdeReviewAgentMessage(content, selected)
  const started = await startAssistantStream(agentMessage, files, selected || null, null, {
    force: true,
  })
  if (!started) {
    streaming.value = false
    streamProcess.value = []
    messages.value.push({
      role: 'assistant',
      content: '[错误] 未能发起代码审核请求。请刷新页面后新开对话，再说一次「审核代码」。',
    })
    await persistSession()
    return false
  }
  return true
}

async function onIdePickResolved(msg, payload) {
  if (!msg?.idePick || !payload) return
  if (msg.idePick.status && msg.idePick.status !== 'pending') return

  const selected = payload.selected || msg.idePick.selected || ''
  let content = msg.idePick.pendingContent || ''
  const files = Array.isArray(msg.idePick.pendingFiles) ? [...msg.idePick.pendingFiles] : []

  if (!content) {
    const idx = messages.value.indexOf(msg)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i]?.role === 'user') {
        content = String(messages.value[i].content || '').trim()
        break
      }
    }
  }
  if (!content) content = '请审核已选本机工程并输出代码审核报告'

  msg.idePick = {
    ...msg.idePick,
    status: payload.status,
    selected,
    pendingContent: content,
  }
  void persistSession()
  scrollToBottom()

  if (payload.status !== 'confirmed') return

  try {
    await beginIdeReviewStream(msg, { selected, content, files })
  } catch (e) {
    console.error('ide pick start stream failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 确认工程后未能开始审核：${e?.message || e}`,
    })
    void persistSession()
  }
}

/** 已确认工程卡上的「重新开始审核」 */
async function retryIdeReview(msg) {
  if (!msg?.idePick) return
  if (msg.idePick.status === 'cancelled') return
  const selected = msg.idePick.selected || ''
  if (!selected) {
    messages.value.push({
      role: 'assistant',
      content: '[错误] 未找到工程路径，请新开对话后重新发送「审核代码」。',
    })
    return
  }
  let content = msg.idePick.pendingContent || ''
  if (!content) {
    const idx = messages.value.indexOf(msg)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i]?.role === 'user') {
        content = String(messages.value[i].content || '').trim()
        break
      }
    }
  }
  if (!content) content = '请审核已选本机工程并输出代码审核报告'
  msg.idePick = { ...msg.idePick, status: 'confirmed', pendingContent: content, selected }
  const files = Array.isArray(msg.idePick.pendingFiles) ? [...msg.idePick.pendingFiles] : []
  try {
    await beginIdeReviewStream(msg, { selected, content, files })
  } catch (e) {
    console.error('ide review retry failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 重新开始审核失败：${e?.message || e}`,
    })
    void persistSession()
  }
}

function buildGitReviewAgentMessage(content, repoUrl, ref) {
  const base = String(content || '').trim() || '请审核已确认的公开 Git 仓库并输出代码审核报告'
  if (!repoUrl) return base
  const refPart = ref ? `（分支/ref：${ref}）` : ''
  return `${base}\n\n【Git仓库已确认】请立刻审核仓库：${repoUrl}${refPart}`
}

async function beginGitReviewStream(msg, { repoUrl, ref, content, files }) {
  if (streaming.value && streamAbort.value) {
    return false
  }
  if (msg?.gitPick) {
    msg.gitPick = {
      ...msg.gitPick,
      status: 'confirmed',
      repoUrl: repoUrl || msg.gitPick.repoUrl,
      ref: ref || msg.gitPick.ref || '',
    }
  }
  if (streamAbort.value) {
    forceResetStreaming()
    await nextTick()
  } else {
    streaming.value = false
    streamContent.value = ''
    streamProcess.value = []
    streamConfirms.value = []
    streamAnswerPending.value = false
  }
  streaming.value = true
  streamProcess.value = [{
    id: 'boot',
    type: 'step',
    state: 'running',
    title: repoUrl ? '正在审核公开 Git 仓库…' : '正在审核…',
  }]
  streamProcessCollapsed.value = false
  streamStartedAt.value = Date.now()
  scrollToBottom()
  await nextTick()

  const agentMessage = buildGitReviewAgentMessage(content, repoUrl, ref)
  const started = await startAssistantStream(agentMessage, files, null, null, {
    force: true,
    gitRepoUrl: repoUrl || '',
    gitRef: ref || '',
  })
  if (!started) {
    streaming.value = false
    streamProcess.value = []
    messages.value.push({
      role: 'assistant',
      content: '[错误] 未能发起 Git 仓库审核请求。请刷新页面后新开对话，再贴一次仓库地址。',
    })
    await persistSession()
    return false
  }
  return true
}

async function onGitPickResolved(msg, payload) {
  if (!msg?.gitPick || !payload) return
  if (msg.gitPick.status && msg.gitPick.status !== 'pending') return

  const repoUrl = payload.repoUrl || msg.gitPick.repoUrl || ''
  const ref = payload.ref || msg.gitPick.ref || ''
  let content = msg.gitPick.pendingContent || ''
  const files = Array.isArray(msg.gitPick.pendingFiles) ? [...msg.gitPick.pendingFiles] : []

  if (!content) {
    const idx = messages.value.indexOf(msg)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i]?.role === 'user') {
        content = String(messages.value[i].content || '').trim()
        break
      }
    }
  }
  if (!content) content = '请审核已确认的公开 Git 仓库并输出代码审核报告'

  msg.gitPick = {
    ...msg.gitPick,
    status: payload.status,
    repoUrl,
    ref,
    pendingContent: content,
  }
  void persistSession()
  scrollToBottom()

  if (payload.status !== 'confirmed') return

  try {
    await beginGitReviewStream(msg, { repoUrl, ref, content, files })
  } catch (e) {
    console.error('git pick start stream failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 确认仓库后未能开始审核：${e?.message || e}`,
    })
    void persistSession()
  }
}

async function retryGitReview(msg) {
  if (!msg?.gitPick) return
  if (msg.gitPick.status === 'cancelled') return
  const repoUrl = msg.gitPick.repoUrl || ''
  if (!repoUrl) {
    messages.value.push({
      role: 'assistant',
      content: '[错误] 未找到仓库地址，请新开对话后重新发送仓库 URL。',
    })
    return
  }
  const ref = msg.gitPick.ref || ''
  let content = msg.gitPick.pendingContent || ''
  if (!content) {
    const idx = messages.value.indexOf(msg)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i]?.role === 'user') {
        content = String(messages.value[i].content || '').trim()
        break
      }
    }
  }
  if (!content) content = '请审核已确认的公开 Git 仓库并输出代码审核报告'
  msg.gitPick = { ...msg.gitPick, status: 'confirmed', pendingContent: content, repoUrl, ref }
  const files = Array.isArray(msg.gitPick.pendingFiles) ? [...msg.gitPick.pendingFiles] : []
  try {
    await beginGitReviewStream(msg, { repoUrl, ref, content, files })
  } catch (e) {
    console.error('git review retry failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 重新开始 Git 审核失败：${e?.message || e}`,
    })
    void persistSession()
  }
}

async function send(text) {
  const content = text || input.value.trim()
  const files = attachedFiles.value
  if ((!content && files.length === 0) || streaming.value) return
  if (hasPendingIdePick() || hasPendingGitPick()) return

  if (!threadId.value) {
    threadId.value = createThreadId()
    syncThreadQuery(threadId.value)
  }

  // 编辑重发：截断该条及之后的消息，再作为新一轮发送
  if (editingFromIndex.value >= 0) {
    messages.value = messages.value.slice(0, editingFromIndex.value)
    editingFromIndex.value = -1
  }

  input.value = ''
  if (inputEl.value) {
    inputEl.value.style.height = 'auto'
  }

  const displayContent = buildUserDisplayContent(content, files)
  const filesSnapshot = [...files]
  messages.value.push({ role: 'user', content: displayContent, files: filesSnapshot })
  attachedFiles.value = []
  scrollToBottom()
  const saved = await persistSession({ required: true })
  if (!saved) {
    // 回滚刚写入的 user，避免 UI 与服务端历史不一致还继续聊
    messages.value.pop()
    input.value = content
    nextTick(() => autoResize())
    return
  }

  // 贴码优先：有源码围栏则直连 Agent，不弹 Git/IDE 选卡
  if (!hasPastedSourceFence(content) && looksLikeGitRepoReview(content)) {
    const repoUrl = extractGitRepoUrl(content)
    messages.value.push({
      role: 'assistant',
      content: '',
      gitPick: {
        id: `git-pick-${Date.now()}`,
        status: 'pending',
        repoUrl,
        ref: '',
        pendingContent: content,
        pendingFiles: filesSnapshot,
      },
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  if (!hasPastedSourceFence(content) && looksLikeCodeReview(content)) {
    const workspaces = await fetchIdeWorkspaces()
    if (workspaces.length) {
      const selected = workspaces.find((w) => w.current)?.path || workspaces[0].path
      messages.value.push({
        role: 'assistant',
        content: '',
        idePick: {
          id: `ide-pick-${Date.now()}`,
          status: 'pending',
          workspaces,
          selected,
          pendingContent: content,
          pendingFiles: filesSnapshot,
        },
        process: [],
        processCollapsed: true,
      })
      await persistSession()
      scrollToBottom()
      return
    }
  }

  const resumeCtx = looksLikeResumeIntent(content) ? findStoppedResumeContext() : null
  await startAssistantStream(
    enrichMessageForAgent(content, resumeCtx),
    filesSnapshot,
    null,
    resumeCtx,
  )
}

async function startAssistantStream(
  content,
  files,
  ideWorkspaceRoot,
  resumeCtx = null,
  opts = null,
) {
  const force = Boolean(opts && opts.force)
  if (streaming.value && !force) return false
  if (streaming.value && force) {
    // 已有进行中的 fetch 才强杀；否则保留 beginIdeReviewStream 刚挂上的 boot UI
    if (streamAbort.value) {
      forceResetStreaming()
    } else {
      streaming.value = false
    }
  }
  if (!threadId.value) {
    threadId.value = createThreadId()
    syncThreadQuery(threadId.value)
  }

  const requestId = ++activeRequestId
  const currentThread = threadId.value
  const abortCtrl = new AbortController()
  streamAbort.value = abortCtrl

  streaming.value = true
  streamContent.value = ''
  streamAnswerPending.value = false
  streamConfirms.value = []
  // 本地先挂一条「分析中」，后续真实步骤会替换掉
  const gitRepoUrl = String((opts && opts.gitRepoUrl) || '').trim()
  const gitRef = String((opts && opts.gitRef) || '').trim()

  streamProcess.value = [{
    id: 'boot',
    type: 'step',
    state: 'running',
    title: resumeCtx
      ? '继续生成…'
      : ideWorkspaceRoot
        ? '正在审核本机工程…'
        : gitRepoUrl
          ? '正在审核公开 Git 仓库…'
          : '分析问题…',
  }]
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamStartedAt.value = Date.now()
  scrollToBottom()

  let stepRevealChain = Promise.resolve()
  let flushStepsNow = false
  let streamGotError = false
  const STEP_GAP_MS = 150

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

  const applyStep = (event) => {
    const id = event.id || `tool-${event.tool || event.title}`
    const steps = streamProcess.value.filter((i) => i.type === 'step' && i.id !== 'boot')
    const isEnd =
      event.phase === 'end' ||
      event.state === 'done' ||
      event.state === 'error' ||
      event.state === 'waiting'
    // 严格按 run_id 对齐；禁止 start 用「同工具 running」互吞（否则分批 9/10 会乱序）
    let idx = steps.findIndex((i) => i.id === id)
    if (idx < 0 && isEnd && event.tool) {
      idx = steps.findIndex((i) => i.tool === event.tool && i.state === 'running')
    }
    const prev = idx >= 0 ? steps[idx] : null
    // end 若兜底命中了 running 卡，保留原 id，避免与后续 start 的 run_id 错位
    const stableId = prev && isEnd && prev.id ? prev.id : id
    const item = {
      id: stableId,
      type: 'step',
      tool: event.tool,
      phase: event.phase,
      state: event.state || (event.phase === 'end' ? (event.ok === false ? 'error' : 'done') : 'running'),
      title: event.title || prev?.title || '',
      args: event.args || prev?.args || '',
      detail: event.detail || prev?.detail || '',
      preview: Array.isArray(event.preview) ? event.preview : (prev?.preview || []),
      ok: event.ok,
      batch_index:
        event.batch_index != null
          ? event.batch_index
          : prev?.batch_index,
    }
    if (idx >= 0) steps[idx] = { ...steps[idx], ...item }
    else steps.push(item)
    streamProcess.value = steps
  }

  const enqueueStep = (event) => {
    // start：错峰露出；分批读写工具不加延迟，避免同工具多 start 交错
    const isBatchTool = /read_batch|list_source_files/i.test(String(event.tool || ''))
    const gap =
      !isBatchTool && (event.phase === 'start' || event.state === 'running') ? STEP_GAP_MS : 0
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
      expires_at: event.expires_at,
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
    let extraPageContext = null
    if (ideWorkspaceRoot) {
      extraPageContext = { ide_workspace_root: ideWorkspaceRoot }
    } else if (gitRepoUrl) {
      extraPageContext = { git_repo_url: gitRepoUrl }
      if (gitRef) extraPageContext.git_ref = gitRef
    }
    const result = await streamMessage(
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
          pushAssistantMessage({
            content: finalContent,
            processItems,
            confirms,
            durationText,
            stopped: false,
          })
        } else if ((ideWorkspaceRoot || gitRepoUrl) && !streamGotError) {
          // 审核流结束却无正文：必须给用户可见反馈，避免只剩确认卡
          pushAssistantMessage({
            content:
              '[错误] 本轮未生成审核正文。请点「重新开始审核」再试一次。',
            processItems: [],
            confirms: [],
            durationText,
            stopped: false,
          })
        }
        streamContent.value = ''
        streamProcess.value = []
        streamConfirms.value = []
        streamProcessCollapsed.value = false
        streamDurationText.value = ''
        streamAnswerPending.value = false
        streaming.value = false
        streamAbort.value = null
        scrollToBottom()
        await persistSession()
        await attachPendingConfirms(currentThread)
        await loadWriteAudit(currentThread)
      },
      async (err) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        streamGotError = true
        flushStepsNow = true
        await stepRevealChain
        const errText = typeof err === 'string' ? err : (err?.message || err)
        pushAssistantMessage({
          content: '[错误] 请求失败：' + errText,
          processItems: (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
          confirms: (streamConfirms.value || []).map((c) => ({ ...c })),
          durationText: streamDurationText.value || '',
          stopped: false,
        })
        streamContent.value = ''
        streamProcess.value = []
        streamConfirms.value = []
        streamProcessCollapsed.value = false
        streamDurationText.value = ''
        streamAnswerPending.value = false
        streaming.value = false
        streamAbort.value = null
        scrollToBottom()
        await persistSession()
        await attachPendingConfirms(currentThread)
        await loadWriteAudit(currentThread)
      },
      filePaths,
      extraPageContext,
      abortCtrl.signal,
    )
    // abort 时 streamMessage 不抛错也不调 onDone，这里必须清掉 streaming，否则后续审核会被静默跳过
    if (
      result?.aborted &&
      requestId === activeRequestId &&
      threadId.value === currentThread &&
      streaming.value
    ) {
      streamContent.value = ''
      streamProcess.value = []
      streamConfirms.value = []
      streamProcessCollapsed.value = false
      streamDurationText.value = ''
      streamAnswerPending.value = false
      streaming.value = false
      streamAbort.value = null
    }
    return true
  } catch (err) {
    if (requestId !== activeRequestId || threadId.value !== currentThread) return false
    if (err?.name === 'AbortError') {
      streamContent.value = ''
      streamProcess.value = []
      streamConfirms.value = []
      streamProcessCollapsed.value = false
      streamDurationText.value = ''
      streamAnswerPending.value = false
      streaming.value = false
      streamAbort.value = null
      return false
    }
    pushAssistantMessage({
      content: '[错误] 连接服务器失败，请确认服务端已启动',
      processItems: (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
      confirms: (streamConfirms.value || []).map((c) => ({ ...c })),
      durationText: streamDurationText.value || '',
      stopped: false,
    })
    streamContent.value = ''
    streamProcess.value = []
    streamConfirms.value = []
    streamProcessCollapsed.value = false
    streamDurationText.value = ''
    streamAnswerPending.value = false
    streaming.value = false
    streamAbort.value = null
    scrollToBottom()
    await persistSession()
    await attachPendingConfirms(currentThread)
    await loadWriteAudit(currentThread)
    return false
  }
}

function applyConfirmResolved(list, payload) {
  if (!Array.isArray(list) || !payload?.action_id) return list || []
  const status = payload.status
  // 确认成功 / 取消 / 过期：移除卡片（过期不可重试）
  if (status === 'confirmed' || status === 'cancelled' || status === 'expired') {
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

async function onConfirmResolved(msg, payload) {
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
  } else if (payload?.status === 'expired') {
    msg.content = finalizeWriteMessage(
      msg.content,
      '确认已过期，未写入平台。请重新发起导入后再确认。',
      preview
    )
    collapseImportDuplicateMessages(msg)
  } else if (payload?.status === 'failed' && payload?.error) {
    const tip = `写入失败：${payload.error}（可重试）`
    if (msg.content && !msg.content.includes(tip)) {
      msg.content = `${msg.content}\n\n${tip}`
    } else if (!msg.content) {
      msg.content = tip
    }
  }
  await persistSession()
  void loadWriteAudit(threadId.value)
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
    } else if (payload?.status === 'expired') {
      streamContent.value = finalizeWriteMessage(
        streamContent.value,
        '确认已过期，未写入平台。请重新发起导入后再确认。',
        preview
      )
    } else if (payload?.status === 'failed') {
      const tip = `写入失败：${payload.error || ''}（可重试）`
      streamContent.value = (streamContent.value || '') + (streamContent.value ? `\n\n${tip}` : tip)
    }
    loadWriteAudit(threadId.value)
    return
  }

  // 流已结束、卡片已落入 messages：按 action_id 更新，避免确认结果丢失导致二次写入
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const msg = messages.value[i]
    if (msg.role !== 'assistant') continue
    if (!(msg.confirms || []).some((c) => c.action_id === payload.action_id)) continue
    void onConfirmResolved(msg, payload)
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

  html = html.replace(/```(\w*)\r?\n([\s\S]*?)```/g, (_, lang, code) => {
    const label = (lang || '').trim()
    const langHtml = label
      ? `<span class="code-lang">${label}</span>`
      : '<span class="code-lang"></span>'
    return (
      `<div class="code-block-wrap">` +
      `<div class="code-block-bar">${langHtml}` +
      `<button type="button" class="code-copy-btn" data-code-copy title="复制代码">复制</button>` +
      `</div>` +
      `<pre class="code-block"><code>${code}</code></pre>` +
      `</div>`
    )
  })
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
  gap: 28px;
  padding: 24px;
  text-align: center;
}

.empty-title {
  font-size: 32px;
  font-weight: 650;
  letter-spacing: -0.4px;
  color: var(--ui-text);
  line-height: 1.25;
  margin: 0;
}

.empty-loading {
  margin: 0;
  font-size: 15px;
  color: var(--ui-text-dim);
}

.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 100%;
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
  background: rgba(145, 94, 246, 0.08);
  border-color: #915ef6;
  color: #915ef6;
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

.msg-content {
  display: flex;
  flex-direction: column;
  max-width: min(100%, 920px);
  align-items: flex-start;
  position: relative;
}

.message.assistant .msg-content {
  width: 100%;
}

.message.user .msg-content {
  align-items: flex-end;
  max-width: min(100%, 720px);
}

/* 消息体顶部品牌行（对齐参考：头像 + 名称） */
.msg-brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  align-self: flex-start;
}

.msg-brand-name {
  font-size: 14px;
  font-weight: 650;
  color: var(--ui-text);
  letter-spacing: -0.2px;
  line-height: 1;
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
.message.assistant .msg-content :deep(.write-confirm),
.message.assistant .msg-content :deep(.ide-ws-pick) {
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
:deep(.code-block-wrap) {
  position: relative;
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #1e293b;
  border: 1px solid #334155;
}

:deep(.code-block-bar) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 10px 0 12px;
  min-height: 32px;
}

:deep(.code-lang) {
  font-size: 11px;
  color: #94a3b8;
  font-family: var(--font-mono);
  text-transform: lowercase;
}

:deep(.code-copy-btn) {
  flex-shrink: 0;
  margin-left: auto;
  border: none;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 12px;
  line-height: 1.4;
  color: #cbd5e1;
  background: rgba(148, 163, 184, 0.15);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

:deep(.code-copy-btn:hover) {
  background: rgba(148, 163, 184, 0.28);
  color: #f8fafc;
}

:deep(.code-copy-btn.is-copied) {
  color: #86efac;
  background: rgba(34, 197, 94, 0.18);
}

:deep(.code-block) {
  background: transparent;
  color: #e2e8f0;
  padding: 8px 16px 12px;
  border-radius: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  max-width: 100%;
  margin: 0;
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

.audit-strip {
  max-width: 100%;
  margin: 0 auto 10px;
}

.audit-toggle {
  border: none;
  background: transparent;
  color: var(--ui-text-dim);
  font-size: 12px;
  padding: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.audit-toggle:hover {
  color: var(--ui-text);
}

.audit-count {
  min-width: 16px;
  height: 16px;
  padding: 0 5px;
  border-radius: 8px;
  background: color-mix(in srgb, var(--ui-text-dim) 18%, transparent);
  font-size: 11px;
  line-height: 16px;
  text-align: center;
}

.audit-panel {
  margin-top: 8px;
  max-height: 140px;
  overflow: auto;
  border-top: 1px solid color-mix(in srgb, var(--ui-border, #ddd) 70%, transparent);
  padding-top: 8px;
}

.audit-empty {
  font-size: 12px;
  color: var(--ui-text-dim);
}

.audit-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.audit-item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
  color: var(--ui-text-dim);
}

.audit-event {
  font-weight: 600;
  color: var(--ui-text);
}

.audit-event.ev-confirmed { color: #1a7f37; }
.audit-event.ev-cancelled { color: #9a6700; }
.audit-event.ev-expired { color: #cf222e; }
.audit-event.ev-failed { color: #cf222e; }
.audit-event.ev-pending { color: #0969da; }

.audit-main {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-time {
  white-space: nowrap;
  opacity: 0.85;
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
  max-height: min(55vh, 560px);
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
  overflow-y: auto;
  overscroll-behavior: contain;
  field-sizing: content;
}

.prompt-input::placeholder {
  color: var(--ui-text-dim);
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

.new-chat-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.send-btn,
.stop-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  color: #fff;
  cursor: pointer;
  transition: all 0.15s;
}

.send-btn {
  background: var(--ui-accent);
}

.stop-btn {
  background: #64748b;
}

.send-btn:hover:not(:disabled),
.stop-btn:hover {
  opacity: 0.9;
}

.send-btn:active:not(:disabled),
.stop-btn:active {
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
