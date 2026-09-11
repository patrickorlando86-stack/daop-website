#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I testi dei corsi scritti DAI DATI: l'hero e la description di corsi.html, il
paragrafo d'apertura delle pagine realta', le domande frequenti.

PERCHE' ESISTE (11/09/2026). Nascono dall'analisi SEO di Giovanni, e la prima
stesura di quei testi aveva tre difetti che nessuna pagina avrebbe mostrato
come errore: nominava sette comuni di cui quattro senza corsi, prometteva giorni
e orari che sono colonne facoltative, e metteva in fondo domande con una
risposta che poteva solo dire "no". Le decisioni difese qui:

  1. UN COMUNE SI NOMINA SOLO SE HA CORSI, e un'attivita' solo se c'e'.
  2. NESSUN TESTO PROMETTE GIORNI, ORARI O COSTI.
  3. UNA DOMANDA SENZA DATI NON SI STAMPA, e nessuna risposta comincia con
     "no": un dato che manca non e' un no.
  4. "LINGUE" DIVENTA "INGLESE" SOLO SE E' VERO PER TUTTI i corsi di lingue.
  5. "AD" DAVANTI A VOCALE nel title delle realta' ("ad Alba", non "a Alba").
  6. NIENTE FAQPage in JSON-LD: Google ha spento quei risultati il 07/05/2026.

Nessuna prova conta i corsi veri: sarebbe rossa alla prima riga nuova del
foglio. Si lavora su corsi finti costruiti qui.

Offline, due secondi.
"""
import io
import os
import re
import sys

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


def corso(**kw):
    c = {k: '' for k in C.COLONNE}
    c.update(kw)
    return c


DOVE = 'in provincia di Cuneo'
INGLESE = [
    corso(codice='T1', nome='Inglese 4 anni', org='Scuola Finta', cat='Lingue › Lingue',
          citta='Alba', prov='CN', eta='4-5 anni', sede='Corso Piave 16'),
    corso(codice='T2', nome='Inglese 2 anni', org='Scuola Finta', cat='Lingue › Lingue',
          citta='Alba', prov='CN', eta='2-3 anni', sede='Corso Piave 16',
          prova='Gratuita'),
]
ATLETICA = [
    corso(codice='T3', nome='Esordienti', org='ASD Finta', cat='Movimento › Atletica leggera',
          citta='Moretta', prov='CN', eta='6-10 anni', sede='Palestra comunale'),
    corso(codice='T4', nome='Ragazzi', org='ASD Finta', cat='Movimento › Atletica leggera',
          citta='Moretta', prov='CN', eta='11-12 anni'),
]
TEATRO = [
    corso(codice='T5', nome='Recitazione', org='Teatro Finto', cat='Teatro › Recitazione',
          citta='Caraglio', prov='CN', eta='8-14 anni'),
]
TUTTI = INGLESE + ATLETICA + TEATRO
PROMESSE = re.compile(r'\b(giorni|orari|costi|prezzi|quota)\b', re.I)


def testi_hub(corsi):
    return [C.testo_hero(corsi, DOVE), C.testo_numeri(corsi), C.descr_corsi(corsi, DOVE)] + [
        f"{q} {a}" for q, a in C.faq_corsi(corsi, DOVE)]


print("1. i comuni nominati sono solo quelli con corsi")
tutto = ' '.join(testi_hub(TUTTI))
ok("Alba, Moretta e Caraglio ci sono", all(x in tutto for x in ('Alba', 'Moretta', 'Caraglio')))
assenti = [x for x in ('Bra', 'Fossano', 'Saluzzo', 'Savigliano', 'Mondovì')
           if re.search(rf'\b{x}\b', tutto)]
ok(f"nessun comune senza corsi (trovati: {assenti or 'nessuno'})", not assenti)
senza_prov = re.sub(r'provincia di Cuneo', '', tutto)
ok("'Cuneo' compare solo come provincia", 'Cuneo' not in senza_prov)
ok("le attivita' che non ci sono non si nominano (danza, musica)",
   not re.search(r'\b(danza|musica)\b', tutto, re.I))
molti = [corso(codice=f'M{i}', nome=f'Corso {i}', org='X', cat='Musica › Coro',
               citta=f'Paese{i}', prov='CN', eta='6-10 anni') for i in range(10)]
hero = C.testo_hero(molti, DOVE)
ok(f"oltre {C.MAX_COMUNI_TESTO} comuni chiude con la coda: {hero!r}",
   f'in altri {10 - C.MAX_COMUNI_TESTO} comuni' in hero)

print("2. nessuna promessa su giorni, orari o costi")
ok("hub", not any(PROMESSE.search(t) for t in testi_hub(TUTTI)))
ok("pagina realta'", not any(PROMESSE.search(t) for t in
                             [C.testo_realta('Scuola Finta', INGLESE, {})]
                             + [f"{q} {a}" for q, a in C.faq_realta('Scuola Finta', INGLESE, {})]))

print("3. una domanda senza dati non si stampa, e nessuna risposta dice no")
domande = [q for q, _ in C.faq_corsi(TUTTI, DOVE)]
ok("sotto i 3 anni c'e' quando c'e' un corso da 2 anni",
   any('sotto i 3 anni' in q for q in domande))
senza_piccoli = [c for c in TUTTI if c['codice'] != 'T2']
ok("e sparisce senza quel corso",
   not any('sotto i 3 anni' in q for q, _ in C.faq_corsi(senza_piccoli, DOVE)))
ok("la prova c'e' quando un corso ha la riga Prova",
   any('provare' in q for q in domande))
ok("e sparisce se nessuno ce l'ha",
   not any('provare' in q for q, _ in C.faq_corsi(senza_piccoli, DOVE)))
ok("sulla realta' senza prova niente domanda sulla prova",
   not any('prova' in q for q, _ in C.faq_realta('ASD Finta', ATLETICA, {})))
risposte = [a for _, a in C.faq_corsi(TUTTI, DOVE)] + [
    a for org, cc in (('Scuola Finta', INGLESE), ('ASD Finta', ATLETICA))
    for _, a in C.faq_realta(org, cc, {})]
ok("nessuna risposta comincia con 'No'", not any(re.match(r'no\b', a, re.I) for a in risposte))
ok("zero corsi: niente domande", C.faq_corsi([], DOVE) == [])
ok("zero corsi: l'hero non elenca attivita'", 'sport' not in C.testo_hero([], ''))

print("4. 'inglese' solo se e' vero per tutti i corsi di lingue")
ok("due corsi d'inglese -> 'inglese'", C._attivita(INGLESE) == 'inglese')
misto = INGLESE + [corso(codice='T6', nome='Francese per bambini', org='Scuola Finta',
                         cat='Lingue › Lingue', citta='Alba', prov='CN')]
ok("con un corso di francese -> 'lingue'", C._attivita(misto) == 'lingue')
ok("una disciplina sola vince sulla famiglia -> 'atletica leggera'",
   C._attivita(ATLETICA) == 'atletica leggera')
tre = INGLESE + ATLETICA + TEATRO
ok("tre famiglie -> niente attivita' (non un elenco nel title)", C._attivita(tre) == '')

print("5. il title delle realta'")
html = C.pagina_realta('Scuola Finta', INGLESE, {}, '', '', '')
t = re.search(r'<title>(.*?)</title>', html).group(1)
ok(f"'ad Alba' e l'attivita': {t!r}", t == 'Scuola Finta: corsi di inglese per bambini ad Alba | DAOP')
html_b = C.pagina_realta('ASD Finta', ATLETICA, {}, '', '', '')
t_b = re.search(r'<title>(.*?)</title>', html_b).group(1)
ok(f"'a Moretta': {t_b!r}", t_b == 'ASD Finta: corsi di atletica leggera per bambini a Moretta | DAOP')
intro = C.testo_realta('Scuola Finta', INGLESE, {})
ok(f"il paragrafo dice eta' e sede: {intro!r}",
   'da 2 a 5 anni' in intro and 'Corso Piave 16' in intro and 'ad Alba' in intro)
ok("il paragrafo e' in pagina", 'class="cr-intro"' in html)
ok("l'occhiello ha gli spazi (G.esc li toglie)",
   'Corsi di inglese per bambini ad Alba</p>' in html)
ok("due famiglie: 'teatro e movimento', non 'teatro e sport e movimento'",
   C._attivita(TEATRO + ATLETICA) == 'teatro e movimento')
col_nome = [dict(c, org='Scuola Finta Alba') for c in INGLESE]
d0 = C.faq_realta('Scuola Finta Alba', col_nome, {})[0][0]
ok(f"il comune gia' nel nome non si ripete nella domanda: {d0!r}",
   d0 == 'Che corsi propone Scuola Finta Alba?')
capo = [corso(codice='T7', nome='Musica', org='Studio', cat='Musica › Musica',
              citta='Cuneo', prov='CN', eta='3-6 anni', sede='Via Tanaro 18')]
testi_capo = C.testo_realta('Studio', capo, {}) + ' '.join(
    a for _, a in C.faq_realta('Studio', capo, {}))
ok("col capoluogo niente 'a Cuneo, in provincia di Cuneo'",
   'Cuneo, in provincia di Cuneo' not in testi_capo)
fasce = dict(C.faq_realta('ASD Finta', ATLETICA + [dict(ATLETICA[0], codice='T8', eta='6-10 anni')], {}))
ok("le fasce si scrivono una volta, come le legge il filtro",
   fasce['Da che età si possono frequentare i corsi di ASD Finta?'].count('6-10 anni') == 1)

print("6. le FAQ sono testo, non dati strutturati")
hub = C.render(TUTTI, '', '', '', {})
ok("corsi.html ha le domande in pagina", 'class="co-faq"' in hub and 'class="co-faq-q"' in hub)
ok("e nessun FAQPage", 'FAQPage' not in hub and 'FAQPage' not in html)

print()
print("OK: i testi dei corsi dicono solo quello che i dati sanno" if esito
      else "ROSSO: vedi le righe NO qui sopra")
sys.exit(0 if esito else 1)
