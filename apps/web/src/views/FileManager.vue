<template>
  <div class="file-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">文件管理</h1>
        <p class="page-sub">上传与管理文档，查找与状态一目了然</p>
      </div>
      <el-button type="primary" :loading="uploading" @click="openFilePicker">
        上传文件
      </el-button>
      <input
        ref="fileInput"
        type="file"
        :accept="acceptTypes"
        style="display:none"
        @change="handleFileSelect"
      />
    </header>

    <div class="file-body">
      <div class="stat-row">
        <div v-for="card in statCards" :key="card.key" class="stat-card">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :class="card.tone">{{ card.value }}</div>
        </div>
      </div>

      <div class="toolbar">
        <el-input
          v-model="searchQuery"
          clearable
          placeholder="搜索文件名"
          class="search-input"
          @clear="reloadList"
          @keyup.enter="reloadList"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <div class="status-tabs">
          <button
            v-for="tab in statusTabs"
            :key="tab.value"
            type="button"
            class="status-tab"
            :class="{ active: statusFilter === tab.value }"
            @click="setStatusFilter(tab.value)"
          >
            {{ tab.label }}
          </button>
        </div>

        <el-select v-model="typeFilter" class="type-select" @change="reloadList">
          <el-option
            v-for="opt in typeOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
      </div>

      <div v-if="error" class="error-card">{{ error }}</div>

      <div class="table-wrap">
        <el-table
          v-loading="loading"
          :data="displayItems"
          empty-text="暂无文件，点击右上角上传"
          stripe
          style="width: 100%"
        >
          <el-table-column label="文件" min-width="220">
            <template #default="{ row }">
              <div class="file-cell">
                <el-icon :size="16" color="#64748b"><Document /></el-icon>
                <span class="file-name" :title="row.filename">{{ row.filename }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <span class="type-tag">.{{ row.extension }}</span>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">
              {{ formatSize(row.size) }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <span class="status-pill" :data-status="row.status">
                <i class="status-dot" />
                {{ statusLabel(row.status) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="上传时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.uploaded_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <template v-if="row.status === 'uploading'">
                <span class="muted-text">上传中…</span>
              </template>
              <template v-else-if="row.status === 'failed'">
                <span class="fail-text" :title="row.error">失败</span>
              </template>
              <template v-else>
                <el-button
                  v-if="row.previewable"
                  link
                  type="primary"
                  @click="openPreview(row)"
                >
                  查看
                </el-button>
                <el-button link type="primary" @click="downloadFile(row)">下载</el-button>
              </template>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="displayTotal > pageSize" class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          layout="total, prev, pager, next"
          :total="displayTotal"
          @current-change="reloadList"
        />
      </div>
    </div>

    <el-drawer
      v-model="previewOpen"
      :title="previewItem?.filename || '文件预览'"
      size="520px"
      destroy-on-close
    >
      <div v-if="previewLoading" class="preview-loading">加载中…</div>
      <div v-else-if="previewError" class="error-card">{{ previewError }}</div>
      <template v-else>
        <p v-if="previewTruncated" class="preview-hint">内容较长，仅展示前 100KB</p>
        <pre class="preview-content">{{ previewContent }}</pre>
        <div class="preview-actions">
          <el-button type="primary" @click="downloadFile(previewItem)">下载</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Document, Search } from '@element-plus/icons-vue'
import { authHeaders } from '../auth.js'
import {
  fetchFileManagerList,
  fetchFileManagerPreview,
  fetchFileManagerSummary,
  fileManagerDownloadPath,
  uploadManagerFile,
} from '../api.js'

const acceptTypes = [
  '.pdf', '.doc', '.docx', '.dot', '.dotx', '.rtf', '.odt',
  '.txt', '.md', '.markdown',
  '.xls', '.xlsx', '.xlsm', '.csv', '.tsv', '.ods',
  '.ppt', '.pptx', '.odp',
  '.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tif', '.tiff', '.svg',
  '.json', '.xml', '.yaml', '.yml', '.html', '.htm',
  '.zip', '.rar', '.7z',
].join(',')

const statusTabs = [
  { label: '全部', value: 'all' },
  { label: '正常', value: 'ok' },
  { label: '上传中', value: 'uploading' },
  { label: '失败', value: 'failed' },
]

const typeOptions = [
  { label: '全部类型', value: 'all' },
  { label: '文档', value: 'document' },
  { label: '表格', value: 'spreadsheet' },
  { label: '演示', value: 'presentation' },
  { label: '图片', value: 'image' },
  { label: '数据/网页', value: 'data' },
  { label: '压缩包', value: 'archive' },
  { label: '其它', value: 'other' },
]

const fileInput = ref(null)
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const items = ref([])
const pendingItems = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const searchQuery = ref('')
const statusFilter = ref('all')
const typeFilter = ref('all')
const summary = ref({ total: 0, ok: 0, failed: 0 })

const previewOpen = ref(false)
const previewItem = ref(null)
const previewContent = ref('')
const previewTruncated = ref(false)
const previewLoading = ref(false)
const previewError = ref('')

const statCards = computed(() => {
  const uploadingCount = pendingItems.value.filter(i => i.status === 'uploading').length
  const failedCount = pendingItems.value.filter(i => i.status === 'failed').length + Number(summary.value.failed || 0)
  return [
    { key: 'total', label: '总文件', value: summary.value.total + uploadingCount, tone: '' },
    { key: 'ok', label: '正常', value: summary.value.ok, tone: 'ok' },
    { key: 'uploading', label: '上传中', value: uploadingCount, tone: 'pending' },
    { key: 'failed', label: '失败', value: failedCount, tone: 'fail' },
  ]
})

const displayItems = computed(() => {
  const serverItems = items.value.map(i => ({ ...i }))
  const local = pendingItems.value.filter(p => {
    if (statusFilter.value !== 'all' && p.status !== statusFilter.value) return false
    if (typeFilter.value !== 'all' && p.category !== typeFilter.value) return false
    const q = searchQuery.value.trim().toLowerCase()
    if (q && !String(p.filename || '').toLowerCase().includes(q)) return false
    return true
  })
  if (statusFilter.value === 'uploading' || statusFilter.value === 'failed') {
    return local
  }
  if (page.value === 1) {
    return [...local, ...serverItems]
  }
  return serverItems
})

const displayTotal = computed(() => {
  if (statusFilter.value === 'uploading' || statusFilter.value === 'failed') {
    return pendingItems.value.filter(i => i.status === statusFilter.value).length
  }
  const localOnPage1 = page.value === 1
    ? pendingItems.value.filter(p => {
        if (statusFilter.value !== 'all' && p.status !== statusFilter.value) return false
        if (typeFilter.value !== 'all' && p.category !== typeFilter.value) return false
        const q = searchQuery.value.trim().toLowerCase()
        if (q && !String(p.filename || '').toLowerCase().includes(q)) return false
        return true
      }).length
    : 0
  return total.value + localOnPage1
})

function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

function formatTime(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function statusLabel(status) {
  if (status === 'uploading') return '上传中'
  if (status === 'failed') return '失败'
  return '正常'
}

function openFilePicker() {
  if (uploading.value) return
  fileInput.value?.click()
}

function setStatusFilter(value) {
  statusFilter.value = value
  page.value = 1
  reloadList()
}

async function reloadSummary() {
  try {
    const resp = await fetchFileManagerSummary()
    summary.value = resp.data || { total: 0, ok: 0, failed: 0 }
  } catch {
    /* keep previous */
  }
}

async function reloadList() {
  if (statusFilter.value === 'uploading' || statusFilter.value === 'failed') {
    loading.value = false
    total.value = pendingItems.value.filter(i => i.status === statusFilter.value).length
    return
  }
  loading.value = true
  error.value = ''
  try {
    const resp = await fetchFileManagerList({
      q: searchQuery.value.trim() || undefined,
      status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      type: typeFilter.value === 'all' ? undefined : typeFilter.value,
      page: page.value,
      page_size: pageSize,
    })
    items.value = resp.data?.items || []
    total.value = resp.data?.total || 0
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  await Promise.all([reloadSummary(), reloadList()])
}

function guessCategory(name) {
  const ext = String(name || '').split('.').pop()?.toLowerCase() || ''
  const map = {
    document: ['pdf', 'doc', 'docx', 'dot', 'dotx', 'rtf', 'odt', 'txt', 'md', 'markdown'],
    spreadsheet: ['xls', 'xlsx', 'xlsm', 'csv', 'tsv', 'ods'],
    presentation: ['ppt', 'pptx', 'odp'],
    image: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff', 'svg'],
    archive: ['zip', 'rar', '7z'],
    data: ['json', 'xml', 'yaml', 'yml', 'html', 'htm'],
  }
  for (const [cat, exts] of Object.entries(map)) {
    if (exts.includes(ext)) return cat
  }
  return 'other'
}

async function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (fileInput.value) fileInput.value.value = ''
  if (!file) return
  await uploadOne(file)
}

async function uploadOne(file) {
  const tempId = `pending-${Date.now()}-${Math.random().toString(16).slice(2)}`
  const pending = {
    id: tempId,
    filename: file.name,
    extension: file.name.split('.').pop()?.toLowerCase() || '',
    category: guessCategory(file.name),
    size: file.size,
    status: 'uploading',
    uploaded_at: new Date().toISOString(),
    previewable: false,
  }
  pendingItems.value = [pending, ...pendingItems.value]
  uploading.value = true
  error.value = ''
  try {
    await uploadManagerFile(file)
    pendingItems.value = pendingItems.value.filter(i => i.id !== tempId)
    page.value = 1
    statusFilter.value = 'all'
    await refreshAll()
  } catch (e) {
    pending.status = 'failed'
    pending.error = e.response?.data?.detail || e.message || '上传失败'
    pendingItems.value = pendingItems.value.map(i => (i.id === tempId ? { ...pending } : i))
    error.value = pending.error
  } finally {
    uploading.value = false
  }
}

async function downloadFile(row) {
  if (!row?.id || String(row.id).startsWith('pending-')) return
  try {
    const resp = await fetch(fileManagerDownloadPath(row.id), { headers: authHeaders() })
    if (!resp.ok) {
      const detail = await resp.text()
      throw new Error(detail || '下载失败')
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = row.filename || 'download'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e.message || '下载失败'
  }
}

async function openPreview(row) {
  previewItem.value = row
  previewOpen.value = true
  previewContent.value = ''
  previewTruncated.value = false
  previewError.value = ''
  previewLoading.value = true
  try {
    const resp = await fetchFileManagerPreview(row.id)
    previewContent.value = resp.data?.content || ''
    previewTruncated.value = Boolean(resp.data?.truncated)
  } catch (e) {
    previewError.value = e.response?.data?.detail || e.message || '预览失败'
  } finally {
    previewLoading.value = false
  }
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.file-view {
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
  padding: 16px 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
  flex-shrink: 0;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.page-sub {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.file-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px 24px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  padding: 14px 16px;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.stat-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-value.ok {
  color: var(--success);
}

.stat-value.pending {
  color: var(--brand);
}

.stat-value.fail {
  color: var(--danger);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.search-input {
  width: 240px;
}

.status-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.status-tab {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-primary);
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
}

.status-tab.active {
  border-color: var(--brand);
  background: var(--brand-light);
  color: var(--brand);
}

.type-select {
  width: 140px;
}

.error-card {
  margin-bottom: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 13px;
}

.table-wrap {
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.type-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-size: 12px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
}

.status-pill[data-status='uploading'] .status-dot {
  background: var(--brand);
}

.status-pill[data-status='failed'] .status-dot {
  background: var(--danger);
}

.muted-text {
  font-size: 12px;
  color: var(--text-tertiary);
}

.fail-text {
  font-size: 12px;
  color: var(--danger);
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.preview-loading {
  color: var(--text-tertiary);
  font-size: 13px;
}

.preview-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.preview-content {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.5;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: 12px;
  max-height: 60vh;
  overflow: auto;
}

.preview-actions {
  margin-top: 16px;
}

@media (max-width: 900px) {
  .stat-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
