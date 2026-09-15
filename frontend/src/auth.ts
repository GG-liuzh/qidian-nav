import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, ApiError, setCsrf, setWorkspace } from './api'
import type { User } from './types'

export const useAuth = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)
  const needsSetup = ref(false)
  const registrationEnabled = ref(true)
  const recoveryCode = ref('')
  const contextKey = computed(
    () =>
      `${user.value?.id || 'guest'}:${user.value?.workspace?.id || 'personal'}:${user.value?.role || ''}:${user.value?.is_superadmin || false}`,
  )
  function accept(value: User) {
    const { recovery_code, ...profile } = value
    user.value = profile
    if (recovery_code) recoveryCode.value = recovery_code
    setCsrf(value.csrf_token)
    setWorkspace(value.workspace?.id || '')
    ready.value = true
    needsSetup.value = false
    applyTheme()
  }
  function clear() {
    user.value = null
    recoveryCode.value = ''
    setCsrf('')
    setWorkspace('')
    window.dispatchEvent(new Event('clear-secrets'))
  }
  async function load() {
    const status = await api<{ needs_setup: boolean; registration_enabled: boolean }>('/setup/status')
    needsSetup.value = status.needs_setup
    registrationEnabled.value = status.registration_enabled
    if (!needsSetup.value) {
      try {
        accept(await api<User>('/me'))
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error
      }
    }
    ready.value = true
  }
  async function refresh() {
    if (!user.value) return
    try {
      accept(await api<User>('/me'))
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) clear()
      else throw error
    }
  }
  async function selectWorkspace(id: string) {
    window.dispatchEvent(new Event('clear-secrets'))
    accept(await api<User>(`/workspaces/${id}/select`, 'POST'))
  }
  function applyTheme() {
    const preference = user.value?.preferences.theme || 'system'
    document.documentElement.dataset.theme =
      preference === 'system'
        ? matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
        : preference
  }
  async function savePreferences(values: Partial<User['preferences']> & { display_name?: string }) {
    const result = await api<{ preferences: User['preferences']; display_name: string }>(
      '/me/preferences',
      'PATCH',
      values,
    )
    if (user.value) {
      user.value.preferences = { ...user.value.preferences, ...result.preferences }
      user.value.display_name = result.display_name
      applyTheme()
    }
  }
  return {
    user,
    ready,
    needsSetup,
    registrationEnabled,
    recoveryCode,
    contextKey,
    accept,
    clear,
    load,
    refresh,
    selectWorkspace,
    applyTheme,
    savePreferences,
  }
})
