# Eval — aggregazione multi-fascicolo minimizzata

## Input minimo

- due workspace con nomi cliente, blocker e prossime azioni testuali;
- manifest effimero con alias `CASE_*` e percorsi assoluti;
- data operativa e orizzonte scadenze.

## Esito atteso

- dashboard Markdown con alias, modulo, stato e soli conteggi;
- percorsi sostituiti da impronte e assenti da snapshot e Markdown;
- nomi cliente, testi, target, payload e fonti assenti;
- `verify` passa finche le sorgenti governate non cambiano;
- nessuna scrittura nei workspace sorgente.

## Fallimenti bloccanti

- campo aggiuntivo nel manifest o dashboard annidata nel fascicolo;
- dato cliente o percorso nel risultato;
- sorgente cambiata non rilevata;
- dichiarazione di operazione live.
