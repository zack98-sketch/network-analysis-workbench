<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import TopologyEditor from '@/components/topology/TopologyEditor.vue'
import { topologyApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { TopoNode } from '@/types'

const store = useProjectStore()
const editorRef = ref<InstanceType<typeof TopologyEditor> | null>(null)
const nodes = ref<TopoNode[]>([])

const shapeIcons: Record<string, string> = {
  host: '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
  firewall: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  switch: '<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>'
}

async function loadNodes() {
  try {
    const data = await topologyApi.get(store.currentProject.id)
    nodes.value = data.nodes
  } catch {}
}

function handleRefresh() {
  editorRef.value?.loadTopology()
  loadNodes()
}

function handleExport() {
  editorRef.value?.exportImage()
}

onMounted(async () => {
  await store.init()
  loadNodes()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">动态拓扑生成</div>
        <h1 class="h1">网络拓扑</h1>
        <p class="text-muted">从配置与流量中自动提取节点与连接关系，支持手动拖拽、增删节点与连线。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="handleExport">导出图片</button>
        <button class="btn btn-primary btn-sm" @click="handleRefresh">刷新拓扑</button>
      </div>
    </div>

    <TopologyEditor :projectId="store.currentProject.id" ref="editorRef" />

    <div class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">节点说明</h3>
          <p class="card-desc">拓扑中的设备与连接来源</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>节点</th><th>类型</th><th>IP / 接口</th><th>来源</th></tr>
          </thead>
          <tbody>
            <tr v-for="node in nodes" :key="node.id">
              <td>{{ node.label }}</td>
              <td>
                <span v-if="node.type === 'firewall'" class="badge badge-info">防火墙</span>
                <span v-else-if="node.type === 'switch'" class="badge badge-p2">交换机</span>
                <span v-else class="badge badge-p3">主机</span>
              </td>
              <td class="cell-mono">{{ node.ip }}<span v-if="node.iface"> / {{ node.iface }}</span></td>
              <td>{{ node.source }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
