import { type Ref, use } from 'react'
import {
  Input,
  TextField as AriaTextField,
  type TextFieldProps as AriaTextFieldProps,
} from 'react-aria-components'

import { FieldDescription, FieldErrorMessage, FieldLabel, fieldStyles } from '../Field/Field'
import { FormGroupDisabledContext } from '../Form/formGroupContext'
import { Spinner } from '../Spinner/Spinner'

export type TextFieldProps = Omit<
  AriaTextFieldProps,
  'children' | 'className' | 'style' | 'isInvalid' | 'validate' | 'validationBehavior'
> & {
  /** A noun without a colon; it stays visible, a placeholder never replaces it. */
  label: string
  isOptional?: boolean
  description?: string
  /** Takes the place of the description while a value is looked up, for example «Подбираем свободный slug…». */
  status?: string
  /** Marks the field invalid and replaces the description. */
  errorMessage?: string | undefined
  /** Points at the input, so a form can move focus to the field. */
  ref?: Ref<HTMLInputElement>
}

export function TextField({
  label,
  isOptional = false,
  description,
  status,
  errorMessage,
  isDisabled = false,
  ref,
  ...props
}: TextFieldProps) {
  const isInvalid = errorMessage !== undefined
  const isGroupDisabled = use(FormGroupDisabledContext)

  return (
    <AriaTextField
      {...props}
      className={fieldStyles.field}
      isDisabled={isDisabled || isGroupDisabled}
      isInvalid={isInvalid}
      // Forms validate with their own rules; native validation would show browser bubbles.
      validationBehavior="aria"
    >
      <FieldLabel isOptional={isOptional}>{label}</FieldLabel>
      <Input ref={ref} className={fieldStyles.input} />
      {isInvalid ? (
        <FieldErrorMessage>{errorMessage}</FieldErrorMessage>
      ) : (
        (description !== undefined || status !== undefined) && (
          // The region lives as long as the description, so a status that replaces it is announced.
          <FieldDescription role="status">
            {status === undefined ? (
              description
            ) : (
              <>
                <Spinner size="sm" />
                {status}
              </>
            )}
          </FieldDescription>
        )
      )}
    </AriaTextField>
  )
}
