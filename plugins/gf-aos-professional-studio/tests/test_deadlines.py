import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
PLUGIN = ROOT / "plugins" / "gf-aos-professional-studio"
LIFECYCLE = PLUGIN / "scripts" / "case_lifecycle.py"
PRIVACY = PLUGIN / "scripts" / "privacy_guard.py"
DEADLINES = PLUGIN / "scripts" / "deadlines.py"
ACTIONS = PLUGIN / "scripts" / "external_actions.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args], check=False, capture_output=True, text=True
    )


class DeadlinesTest(unittest.TestCase):
    def workspace(self, root: Path) -> Path:
        workspace = root / "workspace"
        result = run(
            LIFECYCLE, "init", str(workspace), "--case-id", "CASE-DEADLINE-01",
            "--client", "Cliente Riservato Spa", "--module", "ACC_CAP_001",
            "--role", "Commercialista", "--period", "2026",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return workspace

    def source(self, workspace: Path, *, valid: bool = True) -> Path:
        source = workspace / "fonte-scadenza.md"
        text = (
            "# Nota fonte\n\n"
            "## Fonte\n\nDocumento ufficiale verificato dal professionista.\n\n"
            "## Regola\n\nIl termine indicato richiede una verifica di applicabilita.\n\n"
            "## Applicabilita\n\nApplicabile al perimetro sintetico esaminato.\n\n"
        )
        if valid:
            text += "## Data verificata\n\n2026-09-23.\n"
        source.write_text(text, encoding="utf-8")
        return source

    def scan(self, workspace: Path, source: Path) -> None:
        result = run(
            PRIVACY, "scan", str(workspace), "--file", source.name, "--profile", "internal"
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def deadline_id(self, output: str) -> str:
        match = re.search(r"DL-[0-9]{8}-[A-F0-9]{8}", output)
        self.assertIsNotNone(match, output)
        return match.group(0)

    def propose(self, workspace: Path, source: Path, *extra: str) -> tuple[str, subprocess.CompletedProcess[str]]:
        result = run(
            DEADLINES, "propose", str(workspace), "--subject-ref", "CLIENTE_A",
            "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
            "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", source.name,
            "--reminder-days", "7", "--reminder-days", "1", *extra,
        )
        return self.deadline_id(result.stdout), result

    def validate(self, root: Path, workspace: Path, deadline_id: str) -> None:
        note = root / "validazione.md"
        note.write_text("Termine e applicabilita verificati sulla fonte indicata.", encoding="utf-8")
        result = run(
            DEADLINES, "validate", str(workspace), "--deadline-id", deadline_id,
            "--note-file", str(note), "--confirmation", f"CONFERMO SCADENZA {deadline_id}",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_propose_validate_verify_and_minimized_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, proposed = self.propose(workspace, source)
            self.assertEqual(proposed.returncode, 2, proposed.stderr)
            self.assertIn("DRAFT_REVIEW_REQUIRED", proposed.stdout)
            record_path = workspace / "deadlines" / "records" / f"{deadline_id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            serialized = json.dumps(record)
            self.assertNotIn("Documento ufficiale", serialized)
            self.assertNotIn(source.name, serialized)
            self.assertEqual(record_path.stat().st_mode & 0o777, 0o600)

            note = root / "note.md"
            note.write_text("Controllo professionale completo sulla data proposta.", encoding="utf-8")
            denied = run(
                DEADLINES, "validate", str(workspace), "--deadline-id", deadline_id,
                "--note-file", str(note), "--confirmation", "APPROVO OUTPUT",
            )
            self.assertNotEqual(denied.returncode, 0)
            self.validate(root, workspace, deadline_id)
            verified = run(DEADLINES, "verify", str(workspace), "--deadline-id", deadline_id)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("VALIDATED", verified.stdout)

    def test_wrong_rome_offset_and_incomplete_source_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            wrong = run(
                DEADLINES, "propose", str(workspace), "--subject-ref", "CLIENTE_A",
                "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                "--due-at", "2026-10-31T10:00:00+02:00", "--source-note", source.name,
            )
            self.assertNotEqual(wrong.returncode, 0)
            self.assertFalse((workspace / "DEADLINES.json").exists())

            incomplete = self.source(workspace, valid=False)
            scanned = run(
                PRIVACY, "scan", str(workspace), "--file", incomplete.name,
                "--profile", "internal", "--replace",
            )
            self.assertEqual(scanned.returncode, 0, scanned.stderr)
            invalid = run(
                DEADLINES, "propose", str(workspace), "--subject-ref", "CLIENTE_A",
                "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", incomplete.name,
            )
            self.assertNotEqual(invalid.returncode, 0)

            empty_sections = workspace / "fonte-vuota.md"
            empty_sections.write_text(
                "## Fonte aggiuntiva\n\nTesto.\n\n## Fonte\n\n\n## Regola\n\nTesto.\n\n"
                "## Applicabilita\n\nTesto.\n\n## Data verificata\n\nTesto.\n",
                encoding="utf-8",
            )
            scanned = run(
                PRIVACY, "scan", str(workspace), "--file", empty_sections.name,
                "--profile", "internal", "--replace",
            )
            self.assertEqual(scanned.returncode, 0, scanned.stderr)
            invalid = run(
                DEADLINES, "propose", str(workspace), "--subject-ref", "CLIENTE_A",
                "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", empty_sections.name,
            )
            self.assertNotEqual(invalid.returncode, 0)

    def test_aliases_cannot_contain_real_identifiers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            for value in ("cliente@example.it", "RSSMRA80A01H501U"):
                result = run(
                    DEADLINES, "propose", str(workspace), "--subject-ref", value,
                    "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                    "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", source.name,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(value, result.stderr)

    def test_privacy_report_is_bound_to_current_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            source.write_text(source.read_text(encoding="utf-8") + "\nModifica successiva.\n", encoding="utf-8")
            result = run(
                DEADLINES, "propose", str(workspace), "--subject-ref", "CLIENTE_A",
                "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", source.name,
            )
            self.assertNotEqual(result.returncode, 0)

    def test_queue_is_idempotent_and_integrates_with_external_action_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, _ = self.propose(workspace, source)
            before = run(
                DEADLINES, "queue", str(workspace), "--as-of", "2026-10-20",
                "--horizon-days", "10", "--channel", "calendar",
            )
            self.assertEqual(before.returncode, 0, before.stderr)
            self.assertIn("created=0", before.stdout)
            self.assertIn("EMPTY_NO_EXTERNAL_ACTION", before.stdout)
            self.assertNotIn("READY_FOR_EXTERNAL_ACTION_PREPARATION", before.stdout)
            self.validate(root, workspace, deadline_id)
            queued = run(
                DEADLINES, "queue", str(workspace), "--as-of", "2026-10-20",
                "--horizon-days", "10", "--channel", "calendar",
            )
            self.assertEqual(queued.returncode, 0, queued.stderr)
            self.assertIn("created=2", queued.stdout)
            self.assertIn("READY_FOR_EXTERNAL_ACTION_PREPARATION", queued.stdout)
            again = run(
                DEADLINES, "queue", str(workspace), "--as-of", "2026-10-20",
                "--horizon-days", "10", "--channel", "calendar",
            )
            self.assertEqual(again.returncode, 0, again.stderr)
            self.assertIn("existing=2", again.stdout)

            requests = sorted((workspace / "deadline-reminders" / "outbox").glob("*.json"))
            self.assertEqual(len(requests), 2)
            request = json.loads(requests[0].read_text(encoding="utf-8"))
            self.assertEqual(request["status"], "BOZZA PROMEMORIA")
            self.assertFalse(request["delivery_claimed"])
            payload = workspace / request["payload"]
            report = "privacy-reports/calendar-reminder.privacy.md"
            scanned = run(
                PRIVACY, "scan", str(workspace), "--file", request["payload"],
                "--profile", "external-draft", "--output", report,
            )
            self.assertEqual(scanned.returncode, 0, scanned.stderr)
            prepared = run(
                ACTIONS, "prepare", str(workspace), "--kind", "calendar",
                "--target-ref", "CALENDARIO_STUDIO", "--payload", request["payload"],
                "--privacy-report", report,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            self.assertIn("PREPARED", prepared.stdout)
            self.assertNotIn("Cliente Riservato", payload.read_text(encoding="utf-8"))

    def test_agenda_marks_overdue_without_auto_completion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, _ = self.propose(workspace, source)
            self.validate(root, workspace, deadline_id)
            agenda = run(
                DEADLINES, "agenda", str(workspace), "--from-date", "2026-11-01", "--days", "7",
            )
            self.assertEqual(agenda.returncode, 0, agenda.stderr)
            text = (workspace / "DEADLINE_AGENDA.md").read_text(encoding="utf-8")
            self.assertIn("SCADUTA", text)
            self.assertIn("VALIDATED", text)
            self.assertNotIn("COMPLETED", text)
            refused = run(
                DEADLINES, "agenda", str(workspace), "--from-date", "2026-11-01", "--days", "7",
            )
            self.assertNotEqual(refused.returncode, 0)

    def test_operational_agenda_excludes_unvalidated_drafts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, _ = self.propose(workspace, source)
            agenda = run(
                DEADLINES, "agenda", str(workspace), "--from-date", "2026-10-25", "--days", "7",
            )
            self.assertEqual(agenda.returncode, 0, agenda.stderr)
            text = (workspace / "DEADLINE_AGENDA.md").read_text(encoding="utf-8")
            self.assertNotIn(deadline_id, text)

    def test_completion_requires_exact_gate_and_never_claims_filing_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, _ = self.propose(workspace, source)
            self.validate(root, workspace, deadline_id)
            note = root / "completion.md"
            note.write_text("Adempimento segnato come completato dal professionista.", encoding="utf-8")
            denied = run(
                DEADLINES, "complete", str(workspace), "--deadline-id", deadline_id,
                "--note-file", str(note), "--confirmation", "COMPLETATO",
            )
            self.assertNotEqual(denied.returncode, 0)
            completed = run(
                DEADLINES, "complete", str(workspace), "--deadline-id", deadline_id,
                "--note-file", str(note), "--confirmation", f"CONFERMO ADEMPIMENTO {deadline_id}",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(
                (workspace / "deadlines" / "records" / f"{deadline_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(record["status"], "COMPLETED_BY_USER")
            self.assertFalse(record["completion"]["filing_receipt_verified"])

    def test_tampering_is_blocked_live_without_echo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.workspace(root)
            source = self.source(workspace)
            self.scan(workspace, source)
            deadline_id, _ = self.propose(workspace, source)
            self.validate(root, workspace, deadline_id)
            path = workspace / "deadlines" / "records" / f"{deadline_id}.json"
            record = json.loads(path.read_text(encoding="utf-8"))
            record["due_at"] = "2026-11-30T10:00:00+01:00"
            path.write_text(json.dumps(record), encoding="utf-8")
            verified = run(DEADLINES, "verify", str(workspace), "--deadline-id", deadline_id)
            self.assertEqual(verified.returncode, 2)
            self.assertIn("BLOCKED", verified.stdout)
            status = run(DEADLINES, "status", str(workspace))
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("BLOCKED_LIVE", status.stdout)

    def test_v013_packaging_contains_deadline_contract_agent_and_evals(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.13.0")
        required = [
            ROOT / ".codex" / "agents" / "deadline-controller.toml",
            PLUGIN / "scripts" / "deadlines.py",
            PLUGIN / "skills" / "deadlines-brief" / "references" / "deadline-contract.md",
            PLUGIN / "evals" / "deadlines" / "source-validation.md",
            PLUGIN / "evals" / "deadlines" / "reminder-queue.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)


if __name__ == "__main__":
    unittest.main()
