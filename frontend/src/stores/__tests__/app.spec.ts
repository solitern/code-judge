import { beforeEach, describe, expect, it, vi } from 'vitest'

class MemoryStorage {
  private store = new Map<string, string>()
  getItem(key: string): string | null { return this.store.has(key) ? this.store.get(key)! : null }
  setItem(key: string, value: string): void { this.store.set(key, value) }
  removeItem(key: string): void { this.store.delete(key) }
  clear(): void { this.store.clear() }
}

describe('code storage keys', () => {
  beforeEach(() => {
    const storage = new MemoryStorage()
    ;(globalThis as any).localStorage = storage
    vi.resetModules()
  })

  it('builds keys from week, problem and version', async () => {
    const mod = await import('../app')
    expect(mod.codeKey(10, 2, 3)).toBe('code-judge:10:2:3')
  })

  it('saves and restores code', async () => {
    const mod = await import('../app')
    mod.saveCode(10, 1, 1, 'int main(){}')
    expect(mod.loadCode(10, 1, 1, 'fallback')).toBe('int main(){}')
  })

  it('falls back to template when version changes', async () => {
    const mod = await import('../app')
    mod.saveCode(10, 1, 1, 'old code')
    expect(mod.loadCode(10, 1, 2, 'template')).toBe('template')
  })

  it('reset removes stored code', async () => {
    const mod = await import('../app')
    mod.saveCode(10, 1, 1, 'int main(){}')
    mod.resetCode(10, 1, 1)
    expect(mod.loadCode(10, 1, 1, 'fallback')).toBe('fallback')
  })
})
