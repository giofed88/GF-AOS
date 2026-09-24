# Contratto grafico documentale GF-AOS

## Ambito

Applicare questo contratto a lettere d'incarico, relazioni, verbali, carte di lavoro e altri
documenti destinati a Word, firma, stampa o PDF. Il contenuto professionale resta subordinato
alle fonti e ai gate previsti da `template-source-contract.md`.

## Identità visiva approvata

- Usare il blocco identitario `assets/document/gf-header-left-v1.png`: segno verticale petrolio
  con filetto caldo, monogramma GF, nome Giovanni Federico e qualifiche.
- Trattare il blocco sinistro come una sola immagine ad alta risoluzione. Non ricomporre in Word
  monogramma, nome, qualifiche o linee: la ricomposizione produce scarti tra Word e PDF.
- Lasciare editabili nel blocco destro tipo documento, data e revisione.
- Usare pagina A4, margini ariosi, titolo Georgia e testo Arial; palette limitata a petrolio,
  antracite, grigi caldi e bianco.
- Evitare gradienti, ombre, effetti tridimensionali, decorazioni generiche e riquadri ripetuti
  che rendano il documento artificiale o riconducibile a template standardizzati.

## Regole funzionali

- Conservare i contenuti come testo editabile; usare immagini solo per l'identità grafica.
- Inserire `BOZZA DA VALIDARE` finché il contenuto non è approvato professionalmente.
- Usare esclusivamente segnaposto nei template versionati. Non salvare dati personali, nomi
  cliente, identificativi, recapiti, URL o percorsi di sorgenti nel repository.
- Riportare cliente, incarico, periodo, ID, data, revisione e stato nei campi previsti.
- Tenere fatti, fonti, ipotesi, valutazioni, limiti e conclusioni chiaramente distinti.

## Profili disponibili

- `engagement-letter`: lettera d'incarico e allegato operativo.
- `professional-report`: relazione o parere professionale.
- `minutes`: verbale con presenze, ordine del giorno, discussione e deliberazioni.
- `working-paper`: carta di lavoro con obiettivo, campione, procedura, evidenze e riesame.

## Controllo di parità

Prima della consegna renderizzare il DOCX e confrontare visivamente ogni pagina con il PDF.
Verificare almeno: identità completa e non deformata, colori, allineamenti, interruzioni di
pagina, tabelle, footer, numerazione e assenza di quadrati o glifi sostitutivi. Un DOCX non
renderizzato non è considerato verificato.
