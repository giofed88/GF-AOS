#!/usr/bin/env python3
"""Ponte governato tra workspace GF-AOS e fascicoli remoti.

Il programma valida snapshot prodotti da un connettore autorizzato e prepara richieste
di sola lettura o di modifica. Non chiama API, non contiene credenziali e non modifica
mai il provider remoto.
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
ALLOWED_PROVIDERS = {"google-drive", "onedrive", "sharepoint"}
ALIAS_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{1,63}$")
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
CHANGE_ID_RE = re.compile(r"^RC-[0-9]{8}-[A-F0-9]{8}$")
READ_ID_RE = re.compile(r"^RR-[0-9]{8}-[A-F0-9]{8}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
MIME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$")
ALLOWED_KINDS = {"file", "folder", "shortcut"}
ALLOWED_OPERATIONS = {"rename", "move", "metadata-update", "replace", "delete"}
IRREVERSIBLE_OPERATIONS = {"replace", "delete"}
MAX_ITEMS = 5000
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_NOTE_BYTES = 32 * 1024
MAX_IMPORT_BYTES = 100 * 1024 * 1024
ALLOWED_IMPORT_SUFFIXES = {
    ".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".txt", ".md", ".csv",
    ".png", ".jpg", ".jpeg", ".tif", ".tiff",
}
SOURCE_CONFIRMATION = "AUTORIZZO MODIFICA SORGENTI"
CHANGE_DIGEST_FIELDS = (
    "change_id",
    "provider",
    "source_ref",
    "object_ref",
    "target_ref",
    "operation",
    "baseline_sha256",
    "current_state_sha256",
    "expected_revision_sha256",
    "preview",
    "preview_sha256",
    "privacy_report",
    "privacy_report_sha256",
    "privacy_result",
    "irreversible",
)


class RemoteDossierError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return digest_bytes(encoded.encode("utf-8"))


def source_state_digest(manifest: dict[str, Any]) -> str:
    return canonical_digest(
        {
            "provider": manifest["provider"],
            "source_ref": manifest["source_ref"],
            "items": manifest["items"],
        }
    )


def atomic_text(path: Path, content: str, *, replace: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not replace:
        raise RemoteDossierError("Artefatto governato gia esistente")
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
            raise RemoteDossierError("Directory governata non valida")
        if not current.exists():
            if not create:
                raise RemoteDossierError("Directory governata assente")
            current.mkdir()
    resolved = current.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RemoteDossierError("Directory governata fuori dal workspace") from exc
    return resolved


def external_json(raw: str, label: str) -> tuple[Path, dict[str, Any]]:
    path = Path(raw).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_MANIFEST_BYTES:
        raise RemoteDossierError(f"{label} non valido")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteDossierError(f"{label} non valido") from exc
    if not isinstance(value, dict):
        raise RemoteDossierError(f"{label} non valido")
    return path.resolve(), value


def validate_alias(value: object, label: str) -> str:
    alias = str(value)
    if not ALIAS_RE.fullmatch(alias):
        raise RemoteDossierError(f"{label} deve essere un alias pseudonimizzato")
    return alias


def valid_timestamp(value: str) -> bool:
    if not ISO_RE.fullmatch(value):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    provider = str(value.get("provider", ""))
    if value.get("schema_version") != SCHEMA_VERSION or provider not in ALLOWED_PROVIDERS:
        raise RemoteDossierError("Manifest remoto non supportato")
    source_ref = validate_alias(value.get("source_ref"), "source_ref")
    captured_at = str(value.get("captured_at", ""))
    if not valid_timestamp(captured_at):
        raise RemoteDossierError("Timestamp del manifest non valido")
    items = value.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise RemoteDossierError("Numero di oggetti remoti non valido")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict) or set(raw) - {
            "object_ref", "parent_ref", "kind", "mime_type", "modified_at",
            "revision_sha256", "content_sha256", "size",
        }:
            raise RemoteDossierError("Oggetto remoto non valido")
        object_ref = validate_alias(raw.get("object_ref"), "object_ref")
        parent_ref = validate_alias(raw.get("parent_ref"), "parent_ref")
        if object_ref in seen or object_ref == parent_ref:
            raise RemoteDossierError("Riferimenti remoti duplicati o ciclici")
        seen.add(object_ref)
        kind = str(raw.get("kind", ""))
        mime_type = str(raw.get("mime_type", ""))
        modified_at = str(raw.get("modified_at", ""))
        revision = str(raw.get("revision_sha256", ""))
        content = raw.get("content_sha256")
        size = raw.get("size")
        if (
            kind not in ALLOWED_KINDS
            or not MIME_RE.fullmatch(mime_type)
            or not valid_timestamp(modified_at)
            or not HASH_RE.fullmatch(revision)
            or (content is not None and not HASH_RE.fullmatch(str(content)))
            or not isinstance(size, int)
            or size < 0
        ):
            raise RemoteDossierError("Metadati remoti non validi")
        normalized.append(
            {
                "object_ref": object_ref,
                "parent_ref": parent_ref,
                "kind": kind,
                "mime_type": mime_type,
                "modified_at": modified_at,
                "revision_sha256": revision,
                "content_sha256": str(content) if content is not None else None,
                "size": size,
            }
        )
    aliases = {item["object_ref"] for item in normalized}
    parents = {item["object_ref"]: item["parent_ref"] for item in normalized}
    for item in normalized:
        if item["parent_ref"] != "ROOT" and item["parent_ref"] not in aliases:
            raise RemoteDossierError("Parent remoto non risolto")
        visited: set[str] = set()
        cursor = item["object_ref"]
        while cursor != "ROOT":
            if cursor in visited:
                raise RemoteDossierError("Gerarchia remota ciclica")
            visited.add(cursor)
            cursor = parents.get(cursor, "ROOT")
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "source_ref": source_ref,
        "captured_at": captured_at,
        "items": sorted(normalized, key=lambda item: item["object_ref"]),
    }


def load_manifest(raw: str, state: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path, value = external_json(raw, "Manifest remoto")
    manifest = validate_manifest(value)
    aliases = [manifest["source_ref"]]
    aliases.extend(item["object_ref"] for item in manifest["items"])
    aliases.extend(item["parent_ref"] for item in manifest["items"] if item["parent_ref"] != "ROOT")
    alias_text = "\n".join(aliases)
    if scan_findings(alias_text, state) or injection_flags(alias_text):
        raise RemoteDossierError("Il manifest contiene alias non ammessi")
    return path, manifest


def baseline_path(root: Path) -> Path:
    return secure_directory(root, "remote-dossiers", create=True) / "BASELINE.json"


def load_baseline(root: Path) -> dict[str, Any]:
    path = secure_directory(root, "remote-dossiers", create=False) / "BASELINE.json"
    if not path.is_file() or path.is_symlink():
        raise RemoteDossierError("Baseline remota assente")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteDossierError("Baseline remota non valida") from exc
    if not isinstance(value, dict) or not HASH_RE.fullmatch(str(value.get("manifest_sha256", ""))):
        raise RemoteDossierError("Baseline remota non valida")
    manifest = validate_manifest(value.get("manifest", {}))
    if canonical_digest(manifest) != value["manifest_sha256"]:
        raise RemoteDossierError("Baseline remota alterata")
    return value


def diff_manifest(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, list[str]]:
    if (
        baseline["provider"] != current["provider"]
        or baseline["source_ref"] != current["source_ref"]
    ):
        raise RemoteDossierError("Il manifest corrente appartiene a una sorgente diversa")
    old = {item["object_ref"]: item for item in baseline["items"]}
    new = {item["object_ref"]: item for item in current["items"]}
    return {
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "changed": sorted(ref for ref in old.keys() & new.keys() if old[ref] != new[ref]),
    }


def locator(ref: str) -> str:
    return digest_bytes(ref.encode("utf-8"))[:12]


def command_register(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    _, manifest = load_manifest(args.manifest, state)
    output = baseline_path(root)
    index_path = root / "REMOTE_DOSSIER_INDEX.md"
    if (output.exists() or index_path.exists()) and (
        not args.replace or args.confirmation != "SOSTITUISCO BASELINE REMOTA"
    ):
        raise RemoteDossierError(
            "Baseline esistente: sostituire solo con --replace e conferma dedicata"
        )
    value = {
        "schema_version": SCHEMA_VERSION,
        "registered_at": now_iso(),
        "manifest_sha256": canonical_digest(manifest),
        "manifest": manifest,
    }
    atomic_json(output, value, replace=output.exists())
    folders = sum(item["kind"] == "folder" for item in manifest["items"])
    files = len(manifest["items"]) - folders
    index = (
        "# GF-AOS Remote Dossier Index\n\n"
        f"- Provider: `{manifest['provider']}`\n"
        f"- Source ref: `{manifest['source_ref']}`\n"
        f"- Snapshot SHA-256: `{value['manifest_sha256']}`\n"
        f"- Oggetti: {len(manifest['items'])}\n"
        f"- Cartelle: {folders}\n"
        f"- File/shortcut: {files}\n"
        "- Modalita: sola lettura; nessuna API chiamata dal plugin.\n"
    )
    atomic_text(index_path, index, replace=index_path.exists())
    print(f"GF-AOS remote dossier: REGISTERED items={len(manifest['items'])}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    baseline = load_baseline(root)
    _, current = load_manifest(args.manifest, state)
    differences = diff_manifest(baseline["manifest"], current)
    counts = {key: len(value) for key, value in differences.items()}
    status = "PASS" if not any(counts.values()) else "DRIFT"
    lines = [
        "# GF-AOS Remote Source Integrity",
        "",
        f"- Esito: **{status}**",
        f"- Verificato UTC: {now_iso()}",
        f"- Aggiunti: {counts['added']}",
        f"- Rimossi: {counts['removed']}",
        f"- Modificati: {counts['changed']}",
        "",
        "## Locator pseudonimizzati",
        "",
    ]
    for category, refs in differences.items():
        lines.extend(f"- `{locator(ref)}` — {category}" for ref in refs)
    if not any(differences.values()):
        lines.append("- Nessuno.")
    lines.extend(["", "Il report non contiene nomi, URL o identificativi provider.", ""])
    output = root / "REMOTE_SOURCE_INTEGRITY.md"
    atomic_text(output, "\n".join(lines), replace=output.exists())
    print(f"GF-AOS remote dossier: {status}")
    return 0 if status == "PASS" else 2


def request_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def baseline_items(baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["object_ref"]: item for item in baseline["manifest"]["items"]}


def require_current(baseline: dict[str, Any], manifest: dict[str, Any]) -> None:
    if any(diff_manifest(baseline["manifest"], manifest).values()):
        raise RemoteDossierError("La sorgente remota e cambiata rispetto alla baseline")


def command_request_read(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    baseline = load_baseline(root)
    _, current = load_manifest(args.manifest, state)
    require_current(baseline, current)
    refs = list(dict.fromkeys(args.object_ref))
    if not 1 <= len(refs) <= 50:
        raise RemoteDossierError("Selezionare da 1 a 50 oggetti")
    items = baseline_items(baseline)
    selected: list[dict[str, str]] = []
    for raw in refs:
        ref = validate_alias(raw, "object_ref")
        item = items.get(ref)
        if item is None or item["kind"] == "folder":
            raise RemoteDossierError("Oggetto non leggibile o non presente nella baseline")
        selected.append(
            {
                "object_ref": ref,
                "expected_revision_sha256": item["revision_sha256"],
                "expected_content_sha256": item["content_sha256"],
            }
        )
    read_id = request_id("RR")
    outbox = secure_directory(root, "remote-dossiers/outbox", create=True) / f"{read_id}.read.json"
    request = {
        "schema_version": SCHEMA_VERSION,
        "status": "BOZZA RICHIESTA LETTURA",
        "request_id": read_id,
        "provider": baseline["manifest"]["provider"],
        "source_ref": baseline["manifest"]["source_ref"],
        "baseline_sha256": baseline["manifest_sha256"],
        "objects": selected,
        "read_only": True,
        "destination": "remote-imports/inbox",
        "requires_authorized_connector": True,
        "execution_claimed": False,
        "created_at": now_iso(),
    }
    atomic_json(outbox, request, replace=False)
    print(f"GF-AOS remote read: {read_id} READY_FOR_AUTHORIZED_CONNECTOR")
    return 0


def load_read_request(root: Path, read_id: str) -> dict[str, Any]:
    if not READ_ID_RE.fullmatch(read_id):
        raise RemoteDossierError("Request ID non valido")
    path = secure_directory(root, "remote-dossiers/outbox", create=False) / f"{read_id}.read.json"
    if not path.is_file() or path.is_symlink():
        raise RemoteDossierError("Richiesta di lettura non trovata")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteDossierError("Richiesta di lettura non valida") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != SCHEMA_VERSION
        or value.get("request_id") != read_id
        or value.get("provider") not in ALLOWED_PROVIDERS
        or value.get("status") != "BOZZA RICHIESTA LETTURA"
        or value.get("read_only") is not True
        or value.get("execution_claimed") is not False
        or value.get("destination") != "remote-imports/inbox"
        or not isinstance(value.get("objects"), list)
    ):
        raise RemoteDossierError("Richiesta di lettura non valida")
    return value


def command_verify_import(args: argparse.Namespace) -> int:
    root, _ = workspace(args.workspace)
    baseline = load_baseline(root)
    request = load_read_request(root, args.request_id)
    if (
        request.get("baseline_sha256") != baseline["manifest_sha256"]
        or request.get("source_ref") != baseline["manifest"]["source_ref"]
        or request.get("provider") != baseline["manifest"]["provider"]
    ):
        raise RemoteDossierError("Richiesta di lettura non coerente con la baseline")
    object_ref = validate_alias(args.object_ref, "object_ref")
    selected = [item for item in request["objects"] if isinstance(item, dict) and item.get("object_ref") == object_ref]
    if len(selected) != 1:
        raise RemoteDossierError("Oggetto non presente nella richiesta di lettura")
    item = selected[0]
    if not HASH_RE.fullmatch(str(item.get("expected_revision_sha256", ""))):
        raise RemoteDossierError("Revisione attesa non valida")
    expected_content = item.get("expected_content_sha256")
    if expected_content is not None and not HASH_RE.fullmatch(str(expected_content)):
        raise RemoteDossierError("Hash contenuto atteso non valido")
    baseline_item = baseline_items(baseline).get(object_ref)
    if (
        baseline_item is None
        or baseline_item["kind"] == "folder"
        or item["expected_revision_sha256"] != baseline_item["revision_sha256"]
        or expected_content != baseline_item["content_sha256"]
    ):
        raise RemoteDossierError("Oggetto richiesto non coerente con la baseline")
    imported = inside(root, args.file)
    relative = imported.relative_to(root)
    if (
        len(relative.parts) != 3
        or relative.parts[:2] != ("remote-imports", "inbox")
        or imported.suffix.lower() not in ALLOWED_IMPORT_SUFFIXES
        or imported.stem != object_ref
        or imported.stat().st_size > MAX_IMPORT_BYTES
    ):
        raise RemoteDossierError("File importato fuori dall'inbox o non pseudonimizzato")
    actual = digest_file(imported)
    status = "VERIFIED_READ_ONLY_IMPORT" if expected_content == actual else "REVIEW_REQUIRED"
    receipts = secure_directory(root, "remote-dossiers/receipts", create=True)
    receipt = receipts / f"{args.request_id}.{object_ref}.json"
    value = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "request_id": args.request_id,
        "object_ref": object_ref,
        "expected_revision_sha256": item["expected_revision_sha256"],
        "expected_content_sha256": expected_content,
        "imported_content_sha256": actual,
        "read_only": True,
        "verified_at": now_iso(),
    }
    atomic_json(receipt, value, replace=False)
    print(f"GF-AOS remote import: {args.request_id} {status}")
    return 0 if status == "VERIFIED_READ_ONLY_IMPORT" else 2


def parse_privacy_report(path: Path, preview: Path, state: dict[str, Any]) -> str:
    text = path.read_text(encoding="utf-8")
    fields = {
        "result": r"^- Esito: \*\*(PASS|WARN|BLOCKED|REVIEW_REQUIRED)\*\*$",
        "profile": r"^- Profilo: `([^`]+)`$",
        "content": r"^- Content set SHA-256: `([a-f0-9]{64})`$",
    }
    parsed: dict[str, str] = {}
    for name, pattern in fields.items():
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise RemoteDossierError("Report privacy incompleto")
        parsed[name] = match.group(1)
    if parsed["profile"] != "internal" or parsed["content"] != content_set_digest([preview]):
        raise RemoteDossierError("Report privacy non coerente con l'anteprima")
    preview_text = preview.read_text(encoding="utf-8")
    findings = scan_findings(preview_text, state)
    secrets = sum(findings[name] for name, _ in SECRET_PATTERNS)
    if secrets or injection_flags(preview_text) or parsed["result"] not in {"PASS", "WARN"}:
        raise RemoteDossierError("Anteprima bloccata dai controlli privacy")
    expected = "WARN" if findings else "PASS"
    if parsed["result"] != expected:
        raise RemoteDossierError("Esito privacy non coerente con l'anteprima")
    return parsed["result"]


def validate_preview(root: Path, raw: str) -> Path:
    preview = inside(root, raw)
    if preview.suffix.lower() not in {".md", ".txt"} or preview.stat().st_size > MAX_SCAN_BYTES:
        raise RemoteDossierError("Anteprima non ammessa")
    text = preview.read_text(encoding="utf-8")
    for heading in ("## Operazione", "## Impatto", "## Rollback", "## Anteprima"):
        if heading not in text:
            raise RemoteDossierError("Anteprima incompleta")
    return preview


def change_paths(root: Path, change_id: str, *, create: bool = False) -> tuple[Path, Path]:
    if not CHANGE_ID_RE.fullmatch(change_id):
        raise RemoteDossierError("Change ID non valido")
    changes = secure_directory(root, "remote-dossiers/changes", create=create)
    outbox = secure_directory(root, "remote-dossiers/outbox", create=create)
    return changes / f"{change_id}.json", outbox / f"{change_id}.change.json"


def note_digest(raw: str) -> str:
    path = Path(raw).expanduser()
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_NOTE_BYTES:
        raise RemoteDossierError("Nota di autorizzazione non valida")
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 15:
        raise RemoteDossierError("Nota di autorizzazione troppo breve")
    return digest_bytes(text.encode("utf-8"))


def change_digest(record: dict[str, Any]) -> str:
    return canonical_digest({field: record.get(field) for field in CHANGE_DIGEST_FIELDS})


def command_prepare_change(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    baseline = load_baseline(root)
    _, current = load_manifest(args.manifest, state)
    require_current(baseline, current)
    object_ref = validate_alias(args.object_ref, "object_ref")
    item = baseline_items(baseline).get(object_ref)
    if item is None:
        raise RemoteDossierError("Oggetto remoto non presente nella baseline")
    target_ref: str | None = None
    if args.operation != "delete":
        if not args.target_ref:
            raise RemoteDossierError("L'operazione richiede un target_ref pseudonimizzato")
        target_ref = validate_alias(args.target_ref, "target_ref")
        if scan_findings(target_ref, state) or injection_flags(target_ref):
            raise RemoteDossierError("target_ref non ammesso")
    elif args.target_ref:
        raise RemoteDossierError("delete non accetta target_ref")
    if args.operation == "move":
        target = baseline_items(baseline).get(str(target_ref))
        if target is None or target["kind"] != "folder" or target_ref == item["parent_ref"]:
            raise RemoteDossierError("La destinazione move deve essere una diversa cartella della baseline")
    preview = validate_preview(root, args.preview)
    report = inside(root, args.privacy_report)
    relative = report.relative_to(root)
    if not (
        relative.as_posix() == "PRIVACY_REPORT.md"
        or (len(relative.parts) >= 2 and relative.parts[0] == "privacy-reports" and report.name.endswith(".privacy.md"))
    ):
        raise RemoteDossierError("Report privacy fuori dal percorso dedicato")
    privacy_result = parse_privacy_report(report, preview, state)
    change_id = request_id("RC")
    record_path, _ = change_paths(root, change_id, create=True)
    preview_dir = secure_directory(root, "remote-dossiers/previews", create=True)
    report_dir = secure_directory(root, "remote-dossiers/reports", create=True)
    controlled_preview = preview_dir / f"{change_id}.preview.md"
    controlled_report = report_dir / f"{change_id}.privacy.md"
    atomic_text(controlled_preview, preview.read_text(encoding="utf-8"), replace=False)
    atomic_text(controlled_report, report.read_text(encoding="utf-8"), replace=False)
    record = {
        "schema_version": SCHEMA_VERSION,
        "change_id": change_id,
        "provider": baseline["manifest"]["provider"],
        "source_ref": baseline["manifest"]["source_ref"],
        "object_ref": object_ref,
        "target_ref": target_ref,
        "operation": args.operation,
        "baseline_sha256": baseline["manifest_sha256"],
        "current_state_sha256": source_state_digest(current),
        "expected_revision_sha256": item["revision_sha256"],
        "preview": controlled_preview.relative_to(root).as_posix(),
        "preview_sha256": digest_file(controlled_preview),
        "privacy_report": controlled_report.relative_to(root).as_posix(),
        "privacy_report_sha256": digest_file(controlled_report),
        "privacy_result": privacy_result,
        "irreversible": args.operation in IRREVERSIBLE_OPERATIONS,
        "status": "PREPARED",
        "created_at": now_iso(),
        "approval": None,
    }
    atomic_json(record_path, record, replace=False)
    print(f"GF-AOS remote change: {change_id} PREPARED")
    return 0


def load_change(root: Path, change_id: str) -> tuple[dict[str, Any], Path, Path, Path, Path]:
    record_path, outbox_path = change_paths(root, change_id)
    if not record_path.is_file() or record_path.is_symlink():
        raise RemoteDossierError("Modifica remota non trovata")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteDossierError("Modifica remota non valida") from exc
    if (
        not isinstance(record, dict)
        or record.get("schema_version") != SCHEMA_VERSION
        or record.get("change_id") != change_id
        or record.get("operation") not in ALLOWED_OPERATIONS
        or record.get("provider") not in ALLOWED_PROVIDERS
        or record.get("irreversible") != (record.get("operation") in IRREVERSIBLE_OPERATIONS)
        or not ALIAS_RE.fullmatch(str(record.get("source_ref", "")))
        or not ALIAS_RE.fullmatch(str(record.get("object_ref", "")))
    ):
        raise RemoteDossierError("Modifica remota non valida")
    target_ref = record.get("target_ref")
    if (record["operation"] == "delete" and target_ref is not None) or (
        record["operation"] != "delete" and not ALIAS_RE.fullmatch(str(target_ref or ""))
    ):
        raise RemoteDossierError("Target della modifica non valido")
    preview = inside(root, str(record.get("preview", "")))
    report = inside(root, str(record.get("privacy_report", "")))
    if digest_file(preview) != record.get("preview_sha256") or digest_file(report) != record.get("privacy_report_sha256"):
        raise RemoteDossierError("Anteprima o report modificati")
    return record, record_path, outbox_path, preview, report


def command_approve_change(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    record, record_path, outbox_path, preview, report = load_change(root, args.change_id)
    baseline = load_baseline(root)
    if (
        record.get("provider") != baseline["manifest"]["provider"]
        or record.get("source_ref") != baseline["manifest"]["source_ref"]
        or record.get("baseline_sha256") != baseline["manifest_sha256"]
    ):
        raise RemoteDossierError("Modifica non coerente con la baseline")
    if record.get("status") != "PREPARED" or args.confirmation != SOURCE_CONFIRMATION:
        raise RemoteDossierError("Gate di modifica sorgenti non valido")
    if record["irreversible"] and args.irreversible_confirmation != f"AUTORIZZO OPERAZIONE IRREVERSIBILE {args.change_id}":
        raise RemoteDossierError("Conferma aggiuntiva richiesta per l'operazione irreversibile")
    privacy_result = parse_privacy_report(report, preview, state)
    if privacy_result != record.get("privacy_result"):
        raise RemoteDossierError("Esito privacy modificato")
    approval = {
        "approved_at": now_iso(),
        "note_sha256": note_digest(args.note_file),
        "approved_change_sha256": change_digest(record),
        "source_confirmation": SOURCE_CONFIRMATION,
        "irreversible_confirmation": bool(record["irreversible"]),
    }
    record["status"] = "APPROVED_FOR_EXTERNAL_EXECUTOR"
    record["approval"] = approval
    request = {
        **{field: record.get(field) for field in CHANGE_DIGEST_FIELDS},
        "schema_version": SCHEMA_VERSION,
        "provider": record["provider"],
        "status": "BOZZA RICHIESTA MODIFICA SORGENTI",
        "approved_at": approval["approved_at"],
        "approved_change_sha256": approval["approved_change_sha256"],
        "requires_external_executor": True,
        "execution_claimed": False,
    }
    atomic_json(outbox_path, request, replace=False)
    atomic_json(record_path, record, replace=True)
    print(f"GF-AOS remote change: {args.change_id} APPROVED_FOR_EXTERNAL_EXECUTOR")
    return 0


def assert_change_ready(root: Path, state: dict[str, Any], change_id: str, manifest_raw: str) -> None:
    baseline = load_baseline(root)
    _, current = load_manifest(manifest_raw, state)
    require_current(baseline, current)
    record, _, outbox_path, preview, report = load_change(root, change_id)
    if record.get("status") != "APPROVED_FOR_EXTERNAL_EXECUTOR" or not outbox_path.is_file() or outbox_path.is_symlink():
        raise RemoteDossierError("Modifica non pronta")
    if (
        record.get("provider") != baseline["manifest"]["provider"]
        or record.get("provider") != current["provider"]
        or record.get("baseline_sha256") != baseline["manifest_sha256"]
        or record.get("current_state_sha256") != source_state_digest(current)
    ):
        raise RemoteDossierError("Baseline o manifest non coerenti")
    item = baseline_items(baseline).get(str(record["object_ref"]))
    if item is None or item["revision_sha256"] != record.get("expected_revision_sha256"):
        raise RemoteDossierError("Revisione remota non coerente")
    privacy_result = parse_privacy_report(report, preview, state)
    if privacy_result != record.get("privacy_result"):
        raise RemoteDossierError("Esito privacy non coerente")
    try:
        request = json.loads(outbox_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RemoteDossierError("Richiesta di modifica non valida") from exc
    approval = record.get("approval")
    if (
        not isinstance(request, dict)
        or request.get("status") != "BOZZA RICHIESTA MODIFICA SORGENTI"
        or request.get("execution_claimed") is not False
        or request.get("requires_external_executor") is not True
        or not isinstance(approval, dict)
        or not HASH_RE.fullmatch(str(approval.get("note_sha256", "")))
        or approval.get("approved_change_sha256") != change_digest(record)
        or request.get("approved_change_sha256") != approval.get("approved_change_sha256")
    ):
        raise RemoteDossierError("Approvazione o richiesta non valida")
    for field in CHANGE_DIGEST_FIELDS:
        if request.get(field) != record.get(field):
            raise RemoteDossierError("Richiesta modificata dopo l'approvazione")


def command_verify_change(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    try:
        assert_change_ready(root, state, args.change_id, args.manifest)
    except (RemoteDossierError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print(f"GF-AOS remote change: {args.change_id} BLOCKED")
        return 2
    print(f"GF-AOS remote change: {args.change_id} READY_FOR_EXTERNAL_EXECUTOR")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Governed Remote Dossier Bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("workspace")
    register.add_argument("--manifest", required=True)
    register.add_argument("--replace", action="store_true")
    register.add_argument("--confirmation")
    register.set_defaults(func=command_register)
    verify = sub.add_parser("verify")
    verify.add_argument("workspace")
    verify.add_argument("--manifest", required=True)
    verify.set_defaults(func=command_verify)
    read = sub.add_parser("request-read")
    read.add_argument("workspace")
    read.add_argument("--manifest", required=True)
    read.add_argument("--object-ref", action="append", required=True)
    read.set_defaults(func=command_request_read)
    imported = sub.add_parser("verify-import")
    imported.add_argument("workspace")
    imported.add_argument("--request-id", required=True)
    imported.add_argument("--object-ref", required=True)
    imported.add_argument("--file", required=True)
    imported.set_defaults(func=command_verify_import)
    prepare = sub.add_parser("prepare-change")
    prepare.add_argument("workspace")
    prepare.add_argument("--manifest", required=True)
    prepare.add_argument("--object-ref", required=True)
    prepare.add_argument("--target-ref")
    prepare.add_argument("--operation", choices=tuple(sorted(ALLOWED_OPERATIONS)), required=True)
    prepare.add_argument("--preview", required=True)
    prepare.add_argument("--privacy-report", default="PRIVACY_REPORT.md")
    prepare.set_defaults(func=command_prepare_change)
    approve = sub.add_parser("approve-change")
    approve.add_argument("workspace")
    approve.add_argument("--change-id", required=True)
    approve.add_argument("--note-file", required=True)
    approve.add_argument("--confirmation", required=True)
    approve.add_argument("--irreversible-confirmation")
    approve.set_defaults(func=command_approve_change)
    check = sub.add_parser("verify-change")
    check.add_argument("workspace")
    check.add_argument("--change-id", required=True)
    check.add_argument("--manifest", required=True)
    check.set_defaults(func=command_verify_change)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (RemoteDossierError, GuardError, OSError, UnicodeError, ValueError, KeyError, TypeError):
        print("ERRORE: operazione sul fascicolo remoto non completata", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
