#!/usr/bin/env python3
"""Select a private studio format family and prepare a reviewable engagement brief."""
import argparse
from pathlib import Path

FAMILIES = {
    "contabilita": ("ACC_CAP_001", "Contabilità e dichiarazioni", "contabilità, liquidazioni, bilancio e dichiarazioni; servizi continuativi", "F24 telematici, ravvedimenti, controlli e contenzioso: chiarire separatamente"),
    "lavoro": ("LAB_001", "Consulenza e adempimenti lavoro", "posizioni previdenziali, comunicazioni, cedolini, CU e 770; prestazioni per evento", "ispezioni, CIG, licenziamenti collettivi e conciliazioni: delimitare"),
    "revisione": ("AUDIT_001", "Revisione legale", "periodi, bilanci, verifiche periodiche, accesso alle evidenze e relazioni", "responsabilità della direzione, indipendenza, ragionevole sicurezza e limiti del campionamento"),
    "contenzioso": ("TAX_LIT_001", "Contenzioso tributario", "atto impugnato, grado, termini e procura", "fasi e adempimenti non conferiti"),
    "perizia": ("VALUATION_001", "Perizia e valutazione", "oggetto, data di riferimento, metodo, documenti ed elaborato", "assunzioni, limiti e uso consentito della relazione"),
    "odv": ("ODV_001", "Organismo di vigilanza", "perimetro 231, flussi, periodicità e destinatari", "funzione di vigilanza distinta da revisione e consulenza"),
    "agevolazioni": ("ACC_CAP_001", "Agevolazioni e investimenti", "misura, verifica preliminare, domanda, documenti e assistenza successiva", "esito della domanda e certificazioni esterne da non garantire"),
    "crisi": ("CRISIS_001", "Crisi e attestazioni", "specifico mandato, piano, attestazione e destinatario", "indipendenza, documenti non ricevuti e limiti dell'incarico"),
}

def render(family):
    module, title, scope, boundaries = FAMILIES[family]
    return f"""# Scheda format d'incarico — {title}

**BOZZA DA VALIDARE** · Modulo: `{module}` · Famiglia: `{family}`

## Identificazione e fonti
- Cliente, rappresentante, professionista, ruolo, periodo e destinatario: [DA COMPILARE].
- Individuare il format vigente nel OneDrive dello studio, leggerlo in sola lettura e registrare localmente identificativo, versione/data e hash; non copiare nel repository testo, nominativi o URL.
- Confrontare il format specifico con l'eventuale mandato generale e motivare la scelta.

## Perimetro
- Prestazioni da confermare: {scope}.
- Esclusioni e condizioni da chiarire: {boundaries}.
- Prestazioni straordinarie: indicare richiesta separata, compenso e approvazione.

## Clausole e allegati da verificare
- Obblighi e documentazione del cliente, modalità e tempi di consegna.
- Compenso, unità di tariffazione, spese, IVA/cassa, decorrenza e pagamento.
- Durata, rinnovo, recesso, polizza e responsabilità: verifica legale aggiornata, senza riuso automatico di clausole storiche.
- Privacy, antiriciclaggio e deleghe: verificare necessità, versioni e allegati specifici.
- Distinguere prestazioni fiscali, lavoro, revisione e vigilanza quando convivono nello stesso fascicolo.

## Esito della comparazione
| Sezione | Format studio | Adattamento proposto | Da validare |
| --- | --- | --- | --- |
| Oggetto e limiti | [DA VERIFICARE] | [DA COMPILARE] | Sì |
| Compensi | [DA VERIFICARE] | [DA COMPILARE] | Sì |
| Responsabilità e durata | [DA VERIFICARE] | [DA COMPILARE] | Sì |
| Allegati | [DA VERIFICARE] | [DA COMPILARE] | Sì |

Nessuna bozza è pronta per firma o invio finché la comparazione e la verifica professionale non sono completate.
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family", choices=sorted(FAMILIES))
    parser.add_argument("--output", type=Path, required=True, help="File Markdown derivato nel workspace del caso")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        file.write(render(args.family))
    print(args.output)

if __name__ == "__main__":
    main()
