import { Link } from 'react-router-dom'

import type { ProjectStatus } from '../api/types'
import { dateTime } from '../lib/format'
import { IngestPill } from './StatusPill'
import './ProjectList.css'

export function ProjectList({ projects }: { projects: ProjectStatus[] }) {
  if (projects.length === 0) {
    return (
      <div className="async">
        <span className="async__title">No projects yet</span>
        <span className="async__detail">
          Upload a Jira CSV or XLSX export to get started.
        </span>
      </div>
    )
  }

  return (
    <ul className="projects">
      {projects.map((project) => {
        const body = (
          <>
            <div className="projects__main">
              <span className="projects__name">{project.name}</span>
              <IngestPill status={project.status} />
            </div>

            <div className="projects__meta numeric">
              <span>{project.issue_count.toLocaleString()} issues</span>
              <span className="projects__dot">·</span>
              <span>{dateTime(project.created_at)}</span>
            </div>
          </>
        )

        return (
          <li key={project.project_id} className="projects__row">
            {/* Only a ready project has a dashboard to open. Linking to one
                that is still ingesting would land on a 409. */}
            {project.status === 'ready' ? (
              <Link to={`/projects/${project.project_id}`} className="projects__link">
                {body}
              </Link>
            ) : (
              <div className="projects__link projects__link--inert">{body}</div>
            )}

            {/* Ingestion runs in a background task, so a failure has no request
                to fail. Surfacing the stored reason here is the only way a user
                learns why a project never became ready. */}
            {project.error && <p className="projects__error">{project.error}</p>}
          </li>
        )
      })}
    </ul>
  )
}
