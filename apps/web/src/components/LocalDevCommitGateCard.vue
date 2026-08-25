<template>
  <div class="commit-gate" :class="statusClass">
    <div class="cg-head">
      <div class="cg-title-row">
        <span class="cg-badge">审码门禁 · 提交确认</span>
        <span class="cg-hint" v-if="isPending && !isRetryable">无阻断时可提交并推送到远程工作分支</span>
        <span class="cg-hint danger" v-if="needsPushRetry && !isPending">本地已提交，可重试推送</span>
        <span class="cg-hint danger" v-else-if="isRetryable">网络原因失败，可修复后重试</span>
      </div>
      <p class="cg-summary">{{ card.summary || '本轮写码已同步，请确认是否提交' }}</p>
    </div>

    <div class="cg-meta">
      <div class="cg-meta-item cg-meta-wide" v-if="workspace">
        <span class="cg-k">工作区</span>
        <span class="cg-v mono" :title="workspace">{{ workspace }}</span>
      </div>
      <div class="cg-meta-item" v-if="card.work_branch">
        <span class="cg-k">工作分支</span>
        <span class="cg-v mono">{{ card.work_branch }}</span>
      </div>
      <div class="cg-meta-item cg-meta-wide" v-if="remoteLabel">
        <span class="cg-k">远程</span>
        <span class="cg-v mono" :title="remoteUrl">{{ remoteLabel }}</span>
      </div>
      <div class="cg-meta-item">
        <span class="cg-k">Git</span>
        <span class="cg-v">{{ gitLabel }}</span>
      </div>
      <div class="cg-meta-item" v-if="alreadyCommitted && (card.commit || card.prior_commit)">
        <span class="cg-k">本地 commit</span>
        <span class="cg-v mono">{{ String(card.commit || card.prior_commit || '').slice(0, 12) }}</span>
      </div>
      <div class="cg-meta-item">
        <span class="cg-k">{{ needsPushRetry ? '待推送' : '本批待提交' }}</span>
        <span class="cg-v strong">{{ needsPushRetry ? '仅 push' : `${fileCount} 个` }}</span>
      </div>
      <div class="cg-meta-item" v-if="syncedPoolTotal > fileCount">
        <span class="cg-k">业务源码池</span>
        <span class="cg-v">{{ syncedPoolTotal }} 个</span>
      </div>
      <div class="cg-meta-item" v-if="excludedNonBusinessTotal > 0">
        <span class="cg-k">已排除非业务</span>
        <span class="cg-v">{{ excludedNonBusinessTotal }} 个</span>
      </div>
      <div class="cg-meta-item" v-if="card.blocking_count != null">
        <span class="cg-k">阻断</span>
        <span class="cg-v" :class="{ danger: card.blocking_count > 0 }">{{ card.blocking_count }}</span>
      </div>
      <div class="cg-meta-item" v-if="card.warning_count != null">
        <span class="cg-k">警告</span>
        <span class="cg-v">{{ card.warning_count }}</span>
      </div>
    </div>

    <div class="cg-section">
      <div class="cg-label">审核方式</div>
      <p class="cg-process">{{ reviewMethodText }}</p>
      <p class="cg-process muted" v-if="scopeNoteText">{{ scopeNoteText }}</p>
    </div>

    <div class="cg-section" v-if="processSteps.length">
      <div class="cg-label">审核过程</div>
      <ul class="cg-checks">
        <li v-for="(step, i) in processSteps" :key="i">{{ step }}</li>
      </ul>
    </div>

    <div class="cg-section">
      <div class="cg-label">审核范围与检查项</div>
      <p class="cg-process">{{ scopeLabel }}</p>
      <ul class="cg-checks" v-if="checks.length">
        <li v-for="(c, i) in checks" :key="i">{{ c }}</li>
      </ul>
      <ul class="cg-scan-list" v-if="fileScans.length">
        <li v-for="(s, i) in fileScans.slice(0, 16)" :key="i" :class="{ block: s.status === 'blocked' }">
          <span class="scan-mark">{{ s.status === 'pass' ? '✓' : '✗' }}</span>
          <span class="path mono">{{ s.path }}</span>
          <span class="scan-steps">{{ (s.steps || []).join('；') }}</span>
        </li>
      </ul>
      <p class="cg-process muted" v-else-if="!checks.length">已对本批文件做敏感路径 + 内容规则扫描</p>
    </div>

    <div class="cg-section">
      <div class="cg-label">审核结论</div>
      <p class="cg-verdict" :class="verdictClass">{{ verdictText }}</p>
      <ul class="cg-findings" v-if="findings.length">
        <li v-for="(f, i) in findings.slice(0, 12)" :key="i" :class="{ block: f.blocking || f.severity === 'P0' || f.severity === 'P1' }">
          <span class="sev">{{ f.severity || (f.blocking ? 'P0' : 'P1') }}</span>
          <span class="path mono" v-if="f.path">{{ f.path }}</span>
          <span class="msg">{{ f.message }}</span>
        </li>
      </ul>
      <div v-if="findings.length > 12" class="cg-more">…另有 {{ findings.length - 12 }} 条</div>
    </div>

    <div class="cg-section" v-if="filePreview.length">
      <button type="button" class="cg-toggle" @click="filesOpen = !filesOpen">
        {{ filesOpen ? '收起' : '展开' }}本批文件清单（{{ fileCount }}）
      </button>
      <ul v-if="filesOpen" class="cg-files">
        <li v-for="(p, i) in filePreview" :key="i" class="mono">{{ p }}</li>
        <li v-if="fileCount > filePreview.length" class="cg-more">…另有 {{ fileCount - filePreview.length }} 个</li>
      </ul>
    </div>

    <div class="cg-section" v-if="showActions && canCommit && !alreadyCommitted">
      <div class="cg-label">提交说明（必填 · 中文）</div>
      <textarea
        v-model="commitMessage"
        class="cg-textarea"
        rows="3"
        maxlength="200"
        placeholder="用中文概括本次修改，例如：将工单样例数据扩至 100 条并对齐当前日期"
        :disabled="busy"
      />
      <p class="cg-hint-line" :class="{ danger: commitMessageError }">
        {{ commitMessageError || '将作为 git commit message；须含中文，概括本次改动。' }}
      </p>
    </div>

    <div class="cg-section" v-if="showActions && canCommit && (!alreadyCommitted || isRetryable)">
      <div class="cg-label">远程仓库地址</div>
      <input
        v-model="remoteUrlInput"
        type="text"
        class="cg-input"
        placeholder="https://github.com/org/repo.git 或 git@host:path/repo.git"
        :disabled="busy"
        @keydown.enter.prevent="onCommitPush"
      />
      <label class="cg-check">
        <input v-model="saveRemote" type="checkbox" :disabled="busy || !remoteUrlInput.trim()" />
        记住为本地 origin（下次默认推这里）
      </label>
      <p class="cg-hint-line">
        与 Git 审码类似，可在此直接填地址；已有 origin 时可留空沿用，或填写覆盖本次推送。
      </p>
    </div>

    <p class="cg-foot" v-if="showActions && !isRetryable">
      <template v-if="canPushNow">将 push 到 <span class="mono">{{ pushTargetDisplay }}</span>；不合主干。</template>
      <template v-else-if="canCommit">请填写远程仓库地址，或选「仅本地提交」。</template>
      <template v-else>门禁未通过或非 git 仓，无法提交。</template>
      <span v-if="card.relaxed_from_today">（今日无记录，已放宽到该目录历史同步批）</span>
    </p>
    <p class="cg-foot cg-retry-hint" v-if="isRetryable">
      {{ retryHintText }}
    </p>

    <div class="cg-actions" v-if="showActions">
      <button type="button" class="cg-btn cancel" :disabled="busy" @click="onSkip">跳过</button>
      <button
        v-if="!alreadyCommitted"
        type="button"
        class="cg-btn secondary"
        :disabled="busy || !canCommit || !commitMessageOk"
        :title="canCommit ? (commitMessageOk ? '只在本机 git commit，不 push' : '请先填写中文提交说明') : '无法提交'"
        @click="onCommitLocal"
      >
        {{ isRetryable ? '重试本地提交' : '仅本地提交' }}
      </button>
      <button
        v-if="canPushNow || alreadyCommitted"
        type="button"
        class="cg-btn confirm"
        :class="{ 'is-loading': busy }"
        :disabled="busy || !canCommit || (!alreadyCommitted && !commitMessageOk) || (!canPushNow && !alreadyCommitted)"
        :title="pushButtonTitle"
        @click="onCommitPush"
      >
        <span v-if="busy" class="cg-spinner" aria-hidden="true" />
        {{ busy ? '处理中…' : pushPrimaryLabel }}
      </button>
    </div>
    <div class="cg-result" v-else>
      <template v-if="card.status === 'pushed'">已提交并推送到远程工作分支</template>
      <template v-else-if="card.status === 'committed'">已提交到本地工作分支（未 push）</template>
      <template v-else-if="card.status === 'push_failed'">本地已提交，推送失败：{{ card.error || '未知' }}</template>
      <template v-else-if="card.status === 'skipped'">已跳过提交（文件仍在目录）</template>
      <template v-else-if="card.status === 'superseded'">已由新一批提交请求取代</template>
      <template v-else-if="card.status === 'failed'">提交失败：{{ card.error || '未知' }}</template>
      <template v-else>{{ card.status || '已处理' }}</template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { confirmLocalDevCommit } from '../api'

const props = defineProps({
  card: { type: Object, required: true },
})
const emit = defineEmits(['resolved'])

const busy = ref(false)
const filesOpen = ref(false)
const remoteUrlInput = ref('')
const saveRemote = ref(true)
const commitMessage = ref('')

watch(
  () => props.card?.suggested_commit_message,
  (m) => {
    const s = String(m || '').trim()
    if (s && !commitMessage.value.trim()) commitMessage.value = s
  },
  { immediate: true },
)

watch(
  () => props.card?.git?.remote_url,
  (u) => {
    if (!remoteUrlInput.value && u) remoteUrlInput.value = String(u)
  },
  { immediate: true },
)

const isPending = computed(() => {
  const s = String(props.card?.status || 'pending')
  return s === 'pending' || s === 'awaiting_commit'
})

const isRetryable = computed(() => Boolean(props.card?.retryable))

const needsPushRetry = computed(
  () =>
    Boolean(props.card?.push_retry) ||
    Boolean(props.card?.push_only && props.card?.prior_commit) ||
    (Boolean(props.card?.commit) && String(props.card?.status || '') === 'push_failed'),
)

const showActions = computed(() => isPending.value || isRetryable.value || needsPushRetry.value)

const alreadyCommitted = computed(() => {
  if (Boolean(props.card?.prior_commit)) return true
  if (Boolean(props.card?.commit)) return true
  if (props.card?.push_only && props.card?.push_retry) return true
  return String(props.card?.status || '') === 'push_failed'
})

const retryHintText = computed(() => {
  const err = String(props.card?.error || '').trim()
  if (alreadyCommitted.value) {
    return (
      (err ? `推送失败：${err}。` : '推送失败。') +
      '本地已提交，修复网络后可点「重试推送」。'
    )
  }
  return (err ? `提交失败：${err}。` : '提交失败。') + '疑似网络原因，修复后可重试。'
})

const pushPrimaryLabel = computed(() => {
  if (needsPushRetry.value || (isRetryable.value && alreadyCommitted.value)) return '重试推送'
  if (isRetryable.value) return '重试提交并推送'
  if (props.card?.push_only) return '推送到远程'
  return '提交并推送远程'
})

const statusClass = computed(() => {
  if (props.card?.status === 'pushed' || props.card?.status === 'committed') return 'is-ok'
  if (props.card?.status === 'skipped' || props.card?.status === 'superseded') return 'is-skip'
  if (props.card?.status === 'failed' || props.card?.status === 'push_failed') return 'is-fail'
  if ((props.card?.blocking_count || 0) > 0) return 'is-block'
  return 'is-pending'
})

const findings = computed(() =>
  Array.isArray(props.card?.findings) ? props.card.findings : [],
)

const canCommit = computed(() => Boolean(props.card?.can_commit))

const canPush = computed(() => {
  if (props.card?.can_push != null) return Boolean(props.card.can_push)
  return Boolean(props.card?.git?.has_remote)
})

const canPushNow = computed(() => {
  if (!canCommit.value) return false
  if (String(remoteUrlInput.value || '').trim()) return true
  return canPush.value
})

const CJK_RE = /[\u4e00-\u9fff]/
const commitMessageTrimmed = computed(() => String(commitMessage.value || '').trim())
const commitMessageOk = computed(() => {
  const m = commitMessageTrimmed.value
  if (m.length < 4 || m.length > 200) return false
  if (/^wb-local-dev/i.test(m)) return false
  return CJK_RE.test(m)
})
const commitMessageError = computed(() => {
  const m = commitMessageTrimmed.value
  if (!m) return '请填写中文提交说明'
  if (m.length < 4) return '说明过短，请概括本次改了什么'
  if (!CJK_RE.test(m)) return '须含中文'
  return ''
})

const remoteName = computed(() => String(props.card?.git?.remote_name || 'origin'))
const remoteUrl = computed(() => String(props.card?.git?.remote_url || '').trim())
const remoteLabel = computed(() => {
  if (!canCommit.value) return ''
  const typed = String(remoteUrlInput.value || '').trim()
  if (typed) return typed
  if (!canPush.value) return '未配置（可在下方填写）'
  const url = remoteUrl.value
  if (url) return `${remoteName.value} · ${url}`
  return remoteName.value
})

const pushTarget = computed(() => {
  const b = String(props.card?.work_branch || '').trim() || '工作分支'
  return `${remoteName.value}/${b}`
})

const pushTargetDisplay = computed(() => {
  const typed = String(remoteUrlInput.value || '').trim()
  const b = String(props.card?.work_branch || '').trim() || '工作分支'
  if (typed) return `${typed} → ${b}`
  return pushTarget.value
})

const pushButtonTitle = computed(() => {
  if (!canCommit.value) return '门禁未通过或非 git 仓，无法提交'
  if (!alreadyCommitted.value && !commitMessageOk.value) return '请先填写中文提交说明'
  if (!canPushNow.value && !alreadyCommitted.value) return '请填写远程仓库地址，或选「仅本地提交」'
  if (isRetryable.value && alreadyCommitted.value) return '重试 push 到远程'
  return `提交并 push（不合主干）`
})

function sanitizeRemoteUrl(raw) {
  let u = String(raw || '').trim()
  if (!u) return ''
  u = u.split(/\s+/)[0].replace(/\/+$/, '')
  if (u.startsWith('git@') || u.startsWith('ssh://')) return u
  if (u.startsWith('http://') || u.startsWith('https://')) return u
  if (/^[\w.-]+\/[\w.-]+(\.git)?$/i.test(u)) return `https://github.com/${u.replace(/\.git$/i, '')}.git`
  return u
}

const workspace = computed(() => String(props.card?.workspace || '').trim())

const fileCount = computed(() => {
  const n = Array.isArray(props.card?.synced_files) ? props.card.synced_files.length : 0
  if (n) return n
  const c = Number(props.card?.files_reviewed || props.card?.file_count)
  return Number.isFinite(c) ? c : 0
})

const syncedPoolTotal = computed(() => Number(props.card?.synced_pool_total) || fileCount.value)

const excludedNonBusinessTotal = computed(
  () => Number(props.card?.excluded_non_business_total) || 0,
)

const processSteps = computed(() =>
  Array.isArray(props.card?.process_steps) ? props.card.process_steps : [],
)

const reviewMethodText = computed(
  () =>
    String(props.card?.review_method || '').trim() ||
    'ide_review 规则引擎 + 敏感路径（与审码工具同源；非 LLM Skill 全量报告）',
)

const scopeNoteText = computed(() => String(props.card?.scope_note || '').trim())

const fileScans = computed(() =>
  Array.isArray(props.card?.file_scans) ? props.card.file_scans : [],
)

const filePreview = computed(() => {
  const list = Array.isArray(props.card?.synced_files) ? props.card.synced_files : []
  return list.map((p) => String(p)).filter(Boolean).slice(0, 24)
})

const checks = computed(() => {
  if (Array.isArray(props.card?.checks) && props.card.checks.length) return props.card.checks
  return ['敏感路径（.env / 密钥文件等）→ 阻断', '内容规则：eval / SQL 拼接（P0）→ 阻断', '内容规则：硬编码口令/密钥（P1）→ 阻断']
})

const scopeLabel = computed(
  () =>
    String(props.card?.scope_label || '').trim() ||
    `WorkBuddy 同步且 Git 待提交（共 ${fileCount.value} 个，非全仓审码）`,
)

const verdictText = computed(() => {
  const v = String(props.card?.verdict || '').toLowerCase()
  if (v === 'blocked' || (props.card?.blocking_count || 0) > 0) {
    return `未通过：${props.card.blocking_count || 0} 条阻断，${props.card.warning_count || 0} 条警告`
  }
  if (v === 'warn' || (props.card?.warning_count || 0) > 0) {
    return `有条件通过：无阻断，${props.card.warning_count || 0} 条警告`
  }
  return `通过：已扫描 ${fileCount.value} 个文件，未发现阻断或警告`
})

const verdictClass = computed(() => {
  const v = String(props.card?.verdict || '').toLowerCase()
  if (v === 'blocked' || (props.card?.blocking_count || 0) > 0) return 'is-fail'
  if (v === 'warn' || (props.card?.warning_count || 0) > 0) return 'is-warn'
  return 'is-pass'
})

const gitLabel = computed(() => {
  const g = props.card?.git
  if (!g || !g.is_git) return '非 git 仓（无法提交）'
  const b = g.current_branch ? `当前 ${g.current_branch}` : '是 git 仓'
  return g.on_protected ? `${b}（主干，将切工作分支）` : b
})

async function decide(decision, { push } = {}) {
  if (busy.value || !showActions.value) return
  const jobId = props.card?.job_id
  if (!jobId) return
  if (decision === 'commit' && !alreadyCommitted.value && !commitMessageOk.value) {
    window.alert(commitMessageError.value || '请填写中文提交说明')
    return
  }
  const remote_url = sanitizeRemoteUrl(remoteUrlInput.value)
  if (push && !remote_url && !canPush.value) {
    window.alert('请填写远程仓库地址（HTTPS 或 SSH），或选择「仅本地提交」')
    return
  }
  busy.value = true
  try {
    const res = await confirmLocalDevCommit(jobId, decision, {
      push,
      remote_url: push ? remote_url : '',
      save_remote: Boolean(push && saveRemote.value && remote_url),
      commit_message:
        decision === 'commit'
          ? alreadyCommitted.value
            ? String(props.card?.last_commit_message || commitMessageTrimmed.value || props.card?.suggested_commit_message || '重试推送')
            : commitMessageTrimmed.value
          : '',
    })
    const body = res?.data && typeof res.data === 'object' ? res.data : res
    emit('resolved', { decision, push: Boolean(push), jobId, job: body })
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || String(e)
    window.alert(typeof msg === 'string' ? msg : '确认失败')
  } finally {
    busy.value = false
  }
}

function onSkip() {
  return decide('skip')
}
function onCommitLocal() {
  if (!canCommit.value) return
  return decide('commit', { push: false })
}
function onCommitPush() {
  if (!canCommit.value) return
  if (alreadyCommitted.value) {
    if (!canPushNow.value) {
      window.alert('请填写远程仓库地址')
      return
    }
    return decide('commit', { push: true })
  }
  if (!canPushNow.value) return
  return decide('commit', { push: true })
}
</script>

<style scoped>
.commit-gate {
  margin-top: 10px;
  border: 1px solid #dbe4f0;
  border-radius: 10px;
  background: #f8fafc;
  padding: 12px 14px;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
.commit-gate.is-block {
  border-color: #f0c2c2;
  background: #fff8f8;
}
.commit-gate.is-ok {
  border-color: #b7e0c0;
  background: #f3fbf5;
}
.commit-gate.is-skip {
  opacity: 0.92;
}
.cg-badge {
  font-size: 12px;
  font-weight: 600;
  color: #1e40af;
  background: #dbeafe;
  padding: 2px 8px;
  border-radius: 4px;
}
.cg-hint {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
}
.cg-summary {
  margin: 8px 0 0;
  font-size: 14px;
  color: #0f172a;
  line-height: 1.45;
}
.cg-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 10px;
  font-size: 12px;
}
.cg-meta-wide {
  flex: 1 1 100%;
  min-width: 0;
}
.cg-meta-wide .cg-v {
  word-break: break-all;
}
.cg-k {
  color: #64748b;
  margin-right: 4px;
}
.cg-v.mono,
.path.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.cg-v.strong {
  font-weight: 600;
}
.cg-v.danger {
  color: #b91c1c;
  font-weight: 600;
}
.cg-section {
  margin-top: 10px;
}
.cg-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
  font-weight: 600;
}
.cg-process {
  margin: 0 0 6px;
  font-size: 12px;
  color: #334155;
  line-height: 1.45;
}
.cg-process.muted {
  color: #64748b;
}
.cg-checks {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  color: #475569;
  line-height: 1.5;
}
.cg-scan-list {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  font-size: 12px;
  line-height: 1.45;
}
.cg-scan-list li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 8px;
  padding: 6px 8px;
  margin-bottom: 4px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e2e8f0;
}
.cg-scan-list li.block {
  border-color: #fecaca;
  background: #fff8f8;
}
.cg-scan-list .scan-mark {
  grid-row: span 2;
  font-weight: 700;
  color: #15803d;
}
.cg-scan-list li.block .scan-mark {
  color: #b91c1c;
}
.cg-scan-list .scan-steps {
  grid-column: 2;
  color: #64748b;
  font-size: 11px;
}
.cg-verdict {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
}
.cg-verdict.is-pass {
  color: #15803d;
}
.cg-verdict.is-warn {
  color: #b45309;
}
.cg-verdict.is-fail {
  color: #b91c1c;
}
.cg-toggle {
  border: none;
  background: transparent;
  padding: 0;
  font-size: 12px;
  color: #1d4ed8;
  cursor: pointer;
}
.cg-toggle:hover {
  text-decoration: underline;
}
.cg-files {
  margin: 6px 0 0;
  padding-left: 0;
  list-style: none;
  max-height: 160px;
  overflow: auto;
  font-size: 11px;
  color: #475569;
  line-height: 1.45;
}
.cg-files li {
  padding: 2px 0;
  word-break: break-all;
}
.cg-findings {
  margin: 0;
  padding-left: 0;
  list-style: none;
  font-size: 12px;
}
.cg-findings li {
  padding: 4px 0;
  border-bottom: 1px solid #eef2f7;
  line-height: 1.4;
}
.cg-findings li.block .sev {
  color: #b91c1c;
}
.sev {
  font-weight: 600;
  margin-right: 6px;
  color: #b45309;
}
.path {
  margin-right: 6px;
  color: #334155;
}
.msg {
  color: #475569;
}
.cg-more {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}
.cg-foot {
  margin: 10px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}
.cg-input {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  background: #fff;
  color: #0f172a;
}
.cg-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.cg-textarea {
  display: block;
  width: 100%;
  box-sizing: border-box;
  margin-top: 4px;
  padding: 8px 10px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.45;
  resize: vertical;
  min-height: 72px;
  background: #fff;
  color: #0f172a;
  font-family: inherit;
}
.cg-textarea:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}
.cg-check {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #475569;
  cursor: pointer;
}
.cg-hint-line {
  margin: 6px 0 0;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.4;
}
.cg-hint-line.danger {
  color: #b91c1c;
}
.cg-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: flex-end;
}
.cg-btn {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}
.cg-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.cg-btn.confirm {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}
.cg-btn.secondary {
  background: #fff;
  border-color: #94a3b8;
  color: #334155;
}
.cg-btn.secondary:hover:not(:disabled) {
  background: #f8fafc;
}
.cg-btn.cancel:hover:not(:disabled) {
  background: #f1f5f9;
}
.cg-foot .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.cg-result {
  margin-top: 10px;
  font-size: 13px;
  color: #334155;
}
.cg-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 6px;
  vertical-align: -2px;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
