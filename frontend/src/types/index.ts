export interface PublicSample {
  id: number
  input: string
  output: string
}

export interface PublicProblem {
  id: number
  title: string
  description: string
  input_format: string
  output_format: string
  hint: string
  template: string
  time_limit_ms: number
  memory_limit_mb: number
  output_limit_kb: number
  version: number
  samples: PublicSample[]
}

export interface PublicWeek {
  id: number
  week: number
  title: string
  notice: string
  problems: PublicProblem[]
}

export interface PublicWeekSummary {
  id: number
  week: number
  title: string
  problem_count: number
  publish_at: string
}

export interface RunCaseResult {
  case_id: number
  passed: boolean | null
  status: string
  time_ms: number | null
  memory_kb: number | null
  input?: string | null
  expected?: string | null
  actual?: string | null
  stderr?: string | null
}

export interface RunResponse {
  mode: string
  status: string
  summary: string
  compiled: boolean
  compile_error: string | null
  passed_count: number
  total_count: number
  results: RunCaseResult[]
}

export interface WeekOut {
  id: number
  week: number
  title: string
  notice: string
  status: string
  publish_at: string | null
  published_at: string | null
  archived_at: string | null
  created_at: string
  updated_at: string
  problem_count: number
  version: number
  has_unverified_solution: boolean
}

export interface WeekJsonImportResult {
  title: string
  problems_imported: number
  samples_imported: number
  hidden_cases_imported: number
  solutions_imported: number
}

export interface DashboardOut {
  current_public_week: WeekOut | null
  next_scheduled_publish: WeekOut | null
  draft_count: number
  scheduled_count: number
  published_count: number
  archived_count: number
  last_updated_at: string | null
  runner_status: string
  runner_concurrency: number
  judge_max_concurrency: number
  judge_queue_size: number
}

export interface ProblemOut {
  id: number
  week_id: number
  stable_id: number
  title: string
  description: string
  input_format: string
  output_format: string
  hint: string
  template: string
  time_limit_ms: number
  memory_limit_mb: number
  output_limit_kb: number
  sort_order: number
  version: number
  has_solution: boolean
  solution_verified: boolean
}

export interface TestCaseOut {
  id: number
  problem_id: number
  is_public: boolean
  input: string
  output: string
  sort_order: number
  enabled: boolean
}

export interface TestCaseImportItem {
  input: string
  output: string
  is_public?: boolean
  enabled?: boolean
}

export interface TestCaseImportResult {
  imported: number
  solution_imported: boolean
}

export interface ProblemPreview {
  id: number
  stable_id: number
  title: string
  description: string
  input_format: string
  output_format: string
  hint: string
  template: string
  time_limit_ms: number
  memory_limit_mb: number
  output_limit_kb: number
  version: number
  samples: TestCaseOut[]
  hidden_cases: TestCaseOut[]
}

export interface WeekPreview {
  id: number
  week: number
  title: string
  notice: string
  status: string
  is_preview: boolean
  problems: ProblemPreview[]
}

export interface SolutionOut {
  problem_id: number
  code: string
  verified: boolean
  last_verified_at: string | null
}
