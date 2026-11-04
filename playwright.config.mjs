import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests-ui/browser',
  timeout: 20000,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: 2,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:8790',
    headless: true,
    trace: 'retain-on-failure',
    launchOptions: process.env.JARVIS_CHROMIUM
      ? { executablePath: process.env.JARVIS_CHROMIUM, args: ['--no-sandbox'] }
      : {},
  },
  webServer: {
    command: 'node tests-ui/serve.mjs',
    url: 'http://127.0.0.1:8790',
    reuseExistingServer: !process.env.CI,
    timeout: 10000,
  },
});
