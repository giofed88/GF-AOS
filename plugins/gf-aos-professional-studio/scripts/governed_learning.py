#!/usr/bin/env python3
"""Apprendimento governato GF-AOS da fascicoli approvati e contenuti sanificati."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from context_curator import REDACTIONS, injection_flags


MAX_LESSON_BYTES = 16 * 1024
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
MODULE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,39}$")


class LearningError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def case_fingerprint(state: dict[str, Any]) -> str:
    case_id = str(state.get("case_id", "")).strip()
    if not case_id:
        raise LearningError("Case ID assente")
    return sha256_bytes(f"gf-aos-case-v1:{case_id}".encode("utf-8"))


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


def atomic_json(path: Path, content: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(content, ensure_ascii=False, indent=2) + "\n")


def real_directory(raw: str, *, create: bool = False) -> Path:
    lexical = Path(raw).expanduser()
    if lexical.exists() and lexical.is_symlink():
        raise LearningError("I collegamenti simbolici non sono accettati")
    if create:
        lexical.mkdir(parents=True, exist_ok=True)
    path = lexical.resolve()
    if not path.is_dir():
        raise LearningError(f"Directory non valida: {path}")
    return path


def inside(root: Path, raw: str, *, must_exist: bool = True) -> Path:
    lexical = Path(raw).expanduser()
    if not lexical.is_absolute():
        lexical = root / lexical
    if lexical.is_symlink():
        raise LearningError("I collegamenti simbolici non sono accettati")
    path = lexical.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise LearningError("Il file deve restare nel perimetro previsto") from exc
    if must_exist and not path.is_file():
        raise LearningError(f"File assente: {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LearningError(f"JSON non valido: {path.name}") from exc


def approved_workspace(raw: str) -> tuple[Path, dict[str, Any], str]:
    workspace = real_directory(raw)
    state_path = workspace / "CASE_STATE.json"
    receipt = workspace / "APPROVAL_RECEIPT.md"
    if not state_path.is_file() or not receipt.is_file():
        raise LearningError("Servono CASE_STATE.json e APPROVAL_RECEIPT.md")
    state = load_json(state_path)
    approval = state.get("approval", {})
    if state.get("status") != "Approvato" or approval.get("status") != "approvata":
        raise LearningError("L'apprendimento richiede un fascicolo nello stato Approvato")
    artifact_digest = str(approval.get("sha256", ""))
    if not re.fullmatch(r"[a-f0-9]{64}", artifact_digest):
        raise LearningError("Hash dell'artefatto approvato assente o non valido")
    artifact_raw = str(approval.get("artifact", ""))
    if not artifact_raw:
        raise LearningError("Locator dell'artefatto approvato assente")
    artifact = inside(workspace, artifact_raw)
    if sha256(artifact) != artifact_digest:
        raise LearningError("L'artefatto e cambiato dopo l'approvazione")
    if artifact_digest not in receipt.read_text(encoding="utf-8"):
        raise LearningError("La ricevuta non corrisponde all'artefatto approvato")
    return workspace, state, artifact_digest


def slugify(value: str) -> str:
    normalized = value.lower().strip()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    return normalized[:48]


def one_line(value: str, field: str, limit: int = 240) -> str:
    result = value.strip()
    if not result or len(result) > limit or "\n" in result or "\r" in result:
        raise LearningError(f"{field} deve essere una singola riga non vuota di massimo {limit} caratteri")
    return result


def privacy_findings(text: str, state: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    scan_text = re.sub(r"\b[a-f0-9]{64}\b", "[HASH GOVERNANCE]", text, flags=re.I)
    for name, pattern, _ in REDACTIONS:
        if pattern.search(scan_text):
            findings.append(name)
    lowered = scan_text.lower()
    for field in ("case_id", "client_context"):
        value = str(state.get(field, "")).strip()
        if len(value) >= 4 and value.lower() in lowered:
            findings.append(field.upper())
    findings.extend(injection_flags(scan_text))
    return sorted(set(findings))


def assert_sanitized(text: str, state: dict[str, Any], label: str) -> None:
    findings = privacy_findings(text, state)
    if findings:
        raise LearningError(f"{label} contiene elementi non promuovibili: {', '.join(findings)}")


def parse_candidate(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    patterns = {
        "method_id": r"^- Method ID: `([^`]+)`$",
        "module": r"^- Modulo: `([^`]+)`$",
        "scope": r"^- Ambito: `([^`]+)`$",
        "source_digest": r"^- Evidenza approvata: `([a-f0-9]{64})`$",
        "title": r"^# Candidato metodo — DA VALIDARE\n\n## (.+)$",
    }
    result: dict[str, str] = {"text": text}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.MULTILINE)
        if not match:
            raise LearningError(f"Candidato non valido: campo {key} assente")
        result[key] = match.group(1).strip()
    if not ID_RE.fullmatch(result["method_id"]) or not MODULE_RE.fullmatch(result["module"]):
        raise LearningError("Identificativi del candidato non validi")
    if result["scope"] not in {"module", "studio"}:
        raise LearningError("Ambito del candidato non valido")
    return result


def command_propose(args: argparse.Namespace) -> int:
    workspace, state, artifact_digest = approved_workspace(args.workspace)
    lesson = Path(args.lesson_file).expanduser()
    if not lesson.is_file() or lesson.is_symlink() or lesson.stat().st_size > MAX_LESSON_BYTES:
        raise LearningError("La lezione deve essere un file regolare entro 16 KiB")
    content = lesson.read_text(encoding="utf-8").strip()
    title = one_line(args.title, "Titolo", 120)
    trigger = one_line(args.trigger, "Trigger")
    if not content:
        raise LearningError("La lezione e vuota")
    assert_sanitized("\n".join((title, trigger, content)), state, "La proposta")
    module = str(state.get("lead_module", ""))
    if not MODULE_RE.fullmatch(module):
        raise LearningError("Modulo GF-AOS non valido nello stato")
    base = slugify(title)
    if not base:
        raise LearningError("Il titolo non produce un identificativo valido")
    method_id = f"{base}-{sha256_bytes(content.encode('utf-8'))[:8]}"
    target = workspace / "learning" / "candidates" / f"{method_id}.md"
    if target.exists():
        raise LearningError("Il candidato esiste gia")
    body = (
        f"# Candidato metodo — DA VALIDARE\n\n## {title}\n\n"
        f"- Method ID: `{method_id}`\n"
        f"- Modulo: `{module}`\n"
        f"- Ambito: `{args.scope}`\n"
        f"- Evidenza approvata: `{artifact_digest}`\n"
        f"- Proposto UTC: {now_iso()}\n\n"
        f"## Trigger\n\n{trigger}\n\n"
        f"## Azione riutilizzabile\n\n{content}\n\n"
        "## Esclusioni obbligatorie\n\n"
        "- Non trasferire fatti, nomi, importi, date, conclusioni o strategie del caso sorgente.\n"
        "- Verificare sempre fonti e applicabilita nel nuovo incarico.\n"
        "- Non modificare automaticamente skill, agenti, fonti o sistemi esterni.\n"
    )
    atomic_text(target, body)
    print(target)
    return 0


def library_paths(raw: str, workspace: Path) -> tuple[Path, Path, Path]:
    unresolved = Path(raw).expanduser().resolve()
    try:
        unresolved.relative_to(workspace)
    except ValueError:
        pass
    else:
        raise LearningError("La libreria dei metodi deve essere separata dal fascicolo cliente")
    library = real_directory(raw, create=True)
    if library.is_symlink():
        raise LearningError("La libreria non puo essere un collegamento simbolico")
    return library, library / "methods", library / "METHOD_REGISTRY.json"


def command_promote(args: argparse.Namespace) -> int:
    if args.confirmation != "APPROVO METODO":
        raise LearningError("Conferma non valida: usare esattamente APPROVO METODO")
    workspace, state, artifact_digest = approved_workspace(args.workspace)
    candidate_path = inside(workspace, args.candidate)
    expected_parent = (workspace / "learning" / "candidates").resolve()
    try:
        candidate_path.relative_to(expected_parent)
    except ValueError as exc:
        raise LearningError("Il candidato deve provenire da learning/candidates") from exc
    candidate = parse_candidate(candidate_path)
    if candidate["source_digest"] != artifact_digest:
        raise LearningError("Il candidato non appartiene alla versione approvata corrente")
    note_path = Path(args.note_file).expanduser()
    if not note_path.is_file() or note_path.is_symlink():
        raise LearningError("Nota di approvazione non valida")
    note = note_path.read_text(encoding="utf-8").strip()
    if len(note) < 10:
        raise LearningError("La nota deve contenere almeno 10 caratteri")
    assert_sanitized(candidate["text"], state, "Il candidato")
    assert_sanitized(note, state, "La nota")
    library, methods, registry_path = library_paths(args.library, workspace)
    target = methods / candidate["module"] / f"{candidate['method_id']}.md"
    if target.exists():
        raise LearningError("Il metodo esiste gia; usare reinforce con un altro caso approvato")
    method_body = candidate["text"].replace("# Candidato metodo — DA VALIDARE", "# Metodo GF-AOS — APPROVATO", 1)
    method_body += (
        "\n## Governance\n\n"
        f"- Approvato UTC: {now_iso()}\n"
        f"- Nota di approvazione SHA-256: `{sha256_bytes(note.encode('utf-8'))}`\n"
        "- Confidenza iniziale: `0.50`\n"
        "- Evidenze approvate: `1`\n"
    )
    atomic_text(target, method_body)
    registry = load_json(registry_path) if registry_path.exists() else {"schema_version": 1, "methods": {}}
    methods_state = registry.setdefault("methods", {})
    methods_state[candidate["method_id"]] = {
        "module": candidate["module"],
        "scope": candidate["scope"],
        "path": str(target.relative_to(library)),
        "confidence": 0.5,
        "evidence_digests": [artifact_digest],
        "case_fingerprints": [case_fingerprint(state)],
        "approved_at": now_iso(),
    }
    atomic_json(registry_path, registry)
    print(target)
    return 0


def command_reinforce(args: argparse.Namespace) -> int:
    if args.confirmation != "CONFERMO METODO":
        raise LearningError("Conferma non valida: usare esattamente CONFERMO METODO")
    if not ID_RE.fullmatch(args.method_id):
        raise LearningError("Method ID non valido")
    workspace, state, artifact_digest = approved_workspace(args.workspace)
    library, _, registry_path = library_paths(args.library, workspace)
    if not registry_path.is_file():
        raise LearningError("Registro metodi assente")
    registry = load_json(registry_path)
    method = registry.get("methods", {}).get(args.method_id)
    if not isinstance(method, dict):
        raise LearningError("Metodo non trovato")
    if method.get("scope") == "module" and method.get("module") != state.get("lead_module"):
        raise LearningError("Un metodo module puo essere rinforzato solo nello stesso modulo")
    note_path = Path(args.note_file).expanduser()
    if not note_path.is_file() or note_path.is_symlink():
        raise LearningError("Nota di rinforzo non valida")
    note = note_path.read_text(encoding="utf-8").strip()
    if len(note) < 10:
        raise LearningError("La nota di rinforzo deve contenere almeno 10 caratteri")
    assert_sanitized(note, state, "La nota di rinforzo")
    evidence = method.setdefault("evidence_digests", [])
    if artifact_digest in evidence:
        raise LearningError("Questa evidenza approvata e gia registrata")
    fingerprints = method.setdefault("case_fingerprints", [])
    fingerprint = case_fingerprint(state)
    if fingerprint in fingerprints:
        raise LearningError("Lo stesso caso non puo rinforzare due volte un metodo")
    evidence.append(artifact_digest)
    fingerprints.append(fingerprint)
    method["confidence"] = min(0.9, round(0.5 + 0.1 * (len(evidence) - 1), 2))
    method["last_reinforced_at"] = now_iso()
    target = inside(library, str(method["path"]))
    updated_method = target.read_text(encoding="utf-8") + (
        f"\n- Rinforzo UTC {now_iso()}: evidenza `{artifact_digest}`, "
        f"nota `{sha256_bytes(note.encode('utf-8'))}`, confidenza `{method['confidence']:.2f}`\n"
    )
    atomic_text(target, updated_method)
    atomic_json(registry_path, registry)
    print(f"{args.method_id} confidence={method['confidence']:.2f} evidence={len(evidence)}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    library = real_directory(args.library)
    registry_path = library / "METHOD_REGISTRY.json"
    registry = load_json(registry_path) if registry_path.is_file() else {"methods": {}}
    print("# GF-AOS Method Library\n")
    print("| Method ID | Modulo | Ambito | Confidenza | Evidenze |")
    print("| --- | --- | --- | ---: | ---: |")
    for method_id, value in sorted(registry.get("methods", {}).items()):
        print(
            f"| `{method_id}` | `{value.get('module', '')}` | {value.get('scope', '')} | "
            f"{float(value.get('confidence', 0)):.2f} | {len(value.get('evidence_digests', []))} |"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Governed Learning")
    sub = parser.add_subparsers(dest="command", required=True)
    propose = sub.add_parser("propose")
    propose.add_argument("workspace")
    propose.add_argument("--lesson-file", required=True)
    propose.add_argument("--title", required=True)
    propose.add_argument("--trigger", required=True)
    propose.add_argument("--scope", choices=("module", "studio"), default="module")
    propose.set_defaults(func=command_propose)
    promote = sub.add_parser("promote")
    promote.add_argument("workspace")
    promote.add_argument("--candidate", required=True)
    promote.add_argument("--library", required=True)
    promote.add_argument("--note-file", required=True)
    promote.add_argument("--confirmation", required=True)
    promote.set_defaults(func=command_promote)
    reinforce = sub.add_parser("reinforce")
    reinforce.add_argument("workspace")
    reinforce.add_argument("--method-id", required=True)
    reinforce.add_argument("--library", required=True)
    reinforce.add_argument("--note-file", required=True)
    reinforce.add_argument("--confirmation", required=True)
    reinforce.set_defaults(func=command_reinforce)
    status = sub.add_parser("status")
    status.add_argument("--library", required=True)
    status.set_defaults(func=command_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (LearningError, OSError, UnicodeError, ValueError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
