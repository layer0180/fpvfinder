import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Starting point, radius, grid spacing and time profile.
 * The address lookup is debounced because Nominatim allows at most one
 * request per second.
 */
export default function SearchPanel({
  center,
  onCenterChange,
  params,
  onParamsChange,
  timeProfiles,
  onSearch,
  onCancel,
  busy,
  progress,
  pickMode,
  onTogglePickMode,
  stravaAvailable,
  stravaMaxZoom = 12,
  stravaHiRes = false,
  // Instance limits, so the sliders cannot ask for something the server
  // will only clamp again.
  maxRadiusKm = 20,
  minSpacingM = 50,
  maxResultsLimit = 2000,
}) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searching, setSearching] = useState(false)
  const [geoError, setGeoError] = useState('')
  const debounceRef = useRef(null)

  useEffect(() => {
    if (query.trim().length < 3) {
      setResults([])
      return undefined
    }
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(async () => {
      setSearching(true)
      try {
        setResults(await api.geocode(query))
      } catch (error) {
        setGeoError(error.message)
      } finally {
        setSearching(false)
      }
    }, 700)
    return () => clearTimeout(debounceRef.current)
  }, [query])

  const useMyPosition = () => {
    setGeoError('')
    if (!navigator.geolocation) {
      setGeoError('This browser does not support location lookup.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        onCenterChange({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          label: 'Current position',
        }),
      (error) => setGeoError(`Location unavailable: ${error.message}`),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const update = (key, value) => onParamsChange({ ...params, [key]: value })

  return (
    <section className="panel">
      <h2>Location &amp; search</h2>

      <label className="field">
        <span>Address or place</span>
        <input
          type="text"
          value={query}
          placeholder="e.g. Bad Urach"
          onChange={(event) => setQuery(event.target.value)}
        />
      </label>

      {searching && <p className="hint">Searching …</p>}
      {results.length > 0 && (
        <ul className="geocode-results">
          {results.map((result) => (
            <li key={`${result.lat},${result.lon}`}>
              <button
                type="button"
                onClick={() => {
                  onCenterChange({ lat: result.lat, lon: result.lon, label: result.label })
                  setResults([])
                  setQuery('')
                }}
              >
                {result.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="button-row">
        <button type="button" className="secondary" onClick={useMyPosition}>
          📍 Current position
        </button>
        <button
          type="button"
          className={pickMode ? 'secondary active' : 'secondary'}
          onClick={onTogglePickMode}
          title="Then click on the map"
        >
          🖈 Pick on map
        </button>
      </div>
      {geoError && <p className="error">{geoError}</p>}

      <p className="coords">
        {center.label && <span className="coords-label">{center.label}</span>}
        {center.lat.toFixed(5)}, {center.lon.toFixed(5)}
      </p>

      <label className="field">
        <span>
          Search radius <strong>{params.radiusKm} km</strong>
        </span>
        <input
          type="range"
          min="1"
          max={maxRadiusKm}
          step="0.5"
          value={Math.min(params.radiusKm, maxRadiusKm)}
          onChange={(event) => update('radiusKm', Number(event.target.value))}
        />
        {maxRadiusKm < 20 && (
          <small className="hint">
            This instance caps the radius at {maxRadiusKm} km — memory use grows with the square of
            the radius. Self-host to raise it.
          </small>
        )}
      </label>

      <label className="field">
        <span>
          Grid spacing <strong>{params.spacingM} m</strong>
        </span>
        <input
          type="range"
          min={minSpacingM}
          max="400"
          step="25"
          value={Math.max(params.spacingM, minSpacingM)}
          onChange={(event) => update('spacingM', Number(event.target.value))}
        />
        <small className="hint">
          Finer is more precise but slower. For a large radius the backend widens this automatically.
        </small>
      </label>

      <label className="field">
        <span>Time profile</span>
        <select
          value={params.timeProfile}
          onChange={(event) => update('timeProfile', event.target.value)}
        >
          {Object.entries(timeProfiles ?? {}).map(([key, profile]) => (
            <option key={key} value={key}>
              {profile.label ?? key}
            </option>
          ))}
        </select>
        <small className="hint">
          Controls how heavily paths, attractions and Strava tracks count against a location.
        </small>
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={params.useStrava}
          disabled={!stravaAvailable}
          onChange={(event) => update('useStrava', event.target.checked)}
        />
        <span>
          Include the Strava heatmap
          {stravaAvailable && !stravaHiRes && (
            <em className="hint"> (public data up to zoom {stravaMaxZoom}, ~25 m/pixel)</em>
          )}
          {!stravaAvailable && <em className="hint"> (disabled in the config)</em>}
        </span>
      </label>

      <label className="field">
        <span>
          Maximum results <strong>{params.maxResults}</strong>
        </span>
        <input
          type="range"
          min="50"
          max={maxResultsLimit}
          step="50"
          value={Math.min(params.maxResults, maxResultsLimit)}
          onChange={(event) => update('maxResults', Number(event.target.value))}
        />
      </label>

      {busy ? (
        <>
          <div className="progress">
            <div className="progress-bar" style={{ width: `${(progress?.progress ?? 0) * 100}%` }} />
          </div>
          <p className="hint">{progress?.message ?? 'Working …'}</p>
          <button type="button" className="danger" onClick={onCancel}>
            Cancel
          </button>
        </>
      ) : (
        <button type="button" className="primary" onClick={onSearch}>
          Find locations
        </button>
      )}
    </section>
  )
}
