const colorFunctions = [
  'rgb',
  'rgba',
  'hsl',
  'hsla',
  'hwb',
  'lab',
  'lch',
  'oklab',
  'oklch',
  'color',
  'color-mix',
]
const gradientFunctions = ['/gradient$/']

// Only transform, opacity and color may animate; a transition item starts with its property.
const layoutTransition =
  '/(?:^|,)\\s*(?:all|(?:min-|max-)?(?:width|height)|(?:inline|block)-size|margin|padding)\\b/'

/** @type {import('stylelint').Config} */
export default {
  extends: ['stylelint-config-standard', 'stylelint-config-css-modules'],
  reportDescriptionlessDisables: true,
  reportInvalidScopeDisables: true,
  reportNeedlessDisables: true,
  rules: {
    // Class names are read in TypeScript as styles.className.
    'selector-class-pattern': [
      '^[a-z][a-zA-Z0-9]*$',
      { message: (selector) => `Expected class selector "${selector}" to be camelCase` },
    ],
    'color-no-hex': true,
    'color-named': 'never',
    'function-disallowed-list': [...colorFunctions, ...gradientFunctions],
    // Lengths and durations come from tokens; percentages, grid fractions and angles are not design values.
    'declaration-property-unit-allowed-list': { '/.*/': ['%', 'fr', 'deg'] },
    'declaration-property-value-allowed-list': {
      'font-family': ['var(--font-sans)', 'inherit'],
      font: ['inherit'],
      'font-size': ['/^var\\(--text-[a-z-]+-size\\)$/', 'inherit'],
      'font-weight': ['400', '600', 'inherit'],
      'line-height': ['/^var\\(--text-[a-z-]+-line\\)$/', 'inherit'],
      'z-index': ['/^var\\(--z-[a-z]+\\)$/', 'auto'],
    },
    'declaration-property-value-disallowed-list': {
      'text-transform': ['uppercase'],
      '/^transition/': [layoutTransition],
    },
    'property-disallowed-list': ['/backdrop-filter$/'],
    'rule-selector-property-disallowed-list': {
      '/^(?:from|to|[\\d.]+%)$/': [
        '/^(?:min-|max-)?(?:width|height)$/',
        '/^(?:inline|block)-size$/',
        '/^margin/',
        '/^padding/',
      ],
    },
    'media-feature-name-value-allowed-list': { width: ['767px', '1360px'] },
  },
  overrides: [
    {
      files: ['src/shared/styles/tokens.css'],
      rules: {
        'color-no-hex': null,
        'custom-property-empty-line-before': null,
        'function-disallowed-list': gradientFunctions,
        'declaration-property-unit-allowed-list': null,
      },
    },
    {
      // @font-face descriptors name the family and its weight range, not values used in styles.
      files: ['src/shared/styles/fonts.css'],
      rules: { 'declaration-property-value-allowed-list': null },
    },
  ],
}
