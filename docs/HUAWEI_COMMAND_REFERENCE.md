# 华为防火墙与交换机常用查询命令参考

> 本手册结合网络分析工作台（Network Analysis Workbench）的实际审计与排障场景整理而成。
> 命令清单来源于华为官方产品文档：
>
> - **ASG 应用安全网关（防火墙）**：HUAWEI ASG-D, ASG-E, ASG5000 V300R022C00 产品文档 — “显示类命令”
>   来源：<https://support.huawei.com/hedex/hdx.do?docid=EDOC1100313731&id=ZH-CN_TOPIC_0000001314006092>
> - **S12700 园区核心交换机**：S12700, S12700E V200R019C10 产品文档 — “查看设备状态的命令”
>   来源：<https://support.huawei.com/hedex/hdx.do?docid=EDOC1100126513&id=ZH-CN_CONCEPT_0177113659>
>
> 本文件同时作为系统“操作手册字典库（Manuals）”的离线参考资料：每一条命令均会在前端「操作手册 / 解析依据配对」功能中可被检索。

---

## 一、文档来源信息

| 项目     | 防火墙（安全网关）                                | 交换机                                              |
| -------- | ------------------------------------------------- | --------------------------------------------------- |
| 设备型号 | HUAWEI ASG-D / ASG-E / ASG5000                    | HUAWEI S12700 / S12700E                             |
| 软件版本 | V300R022C00                                       | V200R019C10                                         |
| 文档 ID  | EDOC1100313731                                    | EDOC1100126513                                      |
| 章节     | 命令参考 → 显示类命令                             | 设备管理命令 → 查看设备状态的命令                   |
| 用途     | 安全策略 / 会话 / NAT / VPN / HA 等运行状态查询   | 设备硬件、CPU/内存、温度、风扇、电源、版本等状态查询 |

---

## 二、防火墙（ASG 系列）常用查询命令

适用于 ASG-D / ASG-E / ASG5000 V300R022C00 及同系列版本，覆盖**地址/策略/会话/路由/VPN/HA/接口/硬件**等审计高频场景。

### 2.1 系统与版本

| 命令                  | 说明                         | 审计用途                                |
| --------------------- | ---------------------------- | --------------------------------------- |
| `display version`      | 查看设备软件版本与启动信息   | 核对版本号、补丁是否满足合规基线        |
| `display date`         | 查看系统时间                 | 日志关联、事件时间轴校准                |
| `display current-config` | 查看当前生效配置             | 配置快照、配置解析依据（config_parser）|
| `display config-list`  | 查看配置变更列表             | 变更审计、回滚分析                     |

### 2.2 地址与安全策略

| 命令                                | 说明                          | 审计用途                          |
| ----------------------------------- | ----------------------------- | --------------------------------- |
| `display address`                   | 查看地址对象                  | 核对地址对象定义一致性            |
| `display address-group`             | 查看地址组                    | 策略引用核查                      |
| `display audit_policy accelerate`   | 查看审计策略加速状态          | 策略命中性能评估                  |
| `display nat-policy`                | 查看 NAT 策略                 | NAT 转换规则审计（合规/外联分析） |
| `display policy accelerate`         | 查看安全策略加速状态          | 策略匹配性能评估                  |
| `display qos-profile`               | 查看 QoS Profile              | 带宽限速核查                      |
| `display qos-profile statistics`    | 查看 QoS 统计                 | 流量限速命中分析                  |
| `display qos-profile NAME sfq`      | 查看指定 QoS 的 SFQ           | 单策略细化排查                    |

### 2.3 会话与流量

| 命令                                         | 说明                          | 审计用途                          |
| -------------------------------------------- | ----------------------------- | --------------------------------- |
| `display ip session`                         | 查看 IPv4 会话表               | 会话日志（log_parser）关键字依据  |
| `display statistics`                          | 查看流量统计                   | 流量分析（/logs/traffic）数据源   |
| `display flowfast state`                       | 查看 FlowFast 状态             | 转发加速状态评估                  |
| `display tcpstack connection all`              | 查看所有 TCP 连接              | TCP 会话排障                      |
| `display tcpstack connection source-ip <IP>`   | 按源 IP 查看 TCP 连接          | 溯源分析、横向移动检测            |
| `display tcpstack switch`                       | 查看 TCP 协议栈优化开关        | 协议优化审计                      |
| `display sslproxy-optimize switch`              | 查看 SSL 代理优化开关          | SSL 解密性能核查                   |
| `display https-portal new-connection detail`   | 查看 HTTPS Portal 新连接详情  | Portal 认证流量排查                |

### 2.4 路由与接口

| 命令                       | 说明                       | 审计用途                          |
| -------------------------- | -------------------------- | --------------------------------- |
| `display ip route`         | 查看 IPv4 路由表           | 路由黑洞、外联路径分析            |
| `display ip ospf`          | 查看 OSPF 邻居与状态        | 路由协议状态审计                  |
| `display ip rip`            | 查看 RIP 路由                | 路由协议状态审计                  |
| `display ip interface brief`| 查看接口 IP 简要信息       | 接口与 IP 对应关系审计            |
| `display interface`         | 查看接口详细信息           | 接口流量、错包统计                |
| `display arp`               | 查看 ARP 表                 | ARP 欺骗、IP/MAC 绑定核查         |
| `display ipv6`              | 查看 IPv6 相关信息          | IPv6 资产梳理                     |

### 2.5 VPN（IKE / IPSec）

| 命令              | 说明                          | 审计用途                          |
| ----------------- | ----------------------------- | --------------------------------- |
| `display ike sa`  | 查看 IKE SA                   | VPN 隧道状态、密钥协商审计        |
| `display ipsec sa`| 查看 IPSec SA                 | IPSec 隧道状态、加密套件合规核查  |

### 2.6 用户与认证

| 命令                                            | 说明                          | 审计用途                          |
| ----------------------------------------------- | ----------------------------- | --------------------------------- |
| `display user-manage online-user`               | 查看在线用户                   | 在线会话、并发用户审计            |
| `display user-auth whitelist cache`             | 查看用户认证白名单缓存         | 认证白名单核查                    |
| `display user-share`                             | 查看用户共享信息               | 共享账号检测                      |
| `display user-waa`                               | 查看用户 WAA                  | Web 行为审计用户                  |
| `display ldap-auth easy-name-match switch`       | 查看 LDAP 认证易名匹配开关     | LDAP 认证配置核查                 |

### 2.7 HA 与硬件

| 命令                                  | 说明                          | 审计用途                          |
| ------------------------------------- | ----------------------------- | --------------------------------- |
| `display ha config diff`              | 查看 HA 配置差异               | 双机配置一致性核查（高危）        |
| `display ha state`                    | 查看 HA 状态                   | 主备状态、脑裂检测                |
| `display hardware info`               | 查看硬件信息                   | 硬件资产盘点                      |
| `display capacity`                    | 查看设备容量                   | 资源使用容量评估                  |
| `display cpu usage`                   | 查看 CPU 使用率                | 性能监控                          |
| `display memory-usage`                | 查看内存使用率                 | 性能监控                          |
| `display dp drop statistics`          | 查看数据面丢包统计             | 数据面丢包溯源                    |
| `display dp memory`                   | 查看数据面内存                 | 数据面资源监控                    |
| `display dp state`                    | 查看数据面状态                 | 转发引擎状态                      |
| `display ip defend drop info`         | 查看 IP 防御丢包信息           | 抗攻击命中分析                    |
| `display log statistics`              | 查看日志统计                   | 日志完整性核查（log_parser）     |
| `display bridge-group`                | 查看桥组                       | 二层桥接核查                      |
| `display application bypass info`     | 查看应用绕过信息               | 应用识别绕过审计                  |
| `display lldp local-information`     | 查看 LLDP 本地信息             | 邻居发现                          |
| `display lldp neighbor-information`   | 查看 LLDP 邻居信息             | 拓扑发现（topology_engine）依据  |
| `display lldp statistics`            | 查看 LLDP 统计                 | 邻居发现健康度                    |
| `display audit_policy accelerate`     | 查看审计策略加速状态           | 策略命中性能                      |
| `display http_file_cache statistic info` | 查看 HTTP 文件缓存统计      | 缓存命中分析                      |
| `display update-http-proxy`            | 查看 HTTP 代理更新             | 代理更新配置核查                  |
| `display debug all`                    | 查看调试开关                  | 调试残留检查（合规风险）          |

---

## 三、交换机（S12700 / S12700E）常用查询命令

适用于 S12700 / S12700E V200R019C10 及同系列版本，聚焦**设备硬件与运行状态**审计。

### 3.1 系统与版本

| 命令                              | 说明                          | 审计用途                          |
| --------------------------------- | ----------------------------- | --------------------------------- |
| `display version`                 | 查看设备软件版本               | 版本合规、补丁核查                |
| `display version`（集群）          | 集群系统版本                   | 集群一致性核查                    |
| `display system-mac`              | 查看系统 MAC                   | 设备标识、资产关联                |
| `display esn`                     | 查看设备序列号（ESN）          | 资产盘点、合规核查                |
| `display elabel`                  | 查看电子标签                   | 资产信息核查                      |
| `display device manufacture-info` | 查看设备制造信息               | 资产溯源                          |
| `display package-information`    | 查看软件包信息                 | 软件包版本审计                    |
| `display diagnostic-information` | 查看诊断信息（综合）           | 一键采集排障信息                  |

### 3.2 硬件运行状态

| 命令                              | 说明                          | 审计用途                          |
| --------------------------------- | ----------------------------- | --------------------------------- |
| `display device`                  | 查看设备部件信息               | 部件在位状态核查                  |
| `display health`                  | 查看设备健康状态               | 综合健康度评估                    |
| `display fan`                     | 查看风扇状态                   | 风扇故障预警                      |
| `display fan-para`                | 查看风扇参数                   | 散热配置核查                      |
| `display power`                   | 查看电源状态                   | 电源冗余核查                      |
| `display power system`            | 查看电源系统                   | 整机供电评估                      |
| `display temperature`             | 查看温度                       | 过热风险预警                      |
| `display voltage`                 | 查看电压                       | 电压异常预警                      |
| `display environment version`    | 查看环境监控版本               | 监控模块核查                      |
| `display transceiver`            | 查看光模块信息                 | 光模块合规核查（非华为认证光模块）|

### 3.3 CPU / 内存

| 命令                                  | 说明                          | 审计用途                          |
| ------------------------------------- | ----------------------------- | --------------------------------- |
| `display cpu-usage`                   | 查看 CPU 使用率                | 性能监控                          |
| `display cpu-usage configuration`      | 查看 CPU 使用率配置            | 阈值告警配置核查                  |
| `display cpu-usage history`           | 查看 CPU 使用率历史            | 历史趋势分析                      |
| `display memory-usage`                | 查看内存使用率                 | 内存监控                          |
| `display memory-usage threshold`      | 查看内存阈值配置               | 阈值告警配置核查                  |

---

## 四、与系统功能的集成映射

本工作台已将上述命令清单作为「操作手册字典库」的种子条目嵌入系统，可通过以下方式检索与配对：

| 系统功能               | 对应 Manual 条目                              | mapping_target          |
| ---------------------- | --------------------------------------------- | ----------------------- |
| 配置审计 / ConfigView  | 华为 ASG 防火墙显示类命令                      | `config_parser`         |
| 配置审计 / ConfigView  | 华为 S12700 交换机查看设备状态命令             | `config_parser`         |
| 日志分析 / LogView     | 华为 ASG 防火墙显示类命令（log_pattern 用法）  | `log_parser`            |
| 拓扑发现               | LLDP 相关命令                                 | `both`                  |
| 流量分析               | `display statistics` / `display ip session`    | `log_parser`            |
| 设备状态审计           | CPU/内存/温度/电源类命令                       | `config_parser`         |

### 4.1 触发关键字（trigger_keywords）

系统字典条目的触发关键字覆盖以下命令前缀，便于在「解析依据配对」中命中：

- 通用前缀：`display`、`version`、`interface`、`arp`、`route`、`cpu`、`memory`、`fan`、`power`、`temperature`
- 防火墙特有：`session`、`nat-policy`、`ike sa`、`ipsec sa`、`ha`、`qos-profile`、`flowfast`、`sslproxy`、`https-portal`、`ldap-auth`、`user-manage`、`address-group`、`audit_policy`
- 交换机特有：`device`、`health`、`esn`、`elabel`、`transceiver`、`voltage`、`cpu-usage`、`memory-usage`、`system-mac`、`diagnostic-information`

### 4.2 排障建议（troubleshooting）

| 现象                         | 优先查询命令                                                                |
| ---------------------------- | --------------------------------------------------------------------------- |
| 设备无响应 / 网络中断         | `display version` → `display cpu-usage` → `display memory-usage` → `display health` |
| 防火墙策略未命中              | `display audit_policy accelerate` → `display policy accelerate` → `display address-group` |
| 隧道不通                      | `display ike sa` → `display ipsec sa` → `display ip route`                  |
| 双机异常                      | `display ha state` → `display ha config diff`                              |
| 端口异常                      | `display interface` → `display transceiver` → `display device`             |
| 流量异常                      | `display statistics` → `display ip session` → `display qos-profile statistics` |

---

## 五、来源与版权

- 华为产品文档版权归 © 华为技术有限公司 所有。
- 本文件仅作为内部网络分析工作台的离线参考与字典依据使用，不替代官方文档。
- 在线原文请通过 Huawei Hedex 平台访问：
  - ASG: <https://support.huawei.com/hedex/hdx.do?docid=EDOC1100313731&id=ZH-CN_TOPIC_0000001314006092>
  - S12700: <https://support.huawei.com/hedex/hdx.do?docid=EDOC1100126513&id=ZH-CN_CONCEPT_0177113659>
