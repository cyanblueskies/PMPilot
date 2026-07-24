/**
 * FR-F2 — the evidence behind an answer: the exact SQL that ran and the rows it
 * returned.
 *
 * This is what makes an NL2SQL answer checkable. The prose is the model's; the
 * SQL and rows are the deterministic record it was phrased from, so a reader can
 * confirm the number rather than trust it. The SQL is collapsed by default — it
 * is there when wanted, not in the way when not.
 */

import { useState } from 'react'

import './EvidenceTable.css'

interface Props {
  sql: string | null
  rows: Record<string, unknown>[]
  rowCount: number
}

/** Render any cell value as text. null becomes an em dash, not "null". */
function cell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}

export function EvidenceTable({ sql, rows, rowCount }: Props) {
  const [showSql, setShowSql] = useState(false)

  // Column order comes from the first row's keys — the SELECT list order the
  // backend chose, which is more meaningful than an alphabetical sort.
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <div className="evidence">
      <div className="evidence__bar">
        <span className="evidence__count">
          {rowCount === 0
            ? 'No matching rows'
            : `${rowCount.toLocaleString()} row${rowCount === 1 ? '' : 's'}`}
        </span>
        {sql && (
          <button
            type="button"
            className="evidence__toggle"
            aria-expanded={showSql}
            onClick={() => setShowSql((open) => !open)}
          >
            {showSql ? 'Hide SQL' : 'Show SQL'}
          </button>
        )}
      </div>

      {showSql && sql && <pre className="evidence__sql">{sql}</pre>}

      {rows.length > 0 && (
        <div className="evidence__scroll">
          <table className="evidence__table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {columns.map((col) => (
                    <td key={col} className="numeric">
                      {cell(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
