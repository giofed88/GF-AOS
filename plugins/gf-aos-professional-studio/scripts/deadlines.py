#!/usr/bin/env python3
"""Motore governato di scadenze e promemoria GF-AOS.

Non determina autonomamente termini normativi, non invia notifiche e non crea eventi live.
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
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from context_curator import injection_flags
from privacy_guard import (
    GuardError,
    MAX_SCAN_BYTES,
    SECRET_PATTERNS,
    content_set_digest,
    digest_file,
    inside,
    scan_findings,
    workspace,
)


SCHEMA_VERSION = 1
ROME = ZoneInfo("Europe/Rome")
DEADLINE_ID_RE = re.compile(r"^DL-[0-9]{8}-[A-F0-9]{8}$")
REMINDER_ID_RE = re.compile(r"^RM-[0-9]{8}-[A-F0-9]{8}$")
ALIAS_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{1,63}$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
ALLOWED_CATEGORIES = {
    "fiscal", "labour", "audit", "governance", "litigation", "corporate",
    "incentives", "internal", "training", "editorial",
}
ALLOWED_CHANNELS = {"calendar", "telegram-self"}
DEADLINE_STATUSES = {"DRAFT_REVIEW_REQUIRED", "VALIDATED", "COMPLETED_BY_USER"}
REQUIRED_SECTIONS = ("Fonte", "Regola", "Applicabilita", "Data verificata")
MAX_NOTE_BYTES = 64 * 1024
VALIDATION_FIELDS = (
    "deadline_id", "subject_ref", "obligation_code", "category", "due_at", "timezone",
    "reminder_days", "source_note", "source_note_sha256", "privacy_report",
    "privacy_report_sha256", "privacy_result",
)


class DeadlineError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha_text(encoded)


def atomic_text(path: Path, content: str, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise DeadlineError("Artefatto governato gia esistente")
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


def secure_directory(root: Path, relative: str, *, create: bool) -> Path:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise DeadlineError("Directory governata non valida")
        if not current.exists():
            if not create:
                raise DeadlineError("Directory governata assente")
            current.mkdir()
    resolved = current.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise DeadlineError("Directory governata fuori dal workspace") from exc
    return resolved


def validate_alias(value: str, state: dict[str, Any], label: str) -> str:
    if not ALIAS_RE.fullmatch(value):
        raise DeadlineError(f"{label} deve essere un alias non identificativo")
    if scan_findings(value, state) or injection_flags(value):
        raise DeadlineError(f"{label} contiene dati o istruzioni non ammessi")
    return value


def parse_due_at(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DeadlineError("Termine non valido") from exc
    if parsed.tzinfo is None:
        raise DeadlineError("Il termine deve includere l'offset UTC")
    local = parsed.astimezone(ROME).replace(microsecond=0)
    if parsed.utcoffset() != local.utcoffset():
        raise DeadlineError("Il termine deve usare l'offset Europe/Rome applicabile alla data")
    return local


def parse_day(raw: str, label: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise DeadlineError(f"{label} non valida") from exc


def normalize_reminders(values: list[int]) -> list[int]:
    if not values:
        values = [30, 7, 1, 0]
    if len(values) > 12 or any(value < 0 or value > 365 for value in values):
        raise DeadlineError("I reminder devono essere da 0 a 365 giorni, massimo dodici")
    return sorted(set(values), reverse=True)


def deterministic_findings(path: Path, state: dict[str, Any]) -> tuple[int, int, int]:
    text = path.read_text(encoding="utf-8")
    totals: Counter[str] = Counter()
    for line in text.splitlines():
        totals.update(scan_findings(line, state))
    for category in injection_flags(text):
        totals[category] += 1
    secrets = sum(totals[name] for name, _ in SECRET_PATTERNS)
    injections = sum(
        totals[name]
        for name in ("IGNORE_INSTRUCTIONS", "SYSTEM_PROMPT", "SECRET_EXFILTRATION", "ROLE_OVERRIDE")
    )
    personal = sum(totals.values()) - secrets - injections
    return personal, secrets, injections


def privacy_report_path(root: Path, raw: str) -> Path:
    path = inside(root, raw)
    relative = path.relative_to(root)
    allowed = relative.as_posix() == "PRIVACY_REPORT.md" or (
        len(relative.parts) >= 2
        and relative.parts[0] == "privacy-reports"
        and path.name.endswith(".privacy.md")
    )
    if not allowed:
        raise DeadlineError("Report privacy fuori dal percorso dedicato")
    return path


def validate_privacy(note: Path, report: Path, state: dict[str, Any]) -> str:
    text = report.read_text(encoding="utf-8")
    patterns = {
        "result": r"^- Esito: \*\*(PASS|WARN|BLOCKED|REVIEW_REQUIRED)\*\*$",
        "profile": r"^- Profilo: `([^`]+)`$",
        "content": r"^- Content set SHA-256: `([a-f0-9]{64})`$",
    }
    parsed: dict[str, str] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise DeadlineError("Report privacy incompleto")
        parsed[name] = match.group(1)
    if parsed["profile"] != "internal" or parsed["content"] != content_set_digest([note]):
        raise DeadlineError("Report privacy non coerente con la nota-fonte")
    personal, secrets, injections = deterministic_findings(note, state)
    if secrets or injections:
        raise DeadlineError("Nota-fonte bloccata dai controlli privacy")
    expected = "WARN" if personal else "PASS"
    if parsed["result"] != expected:
        raise DeadlineError("Esito privacy non coerente con la nota-fonte")
    return expected


def validate_source_note(root: Path, raw: str) -> Path:
    path = inside(root, raw)
    if path.suffix.lower() != ".md" or path.stat().st_size > MAX_SCAN_BYTES:
        raise DeadlineError("La nota-fonte deve essere Markdown e non superare 2 MiB")
    text = path.read_text(encoding="utf-8")
    matches = list(re.finditer(r"^##[ \t]+([^\r\n]+?)[ \t]*$", text, re.MULTILINE))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        name = match.group(1)
        if name not in REQUIRED_SECTIONS or name in sections:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[name] = text[match.end():end].strip()
    if set(sections) != set(REQUIRED_SECTIONS) or any(len(sections[name]) < 4 for name in REQUIRED_SECTIONS):
        raise DeadlineError("Nota-fonte incompleta")
    return path


def registry_path(root: Path) -> Path:
    path = root / "DEADLINES.json"
    if path.is_symlink():
        raise DeadlineError("Registro scadenze non valido")
    return path


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "deadlines": {}}
    if not path.is_file() or path.is_symlink():
        raise DeadlineError("Registro scadenze non valido")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeadlineError("Registro scadenze non valido") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION or not isinstance(value.get("deadlines"), dict):
        raise DeadlineError("Registro scadenze non valido")
    for deadline_id, item in value["deadlines"].items():
        if (
            not DEADLINE_ID_RE.fullmatch(str(deadline_id))
            or not isinstance(item, dict)
            or item.get("status") not in DEADLINE_STATUSES
            or item.get("category") not in ALLOWED_CATEGORIES
            or not HASH_RE.fullmatch(str(item.get("record_sha256", "")))
        ):
            raise DeadlineError("Registro scadenze non valido")
    return value


def record_sha(record: dict[str, Any]) -> str:
    return canonical_digest(record)


def validation_digest(record: dict[str, Any]) -> str:
    return canonical_digest({field: record.get(field) for field in VALIDATION_FIELDS})


def note_digest(raw: str, label: str, minimum: int) -> str:
    path = Path(raw).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_NOTE_BYTES:
        raise DeadlineError(f"{label} non valida")
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < minimum:
        raise DeadlineError(f"{label} troppo breve")
    return sha_text(text)


def command_propose(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    subject_ref = validate_alias(args.subject_ref, state, "subject_ref")
    obligation_code = validate_alias(args.obligation_code, state, "obligation_code")
    due = parse_due_at(args.due_at)
    reminders = normalize_reminders(args.reminder_days)
    source_note = validate_source_note(root, args.source_note)
    report = privacy_report_path(root, args.privacy_report)
    privacy_result = validate_privacy(source_note, report, state)
    deadline_id = f"DL-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    deadlines_dir = secure_directory(root, "deadlines/records", create=True)
    sources_dir = secure_directory(root, "deadlines/sources", create=True)
    reports_dir = secure_directory(root, "deadlines/reports", create=True)
    controlled_source = sources_dir / f"{deadline_id}.source.md"
    controlled_report = reports_dir / f"{deadline_id}.privacy.md"
    atomic_text(controlled_source, source_note.read_text(encoding="utf-8"), replace=False)
    atomic_text(controlled_report, report.read_text(encoding="utf-8"), replace=False)
    created_at = now_iso()
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "deadline_id": deadline_id,
        "subject_ref": subject_ref,
        "obligation_code": obligation_code,
        "category": args.category,
        "due_at": due.isoformat(),
        "timezone": "Europe/Rome",
        "reminder_days": reminders,
        "source_note": controlled_source.relative_to(root).as_posix(),
        "source_note_sha256": digest_file(controlled_source),
        "privacy_report": controlled_report.relative_to(root).as_posix(),
        "privacy_report_sha256": digest_file(controlled_report),
        "privacy_result": privacy_result,
        "status": "DRAFT_REVIEW_REQUIRED",
        "created_at": created_at,
        "validation": None,
        "completion": None,
    }
    record_path = deadlines_dir / f"{deadline_id}.json"
    registry_file = registry_path(root)
    registry = load_registry(registry_file)
    atomic_json(record_path, record, replace=False)
    registry["deadlines"][deadline_id] = {
        "status": record["status"],
        "category": record["category"],
        "due_at": record["due_at"],
        "record_sha256": record_sha(record),
        "created_at": created_at,
    }
    atomic_json(registry_file, registry, replace=registry_file.exists())
    print(f"GF-AOS deadline: {deadline_id} DRAFT_REVIEW_REQUIRED")
    return 2


def current_record(root: Path, state: dict[str, Any], deadline_id: str) -> tuple[dict[str, Any], Path, Path, Path, dict[str, Any]]:
    if not DEADLINE_ID_RE.fullmatch(deadline_id):
        raise DeadlineError("Deadline ID non valido")
    record_path = secure_directory(root, "deadlines/records", create=False) / f"{deadline_id}.json"
    if not record_path.is_file() or record_path.is_symlink():
        raise DeadlineError("Scadenza non trovata")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeadlineError("Scadenza non valida") from exc
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("deadline_id") != deadline_id
        or record.get("category") not in ALLOWED_CATEGORIES
        or record.get("status") not in DEADLINE_STATUSES
        or record.get("timezone") != "Europe/Rome"
    ):
        raise DeadlineError("Scadenza non valida")
    validate_alias(str(record.get("subject_ref", "")), state, "subject_ref")
    validate_alias(str(record.get("obligation_code", "")), state, "obligation_code")
    if parse_due_at(str(record.get("due_at", ""))).isoformat() != record.get("due_at"):
        raise DeadlineError("Termine non canonico")
    if normalize_reminders(list(record.get("reminder_days", []))) != record.get("reminder_days"):
        raise DeadlineError("Reminder non validi")
    source = inside(root, str(record.get("source_note", "")))
    report = inside(root, str(record.get("privacy_report", "")))
    if digest_file(source) != record.get("source_note_sha256") or digest_file(report) != record.get("privacy_report_sha256"):
        raise DeadlineError("Nota-fonte o report modificati")
    if validate_privacy(source, report, state) != record.get("privacy_result"):
        raise DeadlineError("Privacy non coerente")
    registry_file = registry_path(root)
    registry = load_registry(registry_file)
    indexed = registry["deadlines"].get(deadline_id)
    if (
        not isinstance(indexed, dict)
        or indexed.get("status") != record.get("status")
        or indexed.get("category") != record.get("category")
        or indexed.get("due_at") != record.get("due_at")
        or indexed.get("record_sha256") != record_sha(record)
    ):
        raise DeadlineError("Registro scadenze incoerente")
    return record, record_path, source, report, registry


def validate_approval(record: dict[str, Any]) -> None:
    approval = record.get("validation")
    if (
        not isinstance(approval, dict)
        or not HASH_RE.fullmatch(str(approval.get("note_sha256", "")))
        or approval.get("approved_deadline_sha256") != validation_digest(record)
        or not isinstance(approval.get("validated_at"), str)
    ):
        raise DeadlineError("Validazione professionale non coerente")


def command_validate(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    record, record_path, _, _, registry = current_record(root, state, args.deadline_id)
    if record["status"] != "DRAFT_REVIEW_REQUIRED":
        raise DeadlineError("Scadenza non validabile nello stato corrente")
    if args.confirmation != f"CONFERMO SCADENZA {args.deadline_id}":
        raise DeadlineError("Conferma della scadenza non valida")
    record["validation"] = {
        "validated_at": now_iso(),
        "note_sha256": note_digest(args.note_file, "Nota di validazione", 15),
        "approved_deadline_sha256": validation_digest(record),
    }
    record["status"] = "VALIDATED"
    registry["deadlines"][args.deadline_id]["status"] = record["status"]
    registry["deadlines"][args.deadline_id]["record_sha256"] = record_sha(record)
    atomic_json(record_path, record, replace=True)
    atomic_json(registry_path(root), registry, replace=True)
    print(f"GF-AOS deadline: {args.deadline_id} VALIDATED")
    return 0


def assert_verified(root: Path, state: dict[str, Any], deadline_id: str) -> dict[str, Any]:
    record, _, _, _, _ = current_record(root, state, deadline_id)
    if record["status"] in {"VALIDATED", "COMPLETED_BY_USER"}:
        validate_approval(record)
    if record["status"] == "COMPLETED_BY_USER":
        completion = record.get("completion")
        if (
            not isinstance(completion, dict)
            or not HASH_RE.fullmatch(str(completion.get("note_sha256", "")))
            or not isinstance(completion.get("completed_at"), str)
            or completion.get("filing_receipt_verified") is not False
        ):
            raise DeadlineError("Completamento non coerente")
    return record


def command_verify(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    try:
        record = assert_verified(root, state, args.deadline_id)
    except (DeadlineError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print(f"GF-AOS deadline: {args.deadline_id} BLOCKED")
        return 2
    print(f"GF-AOS deadline: {args.deadline_id} {record['status']}")
    return 0 if record["status"] != "DRAFT_REVIEW_REQUIRED" else 2


def reminder_id(deadline_id: str, scheduled_for: date, channel: str) -> str:
    suffix = sha_text(f"{deadline_id}|{scheduled_for.isoformat()}|{channel}")[:8].upper()
    return f"RM-{scheduled_for:%Y%m%d}-{suffix}"


def reminder_payload(record: dict[str, Any], reminder: str, scheduled_for: date) -> str:
    return (
        "# GF-AOS Promemoria — BOZZA DA AUTORIZZARE\n\n"
        f"- Reminder ID: `{reminder}`\n"
        f"- Deadline ID: `{record['deadline_id']}`\n"
        f"- Soggetto: `{record['subject_ref']}`\n"
        f"- Adempimento: `{record['obligation_code']}`\n"
        f"- Categoria: `{record['category']}`\n"
        f"- Termine Europe/Rome: `{record['due_at']}`\n"
        f"- Data programmata: `{scheduled_for.isoformat()}`\n"
        "- Stato: promemoria locale non inviato.\n"
    )


def load_reminder(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeadlineError("Promemoria esistente non valido") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise DeadlineError("Promemoria esistente non valido")
    return value


def command_queue(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    start = parse_day(args.as_of, "Data as-of")
    if args.horizon_days < 0 or args.horizon_days > 365:
        raise DeadlineError("Orizzonte non valido")
    end = start + timedelta(days=args.horizon_days)
    registry = load_registry(registry_path(root))
    outbox = secure_directory(root, "deadline-reminders/outbox", create=True)
    payloads = secure_directory(root, "deadline-reminders/payloads", create=True)
    created = 0
    existing = 0
    for deadline_id in sorted(registry["deadlines"]):
        record = assert_verified(root, state, deadline_id)
        if record["status"] != "VALIDATED":
            continue
        due = parse_due_at(record["due_at"])
        for days in record["reminder_days"]:
            scheduled_for = due.date() - timedelta(days=days)
            if not start <= scheduled_for <= end:
                continue
            rid = reminder_id(deadline_id, scheduled_for, args.channel)
            request_path = outbox / f"{rid}.json"
            payload_path = payloads / f"{rid}.md"
            payload = reminder_payload(record, rid, scheduled_for)
            request = {
                "schema_version": SCHEMA_VERSION,
                "reminder_id": rid,
                "deadline_id": deadline_id,
                "subject_ref": record["subject_ref"],
                "obligation_code": record["obligation_code"],
                "channel": args.channel,
                "scheduled_for": scheduled_for.isoformat(),
                "due_at": record["due_at"],
                "status": "BOZZA PROMEMORIA",
                "payload": payload_path.relative_to(root).as_posix(),
                "payload_sha256": sha_text(payload),
                "requires_external_action_gate": True,
                "delivery_claimed": False,
                "created_at": now_iso(),
            }
            if request_path.exists() or payload_path.exists():
                if not request_path.is_file() or request_path.is_symlink() or not payload_path.is_file() or payload_path.is_symlink():
                    raise DeadlineError("Promemoria esistente non valido")
                old = load_reminder(request_path)
                if any(old.get(field) != request.get(field) for field in request if field != "created_at") or digest_file(payload_path) != request["payload_sha256"]:
                    raise DeadlineError("Promemoria esistente incoerente")
                existing += 1
                continue
            atomic_text(payload_path, payload, replace=False)
            atomic_json(request_path, request, replace=False)
            created += 1
    queue_state = (
        "READY_FOR_EXTERNAL_ACTION_PREPARATION"
        if created + existing > 0
        else "EMPTY_NO_EXTERNAL_ACTION"
    )
    print(f"GF-AOS reminder queue: created={created} existing={existing} {queue_state}")
    return 0


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def command_agenda(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    start = parse_day(args.from_date, "Data iniziale")
    if args.days < 1 or args.days > 366:
        raise DeadlineError("Intervallo agenda non valido")
    end = start + timedelta(days=args.days - 1)
    output = root / "DEADLINE_AGENDA.md"
    if output.exists() and not args.replace:
        raise DeadlineError("Agenda esistente: usare --replace per il solo report derivato")
    registry = load_registry(registry_path(root))
    rows: list[tuple[datetime, dict[str, Any], str]] = []
    for deadline_id in registry["deadlines"]:
        record = assert_verified(root, state, deadline_id)
        if record["status"] == "DRAFT_REVIEW_REQUIRED":
            continue
        due = parse_due_at(record["due_at"])
        if start <= due.date() <= end or (due.date() < start and record["status"] == "VALIDATED"):
            timing = "SCADUTA" if due.date() < start and record["status"] == "VALIDATED" else "IN FINESTRA"
            rows.append((due, record, timing))
    rows.sort(key=lambda item: (item[0], item[1]["deadline_id"]))
    lines = [
        "# GF-AOS Agenda scadenze — BOZZA OPERATIVA",
        "",
        f"- Finestra: `{start.isoformat()}` / `{end.isoformat()}`",
        f"- Generata UTC: {now_iso()}",
        "- Nessun evento o promemoria e stato inviato.",
        "",
        "| Deadline ID | Soggetto alias | Adempimento | Categoria | Termine Europe/Rome | Stato | Timing |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for due, record, timing in rows:
        lines.append(
            f"| `{record['deadline_id']}` | `{markdown_cell(record['subject_ref'])}` | "
            f"`{markdown_cell(record['obligation_code'])}` | `{record['category']}` | "
            f"`{due.isoformat()}` | `{record['status']}` | `{timing}` |"
        )
    if not rows:
        lines.append("| — | — | — | — | — | — | — |")
    atomic_text(output, "\n".join(lines) + "\n", replace=output.exists())
    print(f"GF-AOS deadline agenda: rows={len(rows)}")
    return 0


def command_complete(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    record, record_path, _, _, registry = current_record(root, state, args.deadline_id)
    if record["status"] != "VALIDATED":
        raise DeadlineError("Scadenza non completabile nello stato corrente")
    validate_approval(record)
    if args.confirmation != f"CONFERMO ADEMPIMENTO {args.deadline_id}":
        raise DeadlineError("Conferma adempimento non valida")
    record["completion"] = {
        "completed_at": now_iso(),
        "note_sha256": note_digest(args.note_file, "Nota di completamento", 15),
        "filing_receipt_verified": False,
    }
    record["status"] = "COMPLETED_BY_USER"
    registry["deadlines"][args.deadline_id]["status"] = record["status"]
    registry["deadlines"][args.deadline_id]["record_sha256"] = record_sha(record)
    atomic_json(record_path, record, replace=True)
    atomic_json(registry_path(root), registry, replace=True)
    print(f"GF-AOS deadline: {args.deadline_id} COMPLETED_BY_USER")
    return 0


def command_status(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    registry = load_registry(registry_path(root))
    print("# GF-AOS Deadline Register\n")
    print("| Deadline ID | Categoria | Stato live |")
    print("| --- | --- | --- |")
    for deadline_id, indexed in sorted(registry["deadlines"].items()):
        live = str(indexed["status"])
        try:
            assert_verified(root, state, deadline_id)
        except (DeadlineError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
            live = "BLOCKED_LIVE"
        print(f"| `{deadline_id}` | `{indexed['category']}` | `{live}` |")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Governed Deadline and Reminder Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    propose = sub.add_parser("propose")
    propose.add_argument("workspace")
    propose.add_argument("--subject-ref", required=True)
    propose.add_argument("--obligation-code", required=True)
    propose.add_argument("--category", choices=tuple(sorted(ALLOWED_CATEGORIES)), required=True)
    propose.add_argument("--due-at", required=True)
    propose.add_argument("--source-note", required=True)
    propose.add_argument("--privacy-report", default="PRIVACY_REPORT.md")
    propose.add_argument("--reminder-days", action="append", type=int, default=[])
    propose.set_defaults(func=command_propose)
    validate = sub.add_parser("validate")
    validate.add_argument("workspace")
    validate.add_argument("--deadline-id", required=True)
    validate.add_argument("--note-file", required=True)
    validate.add_argument("--confirmation", required=True)
    validate.set_defaults(func=command_validate)
    verify = sub.add_parser("verify")
    verify.add_argument("workspace")
    verify.add_argument("--deadline-id", required=True)
    verify.set_defaults(func=command_verify)
    queue = sub.add_parser("queue")
    queue.add_argument("workspace")
    queue.add_argument("--as-of", required=True)
    queue.add_argument("--horizon-days", type=int, default=30)
    queue.add_argument("--channel", choices=tuple(sorted(ALLOWED_CHANNELS)), required=True)
    queue.set_defaults(func=command_queue)
    agenda = sub.add_parser("agenda")
    agenda.add_argument("workspace")
    agenda.add_argument("--from-date", required=True)
    agenda.add_argument("--days", type=int, default=30)
    agenda.add_argument("--replace", action="store_true")
    agenda.set_defaults(func=command_agenda)
    complete = sub.add_parser("complete")
    complete.add_argument("workspace")
    complete.add_argument("--deadline-id", required=True)
    complete.add_argument("--note-file", required=True)
    complete.add_argument("--confirmation", required=True)
    complete.set_defaults(func=command_complete)
    status = sub.add_parser("status")
    status.add_argument("workspace")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (DeadlineError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("ERRORE: operazione scadenza non completata", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
