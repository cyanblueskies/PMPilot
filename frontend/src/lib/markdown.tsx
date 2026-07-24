/**
 * A deliberately small Markdown renderer for report content.
 *
 * The report body is model-generated prose in a known, narrow subset — two
 * `##` sections, paragraphs, bullet and numbered lists, and inline emphasis.
 * A full Markdown library (remark/micromark) is real weight for that, and
 * dependencies here are minimal by design (.claude/rules/code-style.md).
 *
 * It is XSS-safe by construction: every piece of text becomes a React text
 * node, and there is no `dangerouslySetInnerHTML` anywhere. The content comes
 * from an LLM and must be treated as untrusted, so this property is the point,
 * not an accident — swap in a library only if you keep it.
 *
 * Anything it does not recognise degrades to a paragraph rather than
 * disappearing, so an unexpected construct is shown as plain text, never
 * dropped.
 */

import type { ReactNode } from 'react'

/** `**bold**`, `*italic*`, `` `code` `` → React nodes. Non-nesting, which the
 *  report prose never needs. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
  let last = 0
  let match: RegExpExecArray | null
  let i = 0

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(text.slice(last, match.index))
    }
    const token = match[0]
    const key = `${keyPrefix}-${i++}`
    if (token.startsWith('**')) {
      nodes.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    } else if (token.startsWith('`')) {
      nodes.push(<code key={key}>{token.slice(1, -1)}</code>)
    } else {
      nodes.push(<em key={key}>{token.slice(1, -1)}</em>)
    }
    last = match.index + token.length
  }
  if (last < text.length) nodes.push(text.slice(last))
  return nodes
}

export function Markdown({ source }: { source: string }): ReactNode {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: ReactNode[] = []

  // Accumulators for multi-line blocks (paragraphs, lists).
  let paragraph: string[] = []
  let listItems: string[] = []
  let listOrdered = false
  let key = 0

  const flushParagraph = () => {
    if (paragraph.length === 0) return
    blocks.push(
      <p key={key++} className="md__p">
        {renderInline(paragraph.join(' '), `p${key}`)}
      </p>,
    )
    paragraph = []
  }

  const flushList = () => {
    if (listItems.length === 0) return
    const items = listItems.map((item, i) => (
      <li key={i}>{renderInline(item, `li${key}-${i}`)}</li>
    ))
    blocks.push(
      listOrdered ? (
        <ol key={key++} className="md__ol">
          {items}
        </ol>
      ) : (
        <ul key={key++} className="md__ul">
          {items}
        </ul>
      ),
    )
    listItems = []
  }

  for (const raw of lines) {
    const line = raw.trimEnd()

    const heading = /^(#{1,4})\s+(.*)$/.exec(line)
    const bullet = /^[-*]\s+(.*)$/.exec(line)
    const numbered = /^\d+\.\s+(.*)$/.exec(line)

    if (heading) {
      flushParagraph()
      flushList()
      const level = heading[1].length
      const Tag = (`h${Math.min(level + 1, 6)}` as 'h2')
      blocks.push(
        <Tag key={key++} className="md__h">
          {renderInline(heading[2], `h${key}`)}
        </Tag>,
      )
    } else if (bullet) {
      flushParagraph()
      if (listOrdered) flushList()
      listOrdered = false
      listItems.push(bullet[1])
    } else if (numbered) {
      flushParagraph()
      if (!listOrdered) flushList()
      listOrdered = true
      listItems.push(numbered[1])
    } else if (line.trim() === '') {
      // A blank line ends the current block.
      flushParagraph()
      flushList()
    } else {
      flushList()
      paragraph.push(line)
    }
  }

  flushParagraph()
  flushList()

  return <div className="md">{blocks}</div>
}
