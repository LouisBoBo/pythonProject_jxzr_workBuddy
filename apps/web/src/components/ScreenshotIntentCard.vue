<template>
  <div class="shot-intent" :class="statusClass">
    <template v-if="isPending">
      <div class="shot-head">
        <span class="shot-badge">意图确认</span>
        <p class="shot-summary">{{ card.summary || '已收到截图，请确认你想做什么' }}</p>
        <p v-if="card.hint" class="shot-hint">{{ card.hint }}</p>
      </div>
      <div class="shot-opts">
        <button
          v-for="opt in options"
          :key="opt.id"
          type="button"
          class="shot-opt"
          :disabled="busy"
          @click="onPick(opt)"
        >
          {{ opt.label }}
        </button>
      </div>
      <button type="button" class="shot-cancel" :disabled="busy" @click="onCancel">
        先不处理
      </button>
    </template>
    <template v-else-if="card.status === 'confirmed'">
      <div class="shot-head">
        <span class="shot-badge">意图确认</span>
        <p class="shot-summary">已确认：{{ confirmedLabel }}</p>
      </div>
    </template>
    <template v-else>
      <div class="shot-head">
        <span class="shot-badge">意图确认</span>
        <p class="shot-summary">已取消</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  card: { type: Object, required: true },
})
const emit = defineEmits(['resolved'])

const busy = ref(false)
const options = computed(() =>
  Array.isArray(props.card?.options) && props.card.options.length
    ? props.card.options
    : [
        { id: 'code_dev_match', label: '做成跟截图一样（视觉对齐）' },
        { id: 'code_dev_edit', label: '按截图修改部分界面' },
        { id: 'code_dev', label: '按截图写/改功能（不强制照抄视觉）' },
        { id: 'explain', label: '解释截图内容或报错' },
        { id: 'mes', label: '查 MES / 业务问题' },
        { id: 'code_review', label: '审核相关代码' },
        { id: 'other', label: '都不是，我补充说明' },
      ],
)

const isPending = computed(() => !props.card?.status || props.card.status === 'pending')
const statusClass = computed(() => {
  const s = props.card?.status || 'pending'
  return { pending: s === 'pending', confirmed: s === 'confirmed', cancelled: s === 'cancelled' }
})
const confirmedLabel = computed(() => {
  const id = props.card?.chosen
  const hit = options.value.find((o) => o.id === id)
  return hit?.label || id || '已确认'
})

function onPick(opt) {
  if (busy.value || !isPending.value) return
  busy.value = true
  emit('resolved', {
    status: 'confirmed',
    intent: opt.id,
    label: opt.label,
    pendingContent: props.card?.pendingContent || '',
    pendingFiles: props.card?.pendingFiles || [],
  })
  // 父级会立刻改 status；保留短暂 busy 防连点
  setTimeout(() => {
    if (props.card?.status === 'pending') busy.value = false
  }, 800)
}

function onCancel() {
  if (busy.value || !isPending.value) return
  busy.value = true
  emit('resolved', { status: 'cancelled' })
  setTimeout(() => {
    if (props.card?.status === 'pending') busy.value = false
  }, 800)
}
</script>

<style scoped>
.shot-intent {
  margin-top: 10px;
  padding: 12px 14px;
  border: 1px solid var(--ui-border);
  border-radius: 12px;
  background: var(--ui-panel-2);
  max-width: 520px;
}
.shot-head {
  margin-bottom: 10px;
}
.shot-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  color: var(--ui-text-muted);
  background: var(--ui-panel);
  border: 1px solid var(--ui-border);
  border-radius: 6px;
  padding: 2px 8px;
  margin-bottom: 8px;
}
.shot-summary {
  margin: 0;
  font-size: 14px;
  color: var(--ui-text);
  line-height: 1.45;
}
.shot-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--ui-text-muted);
  line-height: 1.4;
}
.shot-opts {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.shot-opt {
  text-align: left;
  padding: 10px 12px;
  border: 1px solid var(--ui-border);
  border-radius: 10px;
  background: var(--ui-surface);
  color: var(--ui-text);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.12s, background 0.12s;
}
.shot-opt:hover:not(:disabled) {
  border-color: color-mix(in oklab, var(--ui-accent, #2563eb) 55%, var(--ui-border));
  background: color-mix(in oklab, var(--ui-accent, #2563eb) 6%, var(--ui-surface));
}
.shot-opt:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.shot-cancel {
  margin-top: 10px;
  border: none;
  background: transparent;
  color: var(--ui-text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.shot-cancel:hover:not(:disabled) {
  color: var(--ui-text);
}
.shot-intent.confirmed,
.shot-intent.cancelled {
  opacity: 0.85;
}
</style>
