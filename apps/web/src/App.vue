<template>
  <div v-if="isLoginRoute" class="login-shell">
    <router-view />
  </div>
  <div v-else :class="['app-shell', { 'is-embed': embedMode }]">
    <aside v-if="!embedMode" class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon" aria-hidden="true">
          <img src="/zr-logo.svg" alt="" class="brand-logo" />
        </div>
        <div class="brand-text">
          <span class="brand-name">ZR WorkBuddy</span>
          <span class="brand-tag">你的工作搭档</span>
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
        <div
          v-if="ideBridgeUiVisible"
          class="ide-bridge-panel"
        >
          <div
            class="ide-bridge-status"
            :class="{ online: ideBridgeOnline, warn: ideBridgeWarn }"
            :title="ideBridgeHint"
          >
            <span class="ide-dot" />
            <span>代码载体：{{ ideBridgeLabel }}</span>
          </div>
        </div>
        <div
          v-if="cursorDevPanelVisible"
          class="cursor-dev-panel"
          :title="cursorDevHint"
        >
          <div
            class="cursor-dev-status"
            :class="{ ready: cursorDevReady, warn: cursorDevWarn }"
          >
            <span class="cursor-dev-dot" />
            <span>写码车道：{{ cursorDevLabel }}</span>
          </div>
        </div>
        <router-link to="/automations" class="footer-link" active-class="active">
          <el-icon :size="16"><Timer /></el-icon>
          <span>自动化</span>
        </router-link>
        <router-link to="/files" class="footer-link" active-class="active">
          <el-icon :size="16"><FolderOpened /></el-icon>
          <span>文件管理</span>
        </router-link>
        <router-link to="/settings" class="footer-link" active-class="active">
          <el-icon :size="16"><Setting /></el-icon>
          <span>系统配置</span>
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
          <span class="embed-brand">ZR WorkBuddy</span>
          <span v-if="contextLabel" class="embed-ctx">{{ contextLabel }}</span>
        </div>
        <div class="embed-bar-right">
          <span class="embed-user">{{ displayName }}</span>
          <button type="button" class="embed-new" @click="goNewChat">新对话</button>
        </div>
      </div>
      <!-- 按会话 thread 强制重挂载，避免写码轮询/HMR 损坏后切换会话无响应 -->
      <router-view :key="mainViewKey" />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, Setting, Timer } from '@element-plus/icons-vue'
import { getHistoryList, deleteHistory, fetchIdeBridgeStatus, fetchCursorDevStatus } from './api.js'
import { clearSession, getDisplayName, getUsername } from './auth.js'
import { isEmbedMode, pageContextLabel, getPageContext, setEmbedMode, clearPageContext } from './embed.js'

const route = useRoute()
const router = useRouter()

const sessions = ref([])
const historyLoading = ref(false)
let historyRefreshTimer = null
const displayName = ref(getDisplayName() || getUsername() || '用户')
const embedMode = ref(isEmbedMode())
const contextLabel = ref(pageContextLabel(getPageContext()))

const ideBridgeUiVisible = ref(false)
const ideBridgeOnline = ref(false)
const ideBridgeWarn = ref(false)
const ideBridgeConnected = ref(false)
const ideBridgeLabel = ref('离线')
const ideBridgeHint = ref('')
let ideBridgeTimer = null

const cursorDevPanelVisible = ref(false)
const cursorDevReady = ref(false)
const cursorDevWarn = ref(false)
const cursorDevLabel = ref('未开启')
const cursorDevHint = ref('')

const isLoginRoute = computed(() => route.name === 'login' || route.path === '/login')
const groupedHistory = computed(() => groupSessions(sessions.value))
/** 对话页：thread 变化即整页重建，保证新对话/历史切换一定生效并清掉残留定时器 */
const mainViewKey = computed(() => {
  if (route.name === 'chat' || route.path === '/') {
    const t = route.query.thread
    return typeof t === 'string' && t ? `chat:${t}` : 'chat:boot'
  }
  return String(route.name || route.path)
})

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

async function loadHistory({ silent = false } = {}) {
  if (isLoginRoute.value) return
  // 已有列表时静默刷新，避免发消息后侧栏空白闪「加载中」
  const showLoading = !silent && sessions.value.length === 0
  if (showLoading) historyLoading.value = true
  try {
    const resp = await getHistoryList()
    sessions.value = resp.data || []
  } catch {
    if (!silent) sessions.value = []
  } finally {
    if (showLoading) historyLoading.value = false
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
  stopIdeBridgePolling()
  ideBridgeUiVisible.value = false
  ideBridgeOnline.value = false
  ideBridgeConnected.value = false
  router.replace('/login')
}

function onHistoryUpdated() {
  if (historyRefreshTimer != null) clearTimeout(historyRefreshTimer)
  historyRefreshTimer = window.setTimeout(() => {
    historyRefreshTimer = null
    loadHistory({ silent: true })
  }, 280)
}

async function refreshIdeBridgeStatus() {
  if (isLoginRoute.value) return
  try {
    const resp = await fetchIdeBridgeStatus()
    const data = resp.data || {}
    ideBridgeUiVisible.value = !!data.feature_enabled
    const online = !!data.online
    const ready = !!data.workspace_ready
    ideBridgeConnected.value = online
    ideBridgeOnline.value = online && ready
    ideBridgeWarn.value = online && !ready
    if (!data.feature_enabled) {
      ideBridgeLabel.value = '离线'
      ideBridgeHint.value = ''
    } else if (!online) {
      ideBridgeLabel.value = '离线'
      ideBridgeHint.value = '到「系统配置 → 审码车道 → vscode-bridge」配对'
    } else if (!ready) {
      ideBridgeLabel.value = '未开工程'
      ideBridgeHint.value = '已连接；发「审核代码」可从最近工程中选择，或先在 VS Code 打开文件夹'
    } else {
      ideBridgeLabel.value = '在线'
      ideBridgeHint.value = `${data.carrier || 'vscode'} · ${data.workspace_root || ''}`
    }
  } catch {
    // 网络抖动时不要整块隐藏「代码载体」状态
    ideBridgeOnline.value = false
    ideBridgeWarn.value = false
    ideBridgeConnected.value = false
    if (ideBridgeUiVisible.value) {
      ideBridgeLabel.value = '状态暂不可用'
      ideBridgeHint.value = '无法拉取 Bridge 状态，请稍后重试'
    }
  }
}

async function refreshCursorDevStatus() {
  if (isLoginRoute.value) return
  try {
    const resp = await fetchCursorDevStatus()
    const data = resp?.data || {}
    cursorDevPanelVisible.value = Boolean(data.enabled)
    if (!data.enabled) {
      cursorDevReady.value = false
      cursorDevWarn.value = false
      cursorDevLabel.value = '未开启'
      cursorDevHint.value = ''
      return
    }
    const ready = Boolean(data.readiness?.ready ?? data.available)
    cursorDevReady.value = ready && data.available
    cursorDevWarn.value = Boolean(data.enabled) && !data.available
    cursorDevLabel.value = !data.available
      ? '不可用'
      : ready
        ? '就绪'
        : '待确认'
    cursorDevHint.value = data.available
      ? '写码车道可用'
      : '写码车道暂不可用，可在「系统配置」中检查 Key 与开关'
  } catch {
    cursorDevPanelVisible.value = false
  }
}

function onSettingsUpdated() {
  refreshCursorDevStatus()
  refreshIdeBridgeStatus()
}

function startIdeBridgePolling() {
  stopIdeBridgePolling()
  refreshIdeBridgeStatus()
  refreshCursorDevStatus()
  ideBridgeTimer = window.setInterval(refreshIdeBridgeStatus, 5000)
}

function stopIdeBridgePolling() {
  if (ideBridgeTimer != null) {
    clearInterval(ideBridgeTimer)
    ideBridgeTimer = null
  }
}
watch(isLoginRoute, (v) => {
  if (!v) {
    displayName.value = getDisplayName() || getUsername() || '用户'
    embedMode.value = isEmbedMode()
    contextLabel.value = pageContextLabel(getPageContext())
    loadHistory()
    startIdeBridgePolling()
  } else {
    stopIdeBridgePolling()
    ideBridgeUiVisible.value = false
  }
})

onMounted(() => {
  displayName.value = getDisplayName() || getUsername() || '用户'
  embedMode.value = isEmbedMode()
  contextLabel.value = pageContextLabel(getPageContext())
  loadHistory()
  window.addEventListener('mes-history-updated', onHistoryUpdated)
  window.addEventListener('workbuddy:settings-updated', onSettingsUpdated)
  if (!isLoginRoute.value) {
    startIdeBridgePolling()
  }
})

onUnmounted(() => {
  window.removeEventListener('mes-history-updated', onHistoryUpdated)
  window.removeEventListener('workbuddy:settings-updated', onSettingsUpdated)
  if (historyRefreshTimer != null) {
    clearTimeout(historyRefreshTimer)
    historyRefreshTimer = null
  }
  stopIdeBridgePolling()
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

.sidebar-brand .brand-icon {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 3px;
  border-radius: 8px;
  background: #1B5E3B;
  border: 1px solid #2E8B57;
  box-sizing: border-box;
}

.sidebar-brand .brand-logo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
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

.ide-bridge-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.cursor-dev-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 4px;
}

.cursor-dev-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  background: #eef1f5;
}

.cursor-dev-status.ready {
  color: #166534;
  background: #ecfdf5;
}

.cursor-dev-status.warn {
  color: #a16207;
  background: #fffbeb;
}

.cursor-dev-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

.cursor-dev-status.ready .cursor-dev-dot {
  background: #22c55e;
}

.cursor-dev-status.warn .cursor-dev-dot {
  background: #eab308;
}

.ide-bridge-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  background: #eef1f5;
}

.ide-bridge-status.online {
  color: #166534;
  background: #ecfdf5;
}

.ide-bridge-status.warn {
  color: #a16207;
  background: #fffbeb;
}

.ide-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
  flex-shrink: 0;
}

.ide-bridge-status.online .ide-dot {
  background: #22c55e;
}

.ide-bridge-status.warn .ide-dot {
  background: #eab308;
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
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
}

.main-content > :deep(.chat-view),
.main-content > :deep(.file-view),
.main-content > :deep(.settings-view) {
  flex: 1;
  min-height: 0;
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
