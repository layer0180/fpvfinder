import { useCallback, useEffect, useRef, useState } from 'react'
import type { Map as MlMap, Marker } from 'maplibre-gl'
import { reverse, runSearch } from './api'
import { categoryLabel, reasonText, t, type Lang } from './i18n'
import { radiusBounds, setArea, setPoints } from './mapSetup'
import { CountUp, createPresentMap, MapUnavailable, Outro, presentCopy, presentSearch, sleep } from './presentKit'
import { percent, pickTopSpots, scoreStep } from './spots'
import type { Point, SearchResult } from './types'
import type { UrlState } from './urlState'

/**
 * Video mode: /app?present=1&lat=..&lon=..&r=..[&n=3]
 *
 * Built to be screen-recorded on a phone for TikTok and friends - a 9:16
 * frame with no controls: an overview, then a camera flight to each of the
 * top spots with its score counting up, then the site's address. Tap to run
 * it again. On a wide screen the frame is centred, so a desktop recording
 * crops to 9:16 without effort.
 */

type Stage = { kind: 'loading' } | { kind: 'ready' } | { kind: 'intro' } | { kind: 'fly'; i: number } | { kind: 'card'; i: number } | { kind: 'outro' } | { kind: 'failed'; noMap?: boolean }

interface Props {
  lang: Lang
  url: UrlState
  lat: number
  lon: number
  radiusKm: number
  count: number
}

export default function Presentation({ lang, url, lat, lon, radiusKm, count }: Props) {
  const c = presentCopy[lang]
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const markers = useRef<Marker[]>([])
  const run = useRef<AbortController | null>(null)
  const [stage, setStage] = useState<Stage>({ kind: 'loading' })
  const [result, setResult] = useState<SearchResult | null>(null)
  const [spots, setSpots] = useState<Point[]>([])
  const [place, setPlace] = useState('')
  const [finished, setFinished] = useState(false)

  // --- data and map ------------------------------------------------------------
  useEffect(() => {
    const controller = new AbortController()
    const search = runSearch(presentSearch(url, lat, lon, radiusKm), () => {}, controller.signal)
    const label = reverse(lat, lon, lang).then((l) => l.split(',')[0])
    const mapReady = createPresentMap(container.current!, radiusBounds(lat, lon, radiusKm)).then((made) => {
      map.current = made.map
      return made.maplibre
    })

    Promise.all([search, label, mapReady])
      .then(([res, name, maplibre]) => {
        const top = pickTopSpots(res.points, count, Math.max(600, (radiusKm * 1000) / 4), undefined, url.protectedAreas)
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
        if ((e as Error).name !== 'AbortError') setStage({ kind: 'failed', noMap: e instanceof MapUnavailable })
      })

    return () => {
      controller.abort()
      run.current?.abort()
      map.current?.remove()
    }
  }, [url, lat, lon, radiusKm, count, lang])

  // --- the sequence ------------------------------------------------------------
  const play = useCallback(async () => {
    const m = map.current
    if (!m || !spots.length) return
    run.current?.abort()
    const controller = new AbortController()
    run.current = controller
    const { signal } = controller
    // Overview below the title block, which takes the top ~40 % of the frame.
    const overview = () => {
      const h = m.getContainer().clientHeight
      m.fitBounds(radiusBounds(lat, lon, radiusKm), {
        padding: { top: h * 0.4, bottom: h * 0.22, left: 24, right: 24 },
        pitch: 0,
        bearing: 0,
        duration: 1800,
        essential: true,
      })
    }
    const highlight = (index: number) =>
      markers.current.forEach((marker, i) => marker.getElement().classList.toggle('is-selected', i === index))
    try {
      setFinished(false)
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
          duration: 3200,
          essential: true,
          curve: 1.5,
          // The spot sits between the card above and the app's caption below.
          padding: { top: m.getContainer().clientHeight * 0.42, bottom: m.getContainer().clientHeight * 0.24, left: 0, right: 0 },
        })
        await sleep(3300, signal)
        setStage({ kind: 'card', i })
        // A slow drift keeps the picture alive while the card is read.
        m.easeTo({ bearing: m.getBearing() + 18, duration: 3600, easing: (k) => k, essential: true })
        await sleep(3600, signal)
      }
      highlight(-1)
      overview()
      setStage({ kind: 'outro' })
      // The replay hint waits, so a recording stopped on the outro ends clean.
      await sleep(3500, signal)
      setFinished(true)
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

        {stage.kind === 'outro' && <Outro c={c} />}

        {stage.kind === 'loading' && <p className="present-hint">{c.loading}</p>}
        {stage.kind === 'failed' && <p className="present-hint">{stage.noMap ? c.noMap : c.failed}</p>}
        {(stage.kind === 'ready' || (stage.kind === 'outro' && finished)) && (
          <p className="present-hint">{finished ? c.replay : c.tap}</p>
        )}

        {(stage.kind === 'ready' || stage.kind === 'failed' || finished) && (
          <a className="present-exit" href={exitHref} aria-label={c.exit} onClick={(e) => e.stopPropagation()}>
            ×
          </a>
        )}
      </div>
    </div>
  )
}
