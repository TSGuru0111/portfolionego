import { useEffect, useRef } from 'react'
import './report.css'

/**
 * Editable letter body. Splits text on blank lines into paragraphs.
 * When isEditing=true, each <p> becomes contentEditable; onChange
 * is called with the new joined text on every input event.
 * When isStreaming=true, shows a blinking cursor after the text.
 */
export default function LetterCard({ text, isEditing, isStreaming, onChange }) {
  const containerRef = useRef(null)
  const paragraphs = (text || '').split(/\n\s*\n/).filter(p => p.length > 0)

  // Re-sync paragraph DOM to incoming text when not editing (handles
  // streaming chunks). When editing, we DON'T overwrite to preserve
  // the RM's cursor and edits in flight.
  useEffect(() => {
    if (isEditing || !containerRef.current) return
    const el = containerRef.current
    const ps = el.querySelectorAll('p')
    ps.forEach((p, i) => {
      const next = paragraphs[i] ?? ''
      if (p.textContent !== next) p.textContent = next
    })
  }, [text, isEditing, paragraphs])

  function handleInput() {
    if (!isEditing || !containerRef.current || !onChange) return
    const ps = containerRef.current.querySelectorAll('p')
    const joined = Array.from(ps)
      .map(p => p.textContent.replace(/[\u200B-\u200D\uFEFF]/g, ''))
      .filter(t => t.length > 0)
      .join('\n\n')
    onChange(joined)
  }

  return (
    <div className={`letter-card ${isEditing ? 'editing' : ''}`}>
      <h3>Letter to the client</h3>
      <div
        ref={containerRef}
        className="letter-body"
        onInput={handleInput}
        suppressContentEditableWarning
      >
        {paragraphs.length === 0 ? (
          <p contentEditable={isEditing} />
        ) : (
          paragraphs.map((p, i) => (
            <p key={i} contentEditable={isEditing}>{p}</p>
          ))
        )}
        {isStreaming ? <span className="streaming-cursor" /> : null}
      </div>
    </div>
  )
}
