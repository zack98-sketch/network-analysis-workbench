<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { configApi, materialApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { ConfigItem, Material } from '@/types'

const store = useProjectStore()
const tabs = ['security-policy', 'interface', 'aaa', 'ssh', 'snmp']
const activeTab = ref('security-policy')
const configItems = ref<ConfigItem[]>([])
const materials = ref<Material[]>([])
const selectedVersion = ref('v2')
const compareWithVersion = ref('')
const diffResult = ref<any>(null)
const loading = ref(false)

const sections = computed(() => {
  const all = Array.from(new Set(configItems.value.map(c => c.section)))
  return all
})

const visibleSections = computed(() => {
  return sections.value.filter(s => s === activeTab.value || activeTab.value === 'all')
})

function linesOf(section: string) {
  return configItems.value.filter(c => c.section === section)
}

async function loadMaterials() {
  try {
    materials.value = await materialApi.list(store.currentProject.id)
  } catch {}
}

async function loadConfigTree() {
  loading.value = true
  try {
    const configMaterial = materials.value.find(m => m.type === 'config')
    if (configMaterial) {
      configItems.value = await configApi.tree(configMaterial.id)
    }
  } finally {
    loading.value = false
  }
}

async function handleDiff() {
  if (!compareWithVersion.value) {
    ElMessage.warning('请选择对比版本')
    return
  }
  const configMaterial = materials.value.find(m => m.type === 'config')
  if (configMaterial) {
    diffResult.value = await configApi.diff(configMaterial.id, compareWithVersion.value)
  }
}

function exportJSON() {
  try {
    const data = JSON.stringify(configItems.value, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `config-tree-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch {
    ElMessage.warning('导出失败')
  }
}

onMounted(async () => {
  await store.init()
  await loadMaterials()
  await loadConfigTree()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">配置解析与智能注释</div>
        <h1 class="h1">配置树与注释</h1>
        <p class="text-muted">自动识别厂商与设备类型，基于知识库为每条配置项生成注释。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="handleDiff">版本对比</button>
        <button class="btn btn-primary btn-sm" @click="exportJSON">导出配置树</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
            <h3 class="card-title h4">Demo-FW (VRP)</h3>
            <span class="badge badge-info">华为 VRP</span>
            <span class="badge badge-p0">{{ configItems.filter(c => c.risk).length }} 项风险</span>
          </div>
          <p class="card-desc">软件版本 V600R025C10SPC100 · {{ configItems.length }} 行</p>
        </div>
        <div style="display:flex;gap:8px">
          <select class="filter-chip" style="padding:8px 12px" v-model="selectedVersion">
            <option value="v2">版本 v2 (最新)</option>
            <option value="v1">版本 v1 (2026-08-15)</option>
          </select>
          <select class="filter-chip" style="padding:8px 12px" v-model="compareWithVersion">
            <option value="">对比版本...</option>
            <option value="v1">版本 v1 (2026-08-15)</option>
          </select>
        </div>
      </div>

      <div v-if="diffResult" style="padding:12px 16px;background:var(--bg-200);border-radius:var(--radius-md);margin-bottom:16px">
        <span style="font-size:13px;font-weight:600">版本差异：</span>
        <span class="badge" style="background:var(--success-50);color:var(--success-700);margin-left:8px">+{{ diffResult.additions }} 新增</span>
        <span class="badge" style="background:var(--error-50);color:var(--error-700);margin-left:8px">-{{ diffResult.deletions }} 删除</span>
      </div>

      <div class="tabs">
        <button
          v-for="t in tabs"
          :key="t"
          class="tab"
          :class="{ active: activeTab === t }"
          @click="activeTab = t"
        >{{ t }}</button>
      </div>

      <div class="config-tree" style="margin-top:20px">
        <div v-for="sec in visibleSections" :key="sec" class="tree-section">
          <div class="tree-section-title">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="6 9 12 15 18 9"/></svg>
            {{ sec }}
          </div>
          <div v-for="line in linesOf(sec)" :key="line.id" class="tree-line" :class="{ risk: line.risk }">
            <span class="tree-lineno">{{ line.lineNo }}</span>
            <span class="tree-key">{{ line.key }}</span>
            <span class="tree-value">{{ line.value }}</span>
            <span class="tree-annotation">{{ line.annotation }}</span>
          </div>
        </div>
        <div v-if="visibleSections.length === 0" style="text-align:center;padding:40px;color:var(--text-500)">
          该标签页暂无配置数据
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
