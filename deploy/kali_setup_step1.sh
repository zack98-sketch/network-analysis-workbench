#!/bin/bash
cd /data/network-analysis-workbench/backend
echo '=== Install python-multipart with --ignore-installed ==='
python3 -m pip install --break-system-packages --ignore-installed --no-deps python-multipart 2>&1 | tail -8

echo ''
echo '=== Verify ==='
python3 -c 'import multipart; print("multipart OK:", getattr(multipart, "__version__", "?"))'
python3 -c 'from multipart.multipart import MultipartParser; print("MultipartParser OK")'

echo ''
echo '=== All backend deps ==='
python3 << 'PYEOF'
import importlib
ms = [
  ("fastapi","FastAPI"),("uvicorn","uvicorn"),("pydantic","pydantic"),
  ("pydantic_settings","pydantic_settings"),
  ("sqlalchemy","SQLAlchemy"),("aiosqlite","aiosqlite"),
  ("yaml","PyYAML"),("jinja2","Jinja2"),
  ("bs4","BeautifulSoup4"),("lxml","lxml"),
  ("markdown","Markdown"),("pdfplumber","pdfplumber"),
  ("aiofiles","aiofiles"),("websockets","websockets"),
  ("httpx","httpx"),("multipart","python-multipart"),
]
for m,n in ms:
    try:
        mod = importlib.import_module(m)
        v = getattr(mod, "__version__", "?")
        print(f"  OK {n}: {v}")
    except Exception as e:
        print(f"  FAIL {n}: {e}")
PYEOF

echo ''
echo '=== E2E parser + risk test ==='
python3 test_parsers_light.py
