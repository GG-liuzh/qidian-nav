<script setup lang="ts">
import { confirmAction } from '../confirm'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { api, errorMessage, notify } from '../api'
import { useAuth } from '../auth'
import type { Catalog, Resource, User } from '../types'
import Sheet from './Sheet.vue'
import Icon from './Icon.vue'
import MembersPanel from './MembersPanel.vue'
import FeedbackPanel from './FeedbackPanel.vue'
import TransferPanel from './TransferPanel.vue'
import BookmarkImportPanel from './BookmarkImportPanel.vue'
import AdministrationPanel from './AdministrationPanel.vue'
import RoleHelp from './RoleHelp.vue'

const props = defineProps<{
  catalog: Catalog
  initialTab?: string
  resource?: Resource | null
  compose?: boolean
}>()
const emit = defineEmits<{ close: []; changed: [] }>()
const auth = useAuth(),
  router = useRouter(),
  queries = useQueryClient(),
  tab = ref(props.initialTab || 'general'),
  error = ref(''),
  busy = ref(false)
const loading = ref(false)
const settingsBody = ref<HTMLElement | null>(null)
let loadSequence = 0
const name = ref(auth.user?.display_name || ''),
  workspaceName = ref(auth.user?.workspace?.name || ''),
  theme = ref<User['preferences']['theme']>(auth.user?.preferences.theme || 'system'),
  layout = ref<User['preferences']['layout']>(auth.user?.preferences.layout || 'grid'),
  recordVisits = ref(auth.user?.preferences.record_visits ?? true),
  oldPassword = ref(''),
  password = ref('')
const publicEnabled = ref(auth.user?.workspace?.public_enabled ?? true),
  workspaceVersion = ref(auth.user?.workspace?.version),
  recoveryPassword = ref(''),
  publicLinkInput = ref<HTMLInputElement | null>(null)
const publicLink = computed(() => `${location.origin}${auth.user?.public_profile_url || '/'}`)
const trash = ref<Resource[]>([]),
  events = ref<
    {
      id: string
      actor_name: string
      action: string
      target_name: string
      created_at: string
      detail: Record<string, unknown>
    }[]
  >([])
const groups = computed(() => [
  {
    label: '我的账号',
    items: [
      { key: 'general', label: '个人偏好', icon: 'sliders', description: '让你的导航，用起来更顺手。' },
      {
        key: 'security',
        label: '登录与安全',
        icon: 'shield',
        description: '管理登录密码、设备会话与账户恢复方式。',
      },
      { key: 'public', label: '公开主页', icon: 'globe', description: '分享你明确选择公开的个人链接。' },
    ],
  },
  ...(auth.user?.workspace
    ? [
        {
          label: '当前空间',
          items: [
            {
              key: 'workspace',
              label: '空间设置',
              icon: 'layout',
              description: '管理当前空间的名称、公开范围与成员资格。',
            },
            ...(auth.user.role === 'admin'
              ? [
                  {
                    key: 'members',
                    label: '成员与邀请',
                    icon: 'users',
                    description: '邀请同事加入，为每个人分配合适的角色。',
                  },
                ]
              : []),
            {
              key: 'feedback',
              label: '建议与反馈',
              icon: 'feedback',
              description: '补充工作入口，跟进链接与账号问题。',
            },
            {
              key: 'roles',
              label: '角色说明',
              icon: 'info',
              description: '了解空间成员、维护人与管理员的职责。',
            },
          ],
        },
      ]
    : []),
  {
    label: '数据管理',
    items: [
      {
        key: 'bookmarks',
        label: '导入浏览器书签',
        icon: 'book',
        description: '将浏览器里的书签和文件夹整理到个人导航。',
      },
      {
        key: 'transfer',
        label: '个人迁移',
        icon: 'package',
        description: '将自己的资料安全地带到另一台栖点服务。',
      },
      {
        key: 'exports',
        label: '导出链接清单',
        icon: 'download',
        description: '下载可读的链接清单，便于归档和整理。',
      },
      { key: 'trash', label: '回收站', icon: 'trash', description: '找回最近 30 天内删除的链接。' },
      { key: 'audit', label: '操作记录', icon: 'history', description: '查看你有权限访问的近期操作。' },
    ],
  },
  ...(auth.user?.is_superadmin
    ? [
        {
          label: '站点管理',
          items: [
            {
              key: 'platform',
              label: '超级管理',
              icon: 'settings',
              description: '管理站点账号、协作空间与首页入口。',
            },
          ],
        },
      ]
    : []),
])
const tabs = computed(() => groups.value.flatMap((group) => group.items))
const activeTab = computed(() => tabs.value.find((item) => item.key === tab.value) || tabs.value[0])
watch(
  tabs,
  (items) => {
    if (!items.some((item) => item.key === tab.value)) tab.value = 'general'
  },
  { immediate: true },
)
const actionNames: Record<string, string> = {
  'workspace.setup': '创建空间',
  'workspace.updated': '修改空间设置',
  'auth.login': '登录',
  'auth.join': '加入团队',
  'auth.invite_created': '创建邀请',
  'auth.invite_revoked': '撤销邀请',
  'auth.reset_created': '发起密码重置',
  'auth.password_changed': '修改登录密码',
  'auth.password_reset': '重置登录密码',
  'auth.logout_all': '退出所有设备',
  'member.updated': '修改成员权限',
  'category.created': '添加目录',
  'category.updated': '修改目录',
  'category.deleted': '删除目录',
  'category.grant_changed': '修改目录授权',
  'environment.created': '添加环境',
  'environment.updated': '修改环境',
  'environment.deleted': '删除环境',
  'resource.created': '添加链接',
  'resource.updated': '更新链接',
  'resource.deleted': '移入回收站',
  'resource.restored': '恢复链接',
  'resource.grant_changed': '修改链接授权',
  'credential.created': '添加账号',
  'credential.updated': '更新账号',
  'credential.deleted': '删除账号',
  'credential.access': '获准读取账号',
  'credential.access_denied': '账号读取被拒绝',
  'credential.grant_changed': '修改账号授权',
  'feedback.created': '提交建议',
  'feedback.resolved': '处理建议',
}
async function load() {
  const sequence = ++loadSequence
  error.value = ''
  loading.value = ['trash', 'audit'].includes(tab.value)
  try {
    if (tab.value === 'trash') {
      const result = await api<Resource[]>('/trash')
      if (sequence === loadSequence) trash.value = result
    }
    if (tab.value === 'audit') {
      const result = await api<typeof events.value>('/audit-events')
      if (sequence === loadSequence) events.value = result
    }
  } catch (e) {
    if (sequence === loadSequence) error.value = errorMessage(e)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}
async function save() {
  busy.value = true
  error.value = ''
  try {
    await auth.savePreferences({
      display_name: name.value,
      theme: theme.value,
      layout: layout.value,
      record_visits: recordVisits.value,
    })
    emit('changed')
    notify('个人设置已保存。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function saveWorkspace() {
  busy.value = true
  error.value = ''
  try {
    await api('/workspace', auth.user?.workspace ? 'PATCH' : 'POST', {
      name: workspaceName.value,
      public_enabled: publicEnabled.value,
      version: workspaceVersion.value,
    })
    auth.accept(await api<User>('/me'))
    emit('changed')
    workspaceVersion.value = auth.user?.workspace?.version
    notify('空间设置已保存。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function selectSpace(id: string) {
  await auth.selectWorkspace(id)
  emit('close')
  await router.replace('/team')
}
async function leaveWorkspace() {
  if (
    !(await confirmAction(
      '离开后将失去部门访问与维护权限，你的个人账号、个人导航和迁移功能会保留。确认离开？',
    ))
  )
    return
  busy.value = true
  error.value = ''
  try {
    auth.accept(await api<User>('/workspace/leave', 'POST'))
    queries.clear()
    emit('close')
    await router.replace('/personal')
    notify('已离开部门，个人导航仍可正常使用。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function recoveryCode() {
  busy.value = true
  error.value = ''
  try {
    const result = await api<{ recovery_code: string }>('/me/recovery-code', 'POST', {
      password: recoveryPassword.value,
    })
    recoveryPassword.value = ''
    auth.recoveryCode = result.recovery_code
    if (auth.user) auth.user.has_recovery_code = true
    emit('close')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function copyPublicLink() {
  try {
    await navigator.clipboard.writeText(publicLink.value)
    notify('个人公开页地址已复制。')
  } catch {
    publicLinkInput.value?.focus()
    publicLinkInput.value?.select()
    notify('请手动复制已选中的地址。')
  }
}
async function transferred() {
  auth.accept(await api<User>('/me'))
  name.value = auth.user!.display_name
  theme.value = auth.user!.preferences.theme
  layout.value = auth.user!.preferences.layout
  recordVisits.value = auth.user!.preferences.record_visits
  await queries.invalidateQueries()
  emit('changed')
}
async function clearVisits() {
  if (!(await confirmAction('清空你自己的全部最近访问记录？'))) return
  try {
    await api('/me/visits', 'DELETE')
    emit('changed')
    notify('最近访问已清空。')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function changePassword() {
  busy.value = true
  error.value = ''
  try {
    await api('/me/password', 'POST', { old_password: oldPassword.value, password: password.value })
    oldPassword.value = ''
    password.value = ''
    auth.clear()
    queries.clear()
    emit('close')
    await router.replace('/login')
    notify('密码已更新，请重新登录。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function logoutAll() {
  if (!(await confirmAction('退出所有设备上的登录？'))) return
  try {
    await api('/auth/logout-all', 'POST')
    auth.clear()
    queries.clear()
    emit('close')
    await router.replace('/login')
  } catch (e) {
    error.value = errorMessage(e)
  }
}
async function restore(item: Resource) {
  busy.value = true
  try {
    await api(`/trash/${item.id}/restore`, 'POST', { version: item.version })
    await load()
    emit('changed')
    notify('链接已恢复；关联账号需要维护人重新确认。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
watch(tab, async () => {
  oldPassword.value = ''
  password.value = ''
  recoveryPassword.value = ''
  void load()
  await nextTick()
  settingsBody.value?.scrollTo({ top: 0 })
})
onMounted(load)
</script>
<template>
  <Sheet
    :open="true"
    title="设置与维护"
    description="栖点 / 工作空间"
    wide
    layout="settings"
    @close="emit('close')"
  >
    <div class="settings-layout">
      <nav class="settings-nav" aria-label="设置分类">
        <section v-for="group in groups" :key="group.label" class="settings-nav-group">
          <h3>{{ group.label }}</h3>
          <button
            v-for="item in group.items"
            :key="item.key"
            :class="{ selected: tab === item.key }"
            :aria-current="tab === item.key ? 'page' : undefined"
            :disabled="busy"
            @click="tab = item.key"
          >
            <Icon :name="item.icon" :size="16" /><span>{{ item.label }}</span>
          </button>
        </section>
      </nav>
      <label class="settings-mobile-select"
        ><span>设置分类</span>
        <select v-model="tab" class="form-field" :disabled="busy" aria-label="设置分类">
          <optgroup v-for="group in groups" :key="group.label" :label="group.label">
            <option v-for="item in group.items" :key="item.key" :value="item.key">{{ item.label }}</option>
          </optgroup>
        </select>
      </label>
      <div ref="settingsBody" class="settings-content" :aria-busy="loading">
        <header class="settings-section-heading">
          <span class="settings-section-icon"><Icon :name="activeTab.icon" :size="22" /></span>
          <div>
            <h2>{{ activeTab.label }}</h2>
            <p>{{ activeTab.description }}</p>
          </div>
        </header>
        <div v-if="error" class="form-error" role="alert">{{ error }}</div>
        <p v-if="loading" class="inline-empty" role="status">正在加载…</p>
        <template v-if="tab === 'general'"
          ><form @submit.prevent="save" class="inline-form">
            <h3>显示与浏览</h3>
            <label class="form-group"
              >显示姓名<input class="form-field" v-model="name" required maxlength="80"
            /></label>
            <div class="form-row">
              <label class="form-group"
                >主题<select class="form-field" v-model="theme">
                  <option value="system">跟随系统</option>
                  <option value="light">浅色</option>
                  <option value="dark">深色</option>
                </select></label
              ><label class="form-group"
                >默认布局<select class="form-field" v-model="layout">
                  <option value="grid">卡片</option>
                  <option value="list">列表</option>
                </select></label
              >
            </div>
            <label class="checkbox-label"
              ><input v-model="recordVisits" type="checkbox" />记录我的最近访问（保留最近 30 天）</label
            >
            <div class="row-actions">
              <button class="button primary" :disabled="busy">保存个人设置</button
              ><button type="button" class="text-button" @click="clearVisits">清空最近访问</button>
            </div>
          </form>
        </template>
        <template v-else-if="tab === 'public'">
          <section class="inline-form">
            <h3>我的公开导航页</h3>
            <p class="form-help">
              编辑个人链接时，勾选“公开此链接”即可出现在这个地址。其他个人资料保持私有。
            </p>
            <label class="form-group"
              >公开页地址<input ref="publicLinkInput" class="form-field" readonly :value="publicLink"
            /></label>
            <div class="row-actions">
              <button class="button secondary" @click="copyPublicLink">
                <Icon name="copy" />复制公开页地址</button
              ><a class="text-button" :href="publicLink" target="_blank" rel="noopener noreferrer"
                >打开我的公开页<Icon name="external"
              /></a>
            </div>
          </section>
        </template>
        <template v-else-if="tab === 'workspace'">
          <form v-if="auth.user?.role === 'admin'" @submit.prevent="saveWorkspace" class="inline-form">
            <h3>{{ auth.user?.workspace ? '部门协作' : '启用部门协作（可选）' }}</h3>
            <p class="form-help">设置只作用于当前空间，个人资料独立保存。</p>
            <label class="form-group"
              >空间名称<input class="form-field" v-model="workspaceName" required maxlength="80" /></label
            ><label class="checkbox-label"
              ><input v-model="publicEnabled" type="checkbox" />允许游客浏览明确公开的团队链接</label
            >
            <p class="form-help">开启后，仅明确勾选公开且处于启用状态的链接对游客可见；业务账号不会公开。</p>
            <button class="button secondary" :disabled="busy">
              {{ auth.user?.workspace ? '保存部门设置' : '创建部门空间' }}
            </button>
          </form>
          <section v-if="auth.user?.is_superadmin && !auth.user.workspace" class="inline-form">
            <h3>空间管理</h3>
            <p class="form-help">个人使用不需要创建空间；需要协作时可创建一个或多个空间。</p>
            <button class="button secondary" @click="tab = 'platform'">打开超级管理</button>
          </section>
          <section v-if="auth.user?.workspace" class="inline-form">
            <h3>部门成员资格</h3>
            <p class="form-help">
              离开部门只会取消团队权限，个人账号和资料会保留。最后一位管理员需要先移交权限。
            </p>
            <button class="text-button danger-text" :disabled="busy" @click="leaveWorkspace">
              离开当前部门
            </button>
          </section>
        </template>
        <template v-else-if="tab === 'exports'">
          <section class="inline-form">
            <h3>导出链接清单</h3>
            <p class="form-help">JSON / CSV 清单仅含链接。需要迁移个人分组、环境与账号，请选择“个人迁移”。</p>
            <div class="export-grid">
              <a class="button secondary" href="/api/v1/exports?scope=personal&format=json" download
                ><Icon name="download" />个人书签 JSON</a
              ><a class="button secondary" href="/api/v1/exports?scope=personal&format=csv" download
                ><Icon name="download" />个人书签 CSV</a
              ><a
                v-if="auth.user?.workspace"
                class="button secondary"
                :href="`/api/v1/exports?scope=team&format=json&workspace_id=${auth.user?.workspace?.id}`"
                download
                ><Icon name="download" />团队链接 JSON</a
              ><a
                v-if="auth.user?.workspace"
                class="button secondary"
                :href="`/api/v1/exports?scope=team&format=csv&workspace_id=${auth.user?.workspace?.id}`"
                download
                ><Icon name="download" />团队链接 CSV</a
              >
            </div>
          </section>
        </template>
        <template v-else-if="tab === 'security'">
          <form class="inline-form" @submit.prevent="recoveryCode">
            <h3>个人账户恢复码</h3>
            <p class="form-help">忘记密码时由你自己找回账号。生成新码后，旧恢复码立即失效。</p>
            <label class="form-group"
              >确认当前密码<input
                v-model="recoveryPassword"
                class="form-field"
                type="password"
                required
                autocomplete="current-password"
                maxlength="256" /></label
            ><button class="button secondary" :disabled="busy">
              {{ auth.user?.has_recovery_code ? '更新账户恢复码' : '生成账户恢复码' }}
            </button>
          </form>
          <form @submit.prevent="changePassword" class="inline-form">
            <h3>修改登录密码</h3>
            <label class="form-group"
              >当前密码<input
                class="form-field"
                type="password"
                v-model="oldPassword"
                required
                autocomplete="current-password" /></label
            ><label class="form-group"
              >新密码（至少 12 位）<input
                class="form-field"
                type="password"
                v-model="password"
                required
                minlength="12"
                maxlength="256"
                autocomplete="new-password"
            /></label>
            <p class="form-help">修改后所有设备需要重新登录，之前签发的密码重置链接也会失效。</p>
            <div class="row-actions">
              <button class="button secondary" :disabled="busy">更新登录密码</button
              ><button class="text-button danger-text" type="button" @click="logoutAll">退出所有设备</button>
            </div>
          </form>
        </template>
        <TransferPanel v-else-if="tab === 'transfer'" @changed="transferred" />
        <BookmarkImportPanel v-else-if="tab === 'bookmarks'" @changed="transferred" />
        <AdministrationPanel
          v-else-if="tab === 'platform' && auth.user?.is_superadmin"
          @workspace="selectSpace"
          @changed="emit('changed')"
        />
        <RoleHelp
          v-else-if="tab === 'roles'"
          :selected="auth.user?.role === 'personal' ? undefined : auth.user?.role"
        />
        <MembersPanel
          v-else-if="tab === 'members' && auth.user?.role === 'admin'"
          @changed="emit('changed')"
        />
        <FeedbackPanel
          v-else-if="tab === 'feedback' && auth.user?.workspace"
          :catalog="catalog"
          :resource="resource"
          :compose="compose"
          @changed="emit('changed')"
        />
        <template v-else-if="tab === 'trash'"
          ><h3>回收站</h3>
          <p class="form-help">
            可恢复最近 30 天内删除且你有维护权限的资源。恢复链接后，账号保持待核实状态。
          </p>
          <div class="management-list">
            <div v-for="item in trash" :key="item.id" class="management-row">
              <div>
                <strong>{{ item.name }}</strong
                ><small
                  >{{ item.scope === 'personal' ? '个人空间' : '团队空间' }} ·
                  {{ new Date(item.deleted_at!).toLocaleString() }}</small
                >
              </div>
              <button class="button secondary compact" :disabled="busy" @click="restore(item)">
                <Icon name="history" />恢复
              </button>
            </div>
            <p v-if="!loading && !error && !trash.length" class="inline-empty">回收站是空的。</p>
          </div></template
        >
        <template v-else-if="tab === 'audit'"
          ><div class="section-heading">
            <h3>操作记录</h3>
            <button class="text-button" @click="load"><Icon name="refresh" />刷新</button>
          </div>
          <p class="form-help">显示授权范围内最近 200 条记录，不记录明文账号密码。</p>
          <ol class="activity-list">
            <li v-for="item in events" :key="item.id">
              <span class="activity-dot"></span>
              <div>
                <strong>{{ item.actor_name }}</strong> {{ actionNames[item.action] || '更新配置'
                }}<span v-if="item.target_name"> · {{ item.target_name }}</span
                ><small
                  >{{ new Date(item.created_at).toLocaleString()
                  }}<template v-if="item.detail.field">
                    · {{ item.detail.field === 'password' ? '密码' : '用户名' }}</template
                  ></small
                >
              </div>
            </li>
          </ol>
          <p v-if="!loading && !error && !events.length" class="inline-empty">
            还没有相关操作记录。
          </p></template
        >
      </div>
    </div>
  </Sheet>
</template>
