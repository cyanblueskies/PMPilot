/**
 * FR-E3 — velocity per sprint, with the flagged sprints emphasised.
 *
 * This is the emphasis form, not a plain bar chart: the reader's question is
 * "which sprint dropped", so the flagged sprints carry the danger colour and
 * the rest recede to one muted hue. A median reference line gives the drop
 * something to be a drop *from* — a bar is only low relative to the others.
 *
 * Inline SVG rather than a charting library: this is one single-series chart,
 * and a dependency is not yet earned (.claude/rules/code-style.md). The tooltip
 * and keyboard focus are part of the deliverable, not an upgrade — every value
 * on hover is also reachable by tabbing to the bar.
 *
 * Not a chart when it cannot be one: with fewer than two sprints there is no
 * trend to draw, so the component renders nothing and the tiles stand alone.
 */

import { useId, useState } from 'react'

import type { SprintVelocity } from '../api/types'
import { num } from '../lib/format'
import './VelocityChart.css'

// A viewBox coordinate space; the SVG scales to its container via CSS. These
// are design units, not pixels.
const W = 720
const H = 260
const PAD = { top: 16, right: 16, bottom: 40, left: 40 }
const PLOT_W = W - PAD.left - PAD.right
const PLOT_H = H - PAD.top - PAD.bottom

interface Props {
  sprints: SprintVelocity[]
  median: number | null
  /** Sprint names carrying a velocity_drop anomaly, matched by name. */
  flagged: Set<string>
}

interface Hover {
  sprint: SprintVelocity
  x: number
  y: number
}

export function VelocityChart({ sprints, median, flagged }: Props) {
  const [hover, setHover] = useState<Hover | null>(null)
  const titleId = useId()

  if (sprints.length < 2) return null

  const maxVelocity = Math.max(...sprints.map((s) => s.velocity), median ?? 0, 1)
  const yFor = (value: number) => PAD.top + PLOT_H * (1 - value / maxVelocity)

  const slot = PLOT_W / sprints.length
  // A 2px surface gap between bars, expressed in design units at this width.
  const gap = Math.min(slot * 0.32, 14)
  const barW = slot - gap

  const medianY = median !== null ? yFor(median) : null

  return (
    <figure className="velocity">
      <figcaption id={titleId} className="velocity__caption">
        Velocity by sprint
        <span className="velocity__unit"> · story points completed</span>
      </figcaption>

      <svg
        className="velocity__svg"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-labelledby={titleId}
      >
        {/* Baseline only — a recessive axis, no full grid competing with the
            bars. */}
        <line
          x1={PAD.left}
          y1={PAD.top + PLOT_H}
          x2={W - PAD.right}
          y2={PAD.top + PLOT_H}
          className="velocity__axis"
        />

        {medianY !== null && (
          <>
            <line
              x1={PAD.left}
              y1={medianY}
              x2={W - PAD.right}
              y2={medianY}
              className="velocity__median"
            />
            <text
              x={W - PAD.right}
              y={medianY - 5}
              textAnchor="end"
              className="velocity__median-label"
            >
              median {num(median!)}
            </text>
          </>
        )}

        {sprints.map((sprint, i) => {
          const x = PAD.left + i * slot + gap / 2
          const y = yFor(sprint.velocity)
          const barH = PAD.top + PLOT_H - y
          const isFlagged = flagged.has(sprint.sprint)
          const active = hover?.sprint === sprint

          return (
            <g key={sprint.sprint}>
              <rect
                x={x}
                y={y}
                width={barW}
                height={Math.max(barH, 0)}
                rx={3}
                className={`velocity__bar${
                  isFlagged ? ' velocity__bar--flagged' : ''
                }${active ? ' velocity__bar--active' : ''}`}
                tabIndex={0}
                role="button"
                aria-label={`${sprint.sprint}: ${num(sprint.velocity)} points, ${
                  sprint.completed_issues
                } of ${sprint.total_issues} issues done${
                  isFlagged ? ', flagged as a velocity drop' : ''
                }`}
                onPointerEnter={() =>
                  setHover({ sprint, x: x + barW / 2, y })
                }
                onPointerLeave={() => setHover(null)}
                onFocus={() => setHover({ sprint, x: x + barW / 2, y })}
                onBlur={() => setHover(null)}
              />
              {/* Label only the flagged bars, not every one — a number on every
                  bar is noise, and the flagged ones are the point. */}
              {isFlagged && (
                <text
                  x={x + barW / 2}
                  y={y - 6}
                  textAnchor="middle"
                  className="velocity__value velocity__value--flagged"
                >
                  {num(sprint.velocity)}
                </text>
              )}
              {/* Every 2nd tick when crowded, so labels never collide. */}
              {(sprints.length <= 8 || i % 2 === 0) && (
                <text
                  x={x + barW / 2}
                  y={H - PAD.bottom + 16}
                  textAnchor="middle"
                  className="velocity__tick"
                >
                  {shortSprint(sprint.sprint)}
                </text>
              )}
            </g>
          )
        })}
      </svg>

      {hover && (
        <div
          className="velocity__tooltip"
          style={{
            left: `${(hover.x / W) * 100}%`,
            top: `${(hover.y / H) * 100}%`,
          }}
        >
          {/* textContent-equivalent: React escapes, so a sprint name from the
              CSV cannot inject markup. */}
          <span className="velocity__tt-name">{hover.sprint.sprint}</span>
          <span className="velocity__tt-value">
            {num(hover.sprint.velocity)} pts
          </span>
          <span className="velocity__tt-detail">
            {hover.sprint.completed_issues} of {hover.sprint.total_issues} issues
            done
            {hover.sprint.unestimated_completed > 0 &&
              ` · ${hover.sprint.unestimated_completed} unestimated`}
          </span>
        </div>
      )}
    </figure>
  )
}

/** "Sprint 12" -> "S12"; anything else is left as-is. */
function shortSprint(name: string): string {
  const match = /sprint\s*(\d+)/i.exec(name)
  return match ? `S${match[1]}` : name
}
