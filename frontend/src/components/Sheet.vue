<script setup lang="ts">
import {
  DialogRoot,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from 'reka-ui'
import Icon from './Icon.vue'
defineProps<{ open: boolean; title: string; description?: string; wide?: boolean; layout?: 'settings' }>()
const emit = defineEmits<{ close: [] }>()
</script>
<template>
  <DialogRoot
    :open="open"
    @update:open="
      (value) => {
        if (!value) emit('close')
      }
    "
  >
    <DialogPortal
      ><DialogOverlay class="sheet-overlay" /><DialogContent
        class="sheet"
        :class="{ wide, 'settings-sheet': layout === 'settings' }"
      >
        <header class="sheet-header">
          <div>
            <DialogDescription class="drawer-eyebrow">{{
              description || '栖点 · 工作空间'
            }}</DialogDescription
            ><DialogTitle class="sheet-title">{{ title }}</DialogTitle>
          </div>
          <button class="icon-button" aria-label="关闭面板" @click="emit('close')"><Icon name="x" /></button>
        </header>
        <div class="sheet-body"><slot /></div> </DialogContent
    ></DialogPortal>
  </DialogRoot>
</template>
