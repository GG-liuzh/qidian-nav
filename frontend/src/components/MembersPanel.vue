<script setup lang="ts">
import { confirmAction } from '../confirm'
import { onMounted, ref } from 'vue'
import { api, errorMessage, notify } from '../api'
import { roleNames, type Member, type Role } from '../types'
import Icon from './Icon.vue'
import RoleHelp from './RoleHelp.vue'
const emit = defineEmits<{ changed: [] }>()
const existingUsername=ref(''),existingRole=ref<Role>('member')
const members = ref<Member[]>([]),
  invitations = ref<{ id: string; role: Role; expires_at: string }[]>([]),
  role = ref<Role>('member'),
  hours = ref(72),
  error = ref(''),
  busy = ref(false),
  link = ref(''),
  linkLabel = ref(''),
  copyInput = ref<HTMLInputElement | null>(null)
async function load() {
  try {
    const [people, invites] = await Promise.all([
      api<Member[]>('/members'),
      api<typeof invitations.value>('/invitations'),
    ])
    members.value = people
    invitations.value = invites
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function invite() {
  busy.value = true
  error.value = ''
  try {
    const result = await api<{ token: string }>('/invitations', 'POST', {
      role: role.value,
      hours: hours.value,
    })
    link.value = `${location.origin}/#/join?token=${encodeURIComponent(result.token)}`
    linkLabel.value = '邀请链接（单次使用）'
    await load()
    notify('邀请已创建，请将链接提供给对应成员。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function copy() {
  try {
    await navigator.clipboard.writeText(link.value)
    notify('链接已复制。')
  } catch {
    copyInput.value?.focus()
    copyInput.value?.select()
    notify('请手动复制已选中的链接。')
  }
}
async function save(member: Member) {
  if (
    member.active === false &&
    !(await confirmAction(`移除“${member.display_name}”的团队访问与维护权限？其个人账号和个人导航会保留。`))
  )
    return
  busy.value = true
  error.value = ''
  try {
    await api(`/members/${member.id}`, 'PATCH', {
      version: member.version,
      role: member.role,
      active: member.active,
    })
    notify('团队权限已更新，个人账号和资料不受影响。')
    await load()
    emit('changed')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function revoke(id: string) {
  try {
    await api(`/invitations/${id}`, 'DELETE')
    await load()
    notify('邀请已撤销。')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function addExisting(){busy.value=true;error.value='';try{await api('/workspace/members','POST',{username:existingUsername.value.trim(),role:existingRole.value});existingUsername.value='';await load();emit('changed');notify('已有用户已加入空间。')}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
onMounted(load)
</script>
<template>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div>
  <form class="inline-form" @submit.prevent="invite">
    <h3>邀请新成员</h3>
    <p class="form-help">已有账号直接接受邀请；没有账号可先注册。邀请只能使用一次，也可提前撤销。</p>
    <div class="form-row">
      <label class="form-group"
        >加入后的角色<select v-model="role" class="form-field">
          <option v-for="(label, key) in roleNames" :key="key" :value="key">{{ label }}</option>
        </select></label
      ><label class="form-group"
        >有效时长<select v-model.number="hours" class="form-field">
          <option :value="24">24 小时</option>
          <option :value="72">3 天</option>
          <option :value="168">7 天</option>
        </select></label
      >
    </div>
    <RoleHelp :selected="role" />
    <button class="button primary" :disabled="busy"><Icon name="plus" />创建邀请</button>
  </form>
  <form class="inline-form" @submit.prevent="addExisting"><h3>添加已注册用户</h3><p class="form-help">对方已经有个人账号时，输入准确用户名即可加入当前空间，其个人资料保持独立。</p><div class="form-row"><label class="form-group">已有用户的用户名<input v-model="existingUsername" class="form-field" required maxlength="80" /></label><label class="form-group">空间角色<select v-model="existingRole" class="form-field"><option v-for="(label,key) in roleNames" :key="key" :value="key">{{ label }}</option></select></label></div><button class="button secondary" :disabled="busy">添加到当前空间</button></form>
  <div v-if="link" class="notice-panel">
    <label class="form-group"
      >{{ linkLabel
      }}<input ref="copyInput" class="form-field" readonly :value="link" aria-label="生成的邀请链接" /></label
    ><button class="button secondary" @click="copy"><Icon name="copy" />复制链接</button>
  </div>
  <div v-if="invitations.length" class="inline-form">
    <h3>待使用的邀请</h3>
    <div v-for="item in invitations" :key="item.id" class="management-row">
      <div>
        <strong>{{ roleNames[item.role] }}</strong
        ><small>{{ new Date(item.expires_at).toLocaleString() }} 到期</small>
      </div>
      <button class="text-button danger-text" @click="revoke(item.id)">撤销</button>
    </div>
  </div>
  <div class="inline-form">
    <h3>空间成员</h3>
    <p class="form-help">角色只影响当前空间。移除成员不会停用其个人账号；忘记密码可联系站点超级管理员。</p>
    <div v-for="member in members" :key="member.id" class="member-card">
      <div class="member-heading">
        <span class="avatar">{{ member.display_name.slice(0, 1) }}</span>
        <div>
          <strong>{{ member.display_name }}</strong
          ><small>{{ member.username }}{{ member.is_superadmin?' · 站点超级管理员':'' }}</small>
        </div>
      </div>
      <div class="member-controls">
        <label
          ><span class="sr-only">{{ member.display_name }}的角色</span
          ><select class="form-field" v-model="member.role">
            <option v-for="(label, key) in roleNames" :key="key" :value="key">{{ label }}</option>
          </select></label
        ><label class="checkbox-label"><input v-model="member.active" type="checkbox" />启用</label
        ><button class="button secondary compact" :disabled="busy" @click="save(member)">保存</button>
      </div>
    </div>
  </div>
</template>
