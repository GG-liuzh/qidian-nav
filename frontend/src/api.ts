import { ref } from 'vue'

let csrf = ''
let workspaceId = ''
export function setWorkspace(value: string) { workspaceId = value }
export function setCsrf(value: string) {
  csrf = value
}
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: Record<string, unknown>,
  ) {
    super(message)
  }
}
export async function api<T = unknown>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'same-origin',
    headers: {
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
      ...(workspaceId ? { 'X-Workspace-ID': workspaceId } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => ({ detail: '服务器响应异常，请稍后重试。' }))
  if (!response.ok) {
    if (response.status === 401 && csrf) window.dispatchEvent(new Event('session-expired'))
    const message =
      typeof data.detail === 'string' ? data.detail : data.detail?.message || '操作失败，请稍后重试。'
    throw new ApiError(
      response.status,
      data.errors?.length
        ? `${message} ${data.errors.map((e: { msg: string }) => e.msg).join(' ')}`
        : message,
      data.detail,
    )
  }
  return data as T
}
export const notification = ref('')
let notificationTimer: ReturnType<typeof setTimeout>
export function notify(message: string) {
  notification.value = message
  clearTimeout(notificationTimer)
  notificationTimer = setTimeout(() => {
    notification.value = ''
  }, 4200)
}
export function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : '操作失败，请重试。'
}
export function hostname(url: string) {
  try {
    return new URL(url).host
  } catch {
    return url
  }
}
