#!/bin/bash
# 检查已上传材料的解析结果（在 backend/data/uploads/ 目录中操作）
cd "$(dirname "$0")/../backend/data/uploads" 2>/dev/null || { echo "uploads 目录不存在"; exit 1; }

echo '=== CSV header + first 3 rows ==='
head -4 "demo_traffic_flow.csv" 2>/dev/null | head -c 3000
echo ''
echo ''
echo '=== SSH log sample - first 100 lines ==='
head -100 "demo_ssh_session.log" | head -c 5000
echo ''
echo ''
echo '=== Look for configuration display output in log files ==='
grep -lE "display current|sysname|interface Gigabit|stp|vlan|ospf|firewall zone|security-policy|nat policy" *.log 2>/dev/null
echo ''
echo '=== Count commands in log ==='
wc -l "demo_ssh_session.log"
echo ''
echo '=== Last 80 lines of log ==='
tail -80 "demo_ssh_session.log" | head -c 5000
