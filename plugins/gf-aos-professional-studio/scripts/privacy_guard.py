#!/usr/bin/env python3
"""Privacy-first bootstrap, scansione e controllo integrita per GF-AOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_curator import REDACTIONS, injection_flags


TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json"}
MAX_SCAN_FILES = 20
MAX_SCAN_BYTES = 2 * 1024 * 1024
MAX_SNAPSHOT_FILES = 5000
PRIVACY_CONFIRMATION = "CONFERMO REVISIONE PRIVACY"
BASELINE_CONFIRMATION = "SOSTITUISCO BASELINE"
SECRET_PATTERNS = (
    ("API_TOKEN", re.compile(r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{12,}\b")),
    ("PRIVATE_KEY", re.compile(r"BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY")),
    ("PASSWORD_ASSIGNMENT", re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+", re.I)),
    ("SECRET_ASSIGNMENT", re.compile(r"\b(?:api[_ -]?key|access[_ -]?token|secret|webhook)\s*[:=]\s*\S+", re.I)),
)
MODULE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,39}$")
SAFE_STATUSES = {
    "Da avviare", "In corso", "Completato", "Da validare", "In attesa documenti",
    "Bloccato", "Ignorato consapevolmente", "Approvato",
}


class GuardError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_set_digest(paths: list[Path]) -> str:
    members = sorted(digest_file(path) for path in paths)
    return digest_bytes("".join(f"{item}\n" for item in members).encode("ascii"))


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
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


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def directory(raw: str) -> Path:
    lexical = Path(raw).expanduser()
    if not lexical.is_dir() or lexical.is_symlink():
        raise GuardError("Directory non valida o simbolica")
    return lexical.resolve()


def workspace(raw: str) -> tuple[Path, dict[str, Any]]:
    root = directory(raw)
    state_path = root / "CASE_STATE.json"
    if not state_path.is_file():
        raise GuardError("CASE_STATE.json assente")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError("CASE_STATE.json non valido") from exc
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise GuardError("CASE_STATE.json non valido")
    return root, state


def inside(root: Path, raw: str, *, must_exist: bool = True) -> Path:
    lexical = Path(raw).expanduser()
    if not lexical.is_absolute():
        lexical = root / lexical
    if lexical.is_symlink():
        raise GuardError("I collegamenti simbolici non sono accettati")
    path = lexical.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GuardError("Il file deve restare nel workspace") from exc
    if must_exist and not path.is_file():
        raise GuardError("File richiesto assente")
    return path


def derived_output(root: Path, raw: str, kind: str) -> Path:
    path = inside(root, raw, must_exist=False)
    relative = path.relative_to(root)
    allowed = {
        "scan": relative.as_posix() == "PRIVACY_REPORT.md"
        or (len(relative.parts) >= 2 and relative.parts[0] == "privacy-reports" and path.name.endswith(".privacy.md")),
        "snapshot": relative.as_posix() == "SOURCE_SNAPSHOT.json"
        or (len(relative.parts) >= 2 and relative.parts[0] == "privacy-snapshots" and path.name.endswith(".snapshot.json")),
        "verify": relative.as_posix() == "SOURCE_INTEGRITY_REPORT.md"
        or (len(relative.parts) >= 2 and relative.parts[0] == "privacy-reports" and path.name.endswith(".integrity.md")),
    }[kind]
    if not allowed:
        raise GuardError("Output non ammesso: usare il report predefinito o la directory privacy dedicata")
    return path


def bootstrap(args: argparse.Namespace) -> int:
    _, state = workspace(args.workspace)
    case_id = str(state.get("case_id", ""))
    created_at = str(state.get("created_at", ""))
    fingerprint = digest_bytes(f"gf-aos-case-v1:{case_id}:{created_at}".encode("utf-8"))[:12]
    actions = state.get("next_actions", [])
    blockers = state.get("blockers", [])
    module = str(state.get("lead_module", ""))
    status = str(state.get("status", ""))
    safe_module = module if MODULE_RE.fullmatch(module) else "NON DISPONIBILE"
    safe_status = status if status in SAFE_STATUSES else "NON DISPONIBILE"
    print("GF-AOS SAFE RESUME")
    print(f"- Case fingerprint: `{fingerprint}`")
    print(f"- Modulo: `{safe_module}`")
    print(f"- Stato: `{safe_status}`")
    print(f"- Checkpoint disponibile: {'si' if state.get('current_checkpoint') else 'no'}")
    print(f"- Azioni registrate: {len(actions) if isinstance(actions, list) else 0}")
    print(f"- Blocker registrati: {len(blockers) if isinstance(blockers, list) else 0}")
    print("- Aprire manualmente CASE_MEMORY.md solo nel contesto autorizzato.")
    return 0


def scan_findings(text: str, state: dict[str, Any]) -> Counter[str]:
    findings: Counter[str] = Counter()
    for name, pattern, _ in REDACTIONS:
        findings[name] += len(pattern.findall(text))
    for name, pattern in SECRET_PATTERNS:
        findings[name] += len(pattern.findall(text))
    lowered = text.lower()
    for field in ("case_id", "client_context"):
        value = str(state.get(field, "")).strip()
        if len(value) >= 4:
            findings[field.upper()] += lowered.count(value.lower())
    return Counter({key: value for key, value in findings.items() if value})


def scan(args: argparse.Namespace) -> int:
    root, state = workspace(args.workspace)
    if not 1 <= len(args.file) <= MAX_SCAN_FILES:
        raise GuardError(f"Indicare da 1 a {MAX_SCAN_FILES} file")
    output = derived_output(root, args.output, "scan")
    if output.exists() and not args.replace:
        raise GuardError("Il report esiste gia; usare --replace per il solo report derivato")
    totals: Counter[str] = Counter()
    locators: list[tuple[str, int, str]] = []
    sources: list[Path] = []
    for raw in args.file:
        path = inside(root, raw)
        if path == output or path.suffix.lower() not in TEXT_SUFFIXES:
            raise GuardError("Formato non ammesso o output usato come input")
        if path.stat().st_size > MAX_SCAN_BYTES:
            raise GuardError("File oltre 2 MiB")
        relative_hash = digest_bytes(str(path.relative_to(root)).encode("utf-8"))[:12]
        sources.append(path)
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            findings = scan_findings(line, state)
            totals.update(findings)
            for category, count in findings.items():
                locators.append((relative_hash, line_number, f"{category}:{count}"))
        for category in injection_flags(text):
            totals[category] += 1
            locators.append((relative_hash, 0, f"{category}:1"))

    secrets = sum(totals[name] for name, _ in SECRET_PATTERNS)
    injections = sum(totals[name] for name in ("IGNORE_INSTRUCTIONS", "SYSTEM_PROMPT", "SECRET_EXFILTRATION", "ROLE_OVERRIDE"))
    personal = sum(totals.values()) - secrets - injections
    if secrets or injections:
        result = "BLOCKED"
    elif args.profile in {"agent-handoff", "public"} and personal:
        result = "BLOCKED"
    elif personal:
        result = "WARN"
    elif args.profile in {"agent-handoff", "public"} and args.review_confirmation != PRIVACY_CONFIRMATION:
        result = "REVIEW_REQUIRED"
    else:
        result = "PASS"

    lines = [
        "# GF-AOS Privacy Report",
        "",
        f"- Esito: **{result}**",
        f"- Profilo: `{args.profile}`",
        f"- Generato UTC: {now_iso()}",
        f"- File esaminati: {len(args.file)}",
        f"- Content set SHA-256: `{content_set_digest(sources)}`",
        f"- Revisione contestuale confermata: {'si' if args.review_confirmation == PRIVACY_CONFIRMATION else 'no'}",
        "",
        "## Categorie rilevate",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in sorted(totals.items()))
    if not totals:
        lines.append("- Nessuna.")
    lines.extend(["", "## Locator pseudonimizzati", ""])
    lines.extend(
        f"- `{file_hash}:{f'L{line}' if line else 'DOCUMENTO'}` — {category}"
        for file_hash, line, category in locators
    )
    if not locators:
        lines.append("- Nessuno.")
    lines.extend(
        [
            "",
            "## Regole",
            "",
            "- Il report non riproduce i valori rilevati ne i nomi dei file.",
            "- BLOCKED impedisce handoff pubblico/agentico o azioni esterne fino a sanificazione e nuova scansione.",
            "- WARN richiede revisione umana e autorizzazione specifica prima di qualunque trasmissione.",
            f"- REVIEW_REQUIRED richiede la revisione contestuale e la conferma esatta `{PRIVACY_CONFIRMATION}`.",
            "- PASS non autorizza invio, pubblicazione, deposito o modifica delle fonti.",
            "",
        ]
    )
    atomic_text(output, "\n".join(lines))
    print(f"GF-AOS privacy scan: {result}")
    return 0 if result == "PASS" else 2


def snapshot_files(source_root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    count = 0
    for path in sorted(source_root.rglob("*")):
        if path.is_symlink():
            raise GuardError("La sorgente contiene collegamenti simbolici")
        if not path.is_file():
            continue
        count += 1
        if count > MAX_SNAPSHOT_FILES:
            raise GuardError(f"La sorgente supera {MAX_SNAPSHOT_FILES} file")
        relative = path.relative_to(source_root).as_posix()
        path_hash = digest_bytes(relative.encode("utf-8"))
        result[path_hash] = {
            "sha256": digest_file(path),
            "size": path.stat().st_size,
            "suffix": path.suffix.lower(),
        }
    return result


def require_separate_roots(root: Path, source_root: Path) -> None:
    if source_root == root or root in source_root.parents or source_root in root.parents:
        raise GuardError("La sorgente e il workspace derivato devono essere separati")


def source_snapshot(args: argparse.Namespace) -> int:
    root, _ = workspace(args.workspace)
    source_root = directory(args.source_root)
    require_separate_roots(root, source_root)
    output = derived_output(root, args.output, "snapshot")
    if output.exists() and (not args.replace or args.confirmation != BASELINE_CONFIRMATION):
        raise GuardError(f"Snapshot esistente; sostituzione consentita solo con --replace e conferma `{BASELINE_CONFIRMATION}`")
    value = {
        "schema_version": 1,
        "created_at": now_iso(),
        "source_root_fingerprint": digest_bytes(str(source_root).encode("utf-8")),
        "files": snapshot_files(source_root),
    }
    atomic_json(output, value)
    print(f"GF-AOS source snapshot: files={len(value['files'])}")
    return 0


def source_verify(args: argparse.Namespace) -> int:
    root, _ = workspace(args.workspace)
    source_root = directory(args.source_root)
    require_separate_roots(root, source_root)
    snapshot = inside(root, args.snapshot)
    try:
        expected = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GuardError("Snapshot non valido") from exc
    if not isinstance(expected, dict) or expected.get("schema_version") != 1 or not isinstance(expected.get("files"), dict):
        raise GuardError("Snapshot non valido")
    if expected.get("source_root_fingerprint") != digest_bytes(str(source_root).encode("utf-8")):
        raise GuardError("La radice sorgente non corrisponde allo snapshot")
    before = expected.get("files", {})
    after = snapshot_files(source_root)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(key for key in set(before) & set(after) if before[key] != after[key])
    result = "PASS" if not (added or removed or modified) else "BLOCKED"
    report = (
        "# GF-AOS Source Integrity Report\n\n"
        f"- Esito: **{result}**\n"
        f"- Aggiunti: {len(added)}\n- Rimossi: {len(removed)}\n- Modificati: {len(modified)}\n"
        f"- Verificato UTC: {now_iso()}\n\n"
        "## Impronte interessate\n\n"
        + "\n".join(f"- {kind}: `{item[:16]}`" for kind, values in (("ADD", added), ("REMOVE", removed), ("MODIFY", modified)) for item in values)
        + "\n\nIl report non contiene nomi o contenuti dei file. BLOCKED richiede verifica prima di proseguire.\n"
    )
    output = derived_output(root, args.output, "verify")
    if output == snapshot:
        raise GuardError("Il report non puo sovrascrivere lo snapshot")
    if output.exists() and not args.replace:
        raise GuardError("Il report esiste gia; usare --replace per il solo report derivato")
    atomic_text(output, report)
    print(f"GF-AOS source integrity: {result}")
    return 2 if result == "BLOCKED" else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Privacy-first Automation Guard")
    sub = parser.add_subparsers(dest="command", required=True)
    boot = sub.add_parser("bootstrap")
    boot.add_argument("workspace")
    boot.set_defaults(func=bootstrap)
    privacy = sub.add_parser("scan")
    privacy.add_argument("workspace")
    privacy.add_argument("--file", action="append", required=True)
    privacy.add_argument("--profile", choices=("agent-handoff", "public", "external-draft", "internal"), default="agent-handoff")
    privacy.add_argument("--output", default="PRIVACY_REPORT.md")
    privacy.add_argument("--replace", action="store_true")
    privacy.add_argument("--review-confirmation")
    privacy.set_defaults(func=scan)
    snap = sub.add_parser("snapshot")
    snap.add_argument("workspace")
    snap.add_argument("--source-root", required=True)
    snap.add_argument("--output", default="SOURCE_SNAPSHOT.json")
    snap.add_argument("--replace", action="store_true")
    snap.add_argument("--confirmation")
    snap.set_defaults(func=source_snapshot)
    verify = sub.add_parser("verify")
    verify.add_argument("workspace")
    verify.add_argument("--source-root", required=True)
    verify.add_argument("--snapshot", default="SOURCE_SNAPSHOT.json")
    verify.add_argument("--output", default="SOURCE_INTEGRITY_REPORT.md")
    verify.add_argument("--replace", action="store_true")
    verify.set_defaults(func=source_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except GuardError as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("ERRORE: operazione privacy non completata", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
