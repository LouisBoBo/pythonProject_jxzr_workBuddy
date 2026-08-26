<template>
  <div class="deploy-gate" :class="statusClass">
    <div class="dg-status-bar" :data-st="status">
      <span class="dg-status-dot" aria-hidden="true"></span>
      <strong class="dg-status-title">{{ statusTitle }}</strong>
      <span class="dg-badge">{{ badgeText }}</span>
    </div>

    <p class="dg-summary" v-if="isPending">{{ card.summary || defaultSummary }}</p>
    <p class="dg-summary" v-else-if="currentStep && !isSucceeded">{{ currentStep }}</p>

    <div class="dg-meta">
      <div class="dg-meta-item">
        <span class="dg-k">环境</span>
        <span class="dg-v strong">{{ displayEnv }}</span>
      </div>
      <div class="dg-meta-item" v-if="isLocalSsh && card.ssh_host">
        <span class="dg-k">主机</span>
        <span class="dg-v mono">{{ card.ssh_host }}</span>
      </div>
      <div class="dg-meta-item" v-if="isLocalSsh && card.local_project_path">
        <span class="dg-k">本机项目</span>
        <span class="dg-v mono">{{ card.local_project_path }}</span>
      </div>
      <div class="dg-meta-item" v-if="!isLocalSsh && card.github_repo">
        <span class="dg-k">仓库</span>
        <span class="dg-v mono">{{ card.github_repo }}</span>
      </div>
      <div class="dg-meta-item" v-if="!isLocalSsh && card.github_workflow">
        <span class="dg-k">Workflow</span>
        <span class="dg-v mono">{{ card.github_workflow }}</span>
      </div>
      <div class="dg-meta-item" v-if="localRunId || card.run_id">
        <span class="dg-k">任务</span>
        <span class="dg-v mono">{{ localRunId || card.run_id }}</span>
      </div>
    </div>

    <div class="dg-section" v-if="isPending">
      <div class="dg-label">Git ref（{{ isLocalSsh ? '本机存在的分支 / tag' : '已推送的分支 / tag' }}）</div>
      <input
        v-model="refInput"
        class="dg-input"
        maxlength="120"
        placeholder="例如 main 或 release-1.0"
        :disabled="busy"
      />
      <p class="dg-hint-line" :class="{ danger: !refInput.trim() }">
        {{
          refInput.trim()
            ? isLocalSsh
              ? '将用临时 worktree 检出该 ref 后本机构建并 SSH 同步'
              : '将对该 ref 触发 workflow_dispatch'
            : isLocalSsh
              ? '必填：本机 git 仓库中已存在的分支或 tag'
              : '必填：须是远程已存在的分支或 tag'
        }}
      </p>
    </div>

    <div class="dg-section" v-if="checks.length && isPending">
      <div class="dg-label">门禁检查</div>
      <ul class="dg-checks">
        <li v-for="(c, i) in checks" :key="i" :class="{ bad: c.ok === false }">
          {{ c.ok === false ? '✗' : '✓' }} {{ c.detail || c.id }}
        </li>
      </ul>
    </div>

    <div class="dg-section" v-if="logLines.length && (isPolling || isTerminal)">
      <div class="dg-label">部署过程</div>
      <ol class="dg-steps">
        <li
          v-for="(line, i) in logLines"
          :key="i"
          :class="{
            current: i === logLines.length - 1 && isPolling,
            done: i < logLines.length - 1 || isSucceeded,
            bad: isFailed && i === logLines.length - 1,
          }"
        >
          <span class="dg-step-mark" aria-hidden="true"></span>
          <span>{{ line }}</span>
        </li>
      </ol>
    </div>

    <div class="dg-section" v-if="!isLocalSsh && (runUrl || actionsUrl)">
      <div class="dg-label">流水线</div>
      <p class="dg-link" v-if="runUrl">
        <a :href="runUrl" target="_blank" rel="noopener noreferrer">打开本次 run</a>
      </p>
      <p class="dg-link" v-else-if="actionsUrl">
        <a :href="actionsUrl" target="_blank" rel="noopener noreferrer">打开 Actions 列表</a>
      </p>
    </div>

    <div class="dg-visit" v-if="isSucceeded && visitUrl">
      <div class="dg-visit-label">部署成功 · 项目访问地址</div>
      <a class="dg-visit-link" :href="visitUrl" target="_blank" rel="noopener noreferrer">{{
        visitUrl
      }}</a>
      <p class="dg-hint-line" v-if="healthLabel">{{ healthLabel }}</p>
    </div>
    <div class="dg-visit muted" v-else-if="isSucceeded && !visitUrl">
      <div class="dg-visit-label">部署成功</div>
      <p class="dg-hint-line">未配置 DEPLOY_HEALTH_URL，无访问地址可展示。</p>
    </div>

    <p class="dg-error" v-if="errorText">{{ errorText }}</p>

    <p class="dg-foot" v-if="isPending">
      {{
        isLocalSsh
          ? '确认后由 API 本机构建并 rsync，不经模型。'
          : '确认后由 API 触发 GitHub Actions，不经模型。'
      }}
    </p>

    <div class="dg-actions" v-if="isPending">
      <button type="button" class="dg-btn ghost" :disabled="busy" @click="onCancel">取消</button>
      <button
        type="button"
        class="dg-btn primary"
        :disabled="busy || !canConfirm"
        @click="onConfirm"
      >
        {{ busy ? '触发中…' : confirmBtnLabel }}
      </button>
    </div>
    <div class="dg-actions" v-else-if="isPolling || status === 'unreachable'">
      <button type="button" class="dg-btn ghost" :disabled="busy" @click="pollOnce">
        {{ busy ? '查询中…' : '刷新状态' }}
      </button>
    </div>
    <p class="dg-done" v-else-if="status === 'cancelled'">已取消，未触发发布。</p>
    <p class="dg-done danger" v-else-if="isFailed">
      {{
        status === 'ci_failed'
          ? isLocalSsh
            ? '本机 SSH 部署失败。'
            : '流水线失败（未改本地代码）。'
          : '触发失败，未改本地代码。'
      }}
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { confirmLocalDevDeploy, pollLocalDevDeploy } from '../api.js'

const props = defineProps({
  card: { type: Object, required: true },
})
const emit = defineEmits(['resolved', 'poll'])

const busy = ref(false)
const localError = ref('')
const pollMsg = ref('')
const localStatus = ref('')
const localRunUrl = ref('')
const localRunId = ref('')
const localLogTail = ref('')
const localVisitUrl = ref('')
const refInput = ref(String(props.card?.ref || props.card?.suggested_ref || ''))
let timer = null
let startedAt = 0
const POLL_MS_LOCAL = 2000
const POLL_MS_CI = 4000
const DEFAULT_TIMEOUT_MS = 30 * 60 * 1000

watch(
  () => [props.card?.ref, props.card?.suggested_ref],
  ([a, b]) => {
    if (!refInput.value) refInput.value = String(a || b || '')
  },
)

const status = computed(() => localStatus.value || String(props.card?.status || 'pending'))
const isPending = computed(() => status.value === 'pending' || status.value === 'awaiting_deploy')
const isPolling = computed(() =>
  ['triggered', 'queued', 'in_progress', 'unreachable'].includes(status.value),
)
const isSucceeded = computed(() => status.value === 'succeeded')
const isFailed = computed(() => status.value === 'failed' || status.value === 'ci_failed')
const isTerminal = computed(
  () => isSucceeded.value || isFailed.value || status.value === 'cancelled',
)
const statusClass = computed(() => `st-${status.value}`)
const displayEnv = computed(() =>
  String(props.card?.env_label || props.card?.env || 'staging'),
)
const defaultSummary = computed(() => `请确认是否部署到 ${displayEnv.value}`)
const checks = computed(() => (Array.isArray(props.card?.checks) ? props.card.checks : []))
const isLocalSsh = computed(() => {
  const p = String(props.card?.ci_provider || props.card?.ci?.provider || '')
  if (p === 'local_ssh') return true
  const rid = String(localRunId.value || props.card?.run_id || props.card?.ci?.run_id || '')
  if (rid.startsWith('local-')) return true
  const msg = String(pollMsg.value || props.card?.poll_message || props.card?.summary || '')
  return msg.includes('本机 SSH')
})
const badgeText = computed(() => (isLocalSsh.value ? '本机 SSH' : 'GitHub Actions'))
const statusTitle = computed(() => {
  const map = {
    pending: '待确认',
    awaiting_deploy: '待确认',
    triggered: '已启动',
    queued: '排队中',
    in_progress: '部署进行中',
    succeeded: '部署成功',
    failed: '触发失败',
    ci_failed: '部署失败',
    cancelled: '已取消',
    unreachable: '状态暂不可达',
  }
  return map[status.value] || status.value
})
const runUrl = computed(
  () => localRunUrl.value || String(props.card?.run_url || props.card?.ci?.run_url || ''),
)
const actionsUrl = computed(() => String(props.card?.actions_url || props.card?.ci?.actions_url || ''))
const errorText = computed(() => localError.value || String(props.card?.error || ''))
const currentStep = computed(() => pollMsg.value || String(props.card?.poll_message || ''))
const logLines = computed(() => {
  const raw = localLogTail.value || String(props.card?.log_tail || '')
  return raw
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(-20)
})
const visitUrl = computed(() => {
  const fromPoll = String(localVisitUrl.value || '').trim()
  if (fromPoll) return fromPoll
  const fromCard = String(
    props.card?.visit_url || props.card?.health_url || props.card?.ci?.visit_url || '',
  ).trim()
  return fromCard
})
const healthLabel = computed(() => {
  const detail = String(props.card?.health_detail || '').trim()
  if (props.card?.health_ok === true) return detail || '探活通过'
  if (props.card?.health_ok === false) return detail || '探活失败'
  return ''
})
const canConfirm = computed(
  () => Boolean(props.card?.can_trigger_ci) && Boolean(refInput.value.trim()) && isPending.value,
)
const confirmBtnLabel = computed(() => {
  const env = String(props.card?.env || displayEnv.value || '').trim()
  const label = String(props.card?.env_label || displayEnv.value || env).trim()
  if (env === 'production' || env === 'prod') return '确认部署到生产'
  if (label) return `确认部署到 ${label}`
  return '确认部署'
})

function stopPoll() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function pollOnce() {
  if (busy.value) return
  const repo = String(props.card?.github_repo || '')
  const workflow = String(props.card?.github_workflow || '')
  const runId = localRunId.value || String(props.card?.run_id || props.card?.ci?.run_id || '')
  const ref = String(props.card?.ref || refInput.value || '')
  if (isLocalSsh.value) {
    if (!runId) return
  } else if (!repo && !runId) {
    return
  }
  busy.value = true
  try {
    const res = await pollLocalDevDeploy({
      repo,
      run_id: runId,
      workflow,
      ref,
    })
    const data = res?.data && typeof res.data === 'object' ? res.data : res
    if (data?.run_id) localRunId.value = String(data.run_id)
    if (data?.run_url) localRunUrl.value = String(data.run_url)
    if (data?.log_tail) localLogTail.value = String(data.log_tail)
    if (data?.visit_url || data?.health_url) {
      localVisitUrl.value = String(data.visit_url || data.health_url || '')
    }
    pollMsg.value = String(data?.message || '')
    if (data?.unreachable || (data?.ok === false && data?.unreachable)) {
      localStatus.value = 'unreachable'
      localError.value = String(data?.message || data?.error || '暂时不可达')
      emit('poll', { ...data, status: 'unreachable' })
      return
    }
    if (!data?.ok) {
      localError.value = String(data?.error || '查询失败')
      pollMsg.value = localError.value
      emit('poll', data)
      return
    }
    localError.value = ''
    if (data.success) {
      localStatus.value = 'succeeded'
      stopPoll()
      emit('poll', {
        ...data,
        status: 'succeeded',
        health_ok: data.health_ok,
        health_url: data.health_url,
        health_detail: data.health_detail,
        visit_url: data.visit_url || data.health_url,
        log_tail: data.log_tail,
      })
      return
    }
    if (data.failed || (data.done && !data.success)) {
      localStatus.value = 'ci_failed'
      stopPoll()
      emit('poll', {
        ...data,
        status: 'ci_failed',
        health_ok: data.health_ok,
        health_url: data.health_url,
        health_detail: data.health_detail,
        visit_url: data.visit_url || data.health_url,
        log_tail: data.log_tail,
      })
      return
    }
    const st = String(data.status || 'in_progress')
    localStatus.value = st === 'queued' ? 'queued' : 'in_progress'
    emit('poll', {
      ...data,
      status: localStatus.value,
      log_tail: data.log_tail,
    })
  } catch (e) {
    localStatus.value = 'unreachable'
    localError.value = e?.message || String(e)
    pollMsg.value = '暂时无法查询（可点「刷新状态」重试）'
  } finally {
    busy.value = false
    const timeoutMs = Number(props.card?.poll_timeout_sec || 1800) * 1000 || DEFAULT_TIMEOUT_MS
    if (startedAt && Date.now() - startedAt > timeoutMs) {
      stopPoll()
      pollMsg.value = isLocalSsh.value
        ? '查询超时，请查看本机 API 日志或稍后刷新'
        : '查询超时，请打开 Actions 链接查看或稍后刷新'
      localStatus.value = 'unreachable'
    }
  }
}

function startPoll() {
  stopPoll()
  startedAt = Date.now()
  void pollOnce()
  const ms = isLocalSsh.value ? POLL_MS_LOCAL : POLL_MS_CI
  timer = setInterval(() => {
    void pollOnce()
  }, ms)
}

watch(
  () => props.card?.status,
  (st) => {
    if (st === 'triggered' || st === 'queued' || st === 'in_progress') {
      if (!localStatus.value || localStatus.value === 'pending') {
        localStatus.value = String(st)
      }
      if (!timer) startPoll()
    }
  },
  { immediate: true },
)

onMounted(() => {
  const st = String(props.card?.status || '')
  if (['triggered', 'queued', 'in_progress'].includes(st)) startPoll()
  if (st === 'succeeded' || st === 'ci_failed') {
    pollMsg.value = String(props.card?.poll_message || props.card?.ci?.message || '')
    if (props.card?.run_id) localRunId.value = String(props.card.run_id)
    if (props.card?.log_tail) localLogTail.value = String(props.card.log_tail)
    if (props.card?.visit_url || props.card?.health_url) {
      localVisitUrl.value = String(props.card.visit_url || props.card.health_url)
    }
  }
})

onBeforeUnmount(stopPoll)

async function onCancel() {
  if (busy.value) return
  busy.value = true
  localError.value = ''
  try {
    const res = await confirmLocalDevDeploy({
      decision: 'cancel',
      env: displayEnv.value,
      ref: refInput.value.trim(),
      message: props.card?.message || '',
    })
    const data = res?.data && typeof res.data === 'object' ? res.data : res
    stopPoll()
    localStatus.value = 'cancelled'
    emit('resolved', { decision: 'cancel', result: data })
  } catch (e) {
    localError.value = e?.message || String(e)
  } finally {
    busy.value = false
  }
}

async function onConfirm() {
  if (busy.value || !canConfirm.value) return
  busy.value = true
  localError.value = ''
  try {
    const res = await confirmLocalDevDeploy({
      decision: 'confirm',
      env: displayEnv.value,
      ref: refInput.value.trim(),
      message: props.card?.message || '',
    })
    const data = res?.data && typeof res.data === 'object' ? res.data : res
    const ci = data?.ci && typeof data.ci === 'object' ? data.ci : {}
    if (ci.run_id) localRunId.value = String(ci.run_id)
    if (ci.run_url) localRunUrl.value = String(ci.run_url)
    if (data?.ok && data?.status === 'triggered') {
      localStatus.value = 'triggered'
      emit('resolved', { decision: 'confirm', result: data })
      startPoll()
    } else {
      localStatus.value = 'failed'
      emit('resolved', {
        decision: 'confirm',
        result: { ok: false, status: 'failed', error: data?.error || '触发失败', ...data },
      })
    }
  } catch (e) {
    localError.value = e?.message || String(e)
    localStatus.value = 'failed'
    emit('resolved', {
      decision: 'confirm',
      result: { ok: false, status: 'failed', error: localError.value },
    })
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.deploy-gate {
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid #d8dee6;
  border-radius: 10px;
  background: #f8fafc;
  color: #1e293b;
}
.deploy-gate.st-triggered,
.deploy-gate.st-queued,
.deploy-gate.st-in_progress {
  border-color: #93c5fd;
  background: #eff6ff;
}
.deploy-gate.st-succeeded {
  border-color: #86efac;
  background: #f0fdf4;
}
.deploy-gate.st-failed,
.deploy-gate.st-ci_failed,
.deploy-gate.st-unreachable {
  border-color: #fca5a5;
  background: #fef2f2;
}
.dg-badge {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  color: #0f766e;
  background: #ccfbf1;
  padding: 2px 8px;
  border-radius: 4px;
}
.dg-status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}
.dg-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}
.dg-status-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.st-pending .dg-status-bar,
.st-awaiting_deploy .dg-status-bar {
  background: #f8fafc;
}
.st-triggered .dg-status-bar,
.st-queued .dg-status-bar,
.st-in_progress .dg-status-bar {
  background: #ecfeff;
  border-color: #a5f3fc;
}
.st-triggered .dg-status-dot,
.st-queued .dg-status-dot,
.st-in_progress .dg-status-dot {
  background: #0891b2;
  box-shadow: 0 0 0 3px rgba(8, 145, 178, 0.25);
  animation: dg-pulse 1.2s ease-in-out infinite;
}
.st-succeeded .dg-status-bar {
  background: #dcfce7;
  border-color: #86efac;
}
.st-succeeded .dg-status-dot {
  background: #16a34a;
}
.st-succeeded .dg-status-title {
  color: #14532d;
  font-size: 16px;
}
.st-failed .dg-status-bar,
.st-ci_failed .dg-status-bar,
.st-unreachable .dg-status-bar {
  background: #fef2f2;
  border-color: #fecaca;
}
.st-failed .dg-status-dot,
.st-ci_failed .dg-status-dot,
.st-unreachable .dg-status-dot {
  background: #dc2626;
}
@keyframes dg-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.45;
  }
}
.dg-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.dg-steps li {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 13px;
  color: #475569;
  line-height: 1.4;
}
.dg-steps li.done {
  color: #166534;
}
.dg-steps li.current {
  color: #0e7490;
  font-weight: 600;
}
.dg-steps li.bad {
  color: #b91c1c;
}
.dg-step-mark {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
}
.dg-steps li.done .dg-step-mark {
  background: #22c55e;
}
.dg-steps li.current .dg-step-mark {
  background: #06b6d4;
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.2);
}
.dg-steps li.bad .dg-step-mark {
  background: #ef4444;
}
.dg-visit {
  margin-top: 14px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #ecfdf5;
  border: 1px solid #6ee7b7;
}
.dg-visit.muted {
  background: #f8fafc;
  border-color: #e2e8f0;
}
.dg-visit-label {
  font-size: 13px;
  font-weight: 700;
  color: #14532d;
  margin-bottom: 6px;
}
.dg-visit-link {
  display: inline-block;
  font-size: 15px;
  font-weight: 600;
  color: #047857;
  word-break: break-all;
  text-decoration: underline;
}
.dg-visit-link:hover {
  color: #065f46;
}
.dg-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
}
.dg-summary {
  margin: 10px 0 0;
  font-size: 14px;
  line-height: 1.5;
}
.dg-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin-top: 12px;
}
.dg-meta-item {
  display: flex;
  gap: 6px;
  font-size: 13px;
}
.dg-k {
  color: #64748b;
}
.dg-v.mono,
.dg-hint-line.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.dg-v.strong {
  font-weight: 600;
}
.dg-v.danger {
  color: #b91c1c;
}
.dg-v.ok {
  color: #166534;
}
.dg-section {
  margin-top: 12px;
}
.dg-label {
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  margin-bottom: 6px;
}
.dg-input {
  width: 100%;
  box-sizing: border-box;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
}
.dg-hint-line {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}
.dg-hint-line.danger {
  color: #b91c1c;
}
.dg-checks {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #334155;
}
.dg-checks .bad {
  color: #b91c1c;
}
.dg-link a {
  color: #0f766e;
  font-size: 13px;
}
.dg-error {
  margin-top: 10px;
  color: #b91c1c;
  font-size: 13px;
}
.dg-foot {
  margin-top: 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}
.dg-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 14px;
}
.dg-btn {
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid #cbd5e1;
  background: #fff;
}
.dg-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.dg-btn.primary {
  background: #0f766e;
  border-color: #0f766e;
  color: #fff;
}
.dg-btn.ghost {
  background: #fff;
}
.dg-done {
  margin-top: 12px;
  font-size: 13px;
  color: #166534;
}
.dg-done.danger {
  color: #b91c1c;
}
</style>
