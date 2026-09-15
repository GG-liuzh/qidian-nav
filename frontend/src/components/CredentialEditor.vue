<script setup lang="ts">
import { confirmAction } from '../confirm'
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { api, errorMessage, notify } from '../api'
import type { Credential, Endpoint } from '../types'
import Icon from './Icon.vue'
const props = defineProps<{ credential: Credential | null; endpoint: Endpoint }>()
const emit = defineEmits<{ close: []; saved: [] }>()
function localDate(value: string | null | undefined) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
const form = reactive({
  name: props.credential?.name || '',
  username: '',
  password: '',
  usage_note: props.credential?.usage_note || '',
  status: props.credential?.status === 'expired' ? 'active' : props.credential?.status || 'active',
  expires_at: localDate(props.credential?.expires_at),
})
const error = ref(''),
  busy = ref(false),
  dirty = ref(false)
watch(
  form,
  () => {
    dirty.value = true
  },
  { deep: true },
)
defineExpose({ dirty })

async function close() {
  if (!dirty.value || (await confirmAction('放弃尚未保存的账号修改？'))) emit('close')
}
async function save() {
  busy.value = true
  error.value = ''
  try {
    const payload = {
      name: form.name,
      usage_note: form.usage_note,
      status: form.status,
      expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
      ...(form.username ? { username: form.username } : {}),
      ...(form.password ? { password: form.password } : {}),
      ...(props.credential ? { version: props.credential.version } : {}),
    }
    await api(
      props.credential
        ? `/credentials/${props.credential.id}`
        : `/endpoints/${props.endpoint.id}/credentials`,
      props.credential ? 'PATCH' : 'POST',
      payload,
    )
    form.username = ''
    form.password = ''
    dirty.value = false
    notify('账号已保存。')
    emit('saved')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
onUnmounted(() => {
  form.username = ''
  form.password = ''
})
onBeforeRouteLeave(() => !dirty.value || confirmAction('离开此页面将放弃尚未保存的修改，是否继续？', {title:'尚未保存'}))
</script>
<template>
  <button class="text-button back-button" @click="close">← 返回账号列表</button>
  <h3>{{ credential ? '编辑账号' : '添加账号' }}</h3>
  <p class="form-help">绑定到 {{ endpoint.env_label }} · {{ endpoint.url }}</p>
  <form @submit.prevent="save">
    <div v-if="error" class="form-error" role="alert">{{ error }}</div>
    <label class="form-group"
      >账号名称<input
        class="form-field"
        v-model="form.name"
        required
        maxlength="80"
        placeholder="例如：联调只读账号" /></label
    ><label class="form-group"
      >{{ credential ? '新用户名（留空保持原值）' : '用户名'
      }}<input
        class="form-field"
        v-model="form.username"
        :required="!credential"
        maxlength="256"
        autocomplete="off" /></label
    ><label class="form-group"
      >{{ credential ? '新密码（留空保持原值）' : '密码'
      }}<input
        class="form-field"
        type="password"
        v-model="form.password"
        :required="!credential"
        maxlength="4096"
        autocomplete="new-password" /></label
    ><label class="form-group"
      >用途与说明<textarea
        class="form-field"
        v-model="form.usage_note"
        maxlength="1000"
        rows="3"
        placeholder="例如：仅用于查询，不可修改数据"
      /></label
    ><label class="form-group"
      >有效期（选填）<input class="form-field" v-model="form.expires_at" type="datetime-local" /></label
    ><label class="form-group"
      >状态<select class="form-field" v-model="form.status">
        <option value="active">可用，已确认适用当前入口</option>
        <option value="pending">待核实</option>
        <option value="disabled">已停用</option>
      </select></label
    >
    <p v-if="credential?.status === 'pending'" class="notice-panel">
      入口地址或状态发生过变化，请确认账号适用于上方环境后再恢复为可用。
    </p>
    <div class="form-footer">
      <button class="button secondary" type="button" @click="close">取消</button
      ><button class="button primary" :disabled="busy">
        <Icon name="key" />{{ busy ? '保存中…' : '保存账号' }}
      </button>
    </div>
  </form>
</template>
