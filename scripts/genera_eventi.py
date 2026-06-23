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
import os, re, csv, io, json, html, datetime, urllib.request, sys

SHEET_ID = "186XuLRXD2DXHL5CVy1vgNfmbEhpSbpW5pSgr4ARhugs"
DEFAULT_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Eventi"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(ROOT, "eventi.html")
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
    url = os.environ.get("EVENTI_CSV_URL", DEFAULT_CSV)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "daop-eventi-bot"})
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
            manifest=d.get('Manifestazione', ''), d_start=di, d_end=df,
        ))
    events.sort(key=lambda e: (e['d_start'], e['nome']))
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


def esc(s):
    return html.escape((s or '').strip())


def trunc(s, n):
    s = (s or '').strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


PIN_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
CLOCK_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
USER_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>'

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
    cards, present = [], set()
    for e in events:
        slug, emoji, catlabel = bucket(e)
        present.add(slug)
        d = e['d_start']
        if e['d_end'] != d:
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
        cards.append(f'''      <article class="event-card" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}" style="--cat-color:{color};--cat-tint:{tint}">
        <div class="ev-top">
          <span class="ev-icon" role="img" aria-label="{esc(catlabel)}">{emoji}</span>
          <span class="ev-cat">{esc(catlabel)}</span>
          <span class="ev-date"><span class="d">{d.day:02d}</span><span class="m">{MESI[d.month-1]}</span></span>
        </div>
        <h3>{esc(trunc(e['nome'], 90))}</h3>
        <div class="event-meta">
          <span>{PIN_SVG} {luogo}</span>
          <span>{CLOCK_SVG} {esc(datestr)}</span>{eta_html}
        </div>
        <p class="event-desc">{esc(trunc(e['descr'], 170))}</p>
        <div class="event-foot">
          {price}
          {manifest}
        </div>
      </article>''')

    chips = ['      <button class="filter-chip active" data-filter="all">Tutte le categorie</button>']
    for s in ORDER:
        if s in present:
            chips.append(f'      <button class="filter-chip" data-filter="{s}">{LABELS[s]}</button>')
    cat_filter = ('    <div class="event-filters" data-group="category" aria-label="Filtra per categoria">\n'
                  + '\n'.join(chips) + '\n    </div>')
    grid = '    <div class="events-grid" id="events-grid">\n\n' + '\n\n'.join(cards) + '\n\n    </div>'
    return cat_filter, grid


def parse_times(ora):
    """Estrae fino a due orari HH:MM (inizio/fine) dal campo Ora."""
    return [f"{int(h):02d}:{m}" for h, m in re.findall(r'(\d{1,2})[:.](\d{2})', ora or '')][:2]


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

    obj = {
        "@type": "Event",
        "name": (e['nome'] or '').strip(),
        "startDate": start,
        "endDate": end,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": city or e['prov'],
            "address": address,
        },
        "image": [DEFAULT_IMG],
        "url": PAGE_URL,
        "organizer": {"@type": "Organization", "name": "DAOP APS", "url": SITE_URL},
    }
    descr = (e['descr'] or '').strip()
    if descr:
        obj["description"] = descr

    pz = (e['prezzo'] or '').lower()
    if any(k in pz for k in FREE_KW):
        obj["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "EUR",
                         "availability": "https://schema.org/InStock", "url": PAGE_URL}
    elif (e['prezzo'] or '').strip():
        obj["offers"] = {"@type": "Offer", "availability": "https://schema.org/InStock",
                         "url": PAGE_URL}
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
    cat_filter, grid = render(events)
    jsonld = render_jsonld(events)
    inject(cat_filter, grid, jsonld)
    # aggiorna l'istantanea committata
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap()
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
