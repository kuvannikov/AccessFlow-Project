import type { CalendarDate } from '@internationalized/date'
import { type Ref, use, useEffect, useId, useImperativeHandle, useRef } from 'react'
import {
  Calendar,
  CalendarCell,
  CalendarGrid,
  CalendarGridBody,
  CalendarGridHeader,
  CalendarHeaderCell,
  DateFieldStateContext,
  DateInput,
  DatePicker,
  type DatePickerProps,
  DateSegment,
  Dialog,
  Group,
  Heading,
  Popover,
  useLocale,
} from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import { FieldDescription, FieldErrorMessage, FieldLabel, fieldStyles } from '../Field/Field'
import { FormGroupDisabledContext } from '../Form/formGroupContext'
import { IconButton } from '../IconButton/IconButton'
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from '../icons/icons'
import classes from './DateField.module.css'
import { type DateEntry, isSameDateEntry, readDateEntry } from './dateEntry'

const styles = pickClasses(
  classes,
  'group',
  'input',
  'segment',
  'popover',
  'calendar',
  'header',
  'title',
  'grid',
  'day',
)

// The design keeps the calendar --space-1 below the field; React Aria takes the offset in pixels.
const POPOVER_OFFSET = 4

export type DateFieldProps = Omit<
  DatePickerProps<CalendarDate>,
  | 'children'
  | 'className'
  | 'style'
  | 'isInvalid'
  | 'validate'
  | 'validationBehavior'
  | 'value'
  | 'onChange'
  | 'granularity'
  | 'hourCycle'
  | 'hideTimeZone'
  | 'shouldForceLeadingZeros'
> & {
  label: string
  isOptional?: boolean
  description?: string
  /** Marks the field invalid and replaces the description. */
  errorMessage?: string | undefined
  onChange?: (entry: DateEntry) => void
  /** Focuses the first segment, where typing starts. */
  ref?: Ref<{ focus: () => void }>
}

export function DateField({
  label,
  isOptional = false,
  description,
  errorMessage,
  onChange,
  isDisabled = false,
  ref,
  ...props
}: DateFieldProps) {
  const isInvalid = errorMessage !== undefined
  const isGroupDisabled = use(FormGroupDisabledContext)
  const inputRef = useRef<HTMLDivElement>(null)
  const dialogTitleId = useId()
  const lastEntry = useRef<DateEntry>(
    props.defaultValue ? { status: 'complete', date: props.defaultValue } : { status: 'empty' },
  )

  useImperativeHandle(ref, () => ({
    focus: () => inputRef.current?.querySelector<HTMLElement>('[role="spinbutton"]')?.focus(),
  }))

  const reportEntry = (entry: DateEntry) => {
    if (!isSameDateEntry(entry, lastEntry.current)) {
      lastEntry.current = entry
      onChange?.(entry)
    }
  }

  return (
    <DatePicker
      {...props}
      className={fieldStyles.field}
      isDisabled={isDisabled || isGroupDisabled}
      isInvalid={isInvalid}
      // Forms validate with their own rules; native validation would show browser bubbles.
      validationBehavior="aria"
    >
      <FieldLabel isOptional={isOptional}>{label}</FieldLabel>
      <Group className={styles.group}>
        <DateInput ref={inputRef} className={styles.input}>
          {(segment) =>
            segment.type === 'day' ? (
              <>
                <DateSegment segment={segment} className={styles.segment} />
                <DateEntryObserver onEntry={reportEntry} />
              </>
            ) : (
              <DateSegment segment={segment} className={styles.segment} />
            )
          }
        </DateInput>
        <IconButton aria-label="Открыть календарь">
          <CalendarIcon />
        </IconButton>
      </Group>
      {isInvalid ? (
        <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      ) : (
        description !== undefined && <FieldDescription>{description}</FieldDescription>
      )}
      <Popover className={styles.popover} placement="bottom start" offset={POPOVER_OFFSET}>
        {/* React Aria names the dialog after its trigger button, which reads as a command. */}
        <Dialog aria-labelledby={dialogTitleId}>
          <span id={dialogTitleId} hidden>
            Календарь: {label}
          </span>
          <Calendar className={styles.calendar}>
            {({ state }) => (
              <>
                <header className={styles.header}>
                  <MonthTitle month={state.visibleRange.start} timeZone={state.timeZone} />
                  <IconButton slot="previous" aria-label="Предыдущий месяц">
                    <ChevronLeftIcon />
                  </IconButton>
                  <IconButton slot="next" aria-label="Следующий месяц">
                    <ChevronRightIcon />
                  </IconButton>
                </header>
                <CalendarGrid className={styles.grid} weekdayStyle="short">
                  <CalendarGridHeader>
                    {(weekday) => <CalendarHeaderCell>{weekday}</CalendarHeaderCell>}
                  </CalendarGridHeader>
                  <CalendarGridBody>
                    {(date) => <CalendarCell date={date} className={styles.day} />}
                  </CalendarGridBody>
                </CalendarGrid>
              </>
            )}
          </Calendar>
        </Dialog>
      </Popover>
    </DatePicker>
  )
}

/**
 * The segments' state is only reachable inside DateInput, so the entry is read there.
 * It is mounted next to the day segment, which a date always has exactly once.
 */
function DateEntryObserver({ onEntry }: { onEntry: (entry: DateEntry) => void }) {
  const state = use(DateFieldStateContext)
  const segments = state?.segments

  useEffect(() => {
    if (segments) {
      onEntry(readDateEntry(segments))
    }
  }, [segments, onEntry])

  return null
}

/** «Октябрь 2026»: the library's own heading reads «октябрь 2026 г.». */
function MonthTitle({ month, timeZone }: { month: CalendarDate; timeZone: string }) {
  const { locale } = useLocale()
  const name = new Intl.DateTimeFormat(locale, { month: 'long', timeZone }).format(
    month.toDate(timeZone),
  )

  return (
    <Heading className={styles.title}>
      {name.charAt(0).toLocaleUpperCase(locale) + name.slice(1)} {month.year}
    </Heading>
  )
}
