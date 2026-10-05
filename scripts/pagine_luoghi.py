#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LE PAGINE DEI LUOGHI SPONSORIZZATI: /luoghi/<slug>.html (05/10/2026).

Il modello, deciso con Patrick e Giovanni lo stesso giorno: LISTA GRATUITA,
PAGINA A PAGAMENTO. La riga in /luoghi.html c'e' per tutti; chi paga ha in piu'
una pagina sua, con un indirizzo da dare al cliente ("mettila sul tuo
Instagram"), che Google puo' mettere in alto per il NOME del posto (dove DAOP
rende di piu': posti poco famosi, poca concorrenza) e che fa da bersaglio ai
redirect pagina-per-pagina del vecchio sito di Giovanni. Il riquadro
"Sponsorizzati" in cima a /luoghi.html resta finche' sono pochi: con dieci o
quindici clienti a rotazione su tre posti non lo vedrebbe piu' nessuno, e la
pagina invece vale uguale con cento.

LA PAGINA STA SOPRA LE LISTE. La riga gratuita sta nella lista del suo Ruolo
(la pagina Luoghi pubblica solo le `meta`); la pagina no: un campeggio e'
`servizio` (ci si va per dormire), non ha la riga in /luoghi.html, ma se paga
ha la sua pagina. Per questo qui si parte dal catalogo PRIMA di solo_mete().

UN SOGGETTO, UNA PAGINA. Se il posto ha gia' la pagina di societa' dei corsi
(data/realta-pagine.json, chiave = slug del nome, come le societa'), non se ne
fa una seconda: la riga linka quella. Lo stampo unico (posto + corsi +
servizi) si fa quando arriva il primo soggetto che e' davvero tutte e due.

QUANDO LO SPONSORIZZATO SCADE la pagina non sparisce: diventa un rimando alla
riga in /luoghi.html (o al suo comune), noindex e fuori sitemap. Chi aveva il
link non trova un errore, e Google sposta il segnale sulla lista. Per sapere
quali pagine sono esistite c'e' data/luoghi-pagine.json, che non dimentica.

I CLIC. daop-track.js attribuisce un clic al posto risalendo a `[data-org]`: la
pagina stampa `data-org` = l'id della riga in /luoghi.html (lg-...), cosi'
mappe, telefono e sito cliccati QUI finiscono nei report sulla stessa riga dei
clic fatti nell'elenco.
"""
import datetime
import json
import math
import os
import re

import genera_luoghi as L

G = L.G

DIR = 'luoghi'
DIR_PATH = os.path.join(L.ROOT, DIR)
REGISTRO = os.path.join(L.ROOT, 'data', 'luoghi-pagine.json')
REALTA = os.path.join(L.ROOT, 'data', 'realta-pagine.json')
VICINI_KM = 20
VICINI_MAX = 4

CSS_LUOGO = """
.pl-wrap{max-width:820px;margin:0 auto;padding:0 20px 48px}
.pl-crumb{font-size:.85rem;margin-bottom:10px}
.page-hero .pl-crumb{color:rgba(255,255,255,.62)}
.page-hero .pl-crumb a{color:rgba(255,255,255,.82)}
.pl-spons{display:inline-block;font-size:.7rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;padding:3px 9px;border-radius:999px;margin:0 0 10px;
  background:rgba(255,255,255,.16);color:#fff}
.pl-sub{margin:6px 0 0;font-size:1.02rem;opacity:.85}
.pl-foto{display:block;width:100%;max-height:440px;object-fit:cover;border-radius:16px;
  margin:24px 0 6px;background:var(--cream,#f5f0e8)}
.pl-wrap .lg-credito{max-width:none;margin:0 0 4px}
.pl-gal{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px;margin:14px 0 0}
.pl-gal img{width:100%;height:110px;object-fit:cover;border-radius:10px;background:var(--cream,#f5f0e8)}
.pl-descr{margin:20px 0 0;font-size:1.04rem;line-height:1.65}
.pl-h{font-size:1.22rem;margin:34px 0 12px}
.pl-cose{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.pl-cose li{padding:6px 12px;border-radius:999px;background:#fff;
  border:1px solid rgba(0,0,0,.09);font-size:.92rem}
.pl-dati{display:grid;grid-template-columns:max-content 1fr;gap:8px 18px;margin:0;
  padding:16px 18px;background:#fff;border:1px solid rgba(0,0,0,.09);border-radius:14px}
.pl-dati dt{font-weight:700}
.pl-dati dd{margin:0}
.pl-act{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 0}
.pl-act a{display:inline-block;padding:10px 16px;border-radius:999px;font-weight:700;
  font-size:.95rem;text-decoration:none;background:var(--navy,#1e3342);color:#fff}
.pl-act a.is-sec{background:#fff;color:var(--navy,#1e3342);border:1px solid rgba(0,0,0,.15)}
.pl-next{margin:0;padding:0;list-style:none}
.pl-next li{padding:10px 0;border-bottom:1px solid rgba(0,0,0,.08)}
.pl-next span{opacity:.7}
.pl-vicini{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}
.pl-vicini a{display:flex;gap:10px;align-items:center;padding:10px 12px;background:#fff;
  border:1px solid rgba(0,0,0,.09);border-radius:12px;text-decoration:none;color:inherit}
.pl-vicini b{display:block;font-size:.96rem}
.pl-vicini small{opacity:.7}
.pl-nota{margin:30px 0 0;font-size:.82rem;color:var(--text-light,#6b7280)}
.pl-torna{margin:18px 0 0;font-size:.95rem}
@media(max-width:520px){.pl-dati{grid-template-columns:1fr}.pl-dati dt{margin-top:6px}}
"""

# Le categorie del foglio sono al plurale ("Fattorie Didattiche"), perche' sono
# il nome di un GRUPPO; il titolo di una pagina parla di UN posto. Quelle che
# mancano qui restano come sono: meglio un plurale che un singolare inventato.
SINGOLARE = {
    'fattorie didattiche': 'Fattoria didattica', 'campeggi': 'Campeggio',
    'agriturismi': 'Agriturismo', 'musei & luoghi di interesse': 'Museo',
    'parchi urbani': 'Parco', 'aree picnic': 'Area picnic', 'laghi': 'Lago',
    'piscine & parchi acquatici': 'Piscina', 'parchi avventura': 'Parco avventura',
    'parchi giochi': 'Parco giochi', 'parchi giochi indoor': 'Parco giochi al chiuso',
    'biblioteche': 'Biblioteca', 'teatri': 'Teatro', 'rifugi': 'Rifugio',
    'panchine giganti': 'Panchina gigante', 'sentieri & passeggiate': 'Sentiero',
    'hotel family': 'Hotel per famiglie',
}


def tipo_singolare(l):
    tipo = l.get('cat_sotto') or l.get('cat_nome') or 'Luogo'
    return SINGOLARE.get(tipo.strip().lower(), tipo)


def slug_pagina(l):
    """Lo slug della pagina: quello della riga senza il prefisso `lg-`.

    Lo STESSO della riga, e non uno nuovo, perche' e' la chiave che lega le
    due cose: l'ancora #lg-... in /luoghi.html, l'id nei report di GA4, e il
    rimando di quando lo sponsorizzato scade."""
    return l['slug'][3:] if l['slug'].startswith('lg-') else l['slug']


def href_pagina(slug):
    return f"/{DIR}/{slug}.html"


def km(a, b):
    try:
        la1, lo1, la2, lo2 = map(float, (a['lat'], a['lon'], b['lat'], b['lon']))
    except (TypeError, ValueError, KeyError):
        return None
    p = math.pi / 180
    h = (math.sin((la2 - la1) * p / 2) ** 2
         + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def vicini(l, elenco):
    """Le mete piu' vicine, per i link in coda. Solo la distanza ordina, e un
    tipo per volta: le panchine giganti sono 85 e stanno ovunque, e senza la
    regola "Nei dintorni" di Gabutti erano tre panchine su quattro."""
    out = []
    for x in elenco:
        if x.get('slug') == l.get('slug') or x.get('fonte') != 'catalogo':
            continue
        d = km(l, x)
        if d is not None and d <= VICINI_KM:
            out.append((d, x))
    out.sort(key=lambda t: t[0])
    tipi, scelti = set(), []
    for d, x in out:
        tipo = x.get('cat_sotto') or x.get('cat_nome')
        if tipo in tipi:
            continue
        tipi.add(tipo)
        scelti.append((d, x))
    return scelti[:VICINI_MAX]


def _tipo_schema(l):
    c = f"{l.get('cat_nome', '')} › {l.get('cat_sotto', '')}".lower()
    if 'campegg' in c:
        return 'Campground'
    if c.startswith('soggiorno'):
        return 'LodgingBusiness'
    return 'TouristAttraction'


def jsonld(l, url):
    o = {'@context': 'https://schema.org', '@type': _tipo_schema(l),
         'name': l['nome'], 'url': url}
    testo = l.get('descr_premium') or l.get('descr')
    if testo:
        o['description'] = testo
    if l.get('foto'):
        o['image'] = l['foto'][:5]
    o['address'] = {'@type': 'PostalAddress', 'addressLocality': l['comune'],
                    'addressRegion': 'Piemonte', 'addressCountry': 'IT'}
    if l.get('indirizzo'):
        o['address']['streetAddress'] = l['indirizzo']
    if l.get('cap'):
        o['address']['postalCode'] = l['cap']
    if l.get('lat') and l.get('lon'):
        o['geo'] = {'@type': 'GeoCoordinates', 'latitude': l['lat'], 'longitude': l['lon']}
    if l.get('tel'):
        o['telephone'] = l['tel']
    if L.url_sito(l.get('sito')):
        o['sameAs'] = [L.url_sito(l['sito'])]
    o['isAccessibleForFree'] = bool(l.get('gratuito'))
    return json.dumps(o, ensure_ascii=False, indent=1)


def _ritorno(l, elenco):
    """Dove si torna: la riga in /luoghi.html se c'e', se no il gruppo del suo
    comune, se no la pagina intera. Un campeggio (`servizio`) la riga non ce
    l'ha, e il suo comune puo' non avere nessuna meta."""
    slug = l['slug']
    if any(x.get('slug') == slug for x in elenco):
        return f"/luoghi.html#{slug}"
    if any(x['prov'] == l['prov'] and G.slugify(x['comune']) == G.slugify(l['comune'])
           for x in elenco):
        return f"/luoghi.html#{L.ancora_comune(l['prov'], l['comune'])}"
    return "/luoghi.html"


def pagina(l, elenco, css, nav, foot):
    e = G.esc
    slug = slug_pagina(l)
    url = f"{G.SITE_URL}{href_pagina(slug)}"
    tipo = tipo_singolare(l)
    dove = G.a_citta(l['comune']).strip()
    # Gli spazi FUORI da G.esc(), che li toglie (stessa trappola di genera_corsi).
    sigla = f" ({l['prov']})" if l.get('prov') else ''
    titolo = f"{l['nome']}{G.a_citta(l['comune'])}: {tipo.lower()} per bambini | DAOP"
    testo = (l.get('descr_premium') or l.get('descr') or '').strip()
    descr = G.trunc(testo or f"{l['nome']}, {tipo.lower()} {dove}{sigla}.", 160)
    foto = l.get('foto') or []
    og = foto[0] if foto else G.DEFAULT_IMG

    corpo = []
    if foto:
        corpo.append(f'<img class="pl-foto" src="{e(foto[0])}" alt="{e(l["nome"])}, '
                     f'{e(l["comune"])}" width="1200" height="800" decoding="async">')
        corpo.append(L.html_credito_foto(l.get('foto_autore'), l.get('foto_licenza')))
    if len(foto) > 1:
        corpo.append('<div class="pl-gal">' + ''.join(
            f'<img src="{e(u)}" alt="" loading="lazy" decoding="async" width="280" height="220">'
            for u in foto[1:5]) + '</div>')
    if testo:
        corpo.append(f'<p class="pl-descr">{e(testo)}</p>')

    visti, cose = set(), []
    for c in (l.get('pratici') or []) + (l.get('servizi') or []):
        if c and c.lower() not in visti:
            visti.add(c.lower())
            cose.append(c)
    if cose:
        corpo.append('<h2 class="pl-h">Cosa c\'è</h2>')
        corpo.append('<ul class="pl-cose">' + ''.join(f'<li>{e(c)}</li>' for c in cose[:16])
                     + '</ul>')

    dati = []
    if L._indirizzo_utile(l):
        dati.append(('Dove', e(f"{l['indirizzo']}, {l['comune']}") + sigla))
    else:
        dati.append(('Dove', e(l['comune']) + sigla))
    if l.get('orari'):
        dati.append(('Orari', e(l['orari'])))
    if l.get('prezzo'):
        dati.append(('Ingresso', e(l['prezzo'])))
    elif l.get('gratuito'):
        dati.append(('Ingresso', 'Gratuito'))
    et = L.eta_testo(l)
    if et:
        dati.append(('Età', et))
    dati.append(('Se piove', L.RIPARO_LABEL[l['riparo']]))
    if l.get('tel'):
        dati.append(('Telefono', e(l['tel'])))
    if l.get('email'):
        dati.append(('Email', f'<a href="mailto:{e(l["email"])}">{e(l["email"])}</a>'))
    corpo.append('<h2 class="pl-h">Informazioni e contatti</h2>')
    corpo.append('<dl class="pl-dati">' + ''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in dati)
                 + '</dl>')

    # Gli stessi bottoni della riga, con lo stesso rel: e' un link a pagamento.
    azioni = [f'<a href="{L.maps_href(l)}" target="_blank" rel="noopener">Come arrivare</a>']
    if l.get('tel'):
        primo = re.split(r'[,/;]', l['tel'])[0]
        num = ''.join(ch for ch in primo if ch.isdigit() or ch == '+')
        azioni.append(f'<a class="is-sec" href="tel:{e(num)}">Chiama</a>')
    sito = L.url_sito(l.get('sito'))
    if sito:
        testo_btn, _ = L.etichetta_sito(sito)
        azioni.append(f'<a class="is-sec" href="{e(sito)}" target="_blank" '
                      f'rel="noopener sponsored">{testo_btn}</a>')
    corpo.append(f'<div class="pl-act">{"".join(azioni)}</div>')

    prossimi = l.get('prossimi') or []
    if prossimi:
        corpo.append(f'<h2 class="pl-h">In programma {e(dove)}</h2>')
        corpo.append('<ul class="pl-next">' + ''.join(
            f'<li><a href="{p["href"]}">{e(G.trunc(p["nome"], 80))}</a> '
            f'<span>· {L.data_breve(p["d"])}</span></li>' for p in prossimi[:8]) + '</ul>')

    vic = vicini(l, elenco)
    if vic:
        corpo.append('<h2 class="pl-h">Nei dintorni</h2>')
        corpo.append('<div class="pl-vicini" data-cta="vicini">' + ''.join(
            f'<a href="/luoghi.html#{x["slug"]}"><span aria-hidden="true">{e(x.get("icona") or "📍")}</span>'
            f'<span><b>{e(x["nome"])}</b><small>{e(x.get("cat_sotto") or x.get("cat_nome") or "")}'
            f' · {e(x["comune"])} · {d:.0f} km</small></span></a>' for d, x in vic) + '</div>')

    corpo.append('<p class="pl-nota">Sponsorizzato: questa pagina la paga chi gestisce il '
                 'luogo. Non cambia l\'ordine dell\'elenco dei luoghi, che resta per comune. '
                 '<a href="/luoghi.html#come-ordiniamo">Come funziona</a>.</p>')
    torna = _ritorno(l, elenco)
    corpo.append(f'<p class="pl-torna"><a href="{torna}">← '
                 + (f'Tutti i luoghi {e(dove)}' if torna != '/luoghi.html' else 'Tutti i luoghi')
                 + '</a></p>')
    crumb_comune = (f' › <a href="{torna}">{e(l["comune"])}</a>' if torna != '/luoghi.html'
                    else '')

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titolo)}</title>
<meta name="description" content="{e(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(titolo)}">
<meta property="og:description" content="{e(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{e(og)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="daop:citta" content="{e(l['comune'])}">
<meta name="daop:provincia" content="{e(l.get('prov') or '')}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{G.GINETTO_CSS}{L.LUOGHI_CSS}{CSS_LUOGO}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld(l, url)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero">
  <div class="page-hero-inner">
    <div class="pl-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/luoghi.html">Luoghi</a>{crumb_comune} › <span>{e(l['nome'])}</span>
    </div>
    <span class="pl-spons">Sponsorizzato</span>
    <span class="section-label">{e(l['comune'])}{sigla} · {e(tipo)}</span>
    <h1>{e(l['nome'])}</h1>
    <p class="pl-sub">{e(tipo)} per bambini e famiglie {e(dove)}{sigla}</p>
  </div>
</header>
<article class="pl-wrap" data-org="{e(l['slug'])}" data-org-nome="{e(l['nome'])}">
{chr(10).join('  ' + c for c in corpo if c)}
{G.blocco_ecosistema('luoghi')}
</article>
{G.blocco_ginetto(l['comune'])}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def rimando(nome, verso):
    """La pagina di uno sponsorizzato SCADUTO: un rimando, non un 404.

    GitHub Pages non fa redirect lato server, quindi e' la forma che resta:
    meta refresh a zero piu' location.replace, noindex, canonical sul bersaglio.
    Google tratta il refresh immediato come un redirect permanente."""
    e = G.esc
    dest = f"{G.SITE_URL}{verso}"
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<title>{e(nome)} | DAOP</title>
<meta name="robots" content="noindex, follow">
<link rel="canonical" href="{e(dest)}">
<meta http-equiv="refresh" content="0; url={e(verso)}">
<script>location.replace({json.dumps(verso)});</script>
</head>
<body>
<p><a href="{e(verso)}">{e(nome)} su DAOP</a></p>
</body>
</html>
"""


def _leggi(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def candidati(base, elenco, agenda):
    """Gli sponsorizzati ATTIVI, anche quelli che la lista non pubblica.

    Chi sta nell'elenco si prende da li' (ha gia' slug ed eventi). Gli altri -
    un campeggio, un hotel - sono righe del catalogo prima di solo_mete(): lo
    slug si calcola come in unisci() e gli eventi si agganciano con la stessa
    chiave."""
    per_codice = {x.get('codice'): x for x in elenco if x.get('codice')}
    out = []
    for l in base:
        if not l.get('premium'):
            continue
        x = per_codice.get(l.get('codice'))
        if x is None:
            x = dict(l)
            x['slug'] = 'lg-' + G.slugify(f"{x['nome']} {x['comune']}")[:70]
            a = agenda.get(L._key(x['nome'], x['comune'])) or {}
            x['prossimi'] = a.get('prossimi') or []
        out.append(x)
    return out


def scrivi(base, elenco, agenda):
    """Scrive le pagine e i rimandi; torna {id della riga: href della pagina}.

    Il dizionario lo legge la riga di /luoghi.html per il link «La pagina di …».
    Un posto che ha gia' la pagina di societa' dei corsi non ne riceve una
    seconda: la riga linka quella."""
    oggi = datetime.date.today().isoformat()
    css, nav, foot = G._guscio()
    realta = _leggi(REALTA)
    registro = _leggi(REGISTRO)
    os.makedirs(DIR_PATH, exist_ok=True)
    link, attive = {}, set()
    for l in candidati(base, elenco, agenda):
        gia = realta.get(G.slugify(l['nome']))
        if gia and gia.get('url'):
            link[l['slug']] = gia['url']
            print(f"[pagine_luoghi] {l['nome']}: ha gia' la pagina dei corsi, linko quella")
            continue
        slug = slug_pagina(l)
        open(os.path.join(DIR_PATH, slug + '.html'), 'w', encoding='utf-8').write(
            pagina(l, elenco, css, nav, foot))
        attive.add(slug)
        link[l['slug']] = href_pagina(slug)
        voce = registro.setdefault(slug, {'nome': l['nome'], 'dal': oggi})
        voce.update({'nome': l['nome'], 'codice': l.get('codice', ''), 'ultimo': oggi,
                     'premium_al': l.get('premium_al', '')})
    spente = 0
    for slug, voce in registro.items():
        if slug in attive:
            continue
        verso = (f"/luoghi.html#lg-{slug}" if any(y.get('slug') == 'lg-' + slug for y in elenco)
                 else "/luoghi.html")
        open(os.path.join(DIR_PATH, slug + '.html'), 'w', encoding='utf-8').write(
            rimando(voce.get('nome', ''), verso))
        spente += 1
    with open(REGISTRO, 'w', encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False, indent=1, sort_keys=True)
    aggiorna_sitemap(sorted(attive))
    print(f"[pagine_luoghi] {len(attive)} pagine di sponsorizzati"
          + (f", {spente} scadute (rimandano alla lista)" if spente else ''))
    return link


def aggiorna_sitemap(slugs):
    """Il blocco delle pagine in sitemap: solo le attive, che sono `index`.

    Stessa forma del blocco CORSI di genera_corsi.py: un blocco suo fra due
    marcatori, riscritto per intero a ogni giro; vuoto = tolto."""
    if not os.path.exists(L.SITEMAP_PATH):
        return
    oggi = datetime.date.today().isoformat()
    s = open(L.SITEMAP_PATH, encoding='utf-8').read()
    re_blocco = re.compile(r'  <!-- LUOGHI-PAGINE:START.*?<!-- LUOGHI-PAGINE:END -->\n?', re.S)
    if not slugs:
        fuori = re_blocco.sub('', s)
        if fuori != s:
            open(L.SITEMAP_PATH, 'w', encoding='utf-8').write(fuori)
        return
    voci = [f"  <url>\n    <loc>{G.SITE_URL}{href_pagina(x)}</loc>\n"
            f"    <lastmod>{oggi}</lastmod>\n    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.6</priority>\n  </url>" for x in slugs]
    blocco = ("  <!-- LUOGHI-PAGINE:START (generato da scripts/pagine_luoghi.py — non "
              "modificare a mano) -->\n" + "\n".join(voci) + "\n  <!-- LUOGHI-PAGINE:END -->\n")
    if re_blocco.search(s):
        s = re_blocco.sub(lambda _: blocco, s)
    else:
        s = s.replace('</urlset>', blocco + '</urlset>')
    open(L.SITEMAP_PATH, 'w', encoding='utf-8').write(s)
