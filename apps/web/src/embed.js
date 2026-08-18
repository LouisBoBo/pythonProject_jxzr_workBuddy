/**
 * 平台嵌入：从 URL 拉起身份与页上下文。
 * 详见 docs/MES业务/平台嵌入说明.md
 */
import { getSession, setSession } from './auth.js'

const EMBED_FLAG_KEY = 'mes_embed_mode'
const PAGE_CTX_KEY = 'mes_page_context'

const CONTEXT_KEYS = ['entity', 'plan_no', 'order_no', 'source']

export function isEmbedMode() {
  try {
    return sessionStorage.getItem(EMBED_FLAG_KEY) === '1'
  } catch {
    return false
  }
}

export function setEmbedMode(on) {
  try {
    if (on) sessionStorage.setItem(EMBED_FLAG_KEY, '1')
    else sessionStorage.removeItem(EMBED_FLAG_KEY)
  } catch {
    /* ignore */
  }
}

export function getPageContext() {
  try {
    const raw = sessionStorage.getItem(PAGE_CTX_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    return data && typeof data === 'object' ? data : null
  } catch {
    return null
  }
}

export function setPageContext(ctx) {
  try {
    if (!ctx || !Object.keys(ctx).length) {
      sessionStorage.removeItem(PAGE_CTX_KEY)
      return
    }
    sessionStorage.setItem(PAGE_CTX_KEY, JSON.stringify(ctx))
  } catch {
    /* ignore */
  }
}

export function clearPageContext() {
  setPageContext(null)
}

function pickContext(params) {
  const ctx = {}
  for (const k of CONTEXT_KEYS) {
    const v = params.get(k)
    if (v != null && String(v).trim()) ctx[k] = String(v).trim()
  }
  if (!ctx.source && (params.get('embed') === '1' || params.get('embed') === 'true')) {
    ctx.source = 'embed'
  }
  return Object.keys(ctx).length ? ctx : null
}

/**
 * 在创建 router 前调用：消费 URL 中的 token / 上下文，并清理敏感 query。
 * 宿主 token 须经 /api/auth/exchange 换成 WorkBuddy 会话，不直接写入。
 * @returns {Promise<{ embedded: boolean, sessionApplied: boolean }>}
 */
export async function bootstrapEmbedFromUrl() {
  if (typeof window === 'undefined') return { embedded: false, sessionApplied: false }

  const url = new URL(window.location.href)
  const params = url.searchParams
  const embedFlag = params.get('embed') === '1' || params.get('embed') === 'true'
  const token = (params.get('access_token') || params.get('token') || '').trim()
  const username = (params.get('username') || params.get('user') || '').trim()
  const displayName = (params.get('display_name') || params.get('displayName') || '').trim()
  const userIdRaw = params.get('user_id') || params.get('userId')
  const ctx = pickContext(params)

  if (embedFlag) setEmbedMode(true)
  if (ctx) setPageContext(ctx)

  // 先去掉地址栏敏感参数，再兑换（避免 token 留在历史记录）
  const strip = [
    'access_token',
    'token',
    'username',
    'user',
    'display_name',
    'displayName',
    'user_id',
    'userId',
    'entity',
    'plan_no',
    'order_no',
    'source',
  ]
  let changed = false
  for (const k of strip) {
    if (params.has(k)) {
      params.delete(k)
      changed = true
    }
  }
  if (changed) {
    const next = url.pathname + (params.toString() ? `?${params.toString()}` : '') + url.hash
    window.history.replaceState({}, '', next)
  }

  let sessionApplied = false
  if (token) {
    try {
      const resp = await fetch('/api/auth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          username,
          display_name: displayName,
        }),
      })
      if (resp.ok) {
        const data = await resp.json()
        const prev = getSession() || {}
        setSession({
          ...prev,
          access_token: data.access_token,
          username: data.username || username || displayName || prev.username || 'embed-user',
          display_name: displayName || data.username || prev.display_name || '',
          user_id: data.user_id != null ? data.user_id : userIdRaw,
          expires_at: data.expires_at ?? prev.expires_at ?? null,
          from_embed: true,
        })
        sessionApplied = true
      }
    } catch {
      /* 不把未兑换的宿主 token 写入会话 */
    }
  }

  return { embedded: embedFlag || isEmbedMode(), sessionApplied }
}

export function pageContextLabel(ctx = getPageContext()) {
  if (!ctx) return ''
  const bits = []
  if (ctx.entity) bits.push(`实体 ${ctx.entity}`)
  if (ctx.plan_no) bits.push(`计划 ${ctx.plan_no}`)
  if (ctx.order_no) bits.push(`工单 ${ctx.order_no}`)
  return bits.join(' · ')
}
