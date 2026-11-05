import type { ReactNode } from 'react'

import { pickClasses } from '../../styles/pickClasses'
import classes from './icons.module.css'

const styles = pickClasses(classes, 'icon')

// Paths are copied from Lucide 0.468.0, see LICENSE in this folder.
function Icon({ children }: { children: ReactNode }) {
  return (
    <svg className={styles.icon} viewBox="0 0 24 24" aria-hidden="true">
      {children}
    </svg>
  )
}

export function ChevronLeftIcon() {
  return (
    <Icon>
      <path d="m15 18-6-6 6-6" />
    </Icon>
  )
}

export function LogOutIcon() {
  return (
    <Icon>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" x2="9" y1="12" y2="12" />
    </Icon>
  )
}

export function MenuIcon() {
  return (
    <Icon>
      <line x1="4" x2="20" y1="12" y2="12" />
      <line x1="4" x2="20" y1="6" y2="6" />
      <line x1="4" x2="20" y1="18" y2="18" />
    </Icon>
  )
}

export function PlusIcon() {
  return (
    <Icon>
      <path d="M5 12h14" />
      <path d="M12 5v14" />
    </Icon>
  )
}

export function RotateCwIcon() {
  return (
    <Icon>
      <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
    </Icon>
  )
}

export function XIcon() {
  return (
    <Icon>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </Icon>
  )
}
