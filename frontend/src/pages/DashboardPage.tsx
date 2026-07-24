/**
 * FR-E1 — the KPI view for one project.
 *
 * The derivation functions below are the whole point of this file. Each turns a
 * report into a tile, and each has to decide between three outcomes that the
 * backend deliberately keeps separate:
 *
 *   a value          the metric computed
 *   no data yet      computable, but the sample is empty
 *   not measurable   the source column is absent from the export
 *
 * Rendering the second and third the same way would tell a user their team
 * finished nothing when in fact their CSV was missing a column.
 */

import { useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'

import { getDashboard } from '../api/client'
import type {
  DefectReport,
  DetectedAnomaly,
  DurationReport,
  VelocityReport,
} from '../api/types'
import { AnomalyPanel } from '../components/AnomalyPanel'
import { Async } from '../components/Async'
import { KpiRow, KpiTile } from '../components/KpiTile'
import type { KpiTileProps } from '../components/KpiTile'
import { QueryPanel } from '../components/QueryPanel'
import { ReportPanel } from '../components/ReportPanel'
import { VelocityChart } from '../components/VelocityChart'
import { useAsync } from '../hooks/useAsync'
import { dateTime, days, num, percent } from '../lib/format'
import './DashboardPage.css'

function velocityTile(report: VelocityReport): KpiTileProps {
  if (!report.available) {
    return {
      label: 'Velocity',
      value: null,
      unavailable:
        report.unavailable_reason ??
        'No story point estimates on completed work.',
    }
  }
  if (report.sprints.length === 0 || report.median === null) {
    return { label: 'Velocity', value: null }
  }
  return {
    label: 'Velocity',
    value: num(report.median),
    unit: 'pts / sprint',
    detail: (
      <>
        median · mean {report.mean === null ? '—' : num(report.mean)}
        {report.stdev !== null && ` · σ ${num(report.stdev)}`} ·{' '}
        {report.sprints.length} sprints
      </>
    ),
    // A real number computed from partial data. Stated rather than silently
    // folded in, because counting an unestimated issue as zero understates
    // velocity and dropping it hides that the figure is incomplete.
    caveat: report.has_unestimated_work
      ? 'Some completed issues carried no estimate.'
      : undefined,
  }
}

function durationTile(label: string, report: DurationReport): KpiTileProps {
  if (!report.available) {
    return {
      label,
      value: null,
      unavailable:
        report.unavailable_reason ?? 'The source columns are absent from this export.',
    }
  }
  if (report.sample_size === 0 || report.median_days === null) {
    return { label, value: null }
  }
  return {
    label,
    value: num(report.median_days),
    unit: 'days',
    detail: (
      <>
        median · 85th pct{' '}
        {report.p85_days === null ? '—' : days(report.p85_days)} · n=
        {report.sample_size}
      </>
    ),
  }
}

function defectTile(report: DefectReport): KpiTileProps {
  if (report.defect_ratio === null) {
    return { label: 'Defect ratio', value: null }
  }
  return {
    label: 'Defect ratio',
    value: percent(report.defect_ratio),
    detail: (
      <>
        {report.defect_count.toLocaleString()} of{' '}
        {report.total_issues.toLocaleString()} issues
        {report.defect_density !== null &&
          ` · ${num(report.defect_density)} per delivered point`}
      </>
    ),
  }
}

/** Sprint names carrying a velocity_drop, so the chart can emphasise them. */
function flaggedSprints(anomalies: DetectedAnomaly[]): Set<string> {
  return new Set(
    anomalies
      .filter((a) => a.anomaly_type === 'velocity_drop')
      .map((a) => a.sprint),
  )
}

export function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const id = Number(projectId)

  const [state, reload] = useAsync(
    useCallback(() => getDashboard(id, false), [id]),
  )

  return (
    <>
      <Link to="/" className="crumb">
        ← All projects
      </Link>

      <Async
        state={state}
        onRetry={reload}
        loadingLabel="Computing KPIs…"
        renderError={(error, httpStatus) =>
          // 409 is not a fault: the project exists and is still ingesting. A
          // generic error would send the user looking for a problem that will
          // resolve on its own.
          httpStatus === 409 ? (
            <div className="async">
              <span className="async__title">Still processing</span>
              <span className="async__detail">{error}</span>
              <button type="button" className="button" onClick={reload}>
                Check again
              </button>
            </div>
          ) : undefined
        }
      >
        {(data) => (
          <>
            <header className="dash__head">
              <div>
                <h2 className="dash__title">{data.project.name}</h2>
                <p className="dash__meta numeric">
                  {data.project.issue_count.toLocaleString()} issues ·{' '}
                  {data.project.sprint_count} sprints · computed{' '}
                  {dateTime(data.project.computed_at)}
                </p>
              </div>
              <button type="button" className="button" onClick={reload}>
                Recompute
              </button>
            </header>

            <KpiRow>
              <KpiTile {...velocityTile(data.velocity)} />
              <KpiTile {...durationTile('Cycle time', data.cycle_time)} />
              <KpiTile {...durationTile('Lead time', data.lead_time)} />
              <KpiTile {...defectTile(data.defects)} />
            </KpiRow>

            <p className="dash__definitions">
              {data.cycle_time.definition} · {data.lead_time.definition}
            </p>

            {data.velocity.available && (
              <div className="card dash__chart">
                <VelocityChart
                  sprints={data.velocity.sprints}
                  median={data.velocity.median}
                  flagged={flaggedSprints(data.anomalies)}
                />
              </div>
            )}

            <section className="section dash__anomalies">
              <div className="section__head">
                <h3 className="section__title">
                  Anomalies
                  <span className="section__count">
                    {data.anomalies.length}
                  </span>
                </h3>
              </div>
              <AnomalyPanel anomalies={data.anomalies} />
            </section>

            <section className="section dash__query">
              <div className="section__head">
                <h3 className="section__title">Ask</h3>
              </div>
              <QueryPanel projectId={id} />
            </section>

            <section className="section dash__report">
              <div className="section__head">
                <h3 className="section__title">Executive summary</h3>
              </div>
              <ReportPanel projectId={id} />
            </section>
          </>
        )}
      </Async>
    </>
  )
}
