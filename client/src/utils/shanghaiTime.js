const SHANGHAI_TIMEZONE = 'Asia/Shanghai'

function getShanghaiFormatter(options = {}) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: SHANGHAI_TIMEZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    ...options,
  })
}

export function getShanghaiParts(date = new Date()) {
  const parts = getShanghaiFormatter().formatToParts(date)
  const map = Object.fromEntries(parts.filter((item) => item.type !== 'literal').map((item) => [item.type, item.value]))
  return {
    year: map.year || '0000',
    month: map.month || '01',
    day: map.day || '01',
    hour: map.hour || '00',
    minute: map.minute || '00',
    second: map.second || '00',
  }
}

export function getShanghaiDateTimeLocalValue(date = new Date()) {
  const parts = getShanghaiParts(date)
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`
}

export function getShanghaiTimestamp(date = new Date()) {
  const parts = getShanghaiParts(date)
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}:${parts.second}`
}

export function getShanghaiMinutes(date = new Date()) {
  const parts = getShanghaiParts(date)
  return Number(parts.hour || 0) * 60 + Number(parts.minute || 0)
}

export function formatShanghaiDate(date = new Date(), locale = 'zh-CN', options = {}) {
  return new Intl.DateTimeFormat(locale, {
    timeZone: SHANGHAI_TIMEZONE,
    ...options,
  }).format(date)
}
