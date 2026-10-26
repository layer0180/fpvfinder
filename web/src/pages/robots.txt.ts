import type { APIRoute } from 'astro'

// The first line records the base URL baked into this build. The backend reads
// it to know what to replace with PUBLIC_URL (backend/app/web.py) - keep it
// first, and keep the format "# <url>".
export const GET: APIRoute = ({ site }) => {
  const base = (site?.href ?? 'http://localhost:8000/').replace(/\/$/, '')
  const body = `# ${base}
User-agent: *
Allow: /
Disallow: /api/
Disallow: /share-template
Disallow: /en/share-template
Disallow: /region-template
Disallow: /en/region-template

Sitemap: ${base}/sitemap.xml
`
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } })
}
