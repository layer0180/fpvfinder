import { useState } from 'react'
import type { Point } from './types'
import { categoryLabel, reasonText, warningText, type Lang, type UiStrings } from './i18n'
import { percent, scoreStep } from './spots'
import { DIPUL_MAP, downloadGpx, preferredRoute, routeLinks } from './exports'
import { favorites } from './storage'
import Weather from './Weather'

interface Props {
  spot: Point
  rank: number | null
  lang: Lang
  s: UiStrings
  onBack: () => void
  onShare: (spot: Point) => Promise<string>
}

export function ScoreRing({ score, blocked, size = 64 }: { score: number; blocked: boolean; size?: number }) {
  const value = percent(score)
  return (
    <div
      className="score-ring"
      style={{ width: size, height: size, ['--ring' as string]: scoreStep(score, blocked), ['--p' as string]: `${value}%` }}
      role="img"
      aria-label={`${value} / 100`}
    >
      <span>{blocked ? '✕' : value}</span>
    </div>
  )
}

const LEVEL_ORDER = { danger: 0, warning: 1, info: 2 } as const

export default function SpotDetail({ spot, rank, lang, s, onBack, onShare }: Props) {
  const [saved, setSaved] = useState(() => favorites.has(spot))
  const [shareState, setShareState] = useState<'idle' | 'busy' | 'copied'>('idle')
  const [copied, setCopied] = useState(false)
  const [storyBusy, setStoryBusy] = useState(false)
  const category = categoryLabel(spot.category, lang)
  const title = spot.area_name || category
  const coords = `${spot.lat.toFixed(5)}, ${spot.lon.toFixed(5)}`
  const warnings = [...spot.warnings].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level])
  const links = routeLinks(spot.lat, spot.lon)

  const share = async () => {
    setShareState('busy')
    try {
      const url = await onShare(spot)
      if (navigator.share) {
        await navigator.share({ title: `${s.shareTitle}: ${title}`, url })
        setShareState('idle')
      } else {
        await navigator.clipboard.writeText(url)
        setShareState('copied')
        setTimeout(() => setShareState('idle'), 2500)
      }
    } catch {
      setShareState('idle')
    }
  }

  // 1080x1920 card for stories and short videos, drawn by the server from the
  // share's snapshot (backend/app/cards.py).
  const downloadStory = async () => {
    setStoryBusy(true)
    try {
      const url = await onShare(spot)
      const id = url.split('/s/')[1]
      const a = document.createElement('a')
      a.href = `/og/s/${id}/story.png`
      a.download = `fpv-spot-${id}.png`
      a.click()
    } finally {
      setStoryBusy(false)
    }
  }

  const copyCoords = async () => {
    try {
      await navigator.clipboard.writeText(coords)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard blocked - the coordinates are visible anyway */
    }
  }

  return (
    <article className="detail" aria-labelledby="detail-title">
      <button type="button" className="link-button back" onClick={onBack}>
        ← {s.back}
      </button>

      <header className="detail-head">
        <ScoreRing score={spot.score} blocked={spot.blocked} />
        <div>
          {rank !== null && <p className="detail-rank">#{rank}</p>}
          <h2 id="detail-title">{title}</h2>
          <p className="muted">
            {spot.area_name ? `${category} · ` : ''}
            {spot.blocked ? s.blocked : `${percent(spot.score)} / 100 ${s.scoreLabel}`}
          </p>
        </div>
      </header>

      <div className="actions">
        <a className="btn btn-primary" href={preferredRoute(spot.lat, spot.lon)} target="_blank" rel="noopener">
          {s.route}
        </a>
        <button type="button" className="btn" onClick={share} disabled={shareState === 'busy'}>
          {shareState === 'copied' ? s.shared : s.share}
        </button>
        <button
          type="button"
          className="btn"
          aria-pressed={saved}
          onClick={() =>
            setSaved(favorites.toggle({ lat: spot.lat, lon: spot.lon, score: spot.score, category: spot.category }))
          }
        >
          {saved ? `★ ${s.saved}` : `☆ ${s.save}`}
        </button>
        <button type="button" className="btn" onClick={downloadStory} disabled={storyBusy}>
          {s.storyImage}
        </button>
      </div>

      {spot.reasons.length > 0 && (
        <section>
          <h3>{s.why}</h3>
          <ul className="reasons">
            {spot.reasons.map((r) => (
              <li key={r.code}>{reasonText(r, lang)}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>{s.watch}</h3>
        {warnings.length ? (
          <ul className="warnings">
            {warnings.map((w, i) => (
              <li key={`${w.code}-${i}`} className={`warning warning-${w.level}`}>
                {warningText(w, lang)}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">{s.noWarnings}</p>
        )}
        <p className="dipul">
          <a className="btn" href={DIPUL_MAP} target="_blank" rel="noopener">
            {s.checkDipul} ↗
          </a>
        </p>
      </section>

      <section>
        <h3>{s.weather}</h3>
        <Weather lat={spot.lat} lon={spot.lon} lang={lang} s={s} />
      </section>

      <section>
        <h3>{s.coords}</h3>
        <p className="coords">
          <code>{coords}</code>
          <button type="button" className="btn btn-small" onClick={copyCoords}>
            {copied ? s.copied : s.copy}
          </button>
          <button
            type="button"
            className="btn btn-small"
            onClick={() =>
              downloadGpx(
                [{ lat: spot.lat, lon: spot.lon, name: title, desc: `${percent(spot.score)}/100` }],
                `fpv-spot-${spot.lat.toFixed(4)}-${spot.lon.toFixed(4)}.gpx`,
              )
            }
          >
            {s.gpx}
          </button>
        </p>
        <p className="route-alt">
          <a href={links.google} target="_blank" rel="noopener">Google Maps</a> ·{' '}
          <a href={links.apple} target="_blank" rel="noopener">{lang === 'de' ? 'Apple Karten' : 'Apple Maps'}</a> ·{' '}
          <a href={links.osm} target="_blank" rel="noopener">OpenStreetMap</a>
        </p>
      </section>

      <details className="components">
        <summary>{s.details}</summary>
        <p className="bars-head">
          {s.solitude} <strong>{percent(spot.solitude)}</strong> · {s.flyability} <strong>{percent(spot.flyability)}</strong>
        </p>
      </details>
    </article>
  )
}
