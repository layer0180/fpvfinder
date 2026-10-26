/**
 * Strings shared by the static pages (header, footer, page chrome).
 * Page bodies live in the pages themselves; the finder has its own
 * dictionary in src/finder/i18n.ts.
 */

export type Lang = 'de' | 'en'

export const SITE_NAME = 'FPV Flying Spot Finder'
export const SITE_NAME_SHORT = 'FPV Spot Finder'
export const GITHUB = 'https://github.com/Layer0180/fpvfinder'

/** Path of each page in each language - the slugs differ for some pages. */
export const ROUTES = {
  home: { de: '/', en: '/en' },
  app: { de: '/app', en: '/en/app' },
  start: { de: '/start', en: '/en/start' },
  faq: { de: '/faq', en: '/en/faq' },
  guides: { de: '/ratgeber', en: '/en/guides' },
  regions: { de: '/regionen', en: '/en/regions' },
  imprint: { de: '/impressum', en: '/en/imprint' },
  privacy: { de: '/datenschutz', en: '/en/privacy' },
  support: { de: '/unterstuetzen', en: '/en/support' },
} as const

export type RouteKey = keyof typeof ROUTES

export const t = {
  de: {
    skip: 'Zum Inhalt springen',
    navApp: 'Spots finden',
    navFaq: 'FAQ',
    navGuides: 'Ratgeber',
    navRegions: 'Regionen',
    otherLang: 'English',
    otherLangCode: 'en',
    mainNav: 'Hauptnavigation',
    footerTagline: 'Kostenloses Community-Tool · keine Konten · keine Werbung · kein Tracking',
    imprint: 'Impressum',
    privacy: 'Datenschutz',
    support: 'Unterstützen',
    source: 'Quellcode',
    attribution:
      'Kartendaten © OpenStreetMap-Mitwirkende (ODbL) · Kartenkacheln OpenFreeMap / OpenMapTiles · Wetter Open-Meteo (CC BY 4.0)',
    disclaimerShort:
      'Kein Ersatz für die Luftraumprüfung: Prüfe vor jedem Flug die geltenden Regeln, z. B. auf dipul.de.',
  },
  en: {
    skip: 'Skip to content',
    navApp: 'Find spots',
    navFaq: 'FAQ',
    navGuides: 'Guides',
    navRegions: 'Regions',
    otherLang: 'Deutsch',
    otherLangCode: 'de',
    mainNav: 'Main navigation',
    footerTagline: 'Free community tool · no accounts · no ads · no tracking',
    imprint: 'Imprint',
    privacy: 'Privacy',
    support: 'Support',
    source: 'Source code',
    attribution:
      'Map data © OpenStreetMap contributors (ODbL) · Map tiles OpenFreeMap / OpenMapTiles · Weather Open-Meteo (CC BY 4.0)',
    disclaimerShort:
      'Not a substitute for an airspace check: verify the rules before every flight, e.g. on dipul.de.',
  },
} as const
