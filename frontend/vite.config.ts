import path from 'node:path'

import babel from '@rolldown/plugin-babel'
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import { playwright } from '@vitest/browser-playwright'
import { defineConfig } from 'vitest/config'
import type { BrowserConfigOptions } from 'vitest/node'

// Vitest names the instances after their project, so each project needs its own copy.
const chromium = (): BrowserConfigOptions => ({
  enabled: true,
  provider: playwright(),
  headless: true,
  instances: [{ browser: 'chromium' }],
})

export default defineConfig({
  plugins: [react(), babel({ presets: [reactCompilerPreset()] })],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          include: ['src/**/*.test.ts', '*.test.ts'],
          environment: 'node',
          // Vitest empties every CSS request it does not process, including `?raw` text imports.
          css: { include: [/\.css\?raw$/] },
          // A zone west of UTC turns a date shifted by the local offset into the wrong day.
          env: { TZ: 'America/New_York' },
        },
      },
      {
        extends: true,
        test: {
          name: 'browser',
          include: ['src/**/*.test.tsx'],
          browser: chromium(),
        },
      },
      {
        extends: true,
        plugins: [storybookTest({ configDir: path.join(import.meta.dirname, '.storybook') })],
        test: {
          name: 'storybook',
          browser: chromium(),
        },
      },
    ],
  },
})
