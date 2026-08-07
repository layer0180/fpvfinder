/** Presentation helpers: colours, formatting, filter logic. */

/** Distances at or above this count as "not nearby" (backend sentinel value). */
export const FAR_AWAY_M = 45000

/**
 * Score -> colour (red = unsuitable, yellow = mediocre, green = ideal).
 * Deliberately via HSL so the gradient is perceived as even.
 */
export function scoreColor(score, blocked = false) {
  if (blocked) return '#6b7280'
  const clamped = Math.max(0, Math.min(1, score))
  const hue = clamped * 125 // 0 = red, 125 = green
  const lightness = 38 + clamped * 14
  return `hsl(${hue.toFixed(0)}, 78%, ${lightness.toFixed(0)}%)`
}

/** Stronger variant for bars and accents. */
export function scoreColorSolid(score) {
  const clamped = Math.max(0, Math.min(1, score))
  return `hsl(${(clamped * 125).toFixed(0)}, 70%, 46%)`
}

export function formatDistance(meters) {
  if (meters == null) return '–'
  if (meters >= FAR_AWAY_M) return '–'
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`
  return `${Math.round(meters)} m`
}

export function formatPercent(value) {
  return `${Math.round((value ?? 0) * 100)} %`
}

/** Marker radius: smaller when there are many points, so nothing smears together. */
export function markerRadius(pointCount, zoom) {
  const base = pointCount > 400 ? 5 : pointCount > 150 ? 6.5 : 8
  const zoomAdjust = Math.max(-2, Math.min(3, (zoom - 12) * 0.8))
  return Math.max(3, base + zoomAdjust)
}

/**
 * Client-side filtering.
 * Done here rather than in the backend on purpose: this way the sliders take
 * effect instantly, with no need to fetch Overpass data again.
 */
export function filterPoints(points, filters) {
  if (!points) return []
  return points.filter((p) => {
    if (!filters.showBlocked && p.blocked) return false
    if (p.score < filters.minScore) return false
    if (p.distances.building < filters.minBuilding) return false
    if (p.distances.settlement < filters.minSettlement) return false
    if (p.distances.road < filters.minRoad) return false
    if (p.distances.path < filters.minPath) return false
    if (p.distances.strava_route < filters.minStravaDistance) return false
    if (filters.maxStrava < 1 && p.strava > filters.maxStrava) return false
    return true
  })
}

export const DEFAULT_FILTERS = {
  minScore: 0,
  minBuilding: 0,
  minSettlement: 0,
  minRoad: 0,
  minPath: 0,
  minStravaDistance: 0,
  maxStrava: 1,
  showBlocked: false,
}

export const WARNING_ICONS = {
  danger: '⛔',
  warning: '⚠️',
  info: 'ℹ️',
}
