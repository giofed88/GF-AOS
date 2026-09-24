import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
LIFECYCLE = PLUGIN / "scripts" / "case_lifecycle.py"
HARNESS = PLUGIN / "scripts" / "eval_harness.py"
HOOK = PLUGIN / "scripts" / "runtime_hooks.py"


def run(script: Path, *args: str, env: dict[str, str] | None = None, data: str | None = None):
    return subprocess.run(
        [sys.executable, str(script), *args], input=data, env=env,
        check=False, capture_output=True, text=True,
    )


class EccRuntimeTest(unittest.TestCase):
    def workspace(self, root: Path) -> Path:
        workspace = root / "case"
        result = run(
            LIFECYCLE, "init", str(workspace), "--case-id", "CASE-SEGRETO",
            "--client", "Cliente Riservato Srl", "--module", "AUDIT_001",
            "--role", "Revisore", "--period", "2026",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return workspace

    def hook(self, workspace: Path, event: str, **extra: object):
        env = dict(os.environ)
        env["GF_AOS_WORKSPACE"] = str(workspace)
        payload = {"hook_event_name": event, "session_id": "SESSION-REALE-123", **extra}
        return run(HOOK, env=env, data=json.dumps(payload))

    def checkpoint(self, workspace: Path) -> None:
        summary = workspace / "summary.md"
        summary.write_text("# Stato\n\nCheckpoint sintetico.\n", encoding="utf-8")
        result = run(
            LIFECYCLE, "checkpoint", str(workspace), "--summary-file", str(summary),
            "--status", "In corso", "--next-action", "Verificare evidenze",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_harness_writes_minimized_external_report(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "reports"
            result = run(
                HARNESS, "--repo", str(ROOT), "--output-dir", str(output),
                "--as-of", "2026-09-24", "--skip-regression",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((output / "EVAL_REPORT.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(len(report["checks"]), 4)
            self.assertFalse(report["professional_approval_claimed"])
            self.assertFalse(report["external_execution_claimed"])
            self.assertIsInstance(report["worktree_clean"], bool)
            self.assertEqual(len(report["source_sha256"]), 64)
            serialized = json.dumps(report)
            self.assertNotIn(str(ROOT), serialized)
            self.assertNotIn("stdout", serialized)

    def test_harness_rejects_output_inside_repository(self):
        result = run(
            HARNESS, "--repo", str(ROOT), "--output-dir", str(ROOT / "eval-output"),
            "--as-of", "2026-09-24", "--skip-regression",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((ROOT / "eval-output").exists())

    def test_hooks_are_minimized_and_never_read_transcript(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self.workspace(Path(temp))
            self.checkpoint(workspace)
            compact = self.hook(workspace, "PreCompact", transcript_path="/secret/transcript.jsonl")
            self.assertEqual(compact.returncode, 0, compact.stderr)
            self.assertTrue(json.loads(compact.stdout)["continue"])

            delegated = self.hook(workspace, "SubagentStart", transcript_path="/secret/transcript.jsonl")
            value = json.loads(delegated.stdout)
            serialized = json.dumps(value)
            self.assertIn("AUDIT_001", serialized)
            for forbidden in ("Cliente Riservato", "CASE-SEGRETO", str(workspace), "transcript"):
                self.assertNotIn(forbidden, serialized)

            ended = self.hook(workspace, "SessionEnd", transcript_path="/secret/transcript.jsonl")
            self.assertEqual(ended.returncode, 0, ended.stderr)
            log = (workspace / "EVENT_LOG.md").read_text(encoding="utf-8")
            self.assertIn("SESSION_ENDED", log)
            self.assertNotIn("SESSION-REALE-123", log)
            self.assertNotIn("transcript", log)

    def test_precompact_blocks_without_canonical_memory(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self.workspace(Path(temp))
            self.checkpoint(workspace)
            (workspace / "CASE_MEMORY.md").unlink()
            result = self.hook(workspace, "PreCompact")
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertFalse(value["continue"])
            self.assertIn("checkpoint", value["stopReason"])

    def test_precompact_blocks_without_current_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self.workspace(Path(temp))
            result = self.hook(workspace, "PreCompact")
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertFalse(value["continue"])
            self.assertIn("checkpoint", value["stopReason"])

    def test_invalid_runtime_state_blocks_compaction_and_is_not_delegated(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = self.workspace(Path(temp))
            state_path = workspace / "CASE_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["lead_module"] = "AUDIT_001\nCliente Riservato"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            compact = self.hook(workspace, "PreCompact")
            self.assertEqual(compact.returncode, 0, compact.stderr)
            self.assertFalse(json.loads(compact.stdout)["continue"])

            delegated = self.hook(workspace, "SubagentStart")
            serialized = delegated.stdout
            self.assertNotIn("Cliente Riservato", serialized)
            self.assertNotIn("AUDIT_001", serialized)
            self.assertIn("non disponibile", serialized)

    def test_v015_packaging(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.16.0")
        hooks = json.loads((PLUGIN / "hooks" / "codex-hooks.json").read_text(encoding="utf-8"))["hooks"]
        for event in ("SessionStart", "PreCompact", "PostCompact", "SubagentStart", "Stop", "SessionEnd"):
            self.assertIn(event, hooks)
        for path in (
            HARNESS, HOOK,
            PLUGIN / "skills" / "professional-evals" / "references" / "runtime-contract.md",
            PLUGIN / "evals" / "ecc-runtime" / "harness.md",
            PLUGIN / "evals" / "ecc-runtime" / "lifecycle.md",
        ):
            self.assertTrue(path.is_file(), path)


if __name__ == "__main__":
    unittest.main()
