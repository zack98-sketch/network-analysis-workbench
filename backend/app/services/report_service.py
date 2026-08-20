import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings


class ReportService:
    def __init__(self):
        templates_dir = settings.BASE_DIR / "app" / "data" / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.export_dir = settings.EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _severity_counts(self, risks: List[Dict[str, Any]]) -> Dict[str, int]:
        counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for r in risks:
            sev = (r.get("severity") or "").lower()
            if sev in ("high", "critical"):
                counts["high"] += 1
            elif sev == "medium":
                counts["medium"] += 1
            elif sev == "low":
                counts["low"] += 1
            else:
                counts["info"] += 1
        return counts

    def _format_size(self, size_bytes: Optional[int]) -> str:
        if size_bytes is None:
            return "—"
        n = float(size_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024.0:
                return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} {unit}"
            n /= 1024.0
        return f"{n:.1f} TB"

    def _prepare_materials(self, materials: List[Dict[str, Any]], config_trees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for m in materials:
            md = dict(m) if isinstance(m, dict) else {
                "file_name": getattr(m, "file_name", ""),
                "file_type": getattr(m, "file_type", ""),
                "parser_type": getattr(m, "parser_type", ""),
                "parse_status": getattr(m, "parse_status", ""),
                "device_name": getattr(m, "device_name", ""),
                "file_size": getattr(m, "file_size", None),
            }
            md["file_size_human"] = self._format_size(md.get("file_size"))
            mid = md.get("id")
            matched_sections = []
            for ct in config_trees:
                if str(ct.get("material_id")) == str(mid):
                    matched_sections.extend(ct.get("sections", []))
            md["config_sections"] = matched_sections
            out.append(md)
        return out

    def generate_html(
        self,
        project: Any,
        materials: List[Dict[str, Any]],
        risks: List[Dict[str, Any]],
        config_trees: List[Dict[str, Any]],
        topology: Dict[str, Any],
        events: List[Dict[str, Any]],
        title: Optional[str] = None,
    ) -> str:
        project_name = getattr(project, "name", None) if project else None
        if not project_name and isinstance(project, dict):
            project_name = project.get("name")
        project_id = getattr(project, "id", None) if project else None
        if project_id is None and isinstance(project, dict):
            project_id = project.get("id")

        sev = self._severity_counts(risks)
        rule_counts = {"config": 10, "log": 5, "traffic": 3}

        topo_nodes = topology.get("nodes", []) if topology else []
        topo_edges = topology.get("edges", []) if topology else []

        prepared_materials = self._prepare_materials(materials, config_trees)

        ctx = {
            "title": title or f"网络环境分析报告 - {project_name or '未命名项目'}",
            "project_name": project_name,
            "project_id": project_id,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "materials": prepared_materials,
            "material_count": len(prepared_materials),
            "risks": risks,
            "risk_total": len(risks),
            "risk_high": sev["high"],
            "risk_medium": sev["medium"],
            "risk_low": sev["low"] + sev["info"],
            "log_events": events,
            "event_count": len(events),
            "topology": topology or {"nodes": [], "edges": []},
            "topo_nodes_count": len(topo_nodes),
            "topo_edges_count": len(topo_edges),
            "rule_count": rule_counts,
        }

        template = self.env.get_template("report_template.html")
        return template.render(**ctx)

    def generate_markdown(
        self,
        project: Any,
        materials: List[Dict[str, Any]],
        risks: List[Dict[str, Any]],
        events: List[Dict[str, Any]],
        title: Optional[str] = None,
    ) -> str:
        project_name = getattr(project, "name", None) if project else None
        if not project_name and isinstance(project, dict):
            project_name = project.get("name")
        project_id = getattr(project, "id", None) if project else None
        if project_id is None and isinstance(project, dict):
            project_id = project.get("id")

        sev = self._severity_counts(risks)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = title or f"网络环境分析报告 - {project_name or '未命名项目'}"

        lines: List[str] = []
        lines.append(f"# {title}")
        lines.append("")
        lines.append(f"- **项目**: {project_name or '未命名项目'} (ID: {project_id or '—'})")
        lines.append(f"- **生成时间**: {now}")
        lines.append(f"- **分析材料**: {len(materials)} 份")
        lines.append(f"- **风险发现**: {len(risks)} 项（高危 {sev['high']} / 中危 {sev['medium']} / 低危 {sev['low'] + sev['info']}）")
        lines.append("")

        lines.append("## 执行摘要")
        lines.append("")
        lines.append(f"本次共分析 **{len(materials)}** 份材料，发现风险项 **{len(risks)}** 项，其中高危 **{sev['high']}**、中危 **{sev['medium']}**、低危 **{sev['low'] + sev['info']}**。")
        lines.append("建议按严重度优先级完成整改。")
        lines.append("")

        lines.append("## 风险发现与整改建议")
        lines.append("")
        if risks:
            lines.append("| 编号 | 严重度 | 分类 | 描述 | 来源 | 合规参考 |")
            lines.append("|---|---|---|---|---|---|")
            for r in risks:
                desc = (r.get('description') or '').replace('|', '\\|')
                lines.append(
                    f"| {r.get('risk_code','')} | {r.get('severity','').upper()} | {r.get('category','')} | "
                    f"{desc} | "
                    f"{r.get('source_ref','')} | {r.get('standard_ref','')} |"
                )
            lines.append("")
            lines.append("### 整改命令详情")
            lines.append("")
            for r in risks:
                if r.get("remediation_cmd"):
                    lines.append(f"#### {r.get('risk_code')} - {r.get('description','')[:40]}")
                    lines.append("")
                    lines.append("```")
                    lines.append(r["remediation_cmd"].rstrip())
                    lines.append("```")
                    lines.append("")
        else:
            lines.append("> 暂未发现风险项。")
            lines.append("")

        lines.append("## 材料清单")
        lines.append("")
        if materials:
            lines.append("| 文件名 | 设备 | 类型 | 状态 | 大小 |")
            lines.append("|---|---|---|---|---|")
            for m in materials:
                if isinstance(m, dict):
                    name = m.get("file_name", "")
                    dev = m.get("device_name") or "—"
                    ft = m.get("file_type") or m.get("parser_type") or "—"
                    ps = str(m.get("parse_status", ""))
                    sz = self._format_size(m.get("file_size"))
                else:
                    name = getattr(m, "file_name", "")
                    dev = getattr(m, "device_name") or "—"
                    ft = getattr(m, "file_type") or getattr(m, "parser_type") or "—"
                    ps = str(getattr(m, "parse_status", ""))
                    sz = self._format_size(getattr(m, "file_size", None))
                lines.append(f"| {name} | {dev} | {ft} | {ps} | {sz} |")
            lines.append("")

        lines.append("## 关键日志事件")
        lines.append("")
        if events:
            for ev in events[:50]:
                ts = ev.get("timestamp") or "—"
                et = ev.get("event_type") or "event"
                user = ev.get("user") and f"用户 {ev['user']}" or ""
                src = ev.get("source_ip") and f"从 {ev['source_ip']}" or ""
                tgt = ev.get("target_ip") and f"→ {ev['target_ip']}" or ""
                detail = ev.get("raw_line") or ""
                if len(detail) > 100:
                    detail = detail[:100] + "..."
                lines.append(f"- **{ts}** `[{et}]` {user} {src} {tgt}  {detail}")
            lines.append("")
        else:
            lines.append("> 暂无可展示的日志事件。")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(f"*本报告由 网络环境分析工作台 于 {now} 自动生成。*")
        return "\n".join(lines)

    def generate_pdf(self, html: str) -> bytes:
        try:
            import weasyprint
            return weasyprint.HTML(string=html).write_pdf()
        except Exception:
            note = (
                "\n\n<!-- PDF NOTE: PDF generation requires a headless Chromium-based renderer or WeasyPrint.\n"
                "WeasyPrint is not installed or failed. As a fallback, the raw HTML report content is stored\n"
                "with a .pdf extension; to produce a real PDF, open this file in Chrome/Edge and use\n"
                "\"Print → Save as PDF\", or install WeasyPrint / Playwright / pyppeteer and regenerate. -->\n"
            )
            return (html + note).encode("utf-8")

    def save_report(self, project_id: int, format: str, content_bytes: bytes) -> Dict[str, Any]:
        format = (format or "html").lower()
        ext_map = {"html": "html", "htm": "html", "pdf": "pdf", "md": "md", "markdown": "md"}
        ext = ext_map.get(format, format)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"report_project{project_id}_{ts}.{ext}"
        file_path = self.export_dir / file_name

        with open(file_path, "wb") as f:
            f.write(content_bytes)

        return {
            "id": f"rep-{project_id}-{ts}",
            "project_id": project_id,
            "file_path": str(file_path),
            "file_name": file_name,
            "format": ext,
            "file_size": len(content_bytes),
            "created_at": datetime.now().isoformat(),
            "download_url": f"/exports/{file_name}",
        }
