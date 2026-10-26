import { useCallback, useEffect, useRef, useState } from 'react'
import type { Map as MlMap, Marker } from 'maplibre-gl'
import { getHealth, reverse, runSearch } from './api'
import { categoryLabel, reasonText, t, type Lang } from './i18n'
import { addSpotLayers, loadMapLibre, radiusBounds, setArea, setPoints } from './mapSetup'
import { percent, pickTopSpots, scoreStep } from './spots'
import { profileFor } from './timeProfile'
import type { Point, SearchResult } from './types'

/**
 * Video mode: /app?present=1&lat=..&lon=..&r=..[&n=3]
 *
 * Built to be screen-recorded on a phone for TikTok and friends - a 9:16
 * frame with no controls: an overview, then a camera flight to each of the
 * top spots with its score counting up, then the site's address. Tap to run
 * it again. On a wide screen the frame is centred, so a desktop recording
 * crops to 9:16 without effort.
 */

const copy = {
  de: {
    title: 'Die ruhigsten FPV-Spots bei {place}',
    titleNoPlace: 'Die ruhigsten FPV-Spots hier',
    sub: 'im Umkreis von {r} km',
    points: 'Punkte',
    outro: 'Finde deinen Spot',
    outroSub: 'kostenlos · ohne Anmeldung',
    tap: 'Tippen zum Starten',
    replay: 'Tippen für Wiederholung',
    exit: 'Video-Modus verlassen',
    loading: 'Lädt …',
    failed: 'Für diesen Ort gibt es keine Ergebnisse.',
  },
  en: {
    title: 'The quietest FPV spots near {place}',
    titleNoPlace: 'The quietest FPV spots around here',
    sub: 'within {r} km',
    points: 'points',
    outro: 'Find your spot',
    outroSub: 'free · no sign-up',
    tap: 'Tap to start',
    replay: 'Tap to replay',
    exit: 'Leave video mode',
    loading: 'Loading …',
    failed: 'No results for this place.',
  },
} as const

type Stage = { kind: 'loading' } | { kind: 'ready' } | { kind: 'intro' } | { kind: 'fly'; i: number } | { kind: 'card'; i: number } | { kind: 'outro' } | { kind: 'failed' }

const reduceMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })

function CountUp({ to, ms = 900 }: { to: number; ms?: number }) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (reduceMotion()) return setValue(to)
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / ms)
      setValue(Math.round(to * (1 - (1 - k) ** 3)))
      if (k < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [to, ms])
  return <>{value}</>
}

interface Props {
  lang: Lang
  lat: number
  lon: number
  radiusKm: number
  count: number
}

export default function Presentation({ lang, lat, lon, radiusKm, count }: Props) {
  const c = copy[lang]
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const markers = useRef<Marker[]>([])
  const run = useRef<AbortController | null>(null)
  const [stage, setStage] = useState<Stage>({ kind: 'loading' })
  const [result, setResult] = useState<SearchResult | null>(null)
  const [spots, setSpots] = useState<Point[]>([])
  const [place, setPlace] = useState('')
  const [played, setPlayed] = useState(false)
  const host = location.host.replace(/^www\./, '')

  // --- data and map ------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController()
    const search = runSearch({ lat, lon, radiusKm, timeProfile: profileFor(), spacingM: 150 }, () => {}, controller.signal)
    const label = reverse(lat, lon, lang).then((l) => l.split(',')[0])
    const mapReady = (async () => {
      const [maplibre, health] = await Promise.all([loadMapLibre(), getHealth().catch(() => null)])
      const m = new maplibre.Map({
        container: container.current!,
        style: health?.map_style_url || 'https://tiles.openfreemap.org/styles/liberty',
        bounds: radiusBounds(lat, lon, radiusKm),
        interactive: false,
        attributionControl: false,
        fadeDuration: 0,
      })
      m.addControl(new maplibre.AttributionControl({ compact: false }), 'top-left')
      await new Promise<void>((resolve) => m.on('load', () => resolve()))
      addSpotLayers(m)
      map.current = m
      return maplibre
    })()

    Promise.all([search, label, mapReady])
      .then(([res, name, maplibre]) => {
        const top = pickTopSpots(res.points, count, Math.max(600, (radiusKm * 1000) / 4))
        setResult(res)
        setSpots(top)
        setPlace(name)
        const m = map.current!
        setArea(m, lat, lon, radiusKm)
        setPoints(m, res.points)
        markers.current = top.map((spot, i) => {
          const el = document.createElement('div')
          el.className = 'spot-pin present-pin'
          el.dataset.step = String(Math.min(4, Math.floor(spot.score * 5)))
          el.textContent = String(i + 1)
          return new maplibre.Marker({ element: el }).setLngLat([spot.lon, spot.lat]).addTo(m)
        })
        setStage(top.length ? { kind: 'ready' } : { kind: 'failed' })
      })
      .catch((e) => {
        if ((e as Error).name !== 'AbortError') setStage({ kind: 'failed' })
      })

    return () => {
      controller.abort()
      run.current?.abort()
      map.current?.remove()
    }
  }, [lat, lon, radiusKm, count, lang])

  // --- the sequence ------------------------------------------------------------
  const play = useCallback(async () => {
    const m = map.current
    if (!m || !spots.length) return
    run.current?.abort()
    const controller = new AbortController()
    run.current = controller
    const { signal } = controller
    const instant = reduceMotion()
    // Overview below the title block, which takes the top ~40 % of the frame.
    const overview = () => {
      const h = m.getContainer().clientHeight
      m.fitBounds(radiusBounds(lat, lon, radiusKm), {
        padding: { top: h * 0.4, bottom: h * 0.06, left: 24, right: 24 },
        pitch: 0,
        bearing: 0,
        duration: instant ? 0 : 1800,
      })
    }
    const highlight = (index: number) =>
      markers.current.forEach((marker, i) => marker.getElement().classList.toggle('is-selected', i === index))
    try {
      setPlayed(true)
      highlight(-1)
      overview()
      setStage({ kind: 'intro' })
      await sleep(2600, signal)
      for (let i = 0; i < spots.length; i++) {
        setStage({ kind: 'fly', i })
        highlight(i)
        m.flyTo({
          center: [spots[i].lon, spots[i].lat],
          zoom: 15.4,
          pitch: 55,
          bearing: 25 - i * 40,
          duration: instant ? 0 : 3200,
          curve: 1.5,
          // Keep the spot above the card at the bottom of the frame.
          padding: { top: 0, bottom: m.getContainer().clientHeight * 0.35, left: 0, right: 0 },
        })
        await sleep(instant ? 300 : 3300, signal)
        setStage({ kind: 'card', i })
        // A slow drift keeps the picture alive while the card is read.
        if (!instant) m.easeTo({ bearing: m.getBearing() + 18, duration: 3600, easing: (k) => k })
        await sleep(3600, signal)
      }
      highlight(-1)
      overview()
      setStage({ kind: 'outro' })
    } catch {
      /* restarted or left - nothing to clean up */
    }
  }, [spots, lat, lon, radiusKm])

  const current = stage.kind === 'card' || stage.kind === 'fly' ? spots[stage.i] : null
  const exitHref = `${location.pathname}?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}&r=${radiusKm}`

  return (
    <div className="present" onClick={() => stage.kind !== 'loading' && stage.kind !== 'failed' && play()}>
      <div className={`present-frame${['intro', 'ready', 'outro'].includes(stage.kind) ? ' has-title' : ''}`}>
        <div ref={container} className="present-map" />

        {(stage.kind === 'intro' || stage.kind === 'ready') && (
          <div className="present-title">
            <h1>{place ? t(c.title, { place }) : c.titleNoPlace}</h1>
            <p>{t(c.sub, { r: result?.radius_km ?? radiusKm })}</p>
          </div>
        )}

        {stage.kind === 'card' && current && (
          <div className="present-card" key={stage.i}>
            <span className="present-rank">#{stage.i + 1}</span>
            <div className="present-score" style={{ ['--ring' as string]: scoreStep(current.score, current.blocked), ['--p' as string]: `${percent(current.score)}%` }}>
              <span>
                <CountUp to={percent(current.score)} />
              </span>
            </div>
            <div className="present-text">
              <h2>{current.area_name || categoryLabel(current.category, lang)}</h2>
              <ul>
                {current.reasons.slice(0, 2).map((r) => (
                  <li key={r.code}>{reasonText(r, lang)}</li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {stage.kind === 'outro' && (
          <div className="present-outro">
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <g fill="none" stroke="#ff8a3d" strokeWidth="2.6" strokeLinecap="round">
                <path d="M9 9 23 23M23 9 9 23" />
                <circle cx="7" cy="7" r="5" />
                <circle cx="25" cy="7" r="5" />
                <circle cx="7" cy="25" r="5" />
                <circle cx="25" cy="25" r="5" />
              </g>
              <circle cx="16" cy="16" r="3.4" fill="#fff" />
            </svg>
            <h2>{c.outro}</h2>
            <p className="present-host">{host}</p>
            <p>{c.outroSub}</p>
          </div>
        )}

        {stage.kind === 'loading' && <p className="present-hint">{c.loading}</p>}
        {stage.kind === 'failed' && <p className="present-hint">{c.failed}</p>}
        {(stage.kind === 'ready' || stage.kind === 'outro') && (
          <p className="present-hint">{played ? c.replay : c.tap}</p>
        )}

        <a className="present-exit" href={exitHref} aria-label={c.exit} onClick={(e) => e.stopPropagation()}>
          ×
        </a>
      </div>
    </div>
  )
}
