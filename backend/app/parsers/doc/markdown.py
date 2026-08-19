import re
from typing import List, Dict, Any
from .base import IDocIndexer
from .html import _extract_keywords


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
CODE_BLOCK_RE = re.compile(r"^```")


class MarkdownIndexer(IDocIndexer):
    def can_parse(self, file_path: str, header_bytes: bytes, sample_lines: List[str]) -> bool:
        joined = "\n".join(sample_lines[:30])
        return bool(HEADING_RE.search(joined))

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        title = None
        section_stack: List[tuple[int, str]] = []
        text_parts: List[str] = []
        code_text_parts: List[str] = []
        in_code_block = False
        page_no = 1

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.rstrip("\n")
                stripped = line.strip()

                code_m = CODE_BLOCK_RE.match(stripped)
                if code_m:
                    if in_code_block:
                        in_code_block = False
                    else:
                        in_code_block = True
                    continue

                if in_code_block:
                    code_text_parts.append(line)
                    continue

                m = HEADING_RE.match(line)
                if m:
                    if text_parts and docs is not None:
                        combined_text = "\n".join(text_parts)
                        section_path = " > ".join([s[1] for s in section_stack])
                        docs.append({
                            "title": title,
                            "section_path": section_path,
                            "content_text": combined_text.strip(),
                            "config_keywords": _extract_keywords(combined_text + "\n" + "\n".join(code_text_parts)),
                            "page_no": page_no,
                        })
                        text_parts = []
                        code_text_parts = []

                    level = len(m.group(1))
                    heading_text = m.group(2).strip()
                    while section_stack and section_stack[-1][0] >= level:
                        section_stack.pop()
                    section_stack.append((level, heading_text))
                    if not title and level <= 1:
                        title = heading_text
                    continue

                if stripped:
                    text_parts.append(stripped)

        if text_parts or code_text_parts:
            combined_text = "\n".join(text_parts)
            section_path = " > ".join([s[1] for s in section_stack])
            docs.append({
                "title": title,
                "section_path": section_path,
                "content_text": combined_text.strip(),
                "config_keywords": _extract_keywords(combined_text + "\n" + "\n".join(code_text_parts)),
                "page_no": page_no,
            })

        return docs
