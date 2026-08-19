<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { manualApi } from '@/api'
import type { DocSection } from '@/types'

const CATEGORY_LABEL: Record<string, string> = {
  command_reference: '命令参考',
  protocol_reference: '协议 / 端口标准',
  config_pattern: '配置结构参考',
  log_pattern: '日志结构参考',
  compliance_baseline: '合规基线',
  troubleshooting: '排障手册',
  vendor_notes: '厂商注意事项',
}

const MAPPING_LABEL: Record<string, string> = {
  config_parser: '配置解析依据',
  log_parser: '日志解析依据',
  both: '双解析依据',
}

interface ManualDictEntry {
  id: number
  title: string
  category: string
  vendor?: string
  device_family?: string
  os_version?: string
  mapping_target?: string
  trigger_keywords?: string[]
  signature_patterns?: string[]
  summary?: string
  content_md: string
  references?: string[]
  standard_ref?: string
  created_at?: string
  updated_at?: string
}

interface PairHit {
  manual_id: number
  title: string
  category: string
  vendor?: string
  mapping_target?: string
  summary?: string
  score: number
  matched_keywords: string[]
  snippet?: string
}

type TabKey = 'library' | 'pair'

const activeTab = ref<TabKey>('library')
const loading = ref(false)
const entries = ref<ManualDictEntry[]>([])

// ---- Filters (library tab) ----
const searchQ = ref('')
const filterCategory = ref<string>('')
const filterMapping = ref<string>('')
const filterVendor = ref<string>('')
const categories = ref<{ value: string; label: string }[]>([])
const mappingTargets = ref<{ value: string; label: string }[]>([])

// ---- Detail / Edit dialog ----
const detailId = ref<number | null>(null)
const editMode = ref<'create' | 'edit' | 'view'>('view')
const editDialogVisible = ref(false)
const emptyForm = (): ManualDictEntry => ({
  id: 0,
  title: '',
  category: 'config_pattern',
  mapping_target: 'config_parser',
  trigger_keywords: [],
  signature_patterns: [],
  summary: '',
  content_md: '',
  references: [],
  standard_ref: '',
  vendor: '',
  device_family: '',
  os_version: '',
})
const form = reactive<ManualDictEntry>(emptyForm())

// ---- Pairing tab ----
const pairQuery = ref('')
const pairTarget = ref<'config_parser' | 'log_parser' | 'both'>('config_parser')
const pairBusy = ref(false)
const pairHits = ref<PairHit[]>([])
const pairPlaceholderMap = {
  config_parser: '粘贴待识别的配置行，例如：\nacl number 3001\n  rule 0 deny tcp destination 10.0.0.0 0.0.0.255 destination-port eq 22',
  log_parser: '粘贴待识别的日志原文，例如：\n%Feb 12 09:27:31.111: %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success to vty0',
  both: '粘贴原文（配置或日志均可），系统将同时匹配两种解析依据',
}

// ---- Library loading ----
const paramsReady = computed(() => [
  searchQ.value.trim(),
  filterCategory.value,
  filterMapping.value,
  filterVendor.value,
].join('|'))

watch(paramsReady, async () => {
  if (activeTab.value === 'library') await loadLibrary()
}, { immediate: false })

watch(activeTab, async (v) => {
  if (v === 'library' && entries.value.length === 0) await loadLibrary()
})

async function loadLibrary() {
  loading.value = true
  try {
    const data = await manualApi.list({
      q: searchQ.value.trim() || undefined,
      category: filterCategory.value || undefined,
      mapping_target: filterMapping.value || undefined,
      vendor: filterVendor.value || undefined,
      limit: 200,
    }) as any
    entries.value = Array.isArray(data) ? data : (data?.items || [])
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  try {
    const r = await manualApi.categories() as any
    categories.value = r?.categories || []
    mappingTargets.value = r?.mapping_targets || []
  } catch {}
}

function categoryLabel(v?: string) {
  if (!v) return ''
  return CATEGORY_LABEL[v] || v
}
function mappingLabel(v?: string) {
  if (!v) return '—'
  return MAPPING_LABEL[v] || v
}

// ---- CRUD ----
function openCreate() {
  Object.assign(form, emptyForm(), {
    category: categories.value[0]?.value || 'config_pattern',
    mapping_target: mappingTargets.value[0]?.value || 'config_parser',
  })
  editMode.value = 'create'
  editDialogVisible.value = true
}
function openView(entry: ManualDictEntry) {
  Object.assign(form, { ...entry })
  detailId.value = entry.id
  editMode.value = 'view'
  editDialogVisible.value = true
}
function openEdit(entry: ManualDictEntry) {
  Object.assign(form, { ...entry })
  detailId.value = entry.id
  editMode.value = 'edit'
  editDialogVisible.value = true
}
function switchFormToEdit() {
  editMode.value = 'edit'
}
async function saveForm() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写标题（条目名）')
    return
  }
  if (!form.content_md.trim()) {
    ElMessage.warning('请填写内容（Markdown）')
    return
  }
  const payload: Record<string, any> = {
    title: form.title.trim(),
    category: form.category,
    mapping_target: form.mapping_target || undefined,
    vendor: (form.vendor || '').trim() || undefined,
    device_family: (form.device_family || '').trim() || undefined,
    os_version: (form.os_version || '').trim() || undefined,
    summary: (form.summary || '').trim() || undefined,
    content_md: form.content_md,
    standard_ref: (form.standard_ref || '').trim() || undefined,
    trigger_keywords: (Array.isArray(form.trigger_keywords) ? form.trigger_keywords : [])
      .map(s => String(s || '').trim()).filter(Boolean),
    signature_patterns: (Array.isArray(form.signature_patterns) ? form.signature_patterns : [])
      .map(s => String(s || '').trim()).filter(Boolean),
    references: (Array.isArray(form.references) ? form.references : [])
      .map(s => String(s || '').trim()).filter(Boolean),
  }
  try {
    if (editMode.value === 'create') {
      const created = await manualApi.create(payload) as any
      entries.value.unshift(created)
      ElMessage.success('字典条目已新增')
    } else {
      if (!form.id) return
      const updated = await manualApi.update(form.id, payload) as any
      const idx = entries.value.findIndex(e => e.id === form.id)
      if (idx >= 0) entries.value.splice(idx, 1, updated)
      ElMessage.success('字典条目已更新')
    }
    editDialogVisible.value = false
    detailId.value = null
  } catch {}
}

async function deleteEntry(e: ManualDictEntry) {
  try {
    await ElMessageBox.confirm(`确认删除字典条目「${e.title}」？此操作不可恢复`,
      '删除字典条目', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await manualApi.remove(e.id)
    entries.value = entries.value.filter(x => x.id !== e.id)
    ElMessage.success('已删除')
  } catch {}
}

// ---- Pairing tab ----
async function runPair() {
  const q = pairQuery.value.trim()
  if (!q) {
    ElMessage.warning('请先粘贴要识别的原文（配置行或日志行）')
    return
  }
  pairBusy.value = true
  try {
    pairHits.value = (await manualApi.pair({ q, mapping_target: pairTarget.value }) as any) || []
    if (!pairHits.value.length) {
      ElMessage.info('未找到匹配的字典依据，可调整关键词或在「字典库」补充条目')
    }
  } finally {
    pairBusy.value = false
  }
}

function jumpHitToLibrary(hit: PairHit) {
  activeTab.value = 'library'
  loadLibrary().then(() => {
    detailId.value = hit.manual_id
    const target = entries.value.find(e => e.id === hit.manual_id)
    if (target) {
      Object.assign(form, { ...target })
      editMode.value = 'view'
      editDialogVisible.value = true
    }
  })
}

function parseArrayInput(v: string): string[] {
  return v.split(/[,，\n;；]/).map(s => s.trim()).filter(Boolean)
}
// bind string <-> string[] helpers for form
const triggerKeywordsStr = computed({
  get: () => Array.isArray(form.trigger_keywords) ? form.trigger_keywords.join('，') : '',
  set: (v: string) => { form.trigger_keywords = parseArrayInput(v) }
})
const signaturePatternsStr = computed({
  get: () => Array.isArray(form.signature_patterns) ? form.signature_patterns.join('\n') : '',
  set: (v: string) => { form.signature_patterns = parseArrayInput(v) }
})
const referencesStr = computed({
  get: () => Array.isArray(form.references) ? form.references.join('\n') : '',
  set: (v: string) => { form.references = parseArrayInput(v) }
})

// ---- Seed helpers: add a few starter entries if none ----
async function seedStarter() {
  const starters: Omit<ManualDictEntry, 'id'>[] = [
    {
      title: '华为 VRP 5/8 ACL 基础命令结构',
      category: 'config_pattern',
      vendor: 'Huawei',
      device_family: 'AR/S/SR',
      os_version: 'VRP5/VRP8',
      mapping_target: 'config_parser',
      trigger_keywords: ['acl', 'rule', 'deny', 'permit', 'acl number'],
      signature_patterns: ['^acl\\s+number\\s+\\d+', '^\\s*rule\\s+\\d+\\s+(deny|permit)'],
      summary: '华为设备 ACL 配置结构解析依据：识别 acl number / acl name 进入段，rule 行逐条解析为条目。',
      content_md: `# 华为 ACL 配置结构\n\n## 格式\n\n1. **编号 ACL**：\n   \`\`\`\nacl number <2000-5999>\n  rule <id> <deny|permit> <protocol> source <src> [wildcard] destination <dst> [wildcard] destination-port eq <port>\n   \`\`\`\n2. **命名 ACL**：\n   \`\`\`\nacl name <name> [advanced|basic]\n  rule ...\n   \`\`\`\n\n## 解析规则\n\n- 进入段后，\`rule\` 开头行归属于当前 ACL\n- 关键字段：rule id / action / protocol / source / destination / port\n- 风险提示：\`deny\` 任何访问 22/telnet 除外的策略缺失 → 标记弱访问控制`,
      references: ['https://support.huawei.com'],
      standard_ref: 'GB/T 22239-2019 7.1.2.3 访问控制',
    },
    {
      title: 'Cisco IOS SYSLOG %FAC-SUBFAC-SEVERITY 结构',
      category: 'log_pattern',
      vendor: 'Cisco',
      device_family: 'IOS/IOS-XE',
      os_version: '12.x, 15.x, 17.x',
      mapping_target: 'log_parser',
      trigger_keywords: ['%SYS', '%SEC', '%LINE', '%LINK', '%SEC_LOGIN'],
      signature_patterns: ['^%[A-Z0-9_-]+-[0-9]-[A-Z0-9_-]+:'],
      summary: 'Cisco IOS 日志行结构解析依据：识别 %FAC-SUBFAC-SEVERITY-MESSAGE 结构并拆解字段。',
      content_md: `# Cisco IOS 日志格式\n\n## 标准格式\n\n\`\`\`\n<sequence>: %<FAC>-<SEVERITY>-<MNEMONIC>: <description>\n\`\`\`\n或带时间戳：\n\`\`\`\n*Mon Mar 14 09:27:31.111: %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: admin] [Source: 10.0.0.5] [localport: 22] at 09:27:31 UTC Mon Mar 14 2024\n\`\`\`\n\n## 解析字段\n\n- timestamp\n- facility (SEC_LOGIN / LINEPROTO / LINK 等)\n- severity (0-7, 0=Emerg, 5=Notice)\n- mnemonic (LOGIN_SUCCESS / UPDOWN 等)\n- description / free fields (user / Source / localport / session_id 等)\n\n## 风险提示\n\n- severity ≤ 2：高风险事件\n- AUTH-* / SECURITY-* 失败：鉴权/入侵异常`,
      references: ['Cisco Syslog Message Guide'],
      standard_ref: 'RFC 3164 BSD syslog Protocol',
    },
    {
      title: 'SSH / TELNET 管理面配置硬ening',
      category: 'compliance_baseline',
      mapping_target: 'both',
      trigger_keywords: ['ssh', 'telnet', 'vty', 'login', 'acl', 'transport input', 'version 2'],
      signature_patterns: ['transport input (ssh|telnet|all|none)', 'ip ssh version 2', 'line vty'],
      summary: '管理面协议硬ening：SSHv2 优先、禁用 Telnet、绑定 ACL、限制 VTY 空闲超时等。',
      content_md: `# 管理通道合规基线\n\n## 必选\n\n1. ` + '`ip ssh version 2`' + `，禁用 v1\n2. VTY 下 ` + '`transport input ssh`' + `，禁止 telnet / all\n3. VTY 绑定 ` + '`access-class <acl> in`' + `\n4. ` + '`exec-timeout 5 0`' + ` 及以下\n5. 启用 ` + '`login authentication`' + `（AAA/TACACS+ 优先）\n\n## 配对标记\n\n- 解析到 ` + '`transport input telnet`' + ` → 中等风险\n- 解析到 ` + '`ip ssh version 1`' + ` 或缺省 → 中风险\n- 无 access-class → 低风险（若直连外网 → 高）`,
      references: ['CIS 2.1 Network Devices'],
      standard_ref: '等保 2.0 三级 / GB/T 22239-2019',
    },
  ]
  try {
    for (const s of starters) {
      await manualApi.create(s as any)
    }
    ElMessage.success(`已注入 ${starters.length} 条样例字典`)
    await loadLibrary()
  } catch {}
}

onMounted(async () => {
  await loadCategories()
  await loadLibrary()
  // 若字典为空，询问是否填充样例（静默先加载）
})
</script>

<template>
  <div class="manuals-page page">
    <header class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">后台知识字典 · 操作手册库</div>
        <h1 class="h1">操作手册 / 解析依据字典库</h1>
        <p class="text-muted">
          本页维护独立的<strong>后台字典</strong>，与项目内用户上传的材料（配置 / 日志 / 手册 PDF）物理隔离。
          字典条目用于：1) 学习查阅厂商 CLI / 日志结构 / 合规基线；2) 为配置解析、日志解析提供「配对依据」。
        </p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-secondary btn-sm" @click="seedStarter">加载样例字典</button>
        <button class="btn btn-primary btn-sm" @click="openCreate" v-if="activeTab === 'library'">+ 新增字典条目</button>
      </div>
    </header>

    <!-- Tabs -->
    <div class="tabs card">
      <button
        class="tab"
        :class="{ active: activeTab === 'library' }"
        @click="activeTab = 'library'"
      >
        📚 字典库
        <small class="tab-count">{{ entries.length }}</small>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'pair' }"
        @click="activeTab = 'pair'"
      >
        🧩 解析依据配对
      </button>
    </div>

    <!-- Library tab -->
    <section v-if="activeTab === 'library'" class="card">
      <div class="library-filters">
        <div class="filter-field">
          <span class="field-label">关键词</span>
          <input
            class="input"
            v-model="searchQ"
            placeholder="按标题/摘要/正文/触发词搜索"
            @keyup.enter="loadLibrary"
          />
        </div>
        <div class="filter-field">
          <span class="field-label">分类</span>
          <select class="select" v-model="filterCategory" @change="loadLibrary">
            <option value="">全部分类</option>
            <option v-for="c in categories" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div class="filter-field">
          <span class="field-label">解析依据</span>
          <select class="select" v-model="filterMapping" @change="loadLibrary">
            <option value="">全部</option>
            <option v-for="m in mappingTargets" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </div>
        <div class="filter-field">
          <span class="field-label">厂商</span>
          <input
            class="input"
            v-model="filterVendor"
            placeholder="如 Huawei / Cisco / H3C"
            @keyup.enter="loadLibrary"
          />
        </div>
        <div class="filter-field actions">
          <button class="btn btn-secondary btn-sm" @click="loadLibrary" :disabled="loading">查询</button>
          <button
            class="btn btn-ghost btn-sm"
            @click="searchQ = ''; filterCategory = ''; filterMapping = ''; filterVendor = ''"
          >重置</button>
        </div>
      </div>

      <div v-if="loading" class="loading-hint">加载中…</div>

      <div v-else-if="!entries.length" class="empty-hint">
        暂无字典条目。点击右上角「+ 新增字典条目」或「加载样例字典」开始。
      </div>

      <div v-else class="entries-grid">
        <article class="entry-card" v-for="e in entries" :key="e.id" @click="openView(e)">
          <header class="entry-head">
            <div class="entry-cats">
              <span class="cat-chip cat-main">{{ categoryLabel(e.category) }}</span>
              <span class="cat-chip" :class="'mt-' + (e.mapping_target || 'none')">
                {{ mappingLabel(e.mapping_target) }}
              </span>
              <span v-if="e.vendor" class="cat-chip vendor">{{ e.vendor }}</span>
            </div>
            <div class="entry-updated muted">
              更新 {{ e.updated_at?.slice(0, 10) }}
            </div>
          </header>
          <h3 class="entry-title">{{ e.title }}</h3>
          <p class="entry-summary" v-if="e.summary">{{ e.summary }}</p>
          <footer class="entry-foot">
            <div class="entry-kws">
              <span class="kw" v-for="(kw, idx) in (e.trigger_keywords || []).slice(0, 8)" :key="idx">#{{ kw }}</span>
              <span v-if="(e.trigger_keywords?.length ?? 0) > 8" class="muted">+{{ (e.trigger_keywords?.length ?? 0) - 8 }} 更多</span>
            </div>
            <div class="entry-actions" @click.stop>
              <button class="btn btn-ghost btn-xs" @click="openEdit(e)">编辑</button>
              <button class="btn btn-danger-ghost btn-xs" @click="deleteEntry(e)">删除</button>
            </div>
          </footer>
        </article>
      </div>
    </section>

    <!-- Pairing tab -->
    <section v-if="activeTab === 'pair'" class="pair-layout">
      <div class="card pair-input-card">
        <h3 class="h4 pair-subtitle">① 粘贴待识别的原文</h3>
        <div class="segmented">
          <label :class="{ active: pairTarget === 'config_parser' }">
            <input type="radio" v-model="pairTarget" value="config_parser" hidden>
            <span>配置解析依据</span>
          </label>
          <label :class="{ active: pairTarget === 'log_parser' }">
            <input type="radio" v-model="pairTarget" value="log_parser" hidden>
            <span>日志解析依据</span>
          </label>
          <label :class="{ active: pairTarget === 'both' }">
            <input type="radio" v-model="pairTarget" value="both" hidden>
            <span>自动识别</span>
          </label>
        </div>
        <textarea
          class="pair-query"
          v-model="pairQuery"
          :placeholder="pairPlaceholderMap[pairTarget]"
          rows="10"
        ></textarea>
        <div class="pair-buttons">
          <button class="btn btn-primary" :disabled="pairBusy" @click="runPair">
            {{ pairBusy ? '匹配中…' : '🧠 根据字典配对解析依据' }}
          </button>
          <button class="btn btn-ghost btn-sm" @click="pairQuery = ''; pairHits = []">清空</button>
        </div>
        <p class="hint pair-hint">
          提示：配对采用「触发关键词 + 正文字面重叠」综合打分。若结果不理想，可在「字典库」新增 / 编辑条目补充 trigger_keywords。
        </p>
      </div>

      <div class="card pair-result-card">
        <h3 class="h4 pair-subtitle">② 配对到的解析依据</h3>
        <div v-if="pairBusy" class="loading-hint">正在匹配字典…</div>
        <div v-else-if="!pairHits.length" class="empty-hint empty-hint-sm">
          请在左侧粘贴配置或日志原文，点击按钮开始配对。
        </div>
        <ol v-else class="hit-list">
          <li v-for="(h, idx) in pairHits" :key="h.manual_id" class="hit-card">
            <div class="hit-head">
              <span class="hit-rank">{{ idx + 1 }}</span>
              <span class="hit-score" :class="'score-' + (h.score >= 10 ? 'high' : h.score >= 3 ? 'mid' : 'low')">
                得分 {{ h.score }}
              </span>
              <span class="cat-chip cat-main">{{ categoryLabel(h.category) }}</span>
              <span class="cat-chip" :class="'mt-' + (h.mapping_target || 'none')">
                {{ mappingLabel(h.mapping_target) }}
              </span>
              <span v-if="h.vendor" class="cat-chip vendor">{{ h.vendor }}</span>
            </div>
            <h4 class="hit-title">{{ h.title }}</h4>
            <p v-if="h.summary" class="hit-summary">{{ h.summary }}</p>
            <div v-if="h.snippet" class="hit-snippet">
              <span class="muted">相关片段：</span>
              <quote>{{ h.snippet }}</quote>
            </div>
            <div v-if="h.matched_keywords?.length" class="hit-kws">
              <span class="muted">匹配触发词：</span>
              <span class="kw kw-hit" v-for="kw in h.matched_keywords.slice(0, 12)" :key="kw">{{ kw }}</span>
              <span v-if="(h.matched_keywords?.length ?? 0) > 12" class="muted">…</span>
            </div>
            <div class="hit-actions">
              <button class="btn btn-ghost btn-xs" @click="jumpHitToLibrary(h)">查看字典条目</button>
            </div>
          </li>
        </ol>
      </div>
    </section>

    <!-- Edit / View dialog -->
    <el-dialog
      v-model="editDialogVisible"
      :title="editMode === 'create' ? '新增字典条目' : editMode === 'edit' ? '编辑字典条目' : '查看字典条目'"
      width="min(880px, 92vw)"
      destroy-on-close
    >
      <div class="form-grid" v-if="editMode !== 'view'">
        <div class="f12">
          <label class="lab">标题 *</label>
          <input class="input" v-model="form.title" placeholder="如：华为 VRP ACL 结构解析" maxlength="200" />
        </div>
        <div>
          <label class="lab">分类 *</label>
          <select class="select" v-model="form.category">
            <option v-for="c in categories" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div>
          <label class="lab">作为</label>
          <select class="select" v-model="form.mapping_target">
            <option value="">—</option>
            <option v-for="m in mappingTargets" :key="m.value" :value="m.value">{{ m.label }}</option>
          </select>
        </div>
        <div>
          <label class="lab">厂商</label>
          <input class="input" v-model="form.vendor" placeholder="Huawei / Cisco / H3C / Juniper …" />
        </div>
        <div>
          <label class="lab">设备系列</label>
          <input class="input" v-model="form.device_family" placeholder="AR/S/SR / IOS-XE / SRX …" />
        </div>
        <div>
          <label class="lab">OS / 版本</label>
          <input class="input" v-model="form.os_version" placeholder="VRP8 / 17.x / Junos 22.x …" />
        </div>
        <div class="f12">
          <label class="lab">触发关键词 <small class="muted">（用 中文逗号 / 英文逗号 / 换行 分隔；用于配对打分）</small></label>
          <input class="input" v-model="triggerKeywordsStr" placeholder="acl, rule, deny, permit, security-policy" />
        </div>
        <div class="f12">
          <label class="lab">签名正则 <small class="muted">（每行一条，用于快速识别该条目）</small></label>
          <textarea class="textarea" v-model="signaturePatternsStr" rows="3" placeholder="^acl\s+number\s+\d+&#10;^\s*rule\s+\d+"></textarea>
        </div>
        <div class="f12">
          <label class="lab">摘要</label>
          <input class="input" v-model="form.summary" maxlength="300" show-word-limit placeholder="1~2 句话概括此条目核心内容" />
        </div>
        <div class="f12">
          <label class="lab">正文（Markdown） *</label>
          <textarea class="textarea" v-model="form.content_md" rows="14" placeholder="# 标题&#10;&#10;## 小节&#10;内容支持 Markdown，建议包含：格式说明 / 字段 / 风险 / 整改建议"></textarea>
        </div>
        <div>
          <label class="lab">标准编号</label>
          <input class="input" v-model="form.standard_ref" placeholder="GB/T 22239-2019 / CIS 3.x …" />
        </div>
        <div class="f12">
          <label class="lab">参考链接 <small class="muted">（每行一条）</small></label>
          <textarea class="textarea" v-model="referencesStr" rows="2" placeholder="https://support.huawei.com"></textarea>
        </div>
      </div>

      <!-- View-only mode -->
      <div v-else class="view-block">
        <div class="view-head">
          <span class="cat-chip cat-main">{{ categoryLabel(form.category) }}</span>
          <span class="cat-chip" :class="'mt-' + (form.mapping_target || 'none')">{{ mappingLabel(form.mapping_target) }}</span>
          <span v-if="form.vendor" class="cat-chip vendor">{{ form.vendor }}</span>
          <span v-if="form.device_family" class="muted">· {{ form.device_family }}</span>
          <span v-if="form.os_version" class="muted">· {{ form.os_version }}</span>
          <span v-if="form.standard_ref" class="muted">· 标准：{{ form.standard_ref }}</span>
        </div>
        <h3 class="view-title">{{ form.title }}</h3>
        <p v-if="form.summary" class="view-summary">{{ form.summary }}</p>
        <div v-if="form.trigger_keywords?.length" class="view-kws">
          <b>触发关键词：</b>
          <span class="kw" v-for="kw in form.trigger_keywords" :key="kw">#{{ kw }}</span>
        </div>
        <div v-if="form.signature_patterns?.length" class="view-signatures">
          <b>签名模式：</b>
          <code v-for="(p, idx) in form.signature_patterns" :key="idx" class="sig-code">{{ p }}</code>
        </div>
        <div class="view-body">
          <pre class="md-body">{{ form.content_md }}</pre>
        </div>
        <div v-if="form.references?.length" class="view-refs">
          <b>参考链接：</b>
          <ul>
            <li v-for="(r, idx) in form.references" :key="idx">{{ r }}</li>
          </ul>
        </div>
      </div>

      <template #footer>
        <button v-if="editMode === 'view'" class="btn btn-ghost btn-sm" @click="switchFormToEdit">编辑</button>
        <button v-if="editMode === 'view'" class="btn btn-ghost btn-sm" @click="editDialogVisible = false">关闭</button>
        <template v-else>
          <button class="btn btn-ghost btn-sm" @click="editDialogVisible = false">取消</button>
          <button class="btn btn-primary btn-sm" @click="saveForm">
            {{ editMode === 'create' ? '新增' : '保存' }}
          </button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.manuals-page { width: 100%; }
.page-head {
  display: flex; justify-content: space-between; align-items: flex-end; gap: 16px;
  margin-bottom: 14px;
}
.page-head-actions { display: flex; gap: 8px; }

.tabs {
  display: inline-flex; gap: 4px;
  padding: 6px; margin-bottom: 14px;
  background: var(--color-bg);
  border: 1px solid var(--color-border-soft);
}
.tab {
  padding: 8px 14px; border-radius: 10px; font-size: 14px; font-weight: 600;
  background: transparent; border: 0; color: var(--color-text-soft);
  display: inline-flex; align-items: center; gap: 8px; cursor: pointer;
}
.tab:hover { color: var(--color-text); }
.tab.active {
  background: linear-gradient(135deg, var(--primary), var(--primary-deep));
  color: #fff; box-shadow: 0 6px 16px -8px var(--primary-deep);
}
.tab-count { font-weight: 500; font-size: 11.5px; opacity: .85; }

.library-filters {
  display: grid; gap: 12px 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  margin-bottom: 16px;
}
@media (max-width: 1100px) { .library-filters { grid-template-columns: repeat(2, 1fr) auto; } }
@media (max-width: 680px) { .library-filters { grid-template-columns: 1fr; } }
.filter-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.filter-field.actions { flex-direction: row; align-items: flex-end; gap: 8px; }
.field-label {
  font-size: 11px; font-weight: 700; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--color-text-soft);
}
.input, .select, .textarea {
  width: 100%;
  padding: 10px 12px; border-radius: 10px;
  border: 1px solid var(--color-border);
  background: var(--color-bg); color: var(--color-text);
  font-size: 13.5px; font-family: inherit;
  transition: border-color .15s ease, box-shadow .15s ease;
}
.input:focus, .select:focus, .textarea:focus {
  outline: none; border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-dim);
}
.textarea { resize: vertical; line-height: 1.6; }

.loading-hint { padding: 36px 0; text-align: center; color: var(--color-text-soft); }
.empty-hint { padding: 40px 20px; text-align: center; color: var(--color-text-soft); font-size: 13.5px; }
.empty-hint-sm { padding: 28px 10px; }

.entries-grid {
  display: grid; gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
}
.entry-card {
  border: 1px solid var(--color-border-soft);
  border-radius: 14px; padding: 16px 16px 14px;
  background: var(--color-bg);
  cursor: pointer;
  transition: transform .15s ease, box-shadow .2s ease, border-color .15s ease;
  display: flex; flex-direction: column; gap: 8px;
}
.entry-card:hover {
  border-color: var(--primary-dim);
  transform: translateY(-2px);
  box-shadow: 0 14px 28px -16px var(--primary-deep);
}
.entry-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.entry-cats { display: flex; flex-wrap: wrap; gap: 6px; }
.entry-updated { font-size: 11.5px; }
.entry-title {
  margin: 0; font-size: 15px; font-weight: 700; color: var(--color-text);
  line-height: 1.4;
}
.entry-summary {
  margin: 0; font-size: 12.5px; color: var(--color-text-soft); line-height: 1.6;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;
  overflow: hidden;
}
.entry-foot {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;
  margin-top: auto; padding-top: 8px;
}
.entry-kws { display: flex; flex-wrap: wrap; gap: 4px 6px; max-width: 70%; }
.entry-actions { display: flex; gap: 6px; }

.cat-chip {
  padding: 2px 9px; border-radius: 999px; font-size: 11.5px;
  background: var(--color-bg-soft); color: var(--color-text-soft);
  border: 1px solid var(--color-border-soft);
}
.cat-chip.cat-main { background: #eef2ff; color: #4338ca; border-color: #c7d2fe; }
.cat-chip.mt-config_parser { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.cat-chip.mt-log_parser { background: #fef9c3; color: #854d0e; border-color: #fde047; }
.cat-chip.mt-both { background: #ede9fe; color: #5b21b6; border-color: #ddd6fe; }
.cat-chip.mt-none { background: #f1f5f9; color: #475569; }
.cat-chip.vendor { background: #ffedd5; color: #9a3412; border-color: #fed7aa; }

.kw {
  display: inline-block; padding: 1px 8px; font-size: 11px;
  border-radius: 999px;
  background: var(--color-bg-soft); color: var(--color-text-soft);
  border: 1px solid var(--color-border-soft);
}
.kw-hit { background: #ecfeff; color: #155e75; border-color: #a5f3fc; }

/* Pair tab */
.pair-layout {
  display: grid; gap: 14px;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.25fr);
}
@media (max-width: 1000px) { .pair-layout { grid-template-columns: 1fr; } }
.pair-subtitle { margin: 0 0 10px; font-weight: 600; }
.segmented {
  display: inline-flex; padding: 4px; margin-bottom: 12px;
  border-radius: 12px; border: 1px solid var(--color-border-soft); background: var(--color-bg-soft);
}
.segmented label {
  padding: 6px 12px; cursor: pointer; border-radius: 9px;
  font-size: 12.5px; color: var(--color-text-soft); transition: all .15s ease;
}
.segmented label.active {
  background: #fff; color: var(--primary-deep); font-weight: 600;
  box-shadow: 0 2px 6px -2px var(--primary-dim);
}
.pair-query {
  width: 100%; min-height: 240px;
  padding: 12px 14px; border-radius: 12px;
  border: 1px solid var(--color-border); background: #fff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 13px; line-height: 1.65;
}
.pair-buttons { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
.pair-hint { margin: 10px 0 0; }

.hit-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.hit-card {
  border: 1px solid var(--color-border-soft);
  border-radius: 14px; padding: 14px 16px;
  background: var(--color-bg);
}
.hit-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 6px; }
.hit-rank {
  width: 22px; height: 22px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--primary-50); color: var(--primary-deep);
  font-weight: 700; font-size: 12px;
}
.hit-score { padding: 2px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700; }
.hit-score.score-high { background: #dcfce7; color: #166534; }
.hit-score.score-mid { background: #fef9c3; color: #854d0e; }
.hit-score.score-low { background: #f1f5f9; color: #475569; }
.hit-title { margin: 4px 0 2px; font-size: 15px; font-weight: 700; }
.hit-summary { margin: 0 0 8px; color: var(--color-text-soft); font-size: 13px; line-height: 1.6; }
.hit-snippet { font-size: 12.5px; margin-bottom: 8px; }
.hit-snippet quote {
  display: block; margin-top: 4px;
  padding: 8px 12px; border-radius: 10px; background: var(--color-bg-soft);
  border-left: 3px solid var(--primary);
  color: var(--color-text);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: pre-wrap; line-height: 1.55;
}
.hit-kws { margin: 6px 0 10px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.hit-actions { display: flex; justify-content: flex-end; }

/* Form grid */
.form-grid {
  display: grid; gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.form-grid .f12 { grid-column: 1 / -1; }
.lab { display: block; font-size: 12.5px; font-weight: 600; margin-bottom: 6px; color: var(--color-text); }
.lab small { font-weight: 400; color: var(--color-text-soft); }

/* View block */
.view-block { display: flex; flex-direction: column; gap: 12px; }
.view-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding-bottom: 10px; border-bottom: 1px dashed var(--color-border-soft); }
.view-title { margin: 0; font-size: 20px; font-weight: 700; }
.view-summary { margin: 0; color: var(--color-text-soft); font-size: 13.5px; line-height: 1.7; }
.view-kws, .view-signatures, .view-refs { font-size: 13px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.view-kws b, .view-signatures b, .view-refs b { font-weight: 600; color: var(--color-text); }
.sig-code {
  padding: 2px 8px; border-radius: 6px;
  background: #f5f3ff; color: #5b21b6; border: 1px solid #ddd6fe;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
}
.md-body {
  background: #fafafa; border: 1px solid var(--color-border-soft);
  border-radius: 12px; padding: 16px 18px;
  font-family: ui-sans-serif, system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 13.5px; line-height: 1.75; white-space: pre-wrap;
  max-height: 52vh; overflow: auto;
}
.view-refs ul { margin: 0; padding-left: 20px; }

.muted { color: var(--color-text-soft); }
.btn-danger-ghost {
  color: var(--color-danger); border-color: #fecaca; background: transparent;
}
.btn-danger-ghost:hover { background: #fef2f2; }
</style>
