<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { reportApi } from '@/api'
import { useProjectStore } from '@/stores/project'

const store = useProjectStore()
const reports = ref<any[]>([])
const generating = ref<Record<string, boolean>>({})

// 预览相关状态
const previewVisible = ref(false)
const previewHtml = ref('')
const previewing = ref(false)        // 预览内容加载中
const confirming = ref(false)        // 确认导出（生成）中
const pendingFormat = ref('')        // 当前待导出的格式

async function loadReports() {
  try {
    reports.value = await reportApi.list(store.currentProject.id)
  } catch {}
}

// 点击导出按钮：先拉取 HTML 预览内容，再弹出 Dialog
async function handleExport(format: string) {
  const fmt = format.toLowerCase()
  pendingFormat.value = fmt
  previewing.value = true
  previewHtml.value = ''
  previewVisible.value = true
  try {
    previewHtml.value = await reportApi.preview(store.currentProject.id)
    if (!previewHtml.value) {
      ElMessage.warning('未获取到预览内容')
    }
  } catch {
    ElMessage.warning('预览加载失败')
  } finally {
    previewing.value = false
  }
}

// 确认导出：调用 generate 生成报告，加入历史并触发下载
async function confirmExport() {
  const fmt = pendingFormat.value
  if (!fmt) return
  confirming.value = true
  generating.value[fmt] = true
  try {
    const r = await reportApi.generate(store.currentProject.id, fmt)
    reports.value.unshift({
      id: r.id,
      createdAt: r.createdAt,
      project: store.currentProject.name,
      format: r.format,
      template: r.template,
      size: r.size
    })
    // 生成成功后触发下载
    if (r.id) reportApi.download(r.id)
    previewVisible.value = false
    ElMessage.success('报告已生成并开始下载')
  } catch {
    ElMessage.error('报告生成失败')
  } finally {
    confirming.value = false
    generating.value[fmt] = false
  }
}

function handleDownload(reportId: string) {
  reportApi.download(reportId)
}

function formatBadgeCls(fmt: string) {
  if (fmt === 'PDF') return 'badge-info'
  if (fmt === 'HTML') return 'badge-p2'
  return 'badge-p3'
}

onMounted(async () => {
  await store.init()
  loadReports()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">报告导出</div>
        <h1 class="h1">报告中心</h1>
        <p class="text-muted">将分析结果导出为 Markdown、HTML 或 PDF 格式。</p>
      </div>
    </div>

    <div class="three-col">
      <div class="card" style="text-align:center">
        <div style="width:56px;height:56px;border-radius:var(--radius-md);background:var(--bg-200);display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
        </div>
        <h3 class="h4" style="margin-bottom:8px">Markdown 报告</h3>
        <p class="text-muted" style="font-size:13px;margin-bottom:20px">轻量文本格式，便于版本管理与二次编辑。</p>
        <button class="btn btn-secondary btn-sm" :disabled="generating['md']" @click="handleExport('md')">
          {{ generating['md'] ? '生成中...' : '导出 MD' }}
        </button>
      </div>
      <div class="card" style="text-align:center">
        <div style="width:56px;height:56px;border-radius:var(--radius-md);background:var(--bg-200);display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>
        </div>
        <h3 class="h4" style="margin-bottom:8px">HTML 报告</h3>
        <p class="text-muted" style="font-size:13px;margin-bottom:20px">富格式网页报告，含交互式表格与拓扑图。</p>
        <button class="btn btn-secondary btn-sm" :disabled="generating['html']" @click="handleExport('html')">
          {{ generating['html'] ? '生成中...' : '导出 HTML' }}
        </button>
      </div>
      <div class="card" style="text-align:center">
        <div style="width:56px;height:56px;border-radius:var(--radius-md);background:var(--bg-200);display:inline-flex;align-items:center;justify-content:center;margin-bottom:16px">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 13l2 2 4-4"/></svg>
        </div>
        <h3 class="h4" style="margin-bottom:8px">PDF 报告</h3>
        <p class="text-muted" style="font-size:13px;margin-bottom:20px">适合打印与合规归档的正式版报告。</p>
        <button class="btn btn-secondary btn-sm" :disabled="generating['pdf']" @click="handleExport('pdf')">
          {{ generating['pdf'] ? '生成中...' : '导出 PDF' }}
        </button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">导出历史</h3>
          <p class="card-desc">最近生成的报告</p>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>时间</th><th>项目</th><th>格式</th><th>模板</th><th>大小</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in reports" :key="r.id">
              <td>{{ r.createdAt }}</td>
              <td>{{ r.project }}</td>
              <td><span class="badge" :class="formatBadgeCls(r.format)">{{ r.format }}</span></td>
              <td>{{ r.template }}</td>
              <td>{{ r.size }}</td>
              <td><button class="btn btn-ghost btn-sm" @click="handleDownload(r.id)">下载</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="reports.length === 0" style="text-align:center;padding:40px;color:var(--text-500)">
        暂无导出记录
      </div>
    </div>

    <!-- 报告预览弹窗：先预览 HTML，确认后再生成并下载 -->
    <el-dialog
      v-model="previewVisible"
      title="报告预览"
      width="86%"
      top="4vh"
      class="report-preview-dialog"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <div class="report-preview-body">
        <div v-if="previewing" class="report-preview-tip">正在生成预览…</div>
        <div v-else-if="previewHtml" v-html="previewHtml" class="report-preview-content"></div>
        <div v-else class="report-preview-tip">暂无可预览的内容</div>
      </div>
      <template #footer>
        <button class="btn btn-ghost btn-sm" :disabled="confirming" @click="previewVisible = false">关闭</button>
        <button
          class="btn btn-primary btn-sm"
          :disabled="previewing || confirming || !previewHtml"
          @click="confirmExport"
        >
          {{ confirming ? '导出中...' : '确认导出' }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
</style>

<style>
/* 报告预览弹窗（el-dialog 默认 teleport 到 body，需用非 scoped 样式） */
.report-preview-dialog .el-dialog__body {
  padding: 0;
}
.report-preview-body {
  max-height: 72vh;
  overflow: auto;
  padding: 16px 24px;
  background: #fff;
}
.report-preview-content {
  font-size: 14px;
  line-height: 1.7;
  color: #1f2937;
}
.report-preview-content :is(h1, h2, h3, h4, h5) {
  margin: 16px 0 8px;
  line-height: 1.4;
}
.report-preview-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
.report-preview-content th,
.report-preview-content td {
  border: 1px solid #e5e7eb;
  padding: 6px 10px;
  font-size: 13px;
  text-align: left;
}
.report-preview-content pre {
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 10px 12px;
  overflow: auto;
  font-size: 12.5px;
}
.report-preview-tip {
  text-align: center;
  padding: 48px 0;
  color: var(--text-500, #6b7280);
}
</style>
