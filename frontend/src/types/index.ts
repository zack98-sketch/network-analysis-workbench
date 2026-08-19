export interface Project {
  id: string | number
  name: string
  status: 'active' | 'archived' | 'in-progress'
  materialsCount?: number
  risksCount?: number
  devicesCount?: number
  description?: string
  completedAt?: string
  created_at?: string
  updated_at?: string
}

export interface Material {
  id: string | number
  name: string
  type: 'log' | 'config' | 'manual' | 'training'
  format: string
  size?: string
  uploadedAt?: string
  rows?: number
  status: 'parsed' | 'indexed' | 'pending' | 'risk' | 'success' | 'failed'
  risksCount?: number
  file_name?: string
  file_type?: string
  file_size?: number
  parse_status?: string
  parser_type?: string
  device_name?: string
  created_at?: string
}

export interface LogEvent {
  id: string | number
  time: string
  type: 'connect' | 'auth' | 'command' | 'change' | 'disconnect'
  user?: string
  sourceIp?: string
  targetIp?: string
  targetPort?: number
  detail: string
}

export interface ConfigItem {
  id: string | number
  section: string
  lineNo: number
  key: string
  value: string
  annotation?: string
  risk?: boolean
  section_type?: string
  section_name?: string
  raw_line?: string
  indent_level?: number
  doc_ref?: string
  is_risk?: boolean
  risk_level?: string
}

export interface RiskFinding {
  id: string | number
  severity: 'p0' | 'p1' | 'p2' | 'p3' | 'high' | 'medium' | 'low' | 'critical' | 'info'
  category: string
  description: string
  source: string
  remediation?: string
  status: '待处理' | '待确认' | '建议' | '记录' | 'open' | 'confirmed' | 'mitigated' | 'dismissed'
  risk_code?: string
  source_ref?: string
  remediation_cmd?: string
  standard_ref?: string
  material_id?: number
  created_at?: string
}

export interface TopoNode {
  id: string | number
  label: string
  type: 'firewall' | 'switch' | 'host'
  left: string
  top: string
  ip?: string
  iface?: string
  source?: string
  node_type?: string
  name?: string
  ip_address?: string
  interface_desc?: string
  pos_x?: number
  pos_y?: number
  source_material?: string
}

export interface TopoEdge {
  from: string
  to: string
  source_node?: number
  target_node?: number
  edge_type?: string
  bandwidth?: string
  source_material?: string
}

export interface Rule {
  id: string | number
  name: string
  domain: string
  section: string
  severity: 'high' | 'medium' | 'low' | 'info'
  enabled: boolean
  yaml?: string
  rule_code?: string
  rule_type?: string
  description?: string
  pattern?: string
  remediation?: string
  standard_ref?: string
}

export interface DocSection {
  id: string | number
  title: string
  product: string
  source: string
  snippet: string
  section_path?: string
  content_text?: string
  config_keywords?: string
  page_no?: number
  material_id?: number
}
