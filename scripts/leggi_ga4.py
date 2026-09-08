#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""La meta' GA4 della lettura settimanale. Search Console dice chi ci trova,
questa dice cosa fanno quelli che sono arrivati.

    python3 scripts/leggi_ga4.py gsc/2026-09-09

Si usa da sola, ma il posto normale e' `scripts/leggi_settimana.py`, che fa
girare tutte e due le meta' sulla stessa cartella.

LA REGOLA DEI 2,5, E PERCHE' QUI VALE DAVVERO
---------------------------------------------
Nel CLAUDE.md sta scritta per le pagine: «su una pagina che non e' l'agenda, un
rapporto visualizzazioni/utenti sopra 2,5 e' navigazione interna, non pubblico».
Applicarla agli EVENTI sarebbe sbagliato se gli eventi fossero automatici -
`scroll_depth` scatta quattro volte a pagina, quindi un lettore vero farebbe
subito 4 eventi a testa e la soglia direbbe «sei tu» di tutti.

Misurato l'08/09/2026, e non e' quello che dice il CLAUDE.md: **`event_city` non
sta su `page_view` ne' su `scroll_depth`.** Sta solo sui clic (`click_*`,
`aggiungi_calendario`, `apri_corso`, `apri_ginetto`). Sono azioni deliberate, e
una persona vera ne fa una o due. Sopra 2,5 e' qualcuno che sta provando il
sito - all'08/09 la riga in cima ai comuni era «Vezza d'Alba, 41 eventi, 4
utenti», dieci a testa.

Quindi la soglia si applica, ma **la riga non si cancella: si marca**. Cancellare
vorrebbe dire che il giorno che un comune diventa davvero attivo sparisce dal
report proprio quando comincia a contare. Marcata, la vedi e sai perche'.

E il totale «vendibile» esclude le righe marcate, perche' quello e' il numero che
finisce davanti a un cliente.
"""

import csv
import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
STORICO = RADICE / 'data' / 'ga4-storico.json'

INTERNO = 2.5          # eventi per utente: sopra, e' navigazione interna
# Sulla TABELLA DEGLI EVENTI la soglia e' piu' alta, e non e' incoerenza. Li' si
# raggruppa per tipo di azione, non per posto: un lettore vero apre due o tre
# locandine nella stessa visita, e a 2,5 `click_locandina` (2,9) verrebbe
# marcato come nostro, che e' falso. Su un comune o su una realta' invece 2,5
# azioni deliberate DALLO STESSO utente sullo STESSO posto sono gia' tante.
# Dieci sono inequivocabili in tutti e due i casi.
INTERNO_EVENTI = 4.0
MIN_EVENTI_AB = 30     # sotto, un confronto fra due bracci non si commenta
CHIUSURA_CANALE = '2026-09-04'   # il giorno che Ginetto ha preso quel posto

# Gli eventi che sono NOSTRI (li manda daop-track.js) e non automatici di GA4.
NOSTRI = ('click_come_arrivare', 'click_telefono', 'click_email',
          'click_locandina', 'click_sito_organizzatore', 'click_social',
          'aggiungi_calendario', 'apri_ginetto', 'apri_corso',
          'iscrizione_canale', 'vicino_a_me', 'scroll_depth', 'scarica_guida')


def _leggi(cartella, nome):
    f = Path(cartella) / f'{nome}.csv'
    if not f.exists():
        return None
    with f.open(encoding='utf-8-sig') as fp:
        righe = list(csv.reader(fp))
    return righe[1:] if righe else []


def _i(v):
    try:
        return int(float(str(v).replace('%', '').replace(',', '.')))
    except (TypeError, ValueError):
        return 0


def titolo(t):
    print('\n' + t)
    print('-' * len(t))


def _tabella_per_utente(righe, etichetta, quante=12):
    """Stampa righe (nome, eventi, utenti) marcando la navigazione interna."""
    dati = [(r[0], _i(r[-2]), _i(r[-1])) for r in righe if r and r[0]]
    dati = [d for d in dati if d[0] not in ('(non impostato)', '(not set)')]
    dati.sort(key=lambda x: -x[1])
    if not dati:
        print('  nessun dato')
        return 0, 0
    vend_e = vend_u = int_e = 0
    print(f"  {etichetta:<26} {'eventi':>7} {'utenti':>7} {'per ut.':>8}")
    for n, e, u in dati[:quante]:
        rap = e / u if u else 0
        marca = '  <- navigazione interna' if u and rap > INTERNO else ''
        print(f"  {n[:26]:<26} {e:>7} {u:>7} {rap:>8.1f}{marca}")
    for _n, e, u in dati:
        if u and e / u > INTERNO:
            int_e += e
        else:
            vend_e += e
            vend_u += u
    print(f"\n  {len(dati)} righe. Al netto della navigazione interna:"
          f" {vend_e} eventi da {vend_u} utenti"
          f"   (scartati {int_e} eventi)")
    return vend_e, vend_u


def leggi(cartella, salva=True):
    cartella = Path(cartella)
    giorni = _leggi(cartella, 'ga4-Giorni')
    if giorni is None:
        raise SystemExit(
            f"[ga4] in {cartella} non ci sono i fogli GA4.\n"
            "      Si scaricano dal downloader: python scarica_ga4.py")
    filtri = dict((r[0], r[1]) for r in (_leggi(cartella, 'ga4-Filtri') or []) if len(r) > 1)

    utenti = sum(_i(r[1]) for r in giorni)
    sessioni = sum(_i(r[2]) for r in giorni)
    viste = sum(_i(r[3]) for r in giorni)

    print('=' * 78)
    print(f"  GA4 - {cartella}")
    print(f"  {filtri.get('Inizio', '?')} -> {filtri.get('Fine', '?')}"
          f"   ({len(giorni)} giorni)"
          f"   allineata a Search Console: {filtri.get('Allineata a Search Console', '?')}")
    print('=' * 78)

    ora = {'fine': filtri.get('Fine'), 'inizio': filtri.get('Inizio'),
           'utenti': utenti, 'sessioni': sessioni, 'viste': viste}
    prec = _precedente(ora['fine'])
    p = prec or {}

    def d(ora_v, chiave, pt=False):
        v = p.get(chiave)
        if v is None:
            return ''
        if pt:
            return '  (%+.2f)' % (ora_v - v)
        return '  (nuovo)' if not v else '  (%+.0f%%)' % (100.0 * (ora_v - v) / v)

    titolo('CRUSCOTTO GA4')
    pps = viste / sessioni if sessioni else 0
    print(f"  utenti                    {utenti:>8}{d(utenti, 'utenti')}")
    print(f"  sessioni                  {sessioni:>8}{d(sessioni, 'sessioni')}")
    print(f"  visualizzazioni           {viste:>8}{d(viste, 'viste')}")
    print(f"  pagine per sessione       {pps:>8.2f}{d(pps, 'pagine_sessione', pt=True)}"
          f"   sopra ~3,9 sarebbe un page_view doppio")
    ora['pagine_sessione'] = round(pps, 2)

    # ---- copertura contro Search Console, SOLO su giorni che esistono in due
    grafico = _leggi(cartella, 'Grafico')
    if grafico:
        gsc = {r[0].strip(): _i(r[1]) for r in grafico if r and r[0].strip()}
        ga = {r[0].strip(): _i(r[1]) for r in giorni if r and r[0].strip()}
        comuni = sorted(set(gsc) & set(ga))
        if comuni:
            tc = sum(gsc[k] for k in comuni)
            tu = sum(ga[k] for k in comuni)
            cop = 100.0 * tu / tc if tc else 0
            print(f"  copertura vs Search Console {cop:>6.1f}%"
                  f"{d(cop, 'copertura', pt=True)}"
                  f"   ({tu} utenti su {tc} clic, {len(comuni)} giorni)")
            print("     e' il numero che rende onesto un report a un cliente:"
                  " quello che riportiamo\n     e' una sottostima, e si dice"
                  " \"almeno\".")
            ora['copertura'] = round(cop, 1)
    else:
        print("  copertura vs Search Console: Grafico.csv non c'e' in questa"
              " cartella")

    # ------------------------------------------------------------------ eventi
    eventi = _leggi(cartella, 'ga4-Eventi') or []
    mappa = {r[0]: (_i(r[1]), _i(r[2])) for r in eventi if r}
    titolo('I NOSTRI EVENTI  (quelli che manda daop-track.js)')
    print(f"  {'evento':<26} {'conteggio':>10} {'utenti':>8} {'per ut.':>8}")
    for n in NOSTRI:
        if n not in mappa:
            continue
        e, u = mappa[n]
        rap = e / u if u else 0
        nota = '  <- navigazione interna' if u and rap > INTERNO_EVENTI else ''
        print(f"  {n:<26} {e:>10} {u:>8} {rap:>8.1f}{nota}")
        ora[f'ev_{n}'] = e
    aut = mappa.get('scroll', (0, 0))[0]
    if aut:
        print(f"\n  ATTENZIONE: l'evento automatico `scroll` fa {aut} eventi e"
              " duplica il nostro\n  `scroll_depth`. Si spegne da GA4 ->"
              " Amministratore -> Flussi di dati -> il flusso\n  web ->"
              " Misurazione avanzata -> togliere \"Scorrimenti\".")

    # ------------------------------------------- lo slot che era del canale
    per_giorno = _leggi(cartella, 'ga4-EventiGiorno')
    if per_giorno:
        pre = post = 0
        canale = 0
        for r in per_giorno:
            if len(r) < 3:
                continue
            data, nome, n = r[0].strip(), r[1].strip(), _i(r[2])
            if nome == 'iscrizione_canale':
                canale += n
            if nome != 'apri_ginetto':
                continue
            if data < CHIUSURA_CANALE:
                pre += n
            else:
                post += n
        titolo(f"LO SLOT CHE ERA DEL CANALE  (chiuso il {CHIUSURA_CANALE})")
        print(f"  apri_ginetto prima:  {pre:>5}")
        print(f"  apri_ginetto dopo:   {post:>5}")
        print(f"  iscrizione_canale:   {canale:>5}  (deve andare a zero)")
        if min(pre, post) < MIN_EVENTI_AB:
            print(f"\n  Troppo pochi per dire qualcosa: sotto i {MIN_EVENTI_AB}"
                  " eventi per braccio l'intervallo\n  copre lo zero, e un"
                  " \"+44%\" letto qui e' rumore. Il valore di questa riga"
                  " oggi\n  non e' il confronto, e' che il PRIMA sta scritto:"
                  " fra un mese esistera'.")
        ora['ginetto_pre'], ora['ginetto_post'] = pre, post

    # ------------------------------------------------------------------ comuni
    com = _leggi(cartella, 'ga4-Comuni')
    if com:
        titolo('COMUNI  (event_city: sta sui CLIC, non sulle visite)')
        print("  Non risponde a \"quanti leggono cose a Ovada\" - quello"
              " nessuno lo misura, perche'\n  event_city non sta su page_view."
              " Risponde a \"quante AZIONI deliberate\", che\n  per vendere e'"
              " un numero migliore e piu' difficile da contestare.\n")
        _tabella_per_utente(com, 'comune')
    prov = _leggi(cartella, 'ga4-Province')
    if prov:
        print()
        _tabella_per_utente(prov, 'provincia', quante=6)

    # ------------------------------------------------------------------ realta
    rea = _leggi(cartella, 'ga4-Realta')
    if rea:
        titolo('REALTA  (quello che si restituisce a chi paga)')
        agg = {}
        for r in rea:
            if len(r) < 4:
                continue
            nome = r[0].strip()
            if nome in ('(non impostato)', '(not set)', ''):
                continue
            a = agg.setdefault(nome, [0, 0])
            a[0] += _i(r[2])
            a[1] = max(a[1], _i(r[3]))   # utenti: non si sommano fra eventi
        righe = [[n, v[0], v[1]] for n, v in agg.items()]
        if righe:
            _tabella_per_utente(righe, 'realta', quante=10)
            print("\n  Gli utenti NON si sommano fra eventi diversi (la stessa"
                  " persona che chiama e\n  apre il sito e' una): qui si tiene"
                  " il massimo, che e' un minimo garantito.")
        else:
            print("  nessuna realta' con eventi: la dimensione risponde dal"
                  " 21/08/2026.")

    if salva:
        _salva(ora)
        print(f"\n[ga4] lettura del {ora['fine']} segnata in {STORICO.name}")
    else:
        print("\n[ga4] --no-salva: storico non toccato")
    return ora


def _tutte():
    if not STORICO.exists():
        return []
    return json.loads(STORICO.read_text(encoding='utf-8')).get('letture', [])


def _precedente(fine):
    c = [l for l in _tutte() if l.get('fine') != fine]
    return sorted(c, key=lambda l: l.get('fine') or '')[-1] if c else None


def _salva(ora):
    letture = [l for l in _tutte() if l.get('fine') != ora['fine']]
    letture.append(ora)
    letture.sort(key=lambda l: l.get('fine') or '')
    STORICO.parent.mkdir(parents=True, exist_ok=True)
    STORICO.write_text(
        json.dumps({'letture': letture}, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')


def main(argv):
    salva = '--no-salva' not in argv
    resto = [a for a in argv if not a.startswith('--')]
    if not resto:
        raise SystemExit("uso: python3 scripts/leggi_ga4.py gsc/AAAA-MM-GG")
    leggi(resto[0], salva=salva)


if __name__ == '__main__':
    main(sys.argv[1:])
