import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './finder.css'
import { ApiError, createShare, geocode, getAirspace, getHealth, reverse, runSearch } from './api'
import { errorText, strings, t, timeProfileLabel, type Lang } from './i18n'
import { distanceM, pickTopSpots } from './spots'
import { profileFor } from './timeProfile'
import { readUrl, writeUrl } from './urlState'
import { disclaimer, favorites } from './storage'
import type { Health, JobStatus, Place, Point, SearchResult, ZoneCollection } from './types'
import SearchBar from './SearchBar'
import ResultList from './ResultList'
import SpotDetail from './SpotDetail'
import TuningPanel, { tuningWeights, type Tuning } from './Tuning'

// The map is the heaviest part of the page by far; it loads after the panel is
// already usable, so the first paint is the search field, not a grey box.
const MapView = lazy(() => import('./MapView'))
const Presentation = lazy(() => import('./Presentation'))

type Phase = 'idle' | 'locating' | 'searching' | 'results' | 'error'
type SheetSize = 'peek' | 'half' | 'full'

const DEFAULT_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const DEFAULT_RADIUS = 5
const DEFAULT_SPACING = 150
// backend/app/scoring/defaults.py: solitude 0.55, flyability 0.45
const DEFAULT_BALANCE = 55
const DESKTOP = '(min-width: 900px)'
const PANEL_WIDTH = 420

function useMedia(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const update = () => setMatches(mql.matches)
    mql.addEventListener('change', update)
    return () => mql.removeEventListener('change', update)
  }, [query])
  return matches
}

function stageOf(job: JobStatus | null): number {
  const p = job?.progress ?? 0
  return p < 0.05 ? 0 : p < 0.58 ? 1 : p < 0.93 ? 2 : 3
}

export default function Finder({ lang }: { lang: Lang }) {
  const initial = useMemo(() => readUrl(), [])
  // Video mode replaces the whole finder (see Presentation.tsx).
  if (initial.present && initial.lat !== undefined && initial.lon !== undefined) {
    const count = Number(new URLSearchParams(location.search).get('n')) || 3
    return (
      <Suspense fallback={null}>
        <Presentation
          lang={lang}
          lat={initial.lat}
          lon={initial.lon}
          radiusKm={initial.r ?? DEFAULT_RADIUS}
          count={Math.min(5, Math.max(1, count))}
        />
      </Suspense>
    )
  }
  return <FinderApp lang={lang} initial={initial} />
}

function FinderApp({ lang, initial }: { lang: Lang; initial: ReturnType<typeof readUrl> }) {
  const s = strings(lang)
  const desktop = useMedia(DESKTOP)

  const [health, setHealth] = useState<Health | null>(null)
  const [zones, setZones] = useState<ZoneCollection | null>(null)
  const [radiusKm, setRadiusKm] = useState(initial.r ?? DEFAULT_RADIUS)
  const [profile, setProfile] = useState(initial.t ?? 'auto')
  const [spacing, setSpacing] = useState(initial.spacing ?? DEFAULT_SPACING)
  const [balance, setBalance] = useState(initial.balance ?? DEFAULT_BALANCE)
  const [tuning, setTuning] = useState<Tuning>({})
  const [includeProtected, setIncludeProtected] = useState(initial.protectedAreas ?? false)
  const [place, setPlace] = useState<Place | null>(
    initial.lat !== undefined && initial.lon !== undefined ? { label: '', lat: initial.lat, lon: initial.lon } : null,
  )
  const [phase, setPhase] = useState<Phase>('idle')
  const [job, setJob] = useState<JobStatus | null>(null)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [selected, setSelected] = useState<Point | null>(null)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [sheet, setSheet] = useState<SheetSize>('half')
  const [ack, setAck] = useState(() => disclaimer.acknowledged())
  const abort = useRef<AbortController | null>(null)
  const pendingSpot = useRef(initial.spot)
  // The map waits until the panel has painted and the browser is idle:
  // parsing MapLibre blocks the main thread for a second on a mid-range
  // phone, and the list is what people read first.
  const [mapWanted, setMapWanted] = useState(false)
  useEffect(() => {
    if (!place || mapWanted) return
    const show = () => setMapWanted(true)
    // Safari has no requestIdleCallback.
    if ('requestIdleCallback' in window) {
      const handle = window.requestIdleCallback(show, { timeout: 1500 })
      return () => window.cancelIdleCallback(handle)
    }
    const handle = setTimeout(show, 200)
    return () => clearTimeout(handle)
  }, [place, mapWanted])

  // Separation grows with the area: in a 5 km search, ten spots 450 m apart
  // tend to be ten corners of the same large field.
  const topSpots = useMemo(
    () =>
      result
        ? pickTopSpots(result.points, 10, Math.max(450, (result.radius_km * 1000) / 6), undefined, result.includeProtected)
        : [],
    [result],
  )
  const maxRadius = Math.min(20, health?.limits.max_radius_km ?? 10)

  // --- search ---------------------------------------------------------------
  const search = useCallback(
    async (target: Place, radius = radiusKm) => {
      abort.current?.abort()
      const controller = new AbortController()
      abort.current = controller
      setPlace(target)
      setSelected(null)
      setError('')
      setJob(null)
      setPhase('searching')
      if (!desktop) setSheet('half')
      writeUrl({
        lat: target.lat,
        lon: target.lon,
        r: radius,
        t: profile,
        spacing: spacing === DEFAULT_SPACING ? undefined : spacing,
        balance: balance === DEFAULT_BALANCE ? undefined : balance,
        protectedAreas: includeProtected,
      })
      try {
        const res = await runSearch(
          {
            lat: target.lat,
            lon: target.lon,
            radiusKm: radius,
            timeProfile: profile === 'auto' ? profileFor() : profile,
            spacingM: spacing,
            solitudeShare: balance === DEFAULT_BALANCE ? undefined : balance / 100,
            weights: tuningWeights(tuning),
            includeProtected,
          },
          setJob,
          controller.signal,
        )
        // Remembered with the result: the list must follow the search that
        // produced it, not a checkbox changed since.
        setResult({ ...res, includeProtected })
        setPhase('results')
        // A shared /app?spot=... link opens straight on that spot.
        const wanted = pendingSpot.current
        pendingSpot.current = undefined
        if (wanted) {
          const match = res.points.reduce<Point | null>(
            (best, p) => (!best || distanceM(p, wanted) < distanceM(best, wanted) ? p : best),
            null,
          )
          if (match && distanceM(match, wanted) < 200) setSelected(match)
        }
      } catch (e) {
        if ((e as Error).name === 'AbortError') return
        setError(errorText(e instanceof ApiError ? e.code : 'generic', lang))
        setPhase('error')
      }
    },
    [radiusKm, profile, spacing, balance, tuning, includeProtected, desktop, lang],
  )

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setMessage(s.locateUnavailable)
      return
    }
    setMessage('')
    setPhase('locating')
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const target = { label: '', lat: position.coords.latitude, lon: position.coords.longitude }
        search(target)
        const label = await reverse(target.lat, target.lon, lang)
        if (label) setPlace((p) => (p && p.lat === target.lat ? { ...p, label } : p))
      },
      (err) => {
        setPhase(result ? 'results' : 'idle')
        setMessage(err.code === err.PERMISSION_DENIED ? s.locateDenied : s.locateUnavailable)
      },
      { enableHighAccuracy: false, timeout: 12_000, maximumAge: 120_000 },
    )
  }, [search, lang, s, result])

  // --- first load: health, then whatever the URL asks for --------------------
  useEffect(() => {
    getHealth()
      .then((h) => {
        setHealth(h)
        if (h.airspace_enabled) getAirspace().then(setZones).catch(() => setZones(null))
      })
      .catch(() => setHealth(null))
    if (initial.lat !== undefined && initial.lon !== undefined) {
      search({ label: '', lat: initial.lat, lon: initial.lon })
      reverse(initial.lat, initial.lon, lang).then((label) => label && setPlace((p) => (p ? { ...p, label } : p)))
    } else if (initial.q) {
      geocode(initial.q, lang)
        .then((found) => (found[0] ? search(found[0]) : setMessage(s.noPlaceFound)))
        .catch(() => setMessage(errorText('geocoder_unavailable', lang)))
    } else if (initial.locate) {
      locate()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Keep the selected spot in the URL, so a reload or a copied link reopens it.
  useEffect(() => {
    if (!place) return
    writeUrl(
      {
        lat: place.lat,
        lon: place.lon,
        r: radiusKm,
        t: profile,
        spacing: spacing === DEFAULT_SPACING ? undefined : spacing,
        balance: balance === DEFAULT_BALANCE ? undefined : balance,
        protectedAreas: includeProtected,
        spot: selected ? { lat: selected.lat, lon: selected.lon } : undefined,
      },
      'replace',
    )
  }, [selected]) // eslint-disable-line react-hooks/exhaustive-deps

  const share = useCallback(
    async (spot: Point) => {
      if (!result) throw new Error('no result')
      const { id } = await createShare(result.result_id, spot.id)
      return `${location.origin}/s/${id}`
    },
    [result],
  )

  const surprise = () => {
    const pool = topSpots.slice(0, 5)
    if (pool.length) select(pool[Math.floor(Math.random() * pool.length)])
  }

  const panelBody = useRef<HTMLDivElement>(null)
  const select = (spot: Point) => {
    setSelected(spot)
    panelBody.current?.scrollTo({ top: 0 })
    if (!desktop) setSheet('half')
  }

  // --- layout ---------------------------------------------------------------
  const sheetHeights: Record<SheetSize, number> = {
    peek: 168,
    half: Math.round(window.innerHeight * 0.52),
    full: Math.round(window.innerHeight * 0.9),
  }
  const padding = desktop
    ? { top: 16, right: 16, bottom: 16, left: PANEL_WIDTH + 16 }
    : { top: 16, right: 16, bottom: sheetHeights[sheet], left: 16 }

  const rank = selected ? topSpots.findIndex((p) => p.id === selected.id) : -1
  const profileShown = profile === 'auto' ? profileFor() : profile

  return (
    <div className={`finder ${desktop ? 'is-desktop' : `is-mobile sheet-${sheet}`}`}>
      {/* MapLibre (~285 kB) loads once there is something to show - not for
          the empty first screen, where it would only cost phones a second of
          blocked main thread. */}
      {place && mapWanted ? (
        <Suspense fallback={<div className="map-wrap" />}>
          <MapView
            styleUrl={health?.map_style_url || DEFAULT_STYLE}
            center={place}
            radiusKm={radiusKm}
            points={result?.points ?? []}
            topSpots={topSpots}
            selected={selected}
            onSelect={select}
            padding={padding}
            zones={zones}
            s={s}
          />
        </Suspense>
      ) : (
        <div className="map-wrap map-idle" aria-hidden="true" />
      )}

      <section className="panel" aria-label={s.searchLabel} style={desktop ? undefined : { height: sheetHeights[sheet] }}>
        {!desktop && (
          <button
            type="button"
            className="sheet-handle"
            aria-label={sheet === 'full' ? s.collapse : s.expand}
            onClick={() => setSheet(sheet === 'peek' ? 'half' : sheet === 'half' ? 'full' : 'peek')}
          >
            <span />
          </button>
        )}

        <div className="panel-top">
          <a className="panel-home" href={lang === 'de' ? '/' : '/en'} aria-label={s.home}>
            <svg viewBox="0 0 32 32" aria-hidden="true">
              <g fill="none" stroke="var(--accent)" strokeWidth="2.6" strokeLinecap="round">
                <path d="M9 9 23 23M23 9 9 23" />
                <circle cx="7" cy="7" r="5" />
                <circle cx="25" cy="7" r="5" />
                <circle cx="7" cy="25" r="5" />
                <circle cx="25" cy="25" r="5" />
              </g>
            </svg>
          </a>
          <SearchBar
            lang={lang}
            s={s}
            value={place?.label?.split(',')[0] ?? initial.q ?? ''}
            onPick={(p) => search(p)}
            onLocate={locate}
            locating={phase === 'locating'}
            message={message}
          />
        </div>

        <div className="panel-body" ref={panelBody}>
          {!ack && (
            <div className="disclaimer" role="note">
              <p>
                <strong>{s.disclaimerTitle}.</strong> {s.disclaimerShort}
              </p>
              <button
                type="button"
                className="btn btn-small"
                onClick={() => {
                  disclaimer.acknowledge()
                  setAck(true)
                }}
              >
                {s.understood}
              </button>
            </div>
          )}

          {selected ? (
            <SpotDetail
              key={selected.id}
              spot={selected}
              rank={rank >= 0 ? rank + 1 : null}
              lang={lang}
              s={s}
              onBack={() => {
                setSelected(null)
                panelBody.current?.scrollTo({ top: 0 })
              }}
              onShare={share}
            />
          ) : (
            <>
              {(phase === 'idle' || phase === 'locating') && !result && (
                <Idle s={s} onSelectSaved={(f) => {
                  pendingSpot.current = { lat: f.lat, lon: f.lon }
                  search({ label: '', lat: f.lat, lon: f.lon }, Math.min(radiusKm, 3))
                }} />
              )}

              {phase === 'searching' && (
                <div className="progress" role="status" aria-live="polite">
                  <p className="progress-title">{s.searchingTitle} …</p>
                  <div className="progress-bar">
                    <span style={{ width: `${Math.max(6, (job?.progress ?? 0.03) * 100)}%` }} />
                  </div>
                  <ol className="stages">
                    {s.stages.map((label, i) => (
                      <li key={label} data-state={i < stageOf(job) ? 'done' : i === stageOf(job) ? 'active' : 'todo'}>
                        {label}
                      </li>
                    ))}
                  </ol>
                  <button type="button" className="btn btn-small" onClick={() => {
                    abort.current?.abort()
                    setPhase(result ? 'results' : 'idle')
                  }}>
                    {s.cancel}
                  </button>
                </div>
              )}

              {phase === 'error' && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}

              {phase === 'results' && result && (
                <>
                  <div className="results-head">
                    <div>
                      <h2>{s.topSpots}</h2>
                      <p className="muted">
                        {t(s.within, { r: result.radius_km })} · {timeProfileLabel(result.time_profile, lang)}
                      </p>
                    </div>
                    <div className="results-actions">
                      {topSpots.length > 1 && (
                        <button type="button" className="btn btn-small" onClick={surprise}>
                          🎲 {s.surprise}
                        </button>
                      )}
                      {place && topSpots.length > 0 && (
                        <a
                          className="btn btn-small"
                          href={`?present=1&lat=${place.lat.toFixed(4)}&lon=${place.lon.toFixed(4)}&r=${result.radius_km}`}
                        >
                          🎬 {s.video}
                        </a>
                      )}
                    </div>
                  </div>
                  <ResultList spots={topSpots} lang={lang} s={s} onSelect={select} />
                </>
              )}

              {phase !== 'searching' && (
                <details className="expert">
                  <summary>{s.expert}</summary>
                  <label className="field">
                    <span>
                      {s.radius}: <strong>{radiusKm} km</strong>
                    </span>
                    <input
                      type="range"
                      min={1}
                      max={maxRadius}
                      step={1}
                      value={radiusKm}
                      onChange={(e) => setRadiusKm(Number(e.target.value))}
                    />
                  </label>
                  <label className="field">
                    <span>{s.timeProfile}</span>
                    <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                      <option value="auto">
                        {s.auto} – {timeProfileLabel(profileShown, lang)}
                      </option>
                      {(health?.time_profiles ?? []).map((key) => (
                        <option key={key} value={key}>
                          {timeProfileLabel(key, lang)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span>{s.balance}</span>
                    <input
                      type="range"
                      min={20}
                      max={80}
                      step={5}
                      value={balance}
                      aria-valuetext={`${s.balanceQuiet} ${balance} %, ${s.balanceFly} ${100 - balance} %`}
                      onChange={(e) => setBalance(Number(e.target.value))}
                    />
                    <span className="balance-scale">
                      <span>
                        {s.balanceQuiet} {balance} %
                      </span>
                      <span>
                        {s.balanceFly} {100 - balance} %
                      </span>
                    </span>
                  </label>
                  <label className="field">
                    <span>{s.spacing}</span>
                    <select value={spacing} onChange={(e) => setSpacing(Number(e.target.value))}>
                      {[100, 150, 200, 300].map((m) => (
                        <option key={m} value={m}>
                          {m} m
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={includeProtected}
                      onChange={(e) => setIncludeProtected(e.target.checked)}
                    />
                    <span>
                      {s.includeProtected}
                      <small>{s.includeProtectedNote}</small>
                    </span>
                  </label>
                  <TuningPanel s={s} value={tuning} onChange={setTuning} />
                  {place && (
                    <button type="button" className="btn btn-primary" onClick={() => search(place)}>
                      {s.apply}
                    </button>
                  )}
                </details>
              )}
            </>
          )}
        </div>
      </section>
    </div>
  )
}

function Idle({ s, onSelectSaved }: { s: ReturnType<typeof strings>; onSelectSaved: (f: { lat: number; lon: number }) => void }) {
  const saved = favorites.list()
  return (
    <div className="idle">
      <h2>{s.idleTitle}</h2>
      <p className="muted">{s.idleText}</p>
      {saved.length > 0 && (
        <>
          <h3>{s.favorites}</h3>
          <ul className="saved">
            {saved.slice(0, 5).map((f) => (
              <li key={`${f.lat},${f.lon}`}>
                <button type="button" className="link-button" onClick={() => onSelectSaved(f)}>
                  ★ {Math.round(f.score * 100)} · {f.lat.toFixed(3)}, {f.lon.toFixed(3)}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
