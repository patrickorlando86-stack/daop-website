#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlla le guide in PDF: le trasformazioni di stampa e il file prodotto.

PERCHE' ESISTE (24/08/2026). Il PDF e' l'unico artefatto del sito che **non si
puo' correggere dopo**: una pagina sbagliata la riscrive la run di stanotte, un
PDG scaricato su un telefono ci resta. E i difetti che ha avuto nascendo erano
tutti silenziosi — il file c'era, pesava, si apriva, e nessuno diventava rosso:

- il dettaglio delle schede e' un <div hidden>, non un <details>: il PDF usciva
  con le sole righe di intestazione, cioe' senza orari, costi e contatti;
- il confine dell'elenco preso con l'ultimo </article> arrivava fino in fondo
  al corpo, dove pero' c'e' la lista delle EDIZIONI CONCLUSE: otto centri gia'
  finiti finivano mescolati fra quelli aperti, con l'avviso che li dichiarava
  conclusi cancellato insieme al resto. Un genitore avrebbe telefonato per
  iscriversi a un centro chiuso da mesi.

Tutti e due trovati guardando la pagina stampata, non leggendo il codice.
Questo script esiste perche' la prossima volta non serva guardare.

COSA CONTROLLA, e in due parti indipendenti:

1. Le trasformazioni, su una pagina finta costruita qui dentro. Non serve ne'
   rete ne' Chromium ne' il foglio Google, quindi gira sempre e in un secondo.
   E' la parte che difende i due difetti qui sopra.
2. Il file vero, se c'e'. Che sia un PDF, che abbia delle pagine, e che
   data/guide.json non nomini file inesistenti.

Uso:
    python scripts/valida_pdf.py
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import genera_pdf as P            # noqa: E402


# --- La pagina finta ------------------------------------------------------
# Riproduce la struttura vera di centri-estivi.html: due centri aperti in due
# comuni, la guida in prosa, e sotto la sezione delle edizioni concluse con il
# suo avviso. E' minuscola apposta — deve restare leggibile a colpo d'occhio,
# perche' quando una prova diventa rossa la prima domanda e' "cosa c'e' dentro
# il caso di prova".

def _scheda(nome, citta, prov, det):
    return (f'<article class="event-card" data-province="{prov.lower()}" '
            f'data-city="{citta.lower()}">\n'
            f'  <h4 class="ev-h"><button class="ev-row" type="button" '
            f'aria-expanded="false" aria-controls="d-{nome}">\n'
            f'    <img class="ev-thumb" src="https://esempio/{nome}.jpg" alt="">\n'
            f'    <span class="ev-main"><span class="ev-name">{nome}</span>'
            f'<span class="ev-line">{citta} ({prov}) · dal 1 al 30 giugno · '
            f'6-11 anni</span><span class="ev-tags"></span></span>\n'
            f'  </button></h4>\n'
            f'  <div class="ev-det" id="d-{nome}" hidden>\n'
            f'    <p class="event-desc">{det}</p>\n'
            f'    <p class="ce-contatti">Contatti: 0143 000000</p>\n'
            f'  </div>\n'
            f'</article>')


FINTA = f"""  <div class="ev-toolbar"><select id="ce-prov"></select></div>
<div class="events-list" id="ce-active">
{_scheda('Estate Insieme', 'Ovada', 'AL', 'Il dettaglio che deve finire nel PDF.')}
{_scheda('Giochi in Piazza', 'Acqui Terme', 'AL', 'Anche questo.')}
{_scheda('Sport e Natura', 'Ovada', 'AL', 'Stesso comune del primo.')}
</div>
  <p class="events-empty" id="ce-empty">Nessun centro con questi filtri.</p>
<h2 class="ce-past-h">I centri dell'edizione 2025</h2>
<p class="ce-past-note">Le date sono quelle dell'edizione conclusa.</p>
<div class="events-list">
{_scheda('Estate 2025', 'Novi Ligure', 'AL', 'CONCLUSO: non deve stare fra gli aperti.')}
</div>
<section class="ce-guide">
  <h2>Come scegliere un centro estivo</h2>
  <p>Testo della guida.</p>
  <h3>Quando ci si iscrive</h3>
  <p>Fra marzo e maggio.</p>
  <h3>Le domande che contano</h3>
  <p>Rapporto educatori/bambini.</p>
</section>"""


def prove():
    """Torna la lista dei guasti trovati. Vuota = tutto a posto."""
    ko = []

    def ok(cond, cosa):
        if not cond:
            ko.append(cosa)

    # --- estrai(): i marker ------------------------------------------------
    ok(P.estrai('<p>senza marker</p>') is None,
       "estrai() deve tornare None senza marker (meglio nessuna guida che una "
       "guida con dentro la nav e il footer)")
    ok(P.estrai(f'{P.MARK_START} nota -->CORPO{P.MARK_END}') == 'CORPO',
       'estrai() deve prendere quello che sta fra i due marker')
    ok(P.estrai(f'{P.MARK_END}CORPO{P.MARK_START} -->') is None,
       'estrai() deve rifiutare i marker in ordine inverso')

    # --- raggruppa(): il difetto delle edizioni concluse -------------------
    # E' la prova piu' importante di questo file.
    g = P.raggruppa(FINTA)
    passati = g.find('<h2 class="ce-past-h"')
    ok(passati >= 0,
       "raggruppa() ha cancellato la sezione delle edizioni CONCLUSE")
    if passati >= 0:
        dentro = g[:passati].count('class="event-card"')
        fuori = g[passati:].count('class="event-card"')
        ok(dentro == 3,
           f'nei gruppi devono finire le 3 schede aperte, ce ne sono {dentro}')
        ok(fuori == 1,
           f'la scheda conclusa deve restare nella sua sezione, ce ne sono {fuori}')
        ok('CONCLUSO' not in g[:passati],
           'una scheda conclusa e\' finita fra i centri aperti')
    ok(g.count('class="event-card"') == FINTA.count('class="event-card"'),
       'raggruppa() ha perso o duplicato delle schede')
    ok('ce-past-note' in g,
       "l'avviso «le date sono quelle dell'edizione conclusa» e' sparito")

    # --- raggruppa(): i gruppi --------------------------------------------
    comuni = re.findall(r'<h3 class="g-comune">([^<]+)</h3>', g)
    ok(comuni == sorted(comuni, key=lambda x: x.lower()),
       f'i comuni non sono in ordine alfabetico: {comuni}')
    ok(comuni == ['Acqui Terme (AL)', 'Ovada (AL)'],
       f'un comune per gruppo, i doppioni uniti: {comuni}')
    # Dentro un gruppo il comune non si ripete, ma la riga non deve restare
    # vuota: e' la condizione che regge quella potatura.
    ok('<span class="ev-line">dal 1 al 30 giugno' in g,
       'dentro il gruppo il comune deve sparire dalla riga, il resto no')
    ok(not re.search(r'<span class="ev-line">\s*</span>', g),
       'una riga dati e\' rimasta vuota dopo aver tolto il comune')

    # --- documento(): le trasformazioni di impaginazione -------------------
    import datetime
    cfg = P.GUIDE['estivi']
    doc = P.documento('estivi', cfg, FINTA, '2027', datetime.date(2026, 8, 24))
    # Il CSS di stampa NOMINA le classi che nasconde (.ce-guidapdf, .ev-toolbar,
    # …), quindi cercarle nel documento intero da sempre un falso positivo. Le
    # prove sul contenuto guardano il corpo.
    corpo_doc = doc.split('</style>', 1)[-1]

    ok('Il dettaglio che deve finire nel PDF.' in doc,
       'il dettaglio delle schede non e\' nel documento')
    ok('<button' not in doc,
       'un <button> e\' rimasto: accanto a un float scende sotto, e il titolo '
       'finisce sotto la locandina')
    ok('<img' not in doc or 'data:image' in doc,
       'sono rimaste <img> che puntano alla rete: un PDF cosi\' le riscarica a '
       'ogni apertura e mostra un buco a chi legge offline')
    ok('esempio/' not in doc,
       'un URL di locandina non scaricata e\' rimasto nel documento')
    ok('g-cover' in doc, 'manca la copertina')
    ok('g-fine' in doc, 'manca la pagina di chiusura')
    ok('ce-guidapdf' not in corpo_doc,
       'la guida contiene l\'invito a scaricare se stessa')
    ok('<nav' not in corpo_doc and '<footer' not in corpo_doc,
       'nav o footer sono finiti nel documento stampato')

    # L'indice: le voci devono puntare a id che esistono davvero.
    ancore = re.findall(r'<a href="#([^"]+)">', doc)
    ok(len(ancore) >= 3, f'indice troppo corto o assente ({len(ancore)} voci)')
    for a in ancore:
        ok(f'id="{a}"' in doc, f'la voce d\'indice #{a} non porta da nessuna parte')

    # Sotto le tre voci l'indice non si stampa.
    ok(P.indice([(2, 'a', 'Uno'), (2, 'b', 'Due')]) == '',
       'con due voci l\'indice non e\' un indice, e\' una pagina sprecata')

    # --- numeri(): la copertina non deve mentire ---------------------------
    n, comuni_n, prov_n = P.numeri(FINTA)
    ok((n, comuni_n, prov_n) == (4, 3, 1),
       f'i numeri di copertina non tornano: {n} schede, {comuni_n} comuni, '
       f'{prov_n} province')

    return ko


def file_prodotti():
    """Il registro e i PDF veri, se ci sono. Non e' un errore che manchino:
    senza date nel foglio nessuna guida nasce, ed e' voluto."""
    ko = []
    reg_path = os.path.join(ROOT, 'data', 'guide.json')
    if not os.path.exists(reg_path):
        print('[valida_pdf] data/guide.json assente: genera_pdf non e\' ancora girato')
        return ko
    try:
        reg = json.load(open(reg_path, encoding='utf-8'))
    except Exception as e:
        return [f'data/guide.json illeggibile: {e}']
    if not reg:
        print('[valida_pdf] nessuna guida nel registro (nessuna stagione con date)')
        return ko
    for chiave, voce in sorted(reg.items()):
        p = os.path.join(ROOT, voce.get('file', ''))
        if not os.path.exists(p):
            ko.append(f'{chiave}: il registro nomina {voce.get("file")}, che non esiste')
            continue
        dati = open(p, 'rb').read()
        if dati[:4] != b'%PDF':
            ko.append(f'{chiave}: {voce["file"]} non e\' un PDF')
            continue
        pagine = len(re.findall(rb'/Type\s*/Page[^s]', dati))
        if pagine < 3:
            ko.append(f'{chiave}: {pagine} pagine — copertina, indice e chiusura '
                      f'da sole ne fanno tre, quindi il corpo e\' vuoto')
        if str(voce.get('anno', '')) not in voce.get('file', ''):
            ko.append(f'{chiave}: il nome del file non porta l\'anno')
        print(f'[valida_pdf] {voce["file"]}: {pagine} pagine, '
              f'{len(dati) // 1024} kB')
    return ko


def main():
    ko = prove()
    print(f'[valida_pdf] trasformazioni di stampa: '
          f'{"OK" if not ko else str(len(ko)) + " GUASTI"}')
    ko += file_prodotti()
    if ko:
        print(f'[valida_pdf] {len(ko)} GUASTI:')
        for k in ko:
            print(f'    - {k}')
        print('[valida_pdf] un PDF sbagliato non si corregge dopo: va sistemato '
              'prima che la run di stanotte lo pubblichi.')
        return 1
    print('[valida_pdf] nessun guasto.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
