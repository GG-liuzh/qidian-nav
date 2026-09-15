import { defineConfig } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import base from './playwright.config'

export default defineConfig(base, {
  testDir: './qa',
  outputDir: '../.runtime/qa-20260915/browser-results',
  reporter: [
    ['list'],
    [
      'json',
      { outputFile: fileURLToPath(new URL('../.runtime/qa-20260915/browser-results.json', import.meta.url)) },
    ],
  ],
  expect: { timeout: 3000 },
  use: { actionTimeout: 10000 },
})
