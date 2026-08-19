<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { Project } from '@/types'

const router = useRouter()
const store = useProjectStore()
const projects = ref<Project[]>([])
const newProjectDialogVisible = ref(false)
const newProjectForm = ref({ name: '', description: '' })

function statusBadge(s: string) {
  if (s === 'active') return { cls: 'badge-p2', text: '进行中', border: true }
  if (s === 'archived') return { cls: 'badge-p3', text: '已归档', border: false }
  return { cls: 'badge-p3', text: '评估中', border: false }
}

async function loadProjects() {
  try {
    projects.value = await projectApi.list()
  } catch {}
}

function openProject(p: Project) {
  store.setProject({
    id: p.id,
    name: p.name,
    status: p.status,
    materialsCount: p.materialsCount,
    risksCount: p.risksCount
  })
  ElMessage.success(`已切换到项目：${p.name}`)
  router.push({ name: 'dashboard' })
}

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
    const p = await projectApi.create(newProjectForm.value)
    projects.value.unshift(p)
    openProject(p)
    newProjectDialogVisible.value = false
  } catch {}
}

onMounted(loadProjects)
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">项目管理</div>
        <h1 class="h1">项目中心</h1>
        <p class="text-muted">以项目维度管理材料、分析结果与版本追溯。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-primary btn-sm" @click="openNewProjectDialog">新建项目</button>
      </div>
    </div>

    <div class="three-col">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card project-card"
        :style="p.status === 'active' ? 'border-top:3px solid var(--primary);cursor:pointer' : 'cursor:pointer'"
        @click="openProject(p)"
      >
        <div class="card-header">
          <div>
            <h3 class="card-title h4">{{ p.name }}</h3>
            <p class="card-desc">{{ p.status === 'active' ? '当前活跃项目' : (p.completedAt ? `${p.completedAt} 完成` : '') }}</p>
          </div>
          <span class="badge" :class="statusBadge(p.status).cls">{{ statusBadge(p.status).text }}</span>
        </div>
        <p class="text-muted" style="margin:0 0 16px;font-size:13px">{{ p.description }}</p>
        <div style="display:flex;gap:16px;font-size:12px;color:var(--text-600)">
          <span>{{ p.materialsCount }} 份材料</span>
          <span>{{ p.devicesCount || 0 }} 台设备</span>
          <span>{{ p.risksCount }} 项风险</span>
        </div>
      </div>
    </div>

    <el-dialog v-model="newProjectDialogVisible" title="新建项目" width="500px">
      <el-form :model="newProjectForm" label-width="90px">
        <el-form-item label="项目名称">
          <el-input v-model="newProjectForm.name" placeholder="如：生产网边界审计 2026-Q4" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="newProjectForm.description"
            type="textarea"
            :rows="3"
            placeholder="简要描述项目范围与目标"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="newProjectDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="confirmCreateProject">创建</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.project-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}
</style>
