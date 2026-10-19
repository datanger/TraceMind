import importlib
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def api(test_case, name):
    try:
        module = importlib.import_module("execution_log")
    except ModuleNotFoundError as error:
        test_case.fail(f"execution_log module is not implemented: {error}")
    if not hasattr(module, name):
        test_case.fail(f"execution_log.{name} is not implemented")
    return getattr(module, name)


class ExecutionLogTests(unittest.TestCase):
    def test_append_only_jsonl_and_malformed_line_diagnostics(self):
        append_event = api(self, "append_event")
        read_events = api(self, "read_events")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.jsonl"
            append_event(path, {"id": "E1", "timestamp": "2026-10-16T09:00:00+08:00", "kind": "status", "summary": "Started", "evidence_links": ["src/a.py"]})
            append_event(path, {"id": "E2", "timestamp": "2026-10-16T09:05:00+08:00", "kind": "result", "summary": "Tests pass", "evidence_links": ["reports/test.json"]})
            with path.open("a", encoding="utf-8") as stream:
                stream.write("not-json\n")
            events, errors = read_events(path)
            self.assertEqual([event["id"] for event in events], ["E1", "E2"])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 3)
            self.assertEqual(len(errors), 1)

    def test_required_timestamp_summary_and_linked_evidence(self):
        append_event = api(self, "append_event")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "execution.jsonl"
            for event in ({"id": "E1", "kind": "status", "summary": "Started", "evidence_links": ["a.py"]},
                          {"id": "E2", "timestamp": "2026-10-16T09:00:00+08:00", "kind": "status", "summary": "Started", "evidence_links": []}):
                with self.assertRaises(ValueError):
                    append_event(path, event)

    def test_realtime_helper_creates_timestamp_and_state_category(self):
        record = api(self, "record_execution")
        with tempfile.TemporaryDirectory() as directory:
            event = record(Path(directory) / "execution.jsonl", kind="status", summary="Started WP-1", evidence_links=["src/a.py"], work_package_id="WP-1", status_category="IN_PROGRESS")
            self.assertTrue(event["timestamp"])
            self.assertEqual(event["status_category"], "IN_PROGRESS")

    def test_only_high_value_questions_are_recorded_but_failed_experiments_remain(self):
        should_record = api(self, "should_record_experiment")
        record = api(self, "record_experiment")
        self.assertFalse(should_record({"impact": 1, "novelty": 1, "learning": 2, "reuse": 1}))
        self.assertTrue(should_record({"impact": 5, "novelty": 4, "learning": 5, "reuse": 4}))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiments.jsonl"
            failed = {"id": "X1", "timestamp": "2026-10-16T10:00:00+08:00", "topic_id": "R-WP-1", "solution_id": "S-WP-1-A", "data_source": "tests/fixtures/token-refresh", "hypothesis": "Cache invalidation is sufficient", "method": "integration test", "result": "FAIL", "observation": "Old token remained valid after rotation", "conclusion": "Cache removal is not propagated across workers", "evidence_links": ["reports/fail.json"], "value": {"impact": 5, "novelty": 4, "learning": 5, "reuse": 4}}
            record(path, failed)
            entries, errors = api(self, "read_events")(path)
            self.assertFalse(errors)
            self.assertEqual(entries[0]["result"], "FAIL")

    def test_low_value_experiment_is_rejected(self):
        record = api(self, "record_experiment")
        experiment = {"id": "X2", "timestamp": "2026-10-16T10:00:00+08:00", "topic_id": "R-WP-1", "solution_id": "S-WP-1-A", "data_source": "tests/fixtures/token-refresh", "hypothesis": "Try a minor rename", "method": "manual", "result": "PASS", "observation": "No behavioral change", "conclusion": "Not worth adopting", "evidence_links": ["src/a.py"], "value": {"impact": 1, "novelty": 1, "learning": 1, "reuse": 1}}
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "value threshold"):
            record(Path(directory) / "experiments.jsonl", experiment)

    def test_daily_weekly_monthly_grouping_keeps_evidence_links(self):
        group = api(self, "group_work_logs")
        events = [{"id": "E1", "timestamp": "2026-10-16T09:00:00+08:00", "summary": "Code change", "evidence_links": ["src/a.py"]},
                  {"id": "E2", "timestamp": "2026-10-12T09:00:00+08:00", "summary": "Test result", "evidence_links": ["reports/t.json"]}]
        report = group(events, date(2026, 10, 16))
        self.assertEqual(len(report["daily"]), 1)
        self.assertEqual(len(report["weekly"]), 2)
        self.assertEqual(len(report["monthly"]), 2)
        self.assertIn("src/a.py", report["daily"][0]["evidence_links"])


if __name__ == "__main__":
    unittest.main()
