# -*- coding: utf-8 -*-
"""prova_prova_scaduta.py - la cella Prova con una data passata non si stampa.

Il buco che chiude (05/09/2026): tutto il resto della pagina si autopulisce - un
evento passa e sparisce, una riga con la Scadenza esce (prova_corsi_scaduti.py),
un open day finito non si annuncia - e la cella Prova no. Il 05/09 i due corsi
di Deborah Dalmasso dicevano "Primo incontro gratuito - lunedi 7 settembre", e
il 7 settembre era due giorni dopo: passato quello, la riga sarebbe rimasta li'
a invitare a una data finita. E' anche l'unica cella che una societa' scrive per
INVITARTI: sbagliarla non e' un dato vecchio, e' una porta chiusa in faccia.

LE TRE REGOLE, che sono la meta' che conta:
  - si toglie la CELLA, non la riga. Il corso resta pubblicato: quello che e'
    scaduto e' l'invito, non il corso. Se un giorno questa prova diventasse
    verde con un corso in meno, la regola avrebbe cambiato mestiere;
  - una cella ILLEGGIBILE non toglie niente ("su appuntamento", "gratuita a
    ottobre"). Stessa regola della Scadenza: serve un GIORNO e un MESE, un mese
    da solo non dice quando;
  - con piu' date vale l'ULTIMA, che e' l'occasione a cui si fa ancora in tempo.

E le due trappole dell'eta', che sono il motivo per cui il trattino non e' un
separatore ammesso e la barra si guarda due volte: "corso 7-9 anni" e "corso 7/9
anni" non sono il 7 settembre, e leggerli come date cancellerebbe una prova
buona.

Niente rete: _scarica e' finto e il "foglio" e' una stringa CSV qui dentro.
"""
import datetime
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import genera_corsi as C

esito = True


def verifica(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


# ── PARTE 1: la regola da sola, a data FISSA ──────────────────────────────
#
# Qui "oggi" e' il 5 settembre 2026 e non cambia mai: sono i casi veri della
# giornata in cui la regola e' nata, e devono restare verdi anche nel 2030.
FINTO = datetime.date(2026, 9, 5)

print()
print("=" * 70)
print("  LA REGOLA, con oggi = 5 settembre 2026")
print("=" * 70)

VIVE = [
    ("la data e' fra due giorni",
     "Primo incontro gratuito - lunedi 7 settembre (open day)"),
    ("la data e' oggi stesso (inclusa, come la Scadenza)",
     "Lezione di prova sabato 5 settembre"),
    ("un mese senza giorno non e' una data",
     "Gratuita a ottobre, su appuntamento"),
    ("nessuna data: la cella dice solo come si fa",
     "Su appuntamento, scrivere in segreteria"),
    ("nessuna data, seconda grafia", "Prima lezione libera"),
    ("due date, l'ULTIMA e' futura", "Prove il 20 agosto e il 24 ottobre"),
    ("l'eta' col trattino non e' il 7 settembre", "Corso 7-9 anni, prova gratuita"),
    ("l'eta' con la barra nemmeno", "Prova aperta ai 7/9 anni"),
    ("il 31 novembre non esiste, e non diventa una data", "Prova il 31/11"),
    ("un orario scritto storto non e' un mese", "Prova alle 17/30"),
    ("una parola che comincia come un mese non e' un mese",
     "Serve 1 genitore accompagnatore"),
    ("data numerica futura, con l'anno", "Prova il 07/09/2026"),
]
for etichetta, cella in VIVE:
    verifica(f"RESTA - {etichetta}", C.prova_ancora_valida(cella, FINTO))

MUORE = [
    ("la data e' ieri", "Primo incontro gratuito - lunedi 4 settembre"),
    ("mese scritto per esteso, un mese fa", "Open day 20 agosto, ore 18"),
    ("mese abbreviato", "Prova il 2 set"),
    ("due date, sono passate tutte e due", "Prove il 20 agosto e il 1 settembre"),
    ("data numerica passata, con l'anno", "Prova il 03/09/2026"),
    ("data numerica passata, senza anno", "Prova il 3/9"),
]
for etichetta, cella in MUORE:
    verifica(f"SI TOGLIE - {etichetta}", not C.prova_ancora_valida(cella, FINTO))

# L'anno non e' scritto quasi mai, e metterci sempre quello corrente sbaglia due
# volte l'anno: a dicembre "10 gennaio" e' l'anno prossimo, a gennaio
# "20 dicembre" e' quello passato. Questi due casi sono il capodanno.
print()
print("  A cavallo dell'anno (l'anno nella cella non c'e'):")
verifica("il 20 dicembre, letto il 10 gennaio, e' PASSATO",
         not C.prova_ancora_valida("Prova il 20 dicembre",
                                   datetime.date(2027, 1, 10)))
verifica("il 10 gennaio, letto il 20 dicembre, e' FUTURO",
         C.prova_ancora_valida("Prova il 10 gennaio",
                               datetime.date(2026, 12, 20)))

# ── PARTE 2: la regola COLLEGATA, cioe' che qualcuno la chiami ────────────
#
# La meta' che il 03/09 era mancata altrove: una regola giusta che nessuno
# invoca e' una regola che non c'e'. Qui si passa dal foglio.
print()
print("=" * 70)
print("  DAL FOGLIO ALLA SCHEDA")
print("=" * 70)

OGGI = datetime.date.today()
IERI = OGGI - datetime.timedelta(days=1)
DOMANI = OGGI + datetime.timedelta(days=1)
STAGIONE = f"{C.stagione_avvio()}/{C.stagione_avvio() + 1}"


def a_parole(d):
    return f"{d.day} {C.G.MESI_LUNGHI[d.month - 1]}"


RIGHE = [
    ("A001", "Prova vuota", ""),
    ("A002", "Prova di ieri", f"Primo incontro gratuito - {a_parole(IERI)}"),
    ("A003", "Prova di domani", f"Primo incontro gratuito - {a_parole(DOMANI)}"),
    ("A004", "Prova senza data", "Gratuita, su appuntamento"),
]


def foglio():
    righe = ["CODICE,Nome,Organizzatore,Annate,Stagione,Prova"]
    for cod, nome, prova in RIGHE:
        # La cella Prova si scrive fra virgolette perche' e' testo libero e la
        # virgola dentro ci sta ("Gratuita, su appuntamento"): senza, il CSV la
        # spezzerebbe in due colonne e questa prova misurerebbe il proprio
        # errore di battitura invece della regola.
        righe.append(f'{cod},{nome},PGS Roccavione,2015-2020,{STAGIONE},"{prova}"')
    return "\n".join(righe) + "\n"


vero = C._scarica
C._scarica = lambda tab: foglio()
try:
    corsi = C.leggi_corsi()
finally:
    C._scarica = vero

verifica("il foglio si legge", corsi is not None)
per_nome = {c["nome"]: c for c in (corsi or [])}

# LA COSA PIU' IMPORTANTE DI TUTTA LA PROVA: nessun corso e' sparito.
verifica("restano tutti e quattro i corsi (si toglie la cella, non la riga)",
         len(corsi or []) == 4)
verifica("la cella con la data di IERI e' stata svuotata",
         per_nome.get("Prova di ieri", {}).get("prova") == "")
verifica("la cella con la data di DOMANI e' intatta",
         per_nome.get("Prova di domani", {}).get("prova", "").startswith(
             "Primo incontro"))
verifica("la cella senza data e' intatta",
         per_nome.get("Prova senza data", {}).get("prova") ==
         "Gratuita, su appuntamento")
verifica("la cella gia' vuota resta vuota",
         per_nome.get("Prova vuota", {}).get("prova") == "")

print()
print("=" * 70)
print("  ESITO:", "TUTTO A POSTO" if esito else "QUALCOSA NON VA")
print("=" * 70)
print()
sys.exit(0 if esito else 1)
