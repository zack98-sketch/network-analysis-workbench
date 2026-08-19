<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { materialApi, projectApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { Material, Project } from '@/types'

function formatSize(s: any): string {
  const n = Number(s) || 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(2)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

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

const analysisBusy = ref(false)
const analysisProgress = ref<any>(null)
const progressPollTimer = ref<any>(null)

// Inline create-project dialog (used by the "+ 新建项目" next to dropdown)
const newProjectDialogVisible = ref(false)
const newProjectForm = ref({ name: '', description: '' })

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
  const s = String(m.status || '').toLowerCase()
  if (s === 'success' || s === 'parsed' || s === 'indexed') return { cls: 'badge-p2', text: '已解析' }
  if (s === 'risk') return { cls: 'badge-p0', text: `${m.risksCount} 项风险` }
  if (s === 'failed') return { cls: 'badge-p0', text: '解析失败' }
  if (s === 'parsing') return { cls: 'badge-p1', text: '解析中' }
  if (s === 'pending') return { cls: 'badge-p1', text: '等待解析' }
  return { cls: 'badge-p3', text: '待处理' }
}

async function loadMaterials() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    materials.value = await materialApi.list(selectedProjectId.value)
    const pending = materials.value.filter(m => {
      const s = String(m.status || '').toLowerCase()
      return s === 'pending' || s === 'parsing'
    })
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
          const prevStatus = String(materials.value[idx].status || '').toLowerCase()
          materials.value[idx] = updated
          const s = String(updated.status || '').toLowerCase()
          if (s !== prevStatus) {
            anyChanged = true
            if (s === 'failed') ElMessage.error(`文件 ${updated.name} 解析失败`)
            else if (s === 'success' || s === 'parsed') ElMessage.success(`文件 ${updated.name} 解析完成`)
          }
        }
        const s = String(updated.status || '').toLowerCase()
        if (s === 'pending' || s === 'parsing') stillPending = true
        else pendingMaterialIds.value.delete(id)
      } catch {}
    }
    if (!stillPending) {
      stopPolling()
      if (anyChanged) await loadMaterials()
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

function startProgressPolling() {
  stopProgressPolling()
  progressPollTimer.value = setInterval(async () => {
    if (!selectedProjectId.value) return
    try {
      analysisProgress.value = await materialApi.progress(selectedProjectId.value)
      // Also refresh material list if parse states advanced
      if (analysisProgress.value) {
        const running = analysisProgress.value.running ?? 0
        if (running === 0) {
          stopProgressPolling()
          await loadMaterials()
        }
      }
    } catch {}
  }, 1500)
}

function stopProgressPolling() {
  if (progressPollTimer.value) {
    clearInterval(progressPollTimer.value)
    progressPollTimer.value = null
  }
}

onBeforeUnmount(() => {
  stopPolling()
  stopProgressPolling()
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

function handleDragOver(e: DragEvent) { e.preventDefault(); dragActive.value = true }
function handleDragLeave() { dragActive.value = false }
function handleDrop(e: DragEvent) {
  e.preventDefault(); dragActive.value = false
  const files = e.dataTransfer?.files
  if (files && files.length > 0) uploadFiles(Array.from(files))
}
function triggerFileInput() { fileInput.value?.click() }
function handleFileInputChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files.length > 0) uploadFiles(Array.from(target.files))
}

async function uploadFiles(files: File[]) {
  if (!selectedProjectId.value) {
    ElMessage.warning('请先选择或创建上传目标项目')
    return
  }
  for (const file of files) {
    const key = file.name + '-' + Date.now()
    uploadProgress.value[key] = 0
    const formData = new FormData()
    formData.append('project_id', String(selectedProjectId.value))
    formData.append('file', file)
    try {
      const created = await materialApi.upload(formData, (progressEvent: any) => {
        if (progressEvent.total) {
          uploadProgress.value[key] = Math.round((progressEvent.loaded * 100) / progressEvent.total)
        }
      })
      pendingMaterialIds.value.add(created.id)
      startPolling()
      await loadMaterials()
    } catch (e: any) {
      ElMessage.error(`上传 ${file.name} 失败`)
    } finally {
      setTimeout(() => { delete uploadProgress.value[key] }, 800)
    }
  }
}

// ---- Inline project creation ----
function openNewProjectDialog() {
  newProjectForm.value = { name: '', description: '' }
  newProjectDialogVisible.value = true
}
async function confirmCreateProject() {
  if (!newProjectForm.value.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  try {
    const p = await projectApi.create({
      name: newProjectForm.value.name,
      description: newProjectForm.value.description,
      status: 'active',
    })
    projects.value.unshift(p)
    selectedProjectId.value = p.id
    store.setProject(p)
    newProjectDialogVisible.value = false
    ElMessage.success(`已创建项目：${p.name}，已自动切换`)
    await loadMaterials()
  } catch {}
}

// ---- Analysis ----
async function analyzeCurrentProject() {
  if (!selectedProjectId.value) {
    ElMessage.warning('请选择目标项目')
    return
  }
  if (materials.value.length === 0) {
    ElMessage.warning('当前项目暂无可分析的材料，请先上传文件')
    return
  }
  try {
    analysisBusy.value = true
    analysisProgress.value = null
    const res: any = await materialApi.analyzeAll(selectedProjectId.value)
    ElMessage.success((res && (res.message || res.detail)) || '分析已启动')
    // 重置材料列表 pending 状态
    materials.value = materials.value.map(m => ({
      ...m,
      status: 'pending',
    }))
    pendingMaterialIds.value = new Set(materials.value.map(m => m.id))
    startPolling()
    startProgressPolling()
  } finally {
    analysisBusy.value = false
  }
}

async function deleteMaterial(m: Material) {
  try {
    await ElMessageBox.confirm(`确认删除材料「${m.name}」及其解析结果、配置项与日志事件？`,
      '删除材料', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await materialApi.remove(m.id)
    ElMessage.success('已删除')
    await loadMaterials()
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  }
}

async function reparseMaterial(m: Material) {
  try {
    const updated = await materialApi.reparse(m.id)
    const idx = materials.value.findIndex(x => x.id === m.id)
    if (idx >= 0) materials.value[idx] = updated
    pendingMaterialIds.value.add(m.id)
    startPolling()
    ElMessage.info('已重新加入解析队列')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  }
}

onMounted(() => { loadProjects() })

watch(selectedProjectId, () => {
  stopProgressPolling()
  analysisProgress.value = null
  if (selectedProjectId.value) loadMaterials()
})
</script>

<template>
  <div class="upload-page page">
    <header class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">文件上传与分析</div>
        <h1 class="h1">上传分析材料</h1>
        <p class="text-muted">支持日志 (.log/.csv)、配置文件 (.cfg/.conf)、操作手册 (.pdf/.md/.html/.chm) 批量上传，上传后按项目隔离存储，点击「开始分析」自动解析并出具配置/流量审核。</p>
      </div>
    </header>

    <!-- Top bar: project selector + stats + actions -->
    <section class="card top-bar">
      <div class="top-bar-grid">
        <!-- 上传目标项目 -->
        <div class="field">
          <span class="field-label">上传目标项目</span>
          <div class="project-select-wrap">
            <select v-model="selectedProjectId" @change="loadMaterials" class="project-select">
              <option v-for="p in projects" :key="p.id" :value="p.id">
                {{ p.name }} · {{ p.status === 'active' ? '进行中' : p.status }}
              </option>
              <option v-if="!projects.length" value="" disabled>暂无可选项目</option>
            </select>
            <button class="btn btn-secondary btn-sm" @click="openNewProjectDialog">+ 新建项目</button>
          </div>
          <p class="hint">上传后将严格按当前项目隔离存储与解析</p>
        </div>

        <!-- Current user / scope -->
        <div class="scope-card">
          <div class="scope-icon">运</div>
          <div class="scope-meta">
            <span class="scope-title">运维审计工作台</span>
            <span class="scope-sub">配置 / 日志 / 流量 三类材料合并审核</span>
          </div>
        </div>

        <!-- Stats chips -->
        <div class="stat-chips">
          <span class="stat-chip"><b>{{ materials.length }}</b><small>份材料</small></span>
          <span class="stat-chip stat-chip-ok">
            <b>{{ materials.filter(m => ['success','parsed','indexed'].includes(String(m.status || '').toLowerCase())).length }}</b>
            <small>已解析</small>
          </span>
          <span class="stat-chip stat-chip-wait">
            <b>{{ materials.filter(m => ['pending','parsing'].includes(String(m.status || '').toLowerCase())).length }}</b>
            <small>解析中</small>
          </span>
          <span class="stat-chip stat-chip-danger">
            <b>{{ materials.filter(m => String(m.status || '').toLowerCase() === 'failed').length }}</b>
            <small>失败</small>
          </span>
        </div>

        <!-- Actions -->
        <div class="top-actions">
          <button class="btn btn-secondary btn-sm" :disabled="!selectedProjectId || loading" @click="loadMaterials">
            刷新材料
          </button>
          <button
            class="btn btn-primary btn-sm"
            :disabled="analysisBusy || !selectedProjectId || materials.length === 0"
            @click="analyzeCurrentProject"
          >
            <span v-if="analysisBusy">已启动…</span>
            <span v-else>🚀 开始分析</span>
          </button>
        </div>
      </div>

      <!-- Analysis progress (aggregated) -->
      <div v-if="analysisProgress || analysisBusy" class="analysis-progress">
        <div class="analysis-progress-head">
          <b>分析进度</b>
          <span class="muted">{{ analysisProgress?.message || '准备中…' }}</span>
          <span class="percent">{{ analysisProgress?.percent ?? 0 }}%</span>
        </div>
        <div class="progress-track-lg">
          <div class="progress-fill-lg" :style="{ width: (analysisProgress?.percent ?? 0) + '%' }"></div>
        </div>
        <div class="analysis-progress-stats">
          <span>总材料 {{ analysisProgress?.total ?? 0 }}</span>
          <span>已完成 {{ analysisProgress?.completed ?? 0 }}</span>
          <span>解析中 {{ analysisProgress?.running ?? 0 }}</span>
          <span class="danger">失败 {{ analysisProgress?.failed ?? 0 }}</span>
        </div>
        <div v-if="analysisProgress?.materials?.length" class="per-file">
          <div class="pf-row" v-for="mf in analysisProgress.materials" :key="mf.id">
            <span class="pf-name" :title="mf.file_name">{{ mf.file_name }}</span>
            <span class="pf-badge" :class="
              mf.status === 'success' ? 'badge-p2' :
              mf.status === 'failed' ? 'badge-p0' :
              mf.status === 'parsing' ? 'badge-p1' : 'badge-p3'
            ">
              {{ mf.status === 'success' ? '完成' : mf.status === 'failed' ? '失败' : mf.status === 'parsing' ? '解析中' : '等待' }}
            </span>
            <div class="pf-progress">
              <div class="pf-fill" :style="{ width: (mf.progress || 0) + '%' }"></div>
            </div>
            <span class="pf-pct">{{ mf.progress || 0 }}%</span>
            <span class="pf-rows" v-if="mf.rows_parsed">{{ mf.rows_parsed }} 行</span>
            <span class="pf-msg muted" v-if="mf.message">{{ mf.message }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Drag & drop upload zone -->
    <section
      class="upload-zone card"
      :class="{ 'drag-active': dragActive, 'disabled': !selectedProjectId }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
      @click="triggerFileInput"
    >
      <input
        ref="fileInput"
        type="file"
        multiple
        accept=".log,.csv,.cfg,.conf,.txt,.chm,.pdf,.html,.md,.docx"
        style="display:none"
        @change="handleFileInputChange"
      />
      <div class="upload-zone-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <h2 class="upload-zone-title">拖放文件到此处，或点击选择文件</h2>
      <p class="upload-zone-hint">
        支持 <code>.log</code> <code>.csv</code> <code>.cfg</code> <code>.conf</code> <code>.txt</code> <code>.pdf</code> <code>.md</code> <code>.html</code> 等 · 单文件建议 <200MB
      </p>
      <div v-if="!selectedProjectId" class="upload-zone-warn">⚠ 请先在上方选择或创建一个「上传目标项目」</div>
    </section>

    <!-- Upload progress (per-file HTTP upload) -->
    <div v-if="Object.keys(uploadProgress).length" class="card upload-progress-card">
      <div class="card-header">
        <h3 class="card-title h4">上传中</h3>
      </div>
      <div class="upload-progress-list">
        <div v-for="(pct, key) in uploadProgress" :key="key" class="up-row">
          <div class="up-meta">
            <span class="up-name">{{ String(key).split('-').slice(0, -1).join('-') }}</span>
            <span class="up-pct">{{ pct }}%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" :style="{ width: pct + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Material list -->
    <section class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">已上传材料</h3>
          <p class="card-desc">
            当前项目共 {{ materials.length }} 份文件，
            已解析 {{ materials.filter(m => ['success','parsed','indexed'].includes(String(m.status || '').toLowerCase())).length }} 份
          </p>
        </div>
        <div class="filter-bar">
          <button v-for="f in filters" :key="f" class="filter-chip" :class="{ active: filterActive === f }" @click="filterActive = f">{{ f }}</button>
        </div>
      </div>

      <div v-if="!filteredMaterials.length" class="empty-hint">
        <div v-if="!materials.length">暂无上传材料，点击上方拖拽区开始</div>
        <div v-else>当前过滤条件下暂无匹配</div>
      </div>

      <div v-else class="file-list">
        <div class="file-row" v-for="m in filteredMaterials" :key="m.id">
          <div class="file-info">
            <div class="file-icon" :class="'type-' + (m.type || 'unknown')">
              {{ (m.format || m.type || '?').slice(0, 4).toUpperCase() }}
            </div>
            <div class="file-text">
              <p class="file-name">{{ m.name }}</p>
              <p class="file-meta">
                <span v-if="m.deviceName">设备 {{ m.deviceName }} · </span>
                <span v-if="m.rows">{{ m.rows.toLocaleString() }} 条记录 · </span>
                <span>{{ formatSize(m.size) }}</span>
                <span v-if="m.uploadedAt"> · {{ m.uploadedAt }}</span>
              </p>
              <!-- Progress inside file-row for pending/parsing -->
              <div v-if="['pending','parsing'].includes(String(m.status || '').toLowerCase())" class="inline-progress-row">
                <div class="mini-track">
                  <div class="mini-fill" :style="{ width: (m.progress ?? 0) + '%' }"></div>
                </div>
                <span class="mini-msg muted">{{ m.message || '解析中…' }}</span>
              </div>
            </div>
          </div>
          <div class="file-status">
            <span class="badge" :class="statusBadge(m).cls">{{ statusBadge(m).text }}</span>
            <div class="file-actions">
              <button
                class="btn btn-ghost btn-xs"
                :disabled="String(m.status || '').toLowerCase() === 'parsing'"
                @click.stop="reparseMaterial(m)"
              >重新解析</button>
              <button
                class="btn btn-danger-ghost btn-xs"
                @click.stop="deleteMaterial(m)"
              >删除</button>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Create project dialog -->
    <el-dialog v-model="newProjectDialogVisible" title="新建项目" width="500px">
      <el-form :model="newProjectForm" label-width="90px">
        <el-form-item label="项目名称" required>
          <el-input v-model="newProjectForm.name" placeholder="例如：XX分行边界审计 2026-Q3" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="newProjectForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit placeholder="项目范围/目标网络/审计阶段" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="newProjectDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="confirmCreateProject">创建并切换</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.upload-page { width: 100%; }

.top-bar { padding: 22px 22px 18px; }
.top-bar-grid {
  display: grid; gap: 18px;
  grid-template-columns: minmax(0, 1.1fr) minmax(220px, 0.7fr) minmax(0, 1.1fr) auto;
  align-items: center;
}
@media (max-width: 1100px) {
  .top-bar-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 620px) {
  .top-bar-grid { grid-template-columns: 1fr; }
}

.field { display: flex; flex-direction: column; gap: 6px; }
.field-label {
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--color-text-soft);
}
.project-select-wrap { display: flex; gap: 10px; align-items: center; }
.project-select {
  flex: 1; min-width: 0;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--color-border);
  background: var(--color-bg);
  color: var(--color-text);
  font-size: 14px;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.project-select:focus {
  outline: none; border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-dim);
}
.hint { font-size: 12px; color: var(--color-text-soft); margin: 0; }

.scope-card {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 14px;
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border-soft);
  border-radius: 12px;
}
.scope-icon {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), var(--primary-deep));
  color: #fff; display: inline-flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 700;
}
.scope-meta { display: flex; flex-direction: column; gap: 2px; }
.scope-title { font-size: 13px; font-weight: 600; }
.scope-sub { font-size: 11.5px; color: var(--color-text-soft); }

.stat-chips { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }
.stat-chip {
  min-width: 76px;
  display: inline-flex; flex-direction: column; align-items: flex-start;
  padding: 8px 12px; border-radius: 10px;
  background: var(--color-bg-soft);
  border: 1px solid var(--color-border-soft);
}
.stat-chip b { font-size: 17px; font-weight: 700; line-height: 1.1; color: var(--color-text); }
.stat-chip small { font-size: 11px; color: var(--color-text-soft); margin-top: 2px; }
.stat-chip-ok b { color: #059669; }
.stat-chip-wait b { color: #d97706; }
.stat-chip-danger b { color: #dc2626; }

.top-actions { display: flex; gap: 8px; justify-content: flex-end; }

.analysis-progress {
  margin-top: 18px;
  padding: 14px 16px;
  background: linear-gradient(180deg, var(--primary-50), transparent);
  border: 1px dashed var(--primary-dim);
  border-radius: 12px;
}
.analysis-progress-head {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 8px; font-size: 13px;
}
.analysis-progress-head b { font-size: 14px; color: var(--primary-deep); }
.analysis-progress-head .muted { color: var(--color-text-soft); font-size: 12.5px; margin-right: auto; }
.analysis-progress-head .percent { font-weight: 700; color: var(--primary-deep); min-width: 48px; text-align: right; }
.progress-track-lg {
  position: relative; width: 100%; height: 10px;
  background: #e5e7eb; border-radius: 999px; overflow: hidden;
}
.progress-fill-lg {
  position: absolute; inset: 0 auto 0 0;
  background: linear-gradient(90deg, var(--primary), var(--primary-deep));
  border-radius: 999px;
  transition: width .3s ease;
}
.analysis-progress-stats {
  display: flex; flex-wrap: wrap; gap: 14px;
  margin-top: 10px; font-size: 12.5px; color: var(--color-text-soft);
}
.analysis-progress-stats .danger { color: var(--color-danger); }

.per-file {
  margin-top: 12px;
  display: flex; flex-direction: column; gap: 8px;
  padding: 10px 12px; background: var(--color-bg);
  border-radius: 10px;
  border: 1px solid var(--color-border-soft);
}
.pf-row {
  display: grid; gap: 8px 10px;
  grid-template-columns: minmax(0, 1.4fr) 74px minmax(0, 1fr) 52px 72px auto;
  align-items: center;
  font-size: 12.5px;
}
@media (max-width: 900px) {
  .pf-row { grid-template-columns: minmax(0, 1fr) 60px minmax(0, 1fr) 48px; }
  .pf-rows, .pf-msg { display: none; }
}
.pf-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pf-badge { padding: 1px 8px; border-radius: 999px; font-size: 11px; text-align: center; color: #fff; }
.pf-badge.badge-p2 { background:#059669;}
.pf-badge.badge-p0 { background:#dc2626;}
.pf-badge.badge-p1 { background:#d97706;}
.pf-badge.badge-p3 { background:#6b7280;}
.pf-progress { height: 6px; border-radius: 999px; background: #e5e7eb; overflow: hidden; }
.pf-fill { height: 100%; background: var(--primary); border-radius: 999px; transition: width .25s ease; }
.pf-pct { text-align: right; color: var(--color-text-soft); font-variant-numeric: tabular-nums; }
.pf-rows { color: var(--color-text-soft); }
.pf-msg { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.upload-zone {
  margin-top: 16px;
  padding: 40px 20px;
  text-align: center;
  border: 2px dashed var(--color-border);
  border-radius: 18px;
  background: var(--color-bg);
  transition: all .2s ease;
}
.upload-zone.disabled { opacity: .6; cursor: not-allowed; }
.upload-zone:hover:not(.disabled) { border-color: var(--primary-dim); background: var(--primary-50); }
.upload-zone.drag-active { border-color: var(--primary); background: var(--primary-50); }
.upload-zone-icon {
  margin: 0 auto 10px;
  width: 54px; height: 54px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary-50), var(--primary-dim));
  color: var(--primary-deep);
  display: flex; align-items: center; justify-content: center;
}
.upload-zone-icon svg { width: 28px; height: 28px; }
.upload-zone-title { margin: 4px 0 6px; font-size: 18px; font-weight: 600; }
.upload-zone-hint { margin: 0; color: var(--color-text-soft); font-size: 13px; }
.upload-zone-hint code {
  padding: 1px 6px; background: var(--color-bg-soft); border: 1px solid var(--color-border-soft);
  border-radius: 6px; font-size: 12px;
}
.upload-zone-warn {
  margin-top: 12px; display: inline-block;
  padding: 6px 12px; border-radius: 999px;
  background: #fff7ed; color: #c2410c;
  border: 1px solid #fed7aa; font-size: 12.5px;
}

.upload-progress-card { margin-top: 16px; }
.upload-progress-list { display: flex; flex-direction: column; gap: 10px; }
.up-row .up-meta { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }
.up-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-track { position: relative; height: 6px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
.progress-fill { position: absolute; inset: 0 auto 0 0; background: var(--primary); border-radius: 999px; transition: width .2s ease; }

.file-list { display: flex; flex-direction: column; gap: 4px; }
.file-row {
  display: flex; justify-content: space-between; align-items: center; gap: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid transparent;
  transition: background .15s ease, border-color .15s ease;
}
.file-row:hover { background: var(--color-bg-soft); border-color: var(--color-border-soft); }
.file-info { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.file-icon {
  width: 40px; height: 40px; border-radius: 10px;
  background: #eef2ff; color: #4338ca;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 11px; letter-spacing: .05em;
}
.file-icon.type-log { background: #fef3c7; color: #92400e; }
.file-icon.type-config { background: #dcfce7; color: #166534; }
.file-icon.type-manual { background: #fee2e2; color: #991b1b; }
.file-icon.type-unknown { background: #f1f5f9; color: #334155; }
.file-text { min-width: 0; flex: 1; }
.file-name { margin: 0; font-size: 14px; font-weight: 500; }
.file-meta { margin: 2px 0 0; font-size: 12px; color: var(--color-text-soft); }
.inline-progress-row {
  margin-top: 6px;
  display: flex; align-items: center; gap: 8px;
}
.mini-track { flex: 1; height: 5px; background: #e5e7eb; border-radius: 999px; overflow: hidden; }
.mini-fill { height: 100%; background: #d97706; border-radius: 999px; }
.mini-msg { font-size: 11.5px; }

.file-status { display: flex; align-items: center; gap: 10px; }
.file-actions { display: flex; gap: 6px; }
.btn-danger-ghost {
  color: var(--color-danger);
  border-color: #fecaca;
  background: transparent;
}
.btn-danger-ghost:hover { background: #fef2f2; }

.empty-hint { padding: 34px 10px; text-align: center; color: var(--color-text-soft); font-size: 13.5px; }
</style>
