<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { ConfigItem, Material } from '@/types'

const store = useProjectStore()
const configItems = ref<ConfigItem[]>([])
const materials = ref<Material[]>([])
const selectedMaterialId = ref<string | number>('')
const compareMaterialId = ref<string | number>('')
const diffResult = ref<any>(null)
const loading = ref(false)
const diffLoading = ref(false)

// 后端 section_type 用下划线（security_policy/aaa/ssh/snmp/interface）
// 前端展示中文名映射
const SECTION_LABELS: Record<string, string> = {
  security_policy: '安全策略',
  security_zone: '安全区域',
  interface: '接口配置',
  acl: 'ACL规则',
  aaa: 'AAA认证',
  ssh: 'SSH配置',
  snmp: 'SNMP配置',
  service: '服务管理',
  routing: '路由配置',
  nat: 'NAT策略',
  vpn: 'VPN实例',
  ipsec: 'IPSec',
  qos: 'QoS策略',
  l2: '二层配置',
  log: '日志配置',
  system: '系统配置',
  management_line: '管理线',
  root: '其他配置',
}

// 从配置项中动态提取所有 section_type（去重），用于动态生成 tab
const availableSections = computed(() => {
  const types = Array.from(new Set(configItems.value.map(c => c.section_type || c.section || '')))
  return types.filter(Boolean)
})

// 选中的 tab：默认第一个可用 section
const activeTab = ref('')

watch(availableSections, (secs) => {
  if (secs.length && !secs.includes(activeTab.value)) {
    activeTab.value = secs[0]
  }
})

const visibleItems = computed(() => {
  if (!activeTab.value) return []
  return configItems.value.filter(c => (c.section_type || c.section) === activeTab.value)
})

// 当前设备信息
const currentDevice = computed(() => {
  const m = materials.value.find(x => String(x.id) === String(selectedMaterialId.value))
  return m
})

const riskCount = computed(() => configItems.value.filter(c => c.risk || c.is_risk).length)

// 所有 config 类型材料（用于设备选择和对比）
const configMaterials = computed(() => materials.value.filter(m => m.type === 'config'))

async function loadMaterials() {
  try {
    materials.value = await materialApi.list(store.currentProject.id)
    // 默认选第一个 config 材料
    const cfgs = configMaterials.value
    if (cfgs.length && !selectedMaterialId.value) {
      selectedMaterialId.value = cfgs[0].id
      await loadConfigTree()
    }
  } catch {}
}

async function loadConfigTree() {
  if (!selectedMaterialId.value) {
    configItems.value = []
    return
  }
  loading.value = true
  try {
    configItems.value = await configApi.tree(selectedMaterialId.value)
  } catch {
    configItems.value = []
  } finally {
    loading.value = false
  }
}

async function handleDiff() {
  if (!selectedMaterialId.value || !compareMaterialId.value) {
    ElMessage.warning('请选择当前设备和对比设备')
    return
  }
  if (String(selectedMaterialId.value) === String(compareMaterialId.value)) {
    ElMessage.warning('不能与自身对比')
    return
  }
  diffLoading.value = true
  try {
    diffResult.value = await configApi.diff(selectedMaterialId.value, String(compareMaterialId.value))
  } catch {
    diffResult.value = null
  } finally {
    diffLoading.value = false
  }
}

function exportJSON() {
  try {
    const data = JSON.stringify(configItems.value, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `config-tree-${currentDevice.value?.name || 'device'}-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.warning('导出失败')
  }
}

watch(selectedMaterialId, () => {
  diffResult.value = null
  loadConfigTree()
})

onMounted(async () => {
  await store.init()
  await loadMaterials()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">配置解析与智能注释</div>
        <h1 class="h1">配置树与注释</h1>
        <p class="text-muted">选择设备配置文件，自动识别厂商与设备类型，基于知识库为每条配置项生成注释。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="handleDiff" :disabled="diffLoading">版本对比</button>
        <button class="btn btn-primary btn-sm" @click="exportJSON" :disabled="!configItems.length">导出配置树</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
            <h3 class="card-title h4">{{ currentDevice?.name || '请选择设备' }}</h3>
            <span class="badge badge-info">{{ currentDevice?.deviceName || currentDevice?.name || 'VRP' }}</span>
            <span class="badge badge-p0" v-if="riskCount">{{ riskCount }} 项风险</span>
            <span class="badge badge-p3" v-else>无风险</span>
          </div>
          <p class="card-desc">{{ configItems.length }} 行配置 · {{ availableSections.length }} 个模块</p>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <select class="filter-chip" style="padding:8px 12px" v-model="selectedMaterialId">
            <option value="">选择设备...</option>
            <option v-for="m in configMaterials" :key="m.id" :value="m.id">
              {{ m.name }}{{ m.deviceName ? ` (${m.deviceName})` : '' }}
            </option>
          </select>
          <select class="filter-chip" style="padding:8px 12px" v-model="compareMaterialId">
            <option value="">对比设备...</option>
            <option v-for="m in configMaterials" :key="m.id" :value="m.id">
              {{ m.name }}{{ m.deviceName ? ` (${m.deviceName})` : '' }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="diffResult" style="padding:12px 16px;background:var(--bg-200,var(--bg-100));border-radius:var(--radius-md);margin-bottom:16px">
        <span style="font-size:13px;font-weight:600">版本差异：</span>
        <span class="badge" style="background:var(--success-50,#dcfce7);color:var(--success-700,#166534);margin-left:8px">+{{ diffResult.added || 0 }} 新增</span>
        <span class="badge" style="background:var(--error-50,#fee2e2);color:var(--error-700,#b91c1c);margin-left:8px">-{{ diffResult.removed || 0 }} 删除</span>
        <span class="badge" style="background:var(--warning-50,#fef9c3);color:var(--warning-700,#a16207);margin-left:8px">~{{ diffResult.changed || 0 }} 修改</span>
        <div v-if="(diffResult.diff || []).length" style="margin-top:10px;max-height:300px;overflow:auto;font-family:monospace;font-size:12px">
          <div v-for="(d, i) in (diffResult.diff || []).slice(0, 100)" :key="i"
               :style="{ color: d.op === 'added' ? '#16a34a' : d.op === 'removed' ? '#dc2626' : '#d97706' }">
            <span v-if="d.op === 'added'">+ </span>
            <span v-else-if="d.op === 'removed'">- </span>
            <span v-else>~ </span>
            {{ d.text_a || d.text_b || '' }}
          </div>
        </div>
      </div>

      <div class="tabs" v-if="availableSections.length">
        <button
          v-for="sec in availableSections"
          :key="sec"
          class="tab"
          :class="{ active: activeTab === sec }"
          @click="activeTab = sec"
        >{{ SECTION_LABELS[sec] || sec }}</button>
      </div>

      <div class="config-tree" style="margin-top:20px" v-loading="loading">
        <div v-if="visibleItems.length" class="tree-section">
          <div class="tree-section-title">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
            {{ SECTION_LABELS[activeTab] || activeTab }}
          </div>
          <div v-for="line in visibleItems" :key="line.id" class="tree-line" :class="{ risk: line.risk || line.is_risk }">
            <span class="tree-lineno">{{ line.lineNo }}</span>
            <span class="tree-key">{{ line.key }}</span>
            <span class="tree-value">{{ line.value }}</span>
            <span class="tree-annotation" v-if="line.annotation">{{ line.annotation }}</span>
          </div>
        </div>
        <div v-else-if="!loading" style="text-align:center;padding:40px;color:var(--text-500,#94a3b8)">
          {{ selectedMaterialId ? '该模块暂无配置数据' : '请选择设备配置文件' }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-tree { min-height: 200px; }
.tree-section { margin-bottom: 16px; }
.tree-section-title {
  font-weight: 600; font-size: 14px; margin-bottom: 8px;
  display: flex; align-items: center; gap: 6px;
  color: var(--text, #0f172a);
}
.tree-line {
  display: grid; grid-template-columns: 50px 180px 1fr 1fr;
  gap: 12px; padding: 6px 8px; font-size: 13px;
  border-bottom: 1px solid var(--border-soft, #f1f5f9);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.tree-line.risk { background: #fef2f2; }
.tree-lineno { color: var(--text-muted, #94a3b8); }
.tree-key { color: #2563eb; font-weight: 500; }
.tree-value { color: var(--text, #0f172a); }
.tree-annotation { color: var(--text-muted, #64748b); font-family: inherit; }
.filter-chip {
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px; background: white; color: var(--text, #0f172a);
  cursor: pointer; outline: none;
}
.filter-chip:focus { border-color: var(--primary, #2563eb); }
</style>
