<template>
  <div class="write-confirm" :class="statusClass">
    <div class="wc-head">
      <div class="wc-title-row">
        <span class="wc-badge">写操作确认</span>
        <span class="wc-hint" v-if="isPending && !isExpiredLocally">确认后才会写入平台</span>
        <span class="wc-hint wc-expire" v-if="isPending && expireLabel">{{ expireLabel }}</span>
      </div>
      <p class="wc-summary">{{ card.summary || '待确认写入平台' }}</p>
    </div>

    <div class="wc-meta" v-if="hasMeta">
      <div class="wc-meta-item" v-if="preview.target_entity">
        <span class="wc-k">实体</span>
        <span class="wc-v">{{ entityDisplay }}</span>
      </div>
      <div class="wc-meta-item" v-if="preview.file">
        <span class="wc-k">文件</span>
        <span class="wc-v mono">{{ preview.file }}</span>
      </div>
      <div class="wc-meta-item" v-if="preview.row_count != null">
        <span class="wc-k">行数</span>
        <span class="wc-v strong">{{ preview.row_count }}</span>
      </div>
    </div>

    <div class="wc-section" v-if="preview?.columns?.length">
      <div class="wc-label">字段</div>
      <div class="wc-chips">
        <span class="wc-chip" v-for="c in preview.columns.slice(0, 16)" :key="c">{{ c }}</span>
        <span v-if="preview.columns.length > 16" class="wc-more">+{{ preview.columns.length - 16 }}</span>
      </div>
    </div>

    <div class="wc-section" v-if="sampleRows.length">
      <div class="wc-label">样例数据</div>
      <div class="wc-table-wrap">
        <table class="wc-table">
          <thead>
            <tr>
              <th v-for="col in sampleColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in sampleRows" :key="i">
              <td v-for="col in sampleColumns" :key="col">{{ formatCell(row[col]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="wc-error" v-if="isPending && card.error && !isExpiredLocally">
      上次写入失败：{{ card.error }}（可再次确认重试）
    </div>

    <div class="wc-actions" v-if="isPending && !isExpiredLocally">
      <button type="button" class="wc-btn cancel" :disabled="busy" @click="onCancel">取消</button>
      <button
        type="button"
        class="wc-btn confirm"
        :class="{ 'is-loading': busy }"
        :disabled="busy"
        @click="onConfirm"
      >
        <span v-if="busy" class="wc-spinner" aria-hidden="true" />
        {{ busy ? '处理中…' : (card.error ? '重试写入' : '确认写入') }}
      </button>
    </div>
    <div class="wc-result" v-else>
      <template v-if="card.status === 'confirmed'">已写入平台</template>
      <template v-else-if="card.status === 'cancelled'">已取消，未写入</template>
      <template v-else-if="card.status === 'expired' || isExpiredLocally">确认已过期，请重新发起导入</template>
      <template v-else-if="card.status === 'failed'">写入失败：{{ card.error || '未知错误' }}</template>
      <template v-else>{{ card.status || '待确认' }}</template>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { confirmWrite, cancelWrite } from '../api.js'

const props = defineProps({
  card: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['resolved'])

const busy = ref(false)
const nowTs = ref(Date.now() / 1000)
let timer = null

const preview = computed(() => props.card?.preview || {})

const entityDisplay = computed(() => {
  const id = preview.value?.target_entity || ''
  const label = String(preview.value?.target_label || preview.value?.label || '').trim()
  if (label && id && label !== id) return `${label}（${id}）`
  return label || id
})

const hasMeta = computed(
  () =>
    preview.value?.target_entity ||
    preview.value?.file ||
    preview.value?.row_count != null
)

const isPending = computed(() => {
  const s = props.card?.status
  return !s || s === 'pending' || s === 'pending_confirmation'
})

const expiresAt = computed(() => {
  const raw = props.card?.expires_at
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
})

const isExpiredLocally = computed(() => {
  if (props.card?.status === 'expired') return true
  if (!expiresAt.value) return false
  return nowTs.value >= expiresAt.value
})

const expireLabel = computed(() => {
  if (!expiresAt.value || !isPending.value) return ''
  const left = Math.max(0, Math.floor(expiresAt.value - nowTs.value))
  if (left <= 0) return '已过期'
  const m = Math.floor(left / 60)
  const s = left % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}小时${m % 60}分后过期`
  }
  if (m > 0) return `${m}分${String(s).padStart(2, '0')}秒后过期`
  return `${s}秒后过期`
})

const sampleRows = computed(() => {
  const rows = preview.value?.sample_rows
  if (!Array.isArray(rows)) return []
  return rows.filter((r) => r && typeof r === 'object').slice(0, 5)
})

const sampleColumns = computed(() => {
  const cols = preview.value?.columns
  if (Array.isArray(cols) && cols.length) return cols.slice(0, 8)
  const rows = sampleRows.value
  if (!rows.length) return []
  return Object.keys(rows[0]).slice(0, 8)
})

const statusClass = computed(() => {
  if (isExpiredLocally.value) return 'is-expired'
  if (isPending.value) return 'is-pending'
  const s = props.card?.status || 'pending'
  return `is-${s}`
})

function formatCell(v) {
  if (v == null || v === '') return '—'
  return String(v)
}

onMounted(() => {
  timer = setInterval(() => {
    nowTs.value = Date.now() / 1000
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

async function onConfirm() {
  if (busy.value || !props.card?.action_id || isExpiredLocally.value) return
  busy.value = true
  try {
    const res = await confirmWrite(props.card.action_id)
    const data = res.data || {}
    emit('resolved', {
      action_id: props.card.action_id,
      status: data.status || 'confirmed',
      result: data.result,
      preview: data.preview || props.card.preview,
    })
  } catch (err) {
    const status = err?.response?.status
    const msg = err?.response?.data?.detail || err?.message || '确认失败'
    const text = typeof msg === 'string' ? msg : JSON.stringify(msg)
    if (status === 410 || /过期/.test(text)) {
      emit('resolved', {
        action_id: props.card.action_id,
        status: 'expired',
        error: text,
        preview: props.card.preview,
      })
    } else {
      emit('resolved', {
        action_id: props.card.action_id,
        status: 'failed',
        error: text,
        preview: props.card.preview,
      })
    }
  } finally {
    busy.value = false
  }
}

async function onCancel() {
  if (busy.value || !props.card?.action_id || isExpiredLocally.value) return
  busy.value = true
  try {
    const res = await cancelWrite(props.card.action_id)
    const data = res.data || {}
    emit('resolved', {
      action_id: props.card.action_id,
      status: 'cancelled',
      preview: data.preview || props.card.preview,
    })
  } catch (err) {
    const status = err?.response?.status
    const msg = err?.response?.data?.detail || err?.message || '取消失败'
    const text = typeof msg === 'string' ? msg : JSON.stringify(msg)
    if (status === 410 || /过期/.test(text)) {
      emit('resolved', {
        action_id: props.card.action_id,
        status: 'expired',
        error: text,
        preview: props.card.preview,
      })
    } else {
      emit('resolved', {
        action_id: props.card.action_id,
        status: 'failed',
        error: text,
        preview: props.card.preview,
      })
    }
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.write-confirm {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #e6d5c8;
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(255, 248, 242, 0.95) 0%, #fff 48%);
  color: var(--ui-text, #1a1f26);
  box-shadow: 0 1px 0 rgba(196, 92, 38, 0.06);
}

.write-confirm.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
}

.write-confirm.is-cancelled,
.write-confirm.is-failed,
.write-confirm.is-expired {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
}

.wc-hint.wc-expire {
  color: #9a3412;
  background: rgba(154, 52, 18, 0.08);
}

.wc-head {
  margin-bottom: 12px;
}

.wc-error {
  margin: 0 0 12px;
  padding: 8px 10px;
  font-size: 12px;
  line-height: 1.45;
  color: #9a3412;
  background: #fff7ed;
  border: 1px solid #fed7aa;
  border-radius: 8px;
}

.wc-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.wc-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #c45c26;
  font-weight: 700;
}

.is-confirmed .wc-badge {
  color: #2f7d4a;
}

.wc-hint {
  font-size: 12px;
  color: #9a6b52;
  background: rgba(196, 92, 38, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.wc-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: #1f2630;
}

.wc-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.wc-meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #efe4db;
  border-radius: 8px;
  min-width: 0;
}

.wc-k {
  font-size: 11px;
  color: #8a7468;
}

.wc-v {
  font-size: 13px;
  color: #2a3340;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wc-v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
}

.wc-v.strong {
  font-weight: 700;
  color: #c45c26;
}

.wc-section {
  margin-bottom: 12px;
}

.wc-label {
  font-size: 12px;
  font-weight: 600;
  color: #7a8494;
  margin-bottom: 6px;
}

.wc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.wc-chip {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f4f1ee;
  color: #4a5360;
  border: 1px solid #e8e1db;
}

.wc-more {
  font-size: 12px;
  color: #7a8494;
  align-self: center;
}

.wc-table-wrap {
  overflow-x: auto;
  border: 1px solid #eadfd6;
  border-radius: 8px;
  background: #fff;
}

.wc-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  line-height: 1.4;
}

.wc-table th,
.wc-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #f0e8e1;
  white-space: nowrap;
}

.wc-table th {
  background: #faf6f3;
  color: #6b5b50;
  font-weight: 600;
}

.wc-table tbody tr:last-child td {
  border-bottom: none;
}

.wc-table td {
  color: #3a4250;
}

.wc-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid #eadfd6;
}

.wc-btn {
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
  transition: background 0.15s, border-color 0.15s, transform 0.1s;
}

.wc-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.wc-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
  background: #fff;
}

.wc-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
}

.wc-btn.confirm {
  background: #c45c26;
  color: #fff !important;
  border-color: #c45c26;
}

.wc-btn.confirm:hover:not(:disabled) {
  background: #a84c1e;
}

.wc-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: wc-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes wc-spin {
  to {
    transform: rotate(360deg);
  }
}

.wc-result {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #e6ebf0;
  font-size: 13px;
  color: #3a4250;
  text-align: right;
}

@media (max-width: 640px) {
  .wc-meta {
    grid-template-columns: 1fr;
  }

  .wc-title-row {
    flex-wrap: wrap;
  }
}
</style>
