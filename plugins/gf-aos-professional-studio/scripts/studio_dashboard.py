#!/usr/bin/env python3
"""Cruscotto governato e pseudonimizzato per workspace GF-AOS.

Aggrega soltanto stato e conteggi controllati. Non copia percorsi, nomi cliente,
testi dei fascicoli e non esegue azioni esterne.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import case_lifecycle as lifecycle
import deadlines as deadline_engine
import external_actions as action_engine
import remote_dossiers as remote_engine
import workflow_packs
from context_curator import injection_flags


SCHEMA_VERSION = 1
STUDIO_REF_RE = re.compile(r"^STUDIO_[A-Z0-9][A-Z0-9_]{1,47}$")
WORKSPACE_REF_RE = re.compile(r"^CASE_[A-Z]{1,4}[0-9]{2,12}$")
TASK_CODE_RE = re.compile(r"^TASK_[A-Z_]{3,48}$")
OWNER_REF_RE = re.compile(r"^OWNER_[A-Z_]{3,32}$")
TASK_ID_RE = re.compile(r"^TK-[0-9]{8}-[A-F0-9]{8}$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
MODULE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,39}$")
PERIOD_RE = re.compile(r"^[0-9]{4}(?:[-/][0-9]{2,4})?$")
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_WORKSPACES = 200
MAX_TASKS = 2000
TASK_PRIORITIES = {"urgent", "high", "normal", "low"}
TASK_CODES = {
    "TASK_DEFINIRE_PERIMETRO",
    "TASK_ACQUISIRE_DOCUMENTI",
    "TASK_VERIFICARE_FONTI",
    "TASK_ESEGUIRE_CONTROLLI",
    "TASK_RISOLVERE_BLOCKER",
    "TASK_PREPARARE_OUTPUT",
    "TASK_VALIDARE_OUTPUT",
    "TASK_PREPARARE_COMUNICAZIONE",
    "TASK_VERIFICARE_SCADENZA",
    "TASK_ARCHIVIARE_FASCICOLO",
}
OWNER_REFS = {
    "OWNER_STUDIO",
    "OWNER_CLIENTE",
    "OWNER_COLLABORATORE",
    "OWNER_PROFESSIONISTA",
    "OWNER_ESTERNO",
}
TASK_STATUSES = {"OPEN", "IN_PROGRESS", "WAITING", "DONE"}
TASK_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "WAITING", "DONE"},
    "IN_PROGRESS": {"WAITING", "DONE"},
    "WAITING": {"IN_PROGRESS", "DONE"},
    "DONE": set(),
}
CASE_STATUSES = set(lifecycle.STATUSES)
CONTROLLED_PATTERNS = (
    "CASE_STATE.json",
    "DEADLINES.json",
    "deadlines/records/*.json",
    "deadlines/sources/*.md",
    "deadlines/reports/*.md",
    "EXTERNAL_ACTIONS.json",
    "external-actions/*.json",
    "external-actions/outbox/*.json",
    "remote-dossiers/BASELINE.json",
    "remote-dossiers/outbox/*.json",
    "deadline-reminders/outbox/*.json",
    "deadline-reminders/payloads/*.md",
)


class DashboardError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_text(value: str) -> str:
    return sha_bytes(value.encode("utf-8"))


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha_text(encoded)


def atomic_text(path: Path, content: str, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise DashboardError("Artefatto governato gia esistente")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: dict[str, Any], *, replace: bool) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", replace=replace)


def directory(raw: str, *, create: bool = False, empty: bool = False) -> Path:
    lexical = Path(raw).expanduser()
    if lexical.exists() and lexical.is_symlink():
        raise DashboardError("Directory dashboard non valida")
    if create:
        lexical.mkdir(parents=True, exist_ok=True)
    path = lexical.resolve()
    if not path.is_dir():
        raise DashboardError("Directory dashboard non valida")
    if empty and any(path.iterdir()):
        raise DashboardError("La directory dashboard iniziale deve essere vuota")
    return path


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise DashboardError(f"{label} non valido")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardError(f"{label} non valido") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise DashboardError(f"{label} non valido")
    return value


def validate_alias(value: object, pattern: re.Pattern[str], label: str) -> str:
    alias = str(value)
    if not pattern.fullmatch(alias) or injection_flags(alias):
        raise DashboardError(f"{label} deve essere un alias pseudonimizzato valido")
    if re.search(r"[0-9]{9,}", alias) or re.search(r"[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]", alias):
        raise DashboardError(f"{label} deve essere un alias pseudonimizzato valido")
    return alias


def parse_day(raw: str, label: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise DashboardError(f"{label} non valida") from exc


def valid_iso(raw: object) -> bool:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    return value.tzinfo is not None


def state_path(root: Path) -> Path:
    return root / "STUDIO_STATE.json"


def task_path(root: Path) -> Path:
    return root / "STUDIO_TASKS.json"


def snapshot_path(root: Path) -> Path:
    return root / "STUDIO_SNAPSHOT.json"


def dashboard_path(root: Path) -> Path:
    return root / "STUDIO_DASHBOARD.md"


def append_event(root: Path, event: str, detail: str) -> None:
    path = root / "STUDIO_EVENT_LOG.md"
    if not path.is_file() or path.is_symlink():
        raise DashboardError("Registro eventi dashboard non valido")
    safe = detail.replace("|", "/").replace("\n", " ")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"| {now_iso()} | {event} | {safe} |\n")


def load_state(root: Path) -> dict[str, Any]:
    value = load_json(state_path(root), "Stato dashboard")
    if set(value) != {
        "schema_version", "studio_ref", "created_at", "updated_at", "snapshot_sha256",
        "dashboard_sha256", "tasks_sha256", "stale",
    }:
        raise DashboardError("Stato dashboard non valido")
    if not STUDIO_REF_RE.fullmatch(str(value.get("studio_ref", ""))):
        raise DashboardError("Stato dashboard non valido")
    for field in ("created_at", "updated_at"):
        if not valid_iso(value.get(field)):
            raise DashboardError("Stato dashboard non valido")
    for field in ("snapshot_sha256", "dashboard_sha256", "tasks_sha256"):
        digest = value.get(field)
        if field == "tasks_sha256" and not HASH_RE.fullmatch(str(digest)):
            raise DashboardError("Stato dashboard non valido")
        if field != "tasks_sha256" and digest is not None and not HASH_RE.fullmatch(str(digest)):
            raise DashboardError("Stato dashboard non valido")
    if not isinstance(value.get("stale"), bool):
        raise DashboardError("Stato dashboard non valido")
    return value


def load_tasks(root: Path) -> dict[str, Any]:
    value = load_json(task_path(root), "Registro task")
    if set(value) != {"schema_version", "tasks"}:
        raise DashboardError("Registro task non valido")
    tasks = value.get("tasks")
    if not isinstance(tasks, dict) or len(tasks) > MAX_TASKS:
        raise DashboardError("Registro task non valido")
    for task_id, item in tasks.items():
        if (
            not TASK_ID_RE.fullmatch(str(task_id))
            or not isinstance(item, dict)
            or set(item) != {
                "task_id", "workspace_ref", "task_code", "owner_ref", "priority",
                "due_date", "status", "created_at", "updated_at",
            }
            or item.get("task_id") != task_id
            or not WORKSPACE_REF_RE.fullmatch(str(item.get("workspace_ref", "")))
            or not TASK_CODE_RE.fullmatch(str(item.get("task_code", "")))
            or not OWNER_REF_RE.fullmatch(str(item.get("owner_ref", "")))
            or item.get("task_code") not in TASK_CODES
            or item.get("owner_ref") not in OWNER_REFS
            or item.get("priority") not in TASK_PRIORITIES
            or item.get("status") not in TASK_STATUSES
            or not valid_iso(item.get("created_at"))
            or not valid_iso(item.get("updated_at"))
        ):
            raise DashboardError("Registro task non valido")
        if item.get("due_date") is not None:
            parse_day(str(item["due_date"]), "Data task")
        validate_alias(item["workspace_ref"], WORKSPACE_REF_RE, "workspace_ref")
        validate_alias(item["task_code"], TASK_CODE_RE, "task_code")
        validate_alias(item["owner_ref"], OWNER_REF_RE, "owner_ref")
    return value


def assert_tasks_integrity(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    path = task_path(root)
    if digest_file(path) != state.get("tasks_sha256"):
        raise DashboardError("Registro task modificato fuori dal flusso governato")
    return load_tasks(root)


def load_manifest(raw: str, studio_root: Path) -> list[tuple[str, Path]]:
    path = Path(raw).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise DashboardError("Manifest workspace non valido")
    value = load_json(path, "Manifest workspace")
    if set(value) != {"schema_version", "workspaces"}:
        raise DashboardError("Manifest workspace non valido")
    items = value.get("workspaces")
    if not isinstance(items, list) or not items or len(items) > MAX_WORKSPACES:
        raise DashboardError("Manifest workspace non valido")
    result: list[tuple[str, Path]] = []
    refs: set[str] = set()
    paths: set[Path] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"workspace_ref", "path"}:
            raise DashboardError("Manifest workspace non valido")
        workspace_ref = validate_alias(item["workspace_ref"], WORKSPACE_REF_RE, "workspace_ref")
        lexical = Path(str(item["path"])).expanduser()
        if not lexical.is_absolute() or not lexical.is_dir() or lexical.is_symlink():
            raise DashboardError("Workspace sorgente non valido")
        workspace = lexical.resolve()
        if workspace == studio_root or studio_root in workspace.parents or workspace in studio_root.parents:
            raise DashboardError("Dashboard e workspace sorgente devono essere separati")
        if workspace_ref in refs or workspace in paths:
            raise DashboardError("Manifest workspace duplicato")
        refs.add(workspace_ref)
        paths.add(workspace)
        result.append((workspace_ref, workspace))
    return sorted(result)


def manifest_digest(items: list[tuple[str, Path]]) -> str:
    sanitized = [
        {"workspace_ref": ref, "locator_sha256": sha_text(str(path))}
        for ref, path in items
    ]
    return canonical_digest(sanitized)


def controlled_files(workspace: Path) -> list[Path]:
    files: set[Path] = set()
    for pattern in CONTROLLED_PATTERNS:
        files.update(path for path in workspace.glob(pattern) if path.is_file())
    if len(files) > 5000:
        raise DashboardError("Troppi artefatti governati nel workspace")
    for path in files:
        if path.is_symlink():
            raise DashboardError("Artefatto governato simbolico")
        try:
            path.resolve().relative_to(workspace)
        except ValueError as exc:
            raise DashboardError("Artefatto governato fuori dal workspace") from exc
    return sorted(files)


def source_fingerprint(workspace: Path) -> str:
    members = [
        f"{path.relative_to(workspace).as_posix()}:{digest_file(path)}"
        for path in controlled_files(workspace)
    ]
    return sha_text("\n".join(members))


def validate_case_state(workspace: Path) -> dict[str, Any]:
    state = lifecycle.read_state(workspace)
    if (
        not isinstance(state, dict)
        or not MODULE_RE.fullmatch(str(state.get("lead_module", "")))
        or state.get("lead_module") not in workflow_packs.PACKS
        or state.get("status") not in CASE_STATUSES
        or not PERIOD_RE.fullmatch(str(state.get("period", "")))
        or not valid_iso(state.get("updated_at"))
        or not isinstance(state.get("next_actions"), list)
        or not isinstance(state.get("blockers"), list)
        or len(state["next_actions"]) > 4
    ):
        raise DashboardError("Stato fascicolo non valido")
    return state


def deadline_counts(workspace: Path, state: dict[str, Any], as_of: date, end: date) -> dict[str, int]:
    counts: Counter[str] = Counter()
    registry_file = workspace / "DEADLINES.json"
    if not registry_file.exists():
        return {key: 0 for key in ("draft", "due", "overdue", "completed", "blocked")}
    registry = deadline_engine.load_registry(registry_file)
    for deadline_id in registry["deadlines"]:
        try:
            record = deadline_engine.assert_verified(workspace, state, deadline_id)
            status = record["status"]
            due = deadline_engine.parse_due_at(record["due_at"]).date()
        except Exception:
            counts["blocked"] += 1
            continue
        if status == "DRAFT_REVIEW_REQUIRED":
            counts["draft"] += 1
        elif status == "COMPLETED_BY_USER":
            counts["completed"] += 1
        elif due < as_of:
            counts["overdue"] += 1
        elif due <= end:
            counts["due"] += 1
    return {key: counts[key] for key in ("draft", "due", "overdue", "completed", "blocked")}


def action_counts(workspace: Path, state: dict[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    registry_file = workspace / "EXTERNAL_ACTIONS.json"
    if not registry_file.exists():
        return {key: 0 for key in ("prepared", "data_review", "approved", "blocked")}
    registry = action_engine.load_registry(registry_file)
    for action_id, item in registry["actions"].items():
        status = item["status"]
        if status == "PREPARED":
            counts["prepared"] += 1
        elif status == "DATA_REVIEW_REQUIRED":
            counts["data_review"] += 1
        else:
            try:
                action_engine.assert_ready(workspace, state, action_id)
                counts["approved"] += 1
            except Exception:
                counts["blocked"] += 1
    return {key: counts[key] for key in ("prepared", "data_review", "approved", "blocked")}


def reminder_counts(workspace: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    outbox = workspace / "deadline-reminders" / "outbox"
    if not outbox.exists():
        return {"draft": 0, "blocked": 0}
    if not outbox.is_dir() or outbox.is_symlink():
        return {"draft": 0, "blocked": 1}
    for path in outbox.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if (
                path.is_symlink()
                or not isinstance(value, dict)
                or value.get("status") != "BOZZA PROMEMORIA"
                or value.get("delivery_claimed") is not False
                or not deadline_engine.REMINDER_ID_RE.fullmatch(str(value.get("reminder_id", "")))
            ):
                raise ValueError
            counts["draft"] += 1
        except (OSError, json.JSONDecodeError, ValueError):
            counts["blocked"] += 1
    return {"draft": counts["draft"], "blocked": counts["blocked"]}


def remote_counts(workspace: Path) -> dict[str, Any]:
    baseline = "ABSENT"
    baseline_path = workspace / "remote-dossiers" / "BASELINE.json"
    if baseline_path.exists():
        try:
            remote_engine.load_baseline(workspace)
            baseline = "REGISTERED_NOT_LIVE_VERIFIED"
        except Exception:
            baseline = "BLOCKED"
    counts: Counter[str] = Counter()
    outbox = workspace / "remote-dossiers" / "outbox"
    if outbox.exists():
        if not outbox.is_dir() or outbox.is_symlink():
            counts["blocked"] += 1
        else:
            for path in outbox.glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                    if path.is_symlink() or not isinstance(value, dict) or value.get("execution_claimed") is not False:
                        raise ValueError
                    status = value.get("status")
                    if status == "BOZZA RICHIESTA LETTURA":
                        counts["read"] += 1
                    elif status == "BOZZA RICHIESTA MODIFICA SORGENTI":
                        counts["change"] += 1
                    else:
                        raise ValueError
                except (OSError, json.JSONDecodeError, ValueError):
                    counts["blocked"] += 1
    return {"baseline": baseline, "read": counts["read"], "change": counts["change"], "blocked": counts["blocked"]}


def workspace_summary(workspace_ref: str, workspace: Path, as_of: date, end: date) -> dict[str, Any]:
    state = validate_case_state(workspace)
    quality, structural_blockers, structural_warnings = lifecycle.evaluate(workspace, state)
    return {
        "workspace_ref": workspace_ref,
        "locator_sha256": sha_text(str(workspace)),
        "source_fingerprint": source_fingerprint(workspace),
        "module": state["lead_module"],
        "period": str(state["period"]),
        "status": state["status"],
        "updated_at": state["updated_at"],
        "quality": quality,
        "blockers": len(state["blockers"]) + len(structural_blockers),
        "next_actions": len(state["next_actions"]),
        "quality_warnings": len(structural_warnings),
        "deadlines": deadline_counts(workspace, state, as_of, end),
        "external_actions": action_counts(workspace, state),
        "reminders": reminder_counts(workspace),
        "remote": remote_counts(workspace),
    }


def task_summary(tasks: dict[str, Any], refs: set[str], as_of: date) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for task_id, task in sorted(tasks["tasks"].items()):
        if task["workspace_ref"] not in refs:
            continue
        due = parse_day(task["due_date"], "Data task") if task.get("due_date") else None
        timing = "OVERDUE" if due and due < as_of and task["status"] != "DONE" else "CURRENT"
        result.append({
            "task_id": task_id,
            "workspace_ref": task["workspace_ref"],
            "task_code": task["task_code"],
            "owner_ref": task["owner_ref"],
            "priority": task["priority"],
            "due_date": task.get("due_date"),
            "status": task["status"],
            "timing": timing,
        })
    return result


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def render_dashboard(snapshot: dict[str, Any]) -> str:
    totals = snapshot["totals"]
    lines = [
        "# GF-AOS Studio Dashboard — DERIVATO PSEUDONIMIZZATO",
        "",
        f"- Studio: `{snapshot['studio_ref']}`",
        f"- Data operativa: `{snapshot['as_of']}`",
        f"- Orizzonte scadenze: {snapshot['horizon_days']} giorni",
        f"- Fascicoli: {totals['cases']}",
        f"- Fascicoli bloccati o con rilievi: {totals['attention_cases']}",
        f"- Scadenze scadute: {totals['overdue_deadlines']}",
        f"- Task aperti scaduti: {totals['overdue_tasks']}",
        "- Il report non contiene nomi cliente, percorsi o testi dei fascicoli.",
        "- Nessuna azione esterna e stata eseguita.",
        "",
        "## Fascicoli",
        "",
        "| Workspace | Modulo | Periodo | Stato | Qualita | Blocker | Prossime azioni | Scadenze entro finestra | Scadute | Azioni esterne pronte | Anomalie live |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in snapshot["cases"]:
        anomalies = (
            case["deadlines"]["blocked"]
            + case["external_actions"]["blocked"]
            + case["reminders"]["blocked"]
            + case["remote"]["blocked"]
            + (1 if case["remote"]["baseline"] == "BLOCKED" else 0)
        )
        lines.append(
            f"| `{case['workspace_ref']}` | `{case['module']}` | `{markdown_cell(case['period'])}` | "
            f"`{case['status']}` | `{case['quality']}` | {case['blockers']} | {case['next_actions']} | "
            f"{case['deadlines']['due']} | {case['deadlines']['overdue']} | "
            f"{case['external_actions']['approved']} | {anomalies} |"
        )
    lines.extend([
        "",
        "## Task governati",
        "",
        "| Task ID | Workspace | Codice | Owner | Priorita | Scadenza | Stato | Timing |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for task in snapshot["tasks"]:
        lines.append(
            f"| `{task['task_id']}` | `{task['workspace_ref']}` | `{task['task_code']}` | "
            f"`{task['owner_ref']}` | `{task['priority']}` | `{task['due_date'] or '—'}` | "
            f"`{task['status']}` | `{task['timing']}` |"
        )
    if not snapshot["tasks"]:
        lines.append("| — | — | — | — | — | — | — | — |")
    lines.extend([
        "",
        "## Limiti",
        "",
        "Il cruscotto e un indice derivato read-only. I conteggi non sostituiscono l'apertura del "
        "fascicolo, la verifica della fonte, il giudizio professionale o il riscontro del connettore live.",
        "",
    ])
    return "\n".join(lines)


def validate_snapshot(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != {
        "schema_version", "studio_ref", "captured_at", "as_of", "horizon_days",
        "manifest_sha256", "cases", "tasks", "totals", "external_execution_claimed",
    }:
        raise DashboardError("Snapshot dashboard non valido")
    if (
        not STUDIO_REF_RE.fullmatch(str(value.get("studio_ref", "")))
        or not valid_iso(value.get("captured_at"))
        or type(value.get("horizon_days")) is not int
        or not 1 <= value["horizon_days"] <= 366
        or not HASH_RE.fullmatch(str(value.get("manifest_sha256", "")))
        or value.get("external_execution_claimed") is not False
    ):
        raise DashboardError("Snapshot dashboard non valido")
    parse_day(str(value.get("as_of")), "Data dashboard")
    cases = value.get("cases")
    tasks = value.get("tasks")
    totals = value.get("totals")
    if not isinstance(cases, list) or not isinstance(tasks, list) or not isinstance(totals, dict):
        raise DashboardError("Snapshot dashboard non valido")
    if len(cases) > MAX_WORKSPACES or len(tasks) > MAX_TASKS:
        raise DashboardError("Snapshot dashboard non valido")
    case_fields = {
        "workspace_ref", "locator_sha256", "source_fingerprint", "module", "period",
        "status", "updated_at", "quality", "blockers", "next_actions",
        "quality_warnings", "deadlines", "external_actions", "reminders", "remote",
    }
    counter_fields = {
        "deadlines": {"draft", "due", "overdue", "completed", "blocked"},
        "external_actions": {"prepared", "data_review", "approved", "blocked"},
        "reminders": {"draft", "blocked"},
    }
    refs: set[str] = set()
    for item in cases:
        if not isinstance(item, dict) or set(item) != case_fields:
            raise DashboardError("Snapshot dashboard non valido")
        workspace_ref = validate_alias(item.get("workspace_ref"), WORKSPACE_REF_RE, "workspace_ref")
        if (
            workspace_ref in refs
            or not HASH_RE.fullmatch(str(item.get("locator_sha256", "")))
            or not HASH_RE.fullmatch(str(item.get("source_fingerprint", "")))
            or item.get("module") not in workflow_packs.PACKS
            or not PERIOD_RE.fullmatch(str(item.get("period", "")))
            or item.get("status") not in CASE_STATUSES
            or not valid_iso(item.get("updated_at"))
            or item.get("quality") not in {"PASS", "PASS CON RILIEVI", "BLOCKED"}
        ):
            raise DashboardError("Snapshot dashboard non valido")
        refs.add(workspace_ref)
        for field in ("blockers", "next_actions", "quality_warnings"):
            if type(item.get(field)) is not int or item[field] < 0:
                raise DashboardError("Snapshot dashboard non valido")
        for field, expected in counter_fields.items():
            counts = item.get(field)
            if (
                not isinstance(counts, dict)
                or set(counts) != expected
                or any(type(count) is not int or count < 0 for count in counts.values())
            ):
                raise DashboardError("Snapshot dashboard non valido")
        remote = item.get("remote")
        if (
            not isinstance(remote, dict)
            or set(remote) != {"baseline", "read", "change", "blocked"}
            or remote.get("baseline") not in {"ABSENT", "REGISTERED_NOT_LIVE_VERIFIED", "BLOCKED"}
            or any(type(remote.get(field)) is not int or remote[field] < 0 for field in ("read", "change", "blocked"))
        ):
            raise DashboardError("Snapshot dashboard non valido")
    task_fields = {
        "task_id", "workspace_ref", "task_code", "owner_ref", "priority",
        "due_date", "status", "timing",
    }
    task_ids: set[str] = set()
    for item in tasks:
        if not isinstance(item, dict) or set(item) != task_fields:
            raise DashboardError("Snapshot dashboard non valido")
        task_id = str(item.get("task_id", ""))
        if (
            not TASK_ID_RE.fullmatch(task_id)
            or task_id in task_ids
            or item.get("workspace_ref") not in refs
            or item.get("task_code") not in TASK_CODES
            or item.get("owner_ref") not in OWNER_REFS
            or item.get("priority") not in TASK_PRIORITIES
            or item.get("status") not in TASK_STATUSES
            or item.get("timing") not in {"CURRENT", "OVERDUE"}
        ):
            raise DashboardError("Snapshot dashboard non valido")
        task_ids.add(task_id)
        if item.get("due_date") is not None:
            parse_day(str(item["due_date"]), "Data task")
    if (
        set(totals) != {"cases", "attention_cases", "overdue_deadlines", "overdue_tasks"}
        or any(type(count) is not int or count < 0 for count in totals.values())
        or totals["cases"] != len(cases)
    ):
        raise DashboardError("Snapshot dashboard non valido")
    return value


def command_init(args: argparse.Namespace) -> int:
    studio_ref = validate_alias(args.studio_ref, STUDIO_REF_RE, "studio_ref")
    root = directory(args.dashboard, create=True, empty=True)
    timestamp = now_iso()
    task_value: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "tasks": {}}
    atomic_json(task_path(root), task_value, replace=False)
    state = {
        "schema_version": SCHEMA_VERSION,
        "studio_ref": studio_ref,
        "created_at": timestamp,
        "updated_at": timestamp,
        "snapshot_sha256": None,
        "dashboard_sha256": None,
        "tasks_sha256": digest_file(task_path(root)),
        "stale": True,
    }
    atomic_json(state_path(root), state, replace=False)
    atomic_text(
        root / "STUDIO_EVENT_LOG.md",
        "# GF-AOS Studio Event Log\n\n| Data UTC | Evento | Dettaglio |\n| --- | --- | --- |\n",
        replace=False,
    )
    append_event(root, "STUDIO_INITIALIZED", f"studio_ref={studio_ref}")
    print(f"GF-AOS studio dashboard: {studio_ref} INITIALIZED")
    return 0


def command_build(args: argparse.Namespace) -> int:
    root = directory(args.dashboard)
    state = load_state(root)
    tasks = assert_tasks_integrity(root, state)
    as_of = parse_day(args.as_of, "Data as-of")
    if args.horizon_days < 1 or args.horizon_days > 366:
        raise DashboardError("Orizzonte dashboard non valido")
    end = as_of + timedelta(days=args.horizon_days)
    manifest = load_manifest(args.manifest, root)
    output_exists = snapshot_path(root).exists() or dashboard_path(root).exists()
    if output_exists and (not args.replace or args.confirmation != "RIGENERO DASHBOARD"):
        raise DashboardError("Dashboard esistente: usare --replace e conferma dedicata")
    cases = [workspace_summary(ref, path, as_of, end) for ref, path in manifest]
    refs = {case["workspace_ref"] for case in cases}
    task_rows = task_summary(tasks, refs, as_of)
    totals = {
        "cases": len(cases),
        "attention_cases": sum(case["quality"] != "PASS" or case["blockers"] > 0 for case in cases),
        "overdue_deadlines": sum(case["deadlines"]["overdue"] for case in cases),
        "overdue_tasks": sum(task["timing"] == "OVERDUE" for task in task_rows),
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "studio_ref": state["studio_ref"],
        "captured_at": now_iso(),
        "as_of": as_of.isoformat(),
        "horizon_days": args.horizon_days,
        "manifest_sha256": manifest_digest(manifest),
        "cases": cases,
        "tasks": task_rows,
        "totals": totals,
        "external_execution_claimed": False,
    }
    markdown = render_dashboard(snapshot)
    atomic_json(snapshot_path(root), snapshot, replace=output_exists)
    atomic_text(dashboard_path(root), markdown, replace=output_exists)
    state["updated_at"] = now_iso()
    state["snapshot_sha256"] = digest_file(snapshot_path(root))
    state["dashboard_sha256"] = digest_file(dashboard_path(root))
    state["stale"] = False
    atomic_json(state_path(root), state, replace=True)
    append_event(root, "DASHBOARD_BUILT", f"cases={len(cases)}; tasks={len(task_rows)}")
    print(f"GF-AOS studio dashboard: cases={len(cases)} tasks={len(task_rows)} BUILT_READ_ONLY")
    return 0


def assert_dashboard(root: Path, manifest_raw: str) -> dict[str, Any]:
    state = load_state(root)
    if state["stale"]:
        raise DashboardError("Dashboard da rigenerare")
    tasks = assert_tasks_integrity(root, state)
    snapshot_file = snapshot_path(root)
    markdown_file = dashboard_path(root)
    if not snapshot_file.is_file() or snapshot_file.is_symlink() or not markdown_file.is_file() or markdown_file.is_symlink():
        raise DashboardError("Dashboard non completa")
    if digest_file(snapshot_file) != state.get("snapshot_sha256") or digest_file(markdown_file) != state.get("dashboard_sha256"):
        raise DashboardError("Dashboard modificata dopo la generazione")
    snapshot = validate_snapshot(load_json(snapshot_file, "Snapshot dashboard"))
    if snapshot.get("studio_ref") != state["studio_ref"] or snapshot.get("external_execution_claimed") is not False:
        raise DashboardError("Snapshot dashboard non valido")
    manifest = load_manifest(manifest_raw, root)
    if manifest_digest(manifest) != snapshot.get("manifest_sha256"):
        raise DashboardError("Manifest workspace diverso da quello della dashboard")
    indexed = {item["workspace_ref"]: item for item in snapshot.get("cases", []) if isinstance(item, dict)}
    if len(indexed) != len(manifest):
        raise DashboardError("Snapshot dashboard non valido")
    for workspace_ref, workspace in manifest:
        item = indexed.get(workspace_ref)
        if not item or item.get("locator_sha256") != sha_text(str(workspace)):
            raise DashboardError("Workspace dashboard non coerente")
        if item.get("source_fingerprint") != source_fingerprint(workspace):
            raise DashboardError("Sorgenti governate cambiate dopo la dashboard")
    as_of = parse_day(str(snapshot.get("as_of")), "Data dashboard")
    end = as_of + timedelta(days=snapshot["horizon_days"])
    expected_cases = [workspace_summary(ref, path, as_of, end) for ref, path in manifest]
    if expected_cases != snapshot["cases"]:
        raise DashboardError("Aggregazione dashboard non coerente")
    expected_tasks = task_summary(tasks, set(indexed), parse_day(str(snapshot.get("as_of")), "Data dashboard"))
    if expected_tasks != snapshot.get("tasks"):
        raise DashboardError("Task dashboard non coerenti")
    expected_totals = {
        "cases": len(expected_cases),
        "attention_cases": sum(case["quality"] != "PASS" or case["blockers"] > 0 for case in expected_cases),
        "overdue_deadlines": sum(case["deadlines"]["overdue"] for case in expected_cases),
        "overdue_tasks": sum(task["timing"] == "OVERDUE" for task in expected_tasks),
    }
    if expected_totals != snapshot["totals"]:
        raise DashboardError("Totali dashboard non coerenti")
    return snapshot


def command_verify(args: argparse.Namespace) -> int:
    root = directory(args.dashboard)
    try:
        assert_dashboard(root, args.manifest)
    except (DashboardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("GF-AOS studio dashboard: BLOCKED_LIVE")
        return 2
    print("GF-AOS studio dashboard: VERIFIED_READ_ONLY")
    return 0


def current_refs(root: Path) -> set[str]:
    state = load_state(root)
    if state["stale"] or digest_file(snapshot_path(root)) != state.get("snapshot_sha256"):
        raise DashboardError("Snapshot dashboard non valido")
    snapshot = load_json(snapshot_path(root), "Snapshot dashboard")
    refs = {str(item.get("workspace_ref", "")) for item in snapshot.get("cases", []) if isinstance(item, dict)}
    if not refs or any(not WORKSPACE_REF_RE.fullmatch(ref) for ref in refs):
        raise DashboardError("Snapshot dashboard non valido")
    return refs


def command_task_add(args: argparse.Namespace) -> int:
    root = directory(args.dashboard)
    state = load_state(root)
    assert_tasks_integrity(root, state)
    refs = current_refs(root)
    workspace_ref = validate_alias(args.workspace_ref, WORKSPACE_REF_RE, "workspace_ref")
    task_code = validate_alias(args.task_code, TASK_CODE_RE, "task_code")
    owner_ref = validate_alias(args.owner_ref, OWNER_REF_RE, "owner_ref")
    if task_code not in TASK_CODES or owner_ref not in OWNER_REFS:
        raise DashboardError("Codice task o owner non appartenente al vocabolario governato")
    if workspace_ref not in refs:
        raise DashboardError("workspace_ref non presente nell'ultima dashboard")
    due_date = parse_day(args.due_date, "Data task").isoformat() if args.due_date else None
    tasks = load_tasks(root)
    if len(tasks["tasks"]) >= MAX_TASKS:
        raise DashboardError("Limite task raggiunto")
    task_id = f"TK-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    timestamp = now_iso()
    tasks["tasks"][task_id] = {
        "task_id": task_id,
        "workspace_ref": workspace_ref,
        "task_code": task_code,
        "owner_ref": owner_ref,
        "priority": args.priority,
        "due_date": due_date,
        "status": "OPEN",
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    atomic_json(task_path(root), tasks, replace=True)
    state["updated_at"] = now_iso()
    state["tasks_sha256"] = digest_file(task_path(root))
    state["stale"] = True
    atomic_json(state_path(root), state, replace=True)
    append_event(root, "TASK_ADDED", f"task_id={task_id}; workspace_ref={workspace_ref}")
    print(f"GF-AOS studio task: {task_id} OPEN")
    return 0


def command_task_update(args: argparse.Namespace) -> int:
    root = directory(args.dashboard)
    state = load_state(root)
    tasks = assert_tasks_integrity(root, state)
    if not TASK_ID_RE.fullmatch(args.task_id) or args.task_id not in tasks["tasks"]:
        raise DashboardError("Task ID non valido")
    task = tasks["tasks"][args.task_id]
    if args.status not in TASK_TRANSITIONS[task["status"]]:
        raise DashboardError("Transizione task non ammessa")
    expected = f"CONFERMO TASK {args.task_id} {args.status}"
    if args.confirmation != expected:
        raise DashboardError("Conferma task non valida")
    task["status"] = args.status
    task["updated_at"] = now_iso()
    atomic_json(task_path(root), tasks, replace=True)
    state["updated_at"] = now_iso()
    state["tasks_sha256"] = digest_file(task_path(root))
    state["stale"] = True
    atomic_json(state_path(root), state, replace=True)
    append_event(root, "TASK_UPDATED", f"task_id={args.task_id}; status={args.status}")
    print(f"GF-AOS studio task: {args.task_id} {args.status}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    root = directory(args.dashboard)
    state = load_state(root)
    tasks = assert_tasks_integrity(root, state)
    print("# GF-AOS Studio Status\n")
    print(f"- Studio: `{state['studio_ref']}`")
    print(f"- Dashboard disponibile: {'si' if dashboard_path(root).is_file() else 'no'}")
    print(f"- Dashboard da rigenerare: {'si' if state['stale'] else 'no'}")
    counts = Counter(item["status"] for item in tasks["tasks"].values())
    print(f"- Task aperti: {counts['OPEN'] + counts['IN_PROGRESS'] + counts['WAITING']}")
    print(f"- Task completati: {counts['DONE']}")
    print("- Nessuna azione esterna eseguita.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Governed Studio Dashboard")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("dashboard")
    init.add_argument("--studio-ref", required=True)
    init.set_defaults(func=command_init)
    build = sub.add_parser("build")
    build.add_argument("dashboard")
    build.add_argument("--manifest", required=True)
    build.add_argument("--as-of", required=True)
    build.add_argument("--horizon-days", type=int, default=30)
    build.add_argument("--replace", action="store_true")
    build.add_argument("--confirmation")
    build.set_defaults(func=command_build)
    verify = sub.add_parser("verify")
    verify.add_argument("dashboard")
    verify.add_argument("--manifest", required=True)
    verify.set_defaults(func=command_verify)
    task_add = sub.add_parser("task-add")
    task_add.add_argument("dashboard")
    task_add.add_argument("--workspace-ref", required=True)
    task_add.add_argument("--task-code", required=True)
    task_add.add_argument("--owner-ref", required=True)
    task_add.add_argument("--priority", choices=tuple(sorted(TASK_PRIORITIES)), default="normal")
    task_add.add_argument("--due-date")
    task_add.set_defaults(func=command_task_add)
    task_update = sub.add_parser("task-update")
    task_update.add_argument("dashboard")
    task_update.add_argument("--task-id", required=True)
    task_update.add_argument("--status", choices=tuple(sorted(TASK_STATUSES - {"OPEN"})), required=True)
    task_update.add_argument("--confirmation", required=True)
    task_update.set_defaults(func=command_task_update)
    status = sub.add_parser("status")
    status.add_argument("dashboard")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (DashboardError, lifecycle.LifecycleError, deadline_engine.DeadlineError,
            action_engine.ActionError, remote_engine.RemoteDossierError,
            OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("ERRORE: operazione dashboard non completata", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
