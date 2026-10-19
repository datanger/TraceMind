import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
try:
    import looma
    HAS_LOOMA_100 = looma.__version__ == "1.0.0"
except ImportError:
    HAS_LOOMA_100 = False


@unittest.skipUnless(HAS_LOOMA_100, "Run with Looma Runtime 1.0.0 on PYTHONPATH")
class LoomaRuntimeIntegrationTests(unittest.TestCase):
    def test_pause_agent_result_resume_and_publish(self):
        with tempfile.TemporaryDirectory(prefix="aipm-looma-integration-") as directory:
            base = Path(directory)
            management = base / "project-management"
            management.mkdir()
            source_state = ROOT / "project-management/project-state.json"
            state_path = management / "project-state.json"
            shutil.copy(source_state, state_path)
            (management / "execution-log.jsonl").write_text("", encoding="utf-8")
            (management / "experiments.jsonl").write_text("", encoding="utf-8")
            output_path = base / "dashboard.html"
            runner = base / "run_update.py"
            runner.write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(ROOT / 'skills/ai-project-management/scripts')!r})\n"
                "from update_workflow import update_project\n"
                f"update_project({str(ROOT)!r}, {str(state_path)!r}, {None!r}, {str(output_path)!r})\n",
                encoding="utf-8",
            )
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "skills/ai-project-management/scripts"), *sys.path])
            first = subprocess.run([sys.executable, str(runner)], cwd=base, env=env, text=True, capture_output=True)
            self.assertEqual(first.returncode, 75, first.stderr)
            self.assertIn("<<<SCRIPT2AGENT>>>", first.stdout)
            self.assertFalse(output_path.exists(), "HTML must not publish before the Agent proposal is validated")

            run_state_path = next((base / ".looma/runs").glob("*/state.json"))
            run_state = json.loads(run_state_path.read_text(encoding="utf-8"))
            request_path = Path(next(event["request_file"] for event in run_state["events"] if event.get("request_file")))
            request = json.loads(request_path.read_text(encoding="utf-8"))
            result_path = Path(request["output"]["result_file"])
            result_path.parent.mkdir(parents=True, exist_ok=True)
            candidate = json.loads(state_path.read_text(encoding="utf-8"))
            result_path.write_text(json.dumps({"project_state": candidate, "summary": "Integration fixture Agent proposal"}), encoding="utf-8")
            response_path = base / "agent2script.json"
            response_path.write_text(json.dumps(request["expected_output"]), encoding="utf-8")
            resume_code = (
                "import sys; sys.argv=['looma','handoff','--request',%r,'--response',%r]; "
                "from looma.cli import main; raise SystemExit(main())"
            ) % (str(request_path), str(response_path))
            resumed = subprocess.run([sys.executable, "-c", resume_code], cwd=base, env=env, text=True, capture_output=True)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertTrue(output_path.exists())
            state_after = json.loads(state_path.read_text(encoding="utf-8"))
            page = output_path.read_text(encoding="utf-8")
            self.assertEqual(state_after["project"]["progress"], 0)
            self.assertIn('id="ai-pm-state"', page)
            self.assertIn('id="aipm-state-plan"', page)


if __name__ == "__main__":
    unittest.main()
