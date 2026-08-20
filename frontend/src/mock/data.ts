import type { Material, RiskFinding, LogEvent, ConfigItem, TopoNode, TopoEdge, Project, Rule, DocSection } from '@/types'

export const materials: Material[] = [
  { id: 'm1', name: 'demo_traffic_flow.csv', type: 'log', format: 'CSV', size: '24.8 MB', uploadedAt: '2026-08-19 14:30', rows: 102341, status: 'parsed' },
  { id: 'm2', name: 'demo_firewall_config.cfg', type: 'config', format: 'CFG', size: '18 KB', uploadedAt: '2026-08-19 11:02', rows: 612, status: 'risk', risksCount: 2 },
  { id: 'm3', name: 'demo_fw_2026-08-17_20_08_36.log', type: 'log', format: 'LOG', size: '86 KB', uploadedAt: '2026-08-18 09:15', rows: 1204, status: 'parsed' },
  { id: 'm4', name: 'demo_fw_2026-08-18_22_14_05.log', type: 'log', format: 'LOG', size: '72 KB', uploadedAt: '2026-08-18 22:20', rows: 986, status: 'parsed' },
  { id: 'm5', name: 'demo_ssh_session.log', type: 'log', format: 'LOG', size: '54 KB', uploadedAt: '2026-08-18 10:32', rows: 712, status: 'parsed' },
  { id: 'm6', name: 'demo_core_switch_syslog.log', type: 'log', format: 'LOG', size: '1.2 MB', uploadedAt: '2026-08-17 18:05', rows: 8532, status: 'parsed' },
  { id: 'm7', name: 'demo_log_auditor_product_doc.chm', type: 'manual', format: 'CHM', size: '12.4 MB', uploadedAt: '2026-08-18 16:20', status: 'indexed' },
  { id: 'm8', name: 'demo_security_training_chapter1.pdf', type: 'training', format: 'PDF', size: '28.6 MB', uploadedAt: '2026-08-17 10:08', status: 'pending' },
  { id: 'm9', name: 'demo_firewall_config_guide.pdf', type: 'manual', format: 'PDF', size: '15.2 MB', uploadedAt: '2026-08-16 15:40', status: 'indexed' },
  { id: 'm10', name: 'demo_compliance_requirements.pdf', type: 'training', format: 'PDF', size: '8.4 MB', uploadedAt: '2026-08-15 09:10', status: 'pending' },
  { id: 'm11', name: 'demo_command_reference_manual.pdf', type: 'manual', format: 'PDF', size: '32.1 MB', uploadedAt: '2026-08-14 14:22', status: 'indexed' },
  { id: 'm12', name: 'demo_benchmark_network_devices.pdf', type: 'training', format: 'PDF', size: '4.8 MB', uploadedAt: '2026-08-13 11:50', status: 'pending' },
  { id: 'm13', name: 'demo_security_lab_manual.pdf', type: 'training', format: 'PDF', size: '22.7 MB', uploadedAt: '2026-08-12 16:18', status: 'pending' },
  { id: 'm14', name: 'demo_compliance_guidelines.pdf', type: 'training', format: 'PDF', size: '6.3 MB', uploadedAt: '2026-08-11 10:05', status: 'pending' }
]

export const risks: RiskFinding[] = [
  {
    id: 'RISK-001',
    severity: 'p0',
    category: '安全策略',
    description: '策略 demo-rule action=permit 但未指定 source-zone 与 source-address',
    source: 'demo_firewall_config.cfg:607',
    remediation: 'source-zone trust\nsource-address 10.0.0.0/24',
    status: '待处理'
  },
  {
    id: 'RISK-002',
    severity: 'p0',
    category: 'SSH',
    description: 'SSH 兼容 SSH1.x 并允许弱密钥交换算法 diffie-hellman-group1',
    source: 'demo_firewall_config.cfg:523',
    remediation: 'undo ssh server compatible-ssh1x enable',
    status: '待处理'
  },
  {
    id: 'RISK-003',
    severity: 'p1',
    category: '管理平面',
    description: 'Telnet 服务未禁用，存在明文传输管理流量风险',
    source: 'demo_firewall_config.cfg:498',
    remediation: 'undo telnet server enable',
    status: '待处理'
  },
  {
    id: 'RISK-004',
    severity: 'p1',
    category: '访问控制',
    description: '本地用户权限级别为 15 且未绑定源 IP 白名单',
    source: 'demo_firewall_config.cfg:412',
    remediation: 'service-type ssh terminal\nacl 2000 inbound',
    status: '待处理'
  },
  {
    id: 'RISK-005',
    severity: 'p1',
    category: '日志审计',
    description: '非工作时间（22:00-06:00）存在成功登录行为',
    source: 'demo_fw.log',
    remediation: '—',
    status: '待确认'
  },
  {
    id: 'RISK-006',
    severity: 'p2',
    category: 'SNMP',
    description: 'SNMP 团体字使用默认 public，建议改为复杂字符串',
    source: 'demo_firewall_config.cfg:567',
    remediation: 'snmp-agent community read ComplexString',
    status: '建议'
  },
  {
    id: 'RISK-007',
    severity: 'p3',
    category: '配置冗余',
    description: '存在未引用的 ACL 2001，建议清理',
    source: 'demo_firewall_config.cfg:301',
    remediation: '—',
    status: '记录'
  }
]

export const logEvents: LogEvent[] = [
  { id: 'e1', time: '20:08:12', type: 'connect', sourceIp: '10.0.0.10', targetIp: '10.0.0.1', targetPort: 22, detail: '源 10.0.0.10 → 目标 10.0.0.1:22' },
  { id: 'e2', time: '20:08:15', type: 'auth', user: 'demo-user', sourceIp: '10.0.0.10', detail: '用户 demo-user 通过密码认证登录' },
  { id: 'e3', time: '20:09:03', type: 'command', user: 'demo-user', sourceIp: '10.0.0.10', detail: 'display security-policy all' },
  { id: 'e4', time: '20:11:47', type: 'change', user: 'demo-user', sourceIp: '10.0.0.10', detail: 'security-policy rule name demo-rule，命中 M5 规则' },
  { id: 'e5', time: '20:14:22', type: 'disconnect', user: 'demo-user', sourceIp: '10.0.0.10', detail: '会话结束，总时长 6 分 10 秒' }
]

export const configTree: ConfigItem[] = [
  { id: 'c1', section: 'security-policy', lineNo: 605, key: 'rule name', value: 'demo-rule', annotation: '定义一条名为 demo-rule 的安全策略规则' },
  { id: 'c2', section: 'security-policy', lineNo: 607, key: 'source-zone', value: '—', annotation: '⚠ 未指定源安全区域，存在全区域放行风险', risk: true },
  { id: 'c3', section: 'security-policy', lineNo: 608, key: 'source-address', value: '—', annotation: '⚠ 未限定源地址，任何源均可命中该策略', risk: true },
  { id: 'c4', section: 'security-policy', lineNo: 609, key: 'destination-address', value: 'any', annotation: '目的地址为 any，允许访问任意目标' },
  { id: 'c5', section: 'security-policy', lineNo: 610, key: 'action', value: 'permit', annotation: '动作为允许通过' },
  { id: 'c6', section: 'security-policy', lineNo: 612, key: 'service', value: 'any', annotation: '服务对象为 any，放行所有端口与协议' },
  { id: 'c7', section: 'ssh', lineNo: 523, key: 'ssh server compatible-ssh1x enable', value: 'enable', annotation: '⚠ 兼容 SSH1.x，建议使用 SSH2 并禁用弱算法', risk: true },
  { id: 'c8', section: 'ssh', lineNo: 524, key: 'ssh server port', value: '22', annotation: 'SSH 服务监听默认端口 22' }
]

export const topoNodes: TopoNode[] = [
  { id: 'n1', label: 'Demo-PC', type: 'host', left: '14%', top: '42%', ip: '10.0.0.10', source: 'SSH 会话日志' },
  { id: 'n2', label: 'Demo-FW', type: 'firewall', left: '40%', top: '42%', ip: '10.0.0.1', iface: 'Vlanif100', source: 'demo_firewall_config.cfg' },
  { id: 'n3', label: 'Demo-SW', type: 'switch', left: '78%', top: '22%', ip: '10.0.0.2', iface: 'Vlanif10', source: '接口 description to-Demo-FW' },
  { id: 'n4', label: 'Server-A', type: 'host', left: '78%', top: '42%', ip: '10.0.0.20', source: 'CSV 流量目的 IP' },
  { id: 'n5', label: 'Server-B', type: 'host', left: '78%', top: '62%', ip: '10.0.0.21', source: 'CSV 流量目的 IP' }
]

export const topoEdges: TopoEdge[] = [
  { from: 'n1', to: 'n2' },
  { from: 'n2', to: 'n3' },
  { from: 'n2', to: 'n4' },
  { from: 'n2', to: 'n5' }
]

export const projects: Project[] = [
  {
    id: 'prod-2026q3',
    name: '生产网边界审计2026-Q3',
    status: 'active',
    materialsCount: 14,
    risksCount: 7,
    devicesCount: 2,
    description: '审计生产网边界防火墙与核心交换机的配置与访问行为。'
  },
  {
    id: 'office-baseline',
    name: '办公网安全基线检查',
    status: 'archived',
    materialsCount: 8,
    risksCount: 12,
    devicesCount: 6,
    description: '针对办公网接入交换机与无线控制器的基线核查。',
    completedAt: '2026-07'
  },
  {
    id: 'dc-refresh',
    name: '数据中心出口改造评估',
    status: 'in-progress',
    materialsCount: 22,
    risksCount: 5,
    devicesCount: 4,
    description: '评估新防火墙上线前后的策略一致性与风险变化。',
    completedAt: '2026-06'
  }
]

export const rules: Rule[] = [
  {
    id: 'r1',
    name: '宽松安全策略告警',
    domain: 'config',
    section: 'security_policy',
    severity: 'high',
    enabled: true,
    yaml: `- name: "宽松安全策略告警"
  rule_type: config
  trigger:
    section_type: security_policy
    conditions:
      - key: action
        value: permit
      - key: source_address
        value: null
  severity: high
  description: "安全策略 action=permit 但未指定 source-address，存在全放行风险"
  standard_ref: "等保2.0三级 8.1.3.2 访问控制"`
  },
  {
    id: 'r2',
    name: 'SSH 弱算法检测',
    domain: 'config',
    section: 'ssh',
    severity: 'high',
    enabled: true
  },
  {
    id: 'r3',
    name: '非工作时间登录告警',
    domain: 'log',
    section: 'connect',
    severity: 'medium',
    enabled: true
  },
  {
    id: 'r4',
    name: 'Telnet 服务启用检测',
    domain: 'config',
    section: 'telnet',
    severity: 'medium',
    enabled: true
  },
  {
    id: 'r5',
    name: 'SNMP 默认团体字检测',
    domain: 'config',
    section: 'snmp',
    severity: 'low',
    enabled: true
  },
  {
    id: 'r6',
    name: '未引用 ACL 冗余检测',
    domain: 'config',
    section: 'acl',
    severity: 'info',
    enabled: true
  }
]

export const docSections: DocSection[] = [
  {
    id: 'd1',
    title: 'security-policy 配置说明',
    product: 'Demo-FW-Series',
    source: 'demo_cfg_security.html',
    snippet: 'security-policy 用于配置安全策略。配置时请明确指定源安全区域、目的安全区域、源地址、目的地址、服务与动作，避免使用 any 导致过度放行。'
  },
  {
    id: 'd2',
    title: 'rule name 命令参考',
    product: 'Demo-FW-Series',
    source: 'demo_security_command.html',
    snippet: '命令 rule name 用于创建安全策略规则。规则按配置顺序匹配，建议将精确规则置于宽松规则之前。'
  }
]
