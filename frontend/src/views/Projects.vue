<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { projectApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { Project, Material } from '@/types'

const router = useRouter()
const store = useProjectStore()
const projects = ref<Project[]>([])

// -- create
const newProjectDialogVisible = ref(false)
type ProjectStatus = 'active' | 'archived' | 'in-progress'
const newProjectForm = ref<{ name: string; description: string; status: ProjectStatus }>({
  name: '', description: '', status: 'active',
})

// -- edit
const editDialogVisible = ref(false)
const editingProject = ref<Project | null>(null)
const editForm = ref<{ name: string; description: string; status: ProjectStatus }>({
  name: '', description: '', status: 'active',
})

const busy = ref(false)

// -- 项目下材料汇总：点击卡片展开，不跳转首页
const expandedId = ref<Project['id'] | null>(null)
const materials = ref<Material[]>([])
const materialsLoading = ref(false)

const expandedProjectName = computed(() => {
  const p = projects.value.find(x => x.id === expandedId.value)
  return p?.name || ''
})

function statusBadge(s: string) {
  if (s === 'active') return { cls: 'badge-p2', text: '进行中' }
  if (s === 'archived') return { cls: 'badge-p3', text: '已归档' }
  return { cls: 'badge-p3', text: '评估中' }
}

// 材料状态文案
function materialStatusText(s: string) {
  const map: Record<string, string> = {
    pending: '待解析',
    parsing: '解析中',
    success: '已解析',
    parsed: '已解析',
    indexed: '已索引',
    risk: '有风险',
    failed: '解析失败'
  }
  return map[String(s || '').toLowerCase()] || s || '—'
}

// 材料状态徽标
function materialBadgeCls(s: string) {
  const d = String(s || '').toLowerCase()
  if (d === 'failed') return 'badge-p0'
  if (d === 'risk') return 'badge-p1'
  if (d === 'parsing' || d === 'pending') return 'badge-p3'
  return 'badge-p2'
}

// 字节数格式化为可读大小
function formatSize(size: any) {
  if (size == null || size === '') return '—'
  const n = Number(size)
  if (!isFinite(n) || n <= 0) return String(size)
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0, v = n
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++ }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`
}

async function loadProjects() {
  try { projects.value = await projectApi.list() } catch {}
}

// 点击项目卡片：展开/收起该项目下的材料列表
async function toggleMaterials(p: Project) {
  if (expandedId.value === p.id) {
    expandedId.value = null
    materials.value = []
    return
  }
  expandedId.value = p.id
  materials.value = []
  materialsLoading.value = true
  try {
    materials.value = await materialApi.list(p.id)
  } catch {
    materials.value = []
  } finally {
    materialsLoading.value = false
  }
}

function collapseMaterials() {
  expandedId.value = null
  materials.value = []
}

// 设为当前项目并跳转首页（保留原有跳转行为）
function setCurrentProject(p: Project, ev?: Event) {
  ev?.stopPropagation()
  store.setProject({
    id: p.id,
    name: p.name,
    status: p.status,
    materialsCount: p.materialsCount,
    risksCount: p.risksCount,
  })
  ElMessage.success(`已切换到项目：${p.name}`)
  router.push({ name: 'dashboard' })
}

function openNewProjectDialog() {
  newProjectForm.value = { name: '', description: '', status: 'active' }
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
      status: newProjectForm.value.status as Project['status'],
    })
    projects.value.unshift(p)
    newProjectDialogVisible.value = false
    // 创建后设为当前项目并跳转首页
    setCurrentProject(p)
  } catch {}
}

function openEditProject(p: Project, ev: Event) {
  ev.stopPropagation()
  editingProject.value = p
  editForm.value = {
    name: p.name,
    description: p.description || '',
    status: p.status || 'active',
  }
  editDialogVisible.value = true
}

async function confirmEditProject() {
  if (!editingProject.value) return
  const name = editForm.value.name.trim()
  if (!name) {
    ElMessage.warning('项目名称不能为空')
    return
  }
  try {
    busy.value = true
    const updated = await projectApi.update(editingProject.value.id, {
      name: editForm.value.name,
      description: editForm.value.description,
      status: editForm.value.status as Project['status'],
    })
    const idx = projects.value.findIndex(p => p.id === updated.id)
    if (idx >= 0) projects.value[idx] = { ...projects.value[idx], ...updated }
    ElMessage.success('项目信息已更新')
    editDialogVisible.value = false
  } finally {
    busy.value = false
  }
}

async function deleteProject(p: Project, ev: Event) {
  ev.stopPropagation()
  try {
    await ElMessageBox.confirm(
      `将删除项目「${p.name}」及其所有上传材料、配置、日志和风险发现，此操作不可恢复。是否继续？`,
      '确认删除项目',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消', dangerouslyUseHTMLString: false },
    )
  } catch { return }
  try {
    busy.value = true
    await projectApi.remove(p.id)
    projects.value = projects.value.filter(x => x.id !== p.id)
    // 若删除的是当前展开的项目，收起材料面板
    if (expandedId.value === p.id) collapseMaterials()
    ElMessage.success(`项目「${p.name}」已删除`)
    if (store.currentProject?.id === p.id) {
      store.clearProject()
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败')
  } finally {
    busy.value = false
  }
}

onMounted(loadProjects)
</script>

<template>
  <div class="projects-page page">
    <header class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">项目管理</div>
        <h1 class="h1">项目中心</h1>
        <p class="text-muted">以项目维度隔离材料、分析结果与版本追溯；数据独立，跨项目无串扰。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" :disabled="busy" @click="loadProjects">刷新</button>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="openNewProjectDialog">+ 新建项目</button>
      </div>
    </header>

    <div v-if="!projects.length" class="empty-panel card">
      <div class="empty">
        <div class="empty-icon">📁</div>
        <h3>还没有项目</h3>
        <p>新建一个项目，然后上传配置、日志、流量 CSV 开始分析。</p>
        <button class="btn btn-primary mt" @click="openNewProjectDialog">创建第一个项目</button>
      </div>
    </div>

    <div v-else class="three-col">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card project-card"
        :class="{ active: p.status === 'active', expanded: expandedId === p.id }"
        @click="toggleMaterials(p)"
      >
        <div class="card-header">
          <div class="project-title-group">
            <h3 class="card-title h4">{{ p.name }}</h3>
            <p class="card-desc">
              {{ p.status === 'active' ? '当前活跃项目' : p.status === 'archived' ? '项目已归档' : `状态：${p.status}` }}
            </p>
          </div>
          <span class="badge" :class="statusBadge(p.status).cls">{{ statusBadge(p.status).text }}</span>
        </div>

        <p class="project-desc" v-if="p.description">{{ p.description }}</p>
        <p class="project-desc empty" v-else>暂无描述</p>

        <div class="project-meta">
          <span><b>{{ p.materialsCount }}</b>份材料</span>
          <span><b>{{ p.devicesCount || 0 }}</b>台设备</span>
          <span><b>{{ p.risksCount }}</b>项风险</span>
        </div>

        <div class="project-footer">
          <div class="project-foot-info">
            <span class="muted">项目 ID #{{ p.id }}</span>
            <span class="muted" v-if="p.created_at">创建于 {{ new Date(p.created_at).toLocaleDateString() }}</span>
          </div>
          <div class="project-actions" @click.stop>
            <button class="btn btn-primary btn-xs" :disabled="busy" @click="setCurrentProject(p, $event)">
              设为当前项目
            </button>
            <button class="btn btn-ghost btn-xs" :disabled="busy" @click="openEditProject(p, $event)">
              编辑
            </button>
            <button class="btn btn-danger-ghost btn-xs" :disabled="busy" @click="deleteProject(p, $event)">
              删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 选中项目的材料汇总面板 -->
    <div v-if="expandedId !== null" class="card materials-panel">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">{{ expandedProjectName }} · 材料汇总</h3>
          <p class="card-desc">项目下已上传的材料，点击项目卡片可切换</p>
        </div>
        <button class="btn btn-ghost btn-sm" @click="collapseMaterials">收起</button>
      </div>
      <div class="table-wrap">
        <div v-if="materialsLoading" class="materials-tip">加载中…</div>
        <table v-else>
          <thead>
            <tr>
              <th>文件名</th>
              <th>类型</th>
              <th>状态</th>
              <th>大小</th>
              <th>上传时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in materials" :key="m.id">
              <td>{{ m.name }}</td>
              <td>{{ m.type }}</td>
              <td><span class="badge" :class="materialBadgeCls(m.status)">{{ materialStatusText(m.status) }}</span></td>
              <td>{{ formatSize(m.size) }}</td>
              <td>{{ m.uploadedAt || m.created_at || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!materialsLoading && materials.length === 0" class="materials-tip">该项目暂无材料</div>
      </div>
    </div>

    <!-- Create dialog -->
    <el-dialog v-model="newProjectDialogVisible" title="新建项目" width="520px" class="project-dialog">
      <el-form :model="newProjectForm" label-width="92px">
        <el-form-item label="项目名称" required>
          <el-input v-model="newProjectForm.name" placeholder="如：生产网边界审计 2026-Q4" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="newProjectForm.description"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="简要描述项目范围、目标网络与审计阶段"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select v-model="newProjectForm.status" style="width:100%">
            <el-option label="进行中" value="active" />
            <el-option label="评估中" value="draft" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="newProjectDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="confirmCreateProject">创建项目</button>
      </template>
    </el-dialog>

    <!-- Edit dialog -->
    <el-dialog v-model="editDialogVisible" title="编辑项目" width="520px" class="project-dialog">
      <el-form :model="editForm" label-width="92px">
        <el-form-item label="项目名称" required>
          <el-input v-model="editForm.name" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select v-model="editForm.status" style="width:100%">
            <el-option label="进行中" value="active" />
            <el-option label="评估中" value="draft" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="editDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="busy" @click="confirmEditProject">保存修改</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.projects-page { width: 100%; }

.project-card {
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  border: 1px solid var(--color-border-soft);
  border-radius: 16px;
  transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
  background: var(--color-bg);
}
.project-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 32px rgba(15,23,42,.08);
  border-color: var(--primary-dim);
}
.project-card.active {
  border-top: 3px solid var(--primary);
}
.project-card.expanded {
  border-color: var(--primary);
  box-shadow: 0 12px 32px rgba(15,23,42,.12);
}

.card-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.project-title-group { min-width: 0; }
.project-title-group .card-title { margin: 0; font-size: 17px; line-height: 1.3; }
.project-title-group .card-desc {
  margin: 4px 0 0;
  color: var(--color-text-soft);
  font-size: 12.5px;
}
.project-desc {
  margin: 0;
  min-height: 36px;
  color: var(--color-text);
  font-size: 13.5px;
  line-height: 1.55;
}
.project-desc.empty { color: var(--color-text-soft); font-style: italic; }

.project-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12.5px;
  color: var(--color-text-soft);
  padding: 10px 12px;
  background: var(--color-bg-soft);
  border-radius: 10px;
}
.project-meta b { color: var(--color-text); font-size: 14px; margin-right: 2px; }

.project-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding-top: 6px;
  margin-top: auto;
  border-top: 1px dashed var(--color-border-soft);
}
.project-foot-info {
  display: flex; flex-direction: column; gap: 2px;
  font-size: 11.5px;
}
.project-foot-info .muted { color: var(--color-text-soft); }
.project-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.btn-danger-ghost {
  color: var(--color-danger);
  border-color: #fecaca;
  background: transparent;
}
.btn-danger-ghost:hover { background: #fef2f2; }

.project-dialog :deep(.el-dialog__body) { padding-top: 8px; }

.empty-panel { padding: 48px 20px; }
.empty-panel .empty { text-align: center; color: var(--color-text-soft); }
.empty-panel .empty-icon { font-size: 40px; margin-bottom: 6px; }
.empty-panel .empty h3 { margin: 0 0 4px; color: var(--color-text); font-weight: 600; font-size: 17px; }
.empty-panel .empty p { margin: 0; }
.empty-panel .mt { margin-top: 14px; }

/* 材料汇总面板 */
.materials-panel { margin-top: 20px; }
.materials-tip {
  text-align: center;
  padding: 32px 0;
  color: var(--color-text-soft);
  font-size: 13px;
}
</style>
