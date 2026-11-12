import { CalendarDate } from '@internationalized/date'
import { describe, expect, it } from 'vitest'

import { dateEntryError, isSameDateEntry, readDateEntry } from './dateEntry'

const literal = { type: 'literal', isPlaceholder: false } as const

function segments(day: number | null, month: number | null, year: number | null) {
  return [
    { type: 'day', value: day, isPlaceholder: day === null },
    literal,
    { type: 'month', value: month, isPlaceholder: month === null },
    literal,
    { type: 'year', value: year, isPlaceholder: year === null },
  ] as const
}

describe('readDateEntry', () => {
  it('reads an untouched field as empty', () => {
    expect(readDateEntry(segments(null, null, null))).toEqual({ status: 'empty' })
  })

  it('reads a field with any segment left blank as incomplete', () => {
    expect(readDateEntry(segments(14, null, null))).toEqual({ status: 'incomplete' })
    expect(readDateEntry(segments(14, 10, null))).toEqual({ status: 'incomplete' })
    expect(readDateEntry(segments(null, 10, 2026))).toEqual({ status: 'incomplete' })
  })

  it('reads a day past the end of its month as nonexistent', () => {
    expect(readDateEntry(segments(31, 2, 2026))).toEqual({ status: 'nonexistent' })
    expect(readDateEntry(segments(29, 2, 2027))).toEqual({ status: 'nonexistent' })
    expect(readDateEntry(segments(31, 4, 2026))).toEqual({ status: 'nonexistent' })
  })

  it('reads a full date', () => {
    expect(readDateEntry(segments(29, 2, 2028))).toEqual({
      status: 'complete',
      date: new CalendarDate(2028, 2, 29),
    })
  })
})

describe('isSameDateEntry', () => {
  it('compares complete entries by date', () => {
    expect(
      isSameDateEntry(
        { status: 'complete', date: new CalendarDate(2026, 10, 14) },
        { status: 'complete', date: new CalendarDate(2026, 10, 14) },
      ),
    ).toBe(true)
    expect(
      isSameDateEntry(
        { status: 'complete', date: new CalendarDate(2026, 10, 14) },
        { status: 'complete', date: new CalendarDate(2026, 10, 15) },
      ),
    ).toBe(false)
  })

  it('compares other entries by status', () => {
    expect(isSameDateEntry({ status: 'incomplete' }, { status: 'incomplete' })).toBe(true)
    expect(isSameDateEntry({ status: 'incomplete' }, { status: 'nonexistent' })).toBe(false)
    expect(
      isSameDateEntry(
        { status: 'empty' },
        { status: 'complete', date: new CalendarDate(2026, 1, 1) },
      ),
    ).toBe(false)
  })
})

describe('dateEntryError', () => {
  it('names what is missing in an incomplete date', () => {
    expect(dateEntryError({ status: 'incomplete' })).toBe(
      'Введите дату полностью: день, месяц и год.',
    )
  })

  it('points at the day and month of a nonexistent date', () => {
    expect(dateEntryError({ status: 'nonexistent' })).toBe(
      'Такой даты нет. Проверьте день и месяц.',
    )
  })

  it('accepts an empty field and a full date', () => {
    expect(dateEntryError({ status: 'empty' })).toBeUndefined()
    expect(
      dateEntryError({ status: 'complete', date: new CalendarDate(2026, 10, 19) }),
    ).toBeUndefined()
  })
})
