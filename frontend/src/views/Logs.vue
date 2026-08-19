<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { LogEvent, Material } from '@/types'

const store = useProjectStore()
const filterActive = ref('全部')
const filters = ['全部', '连接', '命令', '异常']
const timeline = ref<any[]>([])
const events = ref<LogEvent[]>([])
const materials = ref<Material[]>([])
const loading = ref(false)
const reparseLoading = ref(false)

const filterTypeMap: Record<string, string[]> = {
  '连接': ['connect'],
  '命令': ['command', 'change'],
  '异常': ['disconnect']
}

const filteredEvents = computed(() => {
  if (filterActive.value === '全部') return events.value
  const types = filterTypeMap[filterActive.value] || []
  return events.value.filter(e => types.includes(e.type))
})

function typeBadge(t: string) {
  const map: Record<string, { cls: string; text: string }> = {
    connect: { cls: 'badge-info', text: 'connect' },
    auth: { cls: 'badge-p2', text: 'auth' },
    command: { cls: 'badge-p3', text: 'command' },
    change: { cls: 'badge-p1', text: 'change' },
    disconnect: { cls: 'badge-p3', text: 'disconnect' }
  }
  return map[t] || { cls: 'badge-p3', text: t }
}

async function loadTimeline() {
  try {
    timeline.value = await logApi.timeline(store.currentProject.id)
  } catch {}
}

async function loadEvents() {
  loading.value = true
  try {
    const logMaterial = materials.value.find(m => m.type === 'log')
    if (logMaterial) {
      events.value = await logApi.events(logMaterial.id)
    }
  } finally {
    loading.value = false
  }
}

async function loadMaterials() {
  try {
    materials.value = await materialApi.list(store.currentProject.id)
  } catch {}
}

function exportCSV() {
  try {
    const headers = ['时间', '类型', '用户', '源 IP', '详情']
    const rows = events.value.map(e => [
      e.time, e.type, e.user || '', e.sourceIp || '', e.detail
    ])
    const csv = [headers, ...rows].map(r => r.map(x => `"${x}"`).join(',')).join('\n')
    const BOM = '\uFEFF'
    const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `events-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.warning('导出失败，请检查浏览器设置')
  }
}

async function handleReparse() {
  reparseLoading.value = true
  try {
    const logMaterial = materials.value.find(m => m.type === 'log')
    if (logMaterial) {
      await materialApi.reparse(logMaterial.id)
      await Promise.all([loadTimeline(), loadEvents()])
    } else {
      ElMessage.warning('未找到日志材料')
    }
  } finally {
    reparseLoading.value = false
  }
}

onMounted(async () => {
  await store.init()
  await loadMaterials()
  await Promise.all([loadTimeline(), loadEvents()])
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">日志关联分析</div>
        <h1 class="h1">日志事件与时间线</h1>
        <p class="text-muted">跨文件关联操作行为，识别访问路径与异常会话。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="exportCSV">导出事件</button>
        <button class="btn btn-primary btn-sm" :disabled="reparseLoading" @click="handleReparse">
          {{ reparseLoading ? '解析中...' : '重新解析' }}
        </button>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">会话时间线</h3>
            <p class="card-desc">2026-08-17 20:08 起始的 SSH 会话</p>
          </div>
        </div>
        <div class="timeline">
          <div class="timeline-item" v-for="(item, idx) in timeline" :key="idx">
            <p class="timeline-time">{{ item.time }}</p>
            <p class="timeline-title">{{ item.title }}</p>
            <p class="timeline-desc">{{ item.desc }}</p>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">结构化事件</h3>
            <p class="card-desc">解析后的统一事件模型</p>
          </div>
          <div class="filter-bar">
            <button v-for="f in filters" :key="f" class="filter-chip" :class="{ active: filterActive === f }" @click="filterActive = f">{{ f }}</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>时间</th><th>类型</th><th>用户</th><th>源 IP</th><th>详情</th></tr>
            </thead>
            <tbody>
              <tr v-for="e in filteredEvents" :key="e.id">
                <td>{{ e.time }}</td>
                <td><span class="badge" :class="typeBadge(e.type).cls">{{ typeBadge(e.type).text }}</span></td>
                <td>{{ e.user || '—' }}</td>
                <td class="cell-mono">{{ e.sourceIp || '' }}</td>
                <td :class="{ 'cell-mono': e.type === 'command' || e.type === 'change' }">{{ e.detail }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
