#!/bin/bash
cd /data/network-analysis-workbench/backend
echo '=== Install python-multipart verbose ==='
python3 -m pip install --break-system-packages python-multipart 2>&1 | tail -10

echo ''
echo '=== Try import variants ==='
python3 -c 'import multipart; print("multipart module OK:", getattr(multipart, "__version__", "?"))' 2>&1
python3 -c 'from multipart.multipart import MultipartParser; print("MultipartParser OK")' 2>&1

echo ''
echo '=== List packages with multipart in name ==='
python3 -m pip list 2>/dev/null | grep -i multi || true
