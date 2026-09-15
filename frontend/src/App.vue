<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { useAuth } from './auth'
import { errorMessage, notification, notify } from './api'
import Icon from './components/Icon.vue'
import Sheet from './components/Sheet.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'

const auth = useAuth(),
  router = useRouter(),
  route = useRoute(),
  queries = useQueryClient()
const error = ref('')
const publicPaths = ['/login', '/setup', '/join', '/reset', '/account-reset', '/signup', '/']
const recoveryInput = ref<HTMLInputElement | null>(null)
async function copyRecovery() {
  try {
    await navigator.clipboard.writeText(auth.recoveryCode)
    notify('恢复码已复制，请妥善保存。')
  } catch {
    recoveryInput.value?.focus()
    recoveryInput.value?.select()
    notify('请手动复制已选中的恢复码。')
  }
}
function guard() {
  if (!auth.ready) return
  const home = auth.user?.workspace ? '/team' : '/personal'
  if (auth.needsSetup) {
    if (!['/', '/setup'].includes(route.path)) void router.replace('/setup')
    return
  }
  if (route.path === '/setup') {
    void router.replace(auth.user ? home : '/login')
    return
  }
  if (route.path === '/signup' && !auth.registrationEnabled) {
    void router.replace('/login')
    return
  }
  if (!auth.user && route.path === '/team') {
    void router.replace('/')
    return
  }
  if (
    !auth.user &&
    !publicPaths.includes(route.path) &&
    !route.path.startsWith('/u/') &&
    !route.path.startsWith('/w/')
  )
    void router.replace({ path: '/login', query: { return: route.fullPath } })
  if (auth.user && ['/login', '/signup'].includes(route.path)) {
    const back =
      typeof route.query.return === 'string' &&
      /^\/(team|personal|favorites|recent|join|u\/|$)/.test(route.query.return)
        ? route.query.return
        : home
    void router.replace(back)
  }
  if (auth.user && route.path === '/team' && !auth.user.workspace) void router.replace('/personal')
}
function expired() {
  auth.clear()
  queries.clear()
  notify('登录已过期，公开导航仍可浏览。')
  if (route.path !== '/' && !route.path.startsWith('/u/') && !route.path.startsWith('/w/'))
    void router.replace('/')
}
async function boot() {
  error.value = ''
  try {
    await auth.load()
    guard()
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function refreshSession() {
  if (!auth.user) return
  const membership = `${auth.user.workspace?.id}:${auth.user.role}`
  try {
    await auth.refresh()
    if (membership !== `${auth.user?.workspace?.id}:${auth.user?.role}`) {
      window.dispatchEvent(new Event('clear-secrets'))
      queries.clear()
      guard()
    }
  } catch (e) {
    notify(errorMessage(e))
  }
}
watch(() => [route.path, auth.user?.id, auth.user?.workspace?.id, auth.user?.role, auth.ready], guard)
const colorScheme = matchMedia('(prefers-color-scheme: dark)')
onMounted(() => {
  void boot()
  window.addEventListener('session-expired', expired)
  window.addEventListener('focus', refreshSession)
  colorScheme.addEventListener('change', auth.applyTheme)
})
onUnmounted(() => {
  window.removeEventListener('session-expired', expired)
  window.removeEventListener('focus', refreshSession)
  colorScheme.removeEventListener('change', auth.applyTheme)
})
</script>
<template>
  <div v-if="error" class="center-page">
    <Icon name="info" :size="32" />
    <h1>暂时无法连接</h1>
    <p>{{ error }}</p>
    <button class="button primary" @click="boot">重新连接</button>
  </div>
  <div v-else-if="!auth.ready" class="center-page" role="status">正在打开你的工作空间…</div>
  <RouterView v-else :key="auth.contextKey" />
  <ConfirmDialog />
  <Sheet
    v-if="auth.recoveryCode"
    :open="true"
    title="保存你的账户恢复码"
    description="个人账号 · 独立于部门"
    @close="auth.recoveryCode = ''"
    ><p>
      忘记登录密码时，可以用恢复码找回自己的账号。空间管理员不能重置你的密码；恢复码丢失时，可联系站点超级管理员生成一次性重置链接。
    </p>
    <p class="form-help">恢复码只在这里显示一次。使用后会自动换成新码，请保存在自己掌握的位置。</p>
    <label class="form-group"
      >账户恢复码<input ref="recoveryInput" class="form-field" readonly :value="auth.recoveryCode"
    /></label>
    <div class="row-actions">
      <button class="button secondary" @click="copyRecovery"><Icon name="copy" />复制恢复码</button
      ><button class="button primary" @click="auth.recoveryCode = ''">我已保存恢复码</button>
    </div></Sheet
  >
  <div v-if="notification" class="toast" role="status" aria-live="polite">
    <Icon name="check" /><span>{{ notification }}</span>
  </div>
</template>
