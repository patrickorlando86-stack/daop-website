#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla la SCADENZA delle schede a pagamento di luoghi.html (Premium_al).

PERCHE' ESISTE (11/09/2026): fino a quel giorno nel foglio c'era solo
Premium_dal, e NIENTE SI SPEGNEVA DA SOLO. Uno spazio non piu' pagato restava
pubblicato - riquadro Sponsorizzati, riga "Sponsorizzato" sulle schede evento,
rel="sponsored", Place nei dati strutturati - finche' qualcuno non se ne
ricordava. Le cose che questo script tiene ferme, e che a occhio non si vedono:

  1. la cella vuota vuol dire "nessuna scadenza", cioe' il comportamento di
     prima: la colonna nuova non spegne nessun cliente che c'era gia';
  2. il giorno della scadenza e' ancora pagato ("al 31/12" comprende il 31);
  3. il giorno dopo non lo e' piu';
  4. una data che non si legge NON spegne la scheda (un refuso in una cella non
     toglie dalla pagina un cliente che ha pagato) ma si segnala;
  5. una data senza "Premium = si" non accende niente.

Uso:
    python scripts/prova_premium_al.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Offline, non tocca il
sito.
"""
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_luoghi as L

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OGGI = datetime.date(2026, 9, 11)

# (Premium, Premium_al, attivo atteso, illeggibile atteso, cosa si prova)
CASI = [
    ('si', '', True, False, "cella vuota: nessuna scadenza, come prima della colonna"),
    ('Sì', '', True, False, "'Sì' con l'accento vale si"),
    ('si', '10/09/2026', False, False, "scaduto ieri: torna una riga normale"),
    ('si', '11/09/2026', True, False, "il giorno della scadenza e' ancora pagato"),
    ('si', '12/09/2026', True, False, "scade domani: ancora attivo"),
    ('si', '2026-12-31', True, False, "formato ISO"),
    ('si', '31-12-26', True, False, "anno a due cifre"),
    ('si', '1.3.2026', False, False, "punti come separatori, data passata"),
    ('si', 'fine anno', True, True, "illeggibile: non spegne, si segnala"),
    ('si', '31/02/2026', True, True, "data impossibile: illeggibile, non spegne"),
    ('no', '31/12/2030', False, False, "senza Premium la data non accende niente"),
    ('', '10/09/2026', False, False, "cella Premium vuota, data passata: niente"),
]

esito = True
for premium, al, att_atteso, ill_atteso, cosa in CASI:
    attivo, scadenza, illeggibile = L.premium_attivo(premium, al, OGGI)
    ok = attivo == att_atteso and illeggibile == ill_atteso
    print(f"  {'ok  ' if ok else 'NO  '} {cosa}  (Premium={premium!r}, Premium_al={al!r} "
          f"-> attivo={attivo}, illeggibile={illeggibile})")
    esito = esito and ok

# La data letta deve essere quella scritta, non solo "una data": un giorno e un
# mese scambiati spegnerebbero a febbraio un cliente pagato fino a dicembre.
for testo, attesa in [('05/12/2026', datetime.date(2026, 12, 5)),
                      ('2026-12-05', datetime.date(2026, 12, 5)),
                      ('5-12-26', datetime.date(2026, 12, 5))]:
    letta = L.data_foglio(testo)
    ok = letta == attesa
    print(f"  {'ok  ' if ok else 'NO  '} '{testo}' si legge {attesa.isoformat()} (letta: {letta})")
    esito = esito and ok

print("\nprova_premium_al:", "tutto a posto" if esito else "QUALCOSA NON TORNA")
sys.exit(0 if esito else 1)
