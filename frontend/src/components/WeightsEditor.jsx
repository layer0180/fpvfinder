import { useEffect, useState } from 'react'
import { api } from '../api/client.js'

/**
 * Editor for the score weighting.
 *
 * Two modes of effect:
 *   "Apply" -> only affects the next search (request override)
 *   "Save"  -> writes to backend/config/weights.json
 */
export default function WeightsEditor({ config, labels, onApply, onConfigSaved, writable = true }) {
  const [draft, setDraft] = useState(config)
  const [rawOpen, setRawOpen] = useState(false)
  const [rawText, setRawText] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    setDraft(config)
    setRawText(JSON.stringify(config, null, 2))
  }, [config])

  if (!draft) return null

  const componentLabels = labels?.components ?? {}

  const setPath = (path, value) => {
    // Shallow, immutable update along a path.
    const next = structuredClone(draft)
    let node = next
    for (let i = 0; i < path.length - 1; i += 1) node = node[path[i]]
    node[path[path.length - 1]] = value
    setDraft(next)
  }

  const balance = draft.total.solitude_weight

  const componentSliders = (section) =>
    Object.entries(draft[section].components).map(([key, spec]) => (
      <label className="field compact" key={key}>
        <span>
          {componentLabels[key] ?? key} <strong>{spec.weight.toFixed(2)}</strong>
        </span>
        <input
          type="range"
          min="0"
          max="0.5"
          step="0.01"
          value={spec.weight}
          onChange={(event) => setPath([section, 'components', key, 'weight'], Number(event.target.value))}
        />
      </label>
    ))

  const ruleInput = (key, label, max = 2000) => (
    <label className="field compact" key={key}>
      <span>
        {label} <strong>{draft.hard_rules[key]} m</strong>
      </span>
      <input
        type="range"
        min="0"
        max={max}
        step="10"
        value={draft.hard_rules[key]}
        onChange={(event) => setPath(['hard_rules', key], Number(event.target.value))}
      />
    </label>
  )

  const save = async () => {
    setStatus('Saving …')
    try {
      const response = await api.saveConfig(draft, false)
      onConfigSaved(response.config)
      setStatus('Saved to backend/config/weights.json')
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  const reset = async () => {
    setStatus('Resetting …')
    try {
      const response = await api.resetConfig()
      onConfigSaved(response.config)
      setStatus('Reset to the default values')
    } catch (error) {
      setStatus(`Error: ${error.message}`)
    }
  }

  const applyRaw = () => {
    try {
      const parsed = JSON.parse(rawText)
      setDraft(parsed)
      setStatus('JSON applied - now press "Apply" or "Save".')
    } catch (error) {
      setStatus(`Invalid JSON: ${error.message}`)
    }
  }

  return (
    <section className="panel">
      <h2>Weighting</h2>

      <label className="field">
        <span>
          Balance <strong>{Math.round(balance * 100)} % solitude</strong> /{' '}
          {Math.round((1 - balance) * 100)} % flyability
        </span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={balance}
          onChange={(event) => {
            const value = Number(event.target.value)
            setPath(['total', 'solitude_weight'], value)
            setPath(['total', 'flyability_weight'], Number((1 - value).toFixed(2)))
          }}
        />
      </label>

      <details open>
        <summary>Solitude components</summary>
        {componentSliders('solitude')}
      </details>

      <details>
        <summary>Flyability components</summary>
        {componentSliders('flyability')}
      </details>

      <details>
        <summary>Hard rules (blocking criteria)</summary>
        {ruleInput('min_dist_residential_m', 'Min. distance to residential / recreation')}
        {ruleInput('min_dist_building_m', 'Min. distance to buildings', 500)}
        {ruleInput('min_dist_road_m', 'Min. distance to roads', 300)}
        {ruleInput('min_dist_railway_m', 'Min. distance to railways', 500)}
        {ruleInput('airport_radius_m', 'Aerodrome exclusion radius', 8000)}
        <label className="checkbox">
          <input
            type="checkbox"
            checked={draft.hard_rules.block_in_protected_area}
            onChange={(event) => setPath(['hard_rules', 'block_in_protected_area'], event.target.checked)}
          />
          <span>Block nature reserves</span>
        </label>
      </details>

      <details open={rawOpen} onToggle={(event) => setRawOpen(event.target.open)}>
        <summary>Advanced: full config as JSON</summary>
        <p className="hint">
          This is also where you fine-tune the land use table (<code>landuse_table</code>) - the most
          effective knob for adapting the app to your flying area.
        </p>
        <textarea
          className="raw-json"
          value={rawText}
          spellCheck={false}
          onChange={(event) => setRawText(event.target.value)}
        />
        <button type="button" className="secondary" onClick={applyRaw}>
          Apply JSON
        </button>
      </details>

      <div className="button-row">
        <button type="button" className="primary" onClick={() => onApply(draft)}>
          Apply
        </button>
        {/* Persisting changes the configuration for every visitor, so a shared
            instance refuses it server-side. Hide the buttons rather than offer
            an action that can only fail. */}
        {writable && (
          <>
            <button type="button" className="secondary" onClick={save}>
              Save
            </button>
            <button type="button" className="secondary" onClick={reset}>
              Defaults
            </button>
          </>
        )}
      </div>
      <p className="hint">
        “Apply” re-runs the search with these weights for you only.
        {!writable && ' This is a shared instance, so they cannot be saved server-side.'}
      </p>
      {status && <p className="hint">{status}</p>}
    </section>
  )
}
