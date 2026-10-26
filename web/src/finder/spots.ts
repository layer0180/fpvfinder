import type { Point } from './types'

/**
 * Score -> one of five steps of the viridis-like ramp in global.css. Steps,
 * not a gradient, so the same spot never looks "a bit greener" on one screen
 * than another, and the legend can name each band.
 */
export function scoreStep(score: number, blocked = false): string {
  if (blocked) return 'var(--score-blocked)'
  const step = Math.min(4, Math.max(0, Math.floor(score * 5)))
  return `var(--score-${step})`
}

/** Concrete colours for MapLibre, which cannot read CSS variables. */
export const SCORE_COLORS = ['#45307f', '#2f62a8', '#1d8f87', '#4cab4a', '#b5d334']
export const BLOCKED_COLOR = '#8a929c'

export const percent = (score: number) => Math.round(score * 100)

/** Metres between two coordinates (equirectangular - plenty at this scale). */
export function distanceM(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const k = Math.PI / 180
  const x = (b.lon - a.lon) * k * Math.cos(((a.lat + b.lat) / 2) * k)
  const y = (b.lat - a.lat) * k
  return Math.sqrt(x * x + y * y) * 6_371_000
}

/**
 * The spots worth listing: best first, never blocked, never with a red
 * warning (on water, a power line 50 m away ...), and at least
 * ``minSeparationM`` apart - otherwise the top ten are ten grid points in the
 * same meadow, which is one spot, not ten. Such points stay on the map.
 */
/**
 * Operating sites: empty and open, so they score well, but fenced, private
 * and often dangerous - not something to recommend. They stay on the map.
 */
const NOT_LISTED = new Set(['landfill', 'quarry', 'construction', 'military', 'industrial', 'railway_area', 'farmyard'])

/** Warning codes for nature reserves, national parks and Natura 2000 sites (backend: PROTECTED_CODES). */
export const STRICT_PROTECTED = new Set([
  'protected_strict',
  'protected_national_park',
  'protected_bird',
  'protected_ffh',
  'protected_natura2000',
])

export function pickTopSpots(
  points: Point[],
  count = 10,
  minSeparationM = 450,
  minScore = 0.5,
  includeProtected = false,
): Point[] {
  const picked: Point[] = []
  // With "include protected areas" on, their red warning is the one danger
  // a listed spot may carry - it stays visible on the spot.
  const disqualifies = (w: Point['warnings'][number]) =>
    w.level === 'danger' && !(includeProtected && STRICT_PROTECTED.has(w.code))
  const sorted = points
    .filter(
      (p) =>
        !p.blocked &&
        p.score >= minScore &&
        !NOT_LISTED.has(p.category) &&
        !p.warnings.some(disqualifies),
    )
    .sort((a, b) => b.score - a.score)
  for (const p of sorted) {
    if (picked.every((q) => distanceM(p, q) >= minSeparationM)) picked.push(p)
    if (picked.length >= count) break
  }
  return picked
}
