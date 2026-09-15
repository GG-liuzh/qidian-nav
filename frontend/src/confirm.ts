import { shallowRef } from 'vue'

interface Confirmation {
  title: string
  message: string
  confirmText: string
  danger: boolean
}
export const confirmation = shallowRef<Confirmation | null>(null)
let resolveCurrent: ((accepted: boolean) => void) | undefined

export function finishConfirmation(accepted: boolean) {
  const resolve = resolveCurrent
  resolveCurrent = undefined
  confirmation.value = null
  resolve?.(accepted)
}

export function confirmAction(message: string, options: Partial<Omit<Confirmation, 'message'>> = {}) {
  finishConfirmation(false)
  confirmation.value = { title: '确认操作', message, confirmText: '确认', danger: false, ...options }
  return new Promise<boolean>((resolve) => { resolveCurrent = resolve })
}
