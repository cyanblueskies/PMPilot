/**
 * The one data-fetching primitive.
 *
 * React Query would do this and more, but the app has a handful of endpoints
 * and no cache-invalidation problem, so a dependency is not yet earned
 * (.claude/rules/code-style.md). Revisit if cross-view caching appears.
 */

import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'

/**
 * A discriminated union rather than `{ data, loading, error }`: the compiler
 * then refuses to let a view read `data` without having handled the other two
 * states, which is exactly the graceful-degradation requirement expressed as a
 * type.
 */
export type AsyncState<T> =
  | { status: 'loading' }
  | { status: 'error'; error: string; httpStatus: number }
  | { status: 'ready'; data: T }

function describe(error: unknown): { error: string; httpStatus: number } {
  if (error instanceof ApiError) {
    return { error: error.message, httpStatus: error.status }
  }
  return { error: String(error), httpStatus: 0 }
}

/**
 * `fetcher` must be stable — wrap it in `useCallback` with whatever the request
 * actually depends on. An inline arrow is a new function every render and would
 * refetch forever. Declaring the dependency at the call site keeps it something
 * the linter can check, which a `deps` array passed through here would not be.
 */
export function useAsync<T>(
  fetcher: () => Promise<T>,
): [AsyncState<T>, () => void] {
  const [state, setState] = useState<AsyncState<T>>({ status: 'loading' })
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    // StrictMode runs effects twice in development, and a slow request can
    // still be in flight when deps change. Without this guard a stale response
    // overwrites a fresh one.
    let cancelled = false
    setState({ status: 'loading' })

    fetcher()
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((error: unknown) => {
        if (!cancelled) setState({ status: 'error', ...describe(error) })
      })

    return () => {
      cancelled = true
    }
  }, [fetcher, reloadCount])

  const reload = useCallback(() => setReloadCount((n) => n + 1), [])

  return [state, reload]
}
