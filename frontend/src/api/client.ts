export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const csrf = getCookie('csrf_token')
  if (csrf && (options.method || 'GET').toUpperCase() !== 'GET') {
    headers.set('X-CSRF-Token', csrf)
  }
  let resp: Response
  try {
    resp = await fetch(url, { credentials: 'same-origin', ...options, headers })
  } catch {
    throw new ApiError(0, '网络连接失败，请检查网络后重试')
  }
  if (resp.status === 204) return undefined as T
  const text = await resp.text()
  let data: any = null
  try { data = text ? JSON.parse(text) : null } catch { data = null }
  if (!resp.ok) {
    if (resp.status === 401 && url.startsWith('/api/admin/') && url !== '/api/admin/login') {
      clearAdminSessionHint()
    }
    throw new ApiError(resp.status, data?.detail || `请求失败 (${resp.status})`)
  }
  return data as T
}

export function getCookie(name: string): string | null {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const m = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`))
  if (!m) return null
  try { return decodeURIComponent(m[1]) } catch { return null }
}

function clearAdminSessionHint() {
  document.cookie = 'csrf_token=; Max-Age=0; Path=/; SameSite=Strict'
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('code-judge:unauthorized'))
  }
}
