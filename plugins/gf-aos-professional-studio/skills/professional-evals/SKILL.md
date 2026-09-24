---
name: professional-evals
description: Definisce e applica eval professionali GF-AOS a fascicoli, handoff e output, separando controlli deterministici, revisione indipendente e validazione umana. Usa prima di considerare completo o approvabile un incarico e dopo modifiche a skill, agenti, workflow o gate.
---

# Professional evals

Leggere `references/eval-matrix.md` e `references/runtime-contract.md`. Definire i criteri prima dell'elaborazione sostanziale e
registrare l'esito in Markdown. Preferire controlli deterministici per struttura, hash, campi,
stati e coerenza; usare Independent Reviewer per contenuto e giudizio; riservare al professionista
le conclusioni dispositive.

Eseguire `scripts/eval_harness.py` con repository, directory output esterna e data operativa dopo
modifiche a skill, agenti, hook o script. Conservare `EVAL_REPORT.md` e `EVAL_REPORT.json` come
evidenza derivata; fermarsi su `BLOCKED`.
Un test superato non autorizza pubblicazione, invio, deposito, firma o modifica delle fonti.
