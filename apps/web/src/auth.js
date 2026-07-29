const STORAGE_KEY = 'mes_auth_session'

function readFrom(store) {
  try {
    const raw = store.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data?.access_token) return null
    if (data.expires_at && Date.now() / 1000 > Number(data.expires_at) - 30) {
      try {
        store.removeItem(STORAGE_KEY)
      } catch {
        /* ignore */
      }
      return null
    }
    return data
  } catch {
    return null
  }
}

export function getSession() {
  // 嵌入会话优先读 sessionStorage（关标签即失效）；普通登录仍用 localStorage
  try {
    const embed = readFrom(sessionStorage)
    if (embed?.from_embed) return embed
  } catch {
    /* ignore */
  }
  try {
    const local = readFrom(localStorage)
    if (local) return local
  } catch {
    /* ignore */
  }
  try {
    return readFrom(sessionStorage)
  } catch {
    return null
  }
}

export function getAccessToken() {
  return getSession()?.access_token || ''
}

export function getUsername() {
  return getSession()?.username || ''
}

export function getDisplayName() {
  const s = getSession()
  return s?.display_name || s?.username || ''
}

export function getUserId() {
  const s = getSession()
  return s?.user_id != null && s.user_id !== '' ? String(s.user_id) : ''
}

export function setSession(session) {
  const payload = JSON.stringify(session)
  if (session?.from_embed) {
    try {
      sessionStorage.setItem(STORAGE_KEY, payload)
    } catch {
      /* ignore */
    }
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* ignore */
    }
    return
  }
  try {
    localStorage.setItem(STORAGE_KEY, payload)
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
  try {
    sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export function isLoggedIn() {
  return Boolean(getAccessToken())
}

export function authHeaders(extra = {}) {
  const token = getAccessToken()
  const username = getUsername()
  const headers = { ...extra }
  if (token) headers.Authorization = `Bearer ${token}`
  // 展示/兼容用；服务端归属以 JWT sub 为准
  if (username) headers['X-User-Name'] = username
  return headers
}
