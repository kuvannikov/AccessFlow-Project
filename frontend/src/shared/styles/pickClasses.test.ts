import { describe, expect, it } from 'vitest'

import { pickClasses } from './pickClasses'

describe('pickClasses', () => {
  const module = { button: 'Button_button_x1', label: 'Button_label_x2' }

  it('returns the requested classes', () => {
    expect(pickClasses(module, 'button')).toEqual({ button: 'Button_button_x1' })
  })

  it('fails on a class the module does not define', () => {
    expect(() => pickClasses(module, 'button', 'spinner')).toThrow(
      'Class "spinner" is not defined in the CSS Module',
    )
  })
})
