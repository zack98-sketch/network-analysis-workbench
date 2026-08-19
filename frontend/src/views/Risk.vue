<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { riskApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { RiskFinding } from '@/types'

const router = useRouter()
const store = useProjectStore()
const filterActive = ref('全部')
const filters = ['全部', '安全策略', 'SSH', 'AAA', '管理平面']
const risks = ref<RiskFinding[]>([])
const recheckLoading = ref(false)

const p0Count = computed(() => risks.value.filter(r => r.severity === 'p0').length)
const p1Count = computed(() => risks.value.filter(r => r.severity === 'p1').length)
const p2Count = computed(() => risks.value.filter(r => r.severity === 'p2').length)
const p3Count = computed(() => risks.value.filter(r => r.severity === 'p3').length)

const filteredRisks = computed(() => {
  if (filterActive.value === '全部') return risks.value
  return risks.value.filter(r => r.category === filterActive.value)
})

function severityBadge(sev: string) {
  const map: Record<string, { cls: string; text: string }> = {
    p0: { cls: 'badge-p0', text: '高危' },
    p1: { cls: 'badge-p1', text: '中危' },
    p2: { cls: 'badge-p2', text: '低危' },
    p3: { cls: 'badge-p3', text: '信息' }
  }
  return map[sev]
}

function statusBadge(status: string) {
  if (status === '待处理') return 'badge-p0'
  if (status === '待确认') return 'badge-p1'
  if (status === '建议') return 'badge-p2'
  return 'badge-p3'
}

const statusFlow: Record<string, string> = {
  '待处理': '待确认',
  '待确认': '建议',
  '建议': '记录',
  '记录': '待处理'
}

async function loadRisks() {
  try {
    risks.value = await riskApi.list(store.currentProject.id)
  } catch {}
}

async function handleRecheck() {
  recheckLoading.value = true
  try {
    risks.value = await riskApi.recheck(store.currentProject.id)
  } finally {
    recheckLoading.value = false
  }
}

async function handleRowDoubleClick(risk: RiskFinding) {
  const nextStatus = statusFlow[risk.status] || '待处理'
  try {
    await ElMessageBox.confirm(
      `确认将风险 ${risk.id} 状态从「${risk.status}」更新为「${nextStatus}」？`,
      '更新风险状态',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
    )
    await riskApi.updateStatus(risk.id, nextStatus)
    await loadRisks()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('状态更新失败')
    }
  }
}

function goToRules() {
  router.push({ name: 'rules' })
}

onMounted(async () => {
  await store.init()
  loadRisks()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">风险分析与整改建议</div>
        <h1 class="h1">风险发现清单</h1>
        <p class="text-muted">基于等保 2.0、CIS Benchmark 与厂商加固指南自动检测。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="goToRules">规则库</button>
        <button class="btn btn-primary btn-sm" :disabled="recheckLoading" @click="handleRecheck">
          {{ recheckLoading ? '检测中...' : '重新检测' }}
        </button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">高危</div>
        <div class="stat-value" style="color:var(--error-500)">{{ p0Count }}</div>
        <div class="stat-meta">需立即整改</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">中危</div>
        <div class="stat-value" style="color:var(--warning-500)">{{ p1Count }}</div>
        <div class="stat-meta">限期 7 日</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">低危</div>
        <div class="stat-value" style="color:var(--success-500)">{{ p2Count }}</div>
        <div class="stat-meta">建议 30 日</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">信息</div>
        <div class="stat-value" style="color:var(--text-500)">{{ p3Count }}</div>
        <div class="stat-meta">记录备查</div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">风险详情</h3>
          <p class="card-desc">按等级与功能域排序 · 双击行切换状态</p>
        </div>
        <div class="filter-bar">
          <button v-for="f in filters" :key="f" class="filter-chip" :class="{ active: filterActive === f }" @click="filterActive = f">{{ f }}</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>ID</th><th>等级</th><th>类别</th><th>描述</th><th>来源</th><th>整改命令</th><th>状态</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in filteredRisks" :key="r.id" @dblclick="handleRowDoubleClick(r)" style="cursor:pointer">
              <td class="cell-mono">{{ r.id }}</td>
              <td><span class="badge" :class="severityBadge(r.severity).cls">{{ severityBadge(r.severity).text }}</span></td>
              <td>{{ r.category }}</td>
              <td>{{ r.description }}</td>
              <td class="cell-mono">{{ r.source }}</td>
              <td class="cell-mono" style="white-space:pre-line">{{ r.remediation }}</td>
              <td><span class="badge" :class="statusBadge(r.status)">{{ r.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
