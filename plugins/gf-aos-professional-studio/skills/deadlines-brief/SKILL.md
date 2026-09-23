---
name: deadlines-brief
description: Governa agenda, scadenze professionali, promemoria e brief GF-AOS senza inventare termini o inviare notifiche. Usa per registrare una scadenza da fonte verificata, validarla, generare agenda e reminder locali, preparare calendario o Telegram e produrre il brief professionale ricorrente.
---

# Scadenze e brief

Leggere `references/deadline-contract.md` e, dalla radice del plugin, usare
`scripts/deadlines.py`.

1. Predisporre una nota-fonte Markdown con fonte, regola, applicabilita e data verificata.
2. Scansionarla con `privacy-automation` e profilo `internal`.
3. Proporre il termine con alias, codice adempimento, categoria, offset Europe/Rome e reminder.
4. Riesaminare l'intero record e validare con `CONFERMO SCADENZA <DEADLINE_ID>`.
5. Generare agenda e `BOZZA PROMEMORIA` soltanto dalle scadenze validate.
6. Per calendario o Telegram passare sempre da `external-action-governance`.
7. Segnare completato solo con `CONFERMO ADEMPIMENTO <DEADLINE_ID>`.

Per il brief lunedi/mercoledi/venerdi ore 08 Europe/Rome produrre 10–15 aggiornamenti verificati
in fiscale, lavoro, crisi, revisione e contenzioso. La sintesi Telegram contiene 5–8 punti ed e
trasmessa soltanto da un servizio configurato e autorizzato. Il plugin non incorpora uno
scheduler live.
