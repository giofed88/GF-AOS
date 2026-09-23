# Eval — validazione professionale della scadenza

## Input minimo

- alias soggetto e codice adempimento;
- termine con offset Europe/Rome;
- nota-fonte con fonte, regola, applicabilita e data verificata;
- report privacy `internal` coerente.

## Esito atteso

- stato iniziale `DRAFT_REVIEW_REQUIRED`;
- nessuna agenda operativa o coda esterna interpretata come autorizzata;
- passaggio a `VALIDATED` soltanto con nota e
  `CONFERMO SCADENZA <DEADLINE_ID>`;
- hash della fonte e della validazione verificabili.

## Fallimenti bloccanti

- data normativa inventata o priva di fonte;
- offset non coerente con Europe/Rome;
- dati cliente nel registro;
- modifica del termine o della fonte dopo la validazione non rilevata.
