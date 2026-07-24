/**
 * The backend contract, mirrored.
 *
 * These types are hand-written against `backend/app/schemas/` and the dicts
 * returned by `services/analytics/pipeline.py`. They are not generated, so a
 * backend change that is not reflected here will type-check and then fail at
 * runtime — treat them as part of the API's definition, not as a convenience.
 *
 * Nullable fields are `| null` rather than optional on purpose: the backend
 * sends the key with a null value, and a metric that could not be computed is
 * a result the UI has to render, not an absence it can skip.
 */

export type IngestStatus = 'processing' | 'ready' | 'failed'

export interface Health {
  status: string
  database: string
}

export interface ProjectStatus {
  project_id: number
  name: string
  status: IngestStatus
  issue_count: number
  error: string | null
  created_at: string
}

/* --- Analytics (deterministic track) ------------------------------------- */

export interface ProjectMeta {
  id: number
  name: string
  issue_count: number
  sprint_count: number
  computed_at: string
}

export interface SprintVelocity {
  sprint: string
  sequence: number
  velocity: number
  completed_issues: number
  total_issues: number
  /** Done issues carrying no estimate. Reported so the figure can be qualified. */
  unestimated_completed: number
}

export interface VelocityReport {
  sprints: SprintVelocity[]
  mean: number | null
  median: number | null
  stdev: number | null
  has_unestimated_work: boolean
}

export interface DurationBySprint {
  sprint: string
  sample_size: number
  mean_days: number | null
  median_days: number | null
  p85_days: number | null
}

export interface DurationReport {
  metric: string
  /**
   * False when the source columns are missing entirely. Distinct from a metric
   * that computed to nothing: "not measurable from this export" and "nothing
   * finished yet" must not render the same way.
   */
  available: boolean
  definition: string
  sample_size: number
  mean_days: number | null
  median_days: number | null
  p85_days: number | null
  by_sprint: DurationBySprint[]
  unavailable_reason: string | null
}

export interface DefectBySprint {
  sprint: string
  total_issues: number
  defect_count: number
  defect_ratio: number | null
}

export interface DefectReport {
  total_issues: number
  defect_count: number
  defect_ratio: number | null
  defect_density: number | null
  by_sprint: DefectBySprint[]
}

export interface BurndownPoint {
  date: string
  scope_points: number
  completed_points: number
  remaining_points: number
  ideal_remaining: number
}

export interface SprintBurndown {
  sprint: string
  sequence: number
  start: string
  end: string
  initial_scope: number
  final_scope: number
  completed: number
  scope_added: number
  /** Absent when the dashboard was requested with `include_series=false`. */
  points?: BurndownPoint[]
}

export interface BurndownReport {
  available: boolean
  sprints: SprintBurndown[]
  unavailable_reason?: string | null
}

export type AnomalyType = 'velocity_drop' | 'overdue_pileup' | 'blocked_cluster'

export interface DetectedAnomaly {
  sprint: string
  sprint_sequence: number
  anomaly_type: AnomalyType
  /** 0-1. Distance past the threshold, not severity of the business impact. */
  severity: number
  /** The evidence that triggered it. Shape varies by detector, hence unknown. */
  detail: Record<string, unknown>
}

export interface Dashboard {
  project: ProjectMeta
  velocity: VelocityReport
  cycle_time: DurationReport
  lead_time: DurationReport
  defects: DefectReport
  burndown: BurndownReport
  anomalies: DetectedAnomaly[]
}

/** `GET /projects/{id}/anomalies` — the stored rows, not a recomputation. */
export interface StoredAnomaly {
  id: number
  sprint: string | null
  sprint_sequence: number | null
  anomaly_type: AnomalyType
  severity: number
  detail: Record<string, unknown>
  detected_at: string
}

/* --- Ingestion ----------------------------------------------------------- */

export interface UploadAccepted {
  project_id: number
  name: string
  status: IngestStatus
  row_count: number
  dropped_rows: number
  unmapped_columns: string[]
  missing_optional_fields: string[]
  degraded_kpis: string[]
  unparsed_values: Record<string, number>
}

/* --- Generative track ---------------------------------------------------- */

export type PromptingStrategy = 'grounded' | 'naive'

export interface SupportedQuestion {
  key: string
  description: string
  example: string
}

export interface QueryEvidence {
  generated_sql: string | null
  row_count: number
  rows: Record<string, unknown>[]
}

export interface QueryResponse {
  question: string
  answer: string
  in_scope: boolean
  evidence: QueryEvidence | null
  query_log_id: number | null
  refusal_reason: string | null
}

export interface ReportRequested {
  report_id: number
  project_id: number
  status: string
  prompting_strategy: string
}

export interface Report {
  report_id: number
  project_id: number
  title: string
  content: string
  prompting_strategy: string | null
  created_at: string
  query_log_id: number | null
}

export interface ReportSummary {
  report_id: number
  title: string
  prompting_strategy: string | null
  created_at: string
}
