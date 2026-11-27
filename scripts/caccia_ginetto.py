"""La pagina della caccia di Natale di Ginetto su daop.it (27/11/2026).

/esploratore/caccia-di-natale-<paese>.html, una per caccia in vetrina attiva
(oggi: Novi Ligure). Patrick: «pagina caccia al tesoro di Natale di Ginetto
come sito web, SEO». Su ginettoapp.it c'e' gia' /caccia/novi (netlify function
del repo daop-mobile), ma e' spenta finche' non si scrive la colonna `Sito` e,
soprattutto, sta sul dominio dell'app: chi cerca «caccia al tesoro Natale Novi
Ligure» trova daop.it, che e' il dominio con l'autorita'.

Le decisioni, che non si ricavano dal codice:

- **Si costruisce dal foglio**, tab PuntiCircuito: le stesse righe che usa
  l'app. Righe con `Circuito` che comincia per «Caccia», `Attivo` si, `Demo`
  non si. Raggruppate per percorso; se una citta' ne ha piu' (un anno dopo
  l'altro) vince l'`Al` piu' recente.
- **Niente elenco dei negozi** (Patrick, 27/11: «dai tutti i dettagli dei
  negozi? io non lo farei»): ne' nomi, ne' indirizzi, ne' orari, ne' coupon,
  e niente indovinelli o tappe storiche per nome. La pagina dice quanti sono e
  che la mappa sta nell'app e sul foglio: scoprirli fa parte del gioco.
- **L'indirizzo non porta l'anno** (la regola di /ferragosto.html): il nome del
  percorso «Caccia di Natale · Novi 2026» perde l'anno, e l'edizione 2027
  riscrive la stessa pagina. L'anno sta nel title e nell'H1.
- **Finita la caccia la pagina resta**, `noindex, follow`, fuori sitemap, con
  «torna il prossimo Natale». Si riaccende da sola con le righe nuove.
- **Senza rete non si riscrive niente**: la pagina di ieri resta (la regola di
  genera_centri.py). Per girare a mano senza rete: CACCIA_CSV=file.csv.
- Sta in esploratore/ perche' e' quella la cartella che la run notturna
  committa (e genera_ginetto.py quello che gira): una pagina in una cartella
  nuova vorrebbe una riga nel workflow, che dal cloud non si tocca.
"""
import csv
import datetime
import io
import json
import os
import re
import urllib.request

import genera_eventi as G

ROOT = G.ROOT
CARTELLA = os.path.join(ROOT, "esploratore")
PREFISSO = "caccia-di-natale-"
URL_FOGLIO = (f"https://docs.google.com/spreadsheets/d/{G.SHEET_ID}"
              "/gviz/tq?tqx=out:csv&sheet=PuntiCircuito&headers=1")
APP = "https://ginettoapp.it"

e = G.esc


def _si(v):
    return str(v or "").strip().lower() in ("si", "sì", "x", "true", "1")


def _data(s):
    s = str(s or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
    if m:
        return datetime.date(int(m[3]), int(m[2]), int(m[1]))
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return datetime.date(int(m[1]), int(m[2]), int(m[3]))
    return None


def leggi_righe():
    """Le righe di PuntiCircuito, o None se il foglio non si legge."""
    try:
        if os.environ.get("CACCIA_CSV"):
            testo = open(os.environ["CACCIA_CSV"], encoding="utf-8").read()
        else:
            req = urllib.request.Request(URL_FOGLIO, headers={"User-Agent": "daop-caccia-bot"})
            with urllib.request.urlopen(req, timeout=30) as r:
                testo = r.read().decode("utf-8", "replace")
    except Exception as ex:  # rete, tab che manca: si tiene la pagina di ieri
        print(f"[caccia] foglio non letto ({str(ex)[:80]}): lascio le pagine come sono")
        return None
    righe = list(csv.DictReader(io.StringIO(testo.lstrip("﻿"))))
    # gviz con un tab che non c'e' risponde col PRIMO foglio (il guasto del
    # 20/08 sui corsi): queste due colonne ci sono solo in PuntiCircuito.
    if not righe or "Circuito" not in righe[0] or "Risposta" not in righe[0]:
        print("[caccia] il foglio letto non e' PuntiCircuito: lascio le pagine come sono")
        return None
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in righe]


def _primo(rr, col):
    return next((r[col] for r in rr if r.get(col)), "")


def trova_cacce(righe):
    gruppi = {}
    for r in righe:
        if not re.match(r"(?i)caccia", r.get("Circuito", "")) or not _si(r.get("Attivo")):
            continue
        if _si(r.get("Demo")):
            continue
        gruppi.setdefault(r["Circuito"], []).append(r)
    per_citta = {}
    for nome, rr in gruppi.items():
        citta = rr[0].get("Città") or rr[0].get("Citta") or ""
        titolo = re.sub(r"[\s·\-–]*((?:19|20)\d{2})\s*$", "", nome).strip()
        c = {
            "nome": nome, "titolo": titolo, "citta": citta,
            "prov": rr[0].get("Provincia", ""),
            "slug": PREFISSO + G.slugify(citta),
            "cartella": G.slugify(titolo),
            "dal": _data(_primo(rr, "GiocoDal")) or _data(_primo(rr, "Dal")),
            "al": _data(_primo(rr, "Al")),
            "premi_fino": _data(_primo(rr, "PremiFino")),
            "luogo_premi": _primo(rr, "LuogoPremi"),
            "benvenuto": _primo(rr, "Benvenuto"),
            "stampa": _primo(rr, "Stampa"),
            "negozi": [r for r in rr if not re.match(r"(?i)tappa storic", r.get("Tipo", ""))],
            "storiche": [r for r in rr if re.match(r"(?i)tappa storic", r.get("Tipo", ""))],
        }
        if not c["al"] or not c["negozi"] or not citta:
            continue
        old = per_citta.get(c["slug"])
        if not old or c["al"] > old["al"]:
            per_citta[c["slug"]] = c
    return list(per_citta.values())


def _giorno(d, anno=False):
    s = f"{G.GIORNI[d.weekday()]} {d.day} {G.MESI_LUNGHI[d.month - 1]}"
    return s + (f" {d.year}" if anno else "")


def _periodo(dal, al):
    if not dal:
        return f"il {_giorno(al, True)}"
    if dal.month == al.month:
        return f"dal {dal.day} al {al.day} {G.MESI_LUNGHI[al.month - 1]} {al.year}"
    return (f"dal {dal.day} {G.MESI_LUNGHI[dal.month - 1]} al {al.day} "
            f"{G.MESI_LUNGHI[al.month - 1]} {al.year}")


def _fogli(c):
    out = []
    for s in (c["stampa"] or "").split("|"):
        s = s.strip()
        if not s:
            continue
        et, _, f = s.partition("=") if "=" in s else ("Scarica i fogli da stampare", "", s)
        f = f.strip()
        if not f:
            continue
        url = f if re.match(r"https?://", f) else (
            f"{APP}/{f}" if "/" in f else f"{APP}/percorsi/{c['cartella']}/{f}")
        out.append((et.strip(), url))
    return out


CSS = """
.cc-quando{font-size:1.05rem;font-weight:600}
.cc-bottoni{display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 4px}
.cc-btn{display:inline-flex;align-items:center;min-height:46px;padding:10px 18px;border-radius:12px;
 font-weight:700;text-decoration:none;background:#b3202a;color:#fff}
.cc-btn.carta{background:#fff;color:var(--navy,#2d4a5c);border:2px solid var(--navy,#2d4a5c)}
.cc-nota{font-size:.92rem;color:var(--text-mid,#6a7a85);margin:4px 0 0}
.cc-cop{display:block;width:100%;max-width:720px;height:auto;border-radius:14px;margin:4px 0 18px}
.cc-passi{padding-left:22px;margin:0}.cc-passi li{margin:6px 0;line-height:1.6}
.cc-banco{padding:16px 18px;border-radius:14px;background:#fff6e0;border:1px solid #efd59a;margin:24px 0}
.cc-banco h2{margin-top:0}
.cc-finita{padding:14px 16px;border-radius:12px;background:var(--carta,#fffcf8);border:1px solid var(--linea,#e2d8cb)}
"""


def render(c, oggi, nav, foot, css_sito):
    url = f"{G.SITE_URL}/esploratore/{c['slug']}.html"
    citta, anno = c["citta"], c["al"].year
    fine = c["premi_fino"] or c["al"]
    finita = oggi > fine
    periodo = _periodo(c["dal"], c["al"])
    giorno_banco = c["premi_fino"] or c["al"]
    banco = _giorno(giorno_banco) + (f" in {c['luogo_premi']}" if c["luogo_premi"] else "")
    nn, ns = len(c["negozi"]), len(c["storiche"])
    titolo = f"Caccia al tesoro di Natale {anno} a {citta} per bambini | Ginetto"
    descr = G.trunc(
        f"Caccia al tesoro di Natale per bambini a {citta}, {periodo}: gli indovinelli "
        f"di Ginetto in {nn} vetrine del centro. Gratis, con l'app o su carta, "
        f"e un regalino a ogni bambino.", 158)
    # La copertina dell'app, copiata nel sito (assets/ginetto/<cartella>.webp):
    # cosi' la pagina non dipende da ginettoapp.it. Se manca, quella dell'app.
    locale = f"assets/ginetto/{c['cartella']}.webp"
    copertina = (f"{G.SITE_URL}/{locale}" if os.path.isfile(os.path.join(ROOT, locale))
                 else f"{APP}/percorsi/{c['cartella']}/copertina.webp")
    a_citta = G.a_citta(e(citta))

    benv = "".join(f"<p>{e(p.strip())}</p>"
                   for p in re.split(r"\n+|<br\s*/?>", c["benvenuto"] or "") if p.strip())
    fogli = _fogli(c)
    paese_slug = G.slugify(citta).split("-")[0]
    if finita:
        azioni = (f'<p class="cc-finita">🎄 La caccia di Natale {anno} a {e(citta)} è finita: '
                  'grazie a tutte le famiglie che hanno giocato! Torna il prossimo Natale.</p>')
    else:
        azioni = ('<div class="cc-bottoni">'
                  f'<a class="cc-btn" href="{APP}/scarica?via=caccia-{e(paese_slug)}">📲 Gioca con l\'app Ginetto</a>'
                  + "".join(f'<a class="cc-btn carta" href="{e(u)}" target="_blank" rel="noopener">🖨️ {e(et)}</a>'
                            for et, u in fogli)
                  + '</div><p class="cc-nota">Si gioca gratis. L\'app è per iPhone e Android; '
                  'chi preferisce la carta stampa i fogli e gioca con la penna.</p>')

    luogo = {"@type": "Place", "name": f"Centro di {citta}",
             "address": {"@type": "PostalAddress", "streetAddress": c["luogo_premi"] or "",
                         "addressLocality": citta, "addressRegion": c["prov"], "addressCountry": "IT"}}
    if not c["luogo_premi"]:
        del luogo["address"]["streetAddress"]
    evento = {
        "@type": "Event", "name": f"{c['titolo']} {anno}", "description": descr,
        "startDate": (c["dal"] or c["al"]).isoformat(), "endDate": c["al"].isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": luogo, "image": [copertina], "isAccessibleForFree": True,
        "url": url, "inLanguage": "it",
        "audience": {"@type": "PeopleAudience", "suggestedMinAge": 3, "suggestedMaxAge": 12},
        "organizer": {"@type": "Organization", "name": "DAOP · Dove Andiamo Oggi Papi", "url": G.SITE_URL},
        "offers": {"@type": "Offer", "price": 0, "priceCurrency": "EUR",
                   "availability": "https://schema.org/InStock", "url": url},
    }
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": url, "url": url, "name": titolo, "description": descr,
         "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": G.SITE_URL}},
        evento,
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": G.SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Ginetto l'Esploratore",
             "item": G.SITE_URL + "/esploratore.html"},
            {"@type": "ListItem", "position": 3, "name": f"Caccia di Natale{a_citta}", "item": url}]},
    ]}
    if finita:
        del ld["@graph"][1]

    altro = []
    s = G.slugify(citta)
    if os.path.isfile(os.path.join(ROOT, "eventi", "comune", f"{s}.html")):
        altro.append(f'<a href="/eventi/comune/{s}.html">Gli eventi{a_citta}</a>')
    if os.path.isfile(os.path.join(ROOT, "natale.html")):
        altro.append('<a href="/natale.html">Il Natale con i bambini in zona</a>')
    lib = G.link_libro(citta)
    if lib:
        altro.append(lib)
    lg = G.link_luoghi(citta, c["prov"])
    if lg:
        altro.append(lg)

    robots = "noindex, follow" if finita else "index, follow"
    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/caccia_ginetto.py (via genera_ginetto.py) dal
     foglio, tab PuntiCircuito. Le modifiche scritte a mano spariscono. -->
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titolo)}</title>
<meta name="description" content="{e(descr)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{e(f'Caccia al tesoro di Natale {anno}{a_citta}')}">
<meta property="og:description" content="{e(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{e(copertina)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{e(copertina)}">
<meta name="daop:citta" content="{e(citta)}">
<meta name="daop:provincia" content="{e(c['prov'])}">
<meta name="daop:caccia" content="{fine.isoformat()}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css_sito}{G.PAGINA_CSS}{G.COMUNE_CSS}{CSS}</style>
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
      <a href="/">Home</a> › <a href="/esploratore.html">Ginetto l'Esploratore</a> › <span>Caccia di Natale{a_citta}</span>
    </div>
    <h1>Caccia al tesoro di Natale {anno}{a_citta}</h1>
    <p class="ev-when cc-quando">{e(periodo)} · {nn} vetrine{f' e {ns} tappe storiche' if ns else ''} · gratis</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  <img class="cc-cop" src="{e(copertina.replace(G.SITE_URL, ''))}" alt="Ginetto e Briciola vestiti da Natale: la caccia{a_citta}" width="960" height="480" loading="eager">
  <p>Questo Natale i negozi del centro{a_citta} giocano con Ginetto: in ogni vetrina c'è un indovinello per i bambini, e la risposta è un oggetto da cercare con gli occhi. Si gioca {e(periodo)}, quando volete, a piedi per le vie del centro. Le sorprese si ritirano al banco premi, {e(banco)}.</p>
  {azioni}
  <h2>Come si gioca</h2>
  <ol class="cc-passi">
    <li><b>Scegliete un negozio</b> dall'elenco qui sotto, o dalla mappa nell'app e sul foglio stampato: l'ordine è libero.</li>
    <li><b>Leggete l'indovinello</b> di Ginetto e cercate l'oggetto nella vetrina. Non serve entrare: dove l'oggetto è dentro il negozio, è scritto.</li>
    <li><b>Scrivete la risposta</b> nell'app, o sul foglio. Se sbagliate due volte, arriva un aiutino.</li>
    <li><b>Raccogliete le monete</b>, e dove c'è, il coupon del negozio per le famiglie.</li>
    <li><b>Ritirate il regalino</b> al banco premi, {e(banco)}: basta aver risolto un indovinello.</li>
  </ol>
  <h2>Dove si gioca</h2>
  <p>Nel centro di {e(citta)}, a piedi: {nn} negozi con l'indovinello in vetrina{f' e {ns} tappe storiche, indovinelli sui posti che raccontano la storia della città' if ns else ''}. Quali sono e dove stanno lo dice la mappa, nell'app e sul foglio da stampare: scoprirli fa parte del gioco.</p>
  <section class="cc-banco"><h2>🎁 Il banco premi</h2>
  <p><b>{e(banco[:1].upper() + banco[1:])}</b>. Portate l'app o il foglio compilato: ogni bambino che ha giocato ritira il suo regalino, offerto dai negozi della caccia.</p></section>
  {f'<h2>Benvenuti{a_citta}</h2>{benv}' if benv else ''}
  <h2>Altro{a_citta}</h2>
  <div class="com-link">{"".join(altro)}<a href="/esploratore.html">I libri di Ginetto l'Esploratore</a></div>
  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
{G.blocco_ginetto(citta)}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


def scrivi(oggi=None):
    """Scrive le pagine delle cacce. Ritorna (file tenuti, url da mettere in
    sitemap). Senza foglio tiene le pagine che ci sono, e in sitemap quelle
    ancora in stagione (lette dal meta daop:caccia)."""
    oggi = oggi or datetime.date.today()
    os.makedirs(CARTELLA, exist_ok=True)
    esistenti = sorted(f for f in os.listdir(CARTELLA)
                       if f.startswith(PREFISSO) and f.endswith(".html"))
    righe = leggi_righe()
    if righe is None:
        urls = []
        for f in esistenti:
            m = re.search(r'name="daop:caccia" content="([\d-]+)"',
                          open(os.path.join(CARTELLA, f), encoding="utf-8").read())
            if m and m[1] >= oggi.isoformat():
                urls.append(f"{G.SITE_URL}/esploratore/{f}")
        return set(esistenti), urls
    css, nav, foot = G._guscio()
    tenuti, urls = set(esistenti), []
    for c in trova_cacce(righe):
        f = f"{c['slug']}.html"
        open(os.path.join(CARTELLA, f), "w", encoding="utf-8").write(render(c, oggi, nav, foot, css))
        tenuti.add(f)
        if oggi <= (c["premi_fino"] or c["al"]):
            urls.append(f"{G.SITE_URL}/esploratore/{f}")
        print(f"[caccia] esploratore/{f}: {len(c['negozi'])} vetrine, "
              f"{len(c['storiche'])} tappe storiche, {_periodo(c['dal'], c['al'])}")
    return tenuti, urls
