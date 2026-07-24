/**
 * FR-E2 / FR-F2 — detected anomalies with traceable evidence.
 *
 * The panel's job is not to say "something is wrong" but to show *why the
 * detector fired*, in the numbers it fired on. That is the FR-F2 traceability
 * requirement, and it is also what lets a user trust or dismiss a flag rather
 * than take it on faith.
 *
 * Each anomaly type carries a different `detail` shape (the detector records
 * whatever it measured), so each has its own formatter. The formatters read
 * keys defensively: `detail` is typed `Record<string, unknown>` because it
 * genuinely varies, and a missing key must degrade to "not shown", never crash
 * the whole dashboard over one malformed row.
 */

import type { DetectedAnomaly, StoredAnomaly } from '../api/types'
import { num, percent } from '../lib/format'
import './AnomalyPanel.css'

type AnyAnomaly = DetectedAnomaly | StoredAnomaly

const TYPE_LABEL: Record<string, string> = {
  velocity_drop: 'Velocity drop',
  overdue_pileup: 'Overdue pile-up',
  blocked_cluster: 'Blocked-task cluster',
}

/** Read a number from the loosely-typed detail bag, or null if absent. */
function n(detail: Record<string, unknown>, key: string): number | null {
  const value = detail[key]
  return typeof value === 'number' ? value : null
}

function strings(detail: Record<string, unknown>, key: string): string[] {
  const value = detail[key]
  return Array.isArray(value) ? value.map(String) : []
}

interface Evidence {
  headline: string
  facts: string[]
  issueKeys: string[]
}

function describe(anomaly: AnyAnomaly): Evidence {
  const d = anomaly.detail
  const facts: string[] = []

  switch (anomaly.anomaly_type) {
    case 'velocity_drop': {
      const velocity = n(d, 'velocity')
      const median = n(d, 'project_median_velocity')
      const z = n(d, 'z_score')
      const shortfall = n(d, 'shortfall_vs_mean')
      if (velocity !== null && median !== null) {
        facts.push(`${num(velocity)} points vs a median of ${num(median)}`)
      }
      if (shortfall !== null) facts.push(`${num(shortfall)} below the mean`)
      if (z !== null) facts.push(`z = ${num(z)}`)
      return {
        headline:
          velocity !== null
            ? `Delivered ${num(velocity)} points, well below the team's usual`
            : 'Velocity fell sharply below the usual range',
        facts,
        issueKeys: [],
      }
    }

    case 'overdue_pileup': {
      const overdue = n(d, 'overdue_issues')
      const total = n(d, 'total_issues')
      const median = n(d, 'median_days_overdue')
      const max = n(d, 'max_days_overdue')
      if (overdue !== null && total !== null) {
        facts.push(`${overdue} of ${total} issues past due`)
      }
      if (median !== null) facts.push(`median ${num(median)} days overdue`)
      if (max !== null) facts.push(`worst ${num(max)} days`)
      return {
        headline:
          overdue !== null
            ? `${overdue} issues overdue and piling up`
            : 'Overdue issues piling up',
        facts,
        issueKeys: strings(d, 'example_issue_keys'),
      }
    }

    case 'blocked_cluster': {
      const blocked = n(d, 'blocked_issues')
      const assignee = typeof d.top_assignee === 'string' ? d.top_assignee : null
      const topBlocked = n(d, 'top_assignee_blocked')
      const ratio = n(d, 'blocked_ratio')
      if (blocked !== null) facts.push(`${blocked} blocked issues in the sprint`)
      if (assignee && topBlocked !== null) {
        facts.push(`${topBlocked} of them on ${assignee}`)
      }
      if (ratio !== null) facts.push(`${percent(ratio)} of the sprint blocked`)
      return {
        headline:
          assignee && topBlocked !== null
            ? `${topBlocked} blocked issues concentrated on ${assignee}`
            : 'Blocked issues clustering',
        facts,
        issueKeys: strings(d, 'example_issue_keys'),
      }
    }

    default:
      return { headline: anomaly.anomaly_type, facts: [], issueKeys: [] }
  }
}

function AnomalyCard({ anomaly }: { anomaly: AnyAnomaly }) {
  const evidence = describe(anomaly)
  const label = TYPE_LABEL[anomaly.anomaly_type] ?? anomaly.anomaly_type

  return (
    <li className="anomaly">
      <div className="anomaly__head">
        <span className="anomaly__type">{label}</span>
        {anomaly.sprint && (
          <span className="anomaly__sprint">{anomaly.sprint}</span>
        )}
        {/* Severity is distance past the threshold, not business impact — the
            label says so, so it is not mistaken for a priority. */}
        <span
          className="anomaly__severity"
          title="How far past the detection threshold, 0–1"
        >
          severity {num(anomaly.severity)}
        </span>
      </div>

      <p className="anomaly__headline">{evidence.headline}</p>

      {evidence.facts.length > 0 && (
        <ul className="anomaly__facts">
          {evidence.facts.map((fact) => (
            <li key={fact}>{fact}</li>
          ))}
        </ul>
      )}

      {evidence.issueKeys.length > 0 && (
        <div className="anomaly__evidence">
          <span className="anomaly__evidence-label">Example issues</span>
          <span className="anomaly__keys">
            {evidence.issueKeys.slice(0, 10).join(', ')}
          </span>
        </div>
      )}
    </li>
  )
}

export function AnomalyPanel({ anomalies }: { anomalies: AnyAnomaly[] }) {
  if (anomalies.length === 0) {
    return (
      <div className="anomaly-empty">
        <span className="anomaly-empty__tag">No anomalies</span>
        <span className="anomaly-empty__text">
          No sprint fell outside the statistical thresholds.
        </span>
      </div>
    )
  }

  return (
    <ul className="anomaly-list">
      {anomalies.map((anomaly, i) => (
        <AnomalyCard
          key={'id' in anomaly ? anomaly.id : `${anomaly.anomaly_type}-${i}`}
          anomaly={anomaly}
        />
      ))}
    </ul>
  )
}
