import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
SCRIPT = PLUGIN / "scripts" / "governed_learning.py"


def run_learning(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class GovernedLearningTest(unittest.TestCase):
    def approved_workspace(self, root: Path, name: str, artifact_text: str) -> Path:
        workspace = root / name
        outputs = workspace / "outputs"
        outputs.mkdir(parents=True)
        artifact = outputs / "relazione.md"
        artifact.write_text(artifact_text, encoding="utf-8")
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        state = {
            "case_id": f"CASE-{name}",
            "client_context": f"Cliente {name}",
            "lead_module": "AUDIT_001",
            "status": "Approvato",
            "approval": {
                "status": "approvata",
                "artifact": "outputs/relazione.md",
                "sha256": digest,
            },
        }
        (workspace / "CASE_STATE.json").write_text(json.dumps(state), encoding="utf-8")
        (workspace / "APPROVAL_RECEIPT.md").write_text(
            f"# Ricevuta\n\n- SHA-256: `{digest}`\n", encoding="utf-8"
        )
        return workspace

    def propose(self, workspace: Path, lesson: Path) -> subprocess.CompletedProcess[str]:
        return run_learning(
            "propose",
            str(workspace),
            "--lesson-file",
            str(lesson),
            "--title",
            "Quadratura prima della conclusione",
            "--trigger",
            "Quando una carta di lavoro contiene totali derivati",
        )

    def test_propose_and_promote_require_approved_case_and_exact_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.approved_workspace(root, "uno", "relazione approvata uno")
            lesson = root / "lesson.md"
            lesson.write_text(
                "Ricalcolare i totali e collegare ogni differenza al locator prima di formulare la conclusione.",
                encoding="utf-8",
            )
            proposed = self.propose(workspace, lesson)
            self.assertEqual(proposed.returncode, 0, proposed.stderr)
            candidate = Path(proposed.stdout.strip())
            self.assertTrue(candidate.is_file())
            self.assertIn("DA VALIDARE", candidate.read_text(encoding="utf-8"))

            note = root / "note.md"
            note.write_text("Metodo verificato e riutilizzabile.", encoding="utf-8")
            library = root / "library"
            denied = run_learning(
                "promote", str(workspace), "--candidate", str(candidate), "--library", str(library),
                "--note-file", str(note), "--confirmation", "approvo"
            )
            self.assertNotEqual(denied.returncode, 0)
            promoted = run_learning(
                "promote", str(workspace), "--candidate", str(candidate), "--library", str(library),
                "--note-file", str(note), "--confirmation", "APPROVO METODO"
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            registry = json.loads((library / "METHOD_REGISTRY.json").read_text(encoding="utf-8"))
            serialized = json.dumps(registry)
            self.assertNotIn("Cliente uno", serialized)
            self.assertNotIn("CASE-uno", serialized)
            method = next(iter(registry["methods"].values()))
            self.assertEqual(method["confidence"], 0.5)
            self.assertEqual(len(method["evidence_digests"]), 1)

    def test_sensitive_or_unapproved_lessons_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.approved_workspace(root, "due", "relazione approvata due")
            lesson = root / "sensitive.md"
            lesson.write_text("Contattare mario@example.it per il metodo.", encoding="utf-8")
            self.assertNotEqual(self.propose(workspace, lesson).returncode, 0)
            state_path = workspace / "CASE_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "Da validare"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            clean = root / "clean.md"
            clean.write_text("Verificare sempre la quadratura con un controllo indipendente.", encoding="utf-8")
            self.assertNotEqual(self.propose(workspace, clean).returncode, 0)

    def test_reinforce_uses_distinct_approved_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.approved_workspace(root, "primo", "artefatto primo")
            lesson = root / "lesson.md"
            lesson.write_text("Ricalcolare i totali con un controllo indipendente prima della conclusione.", encoding="utf-8")
            candidate = Path(self.propose(first, lesson).stdout.strip())
            note = root / "note.md"
            note.write_text("Metodo validato per la libreria.", encoding="utf-8")
            library = root / "library"
            promoted = run_learning(
                "promote", str(first), "--candidate", str(candidate), "--library", str(library),
                "--note-file", str(note), "--confirmation", "APPROVO METODO"
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            registry = json.loads((library / "METHOD_REGISTRY.json").read_text(encoding="utf-8"))
            method_id = next(iter(registry["methods"]))
            second = self.approved_workspace(root, "secondo", "artefatto secondo distinto")
            reinforce_note = root / "reinforce-note.md"
            reinforce_note.write_text("Metodo confermato sul secondo caso.", encoding="utf-8")
            reinforced = run_learning(
                "reinforce", str(second), "--method-id", method_id, "--library", str(library),
                "--note-file", str(reinforce_note),
                "--confirmation", "CONFERMO METODO"
            )
            self.assertEqual(reinforced.returncode, 0, reinforced.stderr)
            updated = json.loads((library / "METHOD_REGISTRY.json").read_text(encoding="utf-8"))
            self.assertEqual(updated["methods"][method_id]["confidence"], 0.6)
            duplicate = run_learning(
                "reinforce", str(second), "--method-id", method_id, "--library", str(library),
                "--note-file", str(reinforce_note),
                "--confirmation", "CONFERMO METODO"
            )
            self.assertNotEqual(duplicate.returncode, 0)

            same_case = self.approved_workspace(root, "copia", "terzo artefatto distinto")
            same_state_path = same_case / "CASE_STATE.json"
            same_state = json.loads(same_state_path.read_text(encoding="utf-8"))
            first_state = json.loads((first / "CASE_STATE.json").read_text(encoding="utf-8"))
            same_state["case_id"] = first_state["case_id"]
            same_state_path.write_text(json.dumps(same_state), encoding="utf-8")
            same_case_attempt = run_learning(
                "reinforce", str(same_case), "--method-id", method_id, "--library", str(library),
                "--note-file", str(reinforce_note), "--confirmation", "CONFERMO METODO"
            )
            self.assertNotEqual(same_case_attempt.returncode, 0)

    def test_packaging(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.14.0")
        for relative in (
            "skills/governed-learning/SKILL.md",
            "skills/governed-learning/references/learning-contract.md",
            "evals/governed-learning/privacy.md",
            "evals/governed-learning/gates.md",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)
        self.assertTrue((ROOT / ".codex" / "agents" / "method-curator.toml").is_file())


if __name__ == "__main__":
    unittest.main()
