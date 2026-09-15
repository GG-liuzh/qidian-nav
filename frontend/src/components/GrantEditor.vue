<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, errorMessage, notify } from '../api'
import { roleNames, type Member } from '../types'
import Icon from './Icon.vue'
const props = defineProps<{
  kind: 'categories' | 'resources' | 'credentials'
  id: string
  members: Member[]
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
type Grant = {
  user_id: string
  can_read: boolean
  can_edit?: boolean
  can_manage_accounts?: boolean
  can_manage?: boolean
}
const grants = ref<Record<string, Grant>>({}),
  error = ref(''),
  loading = ref(true),
  busy = ref('')
const people = computed(() => props.members.filter((member) => member.active !== false))
async function load() {
  try {
    const data = await api<Grant[]>(`/${props.kind}/${props.id}/grants`)
    people.value.forEach((member) => {
      grants.value[member.id] = {
        user_id: member.id,
        can_read: false,
        ...(props.kind === 'credentials'
          ? { can_manage: false }
          : { can_edit: false, ...(props.kind === 'resources' ? { can_manage_accounts: false } : {}) }),
        ...data.find((row) => row.user_id === member.id),
      }
    })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function save(userId: string) {
  busy.value = userId
  error.value = ''
  try {
    const { user_id, ...payload } = grants.value[userId]
    await api(`/${props.kind}/${props.id}/grants/${user_id}`, 'PUT', payload)
    notify('授权已更新。')
    emit('changed')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = ''
  }
}
onMounted(load)
</script>
<template>
  <button class="text-button back-button" @click="emit('close')">← 返回</button>
  <h3>
    {{
      kind === 'credentials' ? '此账号的授权' : kind === 'categories' ? '业务线授权' : '链接与账号管理授权'
    }}
  </h3>
  <p class="form-help">
    {{
      kind === 'credentials'
        ? '读取权限允许获取此环境下的用户名和密码。账号管理权与读取权分别授予；授权始终受链接可见范围约束。'
        : kind === 'categories'
          ? '受限业务线仅对获准成员可见。维护链接还需要成员具备业务维护人角色。'
          : '这里设置额外授权；团队链接的基础可见范围由业务线决定。账号管理权允许配置账号，读取密码仍需逐个账号授权。'
    }}
  </p>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div>
  <p v-if="loading" role="status">正在读取授权…</p>
  <div v-else class="management-list">
    <div v-for="member in people" :key="member.id" class="management-row grant-row">
      <div>
        <strong>{{ member.display_name }}</strong
        ><small>{{ roleNames[member.role] }}</small>
      </div>
      <div v-if="grants[member.id]" class="grant-options">
        <label class="checkbox-label"
          ><input type="checkbox" v-model="grants[member.id].can_read" />{{
            kind === 'credentials' ? '读取账号' : '查看链接'
          }}</label
        ><label v-if="kind !== 'credentials'" class="checkbox-label"
          ><input type="checkbox" v-model="grants[member.id].can_edit" />维护链接</label
        ><label v-if="kind === 'resources'" class="checkbox-label"
          ><input type="checkbox" v-model="grants[member.id].can_manage_accounts" />管理账号</label
        ><label v-if="kind === 'credentials'" class="checkbox-label"
          ><input type="checkbox" v-model="grants[member.id].can_manage" />管理账号</label
        >
      </div>
      <button class="button secondary compact" :disabled="!!busy" @click="save(member.id)">
        {{ busy === member.id ? '保存中…' : '保存授权' }}
      </button>
    </div>
  </div>
</template>
