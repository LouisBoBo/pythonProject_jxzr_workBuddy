<template>
  <div class="git-repo-pick" :class="statusClass">
    <template v-if="isPending">
      <div class="gp-head">
        <div class="gp-title-row">
          <span class="gp-badge">Git 仓库</span>
          <span class="gp-hint">确认后开始审核</span>
        </div>
        <p class="gp-summary">确认要审核的公开 HTTPS 仓库</p>
        <p class="gp-desc">一期仅支持公开 https:// 地址，不支持 SSH 与私有仓 Token</p>
      </div>

      <div class="gp-fields">
        <label class="gp-field">
          <span class="gp-label">仓库 URL</span>
          <input
            v-model="repoUrl"
            type="url"
            class="gp-input"
            placeholder="https://github.com/org/repo"
            :disabled="busy"
            @keydown.enter.prevent="onConfirm"
          />
        </label>
        <label class="gp-field">
          <span class="gp-label">分支（可选）</span>
          <input
            v-model="refName"
            type="text"
            class="gp-input"
            placeholder="默认分支留空"
            :disabled="busy"
            @keydown.enter.prevent="onConfirm"
          />
        </label>
      </div>
      <p v-if="localError" class="gp-error">{{ localError }}</p>

      <div class="gp-actions">
        <button type="button" class="gp-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button
          type="button"
          class="gp-btn confirm"
          :disabled="busy || !canConfirm"
          @click="onConfirm"
        >
          {{ busy ? '处理中…' : '开始审核' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="gp-head">
        <div class="gp-title-row">
          <span class="gp-badge">Git 仓库</span>
        </div>
        <p class="gp-summary">已确认审核仓库</p>
      </div>
      <div class="gp-chosen">
        <div class="gp-chosen-row">
          <span class="gp-k">仓库</span>
          <span class="gp-v mono">{{ confirmedUrl }}</span>
        </div>
        <div v-if="confirmedRef" class="gp-chosen-row">
          <span class="gp-k">分支</span>
          <span class="gp-v">{{ confirmedRef }}</span>
        </div>
      </div>
      <div class="gp-actions">
        <button type="button" class="gp-btn confirm" :disabled="busy" @click="onRetry">
          {{ busy ? '处理中…' : '重新开始审核' }}
        </button>
      </div>
    </template>

    <template v-else>
      <div class="gp-head">
        <div class="gp-title-row">
          <span class="gp-badge">Git 仓库</span>
        </div>
        <p class="gp-summary">已取消，未开始审核</p>
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
const repoUrl = ref('')
const refName = ref('')
const localError = ref('')

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')

const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled') return 'is-cancelled'
  return 'is-pending'
})

const confirmedUrl = computed(() => props.card?.repoUrl || repoUrl.value || '')
const confirmedRef = computed(() => props.card?.ref || refName.value || '')

const canConfirm = computed(() => {
  const u = String(repoUrl.value || '').trim()
  return /^https:\/\//i.test(u)
})

watch(
  () => [props.card?.repoUrl, props.card?.ref],
  () => {
    repoUrl.value = props.card?.repoUrl || ''
    refName.value = props.card?.ref || ''
  },
  { immediate: true }
)

function onCancel() {
  if (busy.value || !isPending.value) return
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'cancelled',
      repoUrl: String(repoUrl.value || '').trim(),
      ref: String(refName.value || '').trim(),
    })
  } finally {
    busy.value = false
  }
}

function sanitizeRepoUrl(raw) {
  let url = String(raw || '').trim().replace(/[.,;:)+\]}>'"`]+$/g, '')
  const gitIdx = url.toLowerCase().indexOf('.git')
  if (gitIdx >= 0) {
    url = url.slice(0, gitIdx + 4)
  } else {
    // 截掉尾部中文等非 URL 字符
    const m = url.match(/^https:\/\/[A-Za-z0-9.\-]+(?:\/[A-Za-z0-9_.\-]+)+/i)
    url = m ? m[0].replace(/\/+$/, '') : url.replace(/[^\x00-\x7F].*$/, '')
  }
  return url.replace(/\/+$/, '')
}

function onConfirm() {
  if (busy.value || !isPending.value) return
  const url = sanitizeRepoUrl(repoUrl.value)
  localError.value = ''
  if (!/^https:\/\//i.test(url)) {
    localError.value = '请填写公开 HTTPS 仓库地址（https://…）'
    return
  }
  if (/^https:\/\/[^/]*@/i.test(url)) {
    localError.value = '请勿在 URL 中嵌入账号或 Token'
    return
  }
  if (/[^\x00-\x7F]/.test(url)) {
    localError.value = '地址含非法字符，请只粘贴纯链接（不要带中文说明）'
    return
  }
  // 回填清洗后的地址，避免卡片仍显示脏 URL
  repoUrl.value = url
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'confirmed',
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
.git-repo-pick {
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
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.git-repo-pick.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
}

.git-repo-pick.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
}

.gp-head {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.gp-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.gp-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2f548c;
  font-weight: 700;
}

.is-confirmed .gp-badge {
  color: #2f7d4a;
}

.gp-hint {
  font-size: 12px;
  color: #5a7394;
  background: rgba(47, 84, 140, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.gp-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: #1f2630;
}

.gp-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #7a8494;
}

.gp-fields {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 4px;
}

.gp-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gp-label {
  font-size: 12px;
  color: #6b7c8f;
}

.gp-input {
  border: 1px solid #d0d7e0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  color: #1f2630;
  background: #fff;
  outline: none;
}

.gp-input:focus {
  border-color: #2f548c;
  box-shadow: 0 0 0 2px rgba(47, 84, 140, 0.12);
}

.gp-error {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b42318;
}

.gp-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid #dde5ef;
}

.gp-btn {
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

.gp-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.gp-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
  background: #fff;
}

.gp-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
}

.gp-btn.confirm {
  background: #2f548c;
  color: #fff !important;
  border-color: #2f548c;
}

.gp-btn.confirm:hover:not(:disabled) {
  background: #254572;
}

.gp-chosen {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 2px;
}

.gp-chosen-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #d7e8dc;
  border-radius: 8px;
}

.gp-k {
  font-size: 12px;
  color: #6b7c6f;
  line-height: 1.5;
  padding-top: 1px;
}

.gp-v {
  font-size: 13px;
  font-weight: 600;
  color: #1f2630;
  line-height: 1.5;
  word-break: break-all;
}

.gp-v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
  color: #3a4250;
}
</style>
