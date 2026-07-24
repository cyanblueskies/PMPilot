/**
 * FR-A3 — what the field mapping actually did.
 *
 * The point of showing this is that a Jira export with a missing column does
 * not fail; it succeeds with fewer KPIs. Without this panel the user meets that
 * as an empty chart later and has no way to connect it back to the file. So the
 * degraded KPIs are stated in terms of what is now unavailable, not in terms of
 * which internal field name was absent.
 */

import type { UploadAccepted } from '../api/types'
import './MappingReport.css'

/** `story_points` -> `Story points`. Internal names are not user-facing. */
function humanise(field: string): string {
  const spaced = field.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function Row({
  tone,
  label,
  children,
}: {
  tone: 'ok' | 'warn' | 'info'
  label: string
  children: React.ReactNode
}) {
  return (
    <div className={`mapping__row mapping__row--${tone}`}>
      <span className="mapping__label">{label}</span>
      <span className="mapping__value">{children}</span>
    </div>
  )
}

export function MappingReport({ result }: { result: UploadAccepted }) {
  const unparsed = Object.entries(result.unparsed_values)

  // The backend groups several KPIs into one string ("velocity, scope creep")
  // because one missing column disables several. Flattening them gives a single
  // flat list of what is gone, rather than two levels of separator the reader
  // has to decode.
  const lostKpis = [
    ...new Set(result.degraded_kpis.flatMap((entry) => entry.split(', '))),
  ]

  return (
    <div className="mapping">
      <Row tone="ok" label="Rows accepted">
        <span className="numeric">{result.row_count.toLocaleString()}</span>
        {result.dropped_rows > 0 && (
          <span className="mapping__aside">
            {' '}
            — {result.dropped_rows.toLocaleString()} dropped as duplicates or
            missing an issue key
          </span>
        )}
      </Row>

      {/* The headline warning. A KPI that cannot be computed is a hole in the
          dashboard, and this is the only place the cause is visible. */}
      {lostKpis.length > 0 && (
        <Row tone="warn" label="Unavailable">
          {lostKpis.join(' · ')}
          <span className="mapping__aside">
            {' '}
            — the file has no{' '}
            {result.missing_optional_fields.map(humanise).join(', ')} column
          </span>
        </Row>
      )}

      {unparsed.length > 0 && (
        <Row tone="warn" label="Unreadable values">
          {unparsed
            .map(([field, count]) => `${humanise(field)}: ${count}`)
            .join(' · ')}
          <span className="mapping__aside">
            {' '}
            — kept as empty rather than guessed
          </span>
        </Row>
      )}

      {result.unmapped_columns.length > 0 && (
        <Row tone="info" label="Columns ignored">
          <span className="mapping__mono">
            {result.unmapped_columns.join(', ')}
          </span>
        </Row>
      )}

      {lostKpis.length === 0 && unparsed.length === 0 && (
        <Row tone="ok" label="Mapping">
          Every metric is computable from this file.
        </Row>
      )}
    </div>
  )
}
