import type { ReactNode } from 'react'
import { Button as AriaButton, type ButtonProps as AriaButtonProps } from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import classes from './IconButton.module.css'

const styles = pickClasses(classes, 'iconButton')

export type IconButtonProps = Omit<
  AriaButtonProps,
  'children' | 'className' | 'style' | 'isPending' | 'aria-label'
> & {
  /** Names the action, because the icon has no text. */
  'aria-label': string
  /** Switches colors and the focus ring for the inverse surface. */
  isInverse?: boolean
  children: ReactNode
}

export function IconButton({ isInverse = false, ...props }: IconButtonProps) {
  return (
    <AriaButton {...props} className={styles.iconButton} data-inverse={isInverse || undefined} />
  )
}
