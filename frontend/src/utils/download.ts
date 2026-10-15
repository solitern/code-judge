export function downloadTextFile(filename: string, content: string, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function weekExportFilename(week?: number | null): string {
  return Number.isInteger(week) && (week as number) >= 1 ? `week${week}.json` : 'week.json'
}

export function codeExportFilename(week?: number | null, problemId?: number | null): string {
  const weekNo = Number.isInteger(week) && (week as number) >= 1 ? week : null
  const problemNo = Number.isInteger(problemId) && (problemId as number) >= 1 ? problemId : null
  if (weekNo && problemNo) return `week${weekNo}_p${problemNo}.c`
  if (weekNo) return `week${weekNo}.c`
  if (problemNo) return `p${problemNo}.c`
  return 'code.c'
}
