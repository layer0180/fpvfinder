import { useCallback, useEffect, useRef, useState } from 'react'
import type { CameraOptions, Map as MlMap, PaddingOptions } from 'maplibre-gl'
import { reverse, runSearch } from './api'
import { categoryLabel, reasonText, t, warningText, type Lang } from './i18n'
import { GERMANY, setPoints } from './mapSetup'
import { CountUp, createPresentMap, Outro, presentCopy, presentSearch, sleep, waitIdle } from './presentKit'
import { distanceM, percent, scoreStep } from './spots'
import type { Point } from './types'
import type { UrlState } from './urlState'

/**
 * Video mode for one spot: /app?present=spot&lat=..&lon=..&r=..&spot=LAT,LON
 *
 * A camera flight for a short vertical video, about 20 seconds: Germany with
 * the spot pulsing, down to the town, down to the spot with tilted 3D view,
 * one slow orbit while its card counts the score up, then the site's address.
 *
 *   clean=1     no text at all - for people who add their own in an editor
 *   title=...   own headline instead of "FPV spot near <town>"
 *
 * The search is the finder's own (presentSearch), so the spot scores exactly
 * as in the list. Without ``spot`` the centre itself is the spot.
 *
 * Before the first take the whole flight is flown once behind a cover, so the
 * tiles are in the cache and the recording shows no half-loaded map.
 */

type Stage =
  | { kind: 'loading' }
  | { kind: 'preparing' }
  | { kind: 'ready' }
  | { kind: 'intro' }
  | { kind: 'town' }
  | { kind: 'approach' }
  | { kind: 'card' }
  | { kind: 'outro' }
  | { kind: 'failed' }

const LEVEL_ORDER = { danger: 0, warning: 1, info: 2 } as const
// The rated point nearest to the requested coordinate is the one shown, if it
// is this close. A point picked in a village can be a few hundred metres from
// the nearest rated one: the grid leaves out built-up land.
const MATCH_M = 400

interface Props {
  lang: Lang
  url: UrlState
  lat: number
  lon: number
  radiusKm: number
  spot: { lat: number; lon: number }
  clean: boolean
  title?: string
}

/**
 * The flight's camera positions. The spot sits a little left of centre and
 * between the card above and the caption below - where TikTok's buttons and
 * text leave the picture free.
 */
function cameras(m: MlMap, spot: { lat: number; lon: number }) {
  const { clientWidth: w, clientHeight: h } = m.getContainer()
  const framing: PaddingOptions = { top: h * 0.42, bottom: h * 0.24, left: w * 0.05, right: w * 0.17 }
  const center: [number, number] = [spot.lon, spot.lat]
  // Germany below the title, read back from the map itself.
  m.fitBounds(GERMANY, { padding: { top: h * 0.36, bottom: h * 0.2, left: 16, right: 16 }, duration: 0 })
  const overview = {
    center: m.getCenter().toArray() as [number, number],
    zoom: m.getZoom(),
    pitch: 0,
    bearing: 0,
    padding: { top: 0, bottom: 0, left: 0, right: 0 },
  }
  const town = { center, zoom: 10.8, pitch: 30, bearing: -8, padding: framing }
  const close = { center, zoom: 16.2, pitch: 62, bearing: -30, padding: framing }
  const outro = { center, zoom: 13, pitch: 0, bearing: 0, padding: { top: h * 0.2, bottom: h * 0.2, left: 0, right: 0 } }
  return { overview, town, close, outro, orbit: 105 }
}

/**
 * Flies every camera position of the flight once, behind a cover, and waits
 * at each until its tiles are drawn - afterwards the take plays from cache.
 */
async function prepare(m: MlMap, cam: ReturnType<typeof cameras>, spot: Point, signal: AbortSignal) {
  const [x0, y0] = cam.overview.center
  // flyTo passes the zoom levels in between on its way down to the town.
  const between = [0.35, 0.7].map((k) => ({
    center: [x0 + (spot.lon - x0) * k, y0 + (spot.lat - y0) * k] as [number, number],
    zoom: cam.overview.zoom + (cam.town.zoom - cam.overview.zoom) * k,
    pitch: 0,
    bearing: 0,
    padding: cam.overview.padding,
  }))
  const stops: CameraOptions[] = [
    ...between,
    cam.town,
    { ...cam.close, zoom: 13.5, pitch: 45 },
    cam.close,
    { ...cam.close, bearing: cam.close.bearing + cam.orbit / 2 },
    { ...cam.close, bearing: cam.close.bearing + cam.orbit },
    cam.outro,
    cam.overview,
  ]
  for (const stop of stops) {
    if (signal.aborted) return
    m.jumpTo(stop)
    await waitIdle(m)
  }
}

export default function SpotFlight({ lang, url, lat, lon, radiusKm, spot, clean, title }: Props) {
  const c = presentCopy[lang]
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const run = useRef<AbortController | null>(null)
  const cam = useRef<ReturnType<typeof cameras> | null>(null)
  const [stage, setStage] = useState<Stage>({ kind: 'loading' })
  const [target, setTarget] = useState<Point | null>(null)
  const [place, setPlace] = useState('')
  const [finished, setFinished] = useState(false)

  // --- data and map ------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController()
    const search = runSearch(presentSearch(url, lat, lon, radiusKm), () => {}, controller.signal)
    const label = reverse(spot.lat, spot.lon, lang).then((l) => l.split(',')[0])
    const mapReady = createPresentMap(container.current!, GERMANY).then((made) => {
      map.current = made.map
      return made.maplibre
    })

    Promise.all([search, label, mapReady])
      .then(([res, name, maplibre]) => {
        const match = res.points.reduce<Point | null>(
          (best, p) => (!best || distanceM(p, spot) < distanceM(best, spot) ? p : best),
          null,
        )
        if (!match || distanceM(match, spot) > MATCH_M) return setStage({ kind: 'failed' })
        setTarget(match)
        setPlace(name)
        const m = map.current!
        setPoints(m, res.points)
        // The rated points only appear on the way down; over Germany they
        // would be one smudge.
        m.setPaintProperty('points', 'circle-opacity', [
          'interpolate',
          ['linear'],
          ['zoom'],
          11.5,
          0,
          13.5,
          ['case', ['==', ['get', 'blocked'], 1], 0.35, 0.8],
        ])
        m.setPaintProperty('points', 'circle-stroke-opacity', ['interpolate', ['linear'], ['zoom'], 11.5, 0, 13.5, 1])
        const el = document.createElement('div')
        el.className = 'spot-pin present-target'
        el.dataset.step = match.blocked ? 'blocked' : String(Math.min(4, Math.floor(match.score * 5)))
        new maplibre.Marker({ element: el }).setLngLat([match.lon, match.lat]).addTo(m)
        // Computed once, while the map still has no padding of its own, so
        // every take flies exactly the same path.
        cam.current = cameras(m, match)
        setStage({ kind: 'preparing' })
        return prepare(m, cam.current, match, controller.signal).then(() => {
          if (!controller.signal.aborted) setStage({ kind: 'ready' })
        })
      })
      .catch((e) => {
        if ((e as Error).name !== 'AbortError') setStage({ kind: 'failed' })
      })

    return () => {
      controller.abort()
      run.current?.abort()
      map.current?.remove()
    }
  }, [url, lat, lon, radiusKm, spot, lang])

  // --- the sequence ------------------------------------------------------------
  const play = useCallback(async () => {
    const m = map.current
    const path = cam.current
    if (!m || !path) return
    run.current?.abort()
    const controller = new AbortController()
    run.current = controller
    const { signal } = controller
    try {
      setFinished(false)
      m.jumpTo(path.overview)
      setStage({ kind: 'intro' })
      await sleep(2400, signal)

      setStage({ kind: 'town' })
      m.flyTo({ ...path.town, duration: 3000, curve: 1.3, essential: true })
      await sleep(3100, signal)

      setStage({ kind: 'approach' })
      m.flyTo({ ...path.close, duration: 3400, curve: 1.2, essential: true })
      await sleep(3500, signal)

      setStage({ kind: 'card' })
      // One slow, even orbit while the card is read.
      m.easeTo({ bearing: path.close.bearing + path.orbit, duration: 7000, easing: (k) => k, essential: true })
      await sleep(7000, signal)

      setStage({ kind: 'outro' })
      m.easeTo({ ...path.outro, duration: 2200, essential: true })
      // The replay hint waits, so a recording stopped on the outro ends clean.
      await sleep(3500, signal)
      setFinished(true)
    } catch {
      /* restarted or left - nothing to clean up */
    }
  }, [])

  const warning = target ? [...target.warnings].sort((a, b) => LEVEL_ORDER[a.level] - LEVEL_ORDER[b.level])[0] : undefined
  const headline = title || (place ? t(c.spotTitle, { place }) : c.spotTitleNoPlace)
  const exit = new URLSearchParams(location.search)
  for (const key of ['present', 'clean', 'title']) exit.delete(key)
  const exitHref = `${location.pathname}?${exit.toString().replace(/%2C/gi, ',')}`
  const titled = !clean && ['ready', 'intro'].includes(stage.kind)
  const idle = ['ready', 'failed'].includes(stage.kind) || finished

  return (
    <div className="present" onClick={() => !['loading', 'failed', 'preparing'].includes(stage.kind) && play()}>
      <div className={`present-frame present-spot${titled ? ' has-title' : ''}`}>
        <div ref={container} className="present-map" />

        {titled && (
          <div className="present-title">
            <h1>{headline}</h1>
            {!title && <p>{c.spotSub}</p>}
          </div>
        )}

        {!clean && (stage.kind === 'town' || stage.kind === 'approach') && place && (
          <p className="present-place">📍 {place}</p>
        )}

        {!clean && stage.kind === 'card' && target && (
          <div className="present-card">
            <div
              className="present-score"
              style={{ ['--ring' as string]: scoreStep(target.score, target.blocked), ['--p' as string]: `${percent(target.score)}%` }}
            >
              <span>{target.blocked ? '✕' : <CountUp to={percent(target.score)} />}</span>
            </div>
            <div className="present-text">
              <h2>{target.area_name || categoryLabel(target.category, lang)}</h2>
              <ul>
                {target.reasons.slice(0, 3).map((r) => (
                  <li key={r.code}>{reasonText(r, lang)}</li>
                ))}
              </ul>
            </div>
            {warning && <p className={`present-warning present-warning-${warning.level}`}>{warningText(warning, lang)}</p>}
            <p className="present-check">{c.checkDipul}</p>
          </div>
        )}

        {!clean && stage.kind === 'outro' && <Outro c={c} />}

        {stage.kind === 'preparing' && (
          <div className="present-cover">
            <p>{c.preparing}</p>
          </div>
        )}
        {stage.kind === 'loading' && <p className="present-hint">{c.loading}</p>}
        {stage.kind === 'failed' && <p className="present-hint">{c.failed}</p>}
        {(stage.kind === 'ready' || (stage.kind === 'outro' && finished)) && (
          <p className="present-hint">{finished ? c.replay : c.tap}</p>
        )}

        {idle && (
          <a className="present-exit" href={exitHref} aria-label={c.exit} onClick={(e) => e.stopPropagation()}>
            ×
          </a>
        )}
      </div>
    </div>
  )
}
