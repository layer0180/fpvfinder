/**
 * Finder strings. Texts for backend codes (warnings, reasons, categories,
 * errors) come from shared/i18n, which the backend reads too - one wording for
 * the app and for share previews.
 */
import codesDe from '../../../shared/i18n/de.json'
import codesEn from '../../../shared/i18n/en.json'
import type { Coded } from './types'

export type Lang = 'de' | 'en'

const ui = {
  de: {
    searchPlaceholder: 'Ort oder Adresse',
    searchLabel: 'Ort suchen',
    locate: 'Mein Standort',
    locating: 'Standort wird ermittelt …',
    locateDenied: 'Standortfreigabe abgelehnt. Gib stattdessen einen Ort ein.',
    locateUnavailable: 'Dein Standort ist gerade nicht verfügbar.',
    noPlaceFound: 'Diesen Ort haben wir nicht gefunden.',
    idleTitle: 'Wo willst du fliegen?',
    idleText: 'Gib einen Ort ein oder nutze deinen Standort. Der Finder sucht im Umkreis nach ruhigen Spots mit freiem Gelände.',
    surprise: 'Überrasch mich',
    video: 'Video',
    searchingTitle: 'Suche läuft',
    stages: ['Suchgebiet vorbereiten', 'Kartendaten laden', 'Punkte bewerten', 'Beste Spots auswählen'],
    cancel: 'Abbrechen',
    topSpots: 'Beste Spots',
    noSpots: 'In diesem Umkreis haben wir keinen geeigneten Spot gefunden. Versuch einen größeren Radius oder einen anderen Ort.',
    within: 'im Umkreis von {r} km',
    scoreLabel: 'Punkte',
    blocked: 'Gesperrt',
    back: 'Zurück zur Liste',
    why: 'Warum hier',
    watch: 'Darauf achten',
    noWarnings: 'Keine Auffälligkeiten in den Kartendaten.',
    route: 'Route',
    share: 'Teilen',
    shared: 'Link kopiert',
    shareTitle: 'FPV-Spot',
    storyImage: 'Story-Bild',
    checkDipul: 'Auf dipul.de prüfen',
    save: 'Merken',
    saved: 'Gemerkt',
    gpx: 'GPX',
    coords: 'Koordinaten',
    copy: 'Kopieren',
    copied: 'Kopiert',
    solitude: 'Wenig Menschen',
    flyability: 'Gut fliegen',
    details: 'Alle Werte',
    weather: 'Flugwetter',
    weatherLoading: 'Wetter wird geladen …',
    weatherFailed: 'Wetter gerade nicht verfügbar.',
    weatherGo: 'Gute Bedingungen',
    weatherCaution: 'Mit Vorsicht',
    weatherNoGo: 'Eher nicht fliegen',
    wind: 'Wind',
    gusts: 'Böen',
    wind80: 'in 80 m',
    rain: 'Regen',
    sunset: 'Sonnenuntergang',
    windFrom: 'aus {dir}',
    windArrow: 'Wind aus {dir}',
    compass: ['N', 'NO', 'O', 'SO', 'S', 'SW', 'W', 'NW'],
    goldenHour: 'Goldene Stunde',
    goldenNow: 'jetzt bis {end}',
    goldenMorning: 'morgens {start}–{end}',
    goldenEvening: 'abends {start}–{end}',
    goldenTomorrowMorning: 'morgen früh {start}–{end}',
    goldenTomorrowEvening: 'morgen Abend {start}–{end}',
    lightFrom: 'Licht aus {dir}',
    nextHours: 'nächste 3 Stunden',
    weatherNote: 'Grobe Einschätzung für kleine Copter. Daten: Open-Meteo, NOAA SWPC (Kp).',
    kp: 'GPS (Kp)',
    kpQuiet: 'ruhig',
    kpUnsettled: 'unruhig',
    kpStorm: 'Sturm – GPS-Rescue unzuverlässig',
    expert: 'Experte',
    radius: 'Radius',
    timeProfile: 'Zeitprofil',
    auto: 'Automatisch (jetzt)',
    spacing: 'Raster',
    balance: 'Gewichtung',
    balanceQuiet: 'Ruhe',
    balanceFly: 'Gut fliegen',
    tuning: 'Feinabstimmung',
    includeProtected: 'Natur- und Vogelschutzgebiete einbeziehen',
    includeProtectedNote:
      'Für Freizeitflüge sind sie verboten (§ 21h LuftVO). Spots darin bekommen immer einen roten Hinweis.',
    protectedShort: {
      protected_strict: 'Naturschutzgebiet',
      protected_national_park: 'Nationalpark',
      protected_bird: 'Vogelschutzgebiet',
      protected_ffh: 'FFH-Gebiet',
      protected_natura2000: 'Natura 2000',
    } as Record<string, string>,
    tuningNote: 'Höher heißt: zählt stärker. Gilt nur für deine Suchen.',
    tuningReset: 'Zurücksetzen',
    tuningLabels: {
      'solitude.paths': 'Abstand zu Wegen',
      'solitude.routes': 'Abstand zu Wander- und Radrouten',
      'solitude.buildings': 'Abstand zu Gebäuden',
      'solitude.attractors': 'Abstand zu Ausflugszielen',
      'flyability.powerlines': 'Abstand zu Stromleitungen',
      'flyability.structure': 'Struktur zum Umfliegen',
    },
    apply: 'Neu suchen',
    disclaimerTitle: 'Kein Ersatz für die Luftraumprüfung',
    disclaimer:
      'Die Bewertung beruht auf offenen Kartendaten und kann falsch oder unvollständig sein. Ob du an einem Ort fliegen darfst, musst du vor jedem Flug selbst prüfen – z. B. auf dipul.de.',
    understood: 'OK',
    disclaimerShort: 'Prüfe vor jedem Flug die Regeln, z. B. auf dipul.de.',
    favorites: 'Gemerkte Spots',
    remove: 'Entfernen',
    close: 'Schließen',
    expand: 'Liste ausklappen',
    collapse: 'Liste einklappen',
    mapLoading: 'Karte lädt …',
    zone: 'Eigene Sperrzone',
    mapFailed: 'Die Karte konnte nicht geladen werden (WebGL2 nötig). Die Liste funktioniert trotzdem.',
    outsideNote: 'Hinweis',
    home: 'Startseite',
    km: 'km',
    rank: 'Platz',
    openInFinder: 'Im Finder öffnen',
  },
  en: {
    searchPlaceholder: 'Place or address',
    searchLabel: 'Search a place',
    locate: 'My location',
    locating: 'Finding your location …',
    locateDenied: 'Location access was denied. Enter a place instead.',
    locateUnavailable: 'Your location is not available right now.',
    noPlaceFound: 'We could not find that place.',
    idleTitle: 'Where do you want to fly?',
    idleText: 'Enter a place or use your location. The finder searches the area for quiet spots with open ground.',
    surprise: 'Surprise me',
    video: 'Video',
    searchingTitle: 'Searching',
    stages: ['Preparing the area', 'Loading map data', 'Rating points', 'Picking the best spots'],
    cancel: 'Cancel',
    topSpots: 'Best spots',
    noSpots: 'We found no suitable spot in this area. Try a larger radius or another place.',
    within: 'within {r} km',
    scoreLabel: 'points',
    blocked: 'Blocked',
    back: 'Back to the list',
    why: 'Why here',
    watch: 'Watch out for',
    noWarnings: 'Nothing notable in the map data.',
    route: 'Route',
    share: 'Share',
    shared: 'Link copied',
    shareTitle: 'FPV spot',
    storyImage: 'Story image',
    checkDipul: 'Check on dipul.de',
    save: 'Save',
    saved: 'Saved',
    gpx: 'GPX',
    coords: 'Coordinates',
    copy: 'Copy',
    copied: 'Copied',
    solitude: 'Few people',
    flyability: 'Good flying',
    details: 'All values',
    weather: 'Flight weather',
    weatherLoading: 'Loading weather …',
    weatherFailed: 'Weather unavailable right now.',
    weatherGo: 'Good conditions',
    weatherCaution: 'Take care',
    weatherNoGo: 'Better not fly',
    wind: 'Wind',
    gusts: 'Gusts',
    wind80: 'at 80 m',
    rain: 'Rain',
    sunset: 'Sunset',
    windFrom: 'from {dir}',
    windArrow: 'Wind from {dir}',
    compass: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
    goldenHour: 'Golden hour',
    goldenNow: 'now until {end}',
    goldenMorning: 'morning {start}–{end}',
    goldenEvening: 'evening {start}–{end}',
    goldenTomorrowMorning: 'tomorrow morning {start}–{end}',
    goldenTomorrowEvening: 'tomorrow evening {start}–{end}',
    lightFrom: 'light from {dir}',
    nextHours: 'next 3 hours',
    weatherNote: 'Rough guide for small quads. Data: Open-Meteo, NOAA SWPC (Kp).',
    kp: 'GPS (Kp)',
    kpQuiet: 'quiet',
    kpUnsettled: 'unsettled',
    kpStorm: 'storm – GPS rescue unreliable',
    expert: 'Expert',
    radius: 'Radius',
    timeProfile: 'Time profile',
    auto: 'Automatic (now)',
    spacing: 'Grid',
    balance: 'Weighting',
    balanceQuiet: 'Quiet',
    balanceFly: 'Good flying',
    tuning: 'Fine-tuning',
    includeProtected: 'Include nature and bird protection areas',
    includeProtectedNote:
      'Leisure flights are prohibited there (§ 21h LuftVO). Spots inside always carry a red note.',
    protectedShort: {
      protected_strict: 'Nature reserve',
      protected_national_park: 'National park',
      protected_bird: 'Bird protection area',
      protected_ffh: 'Habitats area',
      protected_natura2000: 'Natura 2000',
    } as Record<string, string>,
    tuningNote: 'Higher means: counts more. Applies to your searches only.',
    tuningReset: 'Reset',
    tuningLabels: {
      'solitude.paths': 'Distance to paths',
      'solitude.routes': 'Distance to hiking and cycle routes',
      'solitude.buildings': 'Distance to buildings',
      'solitude.attractors': 'Distance to destinations',
      'flyability.powerlines': 'Distance to power lines',
      'flyability.structure': 'Structure to fly around',
    },
    apply: 'Search again',
    disclaimerTitle: 'Not a substitute for an airspace check',
    disclaimer:
      'The rating is based on open map data and can be wrong or incomplete. Whether you may fly somewhere is yours to check before every flight – e.g. on dipul.de.',
    understood: 'OK',
    disclaimerShort: 'Check the rules before every flight, e.g. on dipul.de.',
    favorites: 'Saved spots',
    remove: 'Remove',
    close: 'Close',
    expand: 'Expand the list',
    collapse: 'Collapse the list',
    mapLoading: 'Loading map …',
    zone: 'Custom no-fly zone',
    mapFailed: 'The map could not load (WebGL2 required). The list still works.',
    outsideNote: 'Note',
    home: 'Home',
    km: 'km',
    rank: 'Rank',
    openInFinder: 'Open in the finder',
  },
} as const

export type UiStrings = (typeof ui)['de']

const codes = { de: codesDe, en: codesEn } as const

export function strings(lang: Lang): UiStrings {
  return ui[lang] as UiStrings
}

/** "820 m" / "1,4 km" in the visitor's number format. */
export function formatDistance(metres: number, lang: Lang): string {
  if (metres >= 45_000) return codes[lang].far
  if (metres >= 1000) {
    return `${(metres / 1000).toLocaleString(lang, { maximumFractionDigits: 1 })} km`
  }
  return `${Math.round(metres / 10) * 10} m`
}

export function categoryLabel(category: string, lang: Lang): string {
  return (codes[lang].categories as Record<string, string>)[category] ?? category
}

function fill(template: string, params: Record<string, string | number>, lang: Lang): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = key === 'distance' ? params.distance_m : key === 'limit' ? params.limit_m : params[key]
    if (value === undefined) return ''
    if (key === 'distance' || key === 'limit') return formatDistance(Number(value), lang)
    if (key === 'category') return categoryLabel(String(value), lang)
    if (key === 'kind') return (codes[lang].structureKinds as Record<string, string>)[String(value)] ?? String(value)
    return String(value)
  })
}

export function warningText(w: Coded & { text?: string }, lang: Lang): string {
  const unnamed = (codes[lang].warningsUnnamed as Record<string, string>)[w.code]
  if (unnamed && !w.params.name) return fill(unnamed, w.params, lang)
  const template = (codes[lang].warnings as Record<string, string>)[w.code]
  return template ? fill(template, w.params, lang) : (w.text ?? w.code)
}

export function reasonText(r: Coded, lang: Lang): string {
  // "Nearest path {distance} away" needs a distance; when there is nothing of
  // that kind within reach, the backend sends none and a separate phrase fits.
  const far = (codes[lang].reasonsFar as Record<string, string>)[r.code]
  if (far && r.params.distance_m === undefined) return far
  const template = (codes[lang].reasons as Record<string, string>)[r.code]
  return template ? fill(template, r.params, lang) : r.code
}

export function errorText(code: string, lang: Lang): string {
  const errors = codes[lang].errors as Record<string, string>
  return errors[code] ?? errors.generic
}

export function timeProfileLabel(key: string, lang: Lang): string {
  return (codes[lang].timeProfiles as Record<string, string>)[key] ?? key
}

export function t(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, key: string) => String(params[key] ?? ''))
}
