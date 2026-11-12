import { type Ref, use } from 'react'
import {
  Input,
  SearchField as AriaSearchField,
  type SearchFieldProps as AriaSearchFieldProps,
} from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import { FieldLabel, fieldStyles } from '../Field/Field'
import { FormGroupDisabledContext } from '../Form/formGroupContext'
import { IconButton } from '../IconButton/IconButton'
import { SearchIcon, XIcon } from '../icons/icons'
import classes from './SearchField.module.css'

const styles = pickClasses(classes, 'group')

export type SearchFieldProps = Omit<
  AriaSearchFieldProps,
  'children' | 'className' | 'style' | 'isInvalid' | 'validate' | 'validationBehavior'
> & {
  /** Stays visible: without it the field loses its meaning once it holds text. */
  label: string
  /** Lists what the search covers, for example «ФИО, email, должность или отдел». */
  placeholder: string
  /** Points at the input, so a form can move focus to the field. */
  ref?: Ref<HTMLInputElement>
}

export function SearchField({
  label,
  placeholder,
  isDisabled = false,
  ref,
  ...props
}: SearchFieldProps) {
  const isGroupDisabled = use(FormGroupDisabledContext)

  return (
    <AriaSearchField
      {...props}
      className={fieldStyles.field}
      isDisabled={isDisabled || isGroupDisabled}
    >
      {({ isEmpty }) => (
        <>
          <FieldLabel>{label}</FieldLabel>
          <div className={styles.group} data-empty={isEmpty || undefined}>
            <SearchIcon />
            <Input ref={ref} className={fieldStyles.input} placeholder={placeholder} />
            {/* Out of the tab order by React Aria's design: Escape clears from the keyboard. */}
            {!isEmpty && (
              <IconButton aria-label="Очистить поиск">
                <XIcon />
              </IconButton>
            )}
          </div>
        </>
      )}
    </AriaSearchField>
  )
}
