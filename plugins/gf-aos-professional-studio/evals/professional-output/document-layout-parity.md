# Eval: parità grafica Word/PDF

## Input minimo

- Un documento richiesto in formato DOCX e PDF.
- Uno dei profili `engagement-letter`, `professional-report`, `minutes`, `working-paper`.
- Solo segnaposto o dati minimizzati autorizzati.

## Esito atteso

- Il blocco identitario GF è completo, proporzionato e coerente in Word e PDF.
- Tipo documento, data e revisione rimangono editabili.
- Il DOCX è stato renderizzato e tutte le pagine sono state ispezionate.
- Non compaiono quadrati, glifi sostitutivi, righe spezzate o spostamenti ingiustificati.
- Il documento è A4, riporta `BOZZA DA VALIDARE` e non contiene dati reali nel template.

## Fallimenti bloccanti

- Intestazione ricomposta con elementi Word indipendenti o diversa dal PDF.
- Mancata ispezione del render DOCX.
- Dati personali, recapiti reali, percorsi o identificativi di sorgente nel repository.
- Uso di effetti grafici estranei al contratto o contenuto non editabile oltre all'identità.
