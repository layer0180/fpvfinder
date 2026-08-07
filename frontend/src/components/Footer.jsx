import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { renderMarkdown } from '../lib/markdown.js'

/**
 * Footer with the legal links and the optional donation button.
 *
 * Design rules for the donation part, deliberately:
 *   - it is a plain link, nothing else. No third-party script, no conversion
 *     pixel, no tracking of any kind.
 *   - it never blocks or interrupts anything. No popup, no modal on load, no
 *     "dismiss" state to remember, because there is nothing to dismiss.
 *   - if DONATE_URL is not configured, it simply is not rendered.
 */
export default function Footer({ donateUrl, donateLabel }) {
  const [page, setPage] = useState(null) // 'imprint' | 'privacy' | 'funding'
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  const [available, setAvailable] = useState({})

  useEffect(() => {
    api
      .legalIndex()
      .then((data) => setAvailable(data.pages ?? {}))
      .catch(() => setAvailable({}))
  }, [])

  const open = async (name) => {
    setPage(name)
    setContent('')
    setError('')
    try {
      const data = await api.legalPage(name)
      setContent(renderMarkdown(data.markdown))
    } catch (err) {
      setError(err.message)
    }
  }

  // The static landing pages link here as /app?legal=imprint, so an imprint
  // stays one click away from the front page - which is what German law
  // effectively expects - without duplicating the text into a second place.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get('legal')
    if (requested && ['imprint', 'privacy', 'funding'].includes(requested)) {
      open(requested)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Close on Escape - a dialog that traps you is worse than no dialog.
  useEffect(() => {
    if (!page) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') setPage(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [page])

  const titles = { imprint: 'Imprint', privacy: 'Privacy', funding: 'Where donations go' }
  const title = titles[page] ?? page

  return (
    <>
      <footer className="footer">
        <span className="footer-left">
          Free community tool · no accounts · no ads ·{' '}
          <a href="https://github.com/Layer0180/fpvfinder" target="_blank" rel="noreferrer">
            GitHub
          </a>
        </span>

        <span className="footer-right">
          {available.imprint && (
            <button type="button" className="link" onClick={() => open('imprint')}>
              Imprint
            </button>
          )}
          {available.privacy && (
            <button type="button" className="link" onClick={() => open('privacy')}>
              Privacy
            </button>
          )}
          {available.funding && (
            <button type="button" className="link" onClick={() => open('funding')}>
              Running costs
            </button>
          )}
          {donateUrl && (
            <a className="donate" href={donateUrl} target="_blank" rel="noreferrer noopener">
              ☕ {donateLabel || 'Buy me a coffee'}
            </a>
          )}
        </span>
      </footer>

      {page && (
        <div className="modal-backdrop" onClick={() => setPage(null)} role="presentation">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={title}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal-header">
              <h2>{title}</h2>
              <span className="modal-actions">
                <button type="button" className="icon" onClick={() => setPage(null)} aria-label="Close">
                  ✕
                </button>
              </span>
            </div>
            <div className="modal-body">
              {error && <p className="error">{error}</p>}
              {!error && !content && <p className="hint">Loading …</p>}
              {/* Content comes from the operator's own markdown files, and the
                  renderer escapes everything before emitting a fixed tag set. */}
              {content && <div className="prose" dangerouslySetInnerHTML={{ __html: content }} />}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
