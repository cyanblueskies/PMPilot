/**
 * FR-A1 / FR-A2 / FR-A3 — upload a Jira export and report what was made of it.
 *
 * Upload returns 202 immediately: parsing is synchronous but persistence and
 * analysis run in a background task, so "accepted" is not "ready". This panel
 * owns that gap — it polls the project until ingestion resolves, because a
 * background failure has no request left to fail and would otherwise be
 * invisible.
 */

import { useCallback, useEffect, useState } from 'react'

import { ApiError, getProject, uploadDataset } from '../api/client'
import type { UploadAccepted } from '../api/types'
import { MappingReport } from './MappingReport'
import './UploadPanel.css'

// Mirrors backend/app/services/ingestion/loader.py. Checked here only so an
// obviously wrong file fails instantly instead of after a 20 MB round trip —
// the server-side check is the one that counts (.claude/rules/security.md).
const ALLOWED_EXTENSIONS = ['.csv', '.xlsx']
const MAX_FILE_BYTES = 20 * 1024 * 1024

const POLL_INTERVAL_MS = 1000
// 5,000 issues analyse in well under 5s, so anything past this is a stuck job
// rather than a slow one, and saying so beats spinning forever.
const POLL_TIMEOUT_MS = 120_000

type UploadState =
  | { phase: 'idle' }
  | { phase: 'uploading'; filename: string }
  | { phase: 'processing'; accepted: UploadAccepted }
  | { phase: 'ready'; accepted: UploadAccepted; issueCount: number }
  | { phase: 'failed'; accepted: UploadAccepted; error: string }
  | { phase: 'rejected'; error: string }

function localCheck(file: File): string | null {
  const name = file.name.toLowerCase()
  if (!ALLOWED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
    return `Unsupported file type. Upload a ${ALLOWED_EXTENSIONS.join(' or ')} file.`
  }
  if (file.size > MAX_FILE_BYTES) {
    const mb = Math.round(file.size / 1024 / 1024)
    return `File is too large (${mb} MB). The limit is ${MAX_FILE_BYTES / 1024 / 1024} MB.`
  }
  return null
}

export function UploadPanel({ onIngested }: { onIngested: () => void }) {
  const [state, setState] = useState<UploadState>({ phase: 'idle' })
  const [dragging, setDragging] = useState(false)

  const submit = useCallback(async (file: File) => {
    const localError = localCheck(file)
    if (localError) {
      setState({ phase: 'rejected', error: localError })
      return
    }

    setState({ phase: 'uploading', filename: file.name })
    try {
      const accepted = await uploadDataset(file)
      setState({ phase: 'processing', accepted })
    } catch (error) {
      setState({
        phase: 'rejected',
        error:
          error instanceof ApiError ? error.message : 'Upload failed. Try again.',
      })
    }
  }, [])

  // Poll only while a background job is outstanding.
  const projectId =
    state.phase === 'processing' ? state.accepted.project_id : null

  useEffect(() => {
    if (projectId === null) return

    let cancelled = false
    let timer = 0
    const startedAt = Date.now()

    const tick = async () => {
      try {
        const project = await getProject(projectId)
        if (cancelled) return

        if (project.status === 'ready') {
          setState((current) =>
            current.phase === 'processing'
              ? {
                  phase: 'ready',
                  accepted: current.accepted,
                  issueCount: project.issue_count,
                }
              : current,
          )
          onIngested()
          return
        }
        if (project.status === 'failed') {
          setState((current) =>
            current.phase === 'processing'
              ? {
                  phase: 'failed',
                  accepted: current.accepted,
                  error: project.error ?? 'Ingestion failed for an unknown reason.',
                }
              : current,
          )
          onIngested()
          return
        }
        if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          setState((current) =>
            current.phase === 'processing'
              ? {
                  phase: 'failed',
                  accepted: current.accepted,
                  error:
                    'Still processing after two minutes. Check the backend logs — ' +
                    'the project row will hold the reason if the job errored.',
                }
              : current,
          )
          return
        }
        timer = window.setTimeout(tick, POLL_INTERVAL_MS)
      } catch {
        // A transient failure mid-poll is not a failed ingestion. Keep polling;
        // the timeout above is what ends it.
        if (!cancelled) timer = window.setTimeout(tick, POLL_INTERVAL_MS)
      }
    }

    timer = window.setTimeout(tick, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [projectId, onIngested])

  const busy = state.phase === 'uploading' || state.phase === 'processing'

  return (
    <div className="upload">
      <label
        className={`upload__drop${dragging ? ' upload__drop--over' : ''}${
          busy ? ' upload__drop--busy' : ''
        }`}
        onDragOver={(event) => {
          event.preventDefault()
          if (!busy) setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          const file = event.dataTransfer.files[0]
          if (file && !busy) void submit(file)
        }}
      >
        {/* A real file input inside the label: dropping is a convenience, but
            the control has to stay reachable by keyboard. */}
        <input
          type="file"
          accept=".csv,.xlsx"
          className="upload__input"
          disabled={busy}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) void submit(file)
            // Reset so re-selecting the same file fires change again.
            event.target.value = ''
          }}
        />
        <span className="upload__headline">
          {busy ? 'Working…' : 'Drop a Jira export here, or click to choose'}
        </span>
        <span className="upload__hint">CSV or XLSX · up to 20 MB</span>
      </label>

      <UploadStatus state={state} />
    </div>
  )
}

function UploadStatus({ state }: { state: UploadState }) {
  if (state.phase === 'idle') return null

  if (state.phase === 'uploading') {
    return (
      <p className="upload__note">
        <span className="upload__spinner" aria-hidden="true" />
        Parsing <strong>{state.filename}</strong>…
      </p>
    )
  }

  if (state.phase === 'rejected') {
    return (
      <div className="upload__banner upload__banner--bad">
        <strong>File rejected</strong>
        {/* The backend's own message is shown verbatim: for a missing required
            column it lists the headers the file actually has, which is what
            makes the error actionable. */}
        <p className="upload__detail">{state.error}</p>
      </div>
    )
  }

  return (
    <div className="upload__result">
      {state.phase === 'processing' && (
        <p className="upload__note">
          <span className="upload__spinner" aria-hidden="true" />
          Computing KPIs and detecting anomalies for{' '}
          <strong>{state.accepted.name}</strong>…
        </p>
      )}

      {state.phase === 'ready' && (
        <div className="upload__banner upload__banner--ok">
          <strong>{state.accepted.name} is ready</strong>
          <p className="upload__detail">
            {state.issueCount.toLocaleString()} issues analysed.
          </p>
        </div>
      )}

      {state.phase === 'failed' && (
        <div className="upload__banner upload__banner--bad">
          <strong>Ingestion failed</strong>
          <p className="upload__detail upload__detail--mono">{state.error}</p>
        </div>
      )}

      <MappingReport result={state.accepted} />
    </div>
  )
}
