# Contratto del cruscotto GF-AOS

## Perimetro

Il cruscotto e un indice Markdown derivato e read-only. Aggrega workspace gia inizializzati senza
modificarli. Non sostituisce il fascicolo, la fonte, il controllo qualita o il giudizio
professionale.

## Manifest effimero

Accettare un JSON con `schema_version: 1` e una lista `workspaces`. Ogni elemento contiene
esattamente:

- `workspace_ref`: codice non verbale `CASE_` + 1–4 lettere + almeno 2 cifre, per esempio
  `CASE_A001`;
- `path`: percorso assoluto del workspace.

Non copiare il percorso nel cruscotto o nello snapshot. Conservare soltanto un'impronta SHA-256.
Rifiutare campi aggiuntivi, duplicati, link simbolici, identificativi reali e dashboard collocate
dentro un fascicolo.

## Dati ammessi

- alias workspace, modulo, periodo e stato GF-AOS;
- conteggi di blocker e prossime azioni, mai il loro testo;
- conteggi di scadenze, reminder, task e azioni esterne;
- stato strutturale e anomalie di integrita;
- impronte non reversibili degli artefatti governati.

Non esportare `case_id`, `client_context`, percorsi, nomi file originari, target, payload, fonti,
note, importi o contenuti dei documenti.

## Task

Usare soltanto i codici task e owner del vocabolario incorporato, priorita, data e stato. Non
accettare nomi o descrizioni libere negli alias. Stati ammessi: `OPEN`,
`IN_PROGRESS`, `WAITING`, `DONE`. Non riaprire automaticamente un task `DONE`. Ogni transizione
richiede `CONFERMO TASK <TASK_ID> <STATUS>` e rende il dashboard stale fino alla rigenerazione.

## Integrita

`verify` deve controllare hash del Markdown, snapshot, manifest e impronte correnti dei workspace.
Una modifica successiva produce `BLOCKED_LIVE`. La rigenerazione richiede `--replace` e
`RIGENERO DASHBOARD`.

## Limite operativo

Il cruscotto non invia notifiche, non crea eventi, non completa scadenze, non modifica Drive e
non prova consegna, deposito o sincronizzazione.
