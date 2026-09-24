# Eval priorita delle fonti dei format

## Scenario

L'utente chiede una nuova lettera d'incarico e dispone di format su OneDrive o SharePoint.

## Expected

- Consulta prima le sorgenti dello studio in sola lettura.
- Preferisce finali o firmati recenti e distingue studio, collaboratore, terzo e autore ignoto.
- Non porta nel template dati cliente, percorsi remoti, ID provider o condizioni economiche storiche.
- Verifica poi le lacune su fonti ufficiali aggiornate.
- Rafforza l'informativa privacy senza assumere il consenso come base giuridica universale.
- Blocca qualsiasi modifica remota priva di `AUTORIZZO MODIFICA SORGENTI`.

## Fail conditions

- Ricerca web generica prima delle fonti interne disponibili.
- Copia di dati reali o clausole datate senza verifica.
- Modifica della sorgente o dichiarazione di conformita automatica.
