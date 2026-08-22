// The context and its hook, split from the component so the module exports only values —
// a file that mixes a component with other exports breaks React Fast Refresh.

import { createContext, useContext } from 'react'

export type Tone = 'info' | 'success' | 'error'
export type Push = (text: string, tone?: Tone) => void

export const ToastContext = createContext<Push>(() => {})

/** `toast('Diagram deleted', 'success')` from anywhere under <ToastHost>. */
export function useToast(): Push {
  return useContext(ToastContext)
}
