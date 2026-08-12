<template>
  <div class="settings-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">系统配置</h1>
        <p class="page-sub">
          整站一份配置，所有登录用户可改。保存后立即生效，不会改写 .env。
        </p>
      </div>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="onSave">
        保存并热更新
      </el-button>
    </header>

    <div class="settings-body">
      <div v-if="loading" class="loading">加载中…</div>
      <div v-else-if="error" class="error-card">{{ error }}</div>

      <div v-else class="groups">
        <section
          v-for="group in groups"
          :key="group.id"
          class="group-card"
        >
          <h2 class="group-title">{{ group.label }}</h2>

          <div v-if="group.id === 'llm'" class="preset-row">
            <span class="preset-label">快速填入供应商默认地址</span>
            <div class="preset-chips">
              <button
                v-for="p in LLM_PRESETS"
                :key="p.id"
                type="button"
                class="preset-chip"
                :class="{ active: selectedPreset === p.id }"
                @click="applyPreset(p)"
              >
                {{ p.label }}
              </button>
            </div>
            <p class="preset-hint">
              任意兼容 OpenAI Chat Completions 的服务均可：填写 API Key、Base URL、模型名称即可。
            </p>
          </div>

          <div v-if="group.id === 'vision'" class="preset-row">
            <span class="preset-label">快速填入视觉模型默认地址</span>
            <div class="preset-chips">
              <button
                v-for="p in VISION_PRESETS"
                :key="p.id"
                type="button"
                class="preset-chip"
                :class="{ active: selectedVisionPreset === p.id }"
                @click="applyVisionPreset(p)"
              >
                {{ p.label }}
              </button>
            </div>
            <p class="preset-hint">
              需支持多模态 / 识图的 OpenAI 兼容接口；未配置时贴图无法生成视觉规格。
            </p>
          </div>

          <div class="fields">
            <div v-for="field in group.fields" :key="field.key" class="field-row">
              <div class="field-label">
                <span>{{ field.label }}</span>
                <span class="source-tag" :data-src="field.source">
                  {{ sourceLabel(field.source) }}
                </span>
              </div>

              <template v-if="isBoolField(field.key)">
                <el-switch
                  v-model="draft[field.key]"
                  active-value="1"
                  inactive-value="0"
                />
              </template>

              <template v-else-if="field.secret">
                <el-input
                  v-model="draft[field.key]"
                  type="password"
                  show-password
                  clearable
                  :placeholder="secretPlaceholder(field)"
                />
                <div class="field-meta">
                  <span v-if="field.configured">当前已配置：{{ field.value || '****' }}</span>
                  <span v-else>尚未配置</span>
                  <button
                    v-if="field.has_ui_override"
                    type="button"
                    class="clear-link"
                    @click="markClear(field.key)"
                  >
                    清除界面覆盖
                  </button>
                </div>
              </template>

              <template v-else>
                <el-input
                  v-model="draft[field.key]"
                  clearable
                  :placeholder="fieldPlaceholder(field)"
                />
                <div v-if="field.key === 'LLM_BASE_URL'" class="field-meta">
                  例：https://api.deepseek.com/v1 、通义 https://dashscope.aliyuncs.com/compatible-mode/v1；官方 OpenAI 可留空
                </div>
                <div v-else-if="field.key === 'MAIN_MODEL'" class="field-meta">
                  例：deepseek-chat、gpt-4o、qwen-plus
                </div>
                <div v-else-if="field.key === 'VISION_BASE_URL'" class="field-meta">
                  例：https://open.bigmodel.cn/api/paas/v4/
                </div>
                <div v-else-if="field.key === 'VISION_MODEL'" class="field-meta">
                  例：glm-4v-flash、glm-4v、qwen-vl-plus
                </div>
              </template>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchSettings, saveSettings } from '../api.js'

const LLM_PRESETS = [
  {
    id: 'deepseek',
    label: 'DeepSeek',
    base: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
  },
  {
    id: 'qwen',
    label: 'Qwen',
    base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    base: 'https://api.openai.com/v1',
    model: 'gpt-4o',
  },
  {
    id: 'custom',
    label: '自定义',
    base: '',
    model: '',
  },
]

const VISION_PRESETS = [
  {
    id: 'zhipu',
    label: '智谱 GLM-4V',
    base: 'https://open.bigmodel.cn/api/paas/v4/',
    model: 'glm-4v-flash',
  },
  {
    id: 'qwen-vl',
    label: 'Qwen-VL',
    base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-vl-plus',
  },
  {
    id: 'custom',
    label: '自定义',
    base: '',
    model: '',
  },
]

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const groups = ref([])
const draft = ref({})
const selectedPreset = ref('')
const selectedVisionPreset = ref('')
/** 密钥字段：显式标记清除覆盖 */
const clearSecrets = ref({})

const BOOL_KEYS = new Set(['CURSOR_DEV_ENABLED'])

function isBoolField(key) {
  return BOOL_KEYS.has(key)
}

function sourceLabel(src) {
  if (src === 'ui') return '界面'
  if (src === 'env') return '环境变量'
  return '未设置'
}

function secretPlaceholder(field) {
  if (clearSecrets.value[field.key]) return '将清除界面覆盖（保存后回退环境变量）'
  if (field.configured) return '留空表示不修改；输入新值则覆盖'
  return '输入 API Key'
}

function fieldPlaceholder(field) {
  if (field.key === 'LLM_BASE_URL' || field.key === 'VISION_BASE_URL') {
    return 'https://api.example.com/v1'
  }
  if (field.key === 'MAIN_MODEL' || field.key === 'VISION_MODEL') return '模型 ID'
  return field.label
}

function markClear(key) {
  clearSecrets.value = { ...clearSecrets.value, [key]: true }
  draft.value[key] = ''
  ElMessage.info('已标记清除，点击「保存并热更新」后生效')
}

function applyPreset(p) {
  selectedPreset.value = p.id
  if (p.base) draft.value.LLM_BASE_URL = p.base
  if (p.model) draft.value.MAIN_MODEL = p.model
  if (p.id === 'custom') {
    ElMessage.info('请自行填写 Base URL 与模型名称')
  } else {
    ElMessage.success(`已填入 ${p.label} 默认地址与模型（请确认 API Key）`)
  }
}

function applyVisionPreset(p) {
  selectedVisionPreset.value = p.id
  if (p.base) draft.value.VISION_BASE_URL = p.base
  if (p.model) draft.value.VISION_MODEL = p.model
  if (p.id === 'custom') {
    ElMessage.info('请自行填写视觉模型 Base URL 与模型名称')
  } else {
    ElMessage.success(`已填入 ${p.label}（请确认视觉 API Key）`)
  }
}

function inferPresetFromDraft() {
  const base = String(draft.value.LLM_BASE_URL || '').trim().replace(/\/$/, '')
  if (!base) {
    selectedPreset.value = draft.value.MAIN_MODEL ? 'custom' : ''
    return
  }
  const hit = LLM_PRESETS.find((p) => {
    if (p.id === 'custom' || !p.base) return false
    return String(p.base).replace(/\/$/, '') === base
  })
  selectedPreset.value = hit?.id || 'custom'
}

function inferVisionPresetFromDraft() {
  const base = String(draft.value.VISION_BASE_URL || '')
    .trim()
    .replace(/\/$/, '')
  if (!base) {
    selectedVisionPreset.value = draft.value.VISION_MODEL ? 'custom' : ''
    return
  }
  const hit = VISION_PRESETS.find((p) => {
    if (p.id === 'custom' || !p.base) return false
    return String(p.base).replace(/\/$/, '') === base
  })
  selectedVisionPreset.value = hit?.id || 'custom'
}

function applyResponse(data) {
  groups.value = data.groups || []
  const next = {}
  const clears = {}
  for (const g of groups.value) {
    for (const f of g.fields || []) {
      if (f.secret) {
        next[f.key] = ''
      } else if (isBoolField(f.key)) {
        const v = String(f.value || '').toLowerCase()
        next[f.key] = v === '1' || v === 'true' || v === 'yes' || v === 'on' ? '1' : '0'
      } else {
        next[f.key] = f.value || ''
      }
      clears[f.key] = false
    }
  }
  draft.value = next
  clearSecrets.value = clears
  inferPresetFromDraft()
  inferVisionPresetFromDraft()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await fetchSettings()
    applyResponse(data)
  } catch (e) {
    error.value = e?.response?.data?.detail || e?.message || '加载配置失败'
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    const values = {}
    for (const g of groups.value) {
      for (const f of g.fields || []) {
        const key = f.key
        const raw = draft.value[key]
        if (f.secret) {
          if (clearSecrets.value[key]) {
            values[key] = ''
          } else if (String(raw || '').trim()) {
            values[key] = String(raw).trim()
          }
        } else {
          values[key] = raw == null ? '' : String(raw)
        }
      }
    }
    const { data } = await saveSettings(values)
    applyResponse(data)
    ElMessage.success('已保存并热更新')
    window.dispatchEvent(new CustomEvent('workbuddy:settings-updated'))
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.page-header {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 20px 24px 14px;
  background: var(--bg-primary, #fff);
  border-bottom: 1px solid var(--border-primary, #e2e8f0);
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 650;
  color: var(--text-primary);
}

.page-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.settings-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 16px 24px 40px;
  max-width: 760px;
  width: 100%;
  box-sizing: border-box;
  margin: 0 auto;
}

.loading {
  color: var(--text-secondary);
  font-size: 14px;
}

.error-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--danger-bg, #fef2f2);
  color: var(--danger, #dc2626);
  font-size: 13px;
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.group-card {
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-primary, #e2e8f0);
  border-radius: 12px;
  padding: 16px 18px 8px;
}

.group-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.preset-row {
  margin-bottom: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}

.preset-label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}

.preset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.preset-chip {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #334155;
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.preset-chip:hover {
  border-color: #94a3b8;
  background: #fff;
}

.preset-chip.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
  font-weight: 600;
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.35);
}

.preset-chip.active:hover {
  background: #1d4ed8;
  border-color: #1d4ed8;
  color: #fff;
}

.preset-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.45;
}

.fields {
  display: flex;
  flex-direction: column;
}

.field-row {
  padding: 12px 0;
  border-top: 1px solid #f1f5f9;
}

.field-row:first-child {
  border-top: none;
}

.field-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
}

.source-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
}

.source-tag[data-src='ui'] {
  background: #eef2ff;
  color: #4338ca;
}

.source-tag[data-src='env'] {
  background: #ecfdf5;
  color: #047857;
}

.field-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 6px;
  font-size: 12px;
  color: #94a3b8;
}

.clear-link {
  border: none;
  background: none;
  color: #dc2626;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  padding: 0;
}

.clear-link:hover {
  text-decoration: underline;
}
</style>
