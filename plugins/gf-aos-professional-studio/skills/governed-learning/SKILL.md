---
name: governed-learning
description: Trasforma lezioni sanificate provenienti da fascicoli GF-AOS approvati in candidati metodo, li promuove solo con approvazione professionale e ne rinforza la confidenza su casi distinti. Usa dopo la chiusura di un incarico per conservare procedure riutilizzabili senza trasferire dati, conclusioni o strategie del cliente.
---

# Governed learning

Leggere `references/learning-contract.md` e usare `scripts/governed_learning.py`. Non osservare
automaticamente transcript o tool call e non ricavare metodi da fascicoli non approvati.

## Ciclo

1. Predisporre manualmente una breve lezione Markdown gia priva di dati e fatti del cliente.
2. Usare `propose`: il motore verifica approvazione del fascicolo, pattern sensibili e istruzioni
   incorporate, quindi crea un candidato `DA VALIDARE` nel workspace.
3. Riesaminare integralmente il candidato. Usare `promote` solo con nota e frase esatta
   `APPROVO METODO`, verso una libreria separata dai fascicoli cliente.
4. Su un diverso caso approvato, usare `reinforce` con nota e `CONFERMO METODO`; la confidenza
   aumenta fino a 0,90 senza memorizzare cliente o Case ID. Un metodo `module` resta nello stesso modulo.
5. L'aggiornamento di skill, agenti o regole resta una modifica di sviluppo distinta e richiede
   revisione esplicita. Un metodo approvato non e una fonte normativa.
