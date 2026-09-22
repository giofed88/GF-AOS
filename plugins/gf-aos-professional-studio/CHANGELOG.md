# Changelog

## 0.9.0
- Governed Learning da fascicoli approvati, senza osservazione automatica dei transcript.
- Nuovo Method Curator read-only per metodi atomici e sanificati.
- Candidati Markdown `DA VALIDARE` separati dalla libreria riutilizzabile.
- Gate `APPROVO METODO` per la promozione e `CONFERMO METODO` per il rinforzo.
- Blocco su dati identificativi, Case ID, cliente e istruzioni incorporate.
- Confidenza da 0,50 a 0,90 basata su hash distinti di artefatti approvati.
- Nessuna modifica automatica di skill, agenti, fonti o sistemi esterni.

## 0.8.0
- Context Curator agentico read-only per deleghe con contesto minimo e tracciabile.
- Generatore di `CONTEXT_PACKET.md` con query, locator, hash e budget di caratteri.
- Riduzione predefinita di email, IBAN, codice fiscale e partita IVA negli handoff.
- Isolamento dei blocchi che tentano di impartire istruzioni o richiedere segreti.
- Sorgenti esplicite, interne al workspace, senza scansione indiscriminata del fascicolo.
- Due eval di regressione per riservatezza e prompt injection documentale.

## 0.7.0
- Professional Workflow Packs distinti per revisione, collegio, fiscale, lavoro, contenzioso e perizie.
- Un unico skill-router leggero con riferimenti Markdown caricati per la sola famiglia selezionata.
- Generatore sicuro di `WORKFLOW_PLAN.md`, `OUTPUT_REGISTER.md` e `WORKING_PAPERS_INDEX.md`.
- Validatore strutturale con esiti `PASS`, `PASS CON RILIEVI` e `BLOCKED`.
- Sedici moduli professionali coperti senza attivazione implicita di `CRISIS_001` o `ODV_001`.
- Sei casi eval Markdown con input minimo, esito atteso e fallimenti bloccanti.
- Rifiuto di sovrascritture e controllo di coerenza con il `lead_module` del fascicolo.

## 0.6.0
- Lifecycle locale per inizializzare, riprendere e versionare fascicoli derivati.
- Checkpoint e memoria canonica Markdown senza conservare il transcript.
- Quality Engine con esiti `PASS`, `PASS CON RILIEVI` e `BLOCKED`.
- Gate deterministico `APPROVO OUTPUT` con nota, artefatto e hash SHA-256.
- Ricevuta Markdown dell'approvazione, distinta da firma, deposito o trasmissione.
- Hook Codex `SessionStart` read-only e opt-in tramite `GF_AOS_WORKSPACE`.
- Comando hook separato per Windows e limite esplicito del contesto restituito.
- Nuove skill `case-lifecycle` e `professional-evals` con matrice di regressione.
- Vincolo di massimo quattro prossime azioni e attivazione esplicita di `CRISIS_001`.

## 0.5.0
- Agent Core ispirato ai pattern utili di Everything Claude Code e adattato a GF-AOS.
- Otto ruoli Codex repository-local con profili stretti e sandbox read-only.
- Nuova skill `agent-orchestrator` con delega minima, registro ruoli e handoff Markdown.
- Nuova skill `strategic-context` con checkpoint canonico per singolo incarico.
- Revisione indipendente e verifica finale separate dalla validazione professionale.
- Limite di quattro subagenti concorrenti e nessun modello fissato, per contenere contesto e costi.
- Test automatici per manifest, configurazione TOML, profili, gate e packaging delle skill.

## 0.4.0
- Motore Document Intelligence locale per PDF, DOCX, XLSX/XLSM, PPTX, testo e CSV.
- OCR immagini facoltativo tramite Tesseract, disattivato per impostazione predefinita.
- Registro strutturato con SHA-256, locator del testo, limiti, errori e troncamenti.
- Controlli su dimensione, decompressione Office e lingue OCR effettivamente disponibili.
- Nuova skill `document-intelligence` e integrazione nel flusso 006A/workspace.
- Test automatici multi-formato e controllo di immutabilità dei sorgenti.
- Markdown adottato come formato canonico per estratti e output testuali, con eccezioni funzionali esplicite.

## 0.3.0
- Marketplace Codex e manifest validabile.
- Undici skill professionali, comprese orchestrazione e scadenze/brief.
- Inventario locale 006A in sola lettura con report JSON e Markdown.
- Stato delle integrazioni dichiarato senza endpoint o credenziali fittizie.

La v0.2 è stata prodotta in una precedente conversazione, ma il relativo ZIP non era accessibile al momento della pubblicazione. La v0.3 ripristina come pacchetto completo le funzioni documentate della v0.2 e aggiunge i componenti qui elencati; una verifica di differenza file per file richiederà il pacchetto precedente.
