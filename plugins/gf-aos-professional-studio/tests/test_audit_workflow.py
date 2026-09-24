import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN = Path(__file__).parents[1]
LIFECYCLE = PLUGIN / "scripts" / "case_lifecycle.py"
RUNTIME = PLUGIN / "scripts" / "audit_workflow.py"
PHASES = (
    "A01_CONTEXT", "A02_PRIOR_PERIOD", "A03_ANOMALIES", "A04_COHERENCE",
    "A05_ANALYTICS", "A06_RISK_CONTINUITY", "A07_SECTOR_ACCEPTANCE",
    "A08_EVIDENCE_FOLLOWUP",
)


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, check=False)


class AuditWorkflowTest(unittest.TestCase):
    def init_case(self, workspace: Path, module: str = "AUDIT_001") -> None:
        result = run(
            LIFECYCLE, "init", str(workspace), "--case-id", f"CASE-{module}",
            "--client", "CLIENT_ALIAS", "--module", module, "--role", "Ruolo test",
            "--period", "2026",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run(RUNTIME, "init", str(workspace))
        self.assertEqual(result.returncode, 0, result.stderr)

    def complete(self, workspace: Path, module: str = "AUDIT_001") -> None:
        for index, phase in enumerate(PHASES):
            args = [
                "step", str(workspace), phase, "--status", "Completato",
                "--summary", f"Esito sintetico fase {index + 1}",
                "--evidence-locator", f"SRC_{index + 1}",
                "--evidence-proposition", "Proposizione verificata",
                "--evidence-status", "verificata",
            ]
            if module == "DUAL_001":
                args.extend(["--function-tag", "REVISIONE" if index % 2 else "VIGILANZA"])
            result = run(RUNTIME, *args)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_audit_runtime_builds_dossier_and_approval_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "case"
            self.init_case(workspace)
            self.complete(workspace)
            drafted = run(RUNTIME, "draft", str(workspace))
            self.assertEqual(drafted.returncode, 0, drafted.stderr)
            dossier = (workspace / "DOSSIER_INTEGRATO.md").read_text(encoding="utf-8")
            self.assertIn("Parte I — Verbale narrativo", dossier)
            self.assertIn("Parte II — Carta di lavoro", dossier)
            self.assertIn("BOZZA DA VALIDARE", dossier)
            validated = run(RUNTIME, "validate", str(workspace))
            self.assertEqual(validated.returncode, 0, validated.stderr)
            approved = run(
                RUNTIME, "approve", str(workspace), "--note", "Validazione professionale completa",
                "--professional-name", "PROFESSIONAL_ALIAS", "--confirmation", "APPROVO OUTPUT",
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            self.assertTrue((workspace / "AUDIT_APPROVAL_RECEIPT.md").is_file())
            state = json.loads((workspace / "CASE_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "Approvato")
            self.assertEqual(state["professional_workflow"]["steps"][10]["status"], "Approvato")

    def test_sequence_and_conscious_skip_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "case"
            self.init_case(workspace)
            out_of_order = run(
                RUNTIME, "step", str(workspace), "A02_PRIOR_PERIOD", "--status", "Completato",
                "--summary", "Tentativo fuori sequenza",
            )
            self.assertNotEqual(out_of_order.returncode, 0)
            bad_skip = run(
                RUNTIME, "skip", str(workspace), "A01_CONTEXT", "--rationale", "breve",
                "--confirmation", "PRENDO ATTO E IGNORO A01_CONTEXT",
            )
            self.assertNotEqual(bad_skip.returncode, 0)
            good_skip = run(
                RUNTIME, "skip", str(workspace), "A01_CONTEXT",
                "--rationale", "Perimetro escluso con motivazione professionale",
                "--confirmation", "PRENDO ATTO E IGNORO A01_CONTEXT",
            )
            self.assertEqual(good_skip.returncode, 0, good_skip.stderr)

    def test_dual_requires_and_preserves_distinct_function_tags(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "dual"
            self.init_case(workspace, "DUAL_001")
            missing = run(
                RUNTIME, "step", str(workspace), "A01_CONTEXT", "--status", "Completato",
                "--summary", "Perimetro definito",
            )
            self.assertNotEqual(missing.returncode, 0)
            self.complete(workspace, "DUAL_001")
            self.assertEqual(run(RUNTIME, "draft", str(workspace)).returncode, 0)
            self.assertEqual(run(RUNTIME, "validate", str(workspace)).returncode, 0)
            dossier = (workspace / "DOSSIER_INTEGRATO.md").read_text(encoding="utf-8")
            self.assertIn("[REVISIONE]", dossier)
            self.assertIn("[VIGILANZA]", dossier)

    def test_board_defaults_to_vigilanza_and_rejects_tampered_dossier(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "board"
            self.init_case(workspace, "BOARD_001")
            self.complete(workspace, "BOARD_001")
            self.assertEqual(run(RUNTIME, "draft", str(workspace)).returncode, 0)
            state = json.loads((workspace / "CASE_STATE.json").read_text(encoding="utf-8"))
            self.assertTrue(all(x["function_tag"] == "VIGILANZA" for x in state["professional_workflow"]["steps"][:8]))
            self.assertEqual(run(RUNTIME, "validate", str(workspace)).returncode, 0)
            with (workspace / "DOSSIER_INTEGRATO.md").open("a", encoding="utf-8") as handle:
                handle.write("\nmodifica successiva\n")
            approved = run(
                RUNTIME, "approve", str(workspace), "--note", "Validazione professionale completa",
                "--professional-name", "PROFESSIONAL_ALIAS", "--confirmation", "APPROVO OUTPUT",
            )
            self.assertNotEqual(approved.returncode, 0)
            self.assertIn("cambiato", approved.stderr)


if __name__ == "__main__":
    unittest.main()
