<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-icon" aria-hidden="true">
          <img src="/zr-logo.svg" alt="" class="brand-logo" />
        </div>
        <h1>ZR WorkBuddy</h1>
        <p>你的工作搭档 · 使用 ERP 账号登录</p>
      </div>

      <form class="login-form" @submit.prevent="onSubmit">
        <div class="field">
          <span>企业编码</span>
          <div
            class="ent-select"
            :class="{ open: entOpen }"
            ref="entSelectEl"
          >
            <button
              type="button"
              class="ent-trigger"
              :aria-expanded="entOpen"
              aria-haspopup="listbox"
              @click="entOpen = !entOpen"
            >
              <span class="ent-trigger-label">{{ selectedEnterprise?.label || '请选择企业' }}</span>
              <svg class="ent-caret" viewBox="0 0 12 8" width="12" height="8" aria-hidden="true">
                <path
                  d="M1 1.5L6 6.5L11 1.5"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.5"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </button>
            <ul
              v-show="entOpen"
              class="ent-menu"
              role="listbox"
              :aria-activedescendant="selectedEnterprise ? `ent-${selectedEnterprise.key}` : undefined"
            >
              <li
                v-for="item in ENTERPRISES"
                :id="`ent-${item.key}`"
                :key="item.key"
                role="option"
                class="ent-option"
                :class="{ active: item.key === enterpriseKey }"
                :aria-selected="item.key === enterpriseKey"
                @mousedown.prevent="pickEnterprise(item)"
              >
                {{ item.label }}
              </li>
            </ul>
          </div>
        </div>

        <label class="field">
          <span>账号</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="ERP 用户名" required />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="ERP 密码" required />
        </label>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="hint">账号与密码来自公司 ERP，登录接口：/api/v1/auth/login</p>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../api.js'
import { setSession } from '../auth.js'

/**
 * 企业下拉仅改展示；提交逻辑与改前一致：
 * code 为空则不向 ERP 传错误企业名（原先文本框默认可留空）。
 * 若某环境需真实 enterprise_code，只改对应项的 code，勿把中文名当编码。
 */
const ENTERPRISES = [
  { key: 'jsry', label: '江苏软云', code: '' },
  { key: 'jxzr', label: '江西中软', code: '' },
  { key: 'qhzr', label: '前海中软', code: '' },
]

const router = useRouter()

const enterpriseKey = ref('jxzr')
const entOpen = ref(false)
const entSelectEl = ref(null)
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

const selectedEnterprise = computed(
  () => ENTERPRISES.find((e) => e.key === enterpriseKey.value) || ENTERPRISES[1],
)

function pickEnterprise(item) {
  enterpriseKey.value = item.key
  entOpen.value = false
}

function onDocPointerDown(e) {
  const root = entSelectEl.value
  if (!root || !entOpen.value) return
  if (!root.contains(e.target)) entOpen.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown)
})
onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointerDown)
})

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    const enterprise_code = String(selectedEnterprise.value?.code || '').trim()
    const { data } = await login({
      username: username.value.trim(),
      password: password.value,
      enterprise_code,
    })
    setSession({
      access_token: data.access_token,
      token_type: data.token_type || 'bearer',
      username: data.username,
      display_name: data.username,
      user_id: data.user_id,
      enterprise_code: data.enterprise_code || enterprise_code,
      expires_at: data.expires_at,
    })
    // 登录后固定进入新会话，避免 redirect 带回旧 thread 打开历史对话
    router.replace({ path: '/', query: { thread: `session-${Date.now()}` } })
  } catch (e) {
    const msg =
      e?.response?.data?.detail ||
      e?.message ||
      '登录失败'
    error.value = typeof msg === 'string' ? msg : JSON.stringify(msg)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  --brand: #1B5E3B;
  --brand-hover: #164A2F;
  --brand-soft: rgba(27, 94, 59, 0.12);
  --brand-ring: rgba(27, 94, 59, 0.22);
  --brand-border: #2E8B57;
  /* 企业下拉：按设计稿浅蓝强调 */
  --ent-accent: #4a9eff;
  --ent-accent-text: #3b82f6;
  --ent-accent-soft: #eef5ff;
  --ent-border: #b7d4f8;

  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1200px 600px at 10% -10%, #d8f3e4 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #eef7f1 0%, transparent 50%),
    #f6faf7;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 32px 28px 24px;
  background: #fff;
  border: 1px solid #dce8e0;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(27, 94, 59, 0.08);
}

.login-brand {
  text-align: center;
  margin-bottom: 24px;
}

.brand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  padding: 6px;
  margin-bottom: 12px;
  border-radius: 14px;
  background: var(--brand);
  border: 1px solid var(--brand-border);
  box-sizing: border-box;
}

.brand-logo {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 0;
  image-rendering: auto;
}

.login-brand h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.login-brand p {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}

.field input {
  height: 42px;
  padding: 0 12px;
  border: 1px solid #dbe1ea;
  border-radius: 10px;
  font-size: 14px;
  font-family: inherit;
  color: #0f172a;
  background: #fff;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
}

.field input:focus {
  border-color: var(--brand-border);
  background: #f4fbf6;
  box-shadow: 0 0 0 3px var(--brand-ring);
}

.ent-select {
  position: relative;
}

.ent-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  height: 42px;
  padding: 0 12px;
  border: 1px solid #dbe1ea;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  font-family: inherit;
  color: #334155;
  cursor: pointer;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.ent-select.open .ent-trigger,
.ent-trigger:focus-visible {
  border-color: var(--ent-accent);
  box-shadow: 0 0 0 3px rgba(74, 158, 255, 0.18);
}

.ent-trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ent-caret {
  flex-shrink: 0;
  margin-left: 8px;
  color: #94a3b8;
  transition: transform 0.15s;
}

.ent-select.open .ent-caret {
  transform: rotate(180deg);
}

.ent-menu {
  position: absolute;
  z-index: 20;
  left: 0;
  right: 0;
  top: calc(100% + 10px);
  margin: 0;
  padding: 6px 0;
  list-style: none;
  background: #fff;
  border: 1px solid #e8eef5;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.1);
}

.ent-menu::before {
  content: '';
  position: absolute;
  top: -6px;
  left: 50%;
  width: 12px;
  height: 12px;
  background: #fff;
  border-left: 1px solid #e8eef5;
  border-top: 1px solid #e8eef5;
  transform: translateX(-50%) rotate(45deg);
}

.ent-option {
  position: relative;
  z-index: 1;
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 400;
  color: #64748b;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.ent-option:hover {
  background: #f8fafc;
  color: #475569;
}

.ent-option.active {
  background: var(--ent-accent-soft);
  color: var(--ent-accent-text);
}

.error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff1f2;
  color: #e11d48;
  font-size: 13px;
}

.submit {
  margin-top: 4px;
  height: 44px;
  border: none;
  border-radius: 10px;
  background: var(--brand);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.submit:hover:not(:disabled) {
  background: var(--brand-hover);
}

.submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.hint {
  margin: 16px 0 0;
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
  line-height: 1.5;
}
</style>
