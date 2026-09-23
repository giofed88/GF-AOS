# Contratto delle azioni esterne

## Stati

| Stato | Significato |
| --- | --- |
| `PREPARED` | payload e report coerenti, approvazione assente |
| `DATA_REVIEW_REQUIRED` | dati rilevati e necessita da approvare |
| `APPROVED_FOR_DISPATCH` | gate registrati, nessuna esecuzione effettuata |
| `READY_FOR_EXTERNAL_EXECUTOR` | verifica corrente superata, nessuna consegna dichiarata |
| `BLOCKED` | hash, privacy, stato o artefatto non coerente |

## Vincoli

- Conservare il destinatario come alias non identificativo; risolverlo soltanto nell'app esterna.
- Legare approvazione e richiesta agli hash di payload e report privacy.
- Legare l'approvazione al digest canonico di Action ID, tipo, alias target, payload e report.
- Bloccare sempre segreti e istruzioni incorporate.
- Per `linkedin-public` e `website-public` richiedere `public`, `PASS` e revisione contestuale.
- Per azioni dirette accettare `WARN` soltanto con nota e `APPROVO DATI NECESSARI`.
- Non includere il contenuto del payload nel registro o nell'output console.
- Non interpretare approvazione dell'output professionale come approvazione dell'azione esterna.
- Non dichiarare invio o consegna senza ricevuta verificabile prodotta dall'esecutore esterno.
- Calcolare `BLOCKED_LIVE` nello stato quando la richiesta approvata non supera piu la verifica.

La coda non incorpora credenziali e non configura provider. Email, PEC, Telegram, calendario,
Drive e piattaforme editoriali restano disabilitati finche un connettore autorizzato non esegue
la richiesta e restituisce un esito separato.
