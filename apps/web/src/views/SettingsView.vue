<template>
  <div class="settings-view">
    <header class="page-header">
      <div>
        <h1 class="page-title">系统配置</h1>
        <p class="page-sub">
          整站一份配置。保存后立即生效，不会改写 .env。若部署时设置了 SETTINGS_ADMIN_USERS，仅名单内用户可改。
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
          <div class="group-title-row">
            <h2 class="group-title">{{ group.label }}</h2>
            <el-button
              v-if="group.id === 'mes'"
              size="small"
              :loading="mesBusy"
              @click="onClearMesConfig"
            >
              一键清除配置
            </el-button>
          </div>

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

          <div v-if="group.id === 'git_review'" class="preset-row">
            <p class="preset-hint">
              审核公开 GitHub 仓时默认走内置 HTTPS 镜像（ghfast / gh-proxy），再回退直连。
              仅支持 <code>https://</code> 公网前缀（可逗号分隔），禁止 localhost / 内网 IP / 带账号密码；
              填 <code>off</code> 关闭。这不是 VPN，系统代理仍由本机自行配置。
            </p>
          </div>

          <!-- 非 MES：先说明再字段；MES：先名称/地址，再上传 -->
          <div v-if="group.id !== 'mes'" class="fields">
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

          <template v-if="group.id === 'mes'">
            <div class="fields">
              <div v-for="field in group.fields" :key="field.key" class="field-row">
                <div class="field-label">
                  <span>{{ field.label }}</span>
                  <span class="source-tag" :data-src="field.source">
                    {{ sourceLabel(field.source) }}
                  </span>
                </div>
                <template v-if="field.secret">
                  <el-input
                    v-model="draft[field.key]"
                    type="password"
                    show-password
                    clearable
                    :placeholder="secretPlaceholder(field)"
                  />
                </template>
                <el-input
                  v-else
                  v-model="draft[field.key]"
                  clearable
                  :placeholder="fieldPlaceholder(field)"
                />
                <div v-if="field.key === 'MES_PROFILE_ID'" class="field-meta">
                  给这套 MES/ERP 起个名字。须配置后才能查数与表结构摸底；不影响 WorkBuddy 登录。
                </div>
                <div v-else-if="field.key === 'PLATFORM_BASE_URL'" class="field-meta">
                  不用于 WorkBuddy 登录（登录只读环境变量）。查数主机以已导入的接口文档为准。
                </div>
                <div v-else-if="field.key === 'MES_API_USERNAME'" class="field-meta">
                  调用已导入业务接口用的账号，不是 WorkBuddy 登录账号。
                </div>
                <div v-else-if="field.key === 'MES_API_PASSWORD'" class="field-meta">
                  <span v-if="field.configured">当前已配置：{{ field.value || '****' }}</span>
                  <span v-else>尚未配置。该 MES 除登录/健康检查外都要 JWT。</span>
                  <button
                    v-if="field.has_ui_override"
                    type="button"
                    class="clear-link"
                    @click="markClear(field.key)"
                  >
                    清除界面覆盖
                  </button>
                </div>
                <div v-else-if="field.key === 'MES_API_ENTERPRISE_CODE'" class="field-meta">
                  若接口文档要求企业编码则必填，例如：江西中软。
                </div>
              </div>
            </div>

            <div class="mes-upload-block">
              <h3 class="mes-upload-title">上传表结构及 API 接口</h3>
              <div class="fields">
                <div class="field-row">
                  <div class="field-label">
                    <span>① 上传表结构 (.md)</span>
                  </div>
                  <div class="mes-control-row">
                    <label class="mes-pick-btn" :class="{ 'is-disabled': mesBusy }">
                      <input
                        class="mes-file-hidden"
                        type="file"
                        accept=".md,.markdown,.txt,text/markdown,text/plain"
                        :disabled="mesBusy"
                        @change="onUploadSchema"
                      />
                      选择文件
                    </label>
                    <span class="mes-file-hint">
                      {{
                        mesUi?.schema_uploaded
                          ? `已上传（${formatBytes(mesUi.schema_size)}）`
                          : '未上传'
                      }}
                    </span>
                  </div>
                </div>
                <div class="field-row">
                  <div class="field-label">
                    <span>② 接口文档地址</span>
                  </div>
                  <div class="mes-control-row">
                    <el-input
                      v-model="openapiUrl"
                      clearable
                      :disabled="mesBusy"
                      placeholder="http://主机:端口/docs 或 …/openapi.json"
                    />
                    <el-button
                      type="primary"
                      :loading="mesBusy"
                      :disabled="mesBusy"
                      @click="onImportOpenApiUrl"
                    >
                      从地址导入
                    </el-button>
                  </div>
                  <div class="mes-control-row mes-control-row--second">
                    <label class="mes-pick-btn" :class="{ 'is-disabled': mesBusy }">
                      <input
                        class="mes-file-hidden"
                        type="file"
                        accept=".json,.yaml,.yml,application/json,text/yaml"
                        :disabled="mesBusy"
                        @change="onUploadOpenApi"
                      />
                      选择文件
                    </label>
                    <span class="mes-file-hint">
                      {{
                        mesUi?.openapi_imported
                          ? `已导入（${formatBytes(mesUi.openapi_size)}`
                            + (mesUi.entity_count > 0 ? `，${mesUi.entity_count} 个可查对象` : '')
                            + '）'
                          : '或上传 openapi.json'
                      }}
                    </span>
                  </div>
                </div>
              </div>
              <div v-if="mesStatus?.runtime?.api_base" class="field-meta mes-runtime-hint">
                接口文档只用来生成可查对象（当前查数 API 根：{{ mesStatus.runtime.api_base }}），与 WorkBuddy 登录无关。换平台改名称并重新上传表结构与接口文档即可。
              </div>
              <div v-else class="field-meta mes-runtime-hint">
                上传的接口文档只用来生成可查对象（列表地址、分页参数），与 WorkBuddy 登录无关。换平台改名称并重新上传即可。
              </div>
            </div>
          </template>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchSettings,
  saveSettings,
  fetchMesProfile,
  activateMesProfile,
  uploadMesSchema,
  uploadMesOpenApi,
  importMesOpenApiUrl,
} from '../api.js'

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
const mesStatus = ref(null)
const mesBusy = ref(false)
const openapiUrl = ref('')

const BOOL_KEYS = new Set(['CURSOR_DEV_ENABLED', 'IDE_GIT_MIRROR_FIRST'])

const mesUi = computed(() => {
  const ui = mesStatus.value?.ui
  if (ui && typeof ui === 'object') return ui
  // 兼容旧接口：无 ui 字段时从 schema/openapi 推断
  const st = mesStatus.value
  if (!st) return null
  return {
    schema_uploaded: st.schema?.source === 'profile' && !!st.schema?.exists,
    openapi_imported: !!st.openapi?.exists,
    entity_count:
      st.entities?.source === 'profile' && st.entities?.exists
        ? Number(st.entity_count || 0)
        : 0,
    schema_size: st.schema?.source === 'profile' ? Number(st.schema?.size || 0) : 0,
    openapi_size: Number(st.openapi?.size || 0),
  }
})

function formatBytes(n) {
  const size = Number(n) || 0
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function requireProfileId() {
  const id = String(draft.value.MES_PROFILE_ID || '').trim()
  if (!id) {
    ElMessage.warning('请先填写「MES / ERP 平台名称」，再上传表结构或接口文档')
    return ''
  }
  return id
}

async function refreshMesStatus() {
  try {
    const { data } = await fetchMesProfile()
    mesStatus.value = data
    if (data?.active_profile_id && draft.value) {
      // 仅当草稿为空时同步，避免覆盖用户正在编辑的 ID
      if (!String(draft.value.MES_PROFILE_ID || '').trim()) {
        draft.value.MES_PROFILE_ID = data.active_profile_id
      }
    }
    const src = data?.openapi?.source_url
    if (src && !String(openapiUrl.value || '').trim()) {
      openapiUrl.value = src
    }
  } catch {
    mesStatus.value = null
  }
}

async function onUploadSchema(ev) {
  const file = ev?.target?.files?.[0]
  ev.target.value = ''
  const id = requireProfileId()
  if (!file || !id) return
  mesBusy.value = true
  try {
    const { data } = await uploadMesSchema(id, file, true)
    mesStatus.value = data
    draft.value.MES_PROFILE_ID = data.active_profile_id || id
    ElMessage.success('表结构已上传，并设为当前系统')
    window.dispatchEvent(new CustomEvent('workbuddy:settings-updated'))
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '上传失败')
  } finally {
    mesBusy.value = false
  }
}

async function onUploadOpenApi(ev) {
  const file = ev?.target?.files?.[0]
  ev.target.value = ''
  const id = requireProfileId()
  if (!file || !id) return
  mesBusy.value = true
  try {
    const { data } = await uploadMesOpenApi(id, file, true)
    mesStatus.value = data
    draft.value.MES_PROFILE_ID = data.active_profile_id || id
    const n = data.entity_count || 0
    ElMessage.success(`接口文档已导入，生成 ${n} 个可查对象草稿（请核对）`)
    window.dispatchEvent(new CustomEvent('workbuddy:settings-updated'))
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '上传失败')
  } finally {
    mesBusy.value = false
  }
}

async function onImportOpenApiUrl() {
  const id = requireProfileId()
  const url = String(openapiUrl.value || '').trim()
  if (!id) return
  if (!url) {
    ElMessage.warning('请填写接口文档地址，例如 http://主机:端口/docs')
    return
  }
  mesBusy.value = true
  try {
    const { data } = await importMesOpenApiUrl(id, url, true)
    mesStatus.value = data
    draft.value.MES_PROFILE_ID = data.active_profile_id || id
    const n = data.entity_count || 0
    const from = data.fetched_from ? `（来自 ${data.fetched_from}）` : ''
    ElMessage.success(`已从地址导入，生成 ${n} 个可查对象草稿${from}`)
    window.dispatchEvent(new CustomEvent('workbuddy:settings-updated'))
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '导入失败')
  } finally {
    mesBusy.value = false
  }
}

/** 清除当前 MES 资料包（须重新配置后才能查数/摸底） */
async function onClearMesConfig() {
  mesBusy.value = true
  try {
    const { data } = await activateMesProfile('')
    mesStatus.value = data
    draft.value.MES_PROFILE_ID = ''
    // 清除平台地址的界面覆盖，回退 .env
    await saveSettings({
      PLATFORM_BASE_URL: '',
      MES_PROFILE_ID: '',
      MES_API_USERNAME: '',
      MES_API_PASSWORD: '',
      MES_API_ENTERPRISE_CODE: '',
    })
    draft.value.PLATFORM_BASE_URL = ''
    // 重新拉设置以显示 env 回退后的地址
    const { data: settings } = await fetchSettings()
    applyResponse(settings)
    await refreshMesStatus()
    ElMessage.success('已清除 MES 配置，请重新填写平台名称并上传资料')
    window.dispatchEvent(new CustomEvent('workbuddy:settings-updated'))
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '清除失败')
  } finally {
    mesBusy.value = false
  }
}

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
  if (field.key === 'MES_PROFILE_ID') return '现场 MES 名称，例如：车间A'
  if (field.key === 'PLATFORM_BASE_URL') return 'http://主机:端口（网页或 API 根均可）'
  if (field.key === 'MES_API_USERNAME') return 'MES 业务接口账号'
  if (field.key === 'MES_API_ENTERPRISE_CODE') return '例如：江西中软'
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
    await refreshMesStatus()
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
    await refreshMesStatus()
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

.group-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.group-title {
  margin: 0;
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

.mes-upload-block {
  margin-top: 8px;
  padding-top: 14px;
  border-top: 1px solid #f1f5f9;
}

.mes-upload-title {
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #0f172a);
}

.mes-control-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.mes-control-row--second {
  margin-top: 8px;
}

.mes-control-row :deep(.el-input) {
  flex: 1;
  min-width: 200px;
}

.mes-file-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.mes-pick-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 32px;
  padding: 0 15px;
  font-size: 14px;
  line-height: 1;
  color: #606266;
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  cursor: pointer;
  user-select: none;
  box-sizing: border-box;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.mes-pick-btn:hover:not(.is-disabled) {
  color: #409eff;
  border-color: #c6e2ff;
  background: #ecf5ff;
}

.mes-pick-btn.is-disabled {
  color: #a8abb2;
  background: #f5f7fa;
  border-color: #e4e7ed;
  cursor: not-allowed;
}

.mes-file-hint {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
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
