#!/bin/bash
cd /data/network-analysis-workbench/backend

echo '=== Verify python deps ==='
python3 -c '
import importlib
for m,n in [
  ("yaml","PyYAML"),("bs4","BeautifulSoup4"),("lxml","lxml"),
  ("markdown","Markdown"),("pdfplumber","pdfplumber"),
]:
    try:
        mod = importlib.import_module(m)
        print(f"  OK {n}")
    except Exception as e:
        print(f"  FAIL {n}: {e}")
'

echo ''
echo '=== Run full E2E parser, docs + risk engine test ==='
python3 test_parsers_light.py 2>&1
