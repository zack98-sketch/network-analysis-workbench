<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { logApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { LogEvent, Material } from '@/types'

const store = useProjectStore()

// ============ Tab 切换 ============
type TabKey = 'timeline' | 'events' | 'traffic' | 'behavior'
const activeTab = ref<TabKey>('timeline')
const tabs: { key: TabKey; label: string }[] = [
  { key: 'timeline', label: '会话时间线' },
  { key: 'events', label: '结构化事件' },
  { key: 'traffic', label: '流量分析' },
  { key: 'behavior', label: '操作与行为' }
]

// ============ 时间线（Tab 1） ============
// 后端返回 {buckets: [{time, count, by_type: {connect: n, command: n, ...}}]}
const timelineBuckets = ref<any[]>([])
const timelineLoading = ref(false)

// by_type 各类型中文标签
const typeLabelMap: Record<string, string> = {
  connect: '连接',
  auth: '认证',
  command: '命令',
  change: '变更',
  disconnect: '异常'
}

// 将 bucket 的 by_type 渲染为 "连接 5 · 命令 3 · 异常 1" 形式
function bucketDesc(byType: Record<string, number> = {}): string {
  const parts = Object.entries(byType || {})
    .filter(([, n]) => Number(n) > 0)
    .map(([k, n]) => `${typeLabelMap[k] || k} ${n}`)
  return parts.length ? parts.join(' · ') : '无类型分布'
}

// ============ 结构化事件（Tab 2） ============
const filterActive = ref('全部')
const filters = ['全部', '连接', '命令', '异常']
const events = ref<LogEvent[]>([])
const materials = ref<Material[]>([])
const eventsLoading = ref(false)
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

// 事件类型徽章
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

// ============ 流量分析（Tab 3） ============
const traffic = ref<any>(null)
const trafficLoading = ref(false)

// ============ 操作与行为（Tab 4） ============
const operations = ref<any>(null)
const behavior = ref<any>(null)
const opsLoading = ref(false)

// 加载会话时间线
async function loadTimeline() {
  timelineLoading.value = true
  try {
    const data = await logApi.timeline(store.currentProject.id) as any
    // 兼容 {buckets: [...]} 与数组两种返回形态
    timelineBuckets.value = data?.buckets || (Array.isArray(data) ? data : [])
  } catch {
    timelineBuckets.value = []
  } finally {
    timelineLoading.value = false
  }
}

// 加载项目所有 log 类型材料的事件（使用 Promise.all 并发拉取）
async function loadEvents() {
  eventsLoading.value = true
  try {
    const logMaterials = materials.value.filter(m => m.type === 'log')
    if (logMaterials.length === 0) {
      events.value = []
      return
    }
    const results = await Promise.all(
      logMaterials.map(m => logApi.events(m.id).catch(() => [] as LogEvent[]))
    )
    events.value = results.flat()
  } finally {
    eventsLoading.value = false
  }
}

// 加载材料列表
async function loadMaterials() {
  try {
    materials.value = await materialApi.list(store.currentProject.id)
  } catch {
    materials.value = []
  }
}

// 加载流量分析
async function loadTraffic() {
  trafficLoading.value = true
  try {
    traffic.value = await logApi.traffic(store.currentProject.id)
  } catch {
    traffic.value = null
  } finally {
    trafficLoading.value = false
  }
}

// 加载操作分析与用户行为测绘
async function loadOpsAndBehavior() {
  opsLoading.value = true
  try {
    const [opsData, behData] = await Promise.all([
      logApi.operations(store.currentProject.id).catch(() => null),
      logApi.behavior(store.currentProject.id).catch(() => null)
    ])
    operations.value = opsData
    behavior.value = behData
  } finally {
    opsLoading.value = false
  }
}

// 导出 CSV
function exportCSV() {
  try {
    const headers = ['时间', '类型', '用户', '源 IP', '详情']
    const rows = filteredEvents.value.map(e => [
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

// 重新解析所有日志材料
async function handleReparse() {
  const logMaterials = materials.value.filter(m => m.type === 'log')
  if (logMaterials.length === 0) {
    ElMessage.warning('未找到日志材料')
    return
  }
  reparseLoading.value = true
  try {
    await Promise.all(logMaterials.map(m => materialApi.reparse(m.id)))
    await Promise.all([loadTimeline(), loadEvents()])
    ElMessage.success('重新解析完成')
  } finally {
    reparseLoading.value = false
  }
}

// Tab 切换：按需懒加载流量/操作行为数据
function switchTab(tab: TabKey) {
  activeTab.value = tab
  if (tab === 'traffic' && !traffic.value && !trafficLoading.value) {
    loadTraffic()
  } else if (tab === 'behavior' && !operations.value && !opsLoading.value) {
    loadOpsAndBehavior()
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

    <!-- Tab 切换条 -->
    <div class="filter-bar tab-bar">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="filter-chip"
        :class="{ active: activeTab === t.key }"
        @click="switchTab(t.key)"
      >{{ t.label }}</button>
    </div>

    <!-- Tab 1: 会话时间线 -->
    <div v-if="activeTab === 'timeline'" class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">会话时间线</h3>
          <p class="card-desc">按时间分桶聚合的事件流量</p>
        </div>
      </div>
      <div class="timeline">
        <p v-if="timelineLoading" class="text-muted">加载中...</p>
        <p v-else-if="timelineBuckets.length === 0" class="text-muted">暂无时间线数据</p>
        <div class="timeline-item" v-for="(b, idx) in timelineBuckets" :key="idx">
          <p class="timeline-time">{{ b.time }}</p>
          <p class="timeline-title">{{ b.count }} 条事件</p>
          <p class="timeline-desc">{{ bucketDesc(b.by_type) }}</p>
        </div>
      </div>
    </div>

    <!-- Tab 2: 结构化事件 -->
    <div v-else-if="activeTab === 'events'" class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">结构化事件</h3>
          <p class="card-desc">来自 {{ materials.filter(m => m.type === 'log').length }} 个日志材料，共 {{ events.length }} 条事件</p>
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
            <tr v-if="eventsLoading"><td colspan="5" class="text-muted">加载中...</td></tr>
            <tr v-else-if="filteredEvents.length === 0"><td colspan="5" class="text-muted">暂无事件</td></tr>
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

    <!-- Tab 3: 流量分析 -->
    <div v-else-if="activeTab === 'traffic'">
      <p v-if="trafficLoading" class="text-muted">加载中...</p>
      <template v-else-if="traffic">
        <!-- 统计卡片 -->
        <div class="stat-grid">
          <div class="card stat-card">
            <p class="stat-label">总流量数</p>
            <p class="stat-value">{{ traffic.total ?? 0 }}</p>
          </div>
          <div class="card stat-card">
            <p class="stat-label">允许数</p>
            <p class="stat-value stat-allow">{{ traffic.allowed ?? 0 }}</p>
          </div>
          <div class="card stat-card">
            <p class="stat-label">拒绝数</p>
            <p class="stat-value stat-deny">{{ traffic.denied ?? 0 }}</p>
          </div>
        </div>

        <div class="two-col">
          <!-- Top 源 IP -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">Top 源 IP</h3>
                <p class="card-desc">访问源统计</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>IP</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="(it, i) in (traffic.top_source_ips || [])" :key="'s' + i">
                    <td class="cell-mono">{{ it.ip || it.address || it.key || '—' }}</td>
                    <td>{{ it.count || it.value || 0 }}</td>
                  </tr>
                  <tr v-if="(traffic.top_source_ips || []).length === 0"><td colspan="2" class="text-muted">暂无数据</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- Top 目标 IP -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">Top 目标 IP</h3>
                <p class="card-desc">被访问目标统计</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>IP</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="(it, i) in (traffic.top_target_ips || [])" :key="'t' + i">
                    <td class="cell-mono">{{ it.ip || it.address || it.key || '—' }}</td>
                    <td>{{ it.count || it.value || 0 }}</td>
                  </tr>
                  <tr v-if="(traffic.top_target_ips || []).length === 0"><td colspan="2" class="text-muted">暂无数据</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div class="two-col">
          <!-- Top 目标端口 -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">Top 目标端口</h3>
                <p class="card-desc">端口访问统计</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>端口</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="(it, i) in (traffic.top_target_ports || [])" :key="'p' + i">
                    <td class="cell-mono">{{ it.port || it.key || '—' }}</td>
                    <td>{{ it.count || it.value || 0 }}</td>
                  </tr>
                  <tr v-if="(traffic.top_target_ports || []).length === 0"><td colspan="2" class="text-muted">暂无数据</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 协议分布 -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">协议分布</h3>
                <p class="card-desc">按协议分类统计</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>协议</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="(it, i) in (traffic.protocol_distribution || [])" :key="'pr' + i">
                    <td>{{ it.protocol || it.name || it.key || '—' }}</td>
                    <td>{{ it.count || it.value || 0 }}</td>
                  </tr>
                  <tr v-if="(traffic.protocol_distribution || []).length === 0"><td colspan="2" class="text-muted">暂无数据</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </template>
      <p v-else class="text-muted">暂无流量数据</p>
    </div>

    <!-- Tab 4: 操作与行为 -->
    <div v-else-if="activeTab === 'behavior'">
      <p v-if="opsLoading" class="text-muted">加载中...</p>
      <template v-else>
        <!-- 操作统计卡片 -->
        <div class="stat-grid">
          <div class="card stat-card">
            <p class="stat-label">总操作数</p>
            <p class="stat-value">{{ operations?.total ?? 0 }}</p>
          </div>
        </div>

        <div class="two-col">
          <!-- 操作类型分布 -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">操作类型分布</h3>
                <p class="card-desc">按操作类型聚合</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>类型</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="(it, i) in (operations?.type_distribution || operations?.operation_types || [])" :key="'op' + i">
                    <td>{{ it.type || it.name || it.key || '—' }}</td>
                    <td>{{ it.count || it.value || 0 }}</td>
                  </tr>
                  <tr v-if="(operations?.type_distribution || operations?.operation_types || []).length === 0">
                    <td colspan="2" class="text-muted">暂无数据</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- 活跃用户 -->
          <div class="card">
            <div class="card-header">
              <div>
                <h3 class="card-title h4">活跃用户</h3>
                <p class="card-desc">按操作次数排序</p>
              </div>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>用户</th><th>操作次数</th><th>首次时间</th><th>最后时间</th></tr></thead>
                <tbody>
                  <tr v-for="(u, i) in (operations?.active_users || operations?.top_users || [])" :key="'u' + i">
                    <td>{{ u.user || u.name || u.key || '—' }}</td>
                    <td>{{ u.count || u.operations || u.value || 0 }}</td>
                    <td class="cell-mono">{{ u.first_time || u.first_seen || '—' }}</td>
                    <td class="cell-mono">{{ u.last_time || u.last_seen || '—' }}</td>
                  </tr>
                  <tr v-if="(operations?.active_users || operations?.top_users || []).length === 0">
                    <td colspan="4" class="text-muted">暂无数据</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- 用户行为时间线 -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title h4">用户行为时间线</h3>
              <p class="card-desc">按时间梳理用户操作</p>
            </div>
          </div>
          <div class="timeline">
            <p v-if="(behavior?.timeline || []).length === 0" class="text-muted">暂无数据</p>
            <div class="timeline-item" v-for="(b, idx) in (behavior?.timeline || [])" :key="'bt' + idx">
              <p class="timeline-time">{{ b.time || b.timestamp || '—' }}</p>
              <p class="timeline-title">{{ b.user || '未知用户' }}</p>
              <p class="timeline-desc">{{ b.action || b.detail || b.description || '' }}</p>
            </div>
          </div>
        </div>

        <!-- 异常行为告警 -->
        <div class="card">
          <div class="card-header">
            <div>
              <h3 class="card-title h4">异常行为告警</h3>
              <p class="card-desc">检测到的可疑行为</p>
            </div>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>时间</th><th>用户</th><th>行为</th><th>风险</th></tr></thead>
              <tbody>
                <tr v-for="(a, i) in (behavior?.anomalies || behavior?.alerts || [])" :key="'al' + i">
                  <td class="cell-mono">{{ a.time || a.timestamp || '—' }}</td>
                  <td>{{ a.user || '—' }}</td>
                  <td>{{ a.action || a.behavior || a.detail || '' }}</td>
                  <td><span class="badge badge-p3">{{ a.severity || a.risk || 'medium' }}</span></td>
                </tr>
                <tr v-if="(behavior?.anomalies || behavior?.alerts || []).length === 0">
                  <td colspan="4" class="text-muted">暂无异常</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
/* Tab 切换条 */
.tab-bar {
  margin-bottom: 16px;
}

/* 流量/操作统计卡片栅格 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 16px;
  text-align: center;
}

.stat-label {
  margin: 0 0 8px;
  color: var(--text-muted, #94a3b8);
  font-size: 13px;
}

.stat-value {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: var(--text, #0f172a);
  font-variant-numeric: tabular-nums;
}

.stat-allow {
  color: #16a34a;
}

.stat-deny {
  color: #dc2626;
}
</style>
