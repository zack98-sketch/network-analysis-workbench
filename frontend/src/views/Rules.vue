<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ruleApi } from '@/api'
import type { Rule } from '@/types'

const selectedRuleId = ref<string | number>('')
const rules = ref<Rule[]>([])
const newRuleDialogVisible = ref(false)
const newRuleForm = ref({
  name: '',
  domain: 'config',
  section: 'general',
  severity: 'medium' as Rule['severity'],
  enabled: true
})

const selectedRule = computed(() => {
  const r = rules.value.find(x => x.id === selectedRuleId.value)
  return r || rules.value[0]
})

async function loadRules() {
  try {
    rules.value = await ruleApi.list()
    if (rules.value.length && !selectedRuleId.value) {
      selectedRuleId.value = rules.value[0].id
    }
  } catch {}
}

function openNewRuleDialog() {
  newRuleForm.value = { name: '', domain: 'config', section: 'general', severity: 'medium', enabled: true }
  newRuleDialogVisible.value = true
}

async function confirmCreateRule() {
  if (!newRuleForm.value.name.trim()) {
    ElMessage.warning('请输入规则名称')
    return
  }
  try {
    const r = await ruleApi.create(newRuleForm.value)
    rules.value.unshift(r)
    selectedRuleId.value = r.id
    newRuleDialogVisible.value = false
  } catch {}
}

function severityLabel(s: string) {
  return s === 'high' ? '高危' : s === 'medium' ? '中危' : s === 'low' ? '低危' : '信息'
}

function severityColor(s: string) {
  if (s === 'high') return 'background:var(--error-100);color:var(--error-700)'
  if (s === 'medium') return 'background:var(--warning-50);color:#8a5a1a'
  if (s === 'low') return 'background:var(--success-50);color:var(--success-700)'
  return 'background:var(--info-50);color:var(--info-500)'
}

onMounted(loadRules)
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">告警与规则引擎</div>
        <h1 class="h1">规则编辑器</h1>
        <p class="text-muted">自定义关键字告警与异常行为检测规则，YAML 与表单双模式。</p>
      </div>
      <div class="page-head-actions">
        <button class="btn btn-primary btn-sm" @click="openNewRuleDialog">新建规则</button>
      </div>
    </div>

    <div class="two-col">
      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">规则列表</h3>
            <p class="card-desc">已启用 {{ rules.filter(r => r.enabled).length }} / {{ rules.length }} 条规则</p>
          </div>
        </div>
        <div class="file-list">
          <div
            v-for="r in rules"
            :key="r.id"
            class="file-row"
            @click="selectedRuleId = r.id"
            style="cursor:pointer"
            :class="{ 'rule-selected': selectedRuleId === r.id }"
          >
            <div class="file-info">
              <div class="file-icon" :style="severityColor(r.severity)">R</div>
              <div>
                <p class="file-name">{{ r.name }}</p>
                <p class="file-meta">{{ r.domain }} · {{ r.section }} · {{ severityLabel(r.severity) }}</p>
              </div>
            </div>
            <span class="badge" :class="r.enabled ? 'badge-p2' : 'badge-p3'">{{ r.enabled ? '已启用' : '已禁用' }}</span>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <div>
            <h3 class="card-title h4">规则 YAML</h3>
            <p class="card-desc">{{ selectedRule?.name || '选择一条规则查看详情' }}</p>
          </div>
          <div v-if="selectedRule" style="display:flex;gap:8px">
            <span class="badge" :style="severityColor(selectedRule.severity)">{{ severityLabel(selectedRule.severity) }}</span>
          </div>
        </div>
        <pre
          v-if="selectedRule"
          style="margin:0;padding:16px;background:var(--bg-200);border-radius:var(--radius-md);font-family:var(--font-mono);font-size:12px;line-height:1.7;overflow:auto;max-height:600px;color:var(--text-800)"
        ><code>{{ selectedRule.yaml || `- name: "示例规则"
  rule_type: config
  trigger:
    section_type: example
  severity: info
  description: "示例描述"` }}</code></pre>
        <div v-else style="text-align:center;padding:60px;color:var(--text-500)">
          请从左侧选择规则
        </div>
      </div>
    </div>

    <el-dialog v-model="newRuleDialogVisible" title="新建规则" width="500px">
      <el-form :model="newRuleForm" label-width="90px">
        <el-form-item label="规则名称">
          <el-input v-model="newRuleForm.name" placeholder="如：NAT 策略缺失检测" />
        </el-form-item>
        <el-form-item label="规则域">
          <el-select v-model="newRuleForm.domain">
            <el-option label="配置 (config)" value="config" />
            <el-option label="日志 (log)" value="log" />
            <el-option label="流量 (traffic)" value="traffic" />
          </el-select>
        </el-form-item>
        <el-form-item label="功能段">
          <el-input v-model="newRuleForm.section" placeholder="如：security_policy / ssh / snmp" />
        </el-form-item>
        <el-form-item label="严重等级">
          <el-select v-model="newRuleForm.severity">
            <el-option label="高危 (high)" value="high" />
            <el-option label="中危 (medium)" value="medium" />
            <el-option label="低危 (low)" value="low" />
            <el-option label="信息 (info)" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="newRuleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button class="btn btn-ghost btn-sm" @click="newRuleDialogVisible = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="confirmCreateRule">创建</button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.rule-selected {
  background: var(--primary-50);
  border-color: var(--primary-200);
}
</style>
