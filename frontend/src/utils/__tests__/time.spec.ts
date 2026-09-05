import { describe, expect, it } from 'vitest'
import {
  minimumShanghaiDateTimeLocal,
  shanghaiDateTimeLocalToUtc,
  utcToShanghaiDateTimeLocal,
} from '../time'

describe('admin scheduling time helpers', () => {
  it('treats legacy timezone-less API timestamps as UTC', () => {
    expect(utcToShanghaiDateTimeLocal('2026-08-24T01:30:00')).toBe('2026-08-24T09:30')
  })

  it('converts a Beijing picker value to UTC without using browser timezone', () => {
    expect(shanghaiDateTimeLocalToUtc('2026-08-24T09:30')).toBe('2026-08-24T01:30:00.000Z')
  })

  it('sets the minimum to a future whole minute in Beijing time', () => {
    const now = Date.parse('2026-08-24T01:29:15.000Z')
    expect(minimumShanghaiDateTimeLocal(now)).toBe('2026-08-24T09:31')
  })
})
