<script setup lang="ts">
import { confirmAction } from '../confirm'
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useAuth } from '../auth'
import { onBeforeRouteLeave } from 'vue-router'
import { api, ApiError, errorMessage, notify } from '../api'
import type { Catalog, Member, Resource, ResourceDraft, Scope, Page } from '../types'
import Sheet from './Sheet.vue'
import CatalogPanel from './CatalogPanel.vue'
import { categoryTree, categoryLabel } from '../catalog'
import Icon from './Icon.vue'

const props = defineProps<{
  resource: Resource | null
  scope: Scope
  categoryId?: string
  catalog: Catalog
  members: Member[]
}>()
const emit = defineEmits<{ close: []; saved: [resource: Resource]; catalogChange: [] }>()
const auth = useAuth()
const manageCatalog = ref(false)
const original = props.resource
const draft = reactive<ResourceDraft>({
  scope: original?.scope || props.scope,
  type: original?.type || (props.scope === 'personal' ? 'bookmark' : 'system'),
  name: original?.name || '',
  category_id: original?.category_id || props.categoryId || null,
  aliases: original?.aliases || '',
  description: original?.description || '',
  tags: [...(original?.tags || [])],
  icon: original?.icon || 'globe',
  maintainer_id: original?.maintainer_id || auth.user!.id,
  endpoints: [],
  status: original?.status || 'active',
  ...(original ? { version: original.version } : {}),
})
draft.is_public = original?.is_public || false
const tags = ref(original?.tags.join('，') || '')
const bookmarkUrl = ref(original?.type === 'bookmark' ? original.endpoints[0]?.url || '' : '')
const addresses = reactive<Record<string, { url: string; enabled: boolean }>>({})
watch(
  () => props.catalog.environments,
  (values) => {
    values.forEach((env) => {
      if (!addresses[env.id]) {
        const endpoint = original?.endpoints.find((row) => row.environment_id === env.id)
        addresses[env.id] = { url: endpoint?.url || '', enabled: endpoint?.configured_enabled ?? true }
      }
    })
  },
  { immediate: true },
)
const categories = computed(() =>
  categoryTree(props.catalog.categories.filter((row) => row.scope === draft.scope && row.can_edit_resources)),
)
const environments = computed(() =>
  props.catalog.environments.filter(
    (row) => row.scope === draft.scope && (row.enabled || addresses[row.id]?.url),
  ),
)
const canCreateTeam = computed(
  () =>
    auth.user?.role === 'admin' ||
    auth.user?.role === 'maintainer' ||
    props.catalog.categories.some((row) => row.scope === 'team' && row.can_edit_resources),
)
const busy = ref(false),
  error = ref(''),
  dirty = ref(false),
  conflict = ref<Resource | null>(null),
  duplicates = ref<Resource[]>([]),
  duplicateConfirmed = ref(false)
watch(
  [draft, tags, bookmarkUrl, addresses],
  () => {
    dirty.value = true
    duplicateConfirmed.value = false
    duplicates.value = []
  },
  { deep: true },
)
watch(
  () => draft.scope,
  () => {
    if (!categories.value.some((row) => row.id === draft.category_id)) draft.category_id = null
  },
)
async function close() {
  if (!dirty.value || (await confirmAction('放弃尚未保存的修改？'))) emit('close')
}

function applyToLatest() {
  if (conflict.value) {
    draft.version = conflict.value.version
    conflict.value = null
    error.value = ''
    notify('已采用最新版本号，你填写的内容仍然保留。')
  }
}
async function save() {
  error.value = ''
  busy.value = true
  try {
    const endpoints =
      draft.type === 'bookmark'
        ? [{ environment_id: null, url: bookmarkUrl.value.trim(), enabled: true }]
        : environments.value
            .filter((env) => addresses[env.id]?.url.trim())
            .map((env) => ({
              environment_id: env.id,
              ...addresses[env.id],
              url: addresses[env.id].url.trim(),
            }))
    if (!endpoints.length || endpoints.some((endpoint) => !endpoint.url))
      throw new Error('请填写至少一个完整的入口地址。')
    const payload = {
      ...draft,
      endpoints,
      tags: tags.value
        .split(/[,，]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    }
    if (!duplicateConfirmed.value) {
      const found: Resource[] = []
      for (const endpoint of endpoints) {
        if (original?.endpoints.some((row) => row.url === endpoint.url)) continue
        const result = await api<Page<Resource>>(
          `/resources?view=${draft.scope}&url=${encodeURIComponent(endpoint.url)}`,
        )
        found.push(
          ...result.items.filter(
            (row) => row.id !== original?.id && row.endpoints.some((item) => item.url === endpoint.url),
          ),
        )
      }
      if (found.length) {
        duplicates.value = [...new Map(found.map((row) => [row.id, row])).values()]
        return
      }
    }
    const resource = await api<Resource>(
      original ? `/resources/${original.id}` : '/resources',
      original ? 'PATCH' : 'POST',
      payload,
    )
    dirty.value = false
    notify('链接已保存。')
    emit('saved', resource)
  } catch (e) {
    error.value = errorMessage(e)
    if (e instanceof ApiError && e.status === 409 && e.detail?.current)
      conflict.value = e.detail.current as Resource
  } finally {
    busy.value = false
  }
}
onBeforeRouteLeave(
  () => !dirty.value || confirmAction('离开此页面将放弃尚未保存的修改，是否继续？', { title: '尚未保存' }),
)
</script>
<template>
  <Sheet
    :open="true"
    :title="original ? '编辑链接' : '添加链接'"
    :description="draft.scope === 'personal' ? '个人导航 · 默认私有' : '团队空间 · 按授权范围共享'"
    @close="close"
  >
    <form @submit.prevent="save" class="editor-form">
      <div v-if="error" class="form-error" role="alert">{{ error }}</div>
      <div v-if="conflict" class="notice-panel">
        <strong>最新版本：{{ conflict.name }}</strong>
        <p v-for="endpoint in conflict.endpoints" :key="endpoint.id" class="break-word">
          {{ endpoint.env_label }}：{{ endpoint.url }}
        </p>
        <p>你的草稿仍在下方。比较后可在最新版本上重新应用。</p>
        <button type="button" class="button secondary" @click="applyToLatest">
          保留我的内容，使用最新版本
        </button>
      </div>
      <fieldset class="type-options" :disabled="!!original">
        <legend class="form-label">资源类型</legend>
        <label :class="{ selected: draft.type === 'system' }"
          ><input type="radio" v-model="draft.type" value="system" /><Icon name="globe" />业务系统</label
        ><label :class="{ selected: draft.type === 'bookmark' }"
          ><input type="radio" v-model="draft.type" value="bookmark" /><Icon name="book" />普通书签</label
        >
      </fieldset>
      <div class="form-row">
        <label class="form-group"
          >保存到<select v-model="draft.scope" class="form-field" aria-label="保存到" :disabled="!!original">
            <option value="team" :disabled="!canCreateTeam">团队空间 · 部门共享</option>
            <option value="personal">个人导航 · 默认私有</option>
          </select></label
        ><label class="form-group"
          >{{ draft.scope === 'team' ? '业务线' : '个人分组'
          }}<select
            v-model="draft.category_id"
            class="form-field"
            :aria-label="draft.scope === 'team' ? '业务线' : '个人分组'"
          >
            <option
              :value="null"
              :disabled="
                draft.scope === 'team' && auth.user?.role !== 'admin' && auth.user?.role !== 'maintainer'
              "
            >
              未分组
            </option>
            <option v-for="category in categories" :key="category.id" :value="category.id">
              {{ categoryLabel(category) }}
            </option>
          </select></label
        >
      </div>
      <label class="form-group"
        ><span>名称 <span class="required">*</span></span
        ><input v-model="draft.name" required maxlength="120" class="form-field" placeholder="例如：订单中心"
      /></label>
      <label class="form-group"
        >别名<input
          v-model="draft.aliases"
          maxlength="240"
          class="form-field"
          placeholder="例如：OMS、订单后台"
      /></label>
      <label class="form-group"
        >简介<textarea
          v-model="draft.description"
          maxlength="2000"
          rows="2"
          class="form-field"
          placeholder="一句话说明这个入口的用途"
        />
      </label>
      <div class="form-section-heading">
        <Icon name="external" />
        <h3>{{ draft.type === 'system' ? '环境与地址' : '链接地址' }}</h3>
      </div>
      <label v-if="draft.type === 'bookmark'" class="form-group"
        >URL<input
          v-model="bookmarkUrl"
          type="url"
          required
          maxlength="4096"
          class="form-field"
          placeholder="https://"
      /></label>
      <div v-else class="environment-inputs">
        <p class="form-help">填写实际存在的环境，未填写的环境不会生成入口。</p>
        <div v-for="env in environments" :key="env.id" class="form-group">
          <label :for="`endpoint-${env.id}`"
            ><span class="env-badge" :class="env.kind"
              >{{ env.label }} · {{ env.key.toUpperCase() }}</span
            ></label
          ><input
            :id="`endpoint-${env.id}`"
            v-model="addresses[env.id].url"
            type="url"
            maxlength="4096"
            class="form-field"
            :placeholder="`${env.label}环境的完整 URL`"
          /><label v-if="addresses[env.id].url" class="checkbox-label"
            ><input v-model="addresses[env.id].enabled" type="checkbox" />启用此入口</label
          >
        </div>
        <div v-if="!environments.length" class="notice-panel">
          <p>还没有可用的环境。</p>
          <button
            v-if="draft.scope === 'personal' || auth.user?.role === 'admin'"
            type="button"
            class="button secondary"
            @click="manageCatalog = true"
          >
            <Icon name="plus" />现在添加环境
          </button>
          <p v-else class="form-help">请联系空间管理员添加环境；普通书签无需环境也可保存。</p>
        </div>
        <button
          v-if="draft.scope === 'personal' || auth.user?.role === 'admin'"
          type="button"
          class="text-button"
          @click="manageCatalog = true"
        >
          管理环境与地址
        </button>
      </div>
      <div class="form-section-heading">
        <Icon name="users" />
        <h3>维护信息</h3>
      </div>
      <label v-if="draft.scope === 'team'" class="form-group"
        >维护人<select v-model="draft.maintainer_id" class="form-field">
          <option
            v-for="member in members.filter((row) => row.active !== false)"
            :key="member.id"
            :value="member.id"
          >
            {{ member.display_name }}
          </option>
        </select></label
      >
      <label class="form-group"
        >标签<input v-model="tags" class="form-field" placeholder="用逗号分隔，例如：订单，联调"
      /></label>
      <label v-if="original" class="form-group"
        >状态<select v-model="draft.status" class="form-field">
          <option value="active">正常显示</option>
          <option value="archived">归档</option>
        </select></label
      >
      <p class="form-help">保存链接后，维护人和管理员可在详情中配置业务账号，空间成员均可查看。</p>
      <label
        v-if="draft.scope === 'personal' || auth.user?.role === 'admin'"
        class="checkbox-label publish-option"
        ><input v-model="draft.is_public" type="checkbox" />公开此链接，允许未登录访问</label
      >
      <p class="form-help">
        {{
          draft.scope === 'personal'
            ? '只公开选中的链接信息，私人账号和其他书签保持私有。'
            : '团队还需在设置中开启游客访问。公开内容只包含链接信息，不包含账号密码。'
        }}
      </p>
      <p v-if="draft.is_public && draft.type === 'system'" class="form-help">
        此系统的所有启用环境地址都会公开。需要只分享一个环境时，请将该地址保存为独立的公开链接。
      </p>
      <div v-if="duplicates.length" class="notice-panel" role="alert">
        <strong>发现已存在的相同地址</strong>
        <p v-for="item in duplicates" :key="item.id">{{ item.name }} · {{ item.category_name }}</p>
        <button
          type="button"
          class="button secondary"
          @click="
            () => {
              duplicateConfirmed = true
              save()
            }
          "
        >
          仍然保存为独立链接
        </button>
      </div>
      <footer class="form-footer">
        <button type="button" class="button secondary" @click="close">取消</button
        ><button class="button primary" :disabled="busy || !!conflict">
          {{ busy ? '正在保存…' : '保存链接' }}
        </button>
      </footer>
    </form>
    <CatalogPanel
      v-if="manageCatalog"
      :catalog="catalog"
      :scope="draft.scope"
      :members="members"
      initial-tab="environments"
      @close="manageCatalog = false"
      @changed="emit('catalogChange')"
    />
  </Sheet>
</template>
