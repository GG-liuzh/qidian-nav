<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import { roleNames, type Role, type User } from '../types'
import Sheet from './Sheet.vue'
import Icon from './Icon.vue'
import RoleHelp from './RoleHelp.vue'

const emit = defineEmits<{ close: []; administration: [] }>()
const auth = useAuth(),
  router = useRouter(),
  busy = ref(false),
  error = ref(''),
  invitation = ref('')
const preview = ref<{ name: string; role: Role; expires_at: string; remaining_uses: number | null } | null>(
  null,
)
function token() {
  const value = invitation.value.trim()
  const match = value.match(/[?&]token=([^&]+)/)
  return match ? decodeURIComponent(match[1]) : value
}
async function select(id: string) {
  busy.value = true
  error.value = ''
  try {
    await auth.selectWorkspace(id)
    emit('close')
    await router.replace('/team')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function inspect() {
  busy.value = true
  error.value = ''
  preview.value = null
  try {
    preview.value = await api('/auth/invitation-info', 'POST', { token: token() })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function join() {
  busy.value = true
  error.value = ''
  try {
    auth.accept(await api<User>('/auth/join', 'POST', { token: token() }))
    invitation.value = ''
    emit('close')
    await router.replace('/team')
    notify('已加入空间，个人资料仍归你自己。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <Sheet :open="true" title="我的空间" description="一个个人账号 · 多个协作空间" @close="emit('close')">
    <p class="drawer-intro">切换空间时，目录、链接和你的角色一起切换。个人导航始终属于同一个账号。</p>
    <div v-if="error" class="form-error" role="alert">{{ error }}</div>
    <div class="management-list">
      <div v-for="workspace in auth.user?.workspaces || []" :key="workspace.id" class="management-row">
        <div>
          <strong>{{ workspace.name }}</strong
          ><small
            >{{ roleNames[workspace.role]
            }}{{ auth.user?.workspace?.id === workspace.id ? ' · 当前空间' : '' }}</small
          >
        </div>
        <button
          class="button secondary compact"
          :disabled="busy || auth.user?.workspace?.id === workspace.id"
          @click="select(workspace.id)"
        >
          进入空间
        </button>
      </div>
      <p v-if="!auth.user?.workspaces.length" class="inline-empty">
        你还没有加入空间，可以继续使用个人导航，或在下方接受邀请。
      </p>
    </div>
    <form class="inline-form" @submit.prevent="inspect">
      <h3>加入已有空间</h3>
      <p class="form-help">已经注册也可以加入。粘贴管理员给你的邀请链接或令牌，无需再注册一个账号。</p>
      <label class="form-group"
        >邀请链接或令牌<input
          v-model="invitation"
          class="form-field"
          required
          autocomplete="off"
          @input="preview = null" /></label
      ><button class="button secondary" :disabled="busy">查看邀请</button>
    </form>
    <section v-if="preview" class="notice-panel">
      <h3>{{ preview.name }}</h3>
      <p>加入后角色：{{ roleNames[preview.role] }}</p>
      <p class="form-help">
        {{ new Date(preview.expires_at).toLocaleString() }} 到期 ·
        {{ preview.remaining_uses === null ? '有效期内不限次数' : `还可使用 ${preview.remaining_uses} 次` }}
      </p>
      <RoleHelp :selected="preview.role" /><button class="button primary" :disabled="busy" @click="join">
        确认加入这个空间
      </button>
    </section>
    <button v-if="auth.user?.is_superadmin" class="button secondary" @click="emit('administration')">
      <Icon name="settings" />管理或创建空间
    </button>
  </Sheet>
</template>
