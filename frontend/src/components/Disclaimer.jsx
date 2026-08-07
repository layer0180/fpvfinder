import { useState } from 'react'

/**
 * Legal notice.
 *
 * Deliberately not permanently dismissible: the short form stays in the header
 * bar, and only the full text is collapsible.
 */
export default function Disclaimer({ text }) {
  const [open, setOpen] = useState(false)

  return (
    <div className={`disclaimer ${open ? 'open' : ''}`}>
      <button type="button" onClick={() => setOpen(!open)}>
        <span aria-hidden="true">⚖️</span> No substitute for an official airspace check
        <span className="chevron">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="disclaimer-body">
          <p>{text}</p>
          <p>
            Official sources (Germany):{' '}
            <a href="https://maptool-uas.dfs.de/" target="_blank" rel="noreferrer">
              DFS UAS map
            </a>
            {', '}
            <a href="https://www.dipul.de/homepage/en/" target="_blank" rel="noreferrer">
              dipul.de
            </a>
            {'. Elsewhere, check with your national aviation authority.'}
          </p>
        </div>
      )}
    </div>
  )
}
