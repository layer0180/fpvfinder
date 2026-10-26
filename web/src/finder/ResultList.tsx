import type { Point } from './types'
import { categoryLabel, reasonText, type Lang, type UiStrings } from './i18n'
import { percent, STRICT_PROTECTED } from './spots'

interface Props {
  spots: Point[]
  lang: Lang
  s: UiStrings
  onSelect: (spot: Point) => void
}

/** "Vogelschutzgebiet", "Naturschutzgebiet" ... for every strict area the spot lies in. */
function protectedKinds(spot: Point, s: UiStrings): string[] {
  return [...new Set(spot.warnings.filter((w) => STRICT_PROTECTED.has(w.code)).map((w) => s.protectedShort[w.code]))]
}

export default function ResultList({ spots, lang, s, onSelect }: Props) {
  if (!spots.length) return <p className="empty">{s.noSpots}</p>
  return (
    <ol className="results">
      {spots.map((spot, i) => (
        <li key={spot.id}>
          <button type="button" className="result" onClick={() => onSelect(spot)}>
            <span className="result-rank" data-step={Math.min(4, Math.floor(spot.score * 5))}>
              {i + 1}
            </span>
            <span className="result-body">
              <span className="result-title">
                {spot.area_name || categoryLabel(spot.category, lang)}
                {spot.warnings.some((w) => w.level === 'danger' && !STRICT_PROTECTED.has(w.code)) && (
                  <span className="result-flag">!</span>
                )}
              </span>
              {protectedKinds(spot, s).map((label) => (
                <span key={label} className="result-protected">
                  {label}
                </span>
              ))}
              {spot.reasons[0] && <span className="result-reason">{reasonText(spot.reasons[0], lang)}</span>}
            </span>
            <span className="result-score">
              {percent(spot.score)}
              <span className="visually-hidden"> {s.scoreLabel}</span>
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
