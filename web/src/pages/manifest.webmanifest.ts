import type { APIRoute } from 'astro'

// Makes the finder installable ("Zum Home-Bildschirm"). One per language so
// the installed app opens in the language it was installed from.
export const GET: APIRoute = () =>
  new Response(
    JSON.stringify({
      name: 'FPV Flying Spot Finder',
      short_name: 'FPV Spots',
      description: 'Ruhige FPV-Spots in deiner Nähe finden.',
      lang: 'de',
      start_url: '/app?source=pwa',
      scope: '/',
      display: 'standalone',
      background_color: '#0c1015',
      theme_color: '#0c1015',
      icons: [
        { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
        { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
      ],
    }),
    { headers: { 'Content-Type': 'application/manifest+json' } },
  )
