<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/vue-query'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import type { PublicResource } from '../types'
import Icon from '../components/Icon.vue'
import ResourceCard from '../components/ResourceCard.vue'
import Sheet from '../components/Sheet.vue'

interface PublicResult {
  workspace_id: string | null
  spaces: { id: string; name: string }[]
  title: string
  scope: string
  owner_id: string | null
  items: PublicResource[]
  categories: { id: string; name: string; count: number }[]
  environments: { id: string; label: string; kind: string; key: string }[]
  total: number
  next_offset: number | null
}
const auth = useAuth(),
  route = useRoute(),
  router = useRouter(),
  queries = useQueryClient(),
  search = ref(''),
  query = ref(''),
  category = ref(''),
  env = ref(''),
  detail = ref<PublicResource | null>(null),
  layout = ref('grid')
const favoriteQuery = useQuery({
  queryKey: computed(() => ['favorite-ids', auth.contextKey]),
  enabled: computed(() => !!auth.user),
  queryFn: () => api<string[]>('/me/favorites'),
})
const favorites = computed(() => new Set(favoriteQuery.data.value || []))
const workspaceId = computed(() => String(route.params.workspace || ''))
const owner = computed(() => String(route.params.owner || '')),
  home = computed(() => (auth.user?.workspace ? '/team' : '/personal'))
const result = useInfiniteQuery({
  queryKey: computed(() => [
    'public',
    owner.value,
    workspaceId.value,
    query.value,
    category.value,
    env.value,
  ]),
  initialPageParam: 0,
  queryFn: ({ pageParam }) => {
    const params = new URLSearchParams({ q: query.value, offset: String(pageParam) })
    if (owner.value) params.set('owner', owner.value)
    if (workspaceId.value) params.set('workspace_id', workspaceId.value)
    if (category.value) params.set('category_id', category.value)
    if (env.value) params.set('env', env.value)
    return api<PublicResult>(`/public/navigation?${params}`)
  },
  getNextPageParam: (last) => last.next_offset ?? undefined,
})
const info = computed(() => result.data.value?.pages[0]),
  resources = computed(
    () =>
      result.data.value?.pages
        .flatMap((page) => page.items)
        .map((row) => ({ ...row, favorite: favorites.value.has(row.id) })) || [],
  ),
  systems = computed(() => resources.value.filter((row) => row.type === 'system')),
  bookmarks = computed(() => resources.value.filter((row) => row.type === 'bookmark'))
const searchEnvs = computed(() => {
  const words = query.value.normalize('NFKC').toLowerCase().split(/\s+/)
  return (info.value?.environments || [])
    .filter((row) => words.includes(row.key.toLowerCase()) || words.includes(row.label))
    .map((row) => row.id)
})
let timer: ReturnType<typeof setTimeout> | undefined
watch(search, (value) => {
  clearTimeout(timer)
  timer = setTimeout(() => {
    query.value = value.trim()
  }, 180)
})
watch([owner, workspaceId], () => {
  category.value = ''
  env.value = ''
  search.value = ''
})
onUnmounted(() => clearTimeout(timer))
async function favorite(resource: PublicResource) {
  if (!auth.user) {
    await router.push({ path: '/login', query: { return: route.fullPath } })
    return
  }
  try {
    const saved = favorites.value.has(resource.id)
    await api(`/me/favorites/${resource.id}`, saved ? 'DELETE' : 'PUT')
    await queries.invalidateQueries({ queryKey: ['favorite-ids'] })
    await queries.invalidateQueries({ queryKey: ['resources'] })
    notify(saved ? '已从收藏移除。' : '已收藏到自己的账号。')
  } catch (e) {
    notify(errorMessage(e))
  }
}
function toggleTheme() {
  document.documentElement.dataset.theme =
    document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'
}
</script>
<template>
  <div class="app-shell">
    <aside class="sidebar desktop-sidebar public-sidebar" aria-label="公开导航目录">
      <RouterLink class="brand" to="/"
        ><span class="brand-mark"><span></span><span></span></span
        ><span class="brand-name">栖点<span>QIDIAN</span></span></RouterLink
      >
      <div class="workspace">
        <span class="workspace-avatar"><Icon name="globe" /></span>
        <div>
          <strong>{{ info?.title || '栖点导航' }}</strong
          ><small>公开链接 · 免登录浏览</small>
        </div>
      </div>
      <nav class="main-nav">
        <RouterLink to="/" class="nav-item" :class="{ active: !owner }"
          ><Icon name="globe" />公开导航</RouterLink
        ><RouterLink :to="auth.user ? home : '/login'" class="nav-item"
          ><Icon name="folder-lock" />我的导航</RouterLink
        >
      </nav>
      <div class="sidebar-section-label">分类目录</div>
      <nav class="category-nav">
        <button class="nav-item" :class="{ active: !category }" @click="category = ''">
          <Icon name="layout" />全部分类</button
        ><button
          v-for="item in info?.categories || []"
          :key="item.id"
          class="nav-item"
          :class="{ active: category === item.id }"
          @click="category = item.id"
        >
          <span class="category-icon trade"><i /></span>{{ item.name
          }}<span class="nav-count">{{ item.count }}</span>
        </button>
      </nav>
      <div class="sidebar-bottom">
        <div class="sidebar-note">
          <Icon name="compass" /><strong>浏览轻松，资料有归属。</strong>
          <p>公开的入口随时可用，登录后整理自己的收藏，也能参与团队维护。</p>
          <RouterLink
            :to="auth.user ? home : auth.registrationEnabled ? '/signup' : '/login'"
            class="text-button"
            >{{ auth.user ? '进入我的导航' : auth.registrationEnabled ? '创建个人账号' : '登录我的账号'
            }}<Icon name="arrow"
          /></RouterLink>
        </div>
      </div>
    </aside>
    <div class="main-shell">
      <header class="topbar">
        <div class="breadcrumb">
          <Icon name="globe" /><span>{{ owner ? '个人公开页' : '公开导航' }}</span>
        </div>
        <div class="topbar-actions">
          <button class="icon-button" aria-label="切换明暗主题" @click="toggleTheme">
            <Icon name="moon" /></button
          ><RouterLink v-if="auth.needsSetup" class="button primary" to="/setup">初始化我的导航</RouterLink
          ><RouterLink v-else class="button primary" :to="auth.user ? home : '/login'"
            ><Icon :name="auth.user ? 'folder-lock' : 'users'" />{{
              auth.user ? '进入我的导航' : '登录参与维护'
            }}</RouterLink
          >
        </div>
      </header>
      <main id="main">
        <section class="page-heading">
          <div>
            <div class="eyebrow">OPEN LINKS. YOUR OWN SPACE.</div>
            <h1>{{ info?.title || '好用的入口，随时找到。' }}</h1>
            <p>公开链接直接访问；登录后收藏、整理，让工作和自己的资料都有归处。</p>
          </div>
          <span class="public-label"><Icon name="globe" />无需登录即可浏览</span>
        </section>
        <form class="search-box" role="search" @submit.prevent="query = search.trim()">
          <Icon name="search" /><label class="sr-only" for="public-search">搜索公开链接</label
          ><input
            id="public-search"
            v-model="search"
            type="search"
            placeholder="搜索系统、书签、环境或域名…"
            maxlength="200"
            autocomplete="off"
          /><button
            v-if="search"
            type="button"
            class="icon-button"
            aria-label="清除搜索"
            @click="search = ''"
          >
            <Icon name="x" />
          </button>
        </form>
        <div v-if="!owner && (info?.spaces.length || 0) > 1" class="public-space-switch">
          <label
            >公开空间<select
              class="form-field"
              aria-label="切换公开空间"
              :value="workspaceId || info?.workspace_id || ''"
              @change="(event) => router.push(`/w/${(event.target as HTMLSelectElement).value}`)"
            >
              <option v-for="space in info?.spaces || []" :key="space.id" :value="space.id">
                {{ space.name }}
              </option>
            </select></label
          >
        </div>
        <section class="resources-section">
          <div class="resources-toolbar">
            <div class="resource-heading">
              <h2>{{ category ? info?.categories.find((row) => row.id === category)?.name : '公开入口' }}</h2>
              <span class="result-count" role="status">{{ info?.total || 0 }}</span
              ><button
                v-if="category || query || env"
                class="text-button"
                @click="
                  () => {
                    category = ''
                    search = ''
                    env = ''
                  }
                "
              >
                清除筛选
              </button>
            </div>
            <div class="resource-controls">
              <select class="public-category-select form-field" aria-label="公开分类" v-model="category">
                <option value="">全部分类</option>
                <option v-for="item in info?.categories || []" :key="item.id" :value="item.id">
                  {{ item.name }}
                </option>
              </select>
              <label v-if="(info?.environments.length || 0) > 4" class="environment-select"
                ><span class="sr-only">筛选环境</span>
                <select v-model="env">
                  <option value="">全部环境</option>
                  <option v-for="item in info?.environments || []" :key="item.id" :value="item.id">
                    {{ item.label }}
                  </option>
                </select>
              </label>
              <div v-else class="environment-filter" role="group" aria-label="筛选环境">
                <button :class="{ selected: !env }" @click="env = ''">全部环境</button
                ><button
                  v-for="item in info?.environments || []"
                  :key="item.id"
                  :class="{ selected: env === item.id }"
                  @click="env = item.id"
                >
                  <i class="env-dot" :class="item.kind" />{{ item.label }}
                </button>
              </div>
              <div class="layout-toggle">
                <button class="icon-button" aria-label="卡片视图" @click="layout = 'grid'">
                  <Icon name="grid" /></button
                ><button class="icon-button" aria-label="列表视图" @click="layout = 'list'">
                  <Icon name="list" />
                </button>
              </div>
            </div>
          </div>
          <div v-if="result.isError.value" class="notice-panel" role="alert">
            {{ errorMessage(result.error.value)
            }}<RouterLink v-if="auth.user" class="text-button" :to="home">回到我的导航</RouterLink>
          </div>
          <p v-else-if="result.isPending.value" class="inline-empty" role="status">正在读取公开导航…</p>
          <template v-else
            ><div v-if="systems.length" class="resource-grid" :class="{ 'list-view': layout === 'list' }">
              <ResourceCard
                v-for="resource in systems"
                :key="resource.id"
                guest
                :resource="resource"
                :env="env"
                :search-envs="searchEnvs"
                @details="(value) => (detail = value)"
                @favorite="favorite"
              />
            </div>
            <section v-if="bookmarks.length" class="bookmarks-section">
              <div class="section-heading">
                <h2>通用书签</h2>
                <span class="section-hint">好用的资料与工具</span>
              </div>
              <div class="bookmark-grid" :class="{ 'list-view': layout === 'list' }">
                <ResourceCard
                  v-for="resource in bookmarks"
                  :key="resource.id"
                  guest
                  :resource="resource"
                  @details="(value) => (detail = value)"
                  @favorite="favorite"
                />
              </div>
            </section>
            <div v-if="!resources.length" class="empty-state">
              <Icon name="compass" :size="38" />
              <h3>{{ query || category || env ? '暂时没有匹配的入口' : '这里还没有公开的链接' }}</h3>
              <p>链接的维护人可以选择公开哪些内容。个人私有资料和账号密码不会显示在这里。</p>
              <RouterLink v-if="auth.user" class="button secondary" :to="home">管理我的导航</RouterLink
              ><RouterLink v-else-if="!auth.needsSetup" class="button secondary" to="/login"
                >登录查看自己的内容</RouterLink
              >
            </div>
            <div v-if="result.hasNextPage.value" class="load-more">
              <button
                class="button secondary"
                :disabled="result.isFetchingNextPage.value"
                @click="result.fetchNextPage()"
              >
                加载更多
              </button>
            </div></template
          >
        </section>
        <footer class="page-footer">
          <span><span class="footer-logo">栖点</span>让链接有处可寻。</span
          ><span>公开浏览 · 个人独立 · 团队协作</span>
        </footer>
      </main>
    </div>
    <Sheet
      v-if="detail"
      :open="true"
      :title="detail.name"
      description="公开链接与使用说明"
      @close="detail = null"
      ><p class="drawer-intro">{{ detail.description || '维护人还没有填写使用说明。' }}</p>
      <div v-for="endpoint in detail.endpoints" :key="endpoint.id" class="destination-box">
        <span class="env-badge" :class="endpoint.env_kind">{{ endpoint.env_label }}</span
        ><a
          v-if="endpoint.enabled"
          :href="endpoint.url"
          target="_blank"
          rel="noopener noreferrer"
          class="destination-url"
          >{{ endpoint.url }}<Icon name="external"
        /></a>
        <p v-else class="muted">{{ endpoint.disabled_reason }}</p>
      </div>
      <div class="tags">
        <span v-for="tag in detail.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <p class="form-help">维护人：{{ detail.maintainer_name }}</p>
      <RouterLink class="button secondary" :to="auth.user ? home : '/login'">{{
        auth.user ? '进入我的导航' : '登录后收藏与参与维护'
      }}</RouterLink></Sheet
    >
  </div>
</template>
