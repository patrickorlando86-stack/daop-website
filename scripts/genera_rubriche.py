#!/usr/bin/env python3
"""
Genera le pagine delle rubriche DAOP a partire dai testi in contenuti/rubriche/.

Fonte dati:
  - data/rubriche.json          metadati delle rubriche, degli autori e delle CTA
  - contenuti/rubriche/<slug>/*.md   un file per articolo, con frontmatter

Produce:
  - rubriche/<slug>.html        una pagina per articolo
  - rubriche.html               l'indice, dentro i marker RUBRICHE-LISTA e
                                RUBRICHE-JSONLD (il resto della pagina resta
                                intatto: nav, hero, CTA e footer sono a mano)
  - sitemap.xml                 dentro i marker RUBRICHE:START/END

Un articolo esce solo quando arriva la sua data. I pezzi con data futura
restano nel repository, pronti, e compaiono da soli alla run successiva alla
data indicata: e' il modo di tenere un piano editoriale mensile su un sito
statico senza pubblicare articoli datati domani.

Per aggiungere un pezzo: crea il .md, rilancia lo script. Nient'altro.
"""
import os, re, json, html, datetime, unicodedata, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(ROOT, "data", "rubriche.json")
TESTI_DIR = os.path.join(ROOT, "contenuti", "rubriche")
HUB_PATH = os.path.join(ROOT, "rubriche.html")
PAGINE_DIR = os.path.join(ROOT, "rubriche")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")
SITE_URL = "https://www.daop.it"
DEFAULT_IMG = f"{SITE_URL}/assets/images/headerdaop.jpg"

MESI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
        'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


def esc(s):
    return html.escape(str(s or ''), quote=True)


def trunc(s, n):
    s = re.sub(r'\s+', ' ', str(s or '')).strip()
    return s if len(s) <= n else s[:n - 1].rsplit(' ', 1)[0] + '…'


def slugify(s):
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')


def data_estesa(d):
    return f"{d.day} {MESI[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- frontmatter

def leggi_md(path):
    """Restituisce (meta, corpo). Il frontmatter e' un blocco fra --- con
    coppie 'chiave: valore' su una riga sola: non serve YAML vero e non
    vogliamo una dipendenza esterna per tre campi."""
    testo = open(path, encoding='utf-8').read().replace('\r\n', '\n')
    m = re.match(r'\A---\n(.*?)\n---\n(.*)\Z', testo, re.S)
    if not m:
        raise SystemExit(f"[rubriche] frontmatter mancante in {path}")
    meta = {}
    for riga in m.group(1).split('\n'):
        if not riga.strip() or riga.lstrip().startswith('#'):
            continue
        k, _, v = riga.partition(':')
        meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


# ------------------------------------------------------------------ markdown

def _inline(s):
    """Grassetto, corsivo e link. L'escape viene prima, cosi' un < nel testo
    resta un < e non apre un tag."""
    s = esc(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)',
               lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    return s


def md2html(corpo):
    """Sottoinsieme di Markdown che serve a questi testi: ## titoli, elenchi
    puntati e numerati, citazioni, paragrafi. Niente di piu'."""
    out = []
    for blocco in re.split(r'\n\s*\n', corpo):
        righe = [r for r in blocco.split('\n') if r.strip()]
        if not righe:
            continue
        if righe[0].startswith('## '):
            out.append(f"<h2>{_inline(righe[0][3:].strip())}</h2>")
        elif all(r.lstrip().startswith('> ') for r in righe):
            testo = ' '.join(r.lstrip()[2:].strip() for r in righe)
            out.append(f"<blockquote>{_inline(testo)}</blockquote>")
        elif all(r.lstrip().startswith('- ') for r in righe):
            voci = "".join(f"<li>{_inline(r.lstrip()[2:].strip())}</li>" for r in righe)
            out.append(f"<ul>{voci}</ul>")
        elif all(re.match(r'\s*\d+\.\s', r) for r in righe):
            voci = "".join(f"<li>{_inline(re.sub(r'^\s*\d+\.\s*', '', r))}</li>" for r in righe)
            out.append(f"<ol>{voci}</ol>")
        else:
            out.append(f"<p>{_inline(' '.join(r.strip() for r in righe))}</p>")
    return "\n    ".join(out)


# --------------------------------------------------------------------- dati

def carica():
    with open(DATA_PATH, encoding='utf-8') as fh:
        cfg = json.load(fh)
    rubriche = {r['slug']: r for r in cfg['rubriche']}
    autori = {a['slug']: a for a in cfg['autori']}
    articoli = []
    for rslug in rubriche:
        cartella = os.path.join(TESTI_DIR, rslug)
        if not os.path.isdir(cartella):
            print(f"[rubriche] nessuna cartella per '{rslug}', salto")
            continue
        for nome in sorted(os.listdir(cartella)):
            if not nome.endswith('.md'):
                continue
            meta, corpo = leggi_md(os.path.join(cartella, nome))
            try:
                data = datetime.date.fromisoformat(meta['data'])
            except (KeyError, ValueError):
                raise SystemExit(f"[rubriche] data mancante o non valida in {nome}")
            # Lo slug della URL viene dal nome del file senza il prefisso di
            # data: il prefisso serve solo a tenere i file in ordine sul disco.
            articoli.append({
                'rubrica': rslug,
                'slug': slugify(re.sub(r'^\d{4}-\d{2}-', '', nome[:-3])),
                'data': data,
                'titolo': meta.get('titolo', '').strip(),
                'sommario': meta.get('sommario', '').strip(),
                'tag': [t.strip() for t in meta.get('tag', '').split(',') if t.strip()],
                'cta': meta.get('cta', '').strip(),
                'verificare': [v.strip() for v in meta.get('verificare', '').split(';') if v.strip()],
                'corpo': corpo,
                'file': nome,
            })
    dupe = {a['slug'] for a in articoli if [x['slug'] for x in articoli].count(a['slug']) > 1}
    if dupe:
        raise SystemExit(f"[rubriche] slug duplicati fra rubriche diverse: {', '.join(sorted(dupe))}")
    articoli.sort(key=lambda a: a['data'], reverse=True)
    return cfg, rubriche, autori, articoli


# -------------------------------------------------------------------- guscio

def guscio():
    """CSS, nav e footer presi da rubriche.html a ogni run, con i link resi
    root-relative perche' le pagine articolo stanno in /rubriche/. Stessa
    scelta di genera_eventi.py: estrarre invece di duplicare tiene le
    sottopagine allineate quando la pagina madre cambia."""
    s = open(HUB_PATH, encoding='utf-8').read()
    nav = re.search(r'<!-- NAV -->.*?</div>\s*(?=\n<main)', s, re.S)
    foot = re.search(r'<footer>.*?</footer>', s, re.S)
    sprite = re.search(r'<svg xmlns[^>]*style="display:none".*?</svg>', s, re.S)
    css = re.findall(r'<style[^>]*>(.*?)</style>', s, re.S)
    if not nav or not foot or not sprite:
        raise SystemExit("[rubriche] nav, footer o sprite non trovati in rubriche.html")

    def rooted(frag):
        frag = re.sub(r'(href|src)="(?!https?://|/|#|mailto:|tel:)',
                      lambda m: f'{m.group(1)}="/', frag)
        # I marker delle voci che compaiono e spariscono — la stagione dei
        # centri, i corsi quando stanno fuori dall'indice — servono solo dove la
        # nav e' scritta a mano (qui: rubriche.html, che aggiorna_nav()
        # riscrive). Nelle pagine generate la voce e' gia' risolta. Questo
        # guscio e' gemello di quello di genera_eventi.py e la riga sta anche
        # la': trovata da tests/porte.js, che ha contato 15 pagine rubriche con
        # i commenti dentro dopo la prima run — ed e' successo di nuovo il
        # 21/08/2026 coi marker dei corsi, cioe' la stessa prova ha ripreso lo
        # stesso difetto sul secondo marker. Se nasce un terzo generatore con un
        # guscio suo, e' questa la riga da ricordare.
        frag = re.sub(
            r'<!-- (?:NAV|MM|HERO)-(?:CENTRI|CORSI):(?:START|END) -->', '', frag)
        return frag.replace(' class="active"', '')

    # Anche le url() del CSS: la texture della .page-hero in rubriche.html e'
    # url('assets/images/...') senza slash, e da /rubriche/ risponde 404.
    css_txt = re.sub(r"url\((['\"]?)(?!https?://|/|data:)",
                     lambda m: f"url({m.group(1)}/", "\n".join(css))
    return css_txt, rooted(nav.group(0)), rooted(foot.group(0)), sprite.group(0)


ARTICOLO_CSS = """
/* La nav del sito e' position:fixed: senza spazio in cima ci finisce sotto
   il breadcrumb e mezzo H1. Stessi valori della .page-hero. */
.art-wrap{max-width:760px;margin:0 auto;padding:148px 20px 40px}
@media(max-width:600px){.art-wrap{padding:120px 18px 32px}}
/* La barra scura in cima e' la .page-hero delle altre pagine del sito (il CSS
   arriva gia' copiato da rubriche.html): occhiello, titolo e sommario ci
   stanno dentro, la firma dell'autore resta sul bianco perche' le sue righe
   di separazione su fondo navy sparivano. */
.art-hero{padding:148px 24px 56px;text-align:left}
.art-hero .page-hero-inner{max-width:760px}
.art-hero .art-crumb{color:rgba(255,255,255,.62);opacity:1;margin:0 0 12px}
.art-hero .art-crumb a{color:rgba(255,255,255,.82)}
.art-hero .art-occhiello,.art-hero .art-occhiello.orange,
.art-hero .art-occhiello.gold{color:var(--gold,#c9a227)}
.art-hero .art-sommario{color:rgba(255,255,255,.74);margin:0}
@media(max-width:600px){.art-hero{padding:120px 20px 44px}}
/* Con la barra sopra, il corpo non deve piu' compensare la nav fissa. */
.art-wrap--hero{padding-top:36px}
@media(max-width:600px){.art-wrap--hero{padding-top:26px}}
.art-wrap--hero .art-meta{border-top:0;padding-top:0}
/* Il breadcrumb e' un div, non un <nav>: il CSS del sito ha nav{position:fixed}
   come selettore di elemento e lo incollerebbe sopra la barra. */
.art-crumb{position:static;font-size:.85rem;opacity:.72;margin:0 0 14px}
.art-crumb a{color:inherit}
.art-occhiello{display:inline-block;font-size:.74rem;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;margin-bottom:10px}
.art-occhiello.orange{color:var(--orange-ink,#a05714)}
.art-occhiello.gold{color:var(--gold-ink,#856a19)}
.art-head h1,.art-hero h1{font-family:'Playfair Display',serif;font-size:clamp(1.9rem,4.2vw,2.6rem);
  font-weight:800;color:var(--navy);line-height:1.16;margin:0 0 14px;letter-spacing:-0.015em}
/* Sul navy della barra il titolo va in bianco: sta qui sotto e non nel blocco
   .art-hero perche' la regola sopra ha la stessa specificita' e vince l'ultima. */
.art-hero h1{color:#fff}
.art-sommario{font-size:1.08rem;color:var(--text-mid);line-height:1.65;margin-bottom:22px}
.art-meta{display:flex;align-items:center;gap:12px;padding:16px 0;border-top:1px solid rgba(45,74,92,.1);
  border-bottom:1px solid rgba(45,74,92,.1);margin-bottom:34px}
.art-meta-foto{width:44px;height:44px;border-radius:50%;overflow:hidden;flex-shrink:0;background:var(--cream)}
.art-meta-foto img{width:100%;height:100%;object-fit:cover;object-position:center top}
.art-meta-nome{font-size:.92rem;font-weight:600;color:var(--navy);line-height:1.3}
.art-meta-riga{font-size:.82rem;color:var(--text-light);font-variant-numeric:tabular-nums}
.art-body{font-size:1.03rem;line-height:1.78;color:var(--text-dark)}
.art-body h2{font-family:'Playfair Display',serif;font-size:1.42rem;font-weight:700;color:var(--navy);
  line-height:1.28;margin:2.1em 0 .6em}
.art-body p{margin:0 0 1.15em}
.art-body ul,.art-body ol{margin:0 0 1.3em;padding-left:1.35em}
.art-body li{margin-bottom:.55em;line-height:1.68}
.art-body blockquote{margin:1.6em 0;padding:16px 22px;border-left:3px solid var(--orange);
  background:var(--cream);border-radius:0 12px 12px 0;font-size:1.05rem;line-height:1.6}
.art-body blockquote strong{color:var(--navy)}
.art-body a{color:var(--navy);text-underline-offset:3px}
.art-avviso{border:1px solid #e5c07b;background:#fdf6e6;border-radius:14px;padding:16px 20px;
  margin:34px 0 0;font-size:.86rem;color:#5c4a1c;line-height:1.6}
.art-avviso strong{display:block;margin-bottom:4px;color:#4a3b13}
.art-cta{background:var(--navy);border-radius:20px;padding:28px 30px;margin:44px 0 0;color:#fff}
.art-cta-titolo{font-family:'Playfair Display',serif;font-size:1.25rem;font-weight:700;margin-bottom:8px}
.art-cta p{font-size:.92rem;color:rgba(255,255,255,.72);line-height:1.65;margin-bottom:18px}
.art-firma{display:flex;gap:16px;align-items:flex-start;background:var(--cream);border-radius:18px;
  padding:24px 26px;margin:40px 0 0}
.art-firma-foto{width:64px;height:64px;border-radius:50%;overflow:hidden;flex-shrink:0;background:#fff}
.art-firma-foto img{width:100%;height:100%;object-fit:cover;object-position:center top}
.art-firma-nome{font-family:'Playfair Display',serif;font-size:1.08rem;font-weight:700;color:var(--navy)}
.art-firma-ruolo{font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--orange-ink,#a05714);margin:2px 0 8px}
.art-firma p{font-size:.88rem;color:var(--text-mid);line-height:1.65;margin-bottom:10px}
.art-firma-link{font-size:.84rem;font-weight:600;color:var(--navy);margin-right:14px}
/* position:static esplicito come rete di sicurezza: il blocco e' un div con
   role="navigation", ma se un giorno tornasse a essere un <nav> la regola di
   elemento del sito lo incollerebbe di nuovo in cima alla pagina. */
.art-altri{position:static;margin:48px 0 0;border-top:1px solid rgba(45,74,92,.1);padding-top:30px}
.art-altri-titolo{font-size:.78rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  color:var(--text-light);margin-bottom:16px}
.art-altri-lista{display:grid;gap:12px}
.art-altri-lista a{display:block;text-decoration:none;color:inherit;background:#fff;border-radius:14px;
  border:1px solid rgba(45,74,92,.08);padding:14px 18px;transition:.25s}
.art-altri-lista a:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(45,74,92,.1)}
.art-altri-data{font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;
  color:var(--text-light);margin-bottom:4px;font-variant-numeric:tabular-nums}
.art-altri-lista h3{font-family:'Playfair Display',serif;font-size:1rem;font-weight:700;
  color:var(--navy);line-height:1.32;margin:0}
.art-back{display:inline-block;margin-top:34px;font-weight:600;color:var(--navy);
  text-decoration:underline;text-underline-offset:3px}
"""


# --------------------------------------------------------------- articoli

def jsonld_articolo(a, rub, aut, url):
    autore = {"@type": "Person", "name": aut['nome'], "jobTitle": aut['titolo']}
    if aut.get('sito'):
        autore['url'] = aut['sito']
    payload = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": trunc(a['titolo'], 110),
        "description": trunc(a['sommario'], 200),
        "datePublished": a['data'].isoformat(),
        "dateModified": a['data'].isoformat(),
        "inLanguage": "it-IT",
        "author": autore,
        "publisher": {
            "@type": "Organization",
            "name": "DAOP",
            "url": SITE_URL,
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/assets/images/logodaop.webp"},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "isPartOf": {"@type": "Blog", "name": rub['nome'], "@id": f"{SITE_URL}/rubriche.html#{rub['slug']}"},
        "url": url,
    }
    if a['tag']:
        payload['keywords'] = ", ".join(a['tag'])
    return json.dumps(payload, ensure_ascii=False, indent=2)


def blocco_cta(cta):
    if not cta:
        return ''
    return f"""<aside class="art-cta">
      <div class="art-cta-titolo">{esc(cta['titolo'])}</div>
      <p>{esc(cta['testo'])}</p>
      <a href="{esc(cta['link'])}" class="btn btn-primary">{esc(cta['label'])}
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#i-arrow-right"/></svg></a>
    </aside>"""


def blocco_firma(aut, rub):
    link = []
    if aut.get('sito'):
        link.append(f'<a class="art-firma-link" href="{esc(aut["sito"])}" target="_blank" rel="noopener">Sito web →</a>')
    if aut.get('instagram'):
        link.append(f'<a class="art-firma-link" href="{esc(aut["instagram"])}" target="_blank" rel="noopener">Instagram →</a>')
    return f"""<aside class="art-firma">
      <div class="art-firma-foto"><img src="{esc(aut['foto'])}" alt="{esc(aut['nome'])}" width="120" height="120" loading="lazy"></div>
      <div>
        <div class="art-firma-nome">{esc(aut['nome'])}</div>
        <div class="art-firma-ruolo">{esc(aut['titolo'])}</div>
        <p>{esc(aut['bio'])}</p>
        {"".join(link)}
      </div>
    </aside>"""


def blocco_altri(a, pubblicati):
    """Gli ultimi tre pezzi della stessa rubrica, escluso quello corrente.

    Qui l'ordine resta dal piu' recente: in fondo a un articolo si offre
    l'ultima uscita, non il pezzo di gennaio. L'indice invece va in ordine
    di mese (vedi render_hub), perche' li' si legge la rubrica come serie."""
    altri = sorted((x for x in pubblicati
                    if x['rubrica'] == a['rubrica'] and x['slug'] != a['slug']),
                   key=lambda x: x['data'], reverse=True)[:3]
    if not altri:
        return ''
    voci = "".join(
        f'<a href="/rubriche/{x["slug"]}.html">'
        f'<div class="art-altri-data">{esc(data_estesa(x["data"]))}</div>'
        f'<h3>{esc(x["titolo"])}</h3></a>' for x in altri)
    # <div role="navigation"> e non <nav>: il CSS del sito ha nav{position:fixed;
    # top:0;left:0;right:0} come selettore di ELEMENTO, e un <nav> qui dentro
    # finiva incollato in cima alla pagina sopra la barra. Stessa scelta gia'
    # fatta per il breadcrumb delle pagine evento.
    return f"""<div class="art-altri" role="navigation" aria-label="Altri articoli della rubrica">
      <div class="art-altri-titolo">Altri articoli della rubrica</div>
      <div class="art-altri-lista">{voci}</div>
    </div>"""


def pagina_articolo(a, rub, aut, cfg, pubblicati, css, nav, foot, sprite):
    url = f"{SITE_URL}/rubriche/{a['slug']}.html"
    titolo_seo = trunc(f"{a['titolo']} | DAOP", 68)
    meta_d = trunc(a['sommario'], 158)
    avviso = ''
    if rub.get('avviso'):
        avviso = (f'<div class="art-avviso"><strong>Nota</strong>{esc(rub["avviso"])} '
                  f'Informazioni aggiornate al {esc(data_estesa(a["data"]))}.</div>')
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
<meta property="article:published_time" content="{a['data'].isoformat()}">
<meta property="article:author" content="{esc(aut['nome'])}">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(trunc(a['titolo'], 60))}">
<meta name="twitter:description" content="{esc(trunc(a['sommario'], 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{ARTICOLO_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld_articolo(a, rub, aut, url)}
</script>
</head>
<body>
{sprite}
{nav}
<main id="contenuto">
<header class="page-hero art-hero">
  <div class="page-hero-inner">
    <div class="art-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/rubriche.html">Rubriche</a> › <a href="/rubriche.html#{rub['slug']}">{esc(rub['nome'])}</a>
    </div>
    <span class="art-occhiello {rub['accento']}">{esc(rub['nome'])}</span>
    <h1>{esc(a['titolo'])}</h1>
    <p class="art-sommario">{esc(a['sommario'])}</p>
  </div>
</header>
<article class="art-wrap art-wrap--hero">
  <header class="art-head">
    <div class="art-meta">
      <div class="art-meta-foto"><img src="{esc(aut['foto'])}" alt="{esc(aut['nome'])}" width="88" height="88"></div>
      <div>
        <div class="art-meta-nome">{esc(aut['nome'])}</div>
        <div class="art-meta-riga">{esc(aut['titolo'])} · <time datetime="{a['data'].isoformat()}">{esc(data_estesa(a['data']))}</time></div>
      </div>
    </div>
  </header>
  <div class="art-body">
    {md2html(a['corpo'])}
  </div>
  {avviso}
  {blocco_cta(cfg['cta'].get(a['cta']))}
  {blocco_firma(aut, rub)}
  {blocco_altri(a, pubblicati)}
  <a href="/rubriche.html" class="art-back">← Tutte le rubriche</a>
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


def scrivi_pagine(cfg, rubriche, autori, pubblicati):
    os.makedirs(PAGINE_DIR, exist_ok=True)
    css, nav, foot, sprite = guscio()
    attesi, cambiate = set(), 0
    for a in pubblicati:
        rub, aut = rubriche[a['rubrica']], autori[rubriche[a['rubrica']]['autore']]
        path = os.path.join(PAGINE_DIR, f"{a['slug']}.html")
        nuovo = pagina_articolo(a, rub, aut, cfg, pubblicati, css, nav, foot, sprite)
        attesi.add(f"{a['slug']}.html")
        vecchio = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if vecchio != nuovo:
            open(path, 'w', encoding='utf-8').write(nuovo)
            cambiate += 1
    # Un articolo rinviato (data spostata avanti) o rinominato lascerebbe la
    # vecchia pagina orfana e indicizzata: va tolta.
    for nome in os.listdir(PAGINE_DIR):
        if nome.endswith('.html') and nome not in attesi:
            os.remove(os.path.join(PAGINE_DIR, nome))
            print(f"[rubriche] rimossa pagina non piu' prevista: {nome}")
    print(f"[rubriche] {len(pubblicati)} pagine articolo ({cambiate} scritte, "
          f"{len(pubblicati) - cambiate} gia' aggiornate)")


# -------------------------------------------------------------------- hub

def card_articolo(a, acc):
    return (f'<a class="rub-card" href="rubriche/{a["slug"]}.html">'
            f'<div class="rub-card-accent {acc}"></div>'
            f'<div class="rub-card-body">'
            f'<div class="rub-card-date">{esc(data_estesa(a["data"]))}</div>'
            f'<h3>{esc(a["titolo"])}</h3>'
            f'<p>{esc(trunc(a["sommario"], 155))}</p>'
            f'<span class="rub-card-more {acc}">Leggi '
            f'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><use href="#i-arrow-right"/></svg>'
            f'</span></div></a>')


def fisarmonica_anni(articoli, acc):
    """Un <details> per anno. Anni dal piu' recente (chi torna sul sito vuole
    l'annata in corso senza scorrere), mesi in ordine dentro l'anno (la rubrica
    si legge come una serie). Tutti chiusi all'apertura della pagina: si vede
    l'indice degli anni e si apre quello che interessa, senza scorrere schede.

    <details> nativo e non un accordion in JavaScript: funziona senza script,
    e' navigabile da tastiera e i motori indicizzano anche il contenuto chiuso.
    """
    per_anno = collections.OrderedDict()
    for a in sorted(articoli, key=lambda a: a['data']):
        per_anno.setdefault(a['data'].year, []).append(a)

    blocchi = []
    for anno in sorted(per_anno, reverse=True):
        pezzi = per_anno[anno]
        conta = f"{len(pezzi)} articolo" if len(pezzi) == 1 else f"{len(pezzi)} articoli"
        blocchi.append(
            f'<details class="rub-anno">'
            f'<summary class="rub-anno-sommario">'
            f'<span class="rub-anno-num">{anno}</span>'
            f'<span class="rub-anno-conta">{conta}</span>'
            f'<svg class="icon rub-anno-chevron" viewBox="0 0 24 24" aria-hidden="true">'
            f'<use href="#i-chevron-down"/></svg>'
            f'</summary>'
            f'<div class="rub-grid">{"".join(card_articolo(a, acc) for a in pezzi)}</div>'
            f'</details>')
    return "\n    ".join(blocchi)


def render_hub(rubriche, autori, pubblicati):
    sezioni = []
    for i, (rslug, rub) in enumerate(rubriche.items()):
        # Ordine di mese, dal primo all'ultimo: sono rubriche mensili e si
        # leggono come una serie (il pezzo di gennaio e' quello che presenta
        # la rubrica). Dal piu' recente si arrivava all'introduzione per ultima.
        articoli = sorted((a for a in pubblicati if a['rubrica'] == rslug),
                          key=lambda a: a['data'])
        aut = autori[rub['autore']]
        acc = rub['accento']
        link = []
        if aut.get('sito'):
            link.append(f'<a href="{esc(aut["sito"])}" target="_blank" rel="noopener">sito</a>')
        if aut.get('instagram'):
            link.append(f'<a href="{esc(aut["instagram"])}" target="_blank" rel="noopener">Instagram</a>')
        firma = (f'<p class="rub-firma">A cura di <strong>{esc(aut["nome"])}</strong>, '
                 f'{esc(aut["titolo"].lower())}' + (f' · {" · ".join(link)}' if link else '') + '</p>')
        avviso = ''
        if rub.get('avviso'):
            avviso = f'<div class="rub-avviso"><strong>Nota</strong>{esc(rub["avviso"])}</div>'
        if articoli:
            griglia = fisarmonica_anni(articoli, acc)
        else:
            griglia = ('<p class="section-subtitle">Il primo articolo di questa rubrica '
                       'sarà pubblicato a breve.</p>')
        sezioni.append(f"""<section class="{'bg-white' if i % 2 == 0 else 'bg-cream'}" id="{esc(rslug)}">
  <div class="section-inner">
    <div class="rub-head">
      <div class="rub-head-photo"><img src="{esc(aut['foto'].lstrip('/'))}" alt="{esc(aut['nome'])}" width="184" height="184" loading="lazy"></div>
      <div>
        <div class="rub-overline {acc}">{esc(rub['occhiello'])}</div>
        <h2>{esc(rub['nome'])}</h2>
        <p class="rub-head-desc">{esc(rub['descrizione'])}</p>
        {firma}
      </div>
    </div>
    {avviso}
    {griglia}
  </div>
</section>""")
    return "\n\n".join(sezioni)


def jsonld_hub(rubriche, autori, pubblicati):
    graph = [{
        "@type": "CollectionPage",
        "@id": f"{SITE_URL}/rubriche.html",
        "name": "Rubriche DAOP",
        "description": "Le rubriche di DAOP: educazione alimentare per le famiglie e agevolazioni fiscali, firmate da professioniste del settore.",
        "url": f"{SITE_URL}/rubriche.html",
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": SITE_URL},
    }, {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Rubriche", "item": f"{SITE_URL}/rubriche.html"},
        ],
    }]
    for rslug, rub in rubriche.items():
        aut = autori[rub['autore']]
        autore = {"@type": "Person", "name": aut['nome'], "jobTitle": aut['titolo']}
        if aut.get('sito'):
            autore['url'] = aut['sito']
        graph.append({
            "@type": "Blog",
            "@id": f"{SITE_URL}/rubriche.html#{rslug}",
            "name": rub['nome'],
            "description": rub['descrizione'],
            "inLanguage": "it-IT",
            "author": autore,
            "publisher": {"@type": "Organization", "name": "DAOP", "url": SITE_URL},
            "blogPost": [{
                "@type": "BlogPosting",
                "headline": trunc(a['titolo'], 110),
                "description": trunc(a['sommario'], 200),
                "datePublished": a['data'].isoformat(),
                "author": autore,
                "url": f"{SITE_URL}/rubriche/{a['slug']}.html",
            } for a in pubblicati if a['rubrica'] == rslug],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, indent=2)


def scrivi_hub(rubriche, autori, pubblicati):
    s = open(HUB_PATH, encoding='utf-8').read()
    s, n1 = re.subn(r'(<!-- RUBRICHE-LISTA -->).*?(<!-- /RUBRICHE-LISTA -->)',
                    lambda m: f"{m.group(1)}\n{render_hub(rubriche, autori, pubblicati)}\n{m.group(2)}",
                    s, count=1, flags=re.S)
    blocco = ('<script type="application/ld+json">\n'
              + jsonld_hub(rubriche, autori, pubblicati) + '\n</script>')
    s, n2 = re.subn(r'(<!-- RUBRICHE-JSONLD -->).*?(<!-- /RUBRICHE-JSONLD -->)',
                    lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}",
                    s, count=1, flags=re.S)
    if not n1 or not n2:
        raise SystemExit("[rubriche] marker RUBRICHE-LISTA/RUBRICHE-JSONLD non trovati in rubriche.html")
    open(HUB_PATH, 'w', encoding='utf-8').write(s)
    print(f"[rubriche] rubriche.html aggiornata ({len(pubblicati)} articoli in elenco)")


# ---------------------------------------------------------------- sitemap

def update_sitemap(pubblicati):
    if not os.path.exists(SITEMAP_PATH):
        return
    s = open(SITEMAP_PATH, encoding='utf-8').read()
    ultimo = max((a['data'] for a in pubblicati), default=datetime.date.today())
    righe = [f"  <url>\n    <loc>{SITE_URL}/rubriche.html</loc>\n"
             f"    <lastmod>{ultimo.isoformat()}</lastmod>\n"
             f"    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>"]
    righe += [f"  <url>\n    <loc>{SITE_URL}/rubriche/{a['slug']}.html</loc>\n"
              f"    <lastmod>{a['data'].isoformat()}</lastmod>\n"
              f"    <changefreq>yearly</changefreq>\n    <priority>0.7</priority>\n  </url>"
              for a in pubblicati]
    s, n = re.subn(r'(<!-- RUBRICHE:START.*?-->).*?( *<!-- RUBRICHE:END -->)',
                   lambda m: f"{m.group(1)}\n" + "\n".join(righe) + f"\n{m.group(2)}",
                   s, count=1, flags=re.S)
    if n:
        open(SITEMAP_PATH, 'w', encoding='utf-8').write(s)
        print(f"[rubriche] sitemap: {len(pubblicati) + 1} URL")
    else:
        print("[rubriche] sitemap: marker RUBRICHE non trovati, salto")


# -------------------------------------------------------------------- main

def main():
    cfg, rubriche, autori, articoli = carica()
    oggi = datetime.date.today()
    pubblicati = [a for a in articoli if a['data'] <= oggi]
    attesa = [a for a in articoli if a['data'] > oggi]

    for a in articoli:
        if not a['titolo'] or not a['sommario']:
            raise SystemExit(f"[rubriche] titolo o sommario mancante in {a['file']}")

    scrivi_pagine(cfg, rubriche, autori, pubblicati)
    scrivi_hub(rubriche, autori, pubblicati)
    update_sitemap(pubblicati)

    if attesa:
        print(f"\n[rubriche] {len(attesa)} articoli pronti ma non ancora pubblicati "
              f"(escono da soli alla loro data):")
        for a in sorted(attesa, key=lambda x: x['data']):
            print(f"    {a['data']}  {rubriche[a['rubrica']]['nome']:20} {trunc(a['titolo'], 58)}")

    da_verificare = [(a, v) for a in articoli for v in a['verificare']]
    if da_verificare:
        print(f"\n[rubriche] DATI DA FAR CONFERMARE ALL'AUTRICE prima della diffusione "
              f"({len(da_verificare)} voci):")
        for a, v in da_verificare:
            print(f"    {a['file'][:-3]}: {v}")


if __name__ == "__main__":
    main()
