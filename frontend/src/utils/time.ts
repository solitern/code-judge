const SHANGHAI_OFFSET_MS = 8 * 60 * 60 * 1000
const EXPLICIT_ZONE = /(?:z|[+-]\d{2}:\d{2})$/i
const LOCAL_DATE_TIME = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/

/** Parse API timestamps as UTC, including legacy SQLite values without a suffix. */
export function parseUtcDateTime(value: string): Date {
  return new Date(EXPLICIT_ZONE.test(value) ? value : `${value}Z`)
}

export function formatShanghaiTime(value: string | null, empty = '—'): string {
  if (!value) return empty
  const date = parseUtcDateTime(value)
  if (Number.isNaN(date.getTime())) return empty
  return date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
}

export function utcToShanghaiDateTimeLocal(value: string | null): string {
  if (!value) return ''
  const date = parseUtcDateTime(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() + SHANGHAI_OFFSET_MS).toISOString().slice(0, 16)
}

export function shanghaiDateTimeLocalToUtc(value: string): string | null {
  const match = LOCAL_DATE_TIME.exec(value)
  if (!match) return null
  const [, year, month, day, hour, minute] = match
  const utcMs = Date.UTC(+year, +month - 1, +day, +hour - 8, +minute)
  const result = new Date(utcMs)
  if (utcToShanghaiDateTimeLocal(result.toISOString()) !== value) return null
  return result.toISOString()
}

export function minimumShanghaiDateTimeLocal(nowMs = Date.now()): string {
  const nextMinute = Math.ceil((nowMs + 60_000) / 60_000) * 60_000
  return new Date(nextMinute + SHANGHAI_OFFSET_MS).toISOString().slice(0, 16)
}
