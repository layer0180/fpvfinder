/**
 * Picks the time profile that matches a moment. The keys are those of
 * backend/app/scoring/defaults.py TIME_PROFILES.
 *
 * Public holidays count as weekend - nobody is at work on Easter Monday, the
 * paths are as full as on a Sunday. Only the nationwide German holidays are
 * listed; regional ones would need the visitor's state.
 */
function easterSunday(year: number): Date {
  // Anonymous Gregorian algorithm (Meeus/Jones/Butcher).
  const a = year % 19
  const b = Math.floor(year / 100)
  const c = year % 100
  const d = Math.floor(b / 4)
  const e = b % 4
  const f = Math.floor((b + 8) / 25)
  const g = Math.floor((b - f + 1) / 3)
  const h = (19 * a + b - d - g + 15) % 30
  const i = Math.floor(c / 4)
  const k = c % 4
  const l = (32 + 2 * e + 2 * i - h - k) % 7
  const m = Math.floor((a + 11 * h + 22 * l) / 451)
  const month = Math.floor((h + l - 7 * m + 114) / 31)
  const day = ((h + l - 7 * m + 114) % 31) + 1
  return new Date(year, month - 1, day)
}

function isNationalHoliday(date: Date): boolean {
  const y = date.getFullYear()
  const md = `${date.getMonth() + 1}-${date.getDate()}`
  if (['1-1', '5-1', '10-3', '12-25', '12-26'].includes(md)) return true
  const easter = easterSunday(y).getTime()
  const day = 86_400_000
  const offsetDays = Math.round((new Date(y, date.getMonth(), date.getDate()).getTime() - easter) / day)
  // Good Friday, Easter Monday, Ascension, Whit Monday
  return [-2, 1, 39, 50].includes(offsetDays)
}

export function profileFor(date = new Date()): string {
  const hour = date.getHours()
  const weekend = date.getDay() === 0 || date.getDay() === 6 || isNationalHoliday(date)
  if (hour < 7) return 'early_morning'
  const part = hour < 12 ? 'morning' : hour < 17 ? 'afternoon' : 'evening'
  return `${weekend ? 'weekend' : 'weekday'}_${part}`
}
