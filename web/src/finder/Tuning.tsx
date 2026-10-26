import { useEffect, useState } from 'react'
import type { UiStrings } from './i18n'

/**
 * Fine-tuning of the most telling weights, for this visitor's searches only
 * (sent as a per-request override; the server's configuration is untouched).
 * Defaults are fetched when the panel is first opened.
 */
export const TUNABLE = [
  ['solitude', 'paths'],
  ['solitude', 'routes'],
  ['solitude', 'buildings'],
  ['solitude', 'attractors'],
  ['flyability', 'powerlines'],
  ['flyability', 'structure'],
] as const

export type TuningKey =
  | 'solitude.paths'
  | 'solitude.routes'
  | 'solitude.buildings'
  | 'solitude.attractors'
  | 'flyability.powerlines'
  | 'flyability.structure'
export type Tuning = Partial<Record<TuningKey, number>>

/** Overrides -> the nested shape of the scoring config. */
export function tuningWeights(tuning: Tuning): Record<string, unknown> | undefined {
  const out: Record<string, { components: Record<string, { weight: number }> }> = {}
  for (const [key, weight] of Object.entries(tuning)) {
    if (weight === undefined) continue
    const [group, name] = key.split('.')
    out[group] ??= { components: {} }
    out[group].components[name] = { weight }
  }
  return Object.keys(out).length ? out : undefined
}

interface Props {
  s: UiStrings
  value: Tuning
  onChange: (tuning: Tuning) => void
}

export default function TuningPanel({ s, value, onChange }: Props) {
  const [defaults, setDefaults] = useState<Record<TuningKey, number> | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!open || defaults) return
    fetch('/api/config')
      .then((r) => r.json())
      .then(({ config }) => {
        const d = {} as Record<TuningKey, number>
        for (const [group, name] of TUNABLE) d[`${group}.${name}` as TuningKey] = config[group].components[name].weight
        setDefaults(d)
      })
      .catch(() => setDefaults(null))
  }, [open, defaults])

  const changed = Object.keys(value).length > 0

  return (
    <details className="tuning" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>{s.tuning}</summary>
      {defaults ? (
        <>
          {TUNABLE.map(([group, name]) => {
            const key = `${group}.${name}` as TuningKey
            const current = value[key] ?? defaults[key]
            return (
              <label key={key} className="field">
                <span>
                  {s.tuningLabels[key]}: <strong>{Math.round(current * 100)}</strong>
                </span>
                <input
                  type="range"
                  min={0}
                  max={0.4}
                  step={0.02}
                  value={current}
                  onChange={(e) => {
                    const next = Number(e.target.value)
                    const { [key]: _, ...rest } = value
                    onChange(Math.abs(next - defaults[key]) < 1e-9 ? rest : { ...rest, [key]: next })
                  }}
                />
              </label>
            )
          })}
          <p className="muted tuning-note">{s.tuningNote}</p>
          {changed && (
            <button type="button" className="link-button" onClick={() => onChange({})}>
              {s.tuningReset}
            </button>
          )}
        </>
      ) : (
        open && <p className="muted">{s.mapLoading}</p>
      )}
    </details>
  )
}
