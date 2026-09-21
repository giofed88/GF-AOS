---
name: agent-orchestrator
description: Coordina ruoli agentici GF-AOS con delega minima, handoff tracciabili e revisione indipendente
---

# agent-orchestrator

Usa questa skill per incarichi che richiedono piu passaggi indipendenti. Per richieste semplici
lavora direttamente. Seleziona soltanto i ruoli necessari dal registro in
`references/agent-registry.md` e applica `references/handoff-contract.md`.

## Ciclo operativo

1. Il coordinatore definisce modulo principale, workstream, ruolo, periodo, output e blocker.
2. Explorer, planner e researcher possono lavorare in parallelo solo su perimetri non sovrapposti.
3. Il coordinatore consolida gli handoff e risolve divergenze dichiarandole.
4. Il dossier builder propone la struttura dell'artefatto senza approvarlo.
5. L'independent reviewer cerca rilievi; il coordinatore corregge o registra i limiti.
6. Il final verifier emette `PASS`, `PASS CON RILIEVI` o `BLOCKED`.
7. L'output resta `BOZZA DA VALIDARE` fino al gate professionale `APPROVO OUTPUT`.

Non delegare l'approvazione professionale, la modifica delle fonti o un'azione esterna. Attiva
`CRISIS_001` soltanto su incarico esplicito. Mantieni ogni specializzazione e conclusione distinta.

## Economia del contesto

Non creare agenti per ribadire informazioni gia disponibili. Fornisci a ciascun ruolo solo
obiettivo, perimetro, evidenze necessarie e formato di ritorno. Condividi gli estratti pertinenti,
non interi fascicoli, salvo necessita documentata.
