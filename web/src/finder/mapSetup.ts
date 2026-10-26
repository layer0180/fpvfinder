/**
 * Map construction shared by the finder (MapView) and the video mode
 * (Presentation): loading MapLibre, the worker fix, and the layers for the
 * search area and the rated points.
 */
import type { Map as MlMap, GeoJSONSource, LngLatBoundsLike } from 'maplibre-gl'
import type { Point, ZoneCollection } from './types'
import { BLOCKED_COLOR, SCORE_COLORS } from './spots'

export type MapLibre = typeof import('maplibre-gl')

export const GERMANY: LngLatBoundsLike = [
  [5.9, 47.3],
  [15.0, 55.1],
]

let loading: Promise<MapLibre> | null = null

/** MapLibre, its stylesheet and its worker - loaded once, on first use. */
export function loadMapLibre(): Promise<MapLibre> {
  loading ??= (async () => {
    const [maplibre, worker] = await Promise.all([
      import('maplibre-gl'),
      // MapLibre 6 looks for its worker next to its own module file, which no
      // longer exists once bundled. Ship the worker as an asset (it has no
      // imports of its own) and tell MapLibre where it is.
      import('maplibre-gl/dist/maplibre-gl-worker.mjs?url'),
      import('maplibre-gl/dist/maplibre-gl.css'),
    ])
    maplibre.setWorkerUrl(new URL(worker.default, location.href).href)
    return maplibre
  })()
  return loading
}

export function circlePolygon(lat: number, lon: number, radiusKm: number) {
  const coords: [number, number][] = []
  const dLat = radiusKm / 111.32
  const dLon = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180))
  for (let i = 0; i <= 96; i++) {
    const a = (i / 96) * 2 * Math.PI
    coords.push([lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)])
  }
  return { type: 'Feature' as const, properties: {}, geometry: { type: 'Polygon' as const, coordinates: [coords] } }
}

export function radiusBounds(lat: number, lon: number, radiusKm: number): LngLatBoundsLike {
  const dLat = radiusKm / 111.32
  const dLon = radiusKm / (111.32 * Math.cos((lat * Math.PI) / 180))
  return [
    [lon - dLon, lat - dLat],
    [lon + dLon, lat + dLat],
  ]
}

export function pointsGeoJSON(points: Point[]) {
  return {
    type: 'FeatureCollection' as const,
    features: points.map((p) => ({
      type: 'Feature' as const,
      id: p.id,
      properties: { id: p.id, score: p.score, blocked: p.blocked ? 1 : 0 },
      geometry: { type: 'Point' as const, coordinates: [p.lon, p.lat] },
    })),
  }
}

/** Adds the search-area and rated-point layers to a loaded map. */
export function addSpotLayers(m: MlMap): void {
  m.addSource('radius', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  m.addSource('points', { type: 'geojson', data: pointsGeoJSON([]) })
  m.addLayer({
    id: 'radius-fill',
    type: 'fill',
    source: 'radius',
    paint: { 'fill-color': '#e8620c', 'fill-opacity': 0.04 },
  })
  m.addLayer({
    id: 'radius-line',
    type: 'line',
    source: 'radius',
    paint: { 'line-color': '#e8620c', 'line-width': 2, 'line-dasharray': [2, 2] },
  })
  m.addLayer({
    id: 'points',
    type: 'circle',
    source: 'points',
    paint: {
      'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2.5, 13, 5, 16, 9],
      'circle-color': [
        'case',
        ['==', ['get', 'blocked'], 1],
        BLOCKED_COLOR,
        ['step', ['get', 'score'], SCORE_COLORS[0], 0.2, SCORE_COLORS[1], 0.4, SCORE_COLORS[2], 0.6, SCORE_COLORS[3], 0.8, SCORE_COLORS[4]],
      ],
      'circle-opacity': ['case', ['==', ['get', 'blocked'], 1], 0.35, 0.8],
      'circle-stroke-width': 0.5,
      'circle-stroke-color': '#11151a',
    },
  })
}

/**
 * Operator-maintained no-fly zones. Points with a ``buffer_m`` are circles;
 * they are turned into polygons here, so one fill layer draws everything.
 */
export function zonesGeoJSON(zones: ZoneCollection) {
  return {
    type: 'FeatureCollection' as const,
    features: zones.features.flatMap((f) => {
      const props = { name: f.properties.name ?? '', severity: f.properties.severity ?? 'warn' }
      if (f.geometry.type === 'Point') {
        const [lon, lat] = f.geometry.coordinates as [number, number]
        const radius = (f.properties.buffer_m ?? 0) / 1000
        return radius > 0 ? [{ ...circlePolygon(lat, lon, radius), properties: props }] : []
      }
      return [{ type: 'Feature' as const, properties: props, geometry: f.geometry }]
    }),
  }
}

export function addZoneLayers(m: MlMap, zones: ZoneCollection): void {
  m.addSource('zones', { type: 'geojson', data: zonesGeoJSON(zones) as never })
  const colour = ['case', ['==', ['get', 'severity'], 'block'], '#d92d20', '#f79009'] as never
  // Below the rated points, so a blocked point stays clickable.
  m.addLayer({ id: 'zones-fill', type: 'fill', source: 'zones', paint: { 'fill-color': colour, 'fill-opacity': 0.15 } }, 'points')
  m.addLayer({ id: 'zones-line', type: 'line', source: 'zones', paint: { 'line-color': colour, 'line-width': 2 } }, 'points')
}

export function setArea(m: MlMap, lat: number, lon: number, radiusKm: number): void {
  ;(m.getSource('radius') as GeoJSONSource).setData(circlePolygon(lat, lon, radiusKm))
}

export function setPoints(m: MlMap, points: Point[]): void {
  ;(m.getSource('points') as GeoJSONSource).setData(pointsGeoJSON(points))
}
