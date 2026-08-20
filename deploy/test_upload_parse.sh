#!/bin/bash
# Test full upload-parse flow
set -e
BASE=http://127.0.0.1:8000/api/v1

echo "=== 1. Create test project ==="
PROJ=$(curl -sf -X POST $BASE/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"解析验证项目","description":"测试新上传文件解析","status":"active"}')
echo "$PROJ"
PID=$(echo "$PROJ" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "PID=$PID"

echo "=== 2. Upload a log file ==="
curl -sf -X POST $BASE/materials \
  -F "project_id=$PID" \
  -F "file=@../test_materials/demo_ssh_session.log"
echo ""

echo "=== 3. Wait for async parse ==="
sleep 3

echo "=== 4. List materials ==="
curl -sf $BASE/projects/$PID/materials | python3 -m json.tool

echo "=== 5. Upload VRP config ==="
curl -sf -X POST $BASE/materials \
  -F "project_id=$PID" \
  -F "file=@../test_materials/demo_switch_config.cfg"
echo ""

echo "=== 6. Wait & list ==="
sleep 3
curl -sf $BASE/projects/$PID/materials | python3 -m json.tool

echo "=== 7. Check risks ==="
curl -sf $BASE/projects/$PID/risks | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"风险数={len(d)}"); [print(f"- {r[\"risk_code\"]} [{r[\"severity\"]}] {r[\"description\"][:80]}") for r in d[:5]]'

echo "=== 8. Check topology ==="
curl -sf $BASE/projects/$PID/topology | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"nodes={len(d[\"nodes\"])} edges={len(d[\"edges\"])}")'
