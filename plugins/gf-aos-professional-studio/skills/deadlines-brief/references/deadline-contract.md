# Contratto scadenze e promemoria

## Principi

- Non calcolare o inserire termini normativi senza una fonte corrente e una verifica di
  applicabilita al caso.
- Distinguere data della fonte, periodo disciplinato, data di verifica e termine operativo.
- Conservare clienti e pratiche come alias; tenere il testo della fonte fuori dal registro.
- Usare sempre `Europe/Rome` e l'offset effettivo applicabile alla data.
- Non completare automaticamente una scadenza e non equiparare un promemoria a un invio.

## Stati

| Stato | Significato |
| --- | --- |
| `DRAFT_REVIEW_REQUIRED` | termine proposto, non ancora validato |
| `VALIDATED` | fonte, applicabilita e data confermate dal professionista |
| `COMPLETED_BY_USER` | completamento dichiarato dall'utente; ricevuta di deposito non verificata |
| `BLOCKED_LIVE` | record, registro, fonte, privacy o approvazione non piu coerenti |

## Gate

- Validare con nota di almeno 15 caratteri e
  `CONFERMO SCADENZA <DEADLINE_ID>`.
- Segnare completato con nota di almeno 15 caratteri e
  `CONFERMO ADEMPIMENTO <DEADLINE_ID>`.
- Non usare `APPROVO OUTPUT` come sostituto dei gate delle scadenze.
- Non trasformare la validazione in autorizzazione a creare eventi o inviare notifiche.

## Promemoria

Generare soltanto `BOZZA PROMEMORIA` con payload pseudonimizzato, data programmata,
`delivery_claimed: false` e `requires_external_action_gate: true`. Per calendario o Telegram:

1. scansionare il payload con `privacy-automation` e profilo `external-draft`;
2. preparare l'azione con `external-action-governance`;
3. richiedere il relativo gate esterno;
4. lasciare l'esecuzione al connettore autorizzato.

La coda locale non e uno scheduler e non prova creazione dell'evento, notifica, deposito o
ricezione. Una scadenza scaduta resta `VALIDATED` finche l'utente non conferma il completamento.
