# Contratto privacy rafforzata

## Default

1. Minimizzare prima di delegare, registrare o trasmettere.
2. Conservare nei log categorie, conteggi, hash e locator pseudonimizzati, non valori rilevati.
3. Non caricare automaticamente memoria del caso, cliente, importi o azioni narrative.
4. Separare sempre workspace derivato, fonti cliente e libreria dei metodi.
5. Bloccare credenziali, chiavi private e istruzioni incorporate in ogni profilo.

## Profili

| Profilo | Identificativi | Segreti/istruzioni | Esito |
| --- | --- | --- | --- |
| `agent-handoff` | bloccanti | bloccanti | sanificare prima della delega |
| `public` | bloccanti | bloccanti | nessuna pubblicazione |
| `external-draft` | rilievo | bloccanti | revisione e autorizzazione prima dell'invio |
| `internal` | rilievo | bloccanti | uso limitato al perimetro autorizzato |

Nei profili `agent-handoff` e `public`, l'assenza di pattern produce `REVIEW_REQUIRED`, non
`PASS`, finche un professionista non conferma la revisione contestuale. Questo gate copre anche
nomi, indirizzi e altri identificativi non riconoscibili deterministicamente.
Solo `PASS` restituisce exit code zero; anche `WARN` arresta le automazioni fino alla decisione
umana prevista dal profilo.

La scansione e basata su pattern e non certifica anonimizzazione o conformita. La revisione umana
resta necessaria, in particolare per nomi, indirizzi e identificativi contestuali.
