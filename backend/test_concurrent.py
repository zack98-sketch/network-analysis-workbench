"""并发上传测试 - 验证 WAL 模式修复

Usage: cd backend && python test_concurrent.py
前提：后端服务已启动 (uvicorn app.main:app)
"""
import json
import threading
import time
import urllib.request
import urllib.error
import os
import sqlite3
from pathlib import Path

BASE = "http://127.0.0.1:8000/api/v1"
# 测试材料目录：相对于项目根目录
TEST_DIR = str(Path(__file__).resolve().parent.parent / "test_materials")
# 数据库路径：相对于 backend 目录
DB = str(Path(__file__).resolve().parent / "data" / "workbench.db")
# 日志路径
LOG_DIR = str(Path(__file__).resolve().parent / "logs")


def http_post_json(url, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_file(url, file_path, project_id):
    """Simple multipart upload using requests-style manual encoding."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="project_id"\r\n\r\n'
        f"{project_id}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    print("=== 1. 创建并发测试项目 ===")
    proj = http_post_json(f"{BASE}/projects", {"name": "WALConcurrentTest", "description": "concurrent", "status": "active"})
    pid = proj["id"]
    print(f"项目 ID: {pid}")

    files = [
        f"{TEST_DIR}/demo_ssh_session_01.log",
        f"{TEST_DIR}/demo_ssh_session_02.log",
        f"{TEST_DIR}/demo_syslog_01.log",
        f"{TEST_DIR}/demo_switch_config.cfg",
    ]

    print("\n=== 2. 并发上传 4 个文件 ===")
    results = [None] * 4
    threads = []

    def upload(idx, path):
        try:
            r = http_post_file(f"{BASE}/materials", path, pid)
            results[idx] = r
            print(f"  [{idx+1}] OK id={r.get('id')} name={r.get('name', r.get('file_name'))}")
        except Exception as e:
            results[idx] = {"error": str(e)}
            print(f"  [{idx+1}] FAIL: {e}")

    for i, path in enumerate(files):
        t = threading.Thread(target=upload, args=(i, path))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    print("\n=== 3. 等待 10s 让后台解析完成 ===")
    time.sleep(10)

    print("\n=== 4. 检查所有材料状态 ===")
    materials = http_get(f"{BASE}/projects/{pid}/materials")
    for m in materials:
        print(f"  id={m['id']:3d}  status={m['parse_status']:8s}  type={m.get('file_type') or '?':8s}  parser={m.get('parser_type') or '?':20s}  name={m['file_name']}")

    success_count = sum(1 for m in materials if m["parse_status"] == "success")
    failed_count = sum(1 for m in materials if m["parse_status"] == "failed")
    pending_count = sum(1 for m in materials if m["parse_status"] in ("pending", "parsing"))
    print(f"\n  汇总: {success_count} 成功, {failed_count} 失败, {pending_count} 进行中/卡住")

    print("\n=== 5. 检查 database is locked 错误 ===")
    log_path = f"{LOG_DIR}/workbench.log"
    with open(log_path, "r", errors="replace") as f:
        content = f.read()
    lock_count = content.count("database is locked")
    print(f"  'database is locked' 出现次数: {lock_count}")
    if lock_count > 0:
        # 显示最后几次相关日志
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "database is locked" in line:
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                print(f"  --- 上下文 (行 {i}) ---")
                for j in range(start, end):
                    print(f"  {lines[j][:200]}")

    print("\n=== 6. WAL 模式确认 ===")
    conn = sqlite3.connect(DB)
    print(f"  journal_mode = {conn.execute('PRAGMA journal_mode').fetchone()[0]}")
    conn.close()

    print(f"\n=== 结论 ===")
    if pending_count == 0 and lock_count == 0:
        print("  PASS: 所有文件解析成功，无 database locked 错误")
    elif pending_count > 0:
        print(f"  FAIL: 仍有 {pending_count} 个文件卡在 pending/parsing 状态")
    else:
        print(f"  WARN: 有 {lock_count} 次 database locked 错误（但材料最终解析成功）")


if __name__ == "__main__":
    main()
