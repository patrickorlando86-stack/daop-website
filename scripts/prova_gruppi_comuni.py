#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla il raggruppamento dello STESSO CORSO ripetuto in piu' COMUNI.

PERCHE' ESISTE (03/09/2026). L'ASD Atletica Mondovi' ha 23 corsi, che sono 4
fasce d'eta' x 5 comuni piu' sei corsi unici: DICIASSETTE righe che dicono
quattro cose. La domanda di Patrick era "ha senso mettere x corsi di atletica
perche' cambia l'annata?", e i dati rispondono di no: l'annata NON e' il
doppione - e' l'asse su cui filtra un genitore, e distingue davvero i corsi. Il
doppione e' il COMUNE.

Fra le tre strade possibili si e' scelta la B: si raggruppa solo per STAMPARE.
Il foglio resta com'e', ogni corso tiene il suo comune e il suo codice, i filtri
continuano a lavorare sulle righe vere. Risolve la leggibilita' senza toccare il
modello dei dati, che si progetta meglio con dieci societa' davanti che con
cinque.

IL VALORE DA DIFENDERE e' SOMIGLIANZA_STESSO_CORSO, e come per la soglia dei
comuni simili non e' stata una scelta ma una misura: sui 23 corsi veri, le
coppie da unire stanno TUTTE a 100 (un nome e' contenuto nell'altro:
"Esordienti (Scuole Elementari)" dentro "Atletica Esordienti (Scuole
Elementari)") e quelle da tenere separate a 50 o meno (Preparazione Atletica,
Ritiro Societario, Corsi di Atletica per tutte le eta': corsi diversi che
condividono solo la parola "atletica"). Fra 51 e 99 non c'e' niente.

Qui dentro:
  1. lo stesso corso in piu' paesi diventa UNA riga, con tutte le sedi dentro;
  2. corsi DIVERSI della stessa societa' non si toccano, anche se il nome
     comincia uguale;
  3. fasce d'eta' diverse restano righe diverse: e' l'asse che serve a chi
     filtra, e fonderlo sarebbe il danno peggiore;
  4. due righe nello STESSO comune non sono un corso in due sedi: sono due
     corsi, e fonderle nasconderebbe qualcosa invece di ordinarlo;
  5. societa' diverse non si mescolano mai;
  6. e nessuna riga si perde per strada.

Uso:
    python scripts/prova_gruppi_comuni.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca niente.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_corsi as g

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

esito = True


def verifica(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def corso(nome, citta, eta="", org="ASD Atletica Mondovì", cat="Movimento › Atletica",
          sede="", giorni="", codice=""):
    return {"nome": nome, "citta": citta, "eta": eta, "org": org, "cat": cat,
            "sede": sede, "giorni": giorni, "codice": codice, "annate": "",
            "stagione": "2026/2027"}


def sedi(c):
    return [x[0] for x in (c.get("_sedi") or [])]


def per_nome(gruppi, pezzo):
    return next((c for c in gruppi if pezzo in (c.get("nome") or "")), None)


print("=== il caso vero: lo stesso corso in cinque paesi ===")
righe = [
    corso("Atletica Esordienti (Scuole Elementari)", "Ceva", "scuole elementari"),
    corso("Esordienti (Scuole Elementari)", "Mondovì", "scuole elementari"),
    corso("Atletica Esordienti (Scuole Elementari)", "Carrù", "scuole elementari"),
    corso("Esordienti (Scuole Elementari)", "Dogliani", "scuole elementari"),
    corso("Atletica Esordienti (Scuole Elementari)", "Camerana", "scuole elementari"),
]
gr = g.raggruppa_per_comune(righe)
verifica("cinque righe diventano una", len(gr) == 1)
verifica("...che sa di stare in cinque comuni", len(sedi(gr[0])) == 5)
verifica("...e li elenca tutti",
         sorted(sedi(gr[0])) == ["Camerana", "Carrù", "Ceva", "Dogliani", "Mondovì"])
# Il titolo e' il nome piu' CORTO: nella pagina della societa' il prefisso col
# suo nome e' gia' detto in cima.
verifica("il titolo e' il nome senza il prefisso della societa'",
         gr[0]["nome"] == "Esordienti (Scuole Elementari)")

print("\n=== le fasce restano righe diverse ===")
# E' l'asse su cui filtra un genitore: fonderlo sarebbe il danno peggiore,
# perche' un filtro "6-8 anni" comincerebbe a proporre corsi per quattordicenni.
righe = [
    corso("Atletica Esordienti (Scuole Elementari)", "Ceva", "scuole elementari"),
    corso("Atletica Esordienti (Scuole Elementari)", "Carrù", "scuole elementari"),
    corso("Atletica Ragazzi/e (1 e 2 Media)", "Ceva", "1a e 2a media"),
    corso("Atletica Ragazzi/e (1 e 2 Media)", "Carrù", "1a e 2a media"),
]
gr = g.raggruppa_per_comune(righe)
verifica("due gruppi, non uno", len(gr) == 2)
verifica("elementari per conto suo", len(sedi(per_nome(gr, "Esordienti"))) == 2)
verifica("medie per conto loro", len(sedi(per_nome(gr, "Ragazzi"))) == 2)

print("\n=== corsi DIVERSI della stessa societa' non si toccano ===")
# Condividono la parola "atletica" e la fascia (nessuna), ma sono tre cose.
righe = [
    corso("Preparazione Atletica", "Mondovì"),
    corso("Ritiro Societario L'Atletica va in Vacanza", "Mondovì"),
    corso("Corsi di Atletica per tutte le età e tutti i livelli", "Mondovì"),
]
gr = g.raggruppa_per_comune(righe)
verifica("restano tre righe", len(gr) == 3)
verifica("...e nessuna ha sedi multiple", all(len(c.get("_sedi") or []) <= 1 for c in gr))

print("\n=== due righe nello STESSO comune sono due corsi ===")
# Stesso nome, stesso paese: non e' un corso in due sedi. Fonderle
# nasconderebbe una riga invece di ordinarla.
righe = [corso("Ginnastica", "Mondovì", "6-10 anni", sede="Palestra A"),
         corso("Ginnastica", "Mondovì", "6-10 anni", sede="Palestra B")]
gr = g.raggruppa_per_comune(righe)
verifica("non si fondono", len(gr) == 2)

print("\n=== societa' diverse non si mescolano mai ===")
righe = [corso("Esordienti", "Ceva", "6-10 anni", org="ASD Atletica Mondovì"),
         corso("Esordienti", "Carrù", "6-10 anni", org="PGS Roccavione")]
gr = g.raggruppa_per_comune(righe)
verifica("due societa', due righe", len(gr) == 2)

print("\n=== e non si perde niente ===")
righe = [
    corso("Atletica Esordienti (Scuole Elementari)", "Ceva", "scuole elementari",
          sede="Campo comunale", giorni="Lun 17:00", codice="A100"),
    corso("Esordienti (Scuole Elementari)", "Mondovì", "scuole elementari",
          sede="Pista", giorni="Mar 18:00", codice="A101"),
    corso("Bimbi in Pista", "Mondovì", "3-4 anni", codice="A102"),
]
gr = g.raggruppa_per_comune(righe)
codici = {x[3] for c in gr for x in (c.get("_sedi") or [])} | {
    c.get("codice") for c in gr if not c.get("_sedi")}
verifica("i codici delle righe unite ci sono tutti",
         {"A100", "A101"} <= codici)
uniti = per_nome(gr, "Esordienti")
dettagli = [(x[0], x[1], x[2]) for x in uniti["_sedi"]]
verifica("ogni comune si porta la SUA sede",
         ("Ceva", "Campo comunale", "Lun 17:00") in dettagli
         and ("Mondovì", "Pista", "Mar 18:00") in dettagli)
verifica("il corso unico resta al suo posto", per_nome(gr, "Bimbi") is not None)

print("\n=== l'elenco vuoto non fa niente ===")
verifica("niente in, niente out", g.raggruppa_per_comune([]) == [])

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
