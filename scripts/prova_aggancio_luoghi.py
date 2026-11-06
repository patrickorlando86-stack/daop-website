#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla l'aggancio fra i luoghi scritti nell'agenda e le righe del catalogo
di luoghi.html quando i due nomi NON sono identici (aggancia_per_nome).

PERCHE' ESISTE (06/11/2026): la Biblioteca civica del Ricetto di Boves aveva
undici eventi in programma e la sua riga non ne mostrava nessuno, perche'
nell'agenda si chiama «Biblioteca Civica del Ricetto». L'aggancio pretendeva il
nome identico.

Si difendono tutti e due i versi: le grafie vere di uno stesso posto si
agganciano, e un posto diverso NON si aggancia - un evento in piazza finito
sulla riga di un bar costa piu' di un evento che manca.

Uso:  python scripts/prova_aggancio_luoghi.py   (esce 1 al primo che salta)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_luoghi as L  # noqa: E402

errori = 0


def cat(nome, comune='Boves'):
    return {'nome': nome, 'comune': comune, 'codice': nome[:4]}


def prova(cosa, agenda, candidati, atteso):
    global errori
    preso = L.aggancia_per_nome({'nome': agenda, 'comune': candidati[0]['comune']
                                 if candidati else 'Boves'}, candidati)
    nome = preso['nome'] if preso else None
    ok = nome == atteso
    errori += not ok
    print(f"  {'ok  ' if ok else 'NO  '} {cosa}: {agenda!r} -> {nome!r}")


boves = [cat('Biblioteca civica del Ricetto di Boves'), cat('Museo della Castagna')]
print('stesso posto, nomi diversi')
for scritto in ('Biblioteca Civica del Ricetto', 'Biblioteca del Ricetto', 'Biblioteca di Boves'):
    prova('Boves', scritto, boves, 'Biblioteca civica del Ricetto di Boves')
prova('il catalogo e\' il nome corto', 'Museo della Castagna - Cascina Marquet', boves,
      'Museo della Castagna')
prova('maiuscole e virgolette', 'Biblioteca Civica Lidia Beccaria Rolfi',
      [cat('Biblioteca Civica "Lidia Beccaria Rolfi" di Saluzzo', 'Saluzzo')],
      'Biblioteca Civica "Lidia Beccaria Rolfi" di Saluzzo')

print('posti diversi')
prova('la prima parola e\' il tipo di posto', 'Piazza Italia',
      [cat('Bar Piazza Italia')], None)
prova('una parola in piu\' dal lato corto', 'Biblioteca Ragazzi',
      [cat('Biblioteca civica del Ricetto di Boves')], None)
prova('due candidati: non si sceglie', 'Biblioteca',
      [cat('Biblioteca civica'), cat('Biblioteca dei ragazzi')], None)
prova('il solo nome del comune non e\' un posto', 'Boves', boves, None)

print('sponsorizzato fuori lista (prossimi_di)')
camp = cat('Campeggio del Ricetto')
righe = [camp, cat('Biblioteca civica del Ricetto di Boves')]
ev = lambda h, d: {'href': h, 'd': d}
agenda = {
    L._key('Campeggio Ricetto', 'Boves'): {'nome': 'Campeggio Ricetto', 'comune': 'Boves',
                                           'prossimi': [ev('/eventi/b.html', '2026-12-02'),
                                                        ev('/eventi/a.html', '2026-12-01')]},
    L._key('Campeggio del Ricetto', 'Boves'): {'nome': 'Campeggio del Ricetto', 'comune': 'Boves',
                                               'prossimi': [ev('/eventi/a.html', '2026-12-01')]},
    L._key('Biblioteca del Ricetto', 'Boves'): {'nome': 'Biblioteca del Ricetto', 'comune': 'Boves',
                                                'prossimi': [ev('/eventi/c.html', '2026-12-03')]},
}
presi = [p['href'] for p in L.prossimi_di(camp, righe, agenda)]
ok = presi == ['/eventi/a.html', '/eventi/b.html']
errori += not ok
print(f"  {'ok  ' if ok else 'NO  '} chiave esatta + grafia diversa, senza doppioni "
      f"ne' eventi della biblioteca: {presi}")

print(f"\n{'tutto torna' if not errori else f'{errori} controlli saltati'}")
sys.exit(1 if errori else 0)
