import { createContext } from 'react'

/**
 * A disabled fieldset blocks native inputs only: React Aria fields keep their own
 * disabled state, and date segments stay editable, so the group passes it on.
 */
export const FormGroupDisabledContext = createContext(false)
