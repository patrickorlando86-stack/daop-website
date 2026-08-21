#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera /corsi-prova.html: la pagina di PROVA della sezione corsi.

A COSA SERVE. A far vedere con due societa' quello che la pagina vera oggi non
puo' far vedere con una: i filtri che dividono davvero (due discipline, due
comuni), l'elenco piatto ordinato per disciplina, e le due schede realta' in
fondo con le loro ancore #r-…. Nel foglio vero c'e' una societa' sola, quindi
meta' di questa roba li' non si accende — non per un difetto, ma perche' i
comandi si stampano quando dividono.

Serve anche a far vedere la scheda realta' PIENA: nel foglio la tab "Realta"
non esiste ancora, quindi in produzione quelle schede si ricavano dai corsi e
restano scarne. Qui REALTA_DEMO fa le veci di quella tab, ed e' insieme il
mockup e la lista della spesa — quelle sono le colonne da creare.

PERCHE' NON E' UNA PAGINA DEL SITO. Sta fuori dall'indice (noindex) e lo dice
in cima a chi legge, non solo a Google: i dati del teatro vengono dal sito
pubblico della compagnia — sono l'esempio che ha mandato Giovanni il
20/08/2026 — e senza quella fascia basta che il link giri per far credere che
i Santibriganti siano nostri clienti.

Si rigenera con:  python3 scripts/prova_corsi.py

Quando la dimostrazione a Giovanni e' finita si cancellano questo file e
corsi-prova.html: non e' una pagina che il sito debba mantenere, e una pagina
di prova dimenticata online invecchia peggio di qualunque altra.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as G
import genera_corsi as C

# Gli open day sono due eventi VERI di settembre presi dall'agenda, usati come
# segnaposto: quello della PGS non esiste ancora nel foglio. Servono a mostrare
# che il link funziona davvero, invece di puntare a una pagina inventata.
OD_SPORT = 'Festa dello Sport - Evento Finale Plogging Smiling Biking'
OD_TEATRO = 'Un circo in Via Pero - Laboratorio teatrale ed espressivo'

VUOTI = {k: '' for k in C.COLONNE}


def corso(**kw):
    c = dict(VUOTI)
    c.update(kw)
    return c


PGS = [
    ('A001', 'Volley Under 8 M/F', '2019-2020', '6-7 anni',
     'Giovedì 17.30-19.30',
     'Corso di volley per bambini e bambine nati nel 2019 e 2020, con la PGS '
     'Roccavione. Si allenano il giovedì pomeriggio.',
     'Gratuita · open day 10, 17 e 24 settembre', 'Michela'),
    ('A002', 'Volley Under 10 M/F', '2017-2018', '8-9 anni',
     'Lunedì 17.00-18.30 · Mercoledì 17.00-18.30',
     'Corso di volley per bambini e bambine nati nel 2017 e 2018, con la PGS '
     'Roccavione. Due allenamenti a settimana, lunedì e mercoledì.',
     'Gratuita · open day 7, 9, 14 e 16 settembre', 'Alice'),
    ('A003', 'Volley Under 12 M/F', '2015-2016', '10-11 anni',
     'Mercoledì 18.30-20.00 · Venerdì 17.00-18.30',
     'Corso di volley per ragazzi e ragazze nati nel 2015 e 2016, con la PGS '
     'Roccavione. Due allenamenti a settimana, mercoledì e venerdì.',
     'Gratuita · open day 8 e 15 settembre', 'Chiara'),
    ('A004', 'Volley Under 14 F', '2013-2014', '12-13 anni',
     'Lunedì 18.30-20.00 · Giovedì 19.30-21.00',
     'Pallavolo femminile per le ragazze nate nel 2013 e 2014, con la PGS '
     'Roccavione. Due allenamenti a settimana, lunedì e giovedì.',
     'Gratuita · open day 9 e 16 settembre', 'Sara'),
    ('A005', 'Volley Under 15 F', '2012', '13-14 anni',
     'Mercoledì 20.00-21.30 · Venerdì 20.00-21.30',
     'Pallavolo femminile per le ragazze nate nel 2012, con la PGS Roccavione. '
     'Allenamenti serali, mercoledì e venerdì.',
     'Gratuita · open day 10 e 17 settembre', 'Elisa'),
]

corsi = [corso(codice=cod, nome=nome, org='PGS Roccavione',
               cat='Sport › Pallavolo', annate=annate, eta=eta,
               stagione='2026/2027', citta='Roccavione', prov='CN',
               giorni=giorni, descr=descr, prova=prova, referenti=ref,
               openday=OD_SPORT, verificato='19/08/2026',
               periodo='Settembre–maggio',
               sede='Palestra comunale, via Roma 12')
         for cod, nome, annate, eta, giorni, descr, prova, ref in PGS]

# La realta' che ha aderito: l'esempio di Giovanni. Nota che nell'elenco finisce
# PRIMA della PGS soltanto perche' l'ordine e' alfabetico per realta', non
# perche' abbia pagato. E' la stessa regola di luoghi.html, e questa pagina la
# mostra bene proprio perche' il caso e' ambiguo a occhio.
corsi.append(corso(
    codice='A006', nome='Corso di teatro per bambini',
    org='Compagnia Santibriganti Teatro', cat='Espressione › Teatro',
    annate='2015-2020', eta='6-11 anni', stagione='2026/2027',
    citta='Caraglio', prov='CN',
    sede='Teatro Civico di Caraglio, via Roma 118',
    giorni='Una lezione settimanale, il pomeriggio',
    periodo='Ottobre–giugno',
    prova='Open day 22 settembre, 17.30–18.30',
    iscrizioni='Aperte',
    descr='Un percorso per "giocare al teatro".',
    descr_premium='Un percorso per "giocare al teatro": i bambini imparano a '
                  'stare sulla scena partendo dal gioco, e ci arrivano '
                  'attraverso la socializzazione, l\'espressione del corpo e '
                  'della voce e la consapevolezza delle proprie capacità. Non '
                  'si prepara uno spettacolo da mandare a memoria: si '
                  'costruisce insieme, e quello che si porta a casa vale anche '
                  'fuori dal palco.',
    contatto='0171 000000', referenti='Segreteria',
    sito='https://www.santibriganti.it/corsi-teatro-caraglio',
    openday=OD_TEATRO, premium='si', verificato='20/08/2026'))

# NOTA: qui c'era "G.MIN_FILTRI = 2" per forzare la barra dei filtri, che con
# 6 corsi non sarebbe uscita. Dal 20/08/2026 non serve piu': la soglia di
# conteggio e' caduta e i comandi si stampano quando dividono. Questa pagina
# adesso mostra il comportamento VERO del generatore, non una forzatura — che
# e' esattamente quello che una pagina dimostrativa deve fare.

# Le veci della tab "Realta" del foglio, che non esiste ancora. Le chiavi sono
# gli slug dei nomi degli organizzatori, come li produce leggi_realta().
# Indirizzo, telefono e descrizione della PGS sono INVENTATI per far vedere il
# riquadro pieno — ed e' l'ennesima ragione per cui questa pagina sta in
# noindex e lo dice in cima.
REALTA_DEMO = {
    'pgs-roccavione': {
        'descr': 'Polisportiva Giovanile Salesiana di Roccavione: pallavolo '
                 'per bambini e ragazzi dai 6 ai 15 anni, con squadre per '
                 'annata e allenamenti nella palestra comunale.',
        'citta': 'Roccavione', 'indirizzo': 'Palestra comunale, via Roma 12',
        'tel': '0171 000000', 'email': '', 'sito': '', 'logo': '',
    },
    'compagnia-santibriganti-teatro': {
        'descr': 'Compagnia teatrale professionale attiva in Piemonte dal '
                 '1990, con laboratori per bambini e ragazzi al Teatro Civico '
                 'di Caraglio.',
        'citta': 'Caraglio', 'indirizzo': 'Teatro Civico, via Roma 118',
        'tel': '0171 000000', 'email': '', 'logo': '',
        'sito': 'https://www.santibriganti.it',
    },
}

FASCIA = (
    '  <div class="co-prova-avviso">\n'
    '    <strong>Pagina di prova.</strong> Serve a far vedere come potrebbe '
    'essere fatta la sezione corsi: l\'elenco filtrabile dei corsi e, in fondo, '
    'le schede delle realtà che li organizzano. <strong>I dati sono di '
    'esempio</strong> — il corso di teatro è preso dal sito pubblico della '
    'compagnia, e nessuna di queste realtà è un inserzionista. La pagina vera '
    'è <a href="/corsi.html">corsi.html</a>.\n'
    '  </div>\n')

CSS_FASCIA = (
    '.co-prova-avviso{background:#fdf3e0;border:1px solid #e6c98a;'
    'border-radius:10px;padding:14px 16px;margin:0 0 18px;font-size:.94rem;'
    'line-height:1.55;color:#6b4a10}\n'
    '.co-prova-avviso a{color:#6b4a10;font-weight:700}\n')


def main():
    css, nav, foot = G._guscio()
    html = C.render(corsi, css, nav, foot, REALTA_DEMO)

    # 1. FUORI DALL'INDICE. Una pagina di dati finti che si posizionasse su
    #    "corsi per bambini" sarebbe un doppione della pagina vera fatto di roba
    #    non vera, e la penalizzazione si porta dietro il dominio. `follow`
    #    resta, cosi' i link interni continuano a valere.
    # Dal 21/08/2026 la pagina vera puo' essere gia' noindex (CORSI_IN_INDICE
    # in genera_eventi.py): la sostituzione secca non troverebbe niente e
    # fallirebbe in silenzio, che su una pagina di dati finti e' il difetto
    # peggiore che ci sia. Si riscrive il valore qualunque esso sia, e la
    # verifica in fondo lo ricontrolla comunque.
    html = re.sub(r'<meta name="robots" content="[^"]*">',
                  '<meta name="robots" content="noindex, follow">', html, count=1)

    # 2. CANONICAL SU SE STESSA. Ereditata da render() puntava a corsi.html:
    #    con noindex non fa danno, ma "non indicizzarmi" e "la mia versione
    #    buona e' un'altra pagina" sono due ordini che si contraddicono.
    html = html.replace(
        '<link rel="canonical" href="https://www.daop.it/corsi.html">',
        '<link rel="canonical" href="https://www.daop.it/corsi-prova.html">')

    # 3. NIENTE DATI STRUTTURATI. render() dichiara un Course per ogni riga, e
    #    qui dentro ci sono un indirizzo e un telefono inventati per far numero.
    #    Il noindex basterebbe, ma i dati strutturati li leggono anche cose che
    #    non sono Google: su una pagina fatta per un essere umano non servono a
    #    nessuno, e toglierli e' l'unico modo di essere sicuri che nessuna
    #    macchina prenda per buono un corso che non esiste.
    html = re.sub(r'\s*<script type="application/ld\+json">.*?</script>', '',
                  html, flags=re.S)

    # 4. LO DICE A CHI LEGGE. La fascia sta prima dell'H1: chi apre la pagina la
    #    incontra prima di qualunque altra cosa, compreso il bollino.
    html = html.replace(
        '<title>Corsi per bambini in provincia di Cuneo | DAOP</title>',
        '<title>Pagina di prova — Corsi | DAOP</title>')
    # 5. UNA FASCIA SOLA. Da quando /corsi.html sta fuori dall'indice, render()
    #    stampa di suo un avviso "Sezione in preparazione": vero per la pagina
    #    vera, fuori luogo qui, e due riquadri gialli in fila non li legge
    #    nessuno. Quello di render() esce, resta questo — che dice la cosa piu'
    #    importante, cioe' che i dati non sono veri.
    html = re.sub(r'\s*<div class="co-avviso">.*?</div>', '', html, flags=re.S)

    html = html.replace('<main id="contenuto">',
                        '<main id="contenuto">\n' + FASCIA, 1)
    html = html.replace('.co-intro{', CSS_FASCIA + '.co-intro{', 1)

    out = os.path.join(G.ROOT, 'corsi-prova.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)

    print(f"[prova_corsi] scritta {out}")
    print(f"[prova_corsi] {len(corsi)} corsi in "
          f"{len({c['org'] for c in corsi})} realta'")
    # Le tre cose che rendono innocua questa pagina si verificano qui, non a
    # occhio: se una salta, la pagina non va pubblicata.
    for etichetta, ok in (('noindex', 'noindex, follow' in html),
                          ('fascia di avviso', 'co-prova-avviso' in html),
                          ('una fascia sola', 'co-avviso"' not in html),
                          ('canonical propria', 'corsi-prova.html">' in html),
                          ('niente dati strutturati', 'ld+json' not in html)):
        print(f"[prova_corsi] {etichetta}: {'si' if ok else 'NO'}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
