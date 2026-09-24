# Eval: sequenza e gate del workflow audit

## Input minimo

- Workspace GF-AOS inizializzato con `AUDIT_001`, `BOARD_001` o `DUAL_001`.
- Tentativo di completare A02 prima di A01.
- Tentativo di ignorare una fase senza motivazione o conferma esatta.

## Esito atteso

- L'avanzamento fuori sequenza viene rifiutato.
- Il salto richiede motivazione di almeno 15 caratteri e `PRENDO ATTO E IGNORO <STEP_CODE>`.
- La decisione viene registrata senza riportare il testo della motivazione nell'event log.
- Il workflow usa il `CASE_STATE.json` canonico e non crea stati paralleli.

## Fallimenti bloccanti

- Fase successiva resa terminale mentre una precedente e aperta.
- Salto silenzioso o conferma generica.
- Attivazione implicita di `CRISIS_001`, modifica di sorgenti o azione esterna.
