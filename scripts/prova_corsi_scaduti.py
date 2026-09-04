# -*- coding: utf-8 -*-
"""prova_corsi_scaduti.py - la colonna Scadenza toglie il corso dalla pagina.

Il buco che chiude (04/09/2026): un EVENTO si autopulisce quando passa la data,
un CENTRO estivo pure (Data fine), un CORSO no. La danza 2025/26 restava a
catalogo finche' non la toglieva qualcuno a mano, e a un genitore che telefona a
settembre rispondeva una segreteria che quel corso non lo fa piu'.

LA STAGIONE NON BASTA, ed e' il motivo per cui la colonna esiste accanto a
quella: la stagione dichiara quando il corso DOVEVA finire, la scadenza quando
e' finito davvero. Un 2026/2027 chiuso a marzo, con la sola stagione, resta in
pagina fino a luglio.

E le due cose che NON deve fare, che sono la meta' che conta:
  - una cella vuota non toglie niente (la colonna e' facoltativa: la tab la
    compilano persone diverse in momenti diversi);
  - una cella ILLEGGIBILE ("a fine stagione") lascia il corso al suo posto. Una
    data scritta di fretta non deve far sparire un corso buono - stessa regola
    dei centri, e stessa regola dell'app (_corsoScaduto in app.js del repo
    mobile): se le due superfici divergessero, lo stesso corso sarebbe morto di
    qua e vivo di la'.

La data e' INCLUSA: un corso valido "fino al 17 ottobre" si vede tutto il 17.

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


OGGI = datetime.date.today()
IERI = OGGI - datetime.timedelta(days=1)
DOMANI = OGGI + datetime.timedelta(days=1)


def g(d):
    return d.strftime("%d/%m/%Y")


# La stagione e' quella IN CORSO su tutte le righe, se no a scartarle sarebbe il
# filtro di prima e questa prova non proverebbe niente.
STAGIONE = f"{C.stagione_avvio()}/{C.stagione_avvio() + 1}"

RIGHE = [
    ("A001", "Senza scadenza", ""),
    ("A002", "Scaduto ieri", g(IERI)),
    ("A003", "Scade oggi", g(OGGI)),
    ("A004", "Scade domani", g(DOMANI)),
    ("A005", "Scadenza a parole", "a fine stagione"),
    ("A006", "Scadenza ISO passata", IERI.strftime("%Y-%m-%d")),
]


def foglio():
    righe = ["CODICE,Nome,Organizzatore,Annate,Stagione,Scadenza"]
    for cod, nome, scad in RIGHE:
        righe.append(f"{cod},{nome},PGS Roccavione,2015-2020,{STAGIONE},{scad}")
    return "\n".join(righe) + "\n"


def leggi():
    vero = C._scarica
    C._scarica = lambda tab: foglio()
    try:
        return C.leggi_corsi()
    finally:
        C._scarica = vero


print()
print("=" * 70)
print("  LA SCADENZA DI UN CORSO")
print("=" * 70)

corsi = leggi()
verifica("il foglio si legge", corsi is not None)
nomi = {c["nome"] for c in (corsi or [])}

verifica("la colonna Scadenza viene riconosciuta",
         "scadenza" in C.COLONNE)
verifica("senza scadenza il corso resta", "Senza scadenza" in nomi)
verifica("scaduto ieri: fuori", "Scaduto ieri" not in nomi)
verifica("scade OGGI: dentro (la data e' inclusa)", "Scade oggi" in nomi)
verifica("scade domani: dentro", "Scade domani" in nomi)
verifica("una scadenza scritta a parole NON butta il corso",
         "Scadenza a parole" in nomi)
verifica("la data si legge anche in forma ISO",
         "Scadenza ISO passata" not in nomi)
verifica("in tutto restano quattro corsi su sei", len(corsi or []) == 4)

# Le grafie: la tab l'hanno compilata persone diverse, e queste sono le stesse
# che accetta l'app. Una che qui non passasse vorrebbe dire un corso sparito da
# Ginetto e ancora in pagina sul sito.
print()
print("  Le grafie dell'intestazione (le stesse dell'app):")
for testata in ("Scadenza", "Data scadenza", "Valida fino al", "Valido fino al",
                "Data fine", "Fine"):
    def uno(t=testata):
        vero = C._scarica
        C._scarica = lambda tab: (
            f"CODICE,Nome,Organizzatore,Annate,Stagione,{t}\n"
            f"A001,Scaduto,PGS Roccavione,2015-2020,{STAGIONE},{g(IERI)}\n")
        try:
            return C.leggi_corsi()
        finally:
            C._scarica = vero
    fuori = uno()
    verifica(f"'{testata}' toglie il corso scaduto", fuori == [])

print()
print("=" * 70)
print("  ESITO:", "TUTTO A POSTO" if esito else "QUALCOSA NON VA")
print("=" * 70)
print()
sys.exit(0 if esito else 1)
