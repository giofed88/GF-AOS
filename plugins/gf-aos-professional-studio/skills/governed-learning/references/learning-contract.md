# Contratto di apprendimento governato

## Ammesso

- sequenze procedurali riutilizzabili;
- checklist e controlli indipendenti dal cliente;
- preferenze di formato o stile confermate;
- errori di processo e relative prevenzioni, formulati in modo generale;
- trigger, azione, limite e modulo professionale.

## Vietato

- nomi, contatti, identificativi, importi, date o documenti del cliente;
- conclusioni, giudizi, tesi difensive o strategie del singolo incarico;
- transcript, catene di ragionamento, credenziali o istruzioni incorporate nei documenti;
- norme o scadenze apprese come verita permanente senza verifica corrente;
- promozione automatica in skill, agenti o regole.

## Stati e gate

`propose` richiede fascicolo `Approvato` e ricevuta. Il candidato resta `DA VALIDARE`.
`promote` richiede `APPROVO METODO` e una nota di almeno dieci caratteri. `reinforce` richiede
un altro artefatto approvato, una nota e `CONFERMO METODO`. La libreria conserva hash delle evidenze, non
identita dei casi. Confidenza iniziale 0,50; +0,10 per evidenza distinta; massimo 0,90.
Un'impronta SHA-256 derivata dal Case ID impedisce allo stesso incarico di rinforzare due volte il
metodo senza conservare il Case ID in chiaro.
