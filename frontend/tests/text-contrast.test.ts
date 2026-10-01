import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

function color(file: string, selector: string, property = 'color') {
  const css = readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8').replace(/^@import.*$/gm, '')
  const declaration = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*(#[a-f0-9]{3,6})\\s*;`, 'i')
  const rule = Array.from(css.matchAll(/([^{}]+)\{([^{}]*)\}/g))
    .find(match => match[1].split(',').some(part => part.trim() === selector) && declaration.test(match[2]))
  assert.ok(rule, `CSS rule ${selector} is present`)
  const value = rule[2].match(declaration)?.[1]
  assert.ok(value, `${selector} defines ${property}`)
  return value.length === 4 ? `#${value.slice(1).split('').map(char => char + char).join('')}` : value
}

function luminance(color: string) {
  const channels = color.slice(1).match(/../g)!.map(channel => parseInt(channel, 16) / 255)
    .map(channel => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4)
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}

test('small text and primary buttons meet 4.5:1 contrast against their CSS backgrounds', () => {
  const page = color('styles/base.css', ':root', 'background')
  const row = color('styles/directory.css', '.employee-row', 'background')
  const drawer = color('styles/employee-form.css', '.drawer', 'background')
  const login = color('styles/login.css', '.login-page', 'background')
  const pairs = [
    ['styles/base.css', '.primary-button', color('styles/base.css', '.primary-button', 'background')],
    ['styles/base.css', '.primary-button', color('styles/base.css', '.primary-button:hover:not(:disabled)', 'background')],
    ['styles/shell.css', '.topbar-path', color('styles/shell.css', '.topbar', 'background')],
    ['styles/directory.css', '.page-intro p', page],
    ['styles/directory.css', '.summary-strip span', color('styles/directory.css', '.summary-strip', 'background')],
    ['styles/directory.css', '.section-index', page],
    ['styles/directory.css', '.directory-count', page],
    ['styles/directory.css', '.search-box input::placeholder', '#ffffff'],
    ['styles/directory.css', '.list-header', page],
    ['styles/directory.css', '.employee-person small', row],
    ['styles/directory.css', '.employee-slug', row],
    ['styles/directory.css', '.employee-date .mobile-label', row],
    ['styles/directory.css', '.list-state', row],
    ['styles/directory.css', '.main-footer', page],
    ['styles/login.css', '.login-number', login],
    ['styles/login.css', '.login-note', login],
    ['styles/login.css', '.login-action-bottom', login],
    ['styles/employee-form.css', '.drawer-kicker', drawer],
    ['styles/employee-form.css', '.drawer-intro', drawer],
    ['styles/employee-form.css', '.form-section', drawer],
    ['styles/employee-form.css', '.form-section-number', drawer],
    ['styles/employee-form.css', '.form-grid label small', drawer],
    ['styles/employee-form.css', '.form-grid input::placeholder', '#ffffff'],
    ['styles/delete-dialog.css', '.delete-dialog #delete-description span', drawer],
  ]
  for (const [file, selector, background] of pairs) {
    const foreground = color(file, selector)
    const first = luminance(foreground)
    const second = luminance(background)
    const contrast = (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05)
    assert.ok(contrast >= 4.5, `${selector}: ${contrast.toFixed(2)}:1`)
  }
})
