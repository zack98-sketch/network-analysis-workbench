<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, riskApi, materialApi, logApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { Material } from '@/types'

const router = useRouter()
const store = useProjectStore()

const summary = ref<any>(null)
const timelineItems = ref<any[]>([])
const risks = ref<any[]>([])
const materials = ref<Material[]>([])
const loading = ref(false)

const p0Count = computed(() => risks.value.filter(r => r.severity === 'p0').length)
const p1Count = computed(() => risks.value.filter(r => r.severity === 'p1').length)
const p2Count = computed(() => risks.value.filter(r => r.severity === 'p2').length)
const p3Count = computed(() => risks.value.filter(r => r.severity === 'p3').length)

const riskTotal = computed(() => p0Count.value + p1Count.value + p2Count.value + p3Count.value || 1)

// 统计卡片：直接取后端返回值，无硬编码 fallback（0 即 0）
const materialsCount = computed(() => Number(summary.value?.materials_count ?? 0) || 0)
const risksCount = computed(() => Number(summary.value?.risks_count ?? 0) || 0)
const nodesCount = computed(() => Number(summary.value?.nodes_count ?? 0) || 0)
const eventsCount = computed(() => Number(summary.value?.log_events_count ?? 0) || 0)

// 事件数显示：< 1000 显示原值，否则按 k 显示
const eventsDisplay = computed(() => {
  const n = eventsCount.value
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n)
})

// 材料按类型分组的计数（用于统计卡片副文本）
const logCount = computed(() => materials.value.filter(m => m.type === 'log').length)
const configCount = computed(() => materials.value.filter(m => m.type === 'config').length)
const docCount = computed(() => materials.value.filter(m => m.type === 'manual' || m.type === 'training').length)

// 时间线事件类型 → 中文标签
const eventTypeLabel: Record<string, string> = {
  auth: '认证',
  command: '命令',
  connect: '连接',
  change: '变更',
  disconnect: '断开',
  other: '其他'
}

// 将 timeline 接口返回的 bucket 数据转换为时间线条目
function buildTimeline(tl: any): any[] {
  const buckets: any[] = tl?.buckets || []
  // 按时间倒序展示最近的动态
  return [...buckets].reverse().map((b: any) => {
    const byType: Record<string, number> = b.by_type || {}
    const parts = Object.keys(byType).map(k => `${eventTypeLabel[k] || k} ${byType[k]}`)
    return {
      time: b.time,
      count: b.count,
      title: `${b.count} 条日志事件`,
      desc: parts.length ? parts.join(' · ') : '无类型分布'
    }
  })
}

async function loadData() {
  const pid = store.currentProject.id
  if (!pid) return
  loading.value = true
  try {
    const [s, r, mats] = await Promise.all([
      projectApi.summary(pid),
      riskApi.list(pid),
      materialApi.list(pid)
    ])
    summary.value = s
    risks.value = r
    materials.value = mats
  } catch {
    ElMessage.warning('加载数据失败')
  } finally {
    loading.value = false
  }
  // 时间线单独加载，失败时展示空状态
  try {
    const tl = await logApi.timeline(pid)
    timelineItems.value = buildTimeline(tl)
  } catch {
    timelineItems.value = []
  }
}

function goTo(target: string) {
  router.push({ name: target })
}

onMounted(async () => {
  await store.init()
  loadData()
})
</script>

<template>
  <div>
    <div class="page-head page-head-center">
      <div class="page-head-left">
        <div class="eyebrow">工作台总览</div>
        <h1 class="h1">网络环境分析工作台</h1>
        <p class="text-muted">上传任意日志、配置文件或产品手册，自动完成解析、关联、风险检测与拓扑生成。</p>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">已上传材料</div>
        <div class="stat-value">{{ materialsCount }}</div>
        <div class="stat-meta">{{ logCount }} 份日志 · {{ configCount }} 份配置 · {{ docCount }} 份文档</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">解析事件</div>
        <div class="stat-value">{{ eventsDisplay }}</div>
        <div class="stat-meta">来自 {{ logCount }} 份日志材料</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">风险发现</div>
        <div class="stat-value">{{ risksCount }}</div>
        <div class="stat-meta down">{{ p0Count }} 项高危 · {{ p1Count }} 项中危</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">拓扑节点</div>
        <div class="stat-value">{{ nodesCount }}</div>
        <div class="stat-meta">防火墙 · 交换机 · 主机</div>
      </div>
    </div>

    <!-- 快捷操作 -->
    <div class="card quick-actions">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">快捷操作</h3>
          <p class="card-desc">常用功能一键直达</p>
        </div>
      </div>
      <div class="quick-actions-grid">
        <button class="btn btn-secondary" @click="goTo('upload')">上传材料</button>
        <button class="btn btn-secondary" @click="goTo('logs')">查看日志</button>
        <button class="btn btn-secondary" @click="goTo('topology')">查看拓扑</button>
        <button class="btn btn-secondary" @click="goTo('reports')">生成报告</button>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">最近分析动态</h3>
            <p class="card-desc">按时间排序的材料解析与风险检测记录</p>
          </div>
          <button class="btn btn-ghost btn-sm" @click="goTo('logs')">查看全部</button>
        </div>
        <div class="timeline" v-if="timelineItems.length">
          <div class="timeline-item" v-for="(item, idx) in timelineItems" :key="idx">
            <p class="timeline-time">{{ item.time }}</p>
            <p class="timeline-title">{{ item.title }}</p>
            <p class="timeline-desc">{{ item.desc }}</p>
          </div>
        </div>
        <div v-else class="timeline-empty">暂无分析动态</div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">风险概览</h3>
            <p class="card-desc">按等级分布的安全风险 · 点击条目跳转到对应分析位置</p>
          </div>
          <span class="badge badge-p0">{{ p0Count }} 高危</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px">
          <div class="risk-row" data-goto="risk" @click="goTo('risk')" tabindex="0" role="button">
            <div style="width:80px;font-size:12px;font-weight:600;color:var(--error-700)">高危</div>
            <div class="progress-track" style="flex:1"><div class="progress-fill" :style="{ width: Math.round(p0Count / riskTotal * 100) + '%', background: 'var(--error-500)' }"></div></div>
            <div style="width:32px;text-align:right;font-weight:600">{{ p0Count }}</div>
          </div>
          <div class="risk-row" data-goto="risk" @click="goTo('risk')" tabindex="0" role="button">
            <div style="width:80px;font-size:12px;font-weight:600;color:#8a5a1a">中危</div>
            <div class="progress-track" style="flex:1"><div class="progress-fill" :style="{ width: Math.round(p1Count / riskTotal * 100) + '%', background: 'var(--warning-500)' }"></div></div>
            <div style="width:32px;text-align:right;font-weight:600">{{ p1Count }}</div>
          </div>
          <div class="risk-row" data-goto="risk" @click="goTo('risk')" tabindex="0" role="button">
            <div style="width:80px;font-size:12px;font-weight:600;color:var(--success-700)">低危</div>
            <div class="progress-track" style="flex:1"><div class="progress-fill" :style="{ width: Math.round(p2Count / riskTotal * 100) + '%', background: 'var(--success-500)' }"></div></div>
            <div style="width:32px;text-align:right;font-weight:600">{{ p2Count }}</div>
          </div>
          <div class="risk-row" data-goto="risk" @click="goTo('risk')" tabindex="0" role="button">
            <div style="width:80px;font-size:12px;font-weight:600;color:var(--text-600)">信息</div>
            <div class="progress-track" style="flex:1"><div class="progress-fill" :style="{ width: Math.round(p3Count / riskTotal * 100) + '%', background: 'var(--text-400)' }"></div></div>
            <div style="width:32px;text-align:right;font-weight:600">{{ p3Count }}</div>
          </div>
        </div>
        <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
          <h4 class="h4" style="margin-bottom:10px">待处理重点 · 悬停查看整改建议</h4>
          <ul style="margin:0;padding-left:18px;color:var(--text-700);font-size:13px;line-height:1.8">
            <li class="risk-issue" data-goto="config" @click="goTo('config')" tabindex="0" role="button">
              安全策略 <code class="text-mono">demo-rule</code> 未限定源区域与地址
              <div class="remediation-popover">
                <h5>整改建议</h5>
                <pre>security-policy
 rule name demo-rule
  source-zone trust
  source-address 10.0.0.0/24</pre>
                <p>依据：等保 2.0 三级 8.1.3.2 访问控制</p>
              </div>
            </li>
            <li class="risk-issue" data-goto="config" @click="goTo('config')" tabindex="0" role="button">
              SSH 仍允许 <code class="text-mono">diffie-hellman-group1</code> 算法
              <div class="remediation-popover">
                <h5>整改建议</h5>
                <pre>undo ssh server compatible-ssh1x enable
ssh server key-exchange dh-group14-sha256</pre>
                <p>依据：CIS Benchmark 7.4 / 厂商加固指南</p>
              </div>
            </li>
            <li class="risk-issue" data-goto="config" @click="goTo('config')" tabindex="0" role="button">
              Telnet 服务未禁用
              <div class="remediation-popover">
                <h5>整改建议</h5>
                <pre>undo telnet server enable
undo telnet ipv6 server enable</pre>
                <p>依据：等保 2.0 三级 8.1.3.2 访问控制</p>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quick-actions {
  margin-top: 20px;
}
.quick-actions-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.timeline-empty {
  text-align: center;
  padding: 32px 0;
  color: var(--text-500);
  font-size: 13px;
}
</style>
