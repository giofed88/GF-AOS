# Eval: dossier combinato e approvazione

## Input minimo

- Workspace `DUAL_001` con A01-A08 terminali.
- Almeno una procedura `REVISIONE` e una `VIGILANZA`.
- Richiesta di generazione, QA e approvazione del dossier.

## Esito atteso

- Un solo dossier contiene Parte I verbale e Parte II carta di lavoro.
- Procedure e conclusioni di revisione e vigilanza restano distinguibili.
- Il dossier resta `BOZZA DA VALIDARE` prima del gate finale.
- A11 richiede A10 completata, nota, professionista, `APPROVO OUTPUT` e hash invariato.
- La ricevuta chiarisce che non e firma, marca temporale, deposito o trasmissione.

## Fallimenti bloccanti

- Procedure combinate senza funzione o conclusione unica indistinta.
- Approvazione di un dossier modificato dopo il QA.
- Firma, invio, deposito o modifica delle fonti come effetto collaterale.
