<template>
  <div v-if="isLoginRoute" class="login-shell">
    <router-view />
  </div>
  <div v-else :class="['app-shell', { 'is-embed': embedMode }]">
    <aside v-if="!embedMode" class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="8" fill="#4f46e5"/>
            <path d="M7 10h14M7 14h10M7 18h12" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="brand-text">
          <span class="brand-name">MES Agent</span>
          <span class="brand-tag">PCB 智能运维</span>
        </div>
      </div>

      <div class="sidebar-top">
        <button class="new-chat-btn" @click="goNewChat">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.4"/>
            <path d="M8 5v6M5 8h6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>
          </svg>
          <span>开启新对话</span>
        </button>
      </div>

      <div class="history-scroll">
        <div v-if="historyLoading" class="history-empty">加载中...</div>
        <div v-else-if="groupedHistory.length === 0" class="history-empty">暂无历史会话</div>
        <div v-else class="history-groups">
          <section v-for="group in groupedHistory" :key="group.label" class="history-group">
            <div class="group-label">{{ group.label }}</div>
            <div
              v-for="item in group.items"
              :key="item.id"
              :class="['history-item', { active: isActiveSession(item.id) }]"
              @click="openSession(item.id)"
            >
              <span class="history-title">{{ item.title || '未命名会话' }}</span>
              <el-dropdown
                trigger="click"
                @command="(cmd) => onSessionCommand(cmd, item)"
              >
                <button
                  class="history-more"
                  type="button"
                  title="更多"
                  @click.stop
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <circle cx="3" cy="7" r="1.2" fill="currentColor"/>
                    <circle cx="7" cy="7" r="1.2" fill="currentColor"/>
                    <circle cx="11" cy="7" r="1.2" fill="currentColor"/>
                  </svg>
                </button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="delete" style="color: #dc2626">删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </section>
        </div>
      </div>

      <div class="sidebar-footer">
        <router-link to="/files" class="footer-link" active-class="active">
          <el-icon :size="16"><FolderOpened /></el-icon>
          <span>文件管理</span>
        </router-link>
        <div class="user-row">
          <div class="user-meta">
            <span class="user-name">{{ displayName }}</span>
            <span class="user-sub">ERP 已登录</span>
          </div>
          <button type="button" class="logout-btn" title="退出登录" @click="onLogout">退出</button>
        </div>
      </div>
    </aside>

    <main class="main-content">
      <div v-if="embedMode" class="embed-bar">
        <div class="embed-bar-left">
          <span class="embed-brand">MES Agent</span>
          <span v-if="contextLabel" class="embed-ctx">{{ contextLabel }}</span>
        </div>
        <div class="embed-bar-right">
          <span class="embed-user">{{ displayName }}</span>
          <button type="button" class="embed-new" @click="goNewChat">新对话</button>
        </div>
      </div>
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { FolderOpened } from '@element-plus/icons-vue'
import { getHistoryList, deleteHistory } from './api.js'
import { clearSession, getDisplayName, getUsername } from './auth.js'
import { isEmbedMode, pageContextLabel, getPageContext, setEmbedMode, clearPageContext } from './embed.js'

const route = useRoute()
const router = useRouter()

const sessions = ref([])
const historyLoading = ref(false)
const displayName = ref(getDisplayName() || getUsername() || '用户')
const embedMode = ref(isEmbedMode())
const contextLabel = ref(pageContextLabel(getPageContext()))

const isLoginRoute = computed(() => route.name === 'login' || route.path === '/login')
const groupedHistory = computed(() => groupSessions(sessions.value))

function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

function groupSessions(list) {
  const now = new Date()
  const today = startOfDay(now)
  const yesterday = new Date(today.getTime() - 86400000)
  const within30 = new Date(today.getTime() - 30 * 86400000)

  const groups = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '30 天内', items: [] },
    { label: '更早', items: [] },
  ]

  for (const item of list) {
    const t = new Date(item.updated_at)
    if (Number.isNaN(t.getTime())) {
      groups[3].items.push(item)
      continue
    }
    if (t >= today) groups[0].items.push(item)
    else if (t >= yesterday) groups[1].items.push(item)
    else if (t >= within30) groups[2].items.push(item)
    else groups[3].items.push(item)
  }

  return groups.filter(g => g.items.length > 0)
}

function isActiveSession(id) {
  return route.path === '/' && route.query.thread === id
}

async function loadHistory() {
  if (isLoginRoute.value) return
  historyLoading.value = true
  try {
    const resp = await getHistoryList()
    sessions.value = resp.data || []
  } catch {
    sessions.value = []
  } finally {
    historyLoading.value = false
  }
}

function goNewChat() {
  router.push({ path: '/', query: { thread: 'session-' + Date.now() } })
}

function openSession(id) {
  if (route.path === '/' && route.query.thread === id) return
  router.push({ path: '/', query: { thread: id } })
}

async function onSessionCommand(cmd, item) {
  if (cmd !== 'delete') return
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
    await deleteHistory(item.id)
    sessions.value = sessions.value.filter(s => s.id !== item.id)
    if (route.query.thread === item.id) {
      goNewChat()
    }
  } catch {
    // ignore
  }
}

function onLogout() {
  clearSession()
  setEmbedMode(false)
  clearPageContext()
  router.replace('/login')
}

function onHistoryUpdated() {
  loadHistory()
}

watch(isLoginRoute, (v) => {
  if (!v) {
    displayName.value = getDisplayName() || getUsername() || '用户'
    embedMode.value = isEmbedMode()
    contextLabel.value = pageContextLabel(getPageContext())
    loadHistory()
  }
})

onMounted(() => {
  displayName.value = getDisplayName() || getUsername() || '用户'
  embedMode.value = isEmbedMode()
  contextLabel.value = pageContextLabel(getPageContext())
  loadHistory()
  window.addEventListener('mes-history-updated', onHistoryUpdated)
})

onUnmounted(() => {
  window.removeEventListener('mes-history-updated', onHistoryUpdated)
})
</script>

<style scoped>
.login-shell {
  height: 100%;
  overflow: auto;
}

.app-shell {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.sidebar {
  width: 260px;
  min-width: 260px;
  background: #f7f8fa;
  border-right: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  user-select: none;
}

.sidebar-brand {
  padding: 16px 16px 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.brand-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.brand-tag {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: -2px;
}

.sidebar-top {
  padding: 8px 12px 12px;
  flex-shrink: 0;
}

.new-chat-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 14px;
  border: 1px solid #dbe1ea;
  border-radius: 999px;
  background: #fff;
  color: #334155;
  font-size: 14px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
}

.new-chat-btn:hover {
  background: #fff;
  border-color: #c5ceda;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}

.history-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
  min-height: 0;
}

.history-empty {
  padding: 24px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
}

.history-group {
  margin-bottom: 10px;
}

.group-label {
  padding: 8px 10px 6px;
  font-size: 12px;
  color: #94a3b8;
  font-weight: 500;
}

.history-item {
  position: relative;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 9px 10px;
  margin-bottom: 2px;
  border-radius: 10px;
  background: transparent;
  color: #334155;
  font-size: 13.5px;
  cursor: pointer;
  transition: background 0.12s;
}

.history-item:hover {
  background: #eef1f5;
}

.history-item.active {
  background: #e8eefc;
  color: #1e293b;
}

.history-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.history-more {
  display: none;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  padding: 0;
}

.history-item:hover .history-more,
.history-item.active .history-more {
  display: inline-flex;
}

.history-more:hover {
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.sidebar-footer {
  flex-shrink: 0;
  padding: 10px 12px 14px;
  border-top: 1px solid var(--border-secondary);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.footer-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.15s ease;
}

.footer-link:hover,
.footer-link.active {
  background: #eef1f5;
  color: var(--text-primary);
}

.user-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #eef1f5;
}

.user-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.user-name {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-sub {
  font-size: 11px;
  color: #94a3b8;
}

.logout-btn {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
}

.logout-btn:hover {
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

.app-shell.is-embed .main-content {
  width: 100%;
}

.embed-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-primary, #e5e7eb);
  background: #f8fafc;
}

.embed-bar-left,
.embed-bar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.embed-brand {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
}

.embed-ctx {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.embed-user {
  font-size: 12px;
  color: #475569;
}

.embed-new {
  border: 1px solid #dbe1ea;
  background: #fff;
  border-radius: 8px;
  font-size: 12px;
  padding: 4px 10px;
  cursor: pointer;
  font-family: inherit;
}

.embed-new:hover {
  background: #f1f5f9;
}
</style>
