#!/usr/bin/env python3
"""
Genera le pagine dei centri estivi/invernali dal foglio Google "luoghi".

Perche' una pagina dedicata: i centri si cercano quando si iscrivono i figli,
cioe' da marzo a giugno per gli estivi e a novembre per gli invernali. Una
pagina pubblicata in stagione arriva tardi, perche' Google impiega giorni o
settimane a scansionarla e posizionarla. Pubblicandola fuori stagione arriva
al picco di domanda con mesi di storia gia' accumulati.

Per lo stesso motivo l'URL e' fissa e si aggiorna ogni anno invece di cambiare:
"centri-estivi.html", non "centri-estivi-2026.html". I segnali accumulati
restano sulla stessa pagina.

La pagina non e' mai vuota: fuori stagione, o se il foglio non e' raggiungibile,
mostra la guida e l'avviso che le iscrizioni riaprono, invece di una lista
vuota. Una pagina vuota per nove mesi l'anno sarebbe contenuto magro.

Uso:
    python3 scripts/genera_centri.py            # tutte le stagioni configurate
    python3 scripts/genera_centri.py estivi     # solo una

Il nome della tab del foglio si puo' forzare con CENTRI_TAB_<STAGIONE>,
es. CENTRI_TAB_ESTIVI="Centri estivi 2026".
"""
import os
import re
import csv
import io
import json
import datetime
import urllib.request
import urllib.parse
import sys

import genera_eventi as G

ROOT = G.ROOT
SITE_URL = G.SITE_URL
SITEMAP_PATH = G.SITEMAP_PATH

# Una voce per stagione. Aggiungere gli invernali significa aggiungere una
# riga qui: il resto del codice non cambia.
STAGIONI = {
    'estivi': {
        'file': 'centri-estivi.html',
        'tab': 'Centri Est/Inv',
        'h1': 'Centri Estivi',
        'singolare': 'centro estivo',
        'titolo': 'Centri Estivi in Provincia di Alessandria e Asti | DAOP',
        'descr': ('Centri estivi per bambini in provincia di Alessandria e Asti: '
                  'elenco con età, orari e costi, e la guida per scegliere e '
                  'iscriversi in tempo.'),
        'periodo': 'giugno, luglio e agosto',
        'iscrizioni': 'fra marzo e maggio',
        'quando_riaprono': 'in primavera',
    },
    'invernali': {
        'file': 'centri-invernali.html',
        'tab': 'Centri Est/Inv',
        'h1': 'Centri Invernali',
        'singolare': 'centro invernale',
        'titolo': 'Centri Invernali e Vacanze di Natale ad Alessandria e Asti | DAOP',
        'descr': ('Centri invernali e attività per bambini durante le vacanze di Natale '
                  'in provincia di Alessandria e Asti: elenco, età, orari e costi, '
                  'con la guida per scegliere.'),
        'periodo': 'le vacanze di Natale e le chiusure scolastiche invernali',
        'iscrizioni': 'fra ottobre e novembre',
        'quando_riaprono': 'in autunno',
    },
}

# Intestazioni accettate per ogni campo. Il foglio e' compilato a mano e le
# intestazioni cambiano nel tempo: meglio riconoscerne piu' di una che rompersi.
COLONNE = {
    'nome': ('nome', 'denominazione', 'centro', 'titolo'),
    'di': ('data inizio', 'inizio', 'dal'),
    'df': ('data fine', 'fine', 'al'),
    'citta': ('città', 'citta', 'comune', 'paese'),
    'prov': ('provincia', 'prov'),
    'eta': ('età', 'eta', 'fascia', 'fascia età', 'fascia eta'),
    'prezzo': ('prezzo', 'costo', 'tariffa', 'quota'),
    'ora': ('ora', 'orario', 'orari'),
    'descr': ('descrizione', 'note', 'dettagli'),
    'luogo': ('luogo', 'sede', 'struttura', 'nome luogo'),
    'indirizzo': ('indirizzo completo', 'indirizzo', 'via'),
    'gestore': ('gestore', 'ente', 'organizzatore', 'associazione'),
    'contatti': ('contatti', 'contatto', 'telefono', 'email', 'recapiti'),
    'sito': ('sito', 'sito web', 'link', 'url', 'iscrizioni'),
    'loc': ('locandina', 'immagine', 'foto'),
    'consigliato': ('consigliato daop', 'consigliato'),
    # Estivi e invernali stanno nella stessa tab. Se una colonna li distingue
    # la usiamo, ma il criterio affidabile sono le date: un centro che parte a
    # giugno e' estivo comunque sia compilata la riga.
    'stagione': ('stagione', 'tipo', 'tipologia', 'est/inv'),
}

# Mesi di inizio che identificano la stagione, quando non c'e' una colonna.
MESI_STAGIONE = {'estivi': (5, 6, 7, 8, 9), 'invernali': (11, 12, 1, 2)}


def _mappa(header):
    """Da intestazione del foglio a nome di campo interno."""
    out = {}
    for i, h in enumerate(header):
        h_norm = (h or '').strip().lower()
        for campo, alias in COLONNE.items():
            if h_norm in alias and campo not in out:
                out[campo] = i
    return out


def leggi_centri(tab, chiave):
    """Righe della tab indicata, filtrate per stagione.

    Distingue due esiti che prima si confondevano:
      []   il foglio l'abbiamo letto e per questa stagione non c'e' niente
           -> la pagina si rigenera fuori stagione, ed e' giusto cosi';
      None il foglio non l'abbiamo letto (rete, tab sparita, intestazione
           irriconoscibile) -> non sappiamo niente, e chi non sa niente non
           riscrive una pagina piena. Bastava un timeout di Google durante la
           run notturna per pubblicare la pagina svuotata."""
    # safe='' e' obbligatorio: la tab si chiama "Centri Est/Inv" e con la quote
    # di default lo slash resterebbe tale, spezzando il parametro sheet.
    url = (f"https://docs.google.com/spreadsheets/d/{G.SHEET_ID}/gviz/tq"
           f"?tqx=out:csv&sheet={urllib.parse.quote(tab, safe='')}"
           f"&_cb={int(datetime.datetime.now().timestamp())}")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "daop-centri-bot",
            "Cache-Control": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            testo = r.read().decode("utf-8", "replace")
    except Exception as err:
        print(f"[genera_centri] tab '{tab}' non leggibile ({err})")
        return None

    righe = [r for r in csv.reader(io.StringIO(testo)) if any(c.strip() for c in r)]
    if not righe:
        print(f"[genera_centri] tab '{tab}': risposta vuota")
        return None
    # L'intestazione e' la prima riga che contiene qualcosa di riconoscibile.
    hi = next((i for i, r in enumerate(righe) if _mappa(r).get('nome') is not None), None)
    if hi is None:
        print(f"[genera_centri] tab '{tab}': nessuna colonna 'Nome' riconosciuta")
        return None
    idx = _mappa(righe[hi])
    # Il foglio si compila a mano e io non posso leggerlo in fase di sviluppo:
    # dire quali colonne sono state riconosciute e quali ignorate e' l'unico
    # modo per accorgersi da subito di un'intestazione fuori elenco.
    ignorate = [h.strip() for i, h in enumerate(righe[hi])
                if h.strip() and i not in idx.values()]
    print(f"[genera_centri] colonne riconosciute: {', '.join(sorted(idx))}")
    if ignorate:
        print(f"[genera_centri] colonne ignorate (aggiungere un alias in COLONNE "
              f"se servono): {', '.join(ignorate)}")
    for campo in ('citta', 'eta', 'di', 'descr'):
        if campo not in idx:
            print(f"[genera_centri] nota: manca la colonna '{campo}', le schede "
                  f"usciranno senza quel dato")

    parola = 'invern' if chiave == 'invernali' else 'estiv'
    mesi = MESI_STAGIONE[chiave]
    out, scartati = [], 0
    for r in righe[hi + 1:]:
        def val(campo):
            i = idx.get(campo)
            return (r[i].strip() if i is not None and i < len(r) else '')
        if not val('nome'):
            continue
        prov = val('prov').upper()
        if prov and prov not in ('AL', 'AT'):
            continue
        c = {campo: val(campo) for campo in COLONNE}
        c['d_start'] = G.pdate(c['di'])
        c['d_end'] = G.pdate(c['df']) or c['d_start']

        # La colonna stagione, se c'e' ed e' compilata, ha la precedenza.
        # Altrimenti decide il mese di inizio, che e' il dato piu' affidabile.
        st = c['stagione'].lower()
        if st:
            se = parola in st
        elif c['d_start']:
            se = c['d_start'].month in mesi
        else:
            se = chiave == 'estivi'   # senza date, il default e' l'estivo
        if not se:
            scartati += 1
            continue
        out.append(c)

    out.sort(key=lambda c: (c['d_start'] or datetime.date.max, c['nome']))
    coda = f", {scartati} di altra stagione" if scartati else ""
    print(f"[genera_centri] tab '{tab}': {len(out)} centri per '{chiave}'{coda}")
    senza = sum(1 for c in out if c['loc'].strip() and not locandina(c))
    if senza:
        print(f"[genera_centri] ATTENZIONE: {senza} locandine indicate nel foglio "
              f"non esistono in assets/eventi/, le schede escono senza immagine")
    return out


CSS = """
.ce-wrap{max-width:880px;margin:0 auto;padding:148px 20px 40px}
@media(max-width:600px){.ce-wrap{padding:120px 18px 32px}}
.ce-crumb{position:static;font-size:.85rem;opacity:.7;margin:0 0 10px}
.ce-crumb a{color:inherit}
.ce-lead{font-size:1.06rem;line-height:1.7;margin:.4em 0 1.6em}
.ce-note{border:1px solid #cfe0d8;background:#f2f8f5;border-radius:14px;padding:16px 18px;margin:22px 0}
.ce-note strong{display:block;margin-bottom:4px}
@media (prefers-color-scheme:dark){.ce-note{background:#1d2a24;border-color:#3c5548}}
.ce-list{list-style:none;padding:0;margin:26px 0;display:grid;gap:14px}
.ce-card{border:1px solid rgba(45,74,92,0.14);border-radius:16px;overflow:hidden;display:flex;gap:16px;align-items:flex-start}
.ce-img{flex:0 0 116px;width:116px;height:auto;object-fit:cover;align-self:stretch}
.ce-body{padding:16px 18px;min-width:0}
@media(max-width:600px){.ce-card{flex-direction:column;gap:0}.ce-img{flex:none;width:100%;max-height:210px}}
.ce-card h3{margin:0 0 6px;font-size:1.08rem;line-height:1.3}
.ce-badge{display:inline-block;margin-left:8px;padding:2px 9px;border-radius:100px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;background:var(--orange,#e8954a);color:#fff;vertical-align:middle}
.ce-contatti{margin-top:8px;font-size:.9rem;opacity:.85}
.ce-links{margin-top:10px;display:flex;flex-wrap:wrap;gap:16px}
.ce-meta{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.86rem;opacity:.85;margin:0 0 8px}
.ce-card p{margin:0;line-height:1.6}
.ce-card a.ce-go{display:inline-block;margin-top:10px;font-weight:600;text-decoration:underline;text-underline-offset:3px}
.ce-guide h2{margin:2em 0 .5em}
.ce-guide h3{margin:1.6em 0 .35em;font-size:1.05rem}
.ce-guide p,.ce-guide li{line-height:1.7}
.ce-guide ul{padding-left:1.15em}
.ce-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:30px 0 8px}
.ce-actions .btn{color:#fff}
"""


def guida(cfg):
    """La parte che vale tutto l'anno. Senza questa la pagina sarebbe vuota
    nove mesi su dodici, cioe' contenuto magro."""
    return f"""
<section class="ce-guide">
  <h2>Come scegliere un {cfg['singolare']}</h2>
  <p>La scelta si gioca su poche cose concrete, e quasi tutte si chiariscono con
  una telefonata prima di iscrivere. Ecco cosa conviene chiedere.</p>

  <h3>Quando ci si iscrive</h3>
  <p>Le iscrizioni si aprono di solito {cfg['iscrizioni']}, cioè molto prima
  dell'inizio delle attività. I posti nelle strutture più richieste finiscono
  nelle prime settimane, quindi conviene informarsi con anticipo anche se non
  si è ancora deciso. Molti gestori chiedono un acconto per bloccare il posto e
  permettono di scegliere le settimane singolarmente.</p>

  <h3>Le domande che contano</h3>
  <ul>
    <li><strong>Rapporto educatori/bambini.</strong> È il dato che più incide
    sulla qualità della giornata. Chiedete quanti adulti ci sono per gruppo e
    come sono divise le fasce d'età.</li>
    <li><strong>Chi sono gli educatori.</strong> Formazione, esperienza, e se
    sono le stesse persone per tutto il periodo o cambiano ogni settimana.</li>
    <li><strong>Orari reali.</strong> Non solo apertura e chiusura, ma se
    esistono l'ingresso anticipato e l'uscita posticipata, e quanto costano.</li>
    <li><strong>Pranzo.</strong> Mensa interna, catering o pranzo al sacco. E
    come gestiscono allergie e intolleranze.</li>
    <li><strong>Cosa si fa davvero.</strong> Una giornata tipo dice più di un
    volantino: quanto tempo all'aperto, quante uscite, se c'è la piscina e come
    ci si arriva.</li>
    <li><strong>In caso di maltempo.</strong> Dove si sta e cosa si fa quando
    non si può uscire: è la differenza fra una bella settimana e una lunga.</li>
    <li><strong>Cosa succede se il bambino si assenta.</strong> Se la quota si
    recupera o si perde, in caso di malattia o di cambio programma.</li>
  </ul>

  <h3>Cosa serve per iscriversi</h3>
  <p>Di norma servono il modulo di iscrizione firmato da chi esercita la
  responsabilità genitoriale, i recapiti di più di una persona reperibile in
  caso di necessità, l'elenco di eventuali allergie o terapie in corso e le
  deleghe per chi può ritirare il bambino. Diverse strutture chiedono anche un
  certificato medico: verificate per tempo, perché ottenerlo può richiedere
  giorni. I documenti richiesti cambiano da gestore a gestore, quindi fatevi
  dare l'elenco completo al momento della prenotazione.</p>

  <h3>Sui costi</h3>
  <p>Il prezzo dipende soprattutto dalla durata della giornata, dalla presenza
  del pranzo e dal numero di uscite o gite incluse. Confrontate a parità di
  condizioni: una quota più bassa senza mensa e con uscita alle 13 non è più
  conveniente di una più alta a tempo pieno. Chiedete sempre cosa è incluso e
  cosa si paga a parte — trasporti, piscina, materiali, magliette.</p>
  <p>Informatevi anche su riduzioni per più figli iscritti, tariffe agevolate
  per residenti, contributi comunali e sulle misure di sostegno alle famiglie
  attive nell'anno in corso: cambiano spesso, e vale la pena chiedere
  direttamente al gestore e al proprio Comune quali siano disponibili.</p>

  <h3>Bambini con esigenze particolari</h3>
  <p>Se vostro figlio ha una disabilità, una patologia da gestire durante la
  giornata o semplicemente fatica nei gruppi grandi, parlatene prima
  dell'iscrizione e non il primo giorno. Chiedete se è previsto un educatore di
  supporto, come viene organizzato e con quale preavviso va richiesto: spesso
  dipende da finanziamenti che vanno attivati per tempo.</p>

  <h3>Il primo giorno</h3>
  <p>Per i più piccoli, o alla prima esperienza fuori casa, chiedete se è
  possibile un inserimento graduale. E preparate lo zaino con l'essenziale:
  cambio completo, borraccia, cappellino, crema solare se si sta all'aperto, e
  tutto marcato con nome e cognome.</p>
</section>
"""


def locandina(c):
    """Percorso della locandina, ma solo se il file c'e' davvero.

    La colonna Locandina dei centri contiene nomi di immagini che nel repo non
    esistono: sono riferimenti a file mai importati. Emetterli comunque
    riempirebbe la pagina di immagini rotte. Le locandine degli eventi invece
    ci sono tutte, quindi il controllo non toglie niente a loro."""
    p = G.loc_path(c['loc'])
    if not p:
        return ''
    if p.startswith(('http://', 'https://')):
        return p
    return p if os.path.exists(os.path.join(ROOT, p.lstrip('/'))) else ''


def periodo_testo(c):
    """'dal 15 giugno al 31 luglio' dalle due colonne di data."""
    di, df = c['d_start'], c['d_end']
    if not di:
        return ''
    M = G.MESI_LUNGHI
    if not df or df == di:
        return f"{di.day} {M[di.month - 1]}"
    if di.month == df.month:
        return f"dal {di.day} al {df.day} {M[df.month - 1]}"
    return f"dal {di.day} {M[di.month - 1]} al {df.day} {M[df.month - 1]}"


def card(c):
    meta = []
    dove = " · ".join(x for x in (c['citta'], c['luogo']) if x)
    if dove:
        meta.append(G.esc(dove))
    for testo in (periodo_testo(c), c['eta'], c['ora'], c['prezzo']):
        if testo:
            meta.append(G.esc(testo))

    link = c['sito'].strip()
    if link and not link.startswith(('http://', 'https://')):
        link = 'https://' + link
    azioni = []
    if link:
        azioni.append(f'<a class="ce-go" href="{G.esc(link)}" target="_blank" '
                      f'rel="noopener">Informazioni e iscrizioni</a>')
    # maps_url vuole le stesse chiavi degli eventi: gliele passiamo cosi' come
    # sono, invece di riscrivere la stessa logica.
    mappa = G.maps_url({'indirizzo': c['indirizzo'], 'luogo': c['luogo'],
                        'citta': c['citta'], 'prov': c['prov']})
    if mappa:
        azioni.append(f'<a class="ce-go" href="{G.esc(mappa)}" target="_blank" '
                      f'rel="noopener">Come arrivare</a>')
    contatti = (f'<p class="ce-contatti">{G.esc(c["contatti"])}</p>'
                if c['contatti'] else '')

    # Nel foglio il gestore e' spesso gia' dentro il nome ("ARCEAM - Centro
    # Estivo Novi Ligure"): ripeterlo darebbe "... — ARCEAM".
    gestore = c['gestore'].strip()
    titolo = c['nome']
    if gestore and gestore.lower() not in c['nome'].lower():
        titolo = f"{titolo} — {gestore}"
    badge = ('<span class="ce-badge">Consigliato DAOP</span>'
             if c['consigliato'].strip().lower() in ('si', 'sì', 'x', 'true') else '')

    img = locandina(c)
    figura = (f'<img class="ce-img" src="{G.esc(img)}" alt="Locandina di '
              f'{G.esc(c["nome"])}" loading="lazy">') if img else ''

    return (f'<li class="ce-card">\n  {figura}\n  <div class="ce-body">\n'
            f'    <h3>{G.esc(titolo)}{badge}</h3>\n'
            f'    <p class="ce-meta">{" · ".join(meta)}</p>\n'
            f'    <p>{G.esc(c["descr"])}</p>\n    {contatti}\n'
            f'    <p class="ce-links">{" ".join(azioni)}</p>\n  </div>\n</li>')


def jsonld(cfg, centri, url):
    """ItemList dei centri. Non usiamo Event: un centro estivo e' un servizio
    con iscrizione, non un evento con una data di inizio precisa, e dichiararlo
    Event produrrebbe dati strutturati falsi."""
    graph = [{
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": cfg['h1'], "item": url},
        ],
    }]
    if centri:
        graph.append({
            "@type": "ItemList",
            "name": f"{cfg['h1']} in provincia di Alessandria e Asti",
            "numberOfItems": len(centri),
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1,
                 "item": {"@type": "LocalBusiness",
                          "name": c['nome'],
                          "address": {"@type": "PostalAddress",
                                      "addressLocality": c['citta'],
                                      "addressRegion": c['prov'] or 'AL',
                                      "addressCountry": "IT"}}}
                for i, c in enumerate(centri) if c['nome'] and c['citta']
            ],
        })
    return json.dumps({"@context": "https://schema.org", "@graph": graph},
                      ensure_ascii=False, indent=2)


def render(chiave, cfg, centri, css, nav, foot):
    url = f"{SITE_URL}/{cfg['file']}"
    # Un centro concluso non va mostrato come se fosse aperto. Ma l'elenco
    # dell'edizione appena passata resta utile a chi si informa per l'anno
    # prossimo, purche' sia dichiarato per quello che e'.
    oggi = datetime.date.today()
    attivi = [c for c in centri if not c['d_end'] or c['d_end'] >= oggi]
    passati = [c for c in centri if c['d_end'] and c['d_end'] < oggi]

    def lista(v):
        return '<ul class="ce-list">\n' + "\n".join(card(c) for c in v) + '\n</ul>'

    if attivi:
        elenco = lista(attivi)
        avviso = ''
    else:
        elenco = ''
        avviso = (f'<div class="ce-note"><strong>Iscrizioni non ancora aperte</strong>'
                  f'L\'elenco aggiornato torna online appena i gestori pubblicano date e '
                  f'tariffe, di solito {cfg["quando_riaprono"]}. Qui sotto trovi la guida '
                  f'per arrivare preparato alla scelta, e nell\'<a href="/eventi.html">'
                  f'agenda DAOP</a> quello che c\'è in programma in questi giorni.</div>')

    if passati:
        titolo = ("Anche questi hanno aperto quest'anno" if attivi
                  else f"I centri dell'edizione {passati[-1]['d_end'].year}")
        elenco += (f'\n<h2>{titolo}</h2>\n'
                   f'<p>Le date sono quelle dell\'edizione conclusa: servono a farsi '
                   f'un\'idea di chi organizza in zona, per quali età e a quali prezzi. '
                   f'Verifica sempre con il gestore prima di contare su una riapertura.</p>\n'
                   + lista(passati))

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{G.esc(cfg['titolo'])}</title>
<meta name="description" content="{G.esc(cfg['descr'])}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{G.esc(cfg['titolo'])}">
<meta property="og:description" content="{G.esc(cfg['descr'])}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{G.esc(G.trunc(cfg['titolo'], 60))}">
<meta name="twitter:description" content="{G.esc(G.trunc(cfg['descr'], 120))}">
<meta name="twitter:image" content="{G.DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script type="application/ld+json">
{jsonld(cfg, attivi, url)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<article class="ce-wrap">
  <div class="ce-crumb" role="navigation" aria-label="Percorso">
    <a href="/">Home</a> › <span>{G.esc(cfg['h1'])}</span>
  </div>
  <header>
    <h1>{G.esc(cfg['h1'])} in Provincia di <em>Alessandria e Asti</em></h1>
    <p class="ce-lead">I centri per bambini attivi durante {cfg['periodo']} nelle
    province di Alessandria e Asti, con età, orari e costi. Sotto, la guida per
    scegliere: quando ci si iscrive, cosa chiedere prima e quali documenti servono.</p>
  </header>
  {avviso}
  {elenco}
  {guida(cfg)}
  <div class="ce-actions">
    <a class="btn btn-navy" href="/eventi.html">Sagre ed eventi di oggi</a>
    <a class="btn btn-teal" href="/ginetto.html">Chiedi a Ginetto AI</a>
  </div>
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


def aggiorna_sitemap(files):
    """Tiene le pagine dei centri nella sitemap, dentro i propri marker."""
    if not os.path.exists(SITEMAP_PATH):
        return
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding='utf-8').read()
    blocco = "\n".join(
        f"  <url>\n    <loc>{SITE_URL}/{f}</loc>\n    <lastmod>{oggi}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>"
        for f in files)
    s, n = re.subn(r'(<!-- CENTRI:START.*?-->).*?( *<!-- CENTRI:END -->)',
                   lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
    if n != 1:
        print("[genera_centri] marker CENTRI non trovati in sitemap.xml, salto")
        return
    open(SITEMAP_PATH, 'w', encoding='utf-8').write(s)
    print(f"[genera_centri] sitemap: {len(files)} pagine centri")


# Stagioni generate senza argomenti. Gli invernali sono configurati ma NON
# attivi: con la sola guida cambiata nei riferimenti di stagione le due pagine
# risultano identiche al 97,7%, cioe' contenuto duplicato. Prima di attivarli
# va scritta una guida propria (le vacanze di Natale hanno durata, orari e
# problemi diversi dall'estate). Nel frattempo si generano a richiesta con
# "python3 scripts/genera_centri.py invernali".
ATTIVE = ['estivi']


def main(argv):
    chiavi = argv or ATTIVE
    ignote = [k for k in chiavi if k not in STAGIONI]
    if ignote:
        raise SystemExit(f"[genera_centri] stagione sconosciuta: {', '.join(ignote)}")
    css, nav, foot = G._guscio()
    scritte = []
    for chiave in chiavi:
        cfg = STAGIONI[chiave]
        tab = os.environ.get(f"CENTRI_TAB_{chiave.upper()}", cfg['tab'])
        centri = leggi_centri(tab, chiave)
        path = os.path.join(ROOT, cfg['file'])
        if centri is None:
            # Il foglio non l'abbiamo letto. Se la pagina c'e' gia', resta
            # com'e': meglio un elenco vecchio di un giorno che una pagina
            # svuotata e committata al posto di quella buona.
            if os.path.exists(path):
                print(f"[genera_centri] {cfg['file']}: foglio non letto, "
                      f"lascio la pagina com'e'")
                scritte.append(cfg['file'])
                continue
            print(f"[genera_centri] {cfg['file']}: foglio non letto e pagina "
                  f"assente, la creo fuori stagione")
            centri = []
        nuovo = render(chiave, cfg, centri, css, nav, foot)
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            print(f"[genera_centri] {cfg['file']}: invariata")
        else:
            open(path, 'w', encoding='utf-8').write(nuovo)
            print(f"[genera_centri] {cfg['file']}: scritta ({len(centri)} centri)")
        scritte.append(cfg['file'])
    aggiorna_sitemap(scritte)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
