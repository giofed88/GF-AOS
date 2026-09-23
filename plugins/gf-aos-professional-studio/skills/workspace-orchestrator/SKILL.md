---
name: workspace-orchestrator
description: Coordina fascicoli, scadenze, briefing e archivio
---

# workspace-orchestrator

Sequenza: router → Agent Core selettivo → piano → inventario 006A o baseline remota governata → Document Intelligence selettiva → lacune → scadenze governate → output → revisione indipendente → verifica finale → checkpoint → archivio. Per Drive usa `remote-dossier-bridge`: verifica il manifest prima di ogni lettura e non modificare sorgenti senza anteprima e gate dedicato. Per le scadenze usa `deadlines-brief`, conserva fonte e applicabilita e valida il termine prima dei reminder. Crea notifiche Telegram solo se integrazione reale disponibile e autorizzata; registra stato inviato/errore, senza dichiarare consegna prima del riscontro.

Preferisci Markdown per il patrimonio testuale del workspace e per i passaggi intermedi, così il contesto resta compatto e versionabile. Usa formati binari solo quando la funzione del documento li richiede.
