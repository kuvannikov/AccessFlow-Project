import { CalendarDate } from '@internationalized/date'
import type { DateSegmentProps } from 'react-aria-components'

/**
 * What the person has typed. React Aria reports no value for an incomplete or impossible
 * date, so a form could not tell either of them from an empty field.
 */
export type DateEntry =
  | { status: 'empty' }
  | { status: 'incomplete' }
  | { status: 'nonexistent' }
  | { status: 'complete'; date: CalendarDate }

type Segment = Pick<DateSegmentProps['segment'], 'type' | 'value' | 'isPlaceholder'>

export function readDateEntry(segments: readonly Segment[]): DateEntry {
  const parts = segments.filter(
    (segment) => segment.type === 'day' || segment.type === 'month' || segment.type === 'year',
  )
  const filled = parts.filter((segment) => !segment.isPlaceholder)
  if (filled.length === 0) {
    return { status: 'empty' }
  }

  const valueOf = (type: Segment['type']) =>
    filled.find((segment) => segment.type === type)?.value ?? undefined
  const day = valueOf('day')
  const month = valueOf('month')
  const year = valueOf('year')
  if (
    filled.length < parts.length ||
    day === undefined ||
    month === undefined ||
    year === undefined
  ) {
    return { status: 'incomplete' }
  }

  // CalendarDate moves a day past the end of the month back to its last day.
  const date = new CalendarDate(year, month, day)
  return date.day === day ? { status: 'complete', date } : { status: 'nonexistent' }
}

export function isSameDateEntry(a: DateEntry, b: DateEntry) {
  if (a.status === 'complete' && b.status === 'complete') {
    return a.date.compare(b.date) === 0
  }
  return a.status === b.status
}
