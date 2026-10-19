"""Validate project state, enforce work-package transitions, and compute progress."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any, Iterable, Mapping

STATUSES = (
    "TODO", "READY", "IN_PROGRESS", "IMPLEMENTED", "VERIFYING", "DONE",
    "BLOCKED", "FAILED", "FIXING",
)
TRANSITIONS = {
    "TODO": {"READY"},
    "READY": {"IN_PROGRESS", "BLOCKED"},
    "IN_PROGRESS": {"IMPLEMENTED", "BLOCKED"},
    "IMPLEMENTED": {"VERIFYING", "BLOCKED"},
    "VERIFYING": {"DONE", "BLOCKED", "FAILED"},
    "BLOCKED": {"FIXING"},
    "FAILED": {"FIXING"},
    "FIXING": {"VERIFYING", "BLOCKED", "FAILED"},
    "DONE": set(),
}


def _positive_weight(value: Any) -> float:
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 0.0
    return weight if weight > 0 else 0.0


def _has_evidence(evidence: Any) -> bool:
    if isinstance(evidence, str):
        return bool(evidence.strip())
    if isinstance(evidence, (list, tuple)):
        return any(_has_evidence(item) for item in evidence)
    if isinstance(evidence, Mapping):
        return bool(str(evidence.get("ref", "")).strip() or str(evidence.get("url", "")).strip())
    return False


def _weighted_average(values: Iterable[tuple[float, float]]) -> float:
    rows = [(value, weight) for value, weight in values if weight > 0]
    if not rows:
        return 0.0
    total_weight = sum(weight for _, weight in rows)
    return sum(value * weight for value, weight in rows) / total_weight


def compute_work_package_progress(work_package: Mapping[str, Any]) -> float:
    """Compute progress from weighted, evidence-backed delivery checkpoints."""
    items = work_package.get("progress_items", [])
    rows = []
    for item in items:
        weight = _positive_weight(item.get("weight"))
        done = item.get("done") is True and _has_evidence(item.get("evidence"))
        rows.append((100.0 if done else 0.0, weight))
    return _weighted_average(rows)


def derive_work_package_status(work_package: Mapping[str, Any]) -> str:
    """Advance at most one legal state from evidence; failures require an explicit fix/retest."""
    history = work_package.get("status_history", [])
    status = history[-1].get("to") if history else work_package.get("status", "TODO")
    criteria = work_package.get("acceptance_criteria", [])
    dependency_states = work_package.get("dependency_states", [])
    latest_evidence = history[-1].get("evidence", {}) if history else {}
    if status == "TODO" and work_package.get("contract_approved") is True and all(dep.get("status") == "DONE" for dep in dependency_states):
        return "READY"
    if status == "READY" and _has_evidence(work_package.get("start_evidence") or (latest_evidence if latest_evidence.get("kind") in {"start", "execution"} else None)):
        return "IN_PROGRESS"
    if status == "IN_PROGRESS" and _has_evidence(work_package.get("implementation_evidence")):
        return "IMPLEMENTED"
    if status == "IMPLEMENTED" and _has_evidence(work_package.get("verification_evidence")):
        return "VERIFYING"
    if status == "VERIFYING":
        if criteria and all(item.get("status") == "PASS" and _has_evidence(item.get("evidence")) for item in criteria):
            return "DONE"
        if any(item.get("status") == "FAIL" and _has_evidence(item.get("evidence")) for item in criteria):
            return "FAILED"
    if status in {"BLOCKED", "FAILED"} and _has_evidence(work_package.get("fix_plan_evidence")):
        return "FIXING"
    if status == "FIXING" and _has_evidence(work_package.get("rerun_evidence")):
        return "VERIFYING"
    return str(status) if status in STATUSES else "TODO"


def compute_feature_progress(feature: Mapping[str, Any]) -> float:
    """Aggregate L2 work-package progress using estimate_points or equal weights."""
    packages = feature.get("work_packages", [])
    if not packages:
        return 0.0
    estimates = [_positive_weight(wp.get("estimate_points")) for wp in packages]
    if not any(estimates):
        estimates = [1.0] * len(packages)
    else:
        estimates = [weight if weight > 0 else 1.0 for weight in estimates]
    return _weighted_average(
        (compute_work_package_progress(wp), weight)
        for wp, weight in zip(packages, estimates)
    )


def compute_project_progress(state: Mapping[str, Any]) -> float:
    """Aggregate L1 progress using feature weight or equal weights."""
    features = state.get("features", [])
    if not features:
        return 0.0
    weights = [_positive_weight(feature.get("weight")) for feature in features]
    if not any(weights):
        weights = [1.0] * len(features)
    else:
        weights = [weight if weight > 0 else 1.0 for weight in weights]
    return _weighted_average(
        (compute_feature_progress(feature), weight)
        for feature, weight in zip(features, weights)
    )


def _work_package_errors(work_package: Mapping[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    for field in ("id", "title", "description"):
        if not str(work_package.get(field, "")).strip():
            errors.append(f"{path}.{field} is required")
    for field in ("inputs", "outputs", "scope"):
        value = work_package.get(field)
        if not isinstance(value, list) or not value or not all(str(item).strip() for item in value):
            errors.append(f"{path}.{field} must be a non-empty list")
    if "estimate_points" in work_package and _positive_weight(work_package["estimate_points"]) <= 0:
        errors.append(f"{path}.estimate_points must be positive when provided")
    dependencies = work_package.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(isinstance(item, str) and item.strip() for item in dependencies):
        errors.append(f"{path}.dependencies must be a list of Work Package IDs")
    status = work_package.get("status")
    if status not in STATUSES:
        errors.append(f"{path}.status must be one of {', '.join(STATUSES)}")
    criteria = work_package.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria:
        errors.append(f"{path}.acceptance_criteria must contain at least one criterion")
    else:
        for index, criterion in enumerate(criteria):
            criterion_path = f"{path}.acceptance_criteria[{index}]"
            if not isinstance(criterion, Mapping):
                errors.append(f"{criterion_path} must be an object")
                continue
            for field in ("id", "method", "metric", "target"):
                if not str(criterion.get(field, "")).strip():
                    errors.append(f"{criterion_path}.{field} is required")
            criterion_status = criterion.get("status", "NOT_RUN")
            if criterion_status not in {"NOT_RUN", "PASS", "FAIL", "BLOCKED"}:
                errors.append(f"{criterion_path}.status is invalid")
            if criterion_status == "PASS" and not _has_evidence(criterion.get("evidence")):
                errors.append(f"{criterion_path}.evidence is required for PASS")
    topic = work_package.get("research_topic")
    if not isinstance(topic, Mapping) or not all(str(topic.get(field, "")).strip() for field in ("id", "title")):
        errors.append(f"{path}.research_topic with id and title is required")
    elif "solutions" in topic:
        solutions = topic["solutions"]
        if not isinstance(solutions, list):
            errors.append(f"{path}.research_topic.solutions must be a list")
        else:
            solution_ids: set[str] = set()
            for index, solution in enumerate(solutions):
                solution_path = f"{path}.research_topic.solutions[{index}]"
                if not isinstance(solution, Mapping):
                    errors.append(f"{solution_path} must be an object")
                    continue
                for field in ("id", "name", "method", "data_source"):
                    if not str(solution.get(field, "")).strip():
                        errors.append(f"{solution_path}.{field} is required")
                solution_id = str(solution.get("id", ""))
                if solution_id and solution_id in solution_ids:
                    errors.append(f"{solution_path}.id duplicates another solution")
                solution_ids.add(solution_id)
                if "conclusion" in solution and not isinstance(solution["conclusion"], str):
                    errors.append(f"{solution_path}.conclusion must be a string")
    progress_items = work_package.get("progress_items")
    if not isinstance(progress_items, list) or not progress_items:
        errors.append(f"{path}.progress_items must contain at least one checkpoint")
    else:
        for index, item in enumerate(progress_items):
            if not isinstance(item, Mapping):
                errors.append(f"{path}.progress_items[{index}] must be an object")
                continue
            if not str(item.get("id", "")).strip() or _positive_weight(item.get("weight")) <= 0:
                errors.append(f"{path}.progress_items[{index}] requires id and positive weight")
            if item.get("done") is True and not _has_evidence(item.get("evidence")):
                errors.append(f"{path}.progress_items[{index}].evidence is required when done")
    if status == "DONE" and criteria and any(
        item.get("status") != "PASS" or not _has_evidence(item.get("evidence")) for item in criteria
    ):
        errors.append(f"{path}.DONE requires all acceptance criteria to PASS with evidence")
    return errors


def validate_project_state(state: Mapping[str, Any]) -> list[str]:
    """Return all structural and evidence-contract errors in a project state."""
    errors: list[str] = []
    if state.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    project = state.get("project")
    if not isinstance(project, Mapping) or not project.get("id") or not project.get("name"):
        errors.append("project.id and project.name are required")
    elif "baseline_rebased_from" in project and (
        not str(project.get("baseline_rebased_from", "")).strip()
        or not str(project.get("baseline_rebase_reason", "")).strip()
    ):
        errors.append("project baseline rebase requires baseline_rebased_from and baseline_rebase_reason")
    if isinstance(project, Mapping) and "plan_rebased_from" in project and (
        not str(project.get("plan_rebased_from", "")).strip()
        or not str(project.get("plan_rebase_reason", "")).strip()
    ):
        errors.append("project plan rebase requires plan_rebased_from and plan_rebase_reason")
    objectives = state.get("objectives")
    if not isinstance(objectives, list) or not objectives:
        errors.append("objectives must contain at least one OKR objective")
    else:
        for index, objective in enumerate(objectives):
            if not isinstance(objective, Mapping):
                errors.append(f"objectives[{index}] must be an object")
                continue
            if not objective.get("id") or not objective.get("title") or not objective.get("key_results"):
                errors.append(f"objectives[{index}] requires id, title and measurable key_results")
            key_results = objective.get("key_results", [])
            if not isinstance(key_results, list):
                errors.append(f"objectives[{index}].key_results must be a list")
                continue
            for kr_index, result in enumerate(key_results):
                if not isinstance(result, Mapping):
                    errors.append(f"objectives[{index}].key_results[{kr_index}] must be an object")
                    continue
                if not all(str(result.get(field, "")).strip() for field in ("id", "metric", "target", "measurement_method")):
                    errors.append(f"objectives[{index}].key_results[{kr_index}] requires metric, target and measurement_method")
    milestones = state.get("milestones")
    if not isinstance(milestones, list) or not milestones:
        errors.append("milestones must contain at least one milestone")
    else:
        for index, milestone in enumerate(milestones):
            if not isinstance(milestone, Mapping):
                errors.append(f"milestones[{index}] must be an object")
                continue
            if not all(str(milestone.get(field, "")).strip() for field in ("id", "title", "date", "acceptance")):
                errors.append(f"milestones[{index}] requires id, title, date and acceptance")
            try:
                date.fromisoformat(str(milestone.get("date", "")))
            except ValueError:
                errors.append(f"milestones[{index}].date must be an ISO date")
    weeks = state.get("weeks")
    if not isinstance(weeks, list) or not weeks:
        errors.append("weeks must contain a weekly delivery plan")
    else:
        for index, week in enumerate(weeks):
            if not isinstance(week, Mapping):
                errors.append(f"weeks[{index}] must be an object")
                continue
            if not all(str(week.get(field, "")).strip() for field in ("id", "start", "end", "objective", "deliverables")):
                errors.append(f"weeks[{index}] requires id, start, end, objective and deliverables")
            if not isinstance(week.get("deliverables"), list) or not week["deliverables"]:
                errors.append(f"weeks[{index}].deliverables must be a non-empty list")
            try:
                first, last = date.fromisoformat(str(week.get("start", ""))), date.fromisoformat(str(week.get("end", "")))
                if last < first or (last - first).days > 6:
                    errors.append(f"weeks[{index}] must cover no more than one Monday-to-Sunday week")
            except ValueError:
                errors.append(f"weeks[{index}].start and end must be ISO dates")
    features = state.get("features")
    if not isinstance(features, list) or not features:
        errors.append("features must be a non-empty list")
        return errors
    feature_ids: set[str] = set()
    wp_ids: set[str] = set()
    for feature_index, feature in enumerate(features):
        feature_path = f"features[{feature_index}]"
        if not isinstance(feature, Mapping):
            errors.append(f"{feature_path} must be an object")
            continue
        feature_id = str(feature.get("id", ""))
        if not feature_id or not str(feature.get("title", "")).strip():
            errors.append(f"{feature_path}.id and title are required")
        if feature_id in feature_ids:
            errors.append(f"duplicate feature id: {feature_id}")
        feature_ids.add(feature_id)
        if "weight" in feature and _positive_weight(feature["weight"]) <= 0:
            errors.append(f"{feature_path}.weight must be positive when provided")
        packages = feature.get("work_packages")
        if not isinstance(packages, list) or not packages:
            errors.append(f"{feature_path}.work_packages must be a non-empty list")
            continue
        for package_index, package in enumerate(packages):
            package_path = f"{feature_path}.work_packages[{package_index}]"
            if not isinstance(package, Mapping):
                errors.append(f"{package_path} must be an object")
                continue
            package_id = str(package.get("id", ""))
            if package_id in wp_ids:
                errors.append(f"duplicate work-package id: {package_id}")
            wp_ids.add(package_id)
            errors.extend(_work_package_errors(package, package_path))
    for feature_index, feature in enumerate(features):
        if not isinstance(feature, Mapping) or not isinstance(feature.get("work_packages"), list):
            continue
        for package in feature["work_packages"]:
            if not isinstance(package, Mapping):
                continue
            dependencies = package.get("dependencies", [])
            if not isinstance(dependencies, list):
                continue
            for dependency in dependencies:
                if dependency == package.get("id"):
                    errors.append(f"work package {dependency} cannot depend on itself")
                elif dependency not in wp_ids:
                    errors.append(f"work package {package.get('id')} has unknown dependency {dependency}")
    experiments = state.get("experiments", [])
    if not isinstance(experiments, list):
        errors.append("experiments must be a list")
    else:
        solutions_by_topic = {
            str(topic.get("id")): {str(solution.get("id")) for solution in (topic.get("solutions") if isinstance(topic.get("solutions"), list) else []) if isinstance(solution, Mapping)}
            for feature in features if isinstance(feature, Mapping)
            for package in feature.get("work_packages", []) if isinstance(package, Mapping)
            for topic in [package.get("research_topic")] if isinstance(topic, Mapping)
        }
        for index, experiment in enumerate(experiments):
            if not isinstance(experiment, Mapping):
                errors.append(f"experiments[{index}] must be an object")
                continue
            solution_id = experiment.get("solution_id")
            topic_id = str(experiment.get("topic_id", ""))
            if solution_id and str(solution_id) not in solutions_by_topic.get(topic_id, set()):
                errors.append(f"experiments[{index}].solution_id must reference a solution under its topic")
    return errors


def _transition_gate(work_package: Mapping[str, Any], target: str, evidence: Mapping[str, Any]) -> None:
    kind = str(evidence.get("kind", "")).strip()
    if target == "READY":
        errors = _work_package_errors(work_package, "work_package")
        if errors:
            raise ValueError("READY requires a complete contract: " + "; ".join(errors))
        dependency_states = work_package.get("dependency_states", [])
        if not isinstance(dependency_states, list) or any(not isinstance(dep, Mapping) or dep.get("status") != "DONE" for dep in dependency_states):
            raise ValueError("READY requires every dependency to be DONE")
        completed_ids = {str(dep.get("id")) for dep in dependency_states if dep.get("status") == "DONE"}
        if not set(work_package.get("dependencies", [])).issubset(completed_ids):
            raise ValueError("READY requires every declared Work Package dependency to be DONE")
    elif target == "IN_PROGRESS" and kind not in {"start", "execution"}:
        raise ValueError("IN_PROGRESS requires start or execution evidence")
    elif target == "IMPLEMENTED":
        if not work_package.get("implementation_evidence") or not _has_evidence(work_package["implementation_evidence"]):
            raise ValueError("IMPLEMENTED requires implementation evidence")
    elif target == "VERIFYING" and kind not in {"verification", "rerun"}:
        raise ValueError("VERIFYING requires verification or rerun evidence")
    elif target == "DONE":
        criteria = work_package.get("acceptance_criteria", [])
        if not criteria or any(
            criterion.get("status") != "PASS" or not _has_evidence(criterion.get("evidence"))
            for criterion in criteria
        ):
            raise ValueError("DONE requires every acceptance criterion to PASS with evidence")
    elif target == "BLOCKED" and (kind != "blocker" or not evidence.get("reason")):
        raise ValueError("BLOCKED requires blocker evidence and a reason")
    elif target == "FAILED":
        if kind != "verification" or not evidence.get("reason"):
            raise ValueError("FAILED requires failed verification evidence and a reason")
    elif target == "FIXING" and kind != "fix-plan":
        raise ValueError("FIXING requires fix-plan evidence")


def apply_status_transition(
    work_package: Mapping[str, Any],
    target: str,
    *,
    evidence: Mapping[str, Any],
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Return a copied Work Package with one evidence-backed state transition."""
    source = work_package.get("status")
    if target not in STATUSES or target not in TRANSITIONS.get(str(source), set()):
        raise ValueError(f"invalid status transition: {source} -> {target}")
    if not isinstance(evidence, Mapping) or not _has_evidence(evidence):
        raise ValueError("status transition requires evidence")
    _transition_gate(work_package, target, evidence)
    updated = deepcopy(dict(work_package))
    updated["status"] = target
    history = list(updated.get("status_history", []))
    event = {"from": source, "to": target, "evidence": deepcopy(dict(evidence))}
    event["timestamp"] = timestamp or str(evidence.get("timestamp") or datetime.now(timezone.utc).isoformat(timespec="seconds"))
    history.append(event)
    updated["status_history"] = history
    return updated
