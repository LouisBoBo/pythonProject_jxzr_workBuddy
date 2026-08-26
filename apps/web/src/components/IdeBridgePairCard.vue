<template>
  <div class="ide-pair-card">
    <div class="ipc-status" :class="{ online: online, warn: warn }">
      <span class="ipc-dot" />
      <span>状态：{{ label }}</span>
    </div>
    <p v-if="hint" class="ipc-hint">{{ hint }}</p>

    <template v-if="featureEnabled && !connected">
      <button type="button" class="ipc-btn" :disabled="loading" @click="onPair">
        {{ loading ? '生成中…' : '配对 VS Code' }}
      </button>
      <div v-if="code" class="ipc-box">
        <div class="ipc-code">{{ code }}</div>
        <p class="ipc-pair-hint">
          在 VS Code 执行 <b>WorkBuddy: Pair</b> 并输入此码
          <span v-if="expiresIn">（{{ expiresIn }}s 内有效）</span>
        </p>
        <button type="button" class="ipc-copy" :class="{ copied }" @click="onCopy">
          {{ copied ? '已复制' : '复制配对码' }}
        </button>
      </div>
    </template>
    <p v-else-if="featureEnabled && connected" class="ipc-ok">
      已配对。发「审核代码」可选本机 VS Code 工程。
    </p>
    <p v-else class="ipc-off">IDE 审核未启用时无法配对（需服务端开启）。</p>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchIdeBridgeStatus, createIdeBridgePairing } from '../api.js'

const featureEnabled = ref(false)
const online = ref(false)
const warn = ref(false)
const connected = ref(false)
const label = ref('离线')
const hint = ref('')
const loading = ref(false)
const code = ref('')
const expiresIn = ref(0)
const copied = ref(false)

let pollTimer = null
let countdown = null
let copiedTimer = null

function clearCountdown() {
  if (countdown != null) {
    clearInterval(countdown)
    countdown = null
  }
  copied.value = false
  if (copiedTimer != null) {
    clearTimeout(copiedTimer)
    copiedTimer = null
  }
}

async function refresh() {
  try {
    const resp = await fetchIdeBridgeStatus()
    const data = resp.data || {}
    featureEnabled.value = !!data.feature_enabled
    const isOnline = !!data.online
    const ready = !!data.workspace_ready
    connected.value = isOnline
    online.value = isOnline && ready
    warn.value = isOnline && !ready
    if (isOnline) {
      clearCountdown()
      code.value = ''
      expiresIn.value = 0
    }
    if (!data.feature_enabled) {
      label.value = '离线'
      hint.value = ''
    } else if (!isOnline) {
      label.value = '离线'
      hint.value = '点击下方配对，或在扩展中执行 WorkBuddy: Pair'
    } else if (!ready) {
      label.value = '未开工程'
      hint.value = '已连接；请先在 VS Code 打开文件夹，或审核时选最近工程'
    } else {
      label.value = '在线'
      hint.value = `${data.carrier || 'vscode'} · ${data.workspace_root || ''}`
    }
  } catch {
    // 网络抖动时保留上一拍 featureEnabled，避免误显示「未启用」
    online.value = false
    warn.value = false
    connected.value = false
    if (!featureEnabled.value) {
      label.value = '离线'
      hint.value = ''
    } else {
      label.value = '状态暂不可用'
      hint.value = '无法拉取 Bridge 状态，请稍后刷新'
    }
  }
}

async function onPair() {
  loading.value = true
  try {
    const resp = await createIdeBridgePairing()
    const data = resp.data || {}
    code.value = String(data.code || '')
    expiresIn.value = Number(data.expires_in || 120)
    clearCountdown()
    countdown = window.setInterval(() => {
      if (expiresIn.value <= 1) {
        clearCountdown()
        code.value = ''
        expiresIn.value = 0
        return
      }
      expiresIn.value -= 1
    }, 1000)
  } catch (e) {
    code.value = ''
    const msg = e?.response?.data?.detail || e?.message || '配对失败'
    ElMessage.error(typeof msg === 'string' ? msg : '配对失败，请确认已登录且启用了 IDE 审核')
  } finally {
    loading.value = false
  }
}

async function onCopy() {
  if (!code.value) return
  try {
    await navigator.clipboard.writeText(code.value)
    copied.value = true
    if (copiedTimer != null) clearTimeout(copiedTimer)
    copiedTimer = window.setTimeout(() => {
      copied.value = false
      copiedTimer = null
    }, 1600)
    ElMessage.success('配对码已复制')
  } catch {
    ElMessage.error('复制失败，请手动选中配对码')
  }
}

onMounted(() => {
  refresh()
  pollTimer = window.setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (pollTimer != null) clearInterval(pollTimer)
  clearCountdown()
})
</script>

<style scoped>
.ide-pair-card {
  margin-top: 4px;
}
.ipc-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 8px;
  background: #f1f5f9;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.ipc-status.online {
  background: #ecfdf5;
  color: #166534;
}
.ipc-status.warn {
  background: #fffbeb;
  color: #92400e;
}
.ipc-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #94a3b8;
}
.ipc-status.online .ipc-dot {
  background: #22c55e;
}
.ipc-status.warn .ipc-dot {
  background: #f59e0b;
}
.ipc-hint,
.ipc-ok,
.ipc-off,
.ipc-pair-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}
.ipc-btn {
  margin-top: 12px;
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  background: #0f766e;
  color: #fff;
  font-size: 13px;
  font-family: inherit;
  font-weight: 600;
  cursor: pointer;
}
.ipc-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ipc-btn:hover:not(:disabled) {
  background: #0d9488;
}
.ipc-box {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}
.ipc-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: #0f172a;
}
.ipc-copy {
  margin-top: 8px;
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
}
.ipc-copy.copied {
  border-color: #86efac;
  color: #166534;
}
</style>
