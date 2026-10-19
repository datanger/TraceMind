import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/ai-project-management"


class SkillDocsTests(unittest.TestCase):
    def test_skill_frontmatter_and_references_are_complete(self):
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\nname: ai-project-management\n"))
        self.assertIn("Automatic execution recording", content)
        self.assertIn("User-triggered project/dashboard update", content)
        for link in re.findall(r"\[[^]]+\]\(([^)]+\.md)\)", content):
            self.assertTrue((SKILL / link).resolve().exists(), f"missing skill reference: {link}")

    def test_schema_json_and_example_match_runtime_contract(self):
        schema = json.loads((SKILL / "schemas/project-state.schema.json").read_text(encoding="utf-8"))
        state = json.loads((SKILL / "examples/project-state.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        project_state_path = SKILL / "scripts/project_state.py"
        spec = importlib.util.spec_from_file_location("skill_project_state", project_state_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.validate_project_state(state), [])


if __name__ == "__main__":
    unittest.main()
