import { useCallback } from 'react'

import { getHealth, listProjects } from './api/client'
import { Async } from './components/Async'
import { ProjectList } from './components/ProjectList'
import { StatusPill } from './components/StatusPill'
import type { Tone } from './components/StatusPill'
import { UploadPanel } from './components/UploadPanel'
import { useAsync } from './hooks/useAsync'
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
  const [projects, reloadProjects] = useAsync(
    useCallback(() => listProjects(), []),
  )

  return (
    <div className="shell">
      <header className="shell__header">
        <div className="brand">
          <span className="brand__name">PMPilot</span>
          <span className="brand__tagline">
            Decision support for agile projects
          </span>
        </div>
        <BackendStatus />
      </header>

      <main className="shell__main">
        <section className="section">
          <div className="section__head">
            <h2 className="section__title">New dataset</h2>
          </div>
          {/* Refreshing the list on completion is the only link between the
              two panels: a project appears here because ingestion finished,
              not because the upload request returned. */}
          <UploadPanel onIngested={reloadProjects} />
        </section>

        <div className="section__head">
          <h2 className="section__title">
            Projects
            {projects.status === 'ready' && (
              <span className="section__count">{projects.data.length}</span>
            )}
          </h2>
          <button
            type="button"
            className="button"
            onClick={reloadProjects}
            disabled={projects.status === 'loading'}
          >
            Refresh
          </button>
        </div>

        <div className="card">
          <Async
            state={projects}
            onRetry={reloadProjects}
            loadingLabel="Loading projects…"
          >
            {(data) => <ProjectList projects={data} />}
          </Async>
        </div>
      </main>
    </div>
  )
}
