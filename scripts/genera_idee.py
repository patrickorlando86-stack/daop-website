#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""/idee/<slug>.html — le pagine che portano una SCELTA, non un elenco.

Cosa sono, e perche' non sono "l'ennesima pagina categoria".

L'elenco completo dei luoghi c'e' gia' e sta in `luoghi.html`, coi filtri: 800
righe, una pagina sola, per la ragione scritta in CLAUDE.md (800 pagine su
template identico sono la definizione di scaled content abuse). Queste pagine
non rifanno quel lavoro e non ci provano: qui dentro ci sono CINQUE posti scelti
a mano da una persona, con scritto perche' quei cinque.

E' la sola cosa che un aggregatore non puo' copiare. Chi scala non giudica; noi
giudichiamo, e quello che si mette dietro un "consigliato" o si vende a un
Comune e' il giudizio, non l'elenco.

Da qui tre regole che il codice fa rispettare, e non sono di stile:

 1. TITOLO E DESCRIZIONE SI SCRIVONO A MANO, uno per pagina. Su 343 schede
    evento un titolo a stampo va bene; su dieci pagine tematiche no, perche' li'
    ogni singolo CTR pesa - misurato sul nostro stesso sito: /eventi.html sta al
    2,5% e /ferragosto.html al 3,0%, mentre le pagine curate viaggiano molto piu'
    in alto. Se in `data/idee.json` mancano, la pagina NON si scrive.
 2. IL "PERCHE' QUESTI CINQUE" E' OBBLIGATORIO. E' la frase che rende la pagina
    diversa da una query sul catalogo, ed e' anche quella che chi sceglie ha gia'
    in testa mentre sceglie. Senza, la pagina non si scrive.
 3. POCHE. Il rischio dello scaled content abuse e' di volume: queste nascono
    una alla volta, quando un carosello e' piaciuto abbastanza da meritarsela.
    Nessuna soglia automatica, nessun ciclo che le sforni.

I cinque luoghi arrivano per CODICE dal catalogo: il testo, la foto, l'indirizzo
e gli orari non si copiano qui dentro: cosi' la pagina si rigenera ogni notte
come tutto il resto, e se un posto cambia nome o chiude, la pagina lo segue.

    python3 scripts/genera_idee.py
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as G
import genera_luoghi as L

ROOT = G.ROOT
IDEE_JSON = os.path.join(ROOT, "data", "idee.json")
CARTELLA = os.path.join(ROOT, "idee")

# Sotto questo numero la pagina esce lo stesso ma in noindex e fuori sitemap,
# come /piscine.html: resta raggiungibile e non promette un elenco che non ha.
MINIMO_IN_INDICE = 3

IDEE_CSS = """
.id-perche{margin:0 0 6px;font-size:.95rem;line-height:1.5;color:var(--ink-2,#3d4f5a)}
.id-perche b{color:var(--ink,#22333d)}
.id-num{display:inline-flex;align-items:center;justify-content:center;width:26px;
 height:26px;border-radius:50%;background:var(--brand,#2d6b4a);color:#fff;
 font-weight:700;font-size:.85rem;margin-right:8px;flex:0 0 auto}
.id-voce{margin:0 0 18px}
.id-voce > .id-perche{display:flex;align-items:flex-start}
.id-chiusa{margin:22px 0 0;padding:14px 16px;border:1px solid var(--linea,#e2d8cb);
 border-radius:12px;background:var(--carta,#fffcf8)}
.id-chiusa p{margin:0 0 6px}
.id-chiusa p:last-child{margin:0}
"""


def leggi_idee():
    """Le idee decise. [] se il file non c'e' (e non e' un guasto: vuol dire
    che non ne e' stata ancora decisa nessuna)."""
    try:
        with open(IDEE_JSON, encoding="utf-8") as fh:
            return json.load(fh).get("idee") or []
    except FileNotFoundError:
        return []
    except Exception as exc:
        print(f"[genera_idee] {os.path.basename(IDEE_JSON)} illeggibile: {exc}")
        return []


def url_idea(slug):
    return f"{G.SITE_URL}/idee/{slug}.html"


def h1_html(testo):
    """L'H1, con l'unico tag ammesso: <em>.

    Nei titoli del sito la seconda meta' e' in corsivo ("Piscine <em>per
    bambini</em>"), e quel corsivo e' parte del disegno della pagina. Ma il testo
    arriva da un file di dati, quindi si scappa TUTTO e poi si rimette in piedi
    solo <em>: cosi' il corsivo si puo' scrivere e nient'altro passa. Senza,
    sulla pagina si leggeva "5 gite gratis <em>con i bambini</em>" per intero.
    """
    return (G.esc(testo).replace("&lt;em&gt;", "<em>")
            .replace("&lt;/em&gt;", "</em>"))


def _manca(idea):
    """Cosa impedisce di scrivere questa pagina, o "".

    Si controlla PRIMA di aprire il file: una pagina scritta a meta' resterebbe
    online, e online una pagina vuota costa piu' di una pagina che non c'e'.
    """
    for campo, cosa in (("slug", "l'indirizzo"), ("titolo", "il title"),
                        ("descrizione", "la description"),
                        ("h1", "il titolo in pagina"), ("perche", "il perche' questi")):
        if not (idea.get(campo) or "").strip():
            return f"manca {cosa}"
    if len(idea.get("luoghi") or []) < 2:
        return "meno di due luoghi"
    return ""


def voci_della_idea(idea, per_codice):
    """(luoghi trovati, codici spariti dal catalogo).

    Un codice che non c'e' piu' non fa saltare la pagina: si salta la voce e lo
    si dice. Capita per davvero - un posto chiude e la riga esce dal foglio - e
    il giorno che capita la pagina deve continuare a esistere con quattro.
    """
    trovati, persi = [], []
    for voce in idea.get("luoghi") or []:
        codice = str(voce.get("codice") or "").strip()
        luogo = per_codice.get(codice)
        if not luogo:
            persi.append(codice)
            continue
        trovati.append((luogo, (voce.get("riga") or "").strip()))
    return trovati, persi


def render(idea, voci, oggi):
    e = G.esc
    css, nav, foot = G._guscio()
    url = url_idea(idea["slug"])
    luoghi = [l for l, _r in voci]
    comuni = len({(l["prov"], l["comune"]) for l in luoghi})
    zona = L.dove_siamo(luoghi)

    # Le righe sono quelle dell'elenco luoghi: stessa forma, stessi gesti, e
    # soprattutto nessun secondo modo di scrivere un luogo da tenere allineato.
    # Sopra ognuna ci va la riga di chi ha scelto - che e' l'unica cosa che qui
    # dentro non viene dal catalogo.
    corpo = []
    for n, (luogo, riga_mia) in enumerate(voci, 1):
        pezzo = [f'<div class="id-voce">']
        if riga_mia:
            pezzo.append(f'<p class="id-perche"><span class="id-num">{n}</span>'
                         f'<span>{e(riga_mia)}</span></p>')
        pezzo.append(L.riga(luogo, oggi))
        pezzo.append('</div>')
        corpo.append("".join(pezzo))

    quanti = "cinque" if len(voci) == 5 else str(len(voci))
    chiusa = (
        '    <section class="id-chiusa">'
        f"<p><b>Perche' questi {quanti}.</b> "
        f'{e(idea["perche"])}</p>'
        '<p>Questa e\' una scelta, non tutto quello che abbiamo: '
        '<a href="/luoghi.html">l\'elenco completo dei luoghi</a> si filtra per '
        'provincia, categoria e distanza. Come li verifichiamo sta in '
        '<a href="/metodo.html">metodo</a>.</p>'
        '</section>')

    pagina = "\n".join(x for x in [
        '  <div class="lg-wrap">',
        "\n".join(corpo),
        chiusa,
        # Questa pagina appartiene alla famiglia Luoghi: la riga porta le altre
        # tre porte, come fa /piscine.html.
        G.blocco_ecosistema('luoghi'),
        f'    <p class="ev-firma-nota">Pagina rigenerata ogni notte. '
        f'Ultimo aggiornamento: {oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>',
        '  </div>',
    ] if x)

    voci_ld = [{"@type": "ListItem", "position": i,
                "name": l["nome"],
                "url": f'{L.PAGE_URL}#{l["slug"]}'}
               for i, (l, _r) in enumerate(voci, 1)]
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": url, "url": url,
        "name": G.esc(idea["h1"]).replace("&lt;em&gt;", "").replace("&lt;/em&gt;", ""),
        "description": idea["descrizione"],
        "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": G.SITE_URL},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(voci),
                       "itemListOrder": "https://schema.org/ItemListOrderAscending",
                       "itemListElement": voci_ld},
    }
    jsonld = ('<script type="application/ld+json">\n'
              + json.dumps(ld, ensure_ascii=False, indent=1) + '\n</script>')
    robots = "index, follow" if len(voci) >= MINIMO_IN_INDICE else "noindex, follow"
    immagine = idea.get("immagine") or G.DEFAULT_IMG

    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/genera_idee.py: il testo di questa pagina sta in
     data/idee.json, le righe dei luoghi vengono dal catalogo. Le modifiche
     scritte a mano qui dentro spariscono alla run successiva. -->
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(idea["titolo"])}</title>
<meta name="description" content="{e(idea["descrizione"])}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(idea["titolo"])}">
<meta property="og:description" content="{e(idea["descrizione"])}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{e(immagine)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(idea["titolo"])}">
<meta name="twitter:description" content="{e(G.trunc(idea["descrizione"], 120))}">
<meta name="twitter:image" content="{e(immagine)}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preconnect" href="{L.SUPABASE_FOTO}" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{G.PAGINA_CSS}{G.COMUNE_CSS}{L.LUOGHI_CSS}{L._css_categorie(luoghi)}{IDEE_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero lg-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/luoghi.html">Luoghi</a> › <span>{e(idea.get("briciola") or idea["h1"])}</span>
    </div>
    <h1>{h1_html(idea["h1"])}</h1>
    <p class="ev-when">{e(zona)} · {len(voci)} posti in {comuni} comuni · scelti a mano</p>
    <p class="lg-intro">{e(idea["intro"]) if idea.get("intro") else ""}</p>
  </div>
</header>
{pagina}
{G.blocco_ginetto()}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
{L.LUOGHI_JS}
{jsonld}
</body>
</html>
"""


def main():
    idee = leggi_idee()
    if not idee:
        print("[genera_idee] nessuna idea decisa: non scrivo niente")
        return
    oggi = datetime.date.today()

    # Il catalogo si legge una volta sola, con la stessa strada di luoghi.html:
    # foglio se risponde, istantanea se no. Le idee sono poche, il catalogo e'
    # uno.
    foglio = L.leggi_catalogo()
    if not L.controlla_crollo(foglio):
        raise SystemExit(1)
    elenco = L.unisci(L.solo_province_nostre(foglio), L.leggi_agenda())
    if not elenco:
        print("[genera_idee] catalogo vuoto: lascio le pagine come stanno")
        return
    per_codice = {str(l.get("codice") or "").strip(): l for l in elenco}

    os.makedirs(CARTELLA, exist_ok=True)
    fatte = 0
    for idea in idee:
        perche_no = _manca(idea)
        if perche_no:
            print(f"[genera_idee] salto '{idea.get('slug') or '?'}': {perche_no}")
            continue
        voci, persi = voci_della_idea(idea, per_codice)
        if persi:
            print(f"[genera_idee] {idea['slug']}: {len(persi)} luoghi non sono "
                  f"piu' in catalogo ({', '.join(persi)}), la pagina esce senza")
        if len(voci) < 2:
            print(f"[genera_idee] salto '{idea['slug']}': restano meno di due luoghi")
            continue
        percorso = os.path.join(CARTELLA, f"{idea['slug']}.html")
        open(percorso, "w", encoding="utf-8").write(render(idea, voci, oggi))
        if len(voci) >= MINIMO_IN_INDICE:
            L.update_sitemap(len(voci), url_idea(idea["slug"]))
        fatte += 1
        print(f"[genera_idee] idee/{idea['slug']}.html: {len(voci)} luoghi"
              + ("" if len(voci) >= MINIMO_IN_INDICE else " — sotto soglia, noindex"))
    print(f"[genera_idee] {fatte} pagin{'a' if fatte == 1 else 'e'} su {len(idee)}")


if __name__ == "__main__":
    main()
