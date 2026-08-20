#!/bin/bash
set +e
cd /data/network-analysis-workbench/backend
BASE=http://127.0.0.1:8000/api/v1

echo "==================== 冒烟测试 ===================="
echo ""

echo "--- [1] 健康检查 /api/health ---"
curl -sf http://127.0.0.1:8000/api/health 2>&1 | python3 -m json.tool 2>&1 | head -5
echo ""

echo "--- [2] 根路径 (前端 SPA index.html) ---"
ROOT=$(curl -sf http://127.0.0.1:8000/ 2>&1)
TITLE=$(echo "$ROOT" | grep -o '<title>[^<]*</title>' 2>/dev/null || echo "NO TITLE")
echo "  文件大小: $(echo "$ROOT" | wc -c) 字节"
echo "  Title: $TITLE"
APPCNT=$(echo "$ROOT" | grep -c 'id="app"' 2>/dev/null || echo 0)
echo "  包含 Vue app 挂载点: $APPCNT 处"

echo ""
echo "--- [3] GET /api/v1/projects (初始列表) ---"
curl -sf $BASE/projects 2>&1 | python3 -m json.tool 2>&1 | head -10

echo ""
echo "--- [4] POST /api/v1/projects (创建演示项目) ---"
RESP=$(curl -sf -X POST $BASE/projects -H 'Content-Type: application/json' \
  -d '{"name":"演示项目-生产网边界审计","description":"冒烟测试演示项目"}' 2>&1)
echo "$RESP" | python3 -m json.tool 2>&1 | head -15
PID=$(echo "$RESP" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("id",""))' 2>/dev/null)
echo "  [解析得到 PID] = $PID"

if [ -z "$PID" ]; then
  echo "  ! 创建失败，改用列表中第一个项目作为 PID"
  PID=$(curl -sf $BASE/projects 2>&1 | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d[0].get("id","") if d else "")' 2>/dev/null)
  echo "  [回退 PID] = $PID"
fi

echo ""
echo "--- [5] GET /api/v1/projects 列表验证 ---"
curl -sf $BASE/projects 2>&1 | python3 -c 'import sys,json;d=json.load(sys.stdin);print("项目数:",len(d));[print("  -",p["id"],p["name"],"status="+p.get("status","?")) for p in d]' 2>&1

echo ""
echo "--- [6] POST /api/v1/materials 上传演示配置 ---"
CFG_PATH=data/uploads/demo-project/demo_switch_config.cfg
MID=""
if [ -f "$CFG_PATH" -a -n "$PID" ]; then
  RESP2=$(curl -sf -X POST $BASE/materials \
    -H "X-Project-Id: $PID" \
    -F "file=@$CFG_PATH;filename=switch.cfg" 2>&1)
  echo "$RESP2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print("  上传OK:", d.get("name"), d.get("type"), d.get("format"), "size="+str(d.get("size","?")), "status="+str(d.get("status","?")))' 2>&1
  MID=$(echo "$RESP2" | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("id",""))' 2>/dev/null)
  echo "  [解析得到 MID] = $MID"

  # 触发重新解析并等待完成（后端异步任务需要事件循环执行）
  if [ -n "$MID" ]; then
    curl -sf -X POST $BASE/materials/$MID/reparse 2>&1 >/dev/null
    sleep 3
  fi
else
  echo "  SKIP: CFG不存在或无PID ($CFG_PATH, PID=$PID)"
fi

echo ""
echo "--- [7] GET /projects/{id}/materials 材料列表 ---"
if [ -n "$PID" ]; then
  curl -sf $BASE/projects/$PID/materials 2>&1 | python3 -c 'import sys,json;d=json.load(sys.stdin);print("材料数:",len(d));[print("  -",m.get("id"),m.get("file_name"),m.get("material_type"),"parse="+str(m.get("parse_status"))) for m in d]' 2>&1 | head -15
fi

echo ""
echo "--- [8] GET /materials/{id}/config/tree ---"
if [ -n "$MID" ]; then
  curl -sf $BASE/materials/$MID/config/tree 2>&1 | python3 -c 'import sys,json,collections;d=json.load(sys.stdin);sections=[x.get("section_type","?") for x in d];c=collections.Counter(sections);print("配置节数:",len(d),"类型分布:",dict(c))' 2>&1 | head -5
fi

echo ""
echo "--- [9] POST /projects/{id}/risks/recheck 风险重检 ---"
if [ -n "$PID" ]; then
  RESP3=$(curl -sf -X POST $BASE/projects/$PID/risks/recheck 2>&1)
  echo "$RESP3" | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
except Exception:
    print("响应非列表格式")
    sys.exit(0)
print("风险总数:",len(d))
sevs={}
for r in d:
    s=r.get("severity","?")
    sevs[s]=sevs.get(s,0)+1
print("按严重度:",sevs)
for r in d[:8]:
    print("  -["+str(r.get("severity"))+"]",r.get("risk_code"),str(r.get("description",""))[:80])
' 2>&1 | head -25
fi

echo ""
echo "--- [10] GET /projects/{id}/risks 列表 ---"
if [ -n "$PID" ]; then
  curl -sf $BASE/projects/$PID/risks 2>&1 | python3 -c 'import sys,json;d=json.load(sys.stdin);print("风险列表数:",len(d))' 2>&1
fi

echo ""
echo "--- [11] GET /projects/{id}/summary 仪表盘汇总 ---"
if [ -n "$PID" ]; then
  curl -sf $BASE/projects/$PID/summary 2>&1 | python3 -m json.tool 2>&1 | head -20
fi

echo ""
echo "--- [12] GET /rules 规则库概览 ---"
curl -sf $BASE/rules 2>&1 | python3 -c '
import sys,json
d=json.load(sys.stdin)
print("规则总数:",len(d))
doms={}
sevs={}
for r in d:
    dom=r.get("domain","?")
    sev=r.get("severity","?")
    doms[dom]=doms.get(dom,0)+1
    sevs[sev]=sevs.get(sev,0)+1
print("按domain:",doms)
print("按severity:",sevs)
' 2>&1

echo ""
echo "--- [13] GET /projects/{id}/topology 拓扑概览 ---"
if [ -n "$PID" ]; then
  curl -sf $BASE/projects/$PID/topology 2>&1 | python3 -c 'import sys,json;d=json.load(sys.stdin);print("节点数:",len(d.get("nodes",[]))," / 边数:",len(d.get("edges",[])))' 2>&1
fi

echo ""
echo "--- [14] GET /projects/{id}/logs/timeline 时间线 ---"
if [ -n "$PID" ]; then
  TL=$(curl -sf $BASE/projects/$PID/logs/timeline 2>&1)
  echo "$TL" | python3 -c 'import sys,json;d=json.load(sys.stdin);
if isinstance(d,list):
    print("时间线条数:", len(d))
elif isinstance(d,dict):
    buckets = d.get("buckets", [])
    print("时间线条数(buckets):", len(buckets), "总事件数:", d.get("total", "N/A"))
else:
    print("时间线类型:", type(d).__name__)
' 2>&1
fi

echo ""
echo "--- [15] GET /reports 列表 ---"
if [ -n "$PID" ]; then
  REPS=$(curl -sf $BASE/projects/$PID/reports 2>&1)
  echo "$REPS" | python3 -c 'import sys,json;
try:
    d=json.load(sys.stdin)
    print("报告数:", len(d) if isinstance(d,list) else "N/A (type="+type(d).__name__+")")
except Exception as e:
    print("响应非JSON:",str(e)[:60])
' 2>&1
fi

echo ""
echo "==================== 冒烟测试完成 ===================="
