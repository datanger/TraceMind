import unittest
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def api(test_case, name):
    try:
        module = importlib.import_module("project_state")
    except ModuleNotFoundError as error:
        test_case.fail(f"project_state module is not implemented: {error}")
    if not hasattr(module, name):
        test_case.fail(f"project_state.{name} is not implemented")
    return getattr(module, name)


def work_package(**overrides):
    value = {
        "id": "WP-1",
        "title": "Token refresh",
        "status": "TODO",
        "description": "Implement token refresh behavior.",
        "inputs": ["Auth contract"],
        "outputs": ["Refresh endpoint"],
        "scope": ["Refresh and revoke tokens"],
        "dependencies": [],
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "method": "integration test",
                "metric": "old token rejection rate",
                "target": "100%",
                "status": "PASS",
                "evidence": ["tests/auth/test_refresh.py"],
            }
        ],
        "progress_items": [
            {"id": "P-1", "weight": 1, "done": True, "evidence": ["src/auth.py"]},
            {"id": "P-2", "weight": 1, "done": False, "evidence": []},
        ],
        "estimate_points": 2,
        "research_topic": {"id": "R-WP-1", "title": "Token family invalidation"},
    }
    value.update(overrides)
    return value


def project_state():
    wp_a = work_package(id="WP-A", estimate_points=3)
    wp_b = work_package(id="WP-B", estimate_points=1, progress_items=[
        {"id": "P-1", "weight": 1, "done": True, "evidence": ["src/auth.py"]},
    ])
    return {
        "schema_version": 1,
        "project": {"id": "demo", "name": "Demo", "timezone": "Asia/Shanghai"},
        "objectives": [{"id": "O-1", "title": "Secure auth", "key_results": [{"id": "KR-1", "metric": "old token rejection rate", "target": "100%", "measurement_method": "integration test"}]}],
        "features": [
            {"id": "F-1", "title": "Authentication", "weight": 2, "work_packages": [wp_a]},
            {"id": "F-2", "title": "Reporting", "weight": 1, "work_packages": [wp_b]},
        ],
        "milestones": [{"id": "M-1", "title": "Auth release", "date": "2026-11-01", "acceptance": "All auth acceptance criteria pass"}],
        "weeks": [{"id": "W-1", "start": "2026-10-12", "end": "2026-10-18", "objective": "Implement refresh", "deliverables": ["Refresh endpoint"]}],
    }


class ProjectStateTests(unittest.TestCase):
    def test_work_package_progress_uses_weighted_evidence_items(self):
        compute = api(self, "compute_work_package_progress")
        self.assertEqual(compute(work_package()), 50)

    def test_feature_progress_weights_work_packages_by_estimate(self):
        feature = {"work_packages": [
            work_package(estimate_points=3, progress_items=[{"id": "P", "weight": 1, "done": False, "evidence": []}]),
            work_package(estimate_points=1, progress_items=[{"id": "P", "weight": 1, "done": True, "evidence": ["src/a.py"]}]),
        ]}
        compute = api(self, "compute_feature_progress")
        self.assertEqual(compute(feature), 25)
        feature["work_packages"][1].pop("estimate_points")
        self.assertEqual(compute(feature), 25)

    def test_project_progress_weights_features_and_falls_back_to_equal_when_absent(self):
        state = project_state()
        compute = api(self, "compute_project_progress")
        self.assertAlmostEqual(compute(state), 66.6666667)
        state["features"][0].pop("weight")
        state["features"][1].pop("weight")
        self.assertAlmostEqual(compute(state), 75)

    def test_done_requires_all_acceptance_criteria_to_pass_with_evidence(self):
        wp = work_package(status="VERIFYING")
        wp["acceptance_criteria"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "acceptance"):
            api(self, "apply_status_transition")(wp, "DONE", evidence={"kind": "verification", "ref": "reports/vr-1.json"})

    def test_transition_records_evidence_and_rejects_skipped_states(self):
        wp = work_package(status="TODO")
        with self.assertRaisesRegex(ValueError, "transition"):
            api(self, "apply_status_transition")(wp, "IN_PROGRESS", evidence={"kind": "start", "ref": "logs/execution.jsonl"})
        ready = api(self, "apply_status_transition")(wp, "READY", evidence={"kind": "contract", "ref": "plans/wp-1.json"})
        self.assertEqual(ready["status"], "READY")
        self.assertEqual(ready["status_history"][-1]["evidence"]["ref"], "plans/wp-1.json")
        self.assertTrue(ready["status_history"][-1]["timestamp"])

    def test_failure_fixing_verifying_loop_is_supported(self):
        wp = work_package(status="VERIFYING")
        wp["acceptance_criteria"][0]["status"] = "FAIL"
        transition = api(self, "apply_status_transition")
        failed = transition(wp, "FAILED", evidence={"kind": "verification", "ref": "reports/failure.json", "reason": "Old token remained valid"})
        fixing = transition(failed, "FIXING", evidence={"kind": "fix-plan", "ref": "issues/ISS-1.md"})
        verifying = transition(fixing, "VERIFYING", evidence={"kind": "rerun", "ref": "tests/auth/test_refresh.py"})
        self.assertEqual([failed["status"], fixing["status"], verifying["status"]], ["FAILED", "FIXING", "VERIFYING"])

    def test_validation_requires_measurable_acceptance_and_research_topic(self):
        state = project_state()
        wp = state["features"][0]["work_packages"][0]
        wp["acceptance_criteria"][0].pop("metric")
        wp.pop("research_topic")
        errors = api(self, "validate_project_state")(state)
        self.assertTrue(any("metric" in error for error in errors))
        self.assertTrue(any("research_topic" in error for error in errors))

    def test_status_is_derived_from_contract_implementation_and_verification_evidence(self):
        derive = api(self, "derive_work_package_status")
        wp = work_package()
        self.assertEqual(derive(wp), "TODO")
        wp["contract_approved"] = True
        self.assertEqual(derive(wp), "READY")
        wp["status"] = "READY"
        wp["start_evidence"] = ["logs/execution.jsonl#E1"]
        self.assertEqual(derive(wp), "IN_PROGRESS")
        wp["status"] = "IN_PROGRESS"
        wp["implementation_evidence"] = ["src/auth.py"]
        self.assertEqual(derive(wp), "IMPLEMENTED")
        wp["status"] = "IMPLEMENTED"
        wp["verification_evidence"] = ["reports/vr-1.json"]
        self.assertEqual(derive(wp), "VERIFYING")
        wp["status"] = "VERIFYING"
        self.assertEqual(derive(wp), "DONE")


if __name__ == "__main__":
    unittest.main()
