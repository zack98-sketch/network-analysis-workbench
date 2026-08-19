import axios, { type AxiosInstance, type InternalAxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import type {
  Project,
  Material,
  RiskFinding,
  LogEvent,
  ConfigItem,
  TopoNode,
  TopoEdge,
  Rule,
  DocSection
} from '@/types'

const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

api.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    const msg = error?.response?.data?.detail || error.message || '请求失败'
    if (!error?.config?.silent) {
      ElMessage.error(msg)
    }
    return Promise.reject(error)
  }
)

/** 将后端返回的 snake_case 材料对象映射为前端 Material 格式 */
function mapMaterial(raw: any): Material {
  const parseStatus = raw.parse_status || raw.status || 'pending'
  // 保留后端更丰富的 parse 状态：pending/parsing/success/failed 直接透传；parsed/indexed/risk 兼容
  const direct = String(parseStatus || '').toLowerCase()
  let finalStatus: Material['status']
  if (['pending', 'parsing', 'success', 'failed', 'parsed', 'indexed', 'risk'].includes(direct)) {
    finalStatus = direct as any
  } else {
    const legacyMap: Record<string, Material['status']> = {
      pending: 'pending',
      success: 'success',
      parsed: 'parsed',
      failed: 'failed',
      indexed: 'indexed',
      risk: 'risk'
    }
    finalStatus = legacyMap[direct] || 'pending'
  }
  return {
    id: raw.id,
    name: raw.file_name || raw.name || '未命名',
    type: raw.file_type || raw.type || 'log',
    format: (raw.file_name || raw.name || '').split('.').pop()?.toUpperCase() || 'TXT',
    size: raw.file_size ?? raw.size,
    uploadedAt: raw.created_at || raw.uploadedAt || '',
    rows: raw.rows ?? raw.rows_parsed,
    status: finalStatus,
    parse_status: parseStatus,
    parser_type: raw.parser_type,
    device_name: raw.device_name,
    deviceName: raw.device_name,
    file_name: raw.file_name,
    file_type: raw.file_type,
    file_size: raw.file_size,
    parse_progress: Number(raw.parse_progress ?? 0) || 0,
    progress: Number(raw.parse_progress ?? 0) || 0,
    parse_message: raw.parse_message,
    message: raw.parse_message,
    rows_parsed: Number(raw.rows_parsed ?? 0) || 0,
    risksCount: raw.risks_count || 0,
  }
}

function mapProject(raw: any): Project {
  return {
    id: raw.id,
    name: raw.name || '',
    status: raw.status || 'active',
    materialsCount: raw.materials_count || 0,
    risksCount: raw.risks_count || 0,
    description: raw.description,
    created_at: raw.created_at,
    updated_at: raw.updated_at
  }
}

function mapRisk(raw: any): RiskFinding {
  const sevMap: Record<string, RiskFinding['severity']> = {
    critical: 'p0', high: 'p0',
    medium: 'p2', low: 'p3',
    info: 'p3'
  }
  const statusMap: Record<string, RiskFinding['status']> = {
    open: '待处理', confirmed: '待确认',
    mitigated: '建议', dismissed: '记录'
  }
  return {
    id: raw.id,
    severity: sevMap[raw.severity] || raw.severity || 'p2',
    category: raw.category || raw.domain || '',
    description: raw.description || '',
    source: raw.source_ref || raw.source || '',
    remediation: raw.remediation_cmd || raw.remediation || '',
    risk_code: raw.risk_code,
    status: statusMap[raw.status] || raw.status || '待处理',
    standard_ref: raw.standard_ref,
    material_id: raw.material_id,
    created_at: raw.created_at
  }
}

function mapRule(raw: any): Rule {
  return {
    id: raw.id || raw.rule_code || '',
    name: raw.name || raw.title || '',
    domain: raw.domain || raw.rule_type || '',
    section: raw.section || raw.category || '',
    severity: raw.severity || 'medium',
    enabled: raw.enabled !== false,
    yaml: raw.yaml || raw.pattern || '',
    rule_code: raw.rule_code,
    rule_type: raw.rule_type,
    description: raw.description,
    remediation: raw.remediation,
    standard_ref: raw.standard_ref
  }
}

export const projectApi = {
  list: async (): Promise<Project[]> => {
    const data = await api.get('/projects') as any[]
    return data.map(mapProject)
  },

  get: async (id: string | number): Promise<Project> => {
    const data = await api.get(`/projects/${id}`)
    return mapProject(data)
  },

  create: async (data: Partial<Project>): Promise<Project> => {
    const res = await api.post('/projects', {
      name: data.name,
      description: data.description,
      status: data.status || 'active'
    })
    return mapProject(res)
  },

  update: async (id: string | number, data: Partial<Project>): Promise<Project> => {
    const res = await api.put(`/projects/${id}`, {
      name: data.name,
      description: data.description,
      status: data.status
    })
    return mapProject(res)
  },

  remove: async (id: string | number): Promise<void> => {
    await api.delete(`/projects/${id}`)
  },

  summary: async (id: string | number) => {
    return await api.get(`/projects/${id}/summary`)
  }
}

export const materialApi = {
  list: async (projectId: string | number): Promise<Material[]> => {
    const data = await api.get(`/projects/${projectId}/materials`) as any[]
    return data.map(mapMaterial)
  },

  get: async (id: string | number): Promise<Material> => {
    const data = await api.get(`/materials/${id}`)
    return mapMaterial(data)
  },

  upload: async (
    formData: FormData,
    onUploadProgress?: (progressEvent: any) => void
  ): Promise<Material> => {
    const res = await api.post('/materials', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress
    })
    return mapMaterial(res)
  },

  remove: async (id: string | number): Promise<void> => {
    await api.delete(`/materials/${id}`)
  },

  reparse: async (id: string | number): Promise<Material> => {
    const res = await api.post(`/materials/${id}/reparse`)
    return mapMaterial(res)
  },

  analyzeAll: async (projectId: string | number) => {
    return await api.post(`/projects/${projectId}/analyze`)
  },

  progress: async (projectId: string | number) => {
    return await api.get(`/projects/${projectId}/analyze/progress`)
  }
}

export const manualApi = {
  list: async (params?: { q?: string; category?: string; mapping_target?: string; vendor?: string; limit?: number }) => {
    return await api.get('/dictionaries/manuals', { params })
  },
  categories: async () => {
    return await api.get('/dictionaries/manuals/categories')
  },
  get: async (id: number | string) => {
    return await api.get(`/dictionaries/manuals/${id}`)
  },
  create: async (payload: Record<string, any>) => {
    return await api.post('/dictionaries/manuals', payload)
  },
  update: async (id: number | string, payload: Record<string, any>) => {
    return await api.put(`/dictionaries/manuals/${id}`, payload)
  },
  remove: async (id: number | string) => {
    return await api.delete(`/dictionaries/manuals/${id}`)
  },
  /** 解析依据配对：把 raw_line/配置项/日志原文传给后端匹配字典条目 */
  pair: async (payload: { q: string; mapping_target?: 'config_parser' | 'log_parser' | 'both' }) => {
    return await api.post('/dictionaries/manuals/_pair', payload)
  }
}

export const logApi = {
  events: async (materialId: string | number, params?: Record<string, any>): Promise<LogEvent[]> => {
    const data = await api.get(`/materials/${materialId}/events`, { params }) as any
    // Backend returns PaginatedLogs {items, total, page, page_size}; tolerate array shape too.
    const items: any[] = Array.isArray(data) ? data : (data?.items || [])
    return items.map((e: any) => ({
      id: e.id,
      time: e.timestamp || e.time || '',
      type: e.event_type || e.type || 'command',
      user: e.user,
      sourceIp: e.source_ip,
      targetIp: e.target_ip,
      targetPort: e.target_port,
      detail: (e.detail_json && (e.detail_json.value || e.detail_json.detail)) || e.raw_line || e.detail || ''
    }))
  },

  timeline: async (projectId: string | number): Promise<any> => {
    return await api.get(`/projects/${projectId}/logs/timeline`)
  },

  correlation: async (projectId: string | number) => {
    return await api.get(`/projects/${projectId}/logs/correlation`)
  }
}

export const configApi = {
  tree: async (materialId: string | number): Promise<ConfigItem[]> => {
    const data = await api.get(`/materials/${materialId}/config/tree`) as any[]
    return data.map((c: any) => ({
      id: c.id || c.line_no || 0,
      section: c.section_type || c.section || '',
      lineNo: c.line_no || 0,
      key: c.key || '',
      value: c.value || '',
      annotation: c.annotation || '',
      risk: c.is_risk || false,
      section_type: c.section_type,
      section_name: c.section_name,
      raw_line: c.raw_line,
      indent_level: c.indent_level,
      doc_ref: c.doc_ref,
      is_risk: c.is_risk,
      risk_level: c.risk_level
    }))
  },

  diff: async (materialId: string | number, compareWith: string) => {
    return await api.get(`/materials/${materialId}/config/diff`, {
      params: { compare_with: compareWith }
    })
  }
}

/** 遗留手册接口：检索项目内用户上传的材料文档（DocIndex） */
export const docApi = {
  search: async (projectId: string | number, query: string): Promise<DocSection[]> => {
    const data = await api.get(`/projects/${projectId}/manuals/search`, {
      params: { q: query }
    }) as any[]
    return (Array.isArray(data) ? data : []).map((d: any) => ({
      id: d.id || 0,
      title: d.title || '',
      product: d.product || '',
      source: d.source || '',
      snippet: d.content_text || d.snippet || '',
      section_path: d.section_path,
      content_text: d.content_text,
      config_keywords: d.config_keywords,
      page_no: d.page_no,
      material_id: d.material_id
    }))
  },

  sections: async (materialId: string | number): Promise<DocSection[]> => {
    const data = await api.get(`/materials/${materialId}/doc-sections`) as any[]
    return data.map((d: any) => ({
      id: d.id || 0,
      title: d.title || '',
      product: '',
      source: '',
      snippet: d.content_text || ''
    }))
  }
}

export const riskApi = {
  list: async (projectId: string | number, params?: Record<string, any>): Promise<RiskFinding[]> => {
    const data = await api.get(`/projects/${projectId}/risks`, { params }) as any[]
    return data.map(mapRisk)
  },

  recheck: async (projectId: string | number): Promise<RiskFinding[]> => {
    const data = await api.post(`/projects/${projectId}/risks/recheck`) as any[]
    return data.map(mapRisk)
  },

  updateStatus: async (id: string | number, status: string): Promise<RiskFinding> => {
    const res = await api.patch(`/risks/${id}`, { status })
    return mapRisk(res)
  }
}

export const auditApi = {
  /** 项目范围配置核查 (POST /projects/{id}/audit/config) */
  configAudit: async (projectId: string | number) => {
    return await api.post(`/projects/${projectId}/audit/config`)
  },
  /** 项目范围流量审核 (POST /projects/{id}/audit/traffic) */
  trafficAudit: async (projectId: string | number) => {
    return await api.post(`/projects/${projectId}/audit/traffic`)
  },
  /** 项目轻量汇总卡片 (GET /projects/{id}/audit/summary) */
  summary: async (projectId: string | number) => {
    return await api.get(`/projects/${projectId}/audit/summary`)
  }
}

export const topologyApi = {
  get: async (projectId: string | number): Promise<{ nodes: TopoNode[]; edges: TopoEdge[] }> => {
    const data = await api.get(`/projects/${projectId}/topology`) as any
    const nodes: TopoNode[] = (data.nodes || []).map((n: any) => ({
      id: n.id,
      label: n.name || n.label || '',
      type: n.node_type || n.type || 'host',
      left: n.pos_x != null ? String(n.pos_x) : (n.left || '50%'),
      top: n.pos_y != null ? String(n.pos_y) : (n.top || '50%'),
      ip: n.ip_address || n.ip,
      iface: n.interface_desc || n.iface,
      source: n.source_material || n.source || '',
      node_type: n.node_type,
      name: n.name,
      ip_address: n.ip_address,
      pos_x: n.pos_x,
      pos_y: n.pos_y
    }))
    const edges: TopoEdge[] = (data.edges || []).map((e: any) => ({
      from: String(e.source_node ?? e.from ?? ''),
      to: String(e.target_node ?? e.to ?? ''),
      source_node: e.source_node,
      target_node: e.target_node,
      edge_type: e.edge_type,
      bandwidth: e.bandwidth,
      source_material: e.source_material
    }))
    return { nodes, edges }
  },

  addNode: async (projectId: string | number, data: Partial<TopoNode>): Promise<TopoNode> => {
    const res = await api.post(`/projects/${projectId}/topology/nodes`, {
      name: data.label,
      node_type: data.type,
      ip_address: data.ip,
      interface_desc: data.iface,
      pos_x: parseFloat(data.left as string) || 0,
      pos_y: parseFloat(data.top as string) || 0
    }) as any
    return {
      id: res.id,
      label: data.label || '',
      type: data.type || 'host',
      left: data.left || '50%',
      top: data.top || '50%',
      ip: data.ip,
      iface: data.iface,
      source: data.source || ''
    }
  },

  addEdge: async (projectId: string | number, data: TopoEdge): Promise<TopoEdge> => {
    const res = await api.post(`/projects/${projectId}/topology/edges`, {
      source_node: parseInt(data.from),
      target_node: parseInt(data.to),
      edge_type: data.edge_type || 'physical'
    }) as any
    return { ...data, from: String(res.source_node ?? data.from), to: String(res.target_node ?? data.to) }
  },

  updateNodePosition: async (nodeId: string | number, x: number, y: number): Promise<TopoNode> => {
    return await api.patch(`/topology/nodes/${nodeId}`, { pos_x: x, pos_y: y })
  },

  removeNode: async (nodeId: string | number): Promise<void> => {
    await api.delete(`/topology/nodes/${nodeId}`)
  },

  removeEdge: async (edgeId: string | number): Promise<void> => {
    await api.delete(`/topology/edges/${edgeId}`)
  },

  regenerate: async (projectId: string | number): Promise<{ nodes: TopoNode[]; edges: TopoEdge[] }> => {
    return await api.post(`/projects/${projectId}/topology/regenerate`)
  }
}

export const ruleApi = {
  list: async (): Promise<Rule[]> => {
    const data = await api.get('/rules') as any[]
    return data.map(mapRule)
  },

  get: async (id: string | number): Promise<Rule> => {
    const data = await api.get(`/rules/${id}`)
    return mapRule(data)
  },

  create: async (data: Partial<Rule>): Promise<Rule> => {
    const res = await api.post('/rules', data)
    return mapRule(res)
  },

  update: async (id: string | number, data: Partial<Rule>): Promise<Rule> => {
    const res = await api.put(`/rules/${id}`, data)
    return mapRule(res)
  },

  remove: async (id: string | number): Promise<void> => {
    await api.delete(`/rules/${id}`)
  },

  templates: async () => {
    return await api.get('/rules/templates')
  }
}

export const reportApi = {
  generate: async (projectId: string | number, format: string): Promise<any> => {
    return await api.post(`/projects/${projectId}/reports`, { format })
  },

  list: async (projectId: string | number): Promise<any[]> => {
    return await api.get(`/projects/${projectId}/reports`) as any[]
  },

  download: async (reportId: string | number) => {
    window.open(`/api/v1/reports/${reportId}/download`, '_blank')
    return true
  }
}

export default api
