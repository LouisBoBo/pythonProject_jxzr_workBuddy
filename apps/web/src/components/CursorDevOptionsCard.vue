<template>
  <div class="cd-options" :class="statusClass">
    <template v-if="isPending">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">需求选项</span>
          <span class="cd-hint">勾选即可 · 少打字</span>
        </div>
        <p class="cd-summary">{{ card.title || '请确认以下关键项' }}</p>
        <p v-if="card.summary" class="cd-desc">{{ card.summary }}</p>
      </div>

      <div
        v-for="group in groups"
        :key="group.id"
        class="cd-group"
      >
        <div class="cd-group-label">
          {{ group.label }}
          <span v-if="group.required !== false" class="cd-req">必选</span>
          <span class="cd-mode">{{ group.multi ? '可多选' : '单选' }}</span>
        </div>
        <div class="cd-opts">
          <label
            v-for="opt in group.options || []"
            :key="opt.id"
            class="cd-opt"
            :class="{ on: isSelected(group.id, opt.id) }"
          >
            <input
              :type="group.multi ? 'checkbox' : 'radio'"
              :name="`g-${card.id}-${group.id}`"
              :value="opt.id"
              :checked="isSelected(group.id, opt.id)"
              :disabled="busy"
              @change="onToggle(group, opt.id, $event)"
            />
            <span class="cd-opt-text">{{ opt.label }}</span>
          </label>
        </div>
      </div>

      <label class="cd-field">
        <span class="cd-label">备注（可选）</span>
        <textarea
          v-model="notes"
          class="cd-input cd-textarea"
          rows="3"
          :placeholder="card.notes_placeholder || '补充约束、验收点、不要做的事…'"
          :disabled="busy"
        />
      </label>

      <p v-if="localError" class="cd-error">{{ localError }}</p>

      <div class="cd-actions">
        <button type="button" class="cd-btn cancel" :disabled="busy" @click="onCancel">
          跳过本卡
        </button>
        <button
          type="button"
          class="cd-btn confirm"
          :class="{ 'is-loading': busy }"
          :disabled="busy || !canConfirm"
          @click="onConfirm"
        >
          <span v-if="busy" class="cd-spinner" aria-hidden="true" />
          {{ busy ? '提交中…' : '确认选项' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">需求选项</span>
        </div>
        <p class="cd-summary">已确认选项</p>
      </div>
      <div class="cd-chosen">
        <div
          v-for="row in confirmedRows"
          :key="row.label"
          class="cd-chosen-row"
        >
          <span class="cd-k">{{ row.label }}</span>
          <span class="cd-v">{{ row.value }}</span>
        </div>
        <div v-if="card.notes" class="cd-chosen-row">
          <span class="cd-k">备注</span>
          <span class="cd-v">{{ card.notes }}</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="cd-head">
        <div class="cd-title-row">
          <span class="cd-badge">需求选项</span>
        </div>
        <p class="cd-summary">已跳过本卡，可继续文字补充</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
})

const emit = defineEmits(['resolved'])

const busy = ref(false)
const notes = ref('')
const localError = ref('')
/** @type {Record<string, string[]>} */
const selected = reactive({})
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

const groups = computed(() =>
  Array.isArray(props.card?.groups) ? props.card.groups.filter((g) => g?.id) : [],
)

const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled' || s === 'skipped') return 'is-cancelled'
  return 'is-pending'
})

const confirmedRows = computed(() => {
  const labels = props.card?.selectionLabels || {}
  const groupsList = Array.isArray(props.card?.groups) ? props.card.groups : []
  return groupsList
    .map((g) => {
      const vals = labels[g.id]
      if (!vals || !vals.length) return null
      return { label: g.label || g.id, value: vals.join('、') }
    })
    .filter(Boolean)
})

const canConfirm = computed(() => {
  for (const g of groups.value) {
    if (g.required === false) continue
    const ids = selected[g.id] || []
    if (!ids.length) return false
  }
  return groups.value.length > 0
})

watch(
  () => props.card,
  () => {
    notes.value = String(props.card?.notes || '')
    for (const g of groups.value) {
      const preset = props.card?.defaults?.[g.id]
      if (Array.isArray(preset)) {
        selected[g.id] = [...preset]
      } else if (preset) {
        selected[g.id] = [String(preset)]
      } else if (!selected[g.id]) {
        selected[g.id] = []
      }
    }
  },
  { immediate: true, deep: true },
)

function isSelected(groupId, optId) {
  return (selected[groupId] || []).includes(optId)
}

function onToggle(group, optId, event) {
  const on = Boolean(event?.target?.checked)
  if (group.multi) {
    const cur = new Set(selected[group.id] || [])
    if (on) cur.add(optId)
    else cur.delete(optId)
    selected[group.id] = [...cur]
  } else {
    selected[group.id] = on ? [optId] : []
  }
}

function buildLabels() {
  /** @type {Record<string, string[]>} */
  const out = {}
  for (const g of groups.value) {
    const ids = selected[g.id] || []
    const map = Object.fromEntries((g.options || []).map((o) => [o.id, o.label]))
    out[g.id] = ids.map((id) => map[id] || id)
  }
  return out
}

function onCancel() {
  if (busy.value || !isPending.value) return
  armBusy()
  emit('resolved', {
    id: props.card.id,
    status: 'skipped',
    selections: { ...selected },
    selectionLabels: buildLabels(),
    notes: String(notes.value || '').trim(),
  })
}

function onConfirm() {
  if (busy.value || !isPending.value) return
  localError.value = ''
  if (!canConfirm.value) {
    localError.value = '请先完成所有必选项'
    return
  }
  armBusy()
  const selectionLabels = buildLabels()
  emit('resolved', {
    id: props.card.id,
    status: 'confirmed',
    selections: Object.fromEntries(
      Object.entries(selected).map(([k, v]) => [k, [...(v || [])]]),
    ),
    selectionLabels,
    notes: String(notes.value || '').trim(),
  })
}
</script>

<style scoped>
.cd-options {
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
}

.cd-options.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
}

.cd-options.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
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

.cd-group {
  margin: 12px 0;
}

.cd-group-label {
  font-size: 13px;
  font-weight: 600;
  color: #2a3444;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.cd-req {
  font-size: 11px;
  font-weight: 600;
  color: #b45309;
  background: #fff7ed;
  padding: 1px 6px;
  border-radius: 999px;
}

.cd-mode {
  font-size: 11px;
  font-weight: 500;
  color: #6b7c8f;
}

.cd-opts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cd-opt {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 9px 11px;
  border: 1px solid #d0d7e0;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  user-select: none;
}

.cd-opt.on {
  border-color: #2f548c;
  background: rgba(47, 84, 140, 0.06);
}

.cd-opt input {
  margin-top: 2px;
  flex-shrink: 0;
}

.cd-opt-text {
  font-size: 13px;
  line-height: 1.45;
  color: #1f2630;
}

.cd-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
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
  font-family: inherit;
}

.cd-textarea {
  resize: vertical;
  min-height: 72px;
  line-height: 1.5;
}

.cd-input:focus {
  border-color: #2f548c;
  box-shadow: 0 0 0 2px rgba(47, 84, 140, 0.12);
}

.cd-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: #b42318;
}

.cd-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.cd-btn {
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
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
  background: #eef2f6;
  color: #4a5568;
}

.cd-btn.confirm {
  background: #2f548c;
  color: #fff;
}

.cd-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: cd-opt-spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes cd-opt-spin {
  to {
    transform: rotate(360deg);
  }
}

.cd-chosen {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cd-chosen-row {
  display: grid;
  grid-template-columns: 72px 1fr;
  gap: 8px;
  font-size: 13px;
}

.cd-k {
  color: #6b7c8f;
}

.cd-v {
  color: #1f2630;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
