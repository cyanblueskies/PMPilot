/**
 * FR-B6 — workload distribution across the team.
 *
 * A horizontal stacked bar per person: bar length encodes total issues (so the
 * reader can compare who carries most), and the segments split done / open /
 * blocked (so the composition is visible). Blocked is the danger colour because
 * it is the actionable signal — the same concentration the blocked-cluster
 * anomaly detects, shown here per person.
 *
 * Identity is a status triple with a legend, not an arbitrary categorical
 * palette: done, open and blocked are states, which is exactly what status
 * colour is for. Issue count and points are both shown — a person with many
 * issues but few points is doing unestimated work, not light work.
 *
 * Unavailable is distinct from empty: with no assignee column the backend says
 * so, and this renders that reason rather than an empty chart.
 */

import { useState } from 'react'

import type { WorkloadReport } from '../api/types'
import { num } from '../lib/format'
import './WorkloadChart.css'

interface HoverState {
  assignee: string
  segment: 'done' | 'open' | 'blocked'
  count: number
}

export function WorkloadChart({ report }: { report: WorkloadReport }) {
  const [hover, setHover] = useState<HoverState | null>(null)

  if (!report.available) {
    return (
      <div className="workload-empty">
        <span className="workload-empty__tag">Not measurable</span>
        <span className="workload-empty__text">
          {report.unavailable_reason ??
            'No assignee data in this export.'}
        </span>
      </div>
    )
  }

  const maxIssues = Math.max(...report.people.map((p) => p.issue_count), 1)

  return (
    <div className="workload">
      <div className="workload__legend">
        <LegendKey className="workload__key--done" label="Done" />
        <LegendKey className="workload__key--open" label="Open" />
        <LegendKey className="workload__key--blocked" label="Blocked" />
      </div>

      <ul className="workload__rows">
        {report.people.map((person) => {
          // Segment widths are fractions of the widest person's bar, so bar
          // length stays comparable across people.
          const scale = 100 / maxIssues
          const segments = [
            { key: 'done' as const, count: person.done_count },
            { key: 'open' as const, count: person.open_count },
            { key: 'blocked' as const, count: person.blocked_count },
          ]

          return (
            <li key={person.assignee} className="workload__row">
              <span className="workload__name" title={person.assignee}>
                {person.assignee}
              </span>

              <div className="workload__track">
                {segments.map(
                  (seg) =>
                    seg.count > 0 && (
                      <div
                        key={seg.key}
                        className={`workload__seg workload__seg--${seg.key}`}
                        style={{ width: `${seg.count * scale}%` }}
                        onPointerEnter={() =>
                          setHover({
                            assignee: person.assignee,
                            segment: seg.key,
                            count: seg.count,
                          })
                        }
                        onPointerLeave={() => setHover(null)}
                      />
                    ),
                )}
              </div>

              <span className="workload__figures numeric">
                {person.issue_count}
                <span className="workload__points">
                  {num(person.story_points)} pts
                </span>
              </span>
            </li>
          )
        })}
      </ul>

      <div className="workload__readout" aria-live="polite">
        {hover
          ? `${hover.assignee}: ${hover.count} ${hover.segment}`
          : 'Bar length is total issues; segments split by status.'}
      </div>
    </div>
  )
}

function LegendKey({
  className,
  label,
}: {
  className: string
  label: string
}) {
  return (
    <span className="workload__key">
      <span className={`workload__swatch ${className}`} aria-hidden="true" />
      {label}
    </span>
  )
}
