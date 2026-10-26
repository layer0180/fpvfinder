/** Shapes of the backend API (backend/app/models.py). */

export type Level = 'danger' | 'warning' | 'info'

export interface Coded {
  code: string
  params: Record<string, string | number>
}

export interface Warning extends Coded {
  level: Level
  text: string
}

export interface Point {
  id: number
  lat: number
  lon: number
  score: number
  solitude: number
  flyability: number
  blocked: boolean
  category: string
  area_name: string
  distances: Record<string, number>
  components: { solitude: Record<string, number>; flyability: Record<string, number> }
  warnings: Warning[]
  reasons: Coded[]
}

export interface SearchResult {
  center: { lat: number; lon: number }
  radius_km: number
  time_profile: string
  points: Point[]
  notes: string[]
  result_id: string
  /** Client side: whether this search included protected areas (pickTopSpots). */
  includeProtected?: boolean
  stats: {
    grid_points: number
    spacing_m: number
    duration_s: number
    score_max: number
    blocked_share: number
    tiles_fetched: number
  }
}

export interface JobStatus {
  job_id: string
  status: 'pending' | 'running' | 'done' | 'error'
  progress: number
  message: string
  error: string | null
  error_code: string | null
  result: SearchResult | null
}

export interface Place {
  label: string
  lat: number
  lon: number
  type?: string
}

export interface Health {
  map_style_url: string
  limits: { max_radius_km: number; min_spacing_m: number; max_results: number }
  donate_url?: string
  time_profiles: string[]
  /** Operator-maintained no-fly zones (backend data/airspace.geojson). */
  airspace_enabled?: boolean
}

export interface ZoneCollection {
  type: 'FeatureCollection'
  features: {
    type: 'Feature'
    properties: { name?: string; severity?: string; buffer_m?: number }
    geometry: { type: string; coordinates: unknown }
  }[]
}

export interface SearchParams {
  lat: number
  lon: number
  radiusKm: number
  /** 'auto' resolves to the profile matching the current day and hour. */
  timeProfile: string
  spacingM: number
  /** Share of "few people" in the total, 0..1; undefined = server default. */
  solitudeShare?: number
  /** Per-request weight overrides in the scoring config's shape (Tuning.tsx). */
  weights?: Record<string, unknown>
  /**
   * Do not block points in nature reserves, national parks and Natura 2000
   * sites. They still carry a red warning naming the kind of area.
   */
  includeProtected?: boolean
}
