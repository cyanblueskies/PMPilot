import type { IngestStatus } from '../api/types'
import './ui.css'

export type Tone = 'ok' | 'warn' | 'bad' | 'neutral'

export function StatusPill({ tone, label }: { tone: Tone; label: string }) {
  return <span className={`pill pill--${tone}`}>{label}</span>
}

const INGEST_TONES: Record<IngestStatus, Tone> = {
  ready: 'ok',
  processing: 'warn',
  failed: 'bad',
}

export function IngestPill({ status }: { status: IngestStatus }) {
  // Unknown values are shown rather than hidden: a status the frontend does not
  // recognise means the two sides have drifted, and that should be visible.
  return <StatusPill tone={INGEST_TONES[status] ?? 'neutral'} label={status} />
}
