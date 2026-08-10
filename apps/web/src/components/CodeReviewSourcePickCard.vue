<template>
  <div class="cr-source-pick" :class="statusClass">
    <template v-if="isPending">
      <div class="cr-head">
        <div class="cr-title-row">
          <span class="cr-badge">代码审核</span>
          <span class="cr-hint">{{ ideAvailable ? '二选一 · 确认后开始' : '填写仓库 · 确认后开始' }}</span>
        </div>
        <p class="cr-summary">{{ ideAvailable ? '选择审核来源' : '确认要审核的公开 HTTPS 仓库' }}</p>
        <p class="cr-desc">
          <template v-if="ideAvailable">
            本机 VS Code 工程（Bridge 已配对）或公开 Git HTTPS 仓库，任选其一
          </template>
          <template v-else>
            本机未配对 VS Code Bridge，仅支持公开 Git 仓库。配对后可审本机工程。
          </template>
        </p>
      </div>

      <div v-if="ideAvailable" class="cr-tabs" role="tablist">
        <button
          type="button"
          class="cr-tab"
          :class="{ active: source === 'ide' }"
          :disabled="busy"
          role="tab"
          :aria-selected="source === 'ide'"
          @click="source = 'ide'"
        >
          VS Code 本机工程
        </button>
        <button
          type="button"
          class="cr-tab"
          :class="{ active: source === 'git' }"
          :disabled="busy"
          role="tab"
          :aria-selected="source === 'git'"
          @click="source = 'git'"
        >
          Git 公开仓库
        </button>
      </div>

      <div v-if="ideAvailable && source === 'ide'" class="cr-panel">
        <div v-if="workspaces.length" class="cr-ws-list">
          <label
            v-for="w in workspaces"
            :key="w.path"
            class="cr-ws-item"
            :class="{ selected: selected === w.path }"
          >
            <input
              type="radio"
              class="cr-radio"
              name="cr-ws-pick"
              :value="w.path"
              :checked="selected === w.path"
              :disabled="busy"
              @change="selected = w.path"
            />
            <span class="cr-ws-body">
              <span class="cr-ws-name-row">
                <strong class="cr-ws-name">{{ w.name || w.path }}</strong>
                <span v-if="w.current" class="cr-ws-current">当前打开</span>
              </span>
              <span class="cr-ws-path">{{ w.path }}</span>
            </span>
          </label>
        </div>
        <div v-else class="cr-empty">
          Bridge 已连接，但暂无最近工程。请先在 VS Code 打开项目文件夹，或改选「Git 公开仓库」。
        </div>
      </div>

      <div v-if="!ideAvailable || source === 'git'" class="cr-panel">
        <div class="cr-fields">
          <label class="cr-field">
            <span class="cr-label">仓库 URL</span>
            <input
              v-model="repoUrl"
              type="url"
              class="cr-input"
              placeholder="https://github.com/org/repo"
              :disabled="busy"
              @keydown.enter.prevent="onConfirm"
            />
          </label>
          <label class="cr-field">
            <span class="cr-label">分支（可选）</span>
            <input
              v-model="refName"
              type="text"
              class="cr-input"
              placeholder="默认分支留空"
              :disabled="busy"
              @keydown.enter.prevent="onConfirm"
            />
          </label>
        </div>
        <p class="cr-note">一期仅支持公开 https:// 地址，不支持 SSH 与私有仓 Token</p>
      </div>

      <p v-if="localError" class="cr-error">{{ localError }}</p>

      <div class="cr-actions">
        <button type="button" class="cr-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button
          type="button"
          class="cr-btn confirm"
          :disabled="busy || !canConfirm"
          @click="onConfirm"
        >
          {{ busy ? '处理中…' : '开始审核' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="cr-head">
        <div class="cr-title-row">
          <span class="cr-badge">代码审核</span>
        </div>
        <p class="cr-summary">
          {{ card.source === 'ide' ? '已确认本机工程' : '已确认 Git 仓库' }}
        </p>
      </div>
      <div class="cr-chosen">
        <template v-if="card.source === 'ide'">
          <div class="cr-chosen-row">
            <span class="cr-k">来源</span>
            <span class="cr-v">VS Code 本机工程</span>
          </div>
          <div class="cr-chosen-row">
            <span class="cr-k">项目</span>
            <span class="cr-v">{{ selectedName }}</span>
          </div>
          <div class="cr-chosen-row">
            <span class="cr-k">路径</span>
            <span class="cr-v mono">{{ card.selected || selected || '—' }}</span>
          </div>
        </template>
        <template v-else>
          <div class="cr-chosen-row">
            <span class="cr-k">来源</span>
            <span class="cr-v">Git 公开仓库</span>
          </div>
          <div class="cr-chosen-row">
            <span class="cr-k">仓库</span>
            <span class="cr-v mono">{{ card.repoUrl || repoUrl || '—' }}</span>
          </div>
          <div v-if="card.ref || refName" class="cr-chosen-row">
            <span class="cr-k">分支</span>
            <span class="cr-v">{{ card.ref || refName }}</span>
          </div>
        </template>
      </div>
      <div class="cr-actions">
        <button type="button" class="cr-btn confirm" :disabled="busy" @click="onRetry">
          {{ busy ? '处理中…' : '重新开始审核' }}
        </button>
      </div>
    </template>

    <template v-else>
      <div class="cr-head">
        <div class="cr-title-row">
          <span class="cr-badge">代码审核</span>
        </div>
        <p class="cr-summary">已取消，未开始审核</p>
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

const emit = defineEmits(['resolved', 'retry'])

const busy = ref(false)
const source = ref('git')
const selected = ref('')
const repoUrl = ref('')
const refName = ref('')
const localError = ref('')

const workspaces = computed(() =>
  Array.isArray(props.card?.workspaces) ? props.card.workspaces.filter((w) => w?.path) : [],
)

/** Bridge 已配对在线才允许本机工程；未配对仅 Git */
const ideAvailable = computed(() => {
  if (props.card?.ideAvailable === false) return false
  if (props.card?.ideAvailable === true) return true
  // 兼容旧卡片：有工程列表则视为可用
  return workspaces.value.length > 0
})

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')

const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled') return 'is-cancelled'
  return 'is-pending'
})

const selectedName = computed(() => {
  const path = selected.value || props.card?.selected || ''
  const hit = workspaces.value.find((w) => w.path === path)
  if (hit?.name) return hit.name
  if (!path) return '—'
  const parts = String(path).split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] || path
})

const canConfirm = computed(() => {
  if (ideAvailable.value && source.value === 'ide') return Boolean(selected.value)
  return /^https:\/\//i.test(String(repoUrl.value || '').trim())
})

watch(
  () => [
    props.card?.source,
    props.card?.ideAvailable,
    props.card?.selected,
    props.card?.repoUrl,
    props.card?.ref,
    workspaces.value,
    ideAvailable.value,
  ],
  () => {
    if (!ideAvailable.value) {
      source.value = 'git'
    } else {
      const pref = props.card?.source
      if (pref === 'ide' || pref === 'git') {
        source.value = pref
      } else if (props.card?.repoUrl) {
        source.value = 'git'
      } else if (workspaces.value.length) {
        source.value = 'ide'
      } else {
        source.value = 'git'
      }
    }
    selected.value =
      props.card?.selected ||
      workspaces.value.find((w) => w.current)?.path ||
      workspaces.value[0]?.path ||
      ''
    repoUrl.value = props.card?.repoUrl || ''
    refName.value = props.card?.ref || ''
  },
  { immediate: true, deep: true },
)

watch(source, () => {
  localError.value = ''
})

function sanitizeRepoUrl(raw) {
  let url = String(raw || '').trim().replace(/[.,;:)+\]}>'"`]+$/g, '')
  const gitIdx = url.toLowerCase().indexOf('.git')
  if (gitIdx >= 0) {
    url = url.slice(0, gitIdx + 4)
  } else {
    const m = url.match(/^https:\/\/[A-Za-z0-9.\-]+(?:\/[A-Za-z0-9_.\-]+)+/i)
    url = m ? m[0].replace(/\/+$/, '') : url.replace(/[^\x00-\x7F].*$/, '')
  }
  return url.replace(/\/+$/, '')
}

function onCancel() {
  if (busy.value || !isPending.value) return
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'cancelled',
      source: source.value,
      selected: selected.value,
      repoUrl: String(repoUrl.value || '').trim(),
      ref: String(refName.value || '').trim(),
    })
  } finally {
    busy.value = false
  }
}

function onConfirm() {
  if (busy.value || !isPending.value) return
  localError.value = ''

  if (source.value === 'ide') {
    if (!ideAvailable.value) {
      localError.value = '本机未配对 VS Code Bridge，请改用 Git 仓库或先完成配对'
      return
    }
    if (!selected.value) {
      localError.value = '请选择要审核的本机工程，或改选 Git 仓库'
      return
    }
    busy.value = true
    try {
      emit('resolved', {
        id: props.card.id,
        status: 'confirmed',
        source: 'ide',
        selected: selected.value,
        repoUrl: '',
        ref: '',
      })
    } finally {
      busy.value = false
    }
    return
  }

  const url = sanitizeRepoUrl(repoUrl.value)
  if (!/^https:\/\//i.test(url)) {
    localError.value = '请填写公开 HTTPS 仓库地址（https://…）'
    return
  }
  if (/^https:\/\/[^/]*@/i.test(url)) {
    localError.value = '请勿在 URL 中嵌入账号或 Token'
    return
  }
  if (/[^\x00-\x7F]/.test(url)) {
    localError.value = '地址含非法字符，请只粘贴纯链接'
    return
  }
  repoUrl.value = url
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'confirmed',
      source: 'git',
      selected: '',
      repoUrl: url,
      ref: String(refName.value || '').trim(),
    })
  } finally {
    busy.value = false
  }
}

function onRetry() {
  if (busy.value || props.card?.status !== 'confirmed') return
  busy.value = true
  try {
    emit('retry')
  } finally {
    setTimeout(() => {
      busy.value = false
    }, 800)
  }
}
</script>

<style scoped>
.cr-source-pick {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  max-height: 560px;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #d5dde8;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(244, 248, 252, 0.95) 0%, #fff 48%);
  color: var(--ui-text, #1a1f26);
  box-shadow: 0 1px 0 rgba(47, 84, 140, 0.06);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.cr-source-pick.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
  max-height: none;
}

.cr-source-pick.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
  max-height: none;
}

.cr-head {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.cr-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.cr-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2f548c;
  font-weight: 700;
}

.is-confirmed .cr-badge {
  color: #2f7d4a;
}

.cr-hint {
  font-size: 12px;
  color: #5a7394;
  background: rgba(47, 84, 140, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.cr-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: #1f2630;
}

.cr-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #7a8494;
}

.cr-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.cr-tab {
  border: 1px solid #d0d7e0;
  background: #fff;
  color: #3a4250;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.cr-tab:hover:not(:disabled) {
  background: #f3f5f8;
}

.cr-tab.active {
  border-color: #2f548c;
  background: rgba(47, 84, 140, 0.08);
  color: #2f548c;
}

.cr-tab:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.cr-panel {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  margin-bottom: 4px;
}

.cr-ws-list {
  border-top: 1px solid #e6edf5;
}

.cr-ws-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 4px;
  border-bottom: 1px solid #eef2f7;
  cursor: pointer;
}

.cr-ws-item:last-child {
  border-bottom: none;
}

.cr-ws-item.selected {
  background: rgba(47, 84, 140, 0.04);
}

.cr-radio {
  margin-top: 4px;
  flex-shrink: 0;
  accent-color: #2f548c;
}

.cr-ws-body {
  display: block;
  min-width: 0;
  line-height: 1.4;
}

.cr-ws-name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.cr-ws-name {
  font-size: 14px;
  color: #1f2630;
}

.cr-ws-current {
  font-size: 12px;
  font-weight: 500;
  color: #2f7d4a;
}

.cr-ws-path {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #7a8494;
  word-break: break-all;
}

.cr-empty {
  padding: 14px 4px;
  font-size: 13px;
  line-height: 1.5;
  color: #7a8494;
}

.cr-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cr-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.cr-label {
  font-size: 12px;
  color: #6b7c8f;
}

.cr-input {
  border: 1px solid #d0d7e0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: #1f2630;
  background: #fff;
  outline: none;
}

.cr-input:focus {
  border-color: #2f548c;
  box-shadow: 0 0 0 2px rgba(47, 84, 140, 0.12);
}

.cr-note {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #7a8494;
}

.cr-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b42318;
  flex-shrink: 0;
}

.cr-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid #dde5ef;
}

.cr-btn {
  border: 1px solid transparent;
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: #fff;
  border-radius: 8px;
  min-width: 96px;
  transition: background 0.15s, border-color 0.15s;
}

.cr-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.cr-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
  background: #fff;
}

.cr-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
}

.cr-btn.confirm {
  background: #2f548c;
  color: #fff !important;
  border-color: #2f548c;
}

.cr-btn.confirm:hover:not(:disabled) {
  background: #254572;
}

.cr-chosen {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 2px;
}

.cr-chosen-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #d7e8dc;
  border-radius: 8px;
}

.cr-k {
  font-size: 12px;
  color: #6b7c6f;
  line-height: 1.5;
  padding-top: 1px;
}

.cr-v {
  font-size: 13px;
  font-weight: 600;
  color: #1f2630;
  line-height: 1.5;
  word-break: break-all;
}

.cr-v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
  color: #3a4250;
}
</style>
