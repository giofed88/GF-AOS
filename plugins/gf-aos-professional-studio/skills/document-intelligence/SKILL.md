---
name: document-intelligence
description: Estrae e indicizza documenti PDF, DOCX, Excel, PowerPoint, testo e immagini OCR in un workspace GF-AOS separato, preservando i file sorgente e registrando evidenze, hash, limiti e anomalie.
---

# Document Intelligence

Usa `scripts/document_intelligence.py` solo su file o cartelle autorizzati. Conserva i documenti sorgente in sola lettura e scrivi ogni risultato in un workspace separato.

## Flusso

1. Identifica cliente, incarico, ruolo, periodo e finalità dell'estrazione.
2. Esegui prima l'inventario 006A quando la popolazione documentale non è già definita.
3. Avvia l'estrazione senza OCR. Abilita `--ocr` solo per immagini o PDF da trattare separatamente quando il testo nativo non è sufficiente.
4. Controlla `document_index.json`, `document_index.md`, errori, troncamenti e documenti senza testo.
5. Collega ogni affermazione al documento originale e, quando disponibile, alla pagina, al foglio, alla cella o alla diapositiva.
6. Distingui presenza del file, contenuto estratto, calcolo, inferenza e valutazione professionale.

## Comando

```bash
python3 scripts/document_intelligence.py /percorso/fascicolo \
  --output-dir /percorso/workspace/document-intelligence
```

Per OCR facoltativo:

```bash
python3 scripts/document_intelligence.py /percorso/immagini \
  --output-dir /percorso/workspace/ocr --ocr --ocr-language ita+eng
```

## Controlli obbligatori

- Non eseguire macro, formule, collegamenti esterni o contenuti attivi.
- Conserva i limiti predefiniti per dimensione, testo estratto e archivi Office, salvo motivazione registrata.
- Non considerare l'estrazione prova di autenticità, completezza, firma o approvazione.
- Verifica sull'originale tabelle complesse, scansioni, OCR, note, commenti e impaginazione significativa.
- Non copiare dati del cliente nella repository del plugin.
- Non rinominare, spostare, sostituire o cancellare sorgenti senza il gate `AUTORIZZO MODIFICA SORGENTI`.

Leggi [schema-e-controlli.md](references/schema-e-controlli.md) quando devi interpretare il registro o integrare il motore in un workflow.
