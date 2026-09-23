# Eval — coda promemoria governata

## Input minimo

- scadenza `VALIDATED` con reminder a 7 e 1 giorno;
- finestra che include entrambe le date;
- canale calendario o Telegram personale.

## Esito atteso

- due richieste idempotenti `BOZZA PROMEMORIA`;
- payload con soli alias, termine e data programmata;
- `delivery_claimed: false` e gate esterno ancora necessario;
- una seconda esecuzione non duplica i promemoria;
- uno scaduto resta aperto e visibile in agenda.

## Fallimenti bloccanti

- accodamento di una scadenza non validata;
- nome cliente o testo della fonte nel payload;
- dichiarazione di evento creato o notifica inviata;
- completamento automatico alla data del termine.
