#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla la pagina corsi SENZA CORSI: cosa dice quando non ha niente da dire.

PERCHE' ESISTE (02/09/2026): il ramo vuoto di render() e' l'unico pezzo di
corsi.html che nessuno vede mai. In pagina ci sono undici corsi e ce ne sono
sempre stati, quindi quel ramo non e' mai stato guardato - e infatti diceva
"Le prime schede stanno arrivando", cioe' prometteva che qualcosa stesse per
succedere. E' la stessa promessa sopra il vuoto per cui il 17/08/2026, sui
risultati di Ginetto, e' stata fissata l'invariante: zero schede, intro onesta.

E' il ramo che si accende il giorno dello split (CORSI_PER_PROVINCIA): quando
i corsi si dividono per provincia, Alessandria e Asti nascono senza nemmeno un
corso. Cioe' il codice mai eseguito diventa, in una notte, due pagine su tre.
Un test che gira oggi e' l'unico modo di non scoprirlo quel giorno.

Le prove Playwright in tests/ qui non arrivano: aprono i file HTML su disco, e
un corsi.html vuoto su disco non c'e'. Serve chiamare render() con la lista
vuota, che e' quello che fa questo script.

Qui dentro:
  1. la pagina vuota NON promette (niente "stanno arrivando", niente elenco);
  2. non stampa l'intro da catalogo ("qui trovi quello che c'e', scegli per
     tipo, per eta' e per comune") sopra zero corsi;
  3. non dichiara dati strutturati vuoti - un @graph senza Course e' la stessa
     promessa detta alle macchine;
  4. non nomina un posto: zona() ricava la geografia dai corsi, e senza corsi
     un "in Piemonte" direbbe la regione in cui i corsi ce li abbiamo;
  5. non linka se stessa;
  6. e - il controllo che tiene fermo tutto il resto - con dei corsi dentro la
     pagina e' ancora esattamente quella di prima.

Uso:
    python scripts/prova_corsi_vuoti.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca niente.
"""
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_corsi as c

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def corso(**kw):
    riga = {campo: '' for campo in c.COLONNE}
    riga.update(kw)
    return riga


CAMPIONE = [
    corso(codice='Z001', nome='Minivolley Under 10', org='Societa di Prova',
          cat='Sport', annate='2015-2016', eta='8-10', stagione='2026/2027',
          citta='Roccavione', prov='CN', sede='Palestra comunale',
          giorni='Martedi e giovedi 17:00', prezzo='180 euro', prova='Si',
          descr='Avviamento alla pallavolo.'),
    corso(codice='Z002', nome='Coro Voci Bianche', org='Altra Societa',
          cat='Musica', annate='2013-2018', eta='6-12', stagione='2026/2027',
          citta='Cuneo', prov='CN', giorni='Venerdi 18:00'),
]

CSS, NAV, FOOT = c.G._guscio()
VUOTA = c.render([], CSS, NAV, FOOT, {})
PIENA = c.render(CAMPIONE, CSS, NAV, FOOT, {})


def testo(html):
    """Il testo che legge una persona, senza tag."""
    corpo = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S)
    return re.sub(r'<[^>]+>', ' ', corpo)


print("=== 1) la pagina vuota non promette ===")
ok("non dice 'stanno arrivando'", 'stanno arrivando' not in VUOTA)
ok("non c'e' l'elenco delle schede", 'id="co-lista"' not in VUOTA)
ok("dice che non c'e' ancora nessun corso",
   'ancora nessun corso' in testo(VUOTA))
# La nota deve spiegare che il vuoto e' il dato, non un caricamento a meta'.
ok("dice che e' vuoto davvero, non in caricamento",
   'vuoto davvero' in testo(VUOTA))

print()
print("=== 2) niente intro da catalogo sopra il vuoto ===")
ok("nessun <p class=co-intro>", '<p class="co-intro">' not in VUOTA)
ok("l'intro c'e' quando i corsi ci sono", '<p class="co-intro">' in PIENA)

print()
print("=== 3) niente dati strutturati vuoti ===")
ok("nessun blocco ld+json", 'application/ld+json' not in VUOTA)
ok("il blocco c'e' quando i corsi ci sono", 'application/ld+json' in PIENA)
ok("e dichiara un Course per corso",
   PIENA.count('"@type": "Course"') == len(CAMPIONE))

print()
print("=== 4) la pagina vuota non nomina un posto ===")
titolo = re.search(r'<title>(.*?)</title>', VUOTA).group(1)
h1 = re.search(r'<h1>(.*?)</h1>', VUOTA, re.S).group(1)
descr = re.search(r'name="description" content="(.*?)"', VUOTA).group(1)
# "Piemonte" e' il caso che ha fatto nascere il controllo: e' la regione dove i
# corsi ce li abbiamo, quindi su una pagina che non ne mostra nessuno e'
# peggio di generico, e' falso.
for etichetta, s in (('title', titolo), ('H1', h1), ('description', descr)):
    ok(f"{etichetta} senza geografia: {s!r}",
       not re.search(r'Piemonte|provincia|province', s))
ok("nessun <em> vuoto nell'H1", '<em></em>' not in VUOTA)
ok("nessun doppio spazio nel title", '  ' not in titolo)
ok("con i corsi la provincia torna nel title",
   'provincia di Cuneo' in re.search(r'<title>(.*?)</title>', PIENA).group(1))

print()
print("=== 5) la pagina vuota non linka se stessa ===")
# L'hub non si autolinka; una pagina provincia (FILE diverso) invece deve
# mandare all'hub, che e' l'unico posto dove i corsi ci sono davvero.
ok(f"FILE e' l'hub ({c.FILE}) e la nota non rimanda a se stessa",
   c.FILE != c.FILE_HUB or 'tutti i corsi che abbiamo' not in VUOTA)
ok("la nota manda comunque da qualche parte", '/eventi.html' in VUOTA)

print()
print("=== 6) l'interruttore dello split e' ancora spento ===")
# Se qualcuno lo accende senza fare il resto (sitemap a N hub, FAMIGLIE,
# voce_corsi, link_landing, breadcrumb, valida_jsonld, tests/porte.js) la
# sezione si spacca a meta'. Vedi il commento su CORSI_PER_PROVINCIA.
ok("CORSI_PER_PROVINCIA = False", c.CORSI_PER_PROVINCIA is False)
ok("CORSI_ZONA_ATTESA = ('CN',)", tuple(c.CORSI_ZONA_ATTESA) == ('CN',))

print()
print("=== 7) la guida, le FAQ e i dati strutturati (03/09/2026) ===")
# PERCHE' STANNO QUI e non in tests/corsi.js: quelle prove aprono corsi.html
# su disco, e corsi.html lo riscrive genera_corsi.py, che ha bisogno del foglio
# Google - senza rete resta la pagina di ieri, quindi una prova scritta li'
# sarebbe rossa su qualunque macchina senza rete e verde solo in CI. Qui invece
# si chiama render() con i corsi finti, che e' lo stesso codice: e' la stessa
# ragione per cui esiste tutto il resto di questo file.
ok("con i corsi c'e' la guida 'Come scegliere un corso'",
   'Come scegliere un corso per bambini' in PIENA)
# L'ATTRIBUTO INTERO e non il nome secco: '.co-guida' sta anche nel <style>,
# che e' incollato in ogni pagina — un `in` sul nome direbbe "c'e' la guida"
# anche sulla pagina vuota e la prova passerebbe sempre. E' la stessa trappola
# gia' documentata per ev-ginetto-alto.
ok("la guida NON si stampa sopra il vuoto", 'class="co-guida"' not in VUOTA)
# Le tre cose che la guida NON deve promettere, ed e' la ragione per cui e'
# stata scritta in sei sezioni e non nelle nove del documento: sono i dati che
# il foglio tiene facoltativi per decisione di Giovanni (21/08/2026). Una
# guida che dice "controlla il costo" sotto un elenco in cui il costo non c'e'
# mai e' l'occhiello che li prometteva, spostato piu' in basso.
ok("la description non promette piu' i costi",
   'costi' not in re.search(r'name="description" content="(.*?)"', PIENA).group(1))
ok("ne' i giorni",
   'giorni' not in re.search(r'name="description" content="(.*?)"', PIENA).group(1))

ok("con i corsi ci sono le FAQ", 'class="faq"' in PIENA)
ok("le FAQ non si stampano sopra il vuoto", 'class="faq"' not in VUOTA)
# L'INVARIANTE CHE CONTA: quello che si dichiara a Google e' quello che si
# vede. Non e' garantito da una convenzione, e' garantito da faq_blocco(), che
# costruisce i due da una lista sola - questa prova verifica che la garanzia
# regga davvero invece di fidarsi. tests/faq.js lo rifa' su tutto il sito.
import json as _json
_dom_html = re.findall(r'<summary>(.*?)</summary>', PIENA, re.S)
_grafo = _json.loads(re.search(
    r'<script type="application/ld\+json">\s*(.*?)\s*</script>', PIENA, re.S).group(1))
_tipi = [n.get('@type') for n in _grafo['@graph']]
_faq = [n for n in _grafo['@graph'] if n.get('@type') == 'FAQPage']
ok("il FAQPage e' dichiarato una volta sola", len(_faq) == 1)
ok(f"tante domande dichiarate quante visibili ({len(_dom_html)})",
   len(_faq[0]['mainEntity']) == len(_dom_html) and len(_dom_html) > 0)

# I QUATTRO PEZZI CHE MANCAVANO. Misurato il 03/09/2026: corsi.html dichiarava
# Course e Organization e basta - niente briciole (il crumb in pagina c'era, il
# markup no), niente ItemList, niente CollectionPage, niente WebSite. Le pagine
# generate da genera_eventi.py le hanno da mesi.
for _t in ('CollectionPage', 'BreadcrumbList', 'ItemList', 'Course'):
    ok(f"il grafo dichiara {_t}", _t in _tipi)
_lista = [n for n in _grafo['@graph'] if n.get('@type') == 'ItemList'][0]
ok("l'ItemList ha una voce per corso", _lista['numberOfItems'] == len(CAMPIONE))
# Ogni voce punta a un'ancora che in pagina esiste davvero: un ItemList che
# rimanda a un #id inventato scarica in cima a una pagina lunga, ed e' la
# stessa regola gia' scritta per link_luoghi().
_rotte = [v['url'] for v in _lista['itemListElement']
          if f'id="{v["url"].split("#")[-1]}"' not in PIENA]
ok("ogni voce dell'ItemList cade su un'ancora che esiste", not _rotte)
ok("con zero corsi non c'e' nessun grafo", 'application/ld+json' not in VUOTA)

# L'invito al canale: c'era su 323 pagine e non su questa, che e' l'unica del
# sito con una presenza pagata dentro.
ok("l'invito al canale c'e'", 'ev-canale' in PIENA)
ok("e non e' doppio", PIENA.count('class="ev-canale"') == 1)
ok("niente invito sopra il vuoto", 'ev-canale' not in VUOTA)
ok("la data di aggiornamento e' in pagina", 'Ultimo aggiornamento' in PIENA)

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
