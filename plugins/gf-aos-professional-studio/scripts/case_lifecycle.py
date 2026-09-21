#!/usr/bin/env python3
"""Lifecycle locale e controllato dei fascicoli GF-AOS.

Il programma scrive esclusivamente nel workspace indicato. I documenti sorgente del
cliente restano fuori dal perimetro e non vengono mai rinominati o modificati.
"""

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


SCHEMA_VERSION = 1
STATUSES = (
    "Da avviare",
    "In corso",
    "Completato",
    "Da validare",
    "In attesa documenti",
    "Bloccato",
    "Ignorato consapevolmente",
    "Approvato",
)
REQUIRED_MARKDOWN = (
    "RIEPILOGO_INCARICO.md",
    "CASE_MEMORY.md",
    "EVIDENZE.md",
    "DOCUMENTI_MANCANTI.md",
    "ACTION_QUEUE.md",
    "EVENT_LOG.md",
)
MODULE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,39}$")


class LifecycleError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_workspace(raw: str, *, create: bool = False) -> Path:
    path = Path(raw).expanduser()
    if path.exists() and path.is_symlink():
        raise LifecycleError("Il workspace non puo essere un collegamento simbolico")
    if create:
        path.mkdir(parents=True, exist_ok=True)
    path = path.resolve()
    if not path.is_dir():
        raise LifecycleError(f"Workspace non valido: {path}")
    return path


def markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def within_workspace(workspace: Path, raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise LifecycleError("L'artefatto deve trovarsi nel workspace") from exc
    if candidate.is_symlink():
        raise LifecycleError("I collegamenti simbolici non sono accettati")
    return candidate


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_state(workspace: Path) -> dict[str, Any]:
    path = workspace / "CASE_STATE.json"
    if not path.is_file():
        raise LifecycleError("CASE_STATE.json assente: inizializzare prima il fascicolo")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LifecycleError("CASE_STATE.json non leggibile o non valido") from exc
    if state.get("schema_version") != SCHEMA_VERSION:
        raise LifecycleError("Versione dello stato non supportata")
    return state


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def append_event(workspace: Path, event: str, detail: str) -> None:
    path = workspace / "EVENT_LOG.md"
    line = f"| {now_iso()} | {event} | {detail.replace('|', '/')} |\n"
    if not path.exists():
        atomic_text(path, "# Event log\n\n| Data UTC | Evento | Dettaglio |\n| --- | --- | --- |\n")
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)


def case_header(state: dict[str, Any]) -> str:
    return (
        "| Campo | Valore |\n| --- | --- |\n"
        f"| Case ID | {markdown_cell(state['case_id'])} |\n"
        f"| Cliente / contesto | {markdown_cell(state['client_context'])} |\n"
        f"| Modulo principale | {markdown_cell(state['lead_module'])} |\n"
        f"| Ruolo | {markdown_cell(state['role'])} |\n"
        f"| Periodo | {markdown_cell(state['period'])} |\n"
        f"| Stato | {markdown_cell(state['status'])} |\n"
        f"| Ultimo aggiornamento UTC | {markdown_cell(state['updated_at'])} |\n"
    )


def command_init(args: argparse.Namespace) -> int:
    if not MODULE_RE.fullmatch(args.module):
        raise LifecycleError("Il modulo deve essere un codice GF-AOS maiuscolo valido")
    if args.module == "CRISIS_001" and not args.crisis_explicit:
        raise LifecycleError("CRISIS_001 richiede --crisis-explicit")
    workspace = safe_workspace(args.workspace, create=True)
    state_path = workspace / "CASE_STATE.json"
    if state_path.exists():
        raise LifecycleError("Fascicolo gia inizializzato: usare un nuovo workspace per un nuovo caso")
    if any(workspace.iterdir()):
        raise LifecycleError("Il workspace iniziale deve essere vuoto per evitare sovrascritture")

    timestamp = now_iso()
    state: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": args.case_id,
        "client_context": args.client,
        "lead_module": args.module,
        "role": args.role,
        "period": args.period,
        "status": "Da avviare",
        "crisis_explicit": bool(args.crisis_explicit),
        "created_at": timestamp,
        "updated_at": timestamp,
        "current_checkpoint": None,
        "next_actions": [],
        "blockers": [],
        "approval": {
            "status": "non richiesta",
            "note": None,
            "artifact": None,
            "sha256": None,
            "approved_at": None,
        },
        "source_change_authorized": False,
        "external_action_authorized": False,
    }
    for directory in ("checkpoints", "outputs", "document-intelligence"):
        (workspace / directory).mkdir(exist_ok=True)
    atomic_json(state_path, state)
    warning = "BOZZA DA VALIDARE"
    atomic_text(
        workspace / "RIEPILOGO_INCARICO.md",
        f"# Riepilogo incarico — {warning}\n\n{case_header(state)}\n## Perimetro\n\n- Da definire.\n",
    )
    atomic_text(
        workspace / "CASE_MEMORY.md",
        f"# GF-AOS Case Memory — {warning}\n\n{case_header(state)}\n"
        "## Fatti e decisioni confermati\n\n- Nessuno registrato.\n\n"
        "## Documenti mancanti, contraddizioni e blocker\n\n- Da verificare.\n\n"
        "## Prossime azioni consentite\n\n1. Definire il perimetro e acquisire le evidenze.\n",
    )
    atomic_text(workspace / "EVIDENZE.md", f"# Evidenze — {warning}\n\n- Da acquisire e collegare con locator.\n")
    atomic_text(workspace / "DOCUMENTI_MANCANTI.md", "# Documenti mancanti\n\n- Da verificare.\n")
    atomic_text(workspace / "ACTION_QUEUE.md", "# Action queue\n\n1. Definire il perimetro e acquisire le evidenze.\n")
    atomic_text(workspace / "EVENT_LOG.md", "# Event log\n\n| Data UTC | Evento | Dettaglio |\n| --- | --- | --- |\n")
    append_event(workspace, "CASE_INITIALIZED", f"modulo={args.module}; stato=Da avviare")
    print(workspace)
    return 0


def command_checkpoint(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    summary_path = Path(args.summary_file).expanduser().resolve()
    if not summary_path.is_file() or summary_path.is_symlink():
        raise LifecycleError("Il riepilogo Markdown non e un file regolare")
    if summary_path.stat().st_size > 512 * 1024:
        raise LifecycleError("Il riepilogo supera 512 KiB: compattarlo prima del checkpoint")
    summary = summary_path.read_text(encoding="utf-8").strip()
    if not summary:
        raise LifecycleError("Il riepilogo Markdown e vuoto")
    if len(args.next_action) > 4:
        raise LifecycleError("Sono consentite al massimo quattro prossime azioni")
    if args.status not in STATUSES or args.status == "Approvato":
        raise LifecycleError("Usare approve per lo stato Approvato")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    checkpoint_rel = f"checkpoints/{stamp}.md"
    checkpoint = workspace / checkpoint_rel
    state["status"] = args.status
    state["updated_at"] = now_iso()
    state["current_checkpoint"] = checkpoint_rel
    state["next_actions"] = args.next_action
    state["blockers"] = args.blocker
    body = (
        f"# Checkpoint {stamp} — BOZZA DA VALIDARE\n\n{case_header(state)}\n"
        f"## Sintesi canonica\n\n{summary}\n\n"
        "## Blocker\n\n"
        + ("\n".join(f"- {item}" for item in args.blocker) or "- Nessuno registrato.")
        + "\n\n## Prossime azioni consentite\n\n"
        + ("\n".join(f"{index}. {item}" for index, item in enumerate(args.next_action, 1)) or "1. Nessuna registrata.")
        + "\n"
    )
    atomic_text(checkpoint, body)
    atomic_text(workspace / "CASE_MEMORY.md", body.replace(f"Checkpoint {stamp}", "GF-AOS Case Memory", 1))
    atomic_text(
        workspace / "ACTION_QUEUE.md",
        "# Action queue\n\n"
        + ("\n".join(f"{index}. {item}" for index, item in enumerate(args.next_action, 1)) or "1. Nessuna registrata.")
        + "\n",
    )
    atomic_json(workspace / "CASE_STATE.json", state)
    append_event(workspace, "CHECKPOINT_CREATED", f"locator={checkpoint_rel}; stato={args.status}; sha256={sha256(checkpoint)}")
    print(checkpoint)
    return 0


def command_resume(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    memory = workspace / "CASE_MEMORY.md"
    if not memory.is_file():
        raise LifecycleError("CASE_MEMORY.md assente")
    print(f"GF-AOS RESUME | {state['case_id']} | {state['lead_module']} | {state['status']}")
    print(memory.read_text(encoding="utf-8"))
    return 0


def evaluate(workspace: Path, state: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    for field in ("case_id", "client_context", "lead_module", "role", "period", "status"):
        if not state.get(field):
            blockers.append(f"Campo obbligatorio assente: {field}")
    if state.get("status") not in STATUSES:
        blockers.append("Stato non appartenente al vocabolario GF-AOS")
    if state.get("lead_module") == "CRISIS_001" and not state.get("crisis_explicit"):
        blockers.append("CRISIS_001 non risulta attivato esplicitamente")
    for name in REQUIRED_MARKDOWN:
        if not (workspace / name).is_file():
            blockers.append(f"File obbligatorio assente: {name}")
    if len(state.get("next_actions", [])) > 4:
        blockers.append("Sono registrate piu di quattro prossime azioni")
    if state.get("source_change_authorized"):
        warnings.append("Esiste un'autorizzazione a modificare sorgenti: verificare perimetro e log")
    if state.get("external_action_authorized"):
        warnings.append("Esiste un'autorizzazione ad azione esterna: verificare target e log")
    if state.get("status") in {"Completato", "Da validare", "Approvato"}:
        evidence = workspace / "EVIDENZE.md"
        if not evidence.is_file() or evidence.stat().st_size < 100:
            blockers.append("Registro evidenze insufficiente per lo stato dichiarato")
    approval = state.get("approval", {})
    if state.get("status") == "Approvato":
        if approval.get("status") != "approvata" or not approval.get("sha256"):
            blockers.append("Stato Approvato privo di gate professionale e hash")
        artifact = approval.get("artifact")
        if artifact:
            try:
                artifact_path = within_workspace(workspace, artifact)
                if not artifact_path.is_file() or sha256(artifact_path) != approval.get("sha256"):
                    blockers.append("L'artefatto approvato e assente o modificato dopo l'approvazione")
            except LifecycleError as exc:
                blockers.append(str(exc))
    elif approval.get("status") == "approvata":
        blockers.append("Gate approvato incoerente con lo stato del fascicolo")
    if not state.get("current_checkpoint"):
        warnings.append("Nessun checkpoint di sessione ancora creato")
    status = "BLOCKED" if blockers else ("PASS CON RILIEVI" if warnings else "PASS")
    return status, blockers, warnings


def command_quality(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    status, blockers, warnings = evaluate(workspace, state)
    lines = [
        "# GF-AOS Quality Report",
        "",
        f"- Esito: **{status}**",
        f"- Case ID: `{state.get('case_id', '')}`",
        f"- Generato UTC: {now_iso()}",
        "",
        "## Blocker",
        "",
        *(f"- {item}" for item in blockers),
    ]
    if not blockers:
        lines.append("- Nessuno.")
    lines.extend(["", "## Rilievi", "", *(f"- {item}" for item in warnings)])
    if not warnings:
        lines.append("- Nessuno.")
    lines.extend(
        [
            "",
            "## Limite del controllo",
            "",
            "Il controllo e strutturale e non sostituisce revisione indipendente, giudizio professionale, firma o deposito.",
            "",
        ]
    )
    report = "\n".join(lines)
    atomic_text(workspace / "QUALITY_REPORT.md", report)
    append_event(workspace, "QUALITY_CHECK", f"esito={status}; blocker={len(blockers)}; rilievi={len(warnings)}")
    print(report)
    return 2 if blockers else 0


def command_approve(args: argparse.Namespace) -> int:
    if args.confirmation != "APPROVO OUTPUT":
        raise LifecycleError("Conferma non valida: usare esattamente APPROVO OUTPUT")
    note_path = Path(args.note_file).expanduser().resolve()
    if not note_path.is_file() or note_path.is_symlink():
        raise LifecycleError("Nota di approvazione non valida")
    note = note_path.read_text(encoding="utf-8").strip()
    if len(note) < 10:
        raise LifecycleError("La nota finale deve contenere almeno 10 caratteri")
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    if state.get("status") not in {"Completato", "Da validare"}:
        raise LifecycleError("L'approvazione richiede uno stato Completato o Da validare")
    _, blockers, _ = evaluate(workspace, state)
    if blockers:
        raise LifecycleError("Controlli bloccanti non risolti: " + "; ".join(blockers))
    artifact = within_workspace(workspace, args.artifact)
    if not artifact.is_file():
        raise LifecycleError("Artefatto da approvare assente")
    if artifact.suffix.lower() == ".md" and "BOZZA DA VALIDARE" not in artifact.read_text(encoding="utf-8"):
        raise LifecycleError("L'artefatto Markdown deve riportare BOZZA DA VALIDARE prima dell'approvazione")
    digest = sha256(artifact)
    timestamp = now_iso()
    state["status"] = "Approvato"
    state["updated_at"] = timestamp
    state["approval"] = {
        "status": "approvata",
        "note": note,
        "artifact": str(artifact.relative_to(workspace)),
        "sha256": digest,
        "approved_at": timestamp,
    }
    atomic_json(workspace / "CASE_STATE.json", state)
    receipt = (
        "# Ricevuta approvazione GF-AOS\n\n"
        f"- Case ID: `{markdown_cell(state['case_id'])}`\n"
        f"- Artefatto: `{markdown_cell(artifact.relative_to(workspace))}`\n"
        f"- SHA-256: `{digest}`\n"
        f"- Approvato UTC: {timestamp}\n"
        f"- Nota professionale: {markdown_cell(note)}\n"
        "- Conferma registrata: `APPROVO OUTPUT`\n\n"
        "La ricevuta documenta il gate interno e non costituisce firma digitale, marcatura "
        "temporale, deposito o trasmissione.\n"
    )
    atomic_text(workspace / "APPROVAL_RECEIPT.md", receipt)
    append_event(workspace, "OUTPUT_APPROVED", f"artifact={artifact.relative_to(workspace)}; sha256={digest}")
    print(f"APPROVATO {artifact.relative_to(workspace)} {digest}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Lifecycle & Quality Engine")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Inizializza un workspace derivato")
    init.add_argument("workspace")
    init.add_argument("--case-id", required=True)
    init.add_argument("--client", required=True)
    init.add_argument("--module", required=True)
    init.add_argument("--role", required=True)
    init.add_argument("--period", required=True)
    init.add_argument("--crisis-explicit", action="store_true")
    init.set_defaults(func=command_init)

    checkpoint = sub.add_parser("checkpoint", help="Salva memoria Markdown e stato minimo")
    checkpoint.add_argument("workspace")
    checkpoint.add_argument("--summary-file", required=True)
    checkpoint.add_argument("--status", choices=STATUSES[:-1], default="In corso")
    checkpoint.add_argument("--next-action", action="append", default=[])
    checkpoint.add_argument("--blocker", action="append", default=[])
    checkpoint.set_defaults(func=command_checkpoint)

    resume = sub.add_parser("resume", help="Stampa il checkpoint canonico senza scrivere")
    resume.add_argument("workspace")
    resume.set_defaults(func=command_resume)

    quality = sub.add_parser("quality", help="Esegue i controlli strutturali e scrive il report")
    quality.add_argument("workspace")
    quality.set_defaults(func=command_quality)

    approve = sub.add_parser("approve", help="Registra il gate professionale su un artefatto")
    approve.add_argument("workspace")
    approve.add_argument("--artifact", required=True)
    approve.add_argument("--note-file", required=True)
    approve.add_argument("--confirmation", required=True)
    approve.set_defaults(func=command_approve)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (LifecycleError, OSError, UnicodeError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
