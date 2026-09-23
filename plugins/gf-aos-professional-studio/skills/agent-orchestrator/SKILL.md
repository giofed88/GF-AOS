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
2. Il context curator prepara, quando necessario, il pacchetto minimo per ciascuna delega. Il
   coordinatore esegue lo scanner con profilo `agent-handoff`; il Privacy Guardian read-only
   riesamina il report prima che il pacchetto venga condiviso.
3. Explorer, planner e researcher possono lavorare in parallelo solo su perimetri non sovrapposti.
4. Il coordinatore consolida gli handoff e risolve divergenze dichiarandole.
5. Il dossier builder propone la struttura dell'artefatto senza approvarlo.
6. L'independent reviewer cerca rilievi; il coordinatore corregge o registra i limiti.
7. Il final verifier emette `PASS`, `PASS CON RILIEVI` o `BLOCKED`.
8. L'output resta `BOZZA DA VALIDARE` fino al gate professionale `APPROVO OUTPUT`.
9. Il context keeper consolida il checkpoint Markdown al termine della fase; il coordinatore
   esegue il controllo strutturale `case-lifecycle quality` prima della chiusura.
10. Se serve un'azione esterna, il coordinatore prepara la coda governata e l'External Action
    Controller riesamina la richiesta; nessun agente esegue l'azione o dichiara la consegna.

Non delegare l'approvazione professionale, la modifica delle fonti o un'azione esterna. Attiva
`CRISIS_001` soltanto su incarico esplicito. Mantieni ogni specializzazione e conclusione distinta.
Un esito privacy `BLOCKED` interrompe il ciclo; `PASS` non sostituisce alcun gate umano.

## Economia del contesto

Non creare agenti per ribadire informazioni gia disponibili. Fornisci a ciascun ruolo solo
obiettivo, perimetro, evidenze necessarie e formato di ritorno. Condividi gli estratti pertinenti,
non interi fascicoli, salvo necessita documentata.
