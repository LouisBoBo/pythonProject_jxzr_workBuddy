<template>
  <div class="cursor-dev-pick" :class="statusClass">
    <template v-if="isPending">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">写码确认</span>
          <span class="cd-hint">确认后开始改代码；取消可继续对话</span>
        </div>
        <p class="cd-summary">请确认目标仓库与需求摘要</p>
        <p class="cd-desc">需求理解有偏差可点取消，继续聊清楚后再弹确认</p>
      </div>

      <div v-if="card.reason" class="cd-warn">{{ card.reason }}</div>

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
          {{ busy ? '启动中…' : '确认并开始写码' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'failed'">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">写码失败</span>
          <span class="cd-hint warn">可重试</span>
        </div>
        <p class="cd-summary">{{ card.error || '写码未成功' }}</p>
        <p class="cd-desc">将保留仓库、工作分支与需求摘要；点重试继续，或取消后改需求再聊。</p>
      </div>
      <div class="cd-chosen">
        <div v-if="confirmedRepo" class="cd-chosen-row">
          <span class="cd-k">仓库</span>
          <span class="cd-v mono">{{ confirmedRepo }}</span>
        </div>
        <div v-if="confirmedRef" class="cd-chosen-row">
          <span class="cd-k">工作分支</span>
          <span class="cd-v mono">{{ confirmedRef }}</span>
        </div>
        <div v-if="confirmedRequirement" class="cd-chosen-row cd-chosen-req">
          <span class="cd-k">需求</span>
          <span class="cd-v">{{ confirmedRequirement }}</span>
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
          <!-- 完成态只由下方「合入指引」卡表达；确认卡闲置态勿再标「写码完成」 -->
          <span class="cd-badge">{{ isIdle ? '已确认' : '写码确认' }}</span>
          <span v-if="isRunning" class="cd-hint">写码进行中</span>
          <span v-else-if="isIdle" class="cd-hint">可续聊</span>
        </div>
        <p class="cd-summary">
          {{
            isIdle
              ? `本轮已按上表写入工作分支${confirmedRef ? ` ${confirmedRef}` : ''}；合入请看下方「合入指引」`
              : (card.progressText || '已确认，正在按需求写码')
          }}
        </p>
        <p v-if="isRunning" class="cd-desc">可点输入区停止按钮中止；停止后可在本卡重试，无需重选仓库。</p>
        <p v-else-if="isIdle" class="cd-desc">同窗继续发改码需求会沿用本任务与工作分支；无需重新选仓。</p>
      </div>
      <div class="cd-chosen">
        <div class="cd-chosen-row">
          <span class="cd-k">仓库</span>
          <span class="cd-v mono">{{ confirmedRepo }}</span>
        </div>
        <div v-if="confirmedRef" class="cd-chosen-row">
          <span class="cd-k">工作分支</span>
          <span class="cd-v mono">{{ confirmedRef }}</span>
        </div>
        <div v-if="confirmedRequirement" class="cd-chosen-row cd-chosen-req">
          <span class="cd-k">需求</span>
          <span class="cd-v">{{ confirmedRequirement }}</span>
        </div>
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

const props = defineProps({
  card: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['resolved'])

const busy = ref(false)
const repoInput = ref('')
const refInput = ref('')
const requirementInput = ref('')
const createPr = ref(false)
const localError = ref('')
let busyFallbackTimer = null

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
  () => props.card?.status,
  (s) => {
    if (s && s !== 'pending') clearBusy()
  },
)

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')
const isIdle = computed(() => props.card?.phase === 'idle_for_followup')
const isRunning = computed(
  () => props.card?.status === 'confirmed' && props.card?.phase === 'running',
)

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

const canConfirm = computed(
  () =>
    Boolean(normalizeRepo(repoInput.value)) &&
    Boolean(String(requirementInput.value || '').trim()) &&
    props.card?.available !== false,
)

watch(
  () => [
    props.card?.repo,
    props.card?.repos,
    props.card?.ref,
    props.card?.requirement,
    props.card?.pendingContent,
    props.card?.createPr,
  ],
  () => {
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

function onCancel() {
  if (busy.value) return
  if (!isPending.value && props.card?.status !== 'failed') return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'cancelled',
    repo: normalizeRepo(repoInput.value) || props.card?.repo || '',
    ref: String(refInput.value || props.card?.ref || '').trim(),
    requirement: String(requirementInput.value || props.card?.requirement || '').trim(),
    createPr: Boolean(createPr.value),
  })
}

function onConfirm() {
  if (busy.value || !isPending.value) return
  localError.value = ''
  const repo = normalizeRepo(repoInput.value)
  const requirement = String(requirementInput.value || '').trim()
  if (!repo) {
    localError.value = '请填写 owner/repo 或 GitHub HTTPS 地址'
    return
  }
  if (!requirement) {
    localError.value = '请填写或修改需求摘要后再确认'
    return
  }
  repoInput.value = repo
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'confirmed',
    repo,
    ref: String(refInput.value || '').trim(),
    requirement,
    createPr: Boolean(createPr.value),
  })
}

function onRetry() {
  if (busy.value || props.card?.status !== 'failed') return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'retry',
    repo: props.card?.repo || normalizeRepo(repoInput.value),
    ref: String(props.card?.ref || refInput.value || '').trim(),
    requirement: String(props.card?.requirement || requirementInput.value || '').trim(),
    createPr: Boolean(props.card?.createPr ?? createPr.value),
    jobId: props.card?.jobId || '',
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

.cd-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
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

.cd-chosen-req .cd-v {
  white-space: pre-wrap;
}</style>
