#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla le icone dei corsi lette da assets/icone/: che il file vinca, che il
ripiego regga, e che un disegno consegnato "come capita" non finisca invisibile.

PERCHE' ESISTE (07/09/2026). L'icona della famiglia "Movimento" era una
BICICLETTA, e su una famiglia che tiene atletica, pallavolo, nuoto, calcio e
psicomotricita' diceva una cosa precisa e sbagliata: sui 22 corsi dell'ASD
Atletica Mondovi' usciva il francobollo del ciclismo. Da qui due cose: le icone
escono dal codice e vanno in una cartella (le mette Patrick, non le disegna il
programma), e possono essere per DISCIPLINA e non solo per famiglia.

Le cose difese qui, e sono tutte cose che a occhio non si vedono:

  1. IL RIPIEGO E' A CATENA e non salta gradini: disciplina, famiglia, disegno
     scritto nel codice. Un file che manca non e' un errore, e' il gradino dopo.
     Togliere un file deve rimettere le cose esattamente come stavano.

  2. IL DIZIONARIO E' NOSTRO. La disciplina si riconosce cercando le PAROLE di un
     elenco chiuso dentro il testo del foglio, non prendendo quel testo per
     buono: il secondo livello della categoria lo scrive il modello e cambia a
     ogni rilettura (il 07/09, sulla sola famiglia Musica, otto diciture per
     quattro corsi). Cosi' "Atletica leggera" e "Atletica Esordienti" prendono
     la stessa icona, e una dicitura mai vista non ne prende una sbagliata.

  3. UN DISEGNO PIENO NON DEVE SPARIRE. Il CSS del sistema e' per le icone a
     linea (fill: none, stroke: currentColor): un'icona a campiture - come la
     esporta un programma di grafica - finirebbe invisibile. Va riconosciuta e
     marcata, altrimenti la pagina esce con dei quadratini vuoti e sembra a
     posto in tutto tranne che agli occhi.

  4. IL COLORE NON ARRIVA DAL FILE. L'icona prende il colore della sua famiglia:
     un nero scritto dentro il disegno lo inchioderebbe a nero dappertutto.

Offline: scrive icone finte in una cartella temporanea. Non tocca la rete e non
riscrive nessuna pagina.
"""
import io
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import genera_corsi as C  # noqa: E402

esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


tmp = tempfile.mkdtemp(prefix="daop_icone_")
C.CARTELLA_ICONE = tmp


def metti(nome, contenuto):
    with open(os.path.join(tmp, f"{nome}.svg"), "w", encoding="utf-8") as fh:
        fh.write(contenuto)
    C._ICONE_FILE.clear()


def togli(nome):
    os.remove(os.path.join(tmp, f"{nome}.svg"))
    C._ICONE_FILE.clear()


def corso(cat):
    return {"cat": cat, "nome": "Corso di prova", "org": "ASD Prova",
            "citta": "Mondovì", "prov": "CN", "eta": "", "annate": "",
            "sede": "", "giorni": "", "codice": "A001", "descr": "",
            "descr_premium": "", "prezzo": "", "prova": "", "iscrizioni": "",
            "periodo": "", "sito": "", "verificato": "", "openday": "",
            "referenti": "", "contatto": "", "loc": "", "premium": "",
            "lat": "", "lng": ""}


ATLETICA = corso("Movimento › Atletica leggera")
PALLAVOLO = corso("Movimento › Pallavolo")
MUSICA = corso("Musica › Musica gioco")

print("\n── il dizionario e' nostro, non del modello ──")
ok("'Atletica leggera' -> atletica", C._nome_disciplina(ATLETICA) == "atletica")
ok("'Atletica Esordienti (Scuole Elementari)' -> lo stesso file",
   C._nome_disciplina(corso("Movimento › Atletica Esordienti")) == "atletica")
ok("i sinonimi puntano allo stesso file (Pallacanestro -> basket)",
   C._nome_disciplina(corso("Movimento › Pallacanestro")) == "basket")
ok("gli accenti non contano (Psicomotricità -> psicomotricita)",
   C._nome_disciplina(corso("Movimento › Psicomotricità")) == "psicomotricita")
ok("una dicitura inventata non prende nessuna icona",
   C._nome_disciplina(corso("Musica › Musica dolce")) == "")
ok("e senza categoria non si inventa niente", C._nome_disciplina(corso("")) == "")

print("\n── il ripiego e' a catena, e togliere un file rimette tutto ──")
LINEA = '<svg viewBox="0 0 24 24" stroke="#000" fill="none"><path d="M2 2 22 22"/></svg>'
PRIMA = C._icona(ATLETICA)
ok("senza file esce il disegno scritto nel codice",
   "M12 17.5V14" in PRIMA or "circle" in PRIMA)

metti("movimento", LINEA)
con_famiglia = C._icona(ATLETICA)
ok("un file di FAMIGLIA scavalca il codice", "M2 2 22 22" in con_famiglia)
ok("e vale anche per un'altra disciplina della stessa famiglia",
   "M2 2 22 22" in C._icona(PALLAVOLO))
ok("ma non tocca le altre famiglie",
   "M2 2 22 22" not in C._icona(MUSICA))

metti("atletica", '<svg viewBox="0 0 24 24" stroke="#000"><path d="M9 9 1 1"/></svg>')
ok("un file di DISCIPLINA scavalca la famiglia", "M9 9 1 1" in C._icona(ATLETICA))
ok("e la pallavolo resta con la sua famiglia",
   "M2 2 22 22" in C._icona(PALLAVOLO))

togli("atletica")
ok("togliendo la disciplina si torna alla famiglia",
   "M2 2 22 22" in C._icona(ATLETICA))
togli("movimento")
ok("togliendo anche la famiglia si torna al codice, identico a prima",
   C._icona(ATLETICA) == PRIMA)

print("\n── un disegno pieno non sparisce ──")
metti("movimento", '<svg viewBox="0 0 24 24"><path d="M1 1h22v22H1z"/></svg>')
piena = C._icona(ATLETICA)
ok("senza tratto dichiarato si marca come piena", 'class="icon is-piena"' in piena)
metti("movimento", LINEA)
ok("con lo stroke sul tag <svg> resta a linea (e' come le fa Lucide)",
   'class="icon"' in C._icona(ATLETICA))
metti("movimento", '<svg viewBox="0 0 24 24"><path stroke-width="2" d="M3 3 9 9"/></svg>')
ok("e con lo stroke-width sul tracciato pure (come i programmi di grafica)",
   'class="icon"' in C._icona(ATLETICA))

print("\n── il colore non arriva dal file ──")
metti("movimento", '<svg viewBox="0 0 24 24" stroke="#000">'
                   '<path stroke="#ff0000" fill="#123456" d="M3 3 9 9"/>'
                   '<circle fill="none" cx="5" cy="5" r="2"/></svg>')
col = C._icona(ATLETICA)
ok("un colore scritto dentro diventa currentColor",
   '#ff0000' not in col and '#123456' not in col
   and col.count('currentColor') == 2)
ok('ma il fill="none" resta quello che era', 'fill="none"' in col)

print("\n── un file storto non rompe la pagina ──")
metti("movimento", "questo non e' un svg")
ok("un file senza <svg> ripiega sul codice", C._icona(ATLETICA) == PRIMA)
metti("movimento", '<svg viewBox="0 0 24 24" stroke="#000">'
                   '<script>alert(1)</script><path d="M1 1 2 2"/></svg>')
pulita = C._icona(ATLETICA)
ok("uno <script> dentro viene tolto", "<script" not in pulita
   and "alert" not in pulita)
ok("e il disegno buono resta", "M1 1 2 2" in pulita)
metti("movimento", '<svg viewBox="0 0 24 24" stroke="#000">'
                   '<path onclick="alert(1)" d="M1 1 3 3"/></svg>')
ok("e un gestore onclick pure", "onclick" not in C._icona(ATLETICA))

print("\n── il viewBox lo detta il file ──")
metti("movimento", '<svg viewBox="0 0 48 48" stroke="#000"><path d="M4 4 44 44"/></svg>')
ok('un viewBox diverso da 24 si porta dietro il suo',
   'viewBox="0 0 48 48"' in C._icona(ATLETICA))
metti("movimento", '<svg stroke="#000"><path d="M4 4 8 8"/></svg>')
ok("e senza viewBox si mette quello di casa (senza, sotto i 24px si taglia)",
   'viewBox="0 0 24 24"' in C._icona(ATLETICA))

print("\n── la cartella vera del sito ──")
C.CARTELLA_ICONE = os.path.join(C.ROOT, 'assets', 'icone')
C._ICONE_FILE.clear()
ok("la cartella c'e' (col suo LEGGIMI, se no git non la tiene)",
   os.path.isdir(C.CARTELLA_ICONE))
sbagliati = [f for f in os.listdir(C.CARTELLA_ICONE)
             if not f.endswith(('.svg', '.md'))]
ok(f"e dentro ci sono solo .svg" + (f" (trovato: {sbagliati})" if sbagliati else ""),
   not sbagliati)
noti = set(C.DISCIPLINE_ICONA.values()) | set(C.ICONE_CAT) | {'altro'}
ignoti = [f[:-4] for f in os.listdir(C.CARTELLA_ICONE)
          if f.endswith('.svg') and f[:-4] not in noti]
ok("ogni .svg ha un nome che il generatore conosce"
   + (f" (ignorati: {ignoti})" if ignoti else ""), not ignoti)

shutil.rmtree(tmp, ignore_errors=True)
print()
sys.exit(0 if esito else 1)
