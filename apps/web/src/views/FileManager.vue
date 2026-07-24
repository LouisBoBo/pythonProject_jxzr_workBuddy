<template>
  <div class="file-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">文件管理</h1>
        <p class="page-sub">常用文档格式互转：上传后一键生成多种格式，点击即可下载到本地</p>
      </div>
    </header>

    <div class="file-content">
      <div class="format-chips">
        <span v-for="f in formatList" :key="f" class="format-chip">{{ f }}</span>
      </div>

      <div
        class="upload-zone"
        :class="{ dragging, converting }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="handleDrop"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".csv,.tsv,.xlsx,.xls,.json,.md,.txt,.html,.htm"
          style="display:none"
          @change="handleFileSelect"
        />
        <div class="upload-icon">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
            <rect x="2" y="2" width="36" height="36" rx="10" stroke="#cbd5e1" stroke-width="1.5" stroke-dasharray="6 4"/>
            <path d="M16 22l4-4 4 4M20 18v10" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <p class="upload-text">
          <template v-if="converting">正在转换，请稍候…</template>
          <template v-else>
            拖拽文件到此处，或
            <button class="upload-link" @click="$refs.fileInput.click()">点击选择</button>
          </template>
        </p>
        <p class="upload-hint">支持 CSV、TSV、Excel、JSON、Markdown、TXT、HTML，单文件最大 50MB</p>
        <p class="upload-hint">上传成功后将自动生成其它格式，点击对应卡片即可下载到电脑</p>
      </div>

      <div v-if="error" class="error-card">{{ error }}</div>

      <div v-if="result" class="result-section">
        <div class="source-card">
          <div class="source-main">
            <el-icon :size="18" color="#4f46e5"><Document /></el-icon>
            <div class="source-text">
              <div class="source-name">{{ result.original.filename }}</div>
              <div class="source-meta">
                源格式 .{{ result.original.extension }}
                · {{ formatSize(result.original.size) }}
                · {{ result.original.rows }} 行
                · {{ result.converted_count }} 种格式已生成
              </div>
            </div>
          </div>
          <el-button size="small" @click="reset">重新上传</el-button>
        </div>

        <h2 class="section-title">可下载格式</h2>
        <div class="convert-grid">
          <a
            v-for="item in successItems"
            :key="item.format"
            class="convert-card"
            :href="item.download_url"
            :download="item.filename"
            target="_blank"
            rel="noopener"
          >
            <div class="convert-badge">.{{ item.format }}</div>
            <div class="convert-label">{{ item.label }}</div>
            <div class="convert-desc">{{ item.desc }}</div>
            <div class="convert-footer">
              <span>{{ formatSize(item.size) }}</span>
              <span class="download-hint">
                <el-icon :size="14"><Download /></el-icon>
                下载到本地
              </span>
            </div>
          </a>
        </div>

        <div v-if="failedItems.length" class="failed-list">
          <div v-for="item in failedItems" :key="item.format" class="failed-item">
            {{ item.label }} 转换失败：{{ item.error }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Document, Download } from '@element-plus/icons-vue'
import { convertDocument } from '../api.js'

const formatList = ['CSV', 'Excel', 'JSON', 'TSV', 'Markdown', 'TXT', 'HTML']

const fileInput = ref(null)
const dragging = ref(false)
const converting = ref(false)
const error = ref('')
const result = ref(null)

const successItems = computed(() =>
  (result.value?.conversions || []).filter(i => i.status === 'ok')
)
const failedItems = computed(() =>
  (result.value?.conversions || []).filter(i => i.status === 'error')
)

function formatSize(bytes) {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}

function reset() {
  result.value = null
  error.value = ''
  converting.value = false
  if (fileInput.value) fileInput.value.value = ''
}

async function handleFile(f) {
  if (!f) return
  error.value = ''
  result.value = null
  converting.value = true
  try {
    const resp = await convertDocument(f)
    result.value = resp.data
    if (!resp.data.converted_count) {
      error.value = '未能生成可用格式，请检查文件内容'
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '转换失败'
  } finally {
    converting.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

function handleDrop(e) {
  dragging.value = false
  if (converting.value) return
  const files = e.dataTransfer.files
  if (files.length > 0) handleFile(files[0])
}

function handleFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) handleFile(files[0])
}
</script>

<style scoped>
.file-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
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

.file-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.format-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.format-chip {
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  font-size: 12px;
  color: var(--text-secondary);
}

.upload-zone {
  border: 2px dashed var(--border-primary);
  border-radius: var(--radius-xl);
  padding: 40px;
  text-align: center;
  transition: all 0.2s;
  background: var(--bg-primary);
}

.upload-zone.dragging {
  border-color: var(--brand);
  background: var(--brand-light);
}

.upload-zone.converting {
  opacity: 0.75;
  pointer-events: none;
}

.upload-icon {
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: var(--text-primary);
}

.upload-link {
  color: var(--brand);
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-family: inherit;
}

.upload-link:hover {
  text-decoration: underline;
}

.upload-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 6px;
}

.error-card {
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 13px;
}

.result-section {
  margin-top: 20px;
}

.source-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
}

.source-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.source-text {
  min-width: 0;
}

.source-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-meta {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.section-title {
  margin: 20px 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.convert-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.convert-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}

.convert-card:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.convert-badge {
  display: inline-flex;
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-light);
  color: var(--brand);
  font-size: 11px;
  font-weight: 600;
}

.convert-label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.convert-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  flex: 1;
}

.convert-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.download-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--brand);
  font-weight: 500;
}

.failed-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.failed-item {
  font-size: 12px;
  color: var(--danger);
}
</style>
