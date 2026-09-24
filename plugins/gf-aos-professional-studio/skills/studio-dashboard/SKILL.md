---
name: studio-dashboard
description: Genera e verifica il cruscotto operativo multi-fascicolo GF-AOS e governa task pseudonimizzati. Usa per avere una vista unica di stati, blocker, prossime azioni, scadenze, reminder, code esterne e integrita senza copiare nomi cliente, percorsi o contenuti dei fascicoli.
---

# Studio dashboard

Leggere `references/dashboard-contract.md` e, dalla radice del plugin, usare
`scripts/studio_dashboard.py`.

1. Inizializzare una directory centrale separata dai fascicoli con un alias `STUDIO_*`.
2. Predisporre fuori dalla dashboard un manifest effimero con soli `workspace_ref` `CASE_*` e
   percorsi assoluti dei workspace autorizzati.
3. Generare il cruscotto con data operativa e orizzonte espliciti.
4. Consultare soltanto alias, modulo, periodo, stato e conteggi; aprire il singolo fascicolo per
   contenuti, fonti e decisioni professionali.
5. Aggiungere task con codici `TASK_*` e owner `OWNER_*`; non inserire descrizioni libere.
6. Dopo ogni modifica task rigenerare il dashboard con `RIGENERO DASHBOARD`.
7. Prima di affidarsi al cruscotto eseguire `verify`; fermarsi su `BLOCKED_LIVE`.

Non interpretare una richiesta pronta, un reminder o una baseline remota come esecuzione live.
