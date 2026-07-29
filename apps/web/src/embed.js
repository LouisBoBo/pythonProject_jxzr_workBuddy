/**
 * 平台嵌入：从 URL 拉起身份与页上下文。
 * 详见 docs/平台嵌入说明.md
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

/** 只读 JWT payload（不校验签名）；归属以服务端解析为准。 */
function decodeJwtPayload(token) {
  try {
    const parts = String(token).split('.')
    if (parts.length < 2) return {}
    let payload = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    payload += '='.repeat((4 - (payload.length % 4)) % 4)
    const json = atob(payload)
    const data = JSON.parse(json)
    return data && typeof data === 'object' ? data : {}
  } catch {
    return {}
  }
}

function jwtDisplayName(payload) {
  for (const key of ['preferred_username', 'username', 'unique_name', 'name']) {
    const v = payload?.[key]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

/**
 * 在创建 router 前调用：消费 URL 中的 token / 上下文，并清理敏感 query。
 * @returns {{ embedded: boolean, sessionApplied: boolean }}
 */
export function bootstrapEmbedFromUrl() {
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

  let sessionApplied = false
  if (token) {
    const prev = getSession() || {}
    const payload = decodeJwtPayload(token)
    const jwtName = jwtDisplayName(payload)
    // 归属键优先 JWT sub；URL user_id 仅作兜底展示，不当最终信任源
    const user_id =
      payload.sub != null && String(payload.sub).trim() !== ''
        ? String(payload.sub).trim()
        : userIdRaw != null && String(userIdRaw).trim() !== ''
          ? String(userIdRaw).trim()
          : prev.user_id ?? null
    const expires_at =
      typeof payload.exp === 'number'
        ? payload.exp
        : prev.expires_at ?? null
    setSession({
      ...prev,
      access_token: token,
      // 展示名：JWT > URL > 旧会话；服务端仍以 JWT sub 定归属
      username: jwtName || username || prev.username || displayName || 'embed-user',
      display_name: displayName || username || jwtName || prev.display_name || '',
      user_id,
      expires_at,
      from_embed: true,
    })
    sessionApplied = true
  }

  // 去掉敏感与一次性参数，保留 thread 等业务 query
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
  // embed=1 可保留，便于刷新仍识别嵌入布局；也可去掉仅靠 sessionStorage
  if (changed) {
    const next = url.pathname + (params.toString() ? `?${params.toString()}` : '') + url.hash
    window.history.replaceState({}, '', next)
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
