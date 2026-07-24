/**
 * FR-B2 — burndown and burnup for one sprint.
 *
 * The backend computes the daily series (remaining, ideal, scope) precisely so
 * it can be drawn; leaving it unrendered wastes the one chart every agile team
 * reads. Three lines, and identity is carried by line *style*, not by three
 * competing hues — a solid accent line (actual remaining), a dashed muted line
 * (the ideal path), and a solid muted line (total scope). That is CVD-safe by
 * construction and needs no categorical palette.
 *
 * The scope line is the burnup half: when it rises mid-sprint, work was added
 * after the sprint began. On the flagged sprints that is the whole story, so it
 * earns its place rather than crowding the burndown.
 *
 * The sprint selector defaults to a flagged sprint when there is one — the
 * anomalous sprint is the one worth opening first.
 */

import { useId, useMemo, useState } from 'react'

import type { SprintBurndown } from '../api/types'
import { num } from '../lib/format'
import './BurndownChart.css'

const W = 720
const H = 280
const PAD = { top: 16, right: 16, bottom: 40, left: 44 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom

interface Props {
  sprints: SprintBurndown[]
  flagged: Set<string>
}

export function BurndownChart({ sprints, flagged }: Props) {
  // Only sprints that actually carry a daily series can be drawn.
  const drawable = useMemo(
    () => sprints.filter((s) => (s.points?.length ?? 0) >= 2),
    [sprints],
  )

  const defaultIndex = useMemo(() => {
    const flaggedIdx = drawable.findIndex((s) => flagged.has(s.sprint))
    return flaggedIdx >= 0 ? flaggedIdx : drawable.length - 1
  }, [drawable, flagged])

  const [selected, setSelected] = useState(defaultIndex)
  const [hover, setHover] = useState<number | null>(null)
  const titleId = useId()

  if (drawable.length === 0) return null

  // Clamp: the default can point past the array if the data changed.
  const sprint = drawable[Math.min(selected, drawable.length - 1)]
  const points = sprint.points ?? []

  const maxY = Math.max(...points.map((p) => p.scope_points), 1)
  const xFor = (i: number) => PAD.left + (PLOT_W * i) / (points.length - 1)
  const yFor = (v: number) => PAD.top + PLOT_H * (1 - v / maxY)

  const path = (key: 'remaining_points' | 'ideal_remaining' | 'scope_points') =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${xFor(i)},${yFor(p[key])}`).join(' ')

  const hovered = hover !== null ? points[hover] : null

  return (
    <figure className="burndown">
      <div className="burndown__head">
        <figcaption id={titleId} className="burndown__caption">
          {sprint.sprint}
          {flagged.has(sprint.sprint) && (
            <span className="burndown__flag">flagged</span>
          )}
        </figcaption>

        {/* Direct-labelled facts, so the scope-creep story is readable without
            decoding the lines. */}
        <div className="burndown__facts numeric">
          <span>{num(sprint.completed)} completed</span>
          <span>·</span>
          <span>{num(sprint.final_scope)} scope</span>
          {sprint.scope_added > 0 && (
            <span className="burndown__added">
              +{num(sprint.scope_added)} added mid-sprint
            </span>
          )}
        </div>
      </div>

      {drawable.length > 1 && (
        <div className="burndown__selector" role="tablist" aria-label="Sprint">
          {drawable.map((s, i) => (
            <button
              key={s.sprint}
              type="button"
              role="tab"
              aria-selected={i === selected}
              className={`burndown__sprint${
                i === selected ? ' burndown__sprint--on' : ''
              }${flagged.has(s.sprint) ? ' burndown__sprint--flagged' : ''}`}
              onClick={() => {
                setSelected(i)
                setHover(null)
              }}
            >
              {shortSprint(s.sprint)}
            </button>
          ))}
        </div>
      )}

      <svg
        className="burndown__svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-labelledby={titleId}
        onPointerMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect()
          const x = ((event.clientX - rect.left) / rect.width) * W
          const ratio = (x - PAD.left) / PLOT_W
          const i = Math.round(ratio * (points.length - 1))
          setHover(Math.max(0, Math.min(points.length - 1, i)))
        }}
        onPointerLeave={() => setHover(null)}
      >
        {/* Two faint y-gridlines for reading height, recessive. */}
        {[0.5, 1].map((f) => (
          <line
            key={f}
            x1={PAD.left}
            y1={yFor(maxY * f)}
            x2={W - PAD.right}
            y2={yFor(maxY * f)}
            className="burndown__grid"
          />
        ))}
        <text x={PAD.left - 6} y={yFor(maxY) + 4} textAnchor="end" className="burndown__ytick">
          {num(maxY)}
        </text>
        <text x={PAD.left - 6} y={yFor(0) + 4} textAnchor="end" className="burndown__ytick">
          0
        </text>

        <path d={path('ideal_remaining')} className="burndown__ideal" />
        <path d={path('scope_points')} className="burndown__scope" />
        <path d={path('remaining_points')} className="burndown__remaining" />

        {hover !== null && (
          <>
            <line
              x1={xFor(hover)}
              y1={PAD.top}
              x2={xFor(hover)}
              y2={PAD.top + PLOT_H}
              className="burndown__crosshair"
            />
            {(['scope_points', 'remaining_points'] as const).map((k) => (
              <circle
                key={k}
                cx={xFor(hover)}
                cy={yFor(points[hover][k])}
                r={3.5}
                className={`burndown__dot burndown__dot--${
                  k === 'remaining_points' ? 'remaining' : 'scope'
                }`}
              />
            ))}
          </>
        )}

        {/* First and last date ticks — a dense daily axis would collide. */}
        <text x={xFor(0)} y={H - PAD.bottom + 16} textAnchor="start" className="burndown__xtick">
          {shortDate(points[0].date)}
        </text>
        <text
          x={xFor(points.length - 1)}
          y={H - PAD.bottom + 16}
          textAnchor="end"
          className="burndown__xtick"
        >
          {shortDate(points[points.length - 1].date)}
        </text>
      </svg>

      <div className="burndown__legend">
        <LegendKey className="burndown__key--remaining" label="Remaining" />
        <LegendKey className="burndown__key--ideal" label="Ideal" dashed />
        <LegendKey className="burndown__key--scope" label="Scope" />
      </div>

      {hovered && (
        <div className="burndown__tooltip">
          <span className="burndown__tt-date">{shortDate(hovered.date)}</span>
          <span className="burndown__tt-row">
            <strong>{num(hovered.remaining_points)}</strong> remaining
          </span>
          <span className="burndown__tt-row">
            {num(hovered.scope_points)} scope · {num(hovered.completed_points)}{' '}
            done
          </span>
          <span className="burndown__tt-row burndown__tt-muted">
            ideal {num(hovered.ideal_remaining)}
          </span>
        </div>
      )}
    </figure>
  )
}

function LegendKey({
  className,
  label,
  dashed,
}: {
  className: string
  label: string
  dashed?: boolean
}) {
  return (
    <span className="burndown__key">
      <svg width="20" height="8" aria-hidden="true">
        <line
          x1="0"
          y1="4"
          x2="20"
          y2="4"
          className={className}
          strokeDasharray={dashed ? '4 3' : undefined}
        />
      </svg>
      {label}
    </span>
  )
}

function shortSprint(name: string): string {
  const match = /sprint\s*(\d+)/i.exec(name)
  return match ? `S${match[1]}` : name
}

/** "2026-02-03" -> "Feb 3". */
function shortDate(iso: string): string {
  const date = new Date(`${iso}T00:00:00`)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
