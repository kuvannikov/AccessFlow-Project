import { describe, expect, test } from 'vitest'

import { formatDate, formatNumber, pluralize } from './format'

const NBSP = ' '

describe('formatDate', () => {
  test.each([
    ['2026-10-14', '14.10.2026'],
    ['2026-01-01', '01.01.2026'],
    ['2026-12-31', '31.12.2026'],
  ])('formats %s as %s', (isoDate, expected) => {
    expect(formatDate(isoDate)).toBe(expected)
  })
})

describe('formatNumber', () => {
  test.each([
    [7, '7'],
    [1284, `1${NBSP}284`],
    [1000000, `1${NBSP}000${NBSP}000`],
  ])('formats %i', (value, expected) => {
    expect(formatNumber(value)).toBe(expected)
  })
})

describe('pluralize', () => {
  const employees = { one: 'сотрудник', few: 'сотрудника', many: 'сотрудников' }

  test.each([
    [1, 'сотрудник'],
    [21, 'сотрудник'],
    [101, 'сотрудник'],
    [2, 'сотрудника'],
    [4, 'сотрудника'],
    [22, 'сотрудника'],
    [1284, 'сотрудника'],
    [5, 'сотрудников'],
    [11, 'сотрудников'],
    [12, 'сотрудников'],
    [14, 'сотрудников'],
    [111, 'сотрудников'],
    [128, 'сотрудников'],
    [1.5, 'сотрудника'],
  ])('uses the right form for %d', (count, expected) => {
    expect(pluralize(count, employees)).toBe(expected)
  })
})
