import { reactive, readonly } from 'vue'

export interface SavedCode {
  code: string
  savedAt: string
}

function storageGet(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}

function storageSet(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

function storageRemove(key: string) {
  try { localStorage.removeItem(key) } catch { /* storage can be disabled */ }
}

const state = reactive({
  theme: storageGet('code-judge-theme') || 'light',
  currentWeek: null as import('../types').PublicWeek | null,
  loadingWeek: false,
  weekError: '',
})

export function setTheme(theme: 'light' | 'dark') {
  state.theme = theme
  storageSet('code-judge-theme', theme)
  document.documentElement.dataset.theme = theme
}

export function initTheme() {
  const t = state.theme === 'dark' ? 'dark' : 'light'
  document.documentElement.dataset.theme = t
}

export function codeKey(weekId: number, problemId: number, version: number): string {
  return `code-judge:${weekId}:${problemId}:${version}`
}

export function loadCode(weekId: number, problemId: number, version: number, fallback: string): string {
  const key = codeKey(weekId, problemId, version)
  const raw = storageGet(key)
  if (raw === null) return fallback
  try {
    const parsed = JSON.parse(raw) as SavedCode
    return typeof parsed.code === 'string' ? parsed.code : fallback
  } catch {
    return fallback
  }
}

export function saveCode(weekId: number, problemId: number, version: number, code: string) {
  const key = codeKey(weekId, problemId, version)
  const data: SavedCode = { code, savedAt: new Date().toISOString() }
  storageSet(key, JSON.stringify(data))
}

export function resetCode(weekId: number, problemId: number, version: number) {
  storageRemove(codeKey(weekId, problemId, version))
}

export default readonly(state)
