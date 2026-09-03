#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla la CODA del messaggio del canale: le altre cose che DAOP fa.

PERCHE' ESISTE (03/09/2026). Il messaggio del giovedi' parlava solo del weekend,
e chi lo riceve non sa che esistono l'app di Ginetto, il Piatto Sano e i libri.
Chiesto di metterceli.

LA SCELTA CHE VA DIFESA: uno per settimana, non tutti e tre. Metterli tutti
raddoppia il messaggio, e un messaggio che raddoppia si smette di leggere
proprio dove finisce la parte per cui uno si e' iscritto - gli eventi. Uno solo
alla volta sta in fondo senza pesare e ha lo spazio per dire cos'e' invece di
essere una riga di link.

E la rotazione va sul NUMERO DI SETTIMANA, non a caso. Il generatore gira ogni
notte e piu' volte al giorno quando si rifa' il sito: con un random, il
messaggio cambierebbe sotto le mani di chi lo sta copiando, e due copie dello
stesso giovedi' direbbero cose diverse.

Qui dentro:
  1. lo stesso giorno da' sempre lo stesso testo, quante volte lo si chiami;
  2. settimane diverse ruotano, e nel giro di tre passano tutte e tre;
  3. i link ci sono e non sono segnaposto;
  4. la coda non e' cosi' lunga da coprire gli eventi.

Uso:
    python scripts/prova_coda_canale.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca niente.
"""
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as g

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

esito = True


def verifica(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


GIOVEDI = [datetime.date(2026, 9, 3), datetime.date(2026, 9, 10),
           datetime.date(2026, 9, 17), datetime.date(2026, 9, 24)]

print("=== lo stesso giovedi' da' sempre lo stesso testo ===")
# Il generatore gira piu' volte nello stesso giorno: se cambiasse, cambierebbe
# sotto le mani di chi ha appena premuto "Copia msg WhatsApp".
uno = g.coda_del_canale(GIOVEDI[0])
verifica("richiamata due volte, identica", uno == g.coda_del_canale(GIOVEDI[0]))
verifica("...e tre", uno == g.coda_del_canale(GIOVEDI[0]))

print("\n=== settimane diverse, cose diverse ===")
testi = [g.coda_del_canale(d) for d in GIOVEDI[:3]]
verifica("tre settimane, tre testi diversi", len(set(testi)) == 3)
verifica("alla quarta si ricomincia", g.coda_del_canale(GIOVEDI[3]) == testi[0])

print("\n=== nel giro passano tutte e tre ===")
tutte = " ".join(testi)
verifica("c'e' Ginetto", "ginettoapp.it" in tutte)
verifica("c'e' il Piatto Sano", "ilpiattosano" in tutte)
verifica("ci sono i libri", "/libri.html" in tutte)

print("\n=== i link sono link, non segnaposto ===")
for d in GIOVEDI[:3]:
    t = g.coda_del_canale(d)
    verifica(f"settimana {d.isocalendar()[1]}: ha un indirizzo vero",
             "https://" in t and "{" not in t and "}" not in t)

print("\n=== corta abbastanza da non coprire gli eventi ===")
# Il messaggio del weekend sta sui 900 caratteri: una coda che ne aggiunge piu'
# di 400 sposterebbe il baricentro dalla parte sbagliata.
for d in GIOVEDI[:3]:
    t = g.coda_del_canale(d)
    verifica(f"settimana {d.isocalendar()[1]}: {len(t)} caratteri", len(t) <= 400)
verifica("e ognuna ha il suo titolo in grassetto",
         all(x.count("*") >= 2 for x in testi))

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
