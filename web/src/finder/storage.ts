/**
 * Per-visitor conveniences in localStorage: saved spots and the one-time
 * disclaimer acknowledgement. Never needed for the finder to work - every
 * access is wrapped, because private windows and blocked storage throw.
 */
export interface SavedSpot {
  lat: number
  lon: number
  score: number
  category: string
  savedAt: number
}

const FAVORITES = 'fpv.favorites.v1'
const ACK = 'fpv.disclaimer.v1'

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable - the feature just does not persist */
  }
}

const same = (a: { lat: number; lon: number }, b: { lat: number; lon: number }) =>
  Math.abs(a.lat - b.lat) < 1e-5 && Math.abs(a.lon - b.lon) < 1e-5

export const favorites = {
  list: (): SavedSpot[] => read<SavedSpot[]>(FAVORITES, []),
  has: (spot: { lat: number; lon: number }) => favorites.list().some((f) => same(f, spot)),
  toggle(spot: Omit<SavedSpot, 'savedAt'>): boolean {
    const list = favorites.list()
    const exists = list.some((f) => same(f, spot))
    write(FAVORITES, exists ? list.filter((f) => !same(f, spot)) : [{ ...spot, savedAt: Date.now() }, ...list].slice(0, 50))
    return !exists
  },
}

export const disclaimer = {
  acknowledged: () => read<boolean>(ACK, false),
  acknowledge: () => write(ACK, true),
}
