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

# L'OPEN DAY ADESSO E' QUELLO VERO, e non punta piu' a un evento di qualcun
# altro. E' la terza volta che Giovanni inciampa nella stessa cosa: il primo
# segnaposto era una manifestazione lunga un mese (due calendari diversi per la
# stessa cosa, "un po' di casino con le date"), il secondo un evento di un
# giorno solo ma pur sempre altrui — e il 24/08/2026 ha scritto che quel 6
# settembre "non e' quello giusto", chiedendo il post della compagnia o il suo
# sito. Aveva ragione due volte su due, e la lezione e' che un segnaposto che
# si VEDE e' un dato sbagliato: nessuna fascia di avviso lo salva.
#
# L'open day della compagnia nella tab Eventi non c'e' ancora, quindi la cella
# porta il link e la data — vedi openday() in genera_corsi.py: 22 settembre
# 2026 al Teatro Civico di Caraglio, fascia 6-11 anni dalle 17.30, presi dalla
# pagina pubblica santibriganti.it/corsi-teatro-caraglio, la stessa da cui
# viene il resto del corso. Quando l'evento entrera' in agenda qui si rimette
# il nome e tornano scheda, locandina e calendario.
OD_TEATRO = ('https://www.santibriganti.it/corsi-teatro-caraglio'
             ' | Martedì 22 settembre 2026 | 17:30')

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
     'Gratuita, su prenotazione', 'Michela'),
    ('A002', 'Volley Under 10 M/F', '2017-2018', '8-9 anni',
     'Lunedì 17.00-18.30 · Mercoledì 17.00-18.30',
     'Corso di volley per bambini e bambine nati nel 2017 e 2018, con la PGS '
     'Roccavione. Due allenamenti a settimana, lunedì e mercoledì.',
     'Gratuita, su prenotazione', 'Alice'),
    ('A003', 'Volley Under 12 M/F', '2015-2016', '10-11 anni',
     'Mercoledì 18.30-20.00 · Venerdì 17.00-18.30',
     'Corso di volley per ragazzi e ragazze nati nel 2015 e 2016, con la PGS '
     'Roccavione. Due allenamenti a settimana, mercoledì e venerdì.',
     'Gratuita, su prenotazione', 'Chiara'),
    ('A004', 'Volley Under 14 F', '2013-2014', '12-13 anni',
     'Lunedì 18.30-20.00 · Giovedì 19.30-21.00',
     'Pallavolo femminile per le ragazze nate nel 2013 e 2014, con la PGS '
     'Roccavione. Due allenamenti a settimana, lunedì e giovedì.',
     'Gratuita, su prenotazione', 'Sara'),
    ('A005', 'Volley Under 15 F', '2012', '13-14 anni',
     'Mercoledì 20.00-21.30 · Venerdì 20.00-21.30',
     'Pallavolo femminile per le ragazze nate nel 2012, con la PGS Roccavione. '
     'Allenamenti serali, mercoledì e venerdì.',
     'Gratuita, su prenotazione', 'Elisa'),
]

corsi = [corso(codice=cod, nome=nome, org='PGS Roccavione',
               cat='Sport › Pallavolo', annate=annate, eta=eta,
               stagione='2026/2027', citta='Roccavione', prov='CN',
               giorni=giorni, descr=descr, prova=prova, referenti=ref,
               verificato='19/08/2026',
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
    prova='Sì, una lezione di prova gratuita',
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
        # I due domini secchi e non un profilo inventato: qui basta far vedere
        # com'e' fatta la riga, e un URL plausibile ma falso manderebbe chi
        # clicca sul profilo di qualcun altro.
        'instagram': 'https://www.instagram.com/',
        'facebook': 'https://www.facebook.com/',
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

# LA FASCIA STAVA SOTTO LA BARRA FISSA. Giovanni (24/08, dopo il fix
# dell'open day): "vedo ora che c'era questo bannerino ma non lo leggo bene
# tutto". Non era una sua distrazione: la fascia veniva iniettata come primo
# figlio di <main>, dove il padding-top di 96px che compensa la nav fixed non
# c'e' — quel padding vive su .page-hero, che qui viene dopo. Risultato: i
# primi 69px del riquadro finivano DIETRO la barra, cioe' due righe su desktop
# e quattro sul telefono. Un avviso che si legge a meta' e' peggio di nessun
# avviso: quello che nascondeva era proprio la parola "prova".
#
# E il testo era lungo 570 caratteri. Adesso e' meno della meta': prima cos'e'
# la pagina, poi cosa e' finto e cosa no. Chi legge una fascia gialla la legge
# in tre secondi, non in tre frasi.
FASCIA = (
    '  <div class="co-prova-avviso">\n'
    '    <strong>Pagina di prova.</strong> Serve a far vedere com\'è fatta la '
    'sezione corsi. <strong>I dati sono di esempio</strong>: indirizzi e '
    'telefoni sono inventati e nessuna di queste realtà è un inserzionista. '
    'L\'unica cosa vera è l\'open day dei Santibriganti, preso dal loro '
    'sito. La pagina vera è <a href="/corsi.html">corsi.html</a>.\n'
    '  </div>\n')

CSS_FASCIA = (
    # I 96px sono gli stessi di .page-hero, che e' il modo in cui questo sito
    # tiene i contenuti sotto la nav fixed: si copia quella misura invece di
    # inventarne una, cosi' se la barra cambia altezza si cambia in un posto
    # solo. Il calc() sulla larghezza serve al telefono, dove il max-width non
    # morde e il riquadro andrebbe a filo dei bordi.
    '.co-prova-avviso{background:#fdf3e0;border:1px solid #e6c98a;'
    'border-radius:10px;padding:14px 16px;margin:96px auto 18px;'
    'max-width:900px;width:calc(100% - 32px);font-size:.94rem;'
    'line-height:1.55;color:#6b4a10}\n'
    '.co-prova-avviso a{color:#6b4a10;font-weight:700}\n'
    # L'hero che segue si tiene i suoi 96px e sotto la fascia si aprirebbe un
    # buco: la nav l'ha gia' scansata il riquadro.
    '.co-prova-avviso+.page-hero{padding-top:24px}\n')


def innocua(html, canonical):
    """Le quattro cose che rendono innocua una pagina di dati finti.

    Sta in una funzione perche' adesso le pagine sono piu' di una — corsi-prova
    e una per ogni realta' — e quattro trasformazioni ricopiate a mano
    divergerebbero al primo ritocco. Una pagina di prova dimenticata a meta'
    trattamento e' peggio di nessuna pagina di prova."""
    # 1. FUORI DALL'INDICE. Una pagina di dati finti che si posizionasse su
    #    "corsi per bambini" sarebbe un doppione della pagina vera fatto di roba
    #    non vera, e la penalizzazione si porta dietro il dominio. `follow`
    #    resta, cosi' i link interni continuano a valere.
    #    Si riscrive il valore qualunque esso sia, invece di sostituire la
    #    stringa "index, follow": da quando /corsi.html puo' essere gia' noindex
    #    (CORSI_IN_INDICE), la sostituzione secca non troverebbe niente e
    #    fallirebbe in silenzio — il difetto peggiore possibile qui.
    html = re.sub(r'<meta name="robots" content="[^"]*">',
                  '<meta name="robots" content="noindex, follow">', html, count=1)
    # 2. CANONICAL SU SE STESSA. Ereditata da render() puntava a corsi.html:
    #    con noindex non fa danno, ma "non indicizzarmi" e "la mia versione
    #    buona e' un'altra pagina" sono due ordini che si contraddicono.
    html = re.sub(r'<link rel="canonical" href="[^"]*">',
                  f'<link rel="canonical" href="{canonical}">', html, count=1)
    # 3. NIENTE DATI STRUTTURATI. render() dichiara un Course per ogni riga e
    #    la pagina realta' dichiara un'Organization, e qui dentro ci sono un
    #    indirizzo e un telefono inventati per far numero. Il noindex
    #    basterebbe, ma i dati strutturati li leggono anche cose che non sono
    #    Google: toglierli e' l'unico modo di essere sicuri che nessuna macchina
    #    prenda per buona una societa' che non e' nostra cliente.
    html = re.sub(r'\s*<script type="application/ld\+json">.*?</script>', '',
                  html, flags=re.S)
    # 4. LO DICE A CHI LEGGE, e prima di qualunque altra cosa.
    html = re.sub(r'\s*<div class="co-avviso">.*?</div>', '', html, flags=re.S)
    html = html.replace('<main id="contenuto">',
                        '<main id="contenuto">\n' + FASCIA, 1)
    if '.co-intro{' in html:
        html = html.replace('.co-intro{', CSS_FASCIA + '.co-intro{', 1)
    else:
        html = html.replace('.cr-wrap{', CSS_FASCIA + '.cr-wrap{', 1)
    return html


def main():
    css, nav, foot = G._guscio()

    # LE PAGINE DELLE REALTA' FINTE NON VANNO IN /corsi/, che e' la cartella
    # delle pagine vere: una scheda inventata dei Santibriganti fra i clienti
    # veri e' esattamente il danno che questa pagina esiste per evitare. Il
    # generatore legge DIR_REALTA a ogni chiamata, quindi basta spostarlo — e
    # scrivi_realta() ripulisce da se' la cartella di prova.
    C.DIR_REALTA = 'corsi-prova'

    gruppi = {}
    for c in corsi:
        gruppi.setdefault(c['org'] or 'Altre realtà', []).append(c)
    pagine = C.scrivi_realta(gruppi, REALTA_DEMO, css, nav, foot)
    for f in sorted(pagine):
        path = os.path.join(G.ROOT, C.DIR_REALTA, f)
        testo = innocua(open(path, encoding='utf-8').read(),
                        f"{G.SITE_URL}/{C.DIR_REALTA}/{f}")
        open(path, 'w', encoding='utf-8').write(testo)

    html = innocua(C.render(corsi, css, nav, foot, REALTA_DEMO),
                   f"{G.SITE_URL}/corsi-prova.html")
    html = html.replace(
        '<title>Corsi per bambini in provincia di Cuneo | DAOP</title>',
        '<title>Pagina di prova — Corsi | DAOP</title>')

    out = os.path.join(G.ROOT, 'corsi-prova.html')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(html)

    print(f"[prova_corsi] scritta {out}")
    print(f"[prova_corsi] {len(corsi)} corsi in {len(gruppi)} realta', "
          f"{len(pagine)} pagine dedicate in /{C.DIR_REALTA}/")
    # Le cose che rendono innocue queste pagine si verificano qui, non a occhio:
    # se una salta, non vanno pubblicate. Il controllo gira su TUTTE, non solo
    # sulla prima: e' il senso di aver messo le trasformazioni in una funzione.
    tutte = [('corsi-prova.html', html)] + [
        (f, open(os.path.join(G.ROOT, C.DIR_REALTA, f), encoding='utf-8').read())
        for f in sorted(pagine)]
    for nome, testo in tutte:
        prove = (('noindex', 'noindex, follow' in testo),
                 ('fascia di avviso', 'co-prova-avviso' in testo),
                 ('una fascia sola', 'co-avviso"' not in testo),
                 ('canonical propria', f'{C.DIR_REALTA}/{nome}">' in testo
                  or 'corsi-prova.html">' in testo),
                 ('niente dati strutturati', 'ld+json' not in testo))
        esiti = ', '.join(f"{e}: {'si' if ok else 'NO'}" for e, ok in prove)
        print(f"[prova_corsi]   {nome} -> {esiti}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
