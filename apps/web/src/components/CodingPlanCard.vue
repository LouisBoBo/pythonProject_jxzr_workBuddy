<template>
  <div v-if="steps.length" class="coding-plan" :class="{ 'is-collapsed': collapsed }">
    <button type="button" class="cp-head" @click="toggle" :aria-expanded="!collapsed">
      <span class="cp-badge">{{ heading }}</span>
      <span class="cp-summary">{{ summary }}</span>
      <span v-if="collapsible" class="cp-chevron" aria-hidden="true">{{ collapsed ? '展开' : '收起' }}</span>
    </button>
    <ol v-show="!collapsed" class="cp-list">
      <li
        v-for="(s, i) in steps"
        :key="s.id || i"
        class="cp-item"
        :class="itemClass(s)"
      >
        <span class="cp-icon" aria-hidden="true">
          <span v-if="s.state === 'running'" class="cp-spinner" />
          <span v-else-if="s.state === 'done'" class="cp-check">✓</span>
          <span v-else-if="s.state === 'error'" class="cp-fail">!</span>
          <span v-else class="cp-pending">{{ i + 1 }}</span>
        </span>
        <div class="cp-body">
          <span class="cp-title">{{ displayTitle(s, i) }}</span>
          <span v-if="stateHint(s)" class="cp-state">{{ stateHint(s) }}</span>
        </div>
      </li>
    </ol>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  steps: { type: Array, default: () => [] },
  /** 卡片标题 */
  heading: { type: String, default: '本轮进度' },
  /** 完成后是否可折叠 */
  collapsible: { type: Boolean, default: true },
  /** 初始是否折叠（全部完成时默认收起） */
  defaultCollapsed: { type: Boolean, default: null },
})

const collapsed = ref(false)

const allDone = computed(() => {
  const list = props.steps || []
  return list.length > 0 && list.every((s) => s.state === 'done' || s.state === 'error')
})

const summary = computed(() => {
  const list = props.steps || []
  const done = list.filter((s) => s.state === 'done').length
  const running = list.some((s) => s.state === 'running')
  const err = list.filter((s) => s.state === 'error').length
  if (running) return `正在进行 ${done}/${list.length}`
  if (err) return `完成 ${done}/${list.length}（${err} 步失败）`
  if (done === list.length && list.length) return `已全部完成（${list.length} 步）`
  return `共 ${list.length} 步`
})

// 勿 deep watch steps：父组件频繁换数组引用会触发无意义更新，严重时拖垮会话切换
watch(
  () => props.defaultCollapsed,
  (v) => {
    if (v != null) collapsed.value = Boolean(v)
  },
  { immediate: true },
)
watch(
  allDone,
  (done) => {
    if (props.defaultCollapsed != null) return
    collapsed.value = Boolean(done)
  },
  { immediate: true },
)

function toggle() {
  if (!props.collapsible) return
  collapsed.value = !collapsed.value
}

function itemClass(s) {
  const st = s?.state || 'pending'
  if (st === 'running') return 'is-running'
  if (st === 'done') return 'is-done'
  if (st === 'error') return 'is-error'
  return 'is-pending'
}

function stateHint(s) {
  const st = s?.state || 'pending'
  if (st === 'running') return '进行中'
  if (st === 'done') return '已完成'
  if (st === 'error') return '失败'
  return '等待中'
}

/** 去掉「第N步 / 1.」等序号前缀（左侧圆点已有序号），并把常见技术词改成白话 */
function humanizeTitle(raw) {
  let t = String(raw || '').trim()
  t = t.replace(/^第\s*[一二三四五六七八九十百零〇\d]+\s*步\s*[：:．.\-—]?\s*/, '')
  // 模型常自带「1. / 2、」；避免与左侧序号或二次拼接重复
  t = t.replace(/^\d+\s*[.．、:：)\]]\s*/, '')
  t = t.replace(/\s*[—\-]\s*/g, ' · ')
  const replacements = [
    [/schemas?\s*与\s*router/gi, '数据接口'],
    [/\brouter\b/gi, '接口'],
    [/\bschemas?\b/gi, '数据结构'],
    [/注册.+路由到\s*main\.py/gi, '接入系统菜单与服务'],
    [/注册.+路由/gi, '接入系统服务'],
    [/更新路由指向/gi, '接上页面入口'],
    [/更新左侧菜单路由映射/gi, '更新左侧菜单入口'],
    [/API\s*模块/gi, '前端请求'],
    [/main\.py/gi, '后端入口'],
  ]
  for (const [re, to] of replacements) {
    t = t.replace(re, to)
  }
  return t.trim() || '处理中'
}

function displayTitle(s, _i) {
  // 序号只留左侧状态圆点，正文不再写「1. …」
  return humanizeTitle(s?.title)
}
</script>

<style scoped>
.coding-plan {
  margin: 10px 0 4px;
  padding: 10px 12px;
  border: 1px solid #e8eef5;
  border-radius: 10px;
  background: #f8fafc;
  max-width: min(640px, 100%);
}
.coding-plan.is-collapsed {
  padding-bottom: 10px;
}
.cp-head {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin: 0;
  padding: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font: inherit;
}
.cp-badge {
  font-size: 12px;
  font-weight: 700;
  color: #1e3a5f;
  flex-shrink: 0;
}
.cp-summary {
  flex: 1;
  font-size: 12px;
  color: #64748b;
}
.cp-chevron {
  font-size: 11px;
  color: #94a3b8;
  flex-shrink: 0;
}
.cp-list {
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}
.cp-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 0;
  border-top: 1px solid #eef2f7;
}
.cp-item:first-child {
  border-top: none;
  padding-top: 2px;
}
.cp-icon {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}
.cp-pending {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cp-check {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #dcfce7;
  color: #15803d;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cp-fail {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #fee2e2;
  color: #be123c;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.cp-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid #bfdbfe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: cp-spin 0.7s linear infinite;
}
.cp-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cp-title {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.45;
}
.cp-state {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 500;
}
.cp-item.is-running .cp-title {
  color: #1d4ed8;
}
.cp-item.is-running .cp-state {
  color: #2563eb;
}
.cp-item.is-done .cp-title {
  color: #334155;
  font-weight: 500;
}
.cp-item.is-error .cp-title {
  color: #be123c;
}
.cp-item.is-pending .cp-title {
  color: #64748b;
  font-weight: 500;
}
@keyframes cp-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
