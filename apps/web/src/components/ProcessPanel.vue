<template>
  <div v-if="items.length" class="process-panel" :class="{ collapsed: isCollapsed }">
    <button type="button" class="process-header" @click="toggle">
      <span class="process-live" v-if="!isCollapsed && hasRunning" aria-hidden="true"></span>
      <span class="process-title">{{ title }}</span>
      <span class="process-summary">{{ summary }}</span>
      <svg
        class="process-chevron"
        :class="{ open: !isCollapsed }"
        width="14"
        height="14"
        viewBox="0 0 14 14"
        fill="none"
      >
        <path d="M3.5 5.25L7 8.75L10.5 5.25" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>

    <div v-show="!isCollapsed" class="process-shell">
      <div
        v-for="item in visibleItems"
        :key="item.id || `${item.type}-${item.title}-${item.text}`"
        class="process-item"
        :class="itemClass(item)"
      >
        <div class="process-rail" aria-hidden="true">
          <span class="process-dot"></span>
        </div>
        <div class="process-card">
          <div class="process-card-head">
            <span class="process-status-icon" aria-hidden="true">
              <span v-if="isRunningItem(item)" class="process-spinner" />
              <span v-else-if="isDoneItem(item)">✅</span>
              <span v-else-if="isErrorItem(item)">❌</span>
            </span>
            <span class="process-badge">{{ statusLabel(item) }}</span>
            <div class="process-item-title">{{ itemLabel(item) }}</div>
          </div>

          <div v-if="item.args" class="process-block">
            <div class="process-block-label">输入</div>
            <pre class="process-block-body">{{ item.args }}</pre>
          </div>

          <div v-if="item.detail" class="process-block">
            <div class="process-block-label">结果</div>
            <div class="process-block-summary">{{ item.detail }}</div>
            <ul v-if="item.preview?.length" class="process-preview" :class="{ 'is-table': looksLikeTable(item.preview) }">
              <li v-for="(line, i) in item.preview" :key="i" class="mono">{{ line }}</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  collapsed: { type: Boolean, default: false },
  title: { type: String, default: '处理过程' },
  durationText: { type: String, default: '' },
})

const emit = defineEmits(['update:collapsed'])

const isCollapsed = ref(props.collapsed)

watch(
  () => props.collapsed,
  (v) => {
    isCollapsed.value = v
  }
)

const visibleItems = computed(() => {
  const raw = (props.items || []).filter(
    (i) =>
      i.type === 'step' ||
      (i.type === 'status' && (i.phase === 'generating' || i.phase === 'waiting'))
  )
  // 分批读码步骤按 batch_index 升序（图二：第1批在上、其后递增）；其它项保持相对位置
  const batchNo = (item) => {
    if (item?.batch_index != null && item.batch_index !== '') {
      const n = Number(item.batch_index)
      return Number.isFinite(n) ? n : null
    }
    const args = String(item?.args || '')
    const mArgs = args.match(/batch_index\s*[:：]\s*(\d+)/i)
    if (mArgs) return Number(mArgs[1])
    const title = String(item?.title || '')
    const mTitle = title.match(/第\s*(\d+)\s*批/)
    if (mTitle) return Number(mTitle[1]) - 1
    return null
  }
  const indexed = raw.map((item, i) => ({ item, i, b: batchNo(item) }))
  indexed.sort((a, b) => {
    const aBatch = a.item?.tool && /read_batch|list_source_files/i.test(String(a.item.tool || ''))
    const bBatch = b.item?.tool && /read_batch|list_source_files/i.test(String(b.item.tool || ''))
    if (aBatch && bBatch && a.b != null && b.b != null && a.item.tool === b.item.tool) {
      if (a.b !== b.b) return a.b - b.b
    }
    return a.i - b.i
  })
  return indexed.map((x) => x.item)
})

const hasRunning = computed(() =>
  visibleItems.value.some(
    (i) =>
      i.state === 'running' ||
      i.state === 'waiting' ||
      i.phase === 'generating' ||
      i.phase === 'waiting'
  )
)

const summary = computed(() => {
  const steps = (props.items || []).filter((i) => i.type === 'step')
  const n = steps.length
  const parts = []
  if (n) parts.push(`${n} 步`)
  if (props.durationText) parts.push(props.durationText)
  if (!parts.length && props.items?.length) parts.push(`${props.items.length} 项`)
  return parts.join(' · ')
})

function toggle() {
  isCollapsed.value = !isCollapsed.value
  emit('update:collapsed', isCollapsed.value)
}

function itemClass(item) {
  if (item.phase === 'generating' || item.phase === 'waiting' || item.state === 'running') return 'is-running'
  if (item.state === 'waiting') return 'is-running'
  if (item.state === 'error' || item.ok === false) return 'is-error'
  if (item.state === 'done' || item.phase === 'end') return 'is-ok'
  if (item.type === 'status') return 'is-status'
  return 'is-step'
}

function itemLabel(item) {
  if (item.type === 'status') return item.text || ''
  return item.title || ''
}

function statusLabel(item) {
  if (item.phase === 'generating') return '生成中'
  if (item.phase === 'waiting') return '整理中'
  if (item.state === 'waiting') return '待确认'
  if (item.state === 'running') return '执行中'
  if (item.state === 'error' || item.ok === false) return '失败'
  if (item.state === 'done' || item.phase === 'end') return '完成'
  if (item.type === 'status') return '状态'
  return '步骤'
}

function isRunningItem(item) {
  return (
    item?.phase === 'generating' ||
    item?.phase === 'waiting' ||
    item?.state === 'running' ||
    item?.state === 'waiting'
  )
}

function isDoneItem(item) {
  return item?.state === 'done' || item?.phase === 'end'
}

function isErrorItem(item) {
  return item?.state === 'error' || item?.ok === false
}

function looksLikeTable(preview) {
  if (!Array.isArray(preview) || preview.length < 2) return false
  const a = String(preview[0] || '')
  const b = String(preview[1] || '')
  return a.includes(' | ') && (b.includes('---') || /^[\s|:-]+$/.test(b.trim()))
}
</script>

<style scoped>
.process-panel {
  margin-bottom: 12px;
  max-width: min(640px, 100%);
}

.process-header {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: none;
  background: transparent;
  padding: 0;
  cursor: pointer;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}

.process-header:hover {
  color: #475569;
}

.process-live {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.45);
  animation: live-pulse 1.2s ease-out infinite;
}

@keyframes live-pulse {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.45); }
  70% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}

.process-summary {
  color: #94a3b8;
  font-weight: 400;
  font-size: 12px;
}

.process-chevron {
  transition: transform 0.18s ease;
  flex-shrink: 0;
}

.process-chevron.open {
  transform: rotate(180deg);
}

.process-shell {
  margin-top: 10px;
  padding: 12px 12px 8px;
  background: #f8fafc;
  border: 1px solid #e8eef5;
  border-radius: 12px;
}

.process-item {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding-bottom: 12px;
  animation: process-in 0.28s ease-out;
}

.process-item:last-child {
  padding-bottom: 4px;
}

@keyframes process-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.process-rail {
  position: relative;
  width: 14px;
  flex-shrink: 0;
  display: flex;
  justify-content: center;
}

.process-rail::before {
  content: "";
  position: absolute;
  top: 18px;
  bottom: -12px;
  width: 2px;
  background: #e2e8f0;
}

.process-item:last-child .process-rail::before {
  display: none;
}

.process-dot {
  width: 10px;
  height: 10px;
  margin-top: 6px;
  border-radius: 50%;
  background: #cbd5e1;
  border: 2px solid #f8fafc;
  box-shadow: 0 0 0 1px #cbd5e1;
  z-index: 1;
}

.process-item.is-running .process-dot {
  background: #3b82f6;
  box-shadow: 0 0 0 1px #3b82f6;
  animation: live-pulse 1.2s ease-out infinite;
}

.process-item.is-ok .process-dot {
  background: #64748b;
  box-shadow: 0 0 0 1px #64748b;
}

.process-item.is-error .process-dot {
  background: #e11d48;
  box-shadow: 0 0 0 1px #e11d48;
}

.process-card {
  min-width: 0;
  flex: 1;
  padding: 8px 10px;
  background: #fff;
  border: 1px solid #eef2f7;
  border-radius: 10px;
}

.process-card-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.process-status-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  line-height: 1;
}

.process-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: process-spin 0.7s linear infinite;
}

@keyframes process-spin {
  to {
    transform: rotate(360deg);
  }
}

.process-badge {
  flex-shrink: 0;
  margin-top: 1px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #64748b;
  background: #f1f5f9;
}

.process-item.is-running .process-badge {
  color: #1d4ed8;
  background: #dbeafe;
}

.process-item.is-ok .process-badge {
  color: #475569;
  background: #f1f5f9;
}

.process-item.is-error .process-badge {
  color: #be123c;
  background: #ffe4e6;
}

.process-item-title {
  color: #334155;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}

.process-block {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #e8eef5;
}

.process-block-label {
  margin-bottom: 4px;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  letter-spacing: 0.04em;
}

.process-block-body,
.process-block-summary {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #64748b;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.process-block-summary {
  font-family: inherit;
  color: #475569;
  font-weight: 500;
}

.process-preview {
  margin: 6px 0 0;
  padding-left: 16px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.55;
}

.process-preview.is-table {
  list-style: none;
  padding-left: 0;
  overflow-x: auto;
}

.process-preview.is-table li {
  white-space: pre;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  line-height: 1.5;
}

.process-preview li {
  margin: 2px 0;
  word-break: break-word;
}

.process-item.is-error .process-block-summary,
.process-item.is-error .process-item-title {
  color: #e11d48;
}
</style>
