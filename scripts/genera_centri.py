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
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
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
        # parte in corsivo oro dell'H1, come "Oggi" nell'hero degli eventi
        'h1_em': 'Alessandria e Asti',
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
        'h1_em': 'Alessandria e Asti',
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

    # Il foglio e' compilato a mano e capita la stessa riga due volte (es.
    # "Osterietta Summer", "R-Estate a Bosio"): in pagina uscivano schede
    # doppie. Per ogni centro (nome+citta'+inizio) teniamo la riga piu'
    # completa - piu' descrizione, e con locandina/sito/contatti - cosi' non
    # serve ripulire il foglio a mano ogni volta.
    def _chiave(c):
        return (cslug(c['nome']), cslug(c['citta']), c['d_start'])

    def _punteggio(c):
        return (len(c['descr'] or ''), bool(c['loc'].strip()),
                bool(c['sito'].strip()), bool(c['contatti'].strip()))

    migliori = {}
    for c in out:
        k = _chiave(c)
        if k not in migliori or _punteggio(c) > _punteggio(migliori[k]):
            migliori[k] = c
    doppi = len(out) - len(migliori)
    out = list(migliori.values())

    out.sort(key=lambda c: (c['d_start'] or datetime.date.max, c['nome']))
    coda = f", {scartati} di altra stagione" if scartati else ""
    coda += f", {doppi} doppioni uniti" if doppi else ""
    print(f"[genera_centri] tab '{tab}': {len(out)} centri per '{chiave}'{coda}")
    senza = sum(1 for c in out if c['loc'].strip() and not locandina(c))
    if senza:
        print(f"[genera_centri] ATTENZIONE: {senza} locandine indicate nel foglio "
              f"non esistono nel bucket Supabase, le schede escono senza immagine")
    return out


CSS = """
/* L'intestazione ora e' un .page-hero come negli eventi e compensa lei la nav
   fissa: al contenuto serve solo il respiro sotto l'hero. */
.ce-wrap{max-width:900px;margin:0 auto;padding:34px 20px 40px}
@media(max-width:600px){.ce-wrap{padding:26px 18px 32px}}
/* Il breadcrumb sta dentro l'hero blu: testo chiaro, non il grigio su bianco.
   position:static perche' il CSS del sito ha nav{position:fixed} come selettore
   di elemento e renderebbe fisso anche questo. */
.page-hero .ce-crumb{position:static;font-size:.85rem;color:rgba(255,255,255,0.7);margin:0 0 14px}
.page-hero .ce-crumb a{color:rgba(255,255,255,0.9)}
.page-hero .ce-crumb span{color:rgba(255,255,255,0.7)}
.ce-note{border:1px solid #cfe0d8;background:#f2f8f5;border-radius:14px;padding:16px 18px;margin:22px 0}
.ce-note strong{display:block;margin-bottom:4px}
/* Niente @media (prefers-color-scheme:dark): il sito non ha un tema scuro, il
   body resta crema. La regola che stava qui dipingeva l'avviso di verde scuro
   #1d2a24 lasciandoci sopra il testo scuro, su una pagina chiara. */
/* La lista, le card e la toolbar riusano le classi .ev-*/.event-card definite
   nel <style> di eventi.html, che _guscio() inietta per intero in questa pagina.
   Cosi' i centri hanno la stessa struttura degli eventi senza duplicare il CSS.
   Qui restano solo i pezzi propri della pagina centri (guida, avviso, contatti). */
.ce-contatti{margin:10px 0 0;font-size:.9rem;opacity:.85}
.ce-past-h{margin:2.4em 0 .2em;font-size:1.25rem}
.ce-past-note{opacity:.8;margin:0 0 6px}
.ce-guide h2{margin:2em 0 .5em}
.ce-guide h3{margin:1.6em 0 .35em;font-size:1.05rem}
.ce-guide p,.ce-guide li{line-height:1.7}
.ce-guide ul{padding-left:1.15em}
.ce-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:30px 0 8px}
.ce-actions .btn{color:#fff}
"""

# Icona segnaposto (sole) per le schede senza locandina, e lente per la ricerca:
# inline perche' lo sprite #i-* degli eventi non e' presente in questa pagina.
SUN_SVG = ('<svg class="icon" viewBox="0 0 24 24" width="24" height="24" fill="none" '
           'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
           'stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/>'
           '<path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2'
           'M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>')
SEARCH_SVG = ('<svg viewBox="0 0 24 24" width="18" height="18" fill="none" '
              'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"><circle cx="11" cy="11" r="7"/>'
              '<path d="M21 21l-4.3-4.3"/></svg>')

# Accento cromatico delle card per stagione (le stesse tinte degli eventi:
# arancio "sole" per gli estivi, azzurro per gli invernali).
ACCENTO = {
    'estivi': ('#e8954a', 'rgba(232,149,74,0.14)', '#a75b15'),
    'invernali': ('#4a90b9', 'rgba(74,144,185,0.14)', '#397293'),
}
PROV_LABEL = {'AL': 'Alessandria', 'AT': 'Asti'}


def cslug(s):
    """'Novi Ligure' -> 'novi-ligure', per il valore del filtro Citta'."""
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# Apertura schede + filtri (ricerca, provincia, citta'), in vanilla JS come la
# pagina eventi. I filtri agiscono solo sui centri attivi (#ce-active); le schede
# dell'edizione passata restano come archivio, ma anche loro si aprono al tocco.
FILTER_JS = """
(function(){
  var cards=[].slice.call(document.querySelectorAll('.event-card'));
  cards.forEach(function(c){
    var btn=c.querySelector('.ev-row'), det=c.querySelector('.ev-det');
    if(!btn||!det) return;
    btn.addEventListener('click',function(){
      var open=c.classList.toggle('is-open');
      btn.setAttribute('aria-expanded',open?'true':'false');
      det.hidden=!open;
    });
  });
  var box=document.getElementById('ce-active');
  if(!box) return;
  var items=[].slice.call(box.querySelectorAll('.event-card')),
      q=document.getElementById('ce-q'),
      fp=document.getElementById('ce-prov'),
      fc=document.getElementById('ce-city'),
      empty=document.getElementById('ce-empty'),
      count=document.getElementById('ce-count');
  function norm(s){return (s||'').toLowerCase();}
  function apply(){
    var term=norm(q&&q.value.trim()), p=fp?fp.value:'all', ct=fc?fc.value:'all', vis=0;
    items.forEach(function(c){
      var ok=(p==='all'||c.dataset.province===p)
           &&(ct==='all'||c.dataset.city===ct)
           &&(!term||norm(c.textContent).indexOf(term)>=0);
      c.classList.toggle('is-hidden',!ok);
      if(ok) vis++;
    });
    if(fp) fp.classList.toggle('is-on',p!=='all');
    if(fc) fc.classList.toggle('is-on',ct!=='all');
    if(empty) empty.style.display=vis?'none':'block';
    if(count) count.textContent=vis+(vis===1?' centro':' centri');
  }
  [q,fp,fc].forEach(function(el){ if(el){ el.addEventListener('input',apply); el.addEventListener('change',apply); }});
  apply();
})();
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


_ESISTE = {}


def _immagine_c_e(url):
    """L'immagine risponde davvero a quell'indirizzo?

    Il controllo esiste perche' la colonna Locandina dei centri e' compilata a
    mano e ha sempre contenuto nomi di file mai importati: emetterli comunque
    riempirebbe la pagina di immagini rotte. Prima si guardava sul disco
    (assets/eventi/); ora che l'immagine sta nel bucket Supabase si guarda li',
    che poi e' il posto da cui la prende il browser.

    In caso di dubbio si TIENE l'immagine: solo un 404 o un 400 secco la
    scartano. Un timeout o una rete che fa i capricci in GitHub Actions
    cancellerebbe altrimenti locandine buone dalla pagina."""
    if url in _ESISTE:
        return _ESISTE[url]
    ok = True
    try:
        req = urllib.request.Request(url, method='HEAD',
                                     headers={'User-Agent': 'daop-genera-centri'})
        with urllib.request.urlopen(req, timeout=10):
            pass
    except urllib.error.HTTPError as e:
        ok = e.code not in (400, 404)
    except Exception:
        pass
    _ESISTE[url] = ok
    return ok


def locandina(c):
    """URL della locandina, ma solo se l'immagine c'e' davvero."""
    p = G.loc_path(c['loc'])
    if not p:
        return ''
    return p if _immagine_c_e(p) else ''


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


def card(c, accent, idx):
    """Una scheda in stile agenda eventi: riga sempre visibile (miniatura, nome,
    contesto, etichette) + dettaglio che si apre al tocco, con la locandina
    cliccabile fra le azioni. Riusa le classi .event-card/.ev-* degli eventi."""
    color, tint, ink = accent
    det_id = f"det-ce-{idx}"

    # Riga di contesto: dove, periodo, orario, eta'. Il prezzo diventa pill.
    bits = [f"{G.esc(c['citta'])} ({c['prov']})" if c['citta'] else (c['prov'] or '')]
    for testo in (periodo_testo(c), c['ora'], c['eta']):
        if testo:
            bits.append(G.esc(G.trunc(testo, 30)))
    bits = [b for b in bits if b]

    consigliato = c['consigliato'].strip().lower() in ('si', 'sì', 'x', 'true')
    tags = []
    if consigliato:
        tags.append(f'<span class="ev-pill is-daop">{G.STAR_SVG} Consigliato DAOP</span>')
    pill = G.prezzo_pill(c)
    if pill:
        tags.append(pill)

    link = c['sito'].strip()
    if link and not link.startswith(('http://', 'https://')):
        link = 'https://' + link
    img = locandina(c)
    acts = []
    if link:
        acts.append(f'<a class="event-act" href="{G.esc(link)}" target="_blank" '
                    f'rel="noopener">{G.ACT_ARROW_SVG} Informazioni e iscrizioni</a>')
    # maps_url vuole le stesse chiavi degli eventi: gliele passiamo cosi' come
    # sono, invece di riscrivere la stessa logica.
    mappa = G.maps_url({'indirizzo': c['indirizzo'], 'luogo': c['luogo'],
                        'citta': c['citta'], 'prov': c['prov']})
    if mappa:
        acts.append(f'<a class="event-act" href="{G.esc(mappa)}" target="_blank" '
                    f'rel="noopener">{G.NAV_SVG} Come arrivare</a>')
    if img:
        acts.append(f'<a class="event-act" href="{G.esc(img)}" target="_blank" '
                    f'rel="noopener">{G.IMG_SVG} Locandina</a>')

    # Nel foglio il gestore e' spesso gia' dentro il nome ("ARCEAM - Centro
    # Estivo Novi Ligure"): ripeterlo darebbe "... — ARCEAM".
    gestore = c['gestore'].strip()
    titolo = c['nome']
    if gestore and gestore.lower() not in c['nome'].lower():
        titolo = f"{titolo} — {gestore}"

    thumb = (f'<img class="ev-thumb" src="{G.esc(img)}" alt="" loading="lazy" '
             f'decoding="async">' if img
             else f'<span class="ev-thumb is-ph" aria-hidden="true">{SUN_SVG}</span>')
    dove = G.esc(c['indirizzo'] or c['luogo'] or '')
    dove_html = f'\n            <p class="ev-where">{G.PIN_SVG} {dove}</p>' if dove else ''
    contatti = (f'\n            <p class="ce-contatti">Contatti: {G.esc(c["contatti"])}</p>'
                if c['contatti'] else '')

    return f'''        <article class="event-card" data-province="{c['prov'].lower()}" data-city="{cslug(c['citta'])}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <h4 class="ev-h"><button class="ev-row" type="button" aria-expanded="false" aria-controls="{det_id}">
            {thumb}
            <span class="ev-main">
              <span class="ev-name">{G.esc(G.trunc(titolo, 110))}</span>
              <span class="ev-line">{" · ".join(bits)}</span>
              <span class="ev-tags">{"".join(tags)}</span>
            </span>
            {G.CHEV_SVG}
          </button></h4>
          <div class="ev-det" id="{det_id}" hidden>
            <p class="event-desc">{G.esc(c["descr"])}</p>{dove_html}{contatti}
            <div class="event-actions">
              {chr(10) + "              ".join(acts)}
            </div>
          </div>
        </article>'''


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
    accent = ACCENTO.get(chiave, ACCENTO['estivi'])
    # Un centro concluso non va mostrato come se fosse aperto. Ma l'elenco
    # dell'edizione appena passata resta utile a chi si informa per l'anno
    # prossimo, purche' sia dichiarato per quello che e'.
    oggi = datetime.date.today()
    attivi = [c for c in centri if not c['d_end'] or c['d_end'] >= oggi]
    passati = [c for c in centri if c['d_end'] and c['d_end'] < oggi]

    n = [0]  # indice progressivo, per id univoci dei dettagli (det-ce-N)

    def lista(v, active=False):
        schede = []
        for c in v:
            schede.append(card(c, accent, n[0]))
            n[0] += 1
        idattr = ' id="ce-active"' if active else ''
        return f'<div class="events-list"{idattr}>\n' + "\n".join(schede) + '\n</div>'

    if attivi:
        provs = sorted({c['prov'] for c in attivi if c['prov']})
        opt_prov = ['<option value="all">Tutte le province</option>'] + [
            f'<option value="{p.lower()}">{PROV_LABEL.get(p, p)}</option>' for p in provs]
        citta_map = {}
        for c in attivi:
            if c['citta']:
                citta_map.setdefault(cslug(c['citta']), c['citta'])
        opt_city = ['<option value="all">Tutte le città</option>'] + [
            f'<option value="{k}">{G.esc(v)}</option>'
            for k, v in sorted(citta_map.items(), key=lambda kv: kv[1].lower())]
        toolbar = (
            '  <div class="ev-toolbar">\n'
            f'    <div class="ev-search">{SEARCH_SVG}'
            '<input type="search" id="ce-q" placeholder="Cerca un centro, un paese, un gestore…" '
            'aria-label="Cerca fra i centri"></div>\n'
            f'    <select class="ev-select" id="ce-prov" aria-label="Filtra per provincia">'
            f'{"".join(opt_prov)}</select>\n'
            f'    <select class="ev-select" id="ce-city" aria-label="Filtra per città">'
            f'{"".join(opt_city)}</select>\n'
            '  </div>\n'
            '  <div class="ev-viewbar"><p class="events-count" id="ce-count"></p></div>\n')
        elenco = (toolbar + lista(attivi, active=True)
                  + '\n  <p class="events-empty" id="ce-empty">Nessun centro con questi '
                    'filtri. Prova a togliere qualche filtro.</p>')
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
        elenco += (f'\n<h2 class="ce-past-h">{titolo}</h2>\n'
                   f'<p class="ce-past-note">Le date sono quelle dell\'edizione conclusa: '
                   f'servono a farsi un\'idea di chi organizza in zona, per quali età e a '
                   f'quali prezzi. Verifica sempre con il gestore prima di contare su una '
                   f'riapertura.</p>\n' + lista(passati))

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
<script src="/assets/js/daop-track.js" defer></script>
<script src="/assets/js/locandina.js" defer></script>
<script type="application/ld+json">
{jsonld(cfg, attivi, url)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<!-- HERO — stessa intestazione della pagina eventi (.page-hero arriva dal CSS
     di eventi.html copiato da _guscio(): le due pagine restano coerenti). -->
<header class="page-hero">
  <div class="page-hero-inner">
    <div class="ce-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>{G.esc(cfg['h1'])}</span>
    </div>
    <span class="section-label">Alessandria · Asti · Famiglie</span>
    <h1>{G.esc(cfg['h1'])} <em>{cfg['h1_em']}</em></h1>
    <p>I centri per bambini attivi durante {cfg['periodo']} nelle province di
    Alessandria e Asti, con età, orari e costi. Sotto, la guida per scegliere:
    quando ci si iscrive, cosa chiedere prima e quali documenti servono.</p>
    <p style="margin-top:14px;font-size:0.95rem;opacity:0.9;">Cerchi qualcosa per oggi? Vedi le <a href="/eventi.html" style="color:inherit;text-decoration:underline;text-underline-offset:3px;">sagre e gli eventi in provincia di Alessandria e Asti</a>.</p>
  </div>
</header>
<article class="ce-wrap">
  {avviso}
  {elenco}
  {guida(cfg)}
  <div class="ce-actions">
    <a class="btn btn-navy" href="/eventi.html">Eventi di oggi</a>
    <a class="btn btn-teal" href="/ginetto.html">Chiedi a Ginetto AI</a>
  </div>
</article>
</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
<script>{FILTER_JS}</script>
</body>
</html>
"""


def aggiorna_sitemap(cambiate):
    """Tiene le pagine dei centri nella sitemap, dentro i propri marker.

    Elenca TUTTE le pagine di stagione presenti su disco, non solo quelle
    generate in questa run: il blocco viene riscritto per intero, e passare
    solo la stagione appena rigenerata cancellava le altre dalla sitemap
    (bastava un "genera_centri.py invernali" per far sparire gli estivi).

    Il lastmod si aggiorna solo per le pagine davvero cambiate: ristampare
    la data di oggi su una pagina identica e' un segnale di freschezza falso."""
    if not os.path.exists(SITEMAP_PATH):
        return
    # Ordine stabile e senza doppioni (piu' stagioni possono puntare allo
    # stesso file), limitato alle pagine che esistono davvero.
    files, visti = [], set()
    for cfg in STAGIONI.values():
        f = cfg['file']
        if f not in visti and os.path.exists(os.path.join(ROOT, f)):
            visti.add(f)
            files.append(f)
    if not files:
        print("[genera_centri] nessuna pagina centri su disco, sitemap invariata")
        return

    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding='utf-8').read()
    # lastmod gia' in sitemap, per non azzerarlo su pagine non toccate.
    precedenti = dict(re.findall(
        r'<loc>\s*' + re.escape(SITE_URL) + r'/([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>', s))
    blocco = "\n".join(
        f"  <url>\n    <loc>{SITE_URL}/{f}</loc>\n"
        f"    <lastmod>{oggi if f in cambiate else precedenti.get(f, oggi)}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n    <priority>0.8</priority>\n  </url>"
        for f in files)
    s, n = re.subn(r'(<!-- CENTRI:START.*?-->).*?( *<!-- CENTRI:END -->)',
                   lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
    if n != 1:
        print("[genera_centri] marker CENTRI non trovati in sitemap.xml, salto")
        return
    open(SITEMAP_PATH, 'w', encoding='utf-8').write(s)
    print(f"[genera_centri] sitemap: {len(files)} pagine centri "
          f"({len(cambiate & set(files))} con lastmod aggiornato)")


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
    cambiate = set()   # solo le pagine riscritte davvero: guidano il lastmod
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
            cambiate.add(cfg['file'])
    aggiorna_sitemap(cambiate)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
