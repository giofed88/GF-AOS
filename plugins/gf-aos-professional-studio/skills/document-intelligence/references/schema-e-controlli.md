# Schema e controlli Document Intelligence

## Output

Il workspace contiene:

- `document_index.json`: registro strutturato;
- `document_index.md`: riepilogo leggibile;
- `markdown/*.md`: testo estratto in Markdown, identificato da nome normalizzato e prefisso hash.

Ogni record conserva percorso relativo, tipo, dimensione, ultima modifica, SHA-256, stato, estrattore, numero di caratteri, formato e locator del testo, troncamento, dettagli tecnici e anomalie.

## Stati

| Stato | Significato | Azione |
| --- | --- | --- |
| `estratto` | Il motore ha prodotto testo o ha completato l'estrattore | Verificare contenuto e locator |
| `ocr_non_richiesto` | Immagine rilevata con OCR disattivato | Valutare OCR autorizzato |
| `errore` | Dipendenza, formato o documento non elaborabile | Leggere `issues` e controllare l'originale |

## Limiti per formato

- PDF: il testo può avere ordine diverso dalla resa visiva; firme e allegati non sono validati.
- DOCX: testo e tabelle sono estratti; revisioni, commenti, intestazioni e oggetti incorporati possono richiedere controllo dedicato.
- XLSX/XLSM: valori e formule sono letti come contenuto; formule e macro non vengono eseguite.
- PPTX: testo e tabelle sono estratti; grafici, SmartArt, note e ordine visivo richiedono controllo.
- OCR: il risultato è probabilistico e deve essere confrontato con la scansione.

Il motore applica limiti predefiniti alla dimensione del file, al testo estratto e alla decompressione degli archivi Office. Un superamento produce un errore registrato; non autorizza a disabilitare il controllo senza una motivazione legata all'incarico.

## Integrazione GF-AOS

Usa l'hash per verificare che l'evidenza analizzata non sia cambiata. Conserva la data di estrazione e registra nel case state documenti mancanti, errori, troncamenti e verifiche manuali. Non trasferire il testo estratto fuori dal workspace senza una distinta autorizzazione.
