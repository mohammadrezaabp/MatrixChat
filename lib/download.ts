export function downloadTextFile(content: string, filename: string, mimeType = 'application/sql;charset=utf-8') {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export function sanitizeDownloadBasename(text: string, fallback = 'query'): string {
  const cleaned = text
    .trim()
    .slice(0, 48)
    .replace(/[^\w\-]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return cleaned || fallback
}
