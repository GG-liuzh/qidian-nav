<script setup lang="ts">
import { ref, watch } from 'vue'
import { api, errorMessage, notify } from '../api'
import { confirmAction } from '../confirm'
import Icon from './Icon.vue'
interface Preview {resources:number;categories:number;read:number;skipped_invalid:number;duplicates_in_file:number;flattened_deep_folders:number;already_imported:boolean;duplicates:{id:string}[];examples:{name:string;url:string;path:string}[]}
const emit=defineEmits<{changed:[]}>()
const html=ref(''),fileName=ref(''),folders=ref('preserve'),duplicates=ref('skip'),preview=ref<Preview|null>(null),busy=ref(false),error=ref(''),result=ref(''),fileInput=ref<HTMLInputElement|null>(null)
watch([folders,duplicates],()=>{preview.value=null;result.value=''})
async function selectFile(event:Event){html.value='';preview.value=null;error.value='';result.value='';const file=(event.target as HTMLInputElement).files?.[0];fileName.value=file?.name||'';if(!file)return;if(file.size>5*1024*1024){error.value='单个书签文件最大 5 MB。';return}html.value=await file.text()}
function payload(){return {html:html.value,folders:folders.value,duplicates:duplicates.value}}
async function inspect(){busy.value=true;error.value='';try{preview.value=await api('/me/bookmarks/preview','POST',payload())}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
async function importData(){if(!preview.value||!await confirmAction(`把 ${preview.value.resources} 条书签导入个人导航？导入内容默认私有，现有资料会保留。`,{title:'导入浏览器书签',confirmText:'确认导入'}))return;busy.value=true;error.value='';try{const data=await api<{imported:number;skipped:number;already_imported:boolean}>('/me/bookmarks/import','POST',payload());result.value=data.already_imported?'这个文件已按相同方式导入过，没有重复添加。':`已导入 ${data.imported} 条书签，跳过 ${data.skipped} 条已有链接。`;html.value='';preview.value=null;fileName.value='';if(fileInput.value)fileInput.value.value='';emit('changed');notify('浏览器书签已导入个人导航。')}catch(e){error.value=errorMessage(e)}finally{busy.value=false}}
</script>
<template>
  <p class="drawer-intro">在 Chrome 书签管理器中选择“导出书签”，把得到的 HTML 文件导入这里。文件中的网页不会被自动打开。</p>
  <div v-if="error" class="form-error" role="alert">{{ error }}</div><p v-if="result" class="notice-panel" role="status">{{ result }}</p>
  <form class="inline-form" @submit.prevent="inspect"><label class="form-group">Chrome 书签 HTML 文件<input ref="fileInput" type="file" class="form-field" accept=".html,.htm,text/html" :disabled="busy" @change="selectFile" /></label><p v-if="fileName" class="form-help">{{ fileName }}</p><div class="form-row"><label class="form-group">文件夹处理<select v-model="folders" class="form-field"><option value="preserve">保留原文件夹层级</option><option value="flat">全部导入未分组</option></select></label><label class="form-group">重复网址<select v-model="duplicates" class="form-field"><option value="skip">跳过重复网址</option><option value="copy">保留两份</option></select></label></div><button class="button secondary" :disabled="busy||!html"><Icon name="search" />预览书签导入</button></form>
  <section v-if="preview" class="notice-panel bookmark-preview"><h3>读取到 {{ preview.read }} 条书签</h3><p>可导入 {{ preview.resources }} 条 · {{ preview.categories }} 个文件夹</p><p class="form-help">文件内重复 {{ preview.duplicates_in_file }} 条，与个人导航重复 {{ preview.duplicates.length }} 条，不支持的地址 {{ preview.skipped_invalid }} 条。</p><p v-if="preview.flattened_deep_folders" class="form-help">超过 8 层的文件夹会合并到第 8 层，原始路径保留在书签说明中。</p><p v-if="preview.already_imported">这个文件已按相同方式导入过。</p><ul class="bookmark-preview-list"><li v-for="(item,index) in preview.examples" :key="index"><strong>{{ item.name }}</strong><small>{{ item.path||'未分组' }}</small><span class="break-word">{{ item.url }}</span></li></ul><p class="form-help">上方最多预览 12 条。导入后归当前个人账号所有，默认不会公开。</p><button class="button primary" :disabled="busy||preview.already_imported" @click="importData">导入到个人导航</button></section>
</template>
