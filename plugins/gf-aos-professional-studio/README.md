# GF-AOS Professional Studio v0.3.0

Plugin Codex per instradamento professionale, pianificazione, inventario documentale locale, scadenze, brief e verifica. Le 11 skill sono istruzioni operative; **nessun server MCP, collegamento Drive, automazione Telegram o scheduler è attivo in questo pacchetto**. Le integrazioni richiedono configurazione separata.

## Installazione da marketplace repository

Dopo aver caricato il contenuto di questo pacchetto nella repository `giofed88/GF-AOS`, dalla CLI Codex: `codex plugin marketplace add giofed88/GF-AOS --ref main`; quindi aprire il catalogo plugin e installare `gf-aos-professional-studio`. La repository privata deve essere accessibile all'account GitHub usato da Codex. Il solo ZIP locale non rende disponibile il marketplace GitHub.

## Inventario 006A

`python3 plugins/gf-aos-professional-studio/scripts/inventory.py /path/fascicolo --output /path/workspace/inventario.json`

Legge nomi e metadati dei file senza aprirli e scrive solo nel percorso output. Le categorie sono euristiche e richiedono revisione umana. Evitare di inserire dati dei clienti nella repository.

## Stato integrazioni

| Modulo | Stato |
| --- | --- |
| Skill Codex | Incluso |
| Scanner locale 006A | Incluso |
| Drive e fascicoli remoti | Da collegare |
| Scadenze programmate | Da collegare |
| Telegram/TaskNotify | Da collegare e verificare |
| Dashboard GF-AOS | Da integrare |

Il codice sorgente di questa versione è conservato nella repository indicata. L'installazione e le integrazioni esterne restano passaggi separati.
