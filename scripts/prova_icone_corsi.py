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
    C._ICONE_RASTER.clear()


def togli(nome, est=".svg"):
    os.remove(os.path.join(tmp, f"{nome}{est}"))
    C._ICONE_FILE.clear()
    C._ICONE_RASTER.clear()


def illustra(nome, est=".webp"):
    """Un'illustrazione finta. Il contenuto non conta: genera_corsi.py non la
    apre nemmeno - guarda che il file ci sia e ne stampa l'indirizzo. Chi la
    normalizza e' genera_icone.py, ed e' un altro mestiere."""
    with open(os.path.join(tmp, f"{nome}{est}"), "wb") as fh:
        fh.write(b"finta")
    C._ICONE_FILE.clear()
    C._ICONE_RASTER.clear()


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

print("\n── l'illustrazione riempie il quadrato, e vince sul disegno ──")
# La regola: dentro lo STESSO gradino l'illustrazione batte il disegno a linea,
# ma fra due gradini vince sempre il piu' specifico. Cioe' la disciplina giusta
# conta piu' del formato, ed e' l'unico ordine in cui aggiungere
# un'illustrazione di famiglia non puo' PEGGIORARE una riga che aveva gia' la
# sua disciplina.
illustra("movimento")
ill = C._icona(ATLETICA)
ok("un'illustrazione di FAMIGLIA scavalca il codice", 'class="ev-ico"' in ill)
ok("ed esce come <img>, non come <svg> (il quadrato lo riempie)",
   "<img" in ill and "<svg" not in ill)
ok("con l'indirizzo assoluto dalla radice (le pagine realta' stanno in /corsi/)",
   'src="/assets/icone/movimento.webp"' in ill)
ok("e con width e height, cioe' il rapporto 1:1 dichiarato: niente salto",
   'width="60" height="60"' in ill)
ok("non e' bloccante: loading=lazy come le miniature dell'agenda",
   'loading="lazy"' in ill)
ok("vale per un'altra disciplina della stessa famiglia",
   'class="ev-ico"' in C._icona(PALLAVOLO))
ok("ma non tocca le altre famiglie", 'class="ev-ico"' not in C._icona(MUSICA))

metti("movimento", LINEA)
ok("nello stesso gradino l'illustrazione batte il disegno a linea",
   'class="ev-ico"' in C._icona(ATLETICA))

metti("atletica", '<svg viewBox="0 0 24 24" stroke="#000"><path d="M9 9 1 1"/></svg>')
solo_disc = C._icona(ATLETICA)
ok("ma il gradino piu' specifico vince sul formato: "
   "atletica.svg batte movimento.webp",
   "M9 9 1 1" in solo_disc and 'class="ev-ico"' not in solo_disc)
illustra("atletica")
ok("e l'illustrazione della disciplina batte il suo disegno",
   'src="/assets/icone/atletica.webp"' in C._icona(ATLETICA))

togli("atletica", ".webp")
togli("atletica")
togli("movimento")
togli("movimento", ".webp")
ok("togliendo tutto si torna al codice, identico a prima",
   C._icona(ATLETICA) == PRIMA)

illustra("movimento", ".png")
ok("un .png vale come illustrazione (arriva prima della conversione)",
   'src="/assets/icone/movimento.png"' in C._icona(ATLETICA))
illustra("movimento")
ok("ma se c'e' anche il .webp vince quello, che e' il file buono",
   'src="/assets/icone/movimento.webp"' in C._icona(ATLETICA))
togli("movimento", ".webp")
togli("movimento", ".png")

print("\n── il CSS che regge l'illustrazione e' arrivato in pagina ──")
# Senza questa regola l'illustrazione non si rompe - l'<img> ha width e height
# suoi - ma perde object-fit e gli angoli tondi. Il guasto vero che si prende
# qui e' un altro, ed e' capitato altre volte: daop-system.css modificato e
# build_css.py non rilanciato, quindi la regola non arriva a nessuna pagina.
_min = os.path.join(C.ROOT, 'assets', 'css', 'daop-system.min.css')
with io.open(_min, encoding='utf-8') as fh:
    _css = fh.read()
# Il selettore si cerca COL SUO '{' attaccato, che e' la forma che esce dal
# minificatore. Cercando la sola stringa '.ev-thumb.is-ph .ev-ico' la prova
# passava anche rinominando la regola in '.ev-ico-NO': un nome piu' lungo
# contiene quello giusto. Trovato verificando che la prova diventasse rossa, e
# non lo diventava.
_REGOLA = '.ev-thumb.is-ph .ev-ico{'
ok(".ev-thumb.is-ph .ev-ico c'e' nel .min.css (se no: build_css.py)",
   _REGOLA in _css)
ok("con object-fit:contain e non cover (a un disegno si taglierebbe la testa)",
   _REGOLA in _css
   and 'object-fit:contain' in _css.split(_REGOLA)[1].split('}')[0])

print("\n── la cartella vera del sito ──")
C.CARTELLA_ICONE = os.path.join(C.ROOT, 'assets', 'icone')
C._ICONE_FILE.clear()
ok("la cartella c'e' (col suo LEGGIMI, se no git non la tiene)",
   os.path.isdir(C.CARTELLA_ICONE))
# Cosa ci sta di diritto: i disegni a linea (.svg), le illustrazioni pronte
# (.webp), il LEGGIMI e la sottocartella sorgenti/ coi disegni grandi. Un .png
# o un .jpg qui NON ci sta: genera_icone.py lo sposta in sorgenti/ al primo
# giro, quindi trovarcelo vuol dire che quello script non e' passato - e
# intanto ai lettori si sta servendo un file da un megabyte dentro un
# francobollo da 60px.
AMMESSI = ('.svg', '.webp', '.md')
sbagliati = [f for f in os.listdir(C.CARTELLA_ICONE)
             if os.path.isfile(os.path.join(C.CARTELLA_ICONE, f))
             and not f.endswith(AMMESSI)]
ok("dentro ci sono solo .svg, .webp e il LEGGIMI"
   + (f" (trovato: {sbagliati}: lancia scripts/genera_icone.py)"
      if sbagliati else ""),
   not sbagliati)
noti = set(C.DISCIPLINE_ICONA.values()) | set(C.ICONE_CAT) | {'altro'}
ignoti = [os.path.splitext(f)[0] for f in os.listdir(C.CARTELLA_ICONE)
          if f.endswith(('.svg', '.webp'))
          and os.path.splitext(f)[0] not in noti]
ok("ogni icona ha un nome che il generatore conosce"
   + (f" (ignorati: {ignoti})" if ignoti else ""), not ignoti)

# I sorgenti si tengono, perche' un'illustrazione rigenerata cambia stile e lo
# stile e' l'unica cosa capace di rovinare un set. Ma questa e' una NOTA e non
# una prova: un .webp messo a mano e mai passato da genera_icone.py e' uno
# stato legittimo, e una prova rossa quando il sito e' giusto e' il difetto che
# questo repo ha gia' pagato sei volte.
_srg = os.path.join(C.CARTELLA_ICONE, 'sorgenti')
if os.path.isdir(_srg):
    _hanno = {os.path.splitext(f)[0] for f in os.listdir(_srg)}
    _orfane = sorted({os.path.splitext(f)[0]
                      for f in os.listdir(C.CARTELLA_ICONE)
                      if f.endswith('.webp')} - _hanno)
    if _orfane:
        print(f"  nota: illustrazioni senza il loro sorgente in sorgenti/: "
              f"{_orfane} (rigenerarle cambierebbe lo stile)")

shutil.rmtree(tmp, ignore_errors=True)
print()
sys.exit(0 if esito else 1)
