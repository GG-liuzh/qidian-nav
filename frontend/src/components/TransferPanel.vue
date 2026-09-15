<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { api, errorMessage, notify } from '../api'
import Icon from './Icon.vue'

interface Preview {
  resources: number
  categories: number
  credentials: number
  duplicates: { id: string; name: string; existing_name: string }[]
  already_imported: boolean
}
const emit = defineEmits<{ changed: [] }>()
const includeCredentials = ref(false),
  protectFile = ref(false),
  exportPass = ref('')
const packageData = ref<Record<string, unknown> | null>(null),
  fileName = ref(''),
  importPass = ref('')
const preview = ref<Preview | null>(null),
  duplicates = ref<'skip' | 'copy'>('skip')
const busy = ref(false),
  error = ref(''),
  result = ref(''),
  fileInput = ref<HTMLInputElement | null>(null)
watch(includeCredentials, (value) => {
  if (value) protectFile.value = true
})
watch(importPass, () => {
  preview.value = null
})
async function exportData() {
  busy.value = true
  error.value = ''
  result.value = ''
  try {
    const data = await api<Record<string, unknown>>('/me/transfer/export', 'POST', {
      include_credentials: includeCredentials.value,
      passphrase: protectFile.value ? exportPass.value : null,
    })
    const url = URL.createObjectURL(new Blob([JSON.stringify(data)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `qidian-personal-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    exportPass.value = ''
    result.value = '个人迁移文件已下载。在自己的栖点服务登录后，到这里导入即可。'
    notify('个人迁移文件已下载。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function selectFile(event: Event) {
  packageData.value = null
  preview.value = null
  importPass.value = ''
  error.value = ''
  result.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  fileName.value = file?.name || ''
  if (!file) return
  if (file.size > 10 * 1024 * 1024) {
    error.value = '迁移文件最大为 10 MB。'
    return
  }
  try {
    const data: unknown = JSON.parse(await file.text())
    if (!data || typeof data !== 'object' || Array.isArray(data))
      throw new Error('请选择栖点导出的个人迁移 JSON 文件。')
    packageData.value = data as Record<string, unknown>
  } catch (e) {
    error.value = e instanceof SyntaxError ? '文件不是有效的 JSON 迁移文件。' : errorMessage(e)
  }
}
function payload() {
  return { package: packageData.value, passphrase: importPass.value || null, duplicates: duplicates.value }
}
async function inspect() {
  if (!packageData.value) return
  busy.value = true
  error.value = ''
  result.value = ''
  try {
    preview.value = await api<Preview>('/me/transfer/preview', 'POST', payload())
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
async function importData() {
  if (!preview.value || !packageData.value) return
  busy.value = true
  error.value = ''
  try {
    const data = await api<{
      imported: number
      skipped: number
      credentials: number
      already_imported: boolean
    }>('/me/transfer/import', 'POST', payload())
    result.value = data.already_imported
      ? '这个迁移文件已导入过，未重复添加。'
      : `已导入 ${data.imported} 个链接、${data.credentials} 个私人账号，跳过 ${data.skipped} 个重复链接。导入内容默认仅自己可见。`
    packageData.value = null
    preview.value = null
    importPass.value = ''
    fileName.value = ''
    if (fileInput.value) fileInput.value.value = ''
    emit('changed')
    notify('个人资料迁移完成。')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
onUnmounted(() => {
  exportPass.value = ''
  importPass.value = ''
  packageData.value = null
})
</script>

<template>
  <p class="drawer-intro">
    个人导航可以带到自己的电脑或服务器。分组、环境、链接、个人资源的收藏与快捷入口会一起迁移，部门内容留在部门。
  </p>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div>
  <p v-if="result" class="notice-panel" role="status">{{ result }}</p>
  <form class="inline-form" @submit.prevent="exportData">
    <h3>下载我的个人资料</h3>
    <label class="checkbox-label"
      ><input v-model="includeCredentials" type="checkbox" />包含个人资源的账号密码</label
    >
    <label class="checkbox-label"
      ><input v-model="protectFile" type="checkbox" :disabled="includeCredentials" />用迁移口令加密文件</label
    >
    <label v-if="protectFile" class="form-group"
      >迁移口令（至少 12 位）<input
        v-model="exportPass"
        type="password"
        class="form-field"
        required
        minlength="12"
        maxlength="256"
        autocomplete="new-password"
    /></label>
    <p class="form-help">
      包含私人账号时必须加密。请记住迁移口令，导入时需要使用；登录密码和恢复码不会放进迁移文件。
    </p>
    <button class="button primary" :disabled="busy">
      <Icon name="download" />{{ busy ? '正在处理…' : '下载个人迁移文件' }}
    </button>
  </form>
  <form class="inline-form" @submit.prevent="inspect">
    <h3>导入到当前个人账号</h3>
    <label class="form-group"
      >选择个人迁移文件<input
        ref="fileInput"
        class="form-field"
        type="file"
        accept=".json,application/json"
        :disabled="busy"
        @change="selectFile"
    /></label>
    <p v-if="fileName" class="form-help break-word">{{ fileName }}</p>
    <label v-if="packageData?.format === 'qidian-personal-encrypted-v1'" class="form-group"
      >文件的迁移口令<input
        v-model="importPass"
        class="form-field"
        type="password"
        required
        maxlength="256"
        autocomplete="off"
    /></label>
    <button class="button secondary" :disabled="busy || !packageData">
      <Icon name="search" />预览迁移内容
    </button>
    <div v-if="preview" class="notice-panel transfer-preview">
      <p>
        {{ preview.resources }} 个链接 · {{ preview.categories }} 个分组 ·
        {{ preview.credentials }} 个私人账号
      </p>
      <p v-if="preview.already_imported">这个文件已导入过，再次导入不会重复添加。</p>
      <template v-else>
        <label v-if="preview.duplicates.length" class="form-group"
          >发现 {{ preview.duplicates.length }} 个网址重复的链接<select
            v-model="duplicates"
            class="form-field"
          >
            <option value="skip">保留现有链接，跳过重复项</option>
            <option value="copy">保留两份，作为新链接导入</option>
          </select></label
        >
        <p class="form-help">导入内容归当前个人账号所有，默认保持私有。现有资料会保留。</p>
      </template>
      <button
        class="button primary"
        type="button"
        :disabled="busy || preview.already_imported"
        @click="importData"
      >
        确认导入到我的导航
      </button>
    </div>
  </form>
</template>
