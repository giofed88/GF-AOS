# Revisione e governance

## Moduli

- `AUDIT_001`: verbale/report narrativo e carta di lavoro autonoma; framework ISA Italia.
- `BOARD_001`: verbale di vigilanza e scheda art. 2403/CNDCEC; non chiamare i controlli test di revisione.
- `DUAL_001`: unico dossier, con procedure e conclusioni marcate `REVISIONE`, `VIGILANZA` o `COMUNE`.

## Sequenza

`A01_CONTEXT` → `A02_PRIOR_PERIOD` → `A03_ANOMALIES` → `A04_COHERENCE` →
`A05_ANALYTICS` → `A06_RISK_CONTINUITY` → `A07_SECTOR_ACCEPTANCE` →
`A08_EVIDENCE_FOLLOWUP` → `A09_DRAFT_OUTPUTS` → `A10_QUALITY_REVIEW` →
`A11_PROFESSIONAL_APPROVAL`.

Non formulare automaticamente giudizi su continuita, indipendenza, conformita o relazione finale.
Verificare il documento vigente sottostante nelle fonti RGS/MEF e CNDCEC, non la sola landing page.
Prima di A09, A01–A08 devono essere terminali. A11 richiede controllo dell'esatta versione,
nota professionale e `APPROVO OUTPUT`.

## Runtime persistente

Usare `scripts/audit_workflow.py` per l'esecuzione e non limitarsi a marcare il piano statico.
Il runtime conserva fasi, severita, evidenze, limiti, decisioni, follow-up, artefatti e approvazione
nel `CASE_STATE.json` canonico. Non creare uno stato parallelo.

- `step`: registra una fase A01-A08, rifiutando avanzamenti fuori sequenza.
- `skip`: richiede motivazione di almeno 15 caratteri e conferma esatta della fase.
- `draft`: produce `DOSSIER_INTEGRATO.md` con verbale e carta di lavoro indipendenti.
- `validate`: produce `AUDIT_QUALITY_REVIEW.md` e blocca A11 in presenza di errori.
- `approve`: verifica l'hash del dossier e produce `AUDIT_APPROVAL_RECEIPT.md`.

Il locator puo identificare una fonte del workspace, ma il repository e gli event log non devono
contenere nomi cliente, percorsi assoluti o contenuto documentale.
