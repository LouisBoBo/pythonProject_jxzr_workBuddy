<template>
  <div class="cursor-dev-anchor" :class="statusClass">
    <template v-if="isPending">
      <div class="cda-head">
        <div class="cda-title-row">
          <span class="cda-badge">先选目标</span>
          <span class="cda-hint">新对话先定点，再谈需求</span>
        </div>
        <p class="cda-summary">请选择本次写码落盘位置</p>
        <p class="cda-desc">
          默认本机目录（沙箱改码后同步）。也可改走 GitHub 远程仓。
        </p>
      </div>

      <div class="cda-tabs" role="tablist">
        <button
          type="button"
          class="cda-tab"
          :class="{ active: targetTab === 'local' }"
          :disabled="busy"
          @click="targetTab = 'local'"
        >
          本地目录
        </button>
        <button
          type="button"
          class="cda-tab"
          :class="{ active: targetTab === 'github' }"
          :disabled="busy"
          @click="targetTab = 'github'"
        >
          GitHub
        </button>
      </div>

      <div class="cda-mode">
        <label class="cda-radio">
          <input v-model="mode" type="radio" value="existing" :disabled="busy" />
          <span>{{ targetTab === 'local' ? '已有工程（改本机目录）' : '已有项目（读仓衔接）' }}</span>
        </label>
        <label class="cda-radio">
          <input v-model="mode" type="radio" value="new" :disabled="busy" />
          <span>{{ targetTab === 'local' ? '新项目（空目录从零生成）' : '新项目（从头收集）' }}</span>
        </label>
      </div>

      <template v-if="targetTab === 'local'">
        <label class="cda-field">
          <span class="cda-label">本机工程目录</span>
          <div class="cda-path-row">
            <input
              v-model="workspaceInput"
              type="text"
              class="cda-input"
              placeholder="例如 /Users/你/Projects/my-app"
              :disabled="busy || picking"
            />
            <button
              type="button"
              class="cda-btn browse"
              :disabled="busy || picking"
              @click="onBrowseFolder"
            >
              {{ picking ? '选择中…' : '浏览…' }}
            </button>
          </div>
        </label>
        <p v-if="lastWorkspace" class="cda-suggest">
          上次：
          <button
            type="button"
            class="cda-chip"
            :disabled="busy"
            @click="workspaceInput = lastWorkspace"
          >
            {{ lastWorkspace }}
          </button>
        </p>
      </template>

      <template v-else>
        <label class="cda-field">
          <span class="cda-label">代码仓库</span>
          <input
            v-model="repoInput"
            type="text"
            class="cda-input"
            placeholder="owner/repo 或 https://github.com/…"
            :disabled="busy"
          />
        </label>
        <p v-if="suggestions.length" class="cda-suggest">
          常用：
          <button
            v-for="s in suggestions"
            :key="s"
            type="button"
            class="cda-chip"
            :disabled="busy"
            @click="repoInput = s"
          >
            {{ s }}
          </button>
        </p>
      </template>

      <p v-if="localError" class="cda-error">{{ localError }}</p>

      <div class="cda-actions">
        <button type="button" class="cda-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button
          type="button"
          class="cda-btn confirm"
          :class="{ 'is-loading': busy }"
          :disabled="busy || !canConfirm"
          @click="onConfirm"
        >
          <span v-if="busy" class="cda-spinner" aria-hidden="true" />
          {{ confirmLabel }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="cda-head">
        <span class="cda-badge">先选目标</span>
        <p class="cda-summary">
          已选 {{ confirmedModeLabel }}：
          <span class="mono">{{ confirmedDisplay }}</span>
        </p>
      </div>
    </template>

    <template v-else>
      <div class="cda-head">
        <span class="cda-badge">先选目标</span>
        <p class="cda-summary">已取消。可重新说明开发需求后再选目录或仓库。</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { pickLocalDevFolder, checkLocalDevWorkspace } from '../api.js'

const props = defineProps({
  card: { type: Object, required: true },
})
const emit = defineEmits(['resolved'])

const busy = ref(false)
const picking = ref(false)
const targetTab = ref('local')
const repoInput = ref('')
const workspaceInput = ref('')
const lastWorkspace = ref('')
const mode = ref('existing')
const localError = ref('')
let busyFallbackTimer = null

function armBusy() {
  busy.value = true
  if (busyFallbackTimer != null) clearTimeout(busyFallbackTimer)
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
const suggestions = computed(() =>
  Array.isArray(props.card?.repos) ? props.card.repos.filter(Boolean) : [],
)
const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled') return 'is-cancelled'
  return 'is-pending'
})
const confirmedDisplay = computed(() => {
  if (props.card?.target === 'local' || props.card?.workspace) {
    return props.card?.workspace || ''
  }
  return props.card?.repo || ''
})
const confirmedModeLabel = computed(() => {
  const t = props.card?.target === 'github' ? 'GitHub' : '本机'
  const m = props.card?.projectMode === 'new' ? '新项目' : '已有工程'
  return `${t} · ${m}`
})
const canConfirm = computed(() => {
  if (targetTab.value === 'local') {
    return Boolean(String(workspaceInput.value || '').trim())
  }
  return Boolean(normalizeRepo(repoInput.value))
})
const confirmLabel = computed(() => {
  if (busy.value) return '处理中…'
  if (targetTab.value === 'local') {
    return mode.value === 'new' ? '确认本机目录并收集需求' : '确认本机目录'
  }
  return mode.value === 'existing' ? '选仓并读取项目' : '选仓并开始收集需求'
})

watch(
  () => [
    props.card?.repo,
    props.card?.repos,
    props.card?.projectMode,
    props.card?.target,
    props.card?.workspace,
    props.card?.lastWorkspace,
  ],
  () => {
    const t = String(props.card?.target || 'local').toLowerCase()
    targetTab.value = t === 'github' ? 'github' : 'local'
    if (props.card?.repo) repoInput.value = props.card.repo
    else if (!repoInput.value && suggestions.value.length) repoInput.value = suggestions.value[0]
    const ws = props.card?.workspace || props.card?.lastWorkspace || ''
    if (ws) workspaceInput.value = String(ws)
    lastWorkspace.value = String(props.card?.lastWorkspace || ws || '')
    if (props.card?.projectMode === 'new' || props.card?.projectMode === 'existing') {
      mode.value = props.card.projectMode
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

function onCancel() {
  if (busy.value || !isPending.value) return
  armBusy()
  emit('resolved', { id: props.card.id, status: 'cancelled' })
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

async function onConfirm() {
  if (busy.value || !isPending.value) return
  localError.value = ''
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
      projectMode: mode.value === 'new' ? 'new' : 'existing',
      pendingContent: props.card?.pendingContent || '',
      pendingFiles: Array.isArray(props.card?.pendingFiles) ? [...props.card.pendingFiles] : [],
    })
    return
  }
  const repo = normalizeRepo(repoInput.value)
  if (!repo) {
    localError.value = '请填写 owner/repo'
    return
  }
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'confirmed',
    target: 'github',
    workspace: '',
    repo,
    projectMode: mode.value === 'new' ? 'new' : 'existing',
    pendingContent: props.card?.pendingContent || '',
    pendingFiles: Array.isArray(props.card?.pendingFiles) ? [...props.card.pendingFiles] : [],
  })
}
</script>

<style scoped>
.cursor-dev-anchor {
  align-self: stretch;
  width: 100%;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #d5dde8;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(244, 248, 252, 0.95) 0%, #fff 48%);
}
.cursor-dev-anchor.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
}
.cursor-dev-anchor.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
}
.cda-title-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}
.cda-badge {
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2f548c;
  font-weight: 700;
}
.cda-hint {
  font-size: 12px;
  color: #5a7394;
  background: rgba(47, 84, 140, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
}
.cda-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1f2630;
}
.cda-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a8494;
  line-height: 1.5;
}
.cda-tabs {
  display: flex;
  gap: 6px;
  margin: 10px 0 8px;
}
.cda-tab {
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
.cda-tab.active {
  border-color: #2f548c;
  color: #2f548c;
  background: rgba(47, 84, 140, 0.08);
}
.cda-tab:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.cda-mode {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 10px 0;
}
.cda-radio {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #3a4250;
}
.cda-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cda-path-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}
.cda-path-row .cda-input {
  flex: 1;
  min-width: 0;
}
.cda-label {
  font-size: 12px;
  color: #6b7c8f;
}
.cda-input {
  border: 1px solid #d0d7e0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}
.cda-suggest {
  margin: 8px 0 0;
  font-size: 12px;
  color: #6b7c8f;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.cda-chip {
  border: 1px solid #d0d7e0;
  background: #f8fafc;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
}
.cda-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b42318;
}
.cda-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #dde5ef;
}
.cda-btn {
  border: 1px solid transparent;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 8px;
  cursor: pointer;
  background: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.cda-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
}
.cda-btn.browse {
  border-color: #d0d7e0;
  color: #2f548c;
  background: #fff;
  padding: 8px 12px;
  white-space: nowrap;
  flex-shrink: 0;
}
.cda-btn.confirm {
  background: #2f548c;
  color: #fff;
  border-color: #2f548c;
}
.cda-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}
.cda-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: cda-spin 0.7s linear infinite;
  flex-shrink: 0;
}
@keyframes cda-spin {
  to {
    transform: rotate(360deg);
  }
}
.mono {
  font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}
</style>
