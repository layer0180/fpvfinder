import { useEffect, useMemo, useState } from 'react'
import { t, type Lang, type UiStrings } from './i18n'
import { compass, nextGoldenHour } from './sun'

/**
 * Flight weather for one spot, straight from Open-Meteo in the browser - free
 * for non-commercial use, no key, CC BY 4.0 (credited below the widget).
 *
 * The traffic light judges the WORST hour of the next three, because a flight
 * session lasts a while and a gust front an hour from now matters now.
 * Thresholds are for small quads (2-5"); it is a rough guide, not a briefing.
 */
interface Hour {
  wind: number
  gust: number
  wind80: number
  rain: number
  temp: number
  /** Where the wind comes from, compass degrees. */
  dir: number
}

interface Forecast {
  hours: Hour[]
  sunset: Date | null
}

type Verdict = 'go' | 'caution' | 'nogo'

export function judge(hours: Hour[]): { verdict: Verdict; worst: Hour } {
  const worst: Hour = {
    wind: Math.max(...hours.map((h) => h.wind)),
    gust: Math.max(...hours.map((h) => h.gust)),
    wind80: Math.max(...hours.map((h) => h.wind80)),
    rain: Math.max(...hours.map((h) => h.rain)),
    temp: Math.min(...hours.map((h) => h.temp)),
    dir: hours[0].dir,
  }
  let verdict: Verdict = 'go'
  if (worst.gust >= 30 || worst.wind80 >= 35 || worst.rain >= 30 || worst.temp <= 0) verdict = 'caution'
  if (worst.gust >= 45 || worst.wind80 >= 50 || worst.rain >= 60) verdict = 'nogo'
  return { verdict, worst }
}

/**
 * Planetary Kp index (NOAA SWPC via our own /api/kp - the value is global, so
 * the server fetches it once for everyone and no visitor IP leaves for the
 * US). Geomagnetic storms degrade GPS, which GPS rescue relies on; Kp 5 and up
 * is a storm. Loaded once per page.
 */
let kpPending: Promise<number | null> | null = null

function loadKp(): Promise<number | null> {
  kpPending ??= fetch('/api/kp')
    .then((r) => (r.ok ? r.json() : { kp: null }))
    .then((body: { kp: number | null }) => body.kp)
    .catch(() => null)
  return kpPending
}

const cache = new Map<string, Promise<Forecast>>()

/** Shared with the map, which draws the wind arrow at the selected spot. */
export function loadWeather(lat: number, lon: number): Promise<Forecast> {
  // ~1 km grid: neighbouring spots share one request.
  const key = `${lat.toFixed(2)},${lon.toFixed(2)}`
  let pending = cache.get(key)
  if (!pending) {
    const params = new URLSearchParams({
      latitude: lat.toFixed(3),
      longitude: lon.toFixed(3),
      hourly: 'wind_speed_10m,wind_gusts_10m,wind_speed_80m,wind_direction_10m,precipitation_probability,temperature_2m',
      daily: 'sunset',
      timezone: 'auto',
      forecast_days: '2',
      wind_speed_unit: 'kmh',
    })
    pending = fetch(`https://api.open-meteo.com/v1/forecast?${params}`)
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status))
        return r.json()
      })
      .then((data) => {
        const h = data.hourly
        const now = Date.now()
        const start = Math.max(0, h.time.findIndex((t: string) => new Date(t).getTime() + 3_600_000 > now))
        const hours: Hour[] = []
        for (let i = start; i < start + 3 && i < h.time.length; i++) {
          hours.push({
            wind: h.wind_speed_10m[i],
            gust: h.wind_gusts_10m[i],
            wind80: h.wind_speed_80m[i],
            rain: h.precipitation_probability[i] ?? 0,
            temp: h.temperature_2m[i],
            dir: h.wind_direction_10m[i],
          })
        }
        const sunset = data.daily?.sunset?.map((t: string) => new Date(t)).find((d: Date) => d.getTime() > now) ?? null
        return { hours, sunset }
      })
    pending.catch(() => cache.delete(key))
    cache.set(key, pending)
  }
  return pending
}

export default function Weather({ lat, lon, lang, s }: { lat: number; lon: number; lang: Lang; s: UiStrings }) {
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [failed, setFailed] = useState(false)
  const [kp, setKp] = useState<number | null>(null)
  const golden = useMemo(() => nextGoldenHour(lat, lon), [lat, lon])

  useEffect(() => {
    let alive = true
    setForecast(null)
    setFailed(false)
    loadWeather(lat, lon)
      .then((f) => alive && setForecast(f))
      .catch(() => alive && setFailed(true))
    loadKp().then((k) => alive && setKp(k))
    return () => {
      alive = false
    }
  }, [lat, lon])

  if (failed) return <p className="muted">{s.weatherFailed}</p>
  if (!forecast || !forecast.hours.length) return <p className="muted">{s.weatherLoading}</p>

  const judged = judge(forecast.hours)
  const worst = judged.worst
  // A geomagnetic storm makes GPS rescue unreliable - worth a "take care".
  const verdict: Verdict = judged.verdict === 'go' && kp !== null && kp >= 5 ? 'caution' : judged.verdict
  const kpLabel = kp === null ? null : kp >= 5 ? s.kpStorm : kp >= 4 ? s.kpUnsettled : s.kpQuiet
  const label = { go: s.weatherGo, caution: s.weatherCaution, nogo: s.weatherNoGo }[verdict]
  const kmh = (v: number) => `${Math.round(v)} km/h`
  const time = (d: Date) => d.toLocaleTimeString(lang, { hour: '2-digit', minute: '2-digit' })
  const windDir = compass(forecast.hours[0].dir, s.compass)

  return (
    <div className="weather">
      <p className={`weather-verdict weather-${verdict}`}>
        <span className="weather-dot" aria-hidden="true" />
        <strong>{label}</strong> <span className="muted">· {s.nextHours}</span>
      </p>
      <dl className="weather-grid">
        <div>
          <dt>{s.wind}</dt>
          <dd>
            {kmh(worst.wind)}{' '}
            <span className="wind-dir">
              {/* The arrow points where the wind blows to. */}
              <span className="wind-arrow" style={{ transform: `rotate(${forecast.hours[0].dir + 180}deg)` }} aria-hidden="true">
                ↑
              </span>{' '}
              {t(s.windFrom, { dir: windDir })}
            </span>
          </dd>
        </div>
        <div>
          <dt>{s.gusts}</dt>
          <dd>{kmh(worst.gust)}</dd>
        </div>
        <div>
          <dt>{s.wind80}</dt>
          <dd>{kmh(worst.wind80)}</dd>
        </div>
        <div>
          <dt>{s.rain}</dt>
          <dd>{Math.round(worst.rain)} %</dd>
        </div>
        {kpLabel && (
          <div>
            <dt>{s.kp}</dt>
            <dd>
              {Math.round(kp ?? 0)} · {kpLabel}
            </dd>
          </div>
        )}
        {forecast.sunset && (
          <div>
            <dt>{s.sunset}</dt>
            <dd>{time(forecast.sunset)}</dd>
          </div>
        )}
        {golden && (
          <div className="weather-wide">
            <dt>{s.goldenHour}</dt>
            <dd>
              {goldenText(golden, s, time)}{' '}
              <span className="muted">· {t(s.lightFrom, { dir: compass(golden.azimuth, s.compass) })}</span>
            </dd>
          </div>
        )}
      </dl>
      <p className="weather-note">{s.weatherNote}</p>
    </div>
  )
}

function goldenText(g: NonNullable<ReturnType<typeof nextGoldenHour>>, s: UiStrings, time: (d: Date) => string): string {
  if (g.start.getTime() <= Date.now()) return t(s.goldenNow, { end: time(g.end) })
  const today = g.start.toDateString() === new Date().toDateString()
  const template = today
    ? g.evening ? s.goldenEvening : s.goldenMorning
    : g.evening ? s.goldenTomorrowEvening : s.goldenTomorrowMorning
  return t(template, { start: time(g.start), end: time(g.end) })
}
