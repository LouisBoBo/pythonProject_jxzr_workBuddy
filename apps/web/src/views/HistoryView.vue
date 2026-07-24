<template>
  <div class="history-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">历史会话</h1>
        <p class="page-sub">查看、继续或删除本地保存的对话记录</p>
      </div>
    </header>

    <div class="history-content">
      <div v-if="loading" class="loading-state">
        <el-icon class="loading-icon" :size="20"><Loading /></el-icon>
        <span>加载中...</span>
      </div>

      <div v-else-if="list.length === 0" class="empty-state">
        <div class="empty-icon">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="20" stroke="#cbd5e1" stroke-width="2"/>
            <path d="M24 14v10M24 28v1" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <p>暂无历史记录</p>
        <p class="empty-hint">在对话中发送消息后，会话会自动保存到本地数据库</p>
      </div>

      <template v-else>
        <div class="history-list">
          <div
            v-for="item in list"
            :key="item.id"
            :class="['history-item', { selected: selected?.id === item.id }]"
            @click="selectItem(item)"
          >
            <div class="item-header">
              <span class="item-title">{{ item.title }}</span>
              <span class="item-time">{{ formatTime(item.updated_at) }}</span>
            </div>
            <div class="item-id">会话 ID: {{ item.id.slice(0, 12) }}...</div>
          </div>
        </div>

        <div v-if="selected" class="detail-panel">
          <div class="detail-header">
            <h3>{{ selected.title }}</h3>
            <div class="detail-actions">
              <el-button size="small" type="primary" @click="continueChat(selected.id)">
                继续对话
              </el-button>
              <el-button text size="small" type="danger" @click="doDelete(selected.id)">
                <el-icon :size="14"><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </div>
          <div class="detail-messages">
            <div v-if="detailLoading" class="loading-state">
              <el-icon class="loading-icon" :size="16"><Loading /></el-icon>
            </div>
            <div v-for="(msg, i) in detailMessages" :key="i" :class="['detail-msg', msg.role]">
              <span class="detail-role">{{ msg.role === 'user' ? '你' : 'AI' }}</span>
              <div class="detail-text">{{ msg.content }}</div>
            </div>
          </div>
        </div>

        <div v-else class="detail-panel detail-placeholder">
          <p>选择左侧会话查看详情</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Loading, Delete } from '@element-plus/icons-vue'
import { getHistoryList, getHistoryDetail, deleteHistory } from '../api.js'

const router = useRouter()
const list = ref([])
const selected = ref(null)
const detailMessages = ref([])
const loading = ref(false)
const detailLoading = ref(false)

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = now - d
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前'
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

async function loadList() {
  loading.value = true
  try {
    const resp = await getHistoryList()
    list.value = resp.data || []
  } catch (e) {
    list.value = []
  } finally {
    loading.value = false
  }
}

async function selectItem(item) {
  selected.value = item
  detailLoading.value = true
  try {
    const resp = await getHistoryDetail(item.id)
    detailMessages.value = resp.data.messages || []
  } catch (e) {
    detailMessages.value = []
  } finally {
    detailLoading.value = false
  }
}

function continueChat(id) {
  router.push({ path: '/', query: { thread: id } })
}

async function doDelete(id) {
  try {
    await ElMessageBox.confirm('确定删除该会话？删除后无法恢复。', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  try {
    await deleteHistory(id)
    list.value = list.value.filter(i => i.id !== id)
    if (selected.value?.id === id) {
      selected.value = null
      detailMessages.value = []
    }
  } catch (e) {
    // ignore
  }
}

onMounted(loadList)
</script>

<style scoped>
.history-view {
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

.history-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.history-list {
  width: 300px;
  min-width: 300px;
  border-right: 1px solid var(--border-primary);
  overflow-y: auto;
  background: var(--bg-primary);
}

.history-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-secondary);
  transition: background 0.1s;
}

.history-item:hover {
  background: var(--bg-tertiary);
}

.history-item.selected {
  background: var(--brand-light);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 200px;
}

.item-time {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.item-id {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.detail-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  min-width: 0;
}

.detail-placeholder {
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

.detail-header {
  padding: 12px 20px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.detail-header h3 {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.detail-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.detail-msg {
  margin-bottom: 14px;
}

.detail-role {
  font-size: 11px;
  font-weight: 500;
  color: var(--brand);
  display: block;
  margin-bottom: 4px;
}

.detail-msg.user .detail-role {
  color: var(--text-tertiary);
}

.detail-text {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
  background: var(--bg-primary);
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-secondary);
  white-space: pre-wrap;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 200px;
  width: 100%;
  color: var(--text-tertiary);
  font-size: 13px;
}

.empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
