<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../auth'
import { api, errorMessage, notify } from '../api'
import type { Role, User } from '../types'
import Icon from '../components/Icon.vue'
import RoleHelp from '../components/RoleHelp.vue'
import { roleNames } from '../types'

const route = useRoute(),
  router = useRouter(),
  auth = useAuth()
const mode = computed(() => route.path.slice(1))
const existingJoin = computed(() => mode.value === 'join' && !!auth.user)
const invitationInfo = ref<{ name: string; role: Role } | null>(null)
const title = computed(
  () =>
    ({
      setup: '创建我的导航',
      signup: '创建个人账号',
      join: '加入团队',
      reset: '找回个人账号',
      'account-reset': '设置新的登录密码',
      login: '欢迎回到栖点',
    })[mode.value] || '登录栖点',
)
const username = ref(''),
  password = ref(''),
  displayName = ref(''),
  workspaceName = ref(''),
  token = ref(String(route.query.token || '')),
  recovery = ref(''),
  remember = ref(false),
  publicEnabled = ref(true)
const error = ref(''),
  busy = ref(false)
watch(
  () => route.query.token,
  (value) => {
    token.value = String(value || '')
  },
)
watch(mode, () => {
  error.value = ''
  password.value = ''
  recovery.value = ''
})
watch(
  [mode, token],
  async () => {
    invitationInfo.value = null
    if (mode.value === 'join' && token.value.length >= 20) {
      try {
        invitationInfo.value = await api('/auth/invitation-info', 'POST', { token: token.value })
      } catch (e) {
        error.value = errorMessage(e)
      }
    }
  },
  { immediate: true },
)
async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (mode.value === 'reset' || mode.value === 'account-reset') {
      const result = await api<{ recovery_code: string }>(
        mode.value === 'account-reset' ? '/auth/reset-token' : '/auth/reset',
        'POST',
        mode.value === 'account-reset'
          ? { token: token.value, password: password.value }
          : {
              username: username.value.trim(),
              password: password.value,
              recovery_code: recovery.value,
            },
      )
      password.value = ''
      recovery.value = ''
      auth.clear()
      auth.recoveryCode = result.recovery_code
      notify('密码已更新，请保存新的恢复码，再重新登录。')
      await router.replace('/login')
      return
    }
    if (existingJoin.value) {
      auth.accept(await api<User>('/auth/join', 'POST', { token: token.value }))
      token.value = ''
      await router.replace('/team')
      return
    }
    const path =
      mode.value === 'setup'
        ? '/setup'
        : mode.value === 'signup' || mode.value === 'join'
          ? '/auth/register'
          : '/auth/login'
    const payload = {
      username: username.value.trim(),
      password: password.value,
      remember_me: remember.value,
      ...(mode.value !== 'login' ? { display_name: displayName.value } : {}),
      ...(['join', 'setup'].includes(mode.value) ? { token: token.value } : {}),
      ...(mode.value === 'setup'
        ? {
            workspace_name: workspaceName.value,
            public_enabled: !!workspaceName.value && publicEnabled.value,
          }
        : {}),
    }
    const back =
      typeof route.query.return === 'string' &&
      /^\/(team|personal|favorites|recent|join|u\/|$)/.test(route.query.return)
        ? route.query.return
        : ''
    const user = await api<User>(path, 'POST', payload)
    auth.accept(user)
    password.value = ''
    token.value = ''
    await router.replace(back || (user.workspace ? '/team' : '/personal'))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <main class="auth-page">
    <div class="auth-story">
      <RouterLink class="brand" to="/"
        ><span class="brand-mark"><span></span><span></span></span
        ><span class="brand-name">栖点<span>QIDIAN</span></span></RouterLink
      >
      <div class="auth-copy">
        <span class="eyebrow">A LITTLE LESS SEARCHING.</span>
        <h1>好用的入口，<br />随时都能找到<span>。</span></h1>
        <p>公开导航，打开就能用。<br />登录后整理自己的书签，也能和团队一起维护。</p>
        <div class="auth-features">
          <span><Icon name="globe" />公开内容免登录</span><span><Icon name="folder-lock" />个人资料独立</span
          ><span><Icon name="download" />自己的数据可以带走</span>
        </div>
      </div>
      <p class="muted">栖点 · 让链接有处可寻。</p>
    </div>
    <div class="auth-form-wrap">
      <form class="auth-form" @submit.prevent="submit">
        <span class="auth-symbol"><Icon :name="mode === 'setup' ? 'compass' : 'lock'" :size="28" /></span>
        <h2>{{ title }}</h2>
        <p class="muted">
          {{
            mode === 'setup'
              ? '先拥有自己的导航，部门协作可以现在或以后开启。'
              : mode === 'signup'
                ? '个人使用无需建立或加入部门空间。'
                : existingJoin
                  ? '使用当前个人账号加入团队，个人资料继续只归你所有。'
                  : mode === 'join'
                    ? '创建独立账号并接受邀请；离开团队后仍可使用个人导航。'
                    : ['reset', 'account-reset'].includes(mode)
                      ? '使用恢复码找回账号；恢复码也丢失时，可联系站点超级管理员生成重置链接。'
                      : '登录后收藏、整理和参与协作。公开链接无需登录也可浏览。'
          }}
        </p>
        <div v-if="error" class="form-error" role="alert">{{ error }}</div>
        <section v-if="invitationInfo" class="invite-summary">
          <strong>{{ invitationInfo.name }}</strong>
          <p>加入后的角色：{{ roleNames[invitationInfo.role] }}</p>
          <RoleHelp :selected="invitationInfo.role" />
        </section>
        <template v-if="!existingJoin"
          ><label v-if="['setup', 'signup', 'join'].includes(mode)" class="form-group"
            >你的姓名<input
              v-model="displayName"
              required
              maxlength="80"
              autocomplete="name"
              class="form-field" /></label
          ><label v-if="mode !== 'account-reset'" class="form-group"
            >用户名<input
              v-model="username"
              required
              minlength="2"
              maxlength="80"
              pattern="[a-zA-Z0-9_.@\-]+"
              autocomplete="username"
              placeholder="字母、数字或邮箱"
              class="form-field" /></label
          ><label class="form-group"
            >{{ mode === 'login' ? '密码' : '设置密码（至少 12 位）'
            }}<input
              v-model="password"
              type="password"
              required
              :minlength="mode === 'login' ? 1 : 12"
              maxlength="256"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              class="form-field" /></label
        ></template>
        <label v-if="mode === 'setup'" class="form-group"
          >空间名称（选填）<input
            v-model="workspaceName"
            aria-label="空间名称"
            maxlength="80"
            placeholder="个人使用可留空，例如：产品研发部"
            class="form-field"
          /><span class="form-help">填写后同时建立部门空间，由你担任管理员。</span></label
        ><label v-if="mode === 'setup' && workspaceName" class="checkbox-label"
          ><input v-model="publicEnabled" type="checkbox" />允许游客浏览明确公开的团队链接</label
        >
        <label v-if="mode === 'setup' || mode === 'join'" class="form-group"
          >{{ mode === 'setup' ? '安装令牌' : '邀请令牌'
          }}<input
            v-model="token"
            required
            autocomplete="off"
            class="form-field"
            :type="mode === 'setup' ? 'password' : 'text'"
          /><span v-if="mode === 'setup'" class="form-help"
            >由部署人员提供，用于确认首次安装权限。</span
          ></label
        >
        <label v-if="mode === 'reset'" class="form-group"
          >账户恢复码<input v-model="recovery" required autocomplete="off" class="form-field"
        /></label>
        <label v-if="!existingJoin && !['reset', 'account-reset'].includes(mode)" class="checkbox-label"
          ><input v-model="remember" type="checkbox" />在这台设备保持登录 30 天</label
        >
        <button class="button primary full-width" :disabled="busy">
          {{
            busy
              ? '正在处理…'
              : mode === 'setup'
                ? '创建并进入'
                : mode === 'signup'
                  ? '创建个人账号'
                  : mode === 'join'
                    ? '加入团队'
                    : ['reset', 'account-reset'].includes(mode)
                      ? '更新密码'
                      : '登录'
          }}<Icon name="arrow" />
        </button>
        <div class="auth-links">
          <RouterLink to="/">直接浏览公开导航</RouterLink
          ><RouterLink v-if="mode === 'login' && auth.registrationEnabled" to="/signup"
            >创建个人账号</RouterLink
          ><RouterLink v-if="mode === 'login'" to="/reset">忘记密码</RouterLink
          ><RouterLink
            v-if="!['login', 'setup'].includes(mode)"
            :to="mode === 'join' ? { path: '/login', query: { return: route.fullPath } } : '/login'"
            >{{ mode === 'join' ? '已有账号，先登录' : '返回登录' }}</RouterLink
          >
        </div>
      </form>
    </div>
  </main>
</template>
