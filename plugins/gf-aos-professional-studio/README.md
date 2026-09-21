# GF-AOS Professional Studio v0.7.0

Plugin Codex per instradamento professionale, orchestrazione agentica, pianificazione, inventario e Document Intelligence locale, scadenze, brief e verifica. **Nessun server MCP, collegamento Drive, automazione Telegram o scheduler è attivo in questo pacchetto**. Le integrazioni richiedono configurazione separata.

## Agent Core

La v0.5 adatta al lavoro GF-AOS i pattern utili di Everything Claude Code: ruoli stretti,
esplorazione read-only, ricerca separata, revisione indipendente, verifica finale e compattazione
del contesto. La repository include la configurazione CLI in `.codex/config.toml` e otto profili
in `.codex/agents/`. I modelli non sono fissati: viene ereditato quello selezionato in Codex.

Le skill `agent-orchestrator` e `strategic-context` mantengono lo stesso metodo anche negli
ambienti che non caricano automaticamente i profili repository-local. Gli agenti restituiscono
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

L'hook Codex `SessionStart` e read-only: carica `CASE_MEMORY.md` soltanto quando la variabile
`GF_AOS_WORKSPACE` indica esplicitamente il workspace. L'attivazione degli hook resta soggetta al
controllo di fiducia di Codex. Nessun dato cliente viene scritto nella repository del plugin.

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
| Ripresa SessionStart | Inclusa, opt-in tramite `GF_AOS_WORKSPACE` |
| Workflow pack professionali ed eval specifici | Inclusi |
| Drive e fascicoli remoti | Da collegare |
| Scadenze programmate | Da collegare |
| Telegram/TaskNotify | Da collegare e verificare |
| Dashboard GF-AOS | Da integrare |

Il codice sorgente di questa versione è conservato nella repository indicata. L'installazione e le integrazioni esterne restano passaggi separati.
