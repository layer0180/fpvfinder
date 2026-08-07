import { formatDistance, formatPercent, scoreColorSolid, WARNING_ICONS } from '../lib/score.js'

/** Bar for a single score component. */
function ComponentBar({ label, value }) {
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div
          className="bar-fill"
          style={{ width: `${Math.max(2, value * 100)}%`, background: scoreColorSolid(value) }}
        />
      </div>
      <span className="bar-value">{Math.round(value * 100)}</span>
    </div>
  )
}

export default function DetailPanel({ point, labels, onClose }) {
  if (!point) {
    return (
      <section className="panel detail-empty">
        <h2>Detail</h2>
        <p className="hint">Click a point on the map to see its individual scores and warnings.</p>
      </section>
    )
  }

  const componentLabels = labels?.components ?? {}
  const distanceLabels = labels?.distances ?? {}

  const distanceRows = [
    ['settlement', 'd_settlement'],
    ['building', 'd_building'],
    ['road', 'd_road'],
    ['path', 'd_path'],
    ['tree', 'd_tree'],
    ['power', 'd_power'],
    ['railway', 'd_railway'],
    ['water', 'd_water'],
    ['attractor', 'd_attractor'],
    ['strava_route', 'd_strava'],
    ['protected', 'd_protected'],
    ['aerodrome', 'd_aerodrome'],
  ]

  return (
    <section className="panel detail">
      <div className="detail-header">
        <h2>Point detail</h2>
        <button type="button" className="icon" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>

      <div className="score-headline" style={{ borderColor: scoreColorSolid(point.score) }}>
        <div className="score-big" style={{ color: scoreColorSolid(point.score) }}>
          {Math.round(point.score * 100)}
        </div>
        <div className="score-meta">
          <div>
            Solitude <strong>{formatPercent(point.solitude)}</strong>
          </div>
          <div>
            Flyability <strong>{formatPercent(point.flyability)}</strong>
          </div>
          {point.blocked && <div className="blocked-flag">blocked by a hard rule</div>}
        </div>
      </div>

      <p className="coords">
        <a
          href={`https://www.openstreetmap.org/?mlat=${point.lat}&mlon=${point.lon}#map=16/${point.lat}/${point.lon}`}
          target="_blank"
          rel="noreferrer"
        >
          {point.lat.toFixed(5)}, {point.lon.toFixed(5)}
        </a>
        {' · '}
        {point.category_label}
        {point.area_name ? ` (${point.area_name})` : ''}
      </p>

      {point.warnings.length > 0 && (
        <ul className="warnings">
          {point.warnings.map((warning, index) => (
            <li key={index} className={`warning ${warning.level}`}>
              <span aria-hidden="true">{WARNING_ICONS[warning.level]}</span> {warning.text}
            </li>
          ))}
        </ul>
      )}

      <h3>Solitude score</h3>
      {Object.entries(point.components.solitude).map(([key, value]) => (
        <ComponentBar key={key} label={componentLabels[key] ?? key} value={value} />
      ))}

      <h3>Flyability</h3>
      {Object.entries(point.components.flyability).map(([key, value]) => (
        <ComponentBar key={key} label={componentLabels[key] ?? key} value={value} />
      ))}

      <h3>Distances</h3>
      <table className="distances">
        <tbody>
          {distanceRows.map(([key, labelKey]) => (
            <tr key={key}>
              <td>{distanceLabels[labelKey] ?? key}</td>
              <td>{formatDistance(point.distances[key])}</td>
            </tr>
          ))}
          {point.strava > 0 && (
            <tr>
              <td>Strava activity</td>
              <td>{formatPercent(point.strava)}</td>
            </tr>
          )}
          {point.population != null && (
            <tr>
              <td>Population density</td>
              <td>{Math.round(point.population)} /km²</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  )
}
