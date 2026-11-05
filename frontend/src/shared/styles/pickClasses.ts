/**
 * Picks class names from a CSS Module. Vite types a module as a dictionary, so a
 * misspelled name would only leave an element unstyled; here it fails on import.
 */
export function pickClasses<const Name extends string>(
  module: CSSModuleClasses,
  ...names: Name[]
): Record<Name, string> {
  const classes: Partial<Record<Name, string>> = {}
  for (const name of names) {
    const value = module[name]
    if (value === undefined) {
      throw new Error(`Class "${name}" is not defined in the CSS Module`)
    }
    classes[name] = value
  }
  return classes as Record<Name, string>
}
