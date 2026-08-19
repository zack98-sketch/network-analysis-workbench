<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { materialApi, projectApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { Material, Project } from '@/types'

const store = useProjectStore()
const filterActive = ref('全部')
const filters = ['全部', '日志', '配置', '手册']
const materials = ref<Material[]>([])
const projects = ref<Project[]>([])
const uploadProgress = ref<Record<string, number>>({})
const selectedProjectId = ref<string | number>('')
const fileInput = ref<HTMLInputElement | null>(null)
const dragActive = ref(false)
const loading = ref(false)
const pollingTimer = ref<any>(null)
const pendingMaterialIds = ref<Set<string | number>>(new Set())

const typeMap: Record<string, Material['type']> = {
  '日志': 'log',
  '配置': 'config',
  '手册': 'manual'
}

const filteredMaterials = computed(() => {
  if (filterActive.value === '全部') return materials.value
  const t = typeMap[filterActive.value]
  return materials.value.filter(m => m.type === t || (filterActive.value === '手册' && (m.type === 'manual' || m.type === 'training')))
})

function statusBadge(m: Material) {
  if (m.status === 'parsed') return { cls: 'badge-p2', text: '已解析' }
  if (m.status === 'indexed') return { cls: 'badge-p2', text: '已索引' }
  if (m.status === 'risk') return { cls: 'badge-p0', text: `${m.risksCount} 项风险` }
  if (m.status === 'failed') return { cls: 'badge-p0', text: '解析失败' }
  if (m.status === 'pending') return { cls: 'badge-p1', text: '解析中...' }
  return { cls: 'badge-p3', text: '待处理' }
}

async function loadMaterials() {
  loading.value = true
  try {
    materials.value = await materialApi.list(selectedProjectId.value)
    // 跟踪 PENDING/PARSING 状态的材料，启动轮询
    const pending = materials.value.filter(m => m.status === 'pending')
    if (pending.length > 0) {
      pendingMaterialIds.value = new Set(pending.map(m => m.id))
      startPolling()
    } else {
      pendingMaterialIds.value = new Set()
    }
  } finally {
    loading.value = false
  }
}

function startPolling() {
  if (pollingTimer.value) return
  pollingTimer.value = setInterval(async () => {
    if (pendingMaterialIds.value.size === 0) {
      stopPolling()
      return
    }
    const ids = Array.from(pendingMaterialIds.value)
    let stillPending = false
    let anyChanged = false
    for (const id of ids) {
      try {
        const updated = await materialApi.get(id)
        const idx = materials.value.findIndex(m => m.id === id)
        if (idx >= 0) {
          const prevStatus = materials.value[idx].status
          materials.value[idx] = updated
          if (updated.status !== prevStatus) {
            anyChanged = true
            if (updated.status === 'failed') {
              ElMessage.error(`文件 ${updated.name} 解析失败`)
            } else if (updated.status === 'parsed') {
              ElMessage.success(`文件 ${updated.name} 解析完成`)
            }
          }
        }
        if (updated.status === 'pending') {
          stillPending = true
        } else {
          pendingMaterialIds.value.delete(id)
        }
      } catch (e) {
        // 单条失败不影响其他
      }
    }
    if (!stillPending) {
      stopPolling()
      // 所有解析完成，重新加载一次以获取最新风险数和拓扑
      if (anyChanged) {
        await loadMaterials()
      }
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
})

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
    if (projects.value.length > 0) {
      const storeProj = store.currentProject
      if (storeProj.id && projects.value.some(p => p.id === storeProj.id)) {
        selectedProjectId.value = storeProj.id
      } else {
        selectedProjectId.value = projects.value[0].id
        store.setProject(projects.value[0])
      }
      await loadMaterials()
    }
  } catch {}
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  dragActive.value = true
}

function handleDragLeave() {
  dragActive.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  dragActive.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) {
    uploadFiles(Array.from(files))
  }
}

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileInputChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    uploadFiles(Array.from(target.files))
  }
}

async function uploadFiles(files: File[]) {
  for (const file of files) {
    const key = file.name + '-' + Date.now()
    uploadProgress.value[key] = 0
    const formData = new FormData()
    formData.append('project_id', String(selectedProjectId.value))
    formData.append('file', file)

    try {
      await materialApi.upload(formData, (progressEvent: any) => {
        if (progressEvent.total) {
          uploadProgress.value[key] = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        }
      })
      await loadMaterials()
    } catch (e: any) {
      ElMessage.error(`上传 ${file.name} 失败`)
    } finally {
      delete uploadProgress.value[key]
    }
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">文件上传</div>
        <h1 class="h1">上传分析材料</h1>
        <p class="text-muted">支持日志、配置文件、产品手册、培训教材批量上传，系统自动识别格式。</p>
      </div>
    </div>

    <div class="card" style="padding:calc(var(--spacing)*5)">
      <div style="display:flex;align-items:center;gap:calc(var(--spacing)*5);flex-wrap:wrap">
        <div style="display:flex;flex-direction:column;gap:4px">
          <span style="font-size:11px;font-weight:600;color:var(--muted-foreground);text-transform:uppercase;letter-spacing:0.08em">上传目标项目</span>
          <select class="project-select" v-model="selectedProjectId" @change="loadMaterials">
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}（{{ p.status === 'active' ? '当前' : p.status }}）</option>
          </select>
        </div>
        <div style="display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--bg-200);border-radius:var(--radius-md)">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--primary);color:var(--primary-foreground);display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:600">运</div>
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-size:12px;font-weight:600">运维工程师</span>
            <span style="font-size:11px;color:var(--muted-foreground)">上传后将按项目隔离存储</span>
          </div>
        </div>
        <div style="margin-left:auto;display:flex;gap:8px">
          <span class="badge badge-info">{{ materials.length }} 份材料</span>
          <span class="badge badge-p2">{{ materials.filter(m => m.status === 'parsed' || m.status === 'indexed').length }} 已解析</span>
        </div>
      </div>
    </div>

    <div
      class="upload-zone"
      :class="{ 'drag-active': dragActive }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="triggerFileInput"
      style="cursor:pointer"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".log,.csv,.cfg,.conf,.txt,.chm,.pdf,.html,.md"
        style="display:none"
        @change="handleFileInputChange"
      />
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
      <h3 class="h3">拖放文件到此处</h3>
      <p>或点击选择文件 · 支持 .log .csv .cfg .conf .txt .chm .pdf .html .md</p>
    </div>

    <div v-if="Object.keys(uploadProgress).length" class="card" style="margin-top:16px">
      <div class="card-header">
        <h3 class="card-title h4">上传进度</h3>
      </div>
      <div style="display:flex;flex-direction:column;gap:12px">
        <div v-for="(pct, key) in uploadProgress" :key="key">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px">
            <span style="font-size:13px">{{ key.split('-').slice(0, -1).join('-') }}</span>
            <span style="font-size:13px;color:var(--text-500)">{{ pct }}%</span>
          </div>
          <div class="progress-track" style="height:6px;border-radius:3px">
            <div class="progress-fill" :style="{ width: pct + '%', background: 'var(--primary)' }"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">已上传材料</h3>
          <p class="card-desc">当前项目共 {{ materials.length }} 份文件，已解析 {{ materials.filter(m => m.status === 'parsed' || m.status === 'indexed').length }} 份</p>
        </div>
        <div class="filter-bar">
          <button v-for="f in filters" :key="f" class="filter-chip" :class="{ active: filterActive === f }" @click="filterActive = f">{{ f }}</button>
        </div>
      </div>
      <div class="file-list">
        <div class="file-row" v-for="m in filteredMaterials" :key="m.id">
          <div class="file-info">
            <div class="file-icon">{{ m.format }}</div>
            <div style="min-width:0">
              <p class="file-name">{{ m.name }}</p>
              <p class="file-meta">
                <span v-if="m.rows">{{ m.rows.toLocaleString() }} 行 · </span>
                {{ m.size }} · {{ m.uploadedAt }}
              </p>
            </div>
          </div>
          <div class="file-status">
            <span class="badge" :class="statusBadge(m).cls">{{ statusBadge(m).text }}</span>
            <button
              class="btn btn-ghost btn-sm"
              @click.stop="async () => { await materialApi.remove(m.id); await loadMaterials() }"
            >删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-zone.drag-active {
  border-color: var(--primary);
  background: var(--primary-50);
}
</style>
