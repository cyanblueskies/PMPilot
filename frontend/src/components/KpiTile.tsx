/**
 * FR-E1 — one headline metric.
 *
 * A stat tile rather than a one-bar chart: these are single current values, and
 * the reader's job is to read the number, not to compare bar lengths.
 *
 * The tile has three distinct states, and collapsing any two of them would be a
 * lie about the data:
 *
 *   value        the metric computed
 *   empty        computable, but nothing has happened yet (sample size zero)
 *   unavailable  the source column is missing — not measurable from this export
 *
 * The backend draws exactly this distinction (`DurationReport.available` vs
 * `sample_size`), and it is the difference between "your team has no completed
 * work" and "your export has no Resolved Date column".
 */

import type { ReactNode } from 'react'

import './KpiTile.css'

export interface KpiTileProps {
  label: string
  /** The formatted headline. `null` when there is nothing to show. */
  value: string | null
  unit?: string
  detail?: ReactNode
  /** Why there is no value. Rendered with a label, never colour alone. */
  unavailable?: string
  /** A qualifier on a value that is real but partial. */
  caveat?: string
}

export function KpiTile({
  label,
  value,
  unit,
  detail,
  unavailable,
  caveat,
}: KpiTileProps) {
  return (
    <div className="kpi card">
      <span className="kpi__label">{label}</span>

      {value === null ? (
        <span className="kpi__empty">
          {/* Named, not just greyed out: a status conveyed by colour alone is
              invisible to a screen reader and to a monochrome print. */}
          <span className="kpi__empty-tag">
            {unavailable ? 'Not measurable' : 'No data yet'}
          </span>
          <span className="kpi__empty-reason">{unavailable}</span>
        </span>
      ) : (
        <>
          {/* Proportional figures, not tabular: `tabular-nums` widens every
              digit to a zero and makes a large standalone number look loose.
              Tabular figures are for columns that must align. */}
          <span className="kpi__value">
            {value}
            {unit && <span className="kpi__unit">{unit}</span>}
          </span>
          {detail && <span className="kpi__detail">{detail}</span>}
          {caveat && <span className="kpi__caveat">{caveat}</span>}
        </>
      )}
    </div>
  )
}

export function KpiRow({ children }: { children: ReactNode }) {
  return <div className="kpi-row">{children}</div>
}
