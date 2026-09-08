#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legge un export di Search Console e stampa il cruscotto settimanale.

    python3 scripts/leggi_gsc.py                      # l'ultima cartella in gsc/
    python3 scripts/leggi_gsc.py gsc/2026-09-09       # una cartella precisa
    python3 scripts/leggi_gsc.py export.zip           # lo zip appena scaricato
    python3 scripts/leggi_gsc.py --no-salva           # non tocca lo storico

PERCHE' ESISTE
--------------
Non per comodita': per costo e per correttezza.

I sette CSV grezzi dentro il contesto di un modello sono ~50.000 token, di cui
30.000 il solo `Query.csv`; l'uscita di questo script ne fa ~2.000. Ma la
ragione piu' forte e' la seconda: le stesse aggregazioni scritte a mano ogni
settimana sbagliano in modi nuovi ogni settimana. Nel CLAUDE.md ci sono due
errori nati esattamente cosi' - il «70% di copertura» che era il 38% (numeratore
e denominatore di due giorni diversi) e il «picco l'8 agosto» dichiarato due
volte su una finestra non ancora consolidata. Un conto scritto una volta e
ripetuto puo' essere sbagliato, ma almeno e' sbagliato sempre allo stesso modo,
e allora si vede.

Da cui la regola operativa: **i CSV grezzi non si leggono, si legge questa
uscita.**

COSA NON FA, ED E' DELIBERATO
-----------------------------
- **Non scrive niente nel sito.** Non e' un generatore, non gira nel workflow
  notturno, e nessun generatore legge quello che produce. L'unico file che
  tocca e' `data/gsc-storico.json`, che e' un registro di letture: se sparisse,
  si perderebbero i confronti e nient'altro.
- **Non decide.** Dice quali soglie si sono rotte; se aprire una provincia o
  fare un 301 lo decide una persona.
- **Non tiene un elenco di query di capoluogo.** La prima versione ce l'aveva
  ed e' stata tolta: un elenco scritto a mano invecchia alla prima festa nuova,
  ed e' l'inciampo gia' pagato sei volte in questo repo. Il gonfiaggio si
  riconosce per come e' fatto - tante impressioni, quasi nessun clic - non per
  il nome che ha.
- **Non asserisce conteggi come soglie.** Le soglie sono rapporti o confronti
  con la lettura precedente, tranne le due che sono documentate nel CLAUDE.md
  come numeri veri (il pavimento a 150 clic/giorno e il minimo di righe per
  fidarsi di una media).

LE TRE TRAPPOLE DELL'EXPORT, CHE QUI SONO CHIUSE IN CODICE
----------------------------------------------------------
1. **Il nome del file non dice la finestra.** Si legge solo in `Filtri.csv`, e
   il giorno di chiusura solo nell'ultima riga di `Grafico.csv`. Due export con
   finestre diverse non si confrontano: qui il confronto si spegne da solo e lo
   dice, invece di produrre percentuali senza senso.
2. **Gli ultimi due giorni valgono ~10% in piu' di quello che dicono.** Search
   Console consolida all'indietro. Ogni giorno citato nell'uscita porta il
   marchio `~` se sta in quella zona.
3. **I fogli non sommano uguale.** `Grafico`, `Paesi` e `Dispositivi` danno il
   totale del sito; `Pagine` e `Query` danno meno, perche' l'anonimizzazione
   lavora per dimensione. Il totale del sito e' quello di `Grafico`, e le
   percentuali non si mescolano fra fogli: qui ogni cifra dice da che foglio
   viene.
"""

import csv
import io
import json
import re
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
STORICO = RADICE / 'data' / 'gsc-storico.json'
REGISTRO = RADICE / 'data' / 'pagine-evento.json'
DOMINIO = 'https://www.daop.it'

# --- soglie -----------------------------------------------------------------
# Solo due sono numeri veri, e sono documentate nel CLAUDE.md. Le altre sono
# confronti con la lettura precedente, che non invecchiano.
PAVIMENTO_ALLARME = 150      # clic/giorno feriali: sotto, il sistema non si regge
MIN_GIORNI_MEDIA = 3         # sotto, una media feriale non si stampa
GONF_IMPR = 800              # una pagina "gonfia" ha almeno tante impressioni
GONF_CTR = 2.5               # ...e sta sotto questo CTR
DELTA_CTR_SCHEDE = 1.5       # punti: oltre, la salute vera si e' mossa
DELTA_QUOTA_SCHEDE = 5.0     # punti
DELTA_BRAND = 50.0           # percento
BAMBINI_SVEGLIA = 200        # impressioni: sopra, quella domanda ci ha trovati

TEMI = {
    'brand':    ['daop', 'ginetto', 'dove andiamo oggi'],
    'autunno':  ['halloween', 'castagn', 'zucca', 'presep', 'natal', 'vendemm',
                 'fungh', 'tartuf', 'carnevale', 'mercatin'],
    'vicino':   ['vicino a me'],
}

# «per bambini» si riconosce dalla PREPOSIZIONE, non dalla parola.
#
# La prima versione cercava le radici secche (`bambin`, `figli`, `ragazz`,
# `kids`) e diceva **876 impressioni** invece di ~40, cioe' venti volte troppo:
# `figli` prende «festa delle figlie bubbio» (383 impressioni, una patronale),
# `kids` prende «casalnoceto kids», `ragazz` prende «estate ragazzi». Sono nomi
# propri di feste, non gente che cerca dove portare i figli - e la misura
# sbagliata diceva che vinciamo una domanda che non tocchiamo, che e' il verso
# peggiore in cui si puo' sbagliare (fa smettere di lavorarci).
#
# La correzione non e' un elenco di eccezioni - quello invecchia alla prima
# festa nuova, ed e' l'inciampo gia' pagato sei volte in questo repo. E' che
# **l'intenzione sta nella preposizione**: chi cerca dice «per bambini», «con i
# bambini», «cosa fare con»; un nome di festa dice «Festa delle Figlie»,
# «Palio in Famiglia». Su «in» non si aggancia apposta, se no torna dentro il
# Palio in Famiglia.
#
# Si perde qualche intenzione vera scritta senza preposizione («bambini
# alessandria»). E' il verso giusto in cui sbagliare: una misura che sottostima
# lascia lavorare, una che sovrastima fa smettere.
BAMBINI_RE = re.compile(
    r'\b(?:per|con|coi|ai|adatt\w*\s+ai|a\s+misura\s+di)\s+'
    r'(?:i|le|la|il|un|una|dei|delle)?\s*'
    r'(?:bambin|bimb|ragazz|famigli|figli)\w*'
    r'|\bcosa\s+fare\s+con\b',
    re.I)


# --- lettura dei file -------------------------------------------------------

def _num(s):
    """Un numero dall'export, tollerante su separatori e simboli."""
    s = (s or '').strip().replace('%', '').replace(' ', '')
    if not s:
        return 0.0
    # "1.234" e' milleduecentotrentaquattro, "6,43" e' sei virgola quarantatre.
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    elif s.count('.') == 1 and len(s.split('.')[1]) == 3 and s.split('.')[0]:
        s = s.replace('.', '')          # migliaia, non decimali
    try:
        return float(s)
    except ValueError:
        return 0.0


def _int(s):
    return int(round(_num(s)))


def _righe(testo):
    return list(csv.reader(io.StringIO(testo)))


def _da_xlsx(percorso):
    """I fogli di un export .xlsx, come righe di stringhe.

    Search Console esporta in tre modi (zip di CSV, xlsx, Fogli Google) e
    l'unica differenza che conta e' che **nell'xlsx il CTR e' una frazione**
    (0,1064) invece di una stringa col percento. Qui non se ne accorge nessuno
    perche' il CTR non si legge mai dal file: si ricalcola sempre da clic e
    impressioni. E' voluto - un CTR letto e uno calcolato divergono al primo
    arrotondamento, e allora non si sa piu' quale credere.
    """
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            import openpyxl
            wb = openpyxl.load_workbook(percorso, read_only=True, data_only=True)
    except ImportError:
        raise SystemExit(
            "[gsc] per leggere un .xlsx serve openpyxl (pip install openpyxl),\n"
            "      oppure esporta in CSV: Esporta -> CSV.")
    fuori = {}
    for nome in wb.sheetnames:
        righe = []
        for r in wb[nome].iter_rows(values_only=True):
            if r is None:
                continue
            righe.append(['' if c is None else
                          (c.date().isoformat() if hasattr(c, 'date') and
                           not isinstance(c, str) else str(c))
                          for c in r])
        fuori[nome] = righe
    wb.close()
    return fuori


def carica(dove):
    """Torna {nome_foglio_normalizzato: [righe]} da cartella, zip o xlsx."""
    dove = Path(dove)
    grezzi = {}
    pronti = {}
    if dove.is_file() and dove.suffix.lower() in ('.xlsx', '.xlsm'):
        pronti = _da_xlsx(dove)
    elif dove.is_file() and dove.suffix.lower() == '.zip':
        with zipfile.ZipFile(dove) as z:
            for n in z.namelist():
                if n.lower().endswith('.csv'):
                    grezzi[Path(n).stem] = z.read(n).decode('utf-8-sig')
    elif dove.is_dir():
        for f in sorted(dove.glob('*.csv')):
            grezzi[f.stem] = f.read_text(encoding='utf-8-sig')
        for f in sorted(dove.glob('*.xlsx')):
            pronti.update(_da_xlsx(f))
        for f in sorted(dove.glob('*.zip')):
            with zipfile.ZipFile(f) as z:
                for n in z.namelist():
                    if n.lower().endswith('.csv'):
                        grezzi[Path(n).stem] = z.read(n).decode('utf-8-sig')
    else:
        raise SystemExit(f"[gsc] non e' una cartella, uno zip o un xlsx: {dove}")

    fogli = {}
    for nome, righe in pronti.items():
        k = nome.lower()
        for chiave in ('grafico', 'pagine', 'query', 'paesi', 'dispositivi',
                       'filtri', 'aspetto'):
            if k.startswith(chiave):
                fogli[chiave] = righe
                break
    for nome, testo in grezzi.items():
        k = nome.lower()
        for chiave in ('grafico', 'pagine', 'query', 'paesi', 'dispositivi',
                       'filtri', 'aspetto'):
            if k.startswith(chiave):
                fogli[chiave] = _righe(testo)
                break
    mancanti = [k for k in ('grafico', 'pagine', 'query') if k not in fogli]
    if mancanti:
        raise SystemExit(
            f"[gsc] mancano i fogli {', '.join(mancanti)} in {dove}.\n"
            "      Search Console -> Rendimento -> Esporta -> CSV, e si scompatta\n"
            "      lo zip intero: i fogli servono insieme.")
    return fogli


def finestra(fogli):
    """La finestra dichiarata e il giorno di chiusura. Le due trappole n.1."""
    dichiarata = ''
    for r in fogli.get('filtri', [])[1:]:
        if len(r) >= 2 and r[0].strip().lower().startswith('data'):
            dichiarata = r[1].strip()
    giorni = [r for r in fogli['grafico'][1:] if r and r[0].strip()]
    primo, ultimo = giorni[0][0].strip(), giorni[-1][0].strip()
    return dichiarata, primo, ultimo, len(giorni)


# --- classificazione delle pagine ------------------------------------------

def famiglia(url):
    p = url.replace(DOMINIO, '')
    if p == '/eventi.html':
        return 'eventi.html'
    if p in ('/', '/index.html'):
        return 'home'
    if p.startswith('/sagre-provincia-'):
        return 'sagre-provincia-*'
    if p.startswith('/eventi-provincia-'):
        return 'eventi-provincia-*'
    if p.startswith('/eventi/comune/'):
        return 'pagine comune'
    if p.startswith('/eventi/weekend-provincia'):
        return 'weekend-provincia-*'
    if p.startswith('/eventi/oggi-provincia'):
        return 'oggi-provincia-*'
    if p in ('/eventi/oggi.html', '/eventi/weekend.html'):
        return 'oggi/weekend (indici)'
    if p == '/luoghi.html':
        return 'luoghi.html'
    if p == '/corsi.html' or p.startswith('/corsi/'):
        return 'corsi'
    if p.startswith('/centri'):
        return 'centri'
    if p.startswith('/rubriche'):
        return 'rubriche'
    if re.match(r'^/(ferragosto|halloween|natale|pasqua|carnevale|befana'
                r'|capodanno)\.html$', p):
        return 'stagionali'
    if p.startswith('/eventi/'):
        return 'schede evento'
    return 'altre pagine'


def slug_scheda(url):
    """Lo slug di una scheda evento, o None se non lo e'."""
    p = url.replace(DOMINIO, '')
    if not (p.startswith('/eventi/') and p.endswith('.html')):
        return None
    s = p[len('/eventi/'):-len('.html')]
    if '/' in s or s in ('oggi', 'weekend'):
        return None
    if s.startswith(('oggi-provincia', 'weekend-provincia')):
        return None
    return s


def comuni_dal_registro():
    """slug -> (comune, provincia). Se il registro manca, si rinuncia e basta."""
    if not REGISTRO.exists():
        return {}
    dati = json.loads(REGISTRO.read_text(encoding='utf-8'))
    rec = dati.get('pagine', dati) if isinstance(dati, dict) else dati
    if isinstance(rec, dict):
        rec = list(rec.values())
    fuori = {}
    for r in rec:
        s = r.get('slug')
        if s:
            fuori[s] = (r.get('citta') or r.get('comune') or '?',
                        r.get('prov') or '?')
    return fuori


# --- stampa -----------------------------------------------------------------

def _pc(a, b):
    return 100.0 * a / b if b else 0.0


def _delta(ora, prima, punti=False, cifre=1):
    if prima is None:
        return ''
    if punti:
        return '  (%+.*f pt)' % (cifre, ora - prima)
    if not prima:
        return '  (nuovo)'
    return '  (%+.0f%%)' % (100.0 * (ora - prima) / prima)


def titolo(t):
    print('\n' + t)
    print('-' * len(t))


def leggi(cartella, salva=True):
    fogli = carica(cartella)
    dich, primo, ultimo, ngiorni = finestra(fogli)

    giorni = [(r[0].strip(), _int(r[1]), _int(r[2]))
              for r in fogli['grafico'][1:] if r and r[0].strip()]
    tot_c = sum(g[1] for g in giorni)
    tot_i = sum(g[2] for g in giorni)

    pagine = [(r[0], _int(r[1]), _int(r[2]), _num(r[4]))
              for r in fogli['pagine'][1:] if r and r[0].strip()]
    query = [(r[0].lower(), _int(r[1]), _int(r[2]), _num(r[4]))
             for r in fogli['query'][1:] if r and r[0].strip()]

    prec = storico_precedente(ultimo, dich)

    print('=' * 78)
    print(f"  SEARCH CONSOLE - export di {cartella}")
    print(f"  finestra dichiarata: {dich or '(non dichiarata)'}"
          f"   |   {primo} -> {ultimo}   ({ngiorni} giorni)")
    if prec:
        print(f"  confronto con la lettura del {prec['ultimo']}"
              f" ({prec.get('finestra', '?')})")
    else:
        print("  nessuna lettura precedente confrontabile: questa fa da base")
    print('=' * 78)
    print(f"\n  Gli ultimi due giorni ({giorni[-2][0]}, {giorni[-1][0]}) valgono"
          f" ~10% in piu' di quello\n  che dicono: Search Console consolida"
          f" all'indietro. Sono marcati con ~.")

    ora = {'ultimo': ultimo, 'finestra': dich, 'giorni': ngiorni,
           'clic': tot_c, 'impressioni': tot_i}

    # ---------------------------------------------------------------- famiglie
    fam = {}
    for u, c, i, _p in pagine:
        f = fam.setdefault(famiglia(u), [0, 0, 0])
        f[0] += c
        f[1] += i
        f[2] += 1
    pag_c = sum(v[0] for v in fam.values())
    pag_i = sum(v[1] for v in fam.values())

    schede = fam.get('schede evento', [0, 0, 0])
    ctr_schede = _pc(schede[0], schede[1])
    quota_schede = _pc(schede[0], pag_c)
    ora['ctr_schede'] = round(ctr_schede, 2)
    ora['quota_schede'] = round(quota_schede, 2)

    # ------------------------------------------------------- pavimento feriale
    # I lunedi'-giovedi' dell'ULTIMA SETTIMANA INTERA, non gli ultimi N feriali
    # disponibili. La prima versione faceva la media degli ultimi sei lun-gio e
    # dava 479 invece di 434, perche' pescava a cavallo di due settimane: con un
    # ritmo settimanale cosi' marcato (il venerdi' e il sabato valgono il doppio
    # di un martedi') una finestra che scavalca la domenica non misura un
    # pavimento, misura da dove l'hai fatta partire. E' la stessa disciplina
    # gia' scritta nel CLAUDE.md - «una media va presa su settimane intere, mai
    # su una fascia di giorni scelta».
    #
    # Il venerdi' sta fuori: e' gia' weekend nel comportamento, non nel
    # calendario. Sabato e domenica dell'ultima settimana sono anche i due
    # giorni non consolidati, quindi il pavimento non li tocca comunque.
    per_sett = {}
    for g, c, _i in giorni:
        try:
            d = date.fromisoformat(g)
        except ValueError:
            continue
        per_sett.setdefault(d - timedelta(days=d.weekday()), []).append((d, c))
    intere = [(lun, gg) for lun, gg in sorted(per_sett.items()) if len(gg) == 7]
    if intere:
        sett_pav, gg = intere[-1]
        feriali = [c for d, c in gg if d.weekday() <= 3]
    else:
        sett_pav, feriali = None, []
    pavimento = sum(feriali) / len(feriali) if feriali else 0
    ora['pavimento'] = round(pavimento, 1)
    ora['pavimento_sett'] = sett_pav.isoformat() if sett_pav else None

    # ------------------------------------------------------------- gonfiaggio
    gonfie = [r for r in pagine
              if r[2] >= GONF_IMPR and _pc(r[1], r[2]) < GONF_CTR]
    g_c = sum(r[1] for r in gonfie)
    g_i = sum(r[2] for r in gonfie)
    ctr_pulito = _pc(pag_c - g_c, pag_i - g_i)
    ora['ctr_aggregato'] = round(_pc(tot_c, tot_i), 2)
    ora['ctr_pulito'] = round(ctr_pulito, 2)
    ora['gonfie_quota_impr'] = round(_pc(g_i, pag_i), 1)

    # ------------------------------------------------------------------- temi
    def tema(regola):
        if hasattr(regola, 'search'):
            s = [q for q in query if regola.search(q[0])]
        else:
            s = [q for q in query if any(k in q[0] for k in regola)]
        return s, sum(r[1] for r in s), sum(r[2] for r in s)

    _b, brand_c, brand_i = tema(TEMI['brand'])
    _d, daop_c, daop_i = tema(['daop'])
    bam, bam_c, bam_i = tema(BAMBINI_RE)
    ora['brand_clic'] = brand_c
    ora['daop_clic'] = daop_c
    ora['bambini_impr'] = bam_i

    # =============================================================== CRUSCOTTO
    titolo('CRUSCOTTO')
    p = prec or {}
    print(f"  pavimento feriale (lun-gio)   {pavimento:>8.0f} clic/g"
          f"{_delta(pavimento, p.get('pavimento'))}"
          f"   soglia allarme {PAVIMENTO_ALLARME}"
          f"   [sett. {sett_pav or '?'}]")
    print(f"  CTR delle schede  <- SALUTE   {ctr_schede:>8.2f}%"
          f"{_delta(ctr_schede, p.get('ctr_schede'), punti=True, cifre=2)}")
    print(f"  quota clic delle schede       {quota_schede:>8.1f}%"
          f"{_delta(quota_schede, p.get('quota_schede'), punti=True)}")
    print(f"  CTR aggregato   <- NON LEGGERE {_pc(tot_c, tot_i):>7.2f}%"
          f"{_delta(_pc(tot_c, tot_i), p.get('ctr_aggregato'), punti=True, cifre=2)}")
    print(f"  CTR togliendo le pagine gonfie {ctr_pulito:>7.2f}%"
          f"{_delta(ctr_pulito, p.get('ctr_pulito'), punti=True, cifre=2)}")
    print(f"  brand ('daop' e affini)       {brand_c:>8} clic"
          f"{_delta(brand_c, p.get('brand_clic'))}   su {brand_i} impressioni"
          f"   -- solo 'daop': {daop_c} su {daop_i}")
    print(f"  query 'per bambini'           {bam_i:>8} impr"
          f"{_delta(bam_i, p.get('bambini_impr'))}   per {bam_c} clic")
    print(f"  totale sito (foglio Grafico)  {tot_c:>8} clic"
          f"{_delta(tot_c, p.get('clic'))}   su {tot_i} impressioni")
    if len(feriali) < MIN_GIORNI_MEDIA:
        print(f"  ! il pavimento e' su {len(feriali)} giorni soli: non citarlo")

    # ================================================================ FAMIGLIE
    titolo('FAMIGLIE  (foglio Pagine: %d clic, %d impressioni)' % (pag_c, pag_i))
    print(f"  {'famiglia':24} {'pag':>4} {'clic':>7} {'quota':>7}"
          f" {'impressioni':>12} {'CTR':>7}")
    for k, v in sorted(fam.items(), key=lambda x: -x[1][0]):
        print(f"  {k:24} {v[2]:>4} {v[0]:>7} {_pc(v[0], pag_c):>6.1f}%"
              f" {v[1]:>12} {_pc(v[0], v[1]):>6.2f}%")

    # ============================================================== GONFIAGGIO
    titolo('IL GONFIAGGIO  (>=%d impressioni e CTR < %.1f%%)' % (GONF_IMPR, GONF_CTR))
    if not gonfie:
        print("  nessuna pagina in questo stato: il CTR aggregato si puo' leggere.")
    else:
        for u, c, i, pos in sorted(gonfie, key=lambda r: -r[2])[:12]:
            print(f"  {i:>7} impr {c:>5} clic {_pc(c, i):>5.2f}%  pos {pos:>5.2f}"
                  f"  {u.replace(DOMINIO, '')}")
        print(f"\n  {len(gonfie)} pagine: {g_i} impressioni"
              f" ({_pc(g_i, pag_i):.1f}% del foglio Pagine), {g_c} clic"
              f" ({_pc(g_c, pag_c):.1f}%), CTR {_pc(g_c, g_i):.2f}%")
        print(f"  CTR del sito togliendole: {ctr_pulito:.2f}%"
              f"  <- e' questo che si confronta con la settimana scorsa")

    # ================================================================== COMUNI
    mappa = comuni_dal_registro()
    if mappa:
        com, prov = {}, {}
        att_c = att_i = 0
        senza = 0
        for u, c, i, _p in pagine:
            s = slug_scheda(u)
            if not s:
                continue
            if s not in mappa:
                senza += c
                continue
            ct, pr = mappa[s]
            a = com.setdefault((ct, pr), [0, 0, 0])
            a[0] += c
            a[1] += i
            a[2] += 1
            b = prov.setdefault(pr, [0, 0, set()])
            b[0] += c
            b[1] += i
            b[2].add(ct)
            att_c += c
            att_i += i
        titolo('COMUNI  (%d clic attribuiti, %d non attribuiti)' % (att_c, senza))
        top = sorted(com.items(), key=lambda x: -x[1][0])
        print(f"  {'comune':24} {'pr':>2} {'sch':>4} {'clic':>6} {'quota':>7}"
              f" {'impr':>8} {'CTR':>7}")
        for (ct, pr), (c, i, n) in top[:10]:
            print(f"  {ct[:24]:24} {pr:>2} {n:>4} {c:>6} {_pc(c, att_c):>6.1f}%"
                  f" {i:>8} {_pc(c, i):>6.2f}%")
        print()
        for pr, (c, i, cs) in sorted(prov.items(), key=lambda x: -x[1][0]):
            print(f"  {pr}  {c:>6} clic  {i:>8} impr  CTR {_pc(c, i):>5.2f}%"
                  f"  da {len(cs)} comuni")
        # il fossato: piu' schede ha un comune, meno converte. Terza lettura
        # indipendente che lo conferma, e va rifatta ogni volta invece di
        # citare quella vecchia.
        g = {}
        for (_ct, _pr), (c, i, n) in com.items():
            k = '1 scheda' if n == 1 else ('2-4 schede' if n <= 4 else '5+ schede')
            a = g.setdefault(k, [0, 0, 0])
            a[0] += c
            a[1] += i
            a[2] += 1
        print("\n  il fossato (CTR per quante schede ha il comune):")
        for k in ('1 scheda', '2-4 schede', '5+ schede'):
            if k in g:
                c, i, n = g[k]
                print(f"    {k:12} {n:>3} comuni  {c:>6} clic  {i:>8} impr"
                      f"  CTR {_pc(c, i):>5.2f}%")
        cum = 0
        for k, (_kk, (c, _i, _n)) in enumerate(top, 1):
            cum += c
            if cum >= att_c * 0.5:
                print(f"\n  meta' dei clic delle schede: primi {k} comuni su {len(top)}")
                break
    else:
        titolo('COMUNI')
        print("  data/pagine-evento.json non trovato: attribuzione saltata.")

    # =================================================================== QUERY
    titolo('QUERY  (foglio Query: %d clic, %d impressioni - e\' un campione)'
           % (sum(r[1] for r in query), sum(r[2] for r in query)))
    tq_i = sum(r[2] for r in query)
    print("  Google anonimizza le query rare, quindi questo foglio e' una parte")
    print("  del sito. Una famiglia di query con volume vero emerge lo stesso:")
    print("  se qui non c'e', per noi non c'e'.\n")
    for nome, regola in (('bambini/famiglie', BAMBINI_RE),
                         ('brand', TEMI['brand']),
                         ('vicino a me', TEMI['vicino'])):
        s, c, i = tema(regola)
        print(f"  {nome:18} {len(s):>3} query {i:>7} impr ({_pc(i, tq_i):>5.2f}%)"
              f" {c:>5} clic  CTR {_pc(c, i):>5.2f}%")
    # Le query 'per bambini' si stampano per intero: sono l'unica famiglia del
    # cruscotto abbastanza piccola da starci, e l'unica in cui ogni riga nuova
    # e' una notizia. Finche' ce ne stanno dieci, e' anche il modo di accorgersi
    # se il filtro ha ripreso a prendere nomi di feste.
    if bam:
        print("\n  le query 'per bambini', per intero:")
        for t, c, i, pos in sorted(bam, key=lambda r: -r[2])[:10]:
            print(f"    {i:>6} impr {c:>4} clic  pos {pos:>5.2f}  {t}")
    print("\n  segnali d'autunno:")
    for k in TEMI['autunno']:
        s, c, i = tema([k])
        stato = f"{len(s):>2} query {i:>6} impr {c:>4} clic" if s else "zero"
        print(f"    {k:12} {stato}")
    print("\n  le 8 query che perdono piu' pubblico (impressioni alte, CTR basso):")
    persi = [q for q in query if q[2] >= 300 and _pc(q[1], q[2]) < 2.0]
    for t, c, i, pos in sorted(persi, key=lambda r: -r[2])[:8]:
        print(f"    {i:>6} impr {c:>4} clic {_pc(c, i):>5.2f}%  pos {pos:>5.2f}  {t}")
    if not persi:
        print("    nessuna")

    # ================================================================= GIORNI
    titolo('GIORNI  (ultimi 14)')
    gg = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']
    for n, (g, c, i) in enumerate(giorni[-14:]):
        marchio = '~' if n >= len(giorni[-14:]) - 2 else ' '
        try:
            et = gg[date.fromisoformat(g).weekday()]
        except ValueError:
            et = '   '
        print(f"  {marchio}{g} {et}  clic {c:>6}  impr {i:>7}  CTR {_pc(c, i):>5.2f}%")
    sett = {}
    for g, c, i in giorni:
        try:
            d = date.fromisoformat(g)
        except ValueError:
            continue
        lun = d - timedelta(days=d.weekday())
        a = sett.setdefault(lun, [0, 0, 0])
        a[0] += c
        a[1] += i
        a[2] += 1
    print("\n  settimane intere (lun-dom); le parziali sono marcate")
    for lun, (c, i, n) in sorted(sett.items())[-5:]:
        par = '' if n == 7 else f'  [{n} giorni, parziale]'
        print(f"  {lun}  clic {c:>6}  {c / n:>7.1f}/g  impr {i:>8}"
              f"  CTR {_pc(c, i):>5.2f}%{par}")

    # ================================================================= SOGLIE
    titolo('SERVE UNA SEZIONE IN CLAUDE.MD?')
    rotte = soglie(ora, prec)
    if not rotte:
        print("  No. Nessuna soglia rotta: si segna la lettura nello storico e")
        print("  basta. Dodici sezioni quasi identiche e il file non lo rilegge")
        print("  piu' nessuno - quel file documenta decisioni, non misure.")
    else:
        for r in rotte:
            print(f"  * {r}")

    if salva:
        salva_lettura(ora)
        print(f"\n[gsc] lettura del {ultimo} segnata in {STORICO.name}")
    else:
        print("\n[gsc] --no-salva: storico non toccato")
    return ora


# --- storico ----------------------------------------------------------------

def _tutte():
    if not STORICO.exists():
        return []
    return json.loads(STORICO.read_text(encoding='utf-8')).get('letture', [])


def storico_precedente(ultimo, dich):
    """L'ultima lettura CONFRONTABILE: stessa finestra, giorno diverso.

    E' la trappola n.1 chiusa in codice. Un export a 3 mesi e uno a 28 giorni
    non si confrontano, e il modo in cui ci si sbaglia non e' distrazione: e'
    che il nome del file non dice la finestra, quindi due export sembrano
    uguali finche' non si apre Filtri.csv.
    """
    cand = [l for l in _tutte()
            if l.get('ultimo') != ultimo and l.get('finestra') == dich]
    if not cand:
        diverse = [l for l in _tutte() if l.get('ultimo') != ultimo]
        if diverse:
            print("\n[gsc] ATTENZIONE: ci sono letture precedenti ma con"
                  " un'altra finestra\n      (%s). Il confronto e' spento:"
                  " esporta sempre la stessa finestra."
                  % ', '.join(sorted({l.get('finestra', '?') for l in diverse})))
        return None
    return sorted(cand, key=lambda l: l['ultimo'])[-1]


def salva_lettura(ora):
    letture = [l for l in _tutte() if l.get('ultimo') != ora['ultimo']]
    letture.append(ora)
    letture.sort(key=lambda l: l['ultimo'])
    STORICO.parent.mkdir(parents=True, exist_ok=True)
    STORICO.write_text(
        json.dumps({'letture': letture}, ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')


def soglie(ora, prec):
    """Cosa e' successo di abbastanza grosso da meritare di essere scritto."""
    fuori = []
    if ora['pavimento'] and ora['pavimento'] < PAVIMENTO_ALLARME:
        fuori.append(
            f"ALLARME: pavimento feriale a {ora['pavimento']:.0f} clic/g, sotto"
            f" i {PAVIMENTO_ALLARME} della soglia. Il sistema non si regge da"
            " solo: e' la sola riga di questo cruscotto che chiede una decisione"
            " subito.")
    if ora['bambini_impr'] >= BAMBINI_SVEGLIA:
        fuori.append(
            f"le query 'per bambini' fanno {ora['bambini_impr']} impressioni"
            f" (soglia {BAMBINI_SVEGLIA}): quella domanda ci ha trovati, ed e'"
            " la prima volta. Va scritto cosa l'ha mossa.")
    if not prec:
        fuori.append("prima lettura con questa finestra: non c'e' niente da"
                     " confrontare, ma vale la pena segnare i valori di"
                     " partenza.")
        return fuori
    d = ora['ctr_schede'] - prec.get('ctr_schede', ora['ctr_schede'])
    if abs(d) >= DELTA_CTR_SCHEDE:
        fuori.append(f"il CTR delle schede si e' mosso di {d:+.2f} punti"
                     f" ({prec['ctr_schede']}% -> {ora['ctr_schede']}%): e' la"
                     " salute vera, non la composizione.")
    d = ora['quota_schede'] - prec.get('quota_schede', ora['quota_schede'])
    if abs(d) >= DELTA_QUOTA_SCHEDE:
        fuori.append(f"la quota di clic delle schede si e' mossa di {d:+.1f}"
                     " punti: il traffico si sta spostando fra famiglie.")
    pb = prec.get('brand_clic')
    if pb and abs(100.0 * (ora['brand_clic'] - pb) / pb) >= DELTA_BRAND:
        fuori.append(f"il brand passa da {pb} a {ora['brand_clic']} clic: e' il"
                     " KPI del cavallo di Troia, e si guarda la curva.")
    return fuori


def ultima_cartella():
    base = RADICE / 'gsc'
    if not base.is_dir():
        return None
    c = sorted([d for d in base.iterdir() if d.is_dir()])
    return c[-1] if c else None


def main(argv):
    salva = '--no-salva' not in argv
    resto = [a for a in argv if not a.startswith('--')]
    dove = Path(resto[0]) if resto else ultima_cartella()
    if not dove:
        raise SystemExit(
            "[gsc] nessuna cartella indicata e gsc/ e' vuota.\n"
            "      Search Console -> Rendimento -> Ultimi 28 giorni ->\n"
            "      Esporta -> CSV, e si scompatta lo zip in gsc/AAAA-MM-GG/.")
    leggi(dove, salva=salva)


if __name__ == '__main__':
    main(sys.argv[1:])
