<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  DialogRoot,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from 'reka-ui'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import type { Catalog, Endpoint, Member, Page, Resource, Shortcut, View } from '../types'
import Sidebar from '../components/Sidebar.vue'
import Icon from '../components/Icon.vue'
import ResourceCard from '../components/ResourceCard.vue'
import ResourceEditor from '../components/ResourceEditor.vue'
import ResourceDetails from '../components/ResourceDetails.vue'
import CatalogPanel from '../components/CatalogPanel.vue'
import ManagementPanel from '../components/ManagementPanel.vue'
import WorkspacePanel from '../components/WorkspacePanel.vue'

const auth = useAuth(),
  route = useRoute(),
  router = useRouter(),
  queries = useQueryClient()
const view = computed(() => (route.params.view || 'team') as View)
const category = computed(() => String(route.query.category || '')),
  env = computed(() => String(route.query.env || '')),
  search = ref(String(route.query.q || '')),
  searchInput = ref<HTMLInputElement | null>(null),
  sort = ref('default'),
  status = ref('active')
const mobileOpen = ref(false),
  editor = ref<Resource | null | undefined>(undefined),
  catalogOpen = ref(false),
  workspaceOpen = ref(false),
  editingShortcuts = ref(false),
  showAllShortcuts = ref(false),
  management = ref<{ tab: string; resource?: Resource | null; compose?: boolean } | null>(null),
  error = ref('')
const detailId = computed(() => String(route.query.resource || '')),
  detailEnv = ref<string | undefined>(undefined)
const enabled = computed(() => !!auth.user)
const catalogQuery = useQuery({
  queryKey: computed(() => ['catalog', auth.contextKey]),
  queryFn: () => api<Catalog>('/catalog'),
  enabled,
})
const membersQuery = useQuery({
  queryKey: computed(() => ['members', auth.contextKey]),
  queryFn: () => api<Member[]>('/members'),
  enabled,
})
const shortcutsQuery = useQuery({
  queryKey: computed(() => ['shortcuts', auth.contextKey]),
  queryFn: () => api<Shortcut[]>('/me/shortcuts'),
  enabled,
})
const catalog = computed(() => catalogQuery.data.value || { categories: [], environments: [] }),
  members = computed(() => membersQuery.data.value || []),
  shortcuts = computed(() => shortcutsQuery.data.value || [])
const visibleShortcuts = computed(() =>
  showAllShortcuts.value || editingShortcuts.value ? shortcuts.value : shortcuts.value.slice(0, 6),
)
const resourceQuery = useInfiniteQuery({
  queryKey: computed(() => [
    'resources',
    auth.contextKey,
    view.value,
    category.value,
    env.value,
    route.query.q || '',
    sort.value,
    status.value,
  ]),
  initialPageParam: 0,
  enabled,
  queryFn: ({ pageParam }) => {
    const params = new URLSearchParams({
      view: view.value,
      q: String(route.query.q || ''),
      sort: sort.value,
      status: status.value,
      offset: String(pageParam),
    })
    if (category.value) params.set('category_id', category.value)
    if (env.value) params.set('env', env.value)
    return api<Page<Resource>>(`/resources?${params}`)
  },
  getNextPageParam: (last) => last.next_offset ?? undefined,
})
const resources = computed(() => resourceQuery.data.value?.pages.flatMap((page) => page.items) || []),
  systems = computed(() => resources.value.filter((item) => item.type === 'system')),
  bookmarks = computed(() => resources.value.filter((item) => item.type === 'bookmark')),
  total = computed(() => resourceQuery.data.value?.pages[0]?.total || 0)
const scope = computed(() => (view.value === 'personal' || !auth.user?.workspace ? 'personal' : 'team'))
const canCreateTeam = computed(
  () =>
    auth.user?.role === 'admin' ||
    auth.user?.role === 'maintainer' ||
    catalog.value.categories.some((row) => row.scope === 'team' && row.can_edit_resources),
)
const environments = computed(() =>
  catalog.value.environments.filter(
    (row) => row.enabled && (!['team', 'personal'].includes(view.value) || row.scope === scope.value),
  ),
)
const searchEnvs = computed(() => {
  const words = String(route.query.q || '')
    .normalize('NFKC')
    .toLowerCase()
    .split(/\s+/)
  return catalog.value.environments
    .filter((item) => words.includes(item.key.toLowerCase()) || words.includes(item.label))
    .map((item) => item.id)
})
const titles = {
  team: ['每个入口，都井然有序。', '业务后台、共享账号、常用书签。你的工作，从这里开始。', '团队导航'],
  personal: ['留给自己的，好用入口。', '自己的分组、书签与资料。默认私有，也可选择公开。', '个人导航'],
  favorites: ['常用的，就放在手边。', '收藏引用原来的链接，维护人更新后这里也会同步。', '我的收藏'],
  recent: ['回到刚刚到过的地方。', '最近 30 天的访问记录，仅自己可见。', '最近访问'],
}
const heading = computed(() => titles[view.value] || titles.team)
const filtered = computed(() => !!(category.value || env.value || route.query.q || status.value !== 'active'))
const themeIcon = computed(() =>
  auth.user?.preferences.theme === 'dark' ||
  (auth.user?.preferences.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
    ? 'sun'
    : 'moon',
)
let searchTimer: ReturnType<typeof setTimeout> | undefined
function setQuery(values: Record<string, string | undefined>) {
  const query = { ...route.query, ...values }
  Object.keys(query).forEach((key) => {
    if (!query[key]) delete query[key]
  })
  void router.replace({ path: route.path, query })
}
watch(search, (value) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => setQuery({ q: value.trim() || undefined }), 180)
})
watch(
  () => route.query.q,
  (value) => {
    const next = String(value || '')
    if (search.value.trim() !== next) search.value = next
  },
)
watch(view, () => {
  mobileOpen.value = false
  status.value = 'active'
  sort.value = 'default'
})
function reset() {
  clearTimeout(searchTimer)
  search.value = ''
  status.value = 'active'
  setQuery({ category: undefined, env: undefined, q: undefined })
}
function openNew() {
  if (scope.value === 'team' && !canCreateTeam.value) {
    management.value = { tab: 'feedback', compose: true }
    return
  }
  editor.value = null
}
function openDetails(resource: Resource, environment?: string) {
  detailEnv.value = environment
  setQuery({ resource: resource.id })
}
function closeDetails() {
  setQuery({ resource: undefined })
  detailEnv.value = undefined
}
function editResource(resource: Resource) {
  closeDetails()
  editor.value = resource
}
function refresh() {
  void queries.invalidateQueries({ queryKey: ['resources'] })
  void queries.invalidateQueries({ queryKey: ['catalog'] })
  void queries.invalidateQueries({ queryKey: ['shortcuts'] })
  void queries.invalidateQueries({ queryKey: ['members'] })
}
function saved(resource: Resource) {
  editor.value = undefined
  void router.replace({ path: `/${resource.scope}`, query: { resource: resource.id } })
  refresh()
}
async function favorite(resource: Resource) {
  try {
    await api(`/me/favorites/${resource.id}`, resource.favorite ? 'DELETE' : 'PUT')
    notify(resource.favorite ? '已从收藏移除。' : '已添加到我的收藏。')
    refresh()
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function visit(endpoint: Endpoint) {
  try {
    await api('/me/visits', 'POST', { endpoint_id: endpoint.id })
    void queries.invalidateQueries({ queryKey: ['resources'] })
  } catch (e) {
    if (auth.user) notify(errorMessage(e))
  }
}
async function removeShortcut(item: Shortcut) {
  try {
    await api(`/me/shortcuts/${item.id}`, 'DELETE')
    refresh()
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function moveShortcut(item: Shortcut, direction: number) {
  const ids = shortcuts.value.map((row) => row.id),
    index = ids.indexOf(item.id),
    next = index + direction
  if (next < 0 || next >= ids.length) return
  ;[ids[index], ids[next]] = [ids[next], ids[index]]
  try {
    await api('/me/order/shortcuts', 'PUT', { ids })
    refresh()
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function setLayout(layout: 'grid' | 'list') {
  try {
    await auth.savePreferences({ layout })
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function theme() {
  const current = document.documentElement.dataset.theme
  try {
    await auth.savePreferences({ theme: current === 'dark' ? 'light' : 'dark' })
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function logout() {
  try {
    await api('/auth/logout', 'POST')
    auth.clear()
    queries.clear()
    await router.replace('/')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
function feedback(resource?: Resource) {
  closeDetails()
  mobileOpen.value = false
  management.value = { tab: 'feedback', resource, compose: true }
}
function shortcutKey(event: KeyboardEvent) {
  if (document.querySelector('[role="dialog"]')) return
  const target = event.target as HTMLElement
  if (
    ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') ||
    (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
  ) {
    event.preventDefault()
    searchInput.value?.focus()
  }
  if (event.key === 'Escape' && document.activeElement === searchInput.value) search.value = ''
}
onMounted(() => window.addEventListener('keydown', shortcutKey))
onUnmounted(() => {
  window.removeEventListener('keydown', shortcutKey)
  clearTimeout(searchTimer)
})
</script>
<template>
  <DialogRoot v-if="auth.user" v-model:open="mobileOpen"
    ><a class="skip-link" href="#main">跳到主要内容</a>
    <div class="app-shell">
      <Sidebar
        class="desktop-sidebar"
        :view="view"
        :category="category"
        :catalog="catalog"
        @category="(value) => setQuery({ category: value || undefined })"
        @manage="catalogOpen = true"
        @settings="management = { tab: 'general' }"
        @workspaces="
          () => {
            mobileOpen = false
            workspaceOpen = true
          }
        "
      />
      <div class="main-shell">
        <header class="topbar">
          <div class="breadcrumb">
            <DialogTrigger as-child
              ><button class="icon-button menu-toggle" aria-label="展开导航">
                <Icon name="menu" /></button></DialogTrigger
            ><span class="crumb-parent">工作空间</span><span class="crumb-separator">/</span
            ><strong>{{ heading[2] }}</strong>
          </div>
          <div class="topbar-actions">
            <button
              class="workspace-badge workspace-switch"
              aria-label="切换或加入空间"
              @click="workspaceOpen = true"
            >
              <i /><span class="workspace-name">{{ auth.user.workspace?.name || '加入空间' }}</span
              ><Icon name="down" :size="14" /></button
            ><button class="icon-button" aria-label="切换明暗主题" @click="theme">
              <Icon :name="themeIcon" /></button
            ><button class="icon-button" aria-label="退出登录" @click="logout"><Icon name="logout" /></button>
          </div>
        </header>
        <main id="main">
          <section class="page-heading">
            <div>
              <div class="eyebrow">
                {{ view === 'personal' ? 'A SPACE OF YOUR OWN.' : 'A LITTLE LESS SEARCHING.' }}
              </div>
              <h1>{{ heading[0] }}</h1>
              <p>{{ heading[1] }}</p>
            </div>
            <button class="button primary" @click="openNew">
              <Icon name="plus" />{{ scope === 'team' && !canCreateTeam ? '提交链接建议' : '添加链接' }}
            </button>
          </section>
          <div v-if="error" class="form-error" role="alert">
            {{ error }}<button class="text-button" @click="error = ''">关闭</button>
          </div>
          <form
            class="search-box"
            role="search"
            @submit.prevent="setQuery({ q: search.trim() || undefined })"
          >
            <Icon name="search" /><label class="sr-only" for="search">搜索系统、环境、标签或域名</label
            ><input
              id="search"
              ref="searchInput"
              v-model="search"
              type="search"
              placeholder="搜索系统、环境、标签或域名…"
              maxlength="200"
              autocomplete="off"
            /><button
              v-if="search"
              class="icon-button small"
              type="button"
              aria-label="清除搜索"
              @click="search = ''"
            >
              <Icon name="x" /></button
            ><kbd>Ctrl K</kbd>
          </form>
          <section v-if="(view === 'team' || view === 'personal') && !search" class="shortcuts-section">
            <div class="section-heading">
              <h2><Icon name="pin" />我的快捷入口</h2>
              <div class="shortcut-heading-actions">
                <span class="section-hint">直达常用环境</span>
                <button
                  v-if="shortcuts.length"
                  class="text-button"
                  :aria-pressed="editingShortcuts"
                  @click="editingShortcuts = !editingShortcuts"
                >
                  <Icon :name="editingShortcuts ? 'check' : 'sliders'" :size="14" />{{
                    editingShortcuts ? '完成整理' : '整理'
                  }}
                </button>
              </div>
            </div>
            <div v-if="shortcuts.length" class="shortcuts">
              <div
                v-for="(item, index) in visibleShortcuts"
                :key="item.id"
                class="shortcut-item"
                :class="{ editing: editingShortcuts }"
              >
                <a
                  v-if="item.enabled"
                  class="shortcut"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  @click="visit(item)"
                  ><span class="mini-icon"><Icon :name="item.icon" /></span
                  ><span class="shortcut-name">{{ item.name }}</span
                  ><span class="env-badge" :class="item.env_kind">{{ item.env_label }}</span
                  ><Icon name="external" /></a
                ><span v-else class="shortcut disabled" :title="item.disabled_reason"
                  >{{ item.name }} · {{ item.env_label }} · 已停用</span
                >
                <div v-if="editingShortcuts" class="shortcut-actions">
                  <button
                    class="icon-button"
                    aria-label="快捷入口前移"
                    :disabled="index === 0"
                    @click="moveShortcut(item, -1)"
                  >
                    <Icon name="up" /></button
                  ><button
                    class="icon-button"
                    aria-label="快捷入口后移"
                    :disabled="index === shortcuts.length - 1"
                    @click="moveShortcut(item, 1)"
                  >
                    <Icon name="down" /></button
                  ><button
                    class="icon-button"
                    :aria-label="`移除快捷入口${item.name}`"
                    @click="removeShortcut(item)"
                  >
                    <Icon name="x" />
                  </button>
                </div>
              </div>
            </div>
            <button
              v-if="shortcuts.length > 6 && !editingShortcuts"
              class="text-button shortcut-expand"
              @click="showAllShortcuts = !showAllShortcuts"
            >
              {{ showAllShortcuts ? '收起快捷入口' : `查看全部 ${shortcuts.length} 个快捷入口`
              }}<Icon :name="showAllShortcuts ? 'up' : 'down'" :size="14" />
            </button>
            <p v-if="!shortcuts.length" class="shortcut-empty">
              打开一个系统的详情，点击图钉，即可把常用环境放在这里。
            </p>
          </section>
          <section class="resources-section">
            <div class="resources-toolbar">
              <div class="resource-heading">
                <h2>
                  {{
                    category
                      ? catalog.categories.find((row) => row.id === category)?.name || '筛选结果'
                      : view === 'personal'
                        ? '我的书签'
                        : view === 'favorites'
                          ? '收藏的入口'
                          : view === 'recent'
                            ? '最近打开'
                            : '全部资源'
                  }}
                </h2>
                <span class="result-count" role="status" aria-live="polite">{{ total }}</span
                ><button v-if="filtered" class="text-button" @click="reset">重置筛选</button>
              </div>
              <div class="resource-controls">
                <label v-if="environments.length > 4" class="environment-select"
                  ><Icon name="sliders" :size="15" /><span class="sr-only">筛选环境</span>
                  <select
                    :value="env"
                    @change="setQuery({ env: ($event.target as HTMLSelectElement).value || undefined })"
                  >
                    <option value="">全部环境</option>
                    <option v-for="item in environments" :key="item.id" :value="item.id">
                      {{ item.label }}
                    </option>
                  </select>
                </label>
                <div v-else class="environment-filter" role="group" aria-label="筛选环境">
                  <button
                    :class="{ selected: !env }"
                    :aria-pressed="!env"
                    @click="setQuery({ env: undefined })"
                  >
                    全部环境</button
                  ><button
                    v-for="item in environments"
                    :key="item.id"
                    :class="{ selected: env === item.id }"
                    :aria-pressed="env === item.id"
                    @click="setQuery({ env: item.id })"
                  >
                    <i class="env-dot" :class="item.kind" />{{ item.label }}
                  </button>
                </div>
                <div class="layout-toggle" role="group" aria-label="布局">
                  <button
                    class="icon-button"
                    :class="{ selected: auth.user.preferences.layout === 'grid' }"
                    aria-label="卡片视图"
                    @click="setLayout('grid')"
                  >
                    <Icon name="grid" /></button
                  ><button
                    class="icon-button"
                    :class="{ selected: auth.user.preferences.layout === 'list' }"
                    aria-label="列表视图"
                    @click="setLayout('list')"
                  >
                    <Icon name="list" />
                  </button>
                </div>
              </div>
            </div>
            <div class="filter-summary">
              <span>{{
                scope === 'personal' ? '个人资料归自己，公开范围由自己决定' : '为团队整理的每一个工作入口'
              }}</span>
              <div class="row-actions">
                <label
                  ><span class="sr-only">资源状态</span
                  ><select class="quiet-select" v-model="status">
                    <option value="active">正常资源</option>
                    <option value="archived">已归档</option>
                  </select></label
                ><label class="sort-label"
                  ><span class="sr-only">排序方式</span
                  ><select v-model="sort">
                    <option value="default">默认排序</option>
                    <option value="name">名称排序</option>
                    <option value="updated">最近更新</option>
                  </select></label
                >
              </div>
            </div>
            <div
              v-if="resourceQuery.isError.value || catalogQuery.isError.value"
              class="notice-panel"
              role="alert"
            >
              {{ errorMessage(resourceQuery.error.value || catalogQuery.error.value)
              }}<button class="text-button" @click="refresh">重新加载</button>
            </div>
            <div v-else-if="resourceQuery.isPending.value" class="loading-grid" role="status">
              <div v-for="item in 3" :key="item" class="skeleton-card" />
              <span class="sr-only">正在加载资源</span>
            </div>
            <template v-else
              ><div
                v-if="systems.length"
                class="resource-grid"
                :class="{ 'list-view': auth.user.preferences.layout === 'list' }"
              >
                <ResourceCard
                  v-for="item in systems"
                  :key="item.id"
                  :resource="item"
                  :env="env"
                  :search-envs="searchEnvs"
                  @details="openDetails"
                  @edit="editResource"
                  @favorite="favorite"
                  @visit="visit"
                />
              </div>
              <section v-if="bookmarks.length" class="bookmarks-section">
                <div class="section-heading">
                  <h2>通用书签<span class="section-caption">好用的工具，也有自己的位置</span></h2>
                  <span class="section-hint">不区分环境</span>
                </div>
                <div class="bookmark-grid" :class="{ 'list-view': auth.user.preferences.layout === 'list' }">
                  <ResourceCard
                    v-for="item in bookmarks"
                    :key="item.id"
                    :resource="item"
                    @details="openDetails"
                    @edit="editResource"
                    @favorite="favorite"
                    @visit="visit"
                  />
                </div>
              </section>
              <div v-if="!resources.length" class="empty-state">
                <Icon
                  :name="filtered ? 'search' : view === 'personal' ? 'folder-lock' : 'compass'"
                  :size="36"
                />
                <h3>
                  {{
                    filtered
                      ? '暂时没有找到匹配的入口'
                      : view === 'favorites'
                        ? '把常用的入口，先收藏起来'
                        : view === 'recent'
                          ? '从打开第一个入口开始'
                          : '从第一个好用的链接开始'
                  }}
                </h3>
                <p>
                  {{
                    filtered
                      ? '试试其他关键词，或切换到全部环境。'
                      : view === 'personal'
                        ? '添加自己的书签，也可以先创建个人分组。'
                        : view === 'recent'
                          ? '你在导航中打开的链接会出现在这里。'
                          : '添加业务系统或普通书签，让团队少一点寻找。'
                  }}
                </p>
                <button v-if="filtered" class="button secondary" @click="reset">清除筛选</button
                ><button
                  v-else-if="view === 'team' || view === 'personal'"
                  class="button primary"
                  @click="openNew"
                >
                  <Icon name="plus" />{{
                    scope === 'team' && !canCreateTeam ? '提交链接建议' : '添加第一个链接'
                  }}</button
                ><RouterLink v-else class="button secondary" to="/team">去团队导航</RouterLink>
              </div>
              <div v-if="resourceQuery.hasNextPage.value" class="load-more">
                <button
                  class="button secondary"
                  :disabled="resourceQuery.isFetchingNextPage.value"
                  @click="resourceQuery.fetchNextPage()"
                >
                  {{ resourceQuery.isFetchingNextPage.value ? '正在加载…' : '加载更多' }}
                </button>
              </div>
            </template>
          </section>
          <footer class="page-footer">
            <span><span class="footer-logo">栖点</span>让链接有处可寻。</span
            ><span>{{ auth.user.workspace?.name || '个人导航' }} · {{ auth.user.display_name }}</span>
          </footer>
        </main>
      </div>
    </div>
    <DialogPortal
      ><DialogOverlay class="sheet-overlay" /><DialogContent class="mobile-nav-content"
        ><DialogTitle class="sr-only">工作空间导航</DialogTitle
        ><DialogDescription class="sr-only">选择团队导航、个人导航或业务线。</DialogDescription
        ><Sidebar
          mobile
          :view="view"
          :category="category"
          :catalog="catalog"
          @navigate="mobileOpen = false"
          @close="mobileOpen = false"
          @category="
            (value) => {
              setQuery({ category: value || undefined })
              mobileOpen = false
            }
          "
          @manage="
            () => {
              mobileOpen = false
              catalogOpen = true
            }
          "
          @settings="
            () => {
              mobileOpen = false
              management = { tab: 'general' }
            }
          "
          @workspaces="
            () => {
              mobileOpen = false
              workspaceOpen = true
            }
          " /></DialogContent
    ></DialogPortal>
    <ResourceEditor
      v-if="editor !== undefined"
      :resource="editor"
      :scope="scope"
      :category-id="category"
      :catalog="catalog"
      :members="members"
      @close="editor = undefined"
      @saved="saved"
      @catalog-change="refresh"
    />
    <ResourceDetails
      v-if="detailId && editor === undefined"
      :key="detailId"
      :id="detailId"
      :env="detailEnv"
      :members="members"
      :shortcuts="shortcuts"
      @close="closeDetails"
      @edit="editResource"
      @changed="refresh"
      @feedback="feedback"
      @visit="visit"
    />
    <CatalogPanel
      v-if="catalogOpen"
      :catalog="catalog"
      :scope="scope"
      :members="members"
      @close="catalogOpen = false"
      @changed="refresh"
    />
    <ManagementPanel
      v-if="management"
      :catalog="catalog"
      :initial-tab="management.tab"
      :resource="management.resource"
      :compose="management.compose"
      @close="management = null"
      @changed="refresh"
    />
    <WorkspacePanel
      v-if="workspaceOpen"
      @close="workspaceOpen = false"
      @administration="
        () => {
          workspaceOpen = false
          management = { tab: 'platform' }
        }
      "
    />
  </DialogRoot>
</template>
