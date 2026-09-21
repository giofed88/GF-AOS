# Contratto comune dei workflow pack

1. Confermare cliente/contesto, modulo, ruolo, periodo, destinatario, scadenza e deliverable.
2. Trattare i documenti cliente in sola lettura e scrivere soltanto nel workspace derivato.
3. Separare fatto, calcolo, inferenza, valutazione professionale e limite documentale.
4. Registrare fonte, ente, data/versione, locator, data di accesso, proposizione e applicabilita.
5. Mantenere la sequenza delle fasi. Un salto richiede motivazione di almeno 15 caratteri e
   `PRENDO ATTO E IGNORO <STEP_CODE>`; registrare il limite nel piano, nell'output e nel log.
6. Etichettare gli output `BOZZA DA VALIDARE` fino al gate professionale.
7. Tenere modifica sorgenti e azioni esterne separate dall'approvazione dell'output. Una modifica
   ai sorgenti richiede anteprima e conferma esatta `AUTORIZZO MODIFICA SORGENTI`.

Ogni artefatto autonomo mostra ID, ruolo, periodo, data scheda, data verifica/lavoro, data di
generazione, fonti, limiti, follow-up e stato. Preferire un dossier integrato con sezioni autonome
quando cio riduce file dispersi senza confondere i ruoli.

Il piano e i registri Markdown sono memoria operativa; `CASE_STATE.json` resta il solo stato
macchina. Non salvare il transcript.
