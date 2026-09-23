---
name: privacy-automation
description: Applica bootstrap minimizzato, scansione privacy per profilo e controllo di integrita delle fonti ai workflow GF-AOS. Usa all'avvio di una sessione, prima di delegare o pubblicare contenuti, prima di azioni esterne e per verificare che i documenti sorgente non siano cambiati durante l'elaborazione.
---

# Privacy-first automation

Leggere `references/privacy-contract.md` e usare `scripts/privacy_guard.py`.

- `bootstrap` restituisce soltanto impronta del caso, modulo, stato e conteggi; non carica cliente,
  memoria o prossime azioni nel contesto automatico.
- `scan` produce un report senza valori sensibili o nomi file. Usare `agent-handoff` per deleghe,
  `public` per contenuti pubblici, `external-draft` per bozze destinate a terzi e `internal` per uso studio.
- `snapshot` registra solo hash dei percorsi e dei contenuti delle fonti; `verify` segnala aggiunte,
  rimozioni e modifiche senza esporre nomi o contenuti.

`BLOCKED` impedisce la fase successiva. `WARN` richiede revisione e autorizzazione specifica.
Per `agent-handoff` e `public`, anche in assenza di pattern, il primo esito e `REVIEW_REQUIRED`:
dopo la revisione contestuale ripetere con `--review-confirmation "CONFERMO REVISIONE PRIVACY"`
e `--replace` per sostituire soltanto il report derivato. Solo `PASS` restituisce exit code zero.
`PASS` non autorizza invio, pubblicazione, deposito, firma o modifica delle fonti.
