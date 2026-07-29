<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-icon">
          <svg width="36" height="36" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="8" fill="#4f46e5"/>
            <path d="M7 10h14M7 14h10M7 18h12" stroke="#fff" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </div>
        <h1>MES Agent</h1>
        <p>使用 ERP 账号登录后进入运维助手</p>
      </div>

      <form class="login-form" @submit.prevent="onSubmit">
        <label class="field">
          <span>企业编码（可选）</span>
          <input v-model="enterpriseCode" type="text" autocomplete="organization" placeholder="通常可留空" />
        </label>
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
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { login } from '../api.js'
import { setSession } from '../auth.js'

const router = useRouter()
const route = useRoute()

const enterpriseCode = ref('')
const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await login({
      username: username.value.trim(),
      password: password.value,
      enterprise_code: enterpriseCode.value.trim(),
    })
    setSession({
      access_token: data.access_token,
      token_type: data.token_type || 'bearer',
      username: data.username,
      display_name: data.username,
      user_id: data.user_id,
      enterprise_code: data.enterprise_code || '',
      expires_at: data.expires_at,
    })
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect || '/')
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
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(1200px 600px at 10% -10%, #e0e7ff 0%, transparent 55%),
    radial-gradient(900px 500px at 100% 0%, #f1f5f9 0%, transparent 50%),
    #f8fafc;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 32px 28px 24px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.06);
}

.login-brand {
  text-align: center;
  margin-bottom: 24px;
}

.brand-icon {
  display: inline-flex;
  margin-bottom: 12px;
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
  transition: border-color 0.15s, box-shadow 0.15s;
}

.field input:focus {
  border-color: #818cf8;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
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
  background: #4f46e5;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}

.submit:hover:not(:disabled) {
  background: #4338ca;
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
