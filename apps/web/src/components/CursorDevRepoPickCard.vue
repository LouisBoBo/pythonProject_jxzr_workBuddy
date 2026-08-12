<template>
  <div class="cursor-dev-pick" :class="statusClass">
    <template v-if="isPending">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">写码确认</span>
          <span class="cd-hint">确认后开始改代码；取消可继续对话</span>
        </div>
        <p class="cd-summary">请确认写码目标与需求摘要</p>
        <p class="cd-desc">默认写入本机目录（沙箱隔离后再同步）；也可改走 GitHub</p>
      </div>

      <div class="cd-tabs" role="tablist">
        <button
          type="button"
          class="cd-tab"
          :class="{ active: targetTab === 'local' }"
          :disabled="busy"
          @click="targetTab = 'local'"
        >
          本地目录
        </button>
        <button
          type="button"
          class="cd-tab"
          :class="{ active: targetTab === 'github' }"
          :disabled="busy"
          @click="targetTab = 'github'"
        >
          GitHub
        </button>
      </div>

      <div v-if="card.reason && targetTab === 'github'" class="cd-warn">{{ card.reason }}</div>
      <div v-if="localAvailReason && targetTab === 'local'" class="cd-warn">{{ localAvailReason }}</div>

      <label class="cd-field">
        <span class="cd-label">需求摘要</span>
        <textarea
          v-model="requirementInput"
          class="cd-input cd-textarea"
          rows="4"
          placeholder="助手理解的需求（可直接改）"
          :disabled="busy"
        />
      </label>

      <template v-if="targetTab === 'local'">
        <label class="cd-field">
          <span class="cd-label">本机工程目录</span>
          <div class="cd-path-row">
            <input
              v-model="workspaceInput"
              type="text"
              class="cd-input"
              placeholder="例如 /Users/你/Projects/my-app"
              :disabled="busy || picking"
            />
            <button
              type="button"
              class="cd-btn browse"
              :disabled="busy || picking"
              @click="onBrowseFolder"
            >
              {{ picking ? '选择中…' : '浏览…' }}
            </button>
          </div>
        </label>
        <p v-if="lastWorkspace || card.lastWorkspace" class="cd-suggest">
          上次：
          <button
            type="button"
            class="cd-chip"
            :disabled="busy"
            @click="workspaceInput = lastWorkspace || card.lastWorkspace"
          >
            {{ lastWorkspace || card.lastWorkspace }}
          </button>
        </p>
        <p class="cd-desc">改码先在沙箱进行，成功后才同步到该目录；失败不会脏写宿主机。</p>
      </template>

      <template v-else>
        <label class="cd-field">
          <span class="cd-label">代码仓库</span>
          <input
            v-model="repoInput"
            type="text"
            class="cd-input"
            placeholder="例如 LouisBoBo/pythonProject_zr_aicoding 或 https://github.com/…"
            :disabled="busy"
          />
        </label>
        <label class="cd-field">
          <span class="cd-label">起始分支（可留空=仓库默认分支）</span>
          <input
            v-model="refInput"
            type="text"
            class="cd-input"
            placeholder="留空，或填 main / master 等真实存在的分支"
            :disabled="busy"
          />
        </label>
        <label class="cd-check">
          <input v-model="createPr" type="checkbox" :disabled="busy" />
          <span>完成后尝试创建 PR（默认不勾；推荐代码留在你的工作分支，自行合 main）</span>
        </label>
        <p v-if="suggestions.length" class="cd-suggest">
          常用：
          <button
            v-for="s in suggestions"
            :key="s"
            type="button"
            class="cd-chip"
            :disabled="busy"
            @click="repoInput = s"
          >
            {{ s }}
          </button>
        </p>
      </template>

      <p v-if="localError" class="cd-error">{{ localError }}</p>

      <div class="cd-actions">
        <button type="button" class="cd-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button
          type="button"
          class="cd-btn confirm"
          :class="{ 'is-loading': busy }"
          :disabled="busy || !canConfirm"
          @click="onConfirm"
        >
          <span v-if="busy" class="cd-spinner" aria-hidden="true" />
          {{ busy ? '启动中…' : (targetTab === 'local' ? '确认并写入本机' : '确认并开始写码') }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'failed'">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">写码失败</span>
          <span class="cd-hint warn">可补救</span>
        </div>
        <p class="cd-summary">{{ failureTitle }}</p>
        <p class="cd-desc">下一步：{{ failureNext }}</p>
      </div>
      <div class="cd-chosen">
        <div v-if="isLocalTarget && confirmedWorkspace" class="cd-chosen-row">
          <span class="cd-k">本机目录</span>
          <span class="cd-v mono">{{ confirmedWorkspace }}</span>
        </div>
        <div v-if="!isLocalTarget && confirmedRepo" class="cd-chosen-row">
          <span class="cd-k">仓库</span>
          <span class="cd-v mono">{{ confirmedRepo }}</span>
        </div>
        <div v-if="!isLocalTarget && confirmedRef" class="cd-chosen-row">
          <span class="cd-k">工作分支</span>
          <span class="cd-v mono">{{ confirmedRef }}</span>
        </div>
        <div v-if="confirmedRequirement" class="cd-chosen-row cd-chosen-req">
          <span class="cd-k">需求</span>
          <div class="cd-v cd-req-md" v-html="confirmedRequirementHtml"></div>
        </div>
      </div>
      <div class="cd-actions">
        <button type="button" class="cd-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button type="button" class="cd-btn confirm" :class="{ 'is-loading': busy }" :disabled="busy" @click="onRetry">
          <span v-if="busy" class="cd-spinner" aria-hidden="true" />
          {{ busy ? '重试中…' : '重试写码' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">{{ isIdle ? '已确认' : '写码确认' }}</span>
          <span v-if="channelBadge" class="cd-hint" :class="{ warn: isRunning && channelBadge.includes('Cloud') }">
            {{ channelBadge }}
          </span>
          <span v-else-if="isRunning" class="cd-hint">写码进行中</span>
          <span v-else-if="isIdle" class="cd-hint">可续聊</span>
        </div>
        <p class="cd-summary">
          {{
            isLocalTarget
              ? (isIdle
                ? (previewUrl
                  ? `本轮已同步到本机目录${confirmedWorkspace ? ` ${confirmedWorkspace}` : ''}；可打开预览验收`
                  : `本轮已同步到本机目录${confirmedWorkspace ? ` ${confirmedWorkspace}` : ''}；${previewNotes || '预览未自动就绪，可手动启动工程'}`)
                : (runningProgress || '已确认，正在沙箱内写码'))
              : (isIdle
                ? `本轮已按上表写入工作分支${confirmedRef ? ` ${confirmedRef}` : ''}；合入请看下方「合入指引」`
                : (runningProgress || '已确认，正在按需求写码'))
          }}
        </p>
        <p v-if="isRunning" class="cd-desc">
          {{ isLocalTarget ? '改码在沙箱进行，成功后才同步到目标目录。可强制结束。' : runningHint }}
        </p>
        <p v-else-if="isIdle && !isLocalTarget" class="cd-desc">同窗继续发改码需求会沿用本任务与工作分支；无需重新选仓。</p>
        <p v-else-if="isIdle && isLocalTarget" class="cd-desc">同窗可继续对话澄清下一轮需求后再弹确认卡。</p>
      </div>
      <div class="cd-chosen">
        <div v-if="isLocalTarget" class="cd-chosen-row">
          <span class="cd-k">本机目录</span>
          <span class="cd-v mono">{{ confirmedWorkspace }}</span>
        </div>
        <template v-else>
          <div class="cd-chosen-row">
            <span class="cd-k">仓库</span>
            <span class="cd-v mono">{{ confirmedRepo }}</span>
          </div>
          <div v-if="confirmedRef" class="cd-chosen-row">
            <span class="cd-k">工作分支</span>
            <span class="cd-v mono">{{ confirmedRef }}</span>
          </div>
        </template>
        <div v-if="confirmedRequirement" class="cd-chosen-row cd-chosen-req">
          <span class="cd-k">需求</span>
          <div class="cd-v cd-req-md" v-html="confirmedRequirementHtml"></div>
        </div>
        <div v-if="isLocalTarget && previewUrl" class="cd-chosen-row">
          <span class="cd-k">预览</span>
          <span class="cd-v">
            <a class="cd-preview-link" :href="previewUrl" target="_blank" rel="noopener noreferrer">{{ previewUrl }}</a>
          </span>
        </div>
        <div v-else-if="isLocalTarget && isIdle && previewNotes" class="cd-chosen-row">
          <span class="cd-k">预览</span>
          <span class="cd-v">{{ previewNotes }}</span>
        </div>
        <div v-if="isLocalTarget && syncedFiles.length" class="cd-chosen-row cd-chosen-req">
          <span class="cd-k">已同步</span>
          <span class="cd-v mono">{{ syncedFiles.slice(0, 12).join(', ') }}{{ syncedFiles.length > 12 ? '…' : '' }}</span>
        </div>
      </div>
      <CodingPlanCard
        v-if="normalizedPlanSteps.length"
        class="cd-plan"
        :steps="normalizedPlanSteps"
        heading="本轮进度"
        :collapsible="true"
        :default-collapsed="isIdle"
      />
      <div v-if="isRunning" class="cd-actions">
        <button type="button" class="cd-btn cancel" :disabled="busy" @click="onForceStop">
          强制结束
        </button>
        <button v-if="!isLocalTarget" type="button" class="cd-btn ghost" :disabled="busy" @click="onReattach">
          重新挂接
        </button>
        <button type="button" class="cd-btn confirm" :disabled="busy" @click="onRetryFromRunning">
          重试写码
        </button>
      </div>
    </template>

    <template v-else>
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">写码确认</span>
        </div>
        <p class="cd-summary">已取消。可继续对话澄清，需求明确后会再次弹出确认</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  cursorDevChannelBadge,
  cursorDevSpeedLabel,
  friendlyCursorDevFailure,
} from '../cursorDevUx.js'
import { pickLocalDevFolder, checkLocalDevWorkspace } from '../api.js'
import { renderMarkdown } from '../markdown.js'
import CodingPlanCard from './CodingPlanCard.vue'

const props = defineProps({
  card: {
    type: Object,
    required: true,
  },
  /** 本轮写码进度步骤（与确认卡同条消息） */
  planSteps: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['resolved'])

const busy = ref(false)
const picking = ref(false)
const targetTab = ref('local')
const repoInput = ref('')
const refInput = ref('')
const workspaceInput = ref('')
const lastWorkspace = ref('')
const requirementInput = ref('')
const createPr = ref(false)
const localError = ref('')
let busyFallbackTimer = null

const isLocalTarget = computed(
  () => String(props.card?.target || targetTab.value || 'local') === 'local',
)
const localAvailReason = computed(() => {
  if (props.card?.localAvailable === false) {
    return props.card?.localReason || '本机写码暂不可用（请检查对话模型 API Key）'
  }
  return ''
})
const syncedFiles = computed(() =>
  Array.isArray(props.card?.syncedFiles) ? props.card.syncedFiles.filter(Boolean) : [],
)
const previewUrl = computed(() => String(props.card?.previewUrl || '').trim())
const previewNotes = computed(() => {
  const p = props.card?.preview
  if (p && typeof p === 'object' && p.notes) return String(p.notes)
  return ''
})
const normalizedPlanSteps = computed(() =>
  Array.isArray(props.planSteps) ? props.planSteps.filter(Boolean) : [],
)
const confirmedWorkspace = computed(
  () => String(props.card?.workspace || workspaceInput.value || '').trim(),
)

function armBusy() {
  busy.value = true
  if (busyFallbackTimer != null) clearTimeout(busyFallbackTimer)
  // 父级若未更新 status，避免按钮永久锁死
  busyFallbackTimer = window.setTimeout(() => {
    busyFallbackTimer = null
    busy.value = false
  }, 45000)
}

function clearBusy() {
  busy.value = false
  if (busyFallbackTimer != null) {
    clearTimeout(busyFallbackTimer)
    busyFallbackTimer = null
  }
}

watch(
  () => [props.card?.status, props.card?.phase],
  () => {
    // 状态/阶段变化后释放按钮（含 running→failed）
    if (props.card?.status && props.card.status !== 'pending') clearBusy()
  },
)

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')
const isIdle = computed(() => props.card?.phase === 'idle_for_followup')
const isRunning = computed(
  () =>
    props.card?.status === 'confirmed' &&
    (props.card?.phase === 'running' || props.card?.phase === 'starting'),
)

const failureInfo = computed(() =>
  friendlyCursorDevFailure(props.card?.error || '', {
    userStopped: Boolean(props.card?.userStopped),
  }),
)
const failureTitle = computed(() => failureInfo.value.title)
const failureNext = computed(() => failureInfo.value.next)

const channelBadge = computed(() => {
  if (isLocalTarget.value) {
    if (isIdle.value) return '本机已同步'
    if (isRunning.value) return '本机沙箱'
    return ''
  }
  if (isIdle.value && props.card?.channel === 'patch') return '快速补丁完成'
  if (isIdle.value) return ''
  return cursorDevChannelBadge(props.card || {})
})

const runningProgress = computed(() => {
  if (isLocalTarget.value) return props.card?.progressText || ''
  const speed = cursorDevSpeedLabel(props.card || {})
  return speed || props.card?.progressText || ''
})

const runningHint = computed(() => {
  const badge = channelBadge.value
  if (badge === '快速补丁') {
    return '正在走快速补丁（通常几十秒）。异常时可「强制结束」或「重试写码」。'
  }
  if (badge === '复用加速') {
    return '正在复用已有 Cloud Agent。进度丢失可「重新挂接」。'
  }
  if (badge.includes('Cloud')) {
    return 'Cloud 冷启动常见 1–3 分钟。可停止、强制结束，或进度丢失时「重新挂接」。'
  }
  return '可停止 / 强制结束；进度丢失点「重新挂接」；结束后可「重试写码」。'
})

const suggestions = computed(() =>
  Array.isArray(props.card?.repos) ? props.card.repos.filter(Boolean) : []
)

const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed' && isIdle.value) return 'is-confirmed is-idle'
  if (s === 'confirmed' && isRunning.value) return 'is-confirmed is-running'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled') return 'is-cancelled'
  if (s === 'failed') return 'is-failed'
  return 'is-pending'
})

const confirmedRepo = computed(() => props.card?.repo || normalizeRepo(repoInput.value) || '')
const confirmedRef = computed(() => String(props.card?.ref || refInput.value || '').trim())
const confirmedRequirement = computed(
  () => String(props.card?.requirement || props.card?.pendingContent || '').trim(),
)
const confirmedRequirementHtml = computed(() => renderMarkdown(confirmedRequirement.value))

const canConfirm = computed(() => {
  const req = Boolean(String(requirementInput.value || '').trim())
  if (!req) return false
  if (targetTab.value === 'local') {
    return Boolean(String(workspaceInput.value || '').trim()) && props.card?.localAvailable !== false
  }
  return (
    Boolean(normalizeRepo(repoInput.value)) &&
    props.card?.available !== false
  )
})

watch(
  () => [
    props.card?.repo,
    props.card?.repos,
    props.card?.ref,
    props.card?.requirement,
    props.card?.pendingContent,
    props.card?.createPr,
    props.card?.target,
    props.card?.workspace,
    props.card?.lastWorkspace,
  ],
  () => {
    const t = String(props.card?.target || 'local').toLowerCase()
    targetTab.value = t === 'github' ? 'github' : 'local'
    if (props.card?.repo) {
      repoInput.value = props.card.repo
    } else if (!String(repoInput.value || '').trim() && suggestions.value.length) {
      repoInput.value = suggestions.value[0]
    }
    if (props.card?.ref != null) {
      refInput.value = props.card.ref
    } else if (!String(refInput.value || '').trim() && props.card?.ref === undefined) {
      refInput.value = ''
    }
    const ws = props.card?.workspace || props.card?.lastWorkspace || ''
    if (ws) workspaceInput.value = String(ws)
    lastWorkspace.value = String(props.card?.lastWorkspace || ws || '')
    const req = props.card?.requirement || props.card?.pendingContent || ''
    if (req) requirementInput.value = String(req)
    if (typeof props.card?.createPr === 'boolean') {
      createPr.value = props.card.createPr
    }
  },
  { immediate: true },
)

function normalizeRepo(raw) {
  let s = String(raw || '').trim().replace(/^["']|["']$/g, '')
  if (!s) return ''
  const ssh = s.match(/^git@[^:]+:(.+)$/i)
  if (ssh) s = ssh[1]
  if (/^https?:\/\//i.test(s)) {
    try {
      const u = new URL(s)
      s = u.pathname.replace(/^\/+/, '')
    } catch {
      return ''
    }
  }
  s = s.replace(/\.git$/i, '').replace(/\/+$/, '')
  const parts = s.split('/').filter(Boolean)
  if (parts.length < 2) return ''
  return `${parts[0]}/${parts[1]}`
}

async function validateLocalWorkspace(path) {
  const workspace = String(path || '').trim()
  if (!workspace) {
    return { ok: false, error: '请填写本机工程绝对路径' }
  }
  try {
    const resp = await checkLocalDevWorkspace(workspace)
    const data = resp?.data || {}
    if (!data.ok) {
      return { ok: false, error: data.error || '目标目录无效', data }
    }
    return { ok: true, error: '', data }
  } catch (e) {
    const detail = e?.response?.data?.detail
    return {
      ok: false,
      error: (typeof detail === 'string' ? detail : null) || e?.message || '目录校验失败',
    }
  }
}

async function onBrowseFolder() {
  if (busy.value || picking.value) return
  localError.value = ''
  picking.value = true
  try {
    const resp = await pickLocalDevFolder('选择本机工程目录')
    const data = resp?.data || {}
    if (data.ok && data.path) {
      workspaceInput.value = String(data.path)
      const check = await validateLocalWorkspace(data.path)
      if (!check.ok) localError.value = check.error
    } else if (data.error && data.error !== '已取消选择') {
      localError.value = data.error
    }
  } catch (e) {
    localError.value = e?.response?.data?.detail || e?.message || '无法打开选文件夹对话框'
  } finally {
    picking.value = false
  }
}

function onCancel() {
  if (busy.value) return
  if (!isPending.value && props.card?.status !== 'failed') return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'cancelled',
    target: targetTab.value === 'github' ? 'github' : 'local',
    workspace: String(workspaceInput.value || props.card?.workspace || '').trim(),
    repo: normalizeRepo(repoInput.value) || props.card?.repo || '',
    ref: String(refInput.value || props.card?.ref || '').trim(),
    requirement: String(requirementInput.value || props.card?.requirement || '').trim(),
    createPr: Boolean(createPr.value),
  })
}

async function onConfirm() {
  if (busy.value || !isPending.value) return
  localError.value = ''
  const requirement = String(requirementInput.value || '').trim()
  if (!requirement) {
    localError.value = '请填写或修改需求摘要后再确认'
    return
  }
  if (targetTab.value === 'local') {
    const workspace = String(workspaceInput.value || '').trim()
    if (!workspace) {
      localError.value = '请填写本机工程绝对路径'
      return
    }
    armBusy()
    const check = await validateLocalWorkspace(workspace)
    if (!check.ok) {
      clearBusy()
      localError.value = check.error
      return
    }
    if (check.data?.path) workspaceInput.value = String(check.data.path)
    emit('resolved', {
      id: props.card.id,
      status: 'confirmed',
      target: 'local',
      workspace: String(workspaceInput.value || workspace).trim(),
      repo: '',
      ref: '',
      requirement,
      createPr: false,
    })
    return
  }
  const repo = normalizeRepo(repoInput.value)
  if (!repo) {
    localError.value = '请填写 owner/repo 或 GitHub HTTPS 地址'
    return
  }
  repoInput.value = repo
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'confirmed',
    target: 'github',
    workspace: '',
    repo,
    ref: String(refInput.value || '').trim(),
    requirement,
    createPr: Boolean(createPr.value),
  })
}

function onRetry() {
  if (busy.value || props.card?.status !== 'failed') return
  armBusy()
  const target =
    String(props.card?.target || targetTab.value || 'local') === 'github' ? 'github' : 'local'
  emit('resolved', {
    id: props.card.id,
    status: 'retry',
    target,
    workspace: String(props.card?.workspace || workspaceInput.value || '').trim(),
    repo: props.card?.repo || normalizeRepo(repoInput.value),
    ref: String(props.card?.ref || refInput.value || '').trim(),
    requirement: String(props.card?.requirement || requirementInput.value || '').trim(),
    createPr: Boolean(props.card?.createPr ?? createPr.value),
    jobId: props.card?.jobId || '',
  })
}

function onForceStop() {
  if (busy.value || !isRunning.value) return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'force_stop',
    target: isLocalTarget.value ? 'local' : 'github',
    workspace: String(props.card?.workspace || '').trim(),
    repo: props.card?.repo || '',
    ref: String(props.card?.ref || '').trim(),
    requirement: String(props.card?.requirement || props.card?.pendingContent || '').trim(),
    createPr: Boolean(props.card?.createPr),
    jobId: props.card?.jobId || '',
  })
}

function onReattach() {
  if (busy.value || !isRunning.value) return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'reattach',
    repo: props.card?.repo || '',
    ref: String(props.card?.ref || '').trim(),
    requirement: String(props.card?.requirement || props.card?.pendingContent || '').trim(),
    createPr: Boolean(props.card?.createPr),
    jobId: props.card?.jobId || '',
  })
}

function onRetryFromRunning() {
  if (busy.value || !isRunning.value) return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'retry',
    target: isLocalTarget.value ? 'local' : 'github',
    workspace: String(props.card?.workspace || '').trim(),
    repo: props.card?.repo || '',
    ref: String(props.card?.ref || '').trim(),
    requirement: String(props.card?.requirement || props.card?.pendingContent || '').trim(),
    createPr: Boolean(props.card?.createPr),
    jobId: props.card?.jobId || '',
    forceNew: true,
  })
}
</script>

<style scoped>
.cursor-dev-pick {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #d5dde8;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(244, 248, 252, 0.95) 0%, #fff 48%);
  color: var(--ui-text, #1a1f26);
  box-shadow: 0 1px 0 rgba(47, 84, 140, 0.06);
  /* 钉死字号，避免继承聊天气泡 16px 导致「需求」比仓库/分支大一号 */
  font-size: 12px;
  line-height: 1.5;
}

.cursor-dev-pick.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
}

/* 闲置回执：弱化成「已确认」记录，避免与合入指引的「写码完成」抢视觉 */
.cursor-dev-pick.is-idle {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
}

.cursor-dev-pick.is-idle .cd-badge {
  color: #5a6a7a;
}

.cursor-dev-pick.is-idle .cd-summary {
  font-size: 13px;
  font-weight: 500;
  color: #3a4250;
}

.cursor-dev-pick.is-running {
  border-color: #b7c9e0;
  background: linear-gradient(180deg, #f3f7fc 0%, #fff 55%);
}

.cursor-dev-pick.is-running .cd-hint {
  color: #1d4f91;
  background: rgba(47, 84, 140, 0.12);
}

.cursor-dev-pick.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
}

.cursor-dev-pick.is-failed {
  border-color: #f0c2c2;
  background: linear-gradient(180deg, #fff5f5 0%, #fff 50%);
  box-shadow: none;
}

.cd-check {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 10px 0 0;
  font-size: 12px;
  color: #3a4250;
  line-height: 1.45;
}

.cd-check input {
  margin-top: 2px;
}

.cd-head {
  margin-bottom: 10px;
}

.cd-tabs {
  display: flex;
  gap: 6px;
  margin: 0 0 12px;
}

.cd-tab {
  flex: 1;
  border: 1px solid #d5dde8;
  background: #fff;
  color: #4a5564;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.cd-tab.active {
  border-color: #2f548c;
  color: #2f548c;
  background: rgba(47, 84, 140, 0.08);
}

.cd-tab:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cd-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.cd-badge {
  display: inline-flex;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2f548c;
  font-weight: 700;
}

.is-confirmed .cd-badge {
  color: #2f7d4a;
}

.cd-hint {
  font-size: 12px;
  color: #5a7394;
  background: rgba(47, 84, 140, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.cd-hint.warn {
  color: #9a3412;
  background: #fff7ed;
}

.cd-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: #1f2630;
}

.cd-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #7a8494;
}

.cd-warn {
  margin-bottom: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  color: #9a3412;
  font-size: 12px;
  line-height: 1.45;
}

.cd-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cd-path-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.cd-path-row .cd-input {
  flex: 1;
  min-width: 0;
}

.cd-label {
  font-size: 12px;
  color: #6b7c8f;
}

.cd-input {
  border: 1px solid #d0d7e0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: #1f2630;
  background: #fff;
  outline: none;
}

.cd-textarea {
  resize: vertical;
  min-height: 88px;
  font-family: inherit;
  line-height: 1.5;
}

.cd-input:focus {
  border-color: #2f548c;
  box-shadow: 0 0 0 2px rgba(47, 84, 140, 0.12);
}

.cd-suggest {
  margin: 8px 0 0;
  font-size: 12px;
  color: #6b7c8f;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.cd-chip {
  border: 1px solid #d0d7e0;
  background: #f8fafc;
  color: #334155;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.cd-chip:hover:not(:disabled) {
  border-color: #94a3b8;
  background: #f1f5f9;
}

.cd-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b42318;
}

.cd-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #dde5ef;
}

.cd-btn {
  border: 1px solid transparent;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: #fff;
  border-radius: 8px;
  min-width: 96px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.cd-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.cd-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
}

.cd-btn.browse {
  border-color: #d0d7e0;
  color: #2f548c;
  background: #fff;
  min-width: auto;
  padding: 8px 12px;
  white-space: nowrap;
  flex-shrink: 0;
}

.cd-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
}

.cd-btn.ghost {
  border-color: #c5d0de;
  color: #2f548c;
  background: #fff;
}

.cd-btn.ghost:hover:not(:disabled) {
  background: #eef3f9;
}

.cd-btn.confirm {
  background: #2f548c;
  color: #fff !important;
  border-color: #2f548c;
}

.cd-btn.confirm:hover:not(:disabled) {
  background: #254572;
}

.cd-btn.confirm.is-loading {
  opacity: 1;
}

.cd-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: cd-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes cd-spin {
  to {
    transform: rotate(360deg);
  }
}

.cd-chosen {
  margin-top: 2px;
}

.cd-plan {
  margin: 10px 0 0;
  max-width: none;
}

.cd-chosen-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #d7e8dc;
  border-radius: 8px;
}

.cd-chosen-row + .cd-chosen-row {
  margin-top: 8px;
}

.cd-k {
  font-size: 12px;
  line-height: 1.5;
  color: #6b7c6f;
  padding-top: 1px;
}

.cd-v {
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  color: #3a4250;
  word-break: break-word;
}

.cd-v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  word-break: break-all;
}

.cd-preview-link {
  color: #2563eb;
  text-decoration: none;
  word-break: break-all;
}

.cd-preview-link:hover {
  text-decoration: underline;
}

.cd-chosen-req .cd-v {
  white-space: normal;
}

/* 与 ChatView 聊天气泡 Markdown 字号/字重/行高保持一致（图2） */
.cd-req-md {
  font-family: var(--font-sans, inherit);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.65;
  color: #0a0f14;
}

.cd-req-md :deep(.md-h1) {
  font-size: 15px;
  font-weight: 600;
  margin: 12px 0 6px;
  color: inherit;
}

.cd-req-md :deep(.md-h2) {
  font-size: 14px;
  font-weight: 600;
  margin: 10px 0 4px;
  color: inherit;
}

.cd-req-md :deep(.md-h3) {
  font-size: 13px;
  font-weight: 600;
  margin: 8px 0 4px;
  color: inherit;
}

.cd-req-md :deep(.md-ul) {
  padding-left: 18px;
  margin: 4px 0;
}

.cd-req-md :deep(.md-li) {
  margin: 2px 0;
  list-style: disc;
}

.cd-req-md :deep(.inline-code) {
  background: oklch(0.967 0.001 286.375);
  color: oklch(0.52 0.105 223.128);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 12px;
}

.cd-req-md :deep(strong) {
  font-weight: 600;
  color: inherit;
}

.cd-req-md :deep(.md-hr) {
  border: none;
  border-top: 1px solid oklch(0.925 0.005 214.3);
  margin: 10px 0;
}

.cd-req-md :deep(.md-table) {
  width: 100%;
  max-width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
  display: block;
  overflow-x: auto;
}

.cd-req-md :deep(.md-table td),
.cd-req-md :deep(.md-table th) {
  padding: 6px 10px;
  border: 1px solid oklch(0.925 0.005 214.3);
  text-align: left;
}

.cd-req-md :deep(.md-table th) {
  background: oklch(0.985 0.002 197.1);
  font-weight: 500;
}

.cd-req-md :deep(.code-block-wrap) {
  position: relative;
  margin: 8px 0;
  border-radius: 8px;
  overflow: hidden;
  background: #1e293b;
  border: 1px solid #334155;
}

.cd-req-md :deep(.code-block) {
  margin: 0;
  padding: 12px 14px;
  color: #e2e8f0;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace);
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
}

.cd-req-md :deep(.file-link) {
  color: oklch(0.52 0.105 223.128);
  text-decoration: none;
  border-bottom: 1px solid oklch(0.955 0.015 223);
  padding-bottom: 1px;
}
</style>
