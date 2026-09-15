import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
const projectRoot = fileURLToPath(new URL('../', import.meta.url))
const python = resolve(
  projectRoot,
  '.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const script = resolve(projectRoot, 'scripts', 'serve_e2e.py')
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:4179',
    headless: true,
    channel: process.env.TEAM_NAV_E2E_BROWSER || undefined,
    viewport: { width: 1440, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `"${python}" "${script}"`,
    url: 'http://127.0.0.1:4179/api/v1/health',
    reuseExistingServer: false,
    timeout: 30000,
    env: { PYTHONUTF8: '1' },
  },
})
