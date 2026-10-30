#!/usr/bin/env python3
"""
Genera le sezioni dinamiche di esploratore.html (la pagina della collana
"Ginetto l'Esploratore", puntata dai QR code stampati dentro i libri)
a partire da data/ginetto-collana.json.

Rigenera SOLO i blocchi tra le ancore GINETTO:*:START / GINETTO:*:END.
Tutto il resto della pagina (nav, footer, stili, testi fissi) resta intatto,
esattamente come fa scripts/genera_eventi.py con eventi.html.

Due cose che lo script fa apposta, e che e' bene non "semplificare":

  1. Il PESO dei PDF viene letto dal file vero, non dal JSON. Cosi' la riga
     "PDF A4 - 320 KB" non puo' mai mentire dopo che un file viene sostituito.

  2. Se un PDF o una copertina NON esistono ancora nel repo, il link NON viene
     generato: la voce compare come "in preparazione" e la copertina come
     segnaposto disegnato. Su una pagina raggiunta da QR stampato un download
     rotto e' molto peggio di un materiale dichiarato non ancora pronto.

Uso:
    python scripts/genera_ginetto.py
"""
import os, re, json, html, datetime, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "data", "ginetto-collana.json")
HTML_PATH = os.path.join(ROOT, "esploratore.html")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

# Con l'estensione: /esploratore senza .html non esiste come file e rispondeva
# 404. Era il canonical rotto che teneva la pagina fuori dall'indice. Qui
# alimenta i dati strutturati, quindi lasciarlo sbagliato li faceva puntare a
# una pagina inesistente a ogni rigenerazione, anche dopo averlo corretto a
# mano nell'HTML.
PAGE_URL = "https://www.daop.it/esploratore.html"
AMAZON_AUTORE = "https://www.amazon.it/stores/Patrick-Orlando/author/B0F8B95YG5"

# Le pagine dei singoli volumi: /esploratore/<id>.html. Vedi render_tappe().
CARTELLA_VOL = os.path.join(ROOT, "esploratore")
VOL_URL = "https://www.daop.it/esploratore/{}.html"

mancanti = []   # file citati dal JSON ma non presenti nel repo


def e(s):
    """Escape HTML di un valore proveniente dal JSON."""
    return html.escape(str(s or ""), quote=True)


def peso(path_rel):
    """Peso leggibile del file, o None se il file non c'e'."""
    p = os.path.join(ROOT, path_rel.replace("/", os.sep))
    if not path_rel or not os.path.isfile(p):
        return None
    b = os.path.getsize(p)
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{round(b / 1024)} KB"
    return f"{b / 1024 / 1024:.1f}".replace(".", ",") + " MB"


def esiste(path_rel):
    return bool(path_rel) and os.path.isfile(
        os.path.join(ROOT, path_rel.replace("/", os.sep)))


# ─────────────────────────── copertine ───────────────────────────

def copertina(v):
    """<img> se la copertina esiste, altrimenti un segnaposto disegnato con
    le stesse proporzioni (1:1: i libri della collana sono quadrati), cosi'
    il layout non balla quando arrivera' il file vero."""
    src, alt = v.get("copertina", ""), v.get("copertina_alt", "")
    if esiste(src):
        return (f'<img src="{e(src)}" alt="{e(alt)}" width="980" height="980" '
                f'loading="lazy" decoding="async">')
    mancanti.append(src or f"(copertina del volume {v.get('numero')})")
    etichetta = "In arrivo" if v.get("stato") == "in-arrivo" else "Copertina in arrivo"
    return (
        '<div class="vol-placeholder" role="img" aria-label="' + e(alt) + '">'
        '<svg viewBox="0 0 800 800" aria-hidden="true" focusable="false">'
        '<rect width="800" height="800" fill="#2d4a5c"/>'
        # Ago di bussola, non una croce: con due semplici linee il segnaposto
        # sembrava un pulsante "+" (aggiungi) invece di un volume in arrivo.
        '<circle cx="400" cy="330" r="132" fill="none" stroke="#c9a227" stroke-width="9"/>'
        '<g transform="rotate(32 400 330)">'
        '<path d="M400 228 L426 330 L400 330 Z" fill="#c9a227"/>'
        '<path d="M400 228 L374 330 L400 330 Z" fill="#a8871f"/>'
        '<path d="M400 432 L426 330 L400 330 Z" fill="rgba(255,255,255,0.32)"/>'
        '<path d="M400 432 L374 330 L400 330 Z" fill="rgba(255,255,255,0.17)"/>'
        '</g><circle cx="400" cy="330" r="11" fill="#2d4a5c"/>'
        f'<text x="400" y="572" text-anchor="middle" fill="#ffffff" '
        f'font-family="Georgia,serif" font-size="72" font-weight="700">Vol. {e(v.get("numero"))}</text>'
        f'<text x="400" y="650" text-anchor="middle" fill="rgba(255,255,255,0.62)" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="42">{e(etichetta)}</text>'
        '</svg></div>')


# ─────────────────────────── volumi ───────────────────────────

def render_volumi(volumi):
    out = []
    for v in volumi:
        in_arrivo = v.get("stato") == "in-arrivo"
        classi = "vol-card" + (" is-soon" if in_arrivo else "")
        out.append(f'      <article class="{classi}">')
        out.append(f'        <div class="vol-cover">{copertina(v)}</div>')
        out.append('        <div class="vol-body">')
        out.append(f'          <p class="vol-num">Volume {e(v.get("numero"))}</p>')
        out.append(f'          <h3>{e(v.get("titolo"))}</h3>')
        # Il luogo si mostra anche per un volume non ancora uscito (Castelnuovo
        # e' un paese vero); si omette solo per lo slot generico "prossimo
        # paese", che infatti ha "paese" vuoto nel JSON.
        if v.get("paese"):
            out.append(
                '          <p class="vol-luogo">'
                '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                '<path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z"/>'
                '<circle cx="12" cy="10" r="2.6"/></svg>'
                f'<span>{e(v.get("paese"))} <span class="vol-prov">({e(v.get("provincia"))})</span></span></p>')
        out.append(f'          <p class="vol-desc">{e(v.get("descrizione"))}</p>')
        if ha_pagina(v):
            out.append(f'          <p class="vol-percorso"><a href="/esploratore/{e(v["id"])}.html">'
                       f'Le {len(v["tappe"])} tappe del percorso a {e(v["paese"])} &rarr;</a></p>')

        if in_arrivo:
            out.append('          <p class="vol-soon">In preparazione</p>')
        else:
            link = v.get("amazon") or AMAZON_AUTORE
            etichetta = "Vedi su Amazon" if v.get("amazon") else "Cerca su Amazon"
            if not v.get("amazon"):
                mancanti.append(f'(link Amazon diretto del volume {v.get("numero")} '
                                f'- ora punta alla pagina autore)')
            out.append(
                f'          <a class="vol-link" href="{e(link)}" target="_blank" rel="noopener" '
                f'aria-label="{e(etichetta)}: {e(v.get("titolo"))}">{e(etichetta)}'
                '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                '<path d="M5 12h13M12 5l7 7-7 7"/></svg></a>')
        out.append('        </div>')
        out.append('      </article>')
    return "\n".join(out)


# ─────────────────────────── materiali ───────────────────────────

def render_materiali(volumi, visibile=True):
    """La sezione INTERA, intestazione compresa, oppure niente.

    I marker GINETTO:MATERIALI abbracciano tutta la sezione e non solo
    l'elenco, cosi' l'interruttore e' uno solo. Con l'elenco dentro i marker e
    il titolo scritto a mano fuori, spegnere i materiali avrebbe lasciato in
    pagina "Materiali per i piccoli esploratori" sopra il vuoto, che e' peggio
    della sezione intera.

    Spenta il 28/08/2026, e il testo NON e' stato buttato: sta qui e torna
    girando "materiali_visibili" nel JSON. Prometteva un diploma e una
    checklist che non esistono ancora ("Li stiamo preparando"), su una pagina
    raggiunta dal QR stampato DENTRO il libro - cioe' da chi il libro l'ha
    gia' comprato, che e' il pubblico a cui una promessa non mantenuta costa
    di piu'. Quando i PDF ci saranno, si riaccende e la sezione ricompare gia'
    con i suoi download: il peso dei file lo legge lo script dal file vero.
    """
    if not visibile:
        return ""
    out = ['<!-- MATERIALI -->',
           '<section class="bg-white" id="materiali">',
           '  <div class="section-inner">',
           '    <span class="section-label">Da stampare</span>',
           '    <h2 class="section-title">Materiali per i piccoli esploratori</h2>',
           '    <p class="section-subtitle">Il diploma e la checklist dei luoghi che '
           'accompagneranno i volumi, da stampare su un normale foglio A4. Li stiamo '
           "preparando: qui sotto c'è l'elenco di quello che arriverà.</p>",
           '    <p class="nota">',
           '      <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
           '<path d="M9 12.5l2.2 2.2L15.5 10"/><circle cx="12" cy="12" r="9"/></svg>',
           '      <span>Quando saranno pronti saranno download diretti e gratuiti: '
           'nessuna registrazione, nessun indirizzo email da lasciare.</span>',
           '    </p>',
           '    <div class="mat-groups">']
    for v in volumi:
        mats = v.get("materiali") or []
        # I materiali di un volume non ancora uscito non si annunciano: il
        # diploma di un libro che non esiste non e' "in preparazione", e'
        # una promessa che il lettore non puo' verificare.
        if not mats or v.get("stato") == "in-arrivo":
            continue
        out.append('      <div class="mat-group">')
        # Lo spazio dopo </span> non e' cosmetico: senza, uno screen reader
        # legge "Vol. 1Casale Monferrato" tutto attaccato.
        out.append('        <h3 class="mat-group-title">'
                   f'<span class="mat-group-num">Vol. {e(v.get("numero"))}</span> '
                   f'{e(v.get("paese"))}</h3>')
        out.append('        <ul class="mat-list">')
        for m in mats:
            f = m.get("file", "")
            kb = peso(f)
            meta = f'{e(m.get("formato", "PDF"))} &middot; {e(kb)}' if kb else "In preparazione"
            if kb:
                out.append(
                    f'          <li class="mat-item"><a class="mat-link" href="{e(f)}" download '
                    f'type="application/pdf" '
                    f'aria-label="Scarica {e(m.get("titolo"))} del volume {e(v.get("numero"))}, '
                    f'{e(v.get("paese"))} - {e(m.get("formato", "PDF"))}, {e(kb)}">')
            else:
                mancanti.append(f)
                out.append('          <li class="mat-item is-soon"><div class="mat-link">')
            out.append('            <span class="mat-ico" aria-hidden="true">'
                       '<svg viewBox="0 0 24 24" focusable="false">'
                       '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5"/>'
                       '<path d="M5 18.5h14"/></svg></span>')
            out.append('            <span class="mat-text">'
                       f'<span class="mat-titolo">{e(m.get("titolo"))}</span>'
                       f'<span class="mat-desc">{e(m.get("descrizione"))}</span>'
                       f'<span class="mat-meta">{meta}</span></span>')
            out.append('          </a></li>' if kb else '          </div></li>')
        out.append('        </ul>')
        out.append('      </div>')
    out += ['    </div>', '  </div>', '</section>']
    return "\n".join(out)


# ─────────────────────────── dati strutturati ───────────────────────────

def render_jsonld(volumi):
    libri = []
    for v in volumi:
        if v.get("stato") == "in-arrivo":
            continue
        libri.append({
            "@type": "Book",
            "position": v.get("numero"),
            "name": v.get("titolo"),
            "bookEdition": f"Volume {v.get('numero')}",
            "inLanguage": "it",
            "author": {"@type": "Person", "name": "Patrick Orlando"},
            "publisher": {"@type": "Organization", "name": "DAOP"},
            "about": {"@type": "Place", "name": v.get("paese"),
                      "address": {"@type": "PostalAddress",
                                  "addressLocality": v.get("paese"),
                                  "addressRegion": v.get("provincia"),
                                  "addressCountry": "IT"}},
            "url": v.get("amazon") or AMAZON_AUTORE,
        })
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BookSeries",
             "name": "Ginetto l'Esploratore",
             "url": PAGE_URL,
             "inLanguage": "it",
             "author": {"@type": "Person", "name": "Patrick Orlando"},
             "publisher": {"@type": "Organization", "name": "DAOP",
                           "url": "https://www.daop.it"},
             "hasPart": libri},
            {"@type": "WebPage",
             "name": "Ginetto l'Esploratore - la collana",
             "url": PAGE_URL,
             "isPartOf": {"@type": "WebSite", "name": "DAOP",
                          "url": "https://www.daop.it"}},
        ],
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False, indent=2)
            + '\n</script>')


# ─────────────────────────── pagine dei volumi ───────────────────────────
#
# Una pagina per volume, /esploratore/<id>.html, nata il 30/10/2026.
#
# La pagina parla del PAESE, non del libro: nessuno cerca «Ginetto alla
# scoperta di Garbagna», si cerca «Garbagna con i bambini». Quindi title e H1
# sono quelli, il corpo e' il percorso a tappe da fare a piedi, e il libro sta
# sotto, come la ragione per cui quel percorso esiste.
#
# - Le tappe sono un RIASSUNTO delle pagine del libro (data/ginetto-collana.json,
#   chiave "tappe"), non il testo: il libro e' quello che si vende.
# - Senza tappe la pagina non nasce: sarebbe una copertina e quattro righe, cioe'
#   piu' povera della scheda che c'e' gia' in esploratore.html.
# - Sei pagine, una per volume: l'insieme cresce di uno ogni volta che esce un
#   libro, non coi dati. Non e' scaled content.
# - Le pagine esistono anche per un volume in arrivo: i posti sono veri da
#   subito, e al posto del link ad Amazon c'e' «in arrivo».

GN_CSS = """
.gn-wrap h2{margin:34px 0 10px;font-size:1.3rem;line-height:1.32}
.gn-wrap>p{margin:0 0 12px;line-height:1.7;max-width:66ch}
.gn-wrap>p a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
.gn-tappe{list-style:none;margin:8px 0 0;padding:0;counter-reset:gn}
.gn-tappe li{counter-increment:gn;position:relative;padding:0 0 18px 44px}
.gn-tappe li::before{content:counter(gn);position:absolute;left:0;top:1px;width:30px;height:30px;
 border-radius:50%;background:var(--navy,#2d4a5c);color:#fff;font-weight:700;font-size:.9rem;
 display:flex;align-items:center;justify-content:center}
.gn-tappe h3{margin:0 0 4px;font-size:1.05rem;line-height:1.35;color:var(--navy,#2d4a5c)}
.gn-tappe p{margin:0;line-height:1.65}
.gn-libro{display:flex;gap:18px;align-items:flex-start;margin:30px 0 10px;padding:18px;
 border:1px solid var(--linea,#e2d8cb);border-radius:14px;background:var(--carta,#fffcf8)}
.gn-libro img,.gn-libro .gn-cop-vuota{flex:0 0 132px;width:132px;height:132px;border-radius:8px;object-fit:cover}
.gn-cop-vuota{background:#2d4a5c;color:#fff;display:flex;align-items:center;justify-content:center;
 font:700 1.1rem Georgia,serif}
.gn-libro p{margin:0 0 10px;line-height:1.6}
.gn-libro .gn-occh{font-size:.8rem;letter-spacing:.06em;text-transform:uppercase;color:var(--text-mid,#6a7a85);margin:0 0 4px}
.gn-libro h2{margin:0 0 8px;font-size:1.15rem}
.gn-btn{display:inline-flex;align-items:center;min-height:44px;padding:10px 18px;border-radius:10px;
 background:var(--navy,#2d4a5c);color:#fff;font-weight:600;text-decoration:none}
.gn-soon{font-weight:600;color:var(--text-mid,#6a7a85)}
@media (max-width:600px){.gn-libro{flex-direction:column}.gn-libro img,.gn-libro .gn-cop-vuota{width:160px;height:160px;flex-basis:auto}}
"""


def ha_pagina(v):
    return bool(v.get("tappe")) and bool(v.get("paese")) and v.get("id")


def _sigla(provincia):
    nomi = {n.lower(): s for s, n in G.PROVINCE_NOMI.items()}
    return nomi.get((provincia or "").strip().lower(), "")


def _libro_html(v):
    titolo = v.get("titolo", "")
    if esiste(v.get("copertina", "")):
        cop = (f'<img src="/{e(v["copertina"])}" alt="{e(v.get("copertina_alt"))}" '
               f'width="980" height="980" loading="lazy" decoding="async">')
    else:
        cop = f'<div class="gn-cop-vuota" role="img" aria-label="{e(titolo)}">Vol. {e(v.get("numero"))}</div>'
    if v.get("stato") == "in-arrivo":
        azione = '<p class="gn-soon">Il libro è in arrivo.</p>'
    else:
        link = v.get("amazon") or AMAZON_AUTORE
        etich = "Vedi il libro su Amazon" if v.get("amazon") else "Cerca il libro su Amazon"
        azione = (f'<a class="gn-btn" href="{e(link)}" target="_blank" rel="noopener">'
                  f'{etich}</a>')
    return (f'<section class="gn-libro">{cop}<div>'
            f'<p class="gn-occh">Il libro · Volume {e(v.get("numero"))}</p>'
            f'<h2>{e(titolo)}</h2>'
            f'<p>{e(v.get("descrizione"))}</p>{azione}</div></section>')


def render_tappe(v, volumi, oggi):
    css, nav, foot = G._guscio()
    paese, tappe = v["paese"], v["tappe"]
    sigla = _sigla(v.get("provincia"))
    url = VOL_URL.format(v["id"])
    n = len(tappe)
    titolo = f"{paese} con i bambini: le {n} tappe di Ginetto | DAOP"
    nomi = [t["nome"] for t in tappe]
    descr = G.trunc(f"Cosa vedere a {paese} con i bambini, a piedi: "
                    + ", ".join(nomi) + ". Il percorso del libro di Ginetto l'Esploratore.", 158)
    a_paese = G.a_citta(e(paese))

    lis = "\n".join(f'    <li><h3>{e(t["nome"])}</h3><p>{e(t["testo"])}</p></li>'
                    for t in tappe)

    # «Altro qui»: la pagina comune se c'e' su disco, i luoghi se c'e' l'ancora.
    # Quello che manca non si stampa (la regola di link_luoghi()).
    altro = []
    slug = G.slugify(paese)
    if os.path.isfile(os.path.join(ROOT, "eventi", "comune", f"{slug}.html")):
        altro.append(f'<a href="/eventi/comune/{slug}.html">Gli eventi{a_paese}</a>')
    lg = G.link_luoghi(paese, sigla)
    if lg:
        altro.append(lg)
    altro.append('<a href="/esploratore.html">Tutta la collana di Ginetto</a>')

    altri = [w for w in volumi if w is not v and ha_pagina(w)]
    altri_html = "".join(f'<a href="/esploratore/{e(w["id"])}.html">{e(w["paese"])}</a>'
                         for w in altri)

    libro = {
        "@type": "Book", "name": v.get("titolo"), "inLanguage": "it",
        "bookEdition": f"Volume {v.get('numero')}",
        "author": {"@type": "Person", "name": "Patrick Orlando"},
        "isPartOf": {"@type": "BookSeries", "name": "Ginetto l'Esploratore", "url": PAGE_URL},
        "about": {"@type": "Place", "name": paese,
                  "address": {"@type": "PostalAddress", "addressLocality": paese,
                              "addressRegion": v.get("provincia"), "addressCountry": "IT"}},
    }
    if esiste(v.get("copertina", "")):
        libro["image"] = f"{G.SITE_URL}/{v['copertina']}"
    if v.get("amazon"):
        libro["url"] = v["amazon"]
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": url, "url": url, "name": titolo, "description": descr,
         "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": G.SITE_URL},
         "mainEntity": {"@type": "ItemList", "name": f"Le tappe di Ginetto a {paese}",
                        "numberOfItems": n,
                        "itemListElement": [{"@type": "ListItem", "position": i, "name": t}
                                            for i, t in enumerate(nomi, 1)]},
         "about": libro},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": G.SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Ginetto l'Esploratore", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": paese, "item": url}]},
    ]}
    immagine = (f"{G.SITE_URL}/{v['copertina']}" if esiste(v.get("copertina", ""))
                else f"{G.SITE_URL}/assets/ginetto/og-esploratore.jpg")

    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/genera_ginetto.py: il testo sta in
     data/ginetto-collana.json. Le modifiche scritte a mano qui dentro
     spariscono alla run successiva. -->
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
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{e(immagine)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(titolo)}">
<meta name="twitter:description" content="{e(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{e(immagine)}">
<meta name="daop:citta" content="{e(paese)}">
<meta name="daop:provincia" content="{e(sigla)}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{G.PAGINA_CSS}{G.COMUNE_CSS}{GN_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=1)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/esploratore.html">Ginetto l'Esploratore</a> › <span>{e(paese)}</span>
    </div>
    <h1>{e(paese)} con i bambini</h1>
    <p class="ev-when">Il percorso di Ginetto l'Esploratore · {n} tappe a piedi · provincia di {e(v.get("provincia"))}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero gn-wrap">
  <p>Nel libro <i>{e(v.get("titolo"))}</i> Ginetto e la topolina Briciola attraversano {e(paese)} tappa dopo tappa. Sono posti veri: qui sotto c'è il percorso, da fare un pomeriggio con i bambini, con quello che vale la pena di cercare in ognuno.</p>
  <h2>Le {n} tappe</h2>
  <ol class="gn-tappe">
{lis}
  </ol>
  {_libro_html(v)}
  <h2>Altro{a_paese}</h2>
  <div class="com-link">{"".join(altro)}</div>
  {f'<h2>Gli altri paesi di Ginetto</h2><div class="com-link">{altri_html}</div>' if altri_html else ''}
  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
{G.blocco_ginetto(paese)}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def scrivi_pagine_volumi(volumi):
    """Scrive /esploratore/<id>.html per ogni volume con le tappe, toglie
    quelle di un volume che non le ha piu', e rifa' il blocco in sitemap.
    Ritorna gli URL scritti."""
    oggi = datetime.date.today()
    os.makedirs(CARTELLA_VOL, exist_ok=True)
    vivi = [v for v in volumi if ha_pagina(v)]
    for v in vivi:
        open(os.path.join(CARTELLA_VOL, f"{v['id']}.html"), "w",
             encoding="utf-8").write(render_tappe(v, volumi, oggi))
    tenuti = {f"{v['id']}.html" for v in vivi}
    for f in os.listdir(CARTELLA_VOL):
        if f.endswith(".html") and f not in tenuti:
            os.remove(os.path.join(CARTELLA_VOL, f))
            print(f"[genera_ginetto] tolta esploratore/{f}: il volume non ha piu' le tappe")
    urls = [VOL_URL.format(v["id"]) for v in vivi]
    sitemap_volumi(urls, oggi)
    return urls


def sitemap_volumi(urls, oggi):
    if not os.path.exists(SITEMAP_PATH):
        return
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    voci = "".join(f"  <url>\n    <loc>{u}</loc>\n    <lastmod>{oggi.isoformat()}</lastmod>\n"
                   f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>\n"
                   for u in urls)
    inizio = "  <!-- ESPLORATORE:START (generato da scripts/genera_ginetto.py — non modificare a mano) -->\n"
    fine = "  <!-- ESPLORATORE:END -->\n"
    blocco = inizio + voci + fine
    if "<!-- ESPLORATORE:START" in s:
        s = re.sub(r"  <!-- ESPLORATORE:START.*?<!-- ESPLORATORE:END -->\n",
                   lambda _: blocco, s, count=1, flags=re.S)
    else:
        s, k = re.subn(r"(?=  <!-- CORSI:START)", lambda _: blocco, s, count=1)
        if k != 1:
            print("[genera_ginetto] sitemap: non trovo dove mettere le pagine dei volumi")
            return
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)


# ─────────────────────────── iniezione ───────────────────────────

def alterna_fasce(pagina):
    """Rimette in fila bianco/crema/bianco su tutte le <section> della pagina.

    Non e' cosmesi: togliendo la sezione bianca dei materiali, la sezione dei
    volumi (crema) finirebbe attaccata a "Come funziona" (crema), cioe' una
    fascia sola alta il doppio. E il difetto si propaga a tutte quelle dopo,
    quindi non basta girare la vicina. Ricalcolarla a ogni run vuol dire che
    la sezione puo' andare e venire senza che nessuno debba ricordarsi di
    sistemare a mano i colori di quelle che seguono.
    """
    fasce = iter(("bg-white", "bg-cream") * 40)
    return re.sub(r'<section class="bg-(?:white|cream)"',
                  lambda _: f'<section class="{next(fasce)}"', pagina)


def inject(pagina, blocchi):
    for nome, contenuto in blocchi.items():
        pattern = (r'(<!-- GINETTO:' + nome + r':START -->)(.*?)(<!-- GINETTO:'
                   + nome + r':END -->)')
        pagina, n = re.subn(pattern,
                            lambda m: m.group(1) + "\n" + contenuto + "\n" + m.group(3),
                            pagina, flags=re.S)
        if n != 1:
            sys.exit(f"[genera_ginetto] ERRORE: ancora GINETTO:{nome} non trovata "
                     f"(o duplicata) in esploratore.html")
    return pagina


def update_sitemap():
    if not os.path.exists(SITEMAP_PATH):
        return
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    s, n = re.subn(
        # esploratore.html, non /esploratore: quella URL senza estensione non e'
        # mai esistita come file e mandava Google su un 404. Corretta nel
        # canonical, nella sitemap e qui, dove faceva fallire l'aggiornamento
        # del lastmod in silenzio.
        r'(<loc>https://www\.daop\.it/esploratore\.html</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + oggi + m.group(2), s, count=1)
    if n == 1:
        open(SITEMAP_PATH, "w", encoding="utf-8").write(s)
        print(f"[genera_ginetto] sitemap: lastmod /esploratore -> {oggi}")
    else:
        print("[genera_ginetto] sitemap: blocco esploratore.html non trovato, salto")


def main():
    dati = json.load(open(JSON_PATH, encoding="utf-8"))
    volumi = [v for v in dati.get("volumi", []) if v.get("visibile")]
    if not volumi:
        sys.exit("[genera_ginetto] ERRORE: nessun volume visibile nel JSON")

    materiali_on = bool(dati.get("collana", {}).get("materiali_visibili", True))

    pagina = open(HTML_PATH, encoding="utf-8").read()
    pagina = inject(pagina, {
        # La riga che annuncia i materiali e' staccata dall'intro e si attacca
        # solo se la sezione c'e': se no l'intro promette un download che in
        # pagina non esiste, ed e' proprio la promessa che si voleva togliere.
        "INTRO": '      <p class="intro-testo">'
                 + e(dati.get("collana", {}).get("intro", "")
                     + (dati.get("collana", {}).get("intro_materiali", "")
                        if materiali_on else "")) + '</p>',
        "VOLUMI": render_volumi(volumi),
        "MATERIALI": render_materiali(volumi, materiali_on),
        "JSONLD": render_jsonld(volumi),
    })
    pagina = alterna_fasce(pagina)
    open(HTML_PATH, "w", encoding="utf-8").write(pagina)
    update_sitemap()
    urls = scrivi_pagine_volumi(volumi)
    print(f"[genera_ginetto] {len(urls)} pagine in esploratore/: "
          + ", ".join(u.rsplit("/", 1)[-1] for u in urls))

    pubblicati = sum(1 for v in volumi if v.get("stato") != "in-arrivo")
    scaricabili = sum(1 for v in volumi for m in (v.get("materiali") or [])
                      if esiste(m.get("file", "")))
    print(f"[genera_ginetto] esploratore.html aggiornata: {pubblicati} volumi, "
          f"{scaricabili} materiali scaricabili")
    if not materiali_on:
        print("[genera_ginetto] sezione materiali SPENTA (materiali_visibili: false "
              "nel JSON): il testo resta nel generatore, non in pagina")
    if mancanti:
        print("\n[genera_ginetto] DA CARICARE (per ora mostrati come segnaposto "
              "o 'in preparazione'):")
        for m in dict.fromkeys(mancanti):
            print("  - " + m)


if __name__ == "__main__":
    main()
