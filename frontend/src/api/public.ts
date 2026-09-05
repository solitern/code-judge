import { api } from './client'
import type { PublicWeek, PublicWeekSummary, RunResponse } from '../types'

export function fetchCurrentWeek(): Promise<PublicWeek | null> {
  return api<PublicWeek | null>('/api/public/weeks/current')
}

export function fetchPublishedWeeks(): Promise<PublicWeekSummary[]> {
  return api<PublicWeekSummary[]>('/api/public/weeks')
}

export function fetchPublicWeek(weekId: number): Promise<PublicWeek> {
  return api<PublicWeek>(`/api/public/weeks/${weekId}`)
}

export function runSample(weekId: number, problemId: number, code: string, sampleIndex: number): Promise<RunResponse> {
  return api<RunResponse>('/api/public/run/sample', {
    method: 'POST',
    body: JSON.stringify({ week_id: weekId, problem_id: problemId, code, sample_index: sampleIndex })
  })
}

export function runCustom(weekId: number, problemId: number, code: string, input: string): Promise<RunResponse> {
  return api<RunResponse>('/api/public/run/custom', {
    method: 'POST',
    body: JSON.stringify({ week_id: weekId, problem_id: problemId, code, input })
  })
}

export function runAll(weekId: number, problemId: number, code: string): Promise<RunResponse> {
  return api<RunResponse>('/api/public/run/all', {
    method: 'POST',
    body: JSON.stringify({ week_id: weekId, problem_id: problemId, code })
  })
}
