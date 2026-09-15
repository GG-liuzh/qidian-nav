<script setup lang="ts">
import { confirmAction } from '../confirm'
import { computed, reactive, ref } from 'vue'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import type { Catalog, Category, Environment, Member, Scope } from '../types'
import Sheet from './Sheet.vue'
import { categoryTree, categoryLabel } from '../catalog'
import Icon from './Icon.vue'
import GrantEditor from './GrantEditor.vue'

const props = defineProps<{
  catalog: Catalog
  scope: Scope
  members: Member[]
  initialTab?: 'categories' | 'environments'
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
const auth = useAuth(),
  tab = ref<'categories' | 'environments'>(props.initialTab || 'categories'),
  error = ref(''),
  busy = ref(false)
const categoryEdit = ref<Category | null>(null),
  environmentEdit = ref<Environment | null>(null),
  granting = ref<Category | null>(null)
const categoryForm = reactive({
  name: '',
  parent_id: null as string | null,
  visibility: 'workspace' as 'workspace' | 'restricted',
  sort_order: 0,
})
const environmentForm = reactive({ key: '', label: '', kind: 'custom', enabled: true, sort_order: 0 })
const deletion = ref<Category | null>(null),
  moveTo = ref('')
const filter = ref('')
const categories = computed(() =>
  categoryTree(props.catalog.categories.filter((row) => row.scope === props.scope)),
)
const environments = computed(() => props.catalog.environments.filter((row) => row.scope === props.scope))
const matchingCategories = computed(() =>
  categories.value.filter((row) =>
    row.name.toLocaleLowerCase().includes(filter.value.trim().toLocaleLowerCase()),
  ),
)
const matchingEnvironments = computed(() =>
  environments.value.filter((row) =>
    `${row.label} ${row.key}`.toLocaleLowerCase().includes(filter.value.trim().toLocaleLowerCase()),
  ),
)
const parentChoices = computed(() => {
  const byId = new Map(categories.value.map((row) => [row.id, row]))
  return categories.value.filter((row) => {
    if (row.depth >= 7) return false
    let current: typeof row | undefined = row
    const seen = new Set<string>()
    while (current && !seen.has(current.id)) {
      if (current.id === categoryEdit.value?.id) return false
      seen.add(current.id)
      current = byId.get(current.parent_id || '')
    }
    return true
  })
})
function resetCategory() {
  categoryEdit.value = null
  Object.assign(categoryForm, {
    name: '',
    parent_id: null,
    visibility: 'workspace',
    sort_order: categories.value.length,
  })
  error.value = ''
}
function editCategory(item: Category) {
  categoryEdit.value = item
  Object.assign(categoryForm, {
    name: item.name,
    parent_id: item.parent_id,
    visibility: item.visibility,
    sort_order: item.sort_order,
  })
  deletion.value = null
}
function resetEnvironment() {
  environmentEdit.value = null
  Object.assign(environmentForm, {
    key: '',
    label: '',
    kind: 'custom',
    enabled: true,
    sort_order: environments.value.length,
  })
  error.value = ''
}
function editEnvironment(item: Environment) {
  environmentEdit.value = item
  Object.assign(environmentForm, {
    key: item.key,
    label: item.label,
    kind: item.kind,
    enabled: item.enabled,
    sort_order: item.sort_order,
  })
}
async function act(fn: () => Promise<void>) {
  busy.value = true
  error.value = ''
  try {
    await fn()
    emit('changed')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function saveCategory() {
  await act(async () => {
    const item = categoryEdit.value
    await api(item ? `/categories/${item.id}` : '/categories', item ? 'PATCH' : 'POST', {
      scope: props.scope,
      ...categoryForm,
      ...(item ? { version: item.version } : {}),
    })
    resetCategory()
    notify('目录已保存。')
  })
}
async function saveEnvironment() {
  await act(async () => {
    const item = environmentEdit.value
    await api(item ? `/environments/${item.id}` : '/environments', item ? 'PATCH' : 'POST', {
      scope: props.scope,
      ...environmentForm,
      ...(item ? { version: item.version } : {}),
    })
    resetEnvironment()
    notify('环境已保存。')
  })
}
async function removeCategory() {
  if (!deletion.value) return
  await act(async () => {
    const item = deletion.value!
    await api(
      `/categories/${item.id}?version=${item.version}${moveTo.value ? `&target_id=${moveTo.value}` : ''}`,
      'DELETE',
    )
    deletion.value = null
    moveTo.value = ''
    resetCategory()
    notify('目录已删除。')
  })
}
async function removeEnvironment(item: Environment) {
  if (!(await confirmAction(`删除未使用的环境“${item.label}”？`))) return
  await act(async () => {
    await api(`/environments/${item.id}?version=${item.version}`, 'DELETE')
    resetEnvironment()
    notify('环境已删除。')
  })
}
</script>
<template>
  <Sheet
    :open="true"
    :title="scope === 'team' ? '业务线与环境' : '个人分组与环境'"
    :description="scope === 'team' ? '团队空间 · 管理员维护' : '个人导航 · 由自己维护'"
    @close="emit('close')"
  >
    <GrantEditor
      v-if="granting"
      kind="categories"
      :id="granting.id"
      :members="members"
      @close="granting = null"
      @changed="emit('changed')"
    />
    <template v-else
      ><div class="panel-tabs">
        <button :class="{ selected: tab === 'categories' }" @click="tab = 'categories'">
          {{ scope === 'team' ? '业务线目录' : '个人分组' }}</button
        ><button :class="{ selected: tab === 'environments' }" @click="tab = 'environments'">环境配置</button>
      </div>
      <div v-if="error" class="form-error" role="alert">{{ error }}</div>
      <div class="catalog-filter">
        <label class="directory-search"
          ><Icon name="search" :size="15" /><span class="sr-only">查找目录或环境</span
          ><input v-model="filter" type="search" placeholder="输入名称快速定位…" maxlength="80"
        /></label>
        <span class="muted">共 {{ tab === 'categories' ? categories.length : environments.length }} 项</span>
      </div>
      <template v-if="tab === 'categories'">
        <p class="form-help">
          {{
            scope === 'team'
              ? '业务线供全体空间成员查看，由空间管理员维护。'
              : '分组由你维护，最多支持 8 层。浏览器书签导入时可以保留原文件夹层级。'
          }}
        </p>
        <div class="management-list catalog-list">
          <div v-for="item in matchingCategories" :key="item.id" class="management-row">
            <div>
              <strong>{{ categoryLabel(item) }}</strong
              ><small>{{ item.count }} 个资源</small>
            </div>
            <div class="row-actions">
              <button class="icon-button" :aria-label="`编辑目录${item.name}`" @click="editCategory(item)">
                <Icon name="edit" /></button
              ><button
                class="icon-button"
                :aria-label="`删除目录${item.name}`"
                @click="
                  () => {
                    deletion = item
                    moveTo = ''
                  }
                "
              >
                <Icon name="trash" />
              </button>
            </div>
          </div>
          <p v-if="!categories.length" class="inline-empty">还没有目录，在下方添加第一个。</p>
          <p v-else-if="!matchingCategories.length" class="inline-empty">没有匹配的目录，试试其他名称。</p>
        </div>
        <div v-if="deletion" class="notice-panel">
          <h3>删除“{{ deletion.name }}”</h3>
          <p>目录内的资源可以移到其他目录；下级分组需先移动或删除。</p>
          <label class="form-group"
            >将资源迁移到<select class="form-field" v-model="moveTo">
              <option value="">不迁移（仅空目录可删除）</option>
              <option
                v-for="item in categories.filter((row) => row.id !== deletion!.id)"
                :key="item.id"
                :value="item.id"
              >
                {{ categoryLabel(item) }}
              </option>
            </select></label
          >
          <div class="row-actions">
            <button class="button secondary" @click="deletion = null">取消</button
            ><button class="button danger" :disabled="busy" @click="removeCategory">确认删除目录</button>
          </div>
        </div>
        <form @submit.prevent="saveCategory" class="inline-form">
          <h3>{{ categoryEdit ? '编辑目录' : '添加目录' }}</h3>
          <label class="form-group"
            >目录名称<input
              class="form-field"
              v-model="categoryForm.name"
              required
              maxlength="80"
              placeholder="例如：客户服务" /></label
          ><label v-if="scope === 'personal'" class="form-group"
            >上级分组<select class="form-field" v-model="categoryForm.parent_id">
              <option :value="null">一级分组</option>
              <option v-for="item in parentChoices" :key="item.id" :value="item.id">
                {{ categoryLabel(item) }}
              </option>
            </select></label
          >
          <div class="form-row">
            <label class="form-group"
              >排序（小的在前）<input
                class="form-field"
                v-model.number="categoryForm.sort_order"
                type="number"
                min="0"
                max="100000"
                required
            /></label>
          </div>
          <div class="row-actions">
            <button v-if="categoryEdit" type="button" class="button secondary" @click="resetCategory">
              取消编辑</button
            ><button class="button primary" :disabled="busy">
              <Icon name="plus" />{{ busy ? '保存中…' : categoryEdit ? '保存目录' : '添加目录' }}
            </button>
          </div>
        </form>
      </template>
      <template v-else
        ><p class="form-help">
          环境名称可以修改。已经被入口引用的环境请停用；停用后仍保留原地址，不会切换到其他环境。
        </p>
        <div class="management-list catalog-list">
          <div v-for="item in matchingEnvironments" :key="item.id" class="management-row">
            <div>
              <strong>{{ item.label }} · {{ item.key.toUpperCase() }}</strong
              ><small>{{ item.enabled ? '已启用' : '已停用' }}</small>
            </div>
            <div class="row-actions">
              <button
                class="icon-button"
                :aria-label="`编辑环境${item.label}`"
                @click="editEnvironment(item)"
              >
                <Icon name="edit" /></button
              ><button
                class="icon-button"
                :aria-label="`删除环境${item.label}`"
                @click="removeEnvironment(item)"
              >
                <Icon name="trash" />
              </button>
            </div>
          </div>
          <p v-if="!matchingEnvironments.length" class="inline-empty">
            {{ filter ? '没有匹配的环境。' : '还没有环境，在下方添加第一个。' }}
          </p>
        </div>
        <form @submit.prevent="saveEnvironment" class="inline-form">
          <h3>{{ environmentEdit ? '编辑环境' : '添加环境' }}</h3>
          <div class="form-row">
            <label class="form-group"
              >名称<input
                class="form-field"
                v-model="environmentForm.label"
                required
                maxlength="40"
                placeholder="预发" /></label
            ><label class="form-group"
              >稳定标识<input
                class="form-field"
                v-model="environmentForm.key"
                :disabled="!!environmentEdit"
                pattern="[a-z][a-z0-9_\-]*"
                maxlength="24"
                required
                placeholder="staging"
            /></label>
          </div>
          <div class="form-row">
            <label class="form-group"
              >环境类型<select class="form-field" v-model="environmentForm.kind">
                <option value="custom">自定义</option>
                <option value="dev">开发</option>
                <option value="test">测试</option>
                <option value="prod">生产</option>
              </select></label
            ><label class="form-group"
              >排序<input
                class="form-field"
                v-model.number="environmentForm.sort_order"
                type="number"
                min="0"
                max="100000"
                required
            /></label>
          </div>
          <label class="checkbox-label"
            ><input type="checkbox" v-model="environmentForm.enabled" />启用环境</label
          >
          <div class="row-actions">
            <button v-if="environmentEdit" class="button secondary" type="button" @click="resetEnvironment">
              取消编辑</button
            ><button class="button primary" :disabled="busy">
              {{ busy ? '保存中…' : environmentEdit ? '保存环境' : '添加环境' }}
            </button>
          </div>
        </form>
      </template>
    </template>
  </Sheet>
</template>
