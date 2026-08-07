import { formatDistance } from '../lib/score.js'

/**
 * Filters act purely on the already loaded result on the client side,
 * so they respond instantly without another backend request.
 */
export default function FilterPanel({ filters, onChange, total, visible, viewMode, onViewModeChange }) {
  const update = (key, value) => onChange({ ...filters, [key]: value })

  const slider = (key, label, max, step = 25, format = formatDistance) => (
    <label className="field" key={key}>
      <span>
        {label} <strong>{format(filters[key])}</strong>
      </span>
      <input
        type="range"
        min="0"
        max={max}
        step={step}
        value={filters[key]}
        onChange={(event) => update(key, Number(event.target.value))}
      />
    </label>
  )

  return (
    <section className="panel">
      <h2>Filters &amp; display</h2>

      <div className="segmented">
        <button
          type="button"
          className={viewMode === 'markers' ? 'active' : ''}
          onClick={() => onViewModeChange('markers')}
        >
          Markers
        </button>
        <button
          type="button"
          className={viewMode === 'heat' ? 'active' : ''}
          onClick={() => onViewModeChange('heat')}
        >
          Heatmap
        </button>
      </div>

      <label className="field">
        <span>
          Minimum score <strong>{Math.round(filters.minScore * 100)}</strong>
        </span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={filters.minScore}
          onChange={(event) => update('minScore', Number(event.target.value))}
        />
      </label>

      {slider('minSettlement', 'Min. distance to residential / recreation', 1500, 25)}
      {slider('minBuilding', 'Min. distance to buildings', 1000, 25)}
      {slider('minRoad', 'Min. distance to roads', 800, 25)}
      {slider('minPath', 'Min. distance to paths', 500, 10)}
      {slider('minStravaDistance', 'Min. distance to busy routes', 800, 25)}

      <label className="field">
        <span>
          Max. Strava activity <strong>{Math.round(filters.maxStrava * 100)} %</strong>
        </span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={filters.maxStrava}
          onChange={(event) => update('maxStrava', Number(event.target.value))}
        />
      </label>

      <label className="checkbox">
        <input
          type="checkbox"
          checked={filters.showBlocked}
          onChange={(event) => update('showBlocked', event.target.checked)}
        />
        <span>Show blocked points (grey)</span>
      </label>

      <p className="hint">
        {visible} of {total} points visible
      </p>
    </section>
  )
}
