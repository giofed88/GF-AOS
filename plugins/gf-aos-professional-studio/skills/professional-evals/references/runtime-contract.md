# Contratto ECC Runtime GF-AOS

## Eval Harness

Eseguire controlli deterministici su specifiche eval, skill, JSON/TOML, sintassi Python e test di
regressione. Scrivere i report fuori dalla repository. Il report conserva commit, esiti e metriche,
non stdout dei test, percorsi cliente o contenuti documentali.

Usare soltanto `PASS` e `BLOCKED` per l'esito aggregato. `PASS` non equivale ad approvazione
professionale e non autorizza azioni esterne.

## Lifecycle

- `PreCompact`: verificare `CASE_MEMORY.md`, checkpoint e massimo quattro prossime azioni;
- `PostCompact`: registrare soltanto una reference hash della sessione;
- `SessionStart`: ripristinare il bootstrap pseudonimizzato;
- `SubagentStart`: fornire modulo, stato e regole minime, mai cliente, Case ID o percorso;
- `Stop`: ricordare lo stato della memoria e l'assenza di approvazione automatica;
- `SessionEnd`: registrare la chiusura senza acquisire il transcript.

Non leggere `transcript_path`, non memorizzare prompt o output dei tool e non usare gli hook come
prova di firma, deposito, invio o completamento professionale.
