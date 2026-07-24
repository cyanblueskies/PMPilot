import { useCallback } from 'react'

import { listProjects } from '../api/client'
import { Async } from '../components/Async'
import { ProjectList } from '../components/ProjectList'
import { UploadPanel } from '../components/UploadPanel'
import { useAsync } from '../hooks/useAsync'

export function ProjectsPage() {
  const [projects, reloadProjects] = useAsync(
    useCallback(() => listProjects(), []),
  )

  return (
    <>
      <section className="section">
        <div className="section__head">
          <h2 className="section__title">New dataset</h2>
        </div>
        {/* Refreshing the list on completion is the only link between the two
            panels: a project appears here because ingestion finished, not
            because the upload request returned. */}
        <UploadPanel onIngested={reloadProjects} />
      </section>

      <section className="section">
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
      </section>
    </>
  )
}
