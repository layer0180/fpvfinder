import { useEffect, useId, useRef, useState } from 'react'
import { geocode } from './api'
import type { Place } from './types'
import type { Lang, UiStrings } from './i18n'

interface Props {
  lang: Lang
  s: UiStrings
  value: string
  onPick: (place: Place) => void
  onLocate: () => void
  locating: boolean
  /** Shown under the field, e.g. "location denied". */
  message?: string
}

const DEBOUNCE_MS = 300
const MIN_CHARS = 3

/**
 * Place search as an ARIA combobox: suggestions from /api/geocode while
 * typing, arrow keys to move, Enter to pick (or to take the best match when
 * nothing is highlighted).
 */
export default function SearchBar({ lang, s, value, onPick, onLocate, locating, message }: Props) {
  const [query, setQuery] = useState(value)
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [notFound, setNotFound] = useState(false)
  const listId = useId()
  const abort = useRef<AbortController | null>(null)
  const typed = useRef(false)

  useEffect(() => setQuery(value), [value])

  useEffect(() => {
    if (!typed.current) return
    const q = query.trim()
    setNotFound(false)
    if (q.length < MIN_CHARS) {
      setResults([])
      return
    }
    const timer = setTimeout(async () => {
      abort.current?.abort()
      abort.current = new AbortController()
      try {
        const found = await geocode(q, lang, abort.current.signal, true)
        setResults(found)
        setActive(-1)
        setOpen(true)
      } catch {
        /* aborted or unavailable - keep the previous suggestions */
      }
    }, DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [query, lang])

  const input = useRef<HTMLInputElement>(null)
  const pick = (place: Place) => {
    typed.current = false
    // Closes the phone keyboard so the results are not hidden behind it.
    input.current?.blur()
    setQuery(place.label.split(',')[0])
    setOpen(false)
    setResults([])
    onPick(place)
  }

  const submit = async () => {
    if (active >= 0 && results[active]) return pick(results[active])
    if (results[0]) return pick(results[0])
    const q = query.trim()
    if (q.length < 2) return
    try {
      const found = await geocode(q, lang)
      if (found[0]) pick(found[0])
      else setNotFound(true)
    } catch {
      setNotFound(true)
    }
  }

  return (
    <div className="searchbar">
      <form
        className="searchbar-form"
        role="search"
        onSubmit={(event) => {
          event.preventDefault()
          submit()
        }}
      >
        <label className="visually-hidden" htmlFor="finder-q">
          {s.searchLabel}
        </label>
        <svg className="searchbar-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="m15.5 15.5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          ref={input}
          id="finder-q"
          type="search"
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          enterKeyHint="search"
          placeholder={s.searchPlaceholder}
          value={query}
          onChange={(event) => {
            typed.current = true
            setQuery(event.target.value)
          }}
          onFocus={() => results.length && setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown') {
              event.preventDefault()
              setOpen(true)
              setActive((i) => Math.min(results.length - 1, i + 1))
            } else if (event.key === 'ArrowUp') {
              event.preventDefault()
              setActive((i) => Math.max(-1, i - 1))
            } else if (event.key === 'Escape') {
              setOpen(false)
            }
          }}
        />
        <button type="button" className="locate-button" onClick={onLocate} disabled={locating} title={s.locate}>
          <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
            <path fill="none" stroke="currentColor" strokeWidth="2" d="M12 2v3M12 19v3M2 12h3M19 12h3" />
            <circle cx="12" cy="12" r="6" fill="none" stroke="currentColor" strokeWidth="2" />
            <circle cx="12" cy="12" r="2" fill="currentColor" />
          </svg>
          <span className="locate-text">{locating ? s.locating : s.locate}</span>
        </button>
      </form>
      {open && results.length > 0 && (
        <ul id={listId} role="listbox" className="suggestions">
          {results.map((place, i) => {
            const [name, ...rest] = place.label.split(', ')
            return (
              <li
                key={`${place.lat},${place.lon}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(event) => {
                  event.preventDefault()
                  pick(place)
                }}
              >
                <strong>{name}</strong>
                {rest.length > 0 && <span>{rest.join(', ')}</span>}
              </li>
            )
          })}
        </ul>
      )}
      {(message || notFound) && (
        <p className="searchbar-message" role="status">
          {notFound ? s.noPlaceFound : message}
        </p>
      )}
    </div>
  )
}
