# GF-AOS Professional Studio v0.13.0

Plugin Codex per instradamento professionale, orchestrazione agentica, pianificazione, inventario e Document Intelligence locale, scadenze governate, brief e verifica. **Nessun server MCP, connettore Drive live, automazione Telegram o scheduler live è attivo in questo pacchetto**. Le integrazioni richiedono configurazione separata.

## Agent Core

La v0.5 adatta al lavoro GF-AOS i pattern utili di Everything Claude Code: ruoli stretti,
esplorazione read-only, ricerca separata, revisione indipendente, verifica finale e compattazione
del contesto. La repository include la configurazione CLI in `.codex/config.toml` e otto profili
in `.codex/agents/`. I modelli non sono fissati: viene ereditato quello selezionato in Codex.

Le skill `agent-orchestrator` e `strategic-context` mantengono lo stesso metodo anche negli
ambienti che non caricano automaticamente i profili repository-local. I quattordici profili
includono anche Privacy Guardian, External Action Controller, Remote Dossier Controller e Deadline Controller. Gli agenti restituiscono
handoff Markdown; il coordinatore conserva il controllo delle scritture e l'utente mantiene
l'approvazione professionale.

## Lifecycle & Quality Engine

La v0.6 aggiunge un workspace riprendibile senza salvare il transcript. Il motore crea stato
macchina minimo, registri Markdown, checkpoint versionati, coda con massimo quattro azioni e un
report qualita con esito `PASS`, `PASS CON RILIEVI` o `BLOCKED`.
Il gate finale registra anche `APPROVAL_RECEIPT.md` con artefatto, hash, nota e data UTC, senza
presentarlo come firma digitale, deposito o trasmissione.

```bash
python3 plugins/gf-aos-professional-studio/scripts/case_lifecycle.py init /path/workspace \
  --case-id CASE-001 --client "Cliente" --module AUDIT_001 --role "Revisore" --period 2026

python3 plugins/gf-aos-professional-studio/scripts/case_lifecycle.py checkpoint /path/workspace \
  --summary-file /path/sintesi.md --status "In corso" --next-action "Acquisire il libro inventari"

python3 plugins/gf-aos-professional-studio/scripts/case_lifecycle.py quality /path/workspace
```

L'hook Codex `SessionStart` e read-only e minimizzato: quando `GF_AOS_WORKSPACE` indica
esplicitamente il workspace, restituisce soltanto impronta pseudonimizzata, modulo, stato,
presenza del checkpoint e conteggi. Non carica automaticamente cliente, Case ID, memoria o testo
delle azioni. L'attivazione degli hook resta soggetta al controllo di fiducia di Codex.

## Professional Workflow Packs

La v0.7 aggiunge piani operativi riutilizzabili e distinti per revisione legale, collegio,
fiscale, lavoro, contenzioso tributario e perizie. Le istruzioni specialistiche sono riferimenti
Markdown caricati per famiglia: il contesto non viene occupato dai workflow non pertinenti.

```bash
python3 plugins/gf-aos-professional-studio/scripts/workflow_packs.py list
python3 plugins/gf-aos-professional-studio/scripts/workflow_packs.py plan /path/workspace
python3 plugins/gf-aos-professional-studio/scripts/workflow_packs.py validate /path/workspace
```

`plan` usa il `lead_module` di `CASE_STATE.json`, crea piano, registro output e indice carte di
lavoro e rifiuta di sovrascrivere file esistenti. `validate` applica l'eval specifico del modulo.
I pack non includono `CRISIS_001` o `ODV_001` e non li attivano per analogia.

## Context Curation & Confidentiality Guard

La v0.8 prepara pacchetti Markdown mirati prima della delega agli agenti. Le sorgenti devono
essere indicate esplicitamente e trovarsi nel workspace; il motore seleziona soltanto i paragrafi
pertinenti alla query, conserva locator e hash, riduce gli identificativi e isola i blocchi che
tentano di impartire istruzioni al modello.

```bash
python3 plugins/gf-aos-professional-studio/scripts/context_curator.py /path/workspace \
  --source document-intelligence/registro-inventario.md \
  --source EVIDENZE.md \
  --query "valutazione rimanenze obsolescenza slow moving" \
  --max-chars 12000
```

La riduzione `standard` maschera email, IBAN, codice fiscale e partita IVA. L'opzione
`--redaction none` va usata soltanto quando l'identita e necessaria al compito e il destinatario
e autorizzato. Il pacchetto derivato non sostituisce la fonte e non prova la completezza.

## Governed Learning

La v0.9 conserva procedure riutilizzabili soltanto dopo la chiusura approvata del fascicolo.
Non registra automaticamente transcript o tool call: il professionista predispone una breve
lezione sanificata, il Method Curator propone un candidato e la promozione richiede un gate umano.

```bash
python3 plugins/gf-aos-professional-studio/scripts/governed_learning.py propose /path/workspace \
  --lesson-file /path/lezione-sanificata.md \
  --title "Verificare la quadratura prima della conclusione" \
  --trigger "Quando una carta di lavoro contiene totali derivati"

python3 plugins/gf-aos-professional-studio/scripts/governed_learning.py promote /path/workspace \
  --candidate learning/candidates/<method-id>.md \
  --library /path/gf-aos-method-library \
  --note-file /path/nota.md --confirmation "APPROVO METODO"
```

La libreria conserva modulo, ambito, confidenza e hash delle evidenze approvate, non clienti o
Case ID. L'eventuale trasformazione di un metodo in skill o agente resta una modifica separata.

## Privacy-first Automation Guard

La v0.10 estende la riservatezza a bootstrap, handoff, bozze esterne, pubblicazioni, log e
controllo delle fonti. I report conservano categorie, conteggi e locator pseudonimizzati: non
riproducono i valori rilevati, i nomi dei file o i percorsi assoluti.

```bash
python3 plugins/gf-aos-professional-studio/scripts/privacy_guard.py scan /path/workspace \
  --file CONTEXT_PACKET.md --profile agent-handoff

python3 plugins/gf-aos-professional-studio/scripts/privacy_guard.py snapshot /path/workspace \
  --source-root /path/fonti-cliente

python3 plugins/gf-aos-professional-studio/scripts/privacy_guard.py verify /path/workspace \
  --source-root /path/fonti-cliente
```

I profili `agent-handoff` e `public` bloccano gli identificativi rilevati; `external-draft` e
`internal` li segnalano come `WARN`. Segreti e istruzioni incorporate sono sempre bloccanti.
Anche senza pattern, `agent-handoff` e `public` restituiscono `REVIEW_REQUIRED` finche la
revisione contestuale non viene confermata con `--review-confirmation "CONFERMO REVISIONE PRIVACY"`
e `--replace`. Solo `PASS` restituisce exit code zero; anche `WARN` arresta il flusso automatico.
La scansione e euristica e non certifica anonimizzazione o conformita. `PASS` non autorizza
invio, pubblicazione, deposito, firma o modifica delle fonti.

## Governed External Action Queue

La v0.11 prepara richieste controllate per email, PEC, Telegram personale, calendario,
condivisioni Drive e pubblicazioni. Il plugin non esegue queste azioni: lega la richiesta agli
hash del payload e del report privacy, usa un alias non identificativo del destinatario e richiede
un gate distinto dall'approvazione professionale dell'elaborato.

```bash
python3 plugins/gf-aos-professional-studio/scripts/external_actions.py prepare /path/workspace \
  --kind email --target-ref CLIENTE_REFERENTE --payload outputs/comunicazione.md

python3 plugins/gf-aos-professional-studio/scripts/external_actions.py approve /path/workspace \
  --action-id EA-YYYYMMDD-XXXXXXXX --note-file /path/nota.md \
  --confirmation "APPROVO AZIONE ESTERNA EA-YYYYMMDD-XXXXXXXX"

python3 plugins/gf-aos-professional-studio/scripts/external_actions.py verify /path/workspace \
  --action-id EA-YYYYMMDD-XXXXXXXX
```

Se il report `external-draft` contiene identificativi necessari, l'approvazione richiede anche
una nota e `APPROVO DATI NECESSARI`. L'outbox resta `BOZZA RICHIESTA DI INVIO`; lo stato
`READY_FOR_EXTERNAL_EXECUTOR` non prova invio o consegna e non contiene credenziali del provider.

## Governed Remote Dossier Bridge

La v0.12 collega logicamente i fascicoli Google Drive senza incorporare credenziali o chiamate
API. Un connettore autorizzato produce un manifest pseudonimizzato: il plugin accetta alias,
metadati tecnici e hash, ma rifiuta nomi, URL e ID reali del provider. La baseline consente di
rilevare aggiunte, rimozioni e revisioni mutate prima di qualunque acquisizione.

```bash
python3 plugins/gf-aos-professional-studio/scripts/remote_dossiers.py register /path/workspace \
  --manifest /path/connector-manifest.json

python3 plugins/gf-aos-professional-studio/scripts/remote_dossiers.py verify /path/workspace \
  --manifest /path/connector-manifest.json

python3 plugins/gf-aos-professional-studio/scripts/remote_dossiers.py request-read /path/workspace \
  --manifest /path/connector-manifest.json --object-ref DOCUMENTO_01

python3 plugins/gf-aos-professional-studio/scripts/remote_dossiers.py verify-import /path/workspace \
  --request-id RR-YYYYMMDD-XXXXXXXX --object-ref DOCUMENTO_01 \
  --file remote-imports/inbox/DOCUMENTO_01.pdf
```

Le richieste di lettura restano `BOZZA RICHIESTA LETTURA`, sono read-only e indicano come inbox
`remote-imports/inbox`. Un file e `VERIFIED_READ_ONLY_IMPORT` soltanto quando nome pseudonimizzato
e hash corrispondono alla richiesta; altrimenti resta `REVIEW_REQUIRED`. Per rename, move,
aggiornamento metadati, sostituzione o eliminazione si
deve predisporre un'anteprima con impatto e rollback, scansionarla con il profilo `internal` e
usare `AUTORIZZO MODIFICA SORGENTI`. `replace` e `delete` richiedono inoltre
`AUTORIZZO OPERAZIONE IRREVERSIBILE <CHANGE_ID>`. Anche dopo i gate, l'esecuzione appartiene a un
connettore esterno autorizzato e deve verificare identita, permessi e revisione corrente.

## Governed Deadline and Reminder Engine

La v0.13 introduce un registro locale delle scadenze con fonte verificabile, applicabilita,
fuso `Europe/Rome`, conferma umana e controllo di integrita. Il motore non contiene calendari
fiscali precompilati e non inventa termini: ogni scadenza nasce da una nota fonte interna,
associata a un report Privacy Guard valido.

```bash
python3 plugins/gf-aos-professional-studio/scripts/deadlines.py propose /path/workspace \
  --subject-ref CLIENTE_01 --obligation-code ADEMPIMENTO_01 --category fiscal \
  --due-at 2026-11-30T18:00:00+01:00 --source-note fonte.md \
  --privacy-report PRIVACY_REPORT.md

python3 plugins/gf-aos-professional-studio/scripts/deadlines.py validate /path/workspace \
  --deadline-id DL-YYYYMMDD-XXXXXXXX --note-file /path/validazione.md \
  --confirmation "CONFERMO SCADENZA DL-YYYYMMDD-XXXXXXXX"

python3 plugins/gf-aos-professional-studio/scripts/deadlines.py queue /path/workspace \
  --as-of 2026-11-01 --horizon-days 30 --channel calendar
```

Solo una scadenza `VALIDATED` puo generare bozze reminder. La coda contiene riferimenti
pseudonimizzati e resta `BOZZA PROMEMORIA`: ogni payload deve poi attraversare Privacy Guard e
il gate delle azioni esterne. Nessun evento di calendario, messaggio Telegram o adempimento
viene eseguito o dichiarato automaticamente.

## Installazione da marketplace repository

Dopo aver caricato il contenuto di questo pacchetto nella repository `giofed88/GF-AOS`, dalla CLI Codex: `codex plugin marketplace add giofed88/GF-AOS --ref main`; quindi aprire il catalogo plugin e installare `gf-aos-professional-studio`. La repository privata deve essere accessibile all'account GitHub usato da Codex. Il solo ZIP locale non rende disponibile il marketplace GitHub.

## Inventario 006A

`python3 plugins/gf-aos-professional-studio/scripts/inventory.py /path/fascicolo --output /path/workspace/inventario.json`

Legge nomi e metadati dei file senza aprirli e scrive solo nel percorso output. Le categorie sono euristiche e richiedono revisione umana. Evitare di inserire dati dei clienti nella repository.

## Document Intelligence

`python3 plugins/gf-aos-professional-studio/scripts/document_intelligence.py /path/fascicolo --output-dir /path/workspace/document-intelligence`

Estrae PDF, DOCX, XLSX/XLSM, PPTX, TXT, Markdown e CSV in un workspace separato e normalizza il testo in file Markdown. Per le immagini l'OCR è facoltativo con `--ocr` e richiede Tesseract. Il registro conserva hash SHA-256, metodo, anomalie e locator del testo. I sorgenti non vengono modificati; formule, macro, firme e collegamenti non vengono eseguiti o validati.

## Formato canonico

GF-AOS preferisce Markdown UTF-8 per bozze, registri, note, checklist, sintesi e passaggi intermedi. JSON resta riservato allo stato macchina; DOCX, PDF, XLSX e PPTX vengono prodotti quando firma, stampa, formule, tabelle operative o presentazione richiedono il formato specifico.

Dipendenze di estrazione: `pypdf`, `python-docx`, `openpyxl` e `python-pptx`. Il motore registra un errore per il singolo documento quando una dipendenza non è disponibile, senza alterare gli altri file.

## Stato integrazioni

| Modulo | Stato |
| --- | --- |
| Skill Codex | Incluso |
| Scanner locale 006A | Incluso |
| Document Intelligence | Incluso |
| Agent Orchestrator e handoff Markdown | Incluso |
| Profili multi-agente Codex CLI | Inclusi nella repository |
| Memoria strategica per caso | Inclusa come template Markdown |
| Lifecycle, checkpoint e quality report | Incluso |
| Ripresa SessionStart minimizzata | Inclusa, opt-in tramite `GF_AOS_WORKSPACE` |
| Workflow pack professionali ed eval specifici | Inclusi |
| Context Curator e Confidentiality Guard | Inclusi |
| Governed Learning e Method Curator | Inclusi |
| Privacy Guard per handoff, output e fonti | Incluso |
| Coda governata delle azioni esterne | Inclusa, senza esecuzione automatica |
| Drive e fascicoli remoti | Ponte governato incluso; connettore live da configurare e verificare |
| Scadenze programmate | Motore governato e coda reminder inclusi; scheduler live da collegare |
| Telegram/TaskNotify | Outbox pronta; connettore da collegare e verificare |
| Dashboard GF-AOS | Da integrare |

Il codice sorgente di questa versione è conservato nella repository indicata. L'installazione e le integrazioni esterne restano passaggi separati.
