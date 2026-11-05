import '../src/shared/styles/fonts.css'
import '../src/shared/styles/tokens.css'
import '../src/shared/styles/base.css'

import type { Preview } from '@storybook/react-vite'

const preview: Preview = {
  beforeAll() {
    // The frame is declared English, so screen readers would read the Russian text as English.
    document.documentElement.lang = 'ru'
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
