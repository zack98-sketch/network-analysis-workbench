import re
from typing import List, Dict, Any
from .base import IDocIndexer
from .html import _extract_keywords


class PDFIndexer(IDocIndexer):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        return header_bytes[:4] == b"%PDF"

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        title = None
        section_stack: List[tuple[int, str]] = []

        try:
            import pdfplumber
        except ImportError:
            return []

        page_no = 0
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_no += 1
                text = page.extract_text() or ""
                if not text.strip():
                    continue

                lines = text.splitlines()
                text_parts: List[str] = []
                prev_size = None

                try:
                    chars = page.chars
                    size_by_line: Dict[int, float] = {}
                    for ch in chars:
                        ln = ch.get("top", 0)
                        line_idx = int(ln // 10)
                        sz = ch.get("size", 12)
                        if line_idx not in size_by_line or sz > size_by_line[line_idx]:
                            size_by_line[line_idx] = sz
                except Exception:
                    chars = None
                    size_by_line = {}

                for idx, line in enumerate(lines):
                    stripped = line.strip()
                    if not stripped:
                        continue

                    size = size_by_line.get(idx, 12) if size_by_line else 12
                    is_heading = False
                    level = 0

                    m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
                    if m:
                        level = len(m.group(1))
                        stripped = m.group(2)
                        is_heading = True
                    elif re.match(r"^\d+(\.\d+)*\s+[A-Z\u4e00-\u9fa5]", stripped) and size > 14:
                        is_heading = True
                        parts = stripped.split(" ", 1)
                        num_part = parts[0]
                        level = num_part.count(".") + 1
                    elif size >= 18 and len(stripped) < 80:
                        level = 1
                        is_heading = True
                    elif size >= 14 and len(stripped) < 80:
                        level = 2
                        is_heading = True
                    elif prev_size is not None and size > prev_size + 2 and len(stripped) < 60:
                        level = 2
                        is_heading = True

                    if is_heading:
                        if text_parts and docs:
                            combined_text = "\n".join(text_parts)
                            section_path = " > ".join([s[1] for s in section_stack])
                            docs.append({
                                "title": title,
                                "section_path": section_path,
                                "content_text": combined_text.strip(),
                                "config_keywords": _extract_keywords(combined_text),
                                "page_no": page_no,
                            })
                            text_parts = []

                        level = max(1, min(6, level))
                        while section_stack and section_stack[-1][0] >= level:
                            section_stack.pop()
                        section_stack.append((level, stripped))
                        if not title:
                            title = stripped
                    else:
                        text_parts.append(stripped)

                    prev_size = size

                if text_parts:
                    combined_text = "\n".join(text_parts)
                    section_path = " > ".join([s[1] for s in section_stack])
                    docs.append({
                        "title": title,
                        "section_path": section_path,
                        "content_text": combined_text.strip(),
                        "config_keywords": _extract_keywords(combined_text),
                        "page_no": page_no,
                    })

        if not docs:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    page_no = 0
                    for page in pdf.pages:
                        page_no += 1
                        text = page.extract_text() or ""
                        if text.strip():
                            docs.append({
                                "title": title or file_path.split("\\")[-1],
                                "section_path": f"Page {page_no}",
                                "content_text": text.strip(),
                                "config_keywords": _extract_keywords(text),
                                "page_no": page_no,
                            })
            except Exception:
                pass

        return docs
