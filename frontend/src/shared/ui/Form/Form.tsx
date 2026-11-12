import type { ReactNode } from 'react'
import { Form as AriaForm, type FormProps as AriaFormProps } from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import classes from './Form.module.css'
import { FormGroupDisabledContext } from './formGroupContext'

const styles = pickClasses(classes, 'form', 'group', 'legend', 'row', 'actions')

export type FormProps = Omit<
  AriaFormProps,
  'children' | 'className' | 'style' | 'validationBehavior' | 'validationErrors'
> & {
  children: ReactNode
  /** An error about the form as a whole; errors of single fields stay under the fields. */
  error?: ReactNode
  /** Buttons, the main one first. */
  actions: ReactNode
}

export function Form({ children, error, actions, ...props }: FormProps) {
  return (
    // The form validates with its own rules; native validation would show browser bubbles.
    <AriaForm {...props} className={styles.form} validationBehavior="aria">
      {children}
      {error}
      <div className={styles.actions}>{actions}</div>
    </AriaForm>
  )
}

export interface FormGroupProps {
  /** A noun, for example «Личные данные»; groups are not numbered. */
  legend: string
  isDisabled?: boolean
  children: ReactNode
}

export function FormGroup({ legend, isDisabled = false, children }: FormGroupProps) {
  return (
    <fieldset className={styles.group} disabled={isDisabled}>
      <legend className={styles.legend}>{legend}</legend>
      <FormGroupDisabledContext value={isDisabled}>{children}</FormGroupDisabledContext>
    </fieldset>
  )
}

/** Puts short related fields side by side; on a narrow screen they stack. */
export function FormRow({ children }: { children: ReactNode }) {
  return <div className={styles.row}>{children}</div>
}
