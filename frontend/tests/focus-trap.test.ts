import assert from 'node:assert/strict'
import { test } from 'node:test'
import { keepTabInside } from '../src/components/keepTabInside.ts'

function fixture(t: { after: (callback: () => void) => void }) {
  const previous = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const document = { activeElement: null as unknown }
  Object.defineProperty(globalThis, 'document', { configurable: true, value: document })
  t.after(() => {
    if (previous) Object.defineProperty(globalThis, 'document', previous)
    else Reflect.deleteProperty(globalThis, 'document')
  })
  const control = (visible = true, disabled = false) => ({
    tabIndex: 0,
    getClientRects: () => visible ? [{}] : [],
    matches: () => disabled,
    focus() { document.activeElement = this },
  })
  const first = control()
  const last = control()
  const controls = [control(false), first, control(true, true), last]
  const container = {
    querySelectorAll: () => controls,
    contains: (target: unknown) => controls.includes(target as typeof first),
    focus() { document.activeElement = this },
  }
  function tab(shiftKey = false) {
    let prevented = false
    keepTabInside({ key: 'Tab', shiftKey, preventDefault: () => { prevented = true } } as KeyboardEvent,
      container as unknown as HTMLElement, 'button, input')
    assert.equal(prevented, true)
  }
  return { document, first, last, controls, container, tab }
}

test('Tab and Shift+Tab wrap only through visible enabled controls', t => {
  const { document, first, last, tab } = fixture(t)
  document.activeElement = last
  tab()
  assert.equal(document.activeElement, first)
  document.activeElement = first
  tab(true)
  assert.equal(document.activeElement, last)
})

test('focus outside a dialog is brought back in either keyboard direction', t => {
  const { document, first, last, tab } = fixture(t)
  document.activeElement = null
  tab()
  assert.equal(document.activeElement, first)
  document.activeElement = null
  tab(true)
  assert.equal(document.activeElement, last)
})

test('a pending operation with all controls disabled keeps focus on the dialog', t => {
  const { document, controls, container, tab } = fixture(t)
  controls.splice(0)
  tab()
  assert.equal(document.activeElement, container)
})
