import importlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


class MigrationTests(unittest.TestCase):
    def test_supplied_legacy_html_migrates_features_subfeatures_and_weekly_cards(self):
        migrate = importlib.import_module("migrate_legacy_html").migrate_legacy_html
        legacy_html = '''
        <article class="feature status-build" data-status="build">
          <h3>Feature One</h3><p>Feature summary</p>
          <div class="subfeature"><span><strong>WP1 Task One</strong><small>Task details</small></span><select data-task-key="WP1"></select></div>
        </article>
        <article class="week" data-start="2026-10-12" data-end="2026-10-18" data-phase="p0">
          <h3>Weekly objective</h3><ul><li>Weekly delivery</li></ul>
        </article>
        '''
        with tempfile.TemporaryDirectory() as directory:
            legacy_path = Path(directory) / "legacy-project.html"
            legacy_path.write_text(legacy_html, encoding="utf-8")
            state = migrate(legacy_path)
        self.assertEqual(len(state["features"]), 1)
        self.assertEqual(sum(len(feature["work_packages"]) for feature in state["features"]), 1)
        self.assertEqual(len(state["weeks"]), 1)
        for feature in state["features"]:
            for package in feature["work_packages"]:
                self.assertTrue(package["inputs"] and package["outputs"] and package["scope"])
                self.assertTrue(package["acceptance_criteria"][0]["method"])
                self.assertTrue(package["acceptance_criteria"][0]["metric"])
                self.assertTrue(package["research_topic"]["id"])
                self.assertEqual(package["status"], "TODO")


if __name__ == "__main__":
    unittest.main()
