import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
LIFECYCLE = PLUGIN / "scripts" / "case_lifecycle.py"
WORKFLOWS = PLUGIN / "scripts" / "workflow_packs.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class WorkflowPacksTest(unittest.TestCase):
    def init_case(self, workspace: Path, module: str) -> None:
        result = run(
            LIFECYCLE,
            "init",
            str(workspace),
            "--case-id",
            f"CASE-{module}",
            "--client",
            "Cliente test",
            "--module",
            module,
            "--role",
            "Ruolo test",
            "--period",
            "2026",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_catalog_covers_distinct_professional_modules(self):
        result = run(WORKFLOWS, "list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for module in (
            "AUDIT_001",
            "BOARD_001",
            "DUAL_001",
            "ACC_CAP_001",
            "ACC_PART_001",
            "ACC_SOLE_001",
            "ACC_PERSON_001",
            "ACC_NPO_001",
            "LAB_001",
            "LAB_CALC_001",
            "TAX_LIT_001",
            "CTP_001",
            "CTU_001",
            "VALUATION_001",
            "DUE_DIL_001",
            "CONDO_REVIEW_001",
        ):
            self.assertIn(module, result.stdout)
        self.assertNotIn("CRISIS_001", result.stdout)
        self.assertNotIn("ODV_001", result.stdout)

    def test_plan_is_markdown_first_and_validates_every_family(self):
        modules = ("AUDIT_001", "BOARD_001", "ACC_CAP_001", "LAB_001", "TAX_LIT_001", "CTP_001")
        with tempfile.TemporaryDirectory() as temp:
            for module in modules:
                workspace = Path(temp) / module
                self.init_case(workspace, module)
                planned = run(WORKFLOWS, "plan", str(workspace))
                self.assertEqual(planned.returncode, 0, planned.stderr)
                for name in ("WORKFLOW_PLAN.md", "OUTPUT_REGISTER.md", "WORKING_PAPERS_INDEX.md"):
                    text = (workspace / name).read_text(encoding="utf-8")
                    self.assertIn("BOZZA DA VALIDARE", text)
                plan_text = (workspace / "WORKFLOW_PLAN.md").read_text(encoding="utf-8")
                self.assertIn("AUTORIZZO MODIFICA SORGENTI", plan_text)
                self.assertIn("APPROVO OUTPUT", plan_text)
                evaluated = run(WORKFLOWS, "validate", str(workspace))
                self.assertEqual(evaluated.returncode, 0, evaluated.stderr)
                self.assertIn("PASS CON RILIEVI", evaluated.stdout)
                self.assertTrue((workspace / "WORKFLOW_EVAL.md").is_file())

    def test_plan_refuses_overwrite_and_module_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "case"
            self.init_case(workspace, "LAB_001")
            mismatch = run(WORKFLOWS, "plan", str(workspace), "--module", "AUDIT_001")
            self.assertNotEqual(mismatch.returncode, 0)
            first = run(WORKFLOWS, "plan", str(workspace))
            self.assertEqual(first.returncode, 0, first.stderr)
            marker = workspace / "WORKFLOW_PLAN.md"
            original = marker.read_text(encoding="utf-8")
            second = run(WORKFLOWS, "plan", str(workspace))
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), original)

    def test_completed_case_with_open_phases_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "case"
            self.init_case(workspace, "TAX_LIT_001")
            self.assertEqual(run(WORKFLOWS, "plan", str(workspace)).returncode, 0)
            state_path = workspace / "CASE_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "Completato"
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            evaluated = run(WORKFLOWS, "validate", str(workspace))
            self.assertEqual(evaluated.returncode, 2)
            self.assertIn("fasi risultano non completate", evaluated.stdout)

    def test_skill_references_and_eval_cases_are_packaged(self):
        base = PLUGIN / "skills" / "professional-workflow-packs"
        for relative in (
            "SKILL.md",
            "references/workflow-contract.md",
            "references/revisione-governance.md",
            "references/fiscale.md",
            "references/lavoro.md",
            "references/contenzioso.md",
            "references/perizie.md",
        ):
            self.assertTrue((base / relative).is_file(), relative)
        cases = list((PLUGIN / "evals" / "workflow-packs").glob("*.md"))
        self.assertEqual(len(cases), 6)
        for case in cases:
            text = case.read_text(encoding="utf-8")
            self.assertIn("## Input minimo", text)
            self.assertIn("## Esito atteso", text)
            self.assertIn("## Fallimenti bloccanti", text)


if __name__ == "__main__":
    unittest.main()
