# Eval — ECC Runtime harness

## Input minimo

- repository GF-AOS valida;
- directory di report esterna;
- data operativa esplicita.

## Esito atteso

- specifiche eval, skill, strutture JSON/TOML e sintassi Python controllate;
- regressione automatica eseguita per impostazione predefinita;
- report JSON e Markdown con commit, metriche ed esito aggregato;
- stdout dei test e contenuti dei fascicoli esclusi dal report.

## Fallimenti bloccanti

- report scritto dentro la repository;
- singolo controllo fallito rappresentato come `PASS`;
- test omessi silenziosamente nel flusso ordinario;
- `PASS` presentato come autorizzazione esterna.
