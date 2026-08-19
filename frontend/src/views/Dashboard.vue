<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, riskApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import { materials as mockMaterials } from '@/mock/data'

const router = useRouter()
const store = useProjectStore()

const summary = ref<any>(null)
const timelineItems = ref<any[]>([])
const risks = ref<any[]>([])
const loading = ref(false)

const p0Count = computed(() => risks.value.filter(r => r.severity === 'p0').length)
const p1Count = computed(() => risks.value.filter(r => r.severity === 'p1').length)
const p2Count = computed(() => risks.value.filter(r => r.severity === 'p2').length)
const p3Count = computed(() => risks.value.filter(r => r.severity === 'p3').length)

const riskTotal = computed(() => p0Count.value + p1Count.value + p2Count.value + p3Count.value || 1)

async function loadData() {
  loading.value = true
  try {
    const pid = store.currentProject.id
    const [s, r, mats] = await Promise.all([
      projectApi.summary(pid),
      riskApi.list(pid),
      materialApi.list(pid)
    ])
    summary.value = s
    risks.value = r
    timelineItems.value = [
      { time: '今天 14:32', title: `${mats[0]?.name || '文件'} 解析完成`, desc: `识别 ${mats[0]?.rows || 10000} 条记录，关联到安全策略` },
      { time: '今天 11:05', title: '配置文件上传', desc: '新增 1 项中危风险' },
      { time: '昨天 18:47', title: '产品手册索引完成', desc: '已关联 16 条配置注释' },
      { time: '昨天 09:12', title: '会话日志关联分析', desc: '识别 6 个会话，2 次非工作时间登录' }
    ]
  } catch (e: any) {
    ElMessage.warning('加载数据失败，使用本地数据')
  } finally {
    loading.value = false
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
        <div class="stat-value">{{ summary?.materialsCount || 14 }}</div>
        <div class="stat-meta">4 份日志 · 2 份配置 · 8 份文档</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">解析事件</div>
        <div class="stat-value">{{ ((summary?.eventsCount || 10200) / 1000).toFixed(1) }}k</div>
        <div class="stat-meta up">+2,341 来自 CSV 流量</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">风险发现</div>
        <div class="stat-value">{{ summary?.risksCount || 7 }}</div>
        <div class="stat-meta down">{{ p0Count }} 项高危 · {{ p1Count }} 项中危</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">拓扑节点</div>
        <div class="stat-value">{{ summary?.nodesCount || 5 }}</div>
        <div class="stat-meta">防火墙 · 交换机 · 主机</div>
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
        <div class="timeline">
          <div class="timeline-item" v-for="(item, idx) in timelineItems" :key="idx">
            <p class="timeline-time">{{ item.time }}</p>
            <p class="timeline-title">{{ item.title }}</p>
            <p class="timeline-desc">{{ item.desc }}</p>
          </div>
        </div>
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
              安全策略 <code class="text-mono">hufang</code> 未限定源区域与地址
              <div class="remediation-popover">
                <h5>整改建议</h5>
                <pre>security-policy
 rule name hufang
  source-zone trust
  source-address 10.64.0.0/16</pre>
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
</style>
