/**
 * Cursor 写码本轮意图规划（从 ChatView 抽出）。
 * 纯函数：判断 discuss vs direct_followup，不依赖 Vue。
 */
import {
  looksLikeCodeReview,
  looksLikeGitRepoReview,
  looksLikePasteCodeAnalyze,
} from './chatIntent.js'

/**
 * 从原文抽取交付物短语（通用结构，不写死业务名）。
 * 例：「生产概览界面」→ ["生产概览界面","生产概览"]
 */
export function extractDeliverablePhrases(text) {
  const t = String(text || '')
  const out = []
  const seen = new Set()
  const re =
    /((?:[\u4e00-\u9fff]{2,10})|(?:[A-Za-z][A-Za-z0-9_-]{1,24}))(界面|页面|模块|功能|视图|看板)/g
  let m
  while ((m = re.exec(t))) {
    const full = m[0]
    let stem = m[1]
    const suffix = m[2]
    stem = stem.replace(/^(?:开发|实现|新增|搭建|建设|做|写|系统)+/, '') || stem
    if (stem.length >= 6 && /开发|实现|新增|系统/.test(m[1])) {
      stem = stem.slice(-4)
    }
    const phrase = stem.endsWith(suffix) ? stem : `${stem}${suffix}`
    for (const p of [phrase, stem, full]) {
      if (!p || p.length < 2 || seen.has(p)) continue
      if (['系统', '开发', '实现', '功能', '模块', '界面', '页面'].includes(p)) continue
      seen.add(p)
      out.push(p)
    }
  }
  return out
}

export function codingIntentTokens(text) {
  const raw = String(text || '').toLowerCase()
  const parts = raw.match(/[\u4e00-\u9fff]{2,}|[a-z0-9_]{3,}/g) || []
  return new Set(parts)
}

export function tokenOverlapRatio(a, b) {
  const A = codingIntentTokens(a)
  const B = codingIntentTokens(b)
  if (!A.size || !B.size) return 0
  let inter = 0
  for (const x of A) if (B.has(x)) inter += 1
  return inter / Math.max(A.size, B.size)
}

export function isStyleOnlyPatchIntent(text) {
  const t = String(text || '').trim()
  if (!t) return false
  const style =
    /(overflow|100vh|100vw|滚动|横向溢出|超出屏幕|视口|布局壳|纯\s*CSS|仅.*样式|页面固定|框架滚动|不[改动变].{0,6}(视觉|配色|图表|表格))/i.test(
      t,
    )
  const newDeliverable =
    /新(?:界面|页面|模块|功能)|(?:开发|实现|新增|做|写|搭建).{0,20}(?:模块|界面|页面|功能)/.test(t)
  return style && !newDeliverable
}

export function isShortContinuationIntent(text) {
  const t = String(text || '').trim()
  return (
    t.length <= 80 &&
    /^(继续|再改|改一下|补一下|加上|去掉|换成|改成|默认|还要|另外|顺带|顺便)/.test(t)
  )
}

/**
 * 按真实意图规划本轮写码路径（通用，不绑具体页面）。
 * - discuss：先讨论/选项/确认卡
 * - direct_followup：仅明确增量微调时可直开写码
 */
export function planCursorDevTurn(text, idlePick) {
  const t = String(text || '').trim()
  if (!t) return { mode: 'discuss', reason: 'empty' }
  if (looksLikePasteCodeAnalyze(t) || looksLikeCodeReview(t) || looksLikeGitRepoReview(t)) {
    return { mode: 'discuss', reason: 'other_lane' }
  }
  if (!idlePick?.pick?.jobId) {
    return { mode: 'discuss', reason: 'no_idle_job' }
  }
  if (isShortContinuationIntent(t)) {
    return { mode: 'direct_followup', reason: 'short_continuation' }
  }
  if (isStyleOnlyPatchIntent(t)) {
    return { mode: 'direct_followup', reason: 'style_patch' }
  }
  const prior = String(idlePick.pick.requirement || idlePick.pick.pendingContent || '')
  const phrases = extractDeliverablePhrases(t)
  const priorText = prior + ' ' + String(idlePick.pick.progressText || '')
  if (phrases.length) {
    const missing = phrases.filter((p) => p.length >= 2 && !priorText.includes(p))
    if (missing.length) {
      return { mode: 'discuss', reason: 'new_deliverable', missing }
    }
  }
  if (
    /(?:开发|实现|新增|做|写|搭建).{0,20}(?:模块|界面|页面|功能)|新(?:界面|页面|模块|功能)/.test(t) &&
    tokenOverlapRatio(t, prior) < 0.28
  ) {
    return { mode: 'discuss', reason: 'low_overlap_new_work' }
  }
  return { mode: 'discuss', reason: 'default_confirm' }
}

/** 同窗可否跳过确认直接写码：仅 plan=direct_followup。 */
export function looksLikeCursorDevFollowup(text, files = [], idlePick = null) {
  return planCursorDevTurn(text, idlePick).mode === 'direct_followup'
}
