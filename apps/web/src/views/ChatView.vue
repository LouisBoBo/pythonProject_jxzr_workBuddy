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
          <div
            class="msg-body"
            v-if="msg.content && !msg.localDevCommitGate && !msg.localDevDeployGate"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <AnalysisDashboardCard
            v-for="(db, di) in (msg.dashboards || [])"
            :key="db.id || ('dash-' + di)"
            :board="db"
          />
          <AnalysisChartCard
            v-for="(ch, ci) in (msg.charts || [])"
            :key="ch.id || ('chart-' + ci)"
            :chart="ch"
          />
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
            :plan-steps="msg.codingPlan"
            @resolved="(payload) => onCursorDevPickResolved(msg, payload)"
          />
          <CursorDevMergeGuideCard
            v-if="msg.mergeGuide"
            :guide="msg.mergeGuide"
          />
          <LocalDevCommitGateCard
            v-if="msg.localDevCommitGate"
            :card="msg.localDevCommitGate"
            @resolved="(payload) => onLocalDevCommitResolved(msg, payload)"
          />
          <LocalDevDeployGateCard
            v-if="msg.localDevDeployGate"
            :card="msg.localDevDeployGate"
            @resolved="(payload) => onLocalDevDeployResolved(msg, payload)"
            @poll="(payload) => onLocalDevDeployPoll(msg, payload)"
          />
          <!-- 提交结果跟在确认卡下方；部署就绪时正文为空（说明已在卡内），触发后才追加短状态 -->
          <div
            class="msg-body"
            v-if="msg.content && (msg.localDevCommitGate || msg.localDevDeployGate)"
            v-html="renderMarkdown(msg.content)"
          ></div>
          <CodingPlanCard
            v-if="msg.codingPlan?.length && !msg.cursorDevPick"
            :steps="msg.codingPlan"
          />
          <ScreenshotIntentCard
            v-if="msg.intentClarify"
            :card="msg.intentClarify"
            @resolved="(payload) => onScreenshotIntentResolved(msg, payload)"
          />
          <div class="msg-actions" v-if="msg.content || msg.files?.length || (msg.confirms || []).length || msg.idePick || msg.gitPick || msg.codeReviewPick || msg.cursorDevPick || msg.cursorDevOptions || msg.cursorDevAnchor || msg.mergeGuide || msg.intentClarify || msg.localDevCommitGate || msg.localDevDeployGate">
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
          <!-- 写码确认卡已内嵌本轮进度时，流式气泡不再重复展示 -->
          <CodingPlanCard
            v-if="streamCodingPlan.length && !activeCursorDevMsg?.cursorDevPick"
            :steps="streamCodingPlan"
            heading="本轮进度"
            :collapsible="false"
            :default-collapsed="false"
          />
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
            :class="{ thinking: !streamContent, 'streaming-body': !!streamContent }"
          >
            <span v-if="!streamContent" class="thinking-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </span>
            <span v-else v-html="streamDisplayHtml"></span>
          </div>
          <!-- 图表/看板：流式期间只缓冲，等正文 token 结束并落入终稿消息后再展示，避免图先出、说明还在打字 -->
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
import { streamMessage, uploadFile, saveHistory, getHistoryDetail, fetchPendingWrites, fetchWriteAudit, fetchIdeBridgeStatus, fetchCursorDevStatus, fetchCursorDevRepos, fetchCursorDevRepoInspect, createCursorDevJob, streamCursorDevJob, cancelCursorDevJob, followupCursorDevJob, getCursorDevJob, fetchLocalDevStatus, fetchLocalWorkspacePref, saveLocalWorkspacePref, createLocalDevJob, streamLocalDevJob, cancelLocalDevJob, checkLocalDevWorkspace, confirmLocalDevScope, prepareLocalDevCommitBatch, startLocalDevCommitBatch, prepareLocalDevDeploy, getLocalDevJob } from '../api.js'
import ProcessPanel from '../components/ProcessPanel.vue'
import WriteConfirmCard from '../components/WriteConfirmCard.vue'
import AnalysisChartCard from '../components/AnalysisChartCard.vue'
import AnalysisDashboardCard from '../components/AnalysisDashboardCard.vue'
import IdeWorkspacePickCard from '../components/IdeWorkspacePickCard.vue'
import GitRepoPickCard from '../components/GitRepoPickCard.vue'
import CodeReviewSourcePickCard from '../components/CodeReviewSourcePickCard.vue'
import CursorDevRepoPickCard from '../components/CursorDevRepoPickCard.vue'
import CursorDevMergeGuideCard from '../components/CursorDevMergeGuideCard.vue'
import LocalDevCommitGateCard from '../components/LocalDevCommitGateCard.vue'
import LocalDevDeployGateCard from '../components/LocalDevDeployGateCard.vue'
import CursorDevRepoAnchorCard from '../components/CursorDevRepoAnchorCard.vue'
import CursorDevOptionsCard from '../components/CursorDevOptionsCard.vue'
import CodingPlanCard from '../components/CodingPlanCard.vue'
import ScreenshotIntentCard from '../components/ScreenshotIntentCard.vue'
import AiAvatarIcon from '../components/AiAvatarIcon.vue'
import { getUsername, getUserId, authHeaders } from '../auth.js'
import { renderMarkdown, renderStreamingMarkdown } from '../markdown.js'
import {
  cursorDevSpeedLabel,
  formatCursorDevUserError,
  formatPickFailureSummary,
  inferChannelFromEvent,
  pickPatchFromJobStatus,
} from '../cursorDevUx.js'
import {
  buildScreenshotIntentClarifyCard,
  classifyScreenshotIntent,
  extractGitRepoUrl,
  hasCodeDevActionWords,
  hasImageAttachments,
  hasPastedSourceFence,
  isBareGitRepoUrlMessage,
  isVagueCodeDevIntent,
  laneLabel,
  looksLikeCodeDevIntent,
  looksLikeCodeReview,
  looksLikeGitRepoReview,
  looksLikeGuidedShotEditIntent,
  looksLikeLocalCommitBatch,
  looksLikeDeploy,
  looksLikeMesBizIntent,
  looksLikePasteCodeAnalyze,
  looksLikeRawPastedCode,
  looksLikeScreenshotExplainIntent,
  looksLikeScreenshotUiRedesign,
  looksLikeVisualMatchIntent,
  pasteCodeStreamOpts,
} from '../chatIntent.js'
import {
  formatCursorDevAdminGuide,
  hideCursorDevMachineBlocks,
  hideCursorDevPropose,
  parseCursorDevMachineBlocks as parseCursorDevMachineBlocksCore,
  stripCursorDevMergeBoilerplate,
} from '../chatCursorDevParse.js'
import {
  mergeUniqueCharts,
  parseAnalysisChartFences,
} from '../chatAnalysisChartParse.js'
import {
  looksLikeCursorDevFollowup,
  planCursorDevTurn,
} from '../chatCursorDevPlan.js'

const route = useRoute()
const router = useRouter()

const messages = ref([])
const input = ref('')
const streaming = ref(false)
const streamAbort = ref(null)
const streamContent = ref('')
/** 流式气泡展示用 HTML（节流刷新，避免表格每 token 重排闪烁） */
const streamDisplayHtml = ref('')
const streamProcess = ref([])
const streamCodingPlan = ref([])
const streamProcessCollapsed = ref(false)
const streamDurationText = ref('')
const streamStartedAt = ref(0)
const streamAnswerPending = ref(false)
const streamConfirms = ref([])
const streamCharts = ref([])
const streamDashboards = ref([])
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
/** 组件仍挂载；thread 切换会销毁实例，异步 loadSession 收尾需检查 */
let chatViewAlive = true
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
  charts,
  dashboards,
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
    charts: charts || [],
    dashboards: dashboards || [],
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

/** 写码过程区收尾：把残留 running（尤其「核对中」心跳）封成完成/失败 */
function sealCursorDevProcessSteps(items, { asError = false } = {}) {
  return (items || []).map((i) => {
    if (i?.type !== 'step') return i
    if (i.state !== 'running' && i.state !== 'waiting') return i
    const sealed = { ...i, state: asError ? 'error' : 'done' }
    if (i.id === 'cursor-heartbeat' || /核对中|执行中（\d+s/.test(String(i.title || ''))) {
      sealed.title = asError ? 'Cursor 本轮未正常结束' : 'Cursor 本轮已结束'
    }
    return sealed
  })
}

async function stopStreaming() {
  if (!streaming.value) return
  let cursorJobId = String(activeCursorDevJobId.value || '').trim()
  const cursorMsg = activeCursorDevMsg.value
  // 兜底：active id 丢了时仍按确认卡 jobId 取消，避免假死 running
  if (!cursorJobId && cursorMsg?.cursorDevPick?.jobId) {
    cursorJobId = String(cursorMsg.cursorDevPick.jobId || '').trim()
  }
  if (!cursorJobId) {
    const stuck = findRunningCursorDevPick()
    if (stuck?.pick?.jobId) cursorJobId = String(stuck.pick.jobId)
  }
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
      if (
        String(cursorJobId).startsWith('ldj-') ||
        cursorMsg?.cursorDevPick?.target === 'local' ||
        cursorMsg?.cursorDevPick?.channel === 'local_sandbox'
      ) {
        await cancelLocalDevJob(cursorJobId, '用户停止')
      } else {
        await cancelCursorDevJob(cursorJobId, '用户停止')
      }
    } catch {
      /* ignore */
    }
    const pickMsg =
      cursorMsg ||
      messages.value.find((m) => String(m?.cursorDevPick?.jobId || '') === cursorJobId) ||
      null
    if (pickMsg?.cursorDevPick) {
      pickMsg.cursorDevPick = {
        ...pickMsg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: formatPickFailureSummary('已停止写码', { userStopped: true }),
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
  const processItems = sealCursorDevProcessSteps(
    (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
    { asError: false },
  )
  const confirms = (streamConfirms.value || []).map((c) => ({ ...c }))
  let finalContent = (streamContent.value || '').trimEnd()
  if (confirms.length) {
    const stable = buildImportSummaryMarkdown(confirms[0].preview)
    if (stable) finalContent = stable
  }
  const stoppedNote = cursorJobId
    ? `（已停止写码）\n下一步：在上方确认卡点「重试写码」。`
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
    charts: (streamCharts.value || []).map((c) => ({ ...c })),
    dashboards: (streamDashboards.value || []).map((d) => ({ ...d })),
    durationText,
    stopped: true,
  })
  streamContent.value = ''
  resetStreamDisplay()
  streamProcess.value = []
  streamConfirms.value = []
  streamCharts.value = []
  streamDashboards.value = []
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

let streamPaintRaf = 0
let streamScrollTimer = 0
let streamLastPaintAt = 0
let streamLastScrollAt = 0
const STREAM_PAINT_MIN_MS = 120
const STREAM_SCROLL_MIN_MS = 160

function paintStreamDisplay(force = false) {
  const now = Date.now()
  if (!force && now - streamLastPaintAt < STREAM_PAINT_MIN_MS) {
    if (!streamPaintRaf) {
      streamPaintRaf = requestAnimationFrame(() => {
        streamPaintRaf = 0
        paintStreamDisplay(true)
      })
    }
    return
  }
  streamLastPaintAt = now
  if (streamPaintRaf) {
    cancelAnimationFrame(streamPaintRaf)
    streamPaintRaf = 0
  }
  const raw = hideCursorDevPropose(streamContent.value || '')
  const next = raw ? renderStreamingMarkdown(raw) : ''
  // 相同 HTML 不写回，减少无意义的 v-html 重挂载
  if (next === streamDisplayHtml.value) return
  streamDisplayHtml.value = next
}

function scrollToBottomThrottled() {
  const el = msgContainer.value
  if (!el) return
  // 用户上翻阅读时不硬拽到底
  const dist = el.scrollHeight - el.scrollTop - el.clientHeight
  if (dist > 140) return
  const now = Date.now()
  if (now - streamLastScrollAt < STREAM_SCROLL_MIN_MS) {
    if (streamScrollTimer) return
    streamScrollTimer = setTimeout(() => {
      streamScrollTimer = 0
      scrollToBottomThrottled()
    }, STREAM_SCROLL_MIN_MS - (now - streamLastScrollAt))
    return
  }
  streamLastScrollAt = now
  el.scrollTop = el.scrollHeight
}

function resetStreamDisplay() {
  if (streamPaintRaf) {
    cancelAnimationFrame(streamPaintRaf)
    streamPaintRaf = 0
  }
  if (streamScrollTimer) {
    clearTimeout(streamScrollTimer)
    streamScrollTimer = 0
  }
  streamLastPaintAt = 0
  streamLastScrollAt = 0
  streamDisplayHtml.value = ''
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
    ...(m.charts?.length ? { charts: m.charts } : {}),
    ...(m.dashboards?.length ? { dashboards: m.dashboards } : {}),
    ...(m.idePick ? { idePick: m.idePick } : {}),
    ...(m.gitPick ? { gitPick: m.gitPick } : {}),
    ...(m.codeReviewPick ? { codeReviewPick: m.codeReviewPick } : {}),
    ...(m.cursorDevPick ? { cursorDevPick: m.cursorDevPick } : {}),
    ...(m.cursorDevOptions ? { cursorDevOptions: m.cursorDevOptions } : {}),
    ...(m.cursorDevAnchor ? { cursorDevAnchor: m.cursorDevAnchor } : {}),
    ...(m.mergeGuide ? { mergeGuide: m.mergeGuide } : {}),
    ...(m.intentClarify ? { intentClarify: m.intentClarify } : {}),
    ...(m.localDevCommitGate ? { localDevCommitGate: m.localDevCommitGate } : {}),
    ...(m.localDevDeployGate ? { localDevDeployGate: m.localDevDeployGate } : {}),
    ...(Array.isArray(m.codingPlan) && m.codingPlan.length ? { codingPlan: m.codingPlan } : {}),
    // 截图/附件：保留 path 供视觉与写码；预览只留短 dataURL（过大则丢，靠 path）
    ...(Array.isArray(m.files) && m.files.length
      ? {
          files: m.files.map((f) => {
            const preview = String(f?.previewDataUrl || '')
            return {
              id: f?.id,
              name: f?.name,
              status: f?.status || 'done',
              path: f?.path || f?.saved_name || '',
              saved_name: f?.saved_name || f?.path || '',
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
  // 流式进行中禁止改 thread（App 按 key 重挂载会掐断当前请求）
  if (streaming.value) return
  router.replace({ path: '/', query: { thread: id } })
}

/** 保证有会话 id：优先沿用路由上的 thread，避免中途 sync 触发整页重建 */
function ensureThreadId() {
  if (threadId.value) return threadId.value
  const fromRoute = route.query.thread
  if (typeof fromRoute === 'string' && fromRoute) {
    threadId.value = fromRoute
    return fromRoute
  }
  const id = createThreadId()
  threadId.value = id
  syncThreadQuery(id)
  return id
}

async function loadSession(id) {
  const requestId = (activeRequestId += 1)
  try {
    streamAbort.value?.abort()
  } catch {
    /* ignore */
  }
  streamAbort.value = null
  clearActiveCursorDev()
  loadingSession.value = true
  threadId.value = id
  streamContent.value = ''
  streamProcess.value = []
  streamConfirms.value = []
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamAnswerPending.value = false
  streamCodingPlan.value = []
  attachedFiles.value = []
  streaming.value = false
  editingFromIndex.value = -1
  copiedIndex.value = -1
  try {
    const resp = await getHistoryDetail(id)
    if (!chatViewAlive || requestId !== activeRequestId) return
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
        ...(Array.isArray(m.charts) && m.charts.length
          ? { charts: m.charts.map((c) => ({ ...c })) }
          : {}),
        ...(Array.isArray(m.dashboards) && m.dashboards.length
          ? {
              dashboards: m.dashboards.map((d) => ({
                ...d,
                charts: Array.isArray(d?.charts)
                  ? d.charts.map((c) => ({ ...c }))
                  : [],
                kpis: Array.isArray(d?.kpis) ? d.kpis.map((k) => ({ ...k })) : [],
                gaps: Array.isArray(d?.gaps) ? d.gaps.map((g) => ({ ...g })) : [],
              })),
            }
          : {}),
        ...(m.idePick ? { idePick: { ...m.idePick } } : {}),
        ...(m.gitPick ? { gitPick: { ...m.gitPick } } : {}),
        ...(m.codeReviewPick ? { codeReviewPick: { ...m.codeReviewPick } } : {}),
        ...(m.cursorDevPick ? { cursorDevPick: { ...m.cursorDevPick } } : {}),
        ...(m.cursorDevOptions ? { cursorDevOptions: { ...m.cursorDevOptions } } : {}),
        ...(m.cursorDevAnchor ? { cursorDevAnchor: { ...m.cursorDevAnchor } } : {}),
        ...(m.mergeGuide ? { mergeGuide: { ...m.mergeGuide } } : {}),
        ...(m.intentClarify ? { intentClarify: { ...m.intentClarify } } : {}),
        ...(m.localDevCommitGate ? { localDevCommitGate: { ...m.localDevCommitGate } } : {}),
        ...(m.localDevDeployGate ? { localDevDeployGate: { ...m.localDevDeployGate } } : {}),
        ...(Array.isArray(m.codingPlan) && m.codingPlan.length
          ? { codingPlan: m.codingPlan.map((s) => ({ ...s })) }
          : {}),
        processCollapsed: true,
      }
    })
    scrollToBottom()
  } catch {
    if (!chatViewAlive || requestId !== activeRequestId) return
    // 新会话或尚未入库：空消息即可继续聊
    messages.value = []
  } finally {
    if (chatViewAlive && requestId === activeRequestId) {
      loadingSession.value = false
    }
  }
  // App 按 thread 重挂载时，旧实例的异步收尾不得再挂写码流
  if (!chatViewAlive || requestId !== activeRequestId) return
  nextTick(() => inputEl.value?.focus())
  await attachPendingConfirms(id)
  if (!chatViewAlive || requestId !== activeRequestId) return
  await loadWriteAudit(id)
  if (!chatViewAlive || requestId !== activeRequestId) return
  // 刷新/重进会话时：修正「写码进行中」假状态，或重新挂上仍在跑的 job
  void resumeOrReconcileCursorDevAfterLoad()
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
  clearActiveCursorDev()
  const id = createThreadId()
  threadId.value = id
  messages.value = []
  streamContent.value = ''
  streamProcess.value = []
  streamConfirms.value = []
  streamProcessCollapsed.value = false
  streamDurationText.value = ''
  streamAnswerPending.value = false
  streamCodingPlan.value = []
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

// 会话切换由 App.vue 的 router-view :key="thread" 整页重挂载；
// 此处不再 watch thread，避免旧实例异步 loadSession 与新实例抢流。

// 车道/意图启发式见 ../chatIntent.js

function hasCodingDiscussThread() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m?.cursorDevPick || m?.cursorDevOptions || m?.cursorDevAnchor) return true
    if (m?.role === 'user' && looksLikeCodeDevIntent(m.content, m.files || [])) return true
  }
  return false
}

/** 本线程是否已定点（本机目录或 GitHub 仓，或已进入选项/确认卡） */
function hasCursorDevRepoSession() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const a = m?.cursorDevAnchor
    if (a && a.status === 'confirmed' && (a.workspace || a.repo)) return true
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
  const localWs = String(
    fromExtra.localWorkspaceRoot || hit?.anchor?.workspace || '',
  ).trim()
  return {
    ...fromExtra,
    force: true,
    workbuddyLane: 'code_dev',
    cursorDevLane: true,
    ...(repo ? { cursorDevRepo: repo } : {}),
    ...(localWs ? { localWorkspaceRoot: localWs } : {}),
  }
}

function findConfirmedCursorDevAnchor() {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    const a = m?.cursorDevAnchor
    if (a && a.status === 'confirmed' && (a.workspace || a.repo)) {
      return { msg: m, anchor: a, index: i }
    }
  }
  return null
}

/** 本线程锚定后的上下文块（本机目录 / GitHub 已有或新项目） */
function codingSessionContextBlock() {
  const hit = findConfirmedCursorDevAnchor()
  if (!hit) return ''
  const block = String(hit.anchor.promptBlock || '').trim()
  if (block) return block
  if (hit.anchor.target === 'local' || hit.anchor.workspace) {
    const ws = hit.anchor.workspace
    if (hit.anchor.projectMode === 'new') {
      return (
        `【本会话已选定本机新项目目录】\n` +
        `路径：${ws}\n` +
        `空目录从零生成；:::cursor_dev_propose 默认 target=local，workspace 填 \`${ws}\`。`
      )
    }
    return (
      `【本会话已选定本机工程目录】\n` +
      `路径：${ws}\n` +
      `按已有工程增量开发；:::cursor_dev_propose 默认 target=local，workspace 填 \`${ws}\`；不要问 GitHub 仓库。`
    )
  }
  const repo = hit.anchor.repo
  if (hit.anchor.projectMode === 'new') {
    return (
      `【本会话已选定新项目仓库】\n` +
      `仓库：${repo}\n` +
      `这是新项目：从头收集需求与技术栈；:::cursor_dev_propose 的 target=github、repo 必须填 \`${repo}\`。`
    )
  }
  return (
    `【本会话已选定已有仓库】\n` +
    `仓库：${repo}\n` +
    `按该仓增量开发；:::cursor_dev_propose 的 target=github、repo 填 \`${repo}\`。`
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
    if (
      pick &&
      pick.status === 'confirmed' &&
      (pick.phase === 'running' || pick.phase === 'starting') &&
      pick.jobId
    ) {
      return { msg: m, pick, index: i }
    }
  }
  return null
}

/**
 * 对账：确认卡停在「写码进行中」，但服务端 job 已取消/失败/完成时，修正卡片状态。
 * 避免点停止/流断开后仍显示进行中，用户误以为「确认了却没写码」。
 */
async function reconcileStuckCursorDevPicks() {
  if (streaming.value) return false
  let changed = false
  for (const m of messages.value) {
    const pick = m?.cursorDevPick
    if (!pick || pick.status !== 'confirmed' || (pick.phase !== 'running' && pick.phase !== 'starting'))
      continue
    const jobId = String(pick.jobId || '').trim()
    if (!jobId) {
      m.cursorDevPick = {
        ...pick,
        status: 'failed',
        phase: 'failed',
        error: formatPickFailureSummary('写码任务状态丢失'),
        progressText: '',
      }
      changed = true
      continue
    }
    if (String(activeCursorDevJobId.value || '') === jobId) continue
    try {
      const resp = await getCursorDevJob(jobId)
      const patch = pickPatchFromJobStatus(pick, resp?.data || {})
      if (patch) {
        m.cursorDevPick = { ...pick, ...patch, jobId }
        changed = true
      }
    } catch {
      /* 拉不到任务时不强制改，避免误伤 */
    }
  }
  if (changed) await persistSession()
  return changed
}

/** 加载会话后：若仍有 running 卡，对账或重新挂上 SSE（绝不对 running 发 followup） */
async function resumeOrReconcileCursorDevAfterLoad() {
  const stuck = findRunningCursorDevPick()
  if (!stuck?.pick?.jobId || streaming.value) {
    await reconcileStuckCursorDevPicks()
    return
  }
  try {
    const resp = await getCursorDevJob(stuck.pick.jobId)
    const st = String(resp?.data?.status || '')
    // queued / running / failed：只挂流（软挂接或重跑），禁止 messages 续聊
    if (st === 'queued' || st === 'running' || st === 'failed') {
      await beginCursorDevStream(stuck.msg, {
        repo: stuck.pick.repo,
        ref: stuck.pick.ref || '',
        content: stuck.pick.requirement || stuck.pick.pendingContent || '',
        files: Array.isArray(stuck.pick.pendingFiles) ? stuck.pick.pendingFiles : [],
        createPr: Boolean(stuck.pick.createPr),
        existingJobId: stuck.pick.jobId,
        attachOnly: true,
      })
      return
    }
  } catch {
    /* fall through */
  }
  await reconcileStuckCursorDevPicks()
}

// 写码本轮意图规划见 ../chatCursorDevPlan.js

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
  // 重做/设计感优先于正文里残留的「按截图位置 / 与截图一致」（旧 propose 常见）
  const redesignIntent =
    /(重做|重新设计|重新构图|换个布局|换布局|(?:页面|界面|概览|看板|仪表盘|首页).{0,12}重写|重写.{0,12}(?:页面|界面|概览|看板)|更好看|设计感|有设计感|不要?照抄|别照抄|不要?像首页|不要?雷同|不要?套模板|不要按旧|不要按截图|非按截图|不要五卡|非五卡|全新(?:构图|排版|设计|工业)|杂志排版|杂志风|彻底区分|新排版|新构图)/.test(
      textForLane,
    ) && !looksLikeVisualMatchIntent(textForLane)
  const strongShotFidelity = looksLikeVisualMatchIntent(textForLane)
  const guidedShotEdit =
    !strongShotFidelity && !redesignIntent && looksLikeGuidedShotEditIntent(textForLane)
  const cssLayoutOnly =
    /(overflow(?:-x|-y)?|100vh|100vw|滚动|横向溢出|超出屏幕|X\s*方向|视口固定|页面固定|框架滚动|纯\s*CSS|仅.*样式|不[改动变].{0,6}(视觉|配色|图表|表格)|布局壳|侧边栏.*滚动|内容区.*滚动|无横向)/i.test(
      textForLane,
    ) && !strongShotFidelity && !guidedShotEdit && !/(【截图理解】|复刻|按截图)/i.test(textForLane)
  // 视觉对齐或按图修改都算 uiFromShot；重做盖过弱残留
  const uiFromShot =
    !cssLayoutOnly &&
    (strongShotFidelity ||
      guidedShotEdit ||
      (!redesignIntent &&
        /改成这种|改为这种|做成这种|照着|仿照|按这个|按截图|1\s*:\s*1|1：1|复刻|【截图理解】|与截图一致|按截图位置|跟(?:截图|图)一样|按这个效果|设计稿|效果图/.test(
          textForLane,
        )))
  const pageUiDesign =
    !cssLayoutOnly &&
    (redesignIntent ||
      /(界面|页面|概览|看板|仪表盘|首页|视图|更好看|设计感|美观|不要?照抄|不要?像首页)/.test(
        textForLane,
      ))
  const optionsHardRule =
    `【交互铁律】能勾选就不输入。禁止表格/A~D/「请回复xxx」。正文最多 1～2 句。` +
    `同一轮不要同时输出 propose。备注能空就空。\n\n`
  const cssLayoutRule = cssLayoutOnly
    ? `【任务档位 · css_layout】本需求是溢出/滚动/宽度自适应修复。` +
      `够开工则直接 :::cursor_dev_propose；requirement 开头必须写【任务档位：css_layout】，` +
      `写明用户原文中的目标页面/模块名与验收（整页无横向滚动；表格可内部横滚）。` +
      `禁止扩写业务；禁止改图表类型/配色/表格数据。\n\n`
    : ''
  const intentPlanRule =
    `【意图规划】先判断用户本轮是「新交付」还是「对已确认需求的增量微调」。` +
    `新模块/新界面/新功能或范围不清：必须 :::cursor_dev_options 或澄清后再 :::cursor_dev_propose。` +
    `禁止因为同会话曾写过码就跳过确认直接开写。按用户原文规划，不要套固定页面模板。\n\n`
  const uiDesignRule = pageUiDesign
    ? redesignIntent && !strongShotFidelity
      ? `【产品设计 · 重做优先 · Skill ui-product-design】用户要重做/有设计感：` +
        `旧截图、旧「按截图位置」五卡骨架、【截图理解】只可作字段/模块清单参考，**不是布局合同**。` +
        `propose 禁止写「五卡布局与截图一致 / 视觉布局（按截图位置）」；须写新构图。` +
        `requirement 结构：页面身份（与首页/看板差异）→ 信息层级与新布局 → 保留的业务字段 → 禁止照抄 → 验收（并排不可雷同，须有新视觉签名）。` +
        `禁止默认 Element 白卡片 KPI 墙、禁止双 gauge 完全同款复制粘贴。\n\n`
      : `【产品设计 · Skill ui-product-design】做/改业务页时必须有设计感：一页一身份、信息有主次。` +
        `禁止把首页/Home 布局骨架复制到其它业务页只改标题；须独立视图组件。` +
        `propose 的 requirement 须含：页面身份（与首页差异）→ 信息层级 → 禁止照抄 → 验收（与首页并排布局不可雷同）。` +
        `禁止默认 Element 白卡片 KPI 墙、禁止双 gauge 完全同款复制粘贴。\n\n`
    : ''
  const uiShotRule = uiFromShot
    ? strongShotFidelity
      ? `【截图即设计稿 · 视觉对齐 · 质量优先】用户真实意图是效果跟截图一样` +
        `（话术可能是 1:1/复刻/改成这种/跟截图一样/按这个效果等，不要求必须说「1:1」）。` +
        `【截图理解】与原图为最高优先级 UI 规格。禁止占位图/假 Logo 交差。` +
        `requirement 须含主视觉/Logo 资源方案与真正视觉对齐验收。信息够则直接 propose。\n\n`
      : guidedShotEdit
        ? `【按截图修改 · 对准改动点】用户是参照截图改一部分（含红框/标注去掉某块），不一定整页复刻。` +
          `消息里若有【截图理解】必须当规格用，禁止再说「本轮没收到截图/未识别到截图理解」。` +
          `红框/标注指向的区域就是改动目标，禁止再问「红框指哪」或出勾选卡确认位置。` +
          `先改用户点名的点；未点名区域保持现状。若上下文其实是「整页跟截图一样」，按视觉对齐处理。\n\n`
        : `【截图即设计稿 · 视觉优先】用户已贴界面截图并要求按图改界面。` +
          `先判断是「整页跟截图一样」还是「只改图上某处」；拿不准时选项卡确认。` +
          `消息里若有【截图理解】，把它当作 UI 规格。禁止臆造模块、禁止白卡片模板偷换色块仪表盘。\n\n`
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
    `{"title":"按截图复刻，请确认","summary":"布局以截图为准，质量优先","notes_placeholder":"其它备注（可选）","groups":[{"id":"ui_scope","label":"本轮改动范围","multi":true,"required":true,"options":[{"id":"dash_home","label":"复刻首页/仪表盘主区（按截图模块）"},{"id":"sidebar_nav","label":"含左侧侧边栏/顶栏导航"},{"id":"charts_visual","label":"图表类型与色块按截图（非白卡片模板）"},{"id":"keep_stack","label":"沿用现有技术栈，视觉按截图"}]},{"id":"ui_fidelity","label":"还原精度","multi":false,"required":true,"options":[{"id":"visual_1to1","label":"真正 1:1：布局/色块/主视觉资源/控件样式对齐截图"},{"id":"visual_high","label":"高还原：允许个别装饰简化但主构图必须一致"}]}]}\n` +
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
        : redesignIntent && !strongShotFidelity
          ? `:::cursor_dev_propose\n` +
            `{"requirement":"## 页面身份（重做，非按截图骨架）\\n- 与首页/看板差异：…\\n## 新构图与信息层级\\n- …\\n## 保留业务字段\\n- …\\n## 禁止\\n- 照抄 Home；照搬旧「顶行双 gauge+底表」截图骨架\\n## 验收\\n- 并排不可雷同；有新视觉签名","repo":"","ref":""}\n` +
            `:::\n`
          : pageUiDesign
            ? `:::cursor_dev_propose\n` +
              `{"requirement":"## 页面身份\\n- 与首页差异：…\\n## 信息层级\\n- 首屏主指标 / 次要区 / 明细\\n## 禁止照抄\\n- 独立视图，不复制 Home 布局\\n## 验收\\n- 与首页并排布局不可雷同；有主次层级","repo":"","ref":""}\n` +
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
  const userFirst =
    redesignIntent && !strongShotFidelity
      ? `【本轮用户原话最高优先 · 盖过上下文一切旧截图/旧propose/前序摘要】\n用户说：${userText}\n\n` +
        `若上下文有「按截图位置 / 五卡 / 与截图一致 /【截图理解】」一律忽略布局合同，只可留业务字段。\n` +
        `够开工则直接 :::cursor_dev_propose，requirement 写新构图（工业灰蓝杂志风等用户指定风格），禁止再写按截图骨架。\n\n`
      : ''
  return (
    `【写码需求讨论 · 远程 Cursor Cloud】用户要改的是 GitHub 远程仓库代码，不是本机沙箱。` +
    `禁止：建议 echo/vim/本机 clone；禁止任何 IDE/Git 审核工具（request_git_* / request_ide_*，含筛选功能源码）；` +
    `禁止输出代码审核报告；禁止未确认就声称已开 PR。` +
    `仓库名/分支只表示要改哪个仓，绝不等于要审核。` +
    `最终改仓必须 :::cursor_dev_propose。` +
    ctxPart +
    userFirst +
    cssLayoutRule +
    intentPlanRule +
    uiDesignRule +
    uiShotRule +
    optionsHardRule +
    strategy +
    `仅当需求已足够开工时输出：\n` +
    proposeExampleUi +
    (userFirst ? '' : `\n用户说：${userText}`)
  )
}

// 分析图机器块解析见 ../chatAnalysisChartParse.js

function sessionStackLocked() {
  const hit = findConfirmedCursorDevAnchor()
  const block = String(hit?.anchor?.promptBlock || '')
  return /技术栈已锁定|禁止再问技术栈|已锁定技术栈/.test(block)
}

// 写码机器块解析见 ../chatCursorDevParse.js；技术栈锁定由会话态注入
function parseCursorDevMachineBlocks(text) {
  return parseCursorDevMachineBlocksCore(text, { stackLocked: sessionStackLocked() })
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
  let localAvailable = true
  let localReason = ''
  let lastWorkspace = ''
  try {
    const [stResp, repoResp, localStResp, prefResp] = await Promise.all([
      fetchCursorDevStatus().catch(() => null),
      fetchCursorDevRepos().catch(() => null),
      fetchLocalDevStatus().catch(() => null),
      fetchLocalWorkspacePref().catch(() => null),
    ])
    const st = stResp?.data || {}
    const rp = repoResp?.data || {}
    available = Boolean(st.available) && st.user_allowed !== false
    reason = st.reason || rp.reason || ''
    repos = Array.isArray(rp.repos) ? rp.repos : []
    defaultRepo = st.default_repo || rp.default_repo || repos[0] || ''
    defaultRef = st.starting_ref || rp.starting_ref || ''
    const lst = localStResp?.data || {}
    localAvailable = lst.available !== false
    localReason = lst.reason || ''
    lastWorkspace = String(prefResp?.data?.path || '').trim()
  } catch (e) {
    reason = e?.response?.data?.detail || e?.message || '无法加载写码配置'
    available = false
  }
  // 优先用本会话已选目标（本机目录 / GitHub 锚点），再回落到 propose / 默认
  const repo = propose.repo || defaultRepo || ''
  const ref =
    propose.ref != null && String(propose.ref).trim() !== ''
      ? String(propose.ref).trim()
      : defaultRef
  const anchored = findConfirmedCursorDevAnchor()?.anchor || null
  const anchoredWs = String(anchored?.workspace || '').trim()
  const anchoredRepo = String(anchored?.repo || '').trim()
  const resolvedRepo = propose.repo || anchoredRepo || repo
  const workspace = String(propose.workspace || anchoredWs || lastWorkspace || '').trim()
  // 会话已锚定本机时，强制默认 local（除非 propose 明确 github）
  let target = String(propose?.target || 'local').toLowerCase() === 'github' ? 'github' : 'local'
  if (anchored?.target === 'local' || (anchoredWs && !propose.repo && propose?.target !== 'github')) {
    target = 'local'
  }
  if (anchored?.target === 'github' && propose?.target !== 'local') {
    target = 'github'
  }
  const files = codingSessionPendingFiles()
  return {
    id: `cursor-dev-pick-${Date.now()}`,
    status: 'pending',
    target,
    workspace,
    lastWorkspace: lastWorkspace || anchoredWs,
    localAvailable,
    localReason: localAvailable ? '' : localReason,
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

async function beginCursorDevStream(
  msg,
  { repo, ref, content, files, createPr = false, existingJobId = '', attachOnly = false },
) {
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
      phase: 'starting',
      progressText: attachOnly ? '正在重新挂接写码进度…' : '正在创建写码任务…',
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
      // 开新任务会自动取消旧 active：把同会话其它「写码进行中」卡落到可重试
      if (warnings.some((w) => /自动结束你上一次|新任务为准/.test(String(w)))) {
        for (const m of messages.value) {
          const p = m?.cursorDevPick
          if (!p || p === msg?.cursorDevPick) continue
          if (p.status === 'confirmed' && (p.phase === 'running' || p.phase === 'starting')) {
            m.cursorDevPick = {
              ...p,
              status: 'failed',
              phase: 'failed',
              error: '已开新写码任务，本轮被自动结束。可点「重试写码」补救。',
              userStopped: true,
              progressText: '',
            }
          }
        }
      }
    } else if (!attachOnly) {
      // 仅 idle/failed 续聊可 followup；running/queued 绝不可 messages（会 409）
      let jobStatus = ''
      try {
        const stResp = await getCursorDevJob(jobId)
        jobStatus = String(stResp?.data?.status || '')
      } catch {
        jobStatus = ''
      }
      if (jobStatus === 'cancelled' || jobStatus === 'queued' || jobStatus === 'running') {
        // 已取消 / 仍在跑：交给上层 forceNew 或 attachOnly；此处勿 followup
        if (jobStatus === 'cancelled') {
          throw new Error('任务已取消，不可续聊；将自动开新任务')
        }
        // queued/running：直接挂流，不追加 messages
      } else {
        await followupCursorDevJob(jobId, {
          message: content,
          create_pr: Boolean(createPr),
          confirmed: true,
          file_paths: filePaths,
        })
      }
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
        error: formatPickFailureSummary(detail),
        repo,
        ref: String(ref || '').trim(),
        requirement: content,
        createPr: Boolean(createPr),
        progressText: '',
      }
    }
    messages.value.push({
      role: 'assistant',
      content: /CURSOR_API_KEY|白名单|未开启|不可用/i.test(String(detail))
        ? formatCursorDevAdminGuide(detail)
        : formatCursorDevUserError(detail),
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

  ensureThreadId()

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

    // 真实工具/状态步骤到来时，关掉「核对中」心跳，避免夹在已完成步骤中间仍显示执行中
    if (id !== 'cursor-heartbeat') {
      for (let i = 0; i < steps.length; i++) {
        if (steps[i].id === 'cursor-heartbeat' && steps[i].state === 'running') {
          steps[i] = {
            ...steps[i],
            state: 'done',
            title: 'Cursor 云端进度已更新',
          }
        }
      }
    }

    // 新步骤进入执行中时，把其它仍 running 的标为完成，避免「全是执行中」像卡死
    if (nextState === 'running') {
      for (let i = 0; i < steps.length; i++) {
        if (steps[i].id !== item.id && steps[i].state === 'running') {
          steps[i] = { ...steps[i], state: 'done' }
        }
      }
    }

    // 心跳刷新：挪到列表末尾，避免「中间核对中、后面已完成」的错乱时间线
    if (id === 'cursor-heartbeat' && nextState === 'running') {
      const hbIdx = steps.findIndex((s) => s.id === 'cursor-heartbeat')
      if (hbIdx >= 0 && hbIdx !== steps.length - 1) {
        const [hb] = steps.splice(hbIdx, 1)
        steps.push(hb)
      }
    }

    streamProcess.value = steps
  }

  /** 收尾时把残留 running（尤其核对心跳）封成完成/失败，避免摘要已出但过程区仍「执行中」 */
  const sealProcessSteps = (items, opts) => sealCursorDevProcessSteps(items, opts)


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

  const applyChannelMeta = (event) => {
    if (!msg?.cursorDevPick) return
    const meta = inferChannelFromEvent(event)
    if (!meta.channel && !meta.speedHint) return
    msg.cursorDevPick = { ...msg.cursorDevPick, ...meta }
  }

  const touchProgress = (text) => {
    lastEventAt = Date.now()
    const elapsed = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
    streamDurationText.value = `${elapsed}s`
    if (!msg?.cursorDevPick) return
    const speed = cursorDevSpeedLabel(msg.cursorDevPick, { elapsedSec: elapsed })
    const nextText = speed || String(text || '')
    if (nextText) {
      msg.cursorDevPick = { ...msg.cursorDevPick, progressText: nextText }
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
    const processItems = sealProcessSteps(
      (streamProcess.value || []).filter((i) => i.type === 'step' && i.id !== 'boot'),
      { asError: Boolean(streamGotError && !stopped) },
    )
    // 同步流式过程区，避免收尾瞬间仍闪「执行中」
    streamProcess.value = processItems
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
    // 状态可信：收尾时确认卡不得仍停在 running
    if (msg?.cursorDevPick) {
      const ph = msg.cursorDevPick.phase
      if (streamGotError || stopped) {
        if (ph === 'running' || ph === 'starting') {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            status: 'failed',
            phase: 'failed',
            error:
              msg.cursorDevPick.error ||
              formatPickFailureSummary(stopped ? '已停止写码' : '写码未成功结束', {
                userStopped: stopped || Boolean(msg.cursorDevPick.userStopped),
              }),
            userStopped: stopped || Boolean(msg.cursorDevPick.userStopped),
            progressText: '',
          }
        }
      } else if (ph === 'running' || ph === 'starting') {
        msg.cursorDevPick = {
          ...msg.cursorDevPick,
          status: 'confirmed',
          phase: 'idle_for_followup',
          error: '',
          progressText:
            msg.cursorDevPick.channel === 'patch' ? '快速补丁完成' : '写码完成',
        }
      }
    }
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
            error: formatPickFailureSummary(err, {
              userStopped: st === 'cancelled' || Boolean(msg.cursorDevPick.userStopped),
            }),
            jobId,
            progressText: '',
          }
        }
        await finishUi({
          content: formatCursorDevUserError(err, { userStopped: st === 'cancelled' }),
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
          applyChannelMeta(event)
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
          } else if (event.phase === 'patch' || event.channel === 'patch' || event.speed_hint === 'fast') {
            await enqueueStep({
              id: 'cursor-patch',
              state: /未采用|异常|回退/.test(text) ? 'done' : 'running',
              title: text || '快速补丁通道…',
            })
          } else if (event.speed_hint === 'cold_start' || event.phase === 'agent') {
            await enqueueStep({
              id: 'cursor-boot',
              state: 'running',
              title: text || 'Cloud 启动中…',
            })
          }
          scrollToBottom()
        } else if (type === 'step') {
          lastEventAt = Date.now()
          applyChannelMeta(event)
          streamAnswerPending.value = false
          streamProcessCollapsed.value = false
          await enqueueStep(event)
          if (msg?.cursorDevPick && event.title) {
            const elapsed = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
            const speed = cursorDevSpeedLabel(msg.cursorDevPick, { elapsedSec: elapsed })
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              progressText:
                speed ||
                (event.state === 'done' ? `完成：${event.title}` : String(event.title)),
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
          applyChannelMeta(event)
          // 终稿到达：先封掉「核对中」心跳，再写正文
          applyStep({
            id: 'cursor-heartbeat',
            state: 'done',
            title: 'Cursor 本轮已结束',
          })
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
            const ch = String(event.channel || msg.cursorDevPick.channel || '')
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              phase: 'idle_for_followup',
              status: 'confirmed',
              error: '',
              jobId,
              progressText: ch === 'patch' ? '快速补丁完成' : '写码完成',
              ...(ch ? { channel: ch } : {}),
              ...(mergeGuide ? { mergeGuide } : {}),
            }
          }
        } else if (type === 'error') {
          streamGotError = true
          applyChannelMeta(event)
          const rawErr = event.message || event.error || '写码失败'
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              status: 'failed',
              phase: 'failed',
              error: formatPickFailureSummary(rawErr, {
                userStopped: Boolean(msg.cursorDevPick.userStopped),
              }),
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
            'Cursor 已完成本轮写码。小改可直接续聊（复用任务）；若提示复用失败会自动新建 Agent，不影响主线。',
          stopped: false,
        })
      },
      async (err) => {
        if (recoveredByWatchdog || finishedOnce) return
        streamGotError = true
        const errText = typeof err === 'string' ? err : (err?.message || err)
        await finishUi({
          content: formatCursorDevUserError(errText),
          stopped: false,
        })
        if (msg?.cursorDevPick) {
          msg.cursorDevPick = {
            ...msg.cursorDevPick,
            phase: 'failed',
            status: 'failed',
            error: formatPickFailureSummary(errText),
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
            error: formatPickFailureSummary('已停止写码', { userStopped: true }),
            jobId,
            userStopped: true,
            progressText: '',
          }
        }
        await finishUi({
          content: streamContent.value || formatCursorDevUserError('已停止写码', { userStopped: true }),
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
        error: formatPickFailureSummary(e?.message || String(e)),
        jobId,
        progressText: '',
      }
    }
    messages.value.push({
      role: 'assistant',
      content: formatCursorDevUserError(e?.message || e),
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
        '说清楚需求后，我会再请你确认本机目录（或 GitHub）并开始写码。',
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
    let lastWorkspace = ''
    try {
      const [rp, pref] = await Promise.all([
        fetchCursorDevRepos().catch(() => null),
        fetchLocalWorkspacePref().catch(() => null),
      ])
      repos = Array.isArray(rp?.data?.repos) ? rp.data.repos : []
      defaultRepo = rp?.data?.default_repo || repos[0] || ''
      lastWorkspace = String(pref?.data?.path || '').trim()
    } catch {
      /* ignore */
    }
    messages.value.push({
      role: 'assistant',
      content: looksLikeScreenshotUiRedesign(content, files)
        ? '已理解你要按截图改界面。请先选择本机工程目录（默认），或改走 GitHub。'
        : '请先选择本次写码目标。默认本机目录（沙箱改码后同步）；也可改走 GitHub。',
      cursorDevAnchor: {
        id: `cursor-dev-anchor-${Date.now()}`,
        status: 'pending',
        target: 'local',
        workspace: lastWorkspace,
        lastWorkspace,
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

  if (intent === 'code_dev_match') {
    const need =
      `【用户意图·视觉对齐】做成跟截图一样（真正视觉对齐，质量优先；话术不限于「1:1」）。\n\n` +
      (content || '请按截图视觉对齐还原界面。')
    await beginCodingDiscussEntry(need, files)
    return
  }

  if (intent === 'code_dev_edit') {
    const need =
      `【用户意图·按图修改】按截图修改相关部分，不必整页像素复刻；对准用户点名的改动点。\n\n` +
      (content || '请按截图修改界面。')
    await beginCodingDiscussEntry(need, files)
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
      content: '已取消。重新说明开发需求后，我会再请你选择本机目录或 GitHub 仓库。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  const target =
    String(payload.target || msg.cursorDevAnchor.target || 'local').toLowerCase() === 'github'
      ? 'github'
      : 'local'
  const workspace = String(payload.workspace || '').trim()
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

  // —— 本机目录（默认）——
  if (target === 'local') {
    if (!workspace) {
      messages.value.push({
        role: 'assistant',
        content: '本机目录不能为空，请重新选择。',
        process: [],
        processCollapsed: true,
      })
      await persistSession()
      return
    }
    let checkOk = true
    let checkEmpty = projectMode === 'new'
    let checkErr = ''
    let resolvedWs = workspace
    try {
      const resp = await checkLocalDevWorkspace(workspace)
      const data = resp?.data || {}
      checkOk = Boolean(data.ok)
      checkEmpty = Boolean(data.empty)
      checkErr = data.error || ''
      if (checkOk && data.path) resolvedWs = String(data.path)
    } catch (e) {
      checkOk = false
      checkErr = e?.response?.data?.detail || e?.message || String(e)
    }
    if (!checkOk) {
      msg.cursorDevAnchor = { ...msg.cursorDevAnchor, status: 'pending' }
      messages.value.push({
        role: 'assistant',
        content: `本机目录不可用：${checkErr || '请检查路径是否存在且可写'}`,
        process: [],
        processCollapsed: true,
      })
      await persistSession()
      return
    }
    const effectiveMode = checkEmpty ? 'new' : projectMode === 'new' && !checkEmpty ? 'existing' : projectMode
    const promptBlock =
      effectiveMode === 'new'
        ? (
            `【本会话已选定本机新项目目录】\n` +
            `路径：${resolvedWs}\n` +
            `空目录从零生成；:::cursor_dev_propose 默认 target=local，workspace 填 \`${resolvedWs}\`；不要要求 GitHub repo。`
          )
        : (
            `【本会话已选定本机工程目录】\n` +
            `路径：${resolvedWs}\n` +
            `按已有工程增量开发；:::cursor_dev_propose 默认 target=local，workspace 填 \`${resolvedWs}\`；不要问技术栈/GitHub 仓库。`
          )
    msg.cursorDevAnchor = {
      ...msg.cursorDevAnchor,
      status: 'confirmed',
      target: 'local',
      workspace: resolvedWs,
      lastWorkspace: resolvedWs,
      repo: '',
      projectMode: effectiveMode,
      pendingContent,
      pendingFiles,
      promptBlock,
    }
    try {
      await saveLocalWorkspacePref(resolvedWs)
    } catch {
      /* ignore */
    }
    void persistSession()
    messages.value.push({
      role: 'assistant',
      content:
        effectiveMode === 'new'
          ? `已选定本机新项目目录 \`${resolvedWs}\`。接下来从头确认技术栈与需求范围。`
          : `已选定本机工程 \`${resolvedWs}\`。本轮只确认新增范围；写码将经沙箱同步到该目录。`,
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    const userNeed = pendingContent || '请根据已选本机目录继续澄清写码需求'
    const filesForStream =
      Array.isArray(pendingFiles) && pendingFiles.length
        ? pendingFiles
        : codingSessionPendingFiles()
    await startAssistantStream(
      buildCodingDiscussPrompt(userNeed, promptBlock),
      filesForStream,
      null,
      null,
      codingDiscussStreamOpts({ localWorkspaceRoot: resolvedWs }),
    )
    return
  }

  // —— GitHub ——
  msg.cursorDevAnchor = {
    ...msg.cursorDevAnchor,
    status: 'confirmed',
    target: 'github',
    workspace: '',
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
        `仍请按该仓增量开发；不要重新问技术栈（除非用户要换）；propose target=github、repo 填 \`${repo}\`。`
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
      `这是新项目：从头收集需求与技术栈；:::cursor_dev_propose 的 target=github、repo 必须填 \`${repo}\`。`
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
  const filesForStream =
    Array.isArray(pendingFiles) && pendingFiles.length
      ? pendingFiles
      : codingSessionPendingFiles()
  await startAssistantStream(
    buildCodingDiscussPrompt(userNeed, promptBlock || codingSessionContextBlock()),
    filesForStream,
    null,
    null,
    codingDiscussStreamOpts({ cursorDevRepo: repo }),
  )
}

async function beginLocalDevStream(msg, { workspace, content, writeScope = [], files = null }) {
  if (streaming.value && streamAbort.value) {
    messages.value.push({
      role: 'assistant',
      content: '当前还有进行中的生成任务。请先点停止，再发起本机写码。',
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    return false
  }
  const pending =
    Array.isArray(files) && files.length
      ? files
      : Array.isArray(msg?.cursorDevPick?.pendingFiles) && msg.cursorDevPick.pendingFiles.length
        ? msg.cursorDevPick.pendingFiles
        : codingSessionPendingFiles()
  const filePaths = (Array.isArray(pending) ? pending : [])
    .map((f) => String(f?.path || f || '').trim())
    .filter(Boolean)
  if (msg?.cursorDevPick) {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'confirmed',
      target: 'local',
      workspace: workspace || msg.cursorDevPick.workspace,
      writeScope: Array.isArray(writeScope) ? writeScope : [],
      pendingFiles: Array.isArray(pending) ? pending : [],
      requirement: content || msg.cursorDevPick.requirement || '',
      phase: 'starting',
      progressText: '正在创建本机写码任务…',
      channel: 'local_sandbox',
    }
  }

  let jobId = ''
  try {
    try {
      await checkLocalDevWorkspace(workspace)
    } catch {
      /* 创建时后端会再校验 */
    }
    const resp = await createLocalDevJob({
      workspace,
      message: content,
      thread_id: threadId.value || '',
      confirmed: true,
      write_scope: Array.isArray(writeScope) ? writeScope : [],
      file_paths: filePaths,
    })
    jobId = resp?.data?.id || ''
    if (!jobId) throw new Error('未返回本机写码任务 id')
    if (msg?.cursorDevPick) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        jobId,
        phase: 'running',
        status: 'confirmed',
        error: '',
        progressText: `沙箱写码中 → ${workspace}`,
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
        error: formatPickFailureSummary(detail),
        workspace,
        requirement: content,
        progressText: '',
      }
    }
    messages.value.push({
      role: 'assistant',
      content: formatCursorDevUserError(detail),
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    return false
  }

  const requestId = ++activeRequestId
  const currentThread = threadId.value
  streaming.value = true
  streamAbort.value = new AbortController()
  activeCursorDevJobId.value = jobId
  activeCursorDevMsg.value = msg
  streamStartedAt.value = Date.now()
  streamContent.value = ''
  streamProcess.value = [{ id: 'boot', type: 'step', state: 'running', title: '本机 Cursor 写码…' }]
  streamCodingPlan.value = []
  streamProcessCollapsed.value = false
  streamAnswerPending.value = false

  const applyLocalStep = (event) => {
    const id = event?.id || `step-${Date.now()}`
    const title = event?.title || ''
    const state = event?.state || 'running'
    const idx = streamProcess.value.findIndex((i) => i.id === id)
    const item = { id, type: 'step', state, title }
    if (idx >= 0) streamProcess.value[idx] = { ...streamProcess.value[idx], ...item }
    else streamProcess.value = [...streamProcess.value, item]
  }

  const applyCodingPlan = (steps) => {
    if (!Array.isArray(steps)) return
    streamCodingPlan.value = steps.map((s, i) => ({
      id: String(s?.id ?? i),
      title: String(s?.title || '').trim(),
      state: s?.state || 'pending',
    }))
    if (msg) msg.codingPlan = [...streamCodingPlan.value]
  }

  try {
    await streamLocalDevJob(
      jobId,
      async (event) => {
        if (requestId !== activeRequestId || threadId.value !== currentThread) return
        const type = event?.type
        if (type === 'plan' && Array.isArray(event.steps)) {
          applyCodingPlan(event.steps)
          scrollToBottom()
        } else if (type === 'plan_progress') {
          if (Array.isArray(event.steps)) applyCodingPlan(event.steps)
          else if (event.index != null && streamCodingPlan.value.length) {
            const next = streamCodingPlan.value.map((s, i) =>
              i === Number(event.index)
                ? { ...s, state: event.state || s.state }
                : event.state === 'running' && s.state === 'running'
                  ? { ...s, state: 'done' }
                  : s,
            )
            streamCodingPlan.value = next
            if (msg) msg.codingPlan = [...next]
          }
          scrollToBottom()
        } else if (type === 'status') {
          const text = event.text || ''
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = { ...msg.cursorDevPick, progressText: text || '本机写码进行中…' }
          }
          if (streamProcess.value.some((i) => i.id === 'boot')) {
            streamProcess.value = [{ id: 'boot', type: 'step', state: 'running', title: text || '本机沙箱…' }]
          }
          scrollToBottom()
        } else if (type === 'step') {
          streamAnswerPending.value = false
          streamProcessCollapsed.value = false
          applyLocalStep(event)
          if (msg?.cursorDevPick && event.title) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              progressText: event.state === 'done' ? `完成：${event.title}` : String(event.title),
            }
          }
        } else if (type === 'token') {
          const text = event.text != null ? event.text : event.token
          if (!text) return
          streamAnswerPending.value = true
          streamContent.value += String(text)
          scrollToBottom()
        } else if (type === 'replace_text' && event.text != null) {
          streamContent.value = String(event.text)
          scrollToBottom()
          } else if (type === 'scope_confirm') {
          const files = Array.isArray(event.files) ? event.files : []
          const preview = files.slice(0, 12).join('\n')
          const more = files.length > 12 ? `\n…共 ${files.length} 个` : ''
          const ok = window.confirm(
            `${event.message || '写码改动了选定范围外的文件，是否一并同步到本机？'}\n\n${preview}${more}\n\n确定=同步这些文件；取消=仅保留范围内已同步文件。`,
          )
          try {
            await confirmLocalDevScope(jobId, ok ? 'include' : 'skip')
          } catch (ce) {
            console.warn('confirm-scope failed', ce)
          }
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              progressText: ok ? '已确认同步范围外文件…' : '已跳过范围外文件…',
            }
          }
        } else if (type === 'commit_gate') {
          if (msg) {
            msg.localDevCommitGate = {
              status: 'pending',
              job_id: jobId,
              summary: event.summary || '本轮写码已同步，请确认是否提交',
              findings: Array.isArray(event.findings) ? event.findings : [],
              blocking_count: Number(event.blocking_count) || 0,
              warning_count: Number(event.warning_count) || 0,
              can_commit: Boolean(event.can_commit),
              git: event.git && typeof event.git === 'object' ? event.git : null,
              work_branch: String(event.work_branch || ''),
              synced_files: Array.isArray(event.synced_files) ? event.synced_files : [],
              workspace: event.workspace || workspace,
              preview_url: String(event.preview_url || '').trim(),
              suggested_commit_message: String(event.suggested_commit_message || ''),
            }
          }
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              progressText: '等待审码门禁确认是否提交…',
            }
          }
          scrollToBottom()
        } else if (type === 'done') {
          const summary = String(event.text || streamContent.value || '本机写码已完成')
          streamContent.value = summary
          const synced = Array.isArray(event.changed_files) ? event.changed_files : []
          if (streamCodingPlan.value.length) {
            streamCodingPlan.value = streamCodingPlan.value.map((s) => ({
              ...s,
              state: s.state === 'error' ? 'error' : 'done',
            }))
          }
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              phase: 'idle_for_followup',
              status: 'confirmed',
              progressText: '',
              workspace: event.workspace || workspace,
              syncedFiles: synced,
              previewUrl: String(event.preview_url || '').trim(),
              preview: event.preview && typeof event.preview === 'object' ? event.preview : null,
              channel: 'local_sandbox',
              mergeGuide: null,
            }
          }
          if (msg?.localDevCommitGate) {
            const cr = event.commit_result && typeof event.commit_result === 'object' ? event.commit_result : null
            let st = 'skipped'
            if (cr?.ok && cr?.commit) st = 'committed'
            else if (cr?.error && !cr?.skipped) st = 'failed'
            msg.localDevCommitGate = {
              ...msg.localDevCommitGate,
              status: st,
              error: cr?.error || '',
              commit: cr?.commit || '',
              branch: cr?.branch || msg.localDevCommitGate.work_branch,
            }
          }
          applyLocalStep({ id: 'boot', state: 'done', title: '本机写码已同步' })
          scrollToBottom()
        } else if (type === 'error') {
          const err = event.message || '本机写码失败'
          if (msg?.cursorDevPick) {
            msg.cursorDevPick = {
              ...msg.cursorDevPick,
              status: 'failed',
              phase: 'failed',
              error: formatPickFailureSummary(err),
              progressText: '',
            }
          }
          messages.value.push({
            role: 'assistant',
            content: formatCursorDevUserError(err),
            process: [],
            processCollapsed: true,
          })
        }
      },
      null,
      null,
      streamAbort.value.signal,
    )
  } catch (e) {
    if (msg?.cursorDevPick && msg.cursorDevPick.phase !== 'idle_for_followup') {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: formatPickFailureSummary(e?.message || e),
        progressText: '',
      }
    }
  } finally {
    if (requestId === activeRequestId) {
      streaming.value = false
      streamAbort.value = null
      clearActiveCursorDev()
      // 把流式正文落到消息
      if (msg && streamContent.value) {
        msg.content = streamContent.value
        msg.process = [...(streamProcess.value || [])]
        if (streamCodingPlan.value.length) {
          msg.codingPlan = [...streamCodingPlan.value]
        }
      } else if (msg && streamCodingPlan.value.length) {
        msg.codingPlan = [...streamCodingPlan.value]
      }
      streamContent.value = ''
      streamProcess.value = []
      streamCodingPlan.value = []
      void persistSession()
      scrollToBottom()
    }
  }
  return true
}

function onLocalDevCommitResolved(msg, payload) {
  if (!msg?.localDevCommitGate || !payload) return
  const decision = String(payload.decision || '')
  const job = payload.job && typeof payload.job === 'object' ? payload.job : null
  const cr =
    job?.commit_result && typeof job.commit_result === 'object' ? job.commit_result : null
  let st = decision === 'skip' ? 'skipped' : 'pending'
  let err = ''
  let commit = ''
  let branch = msg.localDevCommitGate.work_branch || ''
  if (job) {
    branch = String(cr?.branch || job.work_branch || branch || '')
    commit = String(cr?.commit || msg.localDevCommitGate?.commit || '')
    const retryable = Boolean(cr?.retryable || payload.retryable)
    const pushInfo = cr?.push && typeof cr.push === 'object' ? cr.push : null
    if (decision === 'skip') {
      st = 'skipped'
    } else if (cr && cr.ok === false && !cr.skipped) {
      st = 'failed'
      err = String(cr.error || job.error || job.last_assistant || '提交失败')
    } else if (job.error && !cr?.commit) {
      st = 'failed'
      err = String(job.error)
    } else if (cr?.skipped && cr?.push && cr.push.ok === true) {
      st = 'pushed'
      err = String(cr.message || '本批无新变更，已推送当前分支')
    } else if (cr?.skipped && cr?.push && cr.push.ok === false) {
      st = 'push_failed'
      err = String(cr.push.error || cr.message || '推送失败')
    } else if (cr?.skipped && !cr?.commit) {
      st = 'skipped'
      err = String(cr.message || cr.error || '')
    } else if (cr?.skipped) {
      st = 'skipped'
      err = String(cr.message || cr.error || '')
    } else if (cr?.commit && pushInfo && pushInfo.ok === false) {
      st = 'push_failed'
      err = String(pushInfo.error || '推送失败（本地已提交）')
    } else if (cr?.commit && pushInfo && pushInfo.ok === true) {
      st = 'pushed'
    } else if (String(job.status || '') === 'succeeded' || cr?.commit) {
      st = 'committed'
    } else if (String(job.status || '') === 'failed') {
      st = 'failed'
      err = job.error || job.last_assistant || ''
    }
    if (retryable || cr?.push_retry) {
      if (cr?.commit && pushInfo && pushInfo.ok === false) st = 'push_failed'
      else if (!cr?.ok && !cr?.skipped) st = 'failed'
    }
  }
  // 确认后补一条过程步骤，避免「点了没反应」
  const steps = Array.isArray(msg.process) ? [...msg.process] : []
  const ignored = Array.isArray(cr?.skipped_ignored) ? cr.skipped_ignored : []
  const pushInfo = cr?.push && typeof cr.push === 'object' ? cr.push : null
  let stepDetail = ''
  if (st === 'pushed') {
    stepDetail = `已提交并推送${branch ? ` → ${pushInfo?.remote || 'origin'}/${branch}` : ''}${commit ? ` · ${commit}` : ''}`
  } else if (st === 'push_failed') {
    stepDetail = `本地已提交${commit ? ` · ${commit}` : ''}；推送失败：${err}`
  } else if (st === 'committed') {
    stepDetail =
      `已提交到本地${branch ? ` → ${branch}` : ''}${commit ? ` · ${commit}` : ''}` +
      (ignored.length ? `\n已跳过忽略文件 ${ignored.length} 个` : '')
  } else if (st === 'skipped') {
    stepDetail = err || '文件仍在目标目录'
  } else {
    stepDetail = err || ''
  }
  const commitStep = {
    type: 'step',
    id: 'git-commit',
    title:
      decision === 'skip'
        ? '已跳过 git 提交'
        : st === 'pushed'
          ? '工作分支 commit + push'
          : '工作分支 git commit',
    state: st === 'failed' || st === 'push_failed' ? 'error' : 'done',
    detail: stepDetail,
  }
  const without = steps.filter((s) => s.id !== 'git-commit')
  msg.process = [...without, commitStep]
  msg.processCollapsed = false
  msg.localDevCommitGate = {
    ...msg.localDevCommitGate,
    status: st,
    error: err,
    commit,
    branch,
    retryable: Boolean(cr?.retryable || payload.retryable || cr?.push_retry),
    push_retry: Boolean(cr?.push_retry),
    push_only: Boolean(msg.localDevCommitGate?.push_only || cr?.push_retry),
    prior_commit: String(cr?.commit || msg.localDevCommitGate?.prior_commit || ''),
    last_commit_message: cr?.message || msg.localDevCommitGate?.last_commit_message || '',
  }
  if (msg.cursorDevPick) {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      progressText:
        st === 'pushed'
          ? '本批已提交并推送到远程'
          : st === 'committed'
            ? '本批已提交到本地工作分支'
            : st === 'push_failed'
              ? msg.localDevCommitGate.retryable
                ? '本地已提交，远程推送失败（可重试）'
                : '本地已提交，远程推送失败'
              : st === 'skipped'
                ? '已跳过提交'
                : st === 'failed'
                  ? msg.localDevCommitGate.retryable
                    ? '提交失败（可重试）'
                    : '提交失败'
                  : '正在提交工作分支…',
    }
  }
  if (job?.last_assistant && msg) {
    const prev = String(msg.content || '').trim()
    const add = String(job.last_assistant).trim()
    if (add && !prev.includes(add.slice(0, 40))) {
      msg.content = prev ? `${prev}\n\n${add}` : add
    }
  }
  void persistSession()
  void nextTick(() => scrollToBottom())
}

/**
 * P1-3 人触发部署：门禁探测；就绪则弹确认卡（确认后才触发 CI）。
 * 与 commit_batch / 写码 SSE / 全仓审码互斥。默认 DEPLOY_ENABLED=0 只出文字说明。
 * 就绪时只出确认卡（不再叠一段重复 markdown）；未就绪才用正文说明怎么配。
 */
async function beginLocalDeploy(userText) {
  messages.value.push({
    role: 'assistant',
    content: '正在检查部署配置…',
    process: [],
    processCollapsed: true,
    localDevDeployGate: null,
  })
  const idx = messages.value.length - 1
  void persistSession()
  scrollToBottom()
  try {
    const res = await prepareLocalDevDeploy({ message: userText || '' })
    const data = res?.data && typeof res.data === 'object' ? res.data : res
    const summary = String(data?.summary || '已识别部署意图')
    const hint = String(data?.next_hint || '')
    const env = String(data?.env || 'staging')
    const enabled = Boolean(data?.enabled)
    const ready = Boolean(data?.ready_for_confirm)
    const whitelist = Array.isArray(data?.env_whitelist) ? data.env_whitelist.join(', ') : 'staging'

    if (ready) {
      const provider = String(data?.ci_provider || 'github_actions')
      messages.value[idx] = {
        ...messages.value[idx],
        // 门禁/环境/开关已在确认卡内展示，正文留空避免双框重复
        content: '',
        localDevDeployGate: {
          status: 'pending',
          message: userText || '',
          summary,
          env,
          ref: String(data?.ref || data?.suggested_ref || ''),
          suggested_ref: String(data?.suggested_ref || data?.ref || ''),
          ci_provider: provider,
          github_repo: String(data?.github_repo || ''),
          github_workflow: String(data?.github_workflow || ''),
          ssh_host: String(data?.ssh_host || ''),
          local_project_path: String(data?.local_project_path || ''),
          can_trigger_ci: Boolean(data?.can_trigger_ci),
          checks: Array.isArray(data?.checks) ? data.checks : [],
          env_whitelist: Array.isArray(data?.env_whitelist) ? data.env_whitelist : [],
          poll_timeout_sec: Number(data?.poll_timeout_sec || 1800),
          health_url: String(data?.health_url || data?.visit_url || ''),
          visit_url: String(data?.visit_url || data?.health_url || ''),
        },
      }
    } else {
      const lines = [
        summary,
        '',
        `- 目标环境：\`${env}\``,
        `- 允许环境：\`${whitelist}\``,
        `- 总开关：${enabled ? '已开启' : '关闭（默认，安全）'}`,
      ]
      if (hint) lines.push('', hint)
      if (!enabled) {
        lines.push(
          '',
          '启用方式：打开「系统配置 → 自动化部署」，打开开关并按执行方式填写配置后保存（热更新）。',
          '- GitHub Actions：仓库 / Workflow / Token',
          '- 本机 SSH：将「部署执行方式」设为 local_ssh，并填主机 / 私钥路径 / 远端目录 / 本机项目路径',
        )
      }
      messages.value[idx] = {
        ...messages.value[idx],
        content: lines.join('\n'),
        localDevDeployGate: null,
      }
    }
  } catch (e) {
    messages.value[idx] = {
      ...messages.value[idx],
      content: `部署准备失败：${e?.message || e}\n\n未触发任何发布。`,
      localDevDeployGate: null,
    }
  }
  await persistSession()
  scrollToBottom()
}

function onLocalDevDeployResolved(msg, payload) {
  if (!msg?.localDevDeployGate || !payload) return
  const decision = String(payload.decision || '')
  const result = payload.result && typeof payload.result === 'object' ? payload.result : {}
  const ci = result.ci && typeof result.ci === 'object' ? result.ci : {}
  let st = 'pending'
  let err = ''
  if (decision === 'cancel' || result.status === 'cancelled') {
    st = 'cancelled'
  } else if (result.ok && result.status === 'triggered') {
    st = 'triggered'
  } else {
    st = 'failed'
    err = String(result.error || '触发失败')
  }
  msg.localDevDeployGate = {
    ...msg.localDevDeployGate,
    status: st,
    error: err,
    ref: String(result.ref || msg.localDevDeployGate.ref || ''),
    env: String(result.env || msg.localDevDeployGate.env || ''),
    run_id: String(ci.run_id || msg.localDevDeployGate.run_id || ''),
    run_url: String(ci.run_url || ''),
    actions_url: String(ci.actions_url || ''),
    poll_timeout_sec: Number(msg.localDevDeployGate.poll_timeout_sec || 1800),
    log_tail: '',
    ci,
  }
  // 过程与终态都在确认卡内展示，正文仅保留取消/失败一句
  if (st === 'cancelled') {
    msg.content = '已取消部署，未触发发布。'
  } else if (st === 'failed') {
    msg.content = `触发失败：${err}（未改本地工作区）。`
  } else {
    msg.content = ''
  }
  void persistSession()
  void nextTick(() => scrollToBottom())
}

function onLocalDevDeployPoll(msg, payload) {
  if (!msg?.localDevDeployGate || !payload) return
  const st = String(payload.status || '')
  const visit = String(payload.visit_url || payload.health_url || msg.localDevDeployGate.visit_url || '').trim()
  const patch = {
    ...msg.localDevDeployGate,
    run_id: String(payload.run_id || msg.localDevDeployGate.run_id || ''),
    run_url: String(payload.run_url || msg.localDevDeployGate.run_url || ''),
    poll_message: String(payload.message || ''),
    health_url: String(payload.health_url || msg.localDevDeployGate.health_url || ''),
    health_detail: String(payload.health_detail || msg.localDevDeployGate.health_detail || ''),
    visit_url: visit,
    log_tail: String(payload.log_tail || msg.localDevDeployGate.log_tail || ''),
  }
  if (payload.health_ok === true || payload.health_ok === false) {
    patch.health_ok = payload.health_ok
  }
  if (st === 'succeeded' || st === 'ci_failed' || st === 'unreachable' || st === 'queued' || st === 'in_progress') {
    patch.status = st
  }
  if (st === 'succeeded') {
    msg.content = visit
      ? `**部署成功**\n\n项目访问地址：[${visit}](${visit})`
      : '**部署成功**\n\n（未配置 DEPLOY_HEALTH_URL，无访问地址）'
  } else if (st === 'ci_failed') {
    msg.content = `**部署失败**：${payload.conclusion || payload.message || '见上方过程日志'}。`
  }
  msg.localDevDeployGate = patch
  void persistSession()
  void nextTick(() => scrollToBottom())
}

/**
 * 人触发本批提交：不经 Deep Agents / 不经写码 SSE。
 * 过程面板分步 + 每步耗时；定位目录优先用会话内已有路径（避免干等偏好接口）。
 */
async function beginLocalCommitBatch(userText) {
  const touch = async () => {
    await nextTick()
    scrollToBottom()
  }

  let msgIndex = -1
  const cur = () => (msgIndex >= 0 ? messages.value[msgIndex] : null)
  const bump = (patch) => {
    if (msgIndex < 0) return
    messages.value[msgIndex] = { ...messages.value[msgIndex], ...patch }
  }
  const patchStep = (id, patch) => {
    const msg = cur()
    if (!msg) return
    bump({
      process: (msg.process || []).map((s) => (s.id === id ? { ...s, ...patch } : s)),
    })
  }
  const setProcess = (steps) => {
    bump({
      process: steps.map((s) => ({ type: 'step', ...s })),
      processCollapsed: false,
    })
  }

  /** 每步独立心跳：徽章显示「执行中 Ns」，结束写入 durationMs */
  const stepTimers = {}
  const startStepClock = (id, detail = '') => {
    stopStepClock(id, false)
    const startedAt = Date.now()
    patchStep(id, {
      state: 'running',
      startedAt,
      elapsedSec: 0,
      durationMs: undefined,
      ...(detail ? { detail } : {}),
    })
    stepTimers[id] = setInterval(() => {
      const sec = Math.max(0, Math.round((Date.now() - startedAt) / 1000))
      patchStep(id, { elapsedSec: sec })
    }, 500)
  }
  const stopStepClock = (id, markDone = true, extra = {}) => {
    if (stepTimers[id]) {
      clearInterval(stepTimers[id])
      delete stepTimers[id]
    }
    const curStep = (cur()?.process || []).find((s) => s.id === id)
    const startedAt = Number(curStep?.startedAt) || Date.now()
    const durationMs = Math.max(0, Date.now() - startedAt)
    if (markDone) {
      patchStep(id, {
        state: extra.state || 'done',
        elapsedSec: undefined,
        durationMs,
        ...extra,
      })
    }
  }
  const clearAllClocks = () => {
    Object.keys(stepTimers).forEach((k) => {
      clearInterval(stepTimers[k])
      delete stepTimers[k]
    })
  }

  /** 同步源优先：不发网络 */
  const resolveWorkspaceLocal = () => {
    const idle = findIdleCursorDevPick()
    let ws = String(idle?.pick?.workspace || '').trim()
    if (ws) return { workspace: ws, source: '本会话写码卡' }
    for (let i = messages.value.length - 1; i >= 0; i--) {
      const p = messages.value[i]?.cursorDevPick
      if (p?.workspace && String(p.channel || '') === 'local_sandbox') {
        return { workspace: String(p.workspace).trim(), source: '历史本机写码卡' }
      }
    }
    return { workspace: '', source: '' }
  }

  const fetchPrefWithTimeout = (ms = 2000) =>
    Promise.race([
      fetchLocalWorkspacePref().catch(() => null),
      new Promise((resolve) => setTimeout(() => resolve({ __timeout: true }), ms)),
    ])

  /** 会话内旧确认卡先失效，避免与新一批并存可点（只改有待确认的项，保持其它引用） */
  const markPendingCommitCardsSuperseded = () => {
    for (let i = 0; i < messages.value.length; i++) {
      const m = messages.value[i]
      const g = m?.localDevCommitGate
      if (!g) continue
      const s = String(g.status || 'pending')
      if (s !== 'pending' && s !== 'awaiting_commit') continue
      messages.value[i] = {
        ...m,
        localDevCommitGate: { ...g, status: 'superseded' },
      }
    }
  }

  const gateCardFromPayload = (gate, files, workspacePath, jobId) => {
    const git = gate.git && typeof gate.git === 'object' ? gate.git : null
    const batch = gate.batch && typeof gate.batch === 'object' ? gate.batch : {}
    const priorCommit = String(gate.prior_commit || gate.commit || '').trim()
    return {
      status: gate.push_retry ? 'push_failed' : 'pending',
      job_id: jobId,
      summary: gate.summary || '请确认是否提交本批文件',
      findings: Array.isArray(gate.findings) ? gate.findings : [],
      file_scans: Array.isArray(gate.file_scans) ? gate.file_scans : [],
      blocking_count: Number(gate.blocking_count) || 0,
      warning_count: Number(gate.warning_count) || 0,
      can_commit: Boolean(gate.can_commit),
      can_push: gate.can_push != null ? Boolean(gate.can_push) : Boolean(git?.has_remote),
      git,
      work_branch: String(gate.work_branch || ''),
      synced_files: files,
      workspace: workspacePath,
      relaxed_from_today: Boolean(batch.relaxed_from_today),
      synced_pool_total: Number(batch.synced_pool_total) || 0,
      excluded_non_business_total: Number(batch.excluded_non_business_total) || 0,
      git_dirty_total: Number(batch.git_dirty_total) || 0,
      scope_note: String(batch.scope_note || gate.scope_label || ''),
      push_only: Boolean(gate.push_only),
      push_retry: Boolean(gate.push_retry),
      prior_commit: priorCommit,
      commit: priorCommit,
      retryable: Boolean(gate.push_retry || gate.retryable),
      error: String(gate.push_error || gate.error || ''),
      verdict: String(gate.verdict || ''),
      checks: Array.isArray(gate.checks) ? gate.checks : [],
      scope_label: String(gate.scope_label || 'WorkBuddy 同步且 Git 待提交（非全仓审码）'),
      provider: String(gate.provider || ''),
      review_method: String(gate.review_method || ''),
      files_reviewed: Number(gate.files_reviewed) || (Array.isArray(files) ? files.length : 0),
      process_steps: Array.isArray(gate.process_steps) ? gate.process_steps : [],
      suggested_commit_message: String(gate.suggested_commit_message || ''),
    }
  }

  /** 409 pending_commit：拉回旧任务并展示确认卡 */
  const resumePendingCommitCard = async (jobId, workspacePath) => {
    const jid = String(jobId || '').trim()
    if (!jid) return false
    try {
      const res = await getLocalDevJob(jid)
      const job = res?.data && typeof res.data === 'object' ? res.data : res
      if (!job || String(job.status || '') !== 'awaiting_commit') return false
      const gate =
        job.commit_gate && typeof job.commit_gate === 'object' ? job.commit_gate : {}
      const files = Array.isArray(job.synced_files)
        ? job.synced_files
        : Array.isArray(gate.synced_files)
          ? gate.synced_files
          : []
      const ws = String(job.workspace || workspacePath || '')
      stopStepClock('gate', true, { detail: gate.summary || '已恢复待确认任务' })
      startStepClock('card', '恢复确认卡…')
      await touch()
      bump({
        content: '',
        localDevCommitGate: gateCardFromPayload(gate, files, ws, jid),
      })
      stopStepClock('card', true, {
        detail: gate.can_commit ? '可确认提交' : '有阻断或非 git 仓，仅可跳过',
      })
      return true
    } catch {
      return false
    }
  }

  markPendingCommitCardsSuperseded()

  messages.value.push({
    role: 'assistant',
    content: '开始处理提交请求…',
    process: [],
    processCollapsed: false,
    localDevCommitGate: null,
  })
  msgIndex = messages.value.length - 1
  setProcess([
    { id: 'ws', title: '定位本机工程目录', state: 'pending' },
    { id: 'collect', title: '汇总本批已同步文件', state: 'pending' },
    { id: 'gate', title: '提交前审码门禁（仅本批）', state: 'pending' },
    { id: 'card', title: '生成提交确认卡', state: 'pending' },
  ])
  void persistSession()
  await touch()

  startStepClock('ws', '先查会话内已有本机目录…')
  await touch()

  let workspace = ''
  let wsSource = ''
  const localHit = resolveWorkspaceLocal()
  if (localHit.workspace) {
    workspace = localHit.workspace
    wsSource = localHit.source
  } else {
    patchStep('ws', { detail: '会话无目录，读取上次偏好（最多 2s）…' })
    await touch()
    try {
      const pref = await fetchPrefWithTimeout(2000)
      if (pref?.__timeout) {
        patchStep('ws', { detail: '偏好接口超时，已跳过' })
      } else {
        workspace = String(pref?.data?.path || pref?.path || '').trim()
        if (workspace) wsSource = '用户上次写码目录偏好'
      }
    } catch {
      workspace = ''
    }
  }

  if (!workspace) {
    stopStepClock('ws', true, {
      state: 'error',
      detail: '未找到本机工程目录',
    })
    clearAllClocks()
    bump({
      content:
        '要提交本批代码，请先告诉我本机工程目录（或先完成本机写码，系统会记住上次目录）。\n\n' +
        '说明：只会审**已同步的本批文件**，不会全仓审核，也不会自动每次写码后提交。',
    })
    void persistSession()
    await touch()
    return false
  }

  stopStepClock('ws', true, {
    detail: `${workspace}\n来源：${wsSource || '未知'}`,
  })
  bump({
    content: `已定位工程目录：\`${workspace}\`（${wsSource}）\n\n正在汇总本批已同步文件…`,
  })
  startStepClock('collect', '查询今日已成功同步的文件…')
  void persistSession()
  await touch()

  const todayOnly = /今天|今日|today/i.test(String(userText || ''))
  let prepared = null
  try {
    const prepRes = await prepareLocalDevCommitBatch({
      workspace,
      today_only: todayOnly,
    })
    prepared =
      prepRes?.data && typeof prepRes.data === 'object' && prepRes.data.ok !== undefined
        ? prepRes.data
        : prepRes
  } catch (e) {
    const detail = e?.response?.data?.detail || e?.message || String(e)
    stopStepClock('collect', true, {
      state: 'error',
      detail: typeof detail === 'string' ? detail : '汇总失败',
    })
    clearAllClocks()
    bump({
      content:
        `无法汇总本批文件：${typeof detail === 'string' ? detail : '请求失败'}\n\n` +
        '请确认已完成本机写码同步，且工作区路径与写码时一致。',
    })
    void persistSession()
    await touch()
    return false
  }

  const prepFiles = Array.isArray(prepared?.files) ? prepared.files : []
  const syncedPoolTotal = Number(prepared?.batch?.synced_pool_total) || prepFiles.length
  const gitDirtyTotal = Number(prepared?.batch?.git_dirty_total) || 0
  const scopeNote = String(prepared?.batch?.scope_note || prepared?.message || '')
  const preview = Array.isArray(prepared?.preview) ? prepared.preview : prepFiles.slice(0, 12)
  stopStepClock('collect', true, {
    detail:
      (scopeNote ||
        `WorkBuddy 同步池 ${syncedPoolTotal} 个；Git 待提交 ${prepFiles.length} 个`) +
      (prepared?.batch?.relaxed_from_today ? '\n（今日无记录，已放宽到历史同步批）' : ''),
    preview: preview.map((p) => String(p)),
  })
  bump({
    content:
      prepFiles.length > 0
        ? `已筛出 **${prepFiles.length}** 个待提交文件（同步池 ${syncedPoolTotal} 个，Git 变更 ${gitDirtyTotal} 个）。\n\n` +
          `工作区：\`${workspace}\`\n\n` +
          `正在做提交前审码门禁…`
        : `同步池 ${syncedPoolTotal} 个文件均已提交到 git，无新文件需审。\n\n` +
          `工作区：\`${workspace}\`\n\n` +
          `仍可确认后尝试推送到远程…`,
  })
  startStepClock('gate', '逐文件规则扫描…')
  void persistSession()
  await touch()

  try {
    const res = await startLocalDevCommitBatch({
      workspace,
      message: userText,
      thread_id: threadId.value || '',
      today_only: todayOnly,
      files: prepFiles,
    })
    const resBody = res?.data && typeof res.data === 'object' && res.data.job_id ? res.data : res
    const gate =
      resBody?.commit_gate && typeof resBody.commit_gate === 'object' ? resBody.commit_gate : {}
    const files = Array.isArray(resBody?.files) ? resBody.files : gate.synced_files || prepFiles
    const fileScans = Array.isArray(gate.file_scans) ? gate.file_scans : []
    const findings = Array.isArray(gate.findings) ? gate.findings : []
    const findingLines = findings
      .slice(0, 6)
      .map((f) => `[${f.severity || 'P0'}] ${f.path}: ${f.message}`)
    const processLines = Array.isArray(gate.process_steps) ? gate.process_steps : []
    const scanLines = fileScans
      .slice(0, 10)
      .map((s) => `${s.status === 'pass' ? '✓' : '✗'} ${s.path} — ${(s.steps || []).join('；')}`)
    stopStepClock('gate', true, {
      detail: [
        gate.summary || '门禁完成',
        gate.review_method || '提交批审',
        gate.scope_label || scopeNote,
        processLines.length ? `审核过程：\n${processLines.join('\n')}` : '',
        findingLines.length
          ? `发现问题：\n${findingLines.join('\n')}`
          : scanLines.length
            ? `逐文件结论：\n${scanLines.join('\n')}`
            : '无待审文件或均已通过',
      ]
        .filter(Boolean)
        .join('\n'),
      preview: files.slice(0, 12).map((p) => String(p)),
    })
    startStepClock('card', '组装确认卡…')
    await touch()

    markPendingCommitCardsSuperseded()

    bump({
      content: '',
      localDevCommitGate: gateCardFromPayload(gate, files, workspace, resBody?.job_id),
    })
    stopStepClock('card', true, {
      detail: gate.can_commit ? '可确认提交' : '有阻断或非 git 仓，仅可跳过',
    })
  } catch (e) {
    const rawDetail = e?.response?.data?.detail
    const pendingJobId =
      rawDetail && typeof rawDetail === 'object' ? rawDetail.job_id : null
    const detailMsg =
      rawDetail && typeof rawDetail === 'object'
        ? rawDetail.message || rawDetail.code || '门禁失败'
        : rawDetail || e?.message || String(e)
    if (pendingJobId && (await resumePendingCommitCard(pendingJobId, workspace))) {
      // 已恢复确认卡
    } else {
      stopStepClock('gate', true, {
        state: 'error',
        detail: typeof detailMsg === 'string' ? detailMsg : '门禁失败',
      })
      clearAllClocks()
      bump({
        content:
          `无法启动本批提交：${typeof detailMsg === 'string' ? detailMsg : '请求失败'}\n\n` +
          (String(detailMsg).includes('待确认')
            ? '请向上翻找「审码门禁 · 提交确认」卡片，先确认或跳过；或再说一次「提交今天的代码」覆盖旧任务。'
            : '请确认已完成本机写码同步，且工作区路径与写码时一致。'),
      })
    }
  }
  clearAllClocks()
  void persistSession()
  await touch()
  return true
}

async function onCursorDevPickResolved(msg, payload) {
  if (!msg?.cursorDevPick || !payload) return
  const prevStatus = msg.cursorDevPick.status || 'pending'
  const allowFromConfirmed = ['force_stop', 'reattach', 'retry'].includes(payload.status)
  if (prevStatus && prevStatus !== 'pending' && prevStatus !== 'failed' && !allowFromConfirmed) return
  if (prevStatus === 'failed' && payload.status !== 'retry' && payload.status !== 'cancelled') return

  const target =
    String(payload.target || msg.cursorDevPick.target || 'local').toLowerCase() === 'github'
      ? 'github'
      : 'local'
  const workspace = String(payload.workspace || msg.cursorDevPick.workspace || '').trim()
  const writeScope = Array.isArray(payload.writeScope)
    ? payload.writeScope.map((x) => String(x || '').trim()).filter(Boolean)
    : Array.isArray(msg.cursorDevPick.writeScope)
      ? msg.cursorDevPick.writeScope
      : []
  const repo = payload.repo || msg.cursorDevPick.repo || ''
  const ref = String(payload.ref ?? msg.cursorDevPick.ref ?? '').trim()
  let requirement = String(
    payload.requirement || msg.cursorDevPick.requirement || msg.cursorDevPick.pendingContent || '',
  ).trim()
  // 确认卡里若仍残留旧截图五卡合同，而需求本身是重做 → 开工前撕掉并钉死指令
  if (
    /(重做|重新设计|重新构图|设计感|全新(?:构图|排版|设计|工业)|杂志|彻底区分|不要按旧|不要照抄|不要按截图)/.test(requirement) &&
    !/(1\s*:\s*1|1：1|按截图复刻|改成这种|做成这种)/.test(requirement)
  ) {
    requirement = requirement
      .replace(/【截图理解】[\s\S]*?(?=\n【|\n## |$)/g, '\n')
      .replace(/^[^\n]*按截图位置[^\n]*\n?/gm, '\n')
      .replace(/^[^\n]*五卡布局与截图[^\n]*\n?/gm, '\n')
      .replace(/^[^\n]*与截图一致[^\n]*\n?/gm, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim()
    if (!requirement.startsWith('【本轮最高指令')) {
      requirement =
        '【本轮最高指令 · 重新设计】全新构图；禁止旧截图五卡/首页/看板骨架；只保留业务字段。\n\n' +
        requirement
    }
  }
  const createPr = Boolean(payload.createPr ?? msg.cursorDevPick.createPr)
  // 重做时丢掉会话里残留的旧截图附件，避免 Cloud 看图抄布局
  const redesignNoShot =
    /(重做|重新设计|重新构图|设计感|全新(?:构图|排版|设计|工业)|杂志|彻底区分|不要按旧|不要照抄|不要按截图)/.test(requirement) &&
    !/(1\s*:\s*1|1：1|按截图复刻|改成这种|做成这种)/.test(requirement)
  const pendingFiles = redesignNoShot
    ? []
    : Array.isArray(msg.cursorDevPick.pendingFiles) && msg.cursorDevPick.pendingFiles.length
      ? [...msg.cursorDevPick.pendingFiles]
      : codingSessionPendingFiles()

  if (payload.status === 'cancelled') {
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'cancelled',
      phase: 'cancelled',
      target,
      workspace,
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

  if (payload.status === 'force_stop') {
    const jobId = String(payload.jobId || msg.cursorDevPick?.jobId || '').trim()
    if (jobId && String(activeCursorDevJobId.value || '') === jobId) {
      await stopStreaming()
      return
    }
    if (jobId) {
      try {
        if (target === 'local' || String(jobId).startsWith('ldj-')) {
          await cancelLocalDevJob(jobId, '用户强制结束')
        } else {
          await cancelCursorDevJob(jobId, '用户强制结束')
        }
      } catch {
        /* ignore */
      }
    }
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'failed',
      phase: 'failed',
      error: formatPickFailureSummary('已强制结束写码', { userStopped: true }),
      jobId,
      userStopped: true,
      progressText: '',
      target,
      workspace,
      repo,
      ref,
      requirement,
      createPr,
    }
    void persistSession()
    messages.value.push({
      role: 'assistant',
      content: formatCursorDevUserError('已强制结束写码', { userStopped: true }),
      process: [],
      processCollapsed: true,
    })
    await persistSession()
    scrollToBottom()
    return
  }

  // 本机目标：确认 / 重试走沙箱写码（reattach 对本机无意义）
  if (target === 'local' && (payload.status === 'confirmed' || payload.status === 'retry')) {
    if (!workspace) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: '请填写本机工程绝对路径',
        progressText: '',
      }
      void persistSession()
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
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      target: 'local',
      workspace,
      writeScope,
      requirement,
      pendingContent: requirement,
      phase: 'running',
      status: 'confirmed',
      progressText: '正在启动本机 Cursor 写码…',
      error: '',
      userStopped: false,
    }
    void persistSession()
    const prevJobId = String(payload.jobId || msg.cursorDevPick.jobId || '').trim()
    if (payload.status === 'retry' && prevJobId) {
      try {
        await cancelLocalDevJob(prevJobId, '重试本机写码，结束旧任务')
      } catch {
        /* ignore */
      }
    }
    await beginLocalDevStream(msg, {
      workspace,
      content: requirement,
      writeScope,
      files: pendingFiles,
    })
    return
  }

  if (payload.status === 'reattach') {
    const jobId = String(payload.jobId || msg.cursorDevPick?.jobId || '').trim()
    if (!jobId) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: formatPickFailureSummary('缺少任务 id，无法挂接'),
        progressText: '',
      }
      void persistSession()
      return
    }
    msg.cursorDevPick = {
      ...msg.cursorDevPick,
      status: 'confirmed',
      phase: 'running',
      progressText: '正在重新挂接写码进度…',
      error: '',
      jobId,
      repo,
      ref,
      requirement,
      createPr,
    }
    void persistSession()
    try {
      await beginCursorDevStream(msg, {
        repo,
        ref,
        content: requirement,
        files: pendingFiles,
        createPr,
        existingJobId: jobId,
        attachOnly: true,
      })
    } catch (e) {
      msg.cursorDevPick = {
        ...msg.cursorDevPick,
        status: 'failed',
        phase: 'failed',
        error: e?.message || String(e),
        progressText: '',
      }
      void persistSession()
    }
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
      Boolean(payload.forceNew) ||
      Boolean(msg.cursorDevPick.userStopped) ||
      /已停止|用户停止|用户取消|自动结束|开新写码|不可续聊：(?:running|cancelled|queued)/i.test(
        String(msg.cursorDevPick.error || ''),
      )
    try {
      let ok = false
      if (prevJobId && !forceNewJob) {
        // 先探状态：cancelled/running 必须新开；failed/idle 可续
        let st = ''
        try {
          const jr = await getCursorDevJob(prevJobId)
          st = String(jr?.data?.status || '')
        } catch {
          st = ''
        }
        if (st === 'cancelled' || st === 'queued' || st === 'running') {
          ok = false
        } else {
          ok = await beginCursorDevStream(msg, {
            repo,
            ref,
            content: requirement,
            files: pendingFiles,
            createPr,
            existingJobId: prevJobId,
          })
        }
      }
      if (!ok) {
        // 开新任务前尽量取消旧 job，释放并发并避免双写
        if (prevJobId) {
          try {
            await cancelCursorDevJob(prevJobId, '重试写码，结束旧任务')
          } catch {
            /* ignore */
          }
        }
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
    target: 'github',
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
    // P0：同会话同仓优先复用 idle job（后端也会兜底），避免无谓新建 Agent 拉仓
    let reuseJobId = ''
    const idleSame = findIdleCursorDevPick()
    if (
      idleSame?.pick?.jobId &&
      String(idleSame.pick.repo || '') === String(repo || '') &&
      !msg.cursorDevPick?.userStopped
    ) {
      reuseJobId = String(idleSame.pick.jobId)
    }
    await beginCursorDevStream(msg, {
      repo,
      ref,
      content: requirement,
      files: pendingFiles,
      createPr,
      existingJobId: reuseJobId,
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

  ensureThreadId()

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
  // 截图附件：先判意图；拿不准就反问确认，禁止瞎猜「按图改还是复原」
  let agentContent = content
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
    if (shot.lane === 'code_dev' && shot.uiMode === 'match') {
      agentContent =
        `【用户意图·视觉对齐】做成跟截图一样（真正视觉对齐，质量优先）。\n\n` +
        (content || '请按截图视觉对齐还原界面。')
    } else if (shot.lane === 'code_dev' && shot.uiMode === 'edit') {
      agentContent =
        `【用户意图·按图修改】按截图/红框标注修改相关部分，不必整页像素复原；对准用户点名或标注的改动点。\n\n` +
        (content || '请按截图修改界面。')
    }
    // code_dev / code_review / paste_code：落入下方既有分支
  }

  // 人触发部署（P1-3a：仅门禁探测，不触发 CI；与提交/写码/审码互斥）
  if (!hasPastedSourceFence(content) && looksLikeDeploy(content)) {
    await beginLocalDeploy(content)
    return
  }

  // 人触发本批提交（不经 Agent / 不经写码 SSE；与审码/写码车道互斥）
  if (!hasPastedSourceFence(content) && looksLikeLocalCommitBatch(content)) {
    await beginLocalCommitBatch(content)
    return
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

  // 写码续聊：仅「增量微调」意图才直开 Cursor；新交付必须先讨论/确认
  const idlePick = findIdleCursorDevPick()
  if (
    !hasPastedSourceFence(content) &&
    !looksLikePasteCodeAnalyze(content) &&
    idlePick?.pick?.jobId &&
    looksLikeCursorDevFollowup(content, filesSnapshot, idlePick)
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
    await beginCodingDiscussEntry(agentContent, filesSnapshot)
    return
  }

  const resumeCtx = looksLikeResumeIntent(content) ? findStoppedResumeContext() : null
  await startAssistantStream(
    enrichMessageForAgent(agentContent !== content ? agentContent : content, resumeCtx),
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
  ensureThreadId()

  const requestId = ++activeRequestId
  const currentThread = threadId.value
  const abortCtrl = new AbortController()
  streamAbort.value = abortCtrl

  streaming.value = true
  streamContent.value = ''
  resetStreamDisplay()
  streamAnswerPending.value = false
  streamConfirms.value = []
  streamCharts.value = []
  streamDashboards.value = []
  const gitRepoUrl = String((opts && opts.gitRepoUrl) || '').trim()
  const gitRef = String((opts && opts.gitRef) || '').trim()
  const workbuddyLane = String((opts && opts.workbuddyLane) || '').trim()
  const cursorDevLane =
    Boolean(opts && opts.cursorDevLane) || workbuddyLane === 'code_dev'
  const cursorDevRepo = String((opts && opts.cursorDevRepo) || '').trim()
  const cursorDevJobId = String((opts && opts.cursorDevJobId) || '').trim()
  const localWorkspaceRoot = String((opts && opts.localWorkspaceRoot) || '').trim()
  const isCodeReviewLane =
    workbuddyLane === 'code_review' || Boolean(ideWorkspaceRoot) || Boolean(gitRepoUrl)
  const isPasteCodeLane = workbuddyLane === 'paste_code'
  const isCodeDevLane =
    !isPasteCodeLane &&
    (workbuddyLane === 'code_dev' ||
      cursorDevLane ||
      Boolean(cursorDevRepo) ||
      Boolean(localWorkspaceRoot))

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
            ? (localWorkspaceRoot
              ? `写码讨论：本机 ${localWorkspaceRoot}`
              : cursorDevRepo
                ? `写码讨论：${cursorDevRepo}`
                : '写码需求讨论…')
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
      paintStreamDisplay(true)
      streamAnswerPending.value = true
    }
  }

  try {
    // 选仓/续聊时常漏传附件：写码讨论强制回捞本会话截图，否则智谱【截图理解】永远不跑
    let streamFiles = Array.isArray(files) ? [...files] : []
    if (!streamFiles.length) {
      const reused = codingSessionPendingFiles()
      if (reused.length) streamFiles = reused
    }
    const filePaths = streamFiles
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
      if (localWorkspaceRoot) extraPageContext.local_workspace_root = localWorkspaceRoot
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
        } else if (type === 'dashboard' && Array.isArray(event.charts) && event.charts.length) {
          const id = String(event.id || `dashboard-${Date.now()}`)
          const next = {
            id,
            title: event.title || '分析看板',
            template_id: event.template_id || '',
            presentation: !!event.presentation,
            skin: event.skin || 'ops_dark',
            kpis: Array.isArray(event.kpis) ? event.kpis : [],
            charts: (event.charts || []).map((ch, i) => ({
              id: ch.id || `${id}-${i}`,
              title: ch.title || '分析图',
              chart_type: ch.chart_type || 'bar',
              option: ch.option,
              definition: ch.definition || '',
              caveats: Array.isArray(ch.caveats) ? ch.caveats : [],
              layout: ch.layout || ch.option?._wb_layout || {},
              drill: ch.drill || null,
              entity: ch.entity || '',
            })),
            gaps: Array.isArray(event.gaps) ? event.gaps : [],
          }
          const idx = streamDashboards.value.findIndex((d) => d.id === id)
          if (idx >= 0) streamDashboards.value[idx] = next
          else streamDashboards.value = [...streamDashboards.value, next]
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          scrollToBottom()
        } else if (type === 'chart' && event.option) {
          const id = String(event.id || `chart-${Date.now()}`)
          const next = {
            id,
            title: event.title || '分析图',
            chart_type: event.chart_type || 'bar',
            option: event.option,
            definition: event.definition || '',
            caveats: Array.isArray(event.caveats) ? event.caveats : [],
            layout: event.layout || event.option?._wb_layout || {},
          }
          const idx = streamCharts.value.findIndex((c) => c.id === id)
          if (idx >= 0) streamCharts.value[idx] = next
          else streamCharts.value = [...streamCharts.value, next]
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          scrollToBottom()
        } else if (type === 'token') {
          const text = event.text != null ? event.text : event.token
          if (!text) return
          // 已有写确认预览表时，忽略模型后续散文 token，保持表格稳定
          if (streamConfirms.value.length) return
          // 只在首段正文到来时等步骤错峰链；每个 token 都 await 会把后续 SSE 堵在缓冲里，结束后整段蹦出
          if (!flushStepsNow) {
            flushStepsNow = true
            await stepRevealChain
          }
          streamAnswerPending.value = true
          streamProcessCollapsed.value = false
          if (!streamDurationText.value) {
            const sec = Math.max(1, Math.round((Date.now() - streamStartedAt.value) / 1000))
            streamDurationText.value = `${sec}s`
          }
          streamProcess.value = streamProcess.value.filter(
            (i) => !(i.type === 'status' && i.phase === 'generating')
          )
          // 大段终稿：含表格时禁止按行假流式（每行重绘会抖）；仅散文渐进
          const looksTable =
            /\|.+\|/.test(text) || /\|.+\|/.test(streamContent.value || '')
          if (text.length > 96 && !looksTable) {
            const base = streamContent.value || ''
            const target = base + text
            let i = base.length
            const total = text.length
            const step = total > 2500 ? 48 : total > 1200 ? 32 : 24
            const delay = total > 2500 ? 8 : 12
            while (i < target.length) {
              if (requestId !== activeRequestId || threadId.value !== currentThread) return
              i = Math.min(target.length, i + step)
              streamContent.value = target.slice(0, i)
              paintStreamDisplay()
              scrollToBottomThrottled()
              await new Promise((r) => setTimeout(r, delay))
            }
            streamContent.value = target
          } else {
            streamContent.value += text
          }
          paintStreamDisplay()
          scrollToBottomThrottled()
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
            let lastWorkspace = ''
            try {
              const [rp, pref] = await Promise.all([
                fetchCursorDevRepos().catch(() => null),
                fetchLocalWorkspacePref().catch(() => null),
              ])
              repos = Array.isArray(rp?.data?.repos) ? rp.data.repos : []
              defaultRepo = rp?.data?.default_repo || repos[0] || ''
              lastWorkspace = String(pref?.data?.path || '').trim()
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
            finalContent = '请先选择本次写码目标。默认本机目录（沙箱改码后同步）；也可改走 GitHub。'
            cursorDevAnchor = {
              id: `cursor-dev-anchor-${Date.now()}`,
              status: 'pending',
              target: 'local',
              workspace: lastWorkspace,
              lastWorkspace,
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
              // 主线：即使车道暂不可用也保留确认卡（展示原因），禁止静默丢卡导致「没有后续」
              if (cursorDevPick && cursorDevPick.available === false) {
                finalContent = [
                  finalContent,
                  '写码确认卡已生成；当前车道暂不可用，请按卡片提示处理或联系管理员后点确认。',
                ]
                  .filter(Boolean)
                  .join('\n\n')
              }
            } catch (e) {
              console.error('build cursor-dev pick failed', e)
              finalContent = [finalContent, formatCursorDevAdminGuide(e?.message || e)].filter(Boolean).join('\n\n')
            }
          } else if (
            !parsed.propose &&
            !parsed.options &&
            /:::cursor_dev_propose\b/i.test(streamContent.value || '') &&
            !hasPendingCursorDevPick()
          ) {
            // 机器块存在但解析失败：仍给出可编辑确认卡，避免主线断裂
            const lastUser = [...messages.value].reverse().find((m) => m?.role === 'user')
            const fallbackReq =
              String(hideCursorDevMachineBlocks(streamContent.value || '') || '').trim() ||
              String(lastUser?.content || '').trim() ||
              '请确认并补充本轮写码需求'
            try {
              cursorDevPick = await buildCursorDevPickFromPropose({
                requirement: fallbackReq.slice(0, 6000),
                repo: findConfirmedCursorDevAnchor()?.anchor?.repo || '',
                ref: '',
              })
              finalContent =
                hideCursorDevMachineBlocks(finalContent) ||
                '需求摘要已整理到确认卡（自动修复了不完整的机器块）。请核对后点确认写码。'
            } catch (e) {
              console.error('fallback cursor-dev pick failed', e)
              finalContent = hideCursorDevMachineBlocks(finalContent)
            }
          }
        } else if (!confirms.length && isPasteCodeLane) {
          // 贴码车道：剥掉误出的写码机器块，绝不出选仓卡
          const parsed = parseCursorDevMachineBlocks(finalContent)
          finalContent = parsed.content
        }
        const fenceParsed = parseAnalysisChartFences(finalContent)
        finalContent = fenceParsed.content
        // SSE 已推送图表时，只剥 fence 不再二次挂载，避免同一张图出现两次
        const fromStream = (streamCharts.value || []).map((c) => ({ ...c }))
        const charts = mergeUniqueCharts(
          fromStream,
          fromStream.length ? [] : fenceParsed.charts || [],
        )
        const dashboards = (streamDashboards.value || []).map((d) => ({ ...d }))
        if (finalContent || processItems.length || confirms.length || charts.length || dashboards.length || cursorDevPick || cursorDevOptions || cursorDevAnchor) {
          pushAssistantMessage({
            content: finalContent,
            processItems,
            confirms,
            charts,
            dashboards,
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
            charts: [],
            dashboards: [],
            durationText,
            stopped: false,
          })
        }
        streamContent.value = ''
        resetStreamDisplay()
        streamProcess.value = []
        streamConfirms.value = []
        streamCharts.value = []
        streamDashboards.value = []
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
          charts: (streamCharts.value || []).map((c) => ({ ...c })),
          dashboards: (streamDashboards.value || []).map((d) => ({ ...d })),
          durationText: streamDurationText.value || '',
          stopped: false,
        })
        streamContent.value = ''
        resetStreamDisplay()
        streamProcess.value = []
        streamConfirms.value = []
        streamCharts.value = []
        streamDashboards.value = []
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
      resetStreamDisplay()
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
  const entityLabel = String(preview.target_label || preview.label || '').trim()
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

  const recordWord = entityLabel ? `${entityLabel}记录` : '记录'
  const countWord = entityLabel || '记录'

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
      entityLabel
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

onMounted(async () => {
  window.addEventListener('keydown', onLightboxKeydown)
  await initFromRoute()
  if (inputEl.value) inputEl.value.focus()
})

onUnmounted(() => {
  chatViewAlive = false
  window.removeEventListener('keydown', onLightboxKeydown)
  closeImageLightbox()
  // 会话切换会整页重挂载：先把流式缓冲区里的图/看板并入 messages 并尽力落盘，
  // 再掐断请求；否则 onDone 因 requestId 失效直接 return，图只存在于内存就丢了。
  try {
    const charts = (streamCharts.value || []).map((c) => ({ ...c }))
    const dashboards = (streamDashboards.value || []).map((d) => ({ ...d }))
    const streamText = (streamContent.value || '').trimEnd()
    const chartIds = new Set(charts.map((c) => c?.id).filter(Boolean))
    const dashIds = new Set(dashboards.map((d) => d?.id).filter(Boolean))
    const alreadyPersisted = messages.value.some((m) => {
      if (chartIds.size && (m.charts || []).some((c) => c?.id && chartIds.has(c.id))) return true
      if (dashIds.size && (m.dashboards || []).some((d) => d?.id && dashIds.has(d.id))) return true
      return false
    })
    if (
      !alreadyPersisted &&
      (charts.length || dashboards.length || (streaming.value && streamText))
    ) {
      pushAssistantMessage({
        content: streamText || '',
        processItems: (streamProcess.value || []).filter(
          (i) => i.type === 'step' && i.id !== 'boot',
        ),
        confirms: (streamConfirms.value || []).map((c) => ({ ...c })),
        charts,
        dashboards,
        durationText: streamDurationText.value || '',
        stopped: true,
      })
    }
    streamCharts.value = []
    streamDashboards.value = []
    streamContent.value = ''
    streamProcess.value = []
    streamConfirms.value = []
    if (threadId.value && messages.value.length) {
      void persistSession()
    }
  } catch (e) {
    console.warn('会话卸载前保存图表失败', e)
  }
  // 必须停掉流式请求与写码轮询，否则旧定时器继续改 DOM 导致点击无响应
  activeRequestId += 1
  try {
    streamAbort.value?.abort()
  } catch {
    /* ignore */
  }
  streamAbort.value = null
  clearActiveCursorDev()
  streaming.value = false
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
  width: 100%;
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
  max-width: 100%;
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

/* 流式输出固定气泡宽度，避免表格列变宽时左右抽动 */
.message.assistant .msg-body.streaming-body {
  width: 100%;
  max-width: 100%;
  contain: layout style;
}

/* 确认卡与同条消息体同宽（跟随较宽的表格气泡拉伸） */
.message.assistant .msg-content :deep(.write-confirm),
.message.assistant .msg-content :deep(.ide-ws-pick),
.message.assistant .msg-content :deep(.commit-gate) {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
/* 分析看板/单图与消息区同宽，避免格子又窄又长 */
.message.assistant .msg-content :deep(.analysis-dashboard-card),
.message.assistant .msg-content :deep(.analysis-chart-card) {
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
  table-layout: fixed;
}

:deep(.md-table td),
:deep(.md-table th) {
  padding: 6px 10px;
  border: 1px solid var(--ui-border);
  text-align: left;
  word-break: break-word;
}

:deep(.md-table th) {
  background: var(--ui-panel);
  font-weight: 500;
}

:deep(.md-stream-pending) {
  margin-top: 6px;
  padding: 6px 8px;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 12px;
  line-height: 1.45;
  color: var(--ui-text-muted);
  white-space: pre-wrap;
  opacity: 0.85;
  border-left: 2px solid var(--ui-border);
}

/* 流式阶段表格：等宽预排，固定宽度，禁止 HTML table 列宽重算 */
:deep(.md-table-plain) {
  display: block;
  width: 100%;
  max-width: 100%;
  margin: 8px 0;
  padding: 10px 12px;
  box-sizing: border-box;
  overflow-x: auto;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre;
  tab-size: 4;
  color: var(--ui-text);
  background: var(--ui-panel);
  border: 1px solid var(--ui-border);
  border-radius: 8px;
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
