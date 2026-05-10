export const DEMO_TOKEN = 'aqc-demo-token'
const DEMO_SESSION_KEY = 'aqc_n_demo_mode'

export function isDemoMode() {
  if (typeof window === 'undefined') {
    return false
  }
  const host = String(window.location.hostname || '').toLowerCase()
  const search = new URLSearchParams(window.location.search || '')
  if (host === 'demo.aqc.symuse.com') {
    return true
  }
  if (search.get('demo') === '1') {
    try {
      window.sessionStorage.setItem(DEMO_SESSION_KEY, '1')
    } catch (error) {
      console.warn('Failed to persist demo mode', error)
    }
    return true
  }
  try {
    return window.sessionStorage.getItem(DEMO_SESSION_KEY) === '1'
  } catch (error) {
    console.warn('Failed to read demo mode', error)
    return false
  }
}
