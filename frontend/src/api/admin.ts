import { api } from './client'
import type { DashboardOut, ProblemOut, ProblemPreview, SolutionOut, TestCaseImportItem, TestCaseImportResult, TestCaseOut, WeekJsonImportResult, WeekOut, WeekPreview, RunResponse } from '../types'

export function login(username: string, password: string): Promise<{ username: string; csrf_token: string }> {
  return api('/api/admin/login', { method: 'POST', body: JSON.stringify({ username, password }) })
}
export function logout(): Promise<{ ok: boolean }> {
  return api('/api/admin/logout', { method: 'POST' })
}
export function fetchMe(): Promise<{ username: string }> {
  return api('/api/admin/me')
}
export function fetchDashboard(): Promise<DashboardOut> {
  return api('/api/admin/dashboard')
}
export function fetchWeeks(): Promise<WeekOut[]> {
  return api('/api/admin/weeks')
}
export function createWeek(week: number, title: string): Promise<WeekOut> {
  return api('/api/admin/weeks', { method: 'POST', body: JSON.stringify({ week, title }) })
}
export function updateWeek(id: number, data: Record<string, unknown>): Promise<WeekOut> {
  return api(`/api/admin/weeks/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
export function importWeekJson(id: number, file: File): Promise<WeekJsonImportResult> {
  const body = new FormData()
  body.append('file', file, file.name)
  return api(`/api/admin/weeks/${id}/import-json`, { method: 'POST', body })
}
export function deleteWeek(id: number): Promise<void> {
  return api(`/api/admin/weeks/${id}`, { method: 'DELETE' })
}
export function duplicateWeek(id: number, week: number, title: string): Promise<WeekOut> {
  return api(`/api/admin/weeks/${id}/duplicate`, { method: 'POST', body: JSON.stringify({ week, title }) })
}
export function previewWeek(id: number): Promise<WeekPreview> {
  return api(`/api/admin/weeks/${id}/preview`)
}
export function fetchProblems(weekId: number): Promise<ProblemOut[]> {
  return api(`/api/admin/weeks/${weekId}/problems`)
}
export function saveProblem(weekId: number, stableId: number, data: Record<string, unknown>): Promise<ProblemOut> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}`, { method: 'PUT', body: JSON.stringify(data) })
}
export function deleteProblem(weekId: number, stableId: number): Promise<void> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}`, { method: 'DELETE' })
}
export function fetchTestCases(weekId: number, stableId: number): Promise<TestCaseOut[]> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/testcases`)
}
export function addTestCase(weekId: number, stableId: number, data: Record<string, unknown>): Promise<TestCaseOut> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/testcases`, { method: 'POST', body: JSON.stringify(data) })
}
export function updateTestCase(id: number, data: Record<string, unknown>): Promise<TestCaseOut> {
  return api(`/api/admin/testcases/${id}`, { method: 'PATCH', body: JSON.stringify(data) })
}
export function deleteTestCase(id: number): Promise<void> {
  return api(`/api/admin/testcases/${id}`, { method: 'DELETE' })
}
export function importTestCasesJson(
  weekId: number,
  stableId: number,
  cases: TestCaseImportItem[],
  publicDefault: boolean,
): Promise<TestCaseImportResult> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/testcases/import-json`, {
    method: 'POST',
    body: JSON.stringify({ cases, public_default: publicDefault }),
  })
}
export function importTestCasesZip(weekId: number, stableId: number, file: File): Promise<TestCaseImportResult> {
  const body = new FormData()
  body.append('file', file, file.name)
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/testcases/import-zip`, { method: 'POST', body })
}
export function fetchSolution(weekId: number, stableId: number): Promise<SolutionOut> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/solution`)
}
export function saveSolution(weekId: number, stableId: number, code: string): Promise<SolutionOut> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/solution`, { method: 'PUT', body: JSON.stringify({ code }) })
}
export function verifySolution(weekId: number, stableId: number): Promise<RunResponse & { reveal?: boolean }> {
  return api(`/api/admin/weeks/${weekId}/problems/${stableId}/solution/verify`, { method: 'POST' })
}
export function fetchSnapshots(weekId: number): Promise<{ id: number; week_id: number; version: number; created_at: string }[]> {
  return api(`/api/admin/weeks/${weekId}/snapshots`)
}
export function rollbackSnapshot(weekId: number, snapshotId: number): Promise<WeekOut> {
  return api(`/api/admin/weeks/${weekId}/snapshots/${snapshotId}/rollback`, { method: 'POST' })
}

export function fetchWeekPreview(weekId: number): Promise<WeekPreview> {
  return api(`/api/admin/weeks/${weekId}/preview`)
}
export function runPreviewSample(weekId: number, problemId: number, code: string, sampleIndex: number): Promise<RunResponse> {
  return api(`/api/admin/weeks/${weekId}/preview/run-sample`, { method: 'POST', body: JSON.stringify({ problem_id: problemId, code, sample_index: sampleIndex }) })
}
export function runPreviewCustom(weekId: number, problemId: number, code: string, input: string): Promise<RunResponse> {
  return api(`/api/admin/weeks/${weekId}/preview/run-custom`, { method: 'POST', body: JSON.stringify({ problem_id: problemId, code, input }) })
}
export function runPreviewAll(weekId: number, problemId: number, code: string): Promise<RunResponse> {
  return api(`/api/admin/weeks/${weekId}/preview/run-all`, { method: 'POST', body: JSON.stringify({ problem_id: problemId, code }) })
}

export function importLegacy(path: string, dryRun: boolean): Promise<{ dry_run: boolean; weeks_imported: number; problems_imported: number; samples_imported: number; hidden_cases_imported: number; weeks_updated: number; details: string[]; errors: string[] }> {
  return api('/api/admin/import-legacy', { method: 'POST', body: JSON.stringify({ path, dry_run: dryRun }) })
}
