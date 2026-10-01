export function keepTabInside(event: KeyboardEvent, container: HTMLElement | null, selector: string) {
  if (event.key !== 'Tab' || !container) return
  const controls = Array.from(container.querySelectorAll<HTMLElement>(selector))
    .filter(control => control.tabIndex >= 0 && !control.matches(':disabled') && control.getClientRects().length > 0)
  if (!controls.length) {
    event.preventDefault()
    container.focus()
    return
  }
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (!container.contains(document.activeElement)) {
    event.preventDefault()
    const target = event.shiftKey ? last : first
    target.focus()
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}
