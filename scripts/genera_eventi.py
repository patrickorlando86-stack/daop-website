#!/usr/bin/env python3
"""
Genera/aggiorna la sezione eventi di eventi.html a partire dal foglio Google
"luoghi" (tab "eventi"). Pensato per girare in GitHub Actions ogni notte.

Fonte dati (in ordine di priorità):
  1. URL CSV in EVENTI_CSV_URL (es. export "Pubblica sul web" del tab eventi)
  2. URL CSV gviz di default (richiede foglio condiviso "chiunque con il link")
  3. data/eventi.json (istantanea committata, fallback se la rete non è disponibile)

Rigenera SOLO, dentro eventi.html, quello che sta fra i marker EVENTI-TIPO
(opzioni del filtro per tipo), EVENTI-LISTA (corsie "in evidenza" + agenda
raggruppata per giornata) e il blocco JSON-LD. Tutto il resto resta intatto.
"""
import os, re, csv, io, json, html, datetime, urllib.request, urllib.parse, unicodedata, sys, collections

SHEET_ID = "186XuLRXD2DXHL5CVy1vgNfmbEhpSbpW5pSgr4ARhugs"
DEFAULT_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Eventi"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(ROOT, "eventi.html")
HOME_PATH = os.path.join(ROOT, "index.html")
HOME_LIMIT = 8  # quanti eventi mostrare nel carosello della home
JSON_PATH = os.path.join(ROOT, "data", "eventi.json")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

# Province i cui eventi vengono pubblicati sul sito. Una sola lista, usata sia dal
# filtro dei dati sia dal copy che dice "che zona copre DAOP": prima la sigla era
# scritta a mano dentro normalize() e il numero di province era una costante "2"
# in un'altra pagina, quindi si poteva aprire il filtro e lasciare il testo che
# diceva il contrario. CN aggiunta il 04/08/2026, primi eventi di Cuneo sul foglio.
PROVINCE_PUBBLICATE = ('AL', 'AT', 'CN')
PROVINCE_NOMI = {'AL': 'Alessandria', 'AT': 'Asti', 'CN': 'Cuneo'}

# Pagina Instagram da cui arrivano le segnalazioni, provincia per provincia.
# "nostra": la pagina e' di DAOP (AL, AT) oppure di un partner (CN). Non e' un
# dettaglio grafico: su una pagina nostra il credito e' un rimando, su quella di
# un altro e' l'attribuzione di un lavoro che non e' nostro, ed e' il motivo per
# cui questa riga esiste. La locandina resta comunque dell'organizzatore: qui si
# dice DOVE l'abbiamo trovata, per questo "Segnalato da" e mai "Fonte".
# ATTENZIONE: e' il gemello di PROFILI in config_segreti.py del downloader, che
# sta in un altro repo. Se li' si aggiunge o cambia una provincia, questa mappa
# NON se ne accorge: l'evento arriva lo stesso e resta semplicemente senza
# credito (nessun errore, nessun link rotto). Da aggiornare a mano.
PROVINCE_IG = {
    'AL': {'ig': 'daop_alessandria', 'nostra': True,
           'fb': 'https://www.facebook.com/daopalessandria/',
           'curatore': 'Patrick Orlando'},
    'AT': {'ig': 'daop_asti', 'nostra': True,
           'fb': 'https://www.facebook.com/daopasti',
           'curatore': 'Alessandra Zaccone'},
    # Non e' un curatore DAOP: la provincia la segue una pagina esterna e noi la
    # ospitiamo. Scriverlo e' meglio che lasciar credere che ci sia qualcuno di
    # nostro sul posto. Il nome proprio c'e' lo stesso: una collaborazione con
    # una persona con un nome pesa diverso da una con un handle.
    'CN': {'ig': 'eventi_bambini_provincia_cuneo', 'nostra': False,
           'curatore': 'Giovanni'},
}


def fonte_provincia(prov):
    """Dati della pagina di provenienza, o None se la provincia non ne ha una."""
    f = PROVINCE_IG.get((prov or '').strip().upper())
    if not f:
        return None
    return dict(f, url=f"https://www.instagram.com/{f['ig']}/",
                provincia=PROVINCE_NOMI.get((prov or '').strip().upper(), ''))


def province_in_elenco(codici):
    """"Alessandria, Asti e Cuneo" a partire dalle sigle, in ordine di PROVINCE_PUBBLICATE."""
    nomi = [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE if c in set(codici)]
    if not nomi:
        return ""
    if len(nomi) == 1:
        return nomi[0]
    return ", ".join(nomi[:-1]) + " e " + nomi[-1]


KNOWN_CATS = {'Sagra & Festa', 'Sagra', 'Spettacolo', 'Laboratorio', 'Sport',
              'Musica', 'Cultura', 'Natura', 'Altro', 'Mercato', 'Arte',
              'Cinema', 'Teatro'}
MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
MESI_LUNGHI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
               'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
LABELS = {'feste': 'Sagre & Feste', 'spettacoli': 'Spettacoli', 'musica': 'Musica',
          'laboratori': 'Laboratori', 'sport': 'Sport', 'cultura': 'Cultura & Natura',
          'altro': 'Altro'}
ORDER = ['feste', 'spettacoli', 'laboratori', 'musica', 'sport', 'cultura', 'altro']


def pdate(s):
    s = (s or '').strip()
    for f in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def fetch_rows():
    """Restituisce una lista di dict (chiavi = intestazioni del foglio)."""
    base = os.environ.get("EVENTI_CSV_URL") or DEFAULT_CSV
    # Cache-buster: Google e le CDN possono servire una COPIA IN CACHE del CSV.
    # Era la causa del "sito non aggiornato" dopo una modifica al foglio: la run
    # leggeva dati vecchi e rigenerava identico. Un parametro univoco a ogni run
    # + header no-cache forzano una risposta fresca (DEFAULT_CSV = gviz = live).
    sep = '&' if '?' in base else '?'
    url = f"{base}{sep}_cb={int(datetime.datetime.now().timestamp())}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "daop-eventi-bot",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
        reader = list(csv.reader(io.StringIO(text)))
        hi = next(i for i, row in enumerate(reader) if any('Data Inizio' in c for c in row))
        header = [c.strip() for c in reader[hi]]
        out = []
        for row in reader[hi + 1:]:
            if not any(c.strip() for c in row):
                continue
            d = {header[i]: (row[i].strip() if i < len(row) else '') for i in range(len(header))}
            out.append(d)
        print(f"[genera_eventi] {len(out)} righe lette da CSV remoto")
        return out
    except Exception as e:  # fallback su istantanea locale
        print(f"[genera_eventi] CSV remoto non disponibile ({e}); uso {JSON_PATH}")
        with open(JSON_PATH, encoding="utf-8") as fh:
            snap = json.load(fh)
        # rimappa lo snapshot sulle stesse chiavi del foglio (comprese le
        # colonne editoriali, altrimenti il fallback perderebbe i consigli DAOP)
        return [dict({
            'Nome': e['nome'], 'Data Inizio': e['di'], 'Data fine': e['df'],
            'Ora': e['ora'], 'Città': e['citta'], 'Provincia': e['prov'],
            'Categoria': e['categoria'], 'Età': e['eta'], 'Prezzo': e['prezzo'],
            'Descrizione': e['descr'], 'Manifestazione': e.get('manifest', ''),
            'Locandina': e.get('loc', ''), 'Luogo': e.get('luogo', ''),
            'Indirizzo Completo': e.get('indirizzo', ''),
        }, **{nomi[0]: e[campo]
              for campo, nomi in dict(CAMPI_DAOP, **CAMPI_EXTRA).items()
              if (e.get(campo) or '').strip()})
            for e in snap]


# Colonne facoltative del foglio, in prosa. Il grosso del giudizio editoriale su
# DAOP passa dal flag "Consigliato DAOP", che c'e' gia' su ogni riga: queste
# restano per i casi in cui una frase serve davvero, e finche' sono vuote non
# compare nessun blocco (meglio niente che un titolo senza risposta).
# I nomi sono tollerati in piu' grafie perche' il foglio lo scrivono due persone.
CAMPI_DAOP = {
    'eta_consigliata': ("Età consigliata", "Eta consigliata", "Età ideale"),
    'adatto':          ("Adatto ai bambini", "Adatto davvero ai bambini"),
    'prenotazione':    ("Prenotazione", "Prenotazioni", "Serve prenotare"),
    'dintorni':        ("Nei dintorni", "Cosa fare nei dintorni", "Dintorni"),
}


# Colonne che nel foglio ci sono gia' e che finora buttavamo via: il giudizio
# DAOP e' in parte gia' stato dato, sotto forma di flag, e i recapiti e le
# coordinate sono i due dati che una risposta di un assistente non contiene mai.
CAMPI_EXTRA = {
    'contatto':        ("Contatto", "Contatti", "Telefono", "Email", "Recapiti"),
    'consigliato':     ("Consigliato DAOP", "Consigliato"),
    'adatto_famiglie': ("Adatto Famiglie", "Adatto alle famiglie", "Adatto famiglie"),
    'lat':             ("Latitude", "Latitudine", "Lat"),
    'lon':             ("Longitude", "Longitudine", "Lon", "Lng"),
}


def _key(s):
    """Chiave di confronto per le intestazioni: senza accenti, spazi e maiuscole.
    'Età consigliata', 'ETA CONSIGLIATA' e 'eta_consigliata' sono la stessa cosa."""
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', s.lower())


# Quali colonne editoriali esistono davvero nel foglio (a prescindere dal fatto
# che siano compilate). Serve a non chiedere a fine run di aggiungere una
# colonna che c'e' gia': l'unica cosa da fare, in quel caso, e' riempirla.
COLONNE_VISTE = set()


def campi_daop(d):
    """Legge dalla riga del foglio le colonne editoriali, se ci sono."""
    idx = {_key(k): (v or '').strip() for k, v in d.items()}
    out = {}
    for campo, nomi in dict(CAMPI_DAOP, **CAMPI_EXTRA).items():
        presenti = [_key(n) for n in nomi if _key(n) in idx]
        if presenti:
            COLONNE_VISTE.add(campo)
        out[campo] = next((idx[k] for k in presenti if idx[k]), '')
    return out


def si(v):
    """La colonna e' compilata a mano: 'Si', 'SI', 'Sì', 'x', 'true' valgono si."""
    return _key(v) in ('si', 'sì', 'x', 'true', 'vero', '1', 'y', 'yes')


def coord(e):
    """(lat, lon) come stringhe, solo se sono due numeri plausibili per l'Italia.
    Una cella con un appunto dentro non deve finire nei dati strutturati."""
    try:
        la, lo = float((e.get('lat') or '').replace(',', '.')), \
            float((e.get('lon') or '').replace(',', '.'))
    except ValueError:
        return None
    if 35 <= la <= 48 and 6 <= lo <= 19:
        return f"{la:.7f}".rstrip('0').rstrip('.'), f"{lo:.7f}".rstrip('0').rstrip('.')
    return None


TEL_RE = re.compile(r'(?:\+39[\s.]?)?(?:\d[\s.]?){8,12}\d')
MAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def contatti_html(testo):
    """I recapiti diventano link: da telefono si chiama, da mobile soprattutto.
    Il testo intorno resta come l'ha scritto chi compila il foglio."""
    t = (testo or '').strip()
    if not t:
        return ''
    pezzi, pos = [], 0
    trovati = sorted(
        [(m.start(), m.end(), 'mail') for m in MAIL_RE.finditer(t)]
        + [(m.start(), m.end(), 'tel') for m in TEL_RE.finditer(t)])
    # Un numero dentro un indirizzo email non va linkato due volte.
    ultimo = -1
    for a, b, tipo in trovati:
        if a < ultimo:
            continue
        # html.escape e non esc(): esc() fa strip, e qui mangerebbe lo spazio
        # fra il nome e il numero ("Patrizia351 6754801").
        pezzi.append(html.escape(t[pos:a]))
        val = t[a:b].strip()
        if tipo == 'mail':
            pezzi.append(f'<a href="mailto:{esc(val)}">{esc(val)}</a>')
        else:
            pezzi.append(f'<a href="tel:{esc(re.sub(r"[^+0-9]", "", val))}">{esc(val)}</a>')
        pos, ultimo = b, b
    pezzi.append(html.escape(t[pos:]))
    return "".join(pezzi)


def normalize(rows):
    today = datetime.date.today()
    events = []
    for d in rows:
        di = pdate(d.get('Data Inizio'))
        if not di:
            continue
        prov = (d.get('Provincia') or '').strip().upper()
        if prov not in PROVINCE_PUBBLICATE:
            continue
        df = pdate(d.get('Data fine')) or di
        if df < today:
            continue
        events.append(dict(
            nome=d.get('Nome', ''), di=d.get('Data Inizio', ''), df=d.get('Data fine', ''),
            ora=d.get('Ora', ''), citta=d.get('Città', ''), prov=prov,
            categoria=(d.get('Categoria', '') if d.get('Categoria', '') in KNOWN_CATS else ''),
            eta=d.get('Età', ''), prezzo=d.get('Prezzo', ''), descr=d.get('Descrizione', ''),
            manifest=d.get('Manifestazione', ''), loc=d.get('Locandina', ''),
            luogo=d.get('Luogo', ''), indirizzo=d.get('Indirizzo Completo', ''),
            d_start=di, d_end=df,
            **campi_daop(d),
        ))
    # Ordina per "data utile": un evento già iniziato ma ancora in corso viene
    # trattato come se iniziasse oggi (max(inizio, oggi)), così non finisce in
    # cima con una data passata. A parità di data utile diamo priorità alle
    # novità (eventi che iniziano oggi/domani): gli eventi già in corso, meno
    # "urgenti", scivolano in fondo al gruppo del giorno (d_start < today = True
    # ordina dopo False). Poi l'inizio reale e il nome fanno da spareggio.
    events.sort(key=lambda e: (max(e['d_start'], today), e['d_start'] < today,
                               e['d_start'], e['nome']))
    return events


# Icone dello sprite (assets/icons.svg.html) per categoria. Prima qui c'erano
# emoji: si vedevano diverse su ogni sistema operativo ed erano il segnale piu'
# evidente di "sito fatto in casa".
ICONS = {'feste': 'i-party', 'spettacoli': 'i-drama', 'musica': 'i-music',
         'laboratori': 'i-palette', 'sport': 'i-bike', 'cultura': 'i-landmark',
         'altro': 'i-pin'}


def icon(slug, cls="icon"):
    """Markup dell'icona di categoria, presa dallo sprite inline della pagina."""
    # viewBox obbligatorio: senza, sotto i 24px l'icona viene tagliata.
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">'
            f'<use href="#{ICONS[slug]}"/></svg>')


def bucket(e):
    """Restituisce (slug, icona_svg, etichetta) per la categoria dell'evento."""
    def out(slug, label):
        return slug, icon(slug), label

    cz = e['categoria'].lower()
    if 'sagra' in cz or 'festa' in cz or 'mercato' in cz or 'fiera' in cz: return out('feste', 'Sagra & Festa')
    if 'spettacolo' in cz or 'teatro' in cz or 'cinema' in cz: return out('spettacoli', 'Spettacolo')
    if 'musica' in cz: return out('musica', 'Musica')
    if 'laborator' in cz or 'arte' in cz: return out('laboratori', 'Laboratorio')
    if 'sport' in cz: return out('sport', 'Sport')
    if 'cultura' in cz or 'natura' in cz: return out('cultura', 'Cultura')
    nd = (e['nome'] + ' ' + e['descr']).lower()
    if 'sagra' in nd or 'festa' in nd or 'fiera' in nd: return out('feste', 'Sagra & Festa')
    if 'concerto' in nd or 'musica' in nd: return out('musica', 'Musica')
    if 'laborator' in nd: return out('laboratori', 'Laboratorio')
    if 'spettacol' in nd or 'teatro' in nd: return out('spettacoli', 'Spettacolo')
    if any(k in nd for k in ['sport', 'corsa', 'pedalata', 'run', 'ciclo']): return out('sport', 'Sport')
    return out('altro', 'Evento')


SITE_URL = "https://www.daop.it"
PAGE_URL = f"{SITE_URL}/eventi.html"
DEFAULT_IMG = f"{SITE_URL}/assets/images/headerdaop.jpg"
FREE_KW = ('gratuito', 'gratis', 'libero', 'ingresso libero')


def loc_path(loc):
    """Percorso della locandina per il browser: un nome file diventa
    root-relative (/assets/eventi/<file>, valido sia in locale sia live),
    un URL completo resta intatto. Vuoto se assente. Usato nelle card."""
    loc = (loc or '').strip()
    if not loc:
        return ''
    if loc.startswith(('http://', 'https://')):
        return loc
    return f"/assets/eventi/{loc.lstrip('/')}"


def loc_url(loc):
    """URL assoluto della locandina, per i dati strutturati schema.org
    (che richiedono URL assoluti). Vuoto se assente."""
    p = loc_path(loc)
    if not p or p.startswith(('http://', 'https://')):
        return p
    return f"{SITE_URL}{p}"


def esc(s):
    return html.escape((s or '').strip())


def trunc(s, n):
    s = (s or '').strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


PIN_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
CLOCK_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
USER_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>'
CAL_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
NAV_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'
# Come ARROW_SVG ma con width/height espliciti. ARROW_SVG nasce per .he-more,
# dove e' il CSS a dargli una misura; dentro .event-act nessuna regola lo
# dimensiona, e un SVG senza dimensioni intrinseche si espande fino a sfondare
# la riga. Le altre icone di .event-act portano width/height inline: questa fa
# lo stesso.
ACT_ARROW_SVG = ARROW_SVG.replace('<svg ', '<svg width="14" height="14" ', 1)
CHEV_SVG = '<svg class="ev-chev" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>'
IMG_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>'
HL_LIMIT = 12  # quante schede al massimo nelle corsie "Oggi" / "Questo weekend"


def _luogo_query(e):
    """Stringa luogo migliore disponibile per Maps/calendario."""
    q = (e.get('indirizzo') or '').strip()
    if not q:
        q = " ".join(x for x in [e.get('luogo', ''), e.get('citta', ''),
                                 f"({e['prov']})" if e.get('prov') else ''] if x).strip()
    return q


def maps_url(e):
    """Link 'Come arrivare' su Google Maps.

    Con le coordinate del foglio si va sul punto esatto: la ricerca per nome
    del luogo, in paesi dove la piazza non e' geocodificata, apre il centro del
    comune e ti lascia a cercare a piedi."""
    xy = coord(e)
    if xy:
        return f"https://www.google.com/maps/search/?api=1&query={xy[0]},{xy[1]}"
    q = _luogo_query(e)
    if not q:
        return ''
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q + ", Italia")


def gcal_url(e):
    """Link 'Aggiungi al calendario' (Google Calendar, evento tutto-il-giorno:
    niente fusi orari, robusto anche quando l'ora non è certa)."""
    start = e['d_start'].strftime('%Y%m%d')
    end = (e['d_end'] + datetime.timedelta(days=1)).strftime('%Y%m%d')  # fine esclusiva
    params = {
        'action': 'TEMPLATE',
        'text': (e['nome'] or '').strip(),
        'dates': f"{start}/{end}",
        'details': (e['descr'] or '').strip()[:900],
        'location': _luogo_query(e),
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

# Per ogni categoria: colore d'accento (bordi, icone, sfondi), tinta di
# sfondo, e "inchiostro" per il testo. Il terzo serve perche' i colori
# d'accento come testo su bianco non raggiungono i 4.5:1 richiesti da WCAG AA
# (il teal stava a 2.77:1). Calcolati sul caso peggiore, cioe' sul testo
# posato sulla PROPRIA tinta di sfondo, non sul bianco.
COLORS = {
    'feste': ('#e8954a', 'rgba(232,149,74,0.14)', '#a75b15'),
    'spettacoli': ('#6c63a6', 'rgba(108,99,166,0.14)', '#6a61a5'),
    'laboratori': ('#6ba5a8', 'rgba(107,165,168,0.16)', '#467477'),
    'musica': ('#c9a227', 'rgba(201,162,39,0.16)', '#846a1a'),
    'sport': ('#188663', 'rgba(24,134,99,0.14)', '#167859'),
    'cultura': ('#4a90b9', 'rgba(74,144,185,0.14)', '#397293'),
    'altro': ('#7e8c99', 'rgba(126,140,153,0.16)', '#606d7a'),
}


def weekend_range(today):
    """Sabato e domenica del weekend più vicino. Se oggi è già sabato o domenica
    restituisce il weekend in corso, così la sezione "Questo weekend" non salta
    di una settimana proprio nei giorni in cui serve di più."""
    dow = today.weekday()  # 0 = lunedì … 6 = domenica
    sat = today - datetime.timedelta(days=1) if dow == 6 else today + datetime.timedelta(days=(5 - dow) % 7)
    return sat, sat + datetime.timedelta(days=1)


def prezzo_pill(e):
    pz = (e['prezzo'] or '').lower()
    if any(k in pz for k in FREE_KW):
        return '<span class="ev-pill is-free">Gratuito</span>'
    if e['prezzo']:
        return f'<span class="ev-pill is-price">{esc(trunc(e["prezzo"], 26))}</span>'
    return ''


def riga(e, today, hub=None):
    """Una riga dell'agenda: intestazione sempre visibile (miniatura, nome,
    contesto, etichette) + dettaglio che si apre al tocco."""
    slug, cat_icon, catlabel = bucket(e)
    color, tint, ink = COLORS.get(slug, COLORS['altro'])
    ongoing = e['d_start'] < today
    anchor = e.get('anchor', '')
    cover = loc_path(e['loc'])
    thumb = (f'<img class="ev-thumb" src="{cover}" alt="" loading="lazy" decoding="async">'
             if cover else f'<span class="ev-thumb is-ph" aria-hidden="true">{cat_icon}</span>')

    # La data sta già nell'intestazione del giorno: qui restano luogo, durata,
    # orario ed età, cioè quello che serve per decidere in un colpo d'occhio.
    bits = [f"{esc(e['citta'])} ({e['prov']})" if e['citta'] else e['prov']]
    de = e['d_end']
    if ongoing:
        bits.append('ultimo giorno' if de == today else f"fino al {de.day} {MESI[de.month-1]}")
    elif de != e['d_start']:
        bits.append(f"fino al {de.day} {MESI[de.month-1]}")
    if e['ora']:
        bits.append(esc(trunc(e['ora'], 28)))
    if e['eta']:
        bits.append(esc(trunc(e['eta'], 26)))

    tags = [f'<span class="ev-pill is-cat">{cat_icon} {esc(catlabel)}</span>']
    # Il consiglio di DAOP viene prima del prezzo e della manifestazione: e' il
    # motivo per cui uno guarda l'agenda nostra invece di un elenco qualsiasi.
    if si(e.get('consigliato')):
        tags.append(f'<span class="ev-pill is-daop">{STAR_SVG} Consigliato DAOP</span>')
    if ongoing:
        tags.append('<span class="ev-pill is-live">In corso</span>')
    pill = prezzo_pill(e)
    if pill:
        tags.append(pill)
    if e['manifest']:
        tags.append(f'<span class="ev-pill is-tag">{esc(trunc(e["manifest"], 34))}</span>')

    acts = []
    # Link alla pagina dedicata, quando esiste: è la via con cui Google la
    # scopre e le passa autorità dall'agenda, che è la pagina più forte del sito.
    if ha_pagina(e):
        acts.append(f'<a class="event-act" href="/eventi/{slug_evento(e)}.html">'
                    f'{ACT_ARROW_SVG} Scheda completa</a>')
    murl = maps_url(e)
    if murl:
        acts.append(f'<a class="event-act" href="{murl}" target="_blank" rel="noopener">{NAV_SVG} Come arrivare</a>')
    acts.append(f'<a class="event-act" href="{gcal_url(e)}" target="_blank" rel="noopener">{CAL_SVG} Calendario</a>')
    if cover:
        acts.append(f'<a class="event-act" href="{cover}" target="_blank" rel="noopener">{IMG_SVG} Locandina</a>')
    # Il comune, quando ha una pagina sua. Sta in fondo perche' non e' un'azione
    # su QUESTO evento ma una via laterale, ed e' dentro il dettaglio che si apre
    # (nella riga chiusa la citta' vive dentro un <button>, dove un <a> non puo'
    # stare). Riguarda solo i comuni sopra soglia: gli altri restano testo.
    mio_hub = (hub or {}).get(_key(e.get('citta')))
    if mio_hub:
        acts.append(f'<a class="event-act" href="/eventi/comune/{mio_hub["slug"]}.html">'
                    f'{PIN_SVG} Tutti gli eventi{a_citta(mio_hub["nome"])}</a>')

    dove = esc(e['indirizzo'] or e['luogo'])
    dove_html = f'\n          <p class="ev-where">{PIN_SVG} {dove}</p>' if dove else ''

    # Il credito va anche QUI, non solo sulla scheda dedicata: le schede sono 71
    # su 187 eventi, quindi per due terzi dell'agenda l'attribuzione non
    # esisterebbe da nessuna parte.
    # Cliccabile: le occorrenze sono ~190 ma le destinazioni sono TRE, e i motori
    # consolidano per URL di destinazione - non e' un elenco di link diversi. Un
    # credito che non si puo' seguire e' mezzo credito, soprattutto per Cuneo.
    f = fonte_provincia(e['prov'])
    fonte_html = (f'\n            <p class="ev-src">Segnalato da '
                  f'<a href="{f["url"]}" target="_blank" rel="noopener">'
                  f'@{esc(f["ig"])}</a></p>' if f else '')

    return f'''        <article class="event-card{' is-ongoing' if ongoing else ''}" id="{anchor}" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <h4 class="ev-h"><button class="ev-row" type="button" aria-expanded="false" aria-controls="det-{anchor}">
            {thumb}
            <span class="ev-main">
              <span class="ev-name">{esc(trunc(e['nome'], 110))}</span>
              <span class="ev-line">{' · '.join(bits)}</span>
              <span class="ev-tags">{''.join(tags)}</span>
            </span>
            {CHEV_SVG}
          </button></h4>
          <div class="ev-det" id="det-{anchor}" hidden>
            <p class="event-desc">{esc(e['descr'])}</p>{dove_html}
            <div class="event-actions">
              {chr(10) + '              '.join(acts)}
            </div>{fonte_html}
          </div>
        </article>'''


def hl_card(e, eager=False):
    """Scheda compatta con locandina per le corsie "Oggi" e "Questo weekend".
    Punta all'ancora della riga corrispondente più in basso nell'agenda.

    eager=True per le prime schede: sono sopra la piega e una di loro e'
    l'elemento LCP, quindi il lazy loading la rallenterebbe soltanto."""
    slug, cat_icon, catlabel = bucket(e)
    color, tint, ink = COLORS.get(slug, COLORS['altro'])
    cover = loc_path(e['loc'])
    load = ('loading="eager" fetchpriority="high"' if eager
            else 'loading="lazy"')
    img = (f'<img src="{cover}" alt="" {load} decoding="async">'
           if cover else f'<span class="ev-hl-ph" aria-hidden="true">{cat_icon}</span>')
    bits = [f"{esc(e['citta'])} ({e['prov']})" if e['citta'] else e['prov']]
    if e['ora']:
        bits.append(esc(trunc(e['ora'], 20)))
    pill = prezzo_pill(e)
    return f'''        <a class="ev-hl-card" href="#{e.get('anchor', '')}" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <span class="ev-hl-cover">{img}</span>
          <span class="ev-hl-body">
            <span class="ev-hl-cat">{cat_icon} {esc(catlabel)}</span>
            <span class="ev-hl-name">{esc(trunc(e['nome'], 70))}</span>
            <span class="ev-hl-meta">{' · '.join(bits)}</span>
            {pill}
          </span>
        </a>'''


EAGER_HL = 2  # quante schede della prima corsia caricano l'immagine subito


def rail(titolo, lista, slug, eager=False):
    if not lista:
        return ''
    cards = '\n'.join(hl_card(e, eager=eager and i < EAGER_HL)
                      for i, e in enumerate(lista))
    return (f'      <section class="ev-hl-block" data-rail="{slug}">\n'
            f'        <h3 class="ev-hl-title">{titolo}<span class="ev-hl-n">{len(lista)}</span></h3>\n'
            f'        <div class="ev-rail">\n' + cards +
            '\n        </div>\n      </section>')


def intestazione_giorno(d, today):
    """'Oggi · lunedì 27 luglio'. Il prefisso viene ricalcolato anche lato JS,
    così resta corretto se la pagina viene servita da cache il giorno dopo."""
    if d == today:
        pre = 'Oggi · '
    elif d == today + datetime.timedelta(days=1):
        pre = 'Domani · '
    else:
        pre = ''
    return f"{pre}{GIORNI[d.weekday()]} {d.day} {MESI_LUNGHI[d.month - 1]}"


def render(events, hub=None):
    """Restituisce (opzioni del filtro Tipo, agenda completa)."""
    today = datetime.date.today()
    present = {bucket(e)[0] for e in events}

    # ── in evidenza: oggi e il primo weekend utile ──────────────────────────
    sat, sun = weekend_range(today)
    oggi = [e for e in events if e['d_start'] <= today <= e['d_end']]
    visti = {id(e) for e in oggi}
    wknd = [e for e in events if id(e) not in visti and e['d_start'] <= sun and e['d_end'] >= sat]
    blocchi = [rail('Oggi', oggi[:HL_LIMIT], 'oggi'),
               rail('Questo weekend', wknd[:HL_LIMIT], 'weekend')]
    blocchi = [b for b in blocchi if b]
    highlights = ''
    if blocchi:
        highlights = (f'    <div class="ev-highlights" id="ev-highlights" data-day="{today.isoformat()}">\n'
                      + '\n'.join(blocchi) + '\n    </div>\n\n')

    # ── agenda: prima la giornata più vicina ("Oggi"), poi gli eventi già
    #    iniziati ma ancora in corso, infine gli altri giorni. Prima il gruppo
    #    "in corso" apriva l'agenda: sul telefono spingeva "Oggi" sotto una
    #    lista di 10-15 sagre/mostre lunghe già partite, e chi apre la pagina
    #    vuole vedere subito cosa c'è OGGI, non cosa è iniziato la settimana scorsa.
    per_giorno = {}
    for e in events:
        if e['d_start'] >= today:
            per_giorno.setdefault(e['d_start'], []).append(e)
    giorni = sorted(per_giorno)
    in_corso = [e for e in events if e['d_start'] < today]

    gruppi = []
    if giorni:  # la giornata più vicina (di norma "Oggi") apre sempre l'agenda
        d0 = giorni.pop(0)
        gruppi.append((d0.isoformat(), intestazione_giorno(d0, today), per_giorno[d0]))
    if in_corso:
        gruppi.append(('in-corso', 'Già iniziati, ancora in corso', in_corso))
    for d in giorni:
        gruppi.append((d.isoformat(), intestazione_giorno(d, today), per_giorno[d]))

    sezioni = []
    for day, titolo, lista in gruppi:
        righe = '\n'.join(riga(e, today, hub) for e in lista)
        sezioni.append(f'''      <section class="ev-day" data-day="{day}">
        <h3 class="ev-dayhead"><span class="ev-dayname">{titolo}</span><span class="ev-daycount">{len(lista)}</span></h3>
{righe}
      </section>''')

    # Le pagine di provenienza, linkate UNA volta sola: sulle card il credito e'
    # testo, qui sotto ci sono i link veri. Solo le province con eventi in agenda,
    # cosi' la riga non promette una zona che oggi e' vuota.
    presenti = [s for s in PROVINCE_PUBBLICATE
                if any(e['prov'].upper() == s for e in events)]
    fonti = [f for f in (fonte_provincia(s) for s in presenti) if f]
    fonti_html = ''
    if fonti:
        # Non sono tutte la stessa cosa, e metterle in fila lo faceva credere.
        # Le pagine DAOP sono nostre, quella di Cuneo e' di Giovanni e noi la
        # ospitiamo: la riga separa le due frasi invece di elencare tre handle.
        # Il flag arriva da PROVINCE_IG, lo stesso che usa zone.html.
        def elenco(voci):
            return " · ".join(f'<a href="{f["url"]}" target="_blank" rel="noopener">'
                              f'@{esc(f["ig"])}</a> ({esc(f["provincia"])})' for f in voci)
        nostre = [f for f in fonti if f['nostra']]
        ospiti = [f for f in fonti if not f['nostra']]
        frasi = []
        if nostre:
            frasi.append('Gli eventi arrivano dalle pagine DAOP di zona: '
                         + elenco(nostre) + '.')
        if ospiti:
            quali = " e ".join(f"{esc(f['provincia'])} la segue "
                               f"<a href=\"{f['url']}\" target=\"_blank\" rel=\"noopener\">"
                               f"@{esc(f['ig'])}</a>" for f in ospiti)
            frasi.append(f'{quali}: una pagina che non è nostra, con cui '
                         'collaboriamo e che accreditiamo su ogni scheda.')
        fonti_html = ('\n    <p class="ev-fonti">' + ' '.join(frasi)
                      + f'<br><a href="{ZONE_HREF}">Chi segue la tua provincia</a></p>')

    lista_html = (highlights + '    <div class="events-list" id="events-list">\n'
                  + '\n\n'.join(sezioni) + '\n    </div>' + fonti_html)

    # "Categorie" e non "Tutte le categorie": in un <select> stretto il testo
    # veniva tagliato a meta' sul telefono.
    opts = ['      <option value="all">Categorie</option>']
    for s in ORDER:
        if s in present:
            opts.append(f'      <option value="{s}">{LABELS[s]}</option>')
    return '\n'.join(opts), lista_html


def render_home(events):
    """Card compatte per il carosello "Prossimi eventi" della home (index.html).
    Mostra i primi HOME_LIMIT eventi futuri, ognuno linkato alla card completa
    in eventi.html tramite la sua ancora."""
    items = events[:HOME_LIMIT]
    if not items:
        return ('      <p class="he-empty">Nessun evento in programma al momento. '
                '<a href="eventi.html" style="color:var(--orange);font-weight:700;">'
                'Vedi tutti gli eventi →</a></p>')
    today = datetime.date.today()
    cards = []
    for e in items:
        slug, cat_icon, catlabel = bucket(e)
        d = e['d_start']
        ongoing = d < today
        datebox = ('<span class="he-live">In corso</span>' if ongoing else
                   f'<span class="he-date"><span class="d">{d.day:02d}</span>'
                   f'<span class="m">{MESI[d.month-1]}</span></span>')
        color, tint, ink = COLORS.get(slug, COLORS['altro'])
        luogo = (esc(e['citta']) + f" ({e['prov']})") if e['citta'] else e['prov']
        pz = (e['prezzo'] or '').lower()
        if any(k in pz for k in FREE_KW):
            price = '<span class="he-price free">Gratuito</span>'
        elif e['prezzo']:
            price = f'<span class="he-price">{esc(trunc(e["prezzo"], 22))}</span>'
        else:
            price = '<span class="he-price">&nbsp;</span>'
        cover_url = loc_path(e['loc'])
        cover = (f'        <div class="he-cover"><img src="{cover_url}" '
                 f'alt="Locandina: {esc(trunc(e["nome"], 70))}" loading="lazy" decoding="async"></div>\n'
                 if cover_url else '')
        href = f"eventi.html#{e.get('anchor', '')}"
        cards.append(f'''      <a class="he-card" href="{href}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
{cover}        <div class="he-body">
          <div class="he-top">
            <span class="he-icon">{cat_icon}</span>
            <span class="he-cat">{esc(catlabel)}</span>
            {datebox}
          </div>
          <h3 class="he-title">{esc(trunc(e['nome'], 64))}</h3>
          <div class="he-meta"><span>{PIN_SVG} {luogo}</span></div>
          <div class="he-foot">
            {price}
            <span class="he-more">Scopri di più {ARROW_SVG}</span>
          </div>
        </div>
      </a>''')
    return '\n\n'.join(cards)


def slugify(s):
    """Slug ASCII per ancore/URL: 'Sagra di Città' -> 'sagra-di-citta'."""
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s[:50].strip('-') or 'evento'


def assegna_ancore(events):
    """Dà a ogni evento un id univoco e stabile (data + slug del nome), usato sia
    come ancora della card sia come URL nei dati strutturati."""
    seen = set()
    for e in events:
        base = f"ev-{e['d_start'].isoformat()}-{slugify(e['nome'])}"
        anchor, i = base, 2
        while anchor in seen:
            anchor = f"{base}-{i}"
            i += 1
        seen.add(anchor)
        e['anchor'] = anchor


def parse_times(ora):
    """Estrae fino a due orari HH:MM (inizio/fine) dal campo Ora."""
    return [f"{int(h):02d}:{m}" for h, m in re.findall(r'(\d{1,2})[:.](\d{2})', ora or '')][:2]


def parse_price(prezzo):
    """Estrae il prezzo numerico più basso (in €) dal testo; None se assente.
    Considera solo i numeri accostati a € o "euro", per non confondere
    prezzi con età o numero di persone."""
    p = prezzo or ''
    nums = re.findall(r'€\s*(\d+(?:[.,]\d{1,2})?)', p)
    nums += re.findall(r'(\d+(?:[.,]\d{1,2})?)\s*(?:€|euro)', p, re.I)
    vals = []
    for n in nums:
        try:
            v = float(n.replace(',', '.'))
            if v > 0:
                vals.append(v)
        except ValueError:
            pass
    if not vals:
        return None
    v = min(vals)
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def rome_offset(d):
    """Offset di Europe/Rome per una data: +02:00 in ora legale, +01:00 altrimenti."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Rome")
    except Exception:                      # tzdata assente: assume ora solare
        return "+01:00"
    off = datetime.datetime(d.year, d.month, d.day, 12, tzinfo=tz).utcoffset()
    total = int(off.total_seconds()) // 60
    return f"{'+' if total >= 0 else '-'}{abs(total) // 60:02d}:{abs(total) % 60:02d}"


def event_jsonld(e, url_override=None):
    """Costruisce un oggetto schema.org/Event per un singolo evento.

    url_override: URL canonico dell'evento. Se l'evento ha una pagina dedicata
    passiamo quella, così i dati strutturati puntano alla pagina che vogliamo
    far posizionare invece che all'ancora dentro l'agenda."""
    times = parse_times(e['ora'])
    start = e['d_start'].isoformat()
    if times:
        start += f"T{times[0]}{rome_offset(e['d_start'])}"
    end = e['d_end'].isoformat()
    if len(times) > 1:
        end += f"T{times[1]}{rome_offset(e['d_end'])}"
    elif times:
        end += f"T{times[0]}{rome_offset(e['d_end'])}"

    city = (e['citta'] or '').strip()
    address = {"@type": "PostalAddress", "addressCountry": "IT"}
    if city:
        address["addressLocality"] = city
    if e['prov']:
        address["addressRegion"] = e['prov']
    venue = (e.get('luogo') or '').strip()
    if venue:
        address["streetAddress"] = venue
    if url_override:
        ev_url = url_override
    else:
        ev_url = f"{PAGE_URL}#{e['anchor']}" if e.get('anchor') else PAGE_URL

    obj = {
        "@type": "Event",
        "name": (e['nome'] or '').strip(),
        "startDate": start,
        "endDate": end,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": venue or city or e['prov'],
            "address": address,
        },
        "image": [loc_url(e['loc']) or DEFAULT_IMG],
        "url": ev_url,
    }
    # Questi eventi sono organizzati da pro loco, comuni e associazioni: DAOP
    # li raccoglie e li segnala. Dichiarare DAOP come chi organizza o chi si
    # esibisce e' un dato strutturato falso, e Google lo incrocia con le altre
    # fonti.
    #
    # La manifestazione del foglio NON va in superEvent come semplice nome:
    # Google legge quell'oggetto come un secondo Event a se' stante, che ha solo
    # "name" e quindi risulta privo di startDate e location (errori critici in
    # Search Console: 0 elementi non validi fino al 01/08/2026, 224 il giorno
    # dopo il deploy che introduceva questo blocco). Per dichiararla servirebbe
    # un evento-padre completo di date e luogo propri, dato che il foglio non
    # ha; il nome della manifestazione resta comunque visibile nella card.
    # Chi organizza: NON lo inventiamo, lo leggiamo dalla coda del nome quando il
    # foglio ce l'ha ("... - Pro Loco Ciglione"). E' il dato che Google incrocia
    # con le altre fonti, quindi o e' quello vero o non ci va.
    org = organizzatore(e.get('nome'))
    if org:
        obj["organizer"] = {"@type": "Organization", "name": org}
        # I recapiti del foglio sono di chi organizza, non di DAOP: vanno
        # sull'organizzatore, e solo se abbiamo un nome a cui attaccarli.
        cont = (e.get('contatto') or '').strip()
        mail = MAIL_RE.search(cont)
        tel = TEL_RE.search(cont)
        if mail:
            obj["organizer"]["email"] = mail.group(0)
        if tel:
            obj["organizer"]["telephone"] = re.sub(r'[^+0-9]', '', tel.group(0))
    xy = coord(e)
    if xy:
        obj["location"]["geo"] = {"@type": "GeoCoordinates",
                                  "latitude": xy[0], "longitude": xy[1]}
    if si(e.get('adatto_famiglie')):
        obj["audience"] = {"@type": "Audience", "audienceType": "Famiglie con bambini"}
    fascia = fascia_eta(e.get('eta_consigliata') or e.get('eta'))
    if fascia:
        obj["typicalAgeRange"] = fascia
    descr = (e['descr'] or '').strip()
    if descr:
        obj["description"] = descr

    # offers: includiamo price + priceCurrency + validFrom (richiesti per un'offerta valida).
    # Per gli eventi "a pagamento" senza una cifra nota omettiamo offers, così da non
    # generare un'offerta incompleta (causa degli avvisi di Search Console).
    pz = (e['prezzo'] or '').lower()
    if any(k in pz for k in FREE_KW):
        price = "0"
        obj["isAccessibleForFree"] = True
    else:
        price = parse_price(e['prezzo'])
    if price is not None:
        obj["offers"] = {"@type": "Offer", "price": price, "priceCurrency": "EUR",
                         "availability": "https://schema.org/InStock",
                         "validFrom": e['d_start'].isoformat(), "url": ev_url}
    return obj


def render_jsonld(events):
    """Blocco <script> JSON-LD con tutti gli eventi (schema.org/Event)."""
    graph = [event_jsonld(e, pagina_url(e) if ha_pagina(e) else None) for e in events]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph},
                         ensure_ascii=False, indent=2)
    return ('<script type="application/ld+json" id="eventi-jsonld">\n'
            + payload + '\n</script>')


# ---------------------------------------------------------------------------
# PAGINE EVENTO DEDICATE
#
# Perche': in Search Console le query per nome della singola sagra ("festa
# valenzani 2026", "sagra basaluzzo 2026") portano decine di impressioni con
# zero clic, perche' ci arriviamo con l'agenda generica in ottava posizione.
# Una pagina per evento risponde esattamente a quella query.
#
# Solo sagre e feste: e' dove abbiamo insieme la domanda di ricerca e le
# descrizioni piu' ricche (18 su 31 sopra i 300 caratteri, contro una mediana
# di 212 sul totale). Generare tutti e 143 gli eventi produrrebbe decine di
# pagine-template magre, che Google penalizza oltre la singola pagina.
#
# Le pagine NON vengono mai cancellate. normalize() scarta gli eventi passati,
# quindi una sagra conclusa sparisce dalla sorgente: rigenerare solo dal feed
# significherebbe un 404 per ogni edizione finita. Il registro in
# data/pagine-evento.json conserva i dati, la pagina resta online marcata
# "edizione conclusa" e se l'anno dopo la sagra torna la stessa URL si
# aggiorna, conservando l'autorita' accumulata.
# ---------------------------------------------------------------------------
PAGINE_DIR = os.path.join(ROOT, "eventi")
REGISTRO_PATH = os.path.join(ROOT, "data", "pagine-evento.json")
SAGRA_KW = ('sagra', 'festa', 'palio', 'fiera')


def ha_pagina(e):
    """True se l'evento merita una pagina dedicata."""
    if (e.get('categoria') or '') == 'Sagra & Festa':
        return True
    return any(w in (e.get('nome') or '').lower() for w in SAGRA_KW)


def slug_evento(e):
    """Slug stabile fra un'edizione e l'altra: togliamo l'anno e il numero di
    edizione dal nome ("40ª Sagra del Guanciotto 2026" -> "sagra-del-guanciotto")
    e aggiungiamo la citta'. Cosi' l'edizione 2027 aggiorna la stessa URL invece
    di crearne una nuova che riparte da zero."""
    nome = re.sub(r'\b(?:19|20)\d{2}\b', ' ', e.get('nome') or '')
    # Numero di edizione, in tutte le grafie che compaiono nel foglio: 1°, 3ª,
    # 3^, 40ª, 6º, 3a. Va tolto o l'edizione successiva creerebbe una URL nuova
    # invece di aggiornare questa, che è tutto il punto dello slug evergreen.
    # \b non funziona dopo ° perché non è un carattere di parola.
    nome = re.sub(r'(?<!\w)\d+\s*[°ºª^]', ' ', nome)
    nome = re.sub(r'(?<!\w)\d+a\b', ' ', nome)
    base = slugify(nome)
    citta = slugify(e.get('citta') or '')
    if citta and citta not in base:
        base = f"{base}-{citta}"
    return base.strip('-')[:80].strip('-') or 'evento'


def pagina_url(e):
    return f"{SITE_URL}/eventi/{slug_evento(e)}.html"


MAX_TITLE = 62  # oltre, Google tronca nello snippet

# Nel foglio il nome porta spesso in coda chi organizza ("… - Pro Loco Ferrere").
# Nel title è spazio sprecato: nessuno cerca la sagra per nome della pro loco, e
# senza sparisce quasi ogni troncamento. Resta per intero nell'H1 e nel corpo.
ORGANIZZATORE_RE = re.compile(
    r'\s*[-–—]\s*(?:Pro\s*Loco|Comune|Comitato|Associazione|Circolo|Gruppo|'
    r'Parrocchia|A\.?S\.?D\.?)\b.*$', re.I)

# Stessa coda, ma catturata: serve a dichiarare organizer nei dati strutturati.
ORGANIZZATORE_NOME_RE = re.compile(
    r'[-–—]\s*((?:Pro\s*Loco|Comune|Comitato|Associazione|Circolo|Gruppo|'
    r'Parrocchia|A\.?S\.?D\.?)\b[^-–—]*)$', re.I)


def organizzatore(nome):
    """Chi organizza, quando il nome nel foglio lo porta in coda. '' altrimenti."""
    m = ORGANIZZATORE_NOME_RE.search((nome or '').strip())
    return re.sub(r'\s+', ' ', m.group(1)).strip(' .') if m else ''


def fascia_eta(testo):
    """typicalAgeRange da 'Età consigliata' quando c'e' un intervallo numerico:
    '3-10 anni' -> '3-10', 'dai 6 anni' -> '6-'. 'Tutte le età' non e' una
    fascia: dichiararla come 0- sarebbe un dato inventato, quindi resta vuota."""
    t = (testo or '').strip()
    if not t:
        return ''
    m = re.search(r'(\d{1,2})\s*(?:-|–|—|a|/)\s*(\d{1,2})', t)
    if m and int(m.group(1)) <= int(m.group(2)):
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r'\b(?:dai|da|oltre i|\+)\s*(\d{1,2})', t, re.I)
    if m:
        return f"{m.group(1)}-"
    return ''


def a_citta(citta):
    """' ad Acqui Terme' ma ' a Novi Ligure': davanti a vocale ci va la d.
    Vale sia per il title sia per la meta description, cioè per le due righe
    che la gente legge davvero: "a Acqui" in pagina dei risultati si nota."""
    if not citta:
        return ""
    return f" ad {citta}" if citta[0].lower() in 'aeiou' else f" a {citta}"


def _titolo(nome, citta):
    """Title che sta nei limiti senza mai perdere la città né finire a metà
    parola. Ordine di sacrificio: prima il suffisso di brand, poi il nome."""
    coda = a_citta(citta)
    for base in (nome, ORGANIZZATORE_RE.sub('', nome).strip(' -–—')):
        for suffisso in (" | DAOP", ""):
            t = f"{base}{coda}{suffisso}"
            if len(t) <= MAX_TITLE:
                return t
    corto = ORGANIZZATORE_RE.sub('', nome).strip(' -–—') or nome
    return f"{trunc(corto, max(MAX_TITLE - len(coda), 20))}{coda}"


def _dal(giorno):
    """'Dal 7' ma 'Dall'8' e 'Dall'11': l'articolo cambia davanti a vocale."""
    return f"Dall'{giorno}" if giorno in (8, 11) else f"Dal {giorno}"


def data_estesa(d):
    return f"{GIORNI[d.weekday()]} {d.day} {MESI_LUNGHI[d.month - 1]} {d.year}"


def periodo_esteso(rec):
    di, df = rec['d_start'], rec['d_end']
    if di == df:
        return data_estesa(di).capitalize()
    if (di.year, di.month) == (df.year, df.month):
        return f"{_dal(di.day)} al {df.day} {MESI_LUNGHI[df.month - 1]} {df.year}"
    return (f"{_dal(di.day)} {MESI_LUNGHI[di.month - 1]} "
            f"al {df.day} {MESI_LUNGHI[df.month - 1]} {df.year}")


# Quello che la gente cerca non e' il nome della festa: e' quello che ci trova
# dentro. In sette giorni le query sui fuochi d'artificio di Novi Ligure hanno
# fatto 283 impressioni e 1 solo clic, da settima posizione: la pagina c'era e
# rispondeva, ma nello snippet si leggevano solo le date, e la parola stava
# sepolta a meta' descrizione scritta "spettacolo pirotecnico". Chi cerca
# "fuochi d'artificio novi ligure 2026" non riconosceva la risposta.
#
# Qui il richiamo lo tiriamo fuori dal testo e lo mettiamo in testa alla meta
# description, che e' la riga che si legge fra i risultati. Non si inventa
# niente: se la parola non e' nella descrizione del foglio, non esce. L'ordine
# della lista e' l'ordine in cui la gente cerca, e ne teniamo al massimo tre:
# oltre, la riga diventa un elenco della spesa e non la legge nessuno.
RICHIAMI = [
    (r'pirotecnic|fuochi', "fuochi d'artificio"),
    (r'luna\s*park', "luna park"),
    (r'giostr', "giostre"),
    (r'gonfiabil', "gonfiabili"),
    (r'trucca\s*-?\s*bimbi|face\s*painting', "truccabimbi"),
    (r'buratt|marionett', "burattini"),
    (r'laborator', "laboratori per bambini"),
    (r'mercatin|bancarell|banchett|hobbist', "mercatino"),
    (r'street\s*food', "street food"),
    (r'stand\s+gastronomic|cucina\s+apert', "stand gastronomico"),
    (r'degustazion', "degustazioni"),
    (r'process', "processione"),
    (r'rievocazion|medioeval|sbandierator', "rievocazione storica"),
    (r'sfilat|carr\w*\s+allegoric', "sfilata"),
    (r'orchestra|liscio', "ballo con orchestra"),
    (r'\bdj\b', "dj set"),
    (r'musica\s+dal\s+vivo|concerto|tribute|cover\s+band', "musica dal vivo"),
    (r'mongolfier', "mongolfiere"),
]
RICHIAMI = [(re.compile(rx, re.I), etichetta) for rx, etichetta in RICHIAMI]

# Una descrizione che promette una cosa che non c'e' costa molto piu' del clic
# che porta: e' la parola di DAOP che ci va di mezzo. Quindi se il testo la nega
# ("quest'anno senza fuochi", "lo spettacolo pirotecnico e' annullato"), il
# richiamo non esce. La negazione si cerca nella proposizione in cui cade la
# parola, non in una finestra di caratteri: "niente gonfiabili, ma ci sono i
# burattini" deve perdere i gonfiabili e tenere i burattini.
NEGAZIONE_RE = re.compile(
    r'\b(?:senza|niente|nessun\w*|non|salt(?:a|ato|ata|ate)|annullat\w*|'
    r'sospes\w*|rinviat\w*)\b', re.I)
STACCHI = '.;:!?,\n'


def _proposizione(testo, pos):
    """Il pezzo di frase in cui cade pos, fra due segni di punteggiatura."""
    inizio = max(testo.rfind(c, 0, pos) for c in STACCHI) + 1
    fini = [i for i in (testo.find(c, pos) for c in STACCHI) if i != -1]
    return testo[inizio:min(fini) if fini else len(testo)]


def richiami(testo, massimo=3):
    """Le attrazioni davvero citate nella descrizione, pronte da leggere."""
    testo = testo or ''
    trovati = []
    for rx, etichetta in RICHIAMI:
        for m in rx.finditer(testo):
            if NEGAZIONE_RE.search(_proposizione(testo, m.start())):
                continue
            trovati.append(etichetta)
            break
        if len(trovati) >= massimo:
            break
    return trovati


def elenco_it(voci):
    """'a, b e c': l'ultima virgola in italiano non si mette."""
    if len(voci) < 2:
        return voci[0] if voci else ''
    return ", ".join(voci[:-1]) + " e " + voci[-1]


def carica_registro():
    if not os.path.exists(REGISTRO_PATH):
        return {}
    try:
        with open(REGISTRO_PATH, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        print(f"[genera_eventi] registro pagine illeggibile ({err}), riparto da vuoto")
        return {}


def completezza(e):
    """Quanto e' completa una riga del foglio. Serve a scegliere fra due righe
    che finiscono sullo stesso slug: capita che lo stesso evento sia inserito
    due volte con dati diversi (Acqui Wine Days: 784 caratteri e fine 09/08 in
    una riga, 991 caratteri e fine 10/08 nell'altra). Prima vinceva l'ultima
    letta, cioe' il caso; ora vince la piu' ricca."""
    return (len((e.get('descr') or '').strip()),
            (e['d_end'] - e['d_start']).days,
            sum(1 for k in ('ora', 'luogo', 'indirizzo', 'loc', 'prezzo', 'eta')
                if (e.get(k) or '').strip()))


def segnala_doppioni(events):
    """Elenca gli eventi inseriti piu' volte nel foglio.

    Criterio: stesso evento (slug, che ignora anno e numero di edizione, cosi'
    "3^ Cena Sotto le Stelle" e "3ª Cena sotto le Stelle" si riconoscono) e
    stessa data di inizio. La data di inizio e' quello che distingue un
    doppione da una ricorrenza: "I giovedi' in biblioteca" compare quattro
    volte ma con quattro date, ed e' corretto cosi'.

    Vale su tutti gli eventi, non solo su quelli con pagina dedicata: il
    doppione si vede nell'agenda a prescindere. Si pulisce solo a mano nel
    foglio, quindi va ricordato a ogni run."""
    g = collections.defaultdict(list)
    for e in events:
        g[(slug_evento(e), e['d_start'])].append(e)
    doppi = {k: v for k, v in g.items() if len(v) > 1}
    if not doppi:
        return
    print(f"[genera_eventi] ATTENZIONE: {len(doppi)} eventi ripetuti nel foglio "
          f"(nell'agenda compaiono doppi, vanno uniti a mano):")
    for (s, d), v in sorted(doppi.items(), key=lambda kv: kv[0][1]):
        print(f"    {len(v)}x  {v[0]['nome'][:44]} — {v[0]['citta']} — dal {d.strftime('%d/%m')}")
        for x in v:
            print(f"          fine {x['df']}  {x['categoria'] or '(senza categoria)':16} "
                  f"{len(x['descr'])} caratteri")


def aggiorna_registro(events):
    """Fonde gli eventi correnti nel registro persistente. Non rimuove nulla."""
    reg = carica_registro()
    oggi = datetime.date.today().isoformat()
    nuovi = 0
    # Un solo evento per slug, il piu' completo, prima di toccare il registro.
    migliori = {}
    for e in events:
        if not ha_pagina(e):
            continue
        s = slug_evento(e)
        if s not in migliori or completezza(e) > completezza(migliori[s]):
            migliori[s] = e
    for s, e in migliori.items():
        rec = reg.get(s)
        if rec is None:
            rec, nuovi = {'first_seen': oggi}, nuovi + 1
        rec.update({k: (v.isoformat() if isinstance(v, datetime.date) else v)
                    for k, v in e.items()})
        # Le colonne editoriali vuote non si salvano: otto stringhe vuote per
        # scheda gonfiano il registro e il diff di ogni notte. Vanno tolte, non
        # solo saltate, se no una cella svuotata nel foglio resterebbe qui per
        # sempre.
        for k in dict(CAMPI_DAOP, **CAMPI_EXTRA):
            if not (rec.get(k) or '').strip():
                rec.pop(k, None)
        rec['slug'] = s
        rec['last_seen'] = oggi
        reg[s] = rec
    # Il registro viene scritto da scrivi_pagine(), dopo aver stabilito quali
    # pagine sono davvero cambiate: serve per registrare la data di modifica.
    # Restituiamo anche gli slug visti in QUESTA run: confrontare last_seen con
    # la data odierna non basta, perche' due run nello stesso giorno non si
    # distinguerebbero.
    return reg, nuovi, set(migliori)


def _guscio():
    """CSS, nav e footer presi da eventi.html a ogni run, con i link resi
    root-relative perche' le pagine evento stanno in /eventi/. Estrarli invece
    di duplicarli tiene le sottopagine allineate quando il sito cambia.

    Il CSS va copiato per intero: daop-system.min.css contiene solo i token
    tipografici, mentre le regole di layout (nav, footer, bottoni, griglie)
    stanno in blocchi <style> inline dentro ogni pagina. Linkare solo il file
    lasciava le pagine evento senza stile."""
    s = open(HTML_PATH, encoding="utf-8").read()
    nav = re.search(r'<!-- NAV -->.*?</div>\s*(?=\n<!--|\n<main)', s, re.S)
    foot = re.search(r'<footer>.*?</footer>', s, re.S)
    css = re.findall(r'<style[^>]*>(.*?)</style>', s, re.S)
    if not nav or not foot:
        raise SystemExit("[genera_eventi] nav o footer non trovati in eventi.html")
    if not css:
        raise SystemExit("[genera_eventi] nessun blocco <style> trovato in eventi.html")

    def rooted(html_frag):
        html_frag = re.sub(r'(href|src)="(?!https?://|/|#|mailto:|tel:)',
                           lambda m: f'{m.group(1)}="/', html_frag)
        return html_frag.replace('class="active"', '')

    # Anche le url() del CSS vanno messe alla radice. In eventi.html la texture
    # della .page-hero e' url('assets/images/...') senza slash: da /eventi/ e da
    # /eventi/comune/ diventa /eventi/assets/... e risponde 404. Finche' nessuna
    # pagina generata usava la barra il difetto restava invisibile.
    css_txt = re.sub(r"url\((['\"]?)(?!https?://|/|data:)",
                     lambda m: f"url({m.group(1)}/", "\n".join(css))
    return css_txt, rooted(nav.group(0)), rooted(foot.group(0))


PAGINA_CSS = """
/* La nav del sito e' position:fixed: senza spazio in cima gli finisce sotto
   il breadcrumb e mezzo H1. Stessi valori con cui .page-hero la compensa
   nelle altre pagine (148px, 120px sotto i 600px). */
.ev-wrap{max-width:820px;margin:0 auto;padding:148px 20px 40px}
@media(max-width:600px){.ev-wrap{padding:120px 18px 32px}}
/* La barra scura in cima e' la .page-hero delle altre pagine del sito: il CSS
   arriva gia' copiato da eventi.html, qui c'e' solo la variante allineata a
   sinistra e con il titolo piu' contenuto, perche' i nomi degli eventi sono
   lunghi ("Apertura stand gastronomico con i Controcorrente") e a 3.6rem
   riempivano tre righe. Senza barra queste erano le uniche pagine del sito a
   partire dal bianco. */
.ev-hero{padding:148px 24px 56px;text-align:left}
.ev-hero .page-hero-inner{max-width:820px}
.ev-hero .ev-crumb{color:rgba(255,255,255,.62);opacity:1;margin:0 0 12px}
.ev-hero .ev-crumb a{color:rgba(255,255,255,.82)}
.ev-hero h1{font-family:'Playfair Display',serif;font-size:clamp(2rem,4vw,2.9rem);
  font-weight:800;color:#fff;line-height:1.12;margin:0 0 12px;letter-spacing:-.02em}
.ev-hero .ev-when{font-size:1.08rem;font-weight:600;color:var(--gold,#c9a227);margin:0}
.ev-hero .ev-scelto{background:rgba(255,255,255,.14);color:#f6d9b4;margin:0 0 12px}
@media(max-width:600px){.ev-hero{padding:120px 20px 44px}}
/* Con la barra sopra, il corpo non deve piu' compensare la nav fissa. */
.ev-wrap--hero{padding-top:44px}
@media(max-width:600px){.ev-wrap--hero{padding-top:32px}}
/* Il breadcrumb e' un <div role="navigation">, non un <nav>: il CSS del sito
   ha nav{position:fixed;top:0} come selettore di elemento, che rendeva fisso
   anche il breadcrumb piazzandolo sopra la barra. position:static come
   ulteriore difesa se un giorno la regola si allargasse. */
.ev-crumb{position:static;font-size:.85rem;opacity:.7;margin:0 0 10px}
.ev-crumb a{color:inherit}
.ev-scelto{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:700;
  letter-spacing:.02em;text-transform:uppercase;color:#a75b15;background:rgba(232,149,74,.16);
  border-radius:100px;padding:5px 12px;margin:0 0 8px}
/* .ev-when vive nella barra scura: il colore vero e' in .ev-hero .ev-when,
   qui resta la misura come ripiego se un giorno finisse fuori dalla barra. */
.ev-when{font-size:1.05rem;font-weight:600;color:var(--daop-navy,#1b3a5c)}
.ev-facts{list-style:none;padding:0;margin:22px 0;display:grid;gap:10px}
.ev-facts li{display:flex;gap:10px;align-items:flex-start;line-height:1.45}
.ev-facts svg{flex:0 0 auto;margin-top:3px;opacity:.65}
.ev-body{margin:26px 0;line-height:1.7}
/* La locandina e' un ritratto 3:4: a tutta larghezza occupava 780x1040px,
   cioe' piu' di uno schermo di scroll prima della descrizione. Sta in colonna,
   non e' la pagina. */
.ev-loc{display:block;width:100%;max-width:420px;height:auto;border-radius:14px;
  margin:22px auto;border:1px solid rgba(45,74,92,.12);box-shadow:0 6px 24px rgba(45,74,92,.10)}
.ev-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:28px 0 8px}
/* Rete di sicurezza: se un .btn restasse senza modificatore non deve mai
   ricadere sul blu di sistema, come e' successo a "Come arrivare". */
.ev-actions .btn{color:#fff}
.ev-back{font-weight:600;color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:3px}
.ev-over{border:1px solid #e5c07b;background:#fdf6e6;border-radius:14px;padding:16px 18px;margin:22px 0}
.ev-over strong{display:block;margin-bottom:4px}
/* Niente regole per il dark mode qui dentro: il sito non ha un tema scuro, il
   body resta crema anche col telefono in dark mode. Quella che stava qui
   dipingeva "Edizione conclusa" di marrone #2e2717 lasciandoci sopra il testo
   navy. Il tema scuro, se arriva, si fa sul body in eventi.html e poi scende. */
/* Il punto di vista DAOP: e' il motivo per cui vale la pena aprire la pagina,
   quindi si vede che e' nostro e non copiato dal volantino. */
.ev-daop{border:1px solid rgba(107,165,168,.45);background:rgba(107,165,168,.09);
  border-radius:16px;padding:20px 22px;margin:28px 0}
.ev-daop>h2{display:flex;align-items:center;gap:8px;font-size:1.1rem;margin:0 0 12px;
  color:var(--navy,#2d4a5c)}
.ev-daop-voce+.ev-daop-voce{margin-top:14px}
.ev-daop-voce h3{font-size:.98rem;margin:0 0 3px;color:var(--navy,#2d4a5c)}
.ev-daop-voce p{margin:0 0 6px;line-height:1.6}
/* Firma editoriale: chi ha controllato e quando. */
.ev-firma{border-top:2px solid rgba(45,74,92,.14);margin:30px 0 0;padding:16px 0 0;
  font-size:.92rem;line-height:1.6}
.ev-firma-t{display:flex;align-items:center;gap:7px;font-weight:700;margin:0 0 6px;
  color:var(--teal,#6ba5a8)}
.ev-firma p{margin:0 0 6px}
/* Da dove arriva la segnalazione: piu' leggero della firma, piu' presente
   della nota legale sotto - e' un credito, non un disclaimer. */
.ev-fonte{font-size:.88rem;opacity:.85}
.ev-firma-nota{opacity:.78;font-size:.86rem}
.ev-firma a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
/* Altri eventi vicini: link in uscita e motivo per restare sul sito.
   padding:0 e' obbligatorio: e' un <section>, e il CSS del sito ha
   section{padding:100px 24px} come selettore di elemento, che qui dentro
   diventava 100px di vuoto e 24px di rientro rispetto al resto della colonna. */
.ev-vicini{margin:34px 0 0;padding:0}
.ev-vicini h2{font-size:1.15rem;margin:0 0 12px}
.ev-vicini ul{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.ev-vicini a{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;
  border:1px solid rgba(45,74,92,.14);border-radius:12px;padding:11px 14px;
  color:inherit;text-decoration:none;transition:border-color .2s,background .2s}
.ev-vicini a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.08)}
.ev-vic-d{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.02em;
  color:var(--teal,#6ba5a8);flex:0 0 auto;min-width:92px}
.ev-vic-n{font-weight:600;flex:1 1 220px}
.ev-vic-c{font-size:.85rem;opacity:.7}
.ev-vic-all{margin:14px 0 0;font-size:.92rem}
.ev-vic-all a{color:var(--navy,#2d4a5c);font-weight:600;text-decoration:underline;text-underline-offset:3px}
/* Striscia Ginetto: stesso componente .info-strip della home eventi (card
   crema, titolo Playfair, link arancio), con la mascotte al posto dell'icona.
   Sta in fondo, dopo "altri eventi vicino a": e' il punto in cui chi legge non
   ha trovato quello che cercava. */
.ev-ginetto{padding:56px 24px}
.ev-ginetto .info-strip{margin-bottom:0;align-items:center}
.ginetto-faccia{width:64px;height:64px;flex-shrink:0;object-fit:contain}
@media(max-width:600px){.ev-ginetto{padding:40px 20px}}
"""


def blocco_ginetto(citta=""):
    """Rimando a Ginetto in fondo alle pagine di evento e di comune.

    Non e' un avviso e non e' un popup: e' la .info-strip della home eventi,
    stesso componente, con la mascotte al posto dell'icona. Il comune nel
    titolo lo sappiamo gia', e una domanda che nomina il posto in cui si trova
    chi legge vale piu' di un invito generico."""
    # a_citta() mette la d eufonica: "vicino ad Acqui Terme", non "a Acqui".
    dove = " vicino " + esc(a_citta(citta)) if citta else " con i bambini"
    return f"""<section class="bg-cream ev-ginetto">
  <div class="section-inner">
    <div class="info-strip">
      <img class="ginetto-faccia" src="/assets/images/ginetto-esplora.webp" alt="Ginetto, la mascotte di DAOP" width="500" height="500" loading="lazy">
      <div>
        <h3>Cerchi altro da fare{dove}?</h3>
        <p>Chiedilo a <strong>Ginetto AI</strong>, l'assistente di DAOP: trova eventi e luoghi per famiglie in base all'et&agrave; dei tuoi figli e a quanto sei disposto a guidare. <a href="https://ginettoapp.it" target="_blank" rel="noopener">Apri Ginetto &rarr;</a></p>
      </div>
    </div>
  </div>
</section>
"""


ORG_ID = f"{SITE_URL}/#organization"
SITE_ID = f"{SITE_URL}/#website"
METODO_URL = f"{SITE_URL}/metodo.html"
ZONE_HREF = "/zone.html"                       # nei link interni delle pagine
ZONE_URL = f"{SITE_URL}{ZONE_HREF}"            # canonical e dati strutturati

PHONE_SVG = ('<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>')

STAR_SVG = ('<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" '
            'aria-hidden="true"><path d="m12 2.6 2.9 5.9 6.5.9-4.7 4.6 1.1 6.4-5.8-3-5.8 3 1.1-6.4L2.6 9.4l6.5-.9z"/></svg>')

CHECK_SVG = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4 12 14.01l-3-3"/></svg>')

# L'ordine e' quello con cui si decide davvero: prima se ci vado, poi se e'
# adatto, poi la logistica.
BLOCCHI_DAOP = (
    ('adatto', 'Adatto davvero ai bambini?'),
    ('eta_consigliata', 'Età consigliata'),
    ('dintorni', 'Cosa fare nei dintorni'),
)


def blocco_daop(e):
    """Il giudizio editoriale: l'unica parte che non sta sul volantino.

    Compare solo per i campi compilati nel foglio. Un titolo senza risposta
    ("Dove parcheggiare" seguito dal vuoto) e' peggio che non averlo."""
    voci = [(t, (e.get(k) or '').strip()) for k, t in BLOCCHI_DAOP
            # "Età consigliata" e' il giudizio nostro: se ripete la colonna Età,
            # che sta gia' nella scheda fra i dati, e' una riga in piu' che dice
            # la stessa cosa.
            if not (k == 'eta_consigliata'
                    and _key(e.get(k)) == _key(e.get('eta')))]
    voci = [(t, v) for t, v in voci if v]
    if not voci:
        return ''
    corpo = "".join(
        f'<div class="ev-daop-voce"><h3>{esc(t)}</h3>'
        + "".join(f"<p>{esc(p)}</p>" for p in re.split(r'\n{2,}', v) if p.strip())
        + '</div>' for t, v in voci)
    return ('<section class="ev-daop" aria-labelledby="daop-consiglio">'
            f'<h2 id="daop-consiglio">{CHECK_SVG} Il punto di vista DAOP</h2>'
            f'{corpo}</section>')


def firma_daop(rec, oggi):
    """Firma editoriale + data dell'ultimo controllo + avvertenza.

    La data e' last_seen, cioe' l'ultima volta che la scheda e' stata
    riscontrata sul foglio DAOP: e' un controllo vero, non la data della run."""
    iso = rec.get('last_seen') or rec.get('updated') or rec.get('first_seen') or oggi.isoformat()
    try:
        d = datetime.date.fromisoformat(iso)
        leggibile = f"{d.day} {MESI_LUNGHI[d.month - 1]} {d.year}"
    except ValueError:
        d, leggibile = oggi, iso
    ogg = urllib.parse.quote(f"Correzione scheda: {(rec.get('nome') or '').strip()}")
    # Da dove arriva la segnalazione. Sta QUI, dentro la firma, e non fra i dati
    # in cima: non e' un'informazione che serve a decidere se andarci, e' la
    # trasparenza su come la scheda e' nata - lo stesso posto in cui diciamo chi
    # l'ha controllata e quando.
    f = fonte_provincia(rec.get('prov'))
    credito = ''
    if f:
        chi = (f"la nostra pagina per la provincia di {esc(f['provincia'])}"
               if f['nostra'] else
               f"la pagina che segue la provincia di {esc(f['provincia'])}, "
               "con cui collaboriamo")
        credito = (f'<p class="ev-fonte">Segnalato da <a href="{f["url"]}" '
                   f'target="_blank" rel="noopener">@{esc(f["ig"])}</a>, {chi}. '
                   f'<a href="{ZONE_HREF}">Le pagine della tua zona</a></p>')
    return (
        '<aside class="ev-firma">'
        f'<p class="ev-firma-t">{CHECK_SVG} Scheda verificata da DAOP</p>'
        '<p>Selezionata e verificata da <strong>DAOP – Dove Andiamo Oggi Papi</strong>, '
        'l\'associazione delle famiglie di Alessandria e Asti. Ultimo controllo: '
        f'<time datetime="{d.isoformat()}">{leggibile}</time>.</p>'
        f'{credito}'
        '<p class="ev-firma-nota">Le informazioni possono cambiare. Prima di partire, '
        'controlla eventuali aggiornamenti dell\'organizzatore. '
        '<a href="/metodo.html">Come verifichiamo gli eventi</a> · '
        f'<a href="mailto:info@daop.it?subject={ogg}">Segnala una correzione</a></p>'
        '</aside>')


def blocco_vicini(rec, events, oggi, limite=6, hub=None):
    """Altri eventi vicini: stessa citta' prima, poi stessa provincia.

    Serve a chi legge (l'evento e' finito, o piove: cosa c'e' invece?) e serve
    alle pagine, che senza questo sono foglie senza link in uscita."""
    citta = _key(rec.get('citta'))
    prov = (rec.get('prov') or '').upper()
    mio = rec['slug']
    cand = []
    for e in events:
        if slug_evento(e) == mio:
            continue
        stessa = _key(e.get('citta')) == citta
        if not stessa and (e.get('prov') or '').upper() != prov:
            continue
        cand.append((0 if stessa else 1, max(e['d_start'], oggi),
                     e['d_start'], (e.get('nome') or ''), e))
    if not cand:
        return ''
    cand.sort(key=lambda t: t[:4])
    righe = []
    for _, _, _, _, e in cand[:limite]:
        href = (f"/eventi/{slug_evento(e)}.html" if ha_pagina(e)
                else f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html")
        # Una mostra iniziata a gennaio e ancora aperta non va etichettata
        # "giovedì 1 gen": per chi legge oggi e' semplicemente in corso.
        if e['d_start'] < oggi:
            quando = "in corso"
        elif e['d_start'] == oggi:
            quando = "oggi"
        elif (e['d_start'] - oggi).days == 1:
            quando = "domani"
        else:
            quando = (data_estesa(e['d_start']).split(' ', 1)[0] + ' '
                      + f"{e['d_start'].day} {MESI[e['d_start'].month - 1]}")
        righe.append(
            f'<li><a href="{href}"><span class="ev-vic-d">{esc(quando)}</span>'
            f'<span class="ev-vic-n">{esc(trunc(e.get("nome") or "", 70))}</span>'
            f'<span class="ev-vic-c">{esc(e.get("citta") or "")}</span></a></li>')
    titolo = f"Altri eventi vicino a {rec.get('citta')}" if rec.get('citta') else "Altri eventi vicini"
    # Se il comune ha una pagina sua, il primo link va li': e' piu' vicino a
    # quello che sta cercando chi e' arrivato qui da "festa <comune>".
    mio_hub = (hub or {}).get(citta)
    tutti = (f'<a href="/eventi/comune/{mio_hub["slug"]}.html">Tutti gli eventi'
             f'{a_citta(mio_hub["nome"])}</a> · ' if mio_hub else '')
    return ('<section class="ev-vicini" aria-labelledby="ev-vicini-t">'
            f'<h2 id="ev-vicini-t">{esc(titolo)}</h2>'
            f'<ul>{"".join(righe)}</ul>'
            f'<p class="ev-vic-all">{tutti}'
            '<a href="/eventi.html">Vedi tutta l\'agenda DAOP</a></p>'
            '</section>')


def render_pagina(rec, css, nav, foot, oggi, orfano=False, vicini=(), hub=None):
    """HTML completo di una pagina evento.

    orfano: l'evento e' sparito dal foglio pur non essendo ancora passato.
    Vuol dire che e' stato annullato, oppure rinominato - e in quel caso
    esiste gia' un'altra pagina con lo stesso contenuto. In entrambi i casi
    non deve stare in indice."""
    e = dict(rec)
    e['d_start'] = datetime.date.fromisoformat(rec['d_start'])
    e['d_end'] = datetime.date.fromisoformat(rec['d_end'])
    concluso = e['d_end'] < oggi
    url = f"{SITE_URL}/eventi/{rec['slug']}.html"
    nome = (e.get('nome') or '').strip()
    citta = (e.get('citta') or '').strip()
    anno = e['d_start'].year

    # Il title si costruisce dal nome verso l'esterno: la città non va mai
    # troncata (è metà della query) e il suffisso " | DAOP" si sacrifica prima
    # del contenuto. Si accorcia solo il nome, e solo se serve davvero.
    titolo_seo = _titolo(f"{nome} {anno}" if str(anno) not in nome else nome, citta)

    descr_txt = (e.get('descr') or '').strip()
    # La riga che si legge fra i risultati: prima quando e dove (sono le parole
    # della query, "2026" compreso), poi cosa ci trovi. Prima diceva solo le
    # date e ripeteva l'attacco della descrizione, che quasi sempre le ripete
    # un'altra volta ancora.
    testa = periodo_esteso(e) + a_citta(citta)
    attrazioni = richiami(descr_txt)
    if attrazioni:
        testa += f": {elenco_it(attrazioni)}"
    meta_d = trunc(f"{testa}. {descr_txt}" if descr_txt
                   else f"{nome}{a_citta(citta)}: {periodo_esteso(e)}.", 152)

    facts = []
    if e.get('ora'):
        facts.append(f'<li>{CLOCK_SVG}<span><strong>Orario:</strong> {esc(e["ora"])}</span></li>')
    luogo = " · ".join(x for x in [(e.get('luogo') or '').strip(),
                                   (e.get('indirizzo') or '').strip()] if x)
    if luogo:
        facts.append(f'<li>{PIN_SVG}<span><strong>Dove:</strong> {esc(luogo)}</span></li>')
    if e.get('prezzo'):
        facts.append(f'<li>{CAL_SVG}<span><strong>Ingresso:</strong> {esc(e["prezzo"])}</span></li>')
    if e.get('eta'):
        facts.append(f'<li>{USER_SVG}<span><strong>Età:</strong> {esc(e["eta"])}</span></li>')

    if e.get('prenotazione'):
        facts.append(f'<li>{CHECK_SVG}<span><strong>Prenotazione:</strong> '
                     f'{esc(e["prenotazione"])}</span></li>')
    # I recapiti dell'organizzatore sono la cosa piu' utile che possiamo dare a
    # chi deve decidere oggi: nessuna risposta di un assistente te li da'.
    if contatti_html(e.get('contatto')):
        facts.append(f'<li>{PHONE_SVG}<span><strong>Contatti:</strong> '
                     f'{contatti_html(e["contatto"])}</span></li>')

    loc = loc_path(e.get('loc'))
    img = (f'<img class="ev-loc" src="{esc(loc)}" alt="Locandina di {esc(nome)}" '
           f'loading="lazy" width="900" height="1200">') if loc else ''

    if concluso:
        avviso = ('<div class="ev-over"><strong>Edizione conclusa</strong>'
                  f'Questa edizione si è svolta {periodo_esteso(e).lower()}. '
                  'Se la manifestazione torna, aggiorniamo questa pagina con le nuove date. '
                  'Intanto trovi tutto quello che c\'è in programma nell\'<a href="/eventi.html">agenda DAOP</a>.</div>')
        azioni = '<div class="ev-actions"><a class="btn btn-navy" href="/eventi.html">Vedi gli eventi di oggi</a></div>'
    else:
        avviso = ''
        # .btn da sola dà solo la forma: senza modificatore l'ancora resta un
        # link blu di sistema. I modificatori che il CSS del sito definisce
        # davvero sono btn-primary, btn-navy e btn-teal.
        bottoni = [f'<a class="btn btn-navy" href="{esc(gcal_url(e))}" target="_blank" rel="noopener">Aggiungi al calendario</a>']
        if maps_url(e):
            bottoni.append(f'<a class="btn btn-teal" href="{esc(maps_url(e))}" target="_blank" rel="noopener">Come arrivare</a>')
        bottoni.append('<a class="ev-back" href="/eventi.html">Torna all\'agenda</a>')
        azioni = '<div class="ev-actions">' + "".join(bottoni) + '</div>'

    ev_obj = event_jsonld(e, url)
    ev_obj["@id"] = f"{url}#event"
    if concluso:
        ev_obj["eventStatus"] = "https://schema.org/EventScheduled"
    # La scheda dichiara anche CHI l'ha controllata e QUANDO: e' la traduzione in
    # dati strutturati della firma visibile. lastReviewed/reviewedBy esistono
    # apposta, e chi cita la pagina trova il nome della fonte accanto al dato.
    controllo = rec.get('last_seen') or rec.get('updated') or rec.get('first_seen')
    webpage = {
        "@type": "WebPage",
        "@id": url,
        "url": url,
        "name": titolo_seo,
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
        "about": {"@id": f"{url}#event"},
        "publisher": {"@id": ORG_ID},
        "reviewedBy": {"@id": ORG_ID},
    }
    if rec.get('first_seen'):
        webpage["datePublished"] = rec['first_seen']
    if rec.get('updated'):
        webpage["dateModified"] = rec['updated']
    if controllo:
        webpage["lastReviewed"] = controllo
    organizzazione = {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "DAOP – Dove Andiamo Oggi Papi",
        "alternateName": "DAOP",
        "url": SITE_URL,
        "logo": f"{SITE_URL}/assets/images/logodaop.png",
        "areaServed": [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE] + ["Piemonte"],
        "description": ("Associazione delle famiglie di Alessandria e Asti. Seleziona e "
                        "verifica gli eventi per famiglie del territorio."),
    }
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": nome, "item": url},
        ],
    }
    jsonld = json.dumps({"@context": "https://schema.org",
                         "@graph": [ev_obj, webpage, organizzazione, breadcrumb]},
                        ensure_ascii=False, indent=2)

    corpo = "".join(f"<p>{esc(p)}</p>" for p in re.split(r'\n{2,}', descr_txt) if p.strip())
    consiglio = blocco_daop(e)
    # "Consigliato DAOP" nel foglio e' gia' un giudizio, dato riga per riga:
    # tenerlo dentro il database e non mostrarlo era buttarlo via.
    consigliato_badge = (f'<p class="ev-scelto">{STAR_SVG} Consigliato da DAOP</p>'
                         if si(e.get('consigliato')) else '')
    firma = firma_daop(rec, oggi)
    altri = blocco_vicini(rec, vicini, oggi, hub=hub) if vicini else ''

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo_seo)}</title>
<meta name="description" content="{esc(meta_d)}">
<meta name="robots" content="{'noindex, follow' if orfano else 'index, follow'}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo_seo)}">
<meta property="og:description" content="{esc(meta_d)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{esc(loc_url(e.get('loc')) or DEFAULT_IMG)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(trunc(titolo_seo, 60))}">
<meta name="twitter:description" content="{esc(trunc(meta_d, 120))}">
<meta name="twitter:image" content="{esc(loc_url(e.get('loc')) or DEFAULT_IMG)}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>{esc(trunc(nome, 60))}</span>
    </div>
    {consigliato_badge}<h1>{esc(nome)}</h1>
    <p class="ev-when">{esc(periodo_esteso(e))}{' · ' + esc(citta) if citta else ''}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  {avviso}
  <ul class="ev-facts">
    {"".join(facts)}
  </ul>
  {img}
  <div class="ev-body">
    {corpo}
  </div>
  {consiglio}
  {azioni}
  {firma}
  {altri}
</article>
{blocco_ginetto(citta)}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def scrivi_pagine(events, hub=None):
    """Genera/aggiorna le pagine evento.

    Restituisce {slug: data_ultima_modifica} per la sitemap. La data e' quella
    in cui la pagina e' cambiata davvero, non quella della run: dichiarare 35
    pagine "modificate oggi" a ogni giro e' falso, e Google smette di dare peso
    a <lastmod> quando lo trova inaffidabile."""
    reg, nuovi, visti = aggiorna_registro(events)
    if not reg:
        print("[genera_eventi] nessuna pagina evento da generare")
        return {}
    os.makedirs(PAGINE_DIR, exist_ok=True)
    css, nav, foot = _guscio()
    oggi = datetime.date.today()
    conclusi = cambiate = 0
    orfane = []
    for slug, rec in reg.items():
        path = os.path.join(PAGINE_DIR, f"{slug}.html")
        # Un evento ancora futuro che non compare piu' nel foglio e' stato
        # annullato o rinominato. Se rinominato, la pagina nuova esiste gia' e
        # questa e' un doppione: fuori dall'indice e fuori dalla sitemap.
        orfano = slug not in visti and \
            datetime.date.fromisoformat(rec['d_end']) >= oggi
        nuovo = render_pagina(rec, css, nav, foot, oggi, orfano, vicini=events, hub=hub)
        if orfano:
            orfane.append(slug)
        if datetime.date.fromisoformat(rec['d_end']) < oggi:
            conclusi += 1
        # riscriviamo solo se cambia: evita commit rumorosi ogni notte
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            rec.setdefault('updated', rec.get('first_seen', oggi.isoformat()))
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        rec['updated'] = oggi.isoformat()
        cambiate += 1
    with open(REGISTRO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_eventi] pagine evento: {len(reg)} totali "
          f"({nuovi} nuove, {cambiate} riscritte, {conclusi} concluse)")
    # Il valore aggiunto e' l'unica cosa che un assistente non trova altrove:
    # se e' a zero la pagina resta un doppione del volantino, e va detto.
    con_giudizio = sum(1 for r in reg.values()
                       if any((r.get(k) or '').strip() for k in CAMPI_DAOP))
    print(f"[genera_eventi] schede con giudizio DAOP: {con_giudizio}/{len(reg)}")
    # Distinguiamo i due casi: la colonna non c'e' (va aggiunta) oppure c'e' ed
    # e' vuota (va compilata). Dire "aggiungi Età consigliata" quando nel foglio
    # c'e' gia' fa perdere tempo a chi legge.
    vuote = [nomi[0] for campo, nomi in CAMPI_DAOP.items()
             if campo in COLONNE_VISTE
             and not any((r.get(campo) or '').strip() for r in reg.values())]
    if vuote:
        print("[genera_eventi]   colonne presenti ma mai compilate: "
              + ", ".join(f'"{n}"' for n in vuote))
    if orfane:
        print(f"[genera_eventi] ATTENZIONE: {len(orfane)} pagine di eventi futuri "
              f"spariti dal foglio (annullati o rinominati), messe in noindex "
              f"e tolte dalla sitemap: {', '.join(sorted(orfane))}")
    return {s: r['updated'] for s, r in sorted(reg.items()) if s not in orfane}


# ---------------------------------------------------------------------------
# PAGINA METODO
#
# Perche': un motore o un assistente puo' capire COSA pubblica DAOP dai dati
# strutturati, ma non CHI e' DAOP ne' perche' dovrebbe fidarsi. Questa pagina
# risponde a quello, ed e' il bersaglio del link "Scheda verificata da DAOP"
# che sta su ogni scheda evento.
#
# Viene rigenerata a ogni run come le pagine evento: cosi' i numeri sono veri
# (quante schede, quanti comuni, ultimo aggiornamento) invece di essere una
# frase scritta una volta e diventata falsa il mese dopo.
# ---------------------------------------------------------------------------
METODO_PATH = os.path.join(ROOT, "metodo.html")

METODO_CSS = """
.met-num{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:26px 0}
.met-num div{border:1px solid rgba(45,74,92,.14);border-radius:14px;padding:14px 16px}
.met-num b{display:block;font-size:1.6rem;line-height:1.1;color:var(--teal,#6ba5a8)}
.met-num span{font-size:.88rem;opacity:.78}
.ev-wrap h2{margin:34px 0 10px;font-size:1.3rem}
.ev-wrap h3{margin:20px 0 4px;font-size:1.02rem;color:var(--navy,#2d4a5c)}
/* Il reset del sito azzera i margini dei <p>: senza questo i paragrafi della
   pagina si toccano e sembrano un muro di testo. */
.ev-wrap p{margin:0 0 12px;line-height:1.7}
.ev-wrap li{line-height:1.7}
.ev-wrap p a,.ev-wrap li a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
.met-passi{padding-left:20px;margin:10px 0;display:grid;gap:8px}
.met-passi>li{padding-left:4px}
.met-lim{border:1px solid rgba(45,74,92,.16);border-radius:14px;padding:16px 18px;margin:18px 0}
.met-lim ul{margin:8px 0 0 18px;display:grid;gap:6px}
.met-cta{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
"""

METODO_FAQ = [
    ("Chi inserisce gli eventi su DAOP?",
     "Le schede le compilano a mano Patrick Orlando per la provincia di Alessandria e "
     "Alessandra Zaccone per la provincia di Asti, soci fondatori di DAOP. DAOP non "
     "aggrega in automatico da altri siti: ogni scheda passa da una persona prima di "
     "essere pubblicata."),
    ("Da dove arrivano gli eventi?",
     "Da tre strade: le locandine e i canali ufficiali di comuni, pro loco, biblioteche e "
     "associazioni del territorio; le segnalazioni delle famiglie della community DAOP; "
     "e gli organizzatori che ci scrivono direttamente a info@daop.it."),
    ("Come viene verificata una scheda?",
     "I dati vengono dalla comunicazione ufficiale di chi organizza: locandina, pagina o "
     "avviso del comune, della pro loco o dell'associazione. Prima di pubblicare "
     "controlliamo che data, luogo, orario e prezzo ci siano e siano coerenti con quella "
     "fonte. Se un dato non è confermato non lo inventiamo: lo scriviamo come da "
     "verificare. Ogni scheda riporta la data dell'ultimo controllo."),
    ("Ogni quanto vengono aggiornati gli eventi?",
     "L'agenda si rigenera automaticamente ogni notte: gli eventi passati escono, quelli "
     "nuovi entrano e le schede modificate vengono riscritte. La data dell'ultimo "
     "controllo sulla singola scheda è quella dell'ultima volta che l'abbiamo riscontrata, "
     "non quella dell'aggiornamento automatico."),
    ("Che zona copre DAOP?",
     f"Le province di {province_in_elenco(PROVINCE_PUBBLICATE)}, in Piemonte. Fuori da lì "
     "non pubblichiamo: preferiamo coprire bene un territorio che male mezzo Nord Italia."),
    ("Come segnalo un errore o propongo un evento?",
     "Scrivendo a info@daop.it, oppure dai profili social DAOP di Alessandria e Asti. "
     "Le correzioni su un evento già pubblicato hanno la precedenza su tutto il resto."),
]


def scrivi_metodo(events):
    """Genera /metodo.html: chi è DAOP, come verifica, ogni quanto aggiorna."""
    reg = carica_registro()
    oggi = datetime.date.today()
    comuni = len({_key(e.get('citta')) for e in events if (e.get('citta') or '').strip()})
    schede = len(reg)
    # Province ricavate dagli eventi VERI in agenda, non da una costante scritta a
    # mano: il contatore diceva "2 province" ed era rimasto indietro rispetto al
    # filtro dei dati. Cosi' se una provincia resta senza eventi non viene contata.
    prov_agenda = {e.get('prov') for e in events if e.get('prov')}
    n_province = len(prov_agenda)
    nomi_province = province_in_elenco(prov_agenda) or "—"
    url = METODO_URL
    titolo = "Come verifichiamo gli eventi | DAOP"
    descr = ("Chi inserisce gli eventi su DAOP, da dove arrivano, come li verifichiamo e "
             "ogni quanto aggiorniamo le schede per le famiglie di "
             f"{province_in_elenco(PROVINCE_PUBBLICATE)}.")

    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagina metodo saltata: {err}")
        return

    faq = "".join(
        f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in METODO_FAQ)

    grafo = [
        {"@type": "AboutPage", "@id": url, "url": url, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID},
         "dateModified": oggi.isoformat()},
        {"@type": "Organization", "@id": ORG_ID,
         "name": "DAOP – Dove Andiamo Oggi Papi", "alternateName": "DAOP", "url": SITE_URL,
         "logo": f"{SITE_URL}/assets/images/logodaop.png", "foundingDate": "2023",
         "description": ("Associazione delle famiglie di Alessandria e Asti. Seleziona e "
                         "verifica a mano gli eventi per famiglie del territorio."),
         "areaServed": [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE] + ["Piemonte"],
         "founder": {"@type": "Person", "name": "Patrick Orlando"},
         "member": [{"@type": "Person", "name": "Patrick Orlando"},
                    {"@type": "Person", "name": "Alessandra Zaccone"}],
         "email": "info@daop.it",
         "sameAs": ["https://www.instagram.com/daop_alessandria/",
                    "https://www.instagram.com/daop_asti/",
                    "https://www.facebook.com/daopalessandria/",
                    "https://www.facebook.com/daopasti",
                    "https://www.youtube.com/@DOVEANDIAMOOGGIPAPI"]},
        {"@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in METODO_FAQ]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Come verifichiamo gli eventi",
             "item": url}]},
    ]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)

    html_out = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{METODO_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Come verifichiamo gli eventi</span>
    </div>
    <h1>Come DAOP sceglie e verifica gli eventi</h1>
    <p class="ev-when">Il metodo dietro l'agenda di {nomi_province}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">

  <p>DAOP non è un aggregatore automatico. Ogni evento che leggi sul sito è stato scelto
  e inserito da una persona che vive in questo territorio, con data, luogo, orario,
  prezzo e fascia d'età controllati prima della pubblicazione. Questa pagina spiega chi
  lo fa, come, e ogni quanto.</p>

  <div class="met-num">
    <div><b>{len(events)}</b><span>eventi in agenda adesso</span></div>
    <div><b>{schede}</b><span>schede evento dedicate</span></div>
    <div><b>{comuni}</b><span>comuni coperti</span></div>
    <div><b>{n_province}</b><span>province: {nomi_province}</span></div>
  </div>

  <h2>Chi inserisce gli eventi</h2>
  <p><strong>Patrick Orlando</strong> — fondatore e presidente di DAOP, papà e ingegnere.
  Ha fondato DAOP nel 2023, ha costruito <a href="/ginetto.html">Ginetto AI</a> e
  <a href="/piattosano.html">Il Piatto Sano</a> e ha scritto i
  <a href="/libri.html">libri per famiglie</a> della collana. Cura la provincia di
  Alessandria.</p>
  <p><strong>Alessandra Zaccone</strong> — socia fondatrice e curatrice per la provincia
  di Asti. Seleziona e verifica le proposte della community, aggiorna le pagine DAOP Asti
  e tiene il dialogo con le famiglie del territorio.</p>
  <p>Sono due persone, non una redazione: è il motivo per cui copriamo bene due province
  invece che male mezza regione.</p>

  <h2>Come nasce una scheda</h2>
  <ol class="met-passi">
    <li><strong>Raccolta.</strong> Locandine e canali ufficiali di comuni, pro loco,
    biblioteche e associazioni; segnalazioni delle famiglie della community;
    organizzatori che ci scrivono direttamente.</li>
    <li><strong>Inserimento.</strong> Ogni evento entra nel database DAOP con nome, date,
    orario, luogo e indirizzo, prezzo, fascia d'età e descrizione scritta da noi. Niente
    aggregazione automatica da altri siti: la scheda passa da una persona prima di essere
    pubblicata.</li>
    <li><strong>Controllo.</strong> Data, luogo, orario e prezzo li prendiamo dalla
    comunicazione ufficiale di chi organizza e controlliamo che siano completi e coerenti.
    Quello che non è confermato non viene inventato: resta scritto come
    <em>da verificare</em>.</li>
    <li><strong>Pubblicazione.</strong> L'evento entra nell'agenda e, se è una sagra o una
    festa, riceve una scheda con URL dedicata che resta online anche dopo, così l'anno
    dopo ritrovi la stessa pagina aggiornata.</li>
    <li><strong>Manutenzione.</strong> Gli eventi conclusi escono dall'agenda, le schede
    modificate vengono riscritte e ognuna porta in fondo la data dell'ultimo controllo.</li>
  </ol>

  <h2>Ogni quanto aggiorniamo</h2>
  <p>L'agenda si rigenera <strong>ogni notte</strong>. La data che leggi in fondo a ogni
  scheda ("Ultimo controllo") non è la data della rigenerazione automatica: è l'ultima
  volta che quella scheda è stata riscontrata sui dati DAOP.</p>

  <div class="met-lim">
    <strong>Cosa DAOP non è</strong>
    <ul>
      <li>Non siamo l'organizzatore degli eventi: li raccogliamo e li segnaliamo. Chi
      organizza è indicato nella scheda quando lo conosciamo.</li>
      <li>Non vendiamo biglietti e non gestiamo prenotazioni: per quelle serve
      l'organizzatore.</li>
      <li>Un programma può cambiare o saltare all'ultimo, soprattutto per il meteo. Prima
      di partire, un controllo ai canali dell'organizzatore vale sempre la pena.</li>
    </ul>
  </div>

  <h2>Segnalare un errore o proporre un evento</h2>
  <p>Se trovi un dato sbagliato, scrivici: le correzioni su un evento già pubblicato
  hanno la precedenza su tutto il resto. Se organizzi qualcosa per famiglie in provincia
  di Alessandria o Asti, mandaci locandina, date e contatti.</p>
  <div class="met-cta">
    <a class="btn btn-navy" href="mailto:info@daop.it?subject=Correzione%20su%20un%20evento%20DAOP">Segnala una correzione</a>
    <a class="btn btn-teal" href="mailto:info@daop.it?subject=Proposta%20evento%20per%20DAOP">Proponi un evento</a>
  </div>

  <h2>Domande frequenti</h2>
  {faq}

  <h2>Dove trovi DAOP</h2>
  <p><a href="{ZONE_HREF}">Le pagine della tua zona</a>, una per provincia ·
  <a href="/eventi.html">L'agenda eventi</a> di {nomi_province} ·
  <a href="/ginetto.html">Ginetto AI</a>, l'assistente che risponde alle famiglie ·
  <a href="/index.html#chi-siamo">Chi siamo</a> ·
  <a href="/media.html">Rassegna stampa</a></p>

  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""
    if os.path.exists(METODO_PATH) and \
            open(METODO_PATH, encoding='utf-8').read() == html_out:
        print("[genera_eventi] metodo.html invariato")
        return
    with open(METODO_PATH, 'w', encoding='utf-8') as fh:
        fh.write(html_out)
    print(f"[genera_eventi] metodo.html aggiornato ({schede} schede, {comuni} comuni)")


# ---------------------------------------------------------------------------
# PAGINA ZONE
#
# Perche': il credito in fondo a ogni scheda dice DA DOVE arriva quell'evento,
# ma non spiega il modello - che DAOP e' una pagina per provincia, e che una di
# quelle pagine non e' nostra. Trenta link sparsi non lo raccontano; una pagina
# sola si'. Serve anche a chi arriva da fuori zona e vuole sapere se lo copriamo.
#
# Rigenerata a ogni run come le altre: i conteggi per provincia sono veri, e una
# provincia senza eventi in agenda lo dice invece di fingere copertura.
# ---------------------------------------------------------------------------
ZONE_PATH = os.path.join(ROOT, "zone.html")

ZONE_CSS = """
.zon-card{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:18px 20px;margin:16px 0}
.zon-card h2{margin:0 0 2px;font-size:1.25rem}
.zon-n{font-size:.88rem;opacity:.75;margin:0 0 10px}
.zon-link{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.zon-link a{display:inline-block;border:1px solid rgba(45,74,92,.2);border-radius:100px;
  padding:7px 15px;font-size:.9rem;font-weight:600;text-decoration:none;
  color:var(--navy,#2d4a5c)}
.zon-link a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.09)}
.zon-part{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.03em;
  text-transform:uppercase;color:#a75b15;background:rgba(232,149,74,.16);
  border-radius:100px;padding:4px 11px;margin:0 0 8px}
"""


def scrivi_zone(events, hub=None):
    """Genera /zone.html: una provincia, una pagina, e chi la segue."""
    oggi = datetime.date.today()
    per_prov = collections.Counter((e.get('prov') or '').upper() for e in events)
    titolo = "Le pagine della tua zona | DAOP"
    descr = ("Le pagine DAOP provincia per provincia: chi segue "
             f"{province_in_elenco(PROVINCE_PUBBLICATE)} e da dove arrivano gli eventi "
             "per famiglie che pubblichiamo.")

    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagina zone saltata: {err}")
        return

    schede = []
    for sigla in PROVINCE_PUBBLICATE:
        f = fonte_provincia(sigla)
        if not f:
            continue
        n = per_prov.get(sigla, 0)
        # Il conteggio e' quello vero di adesso. Una provincia a zero non viene
        # nascosta: "nessun evento in questo momento" e' un'informazione, una
        # provincia che sparisce dall'elenco sembra un errore del sito.
        quanti = (f"{n} eventi in agenda in questo momento" if n > 1 else
                  "1 evento in agenda in questo momento" if n == 1 else
                  "nessun evento in agenda in questo momento")
        if f['nostra']:
            badge = ''
            testo = (f"La pagina DAOP della provincia di {esc(f['provincia'])}. "
                     f"Gli eventi che trovi qui sul sito nascono da lì: li seleziona e "
                     f"li verifica <strong>{esc(f['curatore'])}</strong>, che vive in questo "
                     f"territorio.")
        else:
            badge = '<span class="zon-part">In collaborazione</span>'
            # Il nome proprio al posto del solo handle: e' la differenza fra
            # "arriva da una pagina" e "c'e' una persona che lo fa".
            chi = (f"<strong>{esc(f['curatore'])}</strong>, con la sua pagina "
                   f"@{esc(f['ig'])}" if f.get('curatore') else
                   f"<strong>@{esc(f['ig'])}</strong>")
            testo = (f"La provincia di {esc(f['provincia'])} la segue {chi} — "
                     "una pagina che non è nostra. Gli eventi di questa zona "
                     "arrivano dal suo lavoro: noi li ospitiamo nell'agenda e "
                     "sull'app, e li accreditiamo su ogni scheda. Se cerchi la "
                     "fonte originale, è quella.")
        link = [f'<a href="{f["url"]}" target="_blank" rel="noopener">Instagram @{esc(f["ig"])}</a>']
        if f.get('fb'):
            link.append(f'<a href="{f["fb"]}" target="_blank" rel="noopener">Facebook</a>')
        # Link all'agenda intera, non a un'ancora per provincia: il filtro di
        # eventi.html e' una <select> in JS, non ci sono ancore per provincia e
        # un "#prov-al" inventato qui atterrerebbe in cima alla pagina.
        link.append('<a href="/eventi.html">Vedi l\'agenda</a>')
        # I comuni della provincia che hanno una pagina loro. E' qui che
        # restano attaccati al resto del sito: una pagina raggiungibile solo
        # dalla sitemap e' una pagina che Google tratta come tale.
        for d in sorted((hub or {}).values(), key=lambda x: x['nome']):
            if d['prov'] == sigla:
                link.append(f'<a href="/eventi/comune/{d["slug"]}.html">'
                            f'Eventi{a_citta(d["nome"])}</a>')
        schede.append(
            f'<section class="zon-card">{badge}'
            f'<h2>{esc(f["provincia"])}</h2>'
            f'<p class="zon-n">{quanti}</p>'
            f'<p>{testo}</p>'
            f'<div class="zon-link">{"".join(link)}</div>'
            '</section>')

    grafo = [
        {"@type": "WebPage", "@id": ZONE_URL, "url": ZONE_URL, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID},
         "dateModified": oggi.isoformat()},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Le pagine della tua zona",
             "item": ZONE_URL}]},
    ]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)

    html_out = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ZONE_URL}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{ZONE_URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{METODO_CSS}{ZONE_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Le pagine della tua zona</span>
    </div>
    <h1>Le pagine della tua zona</h1>
    <p class="ev-when">Una provincia, una pagina, una persona che la segue</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">

  <p>DAOP non è un calendario unico calato dall'alto: è una pagina per provincia, tenuta
  da chi in quella provincia ci vive. Il sito e l'app le rimettono insieme in un'agenda
  sola, ma ogni evento continua ad arrivare da una pagina precisa — ed è scritto in fondo
  a ogni scheda.</p>

  {"".join(schede)}

  <h2>Perché lo scriviamo</h2>
  <p>Perché una provincia non è coperta allo stesso modo delle altre, e nasconderlo
  sarebbe la cosa sbagliata. Dove c'è un curatore DAOP, gli eventi li scegliamo noi. Dove
  c'è una collaborazione, il lavoro è di qualcun altro e il nome giusto da leggere è il
  loro. In entrambi i casi chi organizza l'evento resta l'organizzatore: noi lo
  segnaliamo, non lo produciamo.</p>

  <h2>Vuoi che arriviamo nella tua provincia?</h2>
  <p>Se segui già gli eventi per famiglie della tua zona — una pagina, un gruppo, un
  blog — il modello è questo: tu continui a fare il tuo lavoro sulla tua pagina, noi lo
  portiamo dentro l'agenda e ti accreditiamo. Scrivici.</p>
  <div class="met-cta">
    <a class="btn btn-navy" href="mailto:info@daop.it?subject=Collaborazione%20per%20la%20mia%20provincia">Proponi la tua zona</a>
    <a class="btn btn-teal" href="/metodo.html">Come verifichiamo gli eventi</a>
  </div>

  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""
    if os.path.exists(ZONE_PATH) and \
            open(ZONE_PATH, encoding='utf-8').read() == html_out:
        print("[genera_eventi] zone.html invariato")
        return
    with open(ZONE_PATH, 'w', encoding='utf-8') as fh:
        fh.write(html_out)
    print(f"[genera_eventi] zone.html aggiornato ({len(schede)} province)")


# ---------------------------------------------------------------------------
# PAGINE COMUNE
#
# Perche': in Search Console le query di comune ("festa novi ligure oggi",
# "sagre provincia di alessandria oggi") fanno decine di impressioni in nona
# posizione e zero clic, perche' ci arriviamo con l'agenda generica. E' lo
# stesso problema che le pagine evento hanno risolto per le query di singola
# sagra, un piano sopra.
#
# Il rischio qui e' peggiore della pagina magra: una serie di pagine per
# localita', tutte uguali tranne il nome del posto, e' quello che Google chiama
# doorway page, e la penalizzazione non colpisce quelle pagine ma il dominio.
# La differenza fra una doorway page e un hub locale vero e' una sola: la
# pagina deve contenere qualcosa che l'agenda non da'. Qui e' il raggruppamento
# per manifestazione (le 13 serate della patronale sono UNA cosa, non 13), i
# luoghi e le pro loco che ricorrono, e le feste che tornano ogni anno.
#
# Per questo la soglia sta scritta nel codice e non nella testa di chi genera.
# ---------------------------------------------------------------------------
COMUNI_DIR = os.path.join(PAGINE_DIR, "comune")
STORICO_PATH = os.path.join(ROOT, "data", "storico-comuni.json")
REGISTRO_COMUNI = os.path.join(ROOT, "data", "pagine-comune.json")

# I comuni per cui una pagina ha senso: i piu' grandi delle province che
# copriamo. E' una lista di ambizione, non di stato: Casale Monferrato oggi ha
# zero eventi sul foglio e infatti la pagina non nasce. Nascera' da sola la
# notte in cui il foglio avra' abbastanza roba, senza che nessuno tocchi il
# codice. Un comune fuori da questa lista non prende una pagina nemmeno se
# passa le soglie: la domanda di ricerca, in un paese di 400 abitanti, non c'e'
# comunque, e una pagina in piu' e' solo un'altra porta che sembra una doorway.
CITTA_HUB = (
    # Alessandria
    'Alessandria', 'Casale Monferrato', 'Novi Ligure', 'Tortona', 'Acqui Terme',
    'Valenza', 'Ovada', 'Serravalle Scrivia', 'Arquata Scrivia',
    # Asti
    'Asti', 'Nizza Monferrato', 'Canelli', "San Damiano d'Asti",
    'Costigliole d\'Asti', 'Montiglio Monferrato',
    # Cuneo
    'Cuneo', 'Alba', 'Bra', 'Mondovì', 'Fossano', 'Savigliano', 'Saluzzo',
)
CITTA_HUB_KEY = {_key(c): c for c in CITTA_HUB}

# Le soglie. Quattro eventi e tre cose diverse: sotto, la pagina non ha niente
# da dire che l'agenda non dica meglio.
MIN_EVENTI_HUB = 4
MIN_VARIETA_HUB = 3
FINESTRA_HUB = 365      # giorni di storico che contano per la soglia
MEMORIA_STORICO = 800   # ~2 anni: bastano a dire "torna ogni anno"


def chiavi_gruppo(terne):
    """La chiave di raggruppamento di ogni evento, date le terne
    (manifestazione, nome, slug).

    Chi ha una manifestazione sta con la sua manifestazione. Chi non ce l'ha ma
    si chiama COME una manifestazione presente e' la riga "cappello" del foglio
    (succede: "Alla (Ri)scoperta delle Favole Disney" esiste sia come
    manifestazione sia come riga singola), e va nello stesso gruppo, non in uno
    nuovo con lo stesso identico titolo. Tutti gli altri stanno per conto loro."""
    terne = list(terne)
    manifesti = {_key(m) for m, _, _ in terne if (m or '').strip()}
    out = []
    for m, nome, sl in terne:
        if (m or '').strip():
            out.append(_key(m))
        elif _key(nome) in manifesti:
            out.append(_key(nome))
        else:
            out.append(f'solo::{sl}')
    return out


def varieta(terne):
    """Quante cose DIVERSE succedono in un comune.

    Le 18 serate di San Liberato a Sant'Albano Stura contano 1, non 18. Senza
    questo numero il comune con piu' eventi in assoluto (18) sarebbe il primo
    candidato a una pagina "Eventi a Sant'Albano Stura" che in realta' e' il
    programma di una festa sola, mentre Novi Ligure - 7 eventi, 5 cose diverse,
    e la domanda di ricerca vera - resterebbe fuori."""
    return len(set(chiavi_gruppo(terne)))


def carica_storico():
    if not os.path.exists(STORICO_PATH):
        return {}
    try:
        with open(STORICO_PATH, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        print(f"[genera_eventi] storico comuni illeggibile ({err}), riparto da vuoto")
        return {}


def aggiorna_storico(events, oggi):
    """Archivio leggero comune -> eventi visti, aggiornato a ogni run.

    data/eventi.json tiene solo il futuro: senza archivio, a novembre la pagina
    di un comune sarebbe una pagina vuota, e una pagina vuota non deve
    esistere. Lo slug di slug_evento() e' stabile fra un'edizione e l'altra,
    quindi l'archivio sa da solo quali feste tornano ogni anno - che e' l'unica
    cosa che questa pagina puo' dire e che ne' l'agenda ne' chi copia gli
    eventi da Instagram sa dire."""
    storico = carica_storico()
    for e in events:
        citta = (e.get('citta') or '').strip()
        k = _key(citta)
        if not k:
            continue
        c = storico.setdefault(k, {"nome": citta, "prov": e.get('prov') or '', "eventi": {}})
        c["nome"] = citta or c["nome"]
        c["prov"] = (e.get('prov') or c.get("prov") or '').upper()
        sl = slug_evento(e)
        r = c["eventi"].setdefault(sl, {"anni": []})
        r["nome"] = (e.get('nome') or '').strip()
        r["manifest"] = (e.get('manifest') or '').strip()
        r["luogo"] = (e.get('luogo') or '').strip()
        r["organizza"] = organizzatore(e.get('nome'))
        r["pagina"] = ha_pagina(e)
        r["ultima"] = e['d_start'].isoformat()
        if e['d_start'].year not in r["anni"]:
            r["anni"] = sorted(r["anni"] + [e['d_start'].year])
    # Potatura: quello che non si vede da due anni non torna piu'.
    limite = (oggi - datetime.timedelta(days=MEMORIA_STORICO)).isoformat()
    for k in list(storico):
        c = storico[k]
        c["eventi"] = {sl: r for sl, r in c["eventi"].items()
                       if (r.get("ultima") or '') >= limite}
        if not c["eventi"]:
            del storico[k]
    with open(STORICO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(storico, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return storico


def comuni_hub(events, storico, oggi):
    """{chiave: dati} dei comuni che meritano una pagina, soglie alla mano."""
    limite = (oggi - datetime.timedelta(days=FINESTRA_HUB)).isoformat()
    hub = {}
    for k, nome_ufficiale in CITTA_HUB_KEY.items():
        futuri = sorted((e for e in events if _key(e.get('citta')) == k),
                        key=lambda e: (e['d_start'], e.get('nome') or ''))
        arch = (storico.get(k) or {}).get('eventi', {})
        visti = {sl: r for sl, r in arch.items() if (r.get('ultima') or '') >= limite}
        # Un evento futuro e' anche in archivio: si contano una volta sola.
        terne = {slug_evento(e): ((e.get('manifest') or ''), (e.get('nome') or ''))
                 for e in futuri}
        for sl, r in visti.items():
            terne.setdefault(sl, (r.get('manifest') or '', r.get('nome') or ''))
        var = varieta((m, nome, sl) for sl, (m, nome) in terne.items())
        if len(terne) < MIN_EVENTI_HUB or var < MIN_VARIETA_HUB:
            continue
        nome = (futuri[0].get('citta') if futuri
                else (storico.get(k) or {}).get('nome') or nome_ufficiale)
        hub[k] = {
            'nome': nome,
            'prov': ((futuri[0].get('prov') if futuri else
                      (storico.get(k) or {}).get('prov')) or '').upper(),
            'slug': slugify(nome),
            'futuri': futuri,
            'archivio': visti,
            'eventi': len(terne),
            'varieta': var,
        }
    return hub


def url_comune(dati):
    return f"{SITE_URL}/eventi/comune/{dati['slug']}.html"


def blocco_comuni(hub):
    """L'elenco delle pagine per comune, per il fondo di eventi.html.

    Le pagine comune esistevano gia' ma le linkavano solo zone.html e le poche
    schede evento di quei comuni: dall'agenda, che e' la pagina piu' forte del
    sito, non arrivava niente. Il conteggio accanto al nome non e' decorazione,
    e' la promessa che dice se vale la pena entrare."""
    if not hub:
        return ''
    voci = sorted(hub.values(), key=lambda d: (-len(d['futuri']), d['nome']))
    link = "".join(
        # Il numero da solo tiene la pillola corta; "eventi in programma" per
        # esteso sta nell'aria-label, perche' un "12" nudo allo screen reader
        # non dice niente.
        f'<a href="/eventi/comune/{d["slug"]}.html" '
        f'aria-label="{esc(d["nome"])}: {len(d["futuri"])} eventi in programma">'
        f'{esc(d["nome"])} <span>{len(d["futuri"])}</span></a>'
        for d in voci if d['futuri'])
    if not link:
        return ''
    return ('      <span class="ev-comuni-lab">Vai al comune</span>\n'
            f'      <div class="ev-comuni">{link}</div>')


COMUNE_CSS = """
.com-stat{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0 6px;padding:0;list-style:none}
.com-stat li{border:1px solid rgba(45,74,92,.16);border-radius:100px;padding:6px 14px;font-size:.86rem}
.com-grp{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:15px 18px;margin:14px 0}
.com-grp h3{margin:0 0 3px;font-size:1.06rem}
.com-per{font-size:.85rem;opacity:.72;margin:0 0 9px}
.com-ev{list-style:none;margin:0;padding:0}
.com-ev li{padding:7px 0;border-top:1px solid rgba(45,74,92,.1);font-size:.94rem;
  display:flex;gap:10px;align-items:baseline}
.com-ev li:first-child{border-top:0}
.com-d{font-weight:700;white-space:nowrap;font-size:.86rem;opacity:.8;min-width:78px}
.com-ev a{text-decoration:none;color:var(--navy,#2d4a5c);font-weight:600}
.com-ev a:hover{text-decoration:underline}
.com-link{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 4px}
.com-link a{display:inline-block;border:1px solid rgba(45,74,92,.2);border-radius:100px;
  padding:7px 15px;font-size:.9rem;font-weight:600;text-decoration:none;color:var(--navy,#2d4a5c)}
.com-link a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.09)}
.com-vuoto{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:16px 18px;
  margin:16px 0;font-size:.95rem}
"""


def _gruppi_comune(futuri):
    """Gli eventi futuri raggruppati per manifestazione.

    E' il motivo per cui questa pagina esiste: nell'agenda le 13 serate della
    patronale sono 13 righe in fila, qui sono una festa con dentro 13 serate.
    Chi cerca "festa novi ligure" vuole la seconda cosa."""
    gruppi = collections.OrderedDict()
    chiavi = chiavi_gruppo(((e.get('manifest') or ''), (e.get('nome') or ''),
                            slug_evento(e)) for e in futuri)
    for e, chiave in zip(futuri, chiavi):
        m = (e.get('manifest') or '').strip()
        g = gruppi.setdefault(chiave, {'titolo': m, 'eventi': []})
        if m and not g['titolo']:
            g['titolo'] = m
        g['eventi'].append(e)
    for g in gruppi.values():
        if not g['titolo']:
            g['titolo'] = (g['eventi'][0].get('nome') or '').strip()
    return list(gruppi.values())


def _href_evento(e):
    if ha_pagina(e):
        return f"/eventi/{slug_evento(e)}.html"
    return f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html"


def _quando_breve(e, oggi):
    d = e['d_start']
    if d < oggi:
        return "in corso"
    if d == oggi:
        return "oggi"
    if (d - oggi).days == 1:
        return "domani"
    return f"{GIORNI[d.weekday()][:3]} {d.day} {MESI[d.month - 1]}"


def _ricorrenti(archivio):
    """Le feste viste in piu' di un anno: quelle che tornano davvero."""
    out = [(sl, r) for sl, r in archivio.items() if len(r.get('anni') or []) > 1]
    out.sort(key=lambda t: (-len(t[1]['anni']), t[1].get('nome') or ''))
    return out


def _ricorrenze(valori, minimo=2, quante=4):
    """I valori che tornano almeno `minimo` volte, dal piu' frequente."""
    c = collections.Counter(v.strip() for v in valori if (v or '').strip())
    return [(v, n) for v, n in c.most_common(quante) if n >= minimo]


def render_comune(dati, css, nav, foot, oggi, vicini=None):
    citta = dati['nome']
    futuri, archivio = dati['futuri'], dati['archivio']
    url = url_comune(dati)
    prov_nome = PROVINCE_NOMI.get(dati['prov'], dati['prov'])

    # L'anno sta nelle query ("sagre novi ligure 2026") ma non si scrive a mano:
    # e' quello del prossimo evento, o l'anno in corso se non ce n'e' nessuno.
    anno = futuri[0]['d_start'].year if futuri else oggi.year
    base = f"Eventi e sagre{a_citta(citta)} {anno}"
    titolo = next((t for t in (f"{base} | DAOP", base) if len(t) <= MAX_TITLE),
                  trunc(base, MAX_TITLE))
    gruppi = _gruppi_comune(futuri)

    # L'attacco si costruisce con i numeri veri: e' quello che rende questa
    # pagina diversa dalla stessa pagina di un altro comune, ed e' anche
    # l'unica cosa onesta da scrivere senza aver visitato il posto.
    if futuri:
        fine = max(e['d_end'] for e in futuri)
        quanti = (f"{len(futuri)} eventi in programma" if len(futuri) > 1
                  else "1 evento in programma")
        cosa = (f"{len(gruppi)} manifestazioni diverse" if len(gruppi) > 1
                else "una manifestazione")
        sotto = f"{quanti}, fino al {fine.day} {MESI_LUNGHI[fine.month - 1]} {fine.year}"
        apertura = (f"{quanti}{a_citta(citta)}, in provincia di {prov_nome}: "
                    f"{cosa}, con le date, gli orari e i contatti di chi le organizza. "
                    "Le schede le controlliamo una per una prima di pubblicarle.")
    else:
        sotto = "Nessun evento in programma in questo momento"
        apertura = (f"In questo momento{a_citta(citta)} non abbiamo eventi in agenda. "
                    "Qui sotto restano le feste che tornano ogni anno, così sai "
                    "quando aspettarle: appena arrivano le date della prossima "
                    "edizione le trovi in questa pagina.")

    stat = [f"<li>{len(futuri)} in programma</li>" if futuri else "",
            f"<li>{len(gruppi)} manifestazioni</li>" if len(gruppi) > 1 else "",
            f"<li>provincia di {esc(prov_nome)}</li>"]
    blocchi = []
    for g in gruppi:
        ev = g['eventi']
        di, df = min(e['d_start'] for e in ev), max(e['d_end'] for e in ev)
        periodo = (data_estesa(di).capitalize() if di == df else
                   f"{_dal(di.day)} {MESI_LUNGHI[di.month - 1]} al "
                   f"{df.day} {MESI_LUNGHI[df.month - 1]}")
        if len(ev) == 1:
            # Un evento solo: il titolo del gruppo E' l'evento. Ripeterlo sotto
            # come unica riga di elenco riempirebbe la pagina di doppioni, che
            # e' il modo piu' rapido per farla sembrare generata a macchina.
            blocchi.append(
                f'<section class="com-grp"><h3>'
                f'<a href="{_href_evento(ev[0])}">{esc(trunc(g["titolo"], 80))}</a></h3>'
                f'<p class="com-per">{esc(periodo)}</p></section>')
            continue
        righe = "".join(
            f'<li><span class="com-d">{esc(_quando_breve(e, oggi))}</span>'
            f'<a href="{_href_evento(e)}">{esc(trunc(e.get("nome") or "", 80))}</a></li>'
            for e in ev)
        blocchi.append(
            f'<section class="com-grp"><h3>{esc(trunc(g["titolo"], 80))}</h3>'
            f'<p class="com-per">{esc(periodo)} · {len(ev)} appuntamenti</p>'
            f'<ul class="com-ev">{righe}</ul></section>')

    ric = _ricorrenti(archivio)
    if ric:
        righe = "".join(
            f'<li><span class="com-d">{r["anni"][0]}–{r["anni"][-1]}</span>'
            + (f'<a href="/eventi/{sl}.html">{esc(trunc(r.get("nome") or "", 80))}</a>'
               if r.get('pagina') else f'<span>{esc(trunc(r.get("nome") or "", 80))}</span>')
            + '</li>' for sl, r in ric[:8])
        blocchi.append(
            f'<h2>Le feste che tornano ogni anno{a_citta(citta)}</h2>'
            f'<p>Le abbiamo già viste in più di un\'edizione: quando escono le date '
            f'nuove, questa pagina si aggiorna da sola.</p>'
            f'<section class="com-grp"><ul class="com-ev">{righe}</ul></section>')

    # Luoghi e organizzatori ricorrenti: si ricavano contando, non si scrivono.
    tutti_luoghi = [e.get('luogo') or '' for e in futuri] + \
                   [r.get('luogo') or '' for r in archivio.values()]
    tutti_org = [organizzatore(e.get('nome')) for e in futuri] + \
                [r.get('organizza') or '' for r in archivio.values()]
    extra = []
    # "I posti che tornano più spesso: Novi Ligure" non è un'informazione: nel
    # foglio la colonna del luogo a volte ripete il comune. Fuori.
    tutti_luoghi = [v for v in tutti_luoghi if _key(v) and _key(v) != _key(citta)]
    luoghi = _ricorrenze(tutti_luoghi)
    if luoghi:
        extra.append("<p>I posti che tornano più spesso: "
                     + elenco_it([f"<strong>{esc(v)}</strong>" for v, _ in luoghi])
                     + ".</p>")
    org = _ricorrenze(tutti_org)
    if org:
        extra.append("<p>A organizzare sono soprattutto "
                     + elenco_it([f"<strong>{esc(v)}</strong>" for v, _ in org])
                     + ": i recapiti stanno sulla scheda di ogni evento.</p>")
    if extra:
        blocchi.append(f"<h2>Come funziona{a_citta(citta)}</h2>" + "".join(extra))

    altri = [d for k, d in sorted((vicini or {}).items())
             if d['slug'] != dati['slug'] and d['prov'] == dati['prov']][:6]
    link_altri = "".join(f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
                         for d in altri)

    descr = trunc(f"Eventi, sagre e feste{a_citta(citta)}: {sotto.lower()}. "
                  "Date, orari e contatti, controllati uno per uno da DAOP.", 152)

    lista = [{"@type": "ListItem", "position": i + 1,
              "url": f"{SITE_URL}{_href_evento(e)}",
              "name": (e.get('nome') or '').strip()}
             for i, e in enumerate(futuri[:30])]
    grafo = [
        {"@type": "CollectionPage", "@id": url, "url": url, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@type": "Place", "name": citta,
                   "address": {"@type": "PostalAddress", "addressLocality": citta,
                               "addressRegion": dati['prov'], "addressCountry": "IT"}},
         "publisher": {"@id": ORG_ID}, "dateModified": oggi.isoformat()},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": citta, "item": url}]},
    ]
    # L'ItemList RIMANDA alle pagine evento, non ripete gli Event: due copie
    # dello stesso evento in due pagine diverse sono due elementi da validare
    # invece di uno, ed e' esattamente il pasticcio del superEvent.
    if lista:
        grafo.append({"@type": "ItemList", "name": f"Eventi{a_citta(citta)}",
                      "numberOfItems": len(lista), "itemListElement": lista})
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)
    robots = "index, follow" if futuri or ric else "noindex, follow"

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{COMUNE_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>{esc(citta)}</span>
    </div>
    <h1>Eventi e sagre{a_citta(citta)}</h1>
    <p class="ev-when">{esc(sotto)}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  <ul class="com-stat">{"".join(stat)}</ul>
  <p>{apertura}</p>

  {'<h2>In programma</h2>' if futuri else ''}
  {"".join(blocchi)}

  <div class="com-link">
    <a href="/eventi.html">Tutta l'agenda DAOP</a>
    <a href="/metodo.html">Come verifichiamo gli eventi</a>
  </div>
  {f'<h2>Altri comuni della provincia di {esc(prov_nome)}</h2><div class="com-link">{link_altri}</div>' if link_altri else ''}

  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
{blocco_ginetto(citta)}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def scrivi_comuni(hub, oggi):
    """Genera le pagine comune. Restituisce {slug: lastmod} per la sitemap."""
    if not hub:
        print("[genera_eventi] nessun comune sopra soglia: nessuna pagina comune")
        return {}
    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagine comune saltate: {err}")
        return {}
    os.makedirs(COMUNI_DIR, exist_ok=True)
    # Il lastmod e' la data in cui la pagina e' cambiata davvero, non quella
    # della run: e' lo stesso motivo per cui scrivi_pagine() tiene un registro.
    # Dichiarare "modificata oggi" ogni notte e' falso, e Google smette di dare
    # peso a <lastmod> quando lo trova inaffidabile.
    try:
        reg = json.load(open(REGISTRO_COMUNI, encoding='utf-8'))
    except (OSError, ValueError):
        reg = {}
    cambiate = 0
    for dati in sorted(hub.values(), key=lambda d: d['slug']):
        path = os.path.join(COMUNI_DIR, f"{dati['slug']}.html")
        nuovo = render_comune(dati, css, nav, foot, oggi, vicini=hub)
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            reg.setdefault(dati['slug'], oggi.isoformat())
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        reg[dati['slug']] = oggi.isoformat()
        cambiate += 1
    # Le pagine dei comuni scesi sotto soglia NON si cancellano: i link che
    # girano restano validi. Vanno pero' in noindex e fuori dalla sitemap,
    # perche' senza abbastanza eventi la pagina non ha piu' niente da dire.
    vivi = {d['slug'] for d in hub.values()}
    orfane = sorted(f[:-5] for f in os.listdir(COMUNI_DIR)
                    if f.endswith('.html') and f[:-5] not in vivi)
    for slug in orfane:
        path = os.path.join(COMUNI_DIR, f"{slug}.html")
        vecchio = open(path, encoding='utf-8').read()
        spento = vecchio.replace('<meta name="robots" content="index, follow">',
                                 '<meta name="robots" content="noindex, follow">')
        if spento != vecchio:
            open(path, 'w', encoding='utf-8').write(spento)
        reg.pop(slug, None)
    with open(REGISTRO_COMUNI, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_eventi] pagine comune: {len(hub)} sopra soglia "
          f"({cambiate} riscritte)" +
          (f", {len(orfane)} sotto soglia in noindex: {', '.join(orfane)}"
           if orfane else ""))
    for d in sorted(hub.values(), key=lambda d: d['nome']):
        print(f"[genera_eventi]   {d['nome']}: {len(d['futuri'])} in programma, "
              f"{d['varieta']} cose diverse")
    return {s: m for s, m in sorted(reg.items()) if s in vivi}


def opzioni_provincia(events):
    """Opzioni del filtro provincia, ricavate dagli eventi in agenda.

    Erano HTML statico FUORI dai marker (solo "Prov. AL" e "Prov. AT"), quindi
    aprire il filtro dei dati a CN non bastava: gli eventi di Cuneo comparivano in
    elenco ma non c'era modo di filtrarli. Ora l'elenco si genera da solo e non
    puo' piu' restare indietro. I value sono minuscoli perche' e' quello che il JS
    confronta con data-province sulle schede.
    """
    presenti = {e.get('prov') for e in events if e.get('prov')}
    righe = ['        <option value="all">Province</option>']
    for c in PROVINCE_PUBBLICATE:
        if c in presenti:
            righe.append(f'        <option value="{c.lower()}">Prov. {c}</option>')
    return "\n".join(righe)


def inject(tipo_opts, lista, jsonld, prov_opts=None, comuni_html=None):
    s = open(HTML_PATH, encoding="utf-8").read()
    s, n1 = re.subn(r'(<!-- EVENTI-TIPO:START -->\n).*?(\n *<!-- EVENTI-TIPO:END -->)',
                    lambda m: m.group(1) + tipo_opts + m.group(2), s, count=1, flags=re.S)
    s, n2 = re.subn(r'(<!-- EVENTI-LISTA:START -->\n).*?(\n *<!-- EVENTI-LISTA:END -->)',
                    lambda m: m.group(1) + lista + m.group(2), s, count=1, flags=re.S)
    s, n3 = re.subn(r'<script type="application/ld\+json" id="eventi-jsonld">.*?</script>',
                    lambda _: jsonld, s, count=1, flags=re.S)
    # Il blocco province e' opzionale: se i marker non ci sono (eventi.html piu'
    # vecchio del deploy) si va avanti con un avviso invece di far fallire tutto.
    n4 = 1
    if prov_opts is not None:
        s, n4 = re.subn(r'(<!-- EVENTI-PROV:START -->\n).*?(\n *<!-- EVENTI-PROV:END -->)',
                        lambda m: m.group(1) + prov_opts + m.group(2), s, count=1, flags=re.S)
        if n4 != 1:
            print("[genera_eventi] ATTENZIONE: marker EVENTI-PROV non trovati in "
                  "eventi.html: il filtro provincia resta quello scritto a mano")
    # Anche questo blocco e' opzionale, stessa ragione: un eventi.html piu'
    # vecchio del deploy non deve far fallire tutta la generazione.
    if comuni_html is not None:
        s, n5 = re.subn(r'(<!-- EVENTI-COMUNI:START -->\n).*?(\n *<!-- EVENTI-COMUNI:END -->)',
                        lambda m: m.group(1) + comuni_html + m.group(2), s, count=1, flags=re.S)
        if n5 != 1:
            print("[genera_eventi] ATTENZIONE: marker EVENTI-COMUNI non trovati in "
                  "eventi.html: l'elenco delle pagine comune non viene scritto")
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise SystemExit(f"Ancoraggi non trovati in eventi.html (tipo={n1}, lista={n2}, json-ld={n3})")
    open(HTML_PATH, "w", encoding="utf-8").write(s)


def inject_home(cards_html):
    """Sostituisce le card del carosello in index.html tra i marker HOME-EVENTI.
    Se la home o i marker mancano, salta senza errore."""
    if not os.path.exists(HOME_PATH):
        print("[genera_eventi] index.html non trovato, salto carosello home")
        return
    s = open(HOME_PATH, encoding="utf-8").read()
    block = "<!-- HOME-EVENTI:START -->\n" + cards_html + "\n      <!-- HOME-EVENTI:END -->"
    s, n = re.subn(r'<!-- HOME-EVENTI:START -->.*?<!-- HOME-EVENTI:END -->',
                   lambda _: block, s, count=1, flags=re.S)
    if n != 1:
        print("[genera_eventi] marker HOME-EVENTI non trovati in index.html, salto carosello home")
        return
    open(HOME_PATH, "w", encoding="utf-8").write(s)
    print("[genera_eventi] carosello eventi aggiornato in index.html")


def update_sitemap(slugs=(), comuni=()):
    """Porta il <lastmod> di eventi.html nella sitemap alla data odierna e
    rigenera il blocco delle pagine evento.
    Il commit avviene (dal workflow) solo se eventi.html è davvero cambiato,
    così la data riflette una modifica reale dei contenuti."""
    if not os.path.exists(SITEMAP_PATH):
        return
    today = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()

    if slugs:
        blocco = "\n".join(
            f"  <url>\n    <loc>{SITE_URL}/eventi/{sl}.html</loc>\n"
            f"    <lastmod>{mod}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
            for sl, mod in slugs.items())
        s, nb = re.subn(
            r'(<!-- PAGINE-EVENTO:START.*?-->).*?( *<!-- PAGINE-EVENTO:END -->)',
            lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
        if nb == 1:
            print(f"[genera_eventi] sitemap: {len(slugs)} pagine evento")
        else:
            print("[genera_eventi] sitemap: marker PAGINE-EVENTO non trovati, salto")

    if comuni:
        # priority piu' alta delle pagine evento: una pagina comune vale tutto
        # l'anno, una pagina evento vale fino alla domenica della sagra.
        blocco = "\n".join(
            f"  <url>\n    <loc>{SITE_URL}/eventi/comune/{sl}.html</loc>\n"
            f"    <lastmod>{mod}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>"
            for sl, mod in comuni.items())
        s, nb = re.subn(
            r'(<!-- PAGINE-COMUNE:START.*?-->).*?( *<!-- PAGINE-COMUNE:END -->)',
            lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
        if nb == 1:
            print(f"[genera_eventi] sitemap: {len(comuni)} pagine comune")
        else:
            print("[genera_eventi] sitemap: marker PAGINE-COMUNE non trovati, salto")

    s, n = re.subn(
        r'(<loc>https://www\.daop\.it/eventi\.html</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + today + m.group(2), s, count=1)
    print(f"[genera_eventi] sitemap: lastmod eventi.html -> {today}" if n == 1
          else "[genera_eventi] sitemap: blocco eventi.html non trovato, salto")
    # Una sola scrittura alla fine: se il lastmod non matcha non dobbiamo
    # comunque perdere il blocco delle pagine evento appena rigenerato.
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)


def controlla_crollo(events):
    """Blocca la rigenerazione se gli eventi sono crollati rispetto all'ultima volta.

    PERCHE' ESISTE (05/08/2026): l'export CSV di Google **rispetta i filtri** del
    foglio. Con un filtro attivo sul tab Eventi l'export restituisce solo le righe
    visibili: quel giorno erano 26 invece di 193. Rigenerare in quello stato
    pubblica un sito con un decimo degli eventi, la sitemap che crolla, e decine di
    pagine messe in noindex - tutto senza un errore, quindi senza che nessuno se ne
    accorga. Il workflow notturno gira non presidiato: e' proprio lo scenario in cui
    un guasto silenzioso fa danno.

    Il confronto e' con data/eventi.json, l'istantanea committata dell'ultimo run
    buono. Se il calo e' oltre la soglia si esce con codice 1: il workflow FALLISCE
    in modo visibile invece di pubblicare. Per un calo legittimo (fine stagione) si
    forza con la variabile d'ambiente ACCETTA_CALO=1.
    """
    if os.environ.get("ACCETTA_CALO"):
        print("[genera_eventi] ACCETTA_CALO attivo: nessun controllo sul crollo.")
        return
    try:
        with open(JSON_PATH, encoding="utf-8") as fh:
            precedenti = len(json.load(fh))
    except Exception:
        return          # prima esecuzione o snapshot illeggibile: niente con cui confrontare

    if precedenti < 20:
        return          # troppo pochi per un confronto sensato

    soglia = int(precedenti * 0.6)
    if len(events) >= soglia:
        return

    print()
    print("=" * 68)
    print("  BLOCCATO: gli eventi sono CROLLATI, non rigenero il sito.")
    print("=" * 68)
    print(f"  letti ora        : {len(events)}")
    print(f"  ultimo run buono : {precedenti}   (soglia di allarme: {soglia})")
    print()
    print("  Causa piu' probabile: un FILTRO attivo sul tab Eventi del foglio.")
    print("  L'export CSV rispetta i filtri, quindi le righe nascoste non arrivano.")
    print("  Togli il filtro (Dati -> Rimuovi filtro) e rilancia.")
    print()
    print("  Se il calo e' vero (fine stagione), forza con:  ACCETTA_CALO=1")
    print("=" * 68)
    sys.exit(1)


def main():
    events = normalize(fetch_rows())
    controlla_crollo(events)
    segnala_doppioni(events)
    assegna_ancore(events)
    # hub va calcolato PRIMA di render(): l'agenda linka le pagine comune sia
    # nelle schede sia nel blocco in fondo, e senza non saprebbe quali esistono.
    oggi = datetime.date.today()
    storico = aggiorna_storico(events, oggi)
    hub = comuni_hub(events, storico, oggi)
    tipo_opts, lista = render(events, hub)
    jsonld = render_jsonld(events)
    inject(tipo_opts, lista, jsonld, opzioni_provincia(events), blocco_comuni(hub))
    inject_home(render_home(events))
    slugs = scrivi_pagine(events, hub)
    comuni = scrivi_comuni(hub, oggi)
    scrivi_metodo(events)
    scrivi_zone(events, hub)
    # aggiorna l'istantanea committata
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()
            if k not in CAMPI_DAOP and k not in CAMPI_EXTRA
            or (v or '').strip()} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap(slugs, comuni)
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
