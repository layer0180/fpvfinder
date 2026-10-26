/** Getting a spot out of the finder: route links and a GPX waypoint file. */

export function routeLinks(lat: number, lon: number) {
  const ll = `${lat.toFixed(6)},${lon.toFixed(6)}`
  return {
    google: `https://www.google.com/maps/dir/?api=1&destination=${ll}`,
    apple: `https://maps.apple.com/?daddr=${ll}`,
    osm: `https://www.openstreetmap.org/directions?to=${ll}`,
  }
}

/** iOS opens Apple Maps natively; everyone else gets Google Maps. */
export function preferredRoute(lat: number, lon: number): string {
  const links = routeLinks(lat, lon)
  return /iPhone|iPad|Macintosh/.test(navigator.userAgent) && 'ontouchend' in document ? links.apple : links.google
}

// The dipul map tool documents no URL parameters for a position, so the link
// opens the map and the coordinates are offered for copying next to it.
export const DIPUL_MAP = 'https://maptool-dipul.dfs.de/'

const escapeXml = (s: string) => s.replace(/[<>&"']/g, (c) => `&#${c.charCodeAt(0)};`)

export function downloadGpx(spots: { lat: number; lon: number; name: string; desc: string }[], filename: string): void {
  const wpts = spots
    .map(
      (s) =>
        `  <wpt lat="${s.lat.toFixed(6)}" lon="${s.lon.toFixed(6)}">\n    <name>${escapeXml(s.name)}</name>\n    <desc>${escapeXml(s.desc)}</desc>\n  </wpt>`,
    )
    .join('\n')
  const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="FPV Flying Spot Finder" xmlns="http://www.topografix.com/GPX/1/1">
${wpts}
</gpx>
`
  const url = URL.createObjectURL(new Blob([gpx], { type: 'application/gpx+xml' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
