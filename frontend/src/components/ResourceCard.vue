<script setup lang="ts" generic="T extends PublicResource">
import type { Endpoint, PublicResource } from '../types'
import { hostname } from '../api'
import Icon from './Icon.vue'
const props = defineProps<{ resource: T; env?: string; searchEnvs?: string[]; guest?: boolean }>()
const emit = defineEmits<{
  details: [resource: T, env?: string]
  edit: [resource: T]
  favorite: [resource: T]
  visit: [endpoint: Endpoint]
}>()
function visible(endpoint: Endpoint) {
  return (
    (!props.env || endpoint.environment_id === props.env) &&
    (!props.searchEnvs?.length || props.searchEnvs.includes(endpoint.environment_id || ''))
  )
}
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
      <template v-for="endpoint in resource.endpoints.filter(visible)" :key="endpoint.id"
        ><a
          v-if="endpoint.enabled"
          class="environment-link"
          :class="endpoint.env_kind"
          :href="endpoint.url"
          target="_blank"
          rel="noopener noreferrer"
          :aria-label="`打开${resource.name} · ${endpoint.env_label}`"
          :title="endpoint.url"
          @click="emit('visit', endpoint)"
          ><i class="env-dot" :class="endpoint.env_kind" /><span class="environment-name">{{
            endpoint.env_label
          }}</span
          ><span class="env-code">{{ endpoint.env_key.toUpperCase() }}</span
          ><Icon name="external" /></a
        ><span v-else class="environment-link disabled" :title="endpoint.disabled_reason"
          >{{ endpoint.env_label }} · 已停用</span
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
