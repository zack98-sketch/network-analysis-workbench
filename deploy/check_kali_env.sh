#!/bin/bash
echo '=== Kali version / Python / pip / node ==='
cat /etc/os-release | head -5
which python3 && python3 --version
which pip3 && pip3 --version
which pip 2>&1
which node && node --version
which npm && npm --version

echo ''
echo '=== Pip cache info ==='
python3 -m pip cache dir 2>/dev/null
pip3 cache dir 2>/dev/null
ls -la ~/.cache/pip 2>/dev/null | head -8
echo '=== Whell count in pip cache ==='
find ~/.cache/pip -maxdepth 5 -name '*.whl' 2>/dev/null | wc -l

echo ''
echo '=== Python packages already installed ==='
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
        print(f"  -- {n}: NOT INSTALLED")
PYEOF

echo ''
echo '=== npm cache dir ==='
npm config get cache 2>/dev/null
ls ~/.npm/_cacache 2>/dev/null | head -5
npm cache ls 2>/dev/null | wc -l

echo ''
echo '=== /data directory ==='
ls -la /data 2>/dev/null
