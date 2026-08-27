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
        <el-input
          v-model="form.prompt"
          type="textarea"
          :rows="6"
          maxlength="8000"
          show-word-limit
          placeholder="描述任务本身；不要写时间与目录（下面单独配置）"
        />
      </el-form-item>

      <el-form-item label="调度类型">
        <el-radio-group v-model="form.schedule_type">
          <el-radio value="recurring">循环执行</el-radio>
          <el-radio value="once">单次执行</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="form.schedule_type === 'recurring'" label="循环规则" prop="rrule">
        <el-select v-model="recurringPreset" class="full-width" @change="applyRecurringPreset">
          <el-option v-for="opt in recurringOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
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
          inactive-text="仅写入运行记录"
        />
        <p class="field-hint">请在「系统配置 → 自动化任务推送」填写企微群机器人 Webhook Key 并开启推送</p>
      </el-form-item>

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
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="onSave">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  AUTOMATION_SCHEDULE_PRESETS,
  findPresetByRrule,
  rruleToScheduleLabel,
} from '../automationSchedulePresets.js'

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
})

const recurringPreset = ref('daily-0900')
const onceDateTime = ref('')

const recurringOptions = computed(() => {
  const opts = schedulePresets.map((p) => ({ ...p }))
  const preset = recurringPreset.value
  if (preset.startsWith(CUSTOM_PRESET_PREFIX)) {
    const rrule = preset.slice(CUSTOM_PRESET_PREFIX.length)
    if (!opts.some((o) => o.rrule === rrule)) {
      opts.unshift({
        value: preset,
        label: rruleToScheduleLabel(rrule),
        rrule,
      })
    }
  }
  return opts
})

const rules = {
  name: [{ required: true, message: '请填写任务名称', trigger: 'blur' }],
  prompt: [{ required: true, message: '请填写执行指令', trigger: 'blur' }],
  rrule: [
    {
      validator: (_rule, _val, cb) => {
        if (form.schedule_type === 'recurring' && !form.rrule) {
          cb(new Error('请选择循环规则'))
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

function syncPresetFromRrule(rrule) {
  const raw = String(rrule || '').trim()
  const matched = findPresetByRrule(raw)
  if (matched) {
    recurringPreset.value = matched.value
    form.rrule = matched.rrule
    return
  }
  if (raw) {
    recurringPreset.value = `${CUSTOM_PRESET_PREFIX}${raw}`
    form.rrule = raw
    return
  }
  recurringPreset.value = 'daily-0900'
  form.rrule = schedulePresets.find((p) => p.value === 'daily-0900')?.rrule || ''
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
  if (raw.startsWith(CUSTOM_PRESET_PREFIX)) {
    form.rrule = raw.slice(CUSTOM_PRESET_PREFIX.length)
    return
  }
  const preset = schedulePresets.find((p) => p.value === value)
  if (preset) form.rrule = preset.rrule
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
  const cwds = form.cwdText
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
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
  })
}
</script>

<style scoped>
.auto-form {
  padding-top: 2px;
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
