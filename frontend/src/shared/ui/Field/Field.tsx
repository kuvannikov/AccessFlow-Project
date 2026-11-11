import type { ReactNode } from 'react'
import { FieldError, Label, Text } from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import { CircleAlertIcon } from '../icons/icons'
import classes from './Field.module.css'

export const fieldStyles = pickClasses(classes, 'field', 'input')

const styles = pickClasses(classes, 'label', 'optional', 'description', 'error')

export function FieldLabel({
  children,
  isOptional = false,
}: {
  children: string
  isOptional?: boolean
}) {
  return (
    <Label className={styles.label}>
      {children}
      {isOptional && (
        <>
          {' '}
          <span className={styles.optional}>(необязательно)</span>
        </>
      )}
    </Label>
  )
}

export function FieldDescription({ children, role }: { children: ReactNode; role?: 'status' }) {
  return (
    <Text slot="description" className={styles.description} role={role}>
      {children}
    </Text>
  )
}

/** Rendered by React Aria only while the field is invalid. */
export function FieldErrorMessage({ children }: { children: string }) {
  return (
    <FieldError className={styles.error}>
      <CircleAlertIcon />
      <span>{children}</span>
    </FieldError>
  )
}
