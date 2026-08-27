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

export function findPresetByRrule(rrule) {
  const raw = String(rrule || '').trim()
  return AUTOMATION_SCHEDULE_PRESETS.find((p) => p.rrule === raw) || null
}

export function rruleToScheduleLabel(rrule) {
  const hit = findPresetByRrule(rrule)
  if (hit) return hit.label
  const raw = String(rrule || '')
  const byhour = raw.match(/BYHOUR=(\d+)/)?.[1]
  const byminute = raw.match(/BYMINUTE=(\d+)/)?.[1]
  const time =
    byhour != null && byminute != null
      ? `${String(byhour).padStart(2, '0')}:${String(byminute).padStart(2, '0')}`
      : ''
  if (raw.includes('FREQ=DAILY')) return time ? `每天 ${time}` : '每天'
  if (raw.includes('FREQ=WEEKLY')) {
    const day = raw.match(/BYDAY=([A-Z,]+)/)?.[1]
    const dayMap = { MO: '一', TU: '二', WE: '三', TH: '四', FR: '五', SA: '六', SU: '日' }
    const days = day ? day.split(',').map((d) => dayMap[d] || d).join('、') : ''
    return days && time ? `每周${days} ${time}` : '每周'
  }
  return '循环执行'
}
