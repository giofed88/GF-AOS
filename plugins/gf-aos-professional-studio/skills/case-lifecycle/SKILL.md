---
name: case-lifecycle
description: Inizializza, riprende, compatta, controlla e approva workspace di incarichi GF-AOS con checkpoint Markdown e stato macchina minimo. Usa quando si apre o riprende un fascicolo, si chiude una fase, si prepara la compattazione del contesto o si verifica un output prima della validazione professionale.
---

# Case lifecycle

Usare `scripts/case_lifecycle.py` per le operazioni deterministiche. Scrivere solo nel workspace
derivato indicato; non collocarlo dentro la cartella delle fonti del cliente.

## Ciclo

1. Eseguire `init` con Case ID, cliente/contesto, modulo, ruolo e periodo. Richiedere
   `--crisis-explicit` per `CRISIS_001`.
2. Aggiornare i registri Markdown del workspace durante il lavoro.
3. Prima di una compattazione o al termine di una fase, preparare una sintesi Markdown ed eseguire
   `checkpoint`. Conservare al massimo quattro prossime azioni.
4. All'avvio successivo, usare `resume`; il comando legge senza modificare.
5. Eseguire `quality` prima del verificatore finale. Trattare `BLOCKED` come blocco reale e
   `PASS CON RILIEVI` come obbligo di dichiarare i rilievi.
6. Usare `approve` soltanto dopo la frase esatta `APPROVO OUTPUT`, con nota di almeno dieci
   caratteri e artefatto già presente nel workspace.

La validazione strutturale non sostituisce l'Independent Reviewer, il Final Verifier, la firma o
il giudizio professionale. Non impostare autorizzazioni a modifiche delle fonti o azioni esterne
come effetto del lifecycle.
