#!/bin/bash
echo '--- risks ---'
curl -sf http://127.0.0.1:8000/api/v1/projects/6/risks > /tmp/risks.json
python3 << 'PYEOF'
import json
with open('/tmp/risks.json') as f:
    d = json.load(f)
print(f"risk count={len(d)}")
for r in d[:5]:
    print(f"  - {r['risk_code']} [{r['severity']}] {r['description'][:60]}")
PYEOF

echo '--- topology ---'
curl -sf http://127.0.0.1:8000/api/v1/projects/6/topology > /tmp/topo.json
python3 << 'PYEOF'
import json
with open('/tmp/topo.json') as f:
    d = json.load(f)
print(f"nodes={len(d['nodes'])} edges={len(d['edges'])}")
for n in d['nodes'][:5]:
    print(f"  - {n.get('name')} ({n.get('node_type')}) ip={n.get('ip_address')}")
PYEOF

echo '--- config tree ---'
curl -sf http://127.0.0.1:8000/api/v1/materials/9/config/tree > /tmp/tree.json
python3 << 'PYEOF'
import json
with open('/tmp/tree.json') as f:
    d = json.load(f)
print(f"sections={len(d)}")
for s in d[:3]:
    print(f"  - [{s.get('section_type')}] {s.get('section_name')}: {len(s.get('items', []))} items")
PYEOF

echo '--- log events ---'
curl -sf http://127.0.0.1:8000/api/v1/materials/8/events > /tmp/events.json
python3 << 'PYEOF'
import json
with open('/tmp/events.json') as f:
    d = json.load(f)
print(f"events={len(d)}")
for e in d[:3]:
    print(f"  - {e.get('time')} {e.get('type')} {e.get('detail', '')[:60]}")
PYEOF
