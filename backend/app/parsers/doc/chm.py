import os
import subprocess
import tempfile
import shutil
from typing import List, Dict, Any
from .base import IDocIndexer
from .html import _extract_keywords


class CHMIndexer(IDocIndexer):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        ext = os.path.splitext(file_path)[1].lower()
        return ext == ".chm" or header_bytes[:4] == b"ITSF"

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        temp_dir = None

        try:
            temp_dir = tempfile.mkdtemp(prefix="chm_extract_")
            try:
                result = subprocess.run(
                    ["7z", "x", "-y", f"-o{temp_dir}", file_path],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode != 0:
                    try:
                        result = subprocess.run(
                            ["7za", "x", "-y", f"-o{temp_dir}", file_path],
                            capture_output=True, text=True, timeout=120
                        )
                    except Exception:
                        pass
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                pass

            extracted_files = []
            for root, _, files in os.walk(temp_dir):
                for name in files:
                    if name.lower().endswith((".htm", ".html")):
                        extracted_files.append(os.path.join(root, name))

            page_no = 0
            for hfile in sorted(extracted_files):
                try:
                    from .html import HTMLIndexer
                    indexer = HTMLIndexer()
                    sub_docs = indexer.parse(hfile)
                    for d in sub_docs:
                        page_no += 1
                        d["page_no"] = page_no
                        if not d["title"]:
                            d["title"] = os.path.splitext(os.path.basename(file_path))[0]
                        docs.append(d)
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            if temp_dir and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        if not docs:
            title = os.path.splitext(os.path.basename(file_path))[0]
            docs.append({
                "title": title,
                "section_path": "未解析(CHM需7z外部工具)",
                "content_text": "CHM文件未解析：需要安装7z并确保在PATH中，或使用7za命令行工具。",
                "config_keywords": "",
                "page_no": 1,
            })

        return docs
