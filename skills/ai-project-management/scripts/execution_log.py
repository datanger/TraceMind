"""Append-only execution and research records for an AI-assisted project."""

from __future__ import annotations

import json
import argparse
import os
import tempfile
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

from project_state import validate_project_state

EVENT_REQUIRED = ("id", "timestamp", "kind", "summary", "evidence_links")
EXPERIMENT_REQUIRED = ("id", "timestamp", "topic_id", "solution_id", "data_source", "hypothesis", "method", "result", "observation", "conclusion", "evidence_links", "value")
VALUE_DIMENSIONS = ("impact", "novelty", "learning", "reuse")


def _validate_timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO-8601 string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("timestamp must be an ISO-8601 string") from error


def _validate_links(value: Any) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("evidence_links must be a non-empty list of links")


def _validate_record(record: Mapping[str, Any], required: tuple[str, ...]) -> None:
    missing = [field for field in required if field not in record]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    for field in ("id", "kind", "summary"):
        if field in required and (not isinstance(record[field], str) or not record[field].strip()):
            raise ValueError(f"{field} must be a non-empty string")
    _validate_timestamp(record["timestamp"])
    _validate_links(record["evidence_links"])


def append_event(path: str | Path, event: Mapping[str, Any]) -> None:
    """Append one validated event; existing lines are never rewritten."""
    if not isinstance(event, Mapping):
        raise ValueError("event must be an object")
    _validate_record(event, EVENT_REQUIRED)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(event), ensure_ascii=False, separators=(",", ":")) + "\n")


def record_execution(
    path: str | Path,
    *,
    kind: str,
    summary: str,
    evidence_links: list[str],
    feature_id: str = "",
    work_package_id: str = "",
    status_category: str = "",
    from_status: str = "",
    to_status: str = "",
    project_id: str = "",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create and append a timestamped execution event at the point it occurs."""
    event: dict[str, Any] = {
        "id": f"E-{uuid.uuid4().hex[:12]}",
        "timestamp": timestamp or datetime.now().astimezone().isoformat(timespec="seconds"),
        "kind": kind,
        "summary": summary,
        "evidence_links": list(evidence_links),
    }
    if project_id:
        event["project_id"] = project_id
    if feature_id:
        event["feature_id"] = feature_id
    if work_package_id:
        event["work_package_id"] = work_package_id
    if status_category:
        event["status_category"] = status_category
    if from_status:
        event["from"] = from_status
    if to_status:
        event["to"] = to_status
    append_event(path, event)
    return event


def read_events(path: str | Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Read valid JSONL records and report, rather than hide, malformed lines."""
    target = Path(path)
    if not target.exists():
        return [], []
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError("record must be an object")
            if "topic_id" in parsed:
                _validate_experiment(parsed, threshold=3.5, allow_legacy=True)
            else:
                _validate_record(parsed, EVENT_REQUIRED)
            events.append(parsed)
        except (json.JSONDecodeError, ValueError) as error:
            errors.append(f"{target}:{line_number}: {error}")
    return events, errors


def experiment_value_score(value: Mapping[str, Any]) -> float:
    """Return a 1–5 equally weighted score for impact, novelty, learning and reuse."""
    if not isinstance(value, Mapping):
        raise ValueError("value must score impact, novelty, learning and reuse")
    scores = []
    for dimension in VALUE_DIMENSIONS:
        score = value.get(dimension)
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 1 <= score <= 5:
            raise ValueError(f"value.{dimension} must be between 1 and 5")
        scores.append(float(score))
    return sum(scores) / len(scores)


def should_record_experiment(value: Mapping[str, Any], threshold: float = 3.5) -> bool:
    return experiment_value_score(value) >= threshold


def record_experiment(path: str | Path, experiment: Mapping[str, Any], threshold: float = 3.5) -> None:
    """Append a high-value experiment, whether it passed, failed or was inconclusive."""
    if not isinstance(experiment, Mapping):
        raise ValueError("experiment must be an object")
    score = _validate_experiment(experiment, threshold)
    record = dict(experiment)
    record["value_score"] = round(score, 2)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def register_solution_and_record_experiment(
    project_state_path: str | Path,
    experiments_path: str | Path,
    experiment: Mapping[str, Any],
    solution: Mapping[str, Any] | None = None,
    threshold: float = 3.5,
) -> None:
    """Validate topic/solution linkage, optionally register a solution, then append an experiment.

    Existing solutions are reused by ID. A new solution is written to project state
    before the append-only experiment record; if the append fails, the state file is
    restored so the operation does not leave an unreferenced solution behind.
    """
    if not isinstance(experiment, Mapping):
        raise ValueError("experiment must be an object")
    _validate_experiment(experiment, threshold)
    state_path = Path(project_state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state_errors = validate_project_state(state)
    if state_errors:
        raise ValueError("invalid project state: " + "; ".join(state_errors))

    owner = next((wp for feature in state.get("features", []) for wp in feature.get("work_packages", [])
                  if wp.get("research_topic", {}).get("id") == experiment["topic_id"]), None)
    if owner is None:
        raise ValueError(f"unknown research topic: {experiment['topic_id']}")
    topic = owner["research_topic"]
    topic.setdefault("solutions", [])
    existing = next((item for item in topic["solutions"] if item.get("id") == experiment["solution_id"]), None)
    new_solution = False
    if existing is None:
        if not isinstance(solution, Mapping):
            raise ValueError("solution_id is not registered under topic; provide --solution-json")
        if solution.get("id") != experiment["solution_id"]:
            raise ValueError("solution.id must match experiment.solution_id")
        topic["solutions"].append(dict(solution))
        new_solution = True
        state_errors = validate_project_state(state)
        if state_errors:
            raise ValueError("invalid registered solution: " + "; ".join(state_errors))
    elif solution is not None and solution.get("id") != experiment["solution_id"]:
        raise ValueError("provided solution.id does not match experiment.solution_id")

    records, record_errors = read_events(experiments_path)
    if record_errors:
        raise ValueError("cannot append to malformed experiment log: " + "; ".join(record_errors))
    if any(record.get("id") == experiment["id"] for record in records):
        raise ValueError(f"duplicate experiment id: {experiment['id']}")

    original = state_path.read_bytes()
    if new_solution:
        _atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    scoped_experiment = dict(experiment)
    scoped_experiment["project_id"] = str(state.get("project", {}).get("id", ""))
    try:
        record_experiment(experiments_path, scoped_experiment, threshold)
    except Exception:
        if new_solution:
            _atomic_write(state_path, original)
        raise


def _atomic_write(path: Path, contents: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    mode = "wb" if isinstance(contents, bytes) else "w"
    try:
        with os.fdopen(descriptor, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def _validate_experiment(experiment: Mapping[str, Any], threshold: float, allow_legacy: bool = False) -> float:
    required = tuple(field for field in EXPERIMENT_REQUIRED if not (allow_legacy and field in {"solution_id", "data_source"}))
    missing = [field for field in required if field not in experiment]
    if missing:
        raise ValueError("missing required fields: " + ", ".join(missing))
    for field in ("id", "topic_id", "hypothesis", "method", "observation", "conclusion"):
        if not isinstance(experiment[field], str) or not experiment[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    for field in ("solution_id", "data_source"):
        if field in experiment and (not isinstance(experiment[field], str) or not experiment[field].strip()):
            raise ValueError(f"{field} must be a non-empty string")
    _validate_timestamp(experiment["timestamp"])
    _validate_links(experiment["evidence_links"])
    if experiment["result"] not in {"PASS", "FAIL", "INCONCLUSIVE"}:
        raise ValueError("result must be PASS, FAIL or INCONCLUSIVE")
    score = experiment_value_score(experiment["value"])
    if score < threshold:
        raise ValueError(f"experiment does not meet value threshold {threshold:g} (score {score:g})")
    return score


def _record_date(record: Mapping[str, Any]) -> date:
    value = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    return value.date()


def group_work_logs(events: list[Mapping[str, Any]], reference_date: date | None = None) -> dict[str, list[dict[str, Any]]]:
    """Return link-bearing entries for the reference day, ISO week and month."""
    reference_date = reference_date or date.today()
    week_start = reference_date - timedelta(days=reference_date.weekday())
    month_prefix = reference_date.strftime("%Y-%m")
    valid = [dict(event) for event in events if event.get("timestamp")]
    daily = [event for event in valid if _record_date(event) == reference_date]
    weekly = [event for event in valid if week_start <= _record_date(event) < week_start + timedelta(days=7)]
    monthly = [event for event in valid if _record_date(event).strftime("%Y-%m") == month_prefix]
    return {"daily": daily, "weekly": weekly, "monthly": monthly}


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a timestamped project Execution Log event")
    parser.add_argument("log_path", help="JSONL path, e.g. project-management/execution-log.jsonl")
    parser.add_argument("--experiment-json", help="Record a high-value experiment from this JSON file instead of an execution event")
    parser.add_argument("--project-state", help="Canonical project-state JSON used to validate or register its research solution")
    parser.add_argument("--solution-json", help="Optional JSON object to register when experiment.solution_id is new")
    parser.add_argument("--kind", help="start, status, implementation, verification, issue, decision, checkpoint")
    parser.add_argument("--summary")
    parser.add_argument("--evidence", action="append", help="Evidence path or URL; repeat for multiple links")
    parser.add_argument("--feature-id", default="")
    parser.add_argument("--work-package-id", default="")
    parser.add_argument("--status", default="", help="State category at this event")
    parser.add_argument("--from-status", default="")
    parser.add_argument("--to-status", default="")
    arguments = parser.parse_args()
    if arguments.experiment_json:
        if not arguments.project_state:
            parser.error("--experiment-json requires --project-state")
        experiment = json.loads(Path(arguments.experiment_json).read_text(encoding="utf-8"))
        solution = json.loads(Path(arguments.solution_json).read_text(encoding="utf-8")) if arguments.solution_json else None
        register_solution_and_record_experiment(arguments.project_state, arguments.log_path, experiment, solution)
        print(f"Recorded experiment {experiment['id']} with value score {experiment_value_score(experiment['value']):.2f}")
        return
    if not arguments.kind or not arguments.summary or not arguments.evidence or not arguments.project_state:
        parser.error("execution events require --kind, --summary, --project-state and at least one --evidence")
    project_state = json.loads(Path(arguments.project_state).read_text(encoding="utf-8"))
    event = record_execution(arguments.log_path, kind=arguments.kind, summary=arguments.summary,
                             evidence_links=arguments.evidence, feature_id=arguments.feature_id,
                             work_package_id=arguments.work_package_id, status_category=arguments.status,
                             from_status=arguments.from_status, to_status=arguments.to_status,
                             project_id=str(project_state.get("project", {}).get("id", "")))
    print(json.dumps(event, ensure_ascii=False))


if __name__ == "__main__":
    main()
