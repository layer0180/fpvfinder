/**
 * Turns the content files into complete, static HTML documents.
 *
 * Why hand-rolled instead of a framework: these are four small marketing pages
 * with no interactivity. A generator of ~200 lines keeps the project on one
 * toolchain and one build, and the emitted HTML needs no JavaScript at all -
 * which is the whole point for crawlers and for Core Web Vitals.
 */

const GITHUB = 'https://github.com/Layer0180/fpvfinder'

const escape = (s) =>
  String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

/** Absolute URL for canonical/hreflang/OG, which must not be relative. */
export function urlFor(siteUrl, prefix, page) {
  const path = [prefix, page].filter(Boolean).join('/')
  return `${siteUrl.replace(/\/$/, '')}/${path}${path ? '' : ''}`
}

/** Path as served (clean URLs, no .html). */
export function pathFor(prefix, page) {
  const parts = [prefix, page].filter(Boolean)
  return '/' + parts.join('/')
}

function head({ c, siteUrl, page, title, description, languages, jsonLd }) {
  const canonical = urlFor(siteUrl, c.prefix, page)
  const alternates = languages
    .map((l) => `<link rel="alternate" hreflang="${l.lang}" href="${urlFor(siteUrl, l.prefix, page)}" />`)
    .concat(`<link rel="alternate" hreflang="x-default" href="${urlFor(siteUrl, '', page)}" />`)
    .join('\n    ')

  return `    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escape(title)}</title>
    <meta name="description" content="${escape(description)}" />
    <link rel="canonical" href="${canonical}" />
    ${alternates}
    <meta name="theme-color" content="#0f1419" />
    <meta name="robots" content="index, follow, max-image-preview:large" />

    <!-- Open Graph / Twitter: controls how the link looks when shared. -->
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="FPV Flying Spot Finder" />
    <meta property="og:locale" content="${c.lang === 'de' ? 'de_DE' : 'en_GB'}" />
    <meta property="og:title" content="${escape(title)}" />
    <meta property="og:description" content="${escape(description)}" />
    <meta property="og:url" content="${canonical}" />
    <meta property="og:image" content="${siteUrl.replace(/\/$/, '')}/og-image.png" />
    <meta property="og:image:width" content="1400" />
    <meta property="og:image:height" content="833" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="${escape(title)}" />
    <meta name="twitter:description" content="${escape(description)}" />
    <meta name="twitter:image" content="${siteUrl.replace(/\/$/, '')}/og-image.png" />

    <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="/site.css" />
    <script type="application/ld+json">
${JSON.stringify(jsonLd, null, 2)
  .split('\n')
  .map((l) => '    ' + l)
  .join('\n')}
    </script>`
}

function header(c, languages, page) {
  const other = languages.find((l) => l.lang !== c.lang)
  return `    <header class="site-header">
      <a class="brand" href="${pathFor(c.prefix, '')}">
        <span class="brand-mark" aria-hidden="true">&#128760;</span>
        <span>FPV Flying Spot Finder</span>
      </a>
      <nav class="site-nav" aria-label="${c.lang === 'de' ? 'Hauptnavigation' : 'Main navigation'}">
        <a href="${pathFor(c.prefix, 'faq')}"${page === 'faq' ? ' aria-current="page"' : ''}>${escape(c.nav.faq)}</a>
        ${other ? `<a href="${pathFor(other.prefix, page)}" hreflang="${other.lang}" lang="${other.lang}">${escape(c.nav.otherLang)}</a>` : ''}
        <a class="btn btn-small" href="/app">${escape(c.nav.app)}</a>
      </nav>
    </header>`
}

function footer(c) {
  return `    <footer class="site-footer">
      <p>${escape(c.footer.tagline)}</p>
      <p class="footer-links">
        <a href="${GITHUB}" rel="noreferrer">${escape(c.footer.source)}</a>
        <a href="/app?legal=imprint">${escape(c.footer.imprint)}</a>
        <a href="/app?legal=privacy">${escape(c.footer.privacy)}</a>
        <a href="/app?legal=funding">${escape(c.footer.funding)}</a>
      </p>
      <p class="attribution">${escape(c.footer.attribution)}</p>
    </footer>`
}

function shell({ c, siteUrl, page, title, description, languages, jsonLd, body }) {
  return `<!doctype html>
<html lang="${c.lang}" dir="${c.dir}">
  <head>
${head({ c, siteUrl, page, title, description, languages, jsonLd })}
  </head>
  <body>
${header(c, languages, page)}
    <main id="main">
${body}
    </main>
${footer(c)}
  </body>
</html>
`
}

// ---------------------------------------------------------------------------
// Landing page
// ---------------------------------------------------------------------------
export function renderLanding({ c, siteUrl, languages }) {
  const L = c.landing

  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'WebApplication',
    name: 'FPV Flying Spot Finder',
    url: urlFor(siteUrl, c.prefix, ''),
    applicationCategory: 'UtilitiesApplication',
    applicationSubCategory: 'Mapping',
    operatingSystem: 'Any (web browser)',
    inLanguage: c.lang,
    description: L.description,
    isAccessibleForFree: true,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'EUR' },
    softwareHelp: urlFor(siteUrl, c.prefix, 'faq'),
    codeRepository: GITHUB,
  }

  const sections = L.sections
    .map((s) => {
      const paras = (s.paragraphs || []).map((p) => `        <p>${p}</p>`).join('\n')
      const list = s.list
        ? `        <ul class="feature-list">\n${s.list.map((i) => `          <li>${i}</li>`).join('\n')}\n        </ul>`
        : ''
      const steps = s.steps
        ? `        <ol class="steps">\n${s.steps
            .map((st) => `          <li><h3>${escape(st.h3)}</h3><p>${escape(st.text)}</p></li>`)
            .join('\n')}\n        </ol>`
        : ''
      return `      <section${s.id ? ` id="${s.id}"` : ''}>
        <h2>${escape(s.h2)}</h2>
${[paras, list, steps].filter(Boolean).join('\n')}
      </section>`
    })
    .join('\n\n')

  const faqTeaser = c.faq.items
    .slice(0, 3)
    .map((i) => `          <li><h3>${escape(i.q)}</h3><p>${escape(i.a)}</p></li>`)
    .join('\n')

  const body = `      <section class="hero">
        <h1>${escape(L.h1)}</h1>
        <p class="lead">${escape(L.lead)}</p>
        <p class="cta-row">
          <a class="btn btn-primary" href="/app">${escape(L.ctaPrimary)}</a>
          <a class="btn" href="#how">${escape(L.ctaSecondary)}</a>
        </p>
        <img
          class="hero-shot"
          src="/og-image.png"
          width="1400"
          height="833"
          alt="${c.lang === 'de'
            ? 'Kartenansicht mit farbig bewerteten Kandidatenpunkten und Detailpanel'
            : 'Map view with colour-scored candidate points and the detail panel'}"
          loading="lazy"
          decoding="async"
        />
      </section>

${sections}

      <section>
        <h2>${escape(L.faqTeaser.h2)}</h2>
        <ul class="faq-teaser">
${faqTeaser}
        </ul>
        <p><a class="btn" href="${pathFor(c.prefix, 'faq')}">${escape(L.faqTeaser.cta)}</a></p>
      </section>

      <section class="callout warning">
        <h2>${escape(L.disclaimer.h2)}</h2>
        <p>${L.disclaimer.text}</p>
      </section>
`

  return shell({
    c,
    siteUrl,
    page: '',
    title: L.title,
    description: L.description,
    languages,
    jsonLd,
    body,
  })
}

// ---------------------------------------------------------------------------
// FAQ page
// ---------------------------------------------------------------------------
export function renderFaq({ c, siteUrl, languages }) {
  const F = c.faq

  // FAQPage markup is what lets Google show the questions directly in results.
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    inLanguage: c.lang,
    mainEntity: F.items.map((i) => ({
      '@type': 'Question',
      name: i.q,
      acceptedAnswer: { '@type': 'Answer', text: i.a },
    })),
  }

  const items = F.items
    .map(
      (i) => `        <div class="faq-item">
          <h2>${escape(i.q)}</h2>
          <p>${escape(i.a)}</p>
        </div>`,
    )
    .join('\n')

  const body = `      <section>
        <h1>${escape(F.h1)}</h1>
        <p class="lead">${escape(F.intro)}</p>
      </section>
      <section class="faq">
${items}
      </section>
      <section class="cta-row">
        <a class="btn btn-primary" href="/app">${escape(c.nav.app)}</a>
        <a class="btn" href="${pathFor(c.prefix, '')}">${escape(c.nav.home)}</a>
      </section>`

  return shell({
    c,
    siteUrl,
    page: 'faq',
    title: F.title,
    description: F.description,
    languages,
    jsonLd,
    body,
  })
}
