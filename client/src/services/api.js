const base = import.meta.env.VITE_API_BASE || '/api'

const API_BASE = base.endsWith('/') ? base.slice(0, -1) : base
const JSON_CONTENT_TYPE_MARKERS = ['application/json', 'application/problem+json', '+json']

function looksLikeJsonPayload(text = '') {
  const normalized = String(text || '').trim()
  if (!normalized) {
    return false
  }
  return normalized.startsWith('{') || normalized.startsWith('[')
}

function isJsonResponse(response, text = '') {
  const contentType = String(response?.headers?.get('content-type') || '').toLowerCase()
  return JSON_CONTENT_TYPE_MARKERS.some((marker) => contentType.includes(marker)) || looksLikeJsonPayload(text)
}

function stripHtmlLikeResponse(text = '') {
  return String(text || '')
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&amp;/gi, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

function extractResponseSummary(text = '') {
  const titleMatch = String(text || '').match(/<title[^>]*>([\s\S]*?)<\/title>/i)
  const title = stripHtmlLikeResponse(titleMatch?.[1] || '')
  if (title) {
    return title.slice(0, 120)
  }
  return stripHtmlLikeResponse(text).slice(0, 120)
}

function buildHttpErrorMessage(response, text = '') {
  const status = Number(response?.status || 0)
  const summary = extractResponseSummary(text)
  const genericSummary = !summary || /^internal server error$/i.test(summary) || /^server error$/i.test(summary)

  if (status >= 500) {
    if (!genericSummary) {
      return `服务器异常：${summary}（HTTP ${status}）`
    }
    return `服务器开小差了，请稍后重试（HTTP ${status}）`
  }
  if (status === 404) {
    return genericSummary ? '请求地址不存在（HTTP 404）' : `${summary}（HTTP 404）`
  }
  if (status === 401) {
    return '登录状态已失效，请重新登录'
  }
  if (status === 403) {
    return genericSummary ? '当前账号无权执行此操作（HTTP 403）' : `${summary}（HTTP 403）`
  }
  if (summary) {
    return `${summary}（HTTP ${status}）`
  }
  return `请求失败（HTTP ${status}）`
}

function buildHeaders(token, { hasJsonBody = false, extraHeaders = {} } = {}) {
  const headers = {
    Accept: 'application/json',
    ...extraHeaders,
  }

  if (hasJsonBody) {
    headers['Content-Type'] = 'application/json'
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  return headers
}

export async function apiRequest(path, options = {}) {
  const {
    method = 'GET',
    token,
    body,
    rawBody,
    headers,
    query,
    signal,
    timeoutMs = 15000,
  } = options

  const sanitizedQuery = query
    ? Object.fromEntries(
        Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ''),
      )
    : null
  const queryString = sanitizedQuery ? `?${new URLSearchParams(sanitizedQuery).toString()}` : ''
  const hasJsonBody = body !== undefined
  const hasRawBody = rawBody !== undefined
  let timeoutId = 0
  const timeoutController = new AbortController()
  const cleanup = () => {
    if (timeoutId) {
      window.clearTimeout(timeoutId)
      timeoutId = 0
    }
  }

  if (signal) {
    if (signal.aborted) {
      return { success: false, message: '请求已取消' }
    }
    signal.addEventListener('abort', () => timeoutController.abort(), { once: true })
  }

  if (timeoutMs > 0) {
    timeoutId = window.setTimeout(() => {
      timeoutController.abort()
    }, timeoutMs)
  }

  let response
  try {
    response = await fetch(`${API_BASE}${path}${queryString}`, {
      method,
      headers: buildHeaders(token, { hasJsonBody, extraHeaders: headers }),
      body: hasJsonBody ? JSON.stringify(body) : hasRawBody ? rawBody : undefined,
      signal: timeoutController.signal,
    })
  } catch (error) {
    cleanup()
    if (error?.name === 'AbortError') {
      return { success: false, message: timeoutMs > 0 ? '请求超时，请重试' : '请求已取消' }
    }
    return { success: false, message: '网络异常，请稍后重试' }
  }
  cleanup()

  const text = await response.text()
  let payload = null

  if (isJsonResponse(response, text)) {
    try {
      payload = text ? JSON.parse(text) : null
    } catch (error) {
      payload = {
        success: false,
        message: response.ok ? '服务返回格式异常，请稍后重试' : buildHttpErrorMessage(response, text),
        raw: text,
        parseFailed: true,
        httpStatus: response.status,
      }
    }
  }

  if (!response.ok) {
    if (payload && typeof payload === 'object') {
      return {
        success: false,
        ...payload,
        message: payload.message || buildHttpErrorMessage(response, text),
        httpStatus: payload.httpStatus || response.status,
      }
    }
    return {
      success: false,
      message: buildHttpErrorMessage(response, text),
      raw: text,
      httpStatus: response.status,
    }
  }

  if (payload === null) {
    return {
      success: false,
      message: text ? '服务返回了非预期内容，请稍后重试' : '响应为空',
      raw: text,
      httpStatus: response.status,
    }
  }
  return payload
}


export const apiGet = (path, options = {}) => apiRequest(path, { ...options, method: 'GET' })
export const apiPost = (path, body, options = {}) => apiRequest(path, { ...options, method: 'POST', body })
export const apiPut = (path, body, options = {}) => apiRequest(path, { ...options, method: 'PUT', body })
export const apiDelete = (path, options = {}) => apiRequest(path, { ...options, method: 'DELETE' })
export const apiUpload = (path, file, options = {}) =>
  apiRequest(path, {
    ...options,
    method: 'POST',
    rawBody: file,
    headers: {
      ...(options.headers || {}),
      'Content-Type': file?.type || 'application/octet-stream',
      'X-File-Name': encodeURIComponent(file?.name || 'upload.xlsx'),
    },
  })
