import { defineConfig, devices } from '@playwright/test'

// Runs against a server that is already up (see .github/workflows/ci.yml):
// the real backend serving web/dist, on a fixture OSM store.
//
// Locally an installed Edge can stand in for Playwright's Chromium:
// PW_CHANNEL=msedge. It only applies to the Chromium projects.
const chromiumChannel = process.env.PW_CHANNEL || undefined

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8000',
    locale: 'de-DE',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'android', use: { ...devices['Pixel 7'], channel: chromiumChannel } },
    // Safari on iPhone - much of the TikTok audience.
    { name: 'iphone', use: { ...devices['iPhone 13'] } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 }, channel: chromiumChannel } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'], viewport: { width: 1440, height: 900 } } },
  ],
})
