<script setup lang="ts">
import type { Role } from '../types'
defineProps<{ selected?: Role }>()
const rows = [
  {key:'member',name:'普通成员',description:'查看本空间全部链接、用户名和密码；收藏、访问并提交建议。'},
  {key:'maintainer',name:'业务维护人',description:'拥有成员权限，并可新增、编辑、删除全部空间链接和业务账号。'},
  {key:'admin',name:'空间管理员',description:'拥有维护人权限，并管理目录、环境、成员、公开范围和空间设置。'},
]
</script>
<template>
  <div class="role-help"><div v-for="row in rows" :key="row.key" class="role-help-row" :class="{selected:selected===row.key}"><strong>{{ row.name }}</strong><p>{{ row.description }}</p></div><p class="form-help">权限只在对应空间内生效。个人导航由本人管理；公开导航不显示业务账号密码。</p></div>
</template>
