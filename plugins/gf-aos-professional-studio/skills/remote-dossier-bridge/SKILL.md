---
name: remote-dossier-bridge
description: Registra e verifica snapshot pseudonimizzati di fascicoli Google Drive, OneDrive e SharePoint, prepara importazioni in sola lettura e governa proposte di modifica remota senza eseguirle. Usa quando GF-AOS deve collegare un fascicolo remoto, rilevare variazioni, richiedere documenti a un connettore autorizzato o predisporre rename, move, metadati, sostituzioni ed eliminazioni con gate separati.
---

# Remote dossier bridge

Leggere `references/remote-dossier-contract.md` e, dalla radice del plugin, usare
`scripts/remote_dossiers.py`.

1. Far produrre al connettore un manifest senza nomi, URL, ID provider o credenziali.
2. Registrare la baseline pseudonimizzata e verificare il manifest corrente prima di ogni richiesta.
3. Per l'acquisizione, selezionare solo gli alias necessari e preparare una richiesta read-only.
4. Verificare il file restituito nell'inbox contro l'hash atteso; in assenza di corrispondenza
   mantenerlo in revisione e non usarlo come evidenza.
5. Per una modifica, creare un'anteprima con operazione, impatto, rollback e differenza attesa;
   indicare anche il `target-ref` pseudonimizzato, salvo l'eliminazione.
6. Scansionare l'anteprima con `privacy-automation` e profilo `internal`.
7. Preparare la modifica e richiedere `AUTORIZZO MODIFICA SORGENTI` con nota specifica.
8. Per sostituzione o eliminazione richiedere anche
   `AUTORIZZO OPERAZIONE IRREVERSIBILE <CHANGE_ID>`.
9. Verificare nuovamente baseline, revisione, anteprima, privacy e richiesta prima dell'esecuzione.

Il plugin non chiama direttamente Google Drive, OneDrive o SharePoint. `READY_FOR_AUTHORIZED_CONNECTOR` e
`READY_FOR_EXTERNAL_EXECUTOR` indicano soltanto che una richiesta locale e coerente; non provano
lettura, modifica, sincronizzazione o consegna.
