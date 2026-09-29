# -*- coding: utf-8 -*-
"""prova_corsi_anteprima.py - un corso in "anteprima" sta SOLO sulla pagina della sua societa'.

Da dove viene (29/09/2026). Per proporre la guida corsi a Rovereto Central Park
se ne e' preparata la pagina e le si e' mandato il link. La scheda diceva "da
inviare" e la pagina era noindex, ma i sei corsi avevano lo Stato vuoto: stavano
in corsi.html, nei conteggi dei comuni e nell'app. Vedi STATI_ANTEPRIMA.

Le due meta' che contano:
  - FUORI: l'anteprima non e' nell'elenco, nei conteggi, nel registro che fa
    partire i link dalle schede evento, ne' in sitemap; e la pagina e' noindex
    anche se la tab Realta dicesse "confermata";
  - DENTRO: la pagina della societa' c'e' e ha i suoi corsi, perche' il link e'
    gia' stato mandato e non deve diventare un 404.

Niente rete, niente pagine vere: le pagine delle realta' vanno in una cartella
di prova, come in prova_corsi.py.
"""
import io
import json
import os
import shutil
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import genera_corsi as C

esito = True


def verifica(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def corso(nome, org, stato="", citta="Alessandria", prov="AL"):
    riga = {k: "" for k in C.COLONNE}          # tutte le colonne, vuote
    riga.update({"nome": nome, "org": org, "stato": stato, "citta": citta,
                 "prov": prov, "categoria": "Movimento › Multisport",
                 "eta": "6-10 anni", "descr": "Un corso di prova."})
    return riga


DESCR = "Una societa' sportiva di prova, con una descrizione abbastanza lunga " \
        "da meritarsi una pagina sua: servono almeno centoventi caratteri, e " \
        "questi lo sono."

print("\n1. separa_anteprime: i corsi in anteprima da una parte")
CORSI = [corso("Functional Kids", "Rovereto Central Park", "anteprima"),
         corso("Giocomotricita", "Rovereto Central Park", "Anteprima 29/09"),
         corso("Minivolley", "PGS Roccavione", "", "Roccavione", "CN")]
pubblici, anteprime = C.separa_anteprime(CORSI)
verifica("i due di Rovereto sono in anteprima (anche con la data accanto)",
         [c["nome"] for c in anteprime] == ["Functional Kids", "Giocomotricita"])
verifica("il Minivolley resta pubblico", [c["nome"] for c in pubblici]
         == ["Minivolley"])
verifica("un corso spento NON e' un'anteprima (sparisce anche dalla pagina)",
         not C.separa_anteprime([corso("X", "Y", "sospeso")])[1])
verifica("e un'anteprima non e' un corso spento",
         C.togli_corsi_spenti([corso("X", "Y", "anteprima")]) != [])

print("\n2. La pagina della societa' in anteprima c'e', ma non si trova")
C.DIR_REALTA = "corsi-prova-anteprima"
dest = os.path.join(C.ROOT, C.DIR_REALTA)
shutil.rmtree(dest, ignore_errors=True)
try:
    css, nav, foot = "", "", ""
    realta = {
        "rovereto-central-park": {"descr": DESCR, "stato": "confermata"},
        "pgs-roccavione": {"descr": DESCR, "stato": "confermata"},
    }
    gruppi = C.raggruppa_per_realta(pubblici + anteprime)
    in_indice = C.scrivi_realta(gruppi, realta, css, nav, foot,
                                in_anteprima={"rovereto-central-park"})
    pagina = os.path.join(dest, "rovereto-central-park.html")
    verifica("la pagina di Rovereto esiste (il link mandato funziona)",
             os.path.exists(pagina))
    testo = open(pagina, encoding="utf-8").read() if os.path.exists(pagina) else ""
    verifica("...con dentro i suoi corsi",
             "Functional Kids" in testo and "Giocomotricita" in testo)
    verifica("...ed e' noindex anche con la scheda 'confermata'",
             'content="noindex, follow"' in testo)
    verifica("fuori dalla sitemap", "rovereto-central-park.html" not in in_indice)
    verifica("la pagina di una societa' pubblica resta in sitemap",
             "pgs-roccavione.html" in in_indice)
    registro = json.load(open(C.indice_realta_path(), encoding="utf-8"))
    verifica("fuori dal registro: le schede evento non ci mandano nessuno",
             "rovereto-central-park" not in registro)
    verifica("...e la societa' pubblica ci resta", "pgs-roccavione" in registro)
finally:
    shutil.rmtree(dest, ignore_errors=True)

print("\n3. La parola e' la stessa dell'app")
app = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                   "mappaDAOP", "mobile", "app.js")
if os.path.exists(app):
    js = open(app, encoding="utf-8").read()
    verifica("app.js ha _STATI_ANTEPRIMA con 'anteprima'",
             "_STATI_ANTEPRIMA = ['anteprima']" in js)
else:
    print("  (app.js non e' su questo PC: controllo saltato)")

print()
print("VERDE" if esito else "ROSSO")
sys.exit(0 if esito else 1)
