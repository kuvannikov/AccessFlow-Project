import { expect } from 'storybook/test'

/** Resolves a color token to the rgb() string that computed styles report. */
export function tokenColor(token: string) {
  const probe = document.createElement('span')
  probe.style.color = `var(${token})`
  document.body.append(probe)
  const { color } = getComputedStyle(probe)
  probe.remove()
  return color
}

export async function expectFocusRing(element: Element, colorToken = '--focus-ring') {
  await expect(element).toHaveFocus()
  await expect(element.matches(':focus-visible')).toBe(true)
  await expect(element).toHaveStyle({
    outlineStyle: 'solid',
    outlineWidth: getComputedStyle(document.documentElement).getPropertyValue('--ring-width'),
    outlineColor: tokenColor(colorToken),
  })
}
