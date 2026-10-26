import { expect, test } from '@playwright/test'

// The guides are the pages meant to rank: full text without JavaScript,
// structured data, and the link to their translation.
test('a guide is complete without JavaScript', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false })
  const page = await context.newPage()
  await page.goto('/ratgeber/wo-darf-ich-fpv-fliegen')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Wo darf ich FPV fliegen?')
  await expect(page.locator('table')).toBeVisible()
  await expect(page.locator('link[hreflang="en"]')).toHaveAttribute('href', /\/en\/guides\/where-to-fly-fpv-germany$/)
  const jsonLd = await page.locator('script[type="application/ld+json"]').allTextContents()
  expect(jsonLd.some((s) => s.includes('"Article"'))).toBe(true)
  expect(jsonLd.some((s) => s.includes('"BreadcrumbList"'))).toBe(true)
  await expect(page.getByRole('link', { name: 'Spots finden' }).last()).toHaveAttribute('href', '/app')
  await context.close()
})

test('the guide index lists every guide', async ({ page }) => {
  await page.goto('/en/guides')
  await expect(page.locator('.guide-list li')).toHaveCount(9)
})

test('the sitemap lists guides with a real lastmod', async ({ request }) => {
  const xml = await (await request.get('/sitemap.xml')).text()
  expect(xml).toMatch(/\/ratgeber\/fpv-spot-checkliste<\/loc>\s*<lastmod>\d{4}-\d{2}-\d{2}<\/lastmod>/)
})
