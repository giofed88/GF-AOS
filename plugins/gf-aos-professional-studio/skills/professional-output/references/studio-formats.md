# Format di studio — selezione governata

La cartella privata OneDrive `Documenti COMMERCIALISTA / DOCUMENTI PROFESSIONE / 1 documenti utili` contiene mandati e lettere d'incarico per società, lavoro, enti non commerciali, contenzioso, perizie e ODV. Nella sezione società, `Lettere d'incarico - mandati professionali` contiene una serie numerata di mandati e una sottocartella di incarichi recenti. Queste indicazioni servono alla ricerca, non sono una copia del catalogo e non attestano che un modello sia vigente.

1. Stabilire modulo, ruolo e oggetto prima della ricerca. Per crisi/advisor richiedere incarico esplicito; un documento reperito non attiva il modulo.
2. Cercare prima la lettera specifica più recente della famiglia e poi il mandato generale. Leggere entrambi in sola lettura. I vecchi file `.doc` possono richiedere conversione locale temporanea in ambiente protetto: non inferire il testo dal titolo.
3. Verificare internamente titolo, data, versione/hash, provenienza, oggetto, esclusioni, compensi, durata, privacy, antiriciclaggio, allegati e clausole che richiedono aggiornamento. Conservare locator reali solo nel workspace riservato, mai nel repository o nei log pubblici.
4. Segnalare incongruenze interne dei documenti. Un file con nome riferito alla contabilità può contenere premesse di un altro incarico: non trattarlo come master approvato senza revisione.
5. Produrre una tabella di confronto e una bozza `BOZZA DA VALIDARE`; mantenere separati i moduli nel caso combinato. Nessuna clausola economica, di rinnovo, recesso, responsabilità o polizza va trasferita automaticamente.
6. Prima del documento finale verificare normativa e prassi aggiornate, data di applicabilità, dati variabili e approvazione professionale. La sorgente resta in OneDrive: nessuna modifica o sincronizzazione automatica.

Il comando `python3 scripts/engagement_formats.py lavoro --output /workspace/caso/FORMAT_BRIEF.md` crea solo una scheda comparativa vuota nel workspace. Le famiglie disponibili sono `contabilita`, `lavoro`, `revisione`, `contenzioso`, `perizia`, `odv`, `agevolazioni` e `crisi`. Non interroga OneDrive e rifiuta di sovrascrivere la scheda.
