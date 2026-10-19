"""Looma AEP workflow: host Agent proposes; Python validates and publishes."""

from __future__ import annotations

import json
import hashlib
import os
import argparse
import re
import tempfile
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Mapping

try:
    from looma import agent, step, workflow
except ImportError as error:  # pragma: no cover - exercised by installation contract
    raise RuntimeError("Install Looma Runtime 1.0.0 from skills/ai-project-management/requirements.txt") from error

from execution_log import group_work_logs, read_events
from project_state import (
    apply_status_transition,
    compute_feature_progress,
    compute_project_progress,
    compute_work_package_progress,
    derive_work_package_status,
    validate_project_state,
)
from render_dashboard import evidence_prefix_for_output, render_dashboard

DASHBOARD_SHELL_PATH = Path(__file__).resolve().parents[1] / "assets" / "dashboard-shell.html"
DEFAULT_DASHBOARD_OUTPUT = "project-management/项目管理.html"
LOOMA_RUNTIME_VERSION = "1.0.0"


def require_looma_runtime_100() -> None:
    """Reject a different installed Looma runtime before starting a workflow run."""
    try:
        import looma
    except ImportError as error:
        raise RuntimeError("Install the bundled Looma Runtime 1.0.0 wheel from skills/ai-project-management/vendor/") from error
    installed = str(getattr(looma, "__version__", "unknown"))
    if installed != LOOMA_RUNTIME_VERSION:
        raise RuntimeError(
            f"This workflow requires Looma Runtime {LOOMA_RUNTIME_VERSION}; found {installed}. "
            "Install it with: python -m pip install -r skills/ai-project-management/requirements.txt"
        )


def resolve_project_name(project_root: str | Path) -> dict[str, str]:
    """Resolve a stable project display name from local repository metadata."""
    root = Path(project_root).resolve()
    metadata: list[tuple[str, str]] = []
    for filename, section in (("pyproject.toml", "project"), ("Cargo.toml", "package"), ("setup.cfg", "metadata")):
        path = root / filename
        if not path.is_file():
            continue
        contents = path.read_text(encoding="utf-8", errors="replace")
        if filename == "pyproject.toml":
            match = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", contents)
            block = match.group(1) if match else ""
            name_match = re.search(r"(?m)^\s*name\s*=\s*['\"]([^'\"]+)['\"]", block)
        elif filename == "Cargo.toml":
            match = re.search(r"(?ms)^\[package\]\s*(.*?)(?=^\[|\Z)", contents)
            block = match.group(1) if match else ""
            name_match = re.search(r"(?m)^\s*name\s*=\s*['\"]([^'\"]+)['\"]", block)
        else:
            match = re.search(r"(?ms)^\[metadata\]\s*(.*?)(?=^\[|\Z)", contents)
            block = match.group(1) if match else ""
            name_match = re.search(r"(?m)^\s*name\s*=\s*([^\s#]+)", block)
        if name_match and name_match.group(1).strip():
            metadata.append((name_match.group(1).strip(), filename))
    for filename, name_key in (("package.json", "name"), ("composer.json", "name")):
        path = root / filename
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get(name_key)
        except (OSError, json.JSONDecodeError, AttributeError):
            value = None
        if isinstance(value, str) and value.strip():
            metadata.append((value.strip(), filename))
    if metadata:
        name, source = metadata[0]
        return {"name": name, "source": source}
    for filename in ("README.md", "README.rst", "README.txt"):
        path = root / filename
        if not path.is_file():
            continue
        first_heading = next((line.strip().lstrip("#").strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip().startswith("#")), "")
        if first_heading and first_heading.casefold() not in {"readme", "overview", "项目说明"}:
            return {"name": first_heading, "source": filename}
    return {"name": root.name or "Local Project", "source": "repository_root_directory"}


def load_project_state(path: str | Path, execution_log_path: str | Path | None = None, experiments_path: str | Path | None = None) -> dict[str, Any]:
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load project state {path}: {error}") from error
    if not isinstance(state, dict):
        raise ValueError("project state root must be a JSON object")
    errors = validate_project_state(state)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    for key, log_path in (("execution_log", execution_log_path), ("experiments", experiments_path)):
        if log_path is not None:
            records, record_errors = read_events(log_path)
            if record_errors:
                raise ValueError("cannot update dashboard from malformed JSONL: " + "; ".join(record_errors))
            project_id = str(state.get("project", {}).get("id", ""))
            # Legacy events without a project_id belong to this workspace's current state;
            # new records are explicitly scoped by the recorder.
            state[key] = [record for record in records if record.get("project_id") == project_id or not record.get("project_id")]
    return state


def _index_work_packages(state: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(wp["id"]): wp for feature in state.get("features", []) for wp in feature.get("work_packages", [])}


def validate_project_identity(
    project_root: str | Path,
    reference_html_path: str | Path | None,
    proposal: Mapping[str, Any],
    resolved_name: Mapping[str, str],
) -> dict[str, Any]:
    """Require an evidence-backed project choice before any plan can be published."""
    identity = proposal.get("project_identity") if isinstance(proposal, Mapping) else None
    if not isinstance(identity, Mapping):
        raise ValueError("Agent must return project_identity before proposing page content")
    if identity.get("status") != "identified":
        question = str(identity.get("clarifying_question", "无法从当前项目资料唯一判断目标项目。"))
        raise ValueError("project identity needs user clarification; nothing was published: " + question)
    root_value = str(identity.get("source_root", "")).strip()
    project_id = str(identity.get("project_id", "")).strip()
    project_name = str(resolved_name.get("name", "")).strip()
    project_name_source = str(resolved_name.get("source", "")).strip()
    rationale = str(identity.get("selection_reason", "")).strip()
    evidence = identity.get("evidence_files")
    if not root_value or not project_id or not project_name or not project_name_source or not rationale or not isinstance(evidence, list) or not evidence:
        raise ValueError("project_identity requires source_root, project_id, selection_reason, and evidence_files; project name must resolve from local repository metadata")
    root = Path(root_value)
    if not root.is_absolute():
        root = Path(project_root) / root
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"project identity source_root does not exist: {root}")
    active_root = Path(project_root).resolve()
    if root != active_root:
        raise ValueError(f"the user selected the current local project; source_root must be the active project root: {active_root}")
    reference = Path(reference_html_path).resolve() if reference_html_path else None
    accepted: list[dict[str, str]] = []
    has_product_source = False
    for item in evidence:
        if not isinstance(item, Mapping):
            continue
        raw_path = str(item.get("path", "")).strip()
        kind = str(item.get("kind", "")).strip()
        claim = str(item.get("supports", "")).strip()
        if not raw_path or not kind or not claim:
            continue
        source = Path(raw_path)
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.is_file() or source == reference:
            continue
        try:
            relative = source.relative_to(root)
        except ValueError:
            continue
        parts = {part.casefold() for part in relative.parts}
        if "project-management" in parts or source == reference:
            continue
        accepted.append({"path": str(source), "kind": kind, "supports": claim})
        if kind in {"implementation", "product_spec", "product_documentation", "product_config"}:
            has_product_source = True
    if not accepted or not has_product_source:
        raise ValueError("project identity evidence must cite existing project code/spec/config files outside generated project-management data and any supplied reference HTML")
    proposed_state = proposal.get("project_state")
    proposed_project = proposed_state.get("project", {}) if isinstance(proposed_state, Mapping) else {}
    if str(proposed_project.get("id", "")) != project_id:
        raise ValueError("project_state.project.id must match the evidence-backed project_identity")
    normalized = deepcopy(dict(proposal))
    normalized_identity = deepcopy(dict(identity))
    normalized_identity["project_name"] = project_name
    normalized_identity["project_name_source"] = project_name_source
    normalized["project_identity"] = normalized_identity
    state = deepcopy(dict(proposed_state))
    state_project = deepcopy(dict(state.get("project", {})))
    state_project["name"] = project_name
    state_project["name_source"] = project_name_source
    state_project["source_root"] = str(root)
    state_project["identity_selection_reason"] = rationale
    state_project["identity_evidence"] = accepted
    state["project"] = state_project
    normalized["project_state"] = state
    return normalized


def validate_feature_inventory(
    project_root: str | Path,
    reference_html_path: str | Path | None,
    proposal: Mapping[str, Any],
) -> dict[str, Any]:
    """Gate downstream planning on a populated, traceable feature inventory."""
    inventory = proposal.get("feature_inventory") if isinstance(proposal, Mapping) else None
    if not isinstance(inventory, Mapping):
        raise ValueError("Agent must establish feature_inventory before proposing OKRs, WBS, solutions, or schedules")
    status = str(inventory.get("status", ""))
    if status == "needs_user_input":
        question = str(inventory.get("question", "请提供项目功能清单，或确认从本地代码和文档推导。"))
        return {"status": "needs_user_input", "question": question}
    if status != "ready":
        raise ValueError("feature_inventory.status must be ready or needs_user_input")
    source = str(inventory.get("source", ""))
    if source not in {"existing_inventory", "repository_inferred", "user_provided"}:
        raise ValueError("feature_inventory.source must identify existing_inventory, repository_inferred, or user_provided")
    items = inventory.get("features")
    state = proposal.get("project_state")
    state_features = state.get("features") if isinstance(state, Mapping) else None
    if not isinstance(items, list) or not items or not isinstance(state_features, list) or not state_features:
        raise ValueError("a ready feature inventory and project_state.features must both be non-empty")
    if len(items) != len(state_features):
        raise ValueError("feature inventory must match project_state.features one-to-one")

    root = Path(project_root).resolve()
    reference = Path(reference_html_path).resolve() if reference_html_path else None
    normalized = deepcopy(dict(proposal))
    normalized_state = deepcopy(dict(state))
    normalized_features = {str(item.get("id", "")): item for item in normalized_state["features"] if isinstance(item, Mapping)}
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError("each feature_inventory entry must be an object")
        feature_id = str(item.get("id", "")).strip()
        title = str(item.get("title", "")).strip()
        evidence = item.get("evidence")
        if not feature_id or not title or feature_id in seen or not isinstance(evidence, list) or not evidence:
            raise ValueError("each inventory feature requires a unique id, title, and evidence list")
        seen.add(feature_id)
        feature = normalized_features.get(feature_id)
        if feature is None or str(feature.get("title", "")).strip() != title:
            raise ValueError(f"feature inventory entry {feature_id} must match project_state.features")
        accepted: list[dict[str, str]] = []
        for reference_item in evidence:
            if not isinstance(reference_item, Mapping):
                continue
            raw_path = str(reference_item.get("path", "")).strip()
            supports = str(reference_item.get("supports", "")).strip()
            if not raw_path or not supports:
                continue
            if raw_path == "user_input" and source == "user_provided":
                accepted.append({"path": raw_path, "supports": supports})
                continue
            file_path = Path(raw_path)
            if not file_path.is_absolute():
                file_path = root / file_path
            file_path = file_path.resolve()
            if not file_path.is_file() or file_path == reference:
                continue
            try:
                relative = file_path.relative_to(root)
            except ValueError:
                continue
            parts = {part.casefold() for part in relative.parts}
            if "project-management" in parts and not (source == "existing_inventory" and relative.as_posix() == "project-management/project-state.json"):
                continue
            accepted.append({"path": str(file_path), "supports": supports})
        if not accepted:
            raise ValueError(f"feature {feature_id} needs at least one valid evidence source")
        feature["source_evidence"] = accepted
    if seen != set(normalized_features):
        raise ValueError("feature inventory IDs must exactly match project_state.features IDs")
    normalized["project_state"] = normalized_state
    normalized["feature_inventory"] = {**dict(inventory), "features": items}
    return {"status": "ready", "proposal": normalized}


def validate_agent_proposal(current: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a complete agent snapshot and require explicit evidence for transitions."""
    if not isinstance(proposal, Mapping) or not isinstance(proposal.get("project_state"), Mapping):
        raise ValueError("agent proposal must contain project_state")
    candidate = deepcopy(dict(proposal["project_state"]))
    current_project_id = str(current.get("project", {}).get("id", ""))
    proposed_project = candidate.get("project", {})
    proposed_project_id = str(proposed_project.get("id", "")) if isinstance(proposed_project, Mapping) else ""
    identity_rebaseline = bool(current_project_id and proposed_project_id and current_project_id != proposed_project_id)
    plan_rebaseline = bool(
        current_project_id
        and proposed_project_id == current_project_id
        and proposed_project.get("plan_rebased_from") == current_project_id
        and str(proposed_project.get("plan_rebase_reason", "")).strip()
    )
    is_rebaseline = identity_rebaseline or plan_rebaseline
    if identity_rebaseline:
        if proposed_project.get("baseline_rebased_from") != current_project_id or not str(proposed_project.get("baseline_rebase_reason", "")).strip():
            raise ValueError("project identity changes require baseline_rebased_from and baseline_rebase_reason")
        if current.get("experiments"):
            raise ValueError("cannot rebaseline while experiment history exists; archive or map it explicitly first")
    old_features = {str(item["id"]): item for item in current.get("features", [])}
    new_features = {str(item.get("id", "")): item for item in candidate.get("features", [])}
    missing_features = set() if is_rebaseline else set(old_features) - set(new_features)
    if missing_features:
        raise ValueError("agent proposal cannot remove existing features: " + ", ".join(sorted(missing_features)))
    old_wps = _index_work_packages(current)
    new_wps = _index_work_packages(candidate)
    missing_wps = set() if is_rebaseline else set(old_wps) - set(new_wps)
    if missing_wps:
        raise ValueError("agent proposal cannot remove existing work packages: " + ", ".join(sorted(missing_wps)))
    old_topics = {
        str(topic.get("id")): topic
        for feature in current.get("features", [])
        for wp in feature.get("work_packages", [])
        for topic in [wp.get("research_topic")]
        if isinstance(topic, Mapping)
    }
    new_topics = {
        str(topic.get("id")): topic
        for feature in candidate.get("features", [])
        for wp in feature.get("work_packages", [])
        for topic in [wp.get("research_topic")]
        if isinstance(topic, Mapping)
    }
    for topic_id, old_topic in old_topics.items() if not is_rebaseline else []:
        old_solutions = {str(item.get("id")) for item in old_topic.get("solutions", []) if isinstance(item, Mapping)}
        new_topic = new_topics.get(topic_id)
        new_solutions = {
            str(item.get("id")) for item in (new_topic or {}).get("solutions", []) if isinstance(item, Mapping)
        }
        removed_solutions = old_solutions - new_solutions
        if removed_solutions:
            raise ValueError(
                f"agent proposal cannot remove existing solutions from topic {topic_id}: "
                + ", ".join(sorted(removed_solutions))
            )
    # JSONL is append-only and is the authority for execution/research history.
    candidate["execution_log"] = deepcopy(list(current.get("execution_log", [])))
    candidate["experiments"] = deepcopy(list(current.get("experiments", [])))
    for wp_id, new_wp in new_wps.items() if not is_rebaseline else []:
        old_wp = old_wps.get(wp_id)
        if old_wp is None:
            if new_wp.get("status", "TODO") != "TODO":
                raise ValueError(f"new work package {wp_id} must start in TODO")
            continue
        if new_wp.get("status") != old_wp.get("status"):
            evidence = new_wp.get("transition_evidence")
            if not isinstance(evidence, Mapping):
                raise ValueError(f"status change for {wp_id} requires transition_evidence")
            transition_input = deepcopy(new_wp)
            transition_input["status"] = old_wp.get("status")
            transition_input["status_history"] = deepcopy(old_wp.get("status_history", []))
            transitioned = apply_status_transition(transition_input, str(new_wp["status"]), evidence=evidence)
            new_wp["status_history"] = transitioned["status_history"]
            new_wp.pop("transition_evidence", None)
    errors = validate_project_state(candidate)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    return candidate


def recalculate_project_state(state: Mapping[str, Any], reference_date: str | None = None) -> dict[str, Any]:
    """Recompute evidence-based WP, L1, and project progress before rendering."""
    errors = validate_project_state(state)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    updated = deepcopy(dict(state))
    for feature in updated["features"]:
        for work_package in feature["work_packages"]:
            work_package["progress"] = round(compute_work_package_progress(work_package), 2)
            work_package["status"] = derive_work_package_status(work_package)
        feature["progress"] = round(compute_feature_progress(feature), 2)
    updated["project"]["progress"] = round(compute_project_progress(updated), 2)
    target_date = date.fromisoformat(reference_date) if reference_date else date.today()
    topic_owner = {
        work_package.get("research_topic", {}).get("id"): (feature["id"], work_package["id"])
        for feature in updated["features"] for work_package in feature["work_packages"]
    }
    activity = list(updated.get("execution_log", []))
    for experiment in updated.get("experiments", []):
        feature_id, work_package_id = topic_owner.get(experiment.get("topic_id"), ("", ""))
        activity.append({
            **experiment,
            "feature_id": experiment.get("feature_id", feature_id),
            "work_package_id": experiment.get("work_package_id", work_package_id),
            "summary": f"{experiment.get('result', '实验')}：{experiment.get('hypothesis', '')}；结论：{experiment.get('conclusion', '')}",
        })
    updated["work_logs"] = group_work_logs(activity, target_date)
    return updated


def render_state_html(template_path: str | Path, state: Mapping[str, Any], evidence_prefix: str = "") -> str:
    errors = validate_project_state(state)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    return render_dashboard(Path(template_path).read_text(encoding="utf-8"), state, evidence_prefix)


def verify_rendered_dashboard(html: str, state: Mapping[str, Any]) -> dict[str, Any]:
    """Verify that the rendered HTML embeds exactly the validated state and required views."""
    start = '<script type="application/json" id="ai-pm-state">'
    end = "</script>"
    if html.count(start) != 1:
        raise ValueError("rendered dashboard must contain exactly one embedded project state")
    offset = html.index(start) + len(start)
    close = html.find(end, offset)
    if close < 0:
        raise ValueError("rendered project state script is not closed")
    embedded = json.loads(html[offset:close])
    if embedded != state:
        raise ValueError("rendered dashboard state does not match the validated project state")
    required = (
        "feature-workspace",
        'id="aipm-project-view-nav"',
        'aria-label="一级功能内容导航"',
        'aria-label="二级功能详情导航"',
        'aria-label="项目视图导航"',
        'data-view="work-package-detail"',
        'data-view="research-detail"',
        'event.work_package_id===workPackage.id',
        '所属二级功能 · ${safe(workPackage.id)}',
        '该研究课题未关联二级功能，无法打开。',
        'data-project-page-view="okr"',
        'data-project-page-view="wbs"',
        'data-project-page-view="milestones"',
        'data-solution-id=',
        'const outcomeChart=',
        'solution.data_source',
        'id="okr-table"',
        'id="wbs-table"',
        'aria-label="执行记录时间线，横轴为时间，纵轴为 Work Package 状态"',
        "research-topic-link",
        "aipm-evidence-unavailable",
        'data-schedule-view="weekly"',
        'data-schedule-view="monthly"',
        "aipm-state-plan",
        "const routeScrollPositions=new Map()",
        "function navigateBack(fallback=",
        "let routeHistory=[location.hash]",
        "window.addEventListener('popstate'",
        "window.history.back()",
    )
    missing = [marker for marker in required if marker not in html]
    if missing:
        raise ValueError("rendered dashboard is missing required views: " + ", ".join(missing))
    return {"valid": True, "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(), "features": len(state["features"])}


def publish_validated_update(
    template_path: str | Path,
    state: Mapping[str, Any],
    output_path: str | Path,
    state_output_path: str | Path | None = None,
    rendered_html: str | None = None,
    verification: Mapping[str, Any] | None = None,
    mirror_output_path: str | Path | None = None,
    mirror_html: str | None = None,
    mirror_verification: Mapping[str, Any] | None = None,
) -> str:
    """Stage and publish the dashboard plus its source state only after validation."""
    errors = validate_project_state(state)
    if errors:
        raise ValueError("invalid project state: " + "; ".join(errors))
    html = rendered_html if rendered_html is not None else render_state_html(template_path, state)
    if verification is None or verification.get("valid") is not True or verification.get("html_sha256") != hashlib.sha256(html.encode("utf-8")).hexdigest():
        raise ValueError("dashboard output must pass render verification before publishing")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    targets = [(target, html)]
    if mirror_output_path is not None:
        if mirror_html is None or mirror_verification is None or mirror_verification.get("valid") is not True or mirror_verification.get("html_sha256") != hashlib.sha256(mirror_html.encode("utf-8")).hexdigest():
            raise ValueError("mirror dashboard output must pass render verification before publishing")
        mirror_target = Path(mirror_output_path)
        mirror_target.parent.mkdir(parents=True, exist_ok=True)
        targets.append((mirror_target, mirror_html))
    if state_output_path is not None:
        state_target = Path(state_output_path)
        state_target.parent.mkdir(parents=True, exist_ok=True)
        targets.append((state_target, json.dumps(state, ensure_ascii=False, indent=2) + "\n"))
    staged: list[tuple[Path, str]] = []
    previous: dict[Path, bytes | None] = {}
    try:
        for destination, contents in targets:
            previous[destination] = destination.read_bytes() if destination.exists() else None
            descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
            staged.append((destination, temporary))
        for destination, temporary in staged:
            os.replace(temporary, destination)
    except Exception:
        for destination, content in previous.items():
            if content is None:
                destination.unlink(missing_ok=True)
            else:
                descriptor, restore_path = tempfile.mkstemp(prefix=f".{destination.name}.rollback.", dir=destination.parent)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(restore_path, destination)
        for _, temporary in staged:
            Path(temporary).unlink(missing_ok=True)
        raise
    return str(target)


@workflow
def update_project(project_root: str, state_path: str, reference_html_path: str | None, output_path: str) -> dict[str, Any]:
    """Run the user-triggered deterministic plan update workflow through Looma."""
    require_looma_runtime_100()
    if reference_html_path and Path(reference_html_path).resolve() == Path(output_path).resolve():
        raise ValueError("reference HTML is read-only and cannot be used as the dashboard output")
    management_dir = Path(state_path).parent
    current = step(load_project_state, state_path, management_dir / "execution-log.jsonl", management_dir / "experiments.jsonl")
    resolved_name = step(resolve_project_name, project_root)
    reference_guidance = (
        "If a separate HTML is supplied, treat it as read-only visual/structural input: extract useful modules and interactions only; never reuse its project identity, feature names, data, plans, or full shell. "
        if reference_html_path else
        "No external HTML reference is supplied. Use the independent dashboard shell in skills/ai-project-management/assets/dashboard-shell.html for structure and interactions; derive project content from this repository. "
    )
    proposal = agent(
        task=(
            "The user has explicitly selected the current local workspace as the target project. Analyze this repository itself; do not search neighboring repositories or ask for a project path. "
            "The first planning input is a feature inventory. First search the active repository, its documentation, and the current structured project state for an existing feature list; reconcile it with real implementation evidence. If no explicit list exists but the code and documentation clearly define the product's capabilities, generate a sourced feature_inventory before any other planning and use that list as the sole L1 feature source. If repository evidence cannot establish a reliable list or scope is ambiguous, return feature_inventory.status='needs_user_input' with one question asking the user to provide a feature list or authorize repository-based derivation; do not generate OKRs, requirements, technical solutions, WBS, milestones, or schedules in that case. "
            "Return feature_inventory as {status:'ready'|'needs_user_input', source:'existing_inventory'|'repository_inferred'|'user_provided', features:[{id,title,evidence:[{path,supports}]}], question?}. A ready inventory must be non-empty, cite an existing source for every feature, and match project_state.features one-to-one. Repository-inferred features must cite implementation/spec evidence. For user-provided features, use path='user_input' and describe the provided scope in supports. "
            + reference_guidance +
            "The generated dashboard must use the independent dashboard shell supplied by the workflow. The local product is the AI-assisted project-management capability being developed in this repository: its Skill, scripts, schemas, and product specifications are valid product evidence. Exclude only generated project-management state/log/output files and the reference HTML from product evidence. "
            "Ground the project identity and every feature in existing code, schemas, plans, or specifications under the active project root. If the repository evidence is sufficient, identify it directly; do not ask the user to repeat the already selected project. "
            "The project display name is resolved deterministically from local metadata and is provided as resolved_project_name in input. Use it exactly when summarizing project identity; do not invent a descriptive suffix or use a feature/skill name as the project name. Python will enforce the resolved name in project_state. "
            "Return project_identity with status, source_root, project_id, selection_reason, and evidence_files (each with path, kind, supports). Keep project_state.project.id aligned with project_identity; Python supplies the project display name from resolved_project_name. "
            "The current feature plan is explicitly known to contain content copied from an unrelated SOTIF example. Keep the project's identity, but replace that incorrect feature/WBS baseline with a repo-grounded plan. Set project.plan_rebased_from to the current project id and give a concise plan_rebase_reason. This authorizes removing incorrect feature and Work Package entries while preserving append-only execution and experiment history. Do not copy the reference HTML's project data. "
            "For ordinary updates preserve existing feature and Work Package IDs; the explicit plan rebaseline above may replace IDs from the incorrect SOTIF-derived plan. Propose a complete updated project_state JSON snapshot; include OKRs, weekly plans, milestones, inputs, outputs, scope, measurable acceptance criteria, "
            "and research topics with solution groups (solution id, name, method, data source, evidence-based conclusion) where repository evidence supports them. "
            "Preserve all existing research solution IDs unless doing the explicit project identity rebaseline above; add solutions only when supported by repository or experiment evidence, and do not fabricate experiments. "
            "Link each experiment to its topic and solution, and cite its data source; leave unsupported plans or conclusions empty instead of inventing them. "
            "For every Work Package status change, include transition_evidence with kind, ref, and reason where required. "
            "Do not invent completion evidence, metrics, test results, or links. Return {feature_inventory, project_identity, project_state, summary}; no markdown."
        ),
        input={"project_root": project_root, "resolved_project_name": resolved_name, "reference_html_path": reference_html_path, "current_project_state": current},
        output_schema=dict,
    )
    inventory_result = step(validate_feature_inventory, project_root, reference_html_path, proposal)
    if inventory_result["status"] == "needs_user_input":
        return {"status": "needs_user_input", "question": inventory_result["question"], "published": False}
    proposal = inventory_result["proposal"]
    identified = step(validate_project_identity, project_root, reference_html_path, proposal, resolved_name)
    validated = step(validate_agent_proposal, current, identified)
    calculated = step(recalculate_project_state, validated)
    rendered = step(render_state_html, str(DASHBOARD_SHELL_PATH), calculated, evidence_prefix_for_output(project_root, output_path))
    verification = step(verify_rendered_dashboard, rendered, calculated)
    published = step(publish_validated_update, str(DASHBOARD_SHELL_PATH), calculated, output_path, state_path, rendered, verification)
    return {"output_path": published, "project_id": calculated["project"]["id"], "progress": calculated["project"]["progress"]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Looma-driven project management update workflow")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--state", required=True, help="Project state JSON path")
    parser.add_argument("--reference-html", "--template", dest="reference_html", help="Optional HTML visual/structural reference; it is never used as the output shell")
    parser.add_argument("--output", default=DEFAULT_DASHBOARD_OUTPUT, help=f"HTML dashboard output path (default: {DEFAULT_DASHBOARD_OUTPUT})")
    arguments = parser.parse_args()
    result = update_project(arguments.project_root, arguments.state, arguments.reference_html, arguments.output)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
