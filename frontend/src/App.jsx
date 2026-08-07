import { useEffect, useMemo, useRef, useState } from 'react'
import { api, runSearch } from './api/client.js'
import DetailPanel from './components/DetailPanel.jsx'
import Disclaimer from './components/Disclaimer.jsx'
import FilterPanel from './components/FilterPanel.jsx'
import Footer from './components/Footer.jsx'
import MapView from './components/MapView.jsx'
import SearchPanel from './components/SearchPanel.jsx'
import WeightsEditor from './components/WeightsEditor.jsx'
import { DEFAULT_FILTERS, filterPoints, scoreColorSolid } from './lib/score.js'

// Fallback starting point until the user picks something else (Swabian Alb).
const INITIAL_CENTER = { lat: 48.548, lon: 9.55, label: '' }

export default function App() {
  const [center, setCenter] = useState(INITIAL_CENTER)
  const [params, setParams] = useState({
    radiusKm: 5,
    spacingM: 150,
    timeProfile: 'weekend_afternoon',
    maxResults: 600,
    useStrava: true,
  })

  const [config, setConfig] = useState(null)
  const [labels, setLabels] = useState(null)
  const [health, setHealth] = useState(null)
  const [disclaimer, setDisclaimer] = useState('')
  const [airspace, setAirspace] = useState(null)

  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')

  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [selected, setSelected] = useState(null)
  const [viewMode, setViewMode] = useState('markers')
  const [pickMode, setPickMode] = useState(false)
  const [showStrava, setShowStrava] = useState(false)
  const [showAirspace, setShowAirspace] = useState(true)
  const [tab, setTab] = useState('search')
  // Narrow screens turn the two side columns into drawers; on desktop the
  // class is inert because the media query does not apply.
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Config override that applies to the next search only.
  const [override, setOverride] = useState(null)
  const abortRef = useRef(null)

  // ---- Load the initial reference data -----------------------------------
  useEffect(() => {
    ;(async () => {
      try {
        const [configResponse, healthResponse, disclaimerResponse, airspaceResponse] = await Promise.all([
          api.config(),
          api.health(),
          api.disclaimer(),
          api.airspace(),
        ])
        setConfig(configResponse.config)
        setLabels(configResponse.labels)
        setHealth(healthResponse)
        setDisclaimer(disclaimerResponse.text)
        setAirspace(airspaceResponse)
        setParams((previous) => ({
          ...previous,
          timeProfile: configResponse.config.default_time_profile ?? previous.timeProfile,
          spacingM: configResponse.config.grid.spacing_m ?? previous.spacingM,
          useStrava: Boolean(healthResponse.strava_enabled),
          // Never start above what this instance will actually run.
          radiusKm: Math.min(
            configResponse.config.search.default_radius_km ?? previous.radiusKm,
            healthResponse.limits?.max_radius_km ?? Infinity,
          ),
          maxResults: Math.min(previous.maxResults, healthResponse.limits?.max_results ?? Infinity),
        }))
        setFilters((previous) => ({
          ...previous,
          showBlocked: !configResponse.config.display.hide_blocked_default,
        }))
      } catch (fetchError) {
        setError(`Backend unreachable: ${fetchError.message}`)
      }
    })()
  }, [])

  // `weightsOverride` is passed explicitly by the weights editor: calling
  // setOverride() and then startSearch() in the same handler would still read
  // the previous state, so the first search after "Apply" would silently use
  // the old weights.
  const startSearch = async (weightsOverride = override) => {
    setSidebarOpen(false)
    setBusy(true)
    setError('')
    setSelected(null)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const payload = {
        lat: center.lat,
        lon: center.lon,
        radius_km: params.radiusKm,
        spacing_m: params.spacingM,
        time_profile: params.timeProfile,
        max_results: params.maxResults,
        use_strava: params.useStrava,
        ...(weightsOverride ? { weights: weightsOverride } : {}),
      }
      const searchResult = await runSearch(payload, setProgress, controller.signal)
      setResult(searchResult)
    } catch (searchError) {
      if (searchError.name !== 'AbortError') setError(searchError.message)
    } finally {
      setBusy(false)
      setProgress(null)
      abortRef.current = null
    }
  }

  const cancelSearch = () => abortRef.current?.abort()

  const visiblePoints = useMemo(() => filterPoints(result?.points, filters), [result, filters])

  // The public heatmap endpoint needs no login.
  const stravaAvailable = Boolean(health?.strava_enabled)
  const stravaHiRes = Boolean(health?.strava_cookies_present)

  // Instance limits. On a shared deployment the server refuses to persist
  // config changes, so the UI hides those buttons instead of offering an
  // action that is guaranteed to fail.
  // Custom no-fly zones are off unless the backend says otherwise.
  const airspaceEnabled = Boolean(health?.airspace_enabled)

  const limits = health?.limits ?? {}
  const configWritable = limits.config_writable !== false

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">🛸</span>
          <div>
            <h1>FPV Flying Spot Finder</h1>
            <p className="subtitle">Quiet spots nearby — OSM · Overpass · Strava heatmap</p>
          </div>
        </div>
        <button
          type="button"
          className="mobile-toggle"
          aria-expanded={sidebarOpen}
          aria-controls="settings-drawer"
          onClick={() => setSidebarOpen((open) => !open)}
        >
          {sidebarOpen ? '✕' : '☰'} Settings
        </button>
        <Disclaimer text={disclaimer} />
      </header>

      <div className="layout">
        <aside id="settings-drawer" className={`sidebar${sidebarOpen ? ' open' : ''}`}>
          <button type="button" className="drawer-close" onClick={() => setSidebarOpen(false)}>
            ✕ Close
          </button>
          <nav className="tabs">
            {[
              ['search', 'Search'],
              ['filter', 'Filters'],
              ['weights', 'Weights'],
            ].map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={tab === key ? 'active' : ''}
                onClick={() => setTab(key)}
              >
                {label}
              </button>
            ))}
          </nav>

          {error && <p className="error panel">{error}</p>}

          {tab === 'search' && (
            <SearchPanel
              center={center}
              onCenterChange={(next) => {
                setCenter(next)
                setPickMode(false)
              }}
              params={params}
              onParamsChange={setParams}
              timeProfiles={config?.time_profiles}
              onSearch={() => startSearch()}
              onCancel={cancelSearch}
              busy={busy}
              progress={progress}
              pickMode={pickMode}
              onTogglePickMode={() => setPickMode(!pickMode)}
              stravaAvailable={stravaAvailable}
              stravaMaxZoom={health?.strava_public_max_zoom ?? 12}
              stravaHiRes={stravaHiRes}
              maxRadiusKm={limits.max_radius_km ?? 20}
              minSpacingM={limits.min_spacing_m ?? 50}
              maxResultsLimit={limits.max_results ?? 2000}
            />
          )}

          {tab === 'filter' && (
            <FilterPanel
              filters={filters}
              onChange={setFilters}
              total={result?.points.length ?? 0}
              visible={visiblePoints.length}
              viewMode={viewMode}
              onViewModeChange={setViewMode}
            />
          )}

          {tab === 'weights' && config && (
            <WeightsEditor
              config={config}
              labels={labels}
              writable={configWritable}
              onApply={(draft) => {
                setOverride(draft)
                setTab('search')
                // Re-run straight away when a result is already on screen.
                // Without this, "Apply" looked like it did nothing: the new
                // weights only reached the backend on the next manual search,
                // so the map kept showing the old scores.
                if (result && !busy) startSearch(draft)
              }}
              onConfigSaved={(saved) => {
                setConfig(saved)
                setOverride(null)
              }}
            />
          )}

          {override && (
            <p className="hint panel">
              Custom weights active (this session only).{' '}
              <button type="button" className="link" onClick={() => setOverride(null)}>
                discard
              </button>
            </p>
          )}

          {result && (
            <section className="panel stats">
              <h2>Statistics</h2>
              <ul>
                <li>
                  Grid points: <strong>{result.stats.grid_points.toLocaleString('en-GB')}</strong> at{' '}
                  {result.stats.spacing_m} m
                </li>
                <li>
                  Overpass tiles: {result.stats.tiles_cached} cached, {result.stats.tiles_fetched} fetched
                </li>
                <li>OSM objects: {result.stats.osm_elements.toLocaleString('en-GB')}</li>
                <li>
                  Best score:{' '}
                  <strong style={{ color: scoreColorSolid(result.stats.score_max) }}>
                    {Math.round(result.stats.score_max * 100)}
                  </strong>{' '}
                  · avg {Math.round(result.stats.score_mean * 100)}
                </li>
                <li>Blocked: {Math.round(result.stats.blocked_share * 100)} % of the area</li>
                <li>Duration: {result.stats.duration_s} s</li>
                <li>Time profile: {result.time_profile_label}</li>
              </ul>
              {result.notes.map((note, index) => (
                <p className="hint" key={index}>
                  {note}
                </p>
              ))}
            </section>
          )}

          <section className="panel">
            <h2>Extra layers</h2>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={showStrava}
                disabled={!stravaAvailable}
                onChange={(event) => setShowStrava(event.target.checked)}
              />
              <span>
                Show the Strava heatmap
                {!stravaHiRes && (
                  <em className="hint"> (public up to zoom {health?.strava_public_max_zoom ?? 12})</em>
                )}
              </span>
            </label>
            {airspaceEnabled && (
              <>
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={showAirspace}
                    onChange={(event) => setShowAirspace(event.target.checked)}
                  />
                  <span>Custom no-fly zones ({airspace?.features?.length ?? 0})</span>
                </label>
                <p className="hint">
                  Maintain your zones in <code>backend/data/airspace.geojson</code>.
                </p>
              </>
            )}
          </section>
        </aside>

        <main className="map-area">
          {pickMode && <div className="pick-hint">Click the map to set the starting point</div>}
          <MapView
            center={center}
            radiusKm={params.radiusKm}
            points={visiblePoints}
            selectedId={selected?.id ?? null}
            onSelect={setSelected}
            onPickCenter={(next) => {
              setCenter({ ...next, label: 'Picked on map' })
              setPickMode(false)
            }}
            pickMode={pickMode}
            showStrava={showStrava && stravaAvailable}
            stravaTileUrl={health?.strava_tile_url}
            stravaMaxNativeZoom={health?.strava_public_max_zoom ?? 12}
            showAirspace={showAirspace && airspaceEnabled}
            airspace={airspace}
            viewMode={viewMode}
          />
          <div className="legend">
            <span>unsuitable</span>
            <div className="legend-gradient" />
            <span>ideal</span>
          </div>
        </main>

        <aside className={`detail-column${selected ? ' open' : ''}`}>
          <DetailPanel point={selected} labels={labels} onClose={() => setSelected(null)} />
        </aside>
      </div>

      {(sidebarOpen || selected) && (
        <div
          className="drawer-backdrop"
          role="presentation"
          onClick={() => {
            setSidebarOpen(false)
            setSelected(null)
          }}
        />
      )}

      <Footer donateUrl={health?.donate_url} donateLabel={health?.donate_label} />
    </div>
  )
}
