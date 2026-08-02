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
        }, **{nomi[0]: e.get(campo, '') for campo, nomi in CAMPI_DAOP.items()})
            for e in snap]


# Colonne facoltative del foglio: sono il giudizio editoriale, cioe' l'unica
# parte che un assistente AI non puo' ricavare dal volantino dell'organizzatore.
# Restano vuote finche' Patrick non aggiunge le colonne al foglio, e quando sono
# vuote non compare nessun blocco: meglio niente che un titolo senza risposta.
# I nomi sono tollerati in piu' grafie perche' il foglio lo scrivono due persone.
CAMPI_DAOP = {
    'perche':          ("Perché andarci", "Perche andarci", "Nota DAOP", "Perché DAOP lo consiglia"),
    'eta_consigliata': ("Età consigliata", "Eta consigliata", "Età ideale"),
    'adatto':          ("Adatto ai bambini", "Adatto davvero ai bambini"),
    'prenotazione':    ("Prenotazione", "Prenotazioni", "Serve prenotare"),
    'parcheggio':      ("Parcheggio", "Dove parcheggiare"),
    'dintorni':        ("Nei dintorni", "Cosa fare nei dintorni", "Dintorni"),
    'piano_b':         ("Piano B", "In caso di pioggia", "Se piove"),
    'ginetto':         ("Consiglio di Ginetto", "Ginetto"),
}


def _key(s):
    """Chiave di confronto per le intestazioni: senza accenti, spazi e maiuscole.
    'Età consigliata', 'ETA CONSIGLIATA' e 'eta_consigliata' sono la stessa cosa."""
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def campi_daop(d):
    """Legge dalla riga del foglio le colonne editoriali, se ci sono."""
    idx = {_key(k): (v or '').strip() for k, v in d.items()}
    return {campo: next((idx[_key(n)] for n in nomi if idx.get(_key(n))), '')
            for campo, nomi in CAMPI_DAOP.items()}


def normalize(rows):
    today = datetime.date.today()
    events = []
    for d in rows:
        di = pdate(d.get('Data Inizio'))
        if not di:
            continue
        prov = (d.get('Provincia') or '').strip().upper()
        if prov not in ('AL', 'AT'):
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
    """Link 'Come arrivare' su Google Maps."""
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


def riga(e, today):
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

    dove = esc(e['indirizzo'] or e['luogo'])
    dove_html = f'\n          <p class="ev-where">{PIN_SVG} {dove}</p>' if dove else ''

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
            </div>
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


def render(events):
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

    # ── agenda: gli eventi già in corso in testa, poi un gruppo per giornata ─
    gruppi = []
    in_corso = [e for e in events if e['d_start'] < today]
    if in_corso:
        gruppi.append(('in-corso', 'Già iniziati, ancora in corso', in_corso))
    per_giorno = {}
    for e in events:
        if e['d_start'] >= today:
            per_giorno.setdefault(e['d_start'], []).append(e)
    for d in sorted(per_giorno):
        gruppi.append((d.isoformat(), intestazione_giorno(d, today), per_giorno[d]))

    sezioni = []
    for day, titolo, lista in gruppi:
        righe = '\n'.join(riga(e, today) for e in lista)
        sezioni.append(f'''      <section class="ev-day" data-day="{day}">
        <h3 class="ev-dayhead"><span class="ev-dayname">{titolo}</span><span class="ev-daycount">{len(lista)}</span></h3>
{righe}
      </section>''')

    lista_html = (highlights + '    <div class="events-list" id="events-list">\n'
                  + '\n\n'.join(sezioni) + '\n    </div>')

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
    # fonti. Quando il foglio indica la manifestazione, quella e' vera.
    manifest = (e.get('manifest') or '').strip()
    if manifest:
        obj["superEvent"] = {"@type": "Event", "name": manifest}
    # Chi organizza: NON lo inventiamo, lo leggiamo dalla coda del nome quando il
    # foglio ce l'ha ("... - Pro Loco Ciglione"). E' il dato che Google incrocia
    # con le altre fonti, quindi o e' quello vero o non ci va.
    org = organizzatore(e.get('nome'))
    if org:
        obj["organizer"] = {"@type": "Organization", "name": org}
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


def _titolo(nome, citta):
    """Title che sta nei limiti senza mai perdere la città né finire a metà
    parola. Ordine di sacrificio: prima il suffisso di brand, poi il nome."""
    coda = f" a {citta}" if citta else ""
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
        for k in CAMPI_DAOP:
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

    return "\n".join(css), rooted(nav.group(0)), rooted(foot.group(0))


PAGINA_CSS = """
/* La nav del sito e' position:fixed: senza spazio in cima gli finisce sotto
   il breadcrumb e mezzo H1. Stessi valori con cui .page-hero la compensa
   nelle altre pagine (148px, 120px sotto i 600px). */
.ev-wrap{max-width:820px;margin:0 auto;padding:148px 20px 40px}
@media(max-width:600px){.ev-wrap{padding:120px 18px 32px}}
/* Il breadcrumb e' un <div role="navigation">, non un <nav>: il CSS del sito
   ha nav{position:fixed;top:0} come selettore di elemento, che rendeva fisso
   anche il breadcrumb piazzandolo sopra la barra. position:static come
   ulteriore difesa se un giorno la regola si allargasse. */
.ev-crumb{position:static;font-size:.85rem;opacity:.7;margin:0 0 10px}
.ev-crumb a{color:inherit}
.ev-head h1{margin:.1em 0 .3em;line-height:1.15}
.ev-when{font-size:1.05rem;font-weight:600;color:var(--daop-navy,#1b3a5c)}
.ev-facts{list-style:none;padding:0;margin:22px 0;display:grid;gap:10px}
.ev-facts li{display:flex;gap:10px;align-items:flex-start;line-height:1.45}
.ev-facts svg{flex:0 0 auto;margin-top:3px;opacity:.65}
.ev-body{margin:26px 0;line-height:1.7}
.ev-loc{width:100%;height:auto;border-radius:14px;margin:22px 0}
.ev-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:28px 0 8px}
/* Rete di sicurezza: se un .btn restasse senza modificatore non deve mai
   ricadere sul blu di sistema, come e' successo a "Come arrivare". */
.ev-actions .btn{color:#fff}
.ev-back{font-weight:600;color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:3px}
.ev-over{border:1px solid #e5c07b;background:#fdf6e6;border-radius:14px;padding:16px 18px;margin:22px 0}
.ev-over strong{display:block;margin-bottom:4px}
@media (prefers-color-scheme:dark){.ev-over{background:#2e2717;border-color:#6b5a2e}}
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
.ev-firma-nota{opacity:.78;font-size:.86rem}
.ev-firma a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
/* Altri eventi vicini: link in uscita e motivo per restare sul sito. */
.ev-vicini{margin:34px 0 0}
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
@media (prefers-color-scheme:dark){
  .ev-daop{background:rgba(107,165,168,.14);border-color:rgba(107,165,168,.35)}
  .ev-vicini a{border-color:rgba(255,255,255,.16)}
}
"""


ORG_ID = f"{SITE_URL}/#organization"
SITE_ID = f"{SITE_URL}/#website"
METODO_URL = f"{SITE_URL}/metodo.html"

CHECK_SVG = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4 12 14.01l-3-3"/></svg>')

# L'ordine e' quello con cui si decide davvero: prima se ci vado, poi se e'
# adatto, poi la logistica.
BLOCCHI_DAOP = (
    ('perche', 'Perché andarci, secondo DAOP'),
    ('adatto', 'Adatto davvero ai bambini?'),
    ('eta_consigliata', 'Età consigliata'),
    ('parcheggio', 'Dove parcheggiare'),
    ('dintorni', 'Cosa fare nei dintorni'),
    ('piano_b', 'Piano B se piove'),
    ('ginetto', 'Il consiglio di Ginetto'),
)


def blocco_daop(e):
    """Il giudizio editoriale: l'unica parte che non sta sul volantino.

    Compare solo per i campi compilati nel foglio. Un titolo senza risposta
    ("Dove parcheggiare" seguito dal vuoto) e' peggio che non averlo."""
    voci = [(t, (e.get(k) or '').strip()) for k, t in BLOCCHI_DAOP]
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
    return (
        '<aside class="ev-firma">'
        f'<p class="ev-firma-t">{CHECK_SVG} Scheda verificata da DAOP</p>'
        '<p>Selezionata e verificata da <strong>DAOP – Dove Andiamo Oggi Papi</strong>, '
        'l\'associazione delle famiglie di Alessandria e Asti. Ultimo controllo: '
        f'<time datetime="{d.isoformat()}">{leggibile}</time>.</p>'
        '<p class="ev-firma-nota">Le informazioni possono cambiare. Prima di partire, '
        'controlla eventuali aggiornamenti dell\'organizzatore. '
        '<a href="/metodo.html">Come verifichiamo gli eventi</a> · '
        f'<a href="mailto:info@daop.it?subject={ogg}">Segnala una correzione</a></p>'
        '</aside>')


def blocco_vicini(rec, events, oggi, limite=6):
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
    return ('<section class="ev-vicini" aria-labelledby="ev-vicini-t">'
            f'<h2 id="ev-vicini-t">{esc(titolo)}</h2>'
            f'<ul>{"".join(righe)}</ul>'
            '<p class="ev-vic-all"><a href="/eventi.html">Vedi tutta l\'agenda DAOP</a></p>'
            '</section>')


def render_pagina(rec, css, nav, foot, oggi, orfano=False, vicini=()):
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
    meta_d = trunc(f"{periodo_esteso(e)}. {descr_txt}" if descr_txt
                   else f"{nome} a {citta}: {periodo_esteso(e)}.", 152)

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
        "areaServed": ["Alessandria", "Asti", "Piemonte"],
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
    firma = firma_daop(rec, oggi)
    altri = blocco_vicini(rec, vicini, oggi) if vicini else ''

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
<article class="ev-wrap">
  <div class="ev-crumb" role="navigation" aria-label="Percorso">
    <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>{esc(trunc(nome, 60))}</span>
  </div>
  <header class="ev-head">
    <h1>{esc(nome)}</h1>
    <p class="ev-when">{esc(periodo_esteso(e))}{' · ' + esc(citta) if citta else ''}</p>
  </header>
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
</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def scrivi_pagine(events):
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
        nuovo = render_pagina(rec, css, nav, foot, oggi, orfano, vicini=events)
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
    print(f"[genera_eventi] schede con giudizio DAOP: {con_giudizio}/{len(reg)}"
          + ("" if con_giudizio else
             "  <- aggiungi al foglio le colonne " + ", ".join(
                 f'"{n[0]}"' for n in CAMPI_DAOP.values())))
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
@media (prefers-color-scheme:dark){
  .met-num div,.met-lim{border-color:rgba(255,255,255,.16)}
}
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
     "Le province di Alessandria e Asti, in Piemonte. Fuori da lì non pubblichiamo: "
     "preferiamo coprire bene un territorio che male mezzo Nord Italia."),
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
    url = METODO_URL
    titolo = "Come verifichiamo gli eventi | DAOP"
    descr = ("Chi inserisce gli eventi su DAOP, da dove arrivano, come li verifichiamo e "
             "ogni quanto aggiorniamo le schede per le famiglie di Alessandria e Asti.")

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
         "areaServed": ["Alessandria", "Asti", "Piemonte"],
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
<article class="ev-wrap">
  <div class="ev-crumb" role="navigation" aria-label="Percorso">
    <a href="/">Home</a> › <span>Come verifichiamo gli eventi</span>
  </div>
  <header class="ev-head">
    <h1>Come DAOP sceglie e verifica gli eventi</h1>
    <p class="ev-when">Il metodo dietro l'agenda di Alessandria e Asti</p>
  </header>

  <p>DAOP non è un aggregatore automatico. Ogni evento che leggi sul sito è stato scelto
  e inserito da una persona che vive in questo territorio, con data, luogo, orario,
  prezzo e fascia d'età controllati prima della pubblicazione. Questa pagina spiega chi
  lo fa, come, e ogni quanto.</p>

  <div class="met-num">
    <div><b>{len(events)}</b><span>eventi in agenda adesso</span></div>
    <div><b>{schede}</b><span>schede evento dedicate</span></div>
    <div><b>{comuni}</b><span>comuni coperti</span></div>
    <div><b>2</b><span>province: Alessandria e Asti</span></div>
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
  <p><a href="/eventi.html">L'agenda eventi</a> di Alessandria e Asti ·
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


def inject(tipo_opts, lista, jsonld):
    s = open(HTML_PATH, encoding="utf-8").read()
    s, n1 = re.subn(r'(<!-- EVENTI-TIPO:START -->\n).*?(\n *<!-- EVENTI-TIPO:END -->)',
                    lambda m: m.group(1) + tipo_opts + m.group(2), s, count=1, flags=re.S)
    s, n2 = re.subn(r'(<!-- EVENTI-LISTA:START -->\n).*?(\n *<!-- EVENTI-LISTA:END -->)',
                    lambda m: m.group(1) + lista + m.group(2), s, count=1, flags=re.S)
    s, n3 = re.subn(r'<script type="application/ld\+json" id="eventi-jsonld">.*?</script>',
                    lambda _: jsonld, s, count=1, flags=re.S)
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


def update_sitemap(slugs=()):
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

    s, n = re.subn(
        r'(<loc>https://www\.daop\.it/eventi\.html</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + today + m.group(2), s, count=1)
    print(f"[genera_eventi] sitemap: lastmod eventi.html -> {today}" if n == 1
          else "[genera_eventi] sitemap: blocco eventi.html non trovato, salto")
    # Una sola scrittura alla fine: se il lastmod non matcha non dobbiamo
    # comunque perdere il blocco delle pagine evento appena rigenerato.
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)


def main():
    events = normalize(fetch_rows())
    segnala_doppioni(events)
    assegna_ancore(events)
    tipo_opts, lista = render(events)
    jsonld = render_jsonld(events)
    inject(tipo_opts, lista, jsonld)
    inject_home(render_home(events))
    slugs = scrivi_pagine(events)
    scrivi_metodo(events)
    # aggiorna l'istantanea committata
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()
            if k not in CAMPI_DAOP or (v or '').strip()} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap(slugs)
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
