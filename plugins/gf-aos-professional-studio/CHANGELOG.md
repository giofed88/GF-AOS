# Changelog

## 0.4.0
- Motore Document Intelligence locale per PDF, DOCX, XLSX/XLSM, PPTX, testo e CSV.
- OCR immagini facoltativo tramite Tesseract, disattivato per impostazione predefinita.
- Registro strutturato con SHA-256, locator del testo, limiti, errori e troncamenti.
- Controlli su dimensione, decompressione Office e lingue OCR effettivamente disponibili.
- Nuova skill `document-intelligence` e integrazione nel flusso 006A/workspace.
- Test automatici multi-formato e controllo di immutabilità dei sorgenti.

## 0.3.0
- Marketplace Codex e manifest validabile.
- Undici skill professionali, comprese orchestrazione e scadenze/brief.
- Inventario locale 006A in sola lettura con report JSON e Markdown.
- Stato delle integrazioni dichiarato senza endpoint o credenziali fittizie.

La v0.2 è stata prodotta in una precedente conversazione, ma il relativo ZIP non era accessibile al momento della pubblicazione. La v0.3 ripristina come pacchetto completo le funzioni documentate della v0.2 e aggiunge i componenti qui elencati; una verifica di differenza file per file richiederà il pacchetto precedente.
