<script setup lang="ts">
import { confirmAction } from '../confirm'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { api, errorMessage, hostname, notify } from '../api'
import type { Credential, Endpoint, Member, Resource, Shortcut } from '../types'
import Sheet from './Sheet.vue'
import Icon from './Icon.vue'
import CredentialEditor from './CredentialEditor.vue'
import GrantEditor from './GrantEditor.vue'

const props = defineProps<{ id: string; env?: string; members: Member[]; shortcuts: Shortcut[] }>()
const emit = defineEmits<{
  close: []
  edit: [resource: Resource]
  changed: []
  feedback: [resource: Resource]
  visit: [endpoint: Endpoint]
}>()
const resource = ref<Resource | null>(null),
  endpointId = ref(''),
  accounts = ref<Credential[]>([]),
  error = ref(''),
  loading = ref(true),
  busy = ref('')
const editing = ref<Credential | null | undefined>(undefined),
  grant = ref<{ kind: 'resources' | 'credentials'; id: string } | null>(null)
const credentialEditor = ref<InstanceType<typeof CredentialEditor> | null>(null)
const secrets = ref<Record<string, string>>({}),
  manual = ref<{ value: string; label: string } | null>(null),
  manualInput = ref<HTMLTextAreaElement | null>(null)
let epoch = 0
const timers = new Map<string, ReturnType<typeof setTimeout>>()
const endpoint = computed(() => resource.value?.endpoints.find((row) => row.id === endpointId.value))
const pinned = computed(() => props.shortcuts.some((item) => item.id === endpointId.value))
const revisions = ref<
  | {
      version: number
      snapshot: { name: string; description: string; endpoints: { url: string }[] }
      changed_by: string
      created_at: string
    }[]
  | null
>(null)
function clearSecrets() {
  epoch++
  secrets.value = {}
  busy.value = ''
  manual.value = null
  timers.forEach(clearTimeout)
  timers.clear()
}
async function load() {
  error.value = ''
  try {
    const result = await api<Resource>(`/resources/${props.id}`)
    resource.value = result
    if (!result.endpoints.some((row) => row.id === endpointId.value))
      endpointId.value =
        (
          result.endpoints.find((row) => row.environment_id === props.env) ||
          result.endpoints.find((row) => row.env_key === 'test') ||
          result.endpoints[0]
        )?.id || ''
    else await loadAccounts()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}
async function loadAccounts() {
  clearSecrets()
  accounts.value = []
  if (!endpointId.value) return
  const current = epoch
  try {
    const result = await api<Credential[]>(`/endpoints/${endpointId.value}/credentials`)
    if (current !== epoch) return
    accounts.value = result
    if (!endpoint.value?.enabled || resource.value?.status !== 'active' || document.hidden) return
    await Promise.all(
      result
        .filter((account) => account.can_read && account.status === 'active')
        .map(async (account) => {
          try {
            const result = await api<{ value: string }>(`/credentials/${account.id}/access`, 'POST', {
              field: 'username',
              purpose: 'reveal',
            })
            if (current === epoch && !document.hidden) secrets.value[`${account.id}:username`] = result.value
          } catch (e) {
            if (current === epoch) error.value = errorMessage(e)
          }
        }),
    )
  } catch (e) {
    if (current === epoch) error.value = errorMessage(e)
  }
}
watch(endpointId, () => {
  editing.value = undefined
  grant.value = null
  void loadAccounts()
})
async function access(account: Credential, field: 'username' | 'password', purpose: 'copy' | 'reveal') {
  const key = `${account.id}:${field}`
  if (purpose === 'reveal' && secrets.value[key]) {
    delete secrets.value[key]
    clearTimeout(timers.get(key))
    return
  }
  const current = epoch
  busy.value = key
  error.value = ''
  let value = ''
  try {
    const result = await api<{ value: string }>(`/credentials/${account.id}/access`, 'POST', {
      field,
      purpose,
    })
    value = result.value
    if (current !== epoch || document.hidden) return
    if (purpose === 'reveal') {
      secrets.value[key] = value
      if (field === 'password')
        timers.set(
          key,
          setTimeout(() => {
            delete secrets.value[key]
          }, 20000),
        )
    } else {
      try {
        await navigator.clipboard.writeText(value)
        if (current === epoch) notify(`${field === 'password' ? '密码' : '用户名'}已复制。`)
      } catch {
        if (current === epoch) {
          manual.value = { value, label: field === 'password' ? '密码' : '用户名' }
          timers.set(
            'manual',
            setTimeout(() => {
              manual.value = null
            }, 20000),
          )
          await nextTick()
          manualInput.value?.focus()
          manualInput.value?.select()
        }
      }
    }
  } catch (e) {
    if (current === epoch) error.value = errorMessage(e)
  } finally {
    value = ''
    if (current === epoch) busy.value = ''
  }
}
async function pin() {
  if (!endpoint.value) return
  try {
    await api(`/me/shortcuts/${endpoint.value.id}`, pinned.value ? 'DELETE' : 'PUT')
    notify(pinned.value ? '已移除快捷入口。' : '已固定到快捷入口。')
    emit('changed')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function removeResource() {
  if (!resource.value || !(await confirmAction(`将“${resource.value.name}”移入回收站？30 天内可恢复。`)))
    return
  try {
    await api(`/resources/${resource.value.id}?version=${resource.value.version}`, 'DELETE')
    notify('已移入回收站。')
    emit('changed')
    emit('close')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function removeAccount(account: Credential) {
  if (!(await confirmAction(`删除账号“${account.name}”？删除后将不能获取该账号。`))) return
  try {
    await api(`/credentials/${account.id}?version=${account.version}`, 'DELETE')
    await loadAccounts()
    notify('账号已删除。')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function history() {
  try {
    revisions.value = await api(`/resources/${props.id}/revisions`)
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function restore(version: number) {
  if (
    !resource.value ||
    !(await confirmAction('恢复此版本的链接信息？已有账号不会恢复旧密码，地址变更后需要重新确认绑定。'))
  )
    return
  try {
    await api(`/resources/${props.id}/revisions/${version}/restore`, 'POST', {
      version: resource.value.version,
    })
    revisions.value = null
    await load()
    emit('changed')
    notify('链接信息已恢复。')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
function hidden() {
  if (document.hidden) clearSecrets()
}
async function close() {
  if (credentialEditor.value?.dirty && !(await confirmAction('放弃尚未保存的账号修改？'))) return
  clearSecrets()
  emit('close')
}
onMounted(() => {
  void load()
  window.addEventListener('blur', clearSecrets)
  window.addEventListener('clear-secrets', clearSecrets)
  document.addEventListener('visibilitychange', hidden)
})
onUnmounted(() => {
  clearSecrets()
  window.removeEventListener('blur', clearSecrets)
  window.removeEventListener('clear-secrets', clearSecrets)
  document.removeEventListener('visibilitychange', hidden)
})
</script>
<template>
  <Sheet
    :open="true"
    :title="resource?.name || '系统详情'"
    :description="
      resource
        ? `${resource.category_name} / ${resource.is_public ? '已公开' : resource.scope === 'personal' ? '仅自己可见' : '团队资源'}`
        : '正在读取详情'
    "
    @close="close"
  >
    <p v-if="loading" role="status">正在加载…</p>
    <div v-if="error" class="form-error" role="alert">
      {{ error }}<button v-if="!resource" class="text-button" @click="load">重试</button>
    </div>
    <template v-if="resource">
      <GrantEditor
        v-if="grant"
        :kind="grant.kind"
        :id="grant.id"
        :members="members"
        @close="
          () => {
            grant = null
            load()
          }
        "
        @changed="emit('changed')"
      />
      <CredentialEditor
        v-else-if="editing !== undefined && endpoint"
        ref="credentialEditor"
        :credential="editing"
        :endpoint="endpoint"
        @close="editing = undefined"
        @saved="
          () => {
            editing = undefined
            loadAccounts()
          }
        "
      />
      <template v-else-if="revisions"
        ><button class="text-button back-button" @click="revisions = null">← 返回详情</button>
        <h3>修改历史</h3>
        <div v-for="revision in revisions" :key="revision.version" class="revision-card">
          <strong>版本 {{ revision.version }} · {{ revision.snapshot.name }}</strong
          ><small>{{ revision.changed_by }} · {{ new Date(revision.created_at).toLocaleString() }}</small>
          <p>{{ revision.snapshot.description }}</p>
          <p v-for="item in revision.snapshot.endpoints" :key="item.url" class="break-word">{{ item.url }}</p>
          <button
            v-if="revision.version !== resource.version"
            class="button secondary compact"
            @click="restore(revision.version)"
          >
            恢复此版本的链接信息</button
          ><span v-else class="small-label">当前版本</span>
        </div></template
      >
      <template v-else>
        <p class="drawer-intro">{{ resource.description || '这个入口还没有填写使用说明。' }}</p>
        <div class="drawer-environments" role="group" aria-label="选择账号所属环境">
          <button
            v-for="item in resource.endpoints"
            :key="item.id"
            :class="['environment-tab', item.env_kind, { selected: item.id === endpointId }]"
            :aria-pressed="item.id === endpointId"
            @click="endpointId = item.id"
          >
            <span>{{ item.env_label }} · {{ item.env_key.toUpperCase() }}</span
            ><small>{{ hostname(item.url) }}</small>
          </button>
        </div>
        <div v-if="endpoint" class="destination-box">
          <div class="endpoint-heading">
            <span class="env-badge" :class="endpoint.env_kind">{{
              resource.type === 'bookmark' ? '书签链接' : `${endpoint.env_label}环境`
            }}</span
            ><button
              class="icon-button"
              :class="{ 'is-favorite': pinned }"
              :aria-label="
                pinned
                  ? '移除快捷入口'
                  : resource.type === 'bookmark'
                    ? '固定此书签到快捷入口'
                    : '固定此环境到快捷入口'
              "
              @click="pin"
            >
              <Icon name="pin" />
            </button>
          </div>
          <a
            v-if="endpoint.enabled && resource.status !== 'archived'"
            :href="endpoint.url"
            target="_blank"
            rel="noopener noreferrer"
            class="destination-url"
            @click="emit('visit', endpoint)"
            >{{ endpoint.url }}<Icon name="external"
          /></a>
          <p v-else class="break-word">
            {{ endpoint.url }}<br />{{ endpoint.disabled_reason || '资源已归档' }}
          </p>
        </div>
        <div class="section-heading">
          <h3><Icon name="key" />{{ resource.scope === 'personal' ? '私人账号' : '共享账号' }}</h3>
          <button
            v-if="resource.can_manage_accounts"
            class="text-button"
            @click="
              () => {
                clearSecrets()
                editing = null
              }
            "
          >
            <Icon name="plus" />添加账号
          </button>
        </div>
        <p v-if="!accounts.length" class="inline-empty">
          暂无你可访问的账号。{{
            resource.can_manage_accounts ? '可以为当前入口添加账号。' : '普通成员可查看空间内的业务账号。'
          }}
        </p>
        <article v-for="account in accounts" :key="account.id" class="account-card">
          <div class="account-header">
            <strong>{{ account.name }}</strong
            ><span class="status-badge" :class="account.status">{{
              { active: '可用', pending: '待核实', disabled: '已停用', expired: '已过期' }[account.status]
            }}</span>
          </div>
          <p class="form-help">{{ account.usage_note || '未填写用途说明' }}</p>
          <div v-if="account.can_read" class="account-actions">
            <div class="secret-row">
              <span>用户名</span>
              <span class="secret-value" :class="{ revealed: !!secrets[`${account.id}:username`] }">{{
                secrets[`${account.id}:username`] || '••••••••'
              }}</span>
              <button
                class="icon-button"
                :aria-label="secrets[`${account.id}:username`] ? '隐藏用户名' : '显示用户名'"
                :disabled="!!busy || account.status !== 'active' || !endpoint?.enabled"
                @click="access(account, 'username', 'reveal')"
              >
                <Icon :name="secrets[`${account.id}:username`] ? 'eye-off' : 'eye'" /></button
              ><button
                class="text-button"
                :disabled="!!busy || account.status !== 'active' || !endpoint?.enabled"
                @click="access(account, 'username', 'copy')"
              >
                <Icon name="copy" />复制用户名
              </button>
            </div>
            <div class="secret-row">
              <span>密码</span
              ><span class="secret-value" :class="{ revealed: !!secrets[`${account.id}:password`] }">{{
                secrets[`${account.id}:password`] || '••••••••••••'
              }}</span
              ><button
                class="icon-button"
                :aria-label="secrets[`${account.id}:password`] ? '隐藏密码' : '显示密码'"
                :disabled="!!busy || account.status !== 'active' || !endpoint?.enabled"
                @click="access(account, 'password', 'reveal')"
              >
                <Icon :name="secrets[`${account.id}:password`] ? 'eye-off' : 'eye'" /></button
              ><button
                class="text-button"
                :disabled="!!busy || account.status !== 'active' || !endpoint?.enabled"
                @click="access(account, 'password', 'copy')"
              >
                <Icon name="copy" />复制密码
              </button>
            </div>
          </div>
          <p v-else class="form-help">你可以维护此账号。读取用户名或密码需要单独授权。</p>
          <small v-if="account.expires_at" class="muted"
            >有效期至 {{ new Date(account.expires_at).toLocaleString() }}</small
          >
          <div class="account-manage">
            <button
              v-if="account.can_manage"
              class="text-button"
              @click="
                () => {
                  clearSecrets()
                  editing = account
                }
              "
            >
              <Icon name="edit" />编辑账号</button
            ><button
              v-if="account.can_grant"
              class="text-button"
              @click="
                () => {
                  clearSecrets()
                  grant = { kind: 'credentials', id: account.id }
                }
              "
            >
              <Icon name="shield" />授权</button
            ><button
              v-if="account.can_manage"
              class="text-button danger-text"
              @click="removeAccount(account)"
            >
              <Icon name="trash" />删除
            </button>
          </div>
        </article>
        <div v-if="manual" class="notice-panel" role="alert">
          <p>浏览器未允许自动复制，请手动复制以下{{ manual.label }}。内容会在 20 秒后隐藏。</p>
          <textarea
            ref="manualInput"
            class="form-field"
            readonly
            :value="manual.value"
            aria-label="手动复制账号内容"
          />
        </div>
        <p v-if="accounts.some((account) => account.can_read)" class="form-help">
          显示的用户名和密码将在 20 秒后隐藏；切换环境或离开页面也会隐藏。
        </p>
        <div class="drawer-detail">
          <div class="detail-row">
            <span>业务归属</span><span>{{ resource.category_name }}</span>
          </div>
          <div class="detail-row">
            <span>维护人</span><span>{{ resource.maintainer_name }}</span>
          </div>
          <div class="detail-row">
            <span>标签</span
            ><span class="tags"
              ><span v-for="tag in resource.tags" :key="tag" class="tag">{{ tag }}</span></span
            >
          </div>
          <div class="detail-row">
            <span>可见范围</span
            ><span>{{
              resource.is_public
                ? '链接信息已公开 · 账号密码仍按授权读取'
                : resource.scope === 'personal'
                  ? '个人导航 · 仅自己可见'
                  : '团队空间 · 按授权范围共享'
            }}</span>
          </div>
        </div>
        <div class="detail-buttons">
          <button
            v-if="resource.can_edit"
            class="button secondary"
            @click="
              () => {
                clearSecrets()
                if (resource) emit('edit', resource)
              }
            "
          >
            <Icon name="edit" />编辑链接</button
          ><button
            v-if="resource.can_grant"
            class="button secondary"
            @click="
              () => {
                clearSecrets()
                if (resource) grant = { kind: 'resources', id: resource.id }
              }
            "
          >
            <Icon name="shield" />管理权限</button
          ><button
            v-if="resource.can_edit"
            class="button secondary"
            @click="
              () => {
                clearSecrets()
                history()
              }
            "
          >
            <Icon name="history" />修改历史</button
          ><button
            v-if="resource.scope === 'team' && members.length"
            class="button secondary"
            @click="
              () => {
                clearSecrets()
                if (resource) emit('feedback', resource)
              }
            "
          >
            <Icon name="feedback" />建议与反馈</button
          ><button v-if="resource.can_edit" class="button danger" @click="removeResource">
            <Icon name="trash" />移入回收站
          </button>
        </div>
      </template>
    </template>
  </Sheet>
</template>
