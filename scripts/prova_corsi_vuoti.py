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
  6. lo split e' acceso (dal 06/10/2026) e le province attese sono le tre;
  7. la pagina provincia vuota - Asti il giorno dello split - dice la sua
     provincia, manda all'hub e sta fuori indice;
  8. le porte delle province non portano verso una provincia senza corsi.

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
print("=== 6) lo split e' acceso, e le province attese sono quelle del sito ===")
# Acceso il 06/10/2026 col primo corso di Alessandria. Le province attese sono
# quelle che una pagina ce l'hanno: se divergono, una provincia nuova non
# suonerebbe piu' (o suonerebbe una che la pagina ce l'ha gia').
ok("CORSI_PER_PROVINCIA = True", c.CORSI_PER_PROVINCIA is True)
ok("CORSI_ZONA_ATTESA = le province del sito",
   tuple(c.CORSI_ZONA_ATTESA) == tuple(c.G.PROVINCE_PUBBLICATE))

print()
print("=== 7) la pagina provincia vuota (Asti, il giorno dello split) ===")
# E' il ramo per cui la nota vuota e' stata scritta: una pagina provincia
# senza corsi. Qui il posto SI nomina - e' la provincia della pagina, non una
# geografia dedotta dai corsi - e la nota manda all'hub.
VUOTA_AT = c.render([], CSS, NAV, FOOT, {}, prov='AT')
PIENA_CN = c.render(CAMPIONE, CSS, NAV, FOOT, {}, prov='CN')
ok("l'H1 dice la provincia",
   'in provincia di Asti' in re.search(r'<h1>(.*?)</h1>', VUOTA_AT, re.S).group(1))
ok("dice che non c'e' ancora nessun corso", 'ancora nessun corso' in testo(VUOTA_AT))
ok("la nota manda all'hub", 'href="/corsi.html">tutti i corsi che abbiamo' in VUOTA_AT)
ok("canonical su se stessa",
   'rel="canonical" href="https://www.daop.it/corsi-provincia-asti.html"' in VUOTA_AT)
ok("vuota = fuori indice", 'content="noindex, follow"' in VUOTA_AT)
ok("il percorso torna all'hub",
   '<a href="/corsi.html">Corsi per bambini</a> › <span>Provincia di Asti</span>' in VUOTA_AT)
ok("nessun blocco ld+json", 'application/ld+json' not in VUOTA_AT)
# Due corsi sono sotto MIN_LANDING: anche piena, resta fuori indice.
ok(f"sotto {c.G.MIN_LANDING} corsi resta fuori indice",
   'content="noindex, follow"' in PIENA_CN)
ok("prov_in_indice segue MIN_LANDING",
   c.prov_in_indice(c.G.MIN_LANDING) is bool(c.G.CORSI_IN_INDICE)
   and c.prov_in_indice(c.G.MIN_LANDING - 1) is False)

print()
print("=== 8) le porte delle province non promettono il vuoto ===")
porte = c.porte_province({'CN': 3, 'AL': 1})
ok("sull'hub: le province con corsi", 'corsi-provincia-cuneo.html' in porte
   and 'corsi-provincia-alessandria.html' in porte)
ok("Asti, senza corsi, non c'e'", 'corsi-provincia-asti.html' not in porte)
ok("sulla pagina di Cuneo non c'e' Cuneo",
   'corsi-provincia-cuneo.html' not in c.porte_province({'CN': 3, 'AL': 1}, qui='CN'))
ok("nessuna provincia con corsi = nessuna riga", c.porte_province({}) == '')

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
