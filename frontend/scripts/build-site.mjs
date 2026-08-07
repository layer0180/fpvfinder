/**
 * Generates the static marketing pages, robots.txt and sitemap.xml.
 *
 * Runs before `vite build` (see package.json). Vite then treats the emitted
 * HTML files as additional entry points, so they end up in dist/ next to the
 * app bundle and are served by the same container.
 *
 * The generated *.html files are git-ignored: content.*.mjs is the source of
 * truth, not the output.
 *
 * SITE_URL matters. canonical, hreflang, Open Graph images and the sitemap all
 * need absolute URLs; a relative one is either ignored or actively wrong. Pass
 * your real domain at build time:
 *
 *     SITE_URL=https://fpvfinder.example.com npm run build
 */

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import de from '../site/content.de.mjs'
import en from '../site/content.en.mjs'
import { renderFaq, renderLanding, urlFor } from '../site/render.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(here, '..')

const FALLBACK_URL = 'http://localhost:8000'
const siteUrl = (process.env.SITE_URL || '').trim().replace(/\/$/, '') || FALLBACK_URL

if (!process.env.SITE_URL) {
  console.warn(
    `[build-site] SITE_URL is not set - using ${FALLBACK_URL} for canonical/OG/sitemap URLs.\n` +
      '[build-site] That is fine locally, but set it for a real deployment or search engines\n' +
      '[build-site] will be pointed at localhost.',
  )
}

// Register a language here to add it. `prefix: ''` means it lives at the root.
const languages = [de, en]

const write = (relativePath, contents) => {
  const target = resolve(frontendRoot, relativePath)
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(target, contents, 'utf8')
  return relativePath
}

const written = []

for (const c of languages) {
  const base = c.prefix ? `${c.prefix}/` : ''
  written.push(write(`${base}index.html`, renderLanding({ c, siteUrl, languages })))
  written.push(write(`${base}faq.html`, renderFaq({ c, siteUrl, languages })))
}

// ---------------------------------------------------------------------------
// robots.txt
// ---------------------------------------------------------------------------
// The first line is a contract, not a decoration: backend/app/main.py reads the
// base URL back out of it to rewrite canonical/sitemap URLs at serve time, so a
// published image can run under a domain nobody knew at build time. Keep the
// "# <absolute url>" shape.
//
// Note what is NOT disallowed here. /app must stay crawlable even though it
// must not be indexed - it carries <meta name="robots" content="noindex">, and
// a crawler blocked in robots.txt can never read that tag. Blocking it instead
// is how a URL ends up listed with no description: Google still learns the URL
// from the links on the landing page, it just never learns it was meant to stay
// out. Letting it fetch the page costs nothing, because /app is a static shell
// and the API that would do real work is disallowed below.
write(
  'public/robots.txt',
  `# ${siteUrl}
User-agent: *
Disallow: /api/

Sitemap: ${siteUrl}/sitemap.xml
`,
)

// ---------------------------------------------------------------------------
// sitemap.xml
// ---------------------------------------------------------------------------
const today = new Date().toISOString().slice(0, 10)
const pages = languages.flatMap((c) => [
  { c, page: '', priority: '1.0' },
  { c, page: 'faq', priority: '0.8' },
])

const urls = pages
  .map(({ c, page, priority }) => {
    // Every URL lists all its language variants, which is what tells Google the
    // pages are translations rather than duplicates.
    //
    // This set has to match the <link rel="alternate"> tags the pages carry
    // (see site/render.mjs), x-default included. Declaring hreflang in both
    // places is allowed, but the two must agree - where they disagree Google
    // reports an hreflang conflict and falls back to trusting neither. Hence
    // x-default here too, pointing at the prefix-less pages, which is what a
    // visitor with no matching language gets.
    const alternates = languages
      .map(
        (l) =>
          `      <xhtml:link rel="alternate" hreflang="${l.lang}" href="${urlFor(siteUrl, l.prefix, page)}" />`,
      )
      .concat(
        `      <xhtml:link rel="alternate" hreflang="x-default" href="${urlFor(siteUrl, '', page)}" />`,
      )
      .join('\n')
    return `  <url>
    <loc>${urlFor(siteUrl, c.prefix, page)}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>${priority}</priority>
${alternates}
  </url>`
  })
  .join('\n')

write(
  'public/sitemap.xml',
  `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
${urls}
</urlset>
`,
)

console.log(
  `[build-site] ${written.length} pages + robots.txt + sitemap.xml for ${siteUrl}\n` +
    written.map((w) => `             ${w}`).join('\n'),
)
