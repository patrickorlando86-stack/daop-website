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
import re
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


def _eta_numeri(t):
    """I numeri di un'eta' scritta a parole, ognuno convertito in ANNI.

    Nasce il 28/08/2026 da un corso vero: "Accarezzami - Corso di massaggio
    infantile", eta' "0-12 mesi". Letta come anni dava la fascia 0-12, cioe' il
    massaggio ai lattanti compariva nel filtro di chi cerca per un dodicenne, e
    la riga in pagina diceva "mesi" mentre il filtro contava anni. E' l'unica
    cosa che questa pagina non puo' permettersi: la riga e il filtro devono dire
    la stessa cosa, ed e' esattamente quello che tests/corsi.js sorveglia.

    L'unita' e' quella scritta DOPO il numero, e chi non ce l'ha prende quella
    del primo numero che la porta: in "0-12 mesi" e' il 12 a dire mesi e lo zero
    la eredita, in "da 6 mesi a 3 anni" ognuno ha la sua. Senza unita' scritta
    si legge in anni, che e' come e' sempre stato.

    I mesi si troncano all'anno (12 mesi = 1 anno, 6 mesi = 0): una fascia
    d'eta' non e' un compleanno, e un corso per lattanti sta nell'anno zero.
    """
    import re as _re
    pezzi = list(_re.finditer(r'\d{1,2}', t))
    unita = []
    for i, m in enumerate(pezzi):
        coda = t[m.end():pezzi[i + 1].start() if i + 1 < len(pezzi) else len(t)]
        unita.append('mesi' if _re.search(r'\bmes', coda)
                     else 'anni' if _re.search(r'\bann', coda) else None)
    # All'indietro: "0-12 mesi" ha l'unita' solo in fondo, ed e' di tutti e due.
    for i in range(len(unita) - 2, -1, -1):
        if unita[i] is None:
            unita[i] = unita[i + 1]
    return [int(m.group()) // 12 if u == 'mesi' else int(m.group())
            for m, u in zip(pezzi, unita)]


def eta_da_testo(testo):
    """La fascia (lo, hi) letta da un'eta' SCRITTA A PAROLE, o None.

    Nasce dal feedback di Giovanni del 26/08/2026 - "nella schedina manca
    l'eta': fondamentale, altrimenti non funzionano i filtri" - e dalla ragione
    per cui mancava: eta_range() la ricava dalle ANNATE, e una scuola di musica
    le annate non le stampa. Sui quattro volantini di Crome c'era scritto "per
    bambini 3-5 anni", "a partire dai 4 anni", "non ci sono limiti d'eta'":
    informazione buona, che nessun filtro poteva leggere.

    E' un'altra cosa dalle annate, e non le sostituisce: un'annata slitta di un
    anno a ogni stagione ("Under 8" = 2018-2019, poi 2019-2020), un'eta'
    stampata su un volantino no - "dai 3 ai 5 anni" descrive il corso, non una
    leva di nati. Per questo qui si puo' leggere senza che invecchi.

    Tre forme, e basta quelle: "3-5 anni" (due numeri), "dai 4 anni" (da la' in
    su), "fino a 10 anni" (da zero a la'). "Tutte le eta'" non da' nessuna
    fascia a posta: non e' un filtro, e' l'assenza di filtro.

    L'unita' la legge _eta_numeri(): "0-12 mesi" e' la fascia 0-1, non 0-12.
    """
    import re as _re
    t = (testo or '').strip().lower()
    if not t:
        return None
    numeri = _eta_numeri(t)
    if not numeri:
        return None
    if len(numeri) >= 2:
        lo, hi = min(numeri[:2]), max(numeri[:2])
    elif _re.search(r'\b(fino|entro|max|massimo)\b', t):
        lo, hi = 0, numeri[0]
    else:
        # "dai 4 anni", "a partire dai 4 anni", "4+": il tetto e' quello del
        # sito (18), non 25: sopra i 18 non e' piu' un corso per bambini e la
        # fascia larghissima farebbe comparire il corso in ogni filtro.
        lo, hi = numeri[0], 18
    return (lo, hi) if 0 <= lo <= hi <= 25 else None


def eta_min_max(c):
    """La fascia da usare PER FILTRARE: prima le annate, poi l'eta' scritta.

    Sta a parte da eta_range() a posta. eta_range() e' la regola gemella di
    _attivitaEtaRange in app.js (repo daop-mobile) e le due devono restare
    identiche: qui dentro invece c'e' un RIPIEGO che di la' non c'e' ancora.
    Tenerle separate vuol dire che il gemello non e' rotto - fa quello che ha
    sempre fatto - e che quando si porta anche la' si sa esattamente cosa
    portare.
    """
    return eta_range(c) or eta_da_testo(c.get('eta'))


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


def _registro():
    """Il registro delle pagine evento, letto una volta sola e indicizzato per
    nome. E' la stessa fonte da cui nascono le schede: qui serve solo a
    risolvere il nome di un open day nella sua pagina e nella sua data."""
    if _registro.cache is None:
        _registro.cache = {}
        for slug, rec in G.carica_registro().items():
            chiave = G.slugify(rec.get('nome') or '')
            if chiave:
                _registro.cache.setdefault(chiave, []).append((slug, rec))
    return _registro.cache


_registro.cache = None


def openday(c, oggi=None):
    """La riga "Open day" di un corso: quando e', e il link alla sua scheda.

    IL LEGAME SI SCRIVE UNA VOLTA, nella colonna OpenDay del corso, e il valore
    e' il NOME dell'evento copiato dalla tab Eventi. Non un codice: un codice
    andrebbe inventato e ricordato, il nome ce l'hai gia' davanti. E la
    direzione e' questa e non l'opposta perche' un open day serve PIU' corsi —
    la PGS ne fa uno per cinque squadre: cosi' e' lo stesso nome in cinque
    celle, invece di cinque corsi elencati dentro una cella dell'evento.

    L'open day sta nella tab Eventi e non qui perche' HA UNA DATA, cioe' e' un
    evento: da li' si prende da solo la scheda, il calendario, il JSON-LD, la
    pagina del comune e il messaggio del giovedi' sul canale. Nessuna di quelle
    superfici va costruita una seconda volta.

    NON si ricalcola lo slug con slug_evento(): si cerca nel registro, che lo
    slug se lo porta scritto. Cosi' il legame non dipende dalle regole dello
    slug ne' dal fatto che nel foglio la citta' sia scritta giusta — e
    slug_evento() senza citta' restituisce "<nome>-evento", che sarebbe una
    pagina che non esiste.

    Un nome che non trova niente NON stampa un link rotto: tace, come fa
    link_luoghi() con le ancore inesistenti. Un link che scarica su una pagina
    sbagliata e' peggio di nessun link."""
    voce = (c.get('openday') or '').strip()
    if not voce:
        return None
    # UN OPEN DAY CHE IN AGENDA NON C'E'. Succede, e non e' un caso storto: la
    # realta' annuncia l'open day sul proprio sito settimane prima che l'evento
    # arrivi nel foglio, e finche' non c'e' la riga non c'e' la scheda. Allora
    # la cella porta l'indirizzo, e dopo una barra verticale la data e l'ora
    # scritte come vanno lette:
    #     https://esempio.it/corsi | Martedi' 22 settembre 2026 | 17:30
    # Il rimando esce dal sito e lo dice. Se la data manca resta il solo link:
    # meglio un link giusto senza data che una data inventata.
    # E' un ripiego DICHIARATO, non la strada maestra. Quando l'evento entra in
    # agenda si rimette il nome e si riprendono scheda, locandina, calendario,
    # JSON-LD e pagina del comune, che un link a casa d'altri non da'.
    if voce.lower().startswith(('http://', 'https://')):
        pezzi = [x.strip() for x in voce.split('|')]
        return {'url': pezzi[0],
                'quando': pezzi[1] if len(pezzi) > 1 else '',
                'ora': pezzi[2] if len(pezzi) > 2 else ''}
    trovati = _registro().get(G.slugify(voce))
    if not trovati:
        return None
    oggi = oggi or datetime.date.today()
    # Un open day passato non si annuncia: sarebbe un invito a una porta chiusa.
    # Fra piu' edizioni con lo stesso nome vince la prima che deve ancora
    # finire, che e' quella a cui si fa ancora in tempo ad andare.
    futuri = []
    for slug, rec in trovati:
        try:
            di = datetime.date.fromisoformat(rec['d_start'])
            df = datetime.date.fromisoformat(rec['d_end'])
        except (KeyError, TypeError, ValueError):
            continue
        if df >= oggi:
            futuri.append((di, df, slug, rec))
    if not futuri:
        return None
    di, df, slug, rec = min(futuri, key=lambda x: (x[0], x[2]))
    return {'url': f"/eventi/{slug}.html",
            'quando': G.periodo_esteso({'d_start': di, 'd_end': df}),
            'ora': (rec.get('ora') or '').strip()}


def _a_openday(od, testo):
    """Il link di un open day, dentro il sito o fuori.

    Un rimando che porta via dal sito lo deve dire prima che uno ci clicchi:
    scheda nuova e rel="noopener", come ogni altro link a casa d'altri qui
    dentro. Sta in una funzione perche' i punti che lo stampano sono due — la
    riga del corso e la scheda della realta' — e divergerebbero al primo
    ritocco."""
    if od['url'].startswith('http'):
        return (f'<a href="{G.esc(od["url"])}" target="_blank" rel="noopener">'
                f'{testo}</a>')
    return f'<a href="{od["url"]}">{testo}</a>'


# ── LA TAB "Realta": una riga per societa', non per corso ─────────────────
#
# Giovanni (21/08/2026) vuole che #r-pgs-roccavione sia la scheda della societa':
# logo, descrizione, comune, indirizzo, sito, contatti, attivita' che organizza,
# corsi, appuntamenti speciali. Nella tab Attivita niente di tutto questo esiste,
# e non ci deve stare: sarebbero lo stesso logo e la stessa descrizione ricopiati
# su cinque righe, che e' il modo piu' sicuro di farli divergere.
#
# Quindi una tab a parte, LETTA SE C'E'. Se non c'e' la scheda si costruisce
# lo stesso, con quello che si ricava dai corsi (comuni, discipline, sede, sito,
# contatto): meno ricca, mai vuota, mai rotta. E' la regola di link_luoghi() —
# quello che manca non si stampa, non si inventa.
COLONNE_REALTA = {
    # 'nome' NON accetta la parola secca "Nome", ed e' apposta: vedi il commento
    # su gviz sopra. Se la tab non esiste, gviz risponde col PRIMO foglio del
    # documento, che e' Luoghi — e Luoghi ha "Nome", "Descrizione", "Indirizzo",
    # "Citta'", "Website", "Telefono", "Email". Chiedendo una colonna che si
    # chiami "Organizzatore" (o "Realta'", o "Societa'") il ripiego non passa,
    # perche' quella colonna Luoghi non ce l'ha.
    'nome': ('organizzatore', 'realtà', 'realta', 'società', 'societa',
             'ente', 'associazione', 'nome realtà', 'nome realta'),
    # Lo STATO della trattativa, e da qui dipende se la pagina entra in Google
    # (vedi confermata()). Una parola in una cella, scritta da una persona: e'
    # l'unico passaggio del giro che una persona deve fare.
    'stato': ('stato', 'stato scheda', 'fase'),
    'descr': ('descrizione', 'descrizione breve', 'presentazione', 'note'),
    'logo': ('logo', 'immagine', 'stemma'),
    'citta': ('città', 'citta', 'comune', 'paese'),
    'indirizzo': ('indirizzo', 'sede', 'via'),
    'sito': ('sito', 'website', 'sito web', 'link', 'url'),
    'tel': ('telefono', 'tel', 'cellulare', 'contatto'),
    'email': ('email', 'mail', 'e-mail', 'posta'),
    # Due colonne e non una "Social" sola: chi compila il foglio incolla un URL
    # per volta, e una colonna unica diventa "ig: @tizio, fb: pagina" — cioe' un
    # testo da cui il generatore non ricava un link. Sono anche le due tappe
    # finali del percorso che si restituisce alle realta' (sito, telefono,
    # email, social) e senza un link cliccabile quella colonna resta vuota per
    # sempre: daop-track.js riconosce instagram.com e facebook.com da se'.
    'instagram': ('instagram', 'ig', 'profilo instagram'),
    'facebook': ('facebook', 'fb', 'pagina facebook'),
}

TAB_REALTA = os.environ.get('REALTA_TAB')
TABS_REALTA = [TAB_REALTA] if TAB_REALTA else ['Realta', 'Realtà', 'Organizzatori']


def _mappa_realta(header):
    """Da intestazione a indice di colonna. VINCE L'ALIAS PIU' PRECISO.

    Prima vinceva la colonna piu' a SINISTRA, e su un foglio vissuto non e' la
    stessa cosa. Il 26/08/2026 la tab Realta aveva due colonne per il comune:
    "Comune" in D (rimasta da una versione vecchia) e "Città" in K, che e' quella
    che il downloader scrive. Il generatore leggeva D, cioe' la colonna vuota, e
    la pagina si salvava solo perche' _dati_realta ripiega sul comune dei corsi:
    su una societa' con la sede in un comune diverso da dove tiene i corsi
    avrebbe pubblicato quello sbagliato, e in silenzio.
    Ordinare per posizione nella lista degli alias risolve senza toccare il
    foglio di nessuno: il primo alias e' il nome canonico, quello che scriviamo
    noi, e i successivi restano ripieghi per le grafie di chi compila a mano.
    """
    out = {}
    for i, h in enumerate(header):
        h_norm = (h or '').strip().lower()
        for campo, alias in COLONNE_REALTA.items():
            if h_norm not in alias:
                continue
            preciso = alias.index(h_norm)
            if campo not in out or preciso < out[campo][0]:
                out[campo] = (preciso, i)
    return {campo: i for campo, (_p, i) in out.items()}


def leggi_realta(orgs):
    """Le schede delle realta', indicizzate per nome. {} se la tab non c'e'.

    `orgs` sono i nomi degli organizzatori che stanno davvero nei corsi, e sono
    il terzo airbag dopo il nome della colonna: una riga che non corrisponde a
    nessuna societa' in pagina viene buttata via. Cosi' anche se un giorno gviz
    rispondesse con un foglio a caso che per disgrazia ha una colonna
    "Organizzatore", quel foglio non riuscirebbe comunque a entrare in pagina.

    Il confronto e' sullo slug, cioe' a meno di maiuscole, accenti, spazi e
    punteggiatura AI BORDI: "crome in movimento" e "Crome in Movimento " sono la
    stessa societa' e non devono diventare due schede.

    ATTENZIONE a cosa NON fa, perche' qui c'era scritto il contrario e il
    contrario e' comodo da credere: slugify() non toglie la punteggiatura, la
    trasforma in trattini. "P.G.S. Roccavione" diventa `p-g-s-roccavione` e
    "PGS Roccavione" diventa `pgs-roccavione` - due slug diversi, quindi due
    societa' diverse in pagina, ognuna con la sua meta' dei corsi. Misurato il
    25/08/2026 con una prova, non dedotto. L'unico rimedio e' scrivere il nome
    allo stesso modo nel foglio: normalizzare piu' di cosi' vorrebbe dire
    decidere da soli che due nomi diversi sono lo stesso ente."""
    chiavi = {G.slugify(o) for o in orgs if o}
    for tab in TABS_REALTA:
        try:
            t = _scarica(tab)
        except Exception as err:
            print(f"[genera_corsi] tab realta' '{tab}' non leggibile ({err})")
            continue
        righe = [r for r in csv.reader(io.StringIO(t)) if any(x.strip() for x in r)]
        hi = next((i for i, r in enumerate(righe)
                   if _mappa_realta(r).get('nome') is not None), None)
        if hi is None:
            continue
        idx = _mappa_realta(righe[hi])
        out = {}
        for r in righe[hi + 1:]:
            def val(campo):
                i = idx.get(campo)
                return (r[i].strip() if i is not None and i < len(r) else '')
            k = G.slugify(val('nome'))
            if not k or k not in chiavi:
                continue
            out[k] = {campo: val(campo) for campo in COLONNE_REALTA}
        print(f"[genera_corsi] tab '{tab}': {len(out)} realta' riconosciute "
              f"su {len(chiavi)} in pagina")
        return out
    print("[genera_corsi] nessuna tab realta': le schede si ricavano dai corsi")
    return {}


def _uniche(valori):
    """I valori distinti, nell'ordine in cui si incontrano. Serve per i campi
    che si ricavano dai corsi: se cinque squadre della stessa societa' hanno la
    stessa palestra, l'indirizzo si scrive una volta."""
    out = []
    for v in valori:
        v = (v or '').strip()
        if v and v not in out:
            out.append(v)
    return out


def _dati_realta(org, corsi_org, info):
    """I dati di una realta': comune, indirizzo, attività, contatti, sito,
    social. Una lista di coppie, non HTML gia' impaginato.

    Sta fuori da scheda_realta() perche' li usano in due — la scheda in fondo a
    corsi.html e la pagina dedicata — e un secondo elenco scritto a mano
    divergerebbe al primo campo aggiunto. E' la stessa ragione per cui la nav
    si rilegge da eventi.html invece di essere copiata.

    Quello che il foglio non dice si ricava dai corsi: e' il motivo per cui
    questi dati non sono mai vuoti, nemmeno il primo giorno."""
    dati = []
    comuni = _uniche([info.get('citta')]) or _uniche(c['citta'] for c in corsi_org)
    if comuni:
        dati.append(('Dove', G.esc(', '.join(comuni))))
    indirizzi = _uniche([info.get('indirizzo')]) or _uniche(c['sede'] for c in corsi_org)
    if indirizzi:
        dati.append(('Indirizzo', G.esc(' · '.join(indirizzi[:2]))))
    # Le attivita' che organizza: e' la stessa disciplina che sta in riga sui
    # corsi, qui riunita. Detta una volta sola non e' una ripetizione, e' il
    # riassunto di cosa fa questa societa'.
    disc = _uniche(_cat_foglia(c) for c in corsi_org)
    if disc:
        dati.append(('Attività', G.esc(' · '.join(disc))))
    tel = (info.get('tel') or '').strip() or (
        _uniche(c['contatto'] for c in corsi_org)[:1] or [''])[0]
    if tel:
        # Vedi il commento in card(): un numero non cliccabile non si misura.
        dati.append(('Contatti', G.contatti_html(tel)))
    mail = (info.get('email') or '').strip()
    if mail:
        dati.append(('Email', f'<a href="mailto:{G.esc(mail)}">{G.esc(mail)}</a>'))
    sito = (info.get('sito') or '').strip() or (
        _uniche(c['sito'] for c in corsi_org)[:1] or [''])[0]
    if sito:
        # Stesso rel dei link "Scopri il corso": la presenza e' pagata, quindi
        # sponsored. Vedi il commento in card().
        dati.append(('Sito', f'<a href="{G.esc(sito)}" rel="sponsored noopener" '
                             f'target="_blank">{G.esc(G.trunc(sito, 46))}</a>'))
    social = []
    for campo, etichetta in (('instagram', 'Instagram'), ('facebook', 'Facebook')):
        u = (info.get(campo) or '').strip()
        if u:
            social.append(f'<a href="{G.esc(u)}" rel="sponsored noopener" '
                          f'target="_blank">{etichetta}</a>')
    if social:
        dati.append(('Social', ' · '.join(social)))
    return dati


def _paragrafi(testo, classe):
    """Il testo di una societa' in paragrafi, non in un muro.

    La descrizione della tab Realta la scrive una PERSONA, e chi scrive di se'
    va a capo: la presentazione arrivata il 26/08/2026 era in sei capoversi.
    Finiva tutta dentro un <p> solo, e in HTML gli a-capo valgono spazi - quindi
    sul sito diventava un blocco unico da leggere col dito. Si taglia sulle
    righe vuote e, se non ce ne sono, sui singoli a-capo: un testo scritto tutto
    di fila resta un paragrafo solo, com'e' giusto."""
    t = (testo or '').strip()
    if not t:
        return ''
    pezzi = [p.strip() for p in re.split(r'\n\s*\n', t) if p.strip()]
    if len(pezzi) == 1:
        pezzi = [p.strip() for p in t.split('\n') if p.strip()]
    return ''.join(f'<p class="{classe}">{G.esc(p)}</p>' for p in pezzi)


def scheda_realta(org, corsi_org, info):
    """La scheda di una societa': l'ancora #r-… che le si manda su WhatsApp.

    Sta IN FONDO alla pagina e non in mezzo all'elenco, che e' la seconda meta'
    della decisione del 21/08: in cima c'e' l'elenco dei corsi, perche' un
    genitore sceglie un corso e non una societa'. Ma la societa' e' il passo
    successivo, e la sua scheda deve esistere davvero — con un indirizzo, un
    numero, e i suoi corsi linkati uno per uno.

    QUANDO ESISTE ANCHE LA PAGINA DEDICATA la scheda non sparisce, ed e' voluto:
    resta il riassunto in fondo all'elenco (l'ancora #r-… gira nei messaggi da
    prima che le pagine esistessero) e guadagna un link verso la pagina. Toglierla
    romperebbe quei link per guadagnare niente."""
    a = _ancora(org)
    dentro = []
    logo = (info.get('logo') or '').strip()
    if logo:
        dentro.append(f'<img class="co-logo" src="{G.esc(logo)}" alt="Logo di '
                      f'{G.esc(org)}" loading="lazy" decoding="async">')
    descr = (info.get('descr') or '').strip()
    if descr:
        # In fondo all'elenco basta l'attacco: la descrizione intera si legge
        # sulla pagina della realta', che e' anche la ragione per andarci.
        if ha_pagina(info):
            dentro.append(f'<p class="co-realta-d">'
                          f'{G.esc(G.trunc(descr, 220))}</p>')
        else:
            # Nessuna pagina dedicata: qui c'e' TUTTO il testo, quindi i
            # capoversi contano (vedi _paragrafi).
            dentro.append(_paragrafi(descr, 'co-realta-d'))

    # SINTETICA SE HA UNA PAGINA SUA (26/08/2026, Giovanni: "le schede
    # potrebbero essere anche piu' sintetiche, immaginando di avere piu' realta'
    # ancora, cosi' da scorrerle piu' facilmente"). Ha ragione, e la regola che
    # regge e' quella del doppione: contatti e elenco corsi non si perdono, sono
    # a un clic e su quella pagina stanno scritti meglio. Ripeterli qui allunga
    # una lista che serve a SCORRERE.
    # Quando la pagina NON c'e', invece, questa scheda e' l'unico posto dove
    # quelle informazioni esistono: resta piena com'era.
    if not ha_pagina(info):
        dati = _dati_realta(org, corsi_org, info)
        if dati:
            dentro.append('<dl class="co-dati">' + ''.join(
                f'<dt>{k}</dt><dd>{v}</dd>' for k, v in dati) + '</dl>')

        # I corsi che organizza, linkati alla loro riga: e' quello che rende
        # questa scheda una scheda e non un riquadro di contatti.
        voci = ' · '.join(f'<a href="#{_id_corso(c)}">{G.esc(c["nome"])}</a>'
                          for c in corsi_org)
        dentro.append(f'<p class="co-realta-corsi"><strong>'
                      f'{"Corsi" if len(corsi_org) > 1 else "Corso"}:</strong> {voci}</p>')
    else:
        # Un numero, non un elenco: dice la dimensione senza occupare tre righe.
        dentro.append(f'<p class="co-realta-corsi">'
                      f'{len(corsi_org)} '
                      f'{"corsi" if len(corsi_org) > 1 else "corso"}'
                      + (f' · {G.esc(", ".join(_uniche(_cat_foglia(c) for c in corsi_org)[:3]))}'
                         if _cat_foglia(corsi_org[0]) else '') + '</p>')

    # Gli appuntamenti speciali. Restano EVENTI e vivono nella tab Eventi: qui
    # se ne stampa solo il rimando, come fa la riga open day dei corsi. Un
    # saggio o una festa di Natale entra da li' e compare anche in agenda, nella
    # pagina del comune e nel messaggio del giovedi'.
    speciali, visti = [], set()
    for c in corsi_org:
        od = openday(c)
        if od and od['url'] not in visti:
            visti.add(od['url'])
            speciali.append(
                _a_openday(od, G.esc(od['quando']) or 'sul sito →'))
    if speciali:
        dentro.append('<p class="co-realta-ev"><strong>Open day e appuntamenti:'
                      '</strong> ' + ' · '.join(speciali) + '</p>')

    if ha_pagina(info):
        dentro.append(f'<p class="co-realta-vai"><a href="{url_realta(org)}">'
                      f'La pagina di {G.esc(org)} →</a></p>')

    # <div> e non <section>: section{padding:100px 24px} arriva dal CSS di
    # sistema, e una scheda nascosta dai filtri lascerebbe 200px di niente.
    # IL NOME E' CLICCABILE quando c'e' una pagina dove andare (26/08/2026,
    # Giovanni: "metterei cliccabile direttamente il nome"). Non sostituisce il
    # link in fondo alla scheda: il nome e' il primo posto dove uno clicca, e
    # trovarlo morto e' un clic che non risponde.
    titolo = (f'<a href="{url_realta(org)}">{G.esc(org)}</a>'
              if ha_pagina(info) else G.esc(org))
    return (f'  <div class="co-realta" id="{a}" data-org="{G.slugify(org)}"'
            f' data-org-nome="{G.esc(org)}">\n'
            f'    <h3>{titolo}</h3>\n    '
            + '\n    '.join(dentro) + '\n  </div>')


# ── LA PAGINA DELL'ORGANIZZATORE ─────────────────────────────────────────
#
# Chiesta da Giovanni il 21/08/2026: "mi ero immaginato che ci fosse proprio una
# pagina organizzatori, non solo la scheda nella pagina generale dei corsi, in
# modo da poterci mettere dentro gli eventi organizzati da quell'organizzatore
# li', con locandina e tutto".
#
# PERCHE' ADESSO SI PUO', VISTO CHE PER I LUOGHI SI ERA DETTO DI NO. Il rischio
# dello scaled content abuse e' di VOLUME: erano le 800 pagine su template
# identico col nome scambiato a essere il problema, non quaranta pagine con
# dentro materiale vero — sta gia' scritto in CLAUDE.md, ed e' la ragione per
# cui le pagine dedicate dei luoghi si fanno "per i clienti che pagano, una alla
# volta". Qui la condizione e' soddisfatta per costruzione: dal 21/08 la
# presenza nella guida e' una sola ed e' pagata, quindi ogni organizzatore con
# una pagina E' un cliente con del materiale. Gli organizzatori sono decine, non
# centinaia, e ognuno porta descrizione, logo, indirizzo, contatti, i suoi corsi
# e i suoi eventi.
#
# LA SOGLIA NON E' UN NUMERO DI CORSI, E' IL MATERIALE. Una societa' con otto
# squadre e nessuna descrizione farebbe una pagina piu' povera della scheda che
# ha gia' in corsi.html, cioe' un doppione debole del proprio riassunto. Quindi:
# serve una riga nella tab Realta (che e' l'atto deliberato — nessuno ci finisce
# per sbaglio) E una descrizione vera. Senza, resta la scheda e basta, che e'
# esattamente com'era fino a ieri.
#
# COSA MANCA PER FARLA COMPLETA. Gli eventi qui dentro sono solo quelli
# agganciati dai corsi con la colonna OpenDay: un saggio di fine anno o la festa
# di Natale della stessa societa' non hanno oggi nessun legame con lei. Per
# averli servirebbe una colonna "Organizzatore" nella tab EVENTI, scritta con lo
# stesso nome — e a quel punto questa pagina li raccoglie da se'.
MIN_DESCR_REALTA = 120
DIR_REALTA = 'corsi'


# Gli stati che valgono "la societa' ha detto sì". Sono tre e non uno perche' il
# giro va avanti: il programma sposta "confermata" in "pubblicata" quando ha
# fatto il suo (vedi avanza_stati_realta nel downloader), e "fatturata" e' un
# fatto commerciale che non deve far uscire la pagina dall'indice.
# Il confronto e' sul PRIMO pezzo della cella: chi scrive a mano aggiunge le date
# ("confermata 26/08"), e una parola in piu' non deve valere un no.
STATI_CONFERMATI = ('confermata', 'confermato', 'pubblicata', 'pubblicato',
                    'fatturata', 'fatturato', 'ok', 'si', 'sì')


def confermata(info):
    """La societa' ha confermato i suoi dati?

    E' la condizione per mettere la sua pagina in Google, e sostituisce
    l'interruttore a mano che c'era prima. Il commento di CORSI_IN_INDICE lo
    diceva gia': "si riaccende quando i corsi in pagina sono dati verificati -
    non c'e' una soglia automatica apposta, il problema non e' quanti corsi ci
    sono, e' che quelli che ci sono vanno confermati da chi li organizza". Quel
    "chi li organizza" adesso ha una cella dove rispondere.

    Vuoto vuol dire NO. Una scheda appena nata non e' confermata, e il silenzio
    non si interpreta mai come un sì: e' la stessa regola dei luoghi ("senza un
    sì umano non si genera niente").
    """
    prima = (info or {}).get('stato', '').strip().lower().split()
    return bool(prima) and prima[0].strip('.,;:') in STATI_CONFERMATI


def ha_pagina(info):
    """Vero se questa realta' si merita una pagina sua.

    Due condizioni, e fanno due lavori diversi: la riga nella tab Realta dice
    che qualcuno l'ha decisa, la descrizione dice che c'e' qualcosa da leggere.
    Con la sola prima nascerebbero pagine vuote appena il foglio si popola; con
    la sola seconda non nascerebbe niente, perche' la descrizione sta li'."""
    return len((info or {}).get('descr', '').strip()) >= MIN_DESCR_REALTA


def slug_realta(org):
    return G.slugify(org or 'altre-realta')


def url_realta(org):
    return f"/{DIR_REALTA}/{slug_realta(org)}.html"


def raggruppa_per_realta(corsi):
    """I corsi raggruppati per SOCIETA': una voce per realta' vera.

    La chiave e' lo SLUG del nome, non il nome. "Crome in Movimento" e "crome
    in  movimento" sono la stessa societa' scritta da due locandine diverse, e
    finche' si raggruppava sulla stringa grezza diventavano due voci: due schede
    con meta' dei corsi ciascuna, ma con la STESSA ancora e lo STESSO file in
    corsi/ - perche' quelli passano da slugify() da sempre. Cioe' un id doppio in
    pagina, il link mandato alla societa' che ne apriva una sola, l'altra meta'
    dei corsi invisibile a chi cliccava, e la pagina dedicata riscritta due volte
    con l'elenco dimezzato.

    Quello che questo NON risolve, e va detto qui perche' e' il posto dove uno
    viene a cercarlo: "P.G.S. Roccavione" e "PGS Roccavione" fanno due slug
    diversi (slugify trasforma i punti in trattini, non li toglie), quindi
    restano due societa'. Li' non c'e' codice che tenga: il nome va scritto
    uguale nel foglio.
    La tab Realta era gia' d'accordo con questa lettura (leggi_realta confronta
    gli slug, e il suo commento lo dice: "non devono diventare due schede"): era
    il raggruppamento a non esserlo.

    Il nome che si MOSTRA e' la grafia piu' frequente fra quelle trovate, a pari
    merito la piu' lunga - che di solito e' quella scritta per intero. Il nome lo
    stampa la scheda, quindi si sceglie quello che la societa' usa di piu', non
    il primo che capita nell'ordine dell'elenco.

    Due societa' DAVVERO diverse con lo stesso slug finirebbero insieme: e' un
    caso che l'ancora e il nome del file avevano gia', e tenerlo uguale in tutti
    e tre i posti e' meglio che avere un raggruppamento che non corrisponde ai
    link che pubblica."""
    per_slug = {}
    for c in corsi:
        nome = c['org'] or 'Altre realtà'
        per_slug.setdefault(G.slugify(nome), []).append((nome, c))
    gruppi = {}
    for voci in per_slug.values():
        grafie = {}
        for nome, _ in voci:
            grafie[nome] = grafie.get(nome, 0) + 1
        etichetta = max(grafie, key=lambda n: (grafie[n], len(n)))
        gruppi[etichetta] = [c for _, c in voci]
    return gruppi


def eventi_realta(corsi_org):
    """Gli eventi di questa realta', presi dagli open day dei suoi corsi.

    Uno stesso open day serve piu' corsi — la PGS ne fa uno per cinque squadre —
    quindi si deduplica sull'URL. Restano EVENTI e vivono nella tab Eventi: da
    li' prendono scheda, locandina, calendario, JSON-LD e pagina del comune, e
    qui se ne stampa solo il rimando. Nessuna di quelle superfici va costruita
    una seconda volta."""
    reg = G.carica_registro()
    per_slug = {}
    for c in corsi_org:
        od = openday(c)
        if not od:
            continue
        # L'open day che sta fuori (vedi openday()) non ha una riga in agenda,
        # quindi non ha ne' locandina ne' nome: la scheda si fa lo stesso, col
        # segnaposto del calendario e la sede del corso, perche' su questa
        # pagina e' l'unica cosa che scade e sparire sarebbe peggio.
        if od['url'].startswith('http'):
            rec = {'nome': 'Open day', 'luogo': c['sede'] or c['citta'],
                   'loc': ''}
        else:
            rec = reg.get(od['url'].rsplit('/', 1)[-1].rsplit('.', 1)[0])
        if rec and od['url'] not in per_slug:
            per_slug[od['url']] = (od, rec)
    # Senza data si finisce in fondo e non in cima: davanti vanno gli
    # appuntamenti che si sanno collocare nel calendario.
    return sorted(per_slug.values(), key=lambda x: x[1].get('d_start') or '9')


def _card_evento(od, rec):
    """Un evento della realta', con la locandina. Qui la miniatura e non
    l'originale: sono immagini in elenco, ed e' la regola gia' scritta per le
    righe di agenda — l'originale sta sulla scheda dell'evento, dove si guarda
    davvero."""
    src = G.loc_path(rec.get('loc'), mini=True)
    img = (f'<img class="cr-ev-loc" src="{G.esc(src)}" alt="" loading="lazy" '
           f'decoding="async">' if src else
           '<span class="cr-ev-loc is-ph" aria-hidden="true">📅</span>')
    quando = od['quando'] + (f", ore {od['ora']}" if od['ora'] else '')
    dove = (rec.get('luogo') or rec.get('citta') or '').strip()
    fuori = (' target="_blank" rel="noopener"'
             if od['url'].startswith('http') else '')
    return (f'    <a class="cr-ev" href="{G.esc(od["url"])}"{fuori}>{img}'
            f'<span class="cr-ev-t">'
            f'<span class="cr-ev-n">{G.esc(G.trunc(rec.get("nome", ""), 90))}</span>'
            f'<span class="cr-ev-q">{G.esc(quando)}'
            f'{" · " + G.esc(dove) if dove else ""}</span>'
            f'</span></a>')


CSS_REALTA = """
.cr-wrap{max-width:820px;margin:0 auto;padding:0 20px 48px}
.cr-crumb{font-size:.85rem;opacity:.85;margin-bottom:10px}
.cr-crumb a{color:inherit}
.cr-logo{max-width:150px;height:auto;border-radius:12px;margin:22px 0 0;display:block}
.cr-descr{margin:18px 0 0;font-size:1.02rem;line-height:1.65}
.cr-h{font-size:1.22rem;margin:34px 0 12px}
.cr-ev{display:flex;gap:12px;align-items:center;padding:10px 12px;margin:0 0 8px;
  border:1px solid rgba(0,0,0,.09);border-radius:12px;background:#fff;
  text-decoration:none;color:inherit}
.cr-ev-loc{width:54px;height:54px;object-fit:cover;border-radius:8px;flex:0 0 54px}
.cr-ev-loc.is-ph{display:flex;align-items:center;justify-content:center;
  background:var(--surface,#f5f3f0);font-size:1.3rem}
.cr-ev-t{display:flex;flex-direction:column;gap:2px;min-width:0}
.cr-ev-n{font-weight:700;font-size:.98rem}
.cr-ev-q{font-size:.86rem;opacity:.72}
.cr-torna{margin:30px 0 0;font-size:.95rem}
/* Il sottotitolo sotto l'H1: dice cosa fa la societa' e dove, che l'H1 (il solo
   nome) non dice. */
.cr-sub{margin:6px 0 0;font-size:1.02rem;opacity:.85}
/* "Chi e' ...": la descrizione che si apre e si chiude. Il triangolino di
   sistema non si tocca — e' l'unica cosa che dice "questo si apre" senza
   spiegarlo. */
.cr-chi{margin:22px 0 0}
.cr-chi>summary{cursor:pointer;font-weight:700;font-size:1.02rem;
  padding:10px 0;list-style:none}
.cr-chi>summary::-webkit-details-marker{display:none}
.cr-chi>summary::before{content:"▸ ";display:inline-block;transition:transform .15s}
.cr-chi[open]>summary::before{content:"▾ "}
.cr-chi>summary:hover{text-decoration:underline}
.cr-chi .cr-descr:first-of-type{margin-top:4px}
"""


def jsonld_realta(org, corsi_org, info):
    o = {'@type': 'Organization', 'name': org,
         'url': f"{SITE_URL}{url_realta(org)}"}
    if info.get('descr'):
        o['description'] = info['descr']
    if info.get('logo'):
        o['logo'] = info['logo']
    if info.get('sito'):
        o['sameAs'] = [info['sito']]
    if info.get('tel'):
        o['telephone'] = info['tel']
    if info.get('email'):
        o['email'] = info['email']
    citta = (info.get('citta') or '').strip() or (
        _uniche(c['citta'] for c in corsi_org)[:1] or [''])[0]
    if citta:
        o['address'] = {'@type': 'PostalAddress', 'addressLocality': citta,
                        'addressRegion': 'Piemonte', 'addressCountry': 'IT'}
        if info.get('indirizzo'):
            o['address']['streetAddress'] = info['indirizzo']
    graph = [o]
    for c in corsi_org:
        graph.append({'@type': 'Course', 'name': c['nome'],
                      'provider': {'@type': 'Organization', 'name': org},
                      'description': (c['descr'] or '').strip()
                      or f"{c['nome']} con {org}."})
    return json.dumps({'@context': 'https://schema.org', '@graph': graph},
                      ensure_ascii=False, indent=1)


def pagina_realta(org, corsi_org, info, css, nav, foot):
    """La pagina di una realta': chi e', dove, i suoi corsi, i suoi eventi."""
    citta = (info.get('citta') or '').strip() or ', '.join(
        _uniche(c['citta'] for c in corsi_org))
    disc = _uniche(_cat_foglia(c) for c in corsi_org)
    # L'OCCHIELLO PORTA LA MACRO, NON LA DISCIPLINA (26/08/2026, Giovanni: "il
    # 'coro' secondo me e' troppo specifico, in fondo loro non fanno solo coro,
    # ma insegnano anche strumenti"). Prendeva disc[0], cioe' una disciplina a
    # caso fra le sei di una scuola di musica: la pagina si presentava come
    # "VEZZA D'ALBA · CORO". La macro le contiene tutte.
    macro = _uniche(_cat_macro(c) for c in corsi_org)
    # Il sottotitolo sotto l'H1, che e' anche l'H1 "parlante" che Giovanni
    # chiedeva nei suggerimenti SEO ("Corsi di musica per bambini a Vezza
    # d'Alba"): l'H1 resta il nome della societa', questo dice cosa fa e dove.
    che_corsi = (f"Corsi di {', '.join(m.lower() for m in macro[:2])}"
                 if macro else "Corsi")
    occhiello = (f'<p class="cr-sub">{G.esc(che_corsi)} per bambini'
                 f'{f" a {G.esc(citta)}" if citta else ""}</p>')
    url = f"{SITE_URL}{url_realta(org)}"
    titolo = f"{org}: corsi per bambini{f' a {citta}' if citta else ''} | DAOP"
    descr = G.trunc((info.get('descr') or '').strip() or
                    f"{org}: {len(corsi_org)} corsi per bambini e ragazzi"
                    f"{f' a {citta}' if citta else ''}"
                    f"{', ' + ', '.join(disc).lower() if disc else ''}.", 300)
    # IN INDICE SE LA SOCIETA' HA CONFERMATO, una per una. L'interruttore globale
    # resta padrone dell'hub (/corsi.html, la nav, le quattro porte): quella e'
    # una decisione sulla sezione. Ma la singola pagina non ha bisogno di
    # aspettare le altre - i suoi dati li ha confermati chi li conosce, e quella
    # era l'unica condizione che mancava.
    robots = ('index, follow' if confermata(info) else 'noindex, follow')

    testa = []
    if info.get('logo'):
        testa.append(f'<img class="cr-logo" src="{G.esc(info["logo"])}" '
                     f'alt="Logo di {G.esc(org)}" loading="lazy" decoding="async">')
    if info.get('descr'):
        # LA DESCRIZIONE SI APRE E SI CHIUDE (26/08/2026, Giovanni: "posso anche
        # non volerla leggere"). E' il testo piu' lungo della pagina e sta sopra
        # i corsi, cioe' sopra la cosa per cui uno e' arrivato qui: chiusa, i
        # corsi partono subito; aperta, si legge tutta.
        # <details> e non un blocco in JS: il testo resta nell'HTML (Google lo
        # legge, ed e' la descrizione della societa'), funziona senza script e
        # non ha uno stato da sincronizzare.
        # `open` sulle descrizioni corte: se sta in tre righe, chiuderla e' un
        # clic chiesto per niente.
        aperto = ' open' if len(info['descr'].strip()) < 400 else ''
        testa.append(
            f'<details class="cr-chi"{aperto}><summary>Chi è {G.esc(org)}</summary>'
            + _paragrafi(info['descr'], 'cr-descr') + '</details>')

    # Gli stessi dati della scheda in corsi.html, e non un secondo elenco
    # scritto a mano: se un domani cambia l'ordine o si aggiunge un campo,
    # cambia in un posto solo. Qui si toglie solo l'elenco dei corsi, che
    # sotto c'e' per intero con le sue schede.
    dati = _dati_realta(org, corsi_org, info)
    riquadro = ('<dl class="co-dati">' + ''.join(
        f'<dt>{k}</dt><dd>{v}</dd>' for k, v in dati) + '</dl>') if dati else ''

    schede = "\n".join(card(c, i, qui_org=slug_realta(org))
                       for i, c in enumerate(corsi_org))
    ev = eventi_realta(corsi_org)
    blocco_ev = ''
    if ev:
        blocco_ev = (f'  <h2 class="cr-h">Open day ed eventi di {G.esc(org)}</h2>\n'
                     + "\n".join(_card_evento(od, rec) for od, rec in ev))

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{G.esc(titolo)}</title>
<meta name="description" content="{G.esc(descr)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{G.esc(titolo)}">
<meta property="og:description" content="{G.esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.esc(info.get('logo') or G.DEFAULT_IMG)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{G.esc(G.trunc(titolo, 60))}">
<meta name="twitter:description" content="{G.esc(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{G.esc(info.get('logo') or G.DEFAULT_IMG)}">
<meta name="daop:citta" content="{G.esc(citta)}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{CSS}{CSS_REALTA}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld_realta(org, corsi_org, info)}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero">
  <div class="page-hero-inner">
    <div class="cr-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/corsi.html">Corsi per bambini</a> › <span>{G.esc(org)}</span>
    </div>
    <span class="section-label">{G.esc(citta or 'Piemonte')}{' · ' + G.esc(macro[0]) if macro else ''}</span>
    <h1>{G.esc(org)}</h1>
    {occhiello}
  </div>
</header>
<article class="cr-wrap" data-org="{slug_realta(org)}" data-org-nome="{G.esc(org)}">
{chr(10).join('  ' + t for t in testa)}
  {'<h2 class="cr-h">Informazioni e contatti</h2>' if riquadro else ''}
  {riquadro}
  <h2 class="cr-h" id="i-corsi">{f'I corsi di {G.esc(org)}' if len(corsi_org) > 1 else f'Il corso di {G.esc(org)}'}</h2>
  <div class="events-list">
{schede}
  </div>
{blocco_ev}
  <p class="cr-torna"><a href="/corsi.html#co-lista">← Tutti i corsi {zona(corsi_org)[0]}</a></p>
{G.blocco_ecosistema('corsi')}
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


def scrivi_realta(gruppi, realta, css, nav, foot):
    """Scrive le pagine delle realta' che se le meritano, e toglie quelle che
    non se le meritano piu'.

    LA RIMOZIONE NON E' UNA SVISTA. Ovunque sul sito le pagine non si cancellano
    mai — una scheda evento resta online marcata "edizione conclusa", perche'
    l'anzianita' dell'URL e' l'unico asset che non si ricompra. Qui e' diverso, e
    la differenza e' che questa pagina e' UNO SPAZIO PAGATO: quando la presenza
    finisce, continuare a pubblicarla vuol dire pubblicare una realta' che non e'
    piu' nella guida. E' lo stesso problema che CLAUDE.md segnala per i luoghi
    ("Premium_al, la data di scadenza: niente si spegne da solo"), risolto nel
    verso giusto — qui qualcosa si spegne da solo.

    La scheda in corsi.html invece resta finche' la realta' ha corsi nel foglio,
    e con lei l'ancora #r-…: i link gia' girati non si rompono comunque."""
    import glob as _glob
    dest = os.path.join(ROOT, DIR_REALTA)
    os.makedirs(dest, exist_ok=True)
    vive, scritte, in_indice = set(), 0, set()
    for org, v in gruppi.items():
        info = realta.get(G.slugify(org), {})
        if not ha_pagina(info):
            continue
        f = f"{slug_realta(org)}.html"
        vive.add(f)
        # Solo le confermate vanno in sitemap. Non e' una restrizione in piu':
        # e' l'invariante che aggiorna_sitemap dichiara gia' - una URL in
        # sitemap con robots noindex sono due ordini che si contraddicono.
        if confermata(info):
            in_indice.add(f)
        path = os.path.join(dest, f)
        nuovo = pagina_realta(org, v, info, css, nav, foot)
        vecchio = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        if nuovo != vecchio:
            open(path, 'w', encoding='utf-8').write(nuovo)
            scritte += 1
    tolte = []
    for path in _glob.glob(os.path.join(dest, '*.html')):
        if os.path.basename(path) not in vive:
            os.remove(path)
            tolte.append(os.path.basename(path))
    print(f"[genera_corsi] pagine realta': {len(vive)} pubblicate "
          f"({scritte} riscritte), {len(in_indice)} in indice"
          + (f", {len(tolte)} tolte: {', '.join(tolte)}" if tolte else ""))
    if vive and not in_indice:
        # Va DETTO, non dedotto dal silenzio: una pagina online e fuori da
        # Google somiglia in tutto a una in indice, e la differenza la vede solo
        # chi guarda il sorgente.
        print(f"[genera_corsi] nessuna realta' ha lo Stato 'confermata' nella "
              f"tab Realta: le pagine sono online ma tutte noindex")
    if not vive:
        print(f"[genera_corsi] nessuna realta' ha una descrizione di almeno "
              f"{MIN_DESCR_REALTA} caratteri nella tab Realta: nessuna pagina "
              f"dedicata (resta la scheda in corsi.html)")
    return in_indice


# ── CHI RISPONDE A CHI SCRIVE ────────────────────────────────────────────
#
# Deciso da Patrick il 21/08/2026: Cuneo la segue Giovanni, Alessandria e Asti
# le seguiamo noi. Non e' una cortesia — e' il modello dei partner territoriali:
# chi cura un territorio e' quello che le societa' di quel territorio conoscono
# gia', e mandarle a un indirizzo che non risponde e' il modo piu' veloce di
# perdere una scheda.
#
# La riga si compone dai DATI, non da un testo scritto a mano: finche' i corsi
# sono tutti di Cuneo si legge un indirizzo solo, e la seconda mail compare da
# se' il giorno che entra la prima societa' di Alessandria. Un testo fisso con
# due indirizzi direbbe oggi una cosa non vera.
MAIL_PROV = {'CN': 'collabora@eventiperbambinicuneo.it'}
MAIL_DEFAULT = 'info@daop.it'


def _mail_per(corsi):
    """[(province, mail)], nell'ordine in cui vanno scritte. Le province che
    condividono un indirizzo stanno insieme."""
    provs = sorted({(c['prov'] or '').strip().upper() for c in corsi if c['prov']})
    if not provs:
        return [([], MAIL_DEFAULT)]
    gruppi = {}
    for p in provs:
        gruppi.setdefault(MAIL_PROV.get(p, MAIL_DEFAULT), []).append(p)
    # Prima l'indirizzo che copre piu' province: e' quello che risponde a piu'
    # gente, e la frase comincia da li'.
    return sorted(((v, k) for k, v in gruppi.items()),
                  key=lambda kv: (-len(kv[0]), kv[1]))


def _elenco_prov(sigle):
    nomi = [PROV_NOME.get(s, s) for s in sigle]
    if len(nomi) == 1:
        return nomi[0]
    return ', '.join(nomi[:-1]) + ' e ' + nomi[-1]


def blocco_adesione(corsi):
    """L'invito alle societa', in coda alla pagina.

    NON DICE CHE E' GRATIS, e non e' una dimenticanza: fino al 21/08/2026 c'era
    scritto "la scheda e' gratuita e la compiliamo noi". Giovanni ha fatto
    notare che regalare tutto in vetrina rende impossibile far percepire il
    valore di quello che si vende — e la decisione presa e' che la presenza
    nella guida sia una sola, uguale per tutti, e pagata. Da qui la riga: non si
    scrive un prezzo (si tratta caso per caso) e non si scrive "gratuita", che
    e' una promessa che poi va ritirata.

    E non dice nemmeno "scopri di piu'": dice cosa comprende, perche' e' quello
    che una societa' deve sapere prima di scrivere."""
    caselle = _mail_per(corsi)
    parti = []
    for sigle, mail in caselle:
        eti = (f"In provincia di {_elenco_prov(sigle)} scrivi a "
               if len(caselle) > 1 else "Scrivici a ")
        parti.append(f'{eti}<a href="mailto:{mail}">{mail}</a>')
    return (
        '  <p class="co-nota"><strong>Sei una scuola, un\'associazione o una '
        'società sportiva e proponi attività per bambini e ragazzi?</strong> '
        'Stiamo costruendo una guida alle attività per famiglie: la presenza '
        'comprende la vostra realtà, i corsi che proponete, le informazioni '
        'utili per le famiglie, le prove e gli open day collegati al calendario '
        'degli eventi. ' + '. '.join(parti) + '.</p>')


def _cat_foglia(c):
    """"Sport › Pallavolo" -> "Pallavolo". Il secondo livello e' quello che dice
    davvero cos'e' il corso: "Pallavolo" vale piu' di "Sport".

    SI SCRIVE, NON SI FILTRA (26/08/2026, vedi _cat_macro)."""
    return (c.get('cat') or '').split('›')[-1].strip()


def _cat_macro(c):
    """"Sport › Pallavolo" -> "Sport". La famiglia, ed e' quella che FILTRA.

    Fino al 26/08/2026 la tendina era costruita sul secondo livello. Giovanni:
    "disciplina e' gia' sfuggito di mano: troppe! nel giro di poco ci metti piu'
    a cercare il filtro che ti serve che il corso stesso". Aveva ragione, e la
    ragione vera e' peggiore di quella che si vedeva in pagina: IL SECONDO
    LIVELLO NON E' STABILE. Le stesse quattro locandine, lette tre volte,
    davano "Coro"/"Canto corale", "Musica gioco"/"Musica per bambini",
    "Musica per bambini"/"Musica per l'infanzia", "Musica d'insieme"/"Musica
    pop" - mentre il primo livello ha detto "Musica" sei volte su sei. Filtrare
    su una parola che cambia a ogni rilettura vuol dire mandare due locandine
    identiche in due filtri diversi, e non e' un problema di UX: e' un filtro
    che perde delle righe.

    Il primo livello invece e' una lista chiusa dettata dal prompt (Sport,
    Musica, Danza, Teatro, Lingue, Arte, Studio, Natura, Altro), e una lista
    chiusa e' l'unica cosa su cui si possa filtrare.

    La disciplina non sparisce: resta scritta in riga sulla scheda, dove serve a
    leggere, e nell'elenco "Attivita'" della realta'. Cambia solo chi comanda la
    tendina.
    """
    testo = (c.get('cat') or '').strip()
    if not testo:
        return ''
    return testo.split('›')[0].strip()


def _ancora(org):
    """L'ancora della realta': #r-pgs-roccavione. E' il link che si manda a una
    societa' ("questa e' la tua pagina"), quindi il nome se lo porta scritto e
    non dipende dall'ordine dell'elenco."""
    return 'r-' + G.slugify(org or 'altre-realta')


def _id_corso(c):
    """L'ancora di un singolo corso. Serve alla scheda della realta', che elenca
    i suoi corsi e ci deve poter mandare: senza, quell'elenco sarebbe un elenco
    di nomi che non porta da nessuna parte."""
    return 'c-' + G.slugify(f"{c.get('org', '')}-{c.get('nome', '')}")


def card(c, idx, pagine=(), qui_org=None):
    """Una scheda in stile agenda: riga sempre visibile + dettaglio che si apre
    al tocco. Riusa le classi .event-card/.ev-* del resto del sito.

    LA RIGA CHIUSA PORTA TRE DATI, E SONO I TRE DEI FILTRI: disciplina, eta',
    comune. E' la richiesta di Giovanni del 21/08/2026, e la ragione e' che
    questa pagina si legge scorrendo: chi e' arrivato qui sta scremando, non
    ancora scegliendo. I giorni e gli orari — che prima stavano in riga —
    servono a chi ha gia' scremato, quindi scendono nel dettaglio: sono anche il
    dato piu' lungo e piu' fragile, perche' cambiano a stagione in corso.

    LA DISCIPLINA SI SCRIVE SEMPRE, ed e' un cambio rispetto a prima. Usciva
    solo dove il gruppo mescolava piu' discipline, perche' dentro una societa'
    di pallavolo "Pallavolo" ripetuto su cinque righe e' rumore. Quel
    ragionamento vale in un elenco raggruppato per realta'; qui l'elenco e'
    piatto e la riga sopra puo' essere un corso di musica, quindi la disciplina
    e' il primo dato utile e non una ripetizione.

    NIENTE PILLOLA "SCHEDA COMPLETA". Dal 21/08/2026 la presenza nella guida e'
    una sola e uguale per tutti: non esiste piu' un livello gratuito da cui
    distinguersi, quindi un bollino che dice "questa ha aderito" distinguerebbe
    da niente. Quello che il premium faceva davvero — descrizione lunga,
    locandina — ce l'ha adesso ogni scheda che abbia il materiale."""
    color, tint, ink = ACCENTO
    det_id = f"det-co-{idx}"
    r = eta_range(c)

    # Il comune, non la sede: l'indirizzo della palestra e' lungo e in riga non
    # aiuta a scegliere. La sede sta nel dettaglio, col suo segnaposto.
    bits = []
    et = eta_testo(c)
    if et:
        bits.append(G.esc(et))
    if c['citta']:
        bits.append(G.esc(G.trunc(c['citta'], 34)))

    tags = []
    # L'open day sta in RIGA e non solo nel dettaglio: e' l'unica cosa della
    # pagina che scade. Un corso lo trovi anche fra un mese, un open day no.
    od = openday(c)
    if od:
        tags.append('<span class="ev-pill is-openday">Open day</span>')
    # NIENTE CARTELLINO SULLA PROVA (26/08/2026, feedback di Giovanni).
    # Diceva "Prova gratuita" su qualunque riga con la colonna Prova piena, e il
    # 26/08 l'avevo corretto in "Lezione di prova" quando il campo non diceva
    # gratis. Ma il rilievo vero era un altro, e piu' a monte: "credo che tutti i
    # corsi di questo mondo ti permettano di provare, quelli che non lo fanno e'
    # perche' hanno da farti pagare l'entrata - quindi l'etichetta la
    # toglierei". Ha ragione, ed e' lo stesso argomento che il 12/08 ha ucciso
    # la colonna "Adatto Famiglie": un cartellino che ce l'hanno (quasi) tutti
    # non fa scegliere nessuno, occupa la riga e la fa sembrare piu' piena di
    # quanto sia.
    # IL DATO RESTA: la data della lezione di prova sta nel dettaglio, fra i
    # dati del corso ("Prova: lezione di prova venerdi 25 settembre"). Quella e'
    # informazione - via l'etichetta, non la riga.

    righe_det = []
    # Se c'e' una descrizione lunga vince quella, e non dipende piu' da un flag:
    # il testo migliore e' il testo migliore, e chi ce l'ha ce l'ha.
    testo = c['descr_premium'] or c['descr']
    if testo:
        righe_det.append(f'<p class="event-desc">{G.esc(testo)}</p>')
    if od:
        quando = od['quando'] + (f", ore {od['ora']}" if od['ora'] else '')
        # "SCOPRI L'OPEN DAY" e non "vedi la locandina" (26/08/2026, Giovanni:
        # "al momento riporta sempre a una stessa locandina, invece delle
        # singole"). Non era una lettura sbagliata: un open day serve PIU' corsi
        # - la PGS ne fa uno per cinque squadre - quindi sei corsi puntano allo
        # stesso evento, ed e' il legame giusto. Era l'etichetta a promettere
        # un'altra cosa: uno leggeva "la locandina" e si aspettava quella del
        # SUO corso, che sta gia' qui sotto in fondo al dettaglio.
        vedi = "vedi sul sito →" if od['url'].startswith('http') else "scopri l'open day →"
        testa = f'{G.esc(quando)} — ' if quando else ''
        righe_det.append(
            f'<p class="co-openday"><strong>Open day:</strong> {testa}'
            + _a_openday(od, vedi) + '</p>')
    dove = c['sede'] or c['citta']
    if dove:
        righe_det.append(f'<p class="ev-where">{G.PIN_SVG} {G.esc(dove)}</p>')

    dati = []
    # L'ORGANIZZATORE E' IL PRIMO DATO DEL DETTAGLIO, e non sta piu' in riga.
    # Nell'elenco un genitore sceglie il corso, non la societa'; la societa' e'
    # il passo dopo, e il link porta alla sua scheda in fondo alla pagina.
    # `pagine` sono gli slug delle realta' che hanno una pagina dedicata: se
    # c'e', il link ci va, se no resta l'ancora della scheda in fondo. Non e'
    # un'alternativa fra due indirizzi buoni — l'ancora esiste sempre e i link
    # gia' girati continuano a funzionare — e' che quando c'e' una pagina vera
    # mandare a un riassunto e' un passo in piu' per niente.
    # `qui_org` e' la realta' della pagina su cui siamo: sulla propria pagina la
    # riga non si stampa affatto, perche' e' l'intestazione che si sta leggendo.
    if c['org'] and G.slugify(c['org']) != qui_org:
        href = (url_realta(c['org']) if G.slugify(c['org']) in pagine
                else f"#{_ancora(c['org'])}")
        dati.append(('Organizzatore',
                     f'<a href="{href}">{G.esc(c["org"])}</a>'))
    if c['periodo']:
        dati.append(('Periodo', G.esc(c['periodo'])))
    # I giorni scendono qui dalla riga: servono a chi ha gia' scelto.
    if c['giorni']:
        dati.append(('Giorni', G.esc(c['giorni'])))
    # LA PROVA E' UNA CARATTERISTICA DEL CORSO, non un annuncio a se'. Fino al
    # 21/08/2026 stava in un paragrafo suo, sopra i dati e subito sotto la riga
    # dell'open day — e le due cose si accavallavano: l'open day porta le sue
    # date dalla tab Eventi, la colonna Prova ne porta altre scritte a mano
    # nella stessa cella ("Gratuita · open day 10, 17 e 24 settembre"), e a
    # schermo si leggevano due calendari diversi per la stessa cosa. Giovanni
    # l'ha chiamato "un po' di casino con le date", ed e' esatto.
    #
    # La divisione e' questa, e va tenuta: l'OPEN DAY e' un evento, ha una data
    # sola, sta nella tab Eventi e da li' prende la sua locandina; la PROVA e'
    # un attributo — si puo' provare o no — e sta qui in mezzo agli altri, sotto
    # i giorni. Nel foglio la colonna Prova non dovrebbe portare date: se ne
    # porta, sono date che nessuno viene ad aggiornare.
    if c['prova']:
        dati.append(('Prova', G.esc(c['prova'])))
    if c['prezzo']:
        dati.append(('Quota', G.esc(c['prezzo'])))
    # NIENTE "Iscrizioni aperte/chiuse", tolto il 21/08/2026 su richiesta di
    # Giovanni. E' un dato che scade in silenzio e che nessuno viene ad
    # aggiornare: alla pallavolo si entra quasi sempre, a un corso di teatro
    # quasi mai, e la risposta vera ce l'ha la societa' — che qui sotto ha il
    # suo numero. Una riga che dice "Aperte" a gennaio e' peggio di nessuna riga.
    if c['contatto']:
        # contatti_html() e non esc(): il numero diventa <a href="tel:">, che su
        # un telefono e' la differenza fra leggere un numero e chiamare. Non e'
        # solo comodita' — un numero stampato come testo NON PRODUCE UN CLIC, e
        # quindi non esiste in GA4: il telefono era l'unica tappa del percorso
        # che si voleva restituire alle realta' e che non si poteva misurare.
        # Il testo intorno resta come l'ha scritto chi compila il foglio.
        dati.append(('Contatti', G.contatti_html(c['contatto'])))
    # Il contatto e' UNO, quello della realta'. I referenti restano nomi: sulla
    # locandina di partenza erano cinque cellulari di volontarie e, a confronto
    # con quella dell'anno prima, erano cambiati quasi tutti. Ripubblicarli qui
    # vorrebbe dire mandare le famiglie a telefonare a chi non segue piu' quel
    # gruppo — e un numero personale dentro un archivio consultabile non e' la
    # stessa cosa dello stesso numero stampato su un manifesto.
    if c['referenti']:
        dati.append(('Referenti', G.esc(c['referenti'])))
    if dati:
        righe_det.append('<dl class="co-dati">' + ''.join(
            f'<dt>{k}</dt><dd>{v}</dd>' for k, v in dati) + '</dl>')
    # "Scopri il corso →" deve portare alla pagina del corso sul sito della
    # scuola, non alla home della societa'. Il rel non e' una formalita': un
    # link commerciale che passa PageRank e' uno schema di link, e si paga con
    # un'azione manuale sul DOMINIO — cioe' su eventi.html, che regge il
    # traffico. Da quando la presenza e' una sola ed e' pagata e' sponsored per
    # tutti: non c'e' piu' una meta' "nostra segnalazione" da distinguere.
    if c['sito']:
        righe_det.append(
            f'<p class="co-fuori"><a href="{G.esc(c["sito"])}" '
            f'rel="sponsored noopener" target="_blank">Scopri il corso →</a></p>')
    # LA LOCANDINA STA IN FONDO (26/08/2026, Giovanni: "prima diamo le info che
    # abbiamo estrapolato, e' quello il valore che stiamo dando"). Ha ragione, e
    # non e' solo gerarchia: l'immagine e' alta, e in cima spingeva eta', giorni
    # e contatti sotto la piega proprio nel momento in cui uno apre la riga per
    # leggerli. Chi vuole vedere il volantino originale scorre; chi vuole i dati
    # non deve scorrere per niente.
    # Qui va l'originale e non la miniatura - si guarda, e' la stessa regola
    # degli elenchi al contrario. Sta dentro un dettaglio chiuso, che il browser
    # non disegna: con loading=lazy non parte nessuna richiesta finche' la riga
    # non si apre.
    if c['loc']:
        src = G.loc_path(c['loc'])
        if src:
            righe_det.append(
                f'<img class="co-loc" src="{G.esc(src)}" alt="Locandina di '
                f'{G.esc(c["nome"])}" loading="lazy" decoding="async">')
    if c['verificato']:
        # Un corso non scade da solo come un evento: senza questa riga una
        # scheda ferma da un anno e' identica a una aggiornata ieri.
        righe_det.append(
            f'<p class="co-verif">Dati verificati il {G.esc(c["verificato"])}</p>')

    # La fascia per i filtri: annate se ci sono, altrimenti l'eta' scritta sulla
    # locandina (vedi eta_min_max). Senza il ripiego, i corsi di una scuola di
    # musica restavano fuori dalla tendina eta' - che e' il rilievo numero uno
    # di Giovanni.
    fascia = eta_min_max(c)
    # `data-etada` dice DA DOVE viene la fascia, e non e' un dato per il
    # visitatore: serve alla prova (tests/corsi.js) per sapere quale invariante
    # controllare. Su "annate" la riga deve portare la fascia CALCOLATA ("6-7
    # anni"), su "testo" deve portare l'eta' come l'ha scritta la locandina
    # ("dai 4 anni"): sono due regole diverse, e senza questo attributo la prova
    # non puo' che confonderle.
    eta_attr = (f' data-etamin="{fascia[0]}" data-etamax="{fascia[1]}"'
                f' data-etada="{"annate" if eta_range(c) else "testo"}"'
                if fascia else '')
    cat = _cat_foglia(c)
    macro = _cat_macro(c)
    riga_cat = f'<span class="co-cat">{G.esc(cat)}</span>' if cat else ''
    # data-org-nome e data-codice esistono per il TRACCIAMENTO, ed e' l'unico
    # posto da cui daop-track.js li puo' sapere. Il nome per esteso non si
    # ricava dalla card (in riga non c'e', per la decisione del 21/08: qui si
    # sceglie un corso, non una societa') e ricostruirlo dallo slug darebbe
    # "pgs-roccavione" in un report che deve leggere una persona. Il codice e'
    # quello del foglio: e' l'identificativo che NON cambia se un domani il
    # corso si chiama "Volley U8" invece di "Volley Under 8 M/F" — lo slug
    # cambierebbe, e con lui si spezzerebbe la serie storica in GA4.
    cod_attr = f' data-codice="{G.esc(c["codice"])}"' if c.get('codice') else ''
    return f"""        <article class="event-card" id="{_id_corso(c)}" data-city="{G.slugify(c['citta'])}" data-prov="{(c['prov'] or '').lower()}" data-cat="{G.slugify(macro)}" data-disc="{G.slugify(cat)}" data-org="{G.slugify(c['org'] or 'altre-realta')}" data-org-nome="{G.esc(c['org'] or 'Altre realtà')}"{cod_attr} data-openday="{'1' if od else '0'}"{eta_attr} style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <h3 class="ev-h"><button class="ev-row" type="button" aria-expanded="false" aria-controls="{det_id}">
            <span class="ev-thumb is-ph" aria-hidden="true">{G.esc(_emoji(c))}</span>
            <span class="ev-main">
              {riga_cat}
              <span class="ev-name">{G.esc(G.trunc(c['nome'], 110))}</span>
              <span class="ev-line">{" · ".join(bits)}</span>
              <span class="ev-tags">{"".join(tags)}</span>
            </span>
            {G.CHEV_SVG}
          </button></h3>
          <div class="ev-det" id="{det_id}" hidden>
            {chr(10) + "            ".join(righe_det)}
          </div>
        </article>"""


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


def _fasce_coperte(corsi):
    """Le fasce d'eta' che l'elenco tocca davvero, nell'ordine di FASCE_ETA.

    Il confronto e' per SOVRAPPOSIZIONE, come nel filtro: un corso 6-11 conta
    sia in "6-8" sia in "9-11", perche' un bambino di 7 anni e uno di 10 ci
    stanno tutti e due.

    Serve a due cose: decidere se la tendina eta' vale la pena (ne servono
    almeno due, se no non divide) e decidere QUALI voci stamparci dentro. La
    seconda non e' un dettaglio: una voce che non puo' che dare zero risultati
    e' un comando che non fa niente, cioe' la stessa cosa di una tendina con
    una voce sola, e chi la sceglie si trova la pagina vuota e pensa che sia
    rotta."""
    tocche = []
    for chiave, _ in FASCE_ETA:
        lo, hi = (int(x) for x in chiave.split('-'))
        if any(r and r[0] <= hi and r[1] >= lo for r in (eta_min_max(c) for c in corsi)):
            tocche.append(chiave)
    return tocche


def toolbar(corsi):
    """Un comando si stampa quando DIVIDE, non quando l'elenco e' lungo.

    Fino al 20/08/2026 c'era una soglia di conteggio: sotto MIN_FILTRI la barra
    non usciva, perche' con pochi elementi si scorre prima l'elenco che una
    tendina. La soglia e' caduta per decisione di Patrick, e il criterio che
    resta e' migliore perche' guarda i dati invece di contarli: una tendina con
    una voce sola non si stampa, e nemmeno una che non toglierebbe niente.

    Sui 5 corsi di oggi il conto lo fa da solo: disciplina e comune spariscono
    (una societa' sola, un paese solo), "solo con prova" sparisce (ce l'hanno
    tutti), resta l'eta' — che divide davvero, perche' vanno dai 6 ai 14 anni.
    Disciplina e comune ricompaiono da se' quando entra la seconda realta'.

    Se nessun campo si qualifica non esce nemmeno la casella di ricerca: una
    barra con dentro solo un campo di testo, sopra cinque righe, e' arredamento."""
    campi = []
    # LA TENDINA E' SULLA MACRO CATEGORIA, non sulla disciplina (26/08/2026,
    # vedi _cat_macro): una scuola di musica sola produceva sei voci, e quelle
    # voci cambiano a ogni rilettura della stessa locandina. "Musica" no.
    cats = {G.slugify(_cat_macro(c)): _cat_macro(c) for c in corsi if _cat_macro(c)}
    if len(cats) > 1:
        opts = "".join(f'<option value="{k}">{G.esc(v)}</option>'
                       for k, v in sorted(cats.items(), key=lambda kv: kv[1].lower()))
        campi.append('<select class="ev-select" data-campo="cat" aria-label="Filtra per tipo di attività">'
                     f'<option value="all">Attività</option>{opts}</select>')
    citta = {G.slugify(c['citta']): c['citta'] for c in corsi if c['citta']}
    if len(citta) > 1:
        opts = "".join(f'<option value="{k}">{G.esc(v)}</option>'
                       for k, v in sorted(citta.items(), key=lambda kv: kv[1].lower()))
        campi.append('<select class="ev-select" data-campo="citta" aria-label="Filtra per comune">'
                     f'<option value="all">Comune</option>{opts}</select>')
    # L'eta' entra se DIVIDE: servono almeno due fasce toccate. Prima si
    # guardava quante righe dichiarassero un'eta' e si chiedeva MIN_FILTRI, che
    # e' un'altra domanda — dodici corsi tutti 6-8 anni avrebbero acceso una
    # tendina inutile, e cinque corsi da 6 a 14 anni la tenevano spenta.
    coperte = _fasce_coperte(corsi)
    if len(coperte) > 1:
        opts = "".join(f'<option value="{v}">{t}</option>'
                       for v, t in FASCE_ETA if v in coperte)
        campi.append('<select class="ev-select" data-campo="eta" aria-label="Filtra per età del bambino">'
                     f'<option value="all">Età</option>{opts}</select>')
    # "SOLO CON OPEN DAY" al posto di "solo con prova" (26/08/2026, Giovanni:
    # "di conseguenza 'solo con prova' non so se lo lascerei come filtro,
    # piuttosto filtro open day"). La ragione e' la stessa che ha tolto il
    # cartellino: provare si puo' quasi sempre, quindi quel filtro non divide
    # niente. L'open day invece e' una data, cioe' l'unica cosa di questa pagina
    # per cui uno si muove entro una scadenza - ed e' anche la domanda vera di
    # settembre: "dove posso andare a vedere prima di decidere?".
    # La regola resta quella di sempre: si stampa solo se divide.
    con_od = sum(1 for c in corsi if openday(c))
    if 0 < con_od < len(corsi):
        campi.append('<label class="ev-chk"><input type="checkbox" data-campo="openday"> '
                     'Solo con open day</label>')
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
/* La disciplina scritta in riga. Stessi valori di .com-cat nelle pagine comune:
   e' la stessa cosa e deve leggersi allo stesso modo. Il colore viene da
   --cat-ink, che la card imposta. */
.co-cat{display:block;font-size:.72rem;font-weight:700;letter-spacing:.05em;
  text-transform:uppercase;color:var(--cat-ink,#606d7a);opacity:.78;margin-bottom:2px}
/* .ev-pill.is-prova e .co-prova sono via col cartellino della prova
   (26/08/2026, vedi card): regole senza piu' nessuno che le porti. */
.ev-pill.is-openday{background:#2E7D46;color:#fff}
.co-openday{margin:8px 0 0;color:#2E7D46}
.co-openday a{color:#2E7D46;font-weight:700}
.co-loc{width:100%;max-width:320px;height:auto;border-radius:10px;margin:0 0 10px;display:block}
.co-fuori{margin:10px 0 0}
.co-fuori a{font-weight:700;color:#2c5d8f;text-decoration:none}
.co-fuori a:hover{text-decoration:underline}
.co-dati{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;margin:12px 0 0;font-size:.93rem}
.co-dati dt{opacity:.65}
.co-dati dd{margin:0;font-weight:600}
.co-dati dd a{color:#2c5d8f}
.co-verif{margin:10px 0 0;font-size:.8rem;opacity:.6}
.co-nota{margin:26px 0 0;padding:14px 16px;border-radius:12px;background:var(--surface,#f5f3f0);font-size:.95rem}
.event-card.is-hidden{display:none}
.co-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
/* ── le schede delle realta', in fondo ──────────────────────────────────
   Sono <div> e non <section>: section{padding:100px 24px} arriva dal CSS di
   sistema, e una scheda nascosta dai filtri lascerebbe 200px di niente. */
.co-realta-wrap{margin:40px 0 0}
.co-realta-t{font-size:1.3rem;margin:0 0 4px}
.co-realta-sub{margin:0 0 16px;font-size:.93rem;opacity:.72}
.co-realta{padding:16px 18px;margin:0 0 14px;border:1px solid rgba(0,0,0,.09);
  border-radius:14px;background:#fff;scroll-margin-top:120px}
.co-realta h3{font-size:1.1rem;margin:0 0 6px}
.co-realta-d{margin:0 0 4px;font-size:.95rem;line-height:1.55;opacity:.85}
.co-realta-corsi,.co-realta-ev{margin:12px 0 0;font-size:.93rem;line-height:1.7}
.co-realta-corsi a,.co-realta-ev a{color:#2c5d8f}
.co-realta-vai{margin:12px 0 0;font-size:.95rem}
.co-realta-vai a{font-weight:700;color:#2c5d8f;text-decoration:none}
.co-realta-vai a:hover{text-decoration:underline}
.co-logo{max-width:120px;height:auto;border-radius:10px;margin:0 0 10px;display:block}
/* L'avviso di sezione in preparazione. Stesso giallo della fascia di
   corsi-prova.html: e' la stessa cosa — una pagina che dichiara di non essere
   ancora quello che sembra. */
.co-avviso{background:#fdf3e0;border:1px solid #e6c98a;border-radius:10px;
  padding:14px 16px;margin:0 0 18px;font-size:.94rem;line-height:1.55;color:#6b4a10}
/* Il bersaglio del "← Tutti i corsi" delle pagine realta'. Lo stesso stacco
   delle schede: senza, l'elenco atterra sotto la barra in cima. */
#co-lista{scroll-margin-top:120px}
.co-realta h3 a{color:inherit;text-decoration:none}
.co-realta h3 a:hover{text-decoration:underline}
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
  // Un link verso un corso (dalla scheda della realta') deve APRIRE la riga,
  // non solo scorrerci sopra: altrimenti si arriva su una riga chiusa che
  // sembra la stessa di prima, e il link pare rotto.
  function apriDaHash(){
    var id=(location.hash||'').replace('#','');
    if(!id) return;
    var c=document.getElementById(id);
    if(!c||!c.classList.contains('event-card')||c.classList.contains('is-open')) return;
    var btn=c.querySelector('.ev-row');
    if(btn) btn.click();
  }
  window.addEventListener('hashchange',apriDaHash);
  apriDaHash();
  var bar=document.getElementById('co-toolbar');
  if(!bar) return;
  var q=document.getElementById('co-q'), count=document.getElementById('co-count'),
      campi=[].slice.call(bar.querySelectorAll('[data-campo]'));
  function norm(s){return (s||'').toLowerCase();}
  function apply(){
    var term=norm(q&&q.value.trim()), vis=0, orgVivi={};
    cards.forEach(function(c){
      var ok=!term||norm(c.textContent).indexOf(term)>=0;
      campi.forEach(function(el){
        if(!ok) return;
        var campo=el.dataset.campo;
        if(campo==='openday'){ if(el.checked && c.dataset.openday!=='1') ok=false; return; }
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
        // IL NOME DEL CAMPO NON E' SEMPRE IL NOME DELL'ATTRIBUTO. La tendina
        // del comune si chiama "citta" (come la colonna del foglio) ma la
        // scheda scrive data-city (come le pagine comune del resto del sito):
        // qui si leggeva c.dataset.citta, cioe' undefined, e QUALUNQUE comune
        // scelto nascondeva tutte le righe. Il filtro comune non ha mai
        // funzionato, e non si vedeva perche' la tendina si stampa solo con due
        // comuni in pagina: fino al 26/08/2026 di comune ce n'era uno.
        // Trovato dalla prova che sceglie ogni voce e conta cosa resta.
        var chiave = campo==='citta' ? 'city' : campo;
        if(c.dataset[chiave]!==v) ok=false;
      });
      c.classList.toggle('is-hidden',!ok);
      if(ok){ vis++; orgVivi[c.dataset.org]=1; }
    });
    // Una realta' di cui non resta visibile nessun corso esce anche dalle
    // schede in fondo: se no il filtro "Musica" lascerebbe in pagina la scheda
    // della societa' di pallavolo, che e' esattamente cio' che si e' chiesto di
    // togliere. E con zero corsi visibili sparisce anche il titolo della
    // sezione, che altrimenti resta in aria sopra il vuoto.
    var schede=[].slice.call(document.querySelectorAll('.co-realta')), viveUna=false;
    schede.forEach(function(s){
      var viva=!!orgVivi[s.dataset.org];
      s.style.display=viva?'':'none';
      if(viva) viveUna=true;
    });
    var wrap=document.getElementById('realta');
    if(wrap) wrap.style.display=viveUna?'':'none';
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


def render(corsi, css, nav, foot, realta=None):
    """La pagina: un elenco piatto di corsi, e in fondo le schede delle realta'.

    L'ELENCO NON E' PIU' RAGGRUPPATO PER SOCIETA', ed e' il cambio piu' grosso
    del 21/08/2026. Prima ogni realta' aveva il suo <h2> con sotto i suoi corsi:
    si leggeva bene, ma obbligava chi cerca a scegliere prima la societa' e poi
    il corso — e nessun genitore ragiona in quell'ordine. Giovanni l'ha detto
    con le sue parole: "in questa pagina mi interessa che compaiano i corsi e io
    genitore possa sceglierli avendo visione di tutti". Coi filtri in cima,
    l'ordine per societa' era anche il modo piu' sicuro di rendere quei filtri
    inutili: filtrando per "Musica" restavano intestazioni sparse.

    LE SOCIETA' NON SPARISCONO, SCENDONO. La loro scheda — #r-pgs-roccavione, il
    link che si manda su WhatsApp — sta in fondo, e da ogni corso ci si arriva
    dalla riga "Organizzatore" del dettaglio. E' la stessa ancora di prima:
    nessun link gia' in giro si rompe.

    L'ORDINE E' disciplina, poi eta', poi comune. Non alfabetico per nome: due
    corsi di pallavolo di due societa' diverse stanno vicini, che e' quello che
    serve a chi confronta. E non per societa', per la ragione di sopra."""
    realta = realta or {}
    dove, zona_breve = zona(corsi)
    titolo = f"Corsi per bambini {dove} | DAOP"
    descr = (f"Corsi e attività continuative per bambini e ragazzi {dove}: musica, sport, "
             f"danza, lingue, teatro. Con età, giorni, costi e le prove gratuite. Curato a mano.")

    # L'ordine segue i filtri: prima la macro (che e' la tendina), poi la
    # disciplina, poi l'eta'. Con la sola disciplina, "Canto corale" e "Coro"
    # della stessa scuola finivano a distanza di mezza pagina.
    ordinati = sorted(corsi, key=lambda c: (
        _cat_macro(c).lower(), _cat_foglia(c).lower(),
        (eta_min_max(c) or (999, 999))[0],
        (c['citta'] or '').lower(), c['nome'].lower()))

    # Le realta' che hanno una pagina dedicata, per slug: le card ci mandano
    # il link "Organizzatore" invece che all'ancora del riassunto.
    pagine = {k for k, v in realta.items() if ha_pagina(v)}

    if ordinati:
        elenco = ('  <div class="events-list" id="co-lista">\n'
                  + "\n".join(card(c, i, pagine) for i, c in enumerate(ordinati))
                  + '\n  </div>')
    else:
        elenco = ('  <p class="co-nota">Le prime schede stanno arrivando.</p>')

    gruppi = raggruppa_per_realta(ordinati)
    if gruppi:
        blocchi = [scheda_realta(org, gruppi[org], realta.get(G.slugify(org), {}))
                   for org in sorted(gruppi, key=lambda s: s.lower())]
        quante = len(gruppi)
        sezione = ('  <div class="co-realta-wrap" id="realta">\n'
                   '    <h2 class="co-realta-t" id="co-realta-t">Chi organizza</h2>\n'
                   f'    <p class="co-realta-sub">{quante} realtà {dove}: '
                   'dove sono, come si contattano, cosa organizzano.</p>\n'
                   + "\n".join(blocchi) + '\n  </div>')
    else:
        sezione = ''

    # La pagina fuori indice lo dice anche a chi legge, non solo a Google. Un
    # link girato su WhatsApp continua a funzionare — e' tutto il senso di
    # lasciarla online — ma chi lo apre deve sapere che sta guardando un elenco
    # non finito, invece di dedurlo dal fatto che c'e' una societa' sola.
    avviso = '' if G.CORSI_IN_INDICE else (
        '  <div class="co-avviso"><strong>Sezione in preparazione.</strong> '
        'Stiamo raccogliendo i corsi con le società, una alla volta, e '
        'verifichiamo con loro ogni scheda prima di pubblicarla. Quello che vedi '
        'qui è un primo elenco: non è ancora completo.</div>\n')
    robots = 'index, follow' if G.CORSI_IN_INDICE else 'noindex, follow'

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{G.esc(titolo)}</title>
<meta name="description" content="{G.esc(descr)}">
<meta name="robots" content="{robots}">
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
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
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
    <p>Sport, musica, danza, lingue, teatro: le attività a cui un bambino si iscrive,
    con l'età che prendono, dove sono e quando si può andare a vederle.
    Informazioni raccolte dalle locandine delle realtà, una società alla volta.</p>
  </div>
</header>
<article class="co-wrap">
{avviso}  <p class="co-intro">Un corso non è un evento: dura nel tempo — una stagione intera,
  qualche mese, a volte poche lezioni — e la domanda di un genitore non è "cosa si fa
  sabato" ma "dove porto mio figlio quest'anno". Qui trovi quello che c'è, e lo scegli
  come lo sceglieresti davvero: per tipo di attività, per età del bambino e per comune.
  Dove c'è un open day per andare a vedere prima di decidere, è scritto.</p>
{toolbar(corsi)}
{elenco}
{sezione}
{blocco_adesione(corsi)}
{G.blocco_ecosistema('corsi')}
  <div class="co-actions">
    <a class="btn btn-teal" href="/eventi.html">Vedi cosa c'è in agenda</a>
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


def aggiorna_sitemap(pagine=()):
    """Il blocco della sitemap: ci sta dentro solo quello che e' in indice.

    L'invariante vale in tutti e due i versi. In sitemap nessuna URL con robots
    noindex: chiedere a Google di scansionare una pagina per poi dirgli di non
    tenerla e' il modo piu' veloce di far ignorare la sitemap intera. Ma anche
    il contrario: una pagina in indice che la sitemap non annuncia e' uno spazio
    pagato che Google fa fatica a trovare.

    Fino al 28/08/2026 il blocco si spegneva TUTTO con CORSI_IN_INDICE, hub e
    realta' insieme. Aveva senso finche' la decisione era una sola; da quando
    confermata() ha reso la pagina della societa' una decisione SUA, quella riga
    teneva fuori dalla sitemap proprio le pagine confermate, cioe' quelle
    pagate. Restavano raggiungibili dall'hub, che e' "noindex, FOLLOW" e quindi
    i link li fa seguire lo stesso — ma un noindex di lunga durata Google
    finisce per trattarlo come un nofollow, e il giro "confermano, indicizziamo,
    fatturiamo" si sarebbe spento da solo dopo qualche mese senza un errore da
    nessuna parte.

    Adesso l'hub segue CORSI_IN_INDICE e ogni realta' segue la sua cella Stato.
    Il blocco resta UNO: due blocchi vorrebbero dire due marker da tenere
    allineati in sitemap.xml per una distinzione che qui e' gia' una riga di
    codice. Se non ci finisce dentro niente, si toglie."""
    if not os.path.exists(SITEMAP_PATH) or not os.path.exists(PATH):
        return
    import re
    re_via = re.compile(r'  <!-- CORSI:START.*?<!-- CORSI:END -->\n?', re.S)
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding='utf-8').read()
    # L'hub e le pagine delle realta' stanno nello STESSO blocco, ma ci entrano
    # per due ragioni diverse: l'hub perche' la SEZIONE e' in indice, la realta'
    # perche' LEI ha confermato. Sotto, `pagine` sono gia' le sole confermate
    # (scrivi_realta restituisce in_indice, non vive).
    voci = [f"  <url>\n    <loc>{URL}</loc>\n    <lastmod>{oggi}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>"]
    if not G.CORSI_IN_INDICE:
        voci = []
    for f in sorted(pagine):
        voci.append(f"  <url>\n    <loc>{SITE_URL}/{DIR_REALTA}/{f}</loc>\n"
                    f"    <lastmod>{oggi}</lastmod>\n"
                    f"    <changefreq>monthly</changefreq>\n"
                    f"    <priority>0.6</priority>\n  </url>")
    if not voci:
        fuori = re_via.sub('', s)
        if fuori != s:
            open(SITEMAP_PATH, 'w', encoding='utf-8').write(fuori)
        print("[genera_corsi] fuori sitemap: hub noindex e nessuna realta' confermata")
        return
    blocco = ("  <!-- CORSI:START (generato da scripts/genera_corsi.py — non modificare a mano) -->\n"
              + "\n".join(voci) + "\n  <!-- CORSI:END -->")
    re_blocco = re.compile(r'  <!-- CORSI:START.*?<!-- CORSI:END -->', re.S)
    if re_blocco.search(s):
        s = re_blocco.sub(blocco, s)
    else:
        s = s.replace('</urlset>', blocco + '\n</urlset>')
    open(SITEMAP_PATH, 'w', encoding='utf-8').write(s)
    print(f"[genera_corsi] sitemap: {'corsi.html + ' if G.CORSI_IN_INDICE else ''}"
          f"{len(pagine)} pagine realta' confermate"
          + ('' if G.CORSI_IN_INDICE else " (l'hub e' noindex)"))


def main():
    corsi = leggi_corsi()
    if corsi is None:
        # Il controllo sta QUI, prima di qualunque scrittura, e non in fondo.
        print("[genera_corsi] foglio non letto: lascio la pagina com'è")
        return 0
    # Il proprio numero prima di render(): la riga delle quattro porte lo
    # rilegge, e questa pagina la scrive di se' stessa (senza contarsi).
    G.conteggio_scrivi('corsi', len(corsi))
    # Le schede delle realta' si leggono DOPO i corsi e usando i loro nomi: e'
    # il filtro che impedisce a un foglio sbagliato di entrare in pagina. Vedi
    # leggi_realta().
    realta = leggi_realta({c['org'] for c in corsi})
    css, nav, foot = G._guscio()
    # Le pagine delle realta' PRIMA di corsi.html: render() deve sapere quali
    # esistono per decidere dove manda il link "Organizzatore". Fra le due
    # chiamate la fonte e' la stessa (ha_pagina sulla riga della tab Realta),
    # quindi non possono divergere.
    gruppi = raggruppa_per_realta(corsi)
    pagine = scrivi_realta(gruppi, realta, css, nav, foot)
    nuovo = render(corsi, css, nav, foot, realta)
    vecchio = open(PATH, encoding='utf-8').read() if os.path.exists(PATH) else ''
    if nuovo != vecchio:
        open(PATH, 'w', encoding='utf-8').write(nuovo)
        print(f"[genera_corsi] {FILE} riscritta — {len(corsi)} corsi")
    else:
        print(f"[genera_corsi] {FILE} invariata — {len(corsi)} corsi")
    aggiorna_sitemap(pagine)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
