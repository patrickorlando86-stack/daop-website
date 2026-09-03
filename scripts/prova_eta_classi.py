#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla che le CLASSI non vengano lette come ANNI.

PERCHE' ESISTE (03/09/2026). Sul foglio l'ASD Atletica Mondovi' ha le eta'
scritte come le dice una societa' sportiva - "1a e 2a media", "3a media e 1a
superiore", "da 2a superiore", "scuole elementari" - e il filtro le leggeva come
anni, perche' eta_da_testo() prendeva i numeri e basta:

    "1a e 2a media"            -> fascia  1-2     (sono 11-12)
    "3a media e 1a superiore"  -> fascia  1-3     (sono 13-14)
    "da 2a superiore"          -> fascia  2-18    (sono 15-18)
    "3a media"                 -> fascia  3-18    (sono 13)
    "scuole elementari"        -> NESSUNA fascia  (sono 6-10)

COSA SI VEDEVA, ed e' come l'ha trovato Patrick: filtrando 0-3 anni uscivano
tutti i corsi di atletica delle medie e delle superiori - le fasce 1-2, 2-18 e
3-18 toccano tutte lo 0-3 - e filtrando 6-8 anni ne usciva UNO SOLO, la 3a
media, l'unico la cui fascia sbagliata arrivava fin la'. Chi cercava per un
bambino di 7 anni si vedeva proposto un corso per quattordicenni e NON vedeva le
elementari, che di fascia non ne avevano nessuna.

Quindici corsi su quindici sbagliati, e nessuno se ne accorgeva guardando la
pagina: la riga scrive le parole ("1a e 2a media"), che sono giuste. A sbagliare
era solo il numero dietro, quello su cui filtra.

Qui dentro:
  1. le cinque forme vere del foglio danno le fasce vere;
  2. il numero davanti alla classe conta DENTRO il ciclo (3a media = 13 anni);
  3. senza numero vale il ciclo intero;
  4. "da" apre in alto, come per le eta' a parole;
  5. e le eta' scritte in ANNI continuano a funzionare come prima - comprese le
     tre che tests/corsi.js sorveglia (mesi, "dai N", "fino a N").

Uso:
    python scripts/prova_eta_classi.py

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


def prova(testo, atteso):
    avuto = g.eta_da_testo(testo)
    verifica(f"{testo!r} -> {avuto} (atteso {atteso})", avuto == atteso)


print("=== le cinque forme vere del foglio ===")
prova("1a e 2a media", (11, 12))
prova("3a media e 1a superiore", (13, 14))
prova("da 2a superiore", (15, 18))
prova("scuole elementari", (6, 10))
prova("3a media", (13, 13))

print("\n=== come le scrivono davvero: accenti, spazi, maiuscole ===")
# Sul foglio convivono tutte e tre le grafie, scritte da mani diverse.
prova("1ª e 2ª media", (11, 12))
prova("1 e 2 media", (11, 12))
prova("3ª media e 1ª superiore", (13, 14))
prova("Scuole Elementari", (6, 10))

print("\n=== il numero conta dentro il ciclo, non in assoluto ===")
prova("1a media", (11, 11))
prova("5a elementare", (10, 10))
prova("1a superiore", (14, 14))
prova("5a superiore", (18, 18))

print("\n=== senza numero, il ciclo intero ===")
prova("scuole medie", (11, 13))
prova("scuola materna", (3, 5))
prova("asilo nido", (0, 2))

print("\n=== le eta' in ANNI continuano a funzionare ===")
# Sono i casi gia' sorvegliati da tests/corsi.js: se questi cambiano, cambia il
# significato della pagina, non solo dei corsi di atletica.
prova("6-13 anni", (6, 13))
prova("3-4 anni", (3, 4))
prova("3-6 anni", (3, 6))
prova("dai 4 anni", (4, 18))
prova("fino a 10 anni", (0, 10))
prova("0-12 mesi", (0, 1))

print("\n=== e cio' che non e' una fascia resta senza fascia ===")
# "Tutte le eta'" non e' un filtro, e' l'assenza di filtro: dargli una fascia
# vorrebbe dire farlo comparire in tutti i filtri o in nessuno.
prova("tutte le età", None)
prova("", None)
prova("   ", None)

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
