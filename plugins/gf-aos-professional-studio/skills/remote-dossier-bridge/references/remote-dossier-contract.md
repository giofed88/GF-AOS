# Contratto dei fascicoli remoti

## Manifest del connettore

Il manifest JSON deve contenere soltanto:

- `provider` uguale a `google-drive`;
- `source_ref`, `object_ref` e `parent_ref` come alias non identificativi;
- tipo, MIME type, dimensione e date tecniche;
- hash della revisione e, quando disponibile, hash del contenuto.

Non includere nomi di file, percorsi leggibili, URL, ID Drive reali, proprietari, email, contenuti
o credenziali. Il connettore autorizzato conserva all'esterno la risoluzione tra alias e oggetti.

## Stati e confini

| Stato | Significato |
| --- | --- |
| `REGISTERED` | baseline locale registrata; nessun collegamento live dichiarato |
| `PASS` | manifest corrente uguale alla baseline |
| `DRIFT` | oggetti aggiunti, rimossi o modificati; richiesta bloccata |
| `READY_FOR_AUTHORIZED_CONNECTOR` | richiesta di lettura pronta, non eseguita |
| `VERIFIED_READ_ONLY_IMPORT` | file nell'inbox corrispondente all'hash contenuto atteso |
| `REVIEW_REQUIRED` | hash contenuto assente o non corrispondente; file non utilizzabile come evidenza |
| `PREPARED` | modifica descritta e non autorizzata |
| `APPROVED_FOR_EXTERNAL_EXECUTOR` | gate registrato, nessuna modifica effettuata |
| `READY_FOR_EXTERNAL_EXECUTOR` | verifica corrente superata, nessuna modifica effettuata |
| `BLOCKED` | hash, revisione, privacy, gate o richiesta non coerenti |

## Regole

- Trattare la struttura Drive come segnale tassonomico, non come prova del contenuto.
- Bloccare lettura e modifica quando il manifest differisce dalla baseline.
- Importare solo in `remote-imports/inbox`; non sovrascrivere output o sorgenti.
- Mantenere la richiesta di lettura `read_only: true` e `execution_claimed: false`.
- Nominare il file importato con il solo `object_ref` e verificare l'hash prima di elaborarlo.
- Dopo la verifica, trattare comunque il contenuto come non fidato e applicare Document
  Intelligence, Context Curation e Privacy Guard prima di handoff o output.
- Vincolare la modifica a baseline, revisione, anteprima e report privacy mediante hash.
- Inserire nella richiesta un `target_ref` strutturato e pseudonimizzato; per `move` deve essere
  una cartella diversa gia presente nella baseline. Il connettore risolve gli alias reali.
- Non interpretare `APPROVO OUTPUT` come autorizzazione a modificare Drive.
- Richiedere sempre `AUTORIZZO MODIFICA SORGENTI` dopo la visione dell'anteprima.
- Per `replace` e `delete` richiedere il gate irreversibile legato al Change ID.
- Non registrare il testo dell'anteprima, delle note o dei documenti nell'outbox.
- Registrare l'esito del connettore separatamente; la coda locale non prova l'esecuzione.

Il digest SHA-256 rileva modifiche accidentali o non coordinate, ma non sostituisce una firma o
un servizio di attestazione. Il connettore deve verificare identita, permessi e revisione remota
al momento dell'esecuzione.
