---
name: external-action-governance
description: Prepara e governa richieste GF-AOS per email, PEC, Telegram personale, calendario, condivisioni Drive e pubblicazioni senza eseguirle. Usa dopo la redazione di un artefatto e prima di qualunque invio, condivisione, deposito o pubblicazione per vincolare privacy, hash, destinatario pseudonimizzato e approvazione professionale.
---

# Governed external actions

Leggere `references/external-action-contract.md` e usare `scripts/external_actions.py`.

1. Scansionare il solo payload con `privacy-automation` e il profilo richiesto.
2. Preparare l'azione con un `target-ref` pseudonimizzato, mai con indirizzo email o nominativo.
3. Riesaminare Action ID, tipo, payload e privacy report nel workspace autorizzato.
4. Approvare con nota e frase esatta `APPROVO AZIONE ESTERNA <ACTION_ID>`.
5. Se il profilo `external-draft` contiene dati necessari, aggiungere nota e
   `APPROVO DATI NECESSARI`.
6. Verificare la richiesta prima di affidarla a un esecutore esterno autorizzato.

Il risultato massimo del plugin e `READY_FOR_EXTERNAL_EXECUTOR`. Non significa inviato,
pubblicato, condiviso, depositato o consegnato. Il destinatario reale deve essere risolto e
verificato al momento dell'esecuzione esterna.
