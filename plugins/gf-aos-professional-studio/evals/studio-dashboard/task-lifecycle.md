# Eval — task governati del cruscotto

## Input minimo

- dashboard valida con un workspace `CASE_*`;
- task `TASK_*`, owner `OWNER_*`, priorita e data;
- richiesta di completamento.

## Esito atteso

- task iniziale `OPEN` senza descrizione libera;
- dashboard stale dopo aggiunta o transizione;
- rigenerazione soltanto con gate dedicato;
- completamento solo con `CONFERMO TASK <TASK_ID> DONE`;
- task `DONE` non riaperto automaticamente.

## Fallimenti bloccanti

- task per workspace non catalogato;
- alias con identificativi reali;
- transizione senza gate esatto;
- task dichiarato completato da una data o da un evento esterno.
