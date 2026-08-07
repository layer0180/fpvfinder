import { useEffect, useMemo, useState } from 'react'
import L from 'leaflet'
import 'leaflet.heat'
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet'
import { markerRadius, scoreColor } from '../lib/score.js'

/** Recentres the map when the starting point or radius changes. */
function Recenter({ center, radiusKm }) {
  const map = useMap()
  useEffect(() => {
    if (!center) return
    const bounds = L.latLng(center.lat, center.lon).toBounds(radiusKm * 2000 * 1.1)
    map.fitBounds(bounds, { padding: [20, 20] })
  }, [center?.lat, center?.lon, radiusKm]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/** Clicking the map sets the starting point (only in "pick on map" mode). */
function ClickHandler({ armed, onPick, onZoom }) {
  const map = useMapEvents({
    click(event) {
      if (armed) onPick({ lat: event.latlng.lat, lon: event.latlng.lng })
    },
    zoomend() {
      onZoom(map.getZoom())
    },
  })
  useEffect(() => {
    const container = map.getContainer()
    container.style.cursor = armed ? 'crosshair' : ''
  }, [armed, map])
  return null
}

/**
 * Heatmap rendering via leaflet.heat.
 * Useful when there are many points - it shows area trends rather than
 * individual spots.
 */
function HeatLayer({ points, visible }) {
  const map = useMap()
  useEffect(() => {
    if (!visible || !points.length) return undefined
    const data = points.map((p) => [p.lat, p.lon, Math.max(p.score, 0.02)])
    const layer = L.heatLayer(data, {
      radius: 26,
      blur: 20,
      maxZoom: 15,
      minOpacity: 0.25,
      // Same logic as the markers: red = poor, green = ideal.
      gradient: { 0.0: '#b91c1c', 0.35: '#dc2626', 0.55: '#f59e0b', 0.75: '#84cc16', 1.0: '#16a34a' },
    })
    layer.addTo(map)
    return () => {
      map.removeLayer(layer)
    }
  }, [map, points, visible])
  return null
}

const centerIcon = L.divIcon({
  className: 'center-pin',
  html: '<div class="center-pin-inner">◎</div>',
  iconSize: [26, 26],
  iconAnchor: [13, 13],
})

export default function MapView({
  center,
  radiusKm,
  points,
  selectedId,
  onSelect,
  onPickCenter,
  pickMode,
  showStrava,
  stravaTileUrl,
  stravaMaxNativeZoom = 12,
  showAirspace,
  airspace,
  viewMode,
}) {
  const [zoom, setZoom] = useState(13)

  const radius = useMemo(() => markerRadius(points.length, zoom), [points.length, zoom])

  // Draw the selected point last so it is not hidden behind others.
  const ordered = useMemo(() => {
    if (selectedId == null) return points
    return [...points.filter((p) => p.id !== selectedId), ...points.filter((p) => p.id === selectedId)]
  }, [points, selectedId])

  const airspaceStyle = (feature) => {
    const severity = feature?.properties?.severity ?? 'warn'
    const color = severity === 'block' ? '#ef4444' : severity === 'warn' ? '#f59e0b' : '#38bdf8'
    return { color, weight: 2, fillColor: color, fillOpacity: 0.12, dashArray: '6 4' }
  }

  return (
    <MapContainer
      center={[center.lat, center.lon]}
      zoom={13}
      className="map"
      preferCanvas
      scrollWheelZoom
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        maxZoom={19}
      />

      {/* Strava heatmap, fetched DIRECTLY from Strava by the browser - it does
          not pass through our server. Tile bandwidth is by far the largest
          traffic item (measured: ~890 KiB in a short panning session, and it
          grows without bound the more you pan), so proxying it would put the
          whole of it on the host for no benefit.

          No CORS header is needed for this: Leaflet renders tiles as plain
          <img> elements. (Reading their pixels would need CORS, and Strava
          sends none - which is why the score sampling still happens on the
          server.)

          maxNativeZoom is essential: above zoom 12 Strava serves nothing
          without a login. Without it Leaflet would request z13+ and receive
          403s, leaving the layer invisible. This way the z12 tiles get
          upscaled instead. */}
      {showStrava && stravaTileUrl && (
        <TileLayer
          url={stravaTileUrl}
          opacity={0.75}
          maxNativeZoom={stravaMaxNativeZoom}
          maxZoom={19}
          attribution='Heatmap &copy; <a href="https://www.strava.com/heatmap">Strava</a>'
        />
      )}

      <Recenter center={center} radiusKm={radiusKm} />
      <ClickHandler armed={pickMode} onPick={onPickCenter} onZoom={setZoom} />

      <Circle
        center={[center.lat, center.lon]}
        radius={radiusKm * 1000}
        pathOptions={{ color: '#38bdf8', weight: 1.5, fillOpacity: 0.04, dashArray: '5 6' }}
      />
      <Marker position={[center.lat, center.lon]} icon={centerIcon} />

      {showAirspace && airspace?.features?.length > 0 && (
        <GeoJSON
          data={airspace}
          style={airspaceStyle}
          // Point zones must be drawn as their actual buffered circle, because
          // that is the area the backend blocks - a pin would understate it.
          //
          // This also avoids a bug: without pointToLayer, Leaflet builds a
          // default Marker, whose icon-path heuristic reads the CSS rule
          // .leaflet-default-icon-path and strips "marker-icon.png" off it. In
          // a production build Vite inlines that image as a base64 data URI, so
          // there is nothing to strip and Leaflet ends up requesting
          // /marker-icon.png from the site root -> 404.
          //
          // (LineString zones are drawn as their centre line; the backend still
          // applies buffer_m to them.)
          pointToLayer={(feature, latlng) => {
            const style = airspaceStyle(feature)
            const bufferM = Number(feature?.properties?.buffer_m ?? 0)
            return bufferM > 0
              ? L.circle(latlng, { ...style, radius: bufferM })
              : L.circleMarker(latlng, { ...style, radius: 7 })
          }}
          onEachFeature={(feature, layer) => {
            const props = feature.properties || {}
            layer.bindTooltip(
              `<strong>${props.name ?? 'Zone'}</strong><br/>${props.kind ?? ''} · ${props.severity ?? ''}` +
                (props.note ? `<br/><em>${props.note}</em>` : ''),
            )
          }}
        />
      )}

      <HeatLayer points={points} visible={viewMode === 'heat'} />

      {viewMode === 'markers' &&
        ordered.map((point) => {
          const isSelected = point.id === selectedId
          return (
            <CircleMarker
              key={point.id}
              center={[point.lat, point.lon]}
              radius={isSelected ? radius + 4 : radius}
              pathOptions={{
                color: isSelected ? '#ffffff' : 'rgba(0,0,0,0.35)',
                weight: isSelected ? 2.5 : 1,
                fillColor: scoreColor(point.score, point.blocked),
                fillOpacity: point.blocked ? 0.5 : 0.9,
              }}
              eventHandlers={{ click: () => onSelect(point) }}
            >
              <Tooltip direction="top" offset={[0, -4]}>
                <strong>{Math.round(point.score * 100)} / 100</strong> · {point.category_label}
              </Tooltip>
            </CircleMarker>
          )
        })}
    </MapContainer>
  )
}
