#!/usr/bin/env python3
"""
Genera/aggiorna la sezione eventi di eventi.html a partire dal foglio Google
"luoghi" (tab "eventi"). Pensato per girare in GitHub Actions ogni notte.

Fonte dati (in ordine di priorità):
  1. URL CSV in EVENTI_CSV_URL (es. export "Pubblica sul web" del tab eventi)
  2. URL CSV gviz di default (richiede foglio condiviso "chiunque con il link")
  3. data/eventi.json (istantanea committata, fallback se la rete non è disponibile)

Rigenera SOLO la griglia .events-grid e il gruppo di filtri per categoria
dentro eventi.html, tra gli ancoraggi esistenti. Tutto il resto resta intatto.
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


def bucket(e):
    cz = e['categoria'].lower()
    if 'sagra' in cz or 'festa' in cz or 'mercato' in cz or 'fiera' in cz: return 'feste', '🎪', 'Sagra & Festa'
    if 'spettacolo' in cz or 'teatro' in cz or 'cinema' in cz: return 'spettacoli', '🎭', 'Spettacolo'
    if 'musica' in cz: return 'musica', '🎵', 'Musica'
    if 'laborator' in cz or 'arte' in cz: return 'laboratori', '🎨', 'Laboratorio'
    if 'sport' in cz: return 'sport', '🚴', 'Sport'
    if 'cultura' in cz or 'natura' in cz: return 'cultura', '🏛️', 'Cultura'
    nd = (e['nome'] + ' ' + e['descr']).lower()
    if 'sagra' in nd or 'festa' in nd or 'fiera' in nd: return 'feste', '🎪', 'Sagra & Festa'
    if 'concerto' in nd or 'musica' in nd: return 'musica', '🎵', 'Musica'
    if 'laborator' in nd: return 'laboratori', '🎨', 'Laboratorio'
    if 'spettacol' in nd or 'teatro' in nd: return 'spettacoli', '🎭', 'Spettacolo'
    if any(k in nd for k in ['sport', 'corsa', 'pedalata', 'run', 'ciclo']): return 'sport', '🚴', 'Sport'
    return 'altro', '📍', 'Evento'


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

# colore (bordo/accent) e tinta (sfondo cerchietto emoji) per categoria
COLORS = {
    'feste': ('#e8954a', 'rgba(232,149,74,0.14)'),
    'spettacoli': ('#6c63a6', 'rgba(108,99,166,0.14)'),
    'laboratori': ('#6ba5a8', 'rgba(107,165,168,0.16)'),
    'musica': ('#c9a227', 'rgba(201,162,39,0.16)'),
    'sport': ('#1d9e75', 'rgba(29,158,117,0.14)'),
    'cultura': ('#4a90b9', 'rgba(74,144,185,0.14)'),
    'altro': ('#7e8c99', 'rgba(126,140,153,0.16)'),
}


def render(events):
    today = datetime.date.today()
    cards, present = [], set()
    for e in events:
        slug, emoji, catlabel = bucket(e)
        present.add(slug)
        d = e['d_start']
        ongoing = d < today  # già iniziato ma non ancora finito (filtrato in normalize)
        if ongoing:
            de = e['d_end']
            datestr = ("In corso · ultimo giorno" if de == today
                       else f"In corso · fino al {de.day} {MESI[de.month-1]}")
        elif e['d_end'] != d:
            de = e['d_end']
            datestr = f"dal {d.day} {MESI[d.month-1]} al {de.day} {MESI[de.month-1]}"
        else:
            datestr = f"{d.day} {MESI[d.month-1]} {d.year}"
        if e['ora']:
            datestr += f" · {trunc(e['ora'], 28)}"
        luogo = (esc(e['citta']) + f" ({e['prov']})") if e['citta'] else e['prov']
        pz = (e['prezzo'] or '').lower()
        if any(k in pz for k in ['gratuito', 'gratis', 'libero', 'ingresso libero']):
            price = '<span class="event-price free">Gratuito</span>'
        elif e['prezzo']:
            price = f'<span class="event-price">{esc(trunc(e["prezzo"], 32))}</span>'
        else:
            price = '<span></span>'
        eta = esc(trunc(e['eta'], 26)) if e['eta'] else ''
        eta_html = f'\n          <span>{USER_SVG} {eta}</span>' if eta else ''
        manifest = f'<span class="event-tag">{esc(trunc(e["manifest"], 40))}</span>' if e['manifest'] else ''
        color, tint = COLORS.get(slug, COLORS['altro'])
        acts = []
        murl = maps_url(e)
        if murl:
            acts.append(f'<a class="event-act" href="{murl}" target="_blank" rel="noopener">{NAV_SVG} Come arrivare</a>')
        acts.append(f'<a class="event-act" href="{gcal_url(e)}" target="_blank" rel="noopener">{CAL_SVG} Calendario</a>')
        actions = '\n        <div class="event-actions">\n          ' + '\n          '.join(acts) + '\n        </div>'
        # In alto a destra: normalmente il riquadro data; per gli eventi in corso
        # un badge "In corso" (la data di inizio è passata e confonderebbe).
        if ongoing:
            datebox = '<span class="ev-live">In corso</span>'
        else:
            datebox = f'<span class="ev-date"><span class="d">{d.day:02d}</span><span class="m">{MESI[d.month-1]}</span></span>'
        cover_url = loc_path(e['loc'])
        cover = (f'''        <a class="ev-cover" href="{cover_url}" target="_blank" rel="noopener" aria-label="Apri la locandina di {esc(e['nome'])}">
          <img src="{cover_url}" alt="Locandina: {esc(trunc(e['nome'], 70))}" loading="lazy" decoding="async">
        </a>
''' if cover_url else '')
        cards.append(f'''      <article class="event-card{' has-cover' if cover_url else ''}{' is-ongoing' if ongoing else ''}" id="{e.get('anchor', '')}" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}" style="--cat-color:{color};--cat-tint:{tint}">
{cover}        <div class="ev-top">
          <span class="ev-icon" role="img" aria-label="{esc(catlabel)}">{emoji}</span>
          <span class="ev-cat">{esc(catlabel)}</span>
          {datebox}
        </div>
        <h3>{esc(trunc(e['nome'], 90))}</h3>
        <div class="event-meta">
          <span>{PIN_SVG} {luogo}</span>
          <span>{CLOCK_SVG} {esc(datestr)}</span>{eta_html}
        </div>
        <p class="event-desc">{esc(e['descr'])}</p>
        <button class="event-readmore" type="button" hidden>Leggi tutto</button>
        <div class="event-foot">
          {price}
          {manifest}
        </div>{actions}
      </article>''')

    chips = ['      <button class="filter-chip active" data-filter="all">Tutte le categorie</button>']
    for s in ORDER:
        if s in present:
            chips.append(f'      <button class="filter-chip" data-filter="{s}">{LABELS[s]}</button>')
    cat_filter = ('    <div class="event-filters" data-group="category" aria-label="Filtra per categoria">\n'
                  + '\n'.join(chips) + '\n    </div>')
    grid = '    <div class="events-grid" id="events-grid">\n\n' + '\n\n'.join(cards) + '\n\n    </div>'
    return cat_filter, grid


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
        slug, emoji, catlabel = bucket(e)
        d = e['d_start']
        ongoing = d < today
        datebox = ('<span class="he-live">In corso</span>' if ongoing else
                   f'<span class="he-date"><span class="d">{d.day:02d}</span>'
                   f'<span class="m">{MESI[d.month-1]}</span></span>')
        color, tint = COLORS.get(slug, COLORS['altro'])
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
        cards.append(f'''      <a class="he-card" href="{href}" style="--cat-color:{color};--cat-tint:{tint}">
{cover}        <div class="he-body">
          <div class="he-top">
            <span class="he-icon" role="img" aria-label="{esc(catlabel)}">{emoji}</span>
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


def event_jsonld(e):
    """Costruisce un oggetto schema.org/Event per un singolo evento."""
    times = parse_times(e['ora'])
    start = e['d_start'].isoformat()
    if times:
        start += f"T{times[0]}"
    end = e['d_end'].isoformat()
    if len(times) > 1:
        end += f"T{times[1]}"
    elif times:
        end += f"T{times[0]}"

    city = (e['citta'] or '').strip()
    address = {"@type": "PostalAddress", "addressCountry": "IT"}
    if city:
        address["addressLocality"] = city
    if e['prov']:
        address["addressRegion"] = e['prov']
    venue = (e.get('luogo') or '').strip()
    if venue:
        address["streetAddress"] = venue
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
        "organizer": {"@type": "Organization", "name": "DAOP APS", "url": SITE_URL},
    }
    descr = (e['descr'] or '').strip()
    if descr:
        obj["description"] = descr

    # performer: campo consigliato da Google per gli Event (qui l'organizzazione)
    obj["performer"] = {"@type": "Organization", "name": "DAOP APS"}

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
    graph = [event_jsonld(e) for e in events]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph},
                         ensure_ascii=False, indent=2)
    return ('<script type="application/ld+json" id="eventi-jsonld">\n'
            + payload + '\n</script>')


def inject(cat_filter, grid, jsonld):
    s = open(HTML_PATH, encoding="utf-8").read()
    s, n1 = re.subn(r'    <div class="event-filters" data-group="category".*?</div>',
                    cat_filter, s, count=1, flags=re.S)
    s, n2 = re.subn(r'    <div class="events-grid" id="events-grid">.*?</div>\s*(?=<p class="events-empty")',
                    grid + "\n    ", s, count=1, flags=re.S)
    s, n3 = re.subn(r'<script type="application/ld\+json" id="eventi-jsonld">.*?</script>',
                    lambda _: jsonld, s, count=1, flags=re.S)
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise SystemExit(f"Ancoraggi non trovati in eventi.html (filtro={n1}, griglia={n2}, json-ld={n3})")
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


def update_sitemap():
    """Porta il <lastmod> di eventi.html nella sitemap alla data odierna.
    Il commit avviene (dal workflow) solo se eventi.html è davvero cambiato,
    così la data riflette una modifica reale dei contenuti."""
    if not os.path.exists(SITEMAP_PATH):
        return
    today = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    s, n = re.subn(
        r'(<loc>https://www\.daop\.it/eventi\.html</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + today + m.group(2), s, count=1)
    if n == 1:
        open(SITEMAP_PATH, "w", encoding="utf-8").write(s)
        print(f"[genera_eventi] sitemap: lastmod eventi.html -> {today}")
    else:
        print("[genera_eventi] sitemap: blocco eventi.html non trovato, salto")


def main():
    events = normalize(fetch_rows())
    assegna_ancore(events)
    cat_filter, grid = render(events)
    jsonld = render_jsonld(events)
    inject(cat_filter, grid, jsonld)
    inject_home(render_home(events))
    # aggiorna l'istantanea committata
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap()
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
