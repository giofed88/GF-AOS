---
name: professional-output
description: Produce output professionali tracciabili
---

# professional-output

Indica cliente, incarico, periodo, ID, data scheda, verifica e stampa. Numerazione verbali per cliente/incarico. Separa bozza da documento approvato. Per PEC e comunicazioni esterne prepara bozze prima dell’invio.

Usa Markdown UTF-8 come formato canonico predefinito per bozze, registri, note, checklist, sintesi, indici e contenuti testuali. Mantieni JSON solo per stato e scambio macchina. Genera DOCX/PDF quando servono firma, stampa o impaginazione; XLSX quando servono formule o tabelle operative; PPTX quando serve una presentazione. Quando produci un formato finale, conserva ove possibile anche la sorgente Markdown senza duplicare allegati o contenuto non necessario.

Per lettere d'incarico, mandati e altri format professionali consulta `references/studio-formats.md`: seleziona il format privato dello studio, confrontalo con l'incarico concreto e registra le differenze prima di redigere la bozza. Il generatore locale `scripts/engagement_formats.py` crea una scheda di confronto vuota, senza accedere alle fonti remote.
