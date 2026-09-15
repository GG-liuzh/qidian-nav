<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { AlertDialogRoot, AlertDialogPortal, AlertDialogOverlay, AlertDialogContent, AlertDialogTitle, AlertDialogDescription } from 'reka-ui'
import { confirmation, finishConfirmation } from '../confirm'
import Icon from './Icon.vue'
const cancel = () => finishConfirmation(false)
onMounted(() => window.addEventListener('clear-secrets', cancel))
onUnmounted(() => { window.removeEventListener('clear-secrets', cancel); cancel() })
</script>
<template>
  <AlertDialogRoot :open="!!confirmation" @update:open="value => { if (!value) cancel() }">
    <AlertDialogPortal>
      <AlertDialogOverlay class="confirmation-overlay" />
      <AlertDialogContent v-if="confirmation" class="confirmation-dialog" @escape-key-down="cancel">
        <span class="confirmation-icon" :class="{danger: confirmation.danger}"><Icon :name="confirmation.danger ? 'trash' : 'info'" :size="24" /></span>
        <AlertDialogTitle class="confirmation-title">{{ confirmation.title }}</AlertDialogTitle>
        <AlertDialogDescription class="confirmation-description">{{ confirmation.message }}</AlertDialogDescription>
        <div class="confirmation-actions"><button class="button secondary" autofocus @click="cancel">取消</button><button class="button" :class="confirmation.danger ? 'danger' : 'primary'" @click="finishConfirmation(true)">{{ confirmation.confirmText }}</button></div>
      </AlertDialogContent>
    </AlertDialogPortal>
  </AlertDialogRoot>
</template>
