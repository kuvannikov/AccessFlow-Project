import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, test } from 'vitest'

const DESCRIPTION = 'Внутренний инструмент HR: справочник сотрудников.'

const html = readFileSync(join(import.meta.dirname, 'index.html'), 'utf8')

function tags(name: string): Record<string, string>[] {
  return [...html.matchAll(new RegExp(`<${name}\\b([^>]*)>`, 'g'))].map(([, attributes = '']) =>
    Object.fromEntries(
      [...attributes.matchAll(/([\w:-]+)="([^"]*)"/g)].map(([, key = '', value = '']) => [
        key,
        value,
      ]),
    ),
  )
}

function meta(key: 'name' | 'property', value: string): string | undefined {
  return tags('meta').find((tag) => tag[key] === value)?.content
}

function publicFile(href: string): string {
  return join(import.meta.dirname, 'public', href)
}

test('the document is Russian and has its own title and description', () => {
  expect(tags('html')[0]?.lang).toBe('ru')
  expect(/<title>(?<title>[^<]*)<\/title>/.exec(html)?.groups?.title).toBe('AccessFlow')
  expect(meta('name', 'description')).toBe(DESCRIPTION)
  expect(meta('name', 'theme-color')).toBe('#f4f6f3')
})

test('every icon is linked and present in public', () => {
  const icons = tags('link').filter((tag) => tag.rel === 'icon' || tag.rel === 'apple-touch-icon')

  expect(icons.map((tag) => tag.href)).toEqual([
    '/favicon.ico',
    '/favicon.svg',
    '/apple-touch-icon.png',
  ])
  for (const { href = '' } of icons) expect(existsSync(publicFile(href)), href).toBe(true)
})

test('the Open Graph image exists and matches its declared size', () => {
  const image = meta('property', 'og:image') ?? ''
  const png = readFileSync(publicFile(image))

  expect(meta('property', 'og:title')).toBe('AccessFlow')
  expect(meta('property', 'og:description')).toBe(DESCRIPTION)
  expect(meta('property', 'og:image:width')).toBe(String(png.readUInt32BE(16)))
  expect(meta('property', 'og:image:height')).toBe(String(png.readUInt32BE(20)))
  expect(meta('property', 'og:image:alt')).toBeTruthy()
})
