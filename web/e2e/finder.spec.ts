import { expect, test } from '@playwright/test'

// Inside the fixture store (backend/tests/test_osm_store.py): 48.40-48.50 N, 9.40-9.50 E.
const FIXTURE = '/app?lat=48.4500&lon=9.4500&r=2'

test('landing page works without JavaScript and leads to the finder', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false })
  const page = await context.newPage()
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href', /\/$/)
  // The hero search is a plain form to the finder.
  await expect(page.locator('form[action="/app"] input[name=q]')).toBeVisible()
  await context.close()
})

test('a deep link runs the search and lists the best spots', async ({ page }) => {
  await page.goto(FIXTURE)
  const results = page.locator('.results .result')
  await expect(results.first()).toBeVisible({ timeout: 30_000 })
  expect(await results.count()).toBeGreaterThan(0)
  // Ranked, with a score.
  await expect(results.first().locator('.result-rank')).toHaveText('1')
  await expect(results.first().locator('.result-score')).toHaveText(/\d+/)
})

test('a spot shows reasons, weather section, route and share', async ({ page, context, browserName }) => {
  await page.goto(FIXTURE)
  await page.locator('.results .result').first().click()
  const detail = page.locator('.detail')
  await expect(detail.getByRole('heading', { level: 2 })).toBeVisible()
  await expect(detail.getByRole('link', { name: 'Route' })).toHaveAttribute('href', /maps/)
  await expect(page).toHaveURL(/spot=48\.\d+,9\.\d+/)

  // Share: the server creates a short link that opens a filled share page.
  if (browserName === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write'])
  const created = page.waitForResponse((r) => r.url().endsWith('/api/share') && r.status() === 200)
  await page.evaluate(() => {
    // Force the clipboard path - navigator.share opens a native sheet.
    ;(navigator as unknown as { share?: unknown }).share = undefined
  })
  await detail.getByRole('button', { name: 'Teilen' }).click()
  const { id } = await (await created).json()
  const share = await page.request.get(`/s/${id}`, { headers: { 'accept-language': 'de-DE' } })
  expect(share.status()).toBe(200)
  const html = await share.text()
  expect(html).toContain('Im Finder öffnen')
  expect(html).toMatch(/<title>[^<]*Score \d+\/100/)
})

test('a spot opens its camera flight, which shows the same score', async ({ page }) => {
  // Search, the preload behind the cover and a 20 s flight - on CI's
  // software-rendered WebGL that takes longer than the default minute.
  test.setTimeout(180_000)
  // The flight moves even when the system asks for reduced motion (Windows
  // with animation effects off does) - the motion is what the video is for.
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(FIXTURE)
  const first = page.locator('.results .result').first()
  const score = (await first.locator('.result-score').textContent())?.match(/\d+/)?.[0]
  await first.click()
  await page.locator('.detail').getByRole('link', { name: /Video/ }).click()
  await expect(page).toHaveURL(/present=spot&spot=48\.\d+,9\.\d+/)

  // Preloaded behind a cover, then waiting for the tap that starts the take.
  await expect(page.locator('.present-hint')).toHaveText('Tippen zum Starten', { timeout: 60_000 })
  await expect(page.locator('.present-title h1')).toContainText('FPV-Spot')
  await page.locator('.present').click()
  const card = page.locator('.present-card')
  await expect(card).toBeVisible({ timeout: 20_000 })
  await expect(card.locator('.present-score')).toHaveText(score!)
  await expect(card).toContainText('dipul.de')
  await expect(page.locator('.present-outro')).toBeVisible({ timeout: 20_000 })
})

test('a place outside Germany is explained, not failed', async ({ page }) => {
  await page.goto('/app?lat=52.37&lon=4.90&r=2')
  await expect(page.getByRole('alert')).toContainText('außerhalb')
})

test('English finder speaks English', async ({ page }) => {
  await page.goto('/en/app?lat=48.4500&lon=9.4500&r=2')
  await expect(page.getByRole('heading', { name: 'Best spots' })).toBeVisible({ timeout: 30_000 })
})

test('fine-tuning sends a weight override with the next search', async ({ page }) => {
  await page.goto(FIXTURE)
  await expect(page.locator('.results .result').first()).toBeVisible({ timeout: 30_000 })
  await page.locator('details.expert > summary').click()
  await page.locator('details.tuning > summary').click()
  const slider = page.getByRole('slider', { name: /Wegen/ })
  await expect(slider).toBeVisible()
  await slider.fill('0.4')
  const request = page.waitForRequest((r) => r.url().endsWith('/api/search') && r.method() === 'POST')
  await page.getByRole('button', { name: 'Neu suchen' }).click()
  const body = (await request).postDataJSON()
  expect(body.weights.solitude.components.paths.weight).toBe(0.4)
})
