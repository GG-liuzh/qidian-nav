<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAuth } from '../auth'
import { categoryTree } from '../catalog'
import { roleNames, type Catalog, type View } from '../types'
import Icon from './Icon.vue'

const props = defineProps<{ view: View; category: string; catalog: Catalog; mobile?: boolean }>()
const emit = defineEmits<{
  navigate: []
  category: [value: string]
  manage: []
  settings: []
  close: []
  workspaces: []
}>()
const auth = useAuth()
const directorySearch = ref('')
const expanded = ref(new Set<string>())
const personal = computed(() => props.view === 'personal' || !auth.user?.workspace)
const canManage = computed(() => personal.value || auth.user?.role === 'admin')
const navItems = computed(() =>
  [
    { view: 'team', label: '团队导航', icon: 'layout' },
    { view: 'personal', label: '个人导航', icon: 'folder-lock' },
    { view: 'favorites', label: '我的收藏', icon: 'star' },
    { view: 'recent', label: '最近访问', icon: 'clock' },
  ].filter((item) => item.view !== 'team' || auth.user?.workspace),
)
const categories = computed(() =>
  categoryTree(
    props.catalog.categories.filter((item) =>
      props.view === 'personal'
        ? item.scope === 'personal'
        : props.view === 'team'
          ? item.scope === 'team'
          : true,
    ),
  ),
)
const categoryMap = computed(() => new Map(categories.value.map((row) => [row.id, row])))
const parents = computed(() => new Set(categories.value.map((row) => row.parent_id).filter(Boolean)))
const counts = computed(() => {
  const totals = new Map(categories.value.map((row) => [row.id, row.count]))
  for (const row of [...categories.value].reverse()) {
    if (row.parent_id && totals.has(row.parent_id))
      totals.set(row.parent_id, (totals.get(row.parent_id) || 0) + (totals.get(row.id) || 0))
  }
  return totals
})
const visibleCategories = computed(() => {
  const term = directorySearch.value.trim().normalize('NFKC').toLocaleLowerCase()
  if (term) {
    const matches = new Set<string>()
    for (const row of categories.value) {
      if (!row.name.normalize('NFKC').toLocaleLowerCase().includes(term)) continue
      let current: typeof row | undefined = row
      while (current && !matches.has(current.id)) {
        matches.add(current.id)
        current = categoryMap.value.get(current.parent_id || '')
      }
    }
    return categories.value.filter((row) => matches.has(row.id))
  }
  return categories.value.filter((row) => {
    let parent = categoryMap.value.get(row.parent_id || '')
    const seen = new Set<string>([row.id])
    while (parent && !seen.has(parent.id)) {
      if (!expanded.value.has(parent.id)) return false
      seen.add(parent.id)
      parent = categoryMap.value.get(parent.parent_id || '')
    }
    return true
  })
})
function toggle(id: string) {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
watch(
  () => [props.category, categories.value],
  () => {
    let parent = categoryMap.value.get(props.category)?.parent_id
    const next = new Set(expanded.value)
    const seen = new Set<string>()
    while (parent && !seen.has(parent)) {
      seen.add(parent)
      next.add(parent)
      parent = categoryMap.value.get(parent)?.parent_id
    }
    expanded.value = next
  },
  { immediate: true },
)
watch(
  () => props.view,
  () => {
    directorySearch.value = ''
  },
)
</script>

<template>
  <aside class="sidebar app-sidebar" aria-label="主导航">
    <button v-if="mobile" class="icon-button mobile-close" aria-label="关闭导航" @click="emit('close')">
      <Icon name="x" />
    </button>
    <RouterLink :to="auth.user?.workspace ? '/team' : '/personal'" class="brand" @click="emit('navigate')">
      <span class="brand-mark" aria-hidden="true"><span></span><span></span></span>
      <span class="brand-name">栖点<span>QIDIAN</span></span>
    </RouterLink>
    <button class="workspace workspace-switch" aria-label="选择空间或加入空间" @click="emit('workspaces')">
      <span class="workspace-avatar">{{
        (auth.user?.workspace?.name || auth.user?.display_name || '我').slice(0, 1)
      }}</span>
      <div>
        <strong :title="auth.user?.workspace?.name">{{
          auth.user?.workspace?.name || '我的个人导航'
        }}</strong>
        <small>{{ auth.user?.workspace ? '团队协作空间' : '个人账号 · 独立使用' }}</small>
      </div>
      <Icon name="down" :size="14" />
    </button>
    <nav class="main-nav" aria-label="工作空间">
      <RouterLink
        v-for="item in navItems"
        :key="item.view"
        :to="`/${item.view}`"
        class="nav-item"
        :class="{ active: view === item.view }"
        :aria-current="view === item.view ? 'page' : undefined"
        @click="emit('navigate')"
      >
        <Icon :name="item.icon" />{{ item.label }}
      </RouterLink>
      <RouterLink to="/" class="nav-item" @click="emit('navigate')"><Icon name="globe" />公开导航</RouterLink>
    </nav>

    <section class="sidebar-directory" aria-label="目录筛选">
      <div class="sidebar-section-label">
        <span
          >{{ personal ? '个人分组' : view === 'team' ? '业务目录' : '全部目录' }}
          <span class="directory-total">{{ categories.length }}</span></span
        >
        <button
          v-if="canManage"
          class="icon-button small"
          :aria-label="personal ? '管理个人分组' : '管理业务线与环境'"
          title="管理目录与环境"
          @click="emit('manage')"
        >
          <Icon name="sliders" :size="15" />
        </button>
      </div>
      <label v-if="categories.length > 6 || directorySearch" class="directory-search">
        <Icon name="search" :size="14" /><span class="sr-only">搜索目录</span>
        <input v-model="directorySearch" type="search" placeholder="查找目录…" maxlength="80" />
      </label>
      <nav class="category-nav directory-scroll" aria-label="分类目录">
        <button
          class="nav-item all-categories"
          :class="{ active: !category }"
          :aria-pressed="!category"
          @click="emit('category', '')"
        >
          <Icon name="grid" :size="15" /><span>全部{{ personal ? '分组' : '目录' }}</span>
        </button>
        <ul class="directory-list">
          <li
            v-for="item in visibleCategories"
            :key="item.id"
            class="directory-row"
            :class="{ selected: category === item.id }"
            :style="{ '--directory-depth': item.depth }"
          >
            <button
              v-if="parents.has(item.id)"
              class="directory-toggle"
              :aria-label="`${expanded.has(item.id) || directorySearch ? '收起' : '展开'}${item.name}`"
              :aria-expanded="expanded.has(item.id) || !!directorySearch"
              :disabled="!!directorySearch"
              @click="toggle(item.id)"
            >
              <Icon :name="expanded.has(item.id) || directorySearch ? 'down' : 'chevron-right'" :size="13" />
            </button>
            <span v-else class="directory-leaf" aria-hidden="true"><i /></span>
            <button
              class="directory-link"
              :aria-pressed="category === item.id"
              :title="item.name"
              @click="emit('category', category === item.id ? '' : item.id)"
            >
              <span class="category-name">{{ item.name }}</span>
              <span v-if="view === 'team' || view === 'personal'" class="nav-count">{{
                counts.get(item.id) || 0
              }}</span>
            </button>
          </li>
        </ul>
        <p v-if="directorySearch && !visibleCategories.length" class="sidebar-empty">没有匹配的目录。</p>
        <p v-else-if="!categories.length" class="sidebar-empty">
          {{ personal ? '创建分组，给常用链接一个位置。' : '还没有可见的业务目录。' }}
        </p>
      </nav>
    </section>

    <div class="sidebar-bottom">
      <button class="nav-item settings-entry" @click="emit('settings')">
        <Icon name="settings" />设置与维护<Icon name="chevron-right" :size="14" />
      </button>
      <div class="user-profile">
        <span class="avatar">{{ auth.user?.display_name.slice(0, 1) }}</span>
        <span
          ><strong :title="auth.user?.display_name">{{ auth.user?.display_name }}</strong>
          <small>{{
            auth.user?.is_superadmin
              ? '站点超级管理员'
              : auth.user?.role === 'personal'
                ? '个人账号'
                : auth.user
                  ? roleNames[auth.user.role]
                  : ''
          }}</small>
        </span>
        <span class="profile-status" title="已登录" aria-label="已登录" />
      </div>
    </div>
  </aside>
</template>
