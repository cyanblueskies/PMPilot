/**
 * Renders the loading and error arms of an `AsyncState` so views only describe
 * the ready case.
 *
 * Errors are shown with a retry rather than swallowed. The dashboard is
 * required to stay useful when parts of the system are unavailable
 * (.claude/rules/architecture.md), which means a failed panel has to say what
 * failed instead of rendering blank.
 */

import type { ReactNode } from 'react'

import type { AsyncState } from '../hooks/useAsync'
import './ui.css'

interface AsyncProps<T> {
  state: AsyncState<T>
  onRetry?: () => void
  loadingLabel?: string
  /** Rendered instead of the generic error for a specific status code. */
  renderError?: (error: string, httpStatus: number) => ReactNode
  children: (data: T) => ReactNode
}

export function Async<T>({
  state,
  onRetry,
  loadingLabel = 'Loading…',
  renderError,
  children,
}: AsyncProps<T>) {
  if (state.status === 'loading') {
    return (
      <div className="async">
        <div className="async__spinner" aria-hidden="true" />
        <span role="status">{loadingLabel}</span>
      </div>
    )
  }

  if (state.status === 'error') {
    const custom = renderError?.(state.error, state.httpStatus)
    if (custom !== undefined) return <>{custom}</>

    return (
      <div className="async">
        <span className="async__title">Could not load this</span>
        <span className="async__detail">{state.error}</span>
        {onRetry && (
          <button type="button" className="button" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    )
  }

  return <>{children(state.data)}</>
}
