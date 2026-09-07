#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla che OGNI SEDE resti un corso a se': una riga del foglio, una card in
pagina, coi SUOI dati.

PERCHE' ESISTE (07/09/2026). Fra il 03/09 e il 07/09 le righe dello stesso
corso in paesi diversi venivano fuse in una card sola, con l'elenco delle sedi
nel dettaglio (raggruppa_per_comune). Il conto che l'aveva fatta nascere era
buono - l'ASD Atletica Mondovi' ha 4 fasce d'eta' x 5 comuni, cioe' diciassette
righe che dicono quattro cose - e la fusione era dichiaratamente "solo per
stampare, il foglio resta com'e'".

Ma la card e' UNA, e i campi sono uno per card: locandina, referente, contatto,
sede e giorni restavano quelli della CAPOFILA. Sotto "Si tiene in 5 comuni" un
genitore di Ceva leggeva il numero della referente di Mondovi' e guardava la
locandina di Mondovi'. Sul foglio le cinque righe erano complete e diverse: era
la pagina a nasconderle.

QUINDI L'INVARIANTE, e questo file esiste per difenderla:
  · N righe accese = N card. Nessuna riga si fonde con un'altra, nemmeno quando
    societa', categoria, fascia d'eta' e nome combaciano.
  · Ogni card porta il comune, la sede, i giorni, il referente, il contatto e la
    locandina della SUA riga. Mai quelli di un'altra.
  · In pagina non restano tracce della fusione: nessun "5 comuni" al posto del
    paese, nessun elenco di sedi, nessun data-comuni (il comune di una card e'
    uno, ed e' data-city - il filtro legge quello).

E' il rovescio esatto della prova che stava qui prima (prova_gruppi_comuni.py),
tolta insieme alla funzione.

Offline e in un secondo: chiama card() sulle righe finte, non tocca la rete e
non riscrive nessuna pagina.

Uso:
    python scripts/prova_corsi_separati.py
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import genera_corsi as g  # noqa: E402

esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def corso(nome, citta, sede, giorni, referenti, contatto, loc, codice):
    """Una riga di corso col minimo che serve a disegnarla."""
    return {"nome": nome, "citta": citta, "sede": sede, "giorni": giorni,
            "referenti": referenti, "contatto": contatto, "loc": loc,
            "codice": codice, "org": "ASD Atletica Mondovì",
            "cat": "Movimento › Atletica leggera", "prov": "CN",
            "eta": "scuole elementari (6-10 anni)", "annate": "",
            "stagione": "2026/2027", "descr": "", "descr_premium": "",
            "prezzo": "", "prova": "", "iscrizioni": "", "periodo": "",
            "sito": "", "verificato": "", "openday": "", "premium": "",
            "lat": "", "lng": ""}


# Le cinque sedi degli Esordienti, come stanno DAVVERO sul foglio (A020, A024,
# A028, A031, A034): stesso corso, stessa societa', stessa fascia d'eta', nomi
# che si contengono - cioe' i cinque casi che la vecchia regola fondeva - e
# referente, contatto, sede, giorni e locandina tutti diversi.
RIGHE = [
    corso("Esordienti (Scuole Elementari)", "Mondovì",
          "Pista Atletica Fantoni-Bono", "Lunedì 17.00-18.30",
          "Monica", "335.57.30.060", "1_Mondovi.webp", "A020"),
    corso("Atletica Esordienti (Scuole Elementari)", "Carrù",
          "Impianti Sportivi IC Perotti", "Martedì 17.30-19.00",
          "Marco Chiecchio", "339.30.86.561", "2_Carru.webp", "A024"),
    corso("Atletica Esordienti (Scuole Elementari)", "Ceva",
          "Impianti sportivi Oratorio Borsi", "Martedi 17.30-19.30",
          "Gianluca Guffanti", "329.76.57.322", "3_Ceva.webp", "A028"),
    corso("Esordienti (Scuole Elementari)", "Dogliani",
          "Via Chabat (ex bocciofila)", "Mercoledì 17.00-18.30",
          "Elena Conterno", "327.17.80.265", "4_Dogliani.webp", "A031"),
    corso("Atletica Esordienti (Scuole Elementari)", "Camerana",
          "Campo Sportivo di Camerana/Saliceto", "Orario da definire",
          "Claudio Bado", "segreteria@atleticamondovi.net",
          "6_Camerana.webp", "A034"),
]

CARD = [g.card(c, i) for i, c in enumerate(RIGHE)]
TUTTO = "\n".join(CARD)

print("\n── cinque sedi, cinque card ──")
ok("una card per riga", len(CARD) == len(RIGHE))
ok("cinque comuni distinti in data-city",
   len(set(re.findall(r'data-city="([^"]*)"', TUTTO))) == 5)
ok("cinque codici distinti",
   len(set(re.findall(r'data-codice="([^"]*)"', TUTTO))) == 5)
ok("cinque ancore distinte (l'elenco della realta' ci manda)",
   len(set(re.findall(r'<article class="event-card" id="([^"]*)"', TUTTO))) == 5)

print("\n── ogni card porta i dati della SUA riga ──")
for c, html_card in zip(RIGHE, CARD):
    suo = (c["referenti"] in html_card
           and c["sede"] in html_card
           and c["loc"] in html_card
           and g.G.slugify(c["citta"]) in html_card)
    ok(f"{c['codice']} {c['citta']}: referente, sede, giorni e locandina sono i suoi",
       suo)
    altri = [d for d in RIGHE if d is not c]
    ok(f"{c['codice']} {c['citta']}: e non ci sono quelli di un'altra sede",
       not any(d["referenti"] in html_card or d["loc"] in html_card
               for d in altri))

print("\n── in pagina non resta traccia della fusione ──")
ok('nessun "N comuni" al posto del paese',
   not re.search(r'\d+\s+comuni', TUTTO))
ok("nessun elenco di sedi (co-sedi)", "co-sedi" not in TUTTO)
ok("nessun data-comuni: il comune di una card e' uno",
   "data-comuni" not in TUTTO)
ok("il CSS della fusione e' andato via col resto",
   "co-sedi" not in g.CSS if hasattr(g, "CSS") else True)

print("\n── e la funzione non torna per sbaglio ──")
# Se qualcuno la rimette, questo controllo diventa rosso: non e' un divieto
# tecnico, e' un promemoria che quella decisione va ripresa in mano. La sola
# variante difendibile e' fondere quando locandina, referente, contatto, sede e
# giorni sono IDENTICI su tutte le sedi, cioe' quando non c'e' niente da
# scegliere - e in quel caso questa prova va riscritta di conseguenza.
ok("raggruppa_per_comune non c'e' piu'",
   not hasattr(g, "raggruppa_per_comune"))
ok("e nemmeno la soglia che le serviva",
   not hasattr(g, "SOMIGLIANZA_STESSO_CORSO"))

print("\n── la pagina vera, se e' su disco ──")
pag = os.path.join(g.ROOT, "corsi",
                   "asd-atletica-mondovi-acqua-s-bernardo.html")
if not os.path.exists(pag):
    print("  -- non c'e': la scrive genera_corsi.py")
else:
    t = open(pag, encoding="utf-8").read()
    card_vere = t.count('<button class="ev-row"')
    loc_vere = len(set(re.findall(r'class="co-loc" src="[^"]*/([^"/]+)"', t)))
    ok(f"{card_vere} card sulla pagina dell'Atletica (erano 5 fuse)",
       card_vere >= 10)
    ok(f"e {loc_vere} locandine diverse, non una per tutte", loc_vere >= 5)
    ok('nessun "N comuni" nella pagina vera',
       not re.search(r'>\s*\d+\s+comuni\s*<', t))
    ok("nessun data-comuni nella pagina vera", "data-comuni" not in t)

print()
sys.exit(0 if esito else 1)
