/**
 * Where the sun stands, for the golden hour. The usual low-precision formulas
 * (as in SunCalc / the NOAA calculator), good to a minute or so in Germany -
 * plenty for planning a session, and no request leaves the browser.
 */

const RAD = Math.PI / 180
const DAY_MS = 86_400_000
const J1970 = 2_440_588
const J2000 = 2_451_545
const OBLIQUITY = RAD * 23.4397

/** Elevation above the horizon and compass bearing (0 = north, 90 = east), in degrees. */
export function sunPosition(date: Date, lat: number, lon: number): { elevation: number; azimuth: number } {
  const d = date.getTime() / DAY_MS - 0.5 + J1970 - J2000
  const anomaly = RAD * (357.5291 + 0.98560028 * d)
  const centre = RAD * (1.9148 * Math.sin(anomaly) + 0.02 * Math.sin(2 * anomaly) + 0.0003 * Math.sin(3 * anomaly))
  const longitude = anomaly + centre + RAD * 102.9372 + Math.PI
  const declination = Math.asin(Math.sin(OBLIQUITY) * Math.sin(longitude))
  const ascension = Math.atan2(Math.sin(longitude) * Math.cos(OBLIQUITY), Math.cos(longitude))
  const hourAngle = RAD * (280.16 + 360.9856235 * d) + RAD * lon - ascension
  const phi = RAD * lat
  const elevation = Math.asin(
    Math.sin(phi) * Math.sin(declination) + Math.cos(phi) * Math.cos(declination) * Math.cos(hourAngle),
  )
  // Measured from south towards west - turned into a compass bearing.
  const fromSouth = Math.atan2(
    Math.sin(hourAngle),
    Math.cos(hourAngle) * Math.sin(phi) - Math.tan(declination) * Math.cos(phi),
  )
  return { elevation: elevation / RAD, azimuth: (fromSouth / RAD + 180 + 360) % 360 }
}

export interface GoldenHour {
  start: Date
  end: Date
  /** Bearing of the sun halfway through - where the light comes from. */
  azimuth: number
  evening: boolean
}

// The photographers' golden hour: the sun between 6 degrees above and 4
// below the horizon - warm, low, long shadows.
const HIGH = 6
const LOW = -4
const STEP_MS = 60_000

/** The golden hour going on now, or else the next one within two days. */
export function nextGoldenHour(lat: number, lon: number, now = new Date()): GoldenHour | null {
  const golden = (t: number) => {
    const { elevation } = sunPosition(new Date(t), lat, lon)
    return elevation <= HIGH && elevation >= LOW
  }
  let t = now.getTime()
  // Already in one: walk back to where it began.
  if (golden(t)) {
    while (golden(t - STEP_MS)) t -= STEP_MS
  } else {
    const limit = t + 2 * DAY_MS
    while (!golden(t) && t < limit) t += STEP_MS
    if (t >= limit) return null
  }
  const start = t
  while (golden(t + STEP_MS) && t - start < DAY_MS) t += STEP_MS
  const middle = new Date((start + t) / 2)
  const later = sunPosition(new Date(middle.getTime() + STEP_MS), lat, lon).elevation
  return {
    start: new Date(start),
    end: new Date(t),
    azimuth: sunPosition(middle, lat, lon).azimuth,
    evening: later < sunPosition(middle, lat, lon).elevation,
  }
}

/** 8-point compass name for a bearing in degrees. */
export function compass(bearing: number, names: readonly string[]): string {
  return names[Math.round((((bearing % 360) + 360) % 360) / 45) % 8]
}
