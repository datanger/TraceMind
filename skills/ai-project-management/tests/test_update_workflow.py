import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SCRIPTS))


def api(test_case, name):
    try:
        module = importlib.import_module("update_workflow")
    except (ModuleNotFoundError, ImportError) as error:
        test_case.fail(f"update_workflow module is not available: {error}")
    if not hasattr(module, name):
        test_case.fail(f"update_workflow.{name} is not implemented")
    return getattr(module, name)


def valid_state():
    return {"schema_version": 1, "project": {"id": "demo", "name": "Demo"}, "objectives": [{"id": "O1", "title": "Goal", "key_results": [{"id": "KR1", "metric": "pass rate", "target": "100%", "measurement_method": "test"}]}], "milestones": [{"id": "M1", "title": "Release", "date": "2026-11-01", "acceptance": "all tests pass"}], "weeks": [{"id": "W1", "start": "2026-10-12", "end": "2026-10-18", "objective": "Implement", "deliverables": ["work package"]}], "features": [{"id": "F1", "title": "Feature", "weight": 1, "work_packages": [{"id": "WP1", "title": "Work", "status": "TODO", "description": "Do work", "inputs": ["req"], "outputs": ["artifact"], "scope": ["implementation"], "acceptance_criteria": [{"id": "AC1", "method": "test", "metric": "pass rate", "target": "100%"}], "progress_items": [{"id": "P1", "weight": 1, "done": False}], "research_topic": {"id": "R1", "title": "Research"}}]}], "execution_log": [], "work_logs": {"daily": [], "weekly": [], "monthly": []}}


class WorkflowTests(unittest.TestCase):
    def test_agent_result_must_be_a_complete_valid_state_snapshot(self):
        validate = api(self, "validate_agent_proposal")
        current = valid_state()
        with self.assertRaisesRegex(ValueError, "agent proposal|invalid project state"):
            validate(current, {"project_state": {"schema_version": 1, "project": {}, "features": []}})
        proposal = {"project_state": valid_state(), "summary": "Reviewed code"}
        normalized = validate(current, proposal)
        self.assertEqual(normalized["project"], current["project"])

    def test_recalculation_derives_l1_and_project_progress_and_periods(self):
        recalculate = api(self, "recalculate_project_state")
        state = valid_state()
        state["features"][0]["work_packages"][0]["progress_items"][0] = {"id": "P1", "weight": 1, "done": True, "evidence": ["src/a.py"]}
        state["execution_log"] = [{"id": "E1", "timestamp": "2026-10-16T10:00:00+08:00", "kind": "result", "summary": "Done", "evidence_links": ["src/a.py"]}]
        state["features"][0]["work_packages"][0]["research_topic"]["solutions"] = [{"id": "S1", "name": "Contract-first", "method": "contract test", "data_source": "tests/fixtures/contract"}]
        state["experiments"] = [{"id": "X1", "timestamp": "2026-10-16T11:00:00+08:00", "topic_id": "R1", "solution_id": "S1", "data_source": "tests/fixtures/contract", "hypothesis": "Candidate works", "method": "contract test", "result": "FAIL", "observation": "Mismatch", "conclusion": "Refine contract", "evidence_links": ["reports/fail.json"], "value": {"impact": 5, "novelty": 4, "learning": 5, "reuse": 4}}]
        result = recalculate(state, reference_date="2026-10-16")
        self.assertEqual(result["features"][0]["progress"], 100)
        self.assertEqual(result["project"]["progress"], 100)
        self.assertEqual(len(result["work_logs"]["daily"]), 2)
        self.assertIn("FAIL", result["work_logs"]["daily"][1]["summary"])

    def test_jsonl_logs_are_loaded_as_authority_and_cannot_be_removed_by_agent(self):
        load = api(self, "load_project_state")
        validate = api(self, "validate_agent_proposal")
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            execution_path = Path(directory) / "execution-log.jsonl"
            experiments_path = Path(directory) / "experiments.jsonl"
            state_path.write_text(json.dumps(valid_state()), encoding="utf-8")
            execution_path.write_text(json.dumps({"id": "E1", "timestamp": "2026-10-16T09:00:00+08:00", "kind": "status", "summary": "Started", "evidence_links": ["src/a.py"]}) + "\n", encoding="utf-8")
            experiments_path.write_text("", encoding="utf-8")
            current = load(state_path, execution_path, experiments_path)
            candidate = valid_state()
            candidate["execution_log"] = []
            normalized = validate(current, {"project_state": candidate, "summary": "Updated"})
            self.assertEqual([row["id"] for row in normalized["execution_log"]], ["E1"])

    def test_publish_stops_before_html_write_when_validation_fails(self):
        publish = api(self, "publish_validated_update")
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "base.html"
            output = Path(directory) / "dashboard.html"
            template.write_text("<html><!-- AI_PM_STATE_SLOT --></html>", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid project state"):
                publish(template, {"schema_version": 1, "project": {}, "features": []}, output)
            self.assertFalse(output.exists())

    def test_publish_requires_render_verification_and_persists_html_and_source_state(self):
        module = importlib.import_module("update_workflow")
        state = json.loads((ROOT / "skills/ai-project-management/examples/project-state.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "base.html"
            output = Path(directory) / "dashboard.html"
            state_output = Path(directory) / "project-state.json"
            template.write_text("<html><!-- AI_PM_STATE_SLOT --></html>", encoding="utf-8")
            rendered = module.render_state_html(template, state)
            verification = module.verify_rendered_dashboard(rendered, state)
            with self.assertRaisesRegex(ValueError, "verification"):
                module.publish_validated_update(template, state, output, state_output, rendered)
            module.publish_validated_update(template, state, output, state_output, rendered, verification)
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(state_output.read_text(encoding="utf-8")), state)

    def test_dashboard_verifier_rejects_missing_page_navigation_contracts(self):
        module = importlib.import_module("update_workflow")
        state = json.loads((ROOT / "skills/ai-project-management/examples/project-state.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "base.html"
            template.write_text("<html><body><!-- AI_PM_STATE_SLOT --></body></html>", encoding="utf-8")
            rendered = module.render_state_html(template, state)

        for marker in (
            'id="aipm-project-view-nav"',
            'aria-label="一级功能内容导航"',
            'aria-label="二级功能详情导航"',
            'aria-label="项目视图导航"',
            'data-project-page-view="okr"',
            'data-project-page-view="wbs"',
            'data-project-page-view="milestones"',
        ):
            with self.subTest(marker=marker):
                broken = rendered.replace(marker, "")
                with self.assertRaisesRegex(ValueError, "missing required views"):
                    module.verify_rendered_dashboard(broken, state)

    def test_workflow_uses_looma_durable_steps_and_host_agent_boundary(self):
        path = SCRIPTS / "update_workflow.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn("@workflow", source)
        self.assertIn("step(", source)
        self.assertIn("agent(", source)
        self.assertIn("verify_rendered_dashboard", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("openai", source.lower())


if __name__ == "__main__":
    unittest.main()
