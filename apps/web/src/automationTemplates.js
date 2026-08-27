/** 自动化任务模板 */

import { rruleToScheduleLabel } from './automationSchedulePresets.js'
import { DAILY_PRODUCTION_REPORT_PROMPT } from './automationProductionReportPrompt.js'

export const AUTOMATION_TEMPLATES = [
  {
    id: 'daily-ai-news',
    icon: 'news',
    title: '每日PCB+AI新闻推送',
    description: '检索并整理今日 PCB+AI 领域重要新闻，聚焦 PCB+AI；输出 3–5 条中文摘要，每条含标题、要点与来源链接（如有）。',
    prompt:
      '检索并整理今日 PCB+AI 领域重要新闻，聚焦 PCB+AI；输出 3–5 条中文摘要，每条含标题、要点与来源链接（如有）。',
    push_to_wecom: true,
    schedule_type: 'recurring',
    rrule: 'FREQ=DAILY;BYHOUR=9;BYMINUTE=0',
    scheduleLabel: '每天 09:00',
  },
  {
    id: 'weekly-work-report',
    icon: 'report',
    title: '每周工作周报',
    description: '每周五根据本周 git 提交与代码变更，汇总 ZR WorkBuddy 真实功能交付（不编造 MES 运维项）。',
    prompt:
      '生成本周 ZR WorkBuddy 工作周报：仅依据系统注入的「本周代码变更依据」（git 提交与变更文件）归纳已完成工作；' +
      '聚焦本周新增/改动的功能与代码；进行中写尚未合入或待验证项；下周计划写 2～3 条可执行事项；' +
      '语气专业简洁，适合发给团队。',
    schedule_type: 'recurring',
    rrule: 'FREQ=WEEKLY;BYDAY=FR;BYHOUR=17;BYMINUTE=0',
    scheduleLabel: '每周五 17:00',
  },
  {
    id: 'mes-daily-production-report',
    icon: 'report',
    title: '每日生产运营日报',
    description:
      '每天早上汇总昨日 MES 真实生产数据：工单、设备稼动率、产量、工序良率；早报式排版，面向领导阅读。',
    prompt: DAILY_PRODUCTION_REPORT_PROMPT,
    schedule_type: 'recurring',
    rrule: 'FREQ=DAILY;BYHOUR=8;BYMINUTE=0',
    scheduleLabel: '每天 08:00',
  },
]

export function templateIconClass(icon) {
  return `tpl-icon tpl-icon--${icon || 'default'}`
}

export function scheduleSummary(item) {
  if (!item) return ''
  if (item.schedule_type === 'once') {
    return item.scheduled_at ? `单次 · ${formatScheduleAt(item.scheduled_at)}` : '单次执行'
  }
  return item.scheduleLabel || rruleToScheduleLabel(item.rrule) || '循环执行'
}

function formatScheduleAt(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
