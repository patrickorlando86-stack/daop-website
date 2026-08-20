#!/usr/bin/env python3
"""
Genera corsi.html dal foglio Google, tab "Attivita".

COSA SONO. Le attivita' continuative: il corso che dura una stagione — scuola
di musica, societa' sportiva, danza, inglese, teatro. Non e' un evento (non ha
una data, ha una stagione) e non e' un luogo (la palestra dove ci vai solo se
sei iscritto non e' una meta di famiglia: il PASSO -1 della procedura di
inserimento la esclude apposta). E' il terzo livello, ed e' nato dal documento
MVP di Giovanni (Cuneo, 19/08/2026).

PERCHE' UNA PAGINA SOLA, E NON UNA PER CORSO. E' la stessa decisione di
luoghi.html: N pagine su template identico col nome scambiato sono la
definizione di scaled content abuse, e la penalizzazione si porta dietro il
dominio — cioe' eventi.html. Qui il rischio e' anche peggiore che sui luoghi,
perche' i corsi sono la cosa piu' fotocopiabile che ci sia: "Under 8", "Under
10", "Under 12" della stessa societa' differiscono per due cifre. Quindi una
pagina, con i corsi raggruppati per realta' e un'ancora per ognuna
(#r-pgs-roccavione): la societa' ha comunque un link suo da mandare su
WhatsApp, che era la richiesta vera, senza che nasca una pagina debole.
Le pagine dedicate si faranno per i clienti che pagano, scritte a mano, una
alla volta — come deciso il 13/08/2026 per i luoghi.

Uso:
    python3 scripts/genera_corsi.py          # richiede rete

Il nome della tab si puo' forzare con ATTIVITA_TAB.
"""
import os
import csv
import io
import json
import datetime
import urllib.request
import urllib.parse

import genera_eventi as G

ROOT = G.ROOT
SITE_URL = G.SITE_URL
SITEMAP_PATH = G.SITEMAP_PATH
FILE = 'corsi.html'
PATH = os.path.join(ROOT, FILE)
URL = f"{SITE_URL}/{FILE}"

# La tab si legge per NOME, prima senza accento e poi con.
#
# ATTENZIONE, questo commento diceva il falso e il falso e' costato una pagina
# pubblicata sbagliata: gviz su una tab che NON esiste non risponde con un
# errore e non risponde con zero righe — risponde col PRIMO foglio del
# documento, che qui e' "Luoghi". Provato il 20/08/2026:
# sheet=TabCheNonEsisteAffatto123 torna 895 righe col catalogo dei luoghi.
# genera_luoghi.py lo sapeva gia' ("gviz risponde comunque, col primo
# foglio") e guarda infatti DUE colonne; questo file era nato credendo il
# contrario e ne guardava una.
#
# Cosa e' successo il 20/08 alle 02:49, e sono TRE difetti in fila — nessuno
# dei quali stava nel foglio, che era a posto:
#   1. _scarica() non passava headers=1, quindi gviz ha indovinato male quante
#      righe fossero intestazione e ha reso la tab illeggibile (il perche' sta
#      nel commento dentro _scarica);
#   2. il ripiego su 'Attività' con l'accento, che non esiste, ha restituito
#      Luoghi — vedi sopra, gviz risponde col primo foglio;
#   3. il controllo si e' accontentato della colonna 'Nome', che Luoghi ha e ha
#      anche Eventi.
# Risultato: 895 schede di agriturismi al posto di 5 corsi. Il primo difetto e'
# la causa, gli altri due sono i due airbag che non si sono aperti.
#
# Quindi non basta chiedersi "ho letto qualcosa": va chiesto "quello che ho
# letto sono corsi".
TAB = os.environ.get('ATTIVITA_TAB')
TABS = [TAB] if TAB else ['Attivita', 'Attività']

# Le colonne che un foglio di CORSI ha e gli altri due fogli no: chi organizza,
# per quali annate, in quale stagione. Ne basta UNA.
#
# Non si guardano 'prova', 'iscrizioni' o 'referenti': un foglio minimo puo'
# non averle. E soprattutto non si guardano 'categoria', 'prezzo', 'orari',
# 'indirizzo' o 'telefono', che sembrano buone e non lo sono — quelle ce le ha
# anche Luoghi, quindi sarebbero un controllo che non controlla niente.
CHIAVI_CORSO = ('org', 'annate', 'stagione')

# I nomi delle colonne sono tollerati in piu' grafie, come nei centri: il foglio
# lo compila una persona e "Città" o "Comune" non devono fare differenza.
COLONNE = {
    'codice': ('codice', 'id corso', 'cod'),
    'nome': ('nome', 'attività', 'attivita', 'corso', 'titolo'),
    'org': ('organizzatore', 'realtà', 'realta', 'societa', 'società', 'ente', 'gestore', 'associazione'),
    'idluogo': ('id', 'id luogo', 'codice luogo'),
    'cat': ('categoria', 'tipo', 'disciplina'),
    'annate': ('annate', 'annata', 'anni di nascita'),
    'eta': ('età', 'eta', 'fascia', 'fascia età'),
    'stagione': ('stagione', 'anno sportivo'),
    'citta': ('città', 'citta', 'comune', 'paese'),
    'prov': ('provincia', 'prov'),
    'sede': ('sede', 'luogo', 'palestra', 'struttura', 'indirizzo'),
    'giorni': ('giorni', 'quando', 'orari', 'orario', 'allenamenti'),
    'periodo': ('periodo', 'durata', 'da/a'),
    'prezzo': ('prezzo', 'costo', 'quota', 'tariffa'),
    'prova': ('prova', 'prova disponibile', 'open day', 'lezione di prova'),
    'iscrizioni': ('iscrizioni', 'iscrizioni aperte', 'stato iscrizioni'),
    'descr': ('descrizione', 'note', 'dettagli'),
    'contatto': ('contatto', 'contatti', 'telefono', 'recapiti'),
    'referenti': ('referenti', 'referente'),
    'loc': ('locandina', 'immagine', 'foto'),
    'lat': ('latitude', 'lat'),
    'lng': ('longitude', 'lng', 'lon'),
    'premium': ('premium',),
    'verificato': ('verificatoil', 'verificato il', 'verificato'),
    # Chiesta da Giovanni il 20/08: "Scopri il corso →". Non c'era nessun campo
    # per il sito della realta', quindi la sua scheda finiva senza via d'uscita.
    'sito': ('sito', 'website', 'sito web', 'link', 'url'),
    # Come su luoghi.html: chi paga porta piu' TESTO, non una posizione migliore.
    'descr_premium': ('descrizione premium', 'descr premium', 'descrizione_premium'),
    # L'open day e' un EVENTO e la sua casa e' la tab Eventi: qui ci sta solo il
    # codice per agganciarlo, cosi' la scheda lo mostra e il calendario resta
    # l'unico posto in cui l'evento vive davvero.
    'openday': ('openday', 'open day', 'codice evento', 'id evento'),
}

# Fasce del filtro eta', quelle suggerite nel documento. Il confronto e' per
# SOVRAPPOSIZIONE, non per contenimento: un corso 6-10 deve uscire sia cercando
# "6-8" sia "9-11", perche' un bambino di 7 anni e uno di 10 ci stanno tutti e
# due. Contenimento vorrebbe dire nasconderlo a entrambi.
FASCE_ETA = [('0-3', '0-3 anni'), ('3-5', '3-5 anni'), ('6-8', '6-8 anni'),
             ('9-11', '9-11 anni'), ('12-14', '12-14 anni'), ('15-99', '15+ anni')]

ACCENTO = ('#5B9BD5', '#eef5fc', '#2c5d8f')

PROV_NOME = {'AL': 'Alessandria', 'AT': 'Asti', 'CN': 'Cuneo', 'TO': 'Torino',
             'NO': 'Novara', 'VC': 'Vercelli', 'BI': 'Biella', 'GE': 'Genova',
             'SV': 'Savona', 'IM': 'Imperia', 'PV': 'Pavia', 'MI': 'Milano'}


def _mappa(header):
    out = {}
    for i, h in enumerate(header):
        h_norm = (h or '').strip().lower()
        for campo, alias in COLONNE.items():
            if h_norm in alias and campo not in out:
                out[campo] = i
    return out


def _e_intestazione(riga):
    """Vero se questa riga e' l'intestazione di un foglio di CORSI.

    Serve il nome del corso E almeno una delle CHIAVI_CORSO, e le due
    condizioni fanno due lavori diversi: 'nome' dice che la riga e' una
    intestazione, le chiavi dicono che il foglio e' quello giusto. Chiedere
    solo la prima vuol dire pubblicare qualsiasi foglio del documento.

    Lo usano sia il controllo in cima a leggi_corsi() sia la ricerca della riga
    di intestazione: devono essere d'accordo, se no si valida una riga e poi si
    legge un'altra."""
    idx = _mappa(riga)
    return idx.get('nome') is not None and any(k in idx for k in CHIAVI_CORSO)


def _scarica(tab):
    # headers=1 NON e' cosmetico, ed e' la riga che ha rotto la pagina il
    # 20/08/2026 non essendoci. Senza quel parametro gviz *indovina* quante
    # righe sono intestazione, e indovina guardando i tipi: se le prime righe di
    # dati sono tutte testo, decide che sono intestazione anche loro e le fonde
    # in una sola, unendo le etichette con uno spazio. In questa tab e'
    # successo esattamente: CODICE, Nome, Organizzatore, Categoria, Annate sono
    # stringhe pure anche nei dati, quindi delle sei righe (intestazione +
    # A001-A005) gviz ne ha fuse cinque e ne ha lasciata una — A005, l'unica con
    # un numero secco in Annate (2012) invece di un intervallo, che rompeva il
    # motivo. Risultato: 1 riga al posto di 5, intestazione illeggibile, tab
    # scartata. Il foglio era e resta a posto.
    #
    # Le altre tab non ne soffrono per caso, non per merito: Eventi ha le date,
    # Luoghi e Centri hanno CAP e coordinate, cioe' un tipo diverso subito. Con
    # headers=1 non c'e' piu' niente da indovinare.
    url = (f"https://docs.google.com/spreadsheets/d/{G.SHEET_ID}/gviz/tq"
           f"?tqx=out:csv&sheet={urllib.parse.quote(tab, safe='')}"
           f"&headers=1"
           f"&_cb={int(datetime.datetime.now().timestamp())}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "daop-corsi-bot", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def stagione_avvio(oggi=None):
    """L'anno in cui comincia la stagione in corso. I corsi ripartono a
    settembre: da luglio in poi si guarda gia' quella nuova (ad agosto le
    societa' stanno annunciando la 2026/2027), da gennaio a giugno e' ancora
    quella cominciata l'anno prima."""
    oggi = oggi or datetime.date.today()
    return oggi.year if oggi.month >= 7 else oggi.year - 1


def eta_range(c):
    """Da `Annate` + `Stagione` alla fascia d'eta'. L'eta' NON si scrive nel
    foglio: le annate sono il dato vero (e' quello che la societa' stampa sulla
    locandina) e l'eta' ne e' il derivato, che slitta di un anno a ogni
    stagione. Misurato su due locandine della PGS Roccavione: l'Under 8 della
    2025/26 dice "2018-2019", quella della 2026/27 dice "2019-2020". Una colonna
    scritta a mano invecchia da sola e ogni settembre pubblica una fascia
    sbagliata.

    ⚠️ La stessa regola vive in app.js (_attivitaEtaRange, repo daop-mobile) per
    la scheda dentro l'app, con la sua guardia in _test-attivita.mjs. Le due
    devono restare d'accordo: se cambi qui, cambia anche li'. Il banco di prova
    e' lo stesso, in tests/corsi.js."""
    anni = [int(x) for x in _numeri4(c.get('annate'))]
    avvio = _numeri4(c.get('stagione'))
    if not anni or not avvio:
        return None
    a = int(avvio[0])
    lo, hi = a - max(anni), a - min(anni)
    return (lo, hi) if 0 <= lo <= hi <= 25 else None


def _numeri4(s):
    import re as _re
    return _re.findall(r'\d{4}', str(s or ''))


def eta_testo(c):
    r = eta_range(c)
    if not r:
        return (c.get('eta') or '').strip()
    return f"{r[0]} anni" if r[0] == r[1] else f"{r[0]}-{r[1]} anni"


def leggi_corsi():
    """Le righe della tab, filtrate sulla stagione in corso.

    Distingue due esiti, come leggi_centri():
      []   il foglio l'abbiamo letto e non c'e' niente -> si puo' riscrivere;
      None il foglio non l'abbiamo letto (rete, tab sparita, intestazione
           irriconoscibile) -> chi non sa niente non riscrive una pagina piena.

    Non e' teoria: il 19/08, alla prima run vera, un generatore che non faceva
    questa distinzione ha pubblicato "0 corsi" su una pagina che ne aveva 5."""
    testo = None
    for tab in TABS:
        try:
            t = _scarica(tab)
        except Exception as err:
            print(f"[genera_corsi] tab '{tab}' non leggibile ({err})")
            continue
        righe = [r for r in csv.reader(io.StringIO(t)) if any(x.strip() for x in r)]
        if righe and any(_e_intestazione(r) for r in righe):
            print(f"[genera_corsi] tab '{tab}': {len(righe) - 1} righe")
            testo = t
            break
        # I due casi si stampano diversi apposta: "manca Nome" e' una tab
        # storta da sistemare nel foglio, "c'e' Nome ma non le chiavi" e' quasi
        # sempre gviz che ha risposto con un'altra tab.
        if righe and any(_mappa(r).get('nome') is not None for r in righe):
            print(f"[genera_corsi] tab '{tab}': c'e' 'Nome' ma nessuna fra "
                  f"{', '.join(CHIAVI_CORSO)} — questo non e' un foglio di "
                  f"corsi (Luoghi ed Eventi hanno 'Nome' anche loro): "
                  f"non lo pubblico")
        else:
            print(f"[genera_corsi] tab '{tab}': nessuna colonna 'Nome' riconosciuta")
    if testo is None:
        return None

    righe = [r for r in csv.reader(io.StringIO(testo)) if any(x.strip() for x in r)]
    hi = next(i for i, r in enumerate(righe) if _e_intestazione(r))
    idx = _mappa(righe[hi])
    ignorate = [h.strip() for i, h in enumerate(righe[hi])
                if h.strip() and i not in idx.values()]
    print(f"[genera_corsi] colonne riconosciute: {', '.join(sorted(idx))}")
    if ignorate:
        print(f"[genera_corsi] colonne ignorate (aggiungere un alias in COLONNE "
              f"se servono): {', '.join(ignorate)}")

    avvio = stagione_avvio()
    out, vecchi = [], 0
    for r in righe[hi + 1:]:
        def val(campo):
            i = idx.get(campo)
            return (r[i].strip() if i is not None and i < len(r) else '')
        if not val('nome'):
            continue
        c = {campo: val(campo) for campo in COLONNE}
        # Una riga SENZA stagione non si scarta: c'e' chi non ragiona per
        # stagioni (un doposcuola tutto l'anno). Si scartano solo le stagioni
        # dichiarate e passate.
        st = _numeri4(c['stagione'])
        if st and int(st[0]) < avvio:
            vecchi += 1
            continue
        out.append(c)
    if vecchi:
        print(f"[genera_corsi] {vecchi} righe di stagioni passate, fuori dall'elenco")
    return out


def is_premium(c):
    return (c.get('premium') or '').strip().lower().replace('sì', 'si') == 'si'


def _cat_foglia(c):
    """"Sport › Pallavolo" -> "Pallavolo". Il secondo livello e' quello che dice
    davvero cos'e' il corso: "Pallavolo" vale piu' di "Sport"."""
    return (c.get('cat') or '').split('›')[-1].strip()


def card(c, idx):
    """Una scheda in stile agenda: riga sempre visibile + dettaglio che si apre
    al tocco. Riusa le classi .event-card/.ev-* del resto del sito."""
    color, tint, ink = ACCENTO
    det_id = f"det-co-{idx}"
    r = eta_range(c)

    bits = []
    et = eta_testo(c)
    if et:
        bits.append(G.esc(et))
    for testo in (c['giorni'], c['citta']):
        if testo:
            bits.append(G.esc(G.trunc(testo, 34)))

    tags = []
    # Chi paga si vede, e si vede che ha pagato: e' la stessa dichiarazione che
    # luoghi.html fa in #come-ordiniamo, e non e' galanteria — art. 22 comma
    # 4-bis del Codice del consumo. Quello che il premium NON fa e' spostare la
    # riga: resta al suo posto alfabetico, dentro la sua realta'.
    if is_premium(c):
        tags.append('<span class="ev-pill is-pagata">★ Scheda completa</span>')
    # La prova e' il campo che decide: un genitore sceglie un corso dopo averlo
    # fatto provare al figlio. Sta in riga, non sepolta nel dettaglio.
    if c['prova']:
        tags.append(f'<span class="ev-pill is-prova">Prova gratuita</span>')
    if c['prezzo']:
        tags.append(f'<span class="ev-pill">{G.esc(G.trunc(c["prezzo"], 22))}</span>')

    righe_det = []
    # La locandina si guarda, quindi qui va l'originale e non la miniatura — e'
    # la stessa regola degli elenchi al contrario. Sta dentro un dettaglio
    # chiuso, che il browser non disegna: con loading=lazy non parte nessuna
    # richiesta finche' la riga non si apre.
    if is_premium(c) and c['loc']:
        src = G.loc_path(c['loc'])
        if src:
            righe_det.append(
                f'<img class="co-loc" src="{G.esc(src)}" alt="Locandina di '
                f'{G.esc(c["nome"])}" loading="lazy" decoding="async">')
    # Il premium aggiunge TESTO, non posizione: se c'e' la descrizione lunga si
    # usa quella, se no si ripiega su quella normale. Mai il contrario.
    testo = (c['descr_premium'] if is_premium(c) and c['descr_premium']
             else c['descr'])
    if testo:
        righe_det.append(f'<p class="event-desc">{G.esc(testo)}</p>')
    if c['prova']:
        righe_det.append(f'<p class="co-prova">Prova: {G.esc(c["prova"])}</p>')
    dove = c['sede'] or c['citta']
    if dove:
        righe_det.append(f'<p class="ev-where">{G.PIN_SVG} {G.esc(dove)}</p>')
    dati = []
    if c['periodo']:
        dati.append(('Periodo', G.esc(c['periodo'])))
    if c['iscrizioni']:
        dati.append(('Iscrizioni', G.esc(c['iscrizioni'])))
    # Il contatto e' UNO, quello della realta'. I referenti restano nomi: sulla
    # locandina di partenza erano cinque cellulari di volontarie e, a confronto
    # con quella dell'anno prima, erano cambiati quasi tutti. Ripubblicarli qui
    # vorrebbe dire mandare le famiglie a telefonare a chi non segue piu' quel
    # gruppo — e un numero personale dentro un archivio consultabile non e' la
    # stessa cosa dello stesso numero stampato su un manifesto.
    if c['contatto']:
        dati.append(('Contatti', G.esc(c['contatto'])))
    if c['referenti']:
        dati.append(('Referenti', G.esc(c['referenti'])))
    if dati:
        righe_det.append('<dl class="co-dati">' + ''.join(
            f'<dt>{k}</dt><dd>{v}</dd>' for k, v in dati) + '</dl>')
    # "Scopri il corso →". Il rel non e' una formalita': un link commerciale che
    # passa PageRank e' uno schema di link, e si paga con un'azione manuale sul
    # DOMINIO — cioe' su eventi.html, che regge il traffico. sponsored dove la
    # presenza e' pagata, nofollow dove e' una nostra segnalazione. Stessa
    # regola di riga() in genera_luoghi.py.
    if c['sito']:
        rel = 'sponsored' if is_premium(c) else 'nofollow'
        righe_det.append(
            f'<p class="co-fuori"><a href="{G.esc(c["sito"])}" '
            f'rel="{rel} noopener" target="_blank">Scopri il corso →</a></p>')
    if c['verificato']:
        # Un corso non scade da solo come un evento: senza questa riga una
        # scheda ferma da un anno e' identica a una aggiornata ieri.
        righe_det.append(f'<p class="co-verif">Dati verificati il {G.esc(c["verificato"])}</p>')

    eta_attr = f' data-etamin="{r[0]}" data-etamax="{r[1]}"' if r else ''
    return f'''        <article class="event-card" data-city="{G.slugify(c['citta'])}" data-prov="{(c['prov'] or '').lower()}" data-cat="{G.slugify(_cat_foglia(c))}" data-prova="{'1' if c['prova'] else '0'}"{eta_attr} style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <h4 class="ev-h"><button class="ev-row" type="button" aria-expanded="false" aria-controls="{det_id}">
            <span class="ev-thumb is-ph" aria-hidden="true">{G.esc(_emoji(c))}</span>
            <span class="ev-main">
              <span class="ev-name">{G.esc(G.trunc(c['nome'], 110))}</span>
              <span class="ev-line">{" · ".join(bits)}</span>
              <span class="ev-tags">{"".join(tags)}</span>
            </span>
            {G.CHEV_SVG}
          </button></h4>
          <div class="ev-det" id="{det_id}" hidden>
            {chr(10) + "            ".join(righe_det)}
          </div>
        </article>'''


def _emoji(c):
    t = f"{c.get('cat','')} {c.get('nome','')}".lower()
    for chiave, e in (('pallavol', '🏐'), ('volley', '🏐'), ('calci', '⚽'),
                      ('basket', '🏀'), ('nuoto', '🏊'), ('danz', '💃'),
                      ('music', '🎵'), ('teatr', '🎭'), ('ingles', '🇬🇧'),
                      ('lingu', '🇬🇧'), ('arti marzial', '🥋'), ('judo', '🥋'),
                      ('karate', '🥋'), ('ginnast', '🤸'), ('arte', '🎨'),
                      ('natur', '🌳'), ('sport', '⚽')):
        if chiave in t:
            return e
    return '🎓'


def toolbar(corsi):
    """Sotto MIN_FILTRI non si stampa niente: si scorre prima l'elenco che una
    tendina. E una tendina con una voce sola e' un comando che non fa niente.

    Oggi la pagina ha 5 corsi di una societa' sola: la barra non esce, ed e'
    giusto. Esce da se' quando i corsi crescono."""
    if len(corsi) < G.MIN_FILTRI:
        return ''
    campi = []
    cats = {G.slugify(_cat_foglia(c)): _cat_foglia(c) for c in corsi if _cat_foglia(c)}
    if len(cats) > 1:
        opts = "".join(f'<option value="{k}">{G.esc(v)}</option>'
                       for k, v in sorted(cats.items(), key=lambda kv: kv[1].lower()))
        campi.append('<select class="ev-select" data-campo="cat" aria-label="Filtra per disciplina">'
                     f'<option value="all">Disciplina</option>{opts}</select>')
    citta = {G.slugify(c['citta']): c['citta'] for c in corsi if c['citta']}
    if len(citta) > 1:
        opts = "".join(f'<option value="{k}">{G.esc(v)}</option>'
                       for k, v in sorted(citta.items(), key=lambda kv: kv[1].lower()))
        campi.append('<select class="ev-select" data-campo="citta" aria-label="Filtra per comune">'
                     f'<option value="all">Comune</option>{opts}</select>')
    # L'eta' entra solo se le righe la dichiarano davvero: con poche righe
    # compilate la tendina non toglierebbe niente, cioe' sarebbe un comando che
    # non fa niente con sei voci invece che con una.
    if sum(1 for c in corsi if eta_range(c)) >= G.MIN_FILTRI:
        opts = "".join(f'<option value="{v}">{t}</option>' for v, t in FASCE_ETA)
        campi.append('<select class="ev-select" data-campo="eta" aria-label="Filtra per età del bambino">'
                     f'<option value="all">Età</option>{opts}</select>')
    # "Solo con prova" solo se divide davvero: se ce l'hanno tutti non toglie
    # niente, se non ce l'ha nessuno idem.
    con_prova = sum(1 for c in corsi if c['prova'])
    if 0 < con_prova < len(corsi):
        campi.append('<label class="ev-chk"><input type="checkbox" data-campo="prova"> '
                     'Solo con prova</label>')
    if not campi:
        return ''
    return f"""    <div class="ev-toolbar" id="co-toolbar">
      <div class="ev-search">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input type="search" id="co-q" placeholder="Cerca un corso, una societa', un paese…" aria-label="Cerca fra i corsi" autocomplete="off">
      </div>
{chr(10).join("      " + c for c in campi)}
    </div>
    <div class="ev-viewbar"><p class="events-count" id="co-count" role="status" aria-live="polite"></p></div>
"""


CSS = """
.co-wrap{max-width:900px;margin:0 auto;padding:0 20px 48px}
.co-crumb{font-size:.85rem;opacity:.85;margin-bottom:10px}
.co-crumb a{color:inherit}
.co-intro{margin:26px 0 20px;font-size:1.02rem;line-height:1.6}
.co-realta{margin:30px 0 10px;scroll-margin-top:120px}
.co-realta h2{font-size:1.18rem;margin:0 0 2px}
.co-realta p{margin:0;font-size:.92rem;opacity:.75}
.ev-pill.is-prova{background:#eaf7ee;color:#2E7D46}
.ev-pill.is-pagata{background:#fdf3e0;color:#8a5a12}
.co-loc{width:100%;max-width:320px;height:auto;border-radius:10px;margin:0 0 10px;display:block}
.co-fuori{margin:10px 0 0}
.co-fuori a{font-weight:700;color:#2c5d8f;text-decoration:none}
.co-fuori a:hover{text-decoration:underline}
.co-prova{margin:8px 0 0;font-weight:600;color:#2E7D46}
.co-dati{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:12px 0 0;font-size:.93rem}
.co-dati dt{opacity:.65}
.co-dati dd{margin:0;font-weight:600}
.co-verif{margin:10px 0 0;font-size:.8rem;opacity:.6}
.co-nota{margin:26px 0 0;padding:14px 16px;border-radius:12px;background:var(--surface,#f5f3f0);font-size:.95rem}
.event-card.is-hidden{display:none}
.co-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
"""

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
  var bar=document.getElementById('co-toolbar');
  if(!bar) return;
  var q=document.getElementById('co-q'), count=document.getElementById('co-count'),
      campi=[].slice.call(bar.querySelectorAll('[data-campo]'));
  function norm(s){return (s||'').toLowerCase();}
  function apply(){
    var term=norm(q&&q.value.trim()), vis=0;
    cards.forEach(function(c){
      var ok=!term||norm(c.textContent).indexOf(term)>=0;
      campi.forEach(function(el){
        if(!ok) return;
        var campo=el.dataset.campo;
        if(campo==='prova'){ if(el.checked && c.dataset.prova!=='1') ok=false; return; }
        var v=el.value;
        if(!v||v==='all') return;
        if(campo==='eta'){
          var f=v.split('-').map(Number), lo=c.dataset.etamin, hi=c.dataset.etamax;
          // Senza eta' dichiarata il corso resta visibile: nasconderlo vorrebbe
          // dire far sparire una realta' vera per un dato che non ci ha dato.
          if(lo!==undefined&&hi!==undefined&&lo!==''&&hi!==''){
            if(!(Number(lo)<=f[1]&&Number(hi)>=f[0])) ok=false;
          }
          return;
        }
        if(c.dataset[campo]!==v) ok=false;
      });
      c.classList.toggle('is-hidden',!ok);
      if(ok) vis++;
    });
    // Una realta' senza piu' nessun corso visibile non deve restare come
    // intestazione sospesa sopra il vuoto.
    [].slice.call(document.querySelectorAll('.co-realta')).forEach(function(h){
      var box=document.getElementById(h.dataset.lista);
      if(!box) return;
      var vivi=box.querySelectorAll('.event-card:not(.is-hidden)').length;
      h.style.display=vivi?'':'none';
      box.style.display=vivi?'':'none';
    });
    campi.forEach(function(el){
      if(el.tagName==='SELECT') el.classList.toggle('is-on',el.value&&el.value!=='all');
    });
    if(count) count.textContent=vis+(vis===1?' corso':' corsi');
  }
  campi.concat([q]).forEach(function(el){
    if(!el) return;
    el.addEventListener('input',apply); el.addEventListener('change',apply);
  });
  apply();
})();
"""


def jsonld(corsi):
    graph = []
    for c in corsi:
        o = {'@type': 'Course', 'name': c['nome'],
             'provider': {'@type': 'Organization', 'name': c['org'] or 'DAOP'}}
        descr = (c['descr'] or '').strip()
        o['description'] = descr or (
            f"{c['nome']}" + (f" con {c['org']}" if c['org'] else '') +
            (f" a {c['citta']}" if c['citta'] else '') + '.')
        # Niente `offers`: la colonna Prezzo e' testo libero, e un prezzo non
        # numerico fa scartare l'offerta a Google. Lezione gia' imparata sugli
        # eventi, dove finiva in errore in Search Console.
        r = eta_range(c)
        if r:
            o['audience'] = {'@type': 'PeopleAudience',
                             'suggestedMinAge': r[0], 'suggestedMaxAge': r[1]}
        if c['citta']:
            o['location'] = {'@type': 'Place', 'name': c['sede'] or c['citta'],
                             'address': {'@type': 'PostalAddress',
                                         'addressLocality': c['citta'],
                                         'addressRegion': 'Piemonte',
                                         'addressCountry': 'IT'}}
        graph.append(o)
    return json.dumps({'@context': 'https://schema.org', '@graph': graph},
                      ensure_ascii=False, indent=1)


def zona(corsi):
    """Il titolo segue i DATI, non la copertura dichiarata. Oggi i corsi sono di
    una provincia sola: un H1 che ne promette tre sarebbe falso, e chi arriva da
    Google se ne accorge in due secondi. Si allarga da solo."""
    provs = []
    for c in corsi:
        p = (c['prov'] or '').strip().upper()
        n = PROV_NOME.get(p, p)
        if n and n not in provs:
            provs.append(n)
    provs.sort()
    if not provs:
        return 'in Piemonte', 'Piemonte'
    if len(provs) == 1:
        return f'in provincia di {provs[0]}', provs[0]
    elenco = ', '.join(provs[:-1]) + ' e ' + provs[-1]
    return f'nelle province di {elenco}', elenco


def render(corsi, css, nav, foot):
    dove, zona_breve = zona(corsi)
    titolo = f"Corsi per bambini {dove} | DAOP"
    descr = (f"Corsi e attività continuative per bambini e ragazzi {dove}: musica, sport, "
             f"danza, lingue, teatro. Con età, giorni, costi e le prove gratuite. Curato a mano.")

    # Raggruppati per realta': una societa' con cinque squadre e' un blocco solo,
    # e la sua ancora (#r-...) e' il link che puo' mandare in giro. E' anche il
    # "collegamento dell'organizzatore con le sue attivita'" del documento, senza
    # che nasca una pagina per ognuna.
    gruppi = {}
    for c in corsi:
        gruppi.setdefault(c['org'] or 'Altre realtà', []).append(c)
    for v in gruppi.values():
        v.sort(key=lambda c: ((eta_range(c) or (999, 999))[0], c['nome'].lower()))

    n = [0]
    blocchi = []
    for org in sorted(gruppi, key=lambda s: s.lower()):
        v = gruppi[org]
        anchor = 'r-' + G.slugify(org)
        lista_id = 'l-' + G.slugify(org)
        luoghi = sorted({c['citta'] for c in v if c['citta']})
        sotto = ' · '.join(filter(None, [
            ', '.join(luoghi),
            f"{len(v)} corsi" if len(v) > 1 else "1 corso",
            next((c['stagione'] for c in v if c['stagione']), ''),
        ]))
        schede = []
        for c in v:
            schede.append(card(c, n[0]))
            n[0] += 1
        blocchi.append(
            f'  <div class="co-realta" id="{anchor}" data-lista="{lista_id}">\n'
            f'    <h2>{G.esc(org)}</h2>\n'
            f'    <p>{G.esc(sotto)}</p>\n'
            f'  </div>\n'
            f'  <div class="events-list" id="{lista_id}">\n' + "\n".join(schede) + '\n  </div>')

    elenco = "\n".join(blocchi) if blocchi else (
        '<p class="co-nota">Le prime schede stanno arrivando. Se hai una scuola, '
        'un\'associazione o una società sportiva, <a href="/ginetto.html">scrivici</a>: '
        'la scheda è gratuita.</p>')

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{G.esc(titolo)}</title>
<meta name="description" content="{G.esc(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{URL}">
<meta property="og:title" content="{G.esc(titolo)}">
<meta property="og:description" content="{G.esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{G.esc(G.trunc(titolo, 60))}">
<meta name="twitter:description" content="{G.esc(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{G.DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-64.png" type="image/png" sizes="64x64">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld(corsi)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero">
  <div class="page-hero-inner">
    <div class="co-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Corsi per bambini</span>
    </div>
    <span class="section-label">{G.esc(zona_breve)} · Famiglie</span>
    <h1>Corsi per bambini <em>{G.esc(dove)}</em></h1>
    <p>Le attività che durano tutto l'anno — sport, musica, danza, lingue — con le età,
    i giorni, i costi e le prove gratuite di settembre. Raccolte a mano, una società
    alla volta.</p>
  </div>
</header>
<article class="co-wrap">
  <p class="co-intro">Un corso non è un evento: comincia a settembre e finisce a primavera,
  e la domanda di un genitore non è "cosa si fa sabato" ma "dove porto mio figlio quest'anno".
  Qui trovi quello che c'è, con quello che serve davvero per decidere: che età prende,
  che giorni, e se si può provare prima di iscriversi.</p>
{toolbar(corsi)}
{elenco}
  <p class="co-nota"><strong>Sei una scuola, un'associazione o una società sportiva?</strong>
  La scheda è gratuita e la compiliamo noi: basta mandarci la locandina che avete già.
  Molte realtà non hanno un sito, e questa pagina diventa il posto dove le famiglie
  vi trovano. <a href="/ginetto.html">Scrivici qui</a>.</p>
  <div class="co-actions">
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


def aggiorna_sitemap():
    if not os.path.exists(SITEMAP_PATH) or not os.path.exists(PATH):
        return
    import re
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding='utf-8').read()
    blocco = (f"  <!-- CORSI:START (generato da scripts/genera_corsi.py — non modificare a mano) -->\n"
              f"  <url>\n    <loc>{URL}</loc>\n    <lastmod>{oggi}</lastmod>\n"
              f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n"
              f"  <!-- CORSI:END -->")
    re_blocco = re.compile(r'  <!-- CORSI:START.*?<!-- CORSI:END -->', re.S)
    if re_blocco.search(s):
        s = re_blocco.sub(blocco, s)
    else:
        s = s.replace('</urlset>', blocco + '\n</urlset>')
    open(SITEMAP_PATH, 'w', encoding='utf-8').write(s)
    print("[genera_corsi] sitemap aggiornata")


def main():
    corsi = leggi_corsi()
    if corsi is None:
        # Il controllo sta QUI, prima di qualunque scrittura, e non in fondo.
        print("[genera_corsi] foglio non letto: lascio la pagina com'è")
        return 0
    css, nav, foot = G._guscio()
    nuovo = render(corsi, css, nav, foot)
    vecchio = open(PATH, encoding='utf-8').read() if os.path.exists(PATH) else ''
    if nuovo != vecchio:
        open(PATH, 'w', encoding='utf-8').write(nuovo)
        print(f"[genera_corsi] {FILE} riscritta — {len(corsi)} corsi")
    else:
        print(f"[genera_corsi] {FILE} invariata — {len(corsi)} corsi")
    aggiorna_sitemap()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
