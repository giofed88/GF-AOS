---
name: context-persistence
description: Registra stato e decisioni di incarichi complessi
---

# context-persistence

Salva checkpoint nel workspace del cliente: ID incarico, periodo, ultimo aggiornamento, fonti e percorsi, decisioni, azioni aperte, prossima scadenza. Evita dati personali non necessari nei log.

Usa `strategic-context` per comprimere conversazioni lunghe nel checkpoint Markdown canonico.
Non conservare trascrizioni, ragionamento interno o dati provenienti da altri clienti.

Gli hook `PreCompact` verificano la presenza della memoria canonica senza leggere il transcript;
`SessionStart` ripristina soltanto il bootstrap minimizzato. Gli hook modificati devono essere
riesaminati e considerati attendibili dall'utente nel runtime Codex prima dell'esecuzione.
