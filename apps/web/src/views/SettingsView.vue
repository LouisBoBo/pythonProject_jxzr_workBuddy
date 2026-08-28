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

      <div v-else class="settings-layout">
        <nav class="settings-nav" aria-label="配置分类">
          <button
            v-for="tab in SETTINGS_TABS"
            :key="tab.id"
            type="button"
            class="settings-nav-item"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </nav>

        <div class="settings-main">
          <p class="tab-hint">{{ activeTabMeta?.hint || '' }}</p>
          <div class="groups">
            <section
              v-for="group in visibleGroups"
              :key="group.id"
              class="group-card"
            >
          <div class="group-title-row">
            <h2 class="group-title">{{ groupDisplayLabel(group) }}</h2>
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
            <div class="preset-chips">
              <button
                v-for="p in REVIEW_MODE_PRESETS"
                :key="p.id"
                type="button"
                class="preset-chip"
                :class="{ active: reviewMode === p.id }"
                @click="reviewMode = p.id"
              >
                {{ p.label }}
              </button>
            </div>
            <p class="preset-hint">{{ reviewModeHint }}</p>
          </div>

          <!-- 审码：vscode-bridge 配对（原侧栏） -->
          <div v-if="group.id === 'git_review' && reviewMode === 'vscode_bridge'" class="fields">
            <IdeBridgePairCard />
          </div>

          <!-- 审码：公开 Git 拉仓镜像 -->
          <div v-else-if="group.id === 'git_review' && reviewMode === 'git'" class="fields">
            <div v-for="field in group.fields" :key="field.key" class="field-row">
              <div class="field-label">
                <span>{{ field.label }}</span>
                <span class="source-tag" :data-src="fieldSourceAttr(field)">
                  {{ fieldSourceLabel(field) }}
                </span>
              </div>
              <template v-if="isBoolField(field.key)">
                <el-switch v-model="draft[field.key]" active-value="1" inactive-value="0" />
              </template>
              <template v-else>
                <el-input
                  v-model="draft[field.key]"
                  clearable
                  :placeholder="fieldPlaceholder(field)"
                />
              </template>
            </div>
          </div>

          <div v-if="group.id === 'deploy'" class="preset-row deploy-intro">
            <p class="preset-hint">
              对话「部署到预发」→ 确认卡 → 发版。先开总开关，改完点右上角「保存并热更新」。
            </p>
          </div>

          <!-- 部署：按执行方式拆分，避免 GitHub / SSH 字段堆在一起 -->
          <div v-if="group.id === 'deploy'" class="fields deploy-fields">
            <template v-for="field in deployCommonFields(group)" :key="field.key">
              <div class="field-row">
                <div class="field-label">
                  <span>
                    <span v-if="field.required" class="req-star" title="必填">*</span>{{ deployFieldLabel(field) }}
                  </span>
                  <span class="source-tag" :data-src="fieldSourceAttr(field)">
                    {{ fieldSourceLabel(field) }}
                  </span>
                </div>
                <template v-if="field.key === 'DEPLOY_CI_PROVIDER'">
                  <div class="preset-chips">
                    <button
                      v-for="p in DEPLOY_PROVIDER_PRESETS"
                      :key="p.id"
                      type="button"
                      class="preset-chip"
                      :class="{ active: deployProvider === p.id }"
                      @click="draft.DEPLOY_CI_PROVIDER = p.id"
                    >
                      {{ p.label }}
                    </button>
                  </div>
                  <div class="field-meta">{{ deployProviderHint }}</div>
                </template>
                <template v-else-if="isBoolField(field.key)">
                  <el-switch v-model="draft[field.key]" active-value="1" inactive-value="0" />
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
                    <span v-if="field.configured">已配置</span>
                    <span v-else>尚未配置</span>
                    <button
                      v-if="field.has_ui_override"
                      type="button"
                      class="clear-link"
                      @click="markClear(field.key)"
                    >
                      清除覆盖
                    </button>
                  </div>
                </template>
                <template v-else>
                  <el-input
                    v-model="draft[field.key]"
                    clearable
                    :placeholder="deployFieldPlaceholder(field)"
                  />
                </template>
              </div>
            </template>

            <h3 class="deploy-section-title">
              {{ deployProvider === 'local_ssh' ? '本机 SSH' : 'GitHub Actions' }}
            </h3>
            <template v-for="field in deployProviderFields(group)" :key="field.key">
              <div class="field-row">
                <div class="field-label">
                  <span>{{ deployFieldLabel(field) }}</span>
                  <span class="source-tag" :data-src="fieldSourceAttr(field)">
                    {{ fieldSourceLabel(field) }}
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
                  <div class="field-meta">
                    <span v-if="field.configured">已配置</span>
                    <span v-else>尚未配置</span>
                    <button
                      v-if="field.has_ui_override"
                      type="button"
                      class="clear-link"
                      @click="markClear(field.key)"
                    >
                      清除覆盖
                    </button>
                  </div>
                </template>
                <template v-else>
                  <el-input
                    v-model="draft[field.key]"
                    clearable
                    :placeholder="deployFieldPlaceholder(field)"
                  />
                </template>
              </div>
            </template>

            <button
              type="button"
              class="deploy-advanced-toggle"
              @click="showDeployAdvanced = !showDeployAdvanced"
            >
              {{ showDeployAdvanced ? '收起高级选项' : '高级选项' }}
            </button>
            <template v-if="showDeployAdvanced">
              <template v-for="field in deployAdvancedFields(group)" :key="field.key">
                <div class="field-row">
                  <div class="field-label">
                    <span>{{ deployFieldLabel(field) }}</span>
                    <span class="source-tag" :data-src="fieldSourceAttr(field)">
                      {{ fieldSourceLabel(field) }}
                    </span>
                  </div>
                  <template v-if="isBoolField(field.key)">
                    <el-switch v-model="draft[field.key]" active-value="1" inactive-value="0" />
                  </template>
                  <template v-else>
                    <el-input
                      v-model="draft[field.key]"
                      clearable
                      :placeholder="deployFieldPlaceholder(field)"
                    />
                  </template>
                </div>
              </template>
            </template>
          </div>

          <!-- 非 MES / 非部署 / 非审码：通用字段列表 -->
          <div
            v-if="group.id !== 'mes' && group.id !== 'deploy' && group.id !== 'git_review'"
            class="fields"
          >
            <div v-for="field in group.fields" :key="field.key" class="field-row">
              <div class="field-label">
                <span>
                  <span v-if="field.required" class="req-star" title="必填">*</span>{{ field.label }}
                </span>
                <span class="source-tag" :data-src="fieldSourceAttr(field)">
                  {{ fieldSourceLabel(field) }}
                </span>
              </div>

              <template v-if="isBoolField(field.key)">
                <el-switch
                  v-model="draft[field.key]"
                  active-value="1"
                  inactive-value="0"
                />
                <div v-if="field.example || field.hint" class="field-meta">
                  <span v-if="field.example">示例：{{ field.example }}</span>
                  <span v-if="field.hint">{{ field.hint }}</span>
                </div>
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
                <div v-if="field.example || field.hint" class="field-meta">
                  <span v-if="field.example">示例：{{ field.example }}</span>
                  <span v-if="field.hint">{{ field.hint }}</span>
                </div>
              </template>

              <template v-else>
                <el-input
                  v-model="draft[field.key]"
                  clearable
                  :placeholder="fieldPlaceholder(field)"
                />
                <div v-if="field.example || field.hint" class="field-meta">
                  <span v-if="field.example">示例：{{ field.example }}</span>
                  <span v-if="field.hint">{{ field.hint }}</span>
                </div>
                <div v-else-if="field.key === 'LLM_BASE_URL'" class="field-meta">
                  例：https://api.deepseek.com/v1 、通义 https://dashscope.aliyuncs.com/compatible-mode/v1；官方 OpenAI 可留空
                </div>
                <div v-else-if="field.key === 'MAIN_MODEL'" class="field-meta">
                  例：deepseek-v4-flash、deepseek-chat；已禁止 deepseek-v4-pro（防误烧）
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
                  <span>{{ fieldDisplayLabel(field) }}</span>
                  <span class="source-tag" :data-src="fieldSourceAttr(field)">
                    {{ fieldSourceLabel(field) }}
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
            <p v-if="!visibleGroups.length" class="empty-tab">此分类暂无配置项。</p>
          </div>
        </div>
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
import IdeBridgePairCard from '../components/IdeBridgePairCard.vue'

/** 左侧分类：只改展现，保存仍提交全部 groups */
const SETTINGS_TABS = [
  {
    id: 'models',
    label: '商用模型',
    groupIds: ['llm', 'vision'],
    hint: '对话模型与视觉（识图）模型；兼容 OpenAI Chat Completions。',
  },
  {
    id: 'platform',
    label: '平台接入',
    groupIds: ['mes', 'mes_analysis'],
    hint: 'MES / ERP 平台名称、接口账号与表结构 / OpenAPI 资料。',
  },
  {
    id: 'code_dev',
    label: '写码车道',
    groupIds: ['cursor_dev'],
    hint: '本机 / Cursor 写码旁路开关与相关参数。',
  },
  {
    id: 'code_review',
    label: '审码车道',
    groupIds: ['git_review'],
    hint: '本机 VS Code Bridge 或公开 Git 仓库两种审核来源。',
  },
  {
    id: 'deploy',
    label: '自动化部署',
    groupIds: ['deploy'],
    hint: '人确认后发版到预发。',
  },
  {
    id: 'automations',
    label: '自动化推送',
    groupIds: ['automations', 'automations_bitable'],
    hint: '企微群消息与飞书多维表格写数是两套独立能力，可只开其一。',
  },
]

const REVIEW_MODE_PRESETS = [
  { id: 'vscode_bridge', label: 'vscode-bridge' },
  { id: 'git', label: 'git' },
]

const DEPLOY_PROVIDER_PRESETS = [
  { id: 'github_actions', label: 'GitHub Actions' },
  { id: 'local_ssh', label: '本机 SSH' },
]

const DEPLOY_COMMON_KEYS = [
  'DEPLOY_ENABLED',
  'DEPLOY_CI_PROVIDER',
  'DEPLOY_DEFAULT_REF',
  'DEPLOY_HEALTH_URL',
]
const DEPLOY_GITHUB_KEYS = [
  'DEPLOY_GITHUB_REPO',
  'DEPLOY_GITHUB_WORKFLOW',
  'DEPLOY_GITHUB_TOKEN',
]
const DEPLOY_SSH_KEYS = [
  'DEPLOY_LOCAL_PROJECT_PATH',
  'DEPLOY_SSH_HOST',
  'DEPLOY_SSH_USER',
  'DEPLOY_SSH_KEY_PATH',
  'DEPLOY_SSH_APP_PATH',
  'DEPLOY_SSH_RESTART_CMD',
  'DEPLOY_SSH_PORT',
]
const DEPLOY_ADVANCED_KEYS = [
  'DEPLOY_ENV_WHITELIST',
  'DEPLOY_ALLOW_PRODUCTION',
  'DEPLOY_REQUIRE_PUSHED_REF',
  'DEPLOY_HEALTH_TIMEOUT_SEC',
  'DEPLOY_HEALTH_RETRIES',
  'DEPLOY_SSH_SYNC_PAIRS',
  'DEPLOY_SSH_BUILD_STEPS',
  'DEPLOY_SSH_RSYNC_EXCLUDES',
  'DEPLOY_GITHUB_WORKFLOW_ENV_INPUT',
]

const DEPLOY_LABEL_OVERRIDES = {
  DEPLOY_ENABLED: '开启自动化部署',
  DEPLOY_CI_PROVIDER: '部署执行方式',
  DEPLOY_DEFAULT_REF: '默认分支 / tag',
  DEPLOY_HEALTH_URL: '部署后访问地址（探活）',
  DEPLOY_GITHUB_REPO: '仓库',
  DEPLOY_GITHUB_WORKFLOW: 'Workflow 文件',
  DEPLOY_GITHUB_TOKEN: 'Token',
  DEPLOY_LOCAL_PROJECT_PATH: '本地项目路径',
  DEPLOY_SSH_HOST: '主机',
  DEPLOY_SSH_USER: '用户',
  DEPLOY_SSH_KEY_PATH: '私钥路径',
  DEPLOY_SSH_APP_PATH: '远端目录',
  DEPLOY_SSH_RESTART_CMD: '远端重启命令',
  DEPLOY_SSH_PORT: 'SSH 端口',
  DEPLOY_ENV_WHITELIST: '允许的环境',
  DEPLOY_ALLOW_PRODUCTION: '允许生产环境',
  DEPLOY_REQUIRE_PUSHED_REF: '要求已存在的 ref',
  DEPLOY_HEALTH_TIMEOUT_SEC: '探活超时（秒）',
  DEPLOY_HEALTH_RETRIES: '探活重试次数',
  DEPLOY_SSH_SYNC_PAIRS: '同步路径对（local:remote）',
  DEPLOY_SSH_BUILD_STEPS: '构建步骤（目录:命令）',
  DEPLOY_SSH_RSYNC_EXCLUDES: 'rsync 排除项',
  DEPLOY_GITHUB_WORKFLOW_ENV_INPUT: 'Workflow 环境输入名',
}

const activeTab = ref('models')
const reviewMode = ref('vscode_bridge')
const showDeployAdvanced = ref(false)

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

const activeTabMeta = computed(() => SETTINGS_TABS.find((t) => t.id === activeTab.value) || null)

const visibleGroups = computed(() => {
  const ids = activeTabMeta.value?.groupIds || []
  const idSet = new Set(ids)
  return (groups.value || []).filter((g) => idSet.has(g.id))
})

const deployProvider = computed(() => {
  const raw = String(draft.value?.DEPLOY_CI_PROVIDER || 'github_actions').trim().toLowerCase()
  return raw === 'local_ssh' ? 'local_ssh' : 'github_actions'
})

const deployProviderHint = computed(() =>
  deployProvider.value === 'local_ssh'
    ? '本机构建后 SSH/rsync 到预发（适合境外 CI 连不上国内机）。'
    : '确认后触发 GitHub Actions workflow。',
)

const reviewModeHint = computed(() =>
  reviewMode.value === 'vscode_bridge'
    ? '审本机 VS Code 工程：先配对扩展，侧栏只显示在线状态。'
    : '审公开 Git HTTPS 仓库：可配置镜像前缀（默认内置镜像）。',
)

function deployFieldMap(group, keys) {
  const list = Array.isArray(group?.fields) ? group.fields : []
  const byKey = new Map(list.map((f) => [f.key, f]))
  return keys.map((k) => byKey.get(k)).filter(Boolean)
}

function deployCommonFields(group) {
  return deployFieldMap(group, DEPLOY_COMMON_KEYS)
}

function deployProviderFields(group) {
  return deployFieldMap(
    group,
    deployProvider.value === 'local_ssh' ? DEPLOY_SSH_KEYS : DEPLOY_GITHUB_KEYS,
  )
}

function deployAdvancedFields(group) {
  return deployFieldMap(group, DEPLOY_ADVANCED_KEYS)
}

function deployFieldLabel(field) {
  return DEPLOY_LABEL_OVERRIDES[field?.key] || field?.label || field?.key || ''
}

function deployFieldPlaceholder(field) {
  if (field?.example) return `示例：${field.example}`
  const examples = {
    DEPLOY_DEFAULT_REF: '例如 main 或 release-1.0',
    DEPLOY_HEALTH_URL: '例如 http://主机:端口/',
    DEPLOY_GITHUB_REPO: 'owner/repo',
    DEPLOY_GITHUB_WORKFLOW: 'deploy-staging.yml',
    DEPLOY_LOCAL_PROJECT_PATH: '本机 git 仓库根路径',
    DEPLOY_SSH_HOST: '例如 203.0.113.1',
    DEPLOY_SSH_USER: '例如 deploy',
    DEPLOY_SSH_KEY_PATH: '~/.ssh/deploy_key',
    DEPLOY_SSH_APP_PATH: '/var/www/myapp',
    DEPLOY_SSH_RESTART_CMD: '可空；如 systemctl restart myapp-api',
    DEPLOY_SSH_PORT: '22',
    DEPLOY_ENV_WHITELIST: 'staging',
    DEPLOY_HEALTH_TIMEOUT_SEC: '20',
    DEPLOY_HEALTH_RETRIES: '5',
    DEPLOY_SSH_SYNC_PAIRS: 'frontend/dist:frontend/dist,backend:backend',
    DEPLOY_SSH_BUILD_STEPS: 'frontend:npm ci,frontend:npm run build',
    DEPLOY_SSH_RSYNC_EXCLUDES: '.env,.venv,__pycache__',
    DEPLOY_GITHUB_WORKFLOW_ENV_INPUT: 'environment 或 none',
  }
  return examples[field?.key] || fieldPlaceholder(field)
}

const BOOL_KEYS = new Set([
  'CURSOR_DEV_ENABLED',
  'IDE_GIT_MIRROR_FIRST',
  'DEPLOY_ENABLED',
  'DEPLOY_ALLOW_PRODUCTION',
  'DEPLOY_REQUIRE_PUSHED_REF',
  'READONLY_SQL_ENABLED',
  'WECOM_PUSH_ENABLED',
  'WECOM_PUSH_DRY_RUN',
  'FEISHU_BITABLE_ENABLED',
  'FEISHU_BITABLE_DRY_RUN',
])

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
  if (src === 'draft') return '未保存'
  return '未设置'
}

/** 输入框已有内容但服务端仍 unset → 提示未保存，避免误以为已生效 */
function fieldSourceAttr(field) {
  const src = String(field?.source || 'unset')
  const key = field?.key
  const draftVal = draft.value?.[key]
  if (isBoolField(key)) {
    // 服务端无覆盖：开关显示默认关，但拨动后应标「未保存」
    if (src === 'unset') {
      return String(draftVal) === '1' ? 'draft' : 'unset'
    }
    const savedOn =
      String(field?.value || '').toLowerCase() === '1' ||
      String(field?.value || '').toLowerCase() === 'true'
    const draftOn = String(draftVal) === '1'
    if (draftOn !== savedOn) return 'draft'
    return src
  }
  if (src !== 'unset') return src
  if (String(draftVal ?? '').trim()) return 'draft'
  return 'unset'
}

function fieldSourceLabel(field) {
  const attr = fieldSourceAttr(field)
  if (attr === 'unset' && isBoolField(field?.key)) return '默认关'
  return sourceLabel(attr)
}

function groupDisplayLabel(group) {
  if (group?.id === 'mes') return 'MES / ERP 接入'
  if (group?.id === 'git_review') {
    return reviewMode.value === 'vscode_bridge' ? 'vscode-bridge（本机工程）' : 'git（公开仓库）'
  }
  return group?.label || ''
}

/** 前端兜底：避免 API 进程未重启时仍显示旧标签 */
const FIELD_LABEL_OVERRIDES = {
  MES_PROFILE_ID: 'MES / ERP 平台名称',
  PLATFORM_BASE_URL: 'MES / ERP 平台访问地址',
  MES_API_USERNAME: 'MES / ERP 接口账号',
  MES_API_PASSWORD: 'MES / ERP 接口密码',
  MES_API_ENTERPRISE_CODE: 'MES / ERP 企业编码',
}

function fieldDisplayLabel(field) {
  return FIELD_LABEL_OVERRIDES[field?.key] || field?.label || ''
}

function secretPlaceholder(field) {
  if (clearSecrets.value[field.key]) return '将清除界面覆盖（保存后回退环境变量）'
  if (field.configured) return '留空表示不修改；输入新值则覆盖'
  if (field.example) return `示例：${field.example}`
  return '输入 API Key'
}

function fieldPlaceholder(field) {
  if (field.example) return `示例：${field.example}`
  if (field.key === 'LLM_BASE_URL' || field.key === 'VISION_BASE_URL') {
    return 'https://api.example.com/v1'
  }
  if (field.key === 'MAIN_MODEL' || field.key === 'VISION_MODEL') return '模型 ID'
  if (field.key === 'MES_PROFILE_ID') return '现场 MES 名称，例如：车间A'
  if (field.key === 'PLATFORM_BASE_URL') return 'http://主机:端口（网页或 API 根均可）'
  if (field.key === 'MES_API_USERNAME') return 'MES / ERP 业务接口账号'
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
  overflow: hidden;
  padding: 0;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
  display: flex;
  flex-direction: column;
}

.settings-body > .loading,
.settings-body > .error-card {
  margin: 16px 24px;
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

.settings-layout {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: stretch;
  overflow: hidden;
}

.settings-nav {
  flex: 0 0 168px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px 12px;
  border-right: 1px solid var(--border-primary, #e2e8f0);
  background: #f8fafc;
  overflow-y: auto;
}

.settings-nav-item {
  display: block;
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  line-height: 1.3;
  transition: background 0.12s ease, color 0.12s ease;
}

.settings-nav-item:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.settings-nav-item.active {
  background: #fff;
  color: #0f172a;
  font-weight: 650;
  box-shadow: 0 0 0 1px #e2e8f0;
}

.settings-main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  padding: 16px 24px 40px;
}

.tab-hint {
  margin: 0 0 14px;
  font-size: 13px;
  color: var(--text-secondary, #64748b);
  line-height: 1.45;
}

.empty-tab {
  margin: 24px 0;
  font-size: 13px;
  color: #94a3b8;
}

.deploy-intro {
  margin-bottom: 4px;
  padding-bottom: 10px;
}

.deploy-section-title {
  margin: 16px 0 8px;
  font-size: 13px;
  font-weight: 650;
  color: #0f172a;
}

.deploy-advanced-toggle {
  margin: 12px 0 4px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.deploy-advanced-toggle:hover {
  color: #0f172a;
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 720px;
}

@media (max-width: 720px) {
  .settings-layout {
    flex-direction: column;
  }
  .settings-nav {
    flex: 0 0 auto;
    flex-direction: row;
    flex-wrap: wrap;
    border-right: none;
    border-bottom: 1px solid var(--border-primary, #e2e8f0);
    padding: 10px 12px;
  }
  .settings-nav-item {
    width: auto;
    padding: 8px 12px;
  }
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

.req-star {
  color: #dc2626;
  font-weight: 700;
  margin-right: 2px;
}

.preset-hint .req-star {
  margin-right: 0;
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

.source-tag[data-src='draft'] {
  background: #fff7ed;
  color: #c2410c;
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
