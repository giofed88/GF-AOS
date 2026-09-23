import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
SCRIPT = PLUGIN / "scripts" / "case_lifecycle.py"
SESSION_START = PLUGIN / "scripts" / "session_start.py"


def run_lifecycle(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


class LifecycleQualityTest(unittest.TestCase):
    def init_case(self, workspace: Path, module: str = "AUDIT_001", *extra: str):
        result = run_lifecycle(
            "init",
            str(workspace),
            "--case-id",
            "CASE-001",
            "--client",
            "Cliente test",
            "--module",
            module,
            "--role",
            "Revisore",
            "--period",
            "2026",
            *extra,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_checkpoint_resume_and_quality(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            self.init_case(workspace)
            for name in (
                "CASE_STATE.json",
                "CASE_MEMORY.md",
                "EVIDENZE.md",
                "DOCUMENTI_MANCANTI.md",
                "ACTION_QUEUE.md",
                "EVENT_LOG.md",
            ):
                self.assertTrue((workspace / name).is_file(), name)

            summary = Path(temp) / "summary.md"
            summary.write_text("Fatti confermati e decisioni della fase corrente.", encoding="utf-8")
            result = run_lifecycle(
                "checkpoint",
                str(workspace),
                "--summary-file",
                str(summary),
                "--status",
                "In corso",
                "--next-action",
                "Acquisire evidenza A",
                "--next-action",
                "Verificare quadratura B",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((workspace / "CASE_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "In corso")
            self.assertEqual(len(state["next_actions"]), 2)
            self.assertTrue((workspace / state["current_checkpoint"]).is_file())

            resumed = run_lifecycle("resume", str(workspace))
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("Fatti confermati", resumed.stdout)

            quality = run_lifecycle("quality", str(workspace))
            self.assertEqual(quality.returncode, 0, quality.stderr)
            self.assertIn("PASS", quality.stdout)
            self.assertTrue((workspace / "QUALITY_REPORT.md").is_file())

    def test_crisis_requires_explicit_activation(self):
        with tempfile.TemporaryDirectory() as temp:
            denied = run_lifecycle(
                "init",
                str(Path(temp) / "denied"),
                "--case-id",
                "C-1",
                "--client",
                "Cliente",
                "--module",
                "CRISIS_001",
                "--role",
                "Advisor",
                "--period",
                "2026",
            )
            self.assertNotEqual(denied.returncode, 0)
            allowed = Path(temp) / "allowed"
            self.init_case(allowed, "CRISIS_001", "--crisis-explicit")
            state = json.loads((allowed / "CASE_STATE.json").read_text(encoding="utf-8"))
            self.assertTrue(state["crisis_explicit"])

    def test_init_refuses_nonempty_workspace(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            protected = workspace / "EVIDENZE.md"
            protected.write_text("contenuto esistente", encoding="utf-8")
            result = run_lifecycle(
                "init",
                str(workspace),
                "--case-id",
                "C-2",
                "--client",
                "Cliente",
                "--module",
                "AUDIT_001",
                "--role",
                "Revisore",
                "--period",
                "2026",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(protected.read_text(encoding="utf-8"), "contenuto esistente")

    def test_approval_gate_binds_artifact_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            self.init_case(workspace)
            (workspace / "EVIDENZE.md").write_text(
                "# Evidenze\n\n" + "Evidenza verificata con locator e periodo. " * 4,
                encoding="utf-8",
            )
            artifact = workspace / "outputs" / "relazione.md"
            artifact.write_text("# Relazione — BOZZA DA VALIDARE\n\nContenuto verificato.", encoding="utf-8")
            summary = Path(temp) / "summary.md"
            summary.write_text("Elaborazione completata e pronta per la validazione.", encoding="utf-8")
            checkpoint = run_lifecycle(
                "checkpoint",
                str(workspace),
                "--summary-file",
                str(summary),
                "--status",
                "Da validare",
            )
            self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
            note = Path(temp) / "note.md"
            note.write_text("Validato dopo lettura integrale.", encoding="utf-8")
            wrong = run_lifecycle(
                "approve",
                str(workspace),
                "--artifact",
                str(artifact),
                "--note-file",
                str(note),
                "--confirmation",
                "approvo",
            )
            self.assertNotEqual(wrong.returncode, 0)
            approved = run_lifecycle(
                "approve",
                str(workspace),
                "--artifact",
                str(artifact),
                "--note-file",
                str(note),
                "--confirmation",
                "APPROVO OUTPUT",
            )
            self.assertEqual(approved.returncode, 0, approved.stderr)
            state = json.loads((workspace / "CASE_STATE.json").read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "Approvato")
            self.assertEqual(len(state["approval"]["sha256"]), 64)
            receipt = (workspace / "APPROVAL_RECEIPT.md").read_text(encoding="utf-8")
            self.assertIn(state["approval"]["sha256"], receipt)
            self.assertIn("non costituisce firma digitale", receipt)

            artifact.write_text("modificato", encoding="utf-8")
            quality = run_lifecycle("quality", str(workspace))
            self.assertEqual(quality.returncode, 2)
            self.assertIn("modificato dopo l'approvazione", quality.stdout)

    def test_session_start_is_opt_in_and_read_only(self):
        env = os.environ.copy()
        env.pop("GF_AOS_WORKSPACE", None)
        result = subprocess.run(
            [sys.executable, str(SESSION_START)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            self.init_case(workspace)
            before = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file()
            }
            env["GF_AOS_WORKSPACE"] = str(workspace)
            resumed = subprocess.run(
                [sys.executable, str(SESSION_START)],
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            after = {
                path.relative_to(workspace).as_posix(): path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file()
            }
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("GF-AOS SAFE RESUME", resumed.stdout)
            self.assertNotIn("CASE-001", resumed.stdout)
            self.assertNotIn("Cliente test", resumed.stdout)
            self.assertNotIn(str(workspace), resumed.stdout)
            self.assertNotIn("CASE_MEMORY", resumed.stdout.replace("CASE_MEMORY.md", ""))
            self.assertEqual(before, after)

    def test_hook_and_skills_are_packaged(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["hooks"], "./hooks/codex-hooks.json")
        hooks = json.loads((PLUGIN / "hooks" / "codex-hooks.json").read_text(encoding="utf-8"))
        self.assertIn("SessionStart", hooks["hooks"])
        self.assertEqual(set(hooks["hooks"]), {"SessionStart"})
        handler = hooks["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertIn("commandWindows", handler)
        self.assertEqual(handler["additionalContextLimit"], 3000)
        for relative in (
            "skills/case-lifecycle/SKILL.md",
            "skills/professional-evals/SKILL.md",
            "skills/professional-evals/references/eval-matrix.md",
        ):
            self.assertTrue((PLUGIN / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
