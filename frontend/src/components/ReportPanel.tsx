/**
 * FR-F3 / FR-F4 — generate an executive summary, read it, export it.
 *
 * Two strategies are offered, and the naive one is labelled as the raw-data
 * baseline it is. That is not an anti-pattern to hide: the grounded/naive
 * comparison is FR-D5, the paper's central experiment, and the naive arm sends
 * raw rows on purpose to measure hallucination against the grounded arm
 * (.claude/rules/experiment.md). Exposing both, on identical data, is the point.
 *
 * Generation runs in a background task making two LLM calls, so the request
 * returns 202 and the panel polls the report until its body is no longer the
 * pending marker — the same accepted-is-not-ready gap as upload.
 *
 * Graceful degradation: when the model is unavailable the backend writes the
 * failure into the report body rather than leaving it empty, so this panel
 * renders that as ordinary content and never breaks the dashboard around it.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import {
  generateReport,
  getReport,
  listReports,
  reportExportUrl,
} from '../api/client'
import type { ReportStrategy } from '../api/client'
import type { Report, ReportSummary } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { dateTime } from '../lib/format'
import { Markdown } from '../lib/markdown'
import './ReportPanel.css'

// The backend marks an in-progress report's body with this exact string.
const PENDING_MARKER = '_Generating…_'
const POLL_INTERVAL_MS = 1500
const POLL_TIMEOUT_MS = 180_000

type State =
  | { phase: 'idle' }
  | { phase: 'generating'; reportId: number; strategy: ReportStrategy }
  | { phase: 'ready'; report: Report }
  | { phase: 'error'; message: string }

const STRATEGY_LABEL: Record<ReportStrategy, string> = {
  grounded: 'Grounded',
  naive: 'Naive baseline',
}

export function ReportPanel({ projectId }: { projectId: number }) {
  const [strategy, setStrategy] = useState<ReportStrategy>('grounded')
  const [state, setState] = useState<State>({ phase: 'idle' })
  const [history, reloadHistory] = useAsync(
    useCallback(() => listReports(projectId), [projectId]),
  )

  const start = useCallback(async () => {
    setState({ phase: 'idle' })
    try {
      const requested = await generateReport(projectId, strategy)
      setState({
        phase: 'generating',
        reportId: requested.report_id,
        strategy,
      })
    } catch (error) {
      setState({
        phase: 'error',
        message: error instanceof Error ? error.message : 'Request failed.',
      })
    }
  }, [projectId, strategy])

  const openReport = useCallback(
    async (reportId: number) => {
      try {
        const report = await getReport(projectId, reportId)
        // A history item could still be mid-generation if opened immediately.
        if (report.content.trim() === PENDING_MARKER) {
          setState({
            phase: 'generating',
            reportId,
            strategy: (report.prompting_strategy as ReportStrategy) ?? 'grounded',
          })
        } else {
          setState({ phase: 'ready', report })
        }
      } catch (error) {
        setState({
          phase: 'error',
          message: error instanceof Error ? error.message : 'Request failed.',
        })
      }
    },
    [projectId],
  )

  // Poll while a generation is outstanding.
  const pollingId =
    state.phase === 'generating' ? state.reportId : null
  const onDone = useRef(reloadHistory)
  onDone.current = reloadHistory

  useEffect(() => {
    if (pollingId === null) return

    let cancelled = false
    let timer = 0
    const startedAt = Date.now()

    const tick = async () => {
      try {
        const report = await getReport(projectId, pollingId)
        if (cancelled) return

        if (report.content.trim() !== PENDING_MARKER) {
          setState({ phase: 'ready', report })
          onDone.current()
          return
        }
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          setState({
            phase: 'error',
            message:
              'The report is still generating after three minutes. Check the ' +
              'backend logs — query_logs holds the reason if a call errored.',
          })
          return
        }
        timer = window.setTimeout(tick, POLL_INTERVAL_MS)
      } catch {
        if (!cancelled) timer = window.setTimeout(tick, POLL_INTERVAL_MS)
      }
    }

    timer = window.setTimeout(tick, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [pollingId, projectId])

  const busy = state.phase === 'generating'

  return (
    <div className="report">
      <div className="report__controls">
        <div className="report__strategy" role="group" aria-label="Prompting strategy">
          {(['grounded', 'naive'] as const).map((option) => (
            <button
              key={option}
              type="button"
              className={`report__strategy-btn${
                strategy === option ? ' report__strategy-btn--on' : ''
              }`}
              aria-pressed={strategy === option}
              disabled={busy}
              onClick={() => setStrategy(option)}
            >
              {STRATEGY_LABEL[option]}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="button button--primary"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? 'Generating…' : 'Generate report'}
        </button>
      </div>

      <p className="report__hint">
        {strategy === 'grounded'
          ? 'Grounded: the model receives only the computed KPIs and anomalies.'
          : 'Naive baseline: the model receives raw issue rows — the FR-D5 comparison arm.'}
      </p>

      {state.phase === 'generating' && (
        <p className="report__pending">
          <span className="report__spinner" aria-hidden="true" />
          Generating the {STRATEGY_LABEL[state.strategy].toLowerCase()} report —
          this makes two model calls and can take a while…
        </p>
      )}

      {state.phase === 'error' && (
        <div className="report__banner report__banner--down">{state.message}</div>
      )}

      {state.phase === 'ready' && (
        <article className="report__doc card">
          <header className="report__doc-head">
            <div>
              <h4 className="report__doc-title">{state.report.title}</h4>
              <span className="report__doc-meta">
                {state.report.prompting_strategy} ·{' '}
                {dateTime(state.report.created_at)}
                {state.report.query_log_id !== null &&
                  ` · query log #${state.report.query_log_id}`}
              </span>
            </div>
            {/* Plain links: the endpoint serves each file with an attachment
                disposition, so the browser downloads rather than navigates.
                Word (FR-F4) for a dissertation appendix; Markdown for a diff or
                a paste into another tool. */}
            <div className="report__exports">
              <a
                className="button"
                href={reportExportUrl(projectId, state.report.report_id, 'docx')}
                download
              >
                Export .docx
              </a>
              <a
                className="button"
                href={reportExportUrl(projectId, state.report.report_id, 'md')}
                download
              >
                .md
              </a>
            </div>
          </header>
          <Markdown source={state.report.content} />
        </article>
      )}

      <ReportHistory
        state={history}
        onOpen={(id) => void openReport(id)}
        activeId={
          state.phase === 'ready'
            ? state.report.report_id
            : state.phase === 'generating'
              ? state.reportId
              : null
        }
      />
    </div>
  )
}

function ReportHistory({
  state,
  onOpen,
  activeId,
}: {
  state: ReturnType<typeof useAsync<ReportSummary[]>>[0]
  onOpen: (reportId: number) => void
  activeId: number | null
}) {
  if (state.status !== 'ready' || state.data.length === 0) return null

  return (
    <div className="report__history">
      <span className="report__history-label">Previous reports</span>
      <ul className="report__history-list">
        {state.data.map((report) => (
          <li key={report.report_id}>
            <button
              type="button"
              className={`report__history-item${
                report.report_id === activeId
                  ? ' report__history-item--active'
                  : ''
              }`}
              onClick={() => onOpen(report.report_id)}
            >
              <span className="report__history-strategy">
                {report.prompting_strategy}
              </span>
              <span className="report__history-date">
                {dateTime(report.created_at)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
