import hashlib
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
DASHBOARD = PLUGIN / "scripts" / "studio_dashboard.py"


def run(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args], check=False, capture_output=True, text=True
    )


class StudioDashboardTest(unittest.TestCase):
    def case(self, root: Path, name: str, client: str, module: str = "ACC_CAP_001") -> Path:
        workspace = root / name
        result = run(
            LIFECYCLE, "init", str(workspace), "--case-id", f"ID-{name}",
            "--client", client, "--module", module,
            "--role", "Commercialista", "--period", "2026",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return workspace

    def studio(self, root: Path) -> Path:
        studio = root / "studio-dashboard"
        result = run(DASHBOARD, "init", str(studio), "--studio-ref", "STUDIO_GF_AOS")
        self.assertEqual(result.returncode, 0, result.stderr)
        return studio

    def manifest(self, root: Path, cases: list[tuple[str, Path]], **extra: object) -> Path:
        value = {
            "schema_version": 1,
            "workspaces": [
                {"workspace_ref": ref, "path": str(path)} for ref, path in cases
            ],
            **extra,
        }
        path = root / "workspace-manifest.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def build(self, studio: Path, manifest: Path, *, replace: bool = False) -> subprocess.CompletedProcess[str]:
        args = [
            "build", str(studio), "--manifest", str(manifest),
            "--as-of", "2026-10-20", "--horizon-days", "30",
        ]
        if replace:
            args.extend(["--replace", "--confirmation", "RIGENERO DASHBOARD"])
        result = run(DASHBOARD, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def checkpoint(self, root: Path, workspace: Path) -> None:
        summary = root / "summary.md"
        summary.write_text("Sintesi controllata del lavoro in corso.", encoding="utf-8")
        result = run(
            LIFECYCLE, "checkpoint", str(workspace), "--summary-file", str(summary),
            "--status", "In corso", "--next-action", "Contattare Mario Rossi",
            "--blocker", "Documento del cliente Alfa Srl non ricevuto",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_is_minimized_read_only_and_verifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = self.case(root, "case-one", "Alfa Riservata Srl")
            second = self.case(root, "case-two", "Beta Segreta Spa", "AUDIT_001")
            self.checkpoint(root, first)
            before = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*") if path.is_file()
            }
            studio = self.studio(root)
            manifest = self.manifest(root, [("CASE_A001", first), ("CASE_B001", second)])
            built = self.build(studio, manifest)
            self.assertIn("BUILT_READ_ONLY", built.stdout)

            dashboard = (studio / "STUDIO_DASHBOARD.md").read_text(encoding="utf-8")
            snapshot = json.loads((studio / "STUDIO_SNAPSHOT.json").read_text(encoding="utf-8"))
            serialized = dashboard + json.dumps(snapshot)
            for forbidden in (
                "Alfa Riservata", "Beta Segreta", "Mario Rossi", "Documento del cliente",
                str(first), str(second), "case-one", "case-two",
            ):
                self.assertNotIn(forbidden, serialized)
            self.assertIn("CASE_A001", dashboard)
            self.assertEqual(snapshot["cases"][0]["next_actions"], 1)
            self.assertGreaterEqual(snapshot["cases"][0]["blockers"], 1)
            self.assertFalse(snapshot["external_execution_claimed"])
            self.assertEqual((studio / "STUDIO_DASHBOARD.md").stat().st_mode & 0o777, 0o600)
            after = {
                path.relative_to(first).as_posix(): path.read_bytes()
                for path in first.rglob("*") if path.is_file()
            }
            self.assertEqual(before, after)
            verified = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("VERIFIED_READ_ONLY", verified.stdout)

    def test_manifest_rejects_real_identifiers_extra_fields_and_nested_dashboard(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = self.case(root, "case", "Cliente")
            studio = self.studio(root)
            for ref in ("MARIO_ROSSI", "CASE_RSSMRA80A01H501U", "CASE_12345678901"):
                manifest = self.manifest(root, [(ref, case)])
                result = run(
                    DASHBOARD, "build", str(studio), "--manifest", str(manifest),
                    "--as-of", "2026-10-20",
                )
                self.assertNotEqual(result.returncode, 0)

            value = {
                "schema_version": 1,
                "workspaces": [{"workspace_ref": "CASE_OK01", "path": str(case), "client": "Cliente"}],
            }
            bad = root / "bad-manifest.json"
            bad.write_text(json.dumps(value), encoding="utf-8")
            result = run(
                DASHBOARD, "build", str(studio), "--manifest", str(bad),
                "--as-of", "2026-10-20",
            )
            self.assertNotEqual(result.returncode, 0)

            top_extra = self.manifest(root, [("CASE_OK01", case)], client="Cliente")
            result = run(
                DASHBOARD, "build", str(studio), "--manifest", str(top_extra),
                "--as-of", "2026-10-20",
            )
            self.assertNotEqual(result.returncode, 0)

            nested = case / "dashboard"
            init = run(DASHBOARD, "init", str(nested), "--studio-ref", "STUDIO_GF_AOS")
            self.assertEqual(init.returncode, 0, init.stderr)
            manifest = self.manifest(root, [("CASE_OK01", case)])
            result = run(
                DASHBOARD, "build", str(nested), "--manifest", str(manifest),
                "--as-of", "2026-10-20",
            )
            self.assertNotEqual(result.returncode, 0)

    def test_task_lifecycle_requires_rebuild_and_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = self.case(root, "case", "Cliente Riservato")
            studio = self.studio(root)
            manifest = self.manifest(root, [("CASE_TASK01", case)])
            self.build(studio, manifest)
            added = run(
                DASHBOARD, "task-add", str(studio), "--workspace-ref", "CASE_TASK01",
                "--task-code", "TASK_ACQUISIRE_DOCUMENTI", "--owner-ref", "OWNER_STUDIO",
                "--priority", "high", "--due-date", "2026-10-10",
            )
            self.assertEqual(added.returncode, 0, added.stderr)
            task_id = re.search(r"TK-[0-9]{8}-[A-F0-9]{8}", added.stdout).group(0)
            stale = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(stale.returncode, 2)
            self.build(studio, manifest, replace=True)
            dashboard = (studio / "STUDIO_DASHBOARD.md").read_text(encoding="utf-8")
            self.assertIn(task_id, dashboard)
            self.assertIn("OVERDUE", dashboard)

            denied = run(
                DASHBOARD, "task-update", str(studio), "--task-id", task_id,
                "--status", "DONE", "--confirmation", "COMPLETATO",
            )
            self.assertNotEqual(denied.returncode, 0)
            completed = run(
                DASHBOARD, "task-update", str(studio), "--task-id", task_id,
                "--status", "DONE", "--confirmation", f"CONFERMO TASK {task_id} DONE",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            reopen = run(
                DASHBOARD, "task-update", str(studio), "--task-id", task_id,
                "--status", "IN_PROGRESS",
                "--confirmation", f"CONFERMO TASK {task_id} IN_PROGRESS",
            )
            self.assertNotEqual(reopen.returncode, 0)

    def test_deadlines_reminders_and_external_actions_are_counted_without_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = self.case(root, "case", "Cliente Riservato")
            source = case / "fonte.md"
            source.write_text(
                "## Fonte\n\nFonte ufficiale.\n\n## Regola\n\nTermine verificato.\n\n"
                "## Applicabilita\n\nCaso applicabile.\n\n## Data verificata\n\n2026-09-24.\n",
                encoding="utf-8",
            )
            scanned = run(PRIVACY, "scan", str(case), "--file", source.name, "--profile", "internal")
            self.assertEqual(scanned.returncode, 0, scanned.stderr)
            proposed = run(
                DEADLINES, "propose", str(case), "--subject-ref", "CLIENTE_A",
                "--obligation-code", "ADEMPIMENTO_IVA", "--category", "fiscal",
                "--due-at", "2026-10-31T10:00:00+01:00", "--source-note", source.name,
                "--reminder-days", "7", "--reminder-days", "1",
            )
            self.assertEqual(proposed.returncode, 2, proposed.stderr)
            deadline_id = re.search(r"DL-[0-9]{8}-[A-F0-9]{8}", proposed.stdout).group(0)
            note = root / "validation.md"
            note.write_text("Fonte e applicabilita controllate dal professionista.", encoding="utf-8")
            validated = run(
                DEADLINES, "validate", str(case), "--deadline-id", deadline_id,
                "--note-file", str(note), "--confirmation", f"CONFERMO SCADENZA {deadline_id}",
            )
            self.assertEqual(validated.returncode, 0, validated.stderr)
            queued = run(
                DEADLINES, "queue", str(case), "--as-of", "2026-10-20",
                "--horizon-days", "15", "--channel", "calendar",
            )
            self.assertEqual(queued.returncode, 0, queued.stderr)
            request = sorted((case / "deadline-reminders" / "outbox").glob("*.json"))[0]
            reminder = json.loads(request.read_text(encoding="utf-8"))
            report = "privacy-reports/reminder.privacy.md"
            scanned = run(
                PRIVACY, "scan", str(case), "--file", reminder["payload"],
                "--profile", "external-draft", "--output", report,
            )
            self.assertEqual(scanned.returncode, 0, scanned.stderr)
            prepared = run(
                ACTIONS, "prepare", str(case), "--kind", "calendar",
                "--target-ref", "CALENDARIO_STUDIO", "--payload", reminder["payload"],
                "--privacy-report", report,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)

            studio = self.studio(root)
            manifest = self.manifest(root, [("CASE_D001", case)])
            self.build(studio, manifest)
            snapshot = json.loads((studio / "STUDIO_SNAPSHOT.json").read_text(encoding="utf-8"))
            row = snapshot["cases"][0]
            self.assertEqual(row["deadlines"]["due"], 1)
            self.assertEqual(row["reminders"]["draft"], 2)
            self.assertEqual(row["external_actions"]["prepared"], 1)
            serialized = json.dumps(snapshot)
            self.assertNotIn("Cliente Riservato", serialized)
            self.assertNotIn("Fonte ufficiale", serialized)
            self.assertNotIn("CALENDARIO_STUDIO", serialized)

    def test_source_or_dashboard_tampering_blocks_live_verification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = self.case(root, "case", "Cliente")
            studio = self.studio(root)
            manifest = self.manifest(root, [("CASE_T001", case)])
            self.build(studio, manifest)
            state_path = case / "CASE_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "In corso"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            blocked = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(blocked.returncode, 2)

            self.build(studio, manifest, replace=True)
            tasks_path = studio / "STUDIO_TASKS.json"
            original_tasks = tasks_path.read_text(encoding="utf-8")
            studio_state_path = studio / "STUDIO_STATE.json"
            original_studio_state = studio_state_path.read_text(encoding="utf-8")
            tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
            tasks["tasks"]["TK-20260924-AAAAAAAA"] = {
                "task_id": "TK-20260924-AAAAAAAA",
                "workspace_ref": "CASE_T001",
                "task_code": "TASK_VALIDARE_OUTPUT",
                "owner_ref": "OWNER_STUDIO",
                "priority": "high",
                "due_date": None,
                "status": "OPEN",
                "created_at": "2026-09-24T10:00:00+00:00",
                "updated_at": "2026-09-24T10:00:00+00:00",
            }
            tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
            blocked = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("BLOCKED_LIVE", blocked.stdout)

            tasks_path.write_text(original_tasks, encoding="utf-8")
            studio_state_path.write_text(original_studio_state, encoding="utf-8")
            self.build(studio, manifest, replace=True)
            dashboard_path = studio / "STUDIO_DASHBOARD.md"
            dashboard_path.write_text(dashboard_path.read_text(encoding="utf-8") + "\nmodifica\n", encoding="utf-8")
            blocked = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(blocked.returncode, 2)

    def test_snapshot_schema_rejects_injected_sensitive_fields_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = self.case(root, "case", "Cliente Riservato")
            studio = self.studio(root)
            manifest = self.manifest(root, [("CASE_S001", case)])
            self.build(studio, manifest)

            snapshot_path = studio / "STUDIO_SNAPSHOT.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["cases"][0]["client_name"] = "Cliente Riservato"
            snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
            state_path = studio / "STUDIO_STATE.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["snapshot_sha256"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
            state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

            verified = run(DASHBOARD, "verify", str(studio), "--manifest", str(manifest))
            self.assertEqual(verified.returncode, 2)
            self.assertIn("BLOCKED_LIVE", verified.stdout)

    def test_v014_packaging_contains_dashboard_contract_agent_and_evals(self):
        manifest = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.14.0")
        required = [
            ROOT / ".codex" / "agents" / "studio-dashboard-controller.toml",
            PLUGIN / "scripts" / "studio_dashboard.py",
            PLUGIN / "skills" / "studio-dashboard" / "SKILL.md",
            PLUGIN / "skills" / "studio-dashboard" / "references" / "dashboard-contract.md",
            PLUGIN / "evals" / "studio-dashboard" / "privacy-aggregation.md",
            PLUGIN / "evals" / "studio-dashboard" / "task-lifecycle.md",
        ]
        for path in required:
            self.assertTrue(path.is_file(), path)


if __name__ == "__main__":
    unittest.main()
