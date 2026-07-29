const STORAGE_KEY = 'mes_auth_session'

export function getSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data?.access_token) return null
    if (data.expires_at && Date.now() / 1000 > Number(data.expires_at) - 30) {
      clearSession()
      return null
    }
    return data
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
  localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
}

export function clearSession() {
  localStorage.removeItem(STORAGE_KEY)
}

export function isLoggedIn() {
  return Boolean(getAccessToken())
}

export function authHeaders(extra = {}) {
  const token = getAccessToken()
  const username = getUsername()
  const headers = { ...extra }
  if (token) headers.Authorization = `Bearer ${token}`
  if (username) headers['X-User-Name'] = username
  return headers
}
