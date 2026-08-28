<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑自动化任务' : '添加自动化任务'"
    width="600px"
    destroy-on-close
    class="automation-edit-dialog"
    @closed="onClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" class="auto-form">
      <el-alert
        v-if="!isEdit"
        type="info"
        :closable="false"
        show-icon
        class="capability-alert"
        title="自动化任务能做什么"
      >
        <ul class="capability-list">
          <li><strong>适合：</strong>MES 查数简报、联网新闻摘要、仓库 git 周报（只读汇总）</li>
          <li><strong>不适合：</strong>改代码、Git 提交、触发部署等需人工确认的操作</li>
          <li><strong>建议：</strong>不确定时先用下方模板；保存后务必「立即测试」再看运行记录</li>
        </ul>
      </el-alert>

      <el-form-item label="任务名称" prop="name" required>
        <el-input
          v-model="form.name"
          maxlength="120"
          show-word-limit
          placeholder="例如：每日 MES 资料包巡检"
          clearable
        />
      </el-form-item>

      <el-form-item label="执行指令" prop="prompt" required>
        <div class="prompt-head">
          <el-button link type="primary" class="skeleton-btn" @click="fillPromptSkeleton">
            填入指令骨架
          </el-button>
        </div>
        <el-input
          v-model="form.prompt"
          type="textarea"
          :rows="8"
          maxlength="8000"
          show-word-limit
          :placeholder="promptPlaceholder"
        />
        <p class="field-hint">写清目标、数据来源、输出格式；时间与目录在下方单独配置，勿写进指令。</p>
      </el-form-item>

      <el-form-item label="调度类型">
        <el-radio-group v-model="form.schedule_type">
          <el-radio value="recurring">循环执行</el-radio>
          <el-radio value="once">单次执行</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="form.schedule_type === 'recurring'" label="循环规则" prop="rrule">
        <el-select v-model="recurringPreset" class="full-width" @change="applyRecurringPreset">
          <el-option
            v-for="opt in recurringOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <div v-if="isCustomSchedule" class="custom-schedule">
          <el-radio-group v-model="customKind" size="small" @change="syncCustomRrule">
            <el-radio-button value="daily">每天</el-radio-button>
            <el-radio-button value="weekday">工作日</el-radio-button>
            <el-radio-button value="weekly">每周</el-radio-button>
          </el-radio-group>
          <el-checkbox-group
            v-if="customKind === 'weekly'"
            v-model="customWeekdays"
            class="weekday-group"
            @change="syncCustomRrule"
          >
            <el-checkbox
              v-for="d in weekdayOptions"
              :key="d.value"
              :label="d.value"
            >
              周{{ d.label }}
            </el-checkbox>
          </el-checkbox-group>
          <div class="custom-time-row">
            <span class="custom-time-label">执行时间</span>
            <el-time-picker
              v-model="customTime"
              format="HH:mm"
              value-format="HH:mm"
              placeholder="选择时分"
              :clearable="false"
              class="custom-time-picker"
              @change="syncCustomRrule"
            />
          </div>
          <p class="field-hint">当前规则：{{ rruleToScheduleLabel(form.rrule) }}</p>
        </div>
      </el-form-item>

      <el-form-item v-else label="执行时间" prop="scheduled_at">
        <el-date-picker
          v-model="onceDateTime"
          type="datetime"
          placeholder="选择日期与时间"
          format="YYYY-MM-DD HH:mm"
          value-format="YYYY-MM-DDTHH:mm"
          class="full-width"
        />
      </el-form-item>

      <el-form-item label="工作目录（可选）">
        <el-input
          v-model="form.cwdText"
          placeholder="留空则使用默认；多个目录用英文逗号分隔"
          clearable
        />
      </el-form-item>

      <el-form-item label="推送到企业微信">
        <el-switch
          v-model="form.push_to_wecom"
          active-text="任务成功后推送到企微群"
          inactive-text="不推企微"
        />
        <p class="field-hint">与飞书写表互不干涉。系统配置 → 自动化推送 填写 Webhook。</p>
      </el-form-item>

      <el-form-item label="同步到飞书多维表格">
        <el-switch
          v-model="form.bitable_enabled"
          active-text="任务成功后写入飞书表"
          inactive-text="不写飞书表"
        />
        <p class="field-hint">
          与企微互不干涉。先在「系统配置 → 飞书多维表格同步」填写 App ID/Secret 并开启总开关。
        </p>
      </el-form-item>

      <template v-if="form.bitable_enabled">
        <el-form-item label="飞书 app_token" required>
          <el-input
            v-model="form.bitable_app_token"
            placeholder="basc… 或粘贴多维表格 base 链接"
            clearable
          />
        </el-form-item>
        <el-form-item label="飞书 table_id" required>
          <el-input
            v-model="form.bitable_table_id"
            placeholder="tbl…（数据表 ID）"
            clearable
          />
        </el-form-item>
        <p class="field-hint bitable-map-hint">
          查什么写什么：Agent 输出的明细会按行列入飞书（自动建列），不是固定「日报汇总」模板。
          空表即可；列表任务会写入多行（如工单号/产品/良率），汇总任务才写一行。
        </p>
      </template>

      <el-form-item label="生效区间（可选）" prop="valid_range">
        <div class="range-row">
          <el-date-picker
            v-model="form.valid_from"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            clearable
            class="range-picker"
          />
          <span class="range-sep">至</span>
          <el-date-picker
            v-model="form.valid_until"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            clearable
            class="range-picker"
          />
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <p v-if="!isEdit" class="footer-tip">保存后请在任务卡片点「立即测试」，确认摘要无误再依赖定时与企微推送。</p>
      <div class="footer-actions">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  AUTOMATION_SCHEDULE_PRESETS,
  CUSTOM_SCHEDULE_VALUE,
  WEEKDAY_OPTIONS,
  buildCustomRrule,
  findPresetByRrule,
  parseRruleToCustom,
  rruleToScheduleLabel,
} from '../automationSchedulePresets.js'

const PROMPT_SKELETON = `【目标】（一句话：要产出什么）
【数据来源】MES 查数 / 联网检索 / 本仓库 git
【查数或检索步骤】
1. …
2. …
【输出格式】
- 共几条；每条含标题、要点；（新闻类须保留来源链接）
- 查不到的数据整段省略，禁止编造
【禁止】Markdown 表格、工具名、写码/提交/部署`

const promptPlaceholder = `示例结构（也可点「填入指令骨架」）：
【目标】汇总昨日工单与设备产出
【数据来源】当前 MES
【输出格式】早报式：编号 + 要点 + 可选细分`

const CUSTOM_PRESET_PREFIX = 'custom:'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initial: { type: Object, default: null },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'save'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const isEdit = computed(() => Boolean(props.initial?.id))
const formRef = ref(null)
const schedulePresets = AUTOMATION_SCHEDULE_PRESETS
const weekdayOptions = WEEKDAY_OPTIONS

const form = reactive({
  name: '',
  prompt: '',
  schedule_type: 'recurring',
  rrule: schedulePresets[1].rrule,
  scheduled_at: null,
  valid_from: null,
  valid_until: null,
  cwdText: '',
  push_to_wecom: false,
  bitable_enabled: false,
  bitable_app_token: '',
  bitable_table_id: '',
})

const recurringPreset = ref('daily-0900')
const onceDateTime = ref('')
const customKind = ref('daily')
const customTime = ref('09:00')
const customWeekdays = ref(['MO', 'TU', 'WE', 'TH', 'FR'])

const isCustomSchedule = computed(() => recurringPreset.value === CUSTOM_SCHEDULE_VALUE)

const recurringOptions = computed(() => {
  const opts = schedulePresets.map((p) => ({ ...p }))
  opts.push({
    value: CUSTOM_SCHEDULE_VALUE,
    label: '自定义时间…',
    rrule: '',
  })
  return opts
})

const rules = {
  name: [{ required: true, message: '请填写任务名称', trigger: 'blur' }],
  prompt: [{ required: true, message: '请填写执行指令', trigger: 'blur' }],
  rrule: [
    {
      validator: (_rule, _val, cb) => {
        if (form.schedule_type !== 'recurring') {
          cb()
          return
        }
        if (!form.rrule) {
          cb(new Error('请选择或配置循环规则'))
          return
        }
        if (isCustomSchedule.value && customKind.value === 'weekly' && !customWeekdays.value.length) {
          cb(new Error('请至少选择一个星期'))
          return
        }
        cb()
      },
      trigger: 'change',
    },
  ],
  scheduled_at: [
    {
      validator: (_rule, _val, cb) => {
        if (form.schedule_type === 'once' && !onceDateTime.value) {
          cb(new Error('请选择单次执行时间'))
          return
        }
        cb()
      },
      trigger: 'change',
    },
  ],
  valid_range: [
    {
      validator: (_rule, _val, cb) => {
        if (form.valid_from && form.valid_until && form.valid_from > form.valid_until) {
          cb(new Error('结束日期不能早于开始日期'))
          return
        }
        cb()
      },
      trigger: 'change',
    },
  ],
}

function applyCustomStateFromRrule(rrule) {
  const parsed = parseRruleToCustom(rrule)
  customKind.value = parsed.kind
  customTime.value = parsed.time
  customWeekdays.value = [...parsed.weekdays]
}

function syncCustomRrule() {
  if (!isCustomSchedule.value) return
  form.rrule = buildCustomRrule({
    kind: customKind.value,
    time: customTime.value || '09:00',
    weekdays: customWeekdays.value,
  })
}

function syncPresetFromRrule(rrule) {
  const raw = String(rrule || '').trim()
  const matched = findPresetByRrule(raw)
  if (matched) {
    recurringPreset.value = matched.value
    form.rrule = matched.rrule
    applyCustomStateFromRrule(matched.rrule)
    return
  }
  if (raw) {
    recurringPreset.value = CUSTOM_SCHEDULE_VALUE
    form.rrule = raw
    applyCustomStateFromRrule(raw)
    return
  }
  recurringPreset.value = 'daily-0900'
  form.rrule = schedulePresets.find((p) => p.value === 'daily-0900')?.rrule || ''
  applyCustomStateFromRrule(form.rrule)
}

function resetFromInitial(initial) {
  form.name = initial?.name || ''
  form.prompt = initial?.prompt || ''
  form.schedule_type = initial?.schedule_type || 'recurring'
  form.rrule = initial?.rrule || schedulePresets[1].rrule
  form.scheduled_at = initial?.scheduled_at || null
  form.valid_from = initial?.valid_from || null
  form.valid_until = initial?.valid_until || null
  form.cwdText = Array.isArray(initial?.cwds) ? initial.cwds.join(', ') : ''
  form.push_to_wecom = Boolean(initial?.push_to_wecom)
  const bs = initial?.bitable_sync
  form.bitable_enabled = Boolean(bs && bs.enabled)
  form.bitable_app_token = (bs && bs.app_token) || ''
  form.bitable_table_id = (bs && bs.table_id) || ''
  onceDateTime.value = initial?.scheduled_at || ''
  syncPresetFromRrule(form.rrule)
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) resetFromInitial(props.initial)
  },
)

watch(
  () => form.schedule_type,
  (type) => {
    if (type === 'recurring' && !form.rrule) {
      applyRecurringPreset(recurringPreset.value)
    }
  },
)

function applyRecurringPreset(value) {
  const raw = String(value || '')
  if (raw === CUSTOM_SCHEDULE_VALUE) {
    if (!customTime.value) customTime.value = '09:00'
    if (!customWeekdays.value.length) {
      customWeekdays.value = ['MO', 'TU', 'WE', 'TH', 'FR']
    }
    syncCustomRrule()
    return
  }
  if (raw.startsWith(CUSTOM_PRESET_PREFIX)) {
    // 兼容旧值
    form.rrule = raw.slice(CUSTOM_PRESET_PREFIX.length)
    recurringPreset.value = CUSTOM_SCHEDULE_VALUE
    applyCustomStateFromRrule(form.rrule)
    return
  }
  const preset = schedulePresets.find((p) => p.value === value)
  if (preset) {
    form.rrule = preset.rrule
    applyCustomStateFromRrule(preset.rrule)
  }
}

async function fillPromptSkeleton() {
  if (form.prompt.trim()) {
    try {
      await ElMessageBox.confirm(
        '当前已有内容，填入骨架将覆盖执行指令。是否继续？',
        '填入指令骨架',
        { confirmButtonText: '覆盖填入', cancelButtonText: '取消', type: 'warning' },
      )
    } catch {
      return
    }
  }
  form.prompt = PROMPT_SKELETON
}

function onClosed() {
  resetFromInitial(null)
  formRef.value?.clearValidate()
}

async function onSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  if (!isEdit.value) {
    try {
      await ElMessageBox.confirm(
        '创建后请先在任务卡片点「立即测试」，在「运行记录」确认摘要符合预期，再开启企微推送。',
        '创建前提示',
        { confirmButtonText: '继续创建', cancelButtonText: '返回修改', type: 'info' },
      )
    } catch {
      return
    }
  }
  const cwds = form.cwdText
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
  if (form.bitable_enabled && (!form.bitable_app_token.trim() || !form.bitable_table_id.trim())) {
    await ElMessageBox.alert('已开启飞书写表时，请填写 app_token 与 table_id。', '缺少配置', {
      type: 'warning',
    })
    return
  }
  emit('save', {
    name: form.name.trim(),
    prompt: form.prompt.trim(),
    schedule_type: form.schedule_type,
    rrule: form.schedule_type === 'recurring' ? form.rrule : '',
    scheduled_at: form.schedule_type === 'once' ? onceDateTime.value : null,
    valid_from: form.valid_from || null,
    valid_until: form.valid_until || null,
    cwds,
    push_to_wecom: Boolean(form.push_to_wecom),
    bitable_sync: form.bitable_enabled
      ? {
          enabled: true,
          app_token: form.bitable_app_token.trim(),
          table_id: form.bitable_table_id.trim(),
          mode: 'append',
        }
      : { enabled: false },
  })
}
</script>

<style scoped>
.auto-form {
  padding-top: 2px;
}

.capability-alert {
  margin-bottom: 16px;
}

.capability-alert :deep(.el-alert__title) {
  font-size: 13px;
  font-weight: 600;
}

.capability-list {
  margin: 6px 0 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.65;
  color: var(--text-secondary);
}

.capability-list li + li {
  margin-top: 4px;
}

.prompt-head {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 4px;
}

.skeleton-btn {
  padding: 0;
  height: auto;
  font-size: 13px;
}

.footer-tip {
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
  text-align: left;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.full-width {
  width: 100%;
}

.range-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.range-picker {
  flex: 1;
  min-width: 0;
}

.range-sep {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-size: 13px;
}

.bitable-map-hint {
  margin: -8px 0 12px;
}

.custom-schedule {
  margin-top: 10px;
  padding: 12px;
  border-radius: 8px;
  background: var(--bg-secondary, #f5f7fa);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.weekday-group {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
}

.custom-time-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.custom-time-label {
  font-size: 13px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.custom-time-picker {
  width: 140px;
}

.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-tertiary);
}

.field-hint code {
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 3px;
  background: var(--bg-tertiary);
}

:deep(.automation-edit-dialog .el-dialog__footer) {
  display: block;
  padding-top: 8px;
}

:deep(.automation-edit-dialog .el-dialog__body) {
  padding-top: 8px;
  padding-bottom: 8px;
}

:deep(.auto-form .el-form-item__label) {
  font-weight: 500;
  color: var(--text-primary);
}

:deep(.auto-form .el-textarea__inner) {
  line-height: 1.6;
}
</style>
