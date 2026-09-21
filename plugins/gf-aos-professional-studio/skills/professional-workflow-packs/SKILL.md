---
name: professional-workflow-packs
description: Avvia e governa workflow GF-AOS riutilizzabili per revisione, collegio, fiscale, lavoro, contenzioso tributario e perizie, con fasi, output ed eval specifici in Markdown.
---

# Professional Workflow Packs

Seleziona un solo modulo principale e conserva workstream distinti quando l'incarico attraversa
piu specializzazioni. Leggi `references/workflow-contract.md`, quindi soltanto il riferimento della
famiglia scelta:

| Famiglia | Riferimento |
| --- | --- |
| `AUDIT_001`, `BOARD_001`, `DUAL_001` | `references/revisione-governance.md` |
| `ACC_CAP_001`, `ACC_PART_001`, `ACC_SOLE_001`, `ACC_PERSON_001`, `ACC_NPO_001` | `references/fiscale.md` |
| `LAB_001`, `LAB_CALC_001` | `references/lavoro.md` |
| `TAX_LIT_001` | `references/contenzioso.md` |
| `CTP_001`, `CTU_001`, `VALUATION_001`, `DUE_DIL_001`, `CONDO_REVIEW_001` | `references/perizie.md` |

Per un workspace gia inizializzato con `case-lifecycle`, creare il piano senza toccare i sorgenti:

```bash
python3 scripts/workflow_packs.py plan /path/workspace
python3 scripts/workflow_packs.py validate /path/workspace
```

`plan` rifiuta ogni sovrascrittura. `validate` produce `WORKFLOW_EVAL.md` con esito `PASS`,
`PASS CON RILIEVI` o `BLOCKED`. L'esito e strutturale e non approva l'output.

`CRISIS_001` e `ODV_001` non appartengono a questi pack. Non attivarli per analogia.
