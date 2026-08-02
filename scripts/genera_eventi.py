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
import os, re, csv, io, json, html, datetime, urllib.request, urllib.parse, unicodedata, sys

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
        # rimappa lo snapshot sulle stesse chiavi del foglio
        return [{
            'Nome': e['nome'], 'Data Inizio': e['di'], 'Data fine': e['df'],
            'Ora': e['ora'], 'Città': e['citta'], 'Provincia': e['prov'],
            'Categoria': e['categoria'], 'Età': e['eta'], 'Prezzo': e['prezzo'],
            'Descrizione': e['descr'], 'Manifestazione': e.get('manifest', ''),
            'Locandina': e.get('loc', ''), 'Luogo': e.get('luogo', ''),
            'Indirizzo Completo': e.get('indirizzo', ''),
        } for e in snap]


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
                    f'{ARROW_SVG} Scheda completa</a>')
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

    opts = ['      <option value="all">Tutte le categorie</option>']
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
    descr = (e['descr'] or '').strip()
    if descr:
        obj["description"] = descr

    # offers: includiamo price + priceCurrency + validFrom (richiesti per un'offerta valida).
    # Per gli eventi "a pagamento" senza una cifra nota omettiamo offers, così da non
    # generare un'offerta incompleta (causa degli avvisi di Search Console).
    pz = (e['prezzo'] or '').lower()
    if any(k in pz for k in FREE_KW):
        price = "0"
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


def aggiorna_registro(events):
    """Fonde gli eventi correnti nel registro persistente. Non rimuove nulla."""
    reg = carica_registro()
    oggi = datetime.date.today().isoformat()
    nuovi = 0
    for e in events:
        if not ha_pagina(e):
            continue
        s = slug_evento(e)
        rec = reg.get(s)
        if rec is None:
            rec, nuovi = {'first_seen': oggi}, nuovi + 1
        rec.update({k: (v.isoformat() if isinstance(v, datetime.date) else v)
                    for k, v in e.items()})
        rec['slug'] = s
        rec['last_seen'] = oggi
        reg[s] = rec
    with open(REGISTRO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return reg, nuovi


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
.ev-actions{display:flex;flex-wrap:wrap;gap:12px;margin:28px 0 8px}
.ev-over{border:1px solid #e5c07b;background:#fdf6e6;border-radius:14px;padding:16px 18px;margin:22px 0}
.ev-over strong{display:block;margin-bottom:4px}
@media (prefers-color-scheme:dark){.ev-over{background:#2e2717;border-color:#6b5a2e}}
"""


def render_pagina(rec, css, nav, foot, oggi):
    """HTML completo di una pagina evento."""
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
        bottoni = [f'<a class="btn btn-navy" href="{esc(gcal_url(e))}" target="_blank" rel="noopener">Aggiungi al calendario</a>']
        if maps_url(e):
            bottoni.append(f'<a class="btn" href="{esc(maps_url(e))}" target="_blank" rel="noopener">Come arrivare</a>')
        bottoni.append('<a class="btn" href="/eventi.html">Altri eventi in zona</a>')
        azioni = '<div class="ev-actions">' + "".join(bottoni) + '</div>'

    ev_obj = event_jsonld(e, url)
    if concluso:
        ev_obj["eventStatus"] = "https://schema.org/EventScheduled"
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": nome, "item": url},
        ],
    }
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": [ev_obj, breadcrumb]},
                        ensure_ascii=False, indent=2)

    corpo = "".join(f"<p>{esc(p)}</p>" for p in re.split(r'\n{2,}', descr_txt) if p.strip())

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo_seo)}</title>
<meta name="description" content="{esc(meta_d)}">
<meta name="robots" content="index, follow">
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
  {azioni}
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
    """Genera/aggiorna le pagine evento. Restituisce la lista degli slug attivi."""
    reg, nuovi = aggiorna_registro(events)
    if not reg:
        print("[genera_eventi] nessuna pagina evento da generare")
        return []
    os.makedirs(PAGINE_DIR, exist_ok=True)
    css, nav, foot = _guscio()
    oggi = datetime.date.today()
    conclusi = 0
    for slug, rec in reg.items():
        path = os.path.join(PAGINE_DIR, f"{slug}.html")
        nuovo = render_pagina(rec, css, nav, foot, oggi)
        if datetime.date.fromisoformat(rec['d_end']) < oggi:
            conclusi += 1
        # riscriviamo solo se cambia: evita commit rumorosi ogni notte
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
    print(f"[genera_eventi] pagine evento: {len(reg)} totali "
          f"({nuovi} nuove, {conclusi} concluse)")
    return sorted(reg)


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
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
            for sl in slugs)
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
    assegna_ancore(events)
    tipo_opts, lista = render(events)
    jsonld = render_jsonld(events)
    inject(tipo_opts, lista, jsonld)
    inject_home(render_home(events))
    slugs = scrivi_pagine(events)
    # aggiorna l'istantanea committata
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap(slugs)
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
