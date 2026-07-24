import { useCallback } from 'react'
import { Link, Route, Routes } from 'react-router-dom'

import { getHealth } from './api/client'
import { StatusPill } from './components/StatusPill'
import type { Tone } from './components/StatusPill'
import { useAsync } from './hooks/useAsync'
import { DashboardPage } from './pages/DashboardPage'
import { ProjectsPage } from './pages/ProjectsPage'
import './App.css'

/**
 * The backend reports database reachability separately from process liveness,
 * and deliberately says nothing about the LLM: a degraded LLM must not make the
 * service look down (.claude/rules/architecture.md). This pill mirrors that —
 * it is a statement about the deterministic track only.
 */
function BackendStatus() {
  const [state] = useAsync(useCallback(() => getHealth(), []))

  if (state.status === 'loading') {
    return <StatusPill tone="neutral" label="checking…" />
  }
  if (state.status === 'error') {
    return <StatusPill tone="bad" label="backend unreachable" />
  }

  const databaseUp = state.data.database === 'up'
  const tone: Tone = databaseUp ? 'ok' : 'bad'
  const label = databaseUp ? 'backend ready' : state.data.database
  return <StatusPill tone={tone} label={label} />
}

export default function App() {
  return (
    <div className="shell">
      <header className="shell__header">
        <Link to="/" className="brand">
          <span className="brand__name">PMPilot</span>
          <span className="brand__tagline">
            Decision support for agile projects
          </span>
        </Link>
        <BackendStatus />
      </header>

      <main className="shell__main">
        <Routes>
          <Route path="/" element={<ProjectsPage />} />
          {/* A project's dashboard is addressable so it can be linked to
              directly — in a report, or when handing a URL to a user-testing
              participant. */}
          <Route path="/projects/:projectId" element={<DashboardPage />} />
          <Route
            path="*"
            element={
              <div className="async">
                <span className="async__title">Page not found</span>
                <Link to="/" className="button">
                  Back to projects
                </Link>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  )
}
