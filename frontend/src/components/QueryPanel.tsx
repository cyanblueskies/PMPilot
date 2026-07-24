/**
 * FR-D1 / FR-F1 / FR-F2 — single-turn question answering over one project.
 *
 * The answer is never shown on its own. When the model phrases a result set,
 * the generated SQL and the rows it returned are shown alongside it — that is
 * the FR-F2 traceability requirement, and it is what lets a reader check the
 * prose against the data rather than trust it. An answer with no evidence is a
 * claim; an answer with its query and rows is a result.
 *
 * The backend deliberately answers three different ways, and each is a distinct
 * outcome the panel must not blur:
 *
 *   out of scope     in_scope=false — a refusal is the designed behaviour for a
 *                    question outside the supported set, not a failure. Rather
 *                    than a wrong answer, the user is shown what *can* be asked.
 *   service down     in_scope=true, no evidence — the LLM is unavailable. The
 *                    message says so and says the dashboard is unaffected,
 *                    because the generative track is an enhancement layer, never
 *                    a dependency of the core views (.claude/rules/architecture).
 *   answered         in_scope=true, evidence present — prose + SQL + rows.
 *
 * Multi-turn follow-up is deliberately not built: the resolved scope is a
 * single-turn panel with traceable evidence (.claude/rules/scope.md).
 */

import { useCallback, useState } from 'react'

import { askQuestion, getSupportedQuestions } from '../api/client'
import type { QueryResponse } from '../api/types'
import { useAsync } from '../hooks/useAsync'
import { EvidenceTable } from './EvidenceTable'
import './QueryPanel.css'

type State =
  | { phase: 'idle' }
  | { phase: 'asking' }
  | { phase: 'answered'; response: QueryResponse }
  | { phase: 'error'; message: string }

export function QueryPanel({ projectId }: { projectId: number }) {
  const [question, setQuestion] = useState('')
  const [state, setState] = useState<State>({ phase: 'idle' })
  const [supported] = useAsync(
    useCallback(() => getSupportedQuestions(), []),
  )

  const ask = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed) return
      setQuestion(trimmed)
      setState({ phase: 'asking' })
      try {
        const response = await askQuestion(projectId, trimmed)
        setState({ phase: 'answered', response })
      } catch (error) {
        // A transport failure is distinct from a refusal: the request never
        // reached an answer. The dashboard around this panel is untouched.
        setState({
          phase: 'error',
          message:
            error instanceof Error ? error.message : 'The request failed.',
        })
      }
    },
    [projectId],
  )

  const busy = state.phase === 'asking'

  return (
    <div className="query">
      <form
        className="query__form"
        onSubmit={(event) => {
          event.preventDefault()
          void ask(question)
        }}
      >
        <input
          className="query__input"
          type="text"
          value={question}
          placeholder="Ask about this project…"
          disabled={busy}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <button
          type="submit"
          className="button button--primary"
          disabled={busy || question.trim().length === 0}
        >
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </form>

      {/* The suggestion chips are the supported set made visible: the user sees
          the boundary rather than discovering it by being refused. */}
      {state.phase === 'idle' && supported.status === 'ready' && (
        <div className="query__suggestions">
          <span className="query__suggestions-label">Try asking</span>
          <div className="query__chips">
            {supported.data.map((q) => (
              <button
                key={q.key}
                type="button"
                className="query__chip"
                title={q.description}
                onClick={() => void ask(q.example)}
              >
                {q.example}
              </button>
            ))}
          </div>
        </div>
      )}

      {busy && (
        <p className="query__pending">
          <span className="query__spinner" aria-hidden="true" />
          Working out an answer…
        </p>
      )}

      {state.phase === 'error' && (
        <div className="query__answer query__answer--down">
          <p className="query__answer-text">{state.message}</p>
        </div>
      )}

      {state.phase === 'answered' && (
        <Answer response={state.response} onSuggest={(q) => void ask(q)} />
      )}
    </div>
  )
}

function Answer({
  response,
  onSuggest,
}: {
  response: QueryResponse
  onSuggest: (question: string) => void
}) {
  const [supported] = useAsync(
    useCallback(() => getSupportedQuestions(), []),
  )

  // Out of scope: not a failure. Show what can be asked instead of the backend's
  // pre-formatted list, so the same clickable chips do the teaching.
  if (!response.in_scope) {
    return (
      <div className="query__answer query__answer--refused">
        <p className="query__answer-text">
          That question is outside what I can answer from this data, so I would
          rather not guess.
        </p>
        {supported.status === 'ready' && (
          <div className="query__chips">
            {supported.data.map((q) => (
              <button
                key={q.key}
                type="button"
                className="query__chip"
                onClick={() => onSuggest(q.example)}
              >
                {q.example}
              </button>
            ))}
          </div>
        )}
      </div>
    )
  }

  // In scope but no evidence: the LLM could not complete. The answer string is
  // already user-safe; the raw refusal_reason is diagnostic and stays hidden.
  if (response.evidence === null) {
    return (
      <div className="query__answer query__answer--down">
        <p className="query__answer-text">{response.answer}</p>
      </div>
    )
  }

  return (
    <div className="query__answer">
      <p className="query__answer-text">{response.answer}</p>
      <EvidenceTable
        sql={response.evidence.generated_sql}
        rows={response.evidence.rows}
        rowCount={response.evidence.row_count}
      />
    </div>
  )
}
