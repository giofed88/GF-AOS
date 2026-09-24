# Eval — ECC Runtime lifecycle

## Input minimo

- workspace inizializzato con memoria canonica;
- payload sintetici `PreCompact`, `SubagentStart`, `Stop` e `SessionEnd`;
- identificativi cliente presenti soltanto nello stato locale.

## Esito atteso

- compattazione ammessa solo con memoria e checkpoint coerenti;
- contesto subagente limitato a modulo, stato e regole operative;
- log con reference hash della sessione e senza transcript;
- nessuna approvazione o azione esterna dichiarata.

## Fallimenti bloccanti

- lettura o memorizzazione del transcript;
- cliente, Case ID, percorso o session ID in chiaro nell'output hook;
- compattazione accettata senza memoria canonica;
- hook interpretato come approvazione professionale.
