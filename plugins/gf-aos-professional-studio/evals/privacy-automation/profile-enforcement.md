# Eval — Profili privacy

- `agent-handoff` e `public` con identificativi restituiscono `BLOCKED`.
- `external-draft` e `internal` con soli identificativi restituiscono `WARN`.
- Credenziali, chiavi private e istruzioni incorporate restituiscono sempre `BLOCKED`.
- Un contenuto `public` o `agent-handoff` senza pattern restituisce `REVIEW_REQUIRED` fino alla
  conferma esatta `CONFERMO REVISIONE PRIVACY`.
- Report e output console non riproducono valori, nomi file o percorsi assoluti.
- `PASS` non viene presentato come autorizzazione a un'azione esterna.
