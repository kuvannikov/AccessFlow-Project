import { expect, test } from 'vitest'

import fontsCss from './fonts.css?raw'
import tokensCss from './tokens.css?raw'

const TEXT = 4.5
const NON_TEXT = 3

function readTokens(css: string): Map<string, string> {
  const tokens = new Map<string, string>()
  for (const { groups } of css.matchAll(/(?<name>--[\w-]+):\s*(?<value>[^;]+);/g)) {
    if (groups?.name && groups.value) tokens.set(groups.name, groups.value.trim())
  }
  return tokens
}

const tokens = readTokens(tokensCss)

function resolveHex(token: string): string {
  const value = tokens.get(`--${token}`)
  if (value === undefined) throw new Error(`--${token} is not defined in tokens.css`)
  const reference = /^var\(--(?<name>[\w-]+)\)$/.exec(value)?.groups?.name
  if (reference) return resolveHex(reference)
  if (!/^#[\da-f]{6}$/i.test(value)) throw new Error(`--${token} is not a six-digit hex: ${value}`)
  return value
}

// WCAG 2.x relative luminance of an sRGB color.
function luminance(hex: string): number {
  const channel = (offset: number) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5)
}

function contrast(foreground: string, background: string): number {
  const first = luminance(resolveHex(foreground)) + 0.05
  const second = luminance(resolveHex(background)) + 0.05
  return Math.max(first, second) / Math.min(first, second)
}

function against(foreground: string, backgrounds: string[], minimum: number) {
  return backgrounds.map((background) => [foreground, background, minimum] as const)
}

const statusSurfaces = [
  'status-success-surface',
  'status-danger-surface',
  'status-warning-surface',
  'status-info-surface',
]

const declaredPairs = [
  ...against(
    'text-primary',
    ['bg-page', 'bg-surface', 'bg-sunken', 'bg-hover', 'bg-selected', ...statusSurfaces],
    TEXT,
  ),
  ...against(
    'text-secondary',
    ['bg-page', 'bg-surface', 'bg-sunken', 'bg-hover', 'bg-selected'],
    TEXT,
  ),
  ...against('text-link', ['bg-page', 'bg-surface', 'bg-hover', 'bg-selected'], TEXT),
  ...against(
    'text-on-action',
    [
      'action-primary',
      'action-primary-hover',
      'action-primary-pressed',
      'action-danger',
      'action-danger-hover',
      'action-danger-pressed',
    ],
    TEXT,
  ),
  ...against('text-on-inverse', ['bg-inverse', 'bg-inverse-hover', 'bg-inverse-selected'], TEXT),
  ...against('text-on-inverse-muted', ['bg-inverse', 'bg-inverse-hover'], TEXT),
  ...against('status-success-text', ['status-success-surface'], TEXT),
  ...against(
    'status-danger-text',
    ['status-danger-surface', 'bg-surface', 'bg-page', 'bg-hover'],
    TEXT,
  ),
  ...against('status-warning-text', ['status-warning-surface'], TEXT),
  ...against('status-info-text', ['status-info-surface'], TEXT),
  ...against('border-control', ['bg-page', 'bg-surface'], NON_TEXT),
  ...against('action-primary', ['bg-page', 'bg-surface'], NON_TEXT),
  ...against('action-danger', ['bg-page', 'bg-surface'], NON_TEXT),
  ...against(
    'focus-ring',
    ['bg-page', 'bg-surface', 'bg-sunken', 'bg-hover', ...statusSurfaces],
    NON_TEXT,
  ),
  ...against('focus-ring-inverse', ['bg-inverse', 'bg-inverse-selected'], NON_TEXT),
  ...against('status-success-border', ['bg-page'], NON_TEXT),
  ...against('status-danger-border', ['bg-page'], NON_TEXT),
  ...against('status-warning-border', ['bg-page'], NON_TEXT),
  ...against('status-info-border', ['bg-page'], NON_TEXT),
  ...against('brand-mark', ['bg-page', 'bg-inverse'], NON_TEXT),
  ...against('brand-mark-ink', ['brand-mark'], NON_TEXT),
]

test.each(declaredPairs)('%s on %s reaches %d:1', (foreground, background, minimum) => {
  expect(contrast(foreground, background)).toBeGreaterThanOrEqual(minimum)
})

test('the palette has no pure black or white', () => {
  const pure = [...tokens].filter(([, value]) => /^#(?:0{3}|0{6}|f{3}|f{6})$/i.test(value))

  expect(pure).toEqual([])
})

const bannedFamilies = [
  'inter',
  'roboto',
  'arial',
  'open sans',
  'helvetica',
  'space grotesk',
  'geist',
  'instrument serif',
  'syne',
  'fraunces',
  'dm sans',
  'plus jakarta sans',
  'manrope',
]

function familyNames(stack: string): string[] {
  return stack.split(',').map((family) =>
    family
      .trim()
      .replace(/^['"]|['"]$/g, '')
      .toLowerCase(),
  )
}

test('the font stack has no banned family and leads with the bundled face', () => {
  const stack = familyNames(tokens.get('--font-sans') ?? '')
  const bundled = [...fontsCss.matchAll(/font-family:\s*(?<name>[^;]+);/g)].flatMap(({ groups }) =>
    familyNames(groups?.name ?? ''),
  )

  expect(stack.filter((family) => bannedFamilies.includes(family))).toEqual([])
  expect(bundled).toContain(stack[0])
})
