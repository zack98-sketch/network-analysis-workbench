<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage, ElDialog, ElMessageBox, ElForm, ElFormItem, ElInput, ElSelect, ElOption } from 'element-plus'
import { topologyApi } from '@/api'
import type { TopoNode, TopoEdge } from '@/types'

const props = defineProps<{
  projectId: string | number
}>()

const tools = [
  { key: 'select', label: '选择', icon: '<path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/>' },
  { key: 'addNode', label: '添加节点', icon: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/>' },
  { key: 'addEdge', label: '添加连线', icon: '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><line x1="8.29" y1="15.71" x2="15.71" y2="8.29"/>' },
  { key: 'delete', label: '删除', icon: '<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>' }
]
const activeTool = ref('select')
const nodes = ref<TopoNode[]>([])
const edges = ref<TopoEdge[]>([])
const canvasRef = ref<HTMLElement | null>(null)
const edgeStartNodeId = ref<string | number | null>(null)
const draggingNodeId = ref<string | number | null>(null)
const dragOffset = ref({ x: 0, y: 0 })
const canvasSize = ref({ width: 0, height: 0 })
const updateTimer = ref<any>(null)
const addNodeDialogVisible = ref(false)
const newNodeForm = ref({ label: '', type: 'host' as 'firewall' | 'switch' | 'host' })
const newNodePosition = ref({ left: '50%', top: '50%' })

// ============ 缩放/平移交互 ============
const scale = ref(1)
const panOffset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0, ox: 0, oy: 0 })
const MIN_SCALE = 0.3
const MAX_SCALE = 3

// ============ 全屏 ============
const containerRef = ref<HTMLElement | null>(null)
const isFullscreen = ref(false)

async function toggleFullscreen() {
  if (!containerRef.value) return
  try {
    if (!document.fullscreenElement) {
      await containerRef.value.requestFullscreen()
    } else {
      await document.exitFullscreen()
    }
  } catch (e) {
    // 部分浏览器需要 webkit 前缀
    const el = containerRef.value as any
    try {
      if (!document.fullscreenElement) {
        (el.webkitRequestFullscreen || el.requestFullscreen).call(el)
      } else {
        (document as any).webkitExitFullscreen?.()
      }
    } catch {}
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  // 全屏切换后需要重新计算画布尺寸
  nextTick(() => updateCanvasSize())
}

// 边类型中文标签 + 颜色
const edgeTypeMap: Record<string, { label: string; color: string }> = {
  physical: { label: '物理连接', color: '#94a3b8' },
  route: { label: '路由', color: '#3b82f6' },
  vrf: { label: 'VRF', color: '#8b5cf6' },
  ssh_session: { label: 'SSH管理', color: '#f59e0b' },
  traffic_flow: { label: '流量', color: '#10b981' },
}
function edgeStyle(etype: string) {
  return edgeTypeMap[etype] || { label: etype || '连接', color: '#94a3b8' }
}

const shapeIcons: Record<string, string> = {
  host: '<rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>',
  firewall: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  switch: '<rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/>'
}

const nodeRefs = ref<Record<string, HTMLElement>>({})

function registerNodeRef(nodeId: string | number, el: any) {
  if (el) nodeRefs.value[String(nodeId)] = el as HTMLElement
}

// 计算节点中心坐标（考虑缩放和平移）
function getNodeCenter(nodeId: string | number) {
  const n = nodes.value.find(x => String(x.id) === String(nodeId))
  if (!n) return { x: 0, y: 0 }
  const left = parseFloat(n.left) / 100 * canvasSize.value.width
  const top = parseFloat(n.top) / 100 * canvasSize.value.height
  const el = nodeRefs.value[String(nodeId)]
  const w = el?.offsetWidth || 100
  const h = el?.offsetHeight || 80
  // SVG 也在 transform 层内部，所以直接用未变换坐标即可
  return { x: left + w / 2, y: top + h / 2 }
}

function updateCanvasSize() {
  if (canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    canvasSize.value = { width: rect.width / scale.value, height: rect.height / scale.value }
  }
}

// 鼠标滚轮缩放
function onWheel(e: WheelEvent) {
  if (!canvasRef.value) return
  e.preventDefault()
  const rect = canvasRef.value.getBoundingClientRect()
  // 鼠标在画布中的位置（相对画布左上角）
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const oldScale = scale.value
  // 缩放因子
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  let newScale = oldScale * delta
  newScale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, newScale))
  // 保持鼠标指向的画布点不变：调整 panOffset
  // newOffset = mouseX - (mouseX - oldOffset) * (newScale / oldScale)
  panOffset.value.x = mouseX - (mouseX - panOffset.value.x) * (newScale / oldScale)
  panOffset.value.y = mouseY - (mouseY - panOffset.value.y) * (newScale / oldScale)
  scale.value = newScale
  updateCanvasSize()
}

function zoomIn() {
  scale.value = Math.min(MAX_SCALE, scale.value * 1.2)
  updateCanvasSize()
}
function zoomOut() {
  scale.value = Math.max(MIN_SCALE, scale.value / 1.2)
  updateCanvasSize()
}
function zoomReset() {
  scale.value = 1
  panOffset.value = { x: 0, y: 0 }
  updateCanvasSize()
}

// 画布拖拽平移（在 select 工具下，点击画布空白区域并拖动）
function onCanvasMouseDown(e: MouseEvent) {
  // 仅在 select 工具下且点击的是画布本身（非节点）时启动平移
  if (activeTool.value !== 'select') return
  const target = e.target as HTMLElement
  // 如果点击的是节点或节点内部元素，不启动平移（由 onNodeMouseDown 处理拖拽节点）
  if (target.closest('.topo-node')) return
  if (target.closest('line')) return
  isPanning.value = true
  panStart.value = { x: e.clientX, y: e.clientY, ox: panOffset.value.x, oy: panOffset.value.y }
  document.addEventListener('mousemove', onPanMove)
  document.addEventListener('mouseup', onPanUp)
}

function onPanMove(e: MouseEvent) {
  if (!isPanning.value) return
  panOffset.value.x = panStart.value.ox + (e.clientX - panStart.value.x)
  panOffset.value.y = panStart.value.oy + (e.clientY - panStart.value.y)
}

function onPanUp() {
  isPanning.value = false
  document.removeEventListener('mousemove', onPanMove)
  document.removeEventListener('mouseup', onPanUp)
}

const transformStyle = computed(() => ({
  transform: `translate(${panOffset.value.x}px, ${panOffset.value.y}px) scale(${scale.value})`,
  transformOrigin: '0 0',
}))

async function loadTopology() {
  try {
    const data = await topologyApi.get(props.projectId)
    nodes.value = data.nodes
    edges.value = data.edges
  } catch (e) {
    ElMessage.warning('拓扑加载失败')
  }
}

async function resetLayout() {
  try {
    const data = await topologyApi.regenerate(props.projectId)
    nodes.value = data.nodes
    edges.value = data.edges
    ElMessage.success('拓扑已重新生成')
  } catch {}
}

async function exportImage() {
  try {
    const html2canvas = (await import('html2canvas')).default
    if (canvasRef.value) {
      const canvas = await html2canvas(canvasRef.value, { backgroundColor: '#ffffff', scale: 2 })
      const url = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = url
      a.download = `topology-${Date.now()}.png`
      a.click()
      ElMessage.success('拓扑图导出成功')
    }
  } catch {
    ElMessage.info('导出组件加载中，使用打印模式作为备选：请使用 Ctrl+P 保存为 PDF 或图片')
    if (canvasRef.value) {
      const w = window.open('', '_blank')
      if (w) {
        w.document.write('<title>拓扑图</title><body>' + canvasRef.value.outerHTML + '</body>')
        w.document.close()
      }
    }
  }
}

function onCanvasClick(e: MouseEvent) {
  if (activeTool.value === 'addNode') {
    const rect = canvasRef.value!.getBoundingClientRect()
    // 考虑缩放和平移：将屏幕坐标转换为画布内坐标
    const localX = (e.clientX - rect.left - panOffset.value.x) / scale.value
    const localY = (e.clientY - rect.top - panOffset.value.y) / scale.value
    const xPct = (localX / rect.width * 100).toFixed(1)
    const yPct = (localY / rect.height * 100).toFixed(1)
    newNodePosition.value = { left: Math.max(0, Math.min(95, parseFloat(xPct))) + '%', top: Math.max(0, Math.min(90, parseFloat(yPct))) + '%' }
    newNodeForm.value = { label: '', type: 'host' }
    addNodeDialogVisible.value = true
  }
}

async function confirmAddNode() {
  if (!newNodeForm.value.label.trim()) {
    ElMessage.warning('请输入节点名称')
    return
  }
  try {
    const newNode = await topologyApi.addNode(props.projectId, {
      label: newNodeForm.value.label,
      type: newNodeForm.value.type,
      left: newNodePosition.value.left,
      top: newNodePosition.value.top
    })
    nodes.value.push(newNode)
    addNodeDialogVisible.value = false
  } catch {}
}

function onNodeClick(nodeId: string | number, e: MouseEvent) {
  e.stopPropagation()
  if (activeTool.value === 'addEdge') {
    if (!edgeStartNodeId.value) {
      edgeStartNodeId.value = nodeId
      ElMessage.info('请点击第二个节点完成连线')
    } else if (edgeStartNodeId.value !== nodeId) {
      topologyApi.addEdge(props.projectId, { from: String(edgeStartNodeId.value), to: String(nodeId) })
        .then(edge => {
          edges.value.push(edge)
          ElMessage.success('连线添加成功')
        })
        .catch(() => {})
      edgeStartNodeId.value = null
    }
  } else if (activeTool.value === 'delete') {
    ElMessageBox.confirm('确认删除该节点？相关连线也会被删除。', '删除节点', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    }).then(async () => {
      await topologyApi.removeNode(nodeId)
      nodes.value = nodes.value.filter(n => n.id !== nodeId)
      edges.value = edges.value.filter(e => String(e.from) !== String(nodeId) && String(e.to) !== String(nodeId))
    }).catch(() => {})
  }
}

function onEdgeClick(idx: number, e: MouseEvent) {
  e.stopPropagation()
  if (activeTool.value === 'delete') {
    const edge = edges.value[idx]
    ElMessageBox.confirm('确认删除该连线？', '删除连线', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
    }).then(async () => {
      await topologyApi.removeEdge(`${edge.from}__${edge.to}`)
      edges.value.splice(idx, 1)
    }).catch(() => {})
  }
}

function onNodeMouseDown(nodeId: string | number, e: MouseEvent) {
  if (activeTool.value !== 'select') return
  e.preventDefault()
  e.stopPropagation()
  draggingNodeId.value = nodeId
  const el = nodeRefs.value[String(nodeId)]
  if (el && canvasRef.value) {
    const nodeRect = el.getBoundingClientRect()
    dragOffset.value = {
      x: e.clientX - nodeRect.left,
      y: e.clientY - nodeRect.top
    }
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  if (!draggingNodeId.value || !canvasRef.value) return
  const canvasRect = canvasRef.value.getBoundingClientRect()
  // 考虑缩放和平移：将屏幕坐标转换为画布内坐标
  const localX = (e.clientX - canvasRect.left - panOffset.value.x) / scale.value
  const localY = (e.clientY - canvasRect.top - panOffset.value.y) / scale.value
  const newX = localX - dragOffset.value.x
  const newY = localY - dragOffset.value.y
  const xPct = Math.max(0, Math.min(95, (newX / canvasRect.width * 100)))
  const yPct = Math.max(0, Math.min(90, (newY / canvasRect.height * 100)))
  const node = nodes.value.find(n => n.id === draggingNodeId.value)
  if (node) {
    node.left = xPct.toFixed(1) + '%'
    node.top = yPct.toFixed(1) + '%'
    if (updateTimer.value) clearTimeout(updateTimer.value)
    const nid = draggingNodeId.value as string | number
    updateTimer.value = setTimeout(() => {
      topologyApi.updateNodePosition(nid, parseFloat(node.left), parseFloat(node.top)).catch(() => {})
    }, 200)
  }
}

function onMouseUp() {
  draggingNodeId.value = null
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}

function onLabelDblClick(nodeId: string | number, e: MouseEvent) {
  if (activeTool.value !== 'select') return
  e.preventDefault()
  e.stopPropagation()
  const target = e.target as HTMLElement
  target.contentEditable = 'true'
  target.focus()
  const originalText = target.textContent || ''
  const saveEdit = async () => {
    target.contentEditable = 'false'
    const newLabel = target.textContent?.trim()
    if (newLabel && newLabel !== originalText) {
      const node = nodes.value.find(n => n.id === nodeId)
      if (node) {
        node.label = newLabel
        try {
          await topologyApi.addNode(props.projectId, node)
        } catch {}
      }
    } else {
      target.textContent = originalText
    }
    target.removeEventListener('blur', saveEdit)
    target.removeEventListener('keydown', onKey)
  }
  const onKey = (ke: KeyboardEvent) => {
    if (ke.key === 'Enter') {
      ke.preventDefault()
      target.blur()
    }
  }
  target.addEventListener('blur', saveEdit)
  target.addEventListener('keydown', onKey)
}

function handleResize() {
  updateCanvasSize()
}

onMounted(async () => {
  await loadTopology()
  await nextTick()
  updateCanvasSize()
  window.addEventListener('resize', handleResize)
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
  if (updateTimer.value) clearTimeout(updateTimer.value)
  document.removeEventListener('mousemove', onPanMove)
  document.removeEventListener('mouseup', onPanUp)
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})

watch(() => props.projectId, () => {
  loadTopology()
})

defineExpose({ resetLayout, exportImage, loadTopology })
</script>

<template>
  <div ref="containerRef" class="topo-container" :class="{ fullscreen: isFullscreen }">
    <div class="card topo-toolbar-card" :class="{ 'fullscreen-toolbar': isFullscreen }">
      <div class="topo-toolbar">
        <button
          v-for="t in tools"
          :key="t.key"
          class="topo-tool"
          :class="{ active: activeTool === t.key }"
          @click="activeTool = t.key; edgeStartNodeId = null"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="t.icon"></svg>
          {{ t.label }}
        </button>
        <!-- 缩放控制 -->
        <div class="zoom-controls">
          <button class="zoom-btn" @click="zoomOut" title="缩小">−</button>
          <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
          <button class="zoom-btn" @click="zoomIn" title="放大">+</button>
          <button class="zoom-btn reset" @click="zoomReset" title="重置缩放">⟲</button>
        </div>
        <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
          <button class="btn btn-ghost btn-sm" @click="resetLayout">重置布局</button>
          <button class="btn btn-ghost btn-sm" @click="exportImage">导出图片</button>
          <button class="btn btn-secondary btn-sm" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏显示'">
            <svg v-if="!isFullscreen" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px">
              <path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:middle;margin-right:4px">
              <path d="M8 3v3a2 2 0 0 1-2 2H3"/><path d="M21 8h-3a2 2 0 0 1-2-2V3"/><path d="M3 16h3a2 2 0 0 1 2 2v3"/><path d="M16 21v-3a2 2 0 0 1 2-2h3"/>
            </svg>
            {{ isFullscreen ? '退出全屏' : '全屏' }}
          </button>
        </div>
        <div class="topo-hint" v-if="activeTool === 'select'">拖拽节点调整位置，双击标签重命名；滚轮缩放，拖拽空白平移；节点下方显示上下行连接说明</div>
        <div class="topo-hint" v-else-if="activeTool === 'addNode'">点击画布空白处添加节点</div>
        <div class="topo-hint" v-else-if="activeTool === 'addEdge'">
          {{ edgeStartNodeId ? '点击第二个节点完成连线' : '先点击起始节点' }}
        </div>
        <div class="topo-hint" v-else-if="activeTool === 'delete'">点击节点或连线进行删除</div>
      </div>
      <!-- 边类型图例 -->
      <div class="edge-legend">
        <span class="legend-title">连线类型：</span>
        <span v-for="(v, k) in edgeTypeMap" :key="k" class="legend-item">
          <span class="legend-dot" :style="{ background: v.color }"></span>
          {{ v.label }}
        </span>
      </div>
    </div>

    <div
      ref="canvasRef"
      class="topology-canvas"
      @click="onCanvasClick"
      @wheel="onWheel"
      @mousedown="onCanvasMouseDown"
      :style="{ cursor: activeTool === 'addNode' ? 'crosshair' : activeTool === 'select' ? (isPanning ? 'grabbing' : 'grab') : 'pointer' }"
    >
      <!-- 缩放/平移变换层：SVG 和节点都在此层内，统一变换 -->
      <div class="topo-transform-layer" :style="transformStyle">
        <svg width="100%" height="100%" :style="{ position: 'absolute', inset: 0, pointerEvents: activeTool === 'delete' ? 'auto' : 'none' }">
          <!-- 箭头 marker 定义 -->
          <defs>
            <marker
              v-for="(v, k) in edgeTypeMap"
              :key="'marker-' + k"
              :id="'arrow-' + k"
              markerWidth="10" markerHeight="10"
              refX="9" refY="3"
              orient="auto" markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L9,3 z" :fill="v.color" />
            </marker>
            <marker
              id="arrow-delete"
              markerWidth="10" markerHeight="10"
              refX="9" refY="3"
              orient="auto" markerUnits="strokeWidth"
            >
              <path d="M0,0 L0,6 L9,3 z" fill="var(--error-400, #ef4444)" />
            </marker>
          </defs>
          <line
            v-for="(e, i) in edges"
            :key="`${e.from}-${e.to}-${i}`"
            :x1="getNodeCenter(e.from).x"
            :y1="getNodeCenter(e.from).y"
            :x2="getNodeCenter(e.to).x"
            :y2="getNodeCenter(e.to).y"
            :stroke="activeTool === 'delete' ? 'var(--error-400)' : edgeStyle(e.edge_type).color"
            :stroke-width="e.edge_type === 'traffic_flow' ? 2.5 : 1.8"
            :stroke-dasharray="e.edge_type === 'ssh_session' ? '6,3' : 'none'"
            :marker-end="activeTool === 'delete' ? 'url(#arrow-delete)' : `url(#arrow-${e.edge_type})`"
            style="cursor:pointer"
            @click.stop="onEdgeClick(i, $event)"
          />
        </svg>
        <div
          v-for="node in nodes"
          :key="node.id"
          :ref="(el) => registerNodeRef(node.id, el)"
          class="topo-node"
          :class="{
            'edge-start': edgeStartNodeId === node.id,
            'draggable': activeTool === 'select'
          }"
          :style="{ left: node.left, top: node.top }"
          @mousedown="onNodeMouseDown(node.id, $event)"
          @click="onNodeClick(node.id, $event)"
        >
          <div class="topo-shape" :class="node.type">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="shapeIcons[node.type]"></svg>
          </div>
          <span class="topo-label" @dblclick="onLabelDblClick(node.id, $event)">{{ node.label }}</span>
          <!-- 节点说明：展示上下行连接和流量走势 -->
          <span v-if="node.iface" class="topo-desc" :title="node.iface">{{ node.iface }}</span>
          <span v-if="node.ip" class="topo-ip">{{ node.ip }}</span>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="addNodeDialogVisible"
      title="添加节点"
      width="400px"
    >
      <el-form :model="newNodeForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="newNodeForm.label" placeholder="请输入节点名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="newNodeForm.type">
            <el-option label="防火墙" value="firewall" />
            <el-option label="交换机" value="switch" />
            <el-option label="主机" value="host" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="addNodeDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="confirmAddNode">确认添加</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.topo-container {
  position: relative;
}
.topo-container.fullscreen {
  background: #ffffff;
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.topo-container.fullscreen .topology-canvas {
  flex: 1;
  min-height: 0;
}
.fullscreen-toolbar {
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
  z-index: 10;
  flex-shrink: 0;
}

.edge-start {
  box-shadow: 0 0 0 2px var(--primary);
  border-radius: 8px;
}
.draggable {
  cursor: move;
}
.topo-transform-layer {
  position: absolute;
  inset: 0;
  transform-origin: 0 0;
}

/* 节点说明文字 */
.topo-desc {
  display: block;
  max-width: 180px;
  font-size: 10px;
  line-height: 1.3;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 4px;
  padding: 2px 6px;
  margin-top: 3px;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.topo-ip {
  display: block;
  font-size: 9px;
  color: #94a3b8;
  font-family: monospace;
  margin-top: 2px;
}

/* 边类型图例 */
.edge-legend {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border, #e2e8f0);
  font-size: 12px;
}
.legend-title {
  color: var(--text-muted, #64748b);
  font-weight: 500;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text, #0f172a);
}
.legend-dot {
  display: inline-block;
  width: 16px;
  height: 3px;
  border-radius: 2px;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: 12px;
  padding: 2px 6px;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-100, #f8fafc);
}
.zoom-btn {
  width: 26px; height: 26px;
  border: none; background: transparent; cursor: pointer;
  border-radius: 6px; font-size: 16px; line-height: 1;
  color: var(--text, #0f172a);
  display: flex; align-items: center; justify-content: center;
}
.zoom-btn:hover { background: var(--bg-200, #f1f5f9); }
.zoom-btn.reset { font-size: 14px; }
.zoom-level {
  font-size: 12px; min-width: 42px; text-align: center;
  color: var(--text-muted, #64748b); font-variant-numeric: tabular-nums;
}
</style>
