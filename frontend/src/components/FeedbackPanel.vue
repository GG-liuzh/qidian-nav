<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import type { Catalog, Feedback, Resource, ResourceDraft } from '../types'
import Icon from './Icon.vue'
const props = defineProps<{ catalog: Catalog; resource?: Resource | null; compose?: boolean }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuth(),
  items = ref<Feedback[]>([]),
  error = ref(''),
  busy = ref(false),
  showForm = ref(props.compose || !!props.resource),
  accepting = ref<Feedback | null>(null),
  resolution = ref('')
const draft = reactive({
  kind: props.resource ? 'edit' : 'add',
  title: props.resource ? `${props.resource.name}的修改建议` : '',
  url: '',
  description: '',
  category_id: props.resource?.category_id || null,
  resource_id: props.resource?.id || null,
})
const acceptedDraft = reactive<ResourceDraft>({
  scope: 'team',
  type: 'bookmark',
  name: '',
  category_id: null,
  aliases: '',
  description: '',
  tags: [],
  icon: 'book',
  maintainer_id: auth.user!.id,
  endpoints: [{ environment_id: null, url: '', enabled: true }],
  status: 'active',
})
const categories = computed(() => props.catalog.categories.filter((row) => row.scope === 'team'))
async function load() {
  try {
    items.value = await api<Feedback[]>('/feedback')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function submit() {
  busy.value = true
  error.value = ''
  try {
    await api('/feedback', 'POST', draft)
    draft.title = ''
    draft.description = ''
    draft.url = ''
    showForm.value = false
    await load()
    notify('已提交，处理结果会保留在这里。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
function prepare(item: Feedback) {
  accepting.value = item
  resolution.value = ''
  Object.assign(acceptedDraft, {
    name: item.title,
    description: item.description,
    category_id: item.category_id,
    endpoints: [{ environment_id: null, url: item.url, enabled: true }],
  })
}
async function resolve(item: Feedback, status: 'accepted' | 'rejected' | 'withdrawn') {
  busy.value = true
  error.value = ''
  try {
    await api(`/feedback/${item.id}/resolve`, 'POST', {
      version: item.version,
      status,
      resolution: resolution.value,
      ...(status === 'accepted' && item.kind === 'add' ? { resource: acceptedDraft } : {}),
    })
    accepting.value = null
    resolution.value = ''
    await load()
    emit('changed')
    notify(status === 'accepted' ? '建议已采用。' : status === 'withdrawn' ? '已撤回。' : '处理结果已保存。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<template>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div>
  <div class="section-heading">
    <h3>建议与反馈</h3>
    <button class="text-button" @click="showForm = !showForm"><Icon name="plus" />提交建议</button>
  </div>
  <form v-if="showForm" class="inline-form" @submit.prevent="submit">
    <p v-if="resource" class="form-help">针对：{{ resource.name }}</p>
    <label class="form-group"
      >类型<select v-model="draft.kind" class="form-field">
        <option value="add">推荐新链接</option>
        <option value="edit">修改建议</option>
        <option value="broken">链接失效</option>
        <option value="account">账号问题</option>
      </select></label
    ><label class="form-group"
      >标题<input v-model="draft.title" class="form-field" required maxlength="120" /></label
    ><label class="form-group"
      >业务线<select v-model="draft.category_id" class="form-field">
        <option :value="null">由管理员分配</option>
        <option v-for="category in categories" :key="category.id" :value="category.id">
          {{ category.name }}
        </option>
      </select></label
    ><label class="form-group"
      >{{ draft.kind === 'add' ? '推荐地址' : '相关地址（选填）'
      }}<input
        v-model="draft.url"
        class="form-field"
        type="url"
        :required="draft.kind === 'add'"
        maxlength="4096"
        placeholder="https://" /></label
    ><label class="form-group"
      >说明<textarea
        v-model="draft.description"
        class="form-field"
        rows="3"
        maxlength="2000"
        placeholder="说明用途或问题现象，请勿填写密码。"
      /></label
    ><button class="button primary" :disabled="busy">提交给维护人</button>
  </form>
  <div v-if="accepting" class="notice-panel">
    <h3>处理“{{ accepting.title }}”</h3>
    <form @submit.prevent="resolve(accepting!, 'accepted')">
      <template v-if="accepting.kind === 'add'"
        ><p class="form-help">确认后将发布为团队普通书签。</p>
        <label class="form-group"
          >发布名称<input v-model="acceptedDraft.name" required class="form-field" /></label
        ><label class="form-group"
          >地址<input
            v-model="acceptedDraft.endpoints[0].url"
            required
            type="url"
            class="form-field" /></label
        ><label class="form-group"
          >保存到业务线<select v-model="acceptedDraft.category_id" class="form-field">
            <option :value="null" :disabled="auth.user?.role !== 'admin'">未分组</option>
            <option
              v-for="category in categories.filter((row) => row.can_edit_resources)"
              :key="category.id"
              :value="category.id"
            >
              {{ category.name }}
            </option>
          </select></label
        ></template
      ><label class="form-group"
        >处理说明<textarea v-model="resolution" class="form-field" rows="2" maxlength="1000" />
      </label>
      <div class="row-actions">
        <button class="button secondary" type="button" @click="accepting = null">取消</button
        ><button
          class="button secondary"
          type="button"
          :disabled="busy"
          @click="resolve(accepting!, 'rejected')"
        >
          不采用</button
        ><button class="button primary" :disabled="busy">
          {{ accepting.kind === 'add' ? '采用并发布链接' : '标记已处理' }}
        </button>
      </div>
    </form>
  </div>
  <div class="management-list">
    <article v-for="item in items" :key="item.id" class="feedback-card">
      <div class="account-header">
        <strong>{{ item.title }}</strong
        ><span class="status-badge" :class="item.status === 'open' ? 'pending' : 'active'">{{
          { open: '待处理', accepted: '已采用', rejected: '未采用', withdrawn: '已撤回' }[item.status]
        }}</span>
      </div>
      <small class="muted">{{ item.creator_name }} · {{ new Date(item.created_at).toLocaleString() }}</small>
      <p>{{ item.description }}</p>
      <p v-if="item.url" class="break-word">{{ item.url }}</p>
      <p v-if="item.resolution" class="notice-panel">处理说明：{{ item.resolution }}</p>
      <div v-if="item.status === 'open'" class="row-actions">
        <button v-if="item.can_handle" class="button secondary compact" @click="prepare(item)">
          处理建议</button
        ><button
          v-if="item.created_by === auth.user?.id"
          class="text-button"
          :disabled="busy"
          @click="resolve(item, 'withdrawn')"
        >
          撤回
        </button>
      </div>
    </article>
    <p v-if="!items.length" class="inline-empty">暂时没有建议或反馈。</p>
  </div>
</template>
