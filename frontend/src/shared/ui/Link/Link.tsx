import type { ReactNode } from 'react'
import { Link as AriaLink, type LinkProps as AriaLinkProps } from 'react-aria-components'

import { pickClasses } from '../../styles/pickClasses'
import classes from './Link.module.css'

const styles = pickClasses(classes, 'link')

export type LinkProps = Omit<
  AriaLinkProps,
  'children' | 'className' | 'style' | 'href' | 'isDisabled'
> & {
  // Without href, or when disabled, React Aria renders a span instead of a link.
  href: string
  /** A standalone link sits outside running text and has the full control height. */
  variant?: 'inline' | 'standalone'
  children: ReactNode
}

export function Link({ variant = 'inline', ...props }: LinkProps) {
  return <AriaLink {...props} className={styles.link} data-variant={variant} />
}
