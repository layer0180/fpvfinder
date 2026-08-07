/**
 * Thin wrapper around the backend API.
 * All paths are relative - the Vite dev server proxies /api to the backend.
 */

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      /* response was not JSON - the status code will do */
    }
    throw new Error(detail)
  }
  return response.json()
}

export const api = {
  health: () => request('/api/health'),

  config: () => request('/api/config'),

  saveConfig: (config, merge = true) =>
    request('/api/config', { method: 'PUT', body: JSON.stringify({ config, merge }) }),

  resetConfig: () => request('/api/config/reset', { method: 'POST' }),

  disclaimer: () => request('/api/disclaimer'),

  geocode: (query) => request(`/api/geocode?q=${encodeURIComponent(query)}&limit=6`),

  airspace: () => request('/api/airspace'),

  legalIndex: () => request('/api/legal'),

  legalPage: (name) => request(`/api/legal/${name}`),

  startSearch: (payload) =>
    request('/api/search', { method: 'POST', body: JSON.stringify(payload) }),

  searchStatus: (jobId) => request(`/api/search/${jobId}`),

  cancelSearch: (jobId) => request(`/api/search/${jobId}`, { method: 'DELETE' }),
}

/**
 * Starts a search and polls until the result is ready.
 * @param payload    search parameters
 * @param onProgress callback ({progress, message}) for the progress indicator
 * @param signal     AbortSignal for cancellation
 */
export async function runSearch(payload, onProgress, signal) {
  const job = await api.startSearch(payload)
  const jobId = job.job_id

  // Short poll interval on purpose: the phases change quickly.
  const POLL_MS = 600

  while (true) {
    if (signal?.aborted) {
      api.cancelSearch(jobId).catch(() => {})
      throw new DOMException('Search cancelled', 'AbortError')
    }
    const status = await api.searchStatus(jobId)
    onProgress?.(status)

    if (status.status === 'done') return status.result
    if (status.status === 'error') throw new Error(status.error || 'Unknown error')

    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
  }
}
