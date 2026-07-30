<template>
  <div class="ide-ws-pick" :class="statusClass">
    <template v-if="isPending">
      <div class="ip-head">
        <div class="ip-title-row">
          <span class="ip-badge">工程确认</span>
          <span class="ip-hint">确认后开始审核</span>
        </div>
        <p class="ip-summary">选择要审核的工程</p>
        <p class="ip-desc">将审核所选本地工程（可不在 VS Code 当前打开该文件夹）</p>
      </div>

      <div class="ip-list" v-if="workspaces.length">
        <label
          v-for="w in workspaces"
          :key="w.path"
          class="ip-item"
          :class="{ selected: selected === w.path }"
        >
          <input
            type="radio"
            class="ip-radio"
            name="ide-ws-pick-card"
            :value="w.path"
            :checked="selected === w.path"
            @change="selected = w.path"
          />
          <span class="ip-item-body">
            <span class="ip-name-row">
              <strong class="ip-name">{{ w.name || w.path }}</strong>
              <span v-if="w.current" class="ip-current">当前打开</span>
            </span>
            <span class="ip-path">{{ w.path }}</span>
          </span>
        </label>
      </div>
      <div class="ip-empty" v-else>暂无最近工程，请先在 VS Code 打开过项目文件夹</div>

      <div class="ip-actions">
        <button type="button" class="ip-btn cancel" :disabled="busy" @click="onCancel">取消</button>
        <button
          type="button"
          class="ip-btn confirm"
          :disabled="busy || !selected"
          @click="onConfirm"
        >
          {{ busy ? '处理中…' : '开始审核' }}
        </button>
      </div>
    </template>

    <template v-else-if="card.status === 'confirmed'">
      <div class="ip-head">
        <div class="ip-title-row">
          <span class="ip-badge">工程确认</span>
        </div>
        <p class="ip-summary">已选择审核的工程</p>
      </div>
      <div class="ip-chosen">
        <div class="ip-chosen-row">
          <span class="ip-k">项目名称</span>
          <span class="ip-v">{{ selectedName }}</span>
        </div>
        <div class="ip-chosen-row">
          <span class="ip-k">项目路径</span>
          <span class="ip-v mono">{{ selectedPath }}</span>
        </div>
      </div>
    </template>

    <template v-else>
      <div class="ip-head">
        <div class="ip-title-row">
          <span class="ip-badge">工程确认</span>
        </div>
        <p class="ip-summary">已取消，未开始审核</p>
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
const selected = ref('')

const workspaces = computed(() =>
  Array.isArray(props.card?.workspaces) ? props.card.workspaces.filter((w) => w?.path) : []
)

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')

const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  if (s === 'confirmed') return 'is-confirmed'
  if (s === 'cancelled') return 'is-cancelled'
  return 'is-pending'
})

const selectedPath = computed(() => selected.value || props.card?.selected || '')

const selectedName = computed(() => {
  const path = selectedPath.value
  const hit = workspaces.value.find((w) => w.path === path)
  if (hit?.name) return hit.name
  if (!path) return '—'
  const parts = String(path).split(/[/\\]/).filter(Boolean)
  return parts[parts.length - 1] || path
})

watch(
  () => [props.card?.selected, workspaces.value],
  () => {
    const cur =
      props.card?.selected ||
      workspaces.value.find((w) => w.current)?.path ||
      workspaces.value[0]?.path ||
      ''
    selected.value = cur
  },
  { immediate: true, deep: true }
)

function onCancel() {
  if (busy.value || !isPending.value) return
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'cancelled',
      selected: selected.value,
    })
  } finally {
    busy.value = false
  }
}

function onConfirm() {
  if (busy.value || !isPending.value || !selected.value) return
  busy.value = true
  try {
    emit('resolved', {
      id: props.card.id,
      status: 'confirmed',
      selected: selected.value,
    })
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.ide-ws-pick {
  align-self: stretch;
  width: 100%;
  max-width: 100%;
  max-height: 500px;
  box-sizing: border-box;
  margin: 10px 0 2px;
  padding: 14px 16px 12px;
  border: 1px solid #e6d5c8;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255, 248, 242, 0.95) 0%, #fff 48%);
  color: var(--ui-text, #1a1f26);
  box-shadow: 0 1px 0 rgba(196, 92, 38, 0.06);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.ide-ws-pick.is-confirmed {
  border-color: #c5ddce;
  background: linear-gradient(180deg, #f4faf6 0%, #fff 50%);
  box-shadow: none;
}

.ide-ws-pick.is-cancelled {
  border-color: #d8dee6;
  background: #f8f9fb;
  box-shadow: none;
}

.ip-head {
  flex-shrink: 0;
  margin-bottom: 10px;
}

.ip-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.ip-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #c45c26;
  font-weight: 700;
}

.is-confirmed .ip-badge {
  color: #2f7d4a;
}

.ip-hint {
  font-size: 12px;
  color: #9a6b52;
  background: rgba(196, 92, 38, 0.08);
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.ip-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.45;
  color: #1f2630;
}

.ip-desc {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #7a8494;
}

.ip-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  margin: 0 0 4px;
  padding-right: 2px;
  border-top: 1px solid #eadfd6;
}

.ip-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 10px 4px;
  border-bottom: 1px solid #f0e8e1;
  cursor: pointer;
}

.ip-item:last-child {
  border-bottom: none;
}

.ip-item.selected {
  background: rgba(196, 92, 38, 0.04);
}

.ip-item.disabled {
  cursor: default;
}

.ip-radio {
  margin-top: 4px;
  flex-shrink: 0;
  accent-color: #c45c26;
}

.ip-item-body {
  display: block;
  min-width: 0;
  line-height: 1.4;
}

.ip-name-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.ip-name {
  font-size: 14px;
  color: #1f2630;
}

.ip-current {
  font-size: 12px;
  font-weight: 500;
  color: #2f7d4a;
}

.ip-path {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: #8a7468;
  word-break: break-all;
}

.ip-empty {
  padding: 16px 4px;
  font-size: 13px;
  color: #7a8494;
}

.ip-actions {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid #eadfd6;
}

.ip-btn {
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

.ip-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.ip-btn.cancel {
  border-color: #d0d7e0;
  color: #3a4250;
  background: #fff;
}

.ip-btn.cancel:hover:not(:disabled) {
  background: #f3f5f8;
}

.ip-btn.confirm {
  background: #c45c26;
  color: #fff !important;
  border-color: #c45c26;
}

.ip-btn.confirm:hover:not(:disabled) {
  background: #a84c1e;
}

.ip-chosen {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 2px;
}

.ip-chosen-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid #d7e8dc;
  border-radius: 8px;
}

.ip-k {
  font-size: 12px;
  color: #6b7c6f;
  line-height: 1.5;
  padding-top: 1px;
}

.ip-v {
  font-size: 13px;
  font-weight: 600;
  color: #1f2630;
  line-height: 1.5;
  word-break: break-all;
}

.ip-v.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  font-weight: 500;
  color: #3a4250;
}

.ide-ws-pick.is-confirmed,
.ide-ws-pick.is-cancelled {
  max-height: none;
}
</style>
