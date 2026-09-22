# Contratto di context curation

## Input

- Un workspace GF-AOS valido con `CASE_STATE.json`.
- Da uno a venti file `.md` o `.txt` interni al workspace.
- Una query riferita al solo compito delegato.
- Un budget da 2.000 a 50.000 caratteri per l'intero pacchetto.

## Output

`CONTEXT_PACKET.md` contiene identita minima del caso, query, hash delle sorgenti derivate,
estratti con locator, blocchi esclusi, riduzioni applicate e limiti. Non contiene il transcript.

## Regole

1. Preferire il minimo contesto sufficiente; non inoltrare interi fascicoli per comodita.
2. Ridurre per impostazione predefinita email, IBAN, codice fiscale, partita IVA e telefoni.
3. Escludere dal testo delegato le possibili istruzioni incorporate e conservarne solo locator e tipo.
4. Non usare il pacchetto come prova di completezza o come sostituto della fonte.
5. Non riutilizzare un pacchetto per un altro cliente, modulo o finalita.
6. Rigenerare il pacchetto quando cambia una sorgente: gli hash rendono visibile la variazione.
7. Riesaminare manualmente il pacchetto: la riduzione a pattern non riconosce tutti gli identificativi contestuali.
8. Considerare `--max-chars` come limite dell'intero pacchetto, inclusi metadati e avvertenze.
