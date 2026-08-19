<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { manualApi } from '@/api'
import { useProjectStore } from '@/stores/project'
import type { DocSection } from '@/types'

const store = useProjectStore()
const hotTopics = ['security-policy', 'NAT 策略', 'SSH 加固', '等保']
const activeTopic = ref('')
const searchQuery = ref('')
const results = ref<DocSection[]>([])
const searchLoading = ref(false)
const currentQuery = ref('')

async function doSearch() {
  const q = searchQuery.value.trim() || activeTopic.value
  currentQuery.value = q
  searchLoading.value = true
  try {
    results.value = await manualApi.search(store.currentProject.id, q)
    if (!results.value.length) {
      ElMessage.warning('未找到相关文档，已显示全部结果')
    }
  } finally {
    searchLoading.value = false
  }
}

function handleHotTopic(topic: string) {
  if (activeTopic.value === topic) {
    activeTopic.value = ''
    searchQuery.value = ''
  } else {
    activeTopic.value = topic
    searchQuery.value = topic
  }
  doSearch()
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') doSearch()
}

onMounted(async () => {
  await store.init()
  doSearch()
})
</script>

<template>
  <div>
    <div class="page-head">
      <div class="page-head-left">
        <div class="eyebrow">产品手册检索</div>
        <h1 class="h1">手册与知识库</h1>
        <p class="text-muted">全文检索产品手册，为配置注释和风险建议提供权威引用。</p>
      </div>
    </div>

    <div class="search-hero">
      <h2 class="h2">搜索产品文档</h2>
      <div class="search-bar">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--muted-foreground)"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input
          type="text"
          v-model="searchQuery"
          placeholder="输入关键字，例如 security-policy、acl、NAT…"
          @keydown="onKeydown"
        />
        <button class="btn btn-primary btn-sm" :disabled="searchLoading" @click="doSearch">
          {{ searchLoading ? '搜索中...' : '搜索' }}
        </button>
      </div>
      <div class="filter-bar" style="justify-content:center">
        <span class="text-muted" style="font-size:12px">热门：</span>
        <button
          v-for="t in hotTopics"
          :key="t"
          class="filter-chip"
          :class="{ active: activeTopic === t }"
          @click="handleHotTopic(t)"
        >{{ t }}</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3 class="card-title h4">检索结果</h3>
          <p class="card-desc">
            找到 {{ results.length }} 条
            <span v-if="currentQuery">与 <code class="text-mono">{{ currentQuery }}</code> 相关的段落</span>
            <span v-else>文档段落</span>
          </p>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:16px">
        <div v-for="d in results" :key="d.id" style="padding:16px;border:1px solid var(--border);border-radius:var(--radius-md)">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <span class="badge badge-info">{{ d.product }}</span>
            <span class="text-mono" style="font-size:12px;color:var(--muted-foreground)">{{ d.source }}</span>
          </div>
          <h4 style="margin:0 0 8px;font-size:15px;font-weight:600">{{ d.title }}</h4>
          <p class="text-serif" style="margin:0 0 8px;font-size:14px;line-height:1.65">{{ d.snippet }}</p>
          <a href="#" style="font-size:12px;font-weight:600;color:var(--primary)">查看原文 →</a>
        </div>
        <div v-if="results.length === 0" style="text-align:center;padding:40px;color:var(--text-500)">
          未找到匹配结果
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
</style>
