import { describe, expect, it } from 'vitest'
import { codeExportFilename, weekExportFilename } from '../download'

describe('export filenames', () => {
  it('names a week JSON file from the saved week number', () => {
    expect(weekExportFilename(8)).toBe('week8.json')
    expect(weekExportFilename(null)).toBe('week.json')
  })

  it('names a C source file from the week and problem', () => {
    expect(codeExportFilename(3, 2)).toBe('week3_p2.c')
    expect(codeExportFilename(3, null)).toBe('week3.c')
    expect(codeExportFilename(null, 2)).toBe('p2.c')
    expect(codeExportFilename(null, null)).toBe('code.c')
  })
})
