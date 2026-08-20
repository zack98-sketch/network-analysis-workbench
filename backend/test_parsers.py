"""Standalone end-to-end parser test against demo materials in working directory.

Runs without FastAPI/DB - just the parsers and risk engine.
Usage: cd backend && python test_parsers.py
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_DIR))

from app.parsers.router import FileRouter
from app.engines.risk_engine import RiskEngine


def section(title: str):
    bar = "=" * 72
    print(f"\n{bar}\n  {title}\n{bar}")


def main():
    # 测试材料目录：相对于项目根目录的 test_materials/
    src_materials = Path(__file__).resolve().parent.parent / "test_materials"
    if not src_materials.exists():
        src_materials = Path(__file__).resolve().parent.parent.parent

    files_to_test = [
        ("demo_ssh_session.log", "SSH 会话日志"),
        ("demo_traffic_flow.csv", "CSV 流量日志"),
    ]

    # 自动发现配置文件
    for candidate in src_materials.glob("*config*"):
        files_to_test.append((candidate.name, "配置文件（自动发现）"))
        break
    else:
        for candidate in list(src_materials.glob("*.cfg")) + list(src_materials.glob("*.conf")):
            files_to_test.append((candidate.name, "配置文件（自动发现）"))
            break

    # 自动发现 CHM 手册
    for chm in src_materials.glob("*.chm"):
        files_to_test.append((chm.name, "CHM 手册"))
        break

    router = FileRouter()
    risk_engine = RiskEngine()

    all_log_events = []
    all_config_trees = []
    all_risks = []

    for fname, label in files_to_test:
        fpath = src_materials / fname
        if not fpath.exists():
            print(f"⚠️  [SKIP] {label}: {fname} 不存在于 {src_materials}")
            continue

        section(f"测试: {label} → {fname}")
        try:
            with open(fpath, "rb") as f:
                header = f.read(500)
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                sample_lines = [next(f, "") for _ in range(100)]

            category, parser_name, conf = router.detect_type(fpath, header, sample_lines)
            print(f"✓ 文件分类: {category} / 解析器: {parser_name} / 置信度: {conf:.0%}")

            parser_instance = router.route(fpath)
            print(f"✓ 解析器实例: {type(parser_instance).__name__}")

            if category == "log":
                events = parser_instance.parse(fpath)
                print(f"✓ 解析得到 {len(events)} 条事件")
                if events:
                    first = events[0]
                    print(f"    首条: {dict(list(first.items())[:6])}")
                    print(f"    类型分布: {_count_by(events, 'event_type')}")
                    all_log_events.extend(events)
            elif category == "config":
                tree = parser_instance.parse(fpath)
                n_sections = len(tree.get("sections", []))
                n_items = sum(len(s.get("items", [])) for s in tree.get("sections", []))
                print(f"✓ 设备: {tree.get('device_name')} | 厂商: {tree.get('vendor')} | 版本: {tree.get('software_version')}")
                print(f"✓ 节数: {n_sections} | 配置项数: {n_items} | CRC: {tree.get('config_crc')}")
                risk_items = [i for s in tree["sections"] for i in s.get("items", []) if i.get("is_risk")]
                print(f"⚠ 解析器内置风险标记: {len(risk_items)} 条")
                for ri in risk_items[:3]:
                    print(f"    - L{ri['line_no']} {ri['key']}={ri['value']}: {ri.get('annotation','')}")
                all_config_trees.append(tree)

                # Run config risk engine
                cfg_risks = risk_engine.analyze_config(tree)
                print(f"🎯 规则引擎发现: {len(cfg_risks)} 项风险")
                for r in cfg_risks[:5]:
                    print(f"    [{r['severity'].upper():6s}] {r['risk_code']} {r['category']}: {r['description'][:80]}")
                all_risks.extend(cfg_risks)
            elif category == "doc":
                docs = parser_instance.parse(fpath)
                print(f"✓ 索引段落: {len(docs)} 段")
                if docs:
                    for d in docs[:2]:
                        print(f"    - [{d.get('page_no','?')}] {d.get('title','')[:60]}  keywords={d.get('config_keywords','')[:40]}")
            else:
                print(f"? 未知类别: {category}")

        except Exception as e:
            print(f"✗ 解析失败: {type(e).__name__}: {e}")
            traceback.print_exc()

    # Run log audit risks
    if all_log_events:
        section("日志审计风险检测")
        log_risks = risk_engine.analyze_logs(all_log_events)
        traffic_risks = risk_engine.analyze_traffic(all_log_events)
        print(f"日志审计风险: {len(log_risks)} 项")
        print(f"流量异常风险: {len(traffic_risks)} 项")
        for r in log_risks + traffic_risks:
            print(f"    [{r['severity'].upper():6s}] {r['risk_code']} {r['category']}: {r['description'][:80]}")
        all_risks.extend(log_risks)
        all_risks.extend(traffic_risks)

    section("汇总")
    print(f"材料总数:       {len(files_to_test)}")
    print(f"日志事件总数:   {len(all_log_events)}")
    print(f"配置树总数:     {len(all_config_trees)}")
    print(f"风险发现总数:   {len(all_risks)}")
    if all_risks:
        by_sev = _count_by(all_risks, "severity")
        print(f"  按严重度:     {by_sev}")
        by_cat = _count_by(all_risks, "category")
        print(f"  按类别:       {by_cat}")

    # Save risk list for reference
    out_path = SRC_DIR / "test_output_summary.json"
    serializable_risks = []
    for r in all_risks:
        rr = dict(r)
        rr.pop("_raw", None)
        serializable_risks.append(rr)
    out_path.write_text(json.dumps({
        "events_count": len(all_log_events),
        "configs_count": len(all_config_trees),
        "risks": serializable_risks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📄 详细结果已保存到: {out_path}")
    return 0


def _count_by(items, key):
    counts = {}
    for it in items:
        v = it.get(key, "unknown")
        counts[str(v)] = counts.get(str(v), 0) + 1
    return counts


if __name__ == "__main__":
    sys.exit(main())
