<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useAuth } from '../auth'
import { api, errorMessage, notify } from '../api'
import { confirmAction } from '../confirm'
import type { Page, Role, User, Workspace } from '../types'
import { roleNames } from '../types'
import Icon from './Icon.vue'

interface SiteUser {id:string;username:string;display_name:string;active:boolean;is_superadmin:boolean;version:number;workspaces:{id:string;name:string;role:Role}[]}
type SiteWorkspace = Workspace & {member_count:number;is_home:boolean}
const emit=defineEmits<{workspace:[id:string];changed:[]}>()
const auth=useAuth(),tab=ref('spaces'),spaces=ref<SiteWorkspace[]>([]),users=ref<SiteUser[]>([]),events=ref<{id:string;actor_name:string;action:string;created_at:string;target_id:string}[]>([])
const search=ref(''),next=ref<number|null>(null),busy=ref(false),error=ref(''),newName=ref(''),newPublic=ref(false),resetLink=ref(''),resetFor=ref(''),linkInput=ref<HTMLInputElement|null>(null)
const actionNames:Record<string,string>={'site.user_updated':'更新用户状态或站点角色','site.reset_issued':'生成账号重置链接','site.workspace_updated':'更新空间状态','site.home_updated':'修改默认首页空间'}
async function load(offset=0) {error.value='';try {
  if(tab.value==='spaces')spaces.value=await api('/admin/workspaces')
  if(tab.value==='users'){const result=await api<Page<SiteUser>>(`/admin/users?q=${encodeURIComponent(search.value)}&offset=${offset}`);users.value=offset?[...users.value,...result.items]:result.items;next.value=result.next_offset}
  if(tab.value==='events')events.value=await api('/admin/events')
}catch(e){error.value=errorMessage(e)}}
async function createSpace(){busy.value=true;error.value='';try{const user=await api<User>('/workspace','POST',{name:newName.value,public_enabled:newPublic.value});auth.accept(user);newName.value='';emit('changed');emit('workspace',user.workspace!.id);notify('空间已创建。')}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
async function state(space:SiteWorkspace){if(!await confirmAction(space.active?`停用“${space.name}”后，成员和游客都无法访问其中内容；数据会保留。`:`重新启用“${space.name}”？`,{title:space.active?'停用空间':'启用空间',confirmText:space.active?'停用':'启用',danger:space.active}))return;busy.value=true;try{await api(`/admin/workspaces/${space.id}`,'PATCH',{active:!space.active,version:space.version});await load();await auth.refresh();emit('changed')}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
async function home(space:SiteWorkspace){try{await api(`/admin/home/${space.id}`,'PUT');await load();notify('默认首页空间已更新。')}catch(e){error.value=errorMessage(e)}}
async function saveUser(user:SiteUser){if(!await confirmAction(`更新“${user.display_name}”的账号状态与站点角色？该用户的已有登录将退出。`,{title:'更新用户',confirmText:'保存',danger:!user.active}))return;busy.value=true;try{await api(`/admin/users/${user.id}`,'PATCH',{active:user.active,is_superadmin:user.is_superadmin,version:user.version});await load();notify('用户已更新。')}catch(e){error.value=errorMessage(e);await load()}finally{busy.value=false}}
async function reset(user:SiteUser){if(!await confirmAction(`为“${user.display_name}”生成有效期 1 小时、只能使用一次的重置链接？请把链接交给账号本人。`,{title:'帮助用户找回账号',confirmText:'生成重置链接'}))return;busy.value=true;try{const result=await api<{token:string}>(`/admin/users/${user.id}/recovery`,'POST');resetLink.value=`${location.origin}/#/account-reset?token=${encodeURIComponent(result.token)}`;resetFor.value=user.username;notify('重置链接已生成，旧链接已失效。')}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
async function copy(){try{await navigator.clipboard.writeText(resetLink.value);notify('重置链接已复制。')}catch{linkInput.value?.focus();linkInput.value?.select();notify('请手动复制已选中的链接。')}}
watch(tab,()=>void load())
onMounted(()=>void load())
</script>
<template>
  <p class="drawer-intro">超级管理员负责站点用户与全部空间。空间管理员只管理自己所在的空间。这里不提供他人个人导航的查看入口。</p>
  <div class="panel-tabs"><button :class="{selected:tab==='spaces'}" @click="tab='spaces'">全部空间</button><button :class="{selected:tab==='users'}" @click="tab='users'">站点用户</button><button :class="{selected:tab==='events'}" @click="tab='events'">管理记录</button></div>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div>
  <template v-if="tab==='spaces'"><div class="management-list"><div v-for="space in spaces" :key="space.id" class="member-card"><div class="section-heading"><strong>{{ space.name }}</strong><span class="status-badge">{{ space.active?'已启用':'已停用' }}</span></div><p class="form-help">{{ space.member_count }} 位成员 · {{ space.public_enabled?'可发布公开链接':'空间内使用' }}{{ space.is_home?' · 默认首页':'' }}</p><div class="row-actions"><button class="button secondary compact" :disabled="!space.active||busy" @click="emit('workspace',space.id)">进入空间管理</button><button class="text-button" :disabled="!space.active||space.is_home||busy" @click="home(space)">设为默认首页</button><button class="text-button" :class="{'danger-text':space.active}" :disabled="busy" @click="state(space)">{{ space.active?'停用空间':'启用空间' }}</button></div></div></div><form class="inline-form" @submit.prevent="createSpace"><h3>创建新空间</h3><label class="form-group">新空间名称<input v-model="newName" class="form-field" required maxlength="80" /></label><label class="checkbox-label"><input v-model="newPublic" type="checkbox" />允许发布公开导航链接</label><p class="form-help">只需要一个空间时创建一个即可；不同空间的目录、链接、成员和角色彼此独立。</p><button class="button primary" :disabled="busy"><Icon name="plus" />创建空间</button></form></template>
  <template v-else-if="tab==='users'"><form class="search-box compact-search" @submit.prevent="load()"><Icon name="search" /><input v-model="search" aria-label="搜索站点用户" placeholder="搜索用户名或姓名" /><button class="text-button">搜索</button></form><div v-if="resetLink" class="notice-panel"><label class="form-group">{{ resetFor }} 的账号重置链接<input ref="linkInput" class="form-field" aria-label="账号重置链接" readonly :value="resetLink" /></label><p class="form-help">使用后旧登录失效，用户自行设置新密码并保存新恢复码。</p><button class="button secondary" @click="copy"><Icon name="copy" />复制重置链接</button></div><div v-for="user in users" :key="user.id" class="member-card"><div class="member-heading"><span class="avatar">{{ user.display_name.slice(0,1) }}</span><div><strong>{{ user.display_name }}</strong><small>{{ user.username }}</small></div><button class="text-button" :disabled="!user.active||busy" @click="reset(user)">帮助重置密码</button></div><p class="form-help">{{ user.workspaces.map(space=>`${space.name}（${roleNames[space.role]}）`).join('、')||'独立个人账号，尚未加入空间' }}</p><div class="member-controls"><label class="checkbox-label"><input v-model="user.active" type="checkbox" :disabled="user.id===auth.user?.id" />账号启用</label><label class="checkbox-label"><input v-model="user.is_superadmin" type="checkbox" :disabled="user.id===auth.user?.id" />超级管理员</label><button class="button secondary compact" :disabled="busy||user.id===auth.user?.id" @click="saveUser(user)">保存用户设置</button></div></div><button v-if="next!==null" class="button secondary" @click="load(next!)">加载更多用户</button></template>
  <ol v-else class="activity-list"><li v-for="event in events" :key="event.id"><span class="activity-dot" /><div><strong>{{ event.actor_name }}</strong> {{ actionNames[event.action]||event.action }}<small>{{ new Date(event.created_at).toLocaleString() }}</small></div></li><li v-if="!events.length" class="inline-empty">暂无站点管理记录。</li></ol>
</template>
