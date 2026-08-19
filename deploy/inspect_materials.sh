#!/bin/bash
cd /data/network-analysis-workbench/backend/data/uploads/demo-project

echo '=== CSV header + first 3 rows ==='
head -4 "FWQ流量.csv" 2>/dev/null | head -c 3000
echo ''
echo ''
echo '=== SSH log sample (5.1 big one) - first 100 lines ==='
head -100 "10.64.5.1_2026-08-17_20_08_36.log" | head -c 5000
echo ''
echo ''
echo '=== Look for configuration display output in log files ==='
grep -lE "display current|sysname|interface Gigabit|stp|vlan|ospf|firewall zone|security-policy|nat policy" *.log 2>/dev/null
echo ''
echo '=== Count commands in largest log (commands are cli lines user typed) ==='
wc -l "10.64.5.1_2026-08-17_20_08_36.log"
echo ''
echo '=== Last 80 lines of big log (likely has display current output or config sections) ==='
tail -80 "10.64.5.1_2026-08-17_20_08_36.log" | head -c 5000
