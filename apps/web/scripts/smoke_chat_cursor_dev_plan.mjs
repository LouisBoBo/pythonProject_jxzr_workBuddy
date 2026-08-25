/**
 * smoke: chatCursorDevPlan.js
 * 用法（仓库根）：node apps/web/scripts/smoke_chat_cursor_dev_plan.mjs
 * 用法（apps/api）：node ../web/scripts/smoke_chat_cursor_dev_plan.mjs
 */
import {
  extractDeliverablePhrases,
  isShortContinuationIntent,
  isStyleOnlyPatchIntent,
  looksLikeCursorDevFollowup,
  planCursorDevTurn,
} from '../src/chatCursorDevPlan.js'

function ok(name) {
  console.log('OK  ', name)
}
function fail(name, detail) {
  console.error('FAIL', name, detail || '')
  process.exitCode = 1
}

const phrases = extractDeliverablePhrases('帮我开发生产概览界面')
if (phrases.some((p) => p.includes('生产概览'))) ok('extract deliverable')
else fail('extract deliverable', phrases)

if (isShortContinuationIntent('继续改一下颜色')) ok('short continuation')
else fail('short continuation')

if (isStyleOnlyPatchIntent('修一下 overflow 横向溢出，不要改配色')) ok('style patch')
else fail('style patch')

const idle = { pick: { jobId: 'j1', requirement: '生产概览界面 KPI' } }
const p1 = planCursorDevTurn('继续', idle)
if (p1.mode === 'direct_followup') ok('plan short followup')
else fail('plan short followup', p1)

const p2 = planCursorDevTurn('开发一个全新登录页面', idle)
if (p2.mode === 'discuss') ok('plan new deliverable discuss')
else fail('plan new deliverable discuss', p2)

if (!looksLikeCursorDevFollowup('开发一个全新登录页面', [], idle)) ok('followup false on new')
else fail('followup false on new')

if (looksLikeCursorDevFollowup('继续', [], idle)) ok('followup true on continue')
else fail('followup true on continue')

if (!process.exitCode) console.log('SMOKE_OK chatCursorDevPlan')
