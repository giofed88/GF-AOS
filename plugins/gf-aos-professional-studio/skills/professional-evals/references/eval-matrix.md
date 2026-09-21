# Matrice eval GF-AOS

## Capability eval

| Controllo | Grader | Criterio di superamento |
| --- | --- | --- |
| Routing | Deterministico + reviewer | Un modulo principale; workstream e ruoli distinti |
| Evidenze | Deterministico + reviewer | Locator presenti; fatto distinto da inferenza e giudizio |
| Fonti | Researcher + reviewer | Ente, data/versione, accesso, proposizione e applicabilita |
| Coerenza output | Independent Reviewer | Nessuna conclusione non supportata; limiti visibili |
| Gate finale | Deterministico + umano | Artefatto, hash, nota e frase `APPROVO OUTPUT` |

## Regression eval

- Le fonti del cliente restano in sola lettura.
- `CRISIS_001` non si attiva implicitamente.
- Revisione, collegio, ODV, CTP, CTU e contenzioso non vengono fusi.
- Gli output non approvati mostrano `BOZZA DA VALIDARE`.
- Le azioni esterne restano separate dalla validazione dell'output.
- Il checkpoint contiene al massimo quattro prossime azioni e non conserva il transcript.

## Esito

Usare soltanto `PASS`, `PASS CON RILIEVI` o `BLOCKED`. Collegare ogni rilievo a una prova o a un
controllo mancante. `PASS` indica idoneita tecnica alla validazione, non approvazione professionale.
