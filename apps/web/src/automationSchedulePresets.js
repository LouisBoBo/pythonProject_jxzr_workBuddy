/** 自动化任务循环规则预设（弹窗与模板共用） */

export const AUTOMATION_SCHEDULE_PRESETS = [
  { value: 'daily-0800', label: '每天 08:00', rrule: 'FREQ=DAILY;BYHOUR=8;BYMINUTE=0' },
  { value: 'daily-0830', label: '每天 08:30', rrule: 'FREQ=DAILY;BYHOUR=8;BYMINUTE=30' },
  { value: 'daily-0900', label: '每天 09:00', rrule: 'FREQ=DAILY;BYHOUR=9;BYMINUTE=0' },
  { value: 'daily-1800', label: '每天 18:00', rrule: 'FREQ=DAILY;BYHOUR=18;BYMINUTE=0' },
  { value: 'weekly-fr-1700', label: '每周五 17:00', rrule: 'FREQ=WEEKLY;BYDAY=FR;BYHOUR=17;BYMINUTE=0' },
  { value: 'weekly-su-1000', label: '每周日 10:00', rrule: 'FREQ=WEEKLY;BYDAY=SU;BYHOUR=10;BYMINUTE=0' },
  { value: 'weekday-0900', label: '工作日 09:00', rrule: 'FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;BYHOUR=9;BYMINUTE=0' },
]

/** 下拉中的「自定义时间」选项值 */
export const CUSTOM_SCHEDULE_VALUE = 'custom'

export const WEEKDAY_OPTIONS = [
  { value: 'MO', label: '一' },
  { value: 'TU', label: '二' },
  { value: 'WE', label: '三' },
  { value: 'TH', label: '四' },
  { value: 'FR', label: '五' },
  { value: 'SA', label: '六' },
  { value: 'SU', label: '日' },
]

const WEEKDAY_SET = new Set(WEEKDAY_OPTIONS.map((d) => d.value))
const WORKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR']

function pad2(n) {
  return String(n).padStart(2, '0')
}

export function findPresetByRrule(rrule) {
  const raw = String(rrule || '').trim()
  return AUTOMATION_SCHEDULE_PRESETS.find((p) => p.rrule === raw) || null
}

/** 从 rrule 解析自定义编辑态 */
export function parseRruleToCustom(rrule) {
  const raw = String(rrule || '').trim()
  const byhour = Number(raw.match(/BYHOUR=(\d+)/)?.[1] ?? 9)
  const byminute = Number(raw.match(/BYMINUTE=(\d+)/)?.[1] ?? 0)
  const hour = Number.isFinite(byhour) ? Math.min(23, Math.max(0, byhour)) : 9
  const minute = Number.isFinite(byminute) ? Math.min(59, Math.max(0, byminute)) : 0
  const time = `${pad2(hour)}:${pad2(minute)}`
  const dayRaw = raw.match(/BYDAY=([A-Z,]+)/)?.[1] || ''
  const days = dayRaw
    .split(',')
    .map((d) => d.trim().toUpperCase())
    .filter((d) => WEEKDAY_SET.has(d))

  if (raw.includes('FREQ=DAILY') || (!raw.includes('FREQ=WEEKLY') && !dayRaw)) {
    return { kind: 'daily', time, weekdays: [...WORKDAYS] }
  }
  const isWorkday =
    days.length === 5 && WORKDAYS.every((d) => days.includes(d)) && days.every((d) => WORKDAYS.includes(d))
  if (isWorkday) {
    return { kind: 'weekday', time, weekdays: [...WORKDAYS] }
  }
  return {
    kind: 'weekly',
    time,
    weekdays: days.length ? days : ['MO'],
  }
}

/** 由自定义编辑态生成 rrule */
export function buildCustomRrule({ kind, time, weekdays }) {
  const m = String(time || '09:00').match(/^(\d{1,2}):(\d{2})$/)
  const hour = m ? Math.min(23, Math.max(0, Number(m[1]))) : 9
  const minute = m ? Math.min(59, Math.max(0, Number(m[2]))) : 0
  const hm = `BYHOUR=${hour};BYMINUTE=${minute}`
  const k = String(kind || 'daily')
  if (k === 'daily') {
    return `FREQ=DAILY;${hm}`
  }
  if (k === 'weekday') {
    return `FREQ=WEEKLY;BYDAY=${WORKDAYS.join(',')};${hm}`
  }
  const days = (Array.isArray(weekdays) ? weekdays : [])
    .map((d) => String(d || '').trim().toUpperCase())
    .filter((d) => WEEKDAY_SET.has(d))
  const byday = days.length ? days.join(',') : 'MO'
  return `FREQ=WEEKLY;BYDAY=${byday};${hm}`
}

export function rruleToScheduleLabel(rrule) {
  const hit = findPresetByRrule(rrule)
  if (hit) return hit.label
  const raw = String(rrule || '')
  const byhour = raw.match(/BYHOUR=(\d+)/)?.[1]
  const byminute = raw.match(/BYMINUTE=(\d+)/)?.[1]
  const time =
    byhour != null && byminute != null
      ? `${pad2(byhour)}:${pad2(byminute)}`
      : ''
  if (raw.includes('FREQ=DAILY')) return time ? `每天 ${time}` : '每天'
  if (raw.includes('FREQ=WEEKLY')) {
    const day = raw.match(/BYDAY=([A-Z,]+)/)?.[1]
    const dayMap = Object.fromEntries(WEEKDAY_OPTIONS.map((d) => [d.value, d.label]))
    const days = day ? day.split(',').map((d) => dayMap[d] || d).join('、') : ''
    const work = day === 'MO,TU,WE,TH,FR'
    if (work && time) return `工作日 ${time}`
    return days && time ? `每周${days} ${time}` : '每周'
  }
  return '循环执行'
}
