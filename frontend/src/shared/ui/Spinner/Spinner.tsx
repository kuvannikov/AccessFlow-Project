import { pickClasses } from '../../styles/pickClasses'
import classes from './Spinner.module.css'

const styles = pickClasses(classes, 'spinner')

export interface SpinnerProps {
  size?: 'md' | 'sm'
  /** Colors for a spinner inside a pending action button. */
  isOnAction?: boolean
}

/** A busy ring. The text of the process next to it carries the meaning. */
export function Spinner({ size = 'md', isOnAction = false }: SpinnerProps) {
  return (
    <span
      className={styles.spinner}
      data-size={size}
      data-on-action={isOnAction || undefined}
      aria-hidden="true"
    />
  )
}
