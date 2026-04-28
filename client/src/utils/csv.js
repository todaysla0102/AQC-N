export function escapeCsvCell(value) {
  const normalized = String(value ?? '').replace(/"/g, '""')
  return `"${normalized}"`
}

export function downloadCsvFile(filename, content) {
  const blob = new Blob([`\uFEFF${content}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}
