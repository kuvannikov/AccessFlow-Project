import '../src/shared/styles/fonts.css'
import '../src/shared/styles/tokens.css'
import '../src/shared/styles/base.css'

import type { Preview } from '@storybook/react-vite'

const preview: Preview = {
  async beforeAll() {
    // The frame is declared English, so screen readers would read the Russian text as English.
    document.documentElement.lang = 'ru'
    // Text measured before the font arrives changes size when it swaps in.
    await document.fonts.load('1em "Golos Text"')
  },
  beforeEach() {
    // React Aria keeps an announcement for seven seconds, so it would outlive its story
    // and point at a button that is gone.
    return () => {
      for (const log of document.querySelectorAll('[data-live-announcer] [role="log"]')) {
        log.replaceChildren()
      }
    }
  },
  parameters: {
    a11y: {
      test: 'error',
      // axe-core runs rules that are off by default, such as target-size, only when selected.
      options: {
        runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'],
      },
    },
  },
}

export default preview
