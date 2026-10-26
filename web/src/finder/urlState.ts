/**
 * The finder's state lives in the URL, so every view can be shared, bookmarked
 * and survives a reload:
 *
 *   /app?lat=48.4&lon=9.4&r=5&t=auto&spot=48.4123,9.4456
 *
 * Entry links from the static pages use ?q=<place> or ?locate=1 instead; those
 * are resolved once and then replaced by coordinates.
 */
export interface UrlState {
  q?: string
  locate?: boolean
  lat?: number
  lon?: number
  r?: number
  t?: string
  spacing?: number
  spot?: { lat: number; lon: number }
  present?: boolean
  /** Solitude share in percent (0-100), see SearchParams.solitudeShare. */
  balance?: number
  /** ns=1: include nature and bird protection areas, see SearchParams.includeProtected. */
  protectedAreas?: boolean
}

const num = (v: string | null) => (v !== null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : undefined)

export function readUrl(search = location.search): UrlState {
  const p = new URLSearchParams(search)
  const spot = p.get('spot')?.split(',').map(Number)
  return {
    q: p.get('q')?.trim() || undefined,
    locate: p.get('locate') === '1',
    lat: num(p.get('lat')),
    lon: num(p.get('lon')),
    r: num(p.get('r')),
    t: p.get('t') ?? undefined,
    spacing: num(p.get('g')),
    spot: spot && spot.length === 2 && spot.every(Number.isFinite) ? { lat: spot[0], lon: spot[1] } : undefined,
    present: p.get('present') === '1',
    balance: num(p.get('b')),
    protectedAreas: p.get('ns') === '1',
  }
}

/** Replaces the finder's own parameters and keeps everything else (utm_* ...). */
export function writeUrl(state: UrlState, mode: 'push' | 'replace' = 'replace'): void {
  const p = new URLSearchParams(location.search)
  for (const key of ['q', 'locate', 'lat', 'lon', 'r', 't', 'g', 'b', 'ns', 'spot']) p.delete(key)
  if (state.lat !== undefined && state.lon !== undefined) {
    p.set('lat', state.lat.toFixed(4))
    p.set('lon', state.lon.toFixed(4))
  }
  if (state.r !== undefined) p.set('r', String(state.r))
  if (state.t && state.t !== 'auto') p.set('t', state.t)
  if (state.spacing !== undefined) p.set('g', String(state.spacing))
  if (state.balance !== undefined) p.set('b', String(state.balance))
  if (state.protectedAreas) p.set('ns', '1')
  if (state.spot) p.set('spot', `${state.spot.lat.toFixed(5)},${state.spot.lon.toFixed(5)}`)
  // Keep "spot=48.41,9.44" readable in shared links instead of "%2C".
  const query = p.toString().replace(/%2C/gi, ',')
  const url = `${location.pathname}${query ? `?${query}` : ''}`
  if (url !== location.pathname + location.search) history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url)
}
