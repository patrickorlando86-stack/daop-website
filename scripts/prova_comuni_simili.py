#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla il riconoscimento dei COMUNI SCRITTI IN DUE MODI, e soprattutto la
soglia con cui li riconosce.

PERCHE' ESISTE (30/08/2026): nel foglio c'erano insieme "Ceresole Alba" e
"Ceresole d'Alba". Le due grafie hanno prodotto due pagine per lo stesso paese
e - la cosa che e' costata davvero - hanno reso cieco segnala_sovrapposizioni(),
che raggruppa per comune: un doppione vero (la "Consegna dei Libri" del 06/09
alle 11:00, entrata due volte da due locandine) e' passato liscio proprio sotto
il controllo nato per trovarlo.

Il valore da difendere e' SOMIGLIANZA_COMUNI. Il margine e' stretto e non si
vede leggendo il codice: fra il caso vero piu' debole (Entracque / Entraque,
94%) e il primo falso allarme (Ozzano Monferrato / Ponzano Monferrato, due
paesi diversi e distanti, 91%) ci sono tre punti. Abbassare la soglia
"per prendere qualcosa in piu'" riempie la run di coppie da ignorare, e un
avviso che si ignora e' un avviso che non c'e'.

Qui dentro:
  1. i due casi VERI, presi dai comuni veri del sito, vanno segnalati;
  2. le coppie di comuni DIVERSI che si somigliano non vanno segnalate;
  3. una grafia sola, anche sbagliata, non e' un problema: non spacca niente;
  4. il confronto guarda le grafie, non le maiuscole e gli accenti.

Uso:
    python scripts/prova_comuni_simili.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca niente.
"""
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as g

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

esito = True
OGGI = datetime.date.today()


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def evento(citta, prov="CN", riga=1):
    return {"citta": citta, "prov": prov, "riga": riga,
            "nome": f"Un Evento a {citta}", "d_start": OGGI, "d_end": OGGI}


def segnalate(*citta):
    """Le coppie che il controllo stampa, per un foglio con quei comuni."""
    eventi = [evento(c, riga=i + 2) for i, c in enumerate(citta)]
    vero = sys.stdout
    sys.stdout = io.StringIO()
    try:
        g.segnala_comuni_simili(eventi)
        uscita = sys.stdout.getvalue()
    finally:
        sys.stdout = vero
    return {frozenset((a, b)) for a in citta for b in citta
            if a != b and f"{a!r} contro {b!r}" in uscita}


print("=== 1) le due grafie dello stesso paese vengono segnalate ===")
ok("Ceresole Alba / Ceresole d'Alba (il caso del 30/08)",
   segnalate("Ceresole Alba", "Ceresole d'Alba"))
ok("Entracque / Entraque (una lettera in meno)",
   segnalate("Entracque", "Entraque"))

print()
print("=== 2) comuni DIVERSI che si somigliano restano fuori ===")
# Tutte coppie vere del territorio DAOP, non inventate: sono i primi falsi
# allarmi che si presenterebbero abbassando la soglia.
for a, b in [("Ozzano Monferrato", "Ponzano Monferrato"),
             ("Rosignano Monferrato", "Spigno Monferrato"),
             ("Casale Monferrato", "Castelletto Monferrato"),
             ("Valderia", "Valdieri"),
             ("Castelferro", "Castell'Alfero"),
             ("Morsasco", "Osasco"),
             ("Albera Ligure", "Cabella Ligure"),
             ("Brossasco", "Osasco")]:
    ok(f"{a} / {b}", not segnalate(a, b))

print()
print("=== 3) una grafia sola non e' un problema ===")
ok("dieci righe tutte 'Ceresole Alba': nessun avviso",
   not segnalate(*(["Ceresole Alba"] * 10)))
ok("comuni diversissimi: nessun avviso",
   not segnalate("Novi Ligure", "Cuneo", "Asti", "Mondovi"))

print()
print("=== 4) maiuscole e accenti non fanno due paesi ===")
# _key() li appiattisce, quindi queste due grafie hanno la stessa chiave: la
# somiglianza e' 1.0 e la coppia viene segnalata comunque, che e' giusto -
# nel foglio restano due stringhe diverse, e a valle si comportano da due.
ok("'NOVI LIGURE' e 'Novi Ligure' vengono segnalate",
   segnalate("NOVI LIGURE", "Novi Ligure"))

print()
print("=== 5) la soglia e' dove deve stare ===")
ok(f"SOMIGLIANZA_COMUNI = {g.SOMIGLIANZA_COMUNI} (sopra il falso allarme piu' alto, 0.909, "
   f"e sotto il caso vero piu' debole, 0.941)",
   0.909 < g.SOMIGLIANZA_COMUNI <= 0.941)

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
