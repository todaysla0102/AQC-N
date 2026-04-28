export const UPDATE_LOG_FALLBACK_MESSAGE = '暂时无法读取更新日志，请稍后重试。'

export function splitUpdateLogScopeTags(scope) {
  return String(scope || '')
    .split('/')
    .map((item) => item.trim())
    .filter(Boolean)
}

export function extractUpdateLogMajorVersion(version) {
  const clean = String(version || '').trim()
  const parts = clean.split('.').map((item) => item.trim()).filter(Boolean)
  if (parts.length >= 2) {
    return `${Number(parts[0])}.${Number(parts[1])}`
  }
  return clean
}

function parseVersionParts(version) {
  return String(version || '')
    .trim()
    .split('.')
    .map((item) => Number(item))
    .map((item) => (Number.isFinite(item) ? item : 0))
}

export function compareUpdateLogVersionsDesc(left, right) {
  const leftParts = parseVersionParts(left)
  const rightParts = parseVersionParts(right)
  const maxLength = Math.max(leftParts.length, rightParts.length)
  for (let index = 0; index < maxLength; index += 1) {
    const leftPart = leftParts[index] ?? 0
    const rightPart = rightParts[index] ?? 0
    if (leftPart !== rightPart) {
      return rightPart - leftPart
    }
  }
  return String(right || '').localeCompare(String(left || ''))
}

export function normalizeUpdateLogEntries(payload, { limit } = {}) {
  const entries = Array.isArray(payload?.entries) ? payload.entries : []
  const normalized = entries
    .map((item) => ({
      date: String(item?.date || '').trim(),
      version: String(item?.version || '').trim(),
      title: String(item?.title || '').trim(),
      scope: String(item?.scope || '').trim(),
      scopeTags: splitUpdateLogScopeTags(item?.scope),
      majorVersion: extractUpdateLogMajorVersion(item?.version),
      summary: String(item?.summary || '').trim(),
      highlights: Array.isArray(item?.highlights)
        ? item.highlights.map((entry) => String(entry || '').trim()).filter(Boolean)
        : [],
    }))
    .filter((item) => item.date && item.title)

  if (Number.isInteger(limit) && limit >= 0) {
    return normalized.slice(0, limit)
  }
  return normalized
}

export async function fetchUpdateLogEntries({ limit } = {}) {
  const response = await fetch(`/update-log.json?ts=${Date.now()}`, {
    cache: 'no-store',
    headers: {
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
    },
  })
  if (!response.ok) {
    throw new Error(UPDATE_LOG_FALLBACK_MESSAGE)
  }
  const payload = await response.json()
  const entries = normalizeUpdateLogEntries(payload, { limit })
  if (!entries.length) {
    throw new Error(UPDATE_LOG_FALLBACK_MESSAGE)
  }
  return {
    updatedAt: String(payload?.updatedAt || '').trim(),
    entries,
  }
}
