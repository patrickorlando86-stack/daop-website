#!/usr/bin/env python3
"""
Genera /luoghi.html: l'elenco filtrabile dei posti dove le famiglie ci vanno.

PERCHE' UNA PAGINA SOLA E NON UNA SCHEDA PER LUOGO
--------------------------------------------------
La domanda di partenza era "800 luoghi, faccio 800 schede?". No, e non per
pigrizia: il sitemap oggi ha 270 URL, e 800 pagine su template identico con il
nome del posto scambiato sarebbero i tre quarti del sito fatti delle pagine piu'
deboli che abbiamo. E' la definizione che Google da' dello scaled content abuse,
e la penalizzazione non resta sulle pagine nuove: si porta dietro il dominio,
cioe' eventi.html, che e' la pagina che regge il traffico.

Quindi: **una pagina, tante righe, i filtri**. Esattamente come l'agenda, che di
schede ne tiene 294 in un file solo. Una scheda propria (/luoghi/<slug>.html) la
si scrive quando c'e' qualcosa da dire che sta solo li' - foto nostre, orari
verificati, dov'e' l'ombra ad agosto, dove si cambia il pannolino - e quel
momento coincide quasi sempre con il luogo che diventa premium, perche' e' il
gestore a darci il materiale. Il campo c'e' gia' (`scheda`), la generazione
delle schede singole no: si aggiunge quando le schede da scrivere esistono, non
prima.

DA DOVE ARRIVANO I LUOGHI
-------------------------
Due sorgenti che si sommano, non che si escludono:

1. **Il catalogo** - il tab "Luoghi" dello stesso foglio Google degli eventi,
   con ripiego su `data/luoghi.json` quando la rete non c'e' (stessa regola di
   genera_eventi.py: senza rete si va avanti con l'istantanea, non ci si ferma).
   E' li' che vivranno le 800 righe.

2. **L'agenda** - i luoghi che DAOP conosce gia' perche' ci sono passati degli
   eventi: `data/eventi.json` per il futuro, `data/storico-comuni.json` per gli
   anni indietro. Sono ~350 posti veri, con il comune e la provincia giusti.

I due insiemi si fondono per chiave (nome normalizzato + comune). Il catalogo
vince sui campi che dichiara; l'agenda aggiunge quello che il catalogo non puo'
sapere - **quante volte ci si e' andati e quando e' la prossima**. Che poi e' il
dato per cui questa pagina non e' un elenco come un altro: nessun'altra directory
puo' scrivere "qui DAOP ha seguito 7 eventi per famiglie, il prossimo e' sabato".

IL PREMIUM: AGGIUNGE, NON RIORDINA
----------------------------------
La regola editoriale e' la stessa gia' presa su "Adatto Famiglie": un elenco non
si spacca in due quando la separazione smentisce il criterio con cui e' fatto. Se
la riga di chi paga stesse piu' in alto, il resto diventerebbe la serie B di una
selezione che abbiamo fatto noi. Quindi la scheda premium **aggiunge** (foto,
orari, contatti, offerta) e sta nel suo posto in ordine alfabetico, dentro il suo
comune, come tutte.

L'unico spazio in cui la posizione si compra e' il blocco "In evidenza" in cima,
che e' separato, dichiarato e non toglie la riga dall'elenco. Ed e' anche un
obbligo, non una scelta di stile: art. 22 comma 4-bis del Codice del consumo -
in una lista ricercabile i parametri di ordinamento vanno dichiarati, e omettere
che una posizione e' stata pagata sta nella lista nera delle pratiche ingannevoli
"in ogni caso". Da qui il blocco #come-ordiniamo, che non e' decorativo.

Uso:
    python3 scripts/genera_luoghi.py        # funziona offline
"""
import os
import re
import io
import csv
import json
import datetime
import collections
import urllib.request

import genera_eventi as G

ROOT = G.ROOT
OUT_PATH = os.path.join(ROOT, "luoghi.html")
JSON_PATH = os.path.join(ROOT, "data", "luoghi.json")
EVENTI_JSON = G.JSON_PATH
STORICO_JSON = os.path.join(ROOT, "data", "storico-comuni.json")
SITEMAP_PATH = G.SITEMAP_PATH

PAGE_URL = f"{G.SITE_URL}/luoghi.html"
DEFAULT_CSV = (f"https://docs.google.com/spreadsheets/d/{G.SHEET_ID}"
               "/gviz/tq?tqx=out:csv&sheet=Luoghi")

# Quanti eventi passati bastano perche' un posto dell'agenda entri in elenco.
# A 1 entrerebbero anche i "Centro Citta'" e le vie in cui e' passata una
# sfilata una volta sola: sono indirizzi, non luoghi dove si va. A 2 resta
# quello che ha ospitato qualcosa piu' di una volta, che e' il minimo perche'
# la riga dica qualcosa a chi legge. Il catalogo non passa da qui: se una riga
# sta nel foglio, e' perche' qualcuno l'ha scelta.
MIN_EVENTI_AGENDA = 2

# Nomi che non sono luoghi: contenitori generici che il foglio eventi usa
# quando il posto preciso non si sa. Tenerli farebbe un elenco in cui "Centro
# Citta'" compare in quaranta comuni diversi.
NON_LUOGHI = re.compile(
    r'^(centro citt|centro storico|vie del (paese|centro)|vie e piazze|'
    r'varie (sedi|location)|tutto il paese|piu\' sedi|da definire|'
    r'sede da definire|vari luoghi|in paese|stand gastronomic|'
    r'sede della manifestazione)', re.I)

# Un "luogo" che si chiama come il suo comune non e' un luogo: e' la riga del
# foglio in cui il posto preciso non si sapeva. In elenco faceva "Novi Ligure ·
# Novi Ligure (AL)", cioe' una voce che non dice niente sotto un'intestazione
# che l'ha appena detto. Stesso discorso per le frazioni scritte come
# "Carrega Ligure - fraz. Magioncalda": il comune sta gia' nel titolo del gruppo.
FRAZIONE = re.compile(r'\bfraz(\.|ione\b)', re.I)


# ── Le categorie di luogo ────────────────────────────────────────────────────
#
# Non sono le categorie degli eventi: un evento e' "Sagra & Festa", un luogo e'
# un parco o un castello. Si dichiarano nel foglio (colonna Categoria) e, quando
# la colonna e' vuota, si deducono dal nome - che per i posti funziona bene,
# perche' un posto si chiama quasi sempre come quello che e' ("Parco Peppino
# Impastato", "Castello dei Paleologi", "Biblioteca civica").
#
# `riparo` e' la risposta a "e se piove?", che e' il filtro piu' usato di
# qualunque elenco di posti con i bambini: chiuso / aperto / misto. E' un valore
# di ripiego per categoria, che la colonna Riparo del foglio sovrascrive.
#
# Le icone stanno nello sprite in fondo a questo file, non in assets/icons.svg.html:
# quello e' lo sprite dell'agenda e non contiene ne' un castello ne' una goccia,
# e allargarlo vorrebbe dire ricommittare eventi.html per una pagina sola.
CATEGORIE = [
    ('acqua', 'Acqua', 'lgi-acqua', 'misto',
     ('piscina', 'lido', 'bagni ', 'spiaggia', 'lago', 'idroscalo', 'acquapark',
      'parco acquatico', 'torrente', 'fiume ')),
    ('castello', 'Castello & Rocca', 'lgi-castello', 'misto',
     ('castello', 'rocca', 'fortezza', 'forte ', 'torre ', 'ricetto', 'bastion',
      'cittadella', 'castell')),
    ('museo', 'Museo', 'lgi-museo', 'chiuso',
     ('museo', 'pinacoteca', 'gipsoteca', 'planetario', 'ecomuseo', 'antiquarium')),
    ('natura', 'Natura & Fattoria', 'lgi-natura', 'aperto',
     ('bosco', 'sentiero', 'riserva', 'oasi', 'fattoria', 'cascina', 'agrituris',
      'azienda agricola', 'orto botanico', 'parco naturale', 'area naturale',
      'laghetto', 'maneggio', 'ippic', 'centro equestre', 'centro faunistic',
      'tenuta ', 'cantina', 'vigne', 'apiario', 'centro visita')),
    ('parco', 'Parco & Giardino', 'lgi-parco', 'aperto',
     ('parco', 'giardin', 'area verde', 'area giochi', 'area attrezzata',
      'villa comunale', 'pineta', 'belvedere')),
    ('sport', 'Sport & Gioco', 'lgi-sport', 'misto',
     ('palestra', 'campo sportivo', 'centro sportivo', 'polisportiv', 'stadio',
      'bocciofil', 'tennis', 'pista', 'palazzetto', 'centro fondo', 'skate',
      'campo da', 'impianti sportivi', 'sferisterio', 'area sportiva',
      'pala', 'sci ', 'seggiovia', 'palaghiaccio')),
    ('cultura', 'Cultura & Teatro', 'lgi-cultura', 'chiuso',
     ('teatro', 'biblioteca', 'cinema', 'auditorium', 'palazzo', 'villa ',
      'sala ', 'ludoteca', 'centro culturale', 'casa d', 'accademia',
      'conservatorio', 'archivio', 'municipio', 'comune di ', 'confraternita')),
    ('fede', 'Chiesa & Oratorio', 'lgi-fede', 'chiuso',
     ('chiesa', 'santuario', 'oratorio', 'parrocchi', 'abbazia', 'chiostro',
      'convento', 'conventual', 'pieve', 'basilica', 'duomo', 'cappella',
      'monastero', 'san francesco', 'battistero')),
    ('piazza', 'Piazza & Vie', 'lgi-piazza', 'aperto',
     ('piazza', 'piazzale', 'via ', 'corso ', 'largo ', 'viale ', 'borgo ',
      'lungo', 'ponte ', 'area pedonale')),
    ('ritrovo', 'Ritrovo & Pro Loco', 'lgi-ritrovo', 'misto',
     ('pro loco', 'proloco', 'circolo', 'area feste', 'capannone', 'salone',
      'polifunzional', 'centro incontro', 'societa\' operaia', 'ex ', 'sede ',
      'padiglione', 'foro boario', 'ostello', 'rifugio', 'balera',
      'ballo a palchetto', 'centro per le famiglie', 's.o.m.s', 'soms',
      's.m.s', 'spazio giovani', 'centro giovani', 'centro anziani')),
]
# L'etichetta della tendina non e' quella della riga, e non e' una svista.
# In riga si parla di UN posto ("Parco & Giardino"), nel filtro di una famiglia
# di posti ("Parchi"): al plurale la riga suonerebbe sbagliata e al singolare il
# filtro sembra una scelta sola. E c'e' una ragione tecnica che vale quanto
# quella di stile - Chrome dimensiona una <select> sull'opzione PIU' LUNGA, non
# su quella scelta: con "Ritrovo & Pro Loco" dentro, la tendina da sola chiedeva
# 150px e mandava a capo la barra appiccicosa del telefono.
CAT_FILTRO = {
    'acqua': 'Acqua', 'castello': 'Castelli', 'museo': 'Musei', 'natura': 'Natura',
    'parco': 'Parchi', 'sport': 'Sport', 'cultura': 'Cultura', 'fede': 'Chiese',
    'piazza': 'Piazze', 'ritrovo': 'Ritrovi',
}
CAT_INFO = {c[0]: {'label': c[1], 'icona': c[2], 'riparo': c[3],
                   'filtro': CAT_FILTRO.get(c[0], c[1])} for c in CATEGORIE}
CAT_INFO['altro'] = {'label': 'Altro luogo', 'icona': 'lgi-pin', 'riparo': 'misto',
                     'filtro': 'Altro'}
ORDINE_CAT = [c[0] for c in CATEGORIE] + ['altro']

RIPARO_LABEL = {'chiuso': 'Al chiuso', 'aperto': "All'aperto", 'misto': 'Chiuso e aperto'}


# Un nome che COMINCIA con "Corso", "Via", "Piazza" e' un indirizzo, e va deciso
# li' e subito: "Corso Bagni" (una strada di Acqui Terme) finiva in "Acqua"
# perche' piu' avanti c'e' la parola bagni, e "Via del Castello" sarebbe
# diventata un castello. La parola che conta e' la prima.
INIZI_PIAZZA = re.compile(
    r"^\s*(piazz(a|ale|etta)|via|viale|corso|c\.so|largo|vicolo|borgo|"
    r"lungo\w+|strada|salita|contrada|p\.zza|v\.le)\b", re.I)


def categoria_di(nome, dichiarata=''):
    """Lo slug di categoria del luogo. La colonna del foglio vince sempre."""
    d = (dichiarata or '').strip().lower()
    if d:
        for slug, label, _ico, _rip, chiavi in CATEGORIE:
            if d == slug or d in label.lower() or any(k.strip() in d for k in chiavi):
                return slug
    if INIZI_PIAZZA.match(nome or ''):
        return 'piazza'
    n = ' ' + (nome or '').lower() + ' '
    for slug, _label, _ico, _rip, chiavi in CATEGORIE:
        if any(k in n for k in chiavi):
            return slug
    return 'altro'


def _key(nome, comune):
    """Chiave di fusione fra catalogo e agenda.

    Sta tutta nel normalizzare: nel foglio eventi lo stesso posto si scrive
    "P.zza Garibaldi", "Piazza Garibaldi" e "piazza garibaldi" nella stessa
    settimana, e senza questo passaggio uscirebbero tre righe."""
    t = (nome or '').lower()
    t = t.replace("p.zza", "piazza").replace("p.za", "piazza").replace("pza ", "piazza ")
    t = t.replace("v.le", "viale").replace("c.so", "corso").replace("s.", "san ")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    # Le sigle puntate si riattaccano: nel foglio lo stesso posto e' "Centro per
    # le Famiglie C.I.S.A." e "Centro per le Famiglie CISA", e senza questo
    # passaggio sono due righe con lo stesso nome nello stesso comune.
    t = re.sub(r"\b(?:[a-z] )+[a-z]\b", lambda m: m.group(0).replace(" ", ""), t)
    return f"{t}|{G.slugify(comune or '')}"


def _alfabetico(s):
    """La chiave con cui si ordina, cioe' l'ordine alfabetico come lo legge una
    persona: senza accenti e senza punteggiatura, non con i trattini di slugify.

    Non e' un dettaglio da niente: slugify trasforma "C.I.S.A." in "c-i-s-a" e
    il trattino viene prima di ogni lettera, quindi l'elenco usciva in un ordine
    che a chi legge sembra sbagliato. E l'ordine alfabetico qui e' una promessa
    scritta in #come-ordiniamo, non una preferenza."""
    t = (s or '').lower()
    for a, b in (('à', 'a'), ('á', 'a'), ('è', 'e'), ('é', 'e'), ('ì', 'i'),
                 ('í', 'i'), ('ò', 'o'), ('ó', 'o'), ('ù', 'u'), ('ú', 'u')):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9 ]", "", t)


def si(v):
    return str(v or '').strip().lower() in ('si', 'sì', 'x', 'true', '1', 'vero')


# ── Sorgente 1: il catalogo (foglio Google, ripiego su data/luoghi.json) ─────

COLONNE = {
    'nome': ('nome', 'luogo', 'denominazione'),
    'comune': ('comune', 'citta', 'città', 'paese'),
    'prov': ('provincia', 'prov', 'sigla'),
    'cat': ('categoria', 'tipo', 'tipologia'),
    'indirizzo': ('indirizzo', 'indirizzo completo', 'via'),
    'riparo': ('riparo', 'coperto', 'al chiuso', 'chiuso/aperto'),
    'prezzo': ('prezzo', 'costo', 'ingresso'),
    'eta': ('eta', 'età', 'fascia', "fascia d'eta", "fascia d'età"),
    'descr': ('descrizione', 'descr', 'note'),
    'orari': ('orari', 'orario', 'apertura'),
    'sito': ('sito', 'sito web', 'link', 'url'),
    'tel': ('telefono', 'tel', 'contatto'),
    'foto': ('foto', 'immagine', 'locandina'),
    'lat': ('lat', 'latitudine'),
    'lon': ('lon', 'lng', 'longitudine'),
    'premium': ('premium', 'scheda premium', 'sponsor'),
    'premium_da': ('a cura di', 'gestore', 'premium a cura di'),
    'offerta': ('offerta', 'offerta famiglie', 'promozione'),
    'evidenza': ('in evidenza', 'evidenza', 'vetrina'),
    'pubblica': ('pubblica', 'pubblicare', 'online'),
}


def _norm_head(s):
    return re.sub(r"\s+", " ", (s or '').strip().lower())


def leggi_catalogo():
    """Le righe del tab "Luoghi", o l'istantanea locale, o niente.

    "O niente" e' un esito normale, non un errore: finche' il tab non esiste la
    pagina si regge sull'agenda, che di luoghi ne conosce gia' ~350."""
    base = os.environ.get("LUOGHI_CSV_URL") or DEFAULT_CSV
    sep = '&' if '?' in base else '?'
    url = f"{base}{sep}_cb={int(datetime.datetime.now().timestamp())}"
    righe = None
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "daop-luoghi-bot", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            testo = r.read().decode("utf-8", "replace")
        lettore = list(csv.reader(io.StringIO(testo)))
        if lettore and any(_norm_head(c) in COLONNE['nome'] for c in lettore[0]):
            head = [_norm_head(c) for c in lettore[0]]
            righe = [dict(zip(head, r)) for r in lettore[1:] if any(c.strip() for c in r)]
            print(f"[genera_luoghi] {len(righe)} righe lette dal tab Luoghi")
        else:
            # Il tab non c'e': gviz risponde comunque, con il primo foglio o con
            # una pagina d'errore. Meglio accorgersene qui che pubblicare un
            # elenco di eventi travestito da elenco di luoghi.
            print("[genera_luoghi] il tab Luoghi non risponde con le colonne attese")
    except Exception as e:
        print(f"[genera_luoghi] tab Luoghi non raggiungibile ({e})")

    if righe is None and os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as fh:
            snap = json.load(fh)
        print(f"[genera_luoghi] uso l'istantanea {os.path.basename(JSON_PATH)}: {len(snap)} luoghi")
        return snap
    if righe is None:
        print("[genera_luoghi] nessun catalogo: la pagina si regge sull'agenda")
        return []

    fuori = []
    for r in righe:
        d = {}
        for campo, nomi in COLONNE.items():
            for n in nomi:
                if r.get(n, '').strip():
                    d[campo] = r[n].strip()
                    break
            d.setdefault(campo, '')
        if not d['nome']:
            continue
        # Colonna "Pubblica" vuota = pubblica. Serve solo a togliere una riga
        # senza cancellarla dal foglio, che e' l'uso vero: un posto chiuso per
        # lavori non si cancella, si spegne.
        if d['pubblica'] and not si(d['pubblica']):
            continue
        fuori.append(d)
    return fuori


# ── Sorgente 2: l'agenda (eventi futuri + storico) ───────────────────────────

def leggi_agenda():
    """I luoghi che l'agenda conosce, con il conto degli eventi e i prossimi.

    Restituisce un dict chiave -> dati. `prossimi` contiene solo eventi ancora
    da fare: e' l'unica parte che invecchia, e infatti la pagina si rigenera
    ogni notte insieme all'agenda."""
    oggi = datetime.date.today()
    luoghi = {}

    def tocca(nome, comune, prov, **extra):
        if not nome or NON_LUOGHI.match(nome.strip()) or FRAZIONE.search(nome):
            return None
        if G.slugify(nome) == G.slugify(comune or ''):
            return None
        k = _key(nome, comune)
        d = luoghi.setdefault(k, {
            'nome': nome.strip(), 'comune': (comune or '').strip(),
            'prov': (prov or '').strip().upper(),
            'indirizzo': '', 'lat': '', 'lon': '',
            'n_eventi': 0, 'ultimo': '', 'prossimi': [],
        })
        for campo, val in extra.items():
            if val and not d.get(campo):
                d[campo] = val
        return d

    # Lo storico: 387 eventi su 118 comuni, con il comune che fa da contenitore.
    if os.path.exists(STORICO_JSON):
        with open(STORICO_JSON, encoding="utf-8") as fh:
            storico = json.load(fh)
        for _slug, com in storico.items():
            for _k, ev in com.get('eventi', {}).items():
                d = tocca(ev.get('luogo'), com.get('nome'), com.get('prov'))
                if d is None:
                    continue
                d['n_eventi'] += 1
                if (ev.get('ultima') or '') > d['ultimo']:
                    d['ultimo'] = ev.get('ultima') or ''

    # L'agenda viva: qui ci sono anche indirizzo e coordinate, che lo storico
    # non tiene. E i prossimi appuntamenti, che sono la ragione per cui questa
    # pagina vale piu' di un elenco di nomi.
    if os.path.exists(EVENTI_JSON):
        with open(EVENTI_JSON, encoding="utf-8") as fh:
            eventi = json.load(fh)
        visti = set()
        for e in eventi:
            d = tocca(e.get('luogo'), e.get('citta'), e.get('prov'),
                      indirizzo=e.get('indirizzo', ''),
                      lat=e.get('lat', ''), lon=e.get('lon', ''))
            if d is None:
                continue
            k = _key(e.get('luogo'), e.get('citta'))
            # Lo storico ha gia' contato gli eventi di quest'anno: ricontarli
            # qui raddoppierebbe il numero scritto in pagina. Si conta una
            # volta sola per (luogo, evento).
            firma = (k, e.get('anchor') or e.get('nome'))
            if firma not in visti:
                visti.add(firma)
            if e.get('d_end', '') >= oggi.isoformat():
                d['prossimi'].append({
                    'nome': e.get('nome', ''),
                    'd': e.get('d_start', ''),
                    'href': f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html",
                })
            if (e.get('d_end') or '') > d['ultimo']:
                d['ultimo'] = e.get('d_end') or ''

    for d in luoghi.values():
        d['prossimi'].sort(key=lambda p: p['d'])
        # Il conteggio non deve mai essere piu' piccolo di quello che la riga
        # elenca sotto, se no si legge "1 evento" con tre link in fila.
        d['n_eventi'] = max(d['n_eventi'], len(d['prossimi']))
    return luoghi


# ── Fusione ──────────────────────────────────────────────────────────────────

def unisci(catalogo, agenda):
    """Catalogo + agenda in un elenco solo, ordinato per provincia, comune, nome.

    Il catalogo vince sui campi che dichiara: e' scritto da una persona, l'altro
    e' dedotto. L'agenda porta quello che il catalogo non puo' avere - il conto
    degli eventi e i prossimi appuntamenti - anche sulle righe del catalogo, che
    e' proprio il punto di fondere invece di scegliere."""
    fuori = {}

    for r in catalogo:
        k = _key(r['nome'], r['comune'])
        cat = categoria_di(r['nome'], r.get('cat'))
        riparo = (r.get('riparo') or '').strip().lower()
        if riparo.startswith('chius') or 'copert' in riparo:
            riparo = 'chiuso'
        elif riparo.startswith('apert') or 'scopert' in riparo:
            riparo = 'aperto'
        elif riparo:
            riparo = 'misto'
        fuori[k] = {
            'nome': r['nome'], 'comune': r['comune'], 'prov': (r['prov'] or '').upper(),
            'cat': cat, 'riparo': riparo or CAT_INFO[cat]['riparo'],
            'indirizzo': r.get('indirizzo', ''), 'lat': r.get('lat', ''),
            'lon': r.get('lon', ''), 'prezzo': r.get('prezzo', ''),
            'eta': r.get('eta', ''), 'descr': r.get('descr', ''),
            'orari': r.get('orari', ''), 'sito': r.get('sito', ''),
            'tel': r.get('tel', ''), 'foto': r.get('foto', ''),
            'premium': si(r.get('premium')), 'premium_da': r.get('premium_da', ''),
            'offerta': r.get('offerta', ''), 'evidenza': si(r.get('evidenza')),
            'n_eventi': 0, 'ultimo': '', 'prossimi': [], 'fonte': 'catalogo',
        }

    for k, a in agenda.items():
        if k in fuori:
            d = fuori[k]
            d['n_eventi'] = a['n_eventi']
            d['ultimo'] = a['ultimo']
            d['prossimi'] = a['prossimi']
            for campo in ('indirizzo', 'lat', 'lon'):
                if not d.get(campo):
                    d[campo] = a.get(campo, '')
            continue
        if a['n_eventi'] < MIN_EVENTI_AGENDA and not a['prossimi']:
            continue
        cat = categoria_di(a['nome'])
        fuori[k] = dict(a, cat=cat, riparo=CAT_INFO[cat]['riparo'],
                        prezzo='', eta='', descr='', orari='', sito='', tel='',
                        foto='', premium=False, premium_da='', offerta='',
                        evidenza=False, fonte='agenda')

    elenco = [d for d in fuori.values() if d['nome'] and d['comune']]
    # Solo le province che pubblichiamo: nel foglio eventi capita una riga fuori
    # regione, e in un elenco di posti "dove andare" una Genova sola stona.
    elenco = [d for d in elenco if not d['prov'] or d['prov'] in G.PROVINCE_PUBBLICATE]
    for d in elenco:
        d['slug'] = 'lg-' + G.slugify(f"{d['nome']} {d['comune']}")[:70]
    # Slug duplicati: due "Piazza Garibaldi" nello stesso comune non dovrebbero
    # esistere dopo _key(), ma un'ancora ripetuta rompe i link in silenzio.
    visti = collections.Counter()
    for d in elenco:
        visti[d['slug']] += 1
        if visti[d['slug']] > 1:
            d['slug'] = f"{d['slug']}-{visti[d['slug']]}"
    elenco.sort(key=lambda d: (d['prov'], _alfabetico(d['comune']), _alfabetico(d['nome'])))
    return elenco


# ── Sprite, CSS e JS della pagina ────────────────────────────────────────────

SPRITE = """<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true" focusable="false"><defs>
<g id="lgi-parco"><path d="M12 22v-6"/><path d="M12 16a6 6 0 0 0 6-6c0-3-2-4-2-6a4 4 0 0 0-8 0c0 2-2 3-2 6a6 6 0 0 0 6 6z"/></g>
<g id="lgi-acqua"><path d="M12 2.7 6.7 8a7.5 7.5 0 1 0 10.6 0z"/></g>
<g id="lgi-museo"><path d="M3 21h18"/><path d="M5 21V9"/><path d="M19 21V9"/><path d="M9 21v-6h6v6"/><path d="M12 3 3 8h18z"/></g>
<g id="lgi-castello"><path d="M3 21h18"/><path d="M4 21V8l3 2V6l2.5 2L12 4l2.5 4L17 6v4l3-2v13"/><path d="M10 21v-4a2 2 0 0 1 4 0v4"/></g>
<g id="lgi-cultura"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></g>
<g id="lgi-fede"><path d="M12 2v20"/><path d="M8 7h8"/><path d="M5 22V12l7-5 7 5v10"/></g>
<g id="lgi-natura"><path d="M12 22V9"/><path d="m6 15 6-9 6 9"/><path d="m3 20 9-14 9 14"/></g>
<g id="lgi-sport"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18"/><path d="M3.5 9h17"/><path d="M3.5 15h17"/></g>
<g id="lgi-piazza"><path d="M3 21h18"/><path d="M6 21V7l6-4 6 4v14"/><path d="M10 21v-5h4v5"/></g>
<g id="lgi-ritrovo"><path d="M3 21V10l9-6 9 6v11"/><path d="M3 21h18"/><path d="M9 21v-6h6v6"/><path d="M9 11h6"/></g>
<g id="lgi-pin"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/></g>
<g id="lgi-rain"><path d="M4 14.9A5 5 0 0 1 6 5.2a6 6 0 0 1 11.3 1.9A4 4 0 0 1 18 15"/><path d="m8 19-1 2"/><path d="m13 19-1 2"/><path d="m18 19-1 2"/></g>
<g id="lgi-star"><path d="m12 3 2.6 5.6 6 .8-4.4 4.2 1.1 6-5.3-3-5.3 3 1.1-6L3.4 9.4l6-.8z"/></g>
</defs></svg>"""

# Le tinte delle categorie stanno QUI e non in uno style= sulla riga: 350 righe
# per ~90 byte di custom property sarebbero 31 KB di attributi ripetuti, che e'
# esattamente il difetto tolto dall'agenda con i link del calendario.
COLORI_CAT = {
    'parco': ('#188663', 'rgba(24,134,99,0.13)', '#146c51'),
    'acqua': ('#3d8fc4', 'rgba(61,143,196,0.14)', '#2f7099'),
    'museo': ('#6c63a6', 'rgba(108,99,166,0.14)', '#5c5493'),
    'castello': ('#a9793f', 'rgba(169,121,63,0.15)', '#8a6132'),
    'cultura': ('#c9a227', 'rgba(201,162,39,0.16)', '#846a1a'),
    'fede': ('#8a7f9b', 'rgba(138,127,155,0.16)', '#6f6580'),
    'natura': ('#5c9a4a', 'rgba(92,154,74,0.14)', '#487a3a'),
    'sport': ('#e8954a', 'rgba(232,149,74,0.15)', '#a75b15'),
    'piazza': ('#7e8c99', 'rgba(126,140,153,0.16)', '#606d7a'),
    'ritrovo': ('#c2704f', 'rgba(194,112,79,0.15)', '#96543a'),
    'altro': ('#7e8c99', 'rgba(126,140,153,0.16)', '#606d7a'),
}

LUOGHI_CSS = """
.lg-wrap{max-width:940px;margin:0 auto;padding:0 20px 40px}
@media(max-width:600px){.lg-wrap{padding:0 16px 32px}}
.lg-intro{font-size:1.02rem;line-height:1.7;color:var(--text-mid);margin:0 0 6px}
/* La barra dei filtri e' la .ev-toolbar dell'agenda: stessa classe, stesso
   aspetto, stesso vocabolario dei data-* - cambia solo cosa filtra. */
.lg-count{font-size:0.8rem;font-weight:600;color:var(--text-light);margin:10px 0 0;min-height:1em}
.lg-reset{font-family:'DM Sans',sans-serif;font-size:0.8rem;font-weight:600;color:var(--text-mid);
  background:none;border:0;border-bottom:1px solid rgba(45,74,92,0.25);padding:0 0 1px;cursor:pointer}
.lg-reset:hover{color:var(--orange-ink,#a05714);border-color:currentColor}

/* ── Il gruppo comune ─────────────────────────────────────────────────────── */
.lg-grp{margin:26px 0 0}
.lg-grp-h{display:flex;align-items:baseline;gap:10px;margin:0 0 6px;padding:0 0 6px;
  border-bottom:1px solid rgba(45,74,92,0.10)}
.lg-grp-h h2{font-family:'Playfair Display',serif;font-size:1.24rem;font-weight:800;
  color:var(--navy);margin:0}
.lg-grp-h span{font-size:0.78rem;font-weight:600;color:var(--text-light)}
.lg-grp-h a{font-size:0.78rem;font-weight:600;color:var(--text-mid);margin-left:auto;white-space:nowrap}

/* ── La riga ──────────────────────────────────────────────────────────────
   E' un <details>, non una riga con del JS sopra: senza JavaScript si apre lo
   stesso, la tastiera la governa da sola e Ctrl+F la trova anche chiusa.
   content-visibility come nell'agenda - a 350 righe e' la voce piu' pesante
   della pagina, e il testo resta comunque nel DOM. */
.lg-row{content-visibility:auto;contain-intrinsic-size:auto 74px;
  border-left:3px solid var(--cat-color,#7e8c99);border-bottom:1px solid rgba(45,74,92,0.07);
  background:white;transition:background .18s ease}
.lg-row:hover{background:var(--cat-tint,rgba(45,74,92,0.04))}
.lg-row[open]{background:var(--cat-tint,rgba(45,74,92,0.04))}
.lg-row > summary{display:flex;align-items:center;gap:12px;padding:13px 14px;cursor:pointer;
  list-style:none;min-height:48px}
.lg-row > summary::-webkit-details-marker{display:none}
.lg-row > summary:focus-visible{outline:2px solid var(--orange);outline-offset:-2px}
.lg-ico{flex:0 0 auto;width:34px;height:34px;border-radius:10px;display:flex;
  align-items:center;justify-content:center;background:var(--cat-tint,rgba(45,74,92,0.08));
  color:var(--cat-ink,#606d7a)}
.lg-ico svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.9;
  stroke-linecap:round;stroke-linejoin:round}
.lg-txt{min-width:0;flex:1 1 auto}
.lg-nome{display:block;font-size:0.99rem;font-weight:700;color:var(--navy);line-height:1.3}
.lg-meta{display:block;font-size:0.79rem;color:var(--text-light);margin-top:2px}
/* La categoria si scrive, non solo si colora: un verde e un blu senza etichetta
   sono due colori. Stessa regola delle pagine comune. */
.lg-cat{font-weight:700;color:var(--cat-ink,#606d7a)}
.lg-tag{flex:0 0 auto;font-size:0.68rem;font-weight:700;letter-spacing:0.03em;
  text-transform:uppercase;border-radius:100px;padding:4px 9px;white-space:nowrap}
.lg-tag.is-ev{background:rgba(24,134,99,0.12);color:#146c51}
.lg-tag.is-prem{background:rgba(201,162,39,0.18);color:#846a1a;display:inline-flex;
  align-items:center;gap:4px}
.lg-tag.is-prem svg{width:11px;height:11px;fill:currentColor;stroke:none}
.lg-tag i{font-style:normal}
.lg-tag b{font-weight:700}
.lg-chev{flex:0 0 auto;width:17px;height:17px;fill:none;stroke:var(--text-light);
  stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;transition:transform .18s ease}
.lg-row[open] .lg-chev{transform:rotate(180deg)}
@media(max-width:600px){
  .lg-row > summary{padding:12px 8px;gap:10px}
  .lg-nome{font-size:0.94rem}
  /* Resta il pallino con il numero: dice la stessa cosa in 26px invece di 120,
     e senza di lui le righe sul telefono erano tutte identiche. La riga aperta
     ha spazio e riprende la parola. */
  .lg-tag i{display:none}
  .lg-tag.is-ev{min-width:26px;text-align:center;padding:4px 7px}
  .lg-row[open] .lg-tag i{display:inline}
}

/* ── Il corpo aperto ─────────────────────────────────────────────────────── */
.lg-body{padding:2px 14px 18px 60px;font-size:0.9rem;line-height:1.62;color:var(--text-mid)}
@media(max-width:600px){.lg-body{padding:2px 8px 16px 8px}}
.lg-facts{list-style:none;margin:0 0 12px;padding:0;display:grid;gap:6px}
.lg-facts li{display:flex;gap:8px}
.lg-facts b{font-weight:700;color:var(--text-dark);flex:0 0 auto}
.lg-next{margin:12px 0 0;padding:12px 14px;background:var(--cream);border-radius:12px}
.lg-next p{margin:0 0 7px;font-size:0.8rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.04em;color:var(--text-light)}
.lg-next ul{list-style:none;margin:0;padding:0;display:grid;gap:5px}
.lg-next a{color:var(--navy);font-weight:600}
.lg-act{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0 0}
.lg-act a{display:inline-flex;align-items:center;gap:6px;font-size:0.83rem;font-weight:600;
  color:var(--text-mid);background:white;border:1px solid rgba(45,74,92,0.14);
  border-radius:100px;padding:9px 15px;min-height:40px;transition:var(--transition)}
.lg-act a:hover{border-color:var(--orange);color:var(--orange-ink,#a05714)}
.lg-manca{margin:12px 0 0;font-size:0.83rem;color:var(--text-light)}
.lg-manca a{color:var(--text-mid);text-decoration:underline}

/* ── Premium ──────────────────────────────────────────────────────────────
   Aggiunge, non sposta: la riga resta al suo posto alfabetico nel suo comune.
   Quello che cambia e' cosa c'e' dentro. */
.lg-row.is-prem{border-left-width:4px}
.lg-foto{display:block;width:100%;max-width:360px;height:auto;aspect-ratio:4/3;object-fit:cover;
  border-radius:12px;margin:0 0 12px;background:var(--cream)}
.lg-offerta{margin:12px 0 0;padding:11px 14px;border:1px dashed rgba(201,162,39,0.55);
  border-radius:12px;background:rgba(201,162,39,0.07);font-size:0.87rem}
.lg-offerta b{color:#846a1a}
.lg-cura{margin:10px 0 0;font-size:0.76rem;color:var(--text-light)}

/* ── In evidenza: l'unico posto in cui la posizione si compra, e si dice ──── */
.lg-vetrina{margin:22px 0 0;padding:16px 16px 6px;border:1px solid rgba(201,162,39,0.35);
  border-radius:var(--radius-lg,16px);background:rgba(201,162,39,0.05)}
.lg-vetrina > p{margin:0 0 4px;font-size:0.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.05em;color:#846a1a}
.lg-vetrina > p span{font-weight:600;text-transform:none;letter-spacing:0;color:var(--text-light)}
.lg-vetrina .lg-row{background:transparent}

/* ── Come ordiniamo: obbligo di legge, non decorazione ───────────────────── */
.lg-ordine{margin:30px 0 0;padding:16px 18px;background:var(--cream);border-radius:14px;
  font-size:0.85rem;line-height:1.65;color:var(--text-mid)}
.lg-ordine h2{font-family:'DM Sans',sans-serif;font-size:0.82rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;color:var(--text-light);margin:0 0 8px}
.lg-ordine p{margin:0 0 8px}
.lg-ordine p:last-child{margin:0}

.lg-vuoto{margin:26px 0;padding:26px 20px;text-align:center;background:var(--cream);
  border-radius:14px;color:var(--text-mid)}
.lg-vuoto b{display:block;color:var(--navy);margin-bottom:4px}
"""

LUOGHI_JS = r"""<script>
(function () {
  var bar = document.getElementById('lg-toolbar');
  if (!bar) return;
  var q = document.getElementById('lg-q');
  var conta = document.getElementById('lg-count');
  var vuoto = document.getElementById('lg-vuoto');
  var reset = document.getElementById('lg-reset');
  var sel = [].slice.call(bar.querySelectorAll('.ev-select'));
  var righe = [].slice.call(document.querySelectorAll('.lg-row[data-cat]'));
  var gruppi = [].slice.call(document.querySelectorAll('.lg-grp'));
  if (!righe.length) return;

  // L'indice si costruisce alla PRIMA ricerca, non al caricamento: leggere il
  // testo di 350 righe e' lavoro che quasi nessun visitatore usa. Stessa regola
  // dell'agenda.
  var testo = null;
  function indice() {
    if (!testo) {
      testo = new Map(righe.map(function (r) {
        var s = r.querySelector('summary');
        return [r, (s ? s.textContent : r.textContent).toLowerCase().replace(/\s+/g, ' ')];
      }));
    }
    return testo;
  }

  function applica() {
    var t = q ? q.value.trim().toLowerCase() : '';
    var f = {};
    sel.forEach(function (s) {
      f[s.dataset.campo] = s.value;
      s.classList.toggle('is-on', s.value !== 'all');
    });
    var visti = 0;
    righe.forEach(function (r) {
      var ok = (!f.prov || f.prov === 'all' || r.dataset.prov === f.prov) &&
               (!f.cat || f.cat === 'all' || r.dataset.cat === f.cat) &&
               (!f.riparo || f.riparo === 'all' ||
                 r.dataset.riparo === f.riparo || r.dataset.riparo === 'misto') &&
               (!f.agenda || f.agenda === 'all' || r.dataset.agenda === '1') &&
               (!t || indice().get(r).indexOf(t) > -1);
      r.hidden = !ok;
      if (ok) visti++;
    });
    // Un gruppo svuotato dai filtri si porta via la sua intestazione: se no
    // resta in pagina il nome di un comune con niente sotto. E' il guasto che
    // si vede solo filtrando, quindi va scritto adesso.
    gruppi.forEach(function (g) {
      g.hidden = !g.querySelector('.lg-row[data-cat]:not([hidden])');
    });
    var filtrato = !!t || sel.some(function (s) { return s.value !== 'all'; });
    conta.textContent = filtrato
      ? visti + (visti === 1 ? ' luogo' : ' luoghi') + ' con questi filtri'
      : '';
    if (vuoto) vuoto.hidden = visti !== 0;
  }

  if (q) q.addEventListener('input', applica);
  sel.forEach(function (s) { s.addEventListener('change', applica); });
  if (reset) reset.addEventListener('click', function () {
    if (q) q.value = '';
    sel.forEach(function (s) { s.value = 'all'; });
    applica();
    bar.scrollIntoView({ block: 'start' });
  });
  applica();

  // Link diretto a un luogo (/luoghi.html#lg-...). Un <details> non si apre da
  // solo quando e' il bersaglio dell'ancora, e se un filtro attivo lo tiene
  // nascosto il browser scrollerebbe nel vuoto: si azzera tutto, si apre, si va.
  function vaiAncora() {
    var id = (location.hash || '').slice(1);
    if (!id) return;
    var r = document.getElementById(id);
    if (!r || !r.classList.contains('lg-row')) return;
    if (r.hidden) {
      if (q) q.value = '';
      sel.forEach(function (s) { s.value = 'all'; });
      applica();
    }
    r.open = true;
    r.scrollIntoView({ block: 'center' });
  }
  window.addEventListener('hashchange', vaiAncora);
  vaiAncora();
})();
</script>
"""


# ── Render ───────────────────────────────────────────────────────────────────

def maps_href(l):
    if l.get('lat') and l.get('lon'):
        return f"https://www.google.com/maps/search/?api=1&query={l['lat']},{l['lon']}"
    query = ", ".join(x for x in (l['nome'], l['comune'], l['prov']) if x)
    return "https://www.google.com/maps/search/?api=1&query=" + G.urllib.parse.quote(query)


def data_lunga(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    return f"{d.day} {G.MESI_LUNGHI[d.month - 1]} {d.year}"


def data_breve(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    return f"{d.day} {G.MESI[d.month - 1]}"


CHEV = ('<svg class="lg-chev" viewBox="0 0 24 24" aria-hidden="true">'
        '<polyline points="6 9 12 15 18 9"/></svg>')
STELLA = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#lgi-star"/></svg>'


def _indirizzo_utile(l):
    """L'indirizzo si stampa solo se aggiunge qualcosa al nome.

    Nel foglio eventi la colonna "Indirizzo Completo" e' spesso il nome del
    posto piu' il comune ("Palazzo Chiabrera - Acqui Terme (AL)"), e la riga
    aperta lo ripeteva subito sotto un'intestazione che diceva gia' "Palazzo
    Chiabrera · Acqui Terme (AL)". Si toglie il rumore, non l'informazione:
    quando l'indirizzo ha davvero una via, resta."""
    ind = (l.get('indirizzo') or '').strip()
    if not ind:
        return False
    resto = ind.lower()
    for pezzo in (l['nome'], l['comune'], f"({l['prov']})", l['prov']):
        if pezzo:
            resto = resto.replace(pezzo.lower(), ' ')
    return len(re.sub(r'[^a-z0-9]+', '', resto)) >= 4


def riga(l, oggi):
    """Una riga dell'elenco. Chiusa dice cos'e' e dov'e'; aperta dice tutto il
    resto. Niente immagine nelle righe non premium: 350 miniature diverse in
    elenco sono l'errore di banda gia' fatto una volta con le locandine, e
    un'icona di categoria si legge meglio di una foto da 34px."""
    e = G.esc
    cat = CAT_INFO[l['cat']]
    prossimi = l.get('prossimi') or []
    ha_agenda = '1' if prossimi else '0'

    # L'etichetta si accorcia sul telefono invece di sparire: "ci sono eventi
    # qui" e' il motivo per cui questa pagina esiste, e nasconderla a chi legge
    # da smartphone - cioe' all'88% - lasciava le righe tutte uguali. La parola
    # sta in un <i> che il CSS spegne sotto i 600px, il numero resta.
    tag = ''
    if l.get('premium'):
        tag = f'<span class="lg-tag is-prem">{STELLA}<i>Scheda curata</i></span>'
    elif prossimi:
        # Lo spazio sta DENTRO l'<i>, non fra i due elementi: e' il margine CSS
        # a distanziarli per l'occhio, ma il testo lo leggono anche l'indice
        # della ricerca e chi usa uno screen reader, e li' "2in programma" e'
        # sbagliato. Dentro l'<i> lo spazio sparisce insieme alla parola quando
        # sul telefono resta il solo numero.
        n = len(prossimi)
        tag = f'<span class="lg-tag is-ev"><b>{n}</b><i> in programma</i></span>'

    # ── corpo ──
    fatti = []
    if _indirizzo_utile(l):
        fatti.append(f"<li><b>Dove:</b> <span>{e(G.trunc(l['indirizzo'], 90))}</span></li>")
    fatti.append(f"<li><b>Se piove:</b> <span>{RIPARO_LABEL[l['riparo']]}</span></li>")
    if l.get('orari'):
        fatti.append(f"<li><b>Orari:</b> <span>{e(G.trunc(l['orari'], 120))}</span></li>")
    if l.get('prezzo'):
        fatti.append(f"<li><b>Ingresso:</b> <span>{e(G.trunc(l['prezzo'], 80))}</span></li>")
    if l.get('eta'):
        fatti.append(f"<li><b>Età:</b> <span>{e(G.trunc(l['eta'], 60))}</span></li>")
    if l.get('tel'):
        fatti.append(f"<li><b>Telefono:</b> <a href=\"tel:{e(re.sub(r'[^0-9+]', '', l['tel']))}\">{e(l['tel'])}</a></li>")

    corpo = []
    if l.get('premium') and l.get('foto'):
        corpo.append(f'<img class="lg-foto" src="{e(l["foto"])}" alt="{e(l["nome"])}, '
                     f'{e(l["comune"])}" loading="lazy" decoding="async" width="360" height="270">')
    if l.get('descr'):
        corpo.append(f"<p>{e(G.trunc(l['descr'], 420))}</p>")
    corpo.append(f'<ul class="lg-facts">{"".join(fatti)}</ul>')

    # La memoria dell'agenda: e' il dato che questa pagina ha e le altre no.
    if l['n_eventi']:
        quanti = ("1 evento per famiglie" if l['n_eventi'] == 1
                  else f"{l['n_eventi']} eventi per famiglie")
        quando = f", l'ultimo il {data_lunga(l['ultimo'])}" if l.get('ultimo') else ""
        corpo.append(f'<p class="lg-manca">Qui DAOP ha seguito {quanti}{quando}.</p>')

    if prossimi:
        voci = "".join(
            f'<li><a href="{p["href"]}">{e(G.trunc(p["nome"], 70))}</a> '
            f'<span>· {data_breve(p["d"])}</span></li>' for p in prossimi[:5])
        corpo.append(f'<div class="lg-next"><p>In programma qui</p><ul>{voci}</ul></div>')

    if l.get('offerta'):
        corpo.append(f'<p class="lg-offerta"><b>Per le famiglie:</b> '
                     f'{e(G.trunc(l["offerta"], 200))}</p>')

    azioni = [f'<a href="{maps_href(l)}" target="_blank" rel="noopener">Apri nelle mappe</a>']
    if l.get('sito'):
        sito = l['sito'] if l['sito'].startswith('http') else 'https://' + l['sito']
        azioni.append(f'<a href="{e(sito)}" target="_blank" rel="noopener nofollow">Sito del luogo</a>')
    corpo.append(f'<div class="lg-act">{"".join(azioni)}</div>')

    if l.get('premium'):
        cura = e(l['premium_da']) if l.get('premium_da') else 'chi gestisce il luogo'
        corpo.append(f'<p class="lg-cura">Scheda curata da {cura} · spazio a pagamento, '
                     f'<a href="#come-ordiniamo">come funziona</a>.</p>')
    else:
        # Il modo in cui le 800 righe si riempiono davvero: non scrivendole
        # tutte noi, ma facendocele correggere da chi ci va.
        corpo.append('<p class="lg-manca">Manca qualcosa o è cambiato? '
                     '<a href="/index.html#social">Scrivicelo</a>.</p>')

    sigla = f' ({l["prov"]})' if l['prov'] else ''
    classe_prem = ' is-prem' if l.get('premium') else ''
    return (
        f'<details class="lg-row cat-{l["cat"]}{classe_prem}" '
        f'id="{l["slug"]}" data-cat="{l["cat"]}" data-prov="{l["prov"].lower()}" '
        f'data-riparo="{l["riparo"]}" data-agenda="{ha_agenda}">'
        f'<summary>'
        f'<span class="lg-ico"><svg viewBox="0 0 24 24" aria-hidden="true">'
        f'<use href="#{cat["icona"]}"/></svg></span>'
        f'<span class="lg-txt"><span class="lg-nome">{e(l["nome"])}</span>'
        f'<span class="lg-meta"><span class="lg-cat">{cat["label"]}</span> · '
        f'{e(l["comune"])}{sigla}</span></span>'
        f'{tag}{CHEV}</summary>'
        f'<div class="lg-body">{"".join(corpo)}</div></details>'
    )


def filtri(elenco):
    """La barra dei filtri, con le regole gia' prese altrove: sotto MIN_FILTRI
    non si stampa niente (si scorre prima l'elenco che una tendina), e una
    tendina con una voce sola non si stampa mai - e' un comando che non fa
    niente."""
    if len(elenco) < G.MIN_FILTRI:
        return ''
    campi = []

    # Le etichette a riposo sono corte apposta. Sul telefono la barra e'
    # appiccicosa: quattro tendine larghe andavano a capo e si mangiavano una
    # riga di schermo per tutto lo scorrimento - lo stesso conto gia' fatto
    # sull'agenda, dove accorciarle valse 47px.
    prov = [p for p in G.PROVINCE_PUBBLICATE if any(l['prov'] == p for l in elenco)]
    if len(prov) > 1:
        opts = "".join(f'<option value="{p.lower()}">Prov. {p}</option>' for p in prov)
        campi.append('<select class="ev-select" data-campo="prov" aria-label="Filtra per provincia">'
                     f'<option value="all">Prov.</option>{opts}</select>')

    cats = [c for c in ORDINE_CAT if any(l['cat'] == c for l in elenco)]
    if len(cats) > 1:
        opts = "".join(f'<option value="{c}">{CAT_INFO[c]["filtro"]}</option>' for c in cats)
        campi.append('<select class="ev-select" data-campo="cat" aria-label="Filtra per tipo di luogo">'
                     f'<option value="all">Tipo</option>{opts}</select>')

    # "Se piove" e' il filtro piu' usato di un elenco di posti con i bambini, e
    # vale la pena anche quando gli altri non ci sono. I "misto" restano visibili
    # in entrambi i casi: un castello ha il cortile e le sale, escluderlo da una
    # delle due risposte sarebbe piu' sbagliato che tenerlo in tutte e due.
    if any(l['riparo'] == 'chiuso' for l in elenco) and any(l['riparo'] == 'aperto' for l in elenco):
        campi.append('<select class="ev-select" data-campo="riparo" aria-label="Filtra per al chiuso o all\'aperto">'
                     '<option value="all">Se piove</option>'
                     '<option value="chiuso">Al chiuso</option>'
                     '<option value="aperto">All\'aperto</option></select>')

    # NON c'e' una quarta tendina "solo dove c'e' qualcosa in programma", ed e'
    # una scelta. Tecnicamente: quattro tendine sul telefono non stanno in una
    # riga (Chrome dimensiona una <select> sull'opzione piu' lunga) e la barra
    # appiccicosa passava da 109 a 156px, cioe' 47px di schermo occupati per
    # tutto lo scorrimento - lo stesso conto gia' fatto sull'agenda.
    # E prima ancora: quel filtro non si guadagna il posto. "Dove c'e' qualcosa
    # in programma" e' la domanda a cui risponde /eventi.html, che lo fa meglio
    # perche' li' l'evento e' la riga. Qui la riga e' il posto, e l'etichetta
    # verde con il numero lo dice gia' senza togliere niente dall'elenco.
    # Il JS il campo lo gestisce lo stesso: se un giorno la tendina serve,
    # basta rimetterla qui.

    if not campi:
        return ''
    return f"""    <div class="ev-toolbar" id="lg-toolbar">
      <div class="ev-search">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input type="search" id="lg-q" placeholder="Cerca un posto o un paese…" aria-label="Cerca fra i luoghi" autocomplete="off">
      </div>
{chr(10).join("      " + c for c in campi)}
    </div>
    <div class="ev-viewbar">
      <p class="lg-count" id="lg-count" role="status" aria-live="polite"></p>
      <button type="button" class="lg-reset" id="lg-reset" style="margin-left:auto">Azzera i filtri</button>
    </div>"""


def gruppi_comune(elenco, oggi):
    """Le righe raggruppate per comune. Il raggruppamento e' anche la risposta a
    "con che ordine sono messi": comune in ordine alfabetico, luoghi in ordine
    alfabetico dentro. Nessun criterio che si compra."""
    fuori = []
    for (prov, comune), righe in _per_comune(elenco):
        n = len(righe)
        pag = G.slugify(comune)
        # Il link alla pagina comune solo se la pagina esiste davvero: un
        # collegamento a una 404 vale meno di nessun collegamento.
        link = ''
        if os.path.exists(os.path.join(ROOT, 'eventi', 'comune', f'{pag}.html')):
            link = f'<a href="/eventi/comune/{pag}.html">Eventi a {G.esc(comune)} →</a>'
        fuori.append(
            f'<section class="lg-grp">'
            f'<div class="lg-grp-h"><h2 id="c-{pag}">{G.esc(comune)}</h2>'
            f'<span>{prov} · {n} {"luogo" if n == 1 else "luoghi"}</span>{link}</div>'
            + "".join(riga(l, oggi) for l in righe) + '</section>')
    return "\n".join(fuori)


def _per_comune(elenco):
    ordinati = collections.OrderedDict()
    for l in elenco:
        ordinati.setdefault((l['prov'], l['comune']), []).append(l)
    return list(ordinati.items())


def vetrina(elenco, oggi):
    """Il blocco "In evidenza". Esiste solo se qualcuno l'ha comprato, e lo dice
    in chiaro nella prima riga: e' l'unico punto della pagina in cui la
    posizione non dipende dall'ordine alfabetico."""
    scelti = [l for l in elenco if l.get('evidenza') and l.get('premium')][:3]
    if not scelti:
        return ''
    righe = "".join(riga(dict(l, slug=l['slug'] + '-ev'), oggi) for l in scelti)
    return (f'<div class="lg-vetrina"><p>In evidenza '
            f'<span>· spazi a pagamento, <a href="#come-ordiniamo">come funziona</a></span></p>'
            f'{righe}</div>')


COME_ORDINIAMO = """    <section class="lg-ordine" id="come-ordiniamo">
      <h2>Come è ordinato questo elenco</h2>
      <p>I luoghi sono raggruppati per comune in ordine alfabetico, e dentro ogni comune
      sono in ordine alfabetico. Non c'è nessun punteggio, nessuna preferenza e nessun
      criterio a pagamento che sposti una riga più in alto: i filtri restringono l'elenco,
      non lo riordinano.</p>
      <p>Alcune schede sono <b>curate da chi gestisce il luogo, che paga questo spazio</b>:
      hanno la dicitura “Scheda curata”, la foto e i contatti. Pagare cambia <em>cosa</em>
      c'è dentro la scheda, non <em>dove</em> sta la riga. L'unica eccezione è il blocco
      “In evidenza” in cima, che è a pagamento e lo dichiara: le stesse schede restano
      comunque al loro posto nell'elenco qui sotto.</p>
      <p>Le informazioni non contrassegnate come curate le mettiamo noi, e vengono dagli
      eventi che DAOP segue in zona: possono essere incomplete. Se un luogo che conosci è
      descritto male, <a href="/index.html#social">scrivicelo</a> — è così che questo
      elenco migliora.</p>
    </section>"""


def jsonld(elenco):
    """ItemList delle voci + Place completo SOLO per le schede curate.

    Un Place per ognuno dei 350 luoghi sarebbe mezzo mega di dati strutturati
    per dichiarare a Google dei nomi che non abbiamo verificato: i dati
    strutturati dicono "questo e' un fatto", e su una riga dedotta dall'agenda
    non lo e'. Le schede curate hanno orari, telefono e foto dati da chi
    gestisce il posto: quelle si possono dichiarare."""
    voci = []
    for i, l in enumerate(elenco, 1):
        voci.append({"@type": "ListItem", "position": i, "name": l['nome'],
                     "url": f"{PAGE_URL}#{l['slug']}"})
    grafo = [{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": PAGE_URL,
        "url": PAGE_URL,
        "name": "I luoghi delle famiglie fra Alessandria, Asti e Cuneo",
        "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": G.SITE_URL},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(elenco),
                       "itemListOrder": "https://schema.org/ItemListUnordered",
                       "itemListElement": voci},
    }]
    for l in elenco:
        if not l.get('premium'):
            continue
        p = {"@context": "https://schema.org", "@type": "Place",
             "@id": f"{PAGE_URL}#{l['slug']}", "name": l['nome'],
             "address": {"@type": "PostalAddress",
                         "addressLocality": l['comune'],
                         "addressRegion": l['prov'] or "Piemonte",
                         "addressCountry": "IT"}}
        if l.get('indirizzo'):
            p['address']['streetAddress'] = l['indirizzo']
        if l.get('lat') and l.get('lon'):
            p['geo'] = {"@type": "GeoCoordinates", "latitude": l['lat'], "longitude": l['lon']}
        for campo, chiave in (('descr', 'description'), ('foto', 'image'),
                              ('sito', 'url'), ('tel', 'telephone'),
                              ('orari', 'openingHours')):
            if l.get(campo):
                p[chiave] = l[campo]
        grafo.append(p)
    return "\n".join(
        '<script type="application/ld+json">\n' + json.dumps(g, ensure_ascii=False, indent=1)
        + '\n</script>' for g in grafo)


def render(elenco, oggi):
    css, nav, foot = G._guscio()
    e = G.esc
    n = len(elenco)
    comuni = len({(l['prov'], l['comune']) for l in elenco})
    con_eventi = sum(1 for l in elenco if l.get('prossimi'))
    prov_nomi = G.province_in_elenco({l['prov'] for l in elenco if l['prov']})

    # Senza "| DAOP" in coda, come le pagine di intenzione: il nome del sito sta
    # gia' in og:site_name, e in SERP quei sette caratteri sono quelli che fanno
    # tagliare il titolo. Cosi' sta in 49 caratteri invece di 68.
    #
    # E non dice "dove andare con i bambini", che pure sarebbe la ricerca piu'
    # grossa: oggi 55 righe su 173 sono piazze e vie in cui passa una sagra, e
    # promettere una guida di posti scelti sarebbe piu' di quello che la pagina
    # ha. Quando il catalogo del foglio sara' pieno, il titolo si potra' alzare.
    titolo = f"Luoghi per famiglie fra {prov_nomi}"
    descr = (f"{n} luoghi in {comuni} comuni fra {prov_nomi}: parchi, musei, castelli, "
             "piscine e spazi al chiuso. Si filtra per provincia, tipo e se piove.")

    intro = (f"<p class=\"lg-intro\">Sono <b>{n} luoghi</b> in <b>{comuni} comuni</b> "
             f"fra {prov_nomi}: i posti dove DAOP segue gli eventi per famiglie, più "
             "quelli che ci segnalate. Si filtra per provincia, per tipo e — quello che "
             "serve davvero — per <b>se piove</b>.</p>")
    if con_eventi:
        intro += (f"<p class=\"lg-intro\">In {con_eventi} di questi c'è già "
                  "qualcosa in programma: la riga lo dice, e porta all'evento.</p>")

    vuoto = ('<div class="lg-vuoto" id="lg-vuoto" hidden><b>Nessun luogo con questi filtri.</b>'
             'Prova a togliere la provincia o il tipo di luogo.</div>')

    corpo = "\n".join(x for x in [
        f'  <div class="lg-wrap">{intro}',
        filtri(elenco),
        vetrina(elenco, oggi),
        vuoto,
        gruppi_comune(elenco, oggi),
        COME_ORDINIAMO,
        '    <div class="com-link"><a href="/eventi.html">Tutta l\'agenda DAOP</a>'
        '<a href="/metodo.html">Come verifichiamo</a>'
        '<a href="/zone.html">Le zone</a></div>',
        f'    <p class="ev-firma-nota">Pagina rigenerata ogni notte. Ultimo aggiornamento: '
        f'{oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>',
        '  </div>',
    ] if x)

    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/genera_luoghi.py: le modifiche scritte a mano
     qui dentro spariscono alla run successiva, senza avvisare. Si tocca il
     generatore. Il CSS della nav, del footer e dei componenti comuni arriva da
     eventi.html tramite _guscio(): anche quello non si modifica qui. -->
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titolo)}</title>
<meta name="description" content="{e(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{PAGE_URL}">
<meta property="og:title" content="{e(titolo)}">
<meta property="og:description" content="{e(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{PAGE_URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.DEFAULT_IMG}">
<!-- Misure e alt dell'immagine sociale: senza, WhatsApp e Facebook devono
     scaricarla per sapere come impaginarla, e finche' non ci riescono mostrano
     l'anteprima senza figura. Sono i valori veri di headerdaop.jpg. Le altre
     pagine generate non li hanno ancora: quando si toccheranno quei generatori,
     si copiano da qui. -->
<meta property="og:image:width" content="1600">
<meta property="og:image:height" content="960">
<meta property="og:image:alt" content="Illustrazione: un adulto e un bambino camminano mano nella mano su un sentiero fra le colline, sotto un arcobaleno">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(titolo)}">
<meta name="twitter:description" content="{e(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{G.DEFAULT_IMG}">
<meta name="twitter:image:alt" content="Illustrazione: un adulto e un bambino camminano mano nella mano su un sentiero fra le colline, sotto un arcobaleno">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{G.PAGINA_CSS}{LUOGHI_CSS}{_css_categorie()}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
</head>
<body>
{SPRITE}
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>Luoghi</span>
    </div>
    <h1>I <em>luoghi</em> delle famiglie</h1>
    <p class="ev-when">{e(prov_nomi)} · {n} posti in {comuni} comuni</p>
  </div>
</header>
{corpo}
{G.blocco_ginetto()}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
{LUOGHI_JS}
{jsonld(elenco)}
</body>
</html>
"""


def _css_categorie():
    return "\n" + "\n".join(
        f".cat-{slug}{{--cat-color:{c};--cat-tint:{t};--cat-ink:{i}}}"
        for slug, (c, t, i) in COLORI_CAT.items()) + "\n"


def salva_istantanea(elenco):
    """L'istantanea che fa da ripiego quando il foglio non risponde.

    Si salvano solo i campi editoriali, non quelli dedotti dall'agenda: quelli
    si ricalcolano a ogni run e riscriverli qui vorrebbe dire committare ogni
    notte un file che cambia da solo."""
    fuori = []
    for l in elenco:
        if l.get('fonte') != 'catalogo':
            continue
        fuori.append({k: l.get(k, '') for k in (
            'nome', 'comune', 'prov', 'cat', 'indirizzo', 'riparo', 'prezzo', 'eta',
            'descr', 'orari', 'sito', 'tel', 'foto', 'lat', 'lon', 'premium_da', 'offerta')}
            | {'premium': 'Si' if l.get('premium') else '',
               'evidenza': 'Si' if l.get('evidenza') else ''})
    if not fuori:
        return
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(fuori, fh, ensure_ascii=False, indent=1)
    print(f"[genera_luoghi] istantanea salvata: {len(fuori)} luoghi di catalogo")


def update_sitemap(n):
    """Aggiunge (o aggiorna) la voce di luoghi.html nella sitemap.

    priority 0.8 come le pagine comune: e' una pagina che vale tutto l'anno.
    changefreq weekly e non daily - i posti non cambiano ogni notte, cambiano i
    riquadri "in programma" che ci stanno dentro."""
    if not os.path.exists(SITEMAP_PATH) or not n:
        return
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    voce = (f"  <url>\n    <loc>{PAGE_URL}</loc>\n    <lastmod>{oggi}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>")
    if f"<loc>{PAGE_URL}</loc>" in s:
        s = re.sub(r'  <url>\s*<loc>' + re.escape(PAGE_URL) + r'</loc>.*?</url>',
                   lambda _: voce, s, count=1, flags=re.S)
    else:
        s, k = re.subn(r'(?=  <url>\s*<loc>https://www\.daop\.it/eventi\.html</loc>)',
                       lambda _: voce + "\n", s, count=1)
        if k != 1:
            print("[genera_luoghi] sitemap: non trovo dove inserire luoghi.html, salto")
            return
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)
    print(f"[genera_luoghi] sitemap: luoghi.html -> {oggi}")


def main():
    oggi = datetime.date.today()
    catalogo = leggi_catalogo()
    agenda = leggi_agenda()
    elenco = unisci(catalogo, agenda)
    if not elenco:
        print("[genera_luoghi] nessun luogo: lascio la pagina com'è")
        return
    da_cat = sum(1 for l in elenco if l.get('fonte') == 'catalogo')
    premium = sum(1 for l in elenco if l.get('premium'))
    open(OUT_PATH, "w", encoding="utf-8").write(render(elenco, oggi))
    salva_istantanea(elenco)
    update_sitemap(len(elenco))
    peso = os.path.getsize(OUT_PATH) / 1024
    print(f"[genera_luoghi] luoghi.html: {len(elenco)} luoghi "
          f"({da_cat} da catalogo, {len(elenco) - da_cat} dall'agenda), "
          f"{premium} schede curate, {peso:.0f} KB")


if __name__ == "__main__":
    main()
