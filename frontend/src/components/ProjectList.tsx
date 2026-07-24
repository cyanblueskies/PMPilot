import type { ProjectStatus } from '../api/types'
import { IngestPill } from './StatusPill'
import './ProjectList.css'

function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      })
}

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
      {projects.map((project) => (
        <li key={project.project_id} className="projects__row">
          <div className="projects__main">
            <span className="projects__name">{project.name}</span>
            <IngestPill status={project.status} />
          </div>

          <div className="projects__meta numeric">
            <span>{project.issue_count.toLocaleString()} issues</span>
            <span className="projects__dot">·</span>
            <span>{formatDate(project.created_at)}</span>
          </div>

          {/* Ingestion runs in a background task, so a failure has no request
              to fail. Surfacing the stored reason here is the only way a user
              learns why a project never became ready. */}
          {project.error && <p className="projects__error">{project.error}</p>}
        </li>
      ))}
    </ul>
  )
}
