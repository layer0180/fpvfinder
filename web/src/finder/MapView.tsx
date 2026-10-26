import { useEffect, useRef, useState } from 'react'
import type { Map as MlMap, Marker } from 'maplibre-gl'
import type { Point, ZoneCollection } from './types'
import { percent } from './spots'
import type { UiStrings } from './i18n'
import { GERMANY, addSpotLayers, addZoneLayers, loadMapLibre, radiusBounds, setArea, setPoints, type MapLibre } from './mapSetup'

interface Props {
  styleUrl: string
  center: { lat: number; lon: number } | null
  radiusKm: number
  points: Point[]
  topSpots: Point[]
  selected: Point | null
  onSelect: (point: Point) => void
  /** Space covered by the panel, so fitBounds keeps the area visible beside or above it. */
  padding: { top: number; right: number; bottom: number; left: number }
  /** Operator no-fly zones; null when the instance has none. */
  zones: ZoneCollection | null
  s: UiStrings
}

export default function MapView({ styleUrl, center, radiusKm, points, topSpots, selected, onSelect, padding, zones, s }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MlMap | null>(null)
  const markers = useRef<Marker[]>([])
  const lib = useRef<MapLibre | null>(null)
  const pointsById = useRef(new Map<number, Point>())
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const paddingRef = useRef(padding)
  paddingRef.current = padding
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')

  // --- create the map once ------------------------------------------------
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const maplibre = await loadMapLibre()
        if (cancelled || !container.current) return
        lib.current = maplibre
        const m = new maplibre.Map({
          container: container.current,
          style: styleUrl,
          bounds: GERMANY,
          // Added below at the top: at the bottom the panel would cover it.
          attributionControl: false,
          dragRotate: false,
          pitchWithRotate: false,
        })
        m.touchZoomRotate.disableRotation()
        m.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right')
        // Not compact: the compact form folds into an (i) button, and the ODbL
        // credit is meant to be visible, not one tap away.
        m.addControl(new maplibre.AttributionControl({ compact: false }), 'top-left')
        m.on('error', (event) => {
          // A failing tile is noise; a failing WebGL context is not.
          if (String(event.error?.message ?? '').toLowerCase().includes('webgl')) setState('failed')
        })
        m.on('load', () => {
          addSpotLayers(m)
          m.on('click', 'points', (event) => {
            const id = event.features?.[0]?.properties?.id
            const point = pointsById.current.get(Number(id))
            if (point) onSelectRef.current(point)
          })
          m.on('mouseenter', 'points', () => (m.getCanvas().style.cursor = 'pointer'))
          m.on('mouseleave', 'points', () => (m.getCanvas().style.cursor = ''))
          map.current = m
          // The constructor's bounds ignore the panel; refit so all of
          // Germany is visible above the sheet / beside the column.
          m.fitBounds(GERMANY, { padding: paddingRef.current, duration: 0 })
          setState('ready')
        })
      } catch {
        if (!cancelled) setState('failed')
      }
    })()
    return () => {
      cancelled = true
      map.current?.remove()
      map.current = null
    }
  }, [styleUrl])

  // --- operator no-fly zones -----------------------------------------------
  useEffect(() => {
    const m = map.current
    const maplibre = lib.current
    if (state !== 'ready' || !m || !maplibre || !zones?.features.length || m.getSource('zones')) return
    addZoneLayers(m, zones)
    m.on('click', 'zones-fill', (event) => {
      const name = event.features?.[0]?.properties?.name
      if (name) new maplibre.Popup({ closeButton: false }).setLngLat(event.lngLat).setText(`${s.zone}: ${name}`).addTo(m)
    })
  }, [state, zones, s])

  // --- search area ---------------------------------------------------------
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m || !center) return
    setArea(m, center.lat, center.lon, radiusKm)
    const pad = paddingRef.current
    m.fitBounds(radiusBounds(center.lat, center.lon, radiusKm), {
      padding: { top: pad.top + 24, right: pad.right + 24, bottom: pad.bottom + 24, left: pad.left + 24 },
      duration: 900,
    })
  }, [state, center?.lat, center?.lon, radiusKm]) // eslint-disable-line react-hooks/exhaustive-deps

  // --- all rated points ------------------------------------------------------
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m) return
    pointsById.current = new Map(points.map((p) => [p.id, p]))
    setPoints(m, points)
  }, [state, points])

  // --- numbered top spots ----------------------------------------------------
  useEffect(() => {
    const m = map.current
    const maplibre = lib.current
    if (state !== 'ready' || !m || !maplibre) return
    markers.current.forEach((marker) => marker.remove())
    markers.current = topSpots.map((spot, index) => {
      const el = document.createElement('button')
      el.type = 'button'
      el.className = 'spot-pin'
      el.dataset.step = String(Math.min(4, Math.floor(spot.score * 5)))
      el.textContent = String(index + 1)
      el.setAttribute('aria-label', `${s.rank} ${index + 1}, ${percent(spot.score)} ${s.scoreLabel}`)
      el.addEventListener('click', (event) => {
        event.stopPropagation()
        onSelectRef.current(spot)
      })
      return new maplibre.Marker({ element: el }).setLngLat([spot.lon, spot.lat]).addTo(m)
    })
  }, [state, topSpots, s])

  // --- selection -------------------------------------------------------------
  useEffect(() => {
    const m = map.current
    if (state !== 'ready' || !m) return
    markers.current.forEach((marker, i) => {
      marker.getElement().classList.toggle('is-selected', topSpots[i]?.id === selected?.id)
    })
    if (selected) {
      m.flyTo({
        center: [selected.lon, selected.lat],
        zoom: Math.max(m.getZoom(), 14.5),
        padding: paddingRef.current,
        duration: 1100,
        essential: false,
      })
    }
  }, [state, selected?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="map-wrap">
      <div ref={container} className="map" />
      {state === 'loading' && <p className="map-status">{s.mapLoading}</p>}
      {state === 'failed' && <p className="map-status map-failed">{s.mapFailed}</p>}
    </div>
  )
}
