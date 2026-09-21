#!/usr/bin/env python3
"""Piani professionali GF-AOS in Markdown, senza modificare i sorgenti cliente."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class Pack:
    family: str
    title: str
    role_boundary: str
    phases: tuple[tuple[str, str], ...]
    outputs: tuple[tuple[str, str], ...]
    source_rule: str


AUDIT_PHASES = (
    ("A01_CONTEXT", "Perimetro e incarico"),
    ("A02_PRIOR_PERIOD", "Confronto con il periodo precedente"),
    ("A03_ANOMALIES", "Anomalie e follow-up aperti"),
    ("A04_COHERENCE", "Coerenza tra documenti"),
    ("A05_ANALYTICS", "Analisi, quadrature e scostamenti"),
    ("A06_RISK_CONTINUITY", "Rischi e continuita aziendale"),
    ("A07_SECTOR_ACCEPTANCE", "Settore, indipendenza e pianificazione"),
    ("A08_EVIDENCE_FOLLOWUP", "Evidenze e richieste"),
    ("A09_DRAFT_OUTPUTS", "Bozza degli output"),
    ("A10_QUALITY_REVIEW", "Controllo qualita"),
    ("A11_PROFESSIONAL_APPROVAL", "Approvazione professionale"),
)

TAX_PHASES = (
    ("T01_SCOPE", "Soggetto, ruolo, periodo, destinatario e scadenza"),
    ("T02_FACTS", "Matrice datata dei fatti e documenti"),
    ("T03_LAW_PRACTICE", "Norme, prassi e principi applicabili"),
    ("T04_CALCULATION", "Calcoli, quadrature e assunzioni"),
    ("T05_OPTIONS_RISKS", "Opzioni, condizioni e rischi"),
    ("T06_CALIBRATED_OUTPUT", "Output calibrato per il soggetto"),
    ("T07_QA_APPROVAL", "Controllo e approvazione"),
)

LABOUR_PHASES = (
    ("L01_SCOPE", "Datore, lavoratore, rapporto, periodo e scadenza"),
    ("L02_FACTS", "Documenti del rapporto e posizioni previdenziali"),
    ("L03_RULES", "Norme, CCNL e istruzioni ufficiali"),
    ("L04_RECONCILIATION", "Retribuzioni, contributi, premi e differenze"),
    ("L05_ACTIONS", "Correzioni, istanze, termini e rischi"),
    ("L06_OUTPUT_QA", "Output, verifica fonti e approvazione"),
)

LITIGATION_PHASES = (
    ("C01_PROCEDURE", "Atto, notifica, giudice, fase e termini"),
    ("C02_FACTS_EVIDENCE", "Cronologia, fatti, prove e lacune"),
    ("C03_ISSUES", "Questioni sostanziali, processuali e sanzionatorie"),
    ("C04_AUTHORITIES", "Norme, prassi e giurisprudenza ufficiale"),
    ("C05_APPLICATION", "Ratio, analogie, differenze e conflitti"),
    ("C06_DRAFT", "Mappa processuale e bozza tecnica"),
    ("C07_QA", "Citazioni, termini, allegati e approvazione"),
)

EXPERT_PHASES = (
    ("P01_MANDATE", "Ruolo, quesito, data di riferimento e limiti"),
    ("P02_CORPUS", "Documenti, provenienza e mancanze"),
    ("P03_FACTS", "Ricostruzione cronologica e tecnica"),
    ("P04_FRAMEWORK", "Quadro normativo e professionale"),
    ("P05_METHOD", "Metodo, assunzioni e alternative"),
    ("P06_ANALYSIS", "Calcoli, quadrature, sensibilita e tesi opposte"),
    ("P07_CONCLUSIONS", "Risposte entro il mandato e riserve"),
    ("P08_QA_APPROVAL", "Controllo e approvazione"),
)


def pack(family: str, title: str, boundary: str, phases: tuple[tuple[str, str], ...],
         outputs: tuple[tuple[str, str], ...], sources: str) -> Pack:
    return Pack(family, title, boundary, phases, outputs, sources)


PACKS: dict[str, Pack] = {
    "AUDIT_001": pack(
        "revisione-governance", "Revisione legale",
        "Procedure e conclusioni di revisione; non usarle come prova automatica di vigilanza.",
        AUDIT_PHASES,
        (("DOS-001", "Dossier integrato"), ("VRB-001", "Verbale narrativo"),
         ("CL-001", "Carta di lavoro / checklist indipendente")),
        "ISA Italia vigenti, RGS/MEF, CNDCEC e OIC quando applicabili.",
    ),
    "BOARD_001": pack(
        "revisione-governance", "Collegio sindacale / sindaco unico",
        "Vigilanza ex art. 2403 c.c.; non descrivere le procedure come test di revisione.",
        AUDIT_PHASES,
        (("DOS-001", "Dossier integrato"), ("VRB-001", "Verbale di vigilanza"),
         ("CL-001", "Scheda CNDCEC e follow-up")),
        "Codice civile e norme di comportamento, verbali e procedure CNDCEC vigenti.",
    ),
    "DUAL_001": pack(
        "revisione-governance", "Sindaco e revisore",
        "Un dossier, ma procedure e conclusioni marcate REVISIONE, VIGILANZA o COMUNE.",
        AUDIT_PHASES,
        (("DOS-001", "Dossier integrato"), ("VRB-001", "Verbale narrativo"),
         ("CL-001", "Carte di lavoro separate per funzione")),
        "ISA Italia/RGS e disciplina di vigilanza/CNDCEC, con applicabilita distinta.",
    ),
    "ACC_CAP_001": pack(
        "fiscale", "Societa di capitali",
        "Separare contabilita, imposte, governance e adempimenti.", TAX_PHASES,
        (("MEM-001", "Memo tecnico"), ("REC-001", "Riconciliazione contabile-fiscale"),
         ("CHK-001", "Checklist e scadenze")),
        "Normattiva/GU, AdE, MEF, OIC, Registro Imprese e fonti CNDCEC/FNC pertinenti.",
    ),
    "ACC_PART_001": pack(
        "fiscale", "Societa di persone",
        "Distinguere effetti della societa ed effetti dei soci.", TAX_PHASES,
        (("MEM-001", "Memo societa/soci"), ("CALC-001", "Calcoli"),
         ("CHK-001", "Checklist dichiarativa")),
        "Normattiva/GU, AdE, MEF e istruzioni ufficiali applicabili al periodo.",
    ),
    "ACC_SOLE_001": pack(
        "fiscale", "Impresa individuale",
        "Tenere distinti reddito d'impresa, posizione personale e contributi.", TAX_PHASES,
        (("MEM-001", "Bridge impresa-persona"), ("CALC-001", "Calcoli fiscali e contributivi"),
         ("CHK-001", "Checklist")),
        "Normattiva/GU, AdE, INPS e istruzioni ufficiali applicabili al periodo.",
    ),
    "ACC_PERSON_001": pack(
        "fiscale", "Persona fisica",
        "Ricostruire la posizione solo da documenti e dati riferiti al contribuente e al periodo.",
        TAX_PHASES,
        (("MEM-001", "Memo della posizione fiscale"), ("SRC-001", "Registro documenti"),
         ("ACT-001", "Calcoli e azioni di versamento/invio")),
        "Normattiva/GU, AdE e istruzioni ufficiali di modello e versamento.",
    ),
    "ACC_NPO_001": pack(
        "fiscale", "Ente non commerciale / RUNTS",
        "Separare attivita istituzionale, commerciale e mista; verificare gli obblighi RUNTS.",
        TAX_PHASES,
        (("MEM-001", "Memo ente"), ("REC-001", "Separazione attivita"),
         ("CHK-001", "Checklist contabile, fiscale, RUNTS e governance")),
        "Normattiva/GU, AdE, Ministero del Lavoro/RUNTS e prassi ufficiale pertinente.",
    ),
    "LAB_001": pack(
        "lavoro", "Lavoro, payroll, INPS e INAIL",
        "Il risultato del software paghe o un DURC non sostituisce la riconciliazione.",
        LABOUR_PHASES,
        (("MEM-001", "Memo operativo"), ("REC-001", "Calcolo o riconciliazione datata"),
         ("SRC-001", "Matrice fonti istituzionali"), ("CHK-001", "Checklist azioni")),
        "Normattiva/GU, Ministero del Lavoro, INPS, INAIL e CCNL pertinente.",
    ),
    "LAB_CALC_001": pack(
        "lavoro", "Conteggi di lavoro",
        "Esporre assunzioni, dati origine, calcolo per periodo, scenari e limiti.",
        LABOUR_PHASES,
        (("CALC-001", "Conteggio per periodo"), ("ASM-001", "Assunzioni e dati fonte"),
         ("SCN-001", "Scenari alternativi e limiti")),
        "Norme, CCNL e istruzioni INPS/INAIL vigenti per ciascun periodo.",
    ),
    "TAX_LIT_001": pack(
        "contenzioso", "Contenzioso tributario",
        "La strategia legale resta al difensore; leggere la motivazione, non soltanto la massima.",
        LITIGATION_PHASES,
        (("TIM-001", "Cronologia processuale"), ("EVD-001", "Matrice fatti/prove"),
         ("AUT-001", "Matrice precedenti ufficiali"), ("DRF-001", "Bozza tecnica"),
         ("CHK-001", "Checklist deposito")),
        "Normattiva/GU, Giustizia Tributaria, Cassazione, Consulta e CGUE quando pertinenti.",
    ),
}

for code, title, boundary, outputs in (
    ("CTP_001", "Consulenza tecnica di parte", "Analisi tecnicamente ferma e parte-aware; strategia legale al difensore.",
     (("REP-001", "Relazione tecnica di parte"), ("EVD-001", "Mappa quesiti ed evidenze"), ("ANN-001", "Allegati"))),
    ("CTU_001", "Consulenza tecnica d'ufficio", "Neutralita, simmetria, risposta per quesito e registro delle operazioni.",
     (("REP-001", "Relazione neutrale per quesito"), ("LOG-001", "Registro operazioni"), ("OBS-001", "Osservazioni delle parti"))),
    ("VALUATION_001", "Perizia di stima", "La valutazione non e revisione; metodi e assunzioni devono essere trasparenti.",
     (("REP-001", "Relazione di stima"), ("CALC-001", "Calcoli e riconciliazioni"), ("SEN-001", "Sensitivita"))),
    ("DUE_DIL_001", "Due diligence", "Perimetro e qualita delle informazioni delimitano ogni finding.",
     (("IDX-001", "Indice data room"), ("RFL-001", "Registro red flag"), ("REQ-001", "Richieste e azioni"))),
    ("CONDO_REVIEW_001", "Revisione/perizia condominiale", "Solo incarico di revisione o perizia; mai contabilita condominiale ordinaria.",
     (("REP-001", "Relazione tecnica"), ("REC-001", "Riconciliazioni e riparti"), ("EXC-001", "Eccezioni e limiti"))),
):
    PACKS[code] = pack(
        "perizie", title, boundary, EXPERT_PHASES, outputs,
        "Norme, standard professionali e fonti ufficiali pertinenti a ruolo, quesito e data di riferimento.",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_workspace(raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_symlink():
        raise WorkflowError("Il workspace non puo essere un collegamento simbolico")
    path = path.resolve()
    if not path.is_dir():
        raise WorkflowError(f"Workspace non valido: {path}")
    return path


def read_state(workspace: Path) -> dict[str, Any]:
    path = workspace / "CASE_STATE.json"
    if not path.is_file() or path.is_symlink():
        raise WorkflowError("CASE_STATE.json assente o non valido")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError("CASE_STATE.json non leggibile") from exc
    return state


def atomic_text(path: Path, content: str) -> None:
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


def selected(code: str) -> Pack:
    try:
        return PACKS[code]
    except KeyError as exc:
        raise WorkflowError(f"Modulo non incluso nei Professional Workflow Packs: {code}") from exc


def command_list(_: argparse.Namespace) -> int:
    print("# GF-AOS Professional Workflow Packs\n")
    print("| Modulo | Famiglia | Workflow |")
    print("| --- | --- | --- |")
    for code, item in PACKS.items():
        print(f"| `{code}` | {item.family} | {item.title} |")
    return 0


def command_show(args: argparse.Namespace) -> int:
    item = selected(args.module)
    print(f"# {args.module} — {item.title}\n")
    print(f"- Famiglia: {item.family}")
    print(f"- Confine di ruolo: {item.role_boundary}")
    print(f"- Fonti: {item.source_rule}\n")
    print("## Fasi\n")
    for code, title in item.phases:
        print(f"- `{code}` — {title}")
    print("\n## Output minimi\n")
    for code, title in item.outputs:
        print(f"- `{code}` — {title}")
    return 0


def render_plan(state: dict[str, Any], module: str, item: Pack) -> str:
    rows = "\n".join(f"| [ ] | `{code}` | {title} | Da avviare | — | — |" for code, title in item.phases)
    return (
        f"# Piano di lavoro — {module} — BOZZA DA VALIDARE\n\n"
        "| Campo | Valore |\n| --- | --- |\n"
        f"| Case ID | {state.get('case_id', '')} |\n| Modulo | `{module}` |\n"
        f"| Workflow | {item.title} |\n| Ruolo | {state.get('role', '')} |\n"
        f"| Periodo | {state.get('period', '')} |\n| Generato UTC | {now_iso()} |\n\n"
        f"## Confine professionale\n\n{item.role_boundary}\n\n"
        "## Fasi\n\n| Fatto | Codice | Obiettivo | Stato | Evidenza/locator | Decisione o limite |\n"
        "| --- | --- | --- | --- | --- | --- |\n" + rows + "\n\n"
        f"## Regola fonti\n\n{item.source_rule}\n\n"
        "Registrare per ogni fonte ente, titolo, data/versione, locator, data di accesso, "
        "proposizione supportata e applicabilita al periodo. Distinguere fatto, calcolo, "
        "inferenza, valutazione professionale e limite documentale.\n\n"
        "## Gate\n\n- Sorgenti cliente: sola lettura.\n"
        "- Salto fase: motivazione e `PRENDO ATTO E IGNORO <STEP_CODE>`.\n"
        "- Modifica sorgenti: anteprima e `AUTORIZZO MODIFICA SORGENTI`.\n"
        "- Conclusioni dispositive: riservate alla validazione professionale.\n"
        "- Approvazione finale: nota e `APPROVO OUTPUT` sull'esatta versione.\n"
        "- Invio, deposito, firma e pubblicazione: azioni esterne separate.\n"
    )


def render_output_register(module: str, item: Pack) -> str:
    rows = "\n".join(f"| `{code}` | {title} | Da avviare | — | — |" for code, title in item.outputs)
    return (
        f"# Registro output — {module} — BOZZA DA VALIDARE\n\n"
        "| Codice | Output | Stato | Versione/locator | SHA-256 |\n"
        "| --- | --- | --- | --- | --- |\n" + rows + "\n\n"
        "L'approvazione dell'output non autorizza modifiche ai sorgenti o azioni esterne.\n"
    )


def render_working_papers(module: str) -> str:
    return (
        f"# Indice carte di lavoro — {module} — BOZZA DA VALIDARE\n\n"
        "| ID | Fase | Titolo | Evidenza/locator | Stato | Preparato/rivisto |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Da assegnare | — | — | — | Da avviare | — |\n\n"
        "Ogni carta autonoma riporta data scheda, data verifica/lavoro, data generazione, "
        "ruolo, periodo, fonti, limiti e follow-up.\n"
    )


def command_plan(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    module = str(state.get("lead_module", ""))
    if args.module and args.module != module:
        raise WorkflowError("Il modulo richiesto non coincide con lead_module del fascicolo")
    item = selected(module)
    targets = {
        workspace / "WORKFLOW_PLAN.md": render_plan(state, module, item),
        workspace / "OUTPUT_REGISTER.md": render_output_register(module, item),
        workspace / "WORKING_PAPERS_INDEX.md": render_working_papers(module),
    }
    existing = [path.name for path in targets if path.exists()]
    if existing:
        raise WorkflowError("Nessuna sovrascrittura: file gia presenti: " + ", ".join(existing))
    for path, content in targets.items():
        atomic_text(path, content)
    print("\n".join(str(path) for path in targets))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    workspace = safe_workspace(args.workspace)
    state = read_state(workspace)
    module = str(state.get("lead_module", ""))
    item = selected(module)
    blockers: list[str] = []
    warnings: list[str] = []
    required = ("WORKFLOW_PLAN.md", "OUTPUT_REGISTER.md", "WORKING_PAPERS_INDEX.md")
    contents: dict[str, str] = {}
    for name in required:
        path = workspace / name
        if not path.is_file() or path.is_symlink():
            blockers.append(f"File workflow assente: {name}")
        else:
            contents[name] = path.read_text(encoding="utf-8")
    plan = contents.get("WORKFLOW_PLAN.md", "")
    register = contents.get("OUTPUT_REGISTER.md", "")
    for code, _ in item.phases:
        if f"`{code}`" not in plan:
            blockers.append(f"Fase assente dal piano: {code}")
    for code, _ in item.outputs:
        if f"`{code}`" not in register:
            blockers.append(f"Output assente dal registro: {code}")
    for name, content in contents.items():
        if "BOZZA DA VALIDARE" not in content:
            blockers.append(f"Etichetta bozza assente: {name}")
    if state.get("status") in {"Completato", "Da validare", "Approvato"}:
        unchecked = plan.count("| [ ] |")
        if unchecked:
            blockers.append(f"{unchecked} fasi risultano non completate nel piano")
    elif plan.count("| [ ] |") == len(item.phases):
        warnings.append("Il piano e strutturalmente valido ma nessuna fase risulta avviata")
    status = "BLOCKED" if blockers else ("PASS CON RILIEVI" if warnings else "PASS")
    report = [
        "# Workflow Pack Eval", "", f"- Esito: **{status}**", f"- Modulo: `{module}`",
        f"- Generato UTC: {now_iso()}", "", "## Blocker", "",
        *(f"- {value}" for value in blockers),
    ]
    if not blockers:
        report.append("- Nessuno.")
    report.extend(["", "## Rilievi", "", *(f"- {value}" for value in warnings)])
    if not warnings:
        report.append("- Nessuno.")
    report.extend([
        "", "## Limite", "",
        "Eval strutturale: non sostituisce verifica delle fonti, revisione indipendente o giudizio professionale.", "",
    ])
    text = "\n".join(report)
    atomic_text(workspace / "WORKFLOW_EVAL.md", text)
    print(text)
    return 2 if blockers else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GF-AOS Professional Workflow Packs")
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("list", help="Elenca i moduli inclusi in Markdown")
    listing.set_defaults(func=command_list)
    show = sub.add_parser("show", help="Mostra un workflow senza scrivere")
    show.add_argument("module")
    show.set_defaults(func=command_show)
    plan = sub.add_parser("plan", help="Crea i registri Markdown nel workspace")
    plan.add_argument("workspace")
    plan.add_argument("--module")
    plan.set_defaults(func=command_plan)
    validate = sub.add_parser("validate", help="Valida struttura e avanzamento del workflow")
    validate.add_argument("workspace")
    validate.set_defaults(func=command_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return int(args.func(args))
    except (WorkflowError, OSError, UnicodeError) as exc:
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
