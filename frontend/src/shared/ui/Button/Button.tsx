import type { ReactNode } from 'react'
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import classes from './Button.module.css'

const styles = pickClasses(classes, 'button', 'label', 'spinner')

type PendingProps =
  | { isPending?: never; pendingLabel?: never }
  | {
      isPending: boolean
      /** Shown with a spinner while the action runs, for example «Сохраняем…». */
      pendingLabel: string
    }

type VariantProps =
  | ({ variant: 'primary' | 'secondary' | 'danger' } & PendingProps)
  // These variants never send anything themselves, so they have no pending state.
  | { variant: 'tertiary' | 'danger-quiet'; isPending?: never; pendingLabel?: never }

export type ButtonProps = Omit<AriaButtonProps, 'children' | 'className' | 'style' | 'isPending'> &
  VariantProps & {
    size?: 'md' | 'sm'
    children: ReactNode
  }

export function Button({
  variant,
  size = 'md',
  isPending = false,
  pendingLabel,
  children,
  ...props
}: ButtonProps) {
  return (
    <AriaButton
      {...props}
      isPending={isPending}
      className={styles.button}
      data-variant={variant}
      data-size={size}
    >
      <span className={styles.label} data-hidden={isPending || undefined}>
        {children}
      </span>
      {/* Both labels share one grid cell, so the button is as wide as the longer one. */}
      {pendingLabel !== undefined && (
        <span className={styles.label} data-hidden={!isPending || undefined}>
          <span className={styles.spinner} />
          {pendingLabel}
        </span>
      )}
    </AriaButton>
  )
}
