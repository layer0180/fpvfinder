import type { Health, JobStatus, Place, SearchParams, SearchResult, ZoneCollection } from './types'

/** An API failure with a code the UI can translate (see shared/i18n errors). */
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message)
  }
}

async function json<T>(response: Response): Promise<T> {
  if (response.ok) return response.json() as Promise<T>
  let code = 'generic'
  let message = `HTTP ${response.status}`
  try {
    const body = await response.json()
    const detail = body.detail
    code = body.code ?? detail?.code ?? code
    message = typeof detail === 'string' ? detail : (detail?.message ?? message)
  } catch {
    /* not JSON - keep the generic code */
  }
  if (response.status === 429) code = 'rate_limited'
  if (response.status === 503 && code === 'generic') code = 'busy'
  throw new ApiError(code, message)
}

export const getHealth = () => fetch('/api/health').then((r) => json<Health>(r))

export const getAirspace = () => fetch('/api/airspace').then((r) => json<ZoneCollection>(r))

/** ``suggest`` for type-ahead: answered by Photon only (Nominatim forbids autocomplete). */
export const geocode = (q: string, lang: string, signal?: AbortSignal, suggest = false) =>
  fetch(`/api/geocode?${new URLSearchParams({ q, lang, limit: '5', ...(suggest && { suggest: 'true' }) })}`, {
    signal,
  }).then((r) => json<Place[]>(r))

export const reverse = (lat: number, lon: number, lang: string) =>
  fetch(`/api/reverse?${new URLSearchParams({ lat: String(lat), lon: String(lon), lang })}`)
    .then((r) => json<{ label: string }>(r))
    .then((r) => r.label)
    .catch(() => '')

export const createShare = (resultId: string, pointId: number) =>
  fetch('/api/share', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ result_id: resultId, point_id: pointId }),
  }).then((r) => json<{ id: string }>(r))

const POLL_MS = 600

/**
 * Starts a search job and polls it to completion. A cached result comes back
 * finished on the first response, so popular places need no polling at all.
 */
export async function runSearch(
  params: SearchParams,
  onProgress: (status: JobStatus) => void,
  signal: AbortSignal,
): Promise<SearchResult> {
  const body = {
    lat: params.lat,
    lon: params.lon,
    radius_km: params.radiusKm,
    spacing_m: params.spacingM,
    time_profile: params.timeProfile,
  }
  const weights = {
    ...params.weights,
    ...(params.includeProtected && { hard_rules: { block_in_protected_area: false } }),
    ...(params.solitudeShare !== undefined && {
      total: { solitude_weight: params.solitudeShare, flyability_weight: 1 - params.solitudeShare },
    }),
  }
  const payload = Object.keys(weights).length ? { ...body, weights } : body
  let status = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  }).then((r) => json<JobStatus>(r))

  try {
    while (status.status === 'pending' || status.status === 'running') {
      onProgress(status)
      await new Promise((resolve) => setTimeout(resolve, POLL_MS))
      if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
      status = await fetch(`/api/search/${status.job_id}`, { signal }).then((r) => json<JobStatus>(r))
    }
  } catch (error) {
    // Free the server slot if the visitor gave up.
    if ((error as Error).name === 'AbortError') fetch(`/api/search/${status.job_id}`, { method: 'DELETE' })
    throw error
  }
  if (status.status === 'error' || !status.result) {
    throw new ApiError(status.error_code ?? 'generic', status.error ?? 'Search failed')
  }
  return status.result
}
