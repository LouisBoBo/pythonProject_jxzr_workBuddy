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
          <div v-if="msg.role === 'user' && msg.files?.length" class="msg-attachments">
            <template v-for="(f, fi) in msg.files" :key="f.id || fi">
              <button
                v-if="f.kind === 'image' && imagePreviewSrc(f)"
                type="button"
                class="msg-attach-thumb-btn"
                title="点击放大"
                @click="openImageLightbox(f)"
              >
                <img
                  class="msg-attach-thumb"
                  :src="imagePreviewSrc(f)"
                  :alt="f.name || '截图'"
                />
              </button>
              <button
                v-else-if="f.kind === 'image'"
                type="button"
                class="msg-attach-thumb-btn msg-attach-loading"
                title="点击加载并放大"
                @click="openImageLightbox(f)"
              >
                <span class="msg-attach-placeholder">{{ f.name || '截图' }} · 点击查看</span>
              </button>
              <span v-else-if="f.kind !== 'image'" class="msg-attach-file">{{ f.name }}</span>
            </template>
          </div>
          <div class="msg-body" v-if="msg.content" v-html="renderMarkdown(msg.content)"></div>
          <WriteConfirmCard
            v-for="card in (msg.confirms || [])"
            :key="card.action_id"
            :card="card"
            @resolved="(payload) => onConfirmResolved(msg, payload)"
          />
          <IdeWorkspacePickCard
            v-if="msg.idePick && !msg.codeReviewPick"
            :card="msg.idePick"
            @resolved="(payload) => onIdePickResolved(msg, payload)"
            @retry="() => retryIdeReview(msg)"
          />
          <GitRepoPickCard
            v-if="msg.gitPick && !msg.codeReviewPick"
            :card="msg.gitPick"
            @resolved="(payload) => onGitPickResolved(msg, payload)"
            @retry="() => retryGitReview(msg)"
          />
          <CodeReviewSourcePickCard
            v-if="msg.codeReviewPick"
            :card="msg.codeReviewPick"
            @resolved="(payload) => onCodeReviewSourceResolved(msg, payload)"
            @retry="() => retryCodeReviewSource(msg)"
          />
          <CursorDevRepoAnchorCard
            v-if="msg.cursorDevAnchor"
            :card="msg.cursorDevAnchor"
            @resolved="(payload) => onCursorDevAnchorResolved(msg, payload)"
          />
          <CursorDevOptionsCard
            v-if="msg.cursorDevOptions"
            :card="msg.cursorDevOptions"
            @resolved="(payload) => onCursorDevOptionsResolved(msg, payload)"
          />
          <CursorDevRepoPickCard
            v-if="msg.cursorDevPick"
            :card="msg.cursorDevPick"
            @resolved="(payload) => onCursorDevPickResolved(msg, payload)"
          />
          <CursorDevMergeGuideCard
            v-if="msg.mergeGuide"
            :guide="msg.mergeGuide"
          />
          <ScreenshotIntentCard
            v-if="msg.intentClarify"
            :card="msg.intentClarify"
            @resolved="(payload) => onScreenshotIntentResolved(msg, payload)"
          />
          <div class="msg-actions" v-if="msg.content || msg.files?.length || (msg.confirms || []).length || msg.idePick || msg.gitPick || msg.codeReviewPick || msg.cursorDevPick || msg.cursorDevOptions || msg.cursorDevAnchor || msg.mergeGuide || msg.intentClarify">
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
            <span v-else v-html="renderMarkdown(hideCursorDevPropose(streamContent))"></span>
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
              :class="{
                uploading: file.status === 'uploading',
                error: file.status === 'error',
                image: file.kind === 'image',
              }"
            >
              <img
                v-if="file.kind === 'image' && file.previewDataUrl"
                class="file-thumb"
                :src="file.previewDataUrl"
                :alt="file.name"
                title="点击放大"
                @click.stop="openImageLightbox(file)"
              />
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
            :placeholder="streaming ? '生成中可继续编辑下一条，或点右侧停止…' : '描述你想做的事情；也可 Ctrl+V 粘贴截图，让我结合画面帮你处理'"
            rows="1"
            @keydown.enter.exact.prevent="onEnterSend"
            @keydown.enter.shift.exact="input += '\n'"
            @input="autoResize"
            @paste="onPaste"
          ></textarea>
          <div class="prompt-actions">
            <input
              ref="fileInput"
              type="file"
              accept=".csv,.xlsx,.xls,.json,.jsonl,.log,.txt,.yaml,.yml,.md,image/*,.png,.jpg,.jpeg,.webp,.gif"
              style="display: none"
              @change="handleFileUpload"
            />
            <button
              class="new-chat-btn"
              @click="fileInput.click()"
              title="上传文件或截图"
              :disabled="streaming"
            >
              <svg width="15" height="15" viewBox="0 0 15 15" fill="none"><path d="M7.5 1v13M1 7.5h13" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
            </button>
            <button
              v-if="streaming"
              class="stop-btn"
              type="button"
              :title="activeCursorDevJobId ? '停止写码' : '停止生成'"
              @click="stopStreaming"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                <rect x="2" y="2" width="8" height="8" rx="1.5" fill="currentColor"/>
              </svg>
            </button>
            <button
              v-else
              class="send-btn"
              :disabled="!canSend"
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

  <Teleport to="body">
    <div
      v-if="imageLightbox.open"
      class="img-lightbox"
      role="dialog"
      aria-modal="true"
      aria-label="图片预览"
      tabindex="-1"
      @click.self="closeImageLightbox"
    >
      <button type="button" class="img-lightbox-close" title="关闭" @click="closeImageLightbox">×</button>
      <img
        class="img-lightbox-img"
        :src="imageLightbox.src"
        :alt="imageLightbox.alt || '截图预览'"
        @click.stop
      />
      <p v-if="imageLightbox.alt" class="img-lightbox-caption">{{ imageLightbox.alt }}</p>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { streamMessage, uploadFile, saveHistory, getHistoryDetail, fetchPendingWrites, fetchWriteAudit, fetchIdeBridgeStatus, fetchCursorDevStatus, fetchCursorDevRepos, fetchCursorDevRepoInspect, createCursorDevJob, streamCursorDevJob, cancelCursorDevJob, followupCursorDevJob, getCursorDevJob } from '../api.js'
import ProcessPanel from '../components/ProcessPanel.vue'
import WriteConfirmCard from '../components/WriteConfirmCard.vue'
import IdeWorkspacePickCard from '../components/IdeWorkspacePickCard.vue'
import GitRepoPickCard from '../components/GitRepoPickCard.vue'
import CodeReviewSourcePickCard from '../components/CodeReviewSourcePickCard.vue'
import CursorDevRepoPickCard from '../components/CursorDevRepoPickCard.vue'
import CursorDevMergeGuideCard from '../components/CursorDevMergeGuideCard.vue'
import CursorDevRepoAnchorCard from '../components/CursorDevRepoAnchorCard.vue'
import CursorDevOptionsCard from '../components/CursorDevOptionsCard.vue'
import ScreenshotIntentCard from '../components/ScreenshotIntentCard.vue'
import AiAvatarIcon from '../components/AiAvatarIcon.vue'
import { getUsername, getUserId, authHeaders } from '../auth.js'

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
const canSend = computed(() => {
  if (streaming.value) return false
  const files = attachedFiles.value
  if (files.some((f) => f.status === 'uploading' || f.status === 'error')) return false
  return Boolean(input.value.trim()) || files.some((f) => f.status === 'done')
})
const imageLightbox = ref({ open: false, src: '', alt: '', objectUrl: '' })

function imagePreviewSrc(file) {
  if (!file) return ''
  return String(file.previewDataUrl || file.previewUrl || '').trim()
}

function closeImageLightbox() {
  const prev = imageLightbox.value?.objectUrl
  if (prev && String(prev).startsWith('blob:')) {
    try {
      URL.revokeObjectURL(prev)
    } catch {
      /* ignore */
    }
  }
  imageLightbox.value = { open: false, src: '', alt: '', objectUrl: '' }
}

function resolveUploadPreviewUrl(file) {
  if (!file) return ''
  const direct = String(file.previewUrl || '').trim()
  if (direct) return direct
  const path = String(file.path || file.saved_name || '').trim()
  if (!path) return ''
  const name = path.includes('/') ? path.split('/').pop() : path
  if (!name || name.includes('..')) return ''
  return `/api/uploads/${name}`
}

async function openImageLightbox(file) {
  if (!file) return
  let src = imagePreviewSrc(file)
  let objectUrl = ''
  // 历史会话可能只剩 path / previewUrl（需鉴权），点击时拉取原图
  const apiUrl = resolveUploadPreviewUrl(file)
  if ((!src || src.startsWith('/api/')) && apiUrl) {
    try {
      const resp = await fetch(apiUrl, { headers: authHeaders() })
      if (resp.ok) {
        const blob = await resp.blob()
        objectUrl = URL.createObjectURL(blob)
        src = objectUrl
      }
    } catch {
      /* keep src */
    }
  }
  if (!src) return
  const prevObjectUrl = imageLightbox.value?.objectUrl
  imageLightbox.value = {
    open: true,
    src,
    alt: file.name || '截图',
    objectUrl,
  }
  if (prevObjectUrl && prevObjectUrl !== objectUrl && String(prevObjectUrl).startsWith('blob:')) {
    try {
      URL.revokeObjectURL(prevObjectUrl)
    } catch {
      /* ignore */
    }
  }
  nextTick(() => {
    document.querySelector('.img-lightbox')?.focus?.()
  })
}

function onLightboxKeydown(e) {
  if (e.key === 'Escape' && imageLightbox.value.open) {
    e.preventDefault()
    closeImageLightbox()
  }
}
const threadId = ref('')
const loadingSession = ref(false)
const copiedIndex = ref(-1)
const editingFromIndex = ref(-1)
const auditOpen = ref(false)
const auditLoading = ref(false)
const auditItems = ref([])
/** 当前进行中的 Cursor 写码 job（停止时要 cancel + 回写确认卡） */
const activeCursorDevJobId = ref('')
const activeCursorDevMsg = ref(null)
const cursorDevWatchTimer = ref(null)
let activeRequestId = 0
let copiedTimer = null

// 首页快捷问法：平台介绍 / 审核 / MES / 写码 / PCB
const suggestions = [
  '这个ZR WorkBuddy平台有哪些功能？',
  '帮我审核代码',
  '你们家MES系统有什么功能？给我一个功能总览',
  '我说需求帮我写代码',
  'PCB电路板有哪些工序？',
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

function fileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('read failed'))
    reader.readAsDataURL(file)
  })
}

function isImageFile(file) {
  if (!file) return false
  if (String(file.type || '').startsWith('image/')) return true
  return /\.(png|jpe?g|webp|gif|bmp)$/i.test(String(file.name || ''))
}

async function attachLocalFile(file) {
  if (!file || streaming.value) return
  const tempId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const kind = isImageFile(file) ? 'image' : 'file'
  let previewDataUrl = ''
  if (kind === 'image') {
    try {
      previewDataUrl = await fileToDataUrl(file)
    } catch {
      previewDataUrl = ''
    }
  }
  // 剪贴板图常无文件名
  const name =
    file.name && file.name !== 'image.png'
      ? file.name
      : kind === 'image'
        ? `截图_${new Date().toISOString().slice(11, 19).replace(/:/g, '')}.png`
        : file.name || 'attachment'

  attachedFiles.value.push({
    id: tempId,
    name,
    status: 'uploading',
    path: null,
    saved_name: null,
    kind,
    previewDataUrl,
  })

  try {
    const uploadBlob =
      kind === 'image' && (!file.name || file.name === 'image.png')
        ? new File([file], name, { type: file.type || 'image/png' })
        : file
    const res = await uploadFile(uploadBlob)
    const saved = res.data
    const index = attachedFiles.value.findIndex((f) => f.id === tempId)
    if (index !== -1) {
      const savedName = saved.saved_name || ''
      attachedFiles.value[index] = {
        id: tempId,
        name: saved.filename || name,
        status: 'done',
        // 只存 saved_name，不回传本机绝对路径（缩小攻击面）
        path: savedName || saved.filename || name,
        saved_name: savedName,
        size: saved.size,
        kind: saved.kind === 'image' || kind === 'image' ? 'image' : 'file',
        previewDataUrl,
        previewUrl: saved.preview_url || '',
      }
    }
  } catch {
    const index = attachedFiles.value.findIndex((f) => f.id === tempId)
    if (index !== -1) {
      attachedFiles.value[index].status = 'error'
    }
  }
}

async function onPaste(e) {
  const items = e.clipboardData?.items
  let pastedImage = false
  if (items) {
    for (const item of items) {
      if (item && String(item.type || '').startsWith('image/')) {
        const blob = item.getAsFile()
        if (blob) {
          pastedImage = true
          e.preventDefault()
          await attachLocalFile(blob)
        }
      }
    }
  }
  if (!pastedImage) onPasteResize()
  else onPasteResize()
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
  cursorDevPick = null,
  cursorDevOptions = null,
  cursorDevAnchor = null,
  mergeGuide = null,
}) {
  messages.value.push({
    role: 'assistant',
    content,
    process: processItems || [],
    confirms: confirms || [],
    processCollapsed: true,
    ...(cursorDevPick ? { cursorDevPick } : {}),
    ...(cursorDevOptions ? { cursorDevOptions } : {}),
    ...(cursorDevAnchor ? { cursorDevAnchor } : {}),
    ...(mergeGuide ? { mergeGuide } : {}),
    meta: {
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
      durationText,
      stopped: Boolean(stopped),
    },
  })
}

async function stopStreaming() {
  if (!streaming.value) return
  const cursorJobId = String(activeCursorDevJobId.value || '').trim()
  const cursorMsg = activeCursorDevMsg.value
  const ctrl = streamAbort.value
  streamAbort.value = null
  // 先抬 requestId，丢弃后续迟到事件，再 abort
  activeRequestId += 1
  try {
    ctrl?.abort()
  } catch {
    /* ignore */
  }

  // 写码旁路：必须 cancel 服务端任务，并把确认卡落到可重试态（避免卡在 running）
  if (cursorJobId) {
    try {
      await cancelCursorDevJob(cursorJobId, '用户停止')
    } catch {
      /* ignore */
    }
                if (cursorMsg?.cursorDevPick) {
      cursorMsg.cursorDevPick = {
        ...cursorMsg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: '已停止写码。可点「重试写码」用同一需求再跑，或继续对话改需求后再确认。',
        jobId: cursorJobId,
        userStopped: true,
        progressText: '',
      }
    }
    activeCursorDevJobId.value = ''
    activeCursorDevMsg.value = null
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
  const stoppedNote = cursorJobId
    ? '（已停止写码。可在上方确认卡点「重试写码」。）'
    : '（已停止生成）'
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
  return messages.value.map((m) => ({
    role: m.role,
    content: m.content,
    ...(m.meta ? { meta: m.meta } : {}),
    ...(m.process?.length ? { process: m.process } : {}),
    ...(m.confirms?.length ? { confirms: m.confirms } : {}),
    ...(m.idePick ? { idePick: m.idePick } : {}),
    ...(m.gitPick ? { gitPick: m.gitPick } : {}),
    ...(m.codeReviewPick ? { codeReviewPick: m.codeReviewPick } : {}),
    ...(m.cursorDevPick ? { cursorDevPick: m.cursorDevPick } : {}),
    ...(m.cursorDevOptions ? { cursorDevOptions: m.cursorDevOptions } : {}),
    ...(m.cursorDevAnchor ? { cursorDevAnchor: m.cursorDevAnchor } : {}),
    ...(m.mergeGuide ? { mergeGuide: m.mergeGuide } : {}),
    ...(m.intentClarify ? { intentClarify: m.intentClarify } : {}),
    // 截图/附件：保留 path 供视觉与写码；预览只留短 dataURL（过大则丢，靠 path）
    ...(Array.isArray(m.files) && m.files.length
      ? {
          files: m.files.map((f) => {
            const preview = String(f?.previewDataUrl || '')
            return {
              id: f?.id,
              name: f?.name,
              status: f?.status || 'done',
              path: f?.path || '',
              kind: f?.kind || 'file',
              size: f?.size,
              previewUrl: f?.previewUrl || '',
              ...(preview && preview.length <= 800000 ? { previewDataUrl: preview } : {}),
            }
          }),
        }
      : {}),
  }))
}

/** 本线程写码流程里应沿用的截图/附件（选仓→选项→propose→Cloud） */
function codingSessionPendingFiles() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const fromPick = m?.cursorDevPick?.pendingFiles
    if (Array.isArray(fromPick) && fromPick.length) return [...fromPick]
    const fromOpts = m?.cursorDevOptions?.pendingFiles
    if (Array.isArray(fromOpts) && fromOpts.length) return [...fromOpts]
    const fromAnchor = m?.cursorDevAnchor?.pendingFiles
    if (Array.isArray(fromAnchor) && fromAnchor.length) return [...fromAnchor]
    const fromClarify = m?.intentClarify?.pendingFiles
    if (Array.isArray(fromClarify) && fromClarify.length) return [...fromClarify]
    if (m?.role === 'user' && Array.isArray(m.files) && m.files.length) {
      return m.files.filter((f) => f?.path || f?.kind === 'image')
    }
  }
  return []
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
        files: Array.isArray(m.files) ? m.files : [],
        ...(m.idePick ? { idePick: { ...m.idePick } } : {}),
        ...(m.gitPick ? { gitPick: { ...m.gitPick } } : {}),
        ...(m.codeReviewPick ? { codeReviewPick: { ...m.codeReviewPick } } : {}),
        ...(m.cursorDevPick ? { cursorDevPick: { ...m.cursorDevPick } } : {}),
        ...(m.cursorDevOptions ? { cursorDevOptions: { ...m.cursorDevOptions } } : {}),
        ...(m.cursorDevAnchor ? { cursorDevAnchor: { ...m.cursorDevAnchor } } : {}),
        ...(m.mergeGuide ? { mergeGuide: { ...m.mergeGuide } } : {}),
        ...(m.intentClarify ? { intentClarify: { ...m.intentClarify } } : {}),
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
  // 审核意图：明确「审/检查代码」；与写码（改界面/加功能）互斥
  return /审核代码|代码审核|代码审查|审查代码|检查代码|code\s*review|review\s+(this\s+)?code|帮我审(一下|下)?(代码|工程|项目)/i.test(
    t
  )
}

/** 消息里已有粘贴源码围栏：走贴码车道，不弹 Git/IDE/写码选卡 */
function hasPastedSourceFence(text) {
  const s = String(text || '')
  // 允许 ```lang 后换行或同行；门槛降到 20 字，避免短片段漏检
  if (/```[\w.+-]*[ \t]*\r?\n[\s\S]{20,}?```/.test(s)) return true
  if (/```[\w.+-]*[ \t]+[\s\S]{20,}?```/.test(s)) return true
  if (/~~~[\w.+-]*[ \t]*\r?\n[\s\S]{20,}?~~~/.test(s)) return true
  return false
}

/** 无围栏时：多行 + 源码形态（防「先选仓库」误抢贴码） */
function looksLikeRawPastedCode(text) {
  const lines = String(text || '').split(/\r?\n/)
  if (lines.length < 3) return false
  let hits = 0
  for (const line of lines) {
    if (
      /^\s*(def |class |function |const |let |var |import |from |return |if |for |while |public |private |protected |\/\/|#include|package )/i.test(
        line,
      ) ||
      /[{};]\s*$/.test(line) ||
      /^\s*\/\*|\*\/\s*$/.test(line)
    ) {
      hits += 1
    }
  }
  return hits >= 2
}

/** 贴码分析意图：粘贴源码问问题/怎么改（与写码、仓审核对等，互不抢） */
function looksLikePasteCodeAnalyze(text) {
  const t = String(text || '').trim()
  if (!t) return false
  // 明确仓审核且几乎无贴码 → 不走贴码
  if (looksLikeGitRepoReview(t) && !hasPastedSourceFence(t) && !looksLikeRawPastedCode(t)) {
    return false
  }
  const ask =
    /帮我看(看|下|一下)?|看看这段|这段(代码|程序)|有没有(什么)?问题|哪里有问题|有啥问题|怎么改|分析(一下|下)?这段|这段.{0,8}(问题|bug)/i.test(
      t,
    )
  if (hasPastedSourceFence(t)) {
    if (ask) return true
    // 有围栏、无写码动词 → 默认贴码分析
    if (!hasCodeDevActionWords(t)) return true
  }
  if (ask && looksLikeRawPastedCode(t)) return true
  return false
}

function pasteCodeStreamOpts() {
  return {
    force: true,
    workbuddyLane: 'paste_code',
    cursorDevLane: false,
  }
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

/** 写码动词：改/写/加功能界面等（不含审核）。允许中间夹仓库 URL。 */
function hasCodeDevActionWords(text) {
  const t = String(text || '')
  // 勿用 \\b：中文后接空格在 JS 里不是 word boundary，会导致「改 https…登录页」漏判
  const action =
    /(写代码|改代码|开发功能|帮我写|生成代码|开\s*PR|pull\s*request|写|改|开发|实现|新增|增加|添加|加入|加一个|加个|做一?个|做成|改成|改为|照着|仿照|参考|加上)/i.test(
      t,
    )
  const target =
    /(代码|功能|界面|页面|首页|主页|登录|模块|接口|下拉|输入|选择框|按钮|表单|字段|侧边栏|菜单|导航|布局|样式|风格|主题|仪表盘|看板|UI)/i.test(
      t,
    )
  if (action && target) return true
  return /(登录页|页面|界面|表单|侧边栏|菜单|导航|布局).{0,24}(增加|加入|添加|加一个|加个|改成|改为|做成|照着|仿照|加上|改)/i.test(
    t,
  )
}

/** 截图 + 「改成这种/照着做」→ 明确写码（UI 参照），勿当普通闲聊 */
function looksLikeScreenshotUiRedesign(text, files = []) {
  const hasImg = (files || []).some(
    (f) => f?.kind === 'image' || /\.(png|jpe?g|webp|gif)$/i.test(String(f?.name || f?.path || '')),
  )
  if (!hasImg) return false
  const t = String(text || '').trim()
  if (!t) return false
  return /(改成这种|改为这种|做成这种|照着|仿照|按这个|按截图|1\s*:\s*1|1：1|复刻|界面效果|像素级|高还原|参考.{0,8}(图|截图|界面)|改成.{0,12}(侧边栏|菜单|导航|布局|风格|样式|仪表盘|首页)|这种.{0,8}(侧边栏|菜单|导航|布局|风格)|侧边栏菜单)/i.test(
    t,
  )
}

function hasImageAttachments(files = []) {
  return (files || []).some(
    (f) => f?.kind === 'image' || /\.(png|jpe?g|webp|gif|bmp)$/i.test(String(f?.name || f?.path || '')),
  )
}

function looksLikeMesBizIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  return /(工单|生产计划|导入平台|查询报表|库存|物料|工序|报工|派工|MES|这个单号|计划号|订单号|查一下|导出)/i.test(
    t,
  )
}

function looksLikeScreenshotExplainIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  // 解释/排错，但不是「改成这种」写码
  if (looksLikeScreenshotUiRedesign(t, [{ kind: 'image' }])) return false
  if (hasCodeDevActionWords(t)) return false
  return /(什么意思|啥意思|解释|这是什么|帮我看(看|下|一下)|怎么回事|为什么|报错|错误|异常|失败|红字|看不懂|识别|OCR|读一下)/i.test(
    t,
  )
}

/**
 * 截图附件意图分流。
 * confidence=high → 直接进对应车道；low/ambiguous → 弹出意图确认卡反问用户。
 * @returns {{ lane: string, confidence: 'high'|'low', hint: string }}
 */
function classifyScreenshotIntent(text, files = []) {
  if (!hasImageAttachments(files)) {
    return { lane: 'none', confidence: 'high', hint: '' }
  }
  const t = String(text || '').trim()
  const hits = []

  if (looksLikePasteCodeAnalyze(t)) hits.push('paste_code')
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) hits.push('code_review')
  if (
    looksLikeScreenshotUiRedesign(t, files) ||
    hasCodeDevActionWords(t) ||
    looksLikeCodeDevIntent(t, files)
  ) {
    hits.push('code_dev')
  }
  if (looksLikeMesBizIntent(t) && !hasCodeDevActionWords(t)) hits.push('mes')
  if (looksLikeScreenshotExplainIntent(t)) hits.push('explain')

  // 去重保序
  const unique = [...new Set(hits)]

  if (!t || t.length < 4) {
    return {
      lane: 'ambiguous',
      confidence: 'low',
      hint: '你只贴了截图，还没说明想做什么。',
    }
  }

  // 多车道冲突 → 反问
  const exclusive = unique.filter((x) => x !== 'explain')
  if (exclusive.length >= 2) {
    return {
      lane: 'ambiguous',
      confidence: 'low',
      hint: `截图相关，但我拿不准是「${exclusive.map(laneLabel).join('」还是「')}」。请点选一项。`,
    }
  }

  if (unique.includes('code_dev')) {
    return { lane: 'code_dev', confidence: 'high', hint: '按截图改代码/界面' }
  }
  if (unique.includes('code_review')) {
    return { lane: 'code_review', confidence: 'high', hint: '审核相关代码' }
  }
  if (unique.includes('paste_code')) {
    return { lane: 'paste_code', confidence: 'high', hint: '分析粘贴代码' }
  }
  if (unique.includes('mes')) {
    return { lane: 'mes', confidence: 'high', hint: 'MES/业务处理' }
  }
  if (unique.includes('explain')) {
    return { lane: 'explain', confidence: 'high', hint: '解释截图/报错' }
  }

  // 有截图 + 有文字，但没命中任何强信号 → 反问，避免瞎走闲聊
  return {
    lane: 'ambiguous',
    confidence: 'low',
    hint: '已收到截图和说明，但我还不确定你的目标。请点选最接近的一项，或选「补充说明」。',
  }
}

function laneLabel(lane) {
  return (
    {
      code_dev: '改代码/界面',
      code_review: '代码审核',
      paste_code: '贴码分析',
      mes: 'MES/业务',
      explain: '解释截图',
    }[lane] || lane
  )
}

function buildScreenshotIntentClarifyCard(content, files, hint = '') {
  return {
    id: `shot-intent-${Date.now()}`,
    status: 'pending',
    summary: '已收到截图，请确认你想做什么',
    hint: hint || '拿不准时先确认，避免走错车道。',
    pendingContent: content,
    pendingFiles: files,
    options: [
      { id: 'code_dev', label: '按截图改代码 / 界面' },
      { id: 'explain', label: '解释截图内容或报错' },
      { id: 'mes', label: '查 MES / 业务问题' },
      { id: 'code_review', label: '审核相关代码' },
      { id: 'other', label: '都不是，我补充说明' },
    ],
  }
}


/**
 * 公开 Git 仓库审核意图。
 * 与写码对等互斥：有写/改/加功能意图则绝不走审核；仅 URL ≠ 审核（须澄清）。
 */
function looksLikeGitRepoReview(text) {
  const t = String(text || '').trim()
  if (!t) return false
  if (hasCodeDevActionWords(t)) return false
  if (looksLikeCodeReview(t) && extractGitRepoUrl(t)) return true
  return /(?:审|审核|审查|检查).{0,16}(?:git|Git|远程)?\s*仓库|(?:git|Git)\s*仓库.{0,12}(?:审|审核|审查)|review\s+(?:this\s+)?(?:git\s+)?repo|审核\s*https:\/\//i.test(
    t,
  )
}

/** 几乎只有仓库 URL、无写/审动词 → 须澄清意图，禁止自动开审或开写 */
function isBareGitRepoUrlMessage(text) {
  const t = String(text || '').trim()
  if (!t) return false
  const url = extractGitRepoUrl(t)
  if (!url) return false
  if (hasCodeDevActionWords(t) || looksLikeCodeReview(t)) return false
  if (/(?:审|审核|审查|检查).{0,16}(?:git|Git|仓库|代码)|(?:写|改|开发|实现|新增).{0,8}(代码|功能|界面|页面)/i.test(t)) {
    return false
  }
  const rest = t.replace(url, '').replace(/[\s，。,.!！？?；;：:、"'`「」【】（）()]+/g, '')
  return rest.length < 8
}

/** 写码/开发功能意图（新窗先选仓，再讨论需求）——与审核、贴码对等互斥 */
function looksLikeCodeDevIntent(text, files = []) {
  const t = String(text || '').trim()
  if (!t && !(files || []).length) return false
  // 贴码 / 审核意图明确时不进写码
  if (looksLikePasteCodeAnalyze(t)) return false
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) return false
  if (looksLikeScreenshotUiRedesign(t, files)) return true
  if (
    /工单|生产计划|导入|导出|查询|报表/.test(t) &&
    !hasCodeDevActionWords(t) &&
    !/(写|改|开发|实现|新增).{0,8}(代码|功能|界面|页面|首页|主页|接口|模块|侧边栏|菜单)/.test(t)
  ) {
    return false
  }
  if (hasCodeDevActionWords(t)) return true
  return /写代码|改代码|开发功能|开发一个|帮我写|实现(一个|功能)|生成代码|写个|写一个|开\s*PR|pull\s*request|代码实现|写登录|写界面|写页面|新增功能|我要开发|新增.{0,10}(首页|主页|页面|界面|模块|接口|功能)|做(一个|个)?.{0,8}(首页|主页|页面|界面)|加(一个|个)?.{0,8}(首页|主页|页面)|登录.{0,16}(首页|主页)|跳(转|入).{0,10}(首页|主页)|(系统|平台|ERP|MES).{0,12}(新增|改成|改为|做成)|改成这种|前端.{0,6}(首页|主页|页面|侧边栏|菜单)|后端.{0,6}(接口|API)|侧边栏菜单/i.test(
    t,
  )
}

function isVagueCodeDevIntent(text) {
  const t = String(text || '').trim()
  if (!t) return true
  if (
    /^(我要开发(功能)?|开发功能|我想开发|帮我开发|写代码|改代码|新增功能|帮我写代码|我想写代码|我说需求帮我写代码|我说需求(,|，)?帮我写代码)[。.!！]?$/i.test(
      t,
    )
  ) {
    return true
  }
  if (/我说需求.{0,12}写代码/.test(t) && !/(登录|页面|接口|模块|按钮|表单|列表|下拉|首页|主页|侧边栏)/.test(t)) {
    return true
  }
  if (t.length < 12 && !/(登录|页面|接口|模块|按钮|表单|列表|权限|导出|导入|下拉|首页|主页)/.test(t)) {
    return true
  }
  return false
}

function hasCodingDiscussThread() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m?.cursorDevPick || m?.cursorDevOptions || m?.cursorDevAnchor) return true
    if (m?.role === 'user' && looksLikeCodeDevIntent(m.content, m.files || [])) return true
  }
  return false
}

/** 本线程是否已选过仓（或已进入选项/确认卡）——旧窗续聊不再弹选仓 */
function hasCursorDevRepoSession() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const a = m?.cursorDevAnchor
    if (a && a.status === 'confirmed' && a.repo) return true
    if (m?.cursorDevPick || m?.cursorDevOptions) return true
  }
  return false
}

/** 当前用户消息是否为本线程第一次写码意图（新窗 → 先选仓） */
function isFirstCodingIntentInThread(content, files = []) {
  if (!looksLikeCodeDevIntent(content, files)) return false
  // 仅当本线程已出现过选仓/选项/确认卡时才不算「第一次」
  // （勿因「上一句写码意图曾被误判进闲聊」而跳过选仓）
  for (let i = 0; i < messages.value.length - 1; i++) {
    const m = messages.value[i]
    if (m?.cursorDevAnchor || m?.cursorDevOptions || m?.cursorDevPick) return false
  }
  return true
}

/** 写码讨论流：显式声明 code_dev 车道（与 code_review 对等互斥，无优先级） */
function codingDiscussStreamOpts(extra = null) {
  const hit = findConfirmedCursorDevAnchor()
  const fromExtra = extra && typeof extra === 'object' ? { ...extra } : {}
  delete fromExtra.workbuddyLane
  delete fromExtra.cursorDevLane
  const repo = String(fromExtra.cursorDevRepo || hit?.anchor?.repo || '').trim()
  return {
    ...fromExtra,
    force: true,
    workbuddyLane: 'code_dev',
    cursorDevLane: true,
    ...(repo ? { cursorDevRepo: repo } : {}),
  }
}

function findConfirmedCursorDevAnchor() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const a = m?.cursorDevAnchor
    if (a && a.status === 'confirmed' && a.repo) {
      return { msg: m, anchor: a, index: i }
    }
  }
  return null
}

/** 本线程锚定仓库后的上下文块（已有项目读仓 / 新项目定仓） */
function codingSessionContextBlock() {
  const hit = findConfirmedCursorDevAnchor()
  if (!hit) return ''
  const block = String(hit.anchor.promptBlock || '').trim()
  if (block) return block
  const repo = hit.anchor.repo
  if (hit.anchor.projectMode === 'new') {
    return (
      `【本会话已选定新项目仓库】\n` +
      `仓库：${repo}\n` +
      `这是新项目：从头收集需求与技术栈；:::cursor_dev_propose 的 repo 必须填 \`${repo}\`。`
    )
  }
  return (
    `【本会话已选定仓库】\n` +
    `仓库：${repo}\n` +
    `请沿用该仓；:::cursor_dev_propose 的 repo 必须填 \`${repo}\`。`
  )
}

function shouldUseCodingDiscuss(content, files = []) {
  if (looksLikePasteCodeAnalyze(content)) return false
  if (looksLikeCodeReview(content) || looksLikeGitRepoReview(content)) return false
  if (/工单|生产计划|导入平台|查询报表|MES/.test(String(content || '')) && !looksLikeCodeDevIntent(content, files)) {
    return false
  }
  if (looksLikeCodeDevIntent(content, files)) return true
  if (!hasCodingDiscussThread()) return false
  // 已有写码讨论上下文的短回复/补充，继续澄清
  const active = findConfirmedCursorDevPick()
  if (active?.pick?.phase === 'running') return false
  return true
}

function findConfirmedCursorDevPick() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const pick = m?.cursorDevPick
    if (pick && pick.status === 'confirmed' && pick.repo) {
      return { msg: m, pick, index: i }
    }
  }
  return null
}

/** 可同 job 续聊的 idle 确认卡（须有 jobId） */
function findIdleCursorDevPick() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const pick = m?.cursorDevPick
    if (
      pick &&
      pick.status === 'confirmed' &&
      pick.phase === 'idle_for_followup' &&
      pick.jobId &&
      pick.repo
    ) {
      return { msg: m, pick, index: i }
    }
  }
  return null
}

/** 写码进行中（禁止再开新写码流，应先停止） */
function findRunningCursorDevPick() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const pick = m?.cursorDevPick
    if (pick && pick.status === 'confirmed' && pick.phase === 'running' && pick.jobId) {
      return { msg: m, pick, index: i }
    }
  }
  return null
}

/**
 * 同窗续聊改码意图：须明确改码，不能仅靠「本线程聊过写码」就跟进 Cursor。
 * 短句续写（继续/再改/加上…）在已有 idle 任务时也算。
 */
function looksLikeCursorDevFollowup(text, files = []) {
  const t = String(text || '').trim()
  if (!t) return false
  if (looksLikePasteCodeAnalyze(t)) return false
  if (looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) return false
  if (looksLikeCodeDevIntent(t, files)) return true
  if (
    t.length <= 80 &&
    /^(继续|再改|改一下|补一下|加上|去掉|换成|改成|默认|还要|另外|顺带|顺便)/.test(t)
  ) {
    return true
  }
  // 同 job 微调：滚动/样式/布局壳类短需求也走续聊，避免无谓新开 Cloud Agent
  if (
    t.length <= 220 &&
    /(滚动|overflow|100vh|侧边栏|内容区|布局壳|纯\s*CSS|仅.*样式|改一下样式|页面固定)/i.test(t)
  ) {
    return true
  }
  return false
}

function clearActiveCursorDev() {
  activeCursorDevJobId.value = ''
  activeCursorDevMsg.value = null
  if (cursorDevWatchTimer.value) {
    clearInterval(cursorDevWatchTimer.value)
    cursorDevWatchTimer.value = null
  }
}

function buildCodingDiscussPrompt(userText, contextBlock = '') {
  const ctx = String(contextBlock || '').trim()
  const ctxPart = ctx ? `\n\n${ctx}\n\n` : '\n\n'
  const stackLocked =
    ctx.includes('技术栈已锁定') ||
    ctx.includes('禁止再问技术栈') ||
    ctx.includes('已锁定技术栈')
  const hasExistingInspect =
    (ctx.includes('现场读取的已有仓库信息') || ctx.includes('已有项目')) &&
    !ctx.includes('确为空仓新项目')
  const treatAsNew =
    !stackLocked &&
    (ctx.includes('确为空仓新项目') ||
      ctx.includes('新项目仓库') ||
      ctx.includes('新项目：从头') ||
      (ctx.includes('按新项目处理') && !ctx.includes('技术栈已锁定')))
  const textForLane = String(userText || '')
  const cssLayoutOnly =
    /(overflow(?:-x|-y)?|100vh|100vw|滚动|横向溢出|超出屏幕|X\s*方向|视口固定|页面固定|框架滚动|纯\s*CSS|仅.*样式|不[改动变].{0,6}(视觉|配色|图表|表格)|布局壳|侧边栏.*滚动|内容区.*滚动|无横向)/i.test(
      textForLane,
    ) && !/(【截图理解】|1\s*:\s*1|1：1|复刻|照着做|仿照|按截图|改成这种|做成这种)/i.test(textForLane)
  // 截图复刻才算 uiFromShot；单提「仪表盘/侧边栏」不算（避免布局修复被拖去视觉复刻流程）
  const uiFromShot =
    !cssLayoutOnly &&
    /改成这种|改为这种|做成这种|照着|仿照|按这个|按截图|1\s*:\s*1|1：1|复刻|【截图理解】/.test(
      textForLane,
    )
  const optionsHardRule =
    `【交互铁律】能勾选就不输入。禁止表格/A~D/「请回复xxx」。正文最多 1～2 句。` +
    `同一轮不要同时输出 propose。备注能空就空。\n\n`
  const cssLayoutRule = cssLayoutOnly
    ? `【任务档位 · css_layout】本需求是溢出/滚动/宽度自适应修复。` +
      `够开工则直接 :::cursor_dev_propose；requirement 开头必须写【任务档位：css_layout】，` +
      `写明目标页面名（如生产看板）与验收（整页无横向滚动；表格可内部横滚）。` +
      `禁止扩写业务；禁止改图表类型/配色/表格数据。\n\n`
    : ''
  const uiShotRule = uiFromShot
    ? `【截图即设计稿 · 视觉优先】用户已贴界面截图并要求复刻/改成这种布局。` +
      `消息里若有【截图理解】，把它当作最高优先级 UI 规格（布局位置、图表类型、色块背景、叠层、菜单原文）。` +
      `不要再问「截图里有什么」。禁止开放题追问技术栈/仓库地址（仓由前端选定；栈已锁定则勿再问）。\n` +
      `【propose 铁律】requirement 必须按截图视觉结构写，禁止：\n` +
      `1) 臆造截图没有的模块（如无中生有的底部双柱图、明细表）；\n` +
      `2) 把彩色色块仪表盘改写成「与 Element Plus 一致的白卡片 KPI 行」；\n` +
      `3) 只抄数字文案却丢掉图表类型（仪表盘/进度条/折线/环形/色块底/半透明浮层）。\n` +
      `requirement 建议结构：视觉布局（按位置）→ 图表与控件类型 → 配色风格 → 技术（可沿用栈与 ECharts，但样式须贴近截图）→ 验收（布局/图表类型/配色接近截图）。\n` +
      `用户说 1:1/复刻 且信息够时：优先直接 :::cursor_dev_propose；仅范围未定时用选项卡。\n\n`
    : ''
  const optionsExampleNew =
    `:::cursor_dev_options\n` +
    `{"title":"请确认写码关键项","summary":"勾选即可，少打字","notes_placeholder":"其它备注（可选）","groups":[{"id":"stack","label":"技术栈","multi":false,"required":true,"options":[{"id":"spring_vue","label":"Java Spring Boot + Vue"},{"id":"fastapi_vue","label":"Python FastAPI + Vue"},{"id":"fastapi_jinja","label":"Python FastAPI + Jinja2"},{"id":"node_react","label":"Node + React"},{"id":"undecided","label":"还没想好，请给建议"}]},{"id":"home_scope","label":"本轮范围","multi":true,"required":true,"options":[{"id":"nav_only","label":"纯导航首页"},{"id":"dashboard","label":"仪表盘统计/图表"},{"id":"todo_list","label":"待办/异常列表"},{"id":"login_loop","label":"含登录闭环"}]}]}\n` +
    `:::\n`
  const optionsExampleLocked =
    `:::cursor_dev_options\n` +
    `{"title":"请确认本轮范围","summary":"技术栈已锁定，勿再选；勾选本轮要做的即可","notes_placeholder":"其它备注（可选）","groups":[{"id":"home_scope","label":"本轮首页/功能范围","multi":true,"required":true,"options":[{"id":"nav_only","label":"纯导航入口卡片"},{"id":"dashboard","label":"仪表盘（统计/快捷入口/图表）"},{"id":"todo_list","label":"待办/异常列表"},{"id":"wire_login","label":"登录成功后跳转到该首页"}]}]}\n` +
    `:::\n`
  const optionsExampleUiShot =
    `:::cursor_dev_options\n` +
    `{"title":"按截图复刻，请确认","summary":"布局以截图为准；勾选本轮范围与还原精度","notes_placeholder":"其它备注（可选）","groups":[{"id":"ui_scope","label":"本轮改动范围","multi":true,"required":true,"options":[{"id":"dash_home","label":"复刻首页/仪表盘主区（按截图模块）"},{"id":"sidebar_nav","label":"含左侧侧边栏/顶栏导航"},{"id":"charts_visual","label":"图表类型与色块按截图（非白卡片模板）"},{"id":"keep_stack","label":"沿用现有技术栈，仅视觉贴近截图"}]},{"id":"ui_fidelity","label":"还原精度","multi":false,"required":true,"options":[{"id":"visual_high","label":"高还原：布局/色块/图表类型尽量接近截图"},{"id":"layout_data","label":"布局+数据对上即可，风格可简化"}]}]}\n` +
    `:::\n`
  const proposeExampleUi =
    uiFromShot
      ? `:::cursor_dev_propose\n` +
        `{"requirement":"## 视觉布局（按截图，禁止臆造）\\n- …\\n## 图表与控件类型\\n- …\\n## 配色与风格\\n- 色块卡/非默认白卡片…\\n## 技术\\n- 沿用现有栈；ECharts+自定义样式贴近截图\\n## 验收\\n- 布局比例、图表类型、配色接近截图；禁止白卡片 KPI 模板交差","repo":"","ref":""}\n` +
        `:::\n`
      : cssLayoutOnly
        ? `:::cursor_dev_propose\n` +
          `{"requirement":"【任务档位：css_layout】\\n- 改动点：…\\n- 布局锚点：…\\n- 验收：整页无滚动条；侧栏/内容区各自内部滚动；视觉不变","repo":"","ref":""}\n` +
          `:::\n`
        : `:::cursor_dev_propose\n` +
          `{"requirement":"<完整需求摘要与验收点>","repo":"","ref":""}\n` +
          `:::\n`
  let strategy = ''
  if (cssLayoutOnly && (stackLocked || hasExistingInspect)) {
    strategy =
      `【已锁定技术栈 + 纯样式/滚动】禁止再问技术栈；优先直接 propose（见上方 css_layout 示例），勿扩成功能开发。\n`
  } else if (uiFromShot && (stackLocked || hasExistingInspect)) {
    strategy =
      `【已锁定技术栈 + 截图参照】禁止再问技术栈/仓库。` +
      `用户已明确 1:1/复刻且【截图理解】较完整时，直接 propose；否则先出范围选项卡：\n${optionsExampleUiShot}\n`
  } else if (stackLocked || (hasExistingInspect && !treatAsNew)) {
    strategy =
      `【已锁定技术栈】禁止再问/再输出技术栈选项组（stack/backend/frontend）。` +
      `若范围未定，只输出范围类选项卡：\n${uiFromShot ? optionsExampleUiShot : optionsExampleLocked}\n`
  } else if (treatAsNew) {
    strategy = `按空仓新项目：可输出含技术栈的选项卡：\n${optionsExampleNew}\n`
  } else {
    strategy = `若需用户决策，优先范围类选项卡；仅当上下文完全没有技术栈信息时才问技术栈：\n${uiFromShot ? optionsExampleUiShot : optionsExampleLocked}\n`
  }
  return (
    `【写码需求讨论 · 远程 Cursor Cloud】用户要改的是 GitHub 远程仓库代码，不是本机沙箱。` +
    `禁止：建议 echo/vim/本机 clone；禁止任何 IDE/Git 审核工具（request_git_* / request_ide_*，含筛选功能源码）；` +
    `禁止输出代码审核报告；禁止未确认就声称已开 PR。` +
    `仓库名/分支只表示要改哪个仓，绝不等于要审核。` +
    `最终改仓必须 :::cursor_dev_propose。` +
    ctxPart +
    cssLayoutRule +
    uiShotRule +
    optionsHardRule +
    strategy +
    `仅当需求已足够开工时输出：\n` +
    proposeExampleUi +
    `\n用户说：${userText}`
  )
}

const CURSOR_DEV_PROPOSE_RE = /:::cursor_dev_propose\s*([\s\S]*?):::/i
const CURSOR_DEV_OPTIONS_RE = /:::cursor_dev_options\s*([\s\S]*?):::/i

function hideCursorDevMachineBlocks(text) {
  const s = String(text || '')
  const idxOpts = s.search(/:::cursor_dev_options/i)
  const idxProp = s.search(/:::cursor_dev_propose/i)
  const idxs = [idxOpts, idxProp].filter((i) => i >= 0)
  if (!idxs.length) return s
  return s.slice(0, Math.min(...idxs)).trimEnd()
}

function hideCursorDevPropose(text) {
  return hideCursorDevMachineBlocks(text)
}

/** 有合入指引卡时，去掉正文里与卡片同义的 push/合入说明 */
function stripCursorDevMergeBoilerplate(text) {
  const raw = String(text || '').trim()
  if (!raw) return ''
  const dropRe =
    /代码已\s*push|已\s*push\s*至|如需合入\s*main|请本地自行合并|没有自动合入|尚未合入\s*main|请在\s*GitHub\s*自行|本轮写码已完成[，,].*工作分支|可继续补充需求做续聊改码/i
  const paras = raw.split(/\n{2,}/)
  const kept = []
  for (const p of paras) {
    let s = String(p || '').trim()
    if (!s) continue
    const lines = s.split('\n').map((ln) => ln.replace(/\s+$/, ''))
    while (lines.length && dropRe.test(lines[lines.length - 1]) && lines[lines.length - 1].length < 200) {
      lines.pop()
    }
    s = lines.join('\n').trim()
    if (!s) continue
    if (dropRe.test(s) && s.length < 220 && !/改动说明|验收/.test(s)) continue
    kept.push(s)
  }
  return kept.join('\n\n').trim() || raw
}

function sessionStackLocked() {
  const hit = findConfirmedCursorDevAnchor()
  const block = String(hit?.anchor?.promptBlock || '')
  return /技术栈已锁定|禁止再问技术栈|已锁定技术栈/.test(block)
}

/** 技术栈已锁定时，剥掉模型误出的技术栈选项组 */
function stripLockedStackOptionGroups(options) {
  if (!options || !Array.isArray(options.groups)) return options
  if (!sessionStackLocked()) return options
  const filtered = options.groups.filter((g) => {
    const id = String(g?.id || '').toLowerCase()
    const label = String(g?.label || '')
    if (/^(stack|backend|frontend|tech|tech_stack|render)$/.test(id)) return false
    if (/技术栈|后端框架|前端框架|渲染方式/.test(label)) return false
    return true
  })
  if (!filtered.length) return null
  return { ...options, groups: filtered, summary: options.summary || '技术栈已锁定，只需确认本轮范围' }
}

function parseCursorDevOptions(text) {
  const s = String(text || '')
  const m = s.match(CURSOR_DEV_OPTIONS_RE)
  if (!m) return { content: null, options: null }
  let options = null
  try {
    const data = JSON.parse(String(m[1] || '').trim())
    const groups = Array.isArray(data.groups)
      ? data.groups.filter((g) => g?.id && Array.isArray(g.options))
      : []
    if (groups.length) {
      options = {
        id: `cursor-dev-opts-${Date.now()}`,
        status: 'pending',
        title: String(data.title || '请确认写码关键项'),
        summary: String(data.summary || '勾选即可，少打字'),
        notes_placeholder: String(data.notes_placeholder || '其它备注（可选）'),
        groups,
        defaults: data.defaults && typeof data.defaults === 'object' ? data.defaults : {},
        notes: '',
      }
      options = stripLockedStackOptionGroups(options)
    }
  } catch {
    options = null
  }
  const content = (s.slice(0, m.index) + s.slice(m.index + m[0].length)).trim()
  return { content, options }
}

function parseCursorDevPropose(text) {
  const s = String(text || '')
  const m = s.match(CURSOR_DEV_PROPOSE_RE)
  if (!m) return { content: s.trimEnd(), propose: null }
  let propose = null
  try {
    const raw = String(m[1] || '').trim()
    const data = JSON.parse(raw)
    const requirement = String(data.requirement || data.summary || '').trim()
    if (requirement) {
      propose = {
        requirement,
        repo: String(data.repo || '').trim(),
        ref: String(data.ref || '').trim(),
      }
    }
  } catch {
    propose = null
  }
  const content = (s.slice(0, m.index) + s.slice(m.index + m[0].length)).trim()
  return { content, propose }
}

function parseCursorDevMachineBlocks(text) {
  const optParsed = parseCursorDevOptions(text)
  if (optParsed.options) {
    const cleaned = parseCursorDevPropose(optParsed.content || '').content
    return { content: cleaned, options: optParsed.options, propose: null }
  }
  const propParsed = parseCursorDevPropose(text)
  return { content: propParsed.content, options: null, propose: propParsed.propose }
}

function formatCursorDevAdminGuide(detail = '') {
  const d = String(detail || '').trim()
  // 并发/配额类是可自助处理的，不要套「找管理员查 Key」话术，避免误导核心流程
  if (/并发已满|resource_exhausted|rate limit|配额/i.test(d)) {
    return (
      `${d}\n\n` +
      `若你并未暂停：多半是上一轮写码流断了但仍占着名额。请再点一次「重试写码」；` +
      `系统会自动结束上一任务再开新任务。`
    )
  }
  const head = d ? `写码车道暂不可用：${d}` : '写码车道暂不可用。'
  return (
    `${head}\n\n` +
    `请联系管理员处理（检查服务端 CURSOR_API_KEY、仓库白名单、Cursor Team↔GitHub 授权与 Cloud Agents）。` +
    `同事侧无需自行配置 Cursor/GitHub。`
  )
}

async function ensureCursorDevAvailableForUser() {
  try {
    const resp = await fetchCursorDevStatus()
    const st = resp?.data || {}
    if (!st.enabled) {
      return { ok: false, message: formatCursorDevAdminGuide('写码功能未开启（CURSOR_DEV_ENABLED）') }
    }
    if (!st.available || st.user_allowed === false) {
      return {
        ok: false,
        message: formatCursorDevAdminGuide(st.reason || '当前账号或配置不可用'),
      }
    }
    return { ok: true, status: st }
  } catch (e) {
    const detail = e?.response?.data?.detail || e?.message || '无法连接写码状态接口'
    return { ok: false, message: formatCursorDevAdminGuide(detail) }
  }
}

async function buildCursorDevPickFromPropose(propose) {
  let available = false
  let reason = ''
  let repos = []
  let defaultRepo = ''
  let defaultRef = ''
  try {
    const [stResp, repoResp] = await Promise.all([
      fetchCursorDevStatus(),
      fetchCursorDevRepos(),
    ])
    const st = stResp.data || {}
    const rp = repoResp.data || {}
    available = Boolean(st.available) && st.user_allowed !== false
    reason = st.reason || rp.reason || ''
    repos = Array.isArray(rp.repos) ? rp.repos : []
    defaultRepo = st.default_repo || rp.default_repo || repos[0] || ''
    defaultRef = st.starting_ref || rp.starting_ref || ''
  } catch (e) {
    reason = e?.response?.data?.detail || e?.message || '无法加载写码配置'
    available = false
  }
  const repo = propose.repo || defaultRepo || ''
  const ref = propose.ref != null && String(propose.ref).trim() !== ''
    ? String(propose.ref).trim()
    : defaultRef
  // 优先用本会话已选仓（新窗锚点），再回落到 propose / 默认仓
  const anchored = findConfirmedCursorDevAnchor()?.anchor?.repo || ''
  const resolvedRepo = propose.repo || anchored || repo
  const files = codingSessionPendingFiles()
  return {
    id: `cursor-dev-pick-${Date.now()}`,
    status: 'pending',
    available,
    reason: available ? '' : formatCursorDevAdminGuide(reason),
    repos,
    repo: resolvedRepo || repo,
    ref,
    requirement: propose.requirement,
    pendingContent: propose.requirement,
    pendingFiles: files,
    phase: 'confirm',
  }
}

function hasPendingIdePick() {
  return messages.value.some((m) => m.idePick && m.idePick.status === 'pending')
}

function hasPendingGitPick() {
  return messages.value.some((m) => m.gitPick && m.gitPick.status === 'pending')
}

function hasPendingCodeReviewPick() {
  return messages.value.some((m) => m.codeReviewPick && m.codeReviewPick.status === 'pending')
}

function hasPendingCursorDevPick() {
  return messages.value.some((m) => m.cursorDevPick && m.cursorDevPick.status === 'pending')
}

function hasPendingCursorDevOptions() {
  return messages.value.some((m) => m.cursorDevOptions && m.cursorDevOptions.status === 'pending')
}

function hasPendingCursorDevAnchor() {
  return messages.value.some((m) => m.cursorDevAnchor && m.cursorDevAnchor.status === 'pending')
}

function hasPendingScreenshotIntent() {
  return messages.value.some((m) => m.intentClarify && m.intentClarify.status === 'pending')
}

function formatCursorDevOptionsReply(payload, card) {
  const labels = payload?.selectionLabels || {}
  const groups = Array.isArray(card?.groups) ? card.groups : []
  const titleById = Object.fromEntries(groups.map((g) => [g.id, g.label || g.id]))
  const lines = ['【写码需求选项已确认】']
  for (const [gid, vals] of Object.entries(labels)) {
    if (!vals?.length) continue
    lines.push(`- ${titleById[gid] || gid}：${vals.join('、')}`)
  }
  if (payload?.notes) lines.push(`- 备注：${payload.notes}`)
  lines.push('请根据以上选择继续澄清；若已足够开工请输出写码确认卡（cursor_dev_propose）。')
  return lines.join('\n')
}


async function fetchIdeWorkspaces() {
  const info = await fetchIdeBridgeReviewInfo()
  return info.workspaces
}

/** Bridge 是否已配对在线 + 可选工程列表（未配对则不可走本机审核） */
async function fetchIdeBridgeReviewInfo() {
  try {
    const resp = await fetchIdeBridgeStatus()
    const data = resp.data || {}
    const featureOn = !!data.feature_enabled
    const online = !!data.online
    if (!featureOn || !online) {
      return { ideAvailable: false, workspaces: [] }
    }
    let list = Array.isArray(data.recent_workspaces)
      ? data.recent_workspaces.filter((w) => w?.path)
      : []
    if (!list.length && data.workspace_root) {
      const name =
        String(data.workspace_root).split(/[/\\]/).filter(Boolean).pop() || data.workspace_root
      list = [{ path: data.workspace_root, name, current: true }]
    }
    return { ideAvailable: true, workspaces: list }
  } catch {
    return { ideAvailable: false, workspaces: [] }
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
  if (msg?.codeReviewPick) {
    msg.codeReviewPick = {
      ...msg.codeReviewPick,
      status: 'confirmed',
      source: 'ide',
      selected: selected || msg.codeReviewPick.selected,
      repoUrl: '',
      ref: '',
    }
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
    workbuddyLane: 'code_review',
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
  if (msg?.codeReviewPick) {
    msg.codeReviewPick = {
      ...msg.codeReviewPick,
      status: 'confirmed',
      source: 'git',
      selected: '',
      repoUrl: repoUrl || msg.codeReviewPick.repoUrl,
      ref: ref || msg.codeReviewPick.ref || '',
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
    workbuddyLane: 'code_review',
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

function resolvePendingReviewContent(msg, fallback) {
  let content = msg?.codeReviewPick?.pendingContent || ''
  if (!content) {
    const idx = messages.value.indexOf(msg)
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i]?.role === 'user') {
        content = String(messages.value[i].content || '').trim()
        break
      }
    }
  }
  return content || fallback
}

/** 合并卡：VS Code 工程 / Git 仓 二选一确认后分流 */
async function onCodeReviewSourceResolved(msg, payload) {
  if (!msg?.codeReviewPick || !payload) return
  if (msg.codeReviewPick.status && msg.codeReviewPick.status !== 'pending') return

  const source = payload.source === 'ide' ? 'ide' : 'git'
  const selected = payload.selected || ''
  const repoUrl = payload.repoUrl || ''
  const ref = payload.ref || ''
  const content = resolvePendingReviewContent(
    msg,
    source === 'ide'
      ? '请审核已选本机工程并输出代码审核报告'
      : '请审核已确认的公开 Git 仓库并输出代码审核报告',
  )
  const files = Array.isArray(msg.codeReviewPick.pendingFiles)
    ? [...msg.codeReviewPick.pendingFiles]
    : []

  msg.codeReviewPick = {
    ...msg.codeReviewPick,
    status: payload.status,
    source,
    selected,
    repoUrl,
    ref,
    pendingContent: content,
  }
  void persistSession()
  scrollToBottom()

  if (payload.status !== 'confirmed') return

  try {
    if (source === 'ide') {
      if (msg.codeReviewPick.ideAvailable === false) {
        messages.value.push({
          role: 'assistant',
          content: '本机未配对 VS Code Bridge，无法审本机工程。请填写公开 Git 仓库，或先完成配对后再试。',
          process: [],
          processCollapsed: true,
        })
        msg.codeReviewPick = { ...msg.codeReviewPick, status: 'pending', source: 'git' }
        void persistSession()
        return
      }
      await beginIdeReviewStream(msg, { selected, content, files })
    } else {
      await beginGitReviewStream(msg, { repoUrl, ref, content, files })
    }
  } catch (e) {
    console.error('code review source start failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 确认审核来源后未能开始：${e?.message || e}`,
    })
    void persistSession()
  }
}

async function retryCodeReviewSource(msg) {
  if (!msg?.codeReviewPick) return
  if (msg.codeReviewPick.status === 'cancelled') return
  const source = msg.codeReviewPick.source === 'ide' ? 'ide' : 'git'
  const files = Array.isArray(msg.codeReviewPick.pendingFiles)
    ? [...msg.codeReviewPick.pendingFiles]
    : []
  if (source === 'ide') {
    const selected = msg.codeReviewPick.selected || ''
    if (!selected) {
      messages.value.push({
        role: 'assistant',
        content: '[错误] 未找到工程路径，请新开对话后重新发送「审核代码」。',
      })
      return
    }
    const content = resolvePendingReviewContent(msg, '请审核已选本机工程并输出代码审核报告')
    msg.codeReviewPick = {
      ...msg.codeReviewPick,
      status: 'confirmed',
      source: 'ide',
      pendingContent: content,
      selected,
    }
    try {
      await beginIdeReviewStream(msg, { selected, content, files })
    } catch (e) {
      console.error('code review ide retry failed', e)
      streaming.value = false
      messages.value.push({
        role: 'assistant',
        content: `[错误] 重新开始本机审核失败：${e?.message || e}`,
      })
      void persistSession()
    }
    return
  }
  const repoUrl = msg.codeReviewPick.repoUrl || ''
  if (!repoUrl) {
    messages.value.push({
      role: 'assistant',
      content: '[错误] 未找到仓库地址，请新开对话后重新选择审核来源。',
    })
    return
  }
  const ref = msg.codeReviewPick.ref || ''
  const content = resolvePendingReviewContent(msg, '请审核已确认的公开 Git 仓库并输出代码审核报告')
  msg.codeReviewPick = {
    ...msg.codeReviewPick,
    status: 'confirmed',
    source: 'git',
    pendingContent: content,
    repoUrl,
    ref,
  }
  try {
    await beginGitReviewStream(msg, { repoUrl, ref, content, files })
  } catch (e) {
    console.error('code review git retry failed', e)
    streaming.value = false
    messages.value.push({
      role: 'assistant',
      content: `[错误] 重新开始 Git 审核失败：${e?.message || e}`,
    })
    void persistSession()
  }
}

/** 弹出审核确认卡：Bridge 已配对 → VS Code/Git 二选一；未配对 → 仅 Git */
async function pushCodeReviewSourcePick(content, files = []) {
  const repoUrl = extractGitRepoUrl(content) || ''
  const bridge = await fetchIdeBridgeReviewInfo()
  const ideAvailable = Boolean(bridge.ideAvailable)
  const workspaces = ideAvailable ? bridge.workspaces : []
  const defaultSource =
    !ideAvailable ? 'git' : repoUrl ? 'git' : workspaces.length ? 'ide' : 'git'
  const selected =
    workspaces.find((w) => w.current)?.path || workspaces[0]?.path || ''
  messages.value.push({
    role: 'assistant',
    content: '',
    codeReviewPick: {
      id: `code-review-pick-${Date.now()}`,
      status: 'pending',
      source: defaultSource,
      ideAvailable,
      workspaces,
      selected,
      repoUrl,
      ref: '',
      pendingContent: content,
      pendingFiles: files,
    },
    process: [],
    processCollapsed: true,
  })
  await persistSession()
  scrollToBottom()
}

function buildCursorDevAgentMessage(content, repo, jobId) {
  const base = String(content || '').trim() || '请协助在目标仓库开发功能'
  if (!repo) return base
  const jobPart = jobId ? `写码任务号：${jobId}。` : ''
  return `${base}\n\n【写码仓库已确认】目标仓库：${repo}。${jobPart}请围绕该仓库澄清需求并给出实现方案；后续轮次可继续修改。开 PR 须用户明确确认。`
}

async function beginCursorDevStream(msg, { repo, ref, content, files, createPr = false, existingJobId = '' }) {
  // D5：确认仓库后只走 Cursor Cloud SSE，绝不调用 Deep Agents / startAssistantStream
  const filePaths = (Array.isArray(files) ? files : [])
    .map((f) => f?.saved_name || (f?.path ? String(f.path).split(/[/\\]/).pop() : ''))
    .filter(Boolean)
  if (streaming.value && streamAbort.value) {
    messages.value.push({
      role: 'assistant',
      content: '当前还有进行中的生成任务。请先点停止，再发起写码。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    return false
  }
  if (msg?.cursorDevPick) {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'confirmed',
      repo: repo || msg.cursorDevPick.repo,
      ref: String(ref || msg.cursorDevPick.ref || '').trim(),
      requirement: content || msg.cursorDevPick.requirement || '',
      createPr: Boolean(createPr),
      progressText: '正在创建写码任务…',
    }
  }

  let jobId = String(existingJobId || '').trim()
  try {
    if (!jobId) {
      const resp = await createCursorDevJob({
        repo,
        ref: String(ref || msg?.cursorDevPick?.ref || '').trim(),
        message: content,
        thread_id: threadId.value || '',
        create_pr: Boolean(createPr),
        confirmed: true,
        file_paths: filePaths,
      })
      jobId = resp?.data?.id || ''
      const warnings = resp?.data?.warnings || []
      if (warnings.length) {
        messages.value.push({
          role: 'assistant',
          content: `注意：${warnings.join(' ')}`,
          process: [],
          processCollapsed: true,
        })
      }
    } else {
      await followupCursorDevJob(jobId, {
        message: content,
        create_pr: Boolean(createPr),
        confirmed: true,
        file_paths: filePaths,
      })
    }
    if (msg?.cursorDevPick) {
      const workRef = String(ref || msg.cursorDevPick.ref || '').trim()
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        jobId,
        phase: 'running',
        status: 'confirmed',
        error: '',
        progressText: workRef
          ? `正在写码 → ${repo || msg.cursorDevPick.repo} @${workRef}`
          : '正在写码…',
      }
    }
    void persistSession()
  } catch (e) {
    const detail = e?.response?.data?.detail || e?.message || e
    streaming.value = false
    clearActiveCursorDev()
    if (msg?.cursorDevPick) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: String(detail),
        repo,
        ref: String(ref || '').trim(),
        requirement: content,
        createPr: Boolean(createPr),
        progressText: '',
      }
    }
    messages.value.push({
      role: 'assistant',
      content: formatCursorDevAdminGuide(detail),
    })
    await persistSession()
    return false
  }

  if (!jobId) {
    streaming.value = false
    clearActiveCursorDev()
    messages.value.push({
      role: 'assistant',
      content: formatCursorDevAdminGuide('创建写码任务未返回 job id'),
    })
    await persistSession()
    return false
  }

  if (streamAbort.value) {
    forceResetStreaming()
    await nextTick()
  }

  if (!threadId.value) {
    threadId.value = createThreadId()
    syncThreadQuery(threadId.value)
  }

  const requestId = ++activeRequestId
  const currentThread = threadId.value
  const abortCtrl = new AbortController()
  streamAbort.value = abortCtrl
  activeCursorDevJobId.value = jobId
  activeCursorDevMsg.value = msg

  streaming.value = true
  streamContent.value = ''
  streamAnswerPending.value = false
  streamConfirms.value = []
  const workRefLabel = String(ref || msg?.cursorDevPick?.ref || '').trim()
  streamProcess.value = [{
    id: 'boot',
    type: 'step',
    state: 'running',
    title: repo
      ? `Cursor 写码：${repo}${workRefLabel ? ` @${workRefLabel}` : ''}`
      : 'Cursor 写码…',
  }]
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamStartedAt.value = Date.now()
  scrollToBottom()
  await nextTick()

  let stepRevealChain = Promise.resolve()
  let flushStepsNow = false
  let streamGotError = false
  let recoveredByWatchdog = false
  let finishedOnce = false
  let lastEventAt = Date.now()
  let watchTimer = null
  let prUrl = ''
  let mergeGuide = null
  const STEP_GAP_MS = 150
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

  const applyStep = (event) => {
    const id = event.id || `cursor-${event.title || 'step'}`
    const steps = streamProcess.value.filter((i) => i.type === 'step' && i.id !== 'boot')
    let idx = steps.findIndex((i) => i.id === id)
    const prev = idx >= 0 ? steps[idx] : null
    const nextState = event.state || 'running'
    const item = {
      id,
      type: 'step',
      state: nextState,
      title: event.title || prev?.title || '',
      detail: event.detail || prev?.detail || '',
    }
    if (idx >= 0) steps[idx] = { ...steps[idx], ...item }
    else steps.push(item)
    // 新步骤进入执行中时，把其它仍 running 的标为完成，避免「全是执行中」像卡死
    if (nextState === 'running') {
      for (let i = 0; i < steps.length; i++) {
        if (steps[i].id !== item.id && steps[i].state === 'running') {
          steps[i] = { ...steps[i], state: 'done' }
        }
      }
    }
    streamProcess.value = steps
  }

  const enqueueStep = (event) => {
    const gap = event.state === 'running' ? STEP_GAP_MS : 0
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

  const touchProgress = (text) => {
    lastEventAt = Date.now()
    const elapsed = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
    streamDurationText.value = `${elapsed}s`
    if (msg?.cursorDevPick && text) {
      msg.cursorDevPick = { ...msg.cursorDevPick, progressText: String(text) }
    }
  }

  const finishUi = async ({ content: finalContent, stopped = false }) => {
    if (finishedOnce) return
    if (requestId !== activeRequestId || threadId.value !== currentThread) return
    finishedOnce = true
    if (watchTimer) {
      clearInterval(watchTimer)
      watchTimer = null
    }
    if (cursorDevWatchTimer.value) {
      clearInterval(cursorDevWatchTimer.value)
      cursorDevWatchTimer.value = null
    }
    flushStepsNow = true
    await stepRevealChain
    const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
    const durationText = streamDurationText.value || `${sec}s`
    const processItems = (streamProcess.value || []).filter(
      (i) => i.type === 'step' && i.id !== 'boot',
    )
    let body = finalContent
    // 有合入指引卡时，正文去掉与卡片同义的 push/合入尾巴，只保留改动摘要
    if (mergeGuide) {
      body = stripCursorDevMergeBoilerplate(body)
      if (mergeGuide.summary && body && body.includes(mergeGuide.summary)) {
        body = body.split(mergeGuide.summary).join('').replace(/\n{3,}/g, '\n\n').trim()
      }
    }
    if (prUrl && createPr && body && !body.includes(prUrl)) {
      body = `${body}\n\nPR：${prUrl}`
    } else if (prUrl && createPr && !body) {
      body = `PR：${prUrl}`
    }
    if (body || processItems.length || mergeGuide) {
      pushAssistantMessage({
        content: body || '',
        processItems,
        confirms: [],
        durationText,
        stopped,
        mergeGuide: mergeGuide || null,
      })
    } else if (!streamGotError) {
      pushAssistantMessage({
        content: '[提示] 本轮写码流已结束，但未收到摘要。可稍后在任务详情查看状态。',
        processItems: [],
        confirms: [],
        durationText,
        stopped,
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
    clearActiveCursorDev()
    scrollToBottom()
    await persistSession()
  }

  /** Cloud 常在结束时一次性下发终稿；大段突然替换时做渐进展示，避免「一下子蹦出来」 */
  const revealStreamText = async (fullText) => {
    const target = String(fullText || '')
    const prev = streamContent.value || ''
    if (!target) return
    streamAnswerPending.value = true
    streamProcessCollapsed.value = false
    // 已有大部分正文，或增量很小：直接落到终稿
    if (prev === target) return
    if (prev && target.startsWith(prev) && target.length - prev.length < 120) {
      streamContent.value = target
      scrollToBottom()
      return
    }
    let i = 0
    if (prev && target.startsWith(prev)) {
      i = prev.length
    } else {
      streamContent.value = ''
    }
    // 按长度动态调速：长文稍快，避免拖太久
    const total = Math.max(1, target.length - i)
    const chunk = total > 2500 ? 48 : total > 1200 ? 32 : 20
    const delay = total > 2500 ? 10 : 14
    while (i < target.length) {
      if (
        finishedOnce ||
        recoveredByWatchdog ||
        requestId !== activeRequestId ||
        threadId.value !== currentThread
      ) {
        break
      }
      i = Math.min(target.length, i + chunk)
      streamContent.value = target.slice(0, i)
      scrollToBottom()
      await new Promise((r) => setTimeout(r, delay))
    }
    streamContent.value = target
    scrollToBottom()
  }

  const tryRecoverFromJob = async () => {
    if (finishedOnce || recoveredByWatchdog) return false
    if (requestId !== activeRequestId || threadId.value !== currentThread) return false
    try {
      const resp = await getCursorDevJob(jobId)
      const st = String(resp?.data?.status || '')
      const recovered = String(resp?.data?.last_assistant || '').trim()
      if (st === 'idle_for_followup' || st === 'succeeded') {
        recoveredByWatchdog = true
        if (msg?.cursorDevPick) {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            phase: 'idle_for_followup',
            status: 'confirmed',
            progressText: '写码完成（已自动恢复）',
            jobId,
          }
        }
        const body =
          recovered ||
          streamContent.value ||
          'Cursor 已完成本轮写码（页面曾无进度推送，已自动核对云端结果）。'
        const prev = streamContent.value || ''
        if (body && (!prev || body.length > prev.length + 80)) {
          await revealStreamText(body)
        }
        await finishUi({
          content: streamContent.value || body,
          stopped: false,
        })
        try {
          abortCtrl.abort()
        } catch {
          /* ignore */
        }
        return true
      }
      if (st === 'failed' || st === 'cancelled') {
        recoveredByWatchdog = true
        streamGotError = true
        const err = resp?.data?.error || (st === 'cancelled' ? '写码已取消' : '写码失败')
        if (msg?.cursorDevPick) {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            phase: 'failed',
            status: 'failed',
            error: String(err),
            jobId,
            progressText: '',
          }
        }
        await finishUi({
          content: `[错误] ${err}\n可在上方确认卡点「重试写码」。`,
          stopped: false,
        })
        try {
          abortCtrl.abort()
        } catch {
          /* ignore */
        }
        return true
      }
      // 仍在跑：刷新可感知进度，避免「调用工具」假死感
      const elapsed = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
      const silentSec = Math.max(0, Math.round((Date.now() - lastEventAt) / 1000))
      streamDurationText.value = `${elapsed}s`
      const tip =
        silentSec >= 20
          ? `云端写码中…已 ${elapsed}s（约 ${silentSec}s 无新推送，正在自动核对）`
          : `云端写码中…已 ${elapsed}s`
      if (msg?.cursorDevPick) {
        msg.cursorDevPick = { ...msg.cursorDevPick, progressText: tip }
      }
      applyStep({
        id: 'cursor-heartbeat',
        state: 'running',
        title: silentSec >= 20 ? `Cursor 执行中（${elapsed}s，核对中…）` : `Cursor 执行中（${elapsed}s）…`,
      })
      scrollToBottom()
    } catch {
      /* ignore poll errors */
    }
    return false
  }

  watchTimer = setInterval(() => {
    void tryRecoverFromJob()
  }, 8000)
  if (cursorDevWatchTimer.value) {
    clearInterval(cursorDevWatchTimer.value)
  }
  cursorDevWatchTimer.value = watchTimer

  try {
    const result = await streamCursorDevJob(
      jobId,
      async (event) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        if (finishedOnce || recoveredByWatchdog) return
        const type = event?.type
        if (type === 'status') {
          const text = event.text || ''
          touchProgress(text || '写码进行中…')
          if (streamProcess.value.some((i) => i.id === 'boot')) {
            streamProcess.value = [{ id: 'boot', type: 'step', state: 'running', title: text || 'Cursor…' }]
          }
          // heartbeat 也推进过程区，避免用户以为卡死
          if (event.phase === 'heartbeat') {
            await enqueueStep({
              id: 'cursor-heartbeat',
              state: 'running',
              title: text || `Cursor 仍在执行…`,
            })
          }
          scrollToBottom()
        } else if (type === 'step') {
          lastEventAt = Date.now()
          streamAnswerPending.value = false
          streamProcessCollapsed.value = false
          await enqueueStep(event)
          if (msg?.cursorDevPick && event.title) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              progressText: event.state === 'done' ? `完成：${event.title}` : String(event.title),
            }
          }
        } else if (type === 'token') {
          const text = event.text != null ? event.text : event.token
          if (!text) return
          lastEventAt = Date.now()
          flushStepsNow = true
          await stepRevealChain
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          if (!streamDurationText.value) {
            const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
            streamDurationText.value = `${sec}s`
          }
          const prev = streamContent.value || ''
          const incoming = String(text)
          // 终稿报告覆盖过程旁白，禁止拼成「正在推送到 `## 已完成」
          const looksFinal = /^\s*##\s*已完成|已完成本轮需求/m.test(incoming)
          const prevIsChatter =
            /^(正在|先|开始|接着|接下来)/m.test(prev.trim()) ||
            (prev.length < 160 && !/##\s*已完成/.test(prev))
          if (looksFinal && prevIsChatter) {
            streamContent.value = incoming
          } else if (prev && incoming.startsWith(prev)) {
            streamContent.value = incoming
          } else if (prev && (incoming === prev || (prev.includes(incoming) && incoming.length > 80))) {
            /* skip replay / subset */
          } else if (looksFinal && /##\s*已完成/.test(prev) && incoming.length >= prev.length * 0.85) {
            streamContent.value = incoming
          } else {
            streamContent.value += incoming
          }
          scrollToBottom()
        } else if (type === 'replace_text' && event.text != null) {
          lastEventAt = Date.now()
          flushStepsNow = true
          await stepRevealChain
          await revealStreamText(String(event.text))
        } else if (type === 'pr' && event.url) {
          // 未勾选开 PR 时忽略成功态 PR 事件（后端也会尝试关闭误开 PR）
          if (!createPr) {
            scrollToBottom()
          } else {
            prUrl = String(event.url)
            const line = `PR：${prUrl}`
            if (!streamContent.value.includes(line)) {
              streamContent.value += (streamContent.value ? '\n\n' : '') + line
            }
            scrollToBottom()
          }
        } else if (type === 'merge_guide') {
          mergeGuide = {
            title: event.title || '',
            summary: event.summary || '',
            repo: event.repo || repo || '',
            work_branch: event.work_branch || ref || '',
            base_branch: event.base_branch || 'main',
            create_pr: Boolean(event.create_pr),
            pr_url: event.pr_url || null,
            branch_url: event.branch_url || '',
            compare_url: event.compare_url || '',
            new_pr_url: event.new_pr_url || '',
            merged_to_main: false,
          }
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              mergeGuide,
              phase: 'idle_for_followup',
              ref: mergeGuide.work_branch || msg.cursorDevPick.ref,
            }
          }
          scrollToBottom()
        } else if (type === 'review_hint' && event.text) {
          // 有合入指引卡时不再把同义提示塞进正文，避免重复
          if (!mergeGuide) {
            const hint = String(event.text)
            if (!streamContent.value.includes(hint)) {
              streamContent.value += (streamContent.value ? '\n\n' : '') + hint
            }
          }
          scrollToBottom()
        } else if (type === 'done') {
          if (event.pr_url && createPr) prUrl = String(event.pr_url)
          if (event.merge_guide && typeof event.merge_guide === 'object') {
            mergeGuide = { ...event.merge_guide, merged_to_main: false }
          }
          // 终稿为准，消除流式双份（review_hint 已由专用事件追加则不再重复）
          if (event.text) {
            let canonical = String(event.text).trim()
            // 前端兜底：多份「## 已完成」只留最后一份完整稿
            const parts = canonical.split(/(?=##\s*已完成)/).filter((p) => /##\s*已完成/.test(p))
            if (parts.length > 1) {
              canonical = parts.reduce((a, b) => (b.length >= a.length ? b : a)).trim()
            }
            const hint = !mergeGuide && event.review_hint ? String(event.review_hint) : ''
            const next = hint && !canonical.includes(hint) ? `${canonical}\n\n${hint}` : canonical
            // 若过程区空转很久、终稿突然到齐：渐进展示再收尾
            const prev = streamContent.value || ''
            if (!prev || (next.length > prev.length + 80 && !prev.includes(next.slice(0, 40)))) {
              await revealStreamText(next)
            } else {
              streamContent.value = next
            }
          }
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              phase: 'idle_for_followup',
              status: 'confirmed',
              jobId,
              progressText: '',
              ...(mergeGuide ? { mergeGuide } : {}),
            }
          }
        } else if (type === 'error') {
          streamGotError = true
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              status: 'failed',
              phase: 'failed',
              error: event.message || event.error || '写码失败',
              jobId,
              repo: repo || msg.cursorDevPick.repo,
              requirement: content || msg.cursorDevPick.requirement,
              createPr: Boolean(createPr),
              progressText: '',
            }
          }
        }
      },
      async (donePayload) => {
        if (streamGotError || recoveredByWatchdog || finishedOnce) return
        let text =
          streamContent.value ||
          donePayload?.text ||
          ''
        // 流断了但云端可能已完成：拉 job 对账摘要，避免一直停在「正在调用工具」
        if (!text || text.length < 40) {
          try {
            const resp = await getCursorDevJob(jobId)
            const st = resp?.data?.status
            const recovered = String(resp?.data?.last_assistant || '').trim()
            if (recovered) text = recovered
            if (st === 'idle_for_followup' || st === 'succeeded') {
              if (msg?.cursorDevPick) {
                msg.cursorDevPick = {
                  ...msg.cursorDevPick,
                  phase: 'idle_for_followup',
                  status: 'confirmed',
                  progressText: '写码完成',
                  jobId,
                }
              }
            }
          } catch {
            /* ignore */
          }
        }
        await finishUi({
          content:
            text ||
            'Cursor 已完成本轮写码。小改（滚动/样式/微调）请直接在本对话继续说，将复用同一任务更快改完。',
          stopped: false,
        })
      },
      async (err) => {
        if (recoveredByWatchdog || finishedOnce) return
        streamGotError = true
        const errText = typeof err === 'string' ? err : (err?.message || err)
        await finishUi({
          content: `[错误] Cursor 写码失败：${errText}\n可在上方确认卡点「重试写码」。`,
          stopped: false,
        })
        if (msg?.cursorDevPick) {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            phase: 'failed',
            status: 'failed',
            error: String(errText),
            jobId,
            progressText: '',
          }
          void persistSession()
        }
      },
      abortCtrl.signal,
    )
    if (result?.aborted) {
      if (recoveredByWatchdog || finishedOnce) {
        return true
      }
      // stopStreaming 已 cancel + 回写确认卡 + 推停止气泡；此处仅兜底 cancel，避免双份正文
      const alreadyStoppedByUi = msg?.cursorDevPick?.phase === 'failed'
      try {
        await cancelCursorDevJob(jobId, '用户停止')
      } catch {
        /* ignore */
      }
      if (!alreadyStoppedByUi) {
        if (msg?.cursorDevPick) {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            status: 'failed',
            phase: 'failed',
            error: '已停止写码。可点「重试写码」用同一需求再跑，或继续对话改需求后再确认。',
            jobId,
            progressText: '',
          }
        }
        await finishUi({
          content: streamContent.value || '已停止写码任务。可在上方确认卡点「重试写码」。',
          stopped: true,
        })
      } else {
        clearActiveCursorDev()
        streaming.value = false
        streamAbort.value = null
      }
      return false
    }
    return true
  } catch (e) {
    if (watchTimer) {
      clearInterval(watchTimer)
      watchTimer = null
    }
    if (recoveredByWatchdog || finishedOnce) return true
    streaming.value = false
    streamAbort.value = null
    clearActiveCursorDev()
    if (msg?.cursorDevPick) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: e?.message || String(e),
        jobId,
        progressText: '',
      }
    }
    messages.value.push({
      role: 'assistant',
      content: `[错误] 写码流异常：${e?.message || e}`,
    })
    await persistSession()
    return false
  }
}

async function onCursorDevOptionsResolved(msg, payload) {
  if (!msg?.cursorDevOptions || !payload) return
  if (msg.cursorDevOptions.status && msg.cursorDevOptions.status !== 'pending') return

  msg.cursorDevOptions = {
    ...msg.cursorDevOptions,
    status: payload.status === 'confirmed' ? 'confirmed' : 'skipped',
    selections: payload.selections || {},
    selectionLabels: payload.selectionLabels || {},
    notes: payload.notes || '',
  }
  void persistSession()
  scrollToBottom()

  if (payload.status !== 'confirmed') {
    messages.value.push({
      role: 'assistant',
      content: '已跳过选项卡。你可以直接打字补充；需要时我会再弹出选项卡。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    return
  }

  const reply = formatCursorDevOptionsReply(payload, msg.cursorDevOptions)
  const pendingFiles = Array.isArray(msg.cursorDevOptions.pendingFiles) && msg.cursorDevOptions.pendingFiles.length
    ? [...msg.cursorDevOptions.pendingFiles]
    : codingSessionPendingFiles()
  messages.value.push({ role: 'user', content: reply })
  await persistSession()
  scrollToBottom()
  await startAssistantStream(
    buildCodingDiscussPrompt(reply, codingSessionContextBlock()),
    pendingFiles,
    null,
    null,
    codingDiscussStreamOpts(),
  )
}

async function beginCodingDiscussEntry(content, files = []) {
  const gate = await ensureCursorDevAvailableForUser()
  if (!gate.ok) {
    messages.value.push({ role: 'assistant', content: gate.message, process: [], processCollapsed: true })
    await persistSession()
    scrollToBottom()
    return
  }
  // 需求太笼统：先反问要实现什么功能，不立刻弹选仓
  if (
    isVagueCodeDevIntent(content) &&
    !hasCursorDevRepoSession() &&
    !looksLikeScreenshotUiRedesign(content, files)
  ) {
    messages.value.push({
      role: 'assistant',
      content:
        '好的，我可以帮你写代码。\n\n' +
        '请先说明你**要实现什么功能**？例如：\n' +
        '- 登录页增加企业编码下拉\n' +
        '- 首页做制造仪表盘\n' +
        '- 给某接口加字段校验\n\n' +
        '说清楚需求后，我会再请你确认代码仓库并开始写码。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }
  if (isFirstCodingIntentInThread(content, files) && !hasCursorDevRepoSession()) {
    let repos = []
    let defaultRepo = ''
    try {
      const rp = await fetchCursorDevRepos()
      repos = Array.isArray(rp?.data?.repos) ? rp.data.repos : []
      defaultRepo = rp?.data?.default_repo || repos[0] || ''
    } catch {
      /* ignore */
    }
    messages.value.push({
      role: 'assistant',
      content: looksLikeScreenshotUiRedesign(content, files)
        ? '已理解你要按截图改界面。请先选择要改的代码仓库。'
        : '请先选择本次要改的代码仓库。已有项目会现场读仓衔接；新项目再从头收集需求。',
      cursorDevAnchor: {
        id: `cursor-dev-anchor-${Date.now()}`,
        status: 'pending',
        repos,
        repo: defaultRepo,
        projectMode: 'existing',
        pendingContent: content,
        pendingFiles: files,
      },
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }
  await startAssistantStream(
    buildCodingDiscussPrompt(content, codingSessionContextBlock()),
    files,
    null,
    null,
    codingDiscussStreamOpts(),
  )
}

async function beginCodeReviewEntry(content, files = []) {
  await pushCodeReviewSourcePick(content, files)
}

async function onScreenshotIntentResolved(msg, payload) {
  if (!msg?.intentClarify || !payload) return
  if (msg.intentClarify.status && msg.intentClarify.status !== 'pending') return

  if (payload.status !== 'confirmed') {
    msg.intentClarify = { ...msg.intentClarify, status: 'cancelled' }
    void persistSession()
    messages.value.push({
      role: 'assistant',
      content: '已取消。你可以直接补充想做什么，或再贴一张截图说明。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  const intent = String(payload.intent || '').trim()
  const content = String(payload.pendingContent || msg.intentClarify.pendingContent || '').trim()
  const files = Array.isArray(payload.pendingFiles)
    ? payload.pendingFiles
    : Array.isArray(msg.intentClarify.pendingFiles)
      ? [...msg.intentClarify.pendingFiles]
      : []

  msg.intentClarify = {
    ...msg.intentClarify,
    status: 'confirmed',
    chosen: intent,
  }
  void persistSession()

  if (intent === 'other') {
    messages.value.push({
      role: 'assistant',
      content: '好的。请再发一句说明你的目标（例如：改哪个页面、查哪个工单、解释哪条报错）。截图我会继续沿用。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    nextTick(() => inputEl.value?.focus?.())
    return
  }

  if (intent === 'code_dev') {
    const need =
      content ||
      '请按用户截图中的界面/布局改代码（以【截图理解】为设计规格）'
    await beginCodingDiscussEntry(need, files)
    return
  }

  if (intent === 'code_review') {
    await beginCodeReviewEntry(content || '请审核与截图相关的代码', files)
    return
  }

  if (intent === 'explain') {
    await startAssistantStream(
      `【截图问答】用户确认要解释截图内容/报错。请结合【截图理解】作答；信息不足时先反问。\n\n用户说：${content || '（请根据截图说明）'}`,
      files,
      null,
      null,
      null,
    )
    return
  }

  if (intent === 'mes') {
    await startAssistantStream(
      `【截图+MES/业务】用户确认要处理 MES/业务问题。请结合【截图理解】与平台工具；不要进写码/审核。\n\n用户说：${content || '（请根据截图协助业务处理）'}`,
      files,
      null,
      null,
      null,
    )
    return
  }

  messages.value.push({
    role: 'assistant',
    content: '未识别的选项，请重新说明你的意图。',
    process: [],
    processCollapsed: true,
  })
  await persistSession()
}

async function onCursorDevAnchorResolved(msg, payload) {
  if (!msg?.cursorDevAnchor || !payload) return
  if (msg.cursorDevAnchor.status && msg.cursorDevAnchor.status !== 'pending') return

  if (payload.status !== 'confirmed') {
    msg.cursorDevAnchor = { ...msg.cursorDevAnchor, status: 'cancelled' }
    void persistSession()
    messages.value.push({
      role: 'assistant',
      content: '已取消选仓。重新说明开发需求后，我会再请你选择仓库。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  const repo = String(payload.repo || '').trim()
  const projectMode = payload.projectMode === 'new' ? 'new' : 'existing'
  const pendingContent = String(
    payload.pendingContent || msg.cursorDevAnchor.pendingContent || '',
  ).trim()
  const pendingFiles = Array.isArray(payload.pendingFiles)
    ? payload.pendingFiles
    : Array.isArray(msg.cursorDevAnchor.pendingFiles)
      ? [...msg.cursorDevAnchor.pendingFiles]
      : []

  msg.cursorDevAnchor = {
    ...msg.cursorDevAnchor,
    status: 'confirmed',
    repo,
    projectMode,
    pendingContent,
    pendingFiles,
    promptBlock: '',
  }
  void persistSession()

  let promptBlock = ''
  if (projectMode === 'existing') {
    messages.value.push({
      role: 'assistant',
      content: `正在读取仓库 \`${repo}\` 的项目信息…`,
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    try {
      const resp = await fetchCursorDevRepoInspect(repo)
      const data = resp?.data || {}
      promptBlock = String(data.prompt_block || '').trim()
      const locked = Array.isArray(data.locked_stack) ? data.locked_stack.filter(Boolean) : []
      const hints = Array.isArray(data.stack_hints) ? data.stack_hints.filter(Boolean) : []
      const stackLine = (locked.length ? locked : hints).join('、')
      const treatAsNew = Boolean(data.treat_as_new)
      const workBranch = data.work_branch || data.ref || ''
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg?.role === 'assistant') {
        if (treatAsNew) {
          lastMsg.content =
            `已选定 \`${repo}\`${workBranch ? `@${workBranch}` : ''}：仓内尚无可用工程，按新项目收集技术栈与范围。`
        } else {
          lastMsg.content =
            `已衔接 \`${repo}\`${workBranch ? `@${workBranch}` : ''}` +
            (stackLine ? `，技术栈已锁定：${stackLine}` : '') +
            '。本轮只确认新增范围，不再选技术栈。'
        }
      }
    } catch (e) {
      const detail = e?.response?.data?.detail || e?.message || String(e)
      promptBlock =
        `【已选定已有仓库，但现场读取失败】\n仓库：${repo}\n错误：${detail}\n` +
        `仍请按该仓增量开发；不要重新问技术栈（除非用户要换）；propose.repo 填 \`${repo}\`。`
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg?.role === 'assistant') {
        lastMsg.content =
          `仓库 \`${repo}\` 信息读取失败（${detail}）。仍会按该仓继续；若私有仓请联系管理员检查 GitHub Token。`
      }
    }
  } else {
    promptBlock =
      `【本会话已选定新项目仓库】\n` +
      `仓库：${repo}\n` +
      `这是新项目：从头收集需求与技术栈；:::cursor_dev_propose 的 repo 必须填 \`${repo}\`。`
    messages.value.push({
      role: 'assistant',
      content: `已选定新项目仓库 \`${repo}\`。接下来从头确认技术栈与需求范围。`,
      process: [],
      processCollapsed: true,
    })
  }

  msg.cursorDevAnchor = { ...msg.cursorDevAnchor, promptBlock }
  await persistSession()
  scrollToBottom()

  const userNeed = pendingContent || '请根据已选仓库继续澄清写码需求'
  await startAssistantStream(
    buildCodingDiscussPrompt(userNeed, promptBlock || codingSessionContextBlock()),
    pendingFiles,
    null,
    null,
    codingDiscussStreamOpts({ cursorDevRepo: repo }),
  )
}

async function onCursorDevPickResolved(msg, payload) {
  if (!msg?.cursorDevPick || !payload) return
  const prevStatus = msg.cursorDevPick.status || 'pending'
  if (prevStatus && prevStatus !== 'pending' && prevStatus !== 'failed') return
  if (prevStatus === 'failed' && payload.status !== 'retry' && payload.status !== 'cancelled') return

  const repo = payload.repo || msg.cursorDevPick.repo || ''
  const ref = String(payload.ref ?? msg.cursorDevPick.ref ?? '').trim()
  const requirement = String(
    payload.requirement || msg.cursorDevPick.requirement || msg.cursorDevPick.pendingContent || '',
  ).trim()
  const createPr = Boolean(payload.createPr ?? msg.cursorDevPick.createPr)
  const pendingFiles =
    Array.isArray(msg.cursorDevPick.pendingFiles) && msg.cursorDevPick.pendingFiles.length
      ? [...msg.cursorDevPick.pendingFiles]
      : codingSessionPendingFiles()

  if (payload.status === 'cancelled') {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'cancelled',
      phase: 'cancelled',
      repo,
      ref,
      requirement,
      createPr,
    }
    void persistSession()
    messages.value.push({
      role: 'assistant',
      content:
        '已取消本次写码确认。我们继续聊需求；等理解对齐后我会再弹出确认卡，你点确认才会开始改代码。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  if (payload.status === 'retry') {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'confirmed',
      phase: 'running',
      repo,
      ref,
      requirement,
      createPr,
      error: '',
      progressText: '正在重试写码…',
    }
    void persistSession()
    const prevJobId = String(payload.jobId || msg.cursorDevPick.jobId || '').trim()
    // 用户停止后的 job 已是 cancelled，不能 /messages 续聊；直接开新 job（保留仓/分支/需求）
    const forceNewJob =
      Boolean(msg.cursorDevPick.userStopped) ||
      /已停止|用户停止|用户取消|不可续聊：(?:running|cancelled)/i.test(
        String(msg.cursorDevPick.error || ''),
      )
    try {
      let ok = false
      if (prevJobId && !forceNewJob) {
        ok = await beginCursorDevStream(msg, {
          repo,
          ref,
          content: requirement,
          files: pendingFiles,
          createPr,
          existingJobId: prevJobId,
        })
      }
      if (!ok) {
        msg.cursorDevPick = {
          ...msg.cursorDevPick,
          userStopped: false,
          error: '',
        }
        await beginCursorDevStream(msg, {
          repo,
          ref,
          content: requirement,
          files: pendingFiles,
          createPr,
          existingJobId: '',
        })
      }
    } catch (e) {
      console.error('cursor-dev retry failed', e)
      streaming.value = false
      clearActiveCursorDev()
      if (msg?.cursorDevPick) {
        msg.cursorDevPick = {
          ...msg.cursorDevPick,
          phase: 'failed',
          status: 'failed',
          error: e?.message || String(e),
          progressText: '',
        }
      }
      void persistSession()
    }
    return
  }

  if (payload.status !== 'confirmed') return

  // 先切到「启动中」，再做可用性检查，避免确认按钮看起来没点上
  msg.cursorDevPick = {
    ...msg.cursorDevPick,
    status: 'confirmed',
    repo,
    ref,
    requirement,
    createPr,
    pendingContent: requirement,
    pendingFiles,
    phase: 'running',
    progressText: '正在启动写码…',
    error: '',
  }
  void persistSession()
  scrollToBottom()

  const gate = await ensureCursorDevAvailableForUser()
  if (!gate.ok) {
    msg.cursorDevPick = { ...msg.cursorDevPick, status: 'failed', phase: 'failed', error: gate.message }
    messages.value.push({
      role: 'assistant',
      content: gate.message,
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  if (!requirement || isVagueCodeDevIntent(requirement)) {
    msg.cursorDevPick = { ...msg.cursorDevPick, status: 'cancelled', phase: 'cancelled' }
    messages.value.push({
      role: 'assistant',
      content: '需求摘要还不够具体，已取消启动。请再补充功能细节后，我会重新弹出确认卡。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    return
  }

  try {
    await beginCursorDevStream(msg, {
      repo,
      ref,
      content: requirement,
      files: pendingFiles,
      createPr,
    })
  } catch (e) {
    console.error('cursor-dev confirm start failed', e)
    streaming.value = false
    if (msg?.cursorDevPick) {
      msg.cursorDevPick = { ...msg.cursorDevPick, phase: 'failed', status: 'failed', error: e?.message || String(e) }
    }
    messages.value.push({
      role: 'assistant',
      content: `[错误] 确认后未能开始写码：${e?.message || e}`,
    })
    void persistSession()
  }
}

async function send(text) {
  const content = text || input.value.trim()
  const files = attachedFiles.value
  if ((!content && files.length === 0) || streaming.value) return
  if (files.some((f) => f.status === 'uploading')) return
  if (files.some((f) => f.status === 'error')) return
  if (hasPendingIdePick() || hasPendingGitPick() || hasPendingCodeReviewPick() || hasPendingCursorDevPick() || hasPendingCursorDevOptions() || hasPendingCursorDevAnchor() || hasPendingScreenshotIntent()) return

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

  // ── 意图分叉（对等互斥，无优先级）：本条用户话决定走审核还是写码 ──
  // 截图附件：先判意图；拿不准就反问确认，禁止瞎走闲聊
  if (hasImageAttachments(filesSnapshot)) {
    const shot = classifyScreenshotIntent(content, filesSnapshot)
    if (shot.confidence === 'low' || shot.lane === 'ambiguous') {
      messages.value.push({
        role: 'assistant',
        content: '',
        intentClarify: buildScreenshotIntentClarifyCard(content, filesSnapshot, shot.hint),
        process: [],
        processCollapsed: true,
      })
      await persistSession()
      scrollToBottom()
      return
    }
    if (shot.lane === 'explain' || shot.lane === 'mes') {
      const prefix =
        shot.lane === 'explain'
          ? '【截图问答】用户贴了截图并希望解释画面/报错。请结合【截图理解】作答；信息不足时先反问再猜。\n\n'
          : '【截图+MES/业务】用户贴了截图并询问业务/平台操作。请结合【截图理解】与 MES 工具处理；不要擅自进写码/审核车道。\n\n'
      await startAssistantStream(
        `${prefix}用户说：${content || '（仅截图，请根据画面说明）'}`,
        filesSnapshot,
        null,
        null,
        null,
      )
      return
    }
    // code_dev / code_review / paste_code：落入下方既有分支
  }

  // 贴码分析：粘贴源码问问题 → 直连 Agent（paste-code-analyze），禁止选仓/审核卡
  if (looksLikePasteCodeAnalyze(content)) {
    await startAssistantStream(
      `【贴码分析】用户粘贴了源码并询问这段代码的问题或改法。\n` +
        `请启用 Skill「paste-code-analyze」：直接分析/给修复建议；\n` +
        `禁止 :::cursor_dev_*、禁止先选仓库、禁止写码确认卡、禁止 Git/IDE 全仓审核报告壳。\n\n` +
        `用户说：${content}`,
      filesSnapshot,
      null,
      null,
      pasteCodeStreamOpts(),
    )
    return
  }

  // 仅贴仓 URL：必须澄清，禁止默认开审（与「仅 URL ≠ 审核」一致）
  if (!hasPastedSourceFence(content) && isBareGitRepoUrlMessage(content)) {
    const repoUrl = extractGitRepoUrl(content)
    messages.value.push({
      role: 'assistant',
      content:
        `收到仓库地址：\`${repoUrl}\`\n\n` +
        `请说明意图（写码与审核是两条对等路由，只贴链接不会自动开写或开审）：\n` +
        `- **写码**：例如「在这个仓给登录页加一个选项」\n` +
        `- **审核**：例如「审核这个仓库」或「帮我审代码」`,
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  if (!hasPastedSourceFence(content) && (looksLikeGitRepoReview(content) || looksLikeCodeReview(content))) {
    await pushCodeReviewSourcePick(content, filesSnapshot)
    return
  }

  // 写码续聊：上一轮已完成（idle）且用户继续提改码需求 → 同一 job 走 Cursor
  const idlePick = findIdleCursorDevPick()
  if (
    !hasPastedSourceFence(content) &&
    !looksLikePasteCodeAnalyze(content) &&
    idlePick?.pick?.jobId &&
    looksLikeCursorDevFollowup(content, filesSnapshot)
  ) {
    const gate = await ensureCursorDevAvailableForUser()
    if (!gate.ok) {
      messages.value.push({ role: 'assistant', content: gate.message, process: [], processCollapsed: true })
      await persistSession()
      scrollToBottom()
      return
    }
    const ok = await beginCursorDevStream(idlePick.msg, {
      repo: idlePick.pick.repo,
      ref: idlePick.pick.ref || '',
      content,
      files: filesSnapshot,
      createPr: Boolean(idlePick.pick.createPr),
      existingJobId: idlePick.pick.jobId,
    })
    if (!ok) {
      // 同 job 续聊失败（如已 cancelled）→ 开新 job，仍保留仓/分支/需求上下文
      await beginCursorDevStream(idlePick.msg, {
        repo: idlePick.pick.repo,
        ref: idlePick.pick.ref || '',
        content,
        files: filesSnapshot,
        createPr: Boolean(idlePick.pick.createPr),
        existingJobId: '',
      })
    }
    return
  }

  // 写码讨论：新窗先选仓；旧窗直接续聊（与上方审核分支对等，互不抢）
  if (!hasPastedSourceFence(content) && shouldUseCodingDiscuss(content, filesSnapshot)) {
    await beginCodingDiscussEntry(content, filesSnapshot)
    return
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
  const workbuddyLane = String((opts && opts.workbuddyLane) || '').trim()
  const cursorDevLane =
    Boolean(opts && opts.cursorDevLane) || workbuddyLane === 'code_dev'
  const cursorDevRepo = String((opts && opts.cursorDevRepo) || '').trim()
  const cursorDevJobId = String((opts && opts.cursorDevJobId) || '').trim()
  const isCodeReviewLane =
    workbuddyLane === 'code_review' || Boolean(ideWorkspaceRoot) || Boolean(gitRepoUrl)
  const isPasteCodeLane = workbuddyLane === 'paste_code'
  const isCodeDevLane =
    !isPasteCodeLane &&
    (workbuddyLane === 'code_dev' || cursorDevLane || Boolean(cursorDevRepo))

  streamProcess.value = [{
    id: 'boot',
    type: 'step',
    state: 'running',
    title: resumeCtx
      ? '继续生成…'
      : isPasteCodeLane
        ? '正在分析粘贴代码…'
      : isCodeReviewLane && ideWorkspaceRoot
        ? '正在审核本机工程…'
        : isCodeReviewLane && gitRepoUrl
          ? '正在审核公开 Git 仓库…'
          : isCodeDevLane
            ? (cursorDevRepo ? `写码讨论：${cursorDevRepo}` : '写码需求讨论…')
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
    const filePaths = files
      .map((f) => f?.saved_name || (f?.path ? String(f.path).split(/[/\\]/).pop() : ''))
      .filter(Boolean)
    let extraPageContext = null
    if (isCodeReviewLane && ideWorkspaceRoot) {
      extraPageContext = {
        workbuddy_lane: 'code_review',
        ide_workspace_root: ideWorkspaceRoot,
        cursor_dev_lane: false,
        cursor_dev_repo: '',
        git_repo_url: '',
        git_ref: '',
      }
    } else if (isCodeReviewLane && gitRepoUrl) {
      extraPageContext = {
        workbuddy_lane: 'code_review',
        git_repo_url: gitRepoUrl,
        cursor_dev_lane: false,
        cursor_dev_repo: '',
        ide_workspace_root: '',
      }
      if (gitRef) extraPageContext.git_ref = gitRef
    } else if (isCodeDevLane) {
      // 写码分支：声明 code_dev，清空审核上下文，两条路由互不干涉
      extraPageContext = {
        workbuddy_lane: 'code_dev',
        cursor_dev_lane: true,
        git_repo_url: '',
        git_ref: '',
        ide_workspace_root: '',
      }
      if (cursorDevRepo) extraPageContext.cursor_dev_repo = cursorDevRepo
      if (cursorDevJobId) extraPageContext.cursor_dev_job_id = cursorDevJobId
    } else if (isPasteCodeLane) {
      extraPageContext = {
        workbuddy_lane: 'paste_code',
        cursor_dev_lane: false,
        cursor_dev_repo: '',
        git_repo_url: '',
        git_ref: '',
        ide_workspace_root: '',
      }
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
        let cursorDevPick = null
        let cursorDevOptions = null
        let cursorDevAnchor = null
        if (!confirms.length && !isPasteCodeLane) {
          const parsed = parseCursorDevMachineBlocks(finalContent)
          finalContent = parsed.content
          const wantCodingCard =
            (parsed.options || parsed.propose) &&
            !hasPendingCursorDevOptions() &&
            !hasPendingCursorDevPick() &&
            !hasPendingCursorDevAnchor()
          // 兜底：未选仓就出了选项/确认卡 → 改成先选仓（避免漏检意图时直出技术栈）
          if (wantCodingCard && !hasCursorDevRepoSession()) {
            let repos = []
            let defaultRepo = ''
            try {
              const rp = await fetchCursorDevRepos()
              repos = Array.isArray(rp?.data?.repos) ? rp.data.repos : []
              defaultRepo = rp?.data?.default_repo || repos[0] || ''
            } catch {
              /* ignore */
            }
            let pendingContent = ''
            let pendingFiles = []
            for (let i = messages.value.length - 1; i >= 0; i--) {
              if (messages.value[i]?.role === 'user') {
                pendingContent = String(messages.value[i].content || '').trim()
                pendingFiles = Array.isArray(messages.value[i].files)
                  ? [...messages.value[i].files]
                  : []
                break
              }
            }
            if (!pendingFiles.length) pendingFiles = codingSessionPendingFiles()
            finalContent = '请先选择本次要改的代码仓库。已有项目会现场读仓衔接；新项目再从头收集需求。'
            cursorDevAnchor = {
              id: `cursor-dev-anchor-${Date.now()}`,
              status: 'pending',
              repos,
              repo: defaultRepo,
              projectMode: 'existing',
              pendingContent,
              pendingFiles,
            }
          } else if (parsed.options && !hasPendingCursorDevOptions() && !hasPendingCursorDevPick()) {
            cursorDevOptions = {
              ...parsed.options,
              pendingFiles: codingSessionPendingFiles(),
            }
          } else if (parsed.propose && !hasPendingCursorDevPick() && !hasPendingCursorDevOptions()) {
            try {
              cursorDevPick = await buildCursorDevPickFromPropose(parsed.propose)
              if (cursorDevPick && cursorDevPick.available === false) {
                finalContent = [finalContent, cursorDevPick.reason || formatCursorDevAdminGuide()].filter(Boolean).join('\n\n')
                cursorDevPick = null
              }
            } catch (e) {
              console.error('build cursor-dev pick failed', e)
              finalContent = [finalContent, formatCursorDevAdminGuide(e?.message || e)].filter(Boolean).join('\n\n')
            }
          }
        } else if (!confirms.length && isPasteCodeLane) {
          // 贴码车道：剥掉误出的写码机器块，绝不出选仓卡
          const parsed = parseCursorDevMachineBlocks(finalContent)
          finalContent = parsed.content
        }
        if (finalContent || processItems.length || confirms.length || cursorDevPick || cursorDevOptions || cursorDevAnchor) {
          pushAssistantMessage({
            content: finalContent,
            processItems,
            confirms,
            durationText,
            stopped: false,
            cursorDevPick,
            cursorDevOptions,
            cursorDevAnchor,
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
  const nonImage = files.filter((f) => f.kind !== 'image')
  if (!nonImage.length) return text
  const fileList = nonImage.map((f) => `[附件: ${f.name}]`).join(' ')
  return text ? `${text} ${fileList}` : fileList
}

function removeAttachedFile(index) {
  attachedFiles.value.splice(index, 1)
}

async function handleFileUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  await attachLocalFile(file)
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
  window.addEventListener('keydown', onLightboxKeydown)
  await initFromRoute()
  if (inputEl.value) inputEl.value.focus()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onLightboxKeydown)
  closeImageLightbox()
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

.file-chip.image {
  border-radius: 12px;
  padding: 4px 8px 4px 4px;
}

.file-thumb {
  width: 36px;
  height: 36px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
  background: var(--ui-panel);
}

.msg-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.msg-attach-thumb-btn {
  display: inline-flex;
  padding: 0;
  border: none;
  background: transparent;
  cursor: zoom-in;
  border-radius: 10px;
}

.msg-attach-thumb-btn:hover .msg-attach-thumb {
  outline: 2px solid color-mix(in oklab, var(--ui-accent, #2563eb) 55%, transparent);
  outline-offset: 1px;
}

.msg-attach-thumb {
  display: block;
  max-width: min(280px, 70vw);
  max-height: 180px;
  object-fit: contain;
  border-radius: 10px;
  border: 1px solid var(--ui-border);
  background: var(--ui-panel-2);
}

.msg-attach-loading {
  max-width: min(280px, 70vw);
  min-height: 72px;
  align-items: center;
  justify-content: center;
  padding: 12px 14px;
  border: 1px dashed var(--ui-border);
  border-radius: 10px;
  background: var(--ui-panel-2);
  cursor: zoom-in;
}

.msg-attach-placeholder {
  font-size: 12px;
  color: var(--ui-text-muted);
}

.file-thumb {
  cursor: zoom-in;
}

.img-lightbox {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 24px;
  background: rgba(10, 12, 18, 0.78);
  backdrop-filter: blur(2px);
  outline: none;
}

.img-lightbox-img {
  max-width: min(96vw, 1400px);
  max-height: min(86vh, 900px);
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
  background: #111;
}

.img-lightbox-caption {
  margin: 0;
  max-width: 90vw;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  text-align: center;
}

.img-lightbox-close {
  position: absolute;
  top: 16px;
  right: 18px;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.img-lightbox-close:hover {
  background: rgba(255, 255, 255, 0.28);
}

.msg-attach-file {
  font-size: 12px;
  color: var(--ui-text-muted);
  padding: 4px 8px;
  border-radius: 8px;
  background: var(--ui-panel-2);
  border: 1px solid var(--ui-border);
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
