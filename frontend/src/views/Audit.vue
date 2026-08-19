<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { auditApi } from '@/api'
import { useProjectStore } from '@/stores/project'

const store = useProjectStore()

const loading = {
  summary: ref(false),
  config: ref(false),
  traffic: ref(false),
}

const summary = ref<any>(null)
const configAudit = ref<any>(null)
const trafficAudit = ref<any>(null)

async function loadSummary() {
  loading.summary.value = true
  try {
    summary.value = await auditApi.summary(store.currentProject.id)
  } catch (e: any) {
    summary.value = null
  } finally {
    loading.summary.value = false
  }
}

async function runConfigAudit() {
  loading.config.value = true
  try {
    configAudit.value = await auditApi.configAudit(store.currentProject.id)
    ElMessage.success('配置核查完成')
    await loadSummary()
  } finally {
    loading.config.value = false
  }
}

async function runTrafficAudit() {
  loading.traffic.value = true
  try {
    trafficAudit.value = await auditApi.trafficAudit(store.currentProject.id)
    ElMessage.success('流量审核完成')
    await loadSummary()
  } finally {
    loading.traffic.value = false
  }
}

function sevCount(key: string) {
  return summary.value?.severity_counts?.[key] ?? 0
}

function totalSeverityCounts() {
  const map: Record<string, number> = {}
  if (!summary.value?.severity_counts) return map
  for (const [k, v] of Object.entries(summary.value.severity_counts as Record<string, number>)) {
    const kl = String(k).toLowerCase()
    if (kl === 'critical' || kl === 'high') map.p0 = (map.p0 || 0) + Number(v)
    else if (kl === 'medium') map.p2 = (map.p2 || 0) + Number(v)
    else map.p3 = (map.p3 || 0) + Number(v)
  }
  return map
}

const sevColors: Record<string, string> = {
  p0: '#ef4444',
  p1: '#f97316',
  p2: '#eab308',
  p3: '#22c55e',
}

function formatBytes(n: number) {
  if (n == null) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

onMounted(async () => {
  await loadSummary()
})
</script>

<template>
  <div class="audit-page page">
    <header class="page-header">
      <div>
        <h2>合规审核中心</h2>
        <p class="sub">基于 YAML 规则引擎对当前项目 ({{ store.currentProject.name }}) 执行配置核查与流量审核</p>
      </div>
      <div class="actions">
        <el-button type="primary" :loading="loading.config" @click="runConfigAudit">
          启动配置核查
        </el-button>
        <el-button type="warning" :loading="loading.traffic" @click="runTrafficAudit">
          启动流量审核
        </el-button>
        <el-button plain :loading="loading.summary" @click="loadSummary">
          刷新汇总
        </el-button>
      </div>
    </header>

    <!-- Summary cards -->
    <section class="cards">
      <div class="card stat-card">
        <div class="label">上传材料</div>
        <div class="value">{{ summary?.materials ?? 0 }}</div>
        <div class="hint">当前项目已上传文件总数</div>
      </div>
      <div class="card stat-card">
        <div class="label">配置条目</div>
        <div class="value">{{ summary?.config_items ?? 0 }}</div>
        <div class="hint" v-if="summary?.config_risk_items">
          其中 <b style="color:#ef4444">{{ summary.config_risk_items }}</b> 条已被标记为风险
        </div>
        <div class="hint" v-else>尚未发现风险条目</div>
      </div>
      <div class="card stat-card">
        <div class="label">日志/流量事件</div>
        <div class="value">{{ summary?.log_events ?? 0 }}</div>
        <div class="hint">包含设备日志、会话日志、CSV 流量等</div>
      </div>
      <div class="card stat-card">
        <div class="label">风险发现总数</div>
        <div class="value" style="color:var(--color-danger)">{{ summary?.total_risks ?? 0 }}</div>
        <div class="sev-bars" v-if="totalSeverityCounts()">
          <span v-for="k in (['p0','p2','p3'] as const)" :key="k"
                class="sev-pill" :style="{ borderColor: sevColors[k], color: sevColors[k] }">
            {{ k === 'p0' ? '高危' : k === 'p2' ? '中危' : '低危' }}
            {{ totalSeverityCounts()[k] || 0 }}
          </span>
        </div>
      </div>
    </section>

    <section class="grid-2">
      <!-- Config Audit panel -->
      <div class="card panel">
        <div class="panel-head">
          <div>
            <h3>配置核查结果</h3>
            <div class="sub">扫描所有配置材料，检测策略弱配置、管理面暴露、合规违背等风险项</div>
          </div>
          <el-button size="small" type="primary" :loading="loading.config" @click="runConfigAudit">
            重新核查
          </el-button>
        </div>
        <div class="panel-body" v-if="configAudit">
          <div class="metrics-inline">
            <div class="metric"><span>扫描材料</span><b>{{ configAudit.total_materials_scanned }}</b></div>
            <div class="metric"><span>配置条目</span><b>{{ configAudit.total_config_items }}</b></div>
            <div class="metric"><span>风险条目</span><b style="color:#ef4444">{{ configAudit.risk_items_count }}</b></div>
            <div class="metric"><span>高危发现</span><b style="color:#ef4444">{{ configAudit.high_risk_count }}</b></div>
            <div class="metric"><span>中危发现</span><b style="color:#eab308">{{ configAudit.medium_risk_count }}</b></div>
            <div class="metric"><span>低危发现</span><b style="color:#22c55e">{{ configAudit.low_risk_count }}</b></div>
          </div>

          <div class="split-box">
            <div>
              <h4>风险按模块分布</h4>
              <table class="mini-table" v-if="Object.keys(configAudit.by_section || {}).length">
                <thead>
                  <tr><th>模块</th><th>条目数</th><th>风险</th><th>占比</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(agg, sec) in (configAudit.by_section || {})" :key="sec">
                    <td>{{ sec }}</td>
                    <td>{{ agg.total }}</td>
                    <td style="color:#ef4444">{{ agg.risk }}</td>
                    <td>
                      <div class="bar"><span :style="{
                        width: `${Math.min(100, (agg.total ? (agg.risk / agg.total) * 100 : 0))}%`,
                        background: agg.risk ? '#ef4444' : '#a3a3a3'
                      }"></span></div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div>
              <h4>按设备分布</h4>
              <table class="mini-table" v-if="Object.keys(configAudit.by_device || {}).length">
                <thead>
                  <tr><th>设备</th><th>条目数</th><th>风险</th></tr>
                </thead>
                <tbody>
                  <tr v-for="(agg, dev) in (configAudit.by_device || {})" :key="dev">
                    <td>{{ dev }}</td>
                    <td>{{ agg.total }}</td>
                    <td style="color:#ef4444">{{ agg.risk }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="findings" v-if="(configAudit.findings || []).length">
            <h4>核查发现 ({{ configAudit.findings.length }})</h4>
            <div class="finding-card" v-for="f in configAudit.findings" :key="f.id">
              <div class="finding-head">
                <span class="chip" :class="'chip-' + (f.severity === 'critical' || f.severity === 'high' ? 'p0'
                  : f.severity === 'medium' ? 'p2' : 'p3')">
                  {{ f.severity }}
                </span>
                <span class="finding-code">{{ f.risk_code }}</span>
                <span class="finding-cat">{{ f.category }}</span>
              </div>
              <div class="finding-desc">{{ f.description }}</div>
              <div class="finding-rem" v-if="f.remediation_cmd"><b>处置建议：</b>{{ f.remediation_cmd }}</div>
              <div class="finding-std" v-if="f.standard_ref"><b>标准：</b>{{ f.standard_ref }}</div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无发现，请先「启动配置核查」。</div>
        </div>
        <div v-else class="panel-body empty-panel">
          <div class="empty">
            <div class="empty-icon">🔍</div>
            <div>尚未执行配置核查</div>
            <el-button class="mt" type="primary" :loading="loading.config" @click="runConfigAudit">
              立即核查
            </el-button>
          </div>
        </div>
      </div>

      <!-- Traffic Audit panel -->
      <div class="card panel">
        <div class="panel-head">
          <div>
            <h3>流量审核结果</h3>
            <div class="sub">聚合所有流量/日志事件，检测端口扫描、异常协议、暴力登录、非工作时间登录等</div>
          </div>
          <el-button size="small" type="warning" :loading="loading.traffic" @click="runTrafficAudit">
            重新审核
          </el-button>
        </div>
        <div class="panel-body" v-if="trafficAudit">
          <div class="metrics-inline">
            <div class="metric"><span>扫描材料</span><b>{{ trafficAudit.total_materials_scanned }}</b></div>
            <div class="metric"><span>总事件</span><b>{{ trafficAudit.total_events }}</b></div>
            <div class="metric"><span>流量事件</span><b>{{ trafficAudit.traffic_events }}</b></div>
            <div class="metric"><span>登录事件</span><b>{{ trafficAudit.logon_events }}</b></div>
            <div class="metric"><span>命令事件</span><b>{{ trafficAudit.command_events }}</b></div>
            <div class="metric"><span>流量字节</span><b>{{ formatBytes(trafficAudit.total_bytes) }}</b></div>
          </div>

          <div class="split-box">
            <div>
              <h4>Top 源 IP (访问最多)</h4>
              <table class="mini-table" v-if="(trafficAudit.top_sources || []).length">
                <thead><tr><th>源 IP</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="s in trafficAudit.top_sources" :key="s.ip">
                    <td class="mono">{{ s.ip }}</td>
                    <td>{{ s.count }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="empty-hint">暂无可统计源 IP</div>
            </div>
            <div>
              <h4>Top 目标 IP (被访问最多)</h4>
              <table class="mini-table" v-if="(trafficAudit.top_targets || []).length">
                <thead><tr><th>目标 IP</th><th>次数</th></tr></thead>
                <tbody>
                  <tr v-for="t in trafficAudit.top_targets" :key="t.ip">
                    <td class="mono">{{ t.ip }}</td>
                    <td>{{ t.count }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-else class="empty-hint">暂无可统计目标 IP</div>
            </div>
          </div>

          <div class="protocol-wrap" v-if="(trafficAudit.top_protocols || []).length">
            <h4>协议分布</h4>
            <div class="protocol-list">
              <div class="proto-pill" v-for="p in trafficAudit.top_protocols" :key="p.protocol">
                <b>{{ p.protocol }}</b>
                <span>{{ p.count }}</span>
              </div>
            </div>
          </div>

          <div class="findings" v-if="(trafficAudit.findings || []).length">
            <h4>审核发现 ({{ trafficAudit.findings.length }})</h4>
            <div class="finding-card" v-for="f in trafficAudit.findings" :key="f.id">
              <div class="finding-head">
                <span class="chip" :class="'chip-' + (f.severity === 'critical' || f.severity === 'high' ? 'p0'
                  : f.severity === 'medium' ? 'p2' : 'p3')">
                  {{ f.severity }}
                </span>
                <span class="finding-code">{{ f.risk_code }}</span>
                <span class="finding-cat">{{ f.category }}</span>
              </div>
              <div class="finding-desc">{{ f.description }}</div>
              <div class="finding-rem" v-if="f.remediation_cmd"><b>处置建议：</b>{{ f.remediation_cmd }}</div>
              <div class="finding-std" v-if="f.standard_ref"><b>标准：</b>{{ f.standard_ref }}</div>
            </div>
          </div>
          <div v-else class="empty-hint">暂无发现，请先「启动流量审核」。</div>
        </div>
        <div v-else class="panel-body empty-panel">
          <div class="empty">
            <div class="empty-icon">🛰️</div>
            <div>尚未执行流量审核</div>
            <el-button class="mt" type="warning" :loading="loading.traffic" @click="runTrafficAudit">
              立即审核
            </el-button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.audit-page { width: 100%; }
.page-header {
  display: flex; justify-content: space-between; align-items: flex-end;
  margin-bottom: 18px; gap: 16px; flex-wrap: wrap;
}
.page-header h2 { margin: 0; font-size: 22px; font-weight: 600; }
.page-header .sub { margin: 4px 0 0; color: var(--color-text-soft); font-size: 13px; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; }

.cards {
  display: grid; gap: 14px; margin-bottom: 18px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}
.stat-card { padding: 18px 20px; }
.stat-card .label { color: var(--color-text-soft); font-size: 13px; }
.stat-card .value {
  font-size: 30px; font-weight: 700; margin-top: 6px; line-height: 1.1; color: var(--color-text);
}
.stat-card .hint { margin-top: 6px; color: var(--color-text-soft); font-size: 12px; }
.sev-bars { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.sev-pill { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid; font-weight: 600; }

.grid-2 {
  display: grid; gap: 16px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}
@media (max-width: 1100px) {
  .grid-2 { grid-template-columns: 1fr; }
}

.panel-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 18px; border-bottom: 1px solid var(--color-border);
}
.panel-head h3 { margin: 0; font-size: 16px; font-weight: 600; }
.panel-head .sub { margin-top: 4px; font-size: 12px; color: var(--color-text-soft); }

.panel-body { padding: 16px 18px 18px; }

.metrics-inline {
  display: grid; gap: 10px 14px; margin-bottom: 16px;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
}
.metric {
  display: flex; flex-direction: column;
  padding: 10px 12px; border: 1px solid var(--color-border-soft);
  border-radius: 10px; background: var(--color-bg-soft);
}
.metric span { font-size: 12px; color: var(--color-text-soft); }
.metric b { font-size: 18px; margin-top: 2px; }

.split-box {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 16px;
}
@media (max-width: 760px) { .split-box { grid-template-columns: 1fr; } }

.split-box h4 { font-size: 13px; margin: 0 0 6px; color: var(--color-text-soft); font-weight: 600; letter-spacing: .3px; }

.mini-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.mini-table th, .mini-table td {
  padding: 6px 8px; border-bottom: 1px solid var(--color-border-soft); text-align: left;
}
.mini-table th { color: var(--color-text-soft); font-weight: 500; font-size: 12px; }
.mini-table td.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace; }

.bar { position: relative; width: 100%; height: 6px; background: #e5e7eb; border-radius: 4px; overflow: hidden; }
.bar span { position: absolute; inset: 0 auto 0 0; }

.findings { display: flex; flex-direction: column; gap: 10px; }
.findings h4 { font-size: 14px; margin: 0 0 6px; }

.finding-card {
  border: 1px solid var(--color-border-soft);
  border-radius: 12px; padding: 12px 14px; background: var(--color-bg-soft);
}
.finding-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chip { font-size: 11px; padding: 2px 8px; border-radius: 999px; font-weight: 700; letter-spacing: .5px; }
.chip-p0 { background: #fee2e2; color: #b91c1c; }
.chip-p1 { background: #ffedd5; color: #c2410c; }
.chip-p2 { background: #fef9c3; color: #a16207; }
.chip-p3 { background: #dcfce7; color: #166534; }
.finding-code { font-family: ui-monospace, monospace; font-size: 12px; color: var(--color-text-soft); }
.finding-cat {
  margin-left: auto; font-size: 11px; padding: 2px 8px; border-radius: 999px;
  background: #eef2ff; color: #4338ca;
}
.finding-desc { margin-top: 8px; line-height: 1.55; font-size: 13.5px; }
.finding-rem, .finding-std { margin-top: 6px; font-size: 12.5px; color: var(--color-text-soft); }

.protocol-wrap { margin-bottom: 16px; }
.protocol-wrap h4 { font-size: 13px; color: var(--color-text-soft); font-weight: 600; margin: 0 0 6px; }
.protocol-list { display: flex; gap: 8px; flex-wrap: wrap; }
.proto-pill {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-width: 68px; padding: 8px 10px;
  background: var(--color-bg-soft); border: 1px solid var(--color-border-soft);
  border-radius: 10px;
}
.proto-pill b { font-size: 14px; }
.proto-pill span { font-size: 11px; color: var(--color-text-soft); margin-top: 2px; }

.empty-panel { min-height: 260px; display: flex; align-items: center; justify-content: center; }
.empty { text-align: center; color: var(--color-text-soft); }
.empty-icon { font-size: 32px; margin-bottom: 6px; }
.mt { margin-top: 10px; }
.empty-hint { padding: 18px 4px; color: var(--color-text-soft); font-size: 13px; }
</style>
