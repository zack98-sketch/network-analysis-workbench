#!/bin/bash
set +e
export DEBIAN_FRONTEND=noninteractive

cd /data/network-analysis-workbench/backend

echo "=============================================="
echo " Step 1: apt install python deps"
echo "=============================================="
apt-get install -y \
  python3-bs4 python3-lxml python3-sqlalchemy \
  python3-markdown python3-pip python3-venv \
  python3-aiofiles 2>&1 | tail -5

echo ""
echo "=============================================="
echo " Step 2: Verify Python packages"
echo "=============================================="
python3 << 'PYEOF'
mods = [
    ("yaml", "PyYAML"),
    ("jinja2", "Jinja2"),
    ("bs4", "BeautifulSoup"),
    ("lxml", "lxml"),
    ("sqlalchemy", "SQLAlchemy"),
    ("markdown", "Markdown"),
]
for m, name in mods:
    try:
        mod = __import__(m)
        v = getattr(mod, "__version__", "?")
        print(f"  ✓ {name}: {v}")
    except ImportError as e:
        print(f"  ✗ {name}: {e}")
import csv, re, json, hashlib
print("  ✓ stdlib (csv/re/json/hashlib) OK")
PYEOF

echo ""
echo "=============================================="
echo " Step 3: Run parser E2E test (stdlib + yaml only)"
echo "=============================================="
cd /data/network-analysis-workbench/backend
python3 test_parsers_light.py 2>&1
