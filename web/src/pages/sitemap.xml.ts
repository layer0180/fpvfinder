import type { APIRoute } from 'astro'
import { getCollection } from 'astro:content'
import { ROUTES, type RouteKey } from '../i18n/site'

// Pages worth a search result. The finder renders nothing without JavaScript,
// and imprint/privacy are obligations rather than landing pages.
const INDEXED: RouteKey[] = ['home', 'guides', 'faq', 'start', 'support']

type Lang = 'de' | 'en'

function entry(loc: string, alternates: Record<Lang, string>, lastmod?: string): string {
  const links = (['de', 'en'] as const)
    .map((l) => `    <xhtml:link rel="alternate" hreflang="${l}" href="${alternates[l]}"/>`)
    .concat(`    <xhtml:link rel="alternate" hreflang="x-default" href="${alternates.de}"/>`)
  return ['  <url>', `    <loc>${loc}</loc>`, ...(lastmod ? [`    <lastmod>${lastmod}</lastmod>`] : []), ...links, '  </url>'].join(
    '\n',
  )
}

export const GET: APIRoute = async ({ site }) => {
  const base = (site?.href ?? 'http://localhost:8000/').replace(/\/$/, '')
  const abs = (path: string) => base + (path === '/' ? '/' : path)

  // No <lastmod> for these pages: the only date available at build time is the
  // build itself, and a lastmod that always says "today" teaches Google to
  // ignore the field.
  const urls = INDEXED.flatMap((key) =>
    (['de', 'en'] as const).map((lang) =>
      entry(abs(ROUTES[key][lang]), { de: abs(ROUTES[key].de), en: abs(ROUTES[key].en) }),
    ),
  )

  // Guides carry a real date - when their content was last checked.
  const guides = await getCollection('guides')
  const guideUrl = (lang: Lang, slug: string) => abs(`${ROUTES.guides[lang]}/${slug}`)
  for (const g of guides) {
    const pair = Object.fromEntries(
      guides
        .filter((o) => o.data.translation === g.data.translation)
        .map((o) => [o.data.lang, guideUrl(o.data.lang, o.data.slug)]),
    ) as Partial<Record<Lang, string>>
    const self = guideUrl(g.data.lang, g.data.slug)
    urls.push(entry(self, { de: pair.de ?? self, en: pair.en ?? self }, g.data.updated.toISOString().slice(0, 10)))
  }

  const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls.join('\n')}
</urlset>
`
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } })
}
