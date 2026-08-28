<template>
  <div class="automations-view">
    <header class="page-header">
      <div class="header-tabs">
        <button
          type="button"
          class="header-tab"
          :class="{ active: activeTab === 'tasks' }"
          @click="activeTab = 'tasks'"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <circle cx="8" cy="8" r="6.5" stroke="currentColor" stroke-width="1.2"/>
            <path d="M8 4.5V8l2.5 1.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          定时任务
        </button>
        <button
          type="button"
          class="header-tab"
          :class="{ active: activeTab === 'runs' }"
          @click="activeTab = 'runs'"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <rect x="3" y="2.5" width="10" height="11" rx="1.5" stroke="currentColor" stroke-width="1.2"/>
            <path d="M5.5 6h5M5.5 8.5h5M5.5 11h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          </svg>
          运行记录
        </button>
      </div>
      <el-button v-if="activeTab === 'tasks'" type="primary" class="add-btn" @click="openCreate">
        + 添加自动化
      </el-button>
    </header>

    <div class="page-body">
      <div v-if="loading" class="loading-state">加载中…</div>
      <div v-else-if="error" class="error-card">{{ error }}</div>

      <!-- 定时任务 -->
      <template v-else-if="activeTab === 'tasks'">
        <section v-if="automations.length === 0" class="empty-section">
          <div class="empty-hero">
            <div class="empty-icon" aria-hidden="true">
              <svg width="72" height="72" viewBox="0 0 72 72" fill="none">
                <circle cx="36" cy="36" r="28" stroke="#cbd5e1" stroke-width="2"/>
                <path d="M36 20v16l10 6" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"/>
                <circle cx="52" cy="52" r="10" fill="#f8fafc" stroke="#22c55e" stroke-width="2"/>
                <path d="M48 52l3 3 6-6" stroke="#22c55e" stroke-width="2" stroke-linecap="round"/>
              </svg>
            </div>
            <p class="empty-title">开启你的第一个自动化任务吧</p>
            <el-button type="primary" class="empty-add-btn" @click="openCreate">
              + 添加自动化
            </el-button>
          </div>

          <div class="templates-section">
            <h2 class="templates-heading">自动化任务模板</h2>
            <div class="template-grid">
              <button
                v-for="tpl in AUTOMATION_TEMPLATES"
                :key="tpl.id"
                type="button"
                class="template-card"
                @click="openFromTemplate(tpl)"
              >
                <span :class="templateIconClass(tpl.icon)" aria-hidden="true">
                  <component :is="iconFor(tpl.icon)" />
                </span>
                <span class="template-title">{{ tpl.title }}</span>
                <span class="template-desc">{{ tpl.description }}</span>
              </button>
            </div>
          </div>
        </section>

        <section v-else class="task-list-section">
          <div class="task-toolbar">
            <span class="task-count">共 {{ automations.length }} 个任务</span>
          </div>
          <div class="task-grid">
            <article v-for="item in automations" :key="item.id" class="task-card">
              <div class="task-card-head">
                <h3 class="task-name">{{ item.name }}</h3>
                <span class="status-pill" :data-status="item.status">
                  {{ item.status === 'active' ? '运行中' : '已暂停' }}
                </span>
              </div>
              <p class="task-schedule">{{ scheduleSummary(item) }}</p>
              <p v-if="item.next_run_at" class="task-next">下次：{{ formatTime(item.next_run_at) }}</p>
              <p class="task-prompt">{{ item.prompt }}</p>
              <div class="task-actions">
                <el-button link type="primary" :loading="testingId === item.id" @click="onTestRun(item)">
                  立即测试
                </el-button>
                <el-button link type="primary" @click="openEdit(item)">编辑</el-button>
                <el-button link @click="togglePause(item)">
                  {{ item.status === 'active' ? '暂停' : '恢复' }}
                </el-button>
                <el-button link type="danger" @click="onDelete(item)">删除</el-button>
              </div>
            </article>
          </div>

          <div class="templates-section templates-section--compact">
            <h2 class="templates-heading">从模板快速创建</h2>
            <div class="template-grid template-grid--compact">
              <button
                v-for="tpl in AUTOMATION_TEMPLATES"
                :key="tpl.id"
                type="button"
                class="template-card template-card--compact"
                @click="openFromTemplate(tpl)"
              >
                <span :class="templateIconClass(tpl.icon)" aria-hidden="true">
                  <component :is="iconFor(tpl.icon)" />
                </span>
                <span class="template-title">{{ tpl.title }}</span>
              </button>
            </div>
          </div>
        </section>
      </template>

      <!-- 运行记录 -->
      <template v-else>
        <section v-if="runsTotal === 0 && !runsLoading" class="runs-empty">
          <p class="empty-title">暂无运行记录</p>
          <p class="runs-hint">调度执行器接入后，每次自动运行会在此展示摘要与状态。</p>
        </section>
        <div v-else class="runs-list-wrap">
          <div class="runs-list-toolbar">
            <span class="runs-total">共 {{ runsTotal }} 条记录</span>
          </div>
          <el-table
            v-loading="runsLoading"
            :data="runs"
            stripe
            row-key="id"
            style="width: 100%"
            :row-class-name="runRowClassName"
            @row-click="selectRun"
          >
            <el-table-column prop="automation_name" label="任务" min-width="180" show-overflow-tooltip />
            <el-table-column label="状态" width="88">
              <template #default="{ row }">
                <span class="run-status" :data-status="row.status">{{ runStatusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="推送" width="88">
              <template #default="{ row }">
                <span
                  v-if="row.delivery_status"
                  class="run-delivery"
                  :data-delivery="row.delivery_status"
                  :title="row.delivery_error || ''"
                >
                  {{ deliveryStatusLabel(row.delivery_status) }}
                </span>
                <span v-else class="run-delivery run-delivery--none">—</span>
              </template>
            </el-table-column>
            <el-table-column label="写表" width="88">
              <template #default="{ row }">
                <span
                  v-if="row.bitable_status"
                  class="run-delivery"
                  :data-delivery="row.bitable_status"
                  :title="row.bitable_error || ''"
                >
                  {{ bitableStatusLabel(row.bitable_status) }}
                </span>
                <span v-else class="run-delivery run-delivery--none">—</span>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="180">
              <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="摘要预览" min-width="240">
              <template #default="{ row }">
                <span class="run-summary-preview">{{ summaryPreview(row.summary) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-if="runsTotal > 0" class="runs-pager">
            <el-pagination
              v-model:current-page="runsPage"
              :page-size="RUNS_PAGE_SIZE"
              layout="total, prev, pager, next"
              :total="runsTotal"
              @current-change="onRunsPageChange"
            />
          </div>
        </div>
      </template>
    </div>

    <el-drawer
      v-model="runDrawerOpen"
      :title="selectedRun?.automation_name || '运行详情'"
      direction="rtl"
      size="40%"
      append-to-body
      destroy-on-close
      class="run-detail-drawer"
      @closed="onRunDrawerClosed"
    >
      <template v-if="selectedRun">
        <div class="run-drawer-meta">
          <span class="run-status" :data-status="selectedRun.status">
            {{ runStatusLabel(selectedRun.status) }}
          </span>
          <span>开始：{{ formatTime(selectedRun.started_at) }}</span>
          <span v-if="selectedRun.finished_at">结束：{{ formatTime(selectedRun.finished_at) }}</span>
          <span
            v-if="selectedRun.delivery_status"
            class="run-delivery"
            :data-delivery="selectedRun.delivery_status"
            :title="selectedRun.delivery_error || ''"
          >
            推送：{{ deliveryStatusLabel(selectedRun.delivery_status) }}
          </span>
        </div>
        <div class="run-drawer-body">
          <p v-if="selectedRun.error" class="run-detail-error">{{ selectedRun.error }}</p>
          <AutomationRunDetail
            v-if="selectedRun.summary"
            :summary="selectedRun.summary"
            :automation-name="selectedRun.automation_name"
          />
          <p v-else-if="!selectedRun.error" class="run-detail-empty">暂无摘要内容</p>
        </div>
      </template>
    </el-drawer>

    <AutomationEditDialog
      v-model="editOpen"
      :initial="editInitial"
      :saving="saving"
      @save="onSave"
    />
  </div>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AutomationEditDialog from '../components/AutomationEditDialog.vue'
import AutomationRunDetail from '../components/AutomationRunDetail.vue'
import {
  AUTOMATION_TEMPLATES,
  scheduleSummary,
  templateIconClass,
} from '../automationTemplates.js'
import { summaryPreviewText } from '../automationRunSummary.js'
import {
  createAutomation,
  deleteAutomation,
  fetchAutomationRuns,
  fetchAutomations,
  runAutomation,
  updateAutomation,
} from '../api.js'

const activeTab = ref('tasks')
const loading = ref(false)
const error = ref('')
const automations = ref([])
const runs = ref([])
const runsTotal = ref(0)
const runsPage = ref(1)
const runsLoading = ref(false)
const RUNS_PAGE_SIZE = 10
const selectedRun = ref(null)
const runDrawerOpen = ref(false)
const editOpen = ref(false)
const editInitial = ref(null)
const saving = ref(false)
const testingId = ref('')

function iconFor(key) {
  const icons = {
    news: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('rect', { x: 3, y: 4, width: 14, height: 12, rx: 2, stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M6 8h8M6 11h5', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    report: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('path', { d: 'M5 4h10v12H5z', stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M7.5 12V9M10 12V7M12.5 12v-4', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    language: () =>
      h('span', { class: 'tpl-text-icon' }, 'A/文'),
    calendar: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('rect', { x: 3, y: 5, width: 14, height: 12, rx: 2, stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M3 8h14M7 3v3M13 3v3', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    contact: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('circle', { cx: 10, cy: 7, r: 3, stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    health: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('rect', { x: 4, y: 6, width: 12, height: 10, rx: 2, stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M10 9v4M8 11h4', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    meeting: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('path', { d: 'M4 6h12v8H4z', stroke: 'currentColor', 'stroke-width': 1.4 }),
        h('path', { d: 'M7 10h6M7 12.5h4', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round' }),
      ]),
    mes: () =>
      h('svg', { width: 20, height: 20, viewBox: '0 0 20 20', fill: 'none' }, [
        h('path', { d: 'M3 15l4-8 3 5 3-3 4 6', stroke: 'currentColor', 'stroke-width': 1.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
      ]),
  }
  return icons[key] || icons.report
}

function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(Number(ts) * 1000)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN')
}

function runStatusLabel(status) {
  const map = {
    pending: '等待中',
    running: '运行中',
    succeeded: '成功',
    failed: '失败',
  }
  return map[status] || status || '—'
}

function deliveryStatusLabel(status) {
  const map = {
    sent: '已推送',
    failed: '失败',
    skipped: '未推送',
  }
  return map[status] || status || '—'
}

function bitableStatusLabel(status) {
  const map = {
    sent: '已写入',
    failed: '失败',
    skipped: '未写表',
  }
  return map[status] || status || '—'
}

function selectRun(row) {
  selectedRun.value = row
  runDrawerOpen.value = true
}

function onRunDrawerClosed() {
  selectedRun.value = null
}

function summaryPreview(text) {
  return summaryPreviewText(text)
}

function runRowClassName({ row }) {
  return row.id === selectedRun.value?.id && runDrawerOpen.value ? 'run-row-selected' : ''
}

async function loadRuns() {
  runsLoading.value = true
  try {
    const runsResp = await fetchAutomationRuns(runsPage.value, RUNS_PAGE_SIZE)
    runs.value = runsResp.data?.items || []
    runsTotal.value = Number(runsResp.data?.total) || 0
    if (selectedRun.value) {
      const hit = runs.value.find((r) => r.id === selectedRun.value.id)
      selectedRun.value = hit || null
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    runsLoading.value = false
  }
}

function onRunsPageChange(page) {
  runsPage.value = page
  loadRuns()
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const autoResp = await fetchAutomations()
    automations.value = autoResp.data?.items || []
    await loadRuns()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editInitial.value = null
  editOpen.value = true
}

function openEdit(item) {
  editInitial.value = { ...item }
  editOpen.value = true
}

function openFromTemplate(tpl) {
  editInitial.value = {
    name: tpl.title,
    prompt: tpl.prompt,
    schedule_type: tpl.schedule_type,
    rrule: tpl.rrule || '',
    scheduled_at: tpl.scheduled_at || null,
    scheduleLabel: tpl.scheduleLabel,
    cwds: [],
    push_to_wecom: Boolean(tpl.push_to_wecom),
  }
  editOpen.value = true
}

async function onSave(payload) {
  saving.value = true
  try {
    if (editInitial.value?.id) {
      await updateAutomation(editInitial.value.id, payload)
      ElMessage.success('已保存')
    } else {
      await createAutomation(payload)
      ElMessage.success('已创建')
    }
    editOpen.value = false
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function togglePause(item) {
  const next = item.status === 'active' ? 'paused' : 'active'
  try {
    await updateAutomation(item.id, { status: next })
    ElMessage.success(next === 'active' ? '已恢复' : '已暂停')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '操作失败')
  }
}

async function onTestRun(item) {
  testingId.value = item.id
  try {
    const resp = await runAutomation(item.id)
    const data = resp.data || {}
    if (data.skipped && data.reason === 'stream_busy') {
      ElMessage.warning('当前有对话在进行，请稍后再试')
    } else if (data.ok) {
      ElMessage.success('执行完成，请到「运行记录」查看摘要')
      runsPage.value = 1
    } else {
      ElMessage.error(data.error || '执行失败')
    }
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '执行失败')
  } finally {
    testingId.value = ''
  }
}

async function onDelete(item) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.name}」？`, '删除任务', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteAutomation(item.id)
    ElMessage.success('已删除')
    await loadAll()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
  }
}

onMounted(loadAll)
</script>

<style scoped>
.automations-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
  flex-shrink: 0;
}

.header-tabs {
  display: flex;
  gap: 4px;
}

.header-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 14px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.header-tab:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.header-tab.active {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-weight: 600;
}

.add-btn {
  flex-shrink: 0;
}

.page-body {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.loading-state {
  text-align: center;
  color: var(--text-tertiary);
  padding: 48px;
}

.error-card {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 13px;
}

.empty-section {
  max-width: 960px;
  margin: 0 auto;
}

.empty-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 48px 16px 40px;
}

.empty-icon {
  margin-bottom: 16px;
  opacity: 0.9;
}

.empty-title {
  font-size: 15px;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.empty-add-btn {
  min-width: 140px;
}

.templates-section {
  margin-top: 8px;
}

.templates-section--compact {
  margin-top: 32px;
}

.templates-heading {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.template-grid--compact {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.template-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 16px;
  text-align: left;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
  cursor: pointer;
  font-family: inherit;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.template-card:hover {
  border-color: var(--brand);
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.template-card--compact {
  padding: 12px;
}

.template-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.template-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tpl-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.tpl-icon--news { color: #2563eb; background: #eff6ff; }
.tpl-icon--report { color: #7c3aed; background: #f5f3ff; }
.tpl-icon--language { color: #059669; background: #ecfdf5; }
.tpl-icon--calendar { color: #d97706; background: #fffbeb; }
.tpl-icon--contact { color: #db2777; background: #fdf2f8; }
.tpl-icon--health { color: #0891b2; background: #ecfeff; }
.tpl-icon--meeting { color: #4f46e5; background: #eef2ff; }
.tpl-icon--mes { color: #0d9488; background: #f0fdfa; }

:deep(.tpl-text-icon) {
  font-size: 11px;
  font-weight: 700;
}

.task-list-section {
  max-width: 960px;
  margin: 0 auto;
}

.task-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.task-count {
  font-size: 13px;
  color: var(--text-tertiary);
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.task-card {
  padding: 16px;
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  background: var(--bg-primary);
}

.task-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.task-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.status-pill {
  flex-shrink: 0;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.status-pill[data-status='active'] {
  background: #ecfdf5;
  color: #166534;
}

.task-schedule {
  font-size: 12px;
  color: var(--brand);
  margin-bottom: 4px;
}

.task-next {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.task-prompt {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 12px;
}

.task-actions {
  display: flex;
  gap: 4px;
}

.runs-empty {
  text-align: center;
  padding: 64px 16px;
}

.runs-hint {
  margin-top: 8px;
  font-size: 13px;
  color: var(--text-tertiary);
}

.runs-list-wrap {
  width: 80%;
  max-width: 1280px;
  margin: 0 auto;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
  padding: 16px 20px 12px;
}

.runs-list-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.runs-total {
  font-size: 13px;
  color: var(--text-tertiary);
}

.runs-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--border-secondary);
}

.runs-list-wrap :deep(.el-table__row) {
  cursor: pointer;
}

.runs-list-wrap :deep(.run-row-selected > td.el-table__cell) {
  background: var(--brand-light) !important;
}

.run-summary-preview {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-delivery {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-tertiary);
}

.run-delivery[data-delivery='sent'] {
  color: #16a34a;
}

.run-delivery[data-delivery='failed'] {
  color: #dc2626;
}

.run-delivery[data-delivery='skipped'] {
  color: var(--text-tertiary);
}

.run-delivery--none {
  font-weight: 400;
  color: var(--text-tertiary);
}

.run-drawer-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-bottom: 4px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-secondary);
  font-size: 12px;
  color: var(--text-tertiary);
}

.run-drawer-meta .run-status {
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  background: var(--bg-tertiary);
}

.run-drawer-meta .run-status[data-status='succeeded'] {
  background: #ecfdf5;
}

.run-drawer-meta .run-status[data-status='failed'] {
  background: #fef2f2;
}

.run-drawer-meta .run-status[data-status='running'] {
  background: #eff6ff;
}

.run-drawer-body {
  overflow-y: auto;
  padding-top: 8px;
}

:deep(.run-detail-drawer .el-drawer__body) {
  padding-top: 8px;
}

.run-detail-error {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 13px;
  line-height: 1.5;
}

.run-detail-empty {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}

.run-status[data-status='succeeded'] { color: #166534; }
.run-status[data-status='failed'] { color: #dc2626; }
.run-status[data-status='running'] { color: #2563eb; }

@media (max-width: 900px) {
  .runs-list-wrap {
    width: 100%;
  }
}

@media (max-width: 900px) {
  .template-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .template-grid--compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .task-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .template-grid,
  .template-grid--compact {
    grid-template-columns: 1fr;
  }
  .page-header {
    flex-wrap: wrap;
  }
}
</style>
