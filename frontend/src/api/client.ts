/**
 * Typed access to the backend.
 *
 * Every request goes through `request()` so that failures arrive as one error
 * type carrying a status code. The dashboard has to distinguish 404 (no such
 * project) from 409 (exists, still ingesting) from a network failure, and it
 * can only do that if the status survives the fetch.
 *
 * Paths are relative: Vite proxies `/api` to the backend in dev, so there is no
 * base URL to configure and no CORS layer on the backend to maintain.
 */

import type {
  Dashboard,
  Health,
  ProjectStatus,
  QueryResponse,
  Report,
  ReportRequested,
  ReportSummary,
  StoredAnomaly,
  SupportedQuestion,
  UploadAccepted,
} from './types'

export class ApiError extends Error {
  // Declared as a field rather than a constructor parameter property: the
  // tsconfig sets `erasableSyntaxOnly`, which forbids syntax that emits code.
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * FastAPI puts the message in `detail`, as a string for HTTPException and as a
 * list of objects for a validation failure. Both are unwrapped here so the UI
 * never has to render `[object Object]`.
 */
async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail
      if (typeof detail === 'string') return detail
      if (Array.isArray(detail)) {
        return detail
          .map((item) =>
            item && typeof item === 'object' && 'msg' in item
              ? String((item as { msg: unknown }).msg)
              : JSON.stringify(item),
          )
          .join('; ')
      }
    }
  } catch {
    // Not JSON. Fall through to the status line, which is still informative.
  }
  return `${response.status} ${response.statusText}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api${path}`, init)
  } catch {
    // fetch only rejects when the request never completed. Status 0 marks the
    // difference between "the server said no" and "there was no server".
    throw new ApiError(0, 'Cannot reach the backend. Is it running?')
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response))
  }
  return (await response.json()) as T
}

export function getHealth(): Promise<Health> {
  return request<Health>('/health')
}

export function listProjects(): Promise<ProjectStatus[]> {
  return request<ProjectStatus[]>('/projects')
}

export function getProject(projectId: number): Promise<ProjectStatus> {
  return request<ProjectStatus>(`/projects/${projectId}`)
}

export function getDashboard(
  projectId: number,
  includeSeries = true,
): Promise<Dashboard> {
  return request<Dashboard>(
    `/projects/${projectId}/dashboard?include_series=${includeSeries}`,
  )
}

export function getAnomalies(projectId: number): Promise<StoredAnomaly[]> {
  return request<StoredAnomaly[]>(`/projects/${projectId}/anomalies`)
}

export function uploadDataset(file: File): Promise<UploadAccepted> {
  const body = new FormData()
  body.append('file', file)
  // No Content-Type header: the browser has to set the multipart boundary.
  return request<UploadAccepted>('/datasets/upload', { method: 'POST', body })
}

export function getSupportedQuestions(): Promise<SupportedQuestion[]> {
  return request<SupportedQuestion[]>('/query/supported')
}

export function askQuestion(
  projectId: number,
  question: string,
): Promise<QueryResponse> {
  return request<QueryResponse>(`/projects/${projectId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
}

export type ReportStrategy = 'grounded' | 'naive'

export function generateReport(
  projectId: number,
  strategy: ReportStrategy,
): Promise<ReportRequested> {
  return request<ReportRequested>(
    `/projects/${projectId}/report/generate?strategy=${strategy}`,
    { method: 'POST' },
  )
}

export function listReports(projectId: number): Promise<ReportSummary[]> {
  return request<ReportSummary[]>(`/projects/${projectId}/reports`)
}

export function getReport(
  projectId: number,
  reportId: number,
): Promise<Report> {
  return request<Report>(`/projects/${projectId}/report/${reportId}`)
}

/** The export endpoint serves the file as a download; a plain link triggers it. */
export function reportExportUrl(
  projectId: number,
  reportId: number,
  format: 'md' | 'docx' = 'md',
): string {
  return `/api/projects/${projectId}/report/${reportId}/export?format=${format}`
}
