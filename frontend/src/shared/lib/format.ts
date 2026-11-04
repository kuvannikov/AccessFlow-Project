const LOCALE = 'ru-RU'

// The API sends calendar dates as `YYYY-MM-DD`, which JavaScript parses as UTC
// midnight; formatting in the local zone would show the previous day west of UTC.
const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  timeZone: 'UTC',
})
const numberFormat = new Intl.NumberFormat(LOCALE)
const pluralRules = new Intl.PluralRules(LOCALE)

export interface PluralForms {
  one: string
  few: string
  many: string
}

/** Formats a `YYYY-MM-DD` date as `ДД.ММ.ГГГГ`. */
export function formatDate(isoDate: string): string {
  return dateFormat.format(new Date(isoDate))
}

/** Formats a number with non-breaking spaces between digit groups: `1 284`. */
export function formatNumber(value: number): string {
  return numberFormat.format(value)
}

/** Picks the word form that agrees with `count`: 1 сотрудник, 3 сотрудника, 5 сотрудников. */
export function pluralize(count: number, forms: PluralForms): string {
  switch (pluralRules.select(count)) {
    case 'one':
      return forms.one
    case 'many':
      return forms.many
    default:
      // Russian fractions (category `other`) agree like `few`: 1,5 сотрудника.
      return forms.few
  }
}
