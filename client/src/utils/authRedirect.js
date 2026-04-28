const DEFAULT_PUBLIC_APP_URL = 'https://aqc.symuse.com'

export const LOGIN_STATE_KEY = 'aqc_n_symuse_login_state'
export const LOGIN_RETURN_KEY = 'aqc_n_symuse_login_return'

function trimTrailingSlash(value) {
  return String(value || '').trim().replace(/\/+$/, '')
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function readStorage(key) {
  if (!canUseStorage()) {
    return ''
  }
  try {
    return sessionStorage.getItem(key) || localStorage.getItem(key) || ''
  } catch (error) {
    return ''
  }
}

function writeStorage(key, value) {
  if (!canUseStorage()) {
    return
  }
  try {
    sessionStorage.setItem(key, value)
    localStorage.setItem(key, value)
  } catch (error) {
    console.error(error)
  }
}

function clearStorage(key) {
  if (!canUseStorage()) {
    return
  }
  try {
    sessionStorage.removeItem(key)
    localStorage.removeItem(key)
  } catch (error) {
    console.error(error)
  }
}

export function sanitizeReturnPath(rawValue = '') {
  const raw = String(rawValue || '').trim()
  if (!raw) {
    return '/'
  }
  if (raw.startsWith('//')) {
    return '/'
  }
  if (raw.startsWith('/')) {
    return raw
  }
  try {
    const parsed = new URL(raw)
    const currentOrigin = trimTrailingSlash(window.location.origin)
    if (trimTrailingSlash(parsed.origin) === currentOrigin) {
      return `${parsed.pathname || '/'}${parsed.search || ''}${parsed.hash || ''}`
    }
  } catch (error) {
    return '/'
  }
  return '/'
}

export function resolvePublicAppOrigin() {
  const configured = trimTrailingSlash(import.meta.env.VITE_PUBLIC_APP_URL || '')
  if (configured) {
    return configured
  }

  const currentOrigin = trimTrailingSlash(window.location.origin)
  if (/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(currentOrigin)) {
    return currentOrigin
  }

  return DEFAULT_PUBLIC_APP_URL
}

export function resolveSymuseLoginRedirectUri() {
  return `${resolvePublicAppOrigin()}/login`
}

export function buildSymuseLogoutReturnTo() {
  return `${resolvePublicAppOrigin()}/login?force_login=1`
}

export function storeLoginState(state) {
  const clean = String(state || '').trim()
  if (!clean) {
    clearStorage(LOGIN_STATE_KEY)
    return
  }
  writeStorage(LOGIN_STATE_KEY, clean)
}

export function readStoredLoginState() {
  return readStorage(LOGIN_STATE_KEY).trim()
}

export function clearStoredLoginState() {
  clearStorage(LOGIN_STATE_KEY)
}

export function storePostLoginPath(path) {
  const clean = sanitizeReturnPath(path)
  writeStorage(LOGIN_RETURN_KEY, clean)
}

export function readStoredPostLoginPath() {
  return sanitizeReturnPath(readStorage(LOGIN_RETURN_KEY))
}

export function clearStoredPostLoginPath() {
  clearStorage(LOGIN_RETURN_KEY)
}

export function consumeStoredPostLoginPath() {
  const path = readStoredPostLoginPath()
  clearStoredPostLoginPath()
  return path
}
