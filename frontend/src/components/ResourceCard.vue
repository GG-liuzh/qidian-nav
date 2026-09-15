<script setup lang="ts" generic="T extends PublicResource">
import { computed } from 'vue'
import type { Endpoint, Environment, PublicResource } from '../types'
import { hostname } from '../api'
import Icon from './Icon.vue'
const props = defineProps<{
  resource: T
  environments?: Environment[]
  env?: string
  searchEnvs?: string[]
  guest?: boolean
}>()
const emit = defineEmits<{
  details: [resource: T, env?: string]
  edit: [resource: T]
  favorite: [resource: T]
  visit: [endpoint: Endpoint]
}>()
const environmentSlots = computed(() => {
  const endpoints = new Map(props.resource.endpoints.map((endpoint) => [endpoint.environment_id, endpoint]))
  const environments = (props.environments || []).filter((item) => item.scope === props.resource.scope)
  // A saved public resource may belong to someone else's catalog.
  const slots = environments.some((item) => endpoints.has(item.id))
    ? environments.map((item) => ({
        id: item.id,
        environment_id: item.id,
        label: item.label,
        endpoint: endpoints.get(item.id),
      }))
    : props.resource.endpoints.map((endpoint) => ({
        id: endpoint.id,
        environment_id: endpoint.environment_id,
        label: endpoint.env_label,
        endpoint,
      }))
  return slots.filter(
    (item) =>
      (!props.env || item.environment_id === props.env) &&
      (!props.searchEnvs?.length || props.searchEnvs.includes(item.environment_id || '')),
  )
})
</script>
<template>
  <article v-if="resource.type === 'system'" class="resource-card" :data-resource-id="resource.id">
    <div class="card-top">
      <span class="app-icon" :class="['green', 'blue', 'amber'][resource.name.length % 3]"
        ><Icon :name="resource.icon" :size="25"
      /></span>
      <div class="card-title-group">
        <button class="card-title" @click="emit('details', resource)">{{ resource.name }}</button>
        <div class="card-subtitle">
          {{ resource.category_name }}<span v-if="resource.aliases"> · {{ resource.aliases }}</span>
        </div>
      </div>
      <button
        class="icon-button favorite-button"
        :class="{ 'is-favorite': resource.favorite }"
        :aria-label="`${resource.favorite ? '取消收藏' : '收藏'}${resource.name}`"
        :aria-pressed="resource.favorite"
        @click="emit('favorite', resource)"
      >
        <Icon name="star" />
      </button>
    </div>
    <p class="card-description">{{ resource.description || '还没有添加描述。' }}</p>
    <div class="environment-links">
      <template v-for="item in environmentSlots" :key="item.id"
        ><a
          v-if="item.endpoint?.enabled"
          class="environment-link"
          :class="item.endpoint.env_kind"
          :href="item.endpoint.url"
          target="_blank"
          rel="noopener noreferrer"
          :aria-label="`打开${resource.name} · ${item.label}`"
          :title="item.endpoint.url"
          @click="emit('visit', item.endpoint)"
          ><i class="env-dot" :class="item.endpoint.env_kind" /><span class="environment-name">{{
            item.label
          }}</span
          ><span class="env-code">{{ item.endpoint.env_key.toUpperCase() }}</span
          ><Icon name="external" /></a
        ><span
          v-else
          class="environment-link disabled"
          :title="item.endpoint ? item.endpoint.disabled_reason : '尚未配置此环境的链接'"
          >{{ item.label }} · {{ item.endpoint ? '已停用' : '未配置链接' }}</span
        ></template
      >
    </div>
    <div class="card-footer">
      <button class="credential-button" @click="emit('details', resource, env)">
        <Icon :name="guest ? 'info' : 'key'" />{{ guest ? '查看说明' : '账号与说明' }}</button
      ><span class="owner"
        ><span class="owner-dot">{{ resource.maintainer_name.slice(0, 1) }}</span
        ><span>{{ resource.maintainer_name }}</span
        ><button
          v-if="resource.can_edit"
          class="icon-button"
          :aria-label="`编辑${resource.name}`"
          @click="emit('edit', resource)"
        >
          <Icon name="edit" /></button
      ></span>
    </div>
  </article>
  <article v-else class="bookmark-card" :data-resource-id="resource.id">
    <span class="app-icon blue"><Icon :name="resource.icon === 'globe' ? 'book' : resource.icon" /></span>
    <div class="bookmark-main">
      <a
        v-if="resource.endpoints[0]?.enabled"
        class="bookmark-link"
        :href="resource.endpoints[0].url"
        target="_blank"
        rel="noopener noreferrer"
        @click="emit('visit', resource.endpoints[0])"
        >{{ resource.name }}</a
      ><button v-else class="bookmark-link" @click="emit('details', resource)">{{ resource.name }}</button>
      <div class="bookmark-domain">
        {{ hostname(resource.endpoints[0]?.url || '') }} ·
        {{
          resource.is_public
            ? '已公开'
            : resource.scope === 'personal'
              ? '仅自己可见'
              : resource.category_name
        }}
      </div>
    </div>
    <button class="icon-button" :aria-label="`查看${resource.name}详情`" @click="emit('details', resource)">
      <Icon name="info" /></button
    ><button
      class="icon-button favorite-button"
      :class="{ 'is-favorite': resource.favorite }"
      :aria-label="`${resource.favorite ? '取消收藏' : '收藏'}${resource.name}`"
      @click="emit('favorite', resource)"
    >
      <Icon name="star" /></button
    ><button
      v-if="resource.can_edit"
      class="icon-button"
      :aria-label="`编辑${resource.name}`"
      @click="emit('edit', resource)"
    >
      <Icon name="edit" />
    </button>
  </article>
</template>
