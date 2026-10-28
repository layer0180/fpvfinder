/**
 * Shared parts of the two video modes: the top-spots tour (Presentation.tsx)
 * and the flight to a single spot (SpotFlight.tsx).
 *
 * Both are recorded straight off a phone screen for TikTok and friends, so
 * the layout keeps clear of the platform's own overlays: the tabs at the top,
 * the like/comment column on the right and the caption at the bottom (see
 * .present-* in finder.css).
 */
import { useEffect, useState } from 'react'
import type { Map as MlMap, LngLatBoundsLike } from 'maplibre-gl'
import { getHealth } from './api'
import type { Lang } from './i18n'
import { addSpotLayers, loadMapLibre, type MapLibre } from './mapSetup'
import { profileFor } from './timeProfile'
import type { SearchParams } from './types'
import type { UrlState } from './urlState'

export const presentCopy = {
  de: {
    title: 'Die ruhigsten FPV-Spots bei {place}',
    titleNoPlace: 'Die ruhigsten FPV-Spots hier',
    sub: 'im Umkreis von {r} km',
    spotTitle: 'FPV-Spot bei {place}',
    spotTitleNoPlace: 'Dieser FPV-Spot',
    spotSub: 'Wie ruhig ist es hier?',
    checkDipul: 'Vor dem Flug: dipul.de prüfen',
    points: 'Punkte',
    outro: 'Finde deinen Spot',
    outroSub: 'kostenlos · ohne Anmeldung',
    tap: 'Tippen zum Starten',
    replay: 'Tippen für Wiederholung',
    preparing: 'Karte wird vorgeladen …',
    exit: 'Video-Modus verlassen',
    loading: 'Lädt …',
    failed: 'Für diesen Ort gibt es keine Ergebnisse.',
    noMap: 'Die Karte lässt sich in diesem Browser nicht anzeigen (WebGL2 nötig).',
  },
  en: {
    title: 'The quietest FPV spots near {place}',
    titleNoPlace: 'The quietest FPV spots around here',
    sub: 'within {r} km',
    spotTitle: 'FPV spot near {place}',
    spotTitleNoPlace: 'This FPV spot',
    spotSub: 'How quiet is it here?',
    checkDipul: 'Before you fly: check dipul.de',
    points: 'points',
    outro: 'Find your spot',
    outroSub: 'free · no sign-up',
    tap: 'Tap to start',
    replay: 'Tap to replay',
    preparing: 'Preloading the map …',
    exit: 'Leave video mode',
    loading: 'Loading …',
    failed: 'No results for this place.',
    noMap: 'This browser cannot show the map (WebGL2 required).',
  },
} as const

export type PresentCopy = (typeof presentCopy)[Lang]

// The camera flights ignore prefers-reduced-motion on purpose: here the motion
// is the content, it starts only on the viewer's own tap, and Windows with its
// animation effects off reports "reduce" to every page - which turned the
// video into a slideshow. Hence `essential: true` on every camera move. The
// endless pulse of the spot's pin does stop (finder.css).

export const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms)
    signal.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    })
  })

/**
 * The search the video shows: the same parameters the finder used, so the
 * server answers from its result cache and the scores match the list.
 */
export function presentSearch(url: UrlState, lat: number, lon: number, radiusKm: number): SearchParams {
  return {
    lat,
    lon,
    radiusKm,
    timeProfile: !url.t || url.t === 'auto' ? profileFor() : url.t,
    spacingM: url.spacing ?? 150,
    solitudeShare: url.balance !== undefined ? url.balance / 100 : undefined,
    includeProtected: url.protectedAreas,
  }
}

/** Thrown when the browser cannot draw the map at all - not "no results". */
export class MapUnavailable extends Error {
  name = 'MapUnavailable'
}

/** A non-interactive map in the video frame, with the spot layers added. */
export async function createPresentMap(
  container: HTMLElement,
  bounds: LngLatBoundsLike,
): Promise<{ maplibre: MapLibre; map: MlMap }> {
  // MapLibre needs WebGL2 - missing in some headless and locked-down browsers.
  if (!document.createElement('canvas').getContext('webgl2')) throw new MapUnavailable()
  const [maplibre, health] = await Promise.all([loadMapLibre(), getHealth().catch(() => null)])
  const map = new maplibre.Map({
    container,
    style: health?.map_style_url || 'https://tiles.openfreemap.org/styles/liberty',
    bounds,
    interactive: false,
    attributionControl: false,
    fadeDuration: 0,
    // The preload (waitIdle below) fills the cache for the whole flight;
    // the default size would evict the first stops before the last ones.
    maxTileCacheSize: 1000,
  })
  map.addControl(new maplibre.AttributionControl({ compact: false }), 'top-left')
  await new Promise<void>((resolve) => map.on('load', () => resolve()))
  addSpotLayers(map)
  return { maplibre, map }
}

/** Resolves once every visible tile is drawn, or after ``ms`` at the latest. */
export function waitIdle(map: MlMap, ms = 5000): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(resolve, ms)
    map.once('idle', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

export function CountUp({ to, ms = 900 }: { to: number; ms?: number }) {
  const [value, setValue] = useState(0)
  useEffect(() => {
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

export function Outro({ c }: { c: PresentCopy }) {
  return (
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
      <p className="present-host">{location.host.replace(/^www\./, '')}</p>
      <p>{c.outroSub}</p>
    </div>
  )
}
