#!/usr/bin/env python3
"""Runtime Markdown-first per AUDIT_001, BOARD_001 e DUAL_001.

Opera soltanto nel workspace GF-AOS e non modifica mai i documenti sorgente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODULES = {
    "AUDIT_001": ("Revisione legale", "REVISIONE"),
    "BOARD_001": ("Collegio sindacale / sindaco unico", "VIGILANZA"),
    "DUAL_001": ("Sindaco e revisore", None),
}
STEPS = (
    ("A01_CONTEXT", "Perimetro e incarico", False),
    ("A02_PRIOR_PERIOD", "Confronto con il periodo precedente", True),
    ("A03_ANOMALIES", "Anomalie e follow-up aperti", True),
    ("A04_COHERENCE", "Coerenza tra documenti", True),
    ("A05_ANALYTICS", "Analisi, quadrature e scostamenti", True),
    ("A06_RISK_CONTINUITY", "Rischi e continuita aziendale", True),
    ("A07_SECTOR_ACCEPTANCE", "Settore, indipendenza e pianificazione", True),
    ("A08_EVIDENCE_FOLLOWUP", "Evidenze e richieste", True),
    ("A09_DRAFT_OUTPUTS", "Bozza verbale e carta di lavoro", True),
    ("A10_QUALITY_REVIEW", "Controllo qualita", False),
    ("A11_PROFESSIONAL_APPROVAL", "Approvazione professionale", True),
)
STATUSES = {
    "Da avviare", "In corso", "Completato", "Da validare",
    "In attesa documenti", "Bloccato", "Ignorato consapevolmente", "Approvato",
}
TERMINAL_FOR_SEQUENCE = {"Completato", "Ignorato consapevolmente"}
SEVERITIES = {"Informativa", "Attenzione", "Bloccante"}
FUNCTION_TAGS = {"REVISIONE", "VIGILANZA", "COMUNE"}


class AuditWorkflowError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_workspace(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_symlink():
        raise AuditWorkflowError("Il workspace non puo essere un collegamento simbolico")
    path = path.resolve()
    if not path.is_dir():
        raise AuditWorkflowError(f"Workspace non valido: {path}")
    return path


def state_path(workspace: Path) -> Path:
    return workspace / "CASE_STATE.json"


def read_state(workspace: Path) -> dict[str, Any]:
    path = state_path(workspace)
    if not path.is_file() or path.is_symlink():
        raise AuditWorkflowError("CASE_STATE.json assente o non valido")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditWorkflowError("CASE_STATE.json non leggibile") from exc
    module = str(state.get("lead_module", ""))
    if module not in MODULES:
        raise AuditWorkflowError("Il runtime accetta soltanto AUDIT_001, BOARD_001 o DUAL_001")
    return state


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


def write_state(workspace: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    atomic_text(state_path(workspace), json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def append_event(state: dict[str, Any], event: str, step: str, detail: str) -> None:
    state.setdefault("audit_event_log", []).append({
        "timestamp": now_iso(), "event": event, "step": step, "detail": detail,
    })


def workflow(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get("professional_workflow")
    if not isinstance(value, dict):
        raise AuditWorkflowError("Workflow non inizializzato: eseguire init")
    return value


def find_step(state: dict[str, Any], code: str) -> dict[str, Any]:
    for step in workflow(state)["steps"]:
        if step["code"] == code:
            return step
    raise AuditWorkflowError(f"Fase sconosciuta: {code}")


def prior_steps(state: dict[str, Any], code: str) -> list[dict[str, Any]]:
    steps = workflow(state)["steps"]
    index = next((i for i, item in enumerate(steps) if item["code"] == code), None)
    if index is None:
        raise AuditWorkflowError(f"Fase sconosciuta: {code}")
    return steps[:index]


def default_tag(module: str) -> str | None:
    return MODULES[module][1]


def render_control(state: dict[str, Any]) -> str:
    wf = workflow(state)
    rows = []
    for item in wf["steps"]:
        rows.append(
            f"| `{item['code']}` | {item['title']} | {item['status']} | "
            f"{item['severity']} | {item.get('function_tag') or '—'} |"
        )
    return (
        "# Workflow professionale — BOZZA DA VALIDARE\n\n"
        "| Campo | Valore |\n| --- | --- |\n"
        f"| Case ID | {state.get('case_id', '')} |\n"
        f"| Modulo | `{state.get('lead_module', '')}` |\n"
        f"| Ruolo | {state.get('role', '')} |\n"
        f"| Periodo | {state.get('period', '')} |\n"
        f"| Workflow | {wf['version']} |\n"
        f"| Fase corrente | `{wf['current_step']}` |\n\n"
        "| Fase | Obiettivo | Stato | Severita | Funzione |\n"
        "| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n\n"
        "## Gate\n\n"
        "- Salto: motivazione di almeno 15 caratteri e `PRENDO ATTO E IGNORO <STEP_CODE>`.\n"
        "- Approvazione: nota di almeno 10 caratteri e `APPROVO OUTPUT`.\n"
        "- Modifica sorgenti e azioni esterne restano autorizzazioni separate.\n"
    )


def render_evidence(state: dict[str, Any]) -> str:
    rows = []
    for item in workflow(state)["steps"]:
        for evidence in item.get("evidence", []):
            rows.append(
                f"| `{item['code']}` | {evidence['locator']} | {evidence['proposition']} | "
                f"{evidence['status']} | {evidence.get('verified_at') or '—'} |"
            )
    body = "\n".join(rows) or "| — | — | — | — | — |"
    return (
        "# Registro evidenze — BOZZA DA VALIDARE\n\n"
        "| Fase | Locator | Proposizione supportata | Stato | Verificata UTC |\n"
        "| --- | --- | --- | --- | --- |\n" + body + "\n\n"
        "La presenza di un file non costituisce prova del suo contenuto. Fonti cliente in sola lettura.\n"
    )


def render_follow_up(state: dict[str, Any]) -> str:
    items = workflow(state).get("follow_up", [])
    rows = [
        f"| `{item['step']}` | {item['action']} | {item.get('owner') or '—'} | "
        f"{item.get('due_date') or '—'} | {item['status']} |"
        for item in items
    ]
    return (
        "# Punti da monitorare e follow-up — BOZZA DA VALIDARE\n\n"
        "| Fase | Azione | Responsabile | Termine | Stato |\n"
        "| --- | --- | --- | --- | --- |\n" + ("\n".join(rows) or "| — | — | — | — | — |") + "\n"
    )


def refresh_markdown(workspace: Path, state: dict[str, Any]) -> None:
    atomic_text(workspace / "AUDIT_WORKFLOW.md", render_control(state))
    atomic_text(workspace / "EVIDENCE_REGISTER.md", render_evidence(state))
    atomic_text(workspace / "FOLLOW_UP.md", render_follow_up(state))


def command_init(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    if "professional_workflow" in state:
        raise AuditWorkflowError("Workflow gia inizializzato: nessuna sovrascrittura")
    module = state["lead_module"]
    tag = default_tag(module)
    state["professional_workflow"] = {
        "version": "0.17.0",
        "module": module,
        "title": MODULES[module][0],
        "current_step": "A01_CONTEXT",
        "steps": [
            {
                "code": code, "title": title, "status": "Da avviare",
                "severity": "Informativa", "required": True, "human_gate": gate,
                "function_tag": tag, "summary": "", "findings": [], "evidence": [],
                "limitations": [], "actions": [], "human_decision": None, "updated_at": None,
            }
            for code, title, gate in STEPS
        ],
        "follow_up": [], "artifacts": [], "approval": None,
        "created_at": now_iso(),
    }
    state.setdefault("locked_memory", {})
    state.setdefault("audit_event_log", [])
    append_event(state, "WORKFLOW_INITIALIZED", "A01_CONTEXT", f"module={module}")
    write_state(workspace, state)
    refresh_markdown(workspace, state)
    print(workspace / "AUDIT_WORKFLOW.md")
    return 0


def command_step(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    wf = workflow(state)
    item = find_step(state, args.step)
    if args.step in {"A09_DRAFT_OUTPUTS", "A10_QUALITY_REVIEW", "A11_PROFESSIONAL_APPROVAL"}:
        raise AuditWorkflowError("Usare rispettivamente draft, validate o approve")
    if args.status not in {"In corso", "Completato", "In attesa documenti", "Bloccato"}:
        raise AuditWorkflowError("Stato non consentito dal comando step")
    open_prior = [x["code"] for x in prior_steps(state, args.step) if x["status"] not in TERMINAL_FOR_SEQUENCE]
    if open_prior:
        raise AuditWorkflowError("Fasi precedenti non terminali: " + ", ".join(open_prior))
    function_tag = args.function_tag or default_tag(state["lead_module"])
    if state["lead_module"] == "DUAL_001" and function_tag not in FUNCTION_TAGS:
        raise AuditWorkflowError("DUAL_001 richiede --function-tag REVISIONE, VIGILANZA o COMUNE")
    if function_tag and function_tag not in FUNCTION_TAGS:
        raise AuditWorkflowError("Function tag non valido")
    if args.severity not in SEVERITIES:
        raise AuditWorkflowError("Severita non valida")
    item.update({
        "status": args.status, "severity": args.severity, "function_tag": function_tag,
        "summary": args.summary, "limitations": args.limitation,
        "actions": args.action, "updated_at": now_iso(),
    })
    if args.evidence_locator:
        item["evidence"].append({
            "locator": args.evidence_locator,
            "proposition": args.evidence_proposition,
            "status": args.evidence_status,
            "verified_at": now_iso() if args.evidence_status == "verificata" else None,
        })
    for action in args.action:
        wf["follow_up"].append({
            "step": args.step, "action": action, "owner": args.owner,
            "due_date": args.due_date, "status": "Aperto",
        })
    if args.status == "Completato":
        next_step = next((x["code"] for x in wf["steps"] if x["status"] == "Da avviare"), args.step)
        wf["current_step"] = next_step
    state["status"] = "In corso" if args.status != "Bloccato" else "Bloccato"
    append_event(state, "STEP_UPDATED", args.step, f"status={args.status}; evidence={len(item['evidence'])}")
    write_state(workspace, state)
    refresh_markdown(workspace, state)
    print(f"{args.step}: {args.status}")
    return 0


def command_skip(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    item = find_step(state, args.step)
    expected = f"PRENDO ATTO E IGNORO {args.step}"
    if len(args.rationale.strip()) < 15 or args.confirmation != expected:
        raise AuditWorkflowError(f"Servono motivazione >=15 caratteri e conferma esatta: {expected}")
    open_prior = [x["code"] for x in prior_steps(state, args.step) if x["status"] not in TERMINAL_FOR_SEQUENCE]
    if open_prior:
        raise AuditWorkflowError("Fasi precedenti non terminali: " + ", ".join(open_prior))
    item.update({
        "status": "Ignorato consapevolmente", "severity": "Attenzione",
        "human_decision": {"confirmation": expected, "rationale": args.rationale, "timestamp": now_iso()},
        "limitations": item.get("limitations", []) + [args.rationale], "updated_at": now_iso(),
    })
    append_event(state, "STEP_CONSCIOUSLY_SKIPPED", args.step, f"rationale_hash={reference_hash(args.rationale)}")
    write_state(workspace, state)
    refresh_markdown(workspace, state)
    print(f"{args.step}: Ignorato consapevolmente")
    return 0


def dossier_text(state: dict[str, Any]) -> str:
    wf = workflow(state)
    parts = []
    table_rows = []
    for item in wf["steps"][:8]:
        tag = item.get("function_tag") or "—"
        evidence = "; ".join(x["locator"] for x in item.get("evidence", [])) or "—"
        limitations = "; ".join(item.get("limitations", [])) or "Nessuna registrata"
        parts.append(
            f"### {item['code']} — {item['title']} [{tag}]\n\n"
            f"{item.get('summary') or 'Nessun risultato registrato.'}\n\n"
            f"**Evidenze:** {evidence}.  \n**Limiti:** {limitations}."
        )
        table_rows.append(
            f"| `{item['code']}` | {tag} | {item.get('summary') or '—'} | {evidence} | "
            f"{item['status']} | {item['severity']} | {'; '.join(item.get('actions', [])) or '—'} |"
        )
    title = MODULES[state["lead_module"]][0]
    return (
        f"# Dossier integrato — {title} — BOZZA DA VALIDARE\n\n"
        "| Campo | Valore |\n| --- | --- |\n"
        f"| Case ID | {state.get('case_id', '')} |\n| Modulo | `{state['lead_module']}` |\n"
        f"| Ruolo | {state.get('role', '')} |\n| Periodo | {state.get('period', '')} |\n"
        f"| Data generazione UTC | {now_iso()} |\n| Stato sorgenti | Sola lettura |\n\n"
        "## Parte I — Verbale narrativo\n\n"
        "### Perimetro e quadro professionale\n\n"
        "Il presente documento raccoglie le procedure e le evidenze registrate nel fascicolo. "
        "Fatti, calcoli, inferenze, valutazioni professionali e limiti documentali restano distinti.\n\n"
        + "\n\n".join(parts) + "\n\n"
        "### Punti da monitorare e follow-up\n\n"
        + ("\n".join(f"- {x['action']} — {x.get('owner') or 'responsabile da definire'} — {x.get('due_date') or 'termine da definire'}" for x in wf["follow_up"]) or "- Nessuno registrato.")
        + "\n\n### Conclusione professionale\n\n[RISERVATA ALLA VALIDAZIONE DEL PROFESSIONISTA]\n\n"
        "## Parte II — Carta di lavoro e checklist\n\n"
        "| Fase | Funzione | Risultato fattuale | Evidenza | Stato | Severita | Follow-up |\n"
        "| --- | --- | --- | --- | --- | --- | --- |\n" + "\n".join(table_rows) + "\n\n"
        "## Tracciabilita e governo delle fonti\n\n"
        "Le fonti cliente sono state trattate in sola lettura. Approvazione, firma, invio, deposito e modifica delle fonti sono azioni distinte.\n"
    )


def command_draft(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    for item in workflow(state)["steps"][:8]:
        if item["status"] not in TERMINAL_FOR_SEQUENCE:
            raise AuditWorkflowError(f"Fase non terminale: {item['code']}")
    output = workspace / "DOSSIER_INTEGRATO.md"
    if output.exists() and not args.replace:
        raise AuditWorkflowError("DOSSIER_INTEGRATO.md esiste: usare --replace")
    atomic_text(output, dossier_text(state))
    item = find_step(state, "A09_DRAFT_OUTPUTS")
    item.update({"status": "Da validare", "severity": "Attenzione", "summary": "Dossier Markdown generato", "updated_at": now_iso()})
    workflow(state)["current_step"] = "A10_QUALITY_REVIEW"
    artifact = {
        "artifact_code": "DOS-001", "document_id": f"{state.get('case_id', '')}-DOS-001",
        "title": "Dossier integrato", "status": "Da validare", "generated_at": now_iso(),
        "verification_date": None, "version": "1", "location": "DOSSIER_INTEGRATO.md", "sha256": sha256(output),
    }
    workflow(state)["artifacts"] = [artifact]
    append_event(state, "DOSSIER_DRAFTED", "A09_DRAFT_OUTPUTS", f"sha256={artifact['sha256']}")
    state["status"] = "Da validare"
    write_state(workspace, state)
    refresh_markdown(workspace, state)
    print(output)
    return 0


def quality_findings(state: dict[str, Any], dossier: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    wf = workflow(state)
    for item in wf["steps"][:8]:
        if item["status"] not in TERMINAL_FOR_SEQUENCE:
            blockers.append(f"Fase non terminale: {item['code']}")
        if item["status"] == "Completato" and not item.get("summary"):
            blockers.append(f"Sintesi assente: {item['code']}")
        if item["human_gate"] and item["status"] == "Completato" and not item.get("evidence"):
            warnings.append(f"Nessuna evidenza collegata: {item['code']}")
        if state["lead_module"] == "DUAL_001" and item["code"] != "A01_CONTEXT" and item.get("function_tag") not in FUNCTION_TAGS:
            blockers.append(f"Funzione non classificata: {item['code']}")
    for required in ("BOZZA DA VALIDARE", "Parte I — Verbale narrativo", "Parte II — Carta di lavoro", "Conclusione professionale"):
        if required not in dossier:
            blockers.append(f"Sezione dossier assente: {required}")
    if state["lead_module"] == "DUAL_001" and not any(x.get("function_tag") == "REVISIONE" for x in wf["steps"][:8]):
        warnings.append("DUAL_001 non contiene procedure marcate REVISIONE")
    if state["lead_module"] == "DUAL_001" and not any(x.get("function_tag") == "VIGILANZA" for x in wf["steps"][:8]):
        warnings.append("DUAL_001 non contiene procedure marcate VIGILANZA")
    return blockers, warnings


def command_validate(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    dossier_path = workspace / "DOSSIER_INTEGRATO.md"
    if not dossier_path.is_file() or dossier_path.is_symlink():
        raise AuditWorkflowError("DOSSIER_INTEGRATO.md assente o non valido")
    dossier = dossier_path.read_text(encoding="utf-8")
    blockers, warnings = quality_findings(state, dossier)
    status = "BLOCKED" if blockers else ("PASS CON RILIEVI" if warnings else "PASS")
    report = (
        "# Audit workflow quality review\n\n"
        f"- Esito: **{status}**\n- Modulo: `{state['lead_module']}`\n- Dossier SHA-256: `{sha256(dossier_path)}`\n"
        f"- Generato UTC: {now_iso()}\n\n## Blocker\n\n"
        + ("\n".join(f"- {x}" for x in blockers) or "- Nessuno.")
        + "\n\n## Rilievi\n\n" + ("\n".join(f"- {x}" for x in warnings) or "- Nessuno.")
        + "\n\nLa verifica e strutturale e non sostituisce il giudizio professionale.\n"
    )
    atomic_text(workspace / "AUDIT_QUALITY_REVIEW.md", report)
    item = find_step(state, "A10_QUALITY_REVIEW")
    item.update({
        "status": "Bloccato" if blockers else "Completato",
        "severity": "Bloccante" if blockers else ("Attenzione" if warnings else "Informativa"),
        "summary": status, "limitations": blockers + warnings, "updated_at": now_iso(),
    })
    workflow(state)["current_step"] = "A10_QUALITY_REVIEW" if blockers else "A11_PROFESSIONAL_APPROVAL"
    append_event(state, "QUALITY_REVIEWED", "A10_QUALITY_REVIEW", f"status={status}; blockers={len(blockers)}")
    write_state(workspace, state)
    refresh_markdown(workspace, state)
    print(report)
    return 2 if blockers else 0


def command_approve(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    if args.confirmation != "APPROVO OUTPUT" or len(args.note.strip()) < 10:
        raise AuditWorkflowError("Servono nota >=10 caratteri e conferma esatta APPPROVO OUTPUT".replace("APPPROVO", "APPROVO"))
    qa = find_step(state, "A10_QUALITY_REVIEW")
    if qa["status"] != "Completato":
        raise AuditWorkflowError("A10_QUALITY_REVIEW non completata")
    dossier = workspace / "DOSSIER_INTEGRATO.md"
    current_hash = sha256(dossier)
    artifact = workflow(state)["artifacts"][0]
    if current_hash != artifact["sha256"]:
        raise AuditWorkflowError("Il dossier e cambiato dopo la generazione: ripetere draft e validate")
    approval = {
        "confirmation": "APPROVO OUTPUT", "note": args.note,
        "professional_name": args.professional_name, "approved_at": now_iso(),
        "artifact": artifact["location"], "sha256": current_hash,
        "statement": "Non costituisce firma digitale, marca temporale, deposito o trasmissione.",
    }
    workflow(state)["approval"] = approval
    item = find_step(state, "A11_PROFESSIONAL_APPROVAL")
    item.update({"status": "Approvato", "severity": "Informativa", "summary": args.note, "human_decision": approval, "updated_at": now_iso()})
    artifact["status"] = "Approvato"
    state["status"] = "Approvato"
    append_event(state, "OUTPUT_APPROVED", "A11_PROFESSIONAL_APPROVAL", f"sha256={current_hash}")
    write_state(workspace, state)
    receipt = (
        "# Ricevuta di approvazione professionale\n\n"
        f"- Case ID: {state.get('case_id', '')}\n- Artefatto: `{artifact['location']}`\n"
        f"- SHA-256: `{current_hash}`\n- Professionista: {args.professional_name}\n"
        f"- Nota: {args.note}\n- Conferma: `APPROVO OUTPUT`\n- Data UTC: {approval['approved_at']}\n\n"
        "La ricevuta non costituisce firma digitale, marca temporale qualificata, deposito o trasmissione.\n"
    )
    atomic_text(workspace / "AUDIT_APPROVAL_RECEIPT.md", receipt)
    refresh_markdown(workspace, state)
    print(workspace / "AUDIT_APPROVAL_RECEIPT.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS audit and governance workflow runtime")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("workspace")
    init.set_defaults(func=command_init)
    step = commands.add_parser("step")
    step.add_argument("workspace")
    step.add_argument("step", choices=[x[0] for x in STEPS[:8]])
    step.add_argument("--status", required=True)
    step.add_argument("--summary", required=True)
    step.add_argument("--severity", choices=sorted(SEVERITIES), default="Informativa")
    step.add_argument("--function-tag", choices=sorted(FUNCTION_TAGS))
    step.add_argument("--evidence-locator")
    step.add_argument("--evidence-proposition", default="Da specificare")
    step.add_argument("--evidence-status", choices=("da verificare", "verificata", "insufficiente"), default="da verificare")
    step.add_argument("--limitation", action="append", default=[])
    step.add_argument("--action", action="append", default=[])
    step.add_argument("--owner")
    step.add_argument("--due-date")
    step.set_defaults(func=command_step)
    skip = commands.add_parser("skip")
    skip.add_argument("workspace")
    skip.add_argument("step", choices=[x[0] for x in STEPS[:8]])
    skip.add_argument("--rationale", required=True)
    skip.add_argument("--confirmation", required=True)
    skip.set_defaults(func=command_skip)
    draft = commands.add_parser("draft")
    draft.add_argument("workspace")
    draft.add_argument("--replace", action="store_true")
    draft.set_defaults(func=command_draft)
    validate = commands.add_parser("validate")
    validate.add_argument("workspace")
    validate.set_defaults(func=command_validate)
    approve = commands.add_parser("approve")
    approve.add_argument("workspace")
    approve.add_argument("--note", required=True)
    approve.add_argument("--professional-name", required=True)
    approve.add_argument("--confirmation", required=True)
    approve.set_defaults(func=command_approve)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (AuditWorkflowError, OSError, UnicodeError, KeyError, IndexError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
