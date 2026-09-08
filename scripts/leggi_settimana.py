#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La lettura del mercoledi', tutta: Search Console e GA4 sulla stessa cartella.

    python3 scripts/leggi_settimana.py gsc/2026-09-09
    python3 scripts/leggi_settimana.py                  # l'ultima cartella in gsc/
    python3 scripts/leggi_settimana.py --no-salva

PERCHE' UN TERZO FILE INVECE DI FONDERE I DUE
---------------------------------------------
Perche' rispondono a due domande diverse e possono servire separate: Search
Console dice **chi ci trova**, GA4 dice **cosa fanno quelli che sono arrivati**.
Fonderli vorrebbe dire un file che sa di Google due volte, e soprattutto vorrebbe
dire che una settimana in cui GA4 non si scarica (permesso scaduto, API spenta)
si porta giu' anche la lettura di Search Console, che invece funzionerebbe
benissimo. Qui se manca una meta' l'altra si legge lo stesso, e lo dice.

L'ordine non e' indifferente: **prima GSC, poi GA4**, perche' `leggi_ga4.py`
calcola la copertura contro i clic di Search Console e vuole `Grafico.csv` gia'
in cartella - e perche' la domanda «chi ci trova» viene prima di «cosa fanno».
"""

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent
sys.path.insert(0, str(RADICE))

import leggi_gsc                                    # noqa: E402
import leggi_ga4                                    # noqa: E402


def main(argv):
    salva = '--no-salva' not in argv
    resto = [a for a in argv if not a.startswith('--')]
    dove = Path(resto[0]) if resto else leggi_gsc.ultima_cartella()
    if not dove:
        raise SystemExit(
            "[settimana] nessuna cartella indicata e gsc/ e' vuota.\n"
            "            Dal downloader: il bottone \"Scarica dati Search"
            " Console\".")

    fatte = []
    try:
        leggi_gsc.leggi(dove, salva=salva)
        fatte.append('Search Console')
    except SystemExit as e:
        print(f"\n[settimana] la meta' Search Console non si legge: {e}")

    print('\n')
    try:
        leggi_ga4.leggi(dove, salva=salva)
        fatte.append('GA4')
    except SystemExit as e:
        print(f"\n[settimana] la meta' GA4 non si legge: {e}")

    print('\n' + '=' * 78)
    if len(fatte) == 2:
        print("  Lette tutte e due le meta'. Quello che si confronta fra")
        print("  settimane e' il CTR delle schede (GSC) e la copertura (GA4);")
        print("  il CTR aggregato no, quando in agenda c'e' un capoluogo.")
    else:
        print(f"  Letta solo: {', '.join(fatte) or 'nessuna'}."
              " L'altra meta' manca, e sopra c'e' il perche'.")
    print('=' * 78)


if __name__ == '__main__':
    main(sys.argv[1:])
