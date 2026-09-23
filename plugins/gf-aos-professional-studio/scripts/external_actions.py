#!/usr/bin/env python3
"""Coda governata di richieste per azioni esterne GF-AOS.

Lo script non invia, pubblica, deposita, condivide o modifica sistemi esterni.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
ACTION_ID_RE = re.compile(r"^EA-[0-9]{8}-[A-F0-9]{8}$")
TARGET_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{1,63}$")
ALLOWED_SUFFIXES = {".md", ".txt", ".csv", ".json"}
MAX_NOTE_BYTES = 16 * 1024
DATA_CONFIRMATION = "APPROVO DATI NECESSARI"
ACTION_STATUSES = {"PREPARED", "DATA_REVIEW_REQUIRED", "APPROVED_FOR_DISPATCH"}
ACTION_KINDS = {
    "email": "external-draft",
    "pec": "external-draft",
    "telegram-self": "external-draft",
    "calendar": "external-draft",
    "drive-share": "external-draft",
    "linkedin-public": "public",
    "website-public": "public",
}
REQUEST_DIGEST_FIELDS = (
    "action_id", "kind", "target_ref", "payload", "payload_sha256", "privacy_profile",
    "privacy_result", "privacy_report", "privacy_report_sha256",
)


class ActionError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_json(path: Path, value: dict[str, Any], *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise ActionError("Artefatto governato gia esistente")
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActionError(f"{label} non valido") from exc
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise ActionError(f"{label} non valido")
    return value


def action_paths(root: Path, action_id: str, *, create: bool = False) -> tuple[Path, Path, Path]:
    if not ACTION_ID_RE.fullmatch(action_id):
        raise ActionError("Action ID non valido")
    actions_dir = secure_directory(root, "external-actions", create=create)
    outbox_dir = secure_directory(root, "external-actions/outbox", create=create)
    registry_path = root / "EXTERNAL_ACTIONS.json"
    if registry_path.is_symlink():
        raise ActionError("Registro azioni non valido")
    return (
        actions_dir / f"{action_id}.json",
        outbox_dir / f"{action_id}.request.json",
        registry_path,
    )


def secure_directory(root: Path, relative: str, *, create: bool) -> Path:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ActionError("Directory governata non valida")
        if not current.exists():
            if not create:
                raise ActionError("Directory governata assente")
            current.mkdir()
    resolved = current.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ActionError("Directory governata fuori dal workspace") from exc
    return resolved


def report_path(root: Path, raw: str) -> Path:
    path = inside(root, raw)
    relative = path.relative_to(root)
    allowed = relative.as_posix() == "PRIVACY_REPORT.md" or (
        len(relative.parts) >= 2
        and relative.parts[0] == "privacy-reports"
        and path.name.endswith(".privacy.md")
    )
    if not allowed:
        raise ActionError("Usare un report privacy nel percorso dedicato")
    return path


def parse_privacy_report(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    patterns = {
        "result": r"^- Esito: \*\*(PASS|WARN|BLOCKED|REVIEW_REQUIRED)\*\*$",
        "profile": r"^- Profilo: `([^`]+)`$",
        "content_set": r"^- Content set SHA-256: `([a-f0-9]{64})`$",
        "context_review": r"^- Revisione contestuale confermata: (si|no)$",
    }
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise ActionError("Report privacy incompleto o non valido")
        result[key] = match.group(1)
    return result


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


def validate_privacy(
    payload: Path,
    report: Path,
    state: dict[str, Any],
    required_profile: str,
) -> dict[str, str]:
    parsed = parse_privacy_report(report)
    if parsed["profile"] != required_profile:
        raise ActionError("Profilo privacy non coerente con l'azione")
    if parsed["content_set"] != content_set_digest([payload]):
        raise ActionError("Il report privacy non corrisponde alla versione corrente dell'artefatto")
    personal, secrets, injections = deterministic_findings(payload, state)
    if secrets or injections:
        raise ActionError("L'artefatto contiene categorie sempre bloccanti")
    if required_profile == "public":
        if personal or parsed["result"] != "PASS" or parsed["context_review"] != "si":
            raise ActionError("L'azione pubblica richiede PASS e revisione contestuale confermata")
    else:
        expected = "WARN" if personal else "PASS"
        if parsed["result"] != expected:
            raise ActionError("Esito privacy non coerente con l'artefatto")
    return parsed


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "actions": {}}
    if path.is_symlink() or not path.is_file():
        raise ActionError("Registro azioni non valido")
    value = load_json(path, "Registro azioni")
    if not isinstance(value.get("actions"), dict):
        raise ActionError("Registro azioni non valido")
    for action_id, item in value["actions"].items():
        if (
            not ACTION_ID_RE.fullmatch(str(action_id))
            or not isinstance(item, dict)
            or item.get("kind") not in ACTION_KINDS
            or item.get("status") not in ACTION_STATUSES
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("payload_sha256", "")))
        ):
            raise ActionError("Registro azioni non valido")
    return value


def note_digest(raw: str, label: str, minimum: int) -> str:
    path = Path(raw).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_NOTE_BYTES:
        raise ActionError(f"{label} non valida")
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < minimum:
        raise ActionError(f"{label} troppo breve")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved_request_digest(value: dict[str, Any]) -> str:
    canonical = {field: value.get(field) for field in REQUEST_DIGEST_FIELDS}
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def validate_target_ref(value: str, state: dict[str, Any]) -> None:
    if not TARGET_RE.fullmatch(value):
        raise ActionError("Il target deve essere un alias non identificativo, non un indirizzo")
    findings = scan_findings(value, state)
    if findings or injection_flags(value):
        raise ActionError("Il target contiene un identificativo o un contenuto non ammesso")


def command_prepare(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    payload = inside(root, args.payload)
    if payload.suffix.lower() not in ALLOWED_SUFFIXES or payload.stat().st_size > MAX_SCAN_BYTES:
        raise ActionError("Artefatto non ammesso o oltre 2 MiB")
    validate_target_ref(args.target_ref, state)
    profile = ACTION_KINDS[args.kind]
    privacy_report = report_path(root, args.privacy_report)
    privacy = validate_privacy(payload, privacy_report, state, profile)
    action_id = f"EA-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    record_path, _, registry_path = action_paths(root, action_id, create=True)
    status = "DATA_REVIEW_REQUIRED" if privacy["result"] == "WARN" else "PREPARED"
    record = {
        "schema_version": SCHEMA_VERSION,
        "action_id": action_id,
        "kind": args.kind,
        "target_ref": args.target_ref,
        "payload": payload.relative_to(root).as_posix(),
        "payload_sha256": digest_file(payload),
        "privacy_report": privacy_report.relative_to(root).as_posix(),
        "privacy_report_sha256": digest_file(privacy_report),
        "privacy_profile": profile,
        "privacy_result": privacy["result"],
        "status": status,
        "created_at": now_iso(),
        "approval": None,
    }
    registry = load_registry(registry_path)
    registry["actions"][action_id] = {
        "kind": args.kind,
        "status": status,
        "payload_sha256": record["payload_sha256"],
        "created_at": record["created_at"],
    }
    atomic_json(record_path, record, replace=False)
    atomic_json(registry_path, registry, replace=registry_path.exists())
    print(f"GF-AOS external action: {action_id} {status}")
    return 2 if status == "DATA_REVIEW_REQUIRED" else 0


def current_record(root: Path, action_id: str) -> tuple[dict[str, Any], Path, Path, Path, Path, Path]:
    record_path, outbox_path, registry_path = action_paths(root, action_id)
    if (
        not record_path.is_file()
        or record_path.is_symlink()
        or not registry_path.is_file()
        or registry_path.is_symlink()
    ):
        raise ActionError("Azione non trovata")
    record = load_json(record_path, "Azione")
    kind = str(record.get("kind", ""))
    if (
        record.get("action_id") != action_id
        or kind not in ACTION_KINDS
        or record.get("privacy_profile") != ACTION_KINDS[kind]
        or not TARGET_RE.fullmatch(str(record.get("target_ref", "")))
    ):
        raise ActionError("Azione non coerente")
    payload = inside(root, str(record.get("payload", "")))
    if payload.suffix.lower() not in ALLOWED_SUFFIXES or payload.stat().st_size > MAX_SCAN_BYTES:
        raise ActionError("Artefatto non ammesso o oltre 2 MiB")
    privacy_report = report_path(root, str(record.get("privacy_report", "")))
    if digest_file(payload) != record.get("payload_sha256"):
        raise ActionError("Artefatto modificato dopo la preparazione")
    if digest_file(privacy_report) != record.get("privacy_report_sha256"):
        raise ActionError("Report privacy modificato dopo la preparazione")
    registry = load_registry(registry_path)
    indexed = registry["actions"].get(action_id)
    if not isinstance(indexed, dict) or any(
        indexed.get(field) != record.get(field)
        for field in ("kind", "status", "payload_sha256")
    ):
        raise ActionError("Registro azioni incoerente")
    return record, record_path, outbox_path, registry_path, payload, privacy_report


def command_approve(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    record, record_path, outbox_path, registry_path, payload, privacy_report = current_record(root, args.action_id)
    if record.get("status") not in {"PREPARED", "DATA_REVIEW_REQUIRED"}:
        raise ActionError("Azione non approvabile nello stato corrente")
    if args.confirmation != f"APPROVO AZIONE ESTERNA {args.action_id}":
        raise ActionError("Conferma azione esterna non valida")
    approval_note_sha = note_digest(args.note_file, "Nota di approvazione", 10)
    parsed = validate_privacy(payload, privacy_report, state, str(record["privacy_profile"]))
    data_note_sha: str | None = None
    if parsed["result"] == "WARN":
        if args.data_confirmation != DATA_CONFIRMATION or not args.data_note_file:
            raise ActionError(f"Dati necessari non approvati: usare `{DATA_CONFIRMATION}` e una nota")
        data_note_sha = note_digest(args.data_note_file, "Nota dati necessari", 15)
    timestamp = now_iso()
    request_sha = approved_request_digest(record)
    record["status"] = "APPROVED_FOR_DISPATCH"
    record["approval"] = {
        "approved_at": timestamp,
        "note_sha256": approval_note_sha,
        "data_note_sha256": data_note_sha,
        "payload_sha256": record["payload_sha256"],
        "privacy_report_sha256": record["privacy_report_sha256"],
        "approved_request_sha256": request_sha,
    }
    request = {
        "schema_version": SCHEMA_VERSION,
        "status": "BOZZA RICHIESTA DI INVIO",
        "action_id": args.action_id,
        "kind": record["kind"],
        "target_ref": record["target_ref"],
        "payload": record["payload"],
        "payload_sha256": record["payload_sha256"],
        "privacy_profile": record["privacy_profile"],
        "privacy_result": record["privacy_result"],
        "privacy_report": record["privacy_report"],
        "privacy_report_sha256": record["privacy_report_sha256"],
        "approved_at": timestamp,
        "approved_request_sha256": request_sha,
        "requires_external_executor": True,
        "delivery_claimed": False,
    }
    registry = load_registry(registry_path)
    if args.action_id not in registry["actions"]:
        raise ActionError("Registro azioni incoerente")
    registry["actions"][args.action_id]["status"] = record["status"]
    registry["actions"][args.action_id]["approved_at"] = timestamp
    atomic_json(outbox_path, request, replace=False)
    atomic_json(record_path, record, replace=True)
    atomic_json(registry_path, registry, replace=True)
    print(f"GF-AOS external action: {args.action_id} APPROVED_FOR_DISPATCH")
    return 0


def assert_ready(root: Path, state: dict[str, Any], action_id: str) -> None:
    record, _, outbox_path, _, payload, privacy_report = current_record(root, action_id)
    if record.get("status") != "APPROVED_FOR_DISPATCH" or not outbox_path.is_file():
        raise ActionError("Richiesta non pronta")
    if outbox_path.is_symlink():
        raise ActionError("Richiesta di invio non valida")
    request = load_json(outbox_path, "Richiesta di invio")
    if request.get("delivery_claimed") is not False or request.get("status") != "BOZZA RICHIESTA DI INVIO":
        raise ActionError("Richiesta di invio non valida")
    if digest_file(payload) != request.get("payload_sha256"):
        raise ActionError("Artefatto non coerente")
    approval = record.get("approval")
    if (
        not isinstance(approval, dict)
        or not isinstance(approval.get("approved_at"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", str(approval.get("note_sha256", "")))
        or not re.fullmatch(r"[a-f0-9]{64}", str(approval.get("approved_request_sha256", "")))
        or approval.get("payload_sha256") != record.get("payload_sha256")
        or approval.get("privacy_report_sha256") != record.get("privacy_report_sha256")
    ):
        raise ActionError("Approvazione non valida")
    if record.get("privacy_result") == "WARN":
        if not re.fullmatch(r"[a-f0-9]{64}", str(approval.get("data_note_sha256", ""))):
            raise ActionError("Approvazione dati necessaria")
    elif approval.get("data_note_sha256") is not None:
        raise ActionError("Approvazione dati incoerente")
    approved_digest = str(approval["approved_request_sha256"])
    if approved_request_digest(record) != approved_digest:
        raise ActionError("Azione modificata dopo l'approvazione")
    if request.get("approved_request_sha256") != approved_digest or approved_request_digest(request) != approved_digest:
        raise ActionError("Richiesta modificata dopo l'approvazione")
    for field in (
        "action_id", "kind", "target_ref", "payload", "payload_sha256", "privacy_profile",
        "privacy_result", "privacy_report", "privacy_report_sha256", "approved_at",
    ):
        expected = approval["approved_at"] if field == "approved_at" else record.get(field)
        if request.get(field) != expected:
            raise ActionError("Richiesta modificata dopo l'approvazione")
    validate_target_ref(str(record["target_ref"]), state)
    validate_privacy(payload, privacy_report, state, str(record["privacy_profile"]))


def command_verify(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    try:
        assert_ready(root, state, args.action_id)
    except (ActionError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print(f"GF-AOS external action: {args.action_id} BLOCKED")
        return 2
    print(f"GF-AOS external action: {args.action_id} READY_FOR_EXTERNAL_EXECUTOR")
    return 0


def command_status(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    registry_path = root / "EXTERNAL_ACTIONS.json"
    registry = load_registry(registry_path)
    print("# GF-AOS External Action Queue\n")
    print("| Action ID | Tipo | Stato |")
    print("| --- | --- | --- |")
    for action_id, value in sorted(registry["actions"].items()):
        live_status = str(value.get("status", ""))
        if live_status == "APPROVED_FOR_DISPATCH":
            try:
                assert_ready(root, state, action_id)
            except (ActionError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
                live_status = "BLOCKED_LIVE"
        print(f"| `{action_id}` | `{value.get('kind', '')}` | `{live_status}` |")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Governed External Action Queue")
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("workspace")
    prepare.add_argument("--kind", choices=tuple(ACTION_KINDS), required=True)
    prepare.add_argument("--target-ref", required=True)
    prepare.add_argument("--payload", required=True)
    prepare.add_argument("--privacy-report", default="PRIVACY_REPORT.md")
    prepare.set_defaults(func=command_prepare)
    approve = sub.add_parser("approve")
    approve.add_argument("workspace")
    approve.add_argument("--action-id", required=True)
    approve.add_argument("--note-file", required=True)
    approve.add_argument("--confirmation", required=True)
    approve.add_argument("--data-note-file")
    approve.add_argument("--data-confirmation")
    approve.set_defaults(func=command_approve)
    verify = sub.add_parser("verify")
    verify.add_argument("workspace")
    verify.add_argument("--action-id", required=True)
    verify.set_defaults(func=command_verify)
    status = sub.add_parser("status")
    status.add_argument("workspace")
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (ActionError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("ERRORE: azione esterna non completata", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
