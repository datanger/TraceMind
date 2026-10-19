"""Create an auditable first project-state scaffold from the existing HTML prototype."""

from __future__ import annotations

import html
import argparse
import json
import re
from pathlib import Path
from typing import Any


def _plain(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def migrate_legacy_html(path: str | Path) -> dict[str, Any]:
    source = Path(path).read_text(encoding="utf-8")
    features: list[dict[str, Any]] = []
    feature_blocks = re.findall(r'<article class="feature\s+[^\"]+"\s+data-status="[^\"]+"[^>]*>(.*?)</article>', source, flags=re.S)
    for feature_index, block in enumerate(feature_blocks, start=1):
        title_match = re.search(r"<h3>(.*?)</h3>", block, flags=re.S)
        description_match = re.search(r"<h3>.*?</h3>\s*<p>(.*?)</p>", block, flags=re.S)
        rows = re.findall(r'<div class="subfeature">\s*<span>\s*<strong>(.*?)</strong>\s*<small>(.*?)</small>\s*</span>\s*<select data-task-key="([^"]+)"', block, flags=re.S)
        if not title_match or not rows:
            continue
        title = _plain(title_match.group(1))
        description = _plain(description_match.group(1)) if description_match else ""
        work_packages = []
        for name_html, detail_html, package_id in rows:
            name = _plain(name_html)
            detail = _plain(detail_html)
            wp_title = re.sub(r"^" + re.escape(package_id) + r"\s*", "", name)
            work_packages.append({
                "id": package_id,
                "title": wp_title,
                "status": "TODO",
                "description": detail or name,
                "inputs": ["v6.0 项目需求基线", f"{title} 上游输入与代码现状"],
                "outputs": [f"{title} / {name} 的实现与验收证据"],
                "scope": [detail or name],
                "estimate_points": 1,
                "progress_items": [
                    {"id": f"{package_id}-P1", "title": "范围与设计", "weight": 1, "done": False, "evidence": []},
                    {"id": f"{package_id}-P2", "title": "实现交付物", "weight": 2, "done": False, "evidence": []},
                    {"id": f"{package_id}-P3", "title": "验收与归档", "weight": 1, "done": False, "evidence": []},
                ],
                "acceptance_criteria": [{
                    "id": f"{package_id}-AC1",
                    "method": "针对本二级功能运行单元/契约测试并审查产物",
                    "metric": "验收用例通过率与证据可追溯率",
                    "target": "通过率 100%，可追溯率 100%",
                    "status": "NOT_RUN",
                }],
                "research_topic": {
                    "id": f"R-{package_id}",
                    "title": f"{title}：{wp_title} 的关键技术与验证方法",
                    "question": f"如何可靠实现并验证“{detail or name}”，以及哪些失败路径需要形成可复用经验？",
                },
            })
        features.append({"id": f"F-{feature_index:02d}", "title": title, "description": description, "weight": 1, "work_packages": work_packages})

    week_blocks = re.findall(r'<article class="week(?:\s+current)?"([^>]*)>(.*?)</article>', source, flags=re.S)
    weeks = []
    week_phases = {}
    for index, (attributes, block) in enumerate(week_blocks, start=1):
        start = re.search(r'data-start="([0-9-]+)"', attributes)
        end = re.search(r'data-end="([0-9-]+)"', attributes)
        if not start or not end:
            continue
        objective_match = re.search(r"<h3>(.*?)</h3>", block, flags=re.S)
        if objective_match:
            objective = _plain(objective_match.group(1))
            deliverables = [_plain(item) for item in re.findall(r"<li>(.*?)</li>", block, flags=re.S) if _plain(item)]
            delivery_match = re.search(r'<div class="deliverable">(.*?)</div>', block, flags=re.S)
            if delivery_match:
                deliverables.append(_plain(delivery_match.group(1)))
        else:
            titles = [_plain(item) for item in re.findall(r'<div class="work-item-title">(.*?)</div>', block, flags=re.S)]
            objective = "本周成果归档与后续计划准备"
            deliverables = titles or ["本周工作成果与验收记录"]
        weeks.append({
            "id": f"W-{start.group(1)}",
            "start": start.group(1),
            "end": end.group(1),
            "objective": objective,
            "deliverables": deliverables,
        })
        week_phases[start.group(1)] = re.search(r'data-phase="([^"]+)"', attributes).group(1) if re.search(r'data-phase="([^"]+)"', attributes) else "p0"

    if not features or not weeks:
        raise ValueError("legacy HTML did not contain recognizable L1 features, L2 items and weekly plans")
    last_week_end = max(week["end"] for week in weeks)
    p0_end = max((week["end"] for week in weeks if week_phases.get(week["start"]) == "p0"), default=last_week_end)
    milestones = [
        {"id": "MS-P0", "title": "P0 功能链路与验收", "date": p0_end, "acceptance": "P0 周计划对应的功能完成验收，失败项进入修复和复验闭环。", "status": "TODO"},
        {"id": "MS-ROADMAP", "title": "当前路线图阶段完成", "date": last_week_end, "acceptance": "周计划交付物均有对应证据链接并完成归档。", "status": "TODO"},
    ]
    return {
        "schema_version": 1,
        "project": {"id": "SOTIF-FORGE-V6", "name": "SOTIF FORGE · v6.0 功能与交付", "timezone": "Asia/Shanghai", "migration_status": "DRAFT_REQUIRES_OWNER_REVIEW"},
        "objectives": [{
            "id": "O-SOTIF-1",
            "title": "建立从产品特定风险分析到场景验证证据的可追溯交付链路",
            "key_results": [
                {"id": "KR-SOTIF-1", "metric": "已验收 Work Package 占比", "target": "100% 的目标范围内 Work Package 达到 DONE", "measurement_method": "按验收证据与项目状态 JSON 计算"},
                {"id": "KR-SOTIF-2", "metric": "关键交付物来源可追溯率", "target": "100%", "measurement_method": "验收记录中的证据链接审计"},
            ],
        }],
        "features": features,
        "milestones": milestones,
        "weeks": weeks,
        "execution_log": [],
        "experiments": [],
        "work_logs": {"daily": [], "weekly": [], "monthly": []},
        "migration_notes": [
            "导入的历史 HTML 状态标签属于代码盘点和手工进度，不作为 DONE 验收证据；迁移后所有二级功能先置为 TODO，避免把未验证进度误报为完成。",
            "验收口径、目标日期和 OKR 为可编辑草案；项目负责人审阅后再作为基线。",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate the existing feature/week HTML prototype into project-state JSON")
    parser.add_argument("html_path")
    parser.add_argument("output_path")
    arguments = parser.parse_args()
    state = migrate_legacy_html(arguments.html_path)
    from project_state import validate_project_state
    errors = validate_project_state(state)
    if errors:
        raise SystemExit("migration produced invalid state: " + "; ".join(errors))
    output = Path(arguments.output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Migrated {len(state['features'])} features, {sum(len(f['work_packages']) for f in state['features'])} work packages and {len(state['weeks'])} weeks to {output}")


if __name__ == "__main__":
    main()
