// Static build only: every page is plain HTML in dist/, served by the FastAPI
// backend in the same container. Node is needed at build time, never at runtime.
import { defineConfig } from 'astro/config'
import react from '@astrojs/react'

// Canonical links, hreflang, Open Graph and the sitemap need absolute URLs, but
// a published image cannot know the domain it will run under. So the build
// bakes this address in and the backend swaps it for PUBLIC_URL while serving
// (backend/app/web.py). Setting SITE_URL here only matters for a fixed-domain
// build; PUBLIC_URL always wins.
const site = (process.env.SITE_URL || 'http://localhost:8000').replace(/\/$/, '')

export default defineConfig({
  site,
  output: 'static',
  // /faq -> dist/faq/index.html; the backend serves it at /faq, no slash.
  trailingSlash: 'never',
  build: { format: 'directory', assets: 'assets' },
  // v7 defaults to JSX whitespace rules, which glue "<strong>A</strong> b"
  // into "Ab" in running text. Prose pages need HTML rules.
  compressHTML: true,
  integrations: [react()],
  i18n: {
    locales: ['de', 'en'],
    defaultLocale: 'de',
    routing: { prefixDefaultLocale: false },
  },
  vite: {
    build: { chunkSizeWarningLimit: 1200 },
  },
})
