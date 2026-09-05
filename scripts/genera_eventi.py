#!/usr/bin/env python3
"""
Genera/aggiorna la sezione eventi di eventi.html a partire dal foglio Google
"luoghi" (tab "eventi"). Pensato per girare in GitHub Actions ogni notte.

Fonte dati (in ordine di priorità):
  1. URL CSV in EVENTI_CSV_URL (es. export "Pubblica sul web" del tab eventi)
  2. URL CSV di export del tab Eventi (richiede foglio condiviso "chiunque con il link")
  3. data/eventi.json (istantanea committata, fallback se la rete non è disponibile)

Rigenera SOLO, dentro eventi.html, quello che sta fra i marker EVENTI-TIPO
(opzioni del filtro per tipo), EVENTI-LISTA (corsie "in evidenza" + agenda
raggruppata per giornata) e il blocco JSON-LD. Tutto il resto resta intatto.
"""
import os, re, csv, io, json, html, datetime, urllib.request, urllib.parse, unicodedata, sys, collections, random, glob, difflib, itertools

SHEET_ID = "186XuLRXD2DXHL5CVy1vgNfmbEhpSbpW5pSgr4ARhugs"
# gid del tab "Eventi". Serve perche' la fonte e' l'export, non gviz: vedi sotto.
EVENTI_GID = "1499875874"
# L'EXPORT, non gviz (31/08/2026). gviz decide UN TIPO per colonna e restituisce
# VUOTE le celle che non gli somigliano: nella colonna "Data Inizio" il foglio
# (locale en_US) tiene 100 date vere e 65 stringhe - "31/08/2026" non e' una data
# per chi legge mm/dd, e resta testo - e gviz mandava indietro quelle 65 vuote.
# Qui sotto normalize() scarta chi non ha data d'inizio, quindi 65 eventi su 165
# non arrivavano sul sito, in silenzio, contati come "non ci sono".
# L'export restituisce le celle COME SI VEDONO, testo o data che siano, ed e' la
# stessa strada che fa gia' il downloader (daop_pipeline.righe_csv_pubblico).
# La sua trappola e' un'altra, e vale la pena saperla: l'export RISPETTA I FILTRI
# del foglio, quindi un filtro attivo lo fa tornare corto. Non e' un errore che
# si veda da solo -> il controllo in fetch_rows().
DEFAULT_CSV = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
               f"/export?format=csv&gid={EVENTI_GID}")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(ROOT, "eventi.html")
HOME_PATH = os.path.join(ROOT, "index.html")
HOME_LIMIT = 8  # quanti eventi mostrare nel carosello della home
JSON_PATH = os.path.join(ROOT, "data", "eventi.json")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")
# Lo scrive genera_luoghi.py, lo legge questo: i comuni che hanno almeno un
# luogo in /luoghi.html, con l'ancora del loro gruppo. Vedi link_luoghi().
INDICE_LUOGHI_PATH = os.path.join(ROOT, "data", "luoghi-comuni.json")
# Le realta' dei corsi che hanno una pagina in /corsi/. Lo scrive
# genera_corsi.py, che gira dopo: si legge quello della notte prima. Vedi
# indice_realta() e link_realta().
INDICE_REALTA_PATH = os.path.join(ROOT, "data", "realta-pagine.json")

# Province i cui eventi vengono pubblicati sul sito. Una sola lista, usata sia dal
# filtro dei dati sia dal copy che dice "che zona copre DAOP": prima la sigla era
# scritta a mano dentro normalize() e il numero di province era una costante "2"
# in un'altra pagina, quindi si poteva aprire il filtro e lasciare il testo che
# diceva il contrario. CN aggiunta il 04/08/2026, primi eventi di Cuneo sul foglio.
PROVINCE_PUBBLICATE = ('AL', 'AT', 'CN')
PROVINCE_NOMI = {'AL': 'Alessandria', 'AT': 'Asti', 'CN': 'Cuneo'}

# Le province per esteso, come si scrivono in un testo: "Alessandria, Asti e
# Cuneo". Derivata dalla lista qui sopra e non scritta a mano, perche' e' proprio
# il copy a restare indietro: CN e' aperta dal 04/08/2026 e per dodici giorni le
# firme delle schede e i JSON-LD hanno continuato a dire "Alessandria e Asti".
PROVINCE_TESTO = (', '.join(PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE[:-1])
                  + ' e ' + PROVINCE_NOMI[PROVINCE_PUBBLICATE[-1]])

# Pagina Instagram da cui arrivano le segnalazioni, provincia per provincia.
# "nostra": la pagina e' di DAOP (AL, AT) oppure di un partner (CN). Non e' un
# dettaglio grafico: su una pagina nostra il credito e' un rimando, su quella di
# un altro e' l'attribuzione di un lavoro che non e' nostro, ed e' il motivo per
# cui questa riga esiste. La locandina resta comunque dell'organizzatore: qui si
# dice DOVE l'abbiamo trovata, per questo "Segnalato da" e mai "Fonte".
# ATTENZIONE: e' il gemello di PROFILI in config_segreti.py del downloader, che
# sta in un altro repo. Se li' si aggiunge o cambia una provincia, questa mappa
# NON se ne accorge: l'evento arriva lo stesso e resta semplicemente senza
# credito (nessun errore, nessun link rotto). Da aggiornare a mano.
PROVINCE_IG = {
    'AL': {'ig': 'daop_alessandria', 'nostra': True,
           'fb': 'https://www.facebook.com/daopalessandria/',
           'curatore': 'Patrick Orlando'},
    'AT': {'ig': 'daop_asti', 'nostra': True,
           'fb': 'https://www.facebook.com/daopasti',
           'curatore': 'Alessandra Zaccone'},
    # Dal 26/08/2026 e' una pagina DAOP come le altre due: era
    # @eventi_bambini_provincia_cuneo, una pagina esterna che ospitavamo, ed e'
    # diventata @daop_cuneo con Giovanni curatore. Il flag 'nostra' non e' un
    # dettaglio grafico: girandolo, zone.html, le firme delle schede e le pagine
    # di provincia smettono da sole di scrivere "una pagina che non e' nostra".
    # Nessun Facebook: quello che non c'e' non si stampa.
    'CN': {'ig': 'daop_cuneo', 'nostra': True,
           'curatore': 'Giovanni'},
}


def fonte_provincia(prov):
    """Dati della pagina di provenienza, o None se la provincia non ne ha una."""
    f = PROVINCE_IG.get((prov or '').strip().upper())
    if not f:
        return None
    return dict(f, url=f"https://www.instagram.com/{f['ig']}/",
                provincia=PROVINCE_NOMI.get((prov or '').strip().upper(), ''))


# YouTube e' l'unico profilo che non ha una provincia: sta qui e non in
# PROVINCE_IG, che e' una mappa per provincia e non un elenco di social.
YOUTUBE_URL = 'https://www.youtube.com/@DOVEANDIAMOOGGIPAPI'


def blocco_social_footer(inline=False):
    """La colonna "Community" del footer, COMPOSTA da PROVINCE_IG.

    PERCHE'. Il footer e' l'unico pezzo del guscio che nessun generatore
    compone: _guscio() lo COPIA da eventi.html, e finche' una cosa si copia e
    basta l'unico posto che la sa e' quello scritto a mano. E' costato
    @daop_cuneo mancante da tutto il sito per settimane, con il codice che lo
    sapeva (sta in PROVINCE_IG, col curatore accanto) e il footer no, su ~470
    pagine. Da qui la voce si compone dall'unico posto dove i profili vivono
    gia' - lo stesso di fonte_provincia() - e una provincia nuova entra nel
    footer da sola.

    Le pagine si nominano per esteso e non con la sigla: "Instagram AL" chiede
    a chi legge di sapere il codice della propria provincia, "Instagram
    Alessandria" no.

    Le pagine ospiti (nostra=False) entrano anche loro: la colonna si chiama
    Community, e una pagina che ospitiamo ne fa parte. La distinzione fra
    nostro e ospite si fa dove serve davvero, cioe' nel credito di ogni scheda,
    che e' l'attribuzione di un lavoro.

    inline=True: index.html ripete gli stili del footer negli attributi style
    invece di usare le classi, quindi la stessa voce le va data vestita. E' la
    stessa deroga gia' fatta per 404.html con la nav assoluta."""
    st_a = (' style="text-decoration:none;font-size:0.88rem;'
            'color:rgba(255,255,255,0.62);"' if inline else '')

    def link(href, testo):
        return (f'<a href="{href}" target="_blank" rel="noopener"{st_a}>'
                f'{esc(testo)}</a>')

    fonti = [f for f in (fonte_provincia(s) for s in PROVINCE_PUBBLICATE) if f]
    voci = [link(f['url'], f"Instagram {f['provincia']}") for f in fonti]
    voci += [link(f['fb'], f"Facebook {f['provincia']}")
             for f in fonti if f.get('fb')]
    voci.append(link(YOUTUBE_URL, 'YouTube'))
    sep = chr(10) + ' ' * 8
    return sep + sep.join(voci) + chr(10) + ' ' * 6


def credito_fonte(f, apertura, classe='com-fonte', breve=False):
    """Il credito alla pagina di provenienza. In un posto solo.

    PERCHE' QUI. Era scritto in cinque punti quasi identici - la firma della
    scheda, le pagine comune e le tre famiglie provinciali - e cambiarne il
    testo voleva dire cambiarlo cinque volte, cioe' la forma esatta in cui due
    copie divergono alla prima modifica. Stessa ragione di _dati_realta() e di
    e_gratuito(): un fatto che si scrive in un posto solo.

    IL VERBO E' LA PARTE CHE NON C'ERA. Il credito diceva da dove viene
    l'evento e si fermava li'. E' un'attribuzione, e va benissimo che lo resti
    - ma "Segnalato da @daop_asti" risponde a *da dove viene questo evento*,
    non a *perche' dovrei seguirvi*: nessun verbo, nessuna ragione. Adesso
    dice anche cosa si trova andandoci.

    COSA NON DIVENTA, ed e' la parte da non rifare al contrario. Non sale in
    cima, non diventa una fascia, non si ripete altrove: dal 28/08/2026
    Ginetto e' l'unica richiesta del sito e il 04/09 il canale WhatsApp e'
    stato chiuso apposta per non dividere l'attenzione. Due richieste nello
    stesso punto si dimezzano, e misurandole insieme non si saprebbe piu'
    quale delle due ha mosso il numero. Questo resta dov'e' - in fondo, dentro
    la trasparenza su come la scheda e' nata - e cambia solo le parole.

    'apertura' e' l'unica cosa che cambia davvero fra i cinque punti:
    "Segnalato da" su una scheda, "Gli eventi di Ovada arrivano da" su una
    pagina comune. 'breve' quando l'apertura ha gia' nominato la provincia,
    per non scriverla due volte nella stessa frase."""
    if not f:
        return ''
    dove = ('questa provincia' if breve
            else f"la provincia di {esc(f['provincia'])}")
    chi = (f"la nostra pagina per {dove}" if f['nostra'] else
           f"la pagina che segue {dove}, con cui collaboriamo")
    return (f'<p class="{classe}">{apertura} '
            f'<a class="ev-ig" href="{f["url"]}" target="_blank" rel="noopener">'
            f'@{esc(f["ig"])}</a>, {chi}: seguila per gli eventi in arrivo. '
            f'<a href="{ZONE_HREF}">Le pagine della tua zona</a></p>')


def province_in_elenco(codici):
    """"Alessandria, Asti e Cuneo" a partire dalle sigle, in ordine di PROVINCE_PUBBLICATE."""
    nomi = [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE if c in set(codici)]
    if not nomi:
        return ""
    if len(nomi) == 1:
        return nomi[0]
    return ", ".join(nomi[:-1]) + " e " + nomi[-1]


KNOWN_CATS = {'Sagra & Festa', 'Sagra', 'Spettacolo', 'Laboratorio', 'Sport',
              'Musica', 'Cultura', 'Natura', 'Altro', 'Mercato', 'Arte',
              'Cinema', 'Teatro'}
MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic']
MESI_LUNGHI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio',
               'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
LABELS = {'feste': 'Sagre & Feste', 'spettacoli': 'Spettacoli', 'musica': 'Musica',
          'laboratori': 'Laboratori', 'sport': 'Sport', 'cultura': 'Cultura & Natura',
          'altro': 'Altro'}
ORDER = ['feste', 'spettacoli', 'laboratori', 'musica', 'sport', 'cultura', 'altro']

# Gli stessi nomi, ma scritti dentro una frase invece che dentro una tendina:
# "Cultura & Natura" e' un'etichetta, "cultura e natura" e' italiano. 'altro'
# non c'e' apposta - una categoria che si chiama cosi' non si annuncia in una
# riga di apertura, si legge nelle righe.
LABELS_PROSA = {'spettacoli': 'spettacoli', 'laboratori': 'laboratori',
                'musica': 'musica', 'sport': 'sport', 'cultura': 'cultura e natura'}


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
    base = os.environ.get("EVENTI_CSV_URL") or DEFAULT_CSV
    # Cache-buster: Google e le CDN possono servire una COPIA IN CACHE del CSV.
    # Era la causa del "sito non aggiornato" dopo una modifica al foglio: la run
    # leggeva dati vecchi e rigenerava identico. Un parametro univoco a ogni run
    # + header no-cache forzano una risposta fresca.
    sep = '&' if '?' in base else '?'
    url = f"{base}{sep}_cb={int(datetime.datetime.now().timestamp())}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "daop-eventi-bot",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
        reader = list(csv.reader(io.StringIO(text)))
        hi = next(i for i, row in enumerate(reader) if any('Data Inizio' in c for c in row))
        header = [c.strip() for c in reader[hi]]
        out = []
        for j, row in enumerate(reader[hi + 1:]):
            if not any(c.strip() for c in row):
                continue
            d = {header[i]: (row[i].strip() if i < len(row) else '') for i in range(len(header))}
            # Numero di riga NEL FOGLIO, quello che si legge nella colonnina
            # grigia a sinistra. Serve alle segnalazioni: dire "togli il
            # doppione di Sant'Albano" costringe chi corregge a cercarlo a
            # mano fra duecento righe, dire "riga 118" no.
            # reader e' 0-based e il foglio 1-based, quindi +1; e la riga
            # dell'intestazione sta a hi, quindi la prima riga di dati e' hi+2.
            # Stringa e non intero: questo dict e' fatto di celle di CSV e c'e'
            # chi lo scorre tutto trattandole come testo (campi_daop).
            d['_riga'] = str(hi + j + 2)
            out.append(d)
        # L'export rispetta i filtri del foglio (vedi DEFAULT_CSV) e un filtro
        # attivo toglie righe senza dire niente: tornerebbe un CSV corto e
        # valido. Il confronto e' con l'istantanea di ieri, che tiene solo il
        # futuro ed e' quindi sempre piu' corta di quello che si legge qui: se
        # perfino quella e' piu' lunga di un terzo abbondante, non e' calo
        # stagionale, e' il filtro.
        try:
            with open(JSON_PATH, encoding="utf-8") as fh:
                ieri = len(json.load(fh))
        except Exception:
            ieri = 0
        if ieri and len(out) < ieri * 0.7:
            print(f"[genera_eventi] ATTENZIONE: {len(out)} righe lette, ma ieri il "
                  f"sito ne pubblicava {ieri}: probabile FILTRO attivo sul tab "
                  f"Eventi, che l'export rispetta. Toglilo e rilancia.")
        print(f"[genera_eventi] {len(out)} righe lette da CSV remoto")
        return out
    except Exception as e:  # fallback su istantanea locale
        print(f"[genera_eventi] CSV remoto non disponibile ({e}); uso {JSON_PATH}")
        with open(JSON_PATH, encoding="utf-8") as fh:
            snap = json.load(fh)
        # rimappa lo snapshot sulle stesse chiavi del foglio (comprese le
        # colonne editoriali, altrimenti il fallback perderebbe i consigli DAOP)
        return [dict({
            'Nome': e['nome'], 'Data Inizio': e['di'], 'Data fine': e['df'],
            'Ora': e['ora'], 'Città': e['citta'], 'Provincia': e['prov'],
            'Categoria': e['categoria'], 'Età': e['eta'], 'Prezzo': e['prezzo'],
            'Descrizione': e['descr'], 'Manifestazione': e.get('manifest', ''),
            'Locandina': e.get('loc', ''), 'Luogo': e.get('luogo', ''),
            'Indirizzo Completo': e.get('indirizzo', ''),
        }, **{nomi[0]: e[campo]
              for campo, nomi in dict(CAMPI_DAOP, **CAMPI_EXTRA).items()
              if (e.get(campo) or '').strip()})
            for e in snap]


# Colonne facoltative del foglio, in prosa. Il grosso del giudizio editoriale su
# DAOP passa dal flag "Consigliato DAOP", che c'e' gia' su ogni riga: queste
# restano per i casi in cui una frase serve davvero, e finche' sono vuote non
# compare nessun blocco (meglio niente che un titolo senza risposta).
# I nomi sono tollerati in piu' grafie perche' il foglio lo scrivono due persone.
CAMPI_DAOP = {
    'eta_consigliata': ("Età consigliata", "Eta consigliata", "Età ideale"),
    'adatto':          ("Adatto ai bambini", "Adatto davvero ai bambini"),
    'prenotazione':    ("Prenotazione", "Prenotazioni", "Serve prenotare"),
    'dintorni':        ("Nei dintorni", "Cosa fare nei dintorni", "Dintorni"),
}


# Colonne che nel foglio ci sono gia' e che finora buttavamo via: il giudizio
# DAOP e' in parte gia' stato dato, sotto forma di flag, e i recapiti e le
# coordinate sono i due dati che una risposta di un assistente non contiene mai.
CAMPI_EXTRA = {
    'contatto':        ("Contatto", "Contatti", "Telefono", "Email", "Recapiti"),
    'consigliato':     ("Consigliato DAOP", "Consigliato"),
    'adatto_famiglie': ("Adatto Famiglie", "Adatto alle famiglie", "Adatto famiglie"),
    'lat':             ("Latitude", "Latitudine", "Lat"),
    'lon':             ("Longitude", "Longitudine", "Lon", "Lng"),
}


def _key(s):
    """Chiave di confronto per le intestazioni: senza accenti, spazi e maiuscole.
    'Età consigliata', 'ETA CONSIGLIATA' e 'eta_consigliata' sono la stessa cosa."""
    s = unicodedata.normalize('NFD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '', s.lower())


# Quali colonne editoriali esistono davvero nel foglio (a prescindere dal fatto
# che siano compilate). Serve a non chiedere a fine run di aggiungere una
# colonna che c'e' gia': l'unica cosa da fare, in quel caso, e' riempirla.
COLONNE_VISTE = set()


def campi_daop(d):
    """Legge dalla riga del foglio le colonne editoriali, se ci sono."""
    idx = {_key(k): (v or '').strip() for k, v in d.items()}
    out = {}
    for campo, nomi in dict(CAMPI_DAOP, **CAMPI_EXTRA).items():
        presenti = [_key(n) for n in nomi if _key(n) in idx]
        if presenti:
            COLONNE_VISTE.add(campo)
        out[campo] = next((idx[k] for k in presenti if idx[k]), '')
    return out


def si(v):
    """La colonna e' compilata a mano: 'Si', 'SI', 'Sì', 'x', 'true' valgono si."""
    return _key(v) in ('si', 'sì', 'x', 'true', 'vero', '1', 'y', 'yes')


def coord(e):
    """(lat, lon) come stringhe, solo se sono due numeri plausibili per l'Italia.
    Una cella con un appunto dentro non deve finire nei dati strutturati."""
    try:
        la, lo = float((e.get('lat') or '').replace(',', '.')), \
            float((e.get('lon') or '').replace(',', '.'))
    except ValueError:
        return None
    if 35 <= la <= 48 and 6 <= lo <= 19:
        return f"{la:.7f}".rstrip('0').rstrip('.'), f"{lo:.7f}".rstrip('0').rstrip('.')
    return None


def geo_attrs(e):
    """Le coordinate della riga, per il filtro "vicino a me" di eventi.html.

    Sono gia' nel foglio e gia' nel JSON-LD: qui costano ~45 byte per riga,
    cioe' ~12 KB su 1,4 MB. E' la lezione dei link calendario al contrario -
    quelli erano 490 byte per riga e li si e' tolti - ma il rapporto e' dodici
    volte piu' basso e senza questi il filtro non puo' esistere: la distanza
    non si deduce dal testo.

    Non sono il centroide del comune: Alessandria ha sei punti distinti, e
    infatti servono proprio a questo, perche' "provincia" non vuol dire
    "vicino" (23 eventi in provincia di AL stanno oltre 30 km dal capoluogo, e
    14 eventi entro 25 km sono in un'altra provincia).

    La citta' viaggia insieme perche' il ripiego senza GPS - "parti da un
    comune" - costruisce il suo elenco leggendo le righe, non una lista
    generata a parte: un elenco in piu' in pagina sarebbe HTML che quasi
    nessuno apre."""
    xy = coord(e)
    if not xy:
        return ''
    citta = esc(e.get('citta') or '')
    return (f' data-lat="{xy[0]}" data-lon="{xy[1]}"'
            + (f' data-citta="{citta}"' if citta else ''))


TEL_RE = re.compile(r'(?:\+39[\s.]?)?(?:\d[\s.]?){8,12}\d')
MAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')


def contatti_html(testo):
    """I recapiti diventano link: da telefono si chiama, da mobile soprattutto.
    Il testo intorno resta come l'ha scritto chi compila il foglio."""
    t = (testo or '').strip()
    if not t:
        return ''
    pezzi, pos = [], 0
    trovati = sorted(
        [(m.start(), m.end(), 'mail') for m in MAIL_RE.finditer(t)]
        + [(m.start(), m.end(), 'tel') for m in TEL_RE.finditer(t)])
    # Un numero dentro un indirizzo email non va linkato due volte.
    ultimo = -1
    for a, b, tipo in trovati:
        if a < ultimo:
            continue
        # html.escape e non esc(): esc() fa strip, e qui mangerebbe lo spazio
        # fra il nome e il numero ("Patrizia351 6754801").
        pezzi.append(html.escape(t[pos:a]))
        val = t[a:b].strip()
        if tipo == 'mail':
            pezzi.append(f'<a href="mailto:{esc(val)}">{esc(val)}</a>')
        else:
            pezzi.append(f'<a href="tel:{esc(re.sub(r"[^+0-9]", "", val))}">{esc(val)}</a>')
        pos, ultimo = b, b
    pezzi.append(html.escape(t[pos:]))
    return "".join(pezzi)


def primo_telefono(testo):
    """Il primo numero dei recapiti, gia' normalizzato per un href="tel:".

    Passa dalle STESSE due espressioni regolari di contatti_html(), nello
    stesso ordine: la barra in fondo allo schermo e la riga "Contatti:" devono
    chiamare lo stesso numero, e due riconoscimenti diversi divergono al primo
    caso storto - "Patrizia351 6754801", oppure un indirizzo email con dentro
    nove cifre di fila, che una search() secca prenderebbe per un telefono.
    Se un domani il riconoscimento cambia, cambia in un posto solo."""
    t = (testo or '').strip()
    if not t:
        return ''
    trovati = sorted(
        [(m.start(), m.end(), 'mail') for m in MAIL_RE.finditer(t)]
        + [(m.start(), m.end(), 'tel') for m in TEL_RE.finditer(t)])
    ultimo = -1
    for a, b, tipo in trovati:
        if a < ultimo:
            continue
        if tipo == 'tel':
            return re.sub(r'[^+0-9]', '', t[a:b].strip())
        ultimo = b
    return ''


def normalize(rows):
    today = datetime.date.today()
    events = []
    for d in rows:
        di = pdate(d.get('Data Inizio'))
        if not di:
            continue
        prov = (d.get('Provincia') or '').strip().upper()
        if prov not in PROVINCE_PUBBLICATE:
            continue
        df = pdate(d.get('Data fine')) or di
        if df < today:
            continue
        events.append(dict(
            nome=d.get('Nome', ''), di=d.get('Data Inizio', ''), df=d.get('Data fine', ''),
            ora=d.get('Ora', ''), citta=d.get('Città', ''), prov=prov,
            categoria=(d.get('Categoria', '') if d.get('Categoria', '') in KNOWN_CATS else ''),
            eta=d.get('Età', ''), prezzo=d.get('Prezzo', ''), descr=d.get('Descrizione', ''),
            manifest=d.get('Manifestazione', ''), loc=d.get('Locandina', ''),
            luogo=d.get('Luogo', ''), indirizzo=d.get('Indirizzo Completo', ''),
            d_start=di, d_end=df, riga=int(d.get('_riga') or 0),
            **campi_daop(d),
        ))
    # Ordina per "data utile": un evento già iniziato ma ancora in corso viene
    # trattato come se iniziasse oggi (max(inizio, oggi)), così non finisce in
    # cima con una data passata. A parità di data utile diamo priorità alle
    # novità (eventi che iniziano oggi/domani): gli eventi già in corso, meno
    # "urgenti", scivolano in fondo al gruppo del giorno (d_start < today = True
    # ordina dopo False). Poi l'inizio reale e il nome fanno da spareggio.
    events.sort(key=lambda e: (max(e['d_start'], today), e['d_start'] < today,
                               e['d_start'], e['nome']))
    return events


# Icone dello sprite (assets/icons.svg.html) per categoria. Prima qui c'erano
# emoji: si vedevano diverse su ogni sistema operativo ed erano il segnale piu'
# evidente di "sito fatto in casa".
ICONS = {'feste': 'i-party', 'spettacoli': 'i-drama', 'musica': 'i-music',
         'laboratori': 'i-palette', 'sport': 'i-bike', 'cultura': 'i-landmark',
         'altro': 'i-pin'}


def icon(slug, cls="icon"):
    """Markup dell'icona di categoria, presa dallo sprite inline della pagina."""
    # viewBox obbligatorio: senza, sotto i 24px l'icona viene tagliata.
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">'
            f'<use href="#{ICONS[slug]}"/></svg>')


def simbolo(sym, cls="icon"):
    """Come icon(), ma per un simbolo qualsiasi dello sprite invece che per una
    categoria.

    Serve SOLO dentro riga(): l'agenda e' l'unica pagina generata che ha lo
    sprite inline. Le pagine evento e le pagine comune non ce l'hanno, quindi
    li' le icone devono restare SVG per esteso (le costanti *_SVG qui sotto) -
    un <use> disegnerebbe il vuoto. E' la stessa ragione spiegata in
    _com_thumb().

    Le sei icone delle card erano ripetute per esteso in ognuna delle ~290
    righe: ~1,3 KB di path per card, e sei elementi SVG in piu' nel DOM."""
    return (f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true">'
            f'<use href="#{sym}"/></svg>')


def bucket(e):
    """Restituisce (slug, icona_svg, etichetta) per la categoria dell'evento."""
    def out(slug, label):
        return slug, icon(slug), label

    cz = e['categoria'].lower()
    if 'sagra' in cz or 'festa' in cz or 'mercato' in cz or 'fiera' in cz: return out('feste', 'Sagra & Festa')
    if 'spettacolo' in cz or 'teatro' in cz or 'cinema' in cz: return out('spettacoli', 'Spettacolo')
    if 'musica' in cz: return out('musica', 'Musica')
    if 'laborator' in cz or 'arte' in cz: return out('laboratori', 'Laboratorio')
    if 'sport' in cz: return out('sport', 'Sport')
    if 'cultura' in cz or 'natura' in cz: return out('cultura', 'Cultura')
    nd = (e['nome'] + ' ' + e['descr']).lower()
    if 'sagra' in nd or 'festa' in nd or 'fiera' in nd: return out('feste', 'Sagra & Festa')
    if 'concerto' in nd or 'musica' in nd: return out('musica', 'Musica')
    if 'laborator' in nd: return out('laboratori', 'Laboratorio')
    if 'spettacol' in nd or 'teatro' in nd: return out('spettacoli', 'Spettacolo')
    if any(k in nd for k in ['sport', 'corsa', 'pedalata', 'run', 'ciclo']): return out('sport', 'Sport')
    return out('altro', 'Evento')


SITE_URL = "https://www.daop.it"
PAGE_URL = f"{SITE_URL}/eventi.html"
DEFAULT_IMG = f"{SITE_URL}/assets/images/headerdaop.jpg"
FREE_KW = ('gratuito', 'gratis', 'libero', 'ingresso libero')

# Le locandine NON stanno piu' nel repo: stanno nel bucket pubblico Supabase
# "locandine", dove il downloader le carica gia' da luglio (ottimizzate 1080/q80,
# ~95 KB invece dei ~190 KB dell'originale) e da dove l'app Ginetto le legge da
# sempre. Erano salvate due volte, e la copia costosa era proprio quella che non
# serviva: committate in git crescevano di ~340 MB l'anno che dai blob non
# escono piu' (misurato: 188 MB di .git in tre mesi e mezzo).
# Il nome file nella colonna "Locandina" del foglio e' identico nei due posti,
# quindi qui cambia solo il prefisso.
SUPABASE_LOCANDINE = ("https://aaseyjdsldgjerjqlumu.supabase.co"
                      "/storage/v1/object/public/locandine")


MINIATURE_DIR = os.path.join(ROOT, "assets", "miniature")
MINIATURE_HREF = "/assets/miniature"


def nome_miniatura(loc):
    """Il nome file della miniatura di una locandina, senza cartella.

    Un URL completo non ce l'ha: quelle immagini stanno da un'altra parte e non
    passano dal nostro bucket, quindi non le ridimensioniamo."""
    loc = (loc or '').strip()
    if not loc or loc.startswith(('http://', 'https://')):
        return ''
    return os.path.splitext(os.path.basename(loc.lstrip('/')))[0] + '.webp'


def ha_miniatura(loc):
    m = nome_miniatura(loc)
    return bool(m) and os.path.exists(os.path.join(MINIATURE_DIR, m))


def loc_path(loc, mini=False):
    """URL della locandina per il browser: un nome file diventa l'URL pubblico
    nel bucket Supabase, un URL completo resta intatto. Vuoto se assente.

    Unico punto in cui un nome file diventa un indirizzo: lo usano le card degli
    eventi, le pagine per comune e (via G.loc_path) i centri estivi.

    mini=True negli ELENCHI, dove l'immagine sta in un francobollo da 50-60px o
    in una copertina da 262: li' serviva l'originale da ~95 KB per riempire un
    quadratino, e moltiplicato per le ~100 righe che si scorrono in una sessione
    era il grosso del traffico in uscita dal bucket. Dall'08/08/2026, quando le
    locandine sono passate da git a Supabase, quel traffico e' salito da ~10 a
    ~250 MB al giorno: con il tetto di 5 GB del piano gratuito le immagini si
    sarebbero spente da sole verso fine mese.

    Le miniature stanno in git e le serve GitHub Pages, che non ha tetto. Ci
    stanno perche' sono ~25 KB l'una invece di 190: il motivo per cui le
    locandine erano uscite dal repo (340 MB l'anno di blob) qui non si ripresenta.

    Il ripiego e' sull'originale, sempre: una locandina arrivata stanotte non ha
    ancora la sua miniatura - la fa genera_miniature.py alla run dopo - e nel
    frattempo la pagina mostra quella grande invece di un buco."""
    loc = (loc or '').strip()
    if not loc:
        return ''
    if mini and ha_miniatura(loc):
        return f"{MINIATURE_HREF}/{urllib.parse.quote(nome_miniatura(loc))}"
    if loc.startswith(('http://', 'https://')):
        return loc
    # quote: i nomi dal downloader sono ASCII, ma la colonna si compila anche a
    # mano e uno spazio spezzerebbe l'attributo src.
    return f"{SUPABASE_LOCANDINE}/{urllib.parse.quote(loc.lstrip('/'))}"


def loc_url(loc):
    """URL assoluto della locandina, per i dati strutturati schema.org
    (che richiedono URL assoluti). Vuoto se assente."""
    p = loc_path(loc)
    if not p or p.startswith(('http://', 'https://')):
        return p
    return f"{SITE_URL}{p}"


def esc(s):
    return html.escape((s or '').strip())


def trunc(s, n):
    s = (s or '').strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


PIN_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
CLOCK_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>'
USER_SVG = '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/></svg>'
CAL_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>'
NAV_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>'
# Come ARROW_SVG ma con width/height espliciti. ARROW_SVG nasce per .he-more,
# dove e' il CSS a dargli una misura; dentro .event-act nessuna regola lo
# dimensiona, e un SVG senza dimensioni intrinseche si espande fino a sfondare
# la riga. Le altre icone di .event-act portano width/height inline: questa fa
# lo stesso.
ACT_ARROW_SVG = ARROW_SVG.replace('<svg ', '<svg width="14" height="14" ', 1)
CHEV_SVG = '<svg class="ev-chev" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>'
IMG_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>'
HL_LIMIT = 12  # quante schede al massimo nelle corsie "Oggi" / "Questo weekend"


def _luogo_query(e):
    """Stringa luogo migliore disponibile per Maps/calendario."""
    q = (e.get('indirizzo') or '').strip()
    if not q:
        q = " ".join(x for x in [e.get('luogo', ''), e.get('citta', ''),
                                 f"({e['prov']})" if e.get('prov') else ''] if x).strip()
    return q


def maps_url(e):
    """Link 'Come arrivare' su Google Maps.

    Con le coordinate del foglio si va sul punto esatto: la ricerca per nome
    del luogo, in paesi dove la piazza non e' geocodificata, apre il centro del
    comune e ti lascia a cercare a piedi."""
    xy = coord(e)
    if xy:
        return f"https://www.google.com/maps/search/?api=1&query={xy[0]},{xy[1]}"
    q = _luogo_query(e)
    if not q:
        return ''
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(q + ", Italia")


# Base del link "Aggiungi al calendario" senza parametri: e' quello che finisce
# nell'HTML dell'agenda, dove i campi li riempie il JS all'apertura della riga.
# Le pagine evento e comune, che hanno una scheda sola per pagina, continuano a
# usare gcal_url() con tutto dentro.
GCAL_BASE = "https://calendar.google.com/calendar/render?action=TEMPLATE"


def gcal_url(e):
    """Link 'Aggiungi al calendario' (Google Calendar, evento tutto-il-giorno:
    niente fusi orari, robusto anche quando l'ora non è certa)."""
    start = e['d_start'].strftime('%Y%m%d')
    end = (e['d_end'] + datetime.timedelta(days=1)).strftime('%Y%m%d')  # fine esclusiva
    params = {
        'action': 'TEMPLATE',
        'text': (e['nome'] or '').strip(),
        'dates': f"{start}/{end}",
        'details': (e['descr'] or '').strip()[:900],
        'location': _luogo_query(e),
    }
    return "https://calendar.google.com/calendar/render?" + urllib.parse.urlencode(params)

# Per ogni categoria: colore d'accento (bordi, icone, sfondi), tinta di
# sfondo, e "inchiostro" per il testo. Il terzo serve perche' i colori
# d'accento come testo su bianco non raggiungono i 4.5:1 richiesti da WCAG AA
# (il teal stava a 2.77:1). Calcolati sul caso peggiore, cioe' sul testo
# posato sulla PROPRIA tinta di sfondo, non sul bianco.
COLORS = {
    'feste': ('#e8954a', 'rgba(232,149,74,0.14)', '#a75b15'),
    'spettacoli': ('#6c63a6', 'rgba(108,99,166,0.14)', '#6a61a5'),
    'laboratori': ('#6ba5a8', 'rgba(107,165,168,0.16)', '#467477'),
    'musica': ('#c9a227', 'rgba(201,162,39,0.16)', '#846a1a'),
    'sport': ('#188663', 'rgba(24,134,99,0.14)', '#167859'),
    'cultura': ('#4a90b9', 'rgba(74,144,185,0.14)', '#397293'),
    'altro': ('#7e8c99', 'rgba(126,140,153,0.16)', '#606d7a'),
}


def weekend_range(today):
    """Sabato e domenica del weekend più vicino. Se oggi è già sabato o domenica
    restituisce il weekend in corso, così la sezione "Questo weekend" non salta
    di una settimana proprio nei giorni in cui serve di più."""
    dow = today.weekday()  # 0 = lunedì … 6 = domenica
    sat = today - datetime.timedelta(days=1) if dow == 6 else today + datetime.timedelta(days=(5 - dow) % 7)
    return sat, sat + datetime.timedelta(days=1)


def e_gratuito(e):
    """Vero se il foglio dichiara l'ingresso libero.

    Sta in una funzione sola perche' la stessa risposta serve in quattro posti
    - il cartellino della riga, la card della home, l'attributo su cui filtra
    l'agenda - e due letture della stessa colonna che divergono vorrebbero dire
    un cartellino "Gratuito" su una riga che il filtro "Solo gratuiti" nasconde,
    cioe' la pagina che smentisce il suo comando."""
    return any(k in (e.get('prezzo') or '').lower() for k in FREE_KW)


def free_attr(e):
    """L'attributo su cui lavora il filtro "Solo gratuiti".

    Si stampa solo dove c'e' (~13 byte su 4 righe su 5, cioe' ~2 KB su 1,4 MB):
    e' la regola di geo_attrs(), quello che manca non si scrive. La condizione
    e' POSITIVA per una ragione che non e' di stile - nel foglio 22 righe su 46
    dicono "a pagamento (da verificare)", quindi "gratuito" e' un fatto
    dichiarato mentre "a pagamento" non lo e', e un filtro non deve nascondere
    righe basandosi su una cella che si dichiara incerta."""
    return ' data-free="1"' if e_gratuito(e) else ''


def prezzo_pill(e):
    if e_gratuito(e):
        return '<span class="ev-pill is-free">Gratuito</span>'
    if e['prezzo']:
        return f'<span class="ev-pill is-price">{esc(trunc(e["prezzo"], 26))}</span>'
    return ''


def riga(e, today, hub=None):
    """Una riga dell'agenda: intestazione sempre visibile (miniatura, nome,
    contesto, etichette) + dettaglio che si apre al tocco."""
    slug, cat_icon, catlabel = bucket(e)
    color, tint, ink = COLORS.get(slug, COLORS['altro'])
    ongoing = e['d_start'] < today
    anchor = e.get('anchor', '')
    # cover = l'originale, che serve al link "Locandina" (si apre grande nel
    # riquadro sopra la pagina). mini = quello che va nel francobollo da 52px.
    cover = loc_path(e['loc'])
    thumb_src = loc_path(e['loc'], mini=True)
    thumb = (f'<img class="ev-thumb" src="{thumb_src}" alt="" loading="lazy" decoding="async">'
             if thumb_src else f'<span class="ev-thumb is-ph" aria-hidden="true">{cat_icon}</span>')

    # La data sta già nell'intestazione del giorno: qui restano luogo, durata,
    # orario ed età, cioè quello che serve per decidere in un colpo d'occhio.
    bits = [f"{esc(e['citta'])} ({e['prov']})" if e['citta'] else e['prov']]
    de = e['d_end']
    if ongoing:
        bits.append('ultimo giorno' if de == today else f"fino al {de.day} {MESI[de.month-1]}")
    elif de != e['d_start']:
        bits.append(f"fino al {de.day} {MESI[de.month-1]}")
    if e['ora']:
        bits.append(esc(trunc(e['ora'], 28)))
    if e['eta']:
        bits.append(esc(trunc(e['eta'], 26)))

    tags = [f'<span class="ev-pill is-cat">{cat_icon} {esc(catlabel)}</span>']
    # Il consiglio di DAOP viene prima del prezzo e della manifestazione: e' il
    # motivo per cui uno guarda l'agenda nostra invece di un elenco qualsiasi.
    if si(e.get('consigliato')):
        tags.append(f'<span class="ev-pill is-daop">{STAR_SVG} Consigliato DAOP</span>')
    if ongoing:
        tags.append('<span class="ev-pill is-live">In corso</span>')
    pill = prezzo_pill(e)
    if pill:
        tags.append(pill)
    if e['manifest']:
        tags.append(f'<span class="ev-pill is-tag">{esc(trunc(e["manifest"], 34))}</span>')

    acts = []
    # Link alla pagina dedicata, quando esiste: è la via con cui Google la
    # scopre e le passa autorità dall'agenda, che è la pagina più forte del sito.
    if ha_pagina(e):
        acts.append(f'<a class="event-act" href="/eventi/{slug_evento(e)}.html">'
                    f'{simbolo("i-arrow-right")} Scheda completa</a>')
    murl = maps_url(e)
    if murl:
        acts.append(f'<a class="event-act" href="{murl}" target="_blank" rel="noopener">{simbolo("i-pin")} Come arrivare</a>')
    # L'URL completo di Google Calendar porta dentro l'href il nome, le date e
    # la descrizione intera riscritta in percent-encoding: ~490 byte per riga,
    # 144 KB sull'agenda, per un link che quasi nessuno apre e che comunque sta
    # dentro un dettaglio chiuso. Qui resta la base valida (senza JS il link
    # funziona ancora, apre Calendar col modulo vuoto) e l'agenda lo completa
    # quando la riga si apre, leggendo nome, date e descrizione dal DOM: sono
    # gia' tutti li'. Nell'attributo resta solo il luogo, che nella riga chiusa
    # non c'e' in questa forma.
    cal_n = (f' data-cal-n="{esc(e["nome"])}"'
             if len((e['nome'] or '').strip()) > 110 else '')
    acts.append(f'<a class="event-act ev-gcal" href="{GCAL_BASE}" target="_blank" rel="noopener"'
                f' data-cal-l="{esc(_luogo_query(e))}"{cal_n}>'
                f'{simbolo("i-calendar")} Calendario</a>')
    if cover:
        acts.append(f'<a class="event-act" href="{cover}" target="_blank" rel="noopener">{simbolo("i-image")} Locandina</a>')
    # Il comune, quando ha una pagina sua. Sta in fondo perche' non e' un'azione
    # su QUESTO evento ma una via laterale, ed e' dentro il dettaglio che si apre
    # (nella riga chiusa la citta' vive dentro un <button>, dove un <a> non puo'
    # stare). Riguarda solo i comuni sopra soglia: gli altri restano testo.
    mio_hub = (hub or {}).get(_key(e.get('citta')))
    if mio_hub:
        acts.append(f'<a class="event-act" href="/eventi/comune/{mio_hub["slug"]}.html">'
                    f'{simbolo("i-pin")} Tutti gli eventi{a_citta(mio_hub["nome"])}</a>')

    dove = esc(e['indirizzo'] or e['luogo'])
    dove_html = (f'\n          <p class="ev-where">{simbolo("i-pin")} {dove}</p>'
                 if dove else '')

    # Il credito va anche QUI, non solo sulla scheda dedicata: le schede sono 71
    # su 187 eventi, quindi per due terzi dell'agenda l'attribuzione non
    # esisterebbe da nessuna parte.
    # Cliccabile: le occorrenze sono ~190 ma le destinazioni sono TRE, e i motori
    # consolidano per URL di destinazione - non e' un elenco di link diversi. Un
    # credito che non si puo' seguire e' mezzo credito, soprattutto per Cuneo.
    f = fonte_provincia(e['prov'])
    fonte_html = (f'\n            <p class="ev-src">Segnalato da '
                  f'<a class="ev-ig" href="{f["url"]}" target="_blank" rel="noopener">'
                  f'@{esc(f["ig"])}</a></p>' if f else '')

    return f'''        <article class="event-card{' is-ongoing' if ongoing else ''}" id="{anchor}" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}"{geo_attrs(e)}{free_attr(e)} style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <h4 class="ev-h"><button class="ev-row" type="button" aria-expanded="false" aria-controls="det-{anchor}">
            {thumb}
            <span class="ev-main">
              <span class="ev-name">{esc(trunc(e['nome'], 110))}</span>
              <span class="ev-line">{' · '.join(bits)}</span>
              <span class="ev-tags">{''.join(tags)}</span>
            </span>
            {simbolo("i-chevron-down", "icon ev-chev")}
          </button></h4>
          <div class="ev-det" id="det-{anchor}" hidden>
            <div class="event-desc">{descrizione_riga(e)}</div>{dove_html}
            <div class="event-actions">
              {chr(10) + '              '.join(acts)}
            </div>{fonte_html}
          </div>
        </article>'''


def hl_card(e, eager=False):
    """Scheda compatta con locandina per le corsie "Oggi" e "Questo weekend".
    Punta all'ancora della riga corrispondente più in basso nell'agenda.

    eager=True per le prime schede: sono sopra la piega e una di loro e'
    l'elemento LCP, quindi il lazy loading la rallenterebbe soltanto."""
    slug, cat_icon, catlabel = bucket(e)
    color, tint, ink = COLORS.get(slug, COLORS['altro'])
    # Anche le corsie prendono la miniatura: sono le PRIME immagini della
    # pagina - misurate, chi apre eventi.html e non scorre ne scarica 4, e sono
    # queste - quindi stanno sul percorso critico due volte, per la banda e per
    # il primo disegno. La copertina e' 262px larga e ritagliata a 130 di
    # altezza: una miniatura da 400 ci sta, su schermi molto densi si ammorbidisce
    # un po' ed e' un prezzo che si paga volentieri.
    cover = loc_path(e['loc'], mini=True)
    load = ('loading="eager" fetchpriority="high"' if eager
            else 'loading="lazy"')
    img = (f'<img src="{cover}" alt="" {load} decoding="async">'
           if cover else f'<span class="ev-hl-ph" aria-hidden="true">{cat_icon}</span>')
    bits = [f"{esc(e['citta'])} ({e['prov']})" if e['citta'] else e['prov']]
    if e['ora']:
        bits.append(esc(trunc(e['ora'], 20)))
    pill = prezzo_pill(e)
    return f'''        <a class="ev-hl-card" href="#{e.get('anchor', '')}" data-category="{slug}" data-province="{e['prov'].lower()}" data-start="{e['d_start'].isoformat()}" data-end="{e['d_end'].isoformat()}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
          <span class="ev-hl-cover">{img}</span>
          <span class="ev-hl-body">
            <span class="ev-hl-cat">{cat_icon} {esc(catlabel)}</span>
            <span class="ev-hl-name">{esc(trunc(e['nome'], 70))}</span>
            <span class="ev-hl-meta">{' · '.join(bits)}</span>
            {pill}
          </span>
        </a>'''


EAGER_HL = 2  # quante schede della prima corsia caricano l'immagine subito


def rail(titolo, lista, slug, eager=False):
    if not lista:
        return ''
    cards = '\n'.join(hl_card(e, eager=eager and i < EAGER_HL)
                      for i, e in enumerate(lista))
    return (f'      <section class="ev-hl-block" data-rail="{slug}">\n'
            f'        <h3 class="ev-hl-title">{titolo}<span class="ev-hl-n">{len(lista)}</span></h3>\n'
            f'        <div class="ev-rail">\n' + cards +
            '\n        </div>\n      </section>')


def intestazione_giorno(d, today):
    """'Oggi · lunedì 27 luglio'. Il prefisso viene ricalcolato anche lato JS,
    così resta corretto se la pagina viene servita da cache il giorno dopo."""
    if d == today:
        pre = 'Oggi · '
    elif d == today + datetime.timedelta(days=1):
        pre = 'Domani · '
    else:
        pre = ''
    return f"{pre}{GIORNI[d.weekday()]} {d.day} {MESI_LUNGHI[d.month - 1]}"


def render(events, hub=None):
    """Restituisce (opzioni del filtro Tipo, agenda completa)."""
    today = datetime.date.today()
    present = {bucket(e)[0] for e in events}

    # ── in evidenza: oggi e il primo weekend utile ──────────────────────────
    sat, sun = weekend_range(today)
    oggi = [e for e in events if e['d_start'] <= today <= e['d_end']]
    visti = {id(e) for e in oggi}
    wknd = [e for e in events if id(e) not in visti and e['d_start'] <= sun and e['d_end'] >= sat]
    blocchi = [rail('Oggi', oggi[:HL_LIMIT], 'oggi'),
               rail('Questo weekend', wknd[:HL_LIMIT], 'weekend')]
    blocchi = [b for b in blocchi if b]
    highlights = ''
    if blocchi:
        highlights = (f'    <div class="ev-highlights" id="ev-highlights" data-day="{today.isoformat()}">\n'
                      + '\n'.join(blocchi) + '\n    </div>\n\n')

    # ── agenda: prima la giornata più vicina ("Oggi"), poi gli eventi già
    #    iniziati ma ancora in corso, infine gli altri giorni. Prima il gruppo
    #    "in corso" apriva l'agenda: sul telefono spingeva "Oggi" sotto una
    #    lista di 10-15 sagre/mostre lunghe già partite, e chi apre la pagina
    #    vuole vedere subito cosa c'è OGGI, non cosa è iniziato la settimana scorsa.
    per_giorno = {}
    for e in events:
        if e['d_start'] >= today:
            per_giorno.setdefault(e['d_start'], []).append(e)
    giorni = sorted(per_giorno)
    in_corso = [e for e in events if e['d_start'] < today]

    gruppi = []
    if giorni:  # la giornata più vicina (di norma "Oggi") apre sempre l'agenda
        d0 = giorni.pop(0)
        gruppi.append((d0.isoformat(), intestazione_giorno(d0, today), per_giorno[d0]))
    if in_corso:
        gruppi.append(('in-corso', 'Già iniziati, ancora in corso', in_corso))
    for d in giorni:
        gruppi.append((d.isoformat(), intestazione_giorno(d, today), per_giorno[d]))

    sezioni = []
    for day, titolo, lista in gruppi:
        righe = '\n'.join(riga(e, today, hub) for e in lista)
        sezioni.append(f'''      <section class="ev-day" data-day="{day}">
        <h3 class="ev-dayhead"><span class="ev-dayname">{titolo}</span><span class="ev-daycount">{len(lista)}</span></h3>
{righe}
      </section>''')

    # Le pagine di provenienza, linkate UNA volta sola: sulle card il credito e'
    # testo, qui sotto ci sono i link veri. Solo le province con eventi in agenda,
    # cosi' la riga non promette una zona che oggi e' vuota.
    presenti = [s for s in PROVINCE_PUBBLICATE
                if any(e['prov'].upper() == s for e in events)]
    fonti = [f for f in (fonte_provincia(s) for s in presenti) if f]
    fonti_html = ''
    if fonti:
        # Non sono tutte la stessa cosa, e metterle in fila lo faceva credere.
        # Le pagine DAOP sono nostre, quella di Cuneo e' di Giovanni e noi la
        # ospitiamo: la riga separa le due frasi invece di elencare tre handle.
        # Il flag arriva da PROVINCE_IG, lo stesso che usa zone.html.
        def elenco(voci):
            return " · ".join(f'<a class="ev-ig" href="{f["url"]}" target="_blank" rel="noopener">'
                              f'@{esc(f["ig"])}</a> ({esc(f["provincia"])})' for f in voci)
        nostre = [f for f in fonti if f['nostra']]
        ospiti = [f for f in fonti if not f['nostra']]
        frasi = []
        if nostre:
            frasi.append('Gli eventi arrivano dalle pagine DAOP di zona: '
                         + elenco(nostre) + '.')
        if ospiti:
            quali = " e ".join(f"{esc(f['provincia'])} la segue "
                               f"<a class=\"ev-ig\" href=\"{f['url']}\" target=\"_blank\" rel=\"noopener\">"
                               f"@{esc(f['ig'])}</a>" for f in ospiti)
            frasi.append(f'{quali}: una pagina che non è nostra, con cui '
                         'collaboriamo e che accreditiamo su ogni scheda.')
        fonti_html = ('\n    <p class="ev-fonti">' + ' '.join(frasi)
                      + f'<br><a href="{ZONE_HREF}">Chi segue la tua provincia</a></p>')

    lista_html = (highlights + '    <div class="events-list" id="events-list">\n'
                  + '\n\n'.join(sezioni) + '\n    </div>' + fonti_html)

    # "Categorie" e non "Tutte le categorie": in un <select> stretto il testo
    # veniva tagliato a meta' sul telefono.
    opts = ['      <option value="all">Categorie</option>']
    for s in ORDER:
        if s in present:
            opts.append(f'      <option value="{s}">{LABELS[s]}</option>')
    return '\n'.join(opts), lista_html


def render_home(events):
    """Card compatte per il carosello "Prossimi eventi" della home (index.html).
    Mostra i primi HOME_LIMIT eventi futuri, ognuno linkato alla card completa
    in eventi.html tramite la sua ancora."""
    items = events[:HOME_LIMIT]
    if not items:
        return ('      <p class="he-empty">Nessun evento in programma al momento. '
                '<a href="eventi.html" style="color:var(--orange);font-weight:700;">'
                'Vedi tutti gli eventi →</a></p>')
    today = datetime.date.today()
    cards = []
    for e in items:
        slug, cat_icon, catlabel = bucket(e)
        d = e['d_start']
        ongoing = d < today
        datebox = ('<span class="he-live">In corso</span>' if ongoing else
                   f'<span class="he-date"><span class="d">{d.day:02d}</span>'
                   f'<span class="m">{MESI[d.month-1]}</span></span>')
        color, tint, ink = COLORS.get(slug, COLORS['altro'])
        luogo = (esc(e['citta']) + f" ({e['prov']})") if e['citta'] else e['prov']
        if e_gratuito(e):
            price = '<span class="he-price free">Gratuito</span>'
        elif e['prezzo']:
            price = f'<span class="he-price">{esc(trunc(e["prezzo"], 22))}</span>'
        else:
            price = '<span class="he-price">&nbsp;</span>'
        cover_url = loc_path(e['loc'])
        cover = (f'        <div class="he-cover"><img src="{cover_url}" '
                 f'alt="Locandina: {esc(trunc(e["nome"], 70))}" loading="lazy" decoding="async"></div>\n'
                 if cover_url else '')
        href = f"eventi.html#{e.get('anchor', '')}"
        cards.append(f'''      <a class="he-card" href="{href}" style="--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}">
{cover}        <div class="he-body">
          <div class="he-top">
            <span class="he-icon">{cat_icon}</span>
            <span class="he-cat">{esc(catlabel)}</span>
            {datebox}
          </div>
          <h3 class="he-title">{esc(trunc(e['nome'], 64))}</h3>
          <div class="he-meta"><span>{PIN_SVG} {luogo}</span></div>
          <div class="he-foot">
            {price}
            <span class="he-more">Scopri di più {ARROW_SVG}</span>
          </div>
        </div>
      </a>''')
    return '\n\n'.join(cards)


def slugify(s):
    """Slug ASCII per ancore/URL: 'Sagra di Città' -> 'sagra-di-citta'."""
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s[:50].strip('-') or 'evento'


def assegna_ancore(events):
    """Dà a ogni evento un id univoco e stabile (data + slug del nome), usato sia
    come ancora della card sia come URL nei dati strutturati."""
    seen = set()
    for e in events:
        base = f"ev-{e['d_start'].isoformat()}-{slugify(e['nome'])}"
        anchor, i = base, 2
        while anchor in seen:
            anchor = f"{base}-{i}"
            i += 1
        seen.add(anchor)
        e['anchor'] = anchor


def parse_times(ora):
    """Estrae fino a due orari HH:MM (inizio/fine) dal campo Ora."""
    return [f"{int(h):02d}:{m}" for h, m in re.findall(r'(\d{1,2})[:.](\d{2})', ora or '')][:2]


def parse_price(prezzo):
    """Estrae il prezzo numerico più basso (in €) dal testo; None se assente.
    Considera solo i numeri accostati a € o "euro", per non confondere
    prezzi con età o numero di persone."""
    p = prezzo or ''
    nums = re.findall(r'€\s*(\d+(?:[.,]\d{1,2})?)', p)
    nums += re.findall(r'(\d+(?:[.,]\d{1,2})?)\s*(?:€|euro)', p, re.I)
    vals = []
    for n in nums:
        try:
            v = float(n.replace(',', '.'))
            if v > 0:
                vals.append(v)
        except ValueError:
            pass
    if not vals:
        return None
    v = min(vals)
    return str(int(v)) if v == int(v) else f"{v:.2f}"


def rome_offset(d):
    """Offset di Europe/Rome per una data: +02:00 in ora legale, +01:00 altrimenti."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Rome")
    except Exception:                      # tzdata assente: assume ora solare
        return "+01:00"
    off = datetime.datetime(d.year, d.month, d.day, 12, tzinfo=tz).utcoffset()
    total = int(off.total_seconds()) // 60
    return f"{'+' if total >= 0 else '-'}{abs(total) // 60:02d}:{abs(total) % 60:02d}"


def event_jsonld(e, url_override=None):
    """Costruisce un oggetto schema.org/Event per un singolo evento.

    url_override: URL canonico dell'evento. Se l'evento ha una pagina dedicata
    passiamo quella, così i dati strutturati puntano alla pagina che vogliamo
    far posizionare invece che all'ancora dentro l'agenda."""
    times = parse_times(e['ora'])
    start = e['d_start'].isoformat()
    end = e['d_end'].isoformat()
    if times:
        ora_i = times[0]
        ora_f = times[1] if len(times) > 1 else times[0]
        fine = e['d_end']
        # Una serata che nel foglio finisce "alle 00:00" (o alle 01:30) finisce
        # DOPO mezzanotte, cioe' il giorno dopo. Scritta sulla stessa data,
        # endDate cade PRIMA di startDate: per Google e' un errore critico, e un
        # Event non valido non prende il rich result - quindi la pagina perde in
        # SERP proprio le date e il badge evento, che sono la ragione per cui i
        # dati strutturati ci sono. Trovato su "Ferragosto 2026 - Family Eco
        # Park", ora "10:00-00:00": 1 pagina su 100 oggi, ma la scrittura
        # "dalle 21 alle 24" nel foglio e' comune e ricapita a ogni stagione.
        if len(times) > 1 and fine == e['d_start'] and ora_f <= ora_i:
            fine += datetime.timedelta(days=1)
        start += f"T{ora_i}{rome_offset(e['d_start'])}"
        end = f"{fine.isoformat()}T{ora_f}{rome_offset(fine)}"

    city = (e['citta'] or '').strip()
    address = {"@type": "PostalAddress", "addressCountry": "IT"}
    if city:
        address["addressLocality"] = city
    if e['prov']:
        address["addressRegion"] = e['prov']
    venue = (e.get('luogo') or '').strip()
    if venue:
        address["streetAddress"] = venue
    if url_override:
        ev_url = url_override
    else:
        ev_url = f"{PAGE_URL}#{e['anchor']}" if e.get('anchor') else PAGE_URL

    obj = {
        "@type": "Event",
        "name": (e['nome'] or '').strip(),
        "startDate": start,
        "endDate": end,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": venue or city or e['prov'],
            "address": address,
        },
        "image": [loc_url(e['loc']) or DEFAULT_IMG],
        "url": ev_url,
    }
    # Questi eventi sono organizzati da pro loco, comuni e associazioni: DAOP
    # li raccoglie e li segnala. Dichiarare DAOP come chi organizza o chi si
    # esibisce e' un dato strutturato falso, e Google lo incrocia con le altre
    # fonti.
    #
    # La manifestazione del foglio NON va in superEvent come semplice nome:
    # Google legge quell'oggetto come un secondo Event a se' stante, che ha solo
    # "name" e quindi risulta privo di startDate e location (errori critici in
    # Search Console: 0 elementi non validi fino al 01/08/2026, 224 il giorno
    # dopo il deploy che introduceva questo blocco). Per dichiararla servirebbe
    # un evento-padre completo di date e luogo propri, dato che il foglio non
    # ha; il nome della manifestazione resta comunque visibile nella card.
    # Chi organizza: NON lo inventiamo, lo leggiamo dalla coda del nome quando il
    # foglio ce l'ha ("... - Pro Loco Ciglione"). E' il dato che Google incrocia
    # con le altre fonti, quindi o e' quello vero o non ci va.
    org = organizzatore(e.get('nome'))
    if org:
        obj["organizer"] = {"@type": "Organization", "name": org}
        # I recapiti del foglio sono di chi organizza, non di DAOP: vanno
        # sull'organizzatore, e solo se abbiamo un nome a cui attaccarli.
        cont = (e.get('contatto') or '').strip()
        mail = MAIL_RE.search(cont)
        tel = TEL_RE.search(cont)
        if mail:
            obj["organizer"]["email"] = mail.group(0)
        if tel:
            obj["organizer"]["telephone"] = re.sub(r'[^+0-9]', '', tel.group(0))
    xy = coord(e)
    if xy:
        obj["location"]["geo"] = {"@type": "GeoCoordinates",
                                  "latitude": xy[0], "longitude": xy[1]}
    # Senza condizioni: in agenda ci entra solo quello che abbiamo scelto per le
    # famiglie, quindi il pubblico e' quello per ogni evento pubblicato. Prima
    # dipendeva dalla colonna "Adatto Famiglie" del foglio, che pero' e' "Si" nel
    # 95% delle righe e vuota o "Da verificare" nelle altre: 13 eventi su 294
    # restavano senza audience per come era compilata una cella, non perche'
    # fossero rivolti a qualcun altro.
    obj["audience"] = {"@type": "Audience", "audienceType": "Famiglie con bambini"}
    fascia = fascia_eta(e.get('eta_consigliata') or e.get('eta'))
    if fascia:
        obj["typicalAgeRange"] = fascia
    descr = (e['descr'] or '').strip()
    if descr:
        obj["description"] = descr

    # offers: includiamo price + priceCurrency + validFrom (richiesti per un'offerta valida).
    # Per gli eventi "a pagamento" senza una cifra nota omettiamo offers, così da non
    # generare un'offerta incompleta (causa degli avvisi di Search Console).
    if e_gratuito(e):
        price = "0"
        obj["isAccessibleForFree"] = True
    else:
        price = parse_price(e['prezzo'])
    if price is not None:
        obj["offers"] = {"@type": "Offer", "price": price, "priceCurrency": "EUR",
                         "availability": "https://schema.org/InStock",
                         "validFrom": e['d_start'].isoformat(), "url": ev_url}
    return obj


def render_jsonld(events):
    """Blocco <script> JSON-LD con tutti gli eventi (schema.org/Event).

    Compatto, non indentato: con 280 eventi l'indentazione a due spazi vale da
    sola ~150 KB di HTML, e nessuno legge questo blocco a occhio - chi vuole
    controllarlo usa il Rich Results Test, che formatta da se'. inject() lo
    scrive in fondo al body, non nel <head>: e' il blocco piu' pesante della
    pagina e non ha niente da dire al browser prima del contenuto."""
    graph = [event_jsonld(e, pagina_url(e) if ha_pagina(e) else None) for e in events]
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph},
                         ensure_ascii=False, separators=(',', ':'))
    return ('<script type="application/ld+json" id="eventi-jsonld">'
            + payload + '</script>')


# ---------------------------------------------------------------------------
# PAGINE EVENTO DEDICATE
#
# Perche': in Search Console le query per nome della singola sagra ("festa
# valenzani 2026", "sagra basaluzzo 2026") portano decine di impressioni con
# zero clic, perche' ci arriviamo con l'agenda generica in ottava posizione.
# Una pagina per evento risponde esattamente a quella query.
#
# Per un anno la regola e' stata "solo Sagra & Festa", con la motivazione che
# generare tutti gli eventi avrebbe prodotto pagine-template magre. I dati del
# 09/08/2026 dicono che quella motivazione non regge: la mediana della
# descrizione e' 187 caratteri per le sagre e 223 per i laboratori. Le sagre non
# vincono perche' le loro pagine siano piu' ricche - vincono perche' hanno un
# nome che qualcuno digita ("festa cassinasco 2026", CTR 24%).
#
# La discriminante vera e' quindi la DOMANDA NOMINALE, non la categoria: un nome
# proprio che si cerca, piu' abbastanza testo da non essere il volantino
# ribattuto. Sotto i 250 caratteri la pagina non ha niente da dire che l'agenda
# non dica meglio - ed e' una soglia piu' severa della mediana delle sagre che
# gia' pubblichiamo, non piu' generosa.
#
# Serve anche a coprire un buco: fino a ieri i 34 laboratori, i 35 spettacoli e
# i 27 eventi di cultura in agenda non avevano NESSUNA pagina, cioe' proprio la
# parte pensata per i bambini restava invisibile ai motori.
#
# Le pagine NON vengono mai cancellate. normalize() scarta gli eventi passati,
# quindi una sagra conclusa sparisce dalla sorgente: rigenerare solo dal feed
# significherebbe un 404 per ogni edizione finita. Il registro in
# data/pagine-evento.json conserva i dati, la pagina resta online marcata
# "edizione conclusa" e se l'anno dopo la sagra torna la stessa URL si
# aggiorna, conservando l'autorita' accumulata.
#
# E' anche il motivo per cui questa regola va allargata con prudenza: una pagina
# sbagliata resta online per sempre. Ogni run stampa l'elenco di quelle aperte
# dal criterio nominale, cosi' si vede cosa e' entrato finche' sono poche.
# ---------------------------------------------------------------------------
PAGINE_DIR = os.path.join(ROOT, "eventi")
REGISTRO_PATH = os.path.join(ROOT, "data", "pagine-evento.json")
SAGRA_KW = ('sagra', 'festa', 'palio', 'fiera')

MIN_DESCR_PAGINA = 250   # caratteri: sopra la mediana delle sagre gia' online

# Soglia piu' bassa per gli eventi pensati per i bambini. MIN_DESCR_PAGINA e'
# tarata sulle sagre, che nel foglio hanno la scheda lunga; laboratori,
# spettacoli e teatro per bambini stanno intorno ai 210 caratteri e restavano
# tutti fuori. Erano 118 eventi su 227 senza pagina propria, e sono proprio le
# righe su cui si cerca "eventi bambini <paese>": senza pagina finiscono in
# un'ancora #ev- dentro eventi.html, che non e' una URL a se' (non si
# posiziona, non si manda su WhatsApp, non vale come voce di carosello - vedi
# _voci_lista). A fare il filtro resta nome_cercabile(), non la lunghezza:
# "Caccia al Tesoro" e "Giochi in Piazza" restano fuori, "Pompieropoli" e "I
# Musicanti di Brema" entrano.
MIN_DESCR_BAMBINI = 120

# Parole che da sole non fanno un nome che qualcuno digita. "Serata Giochi" e
# "Caccia al Tesoro" sono etichette, non nomi: ce n'e' una in ogni paese e
# nessuno le cerca. "Mostra delle Illusioni" invece ha "Illusioni", che e' la
# parola con cui la si cerca. La lista tiene solo teste generiche: se dopo
# averle tolte non resta niente, non c'e' un nome da posizionare.
NOMI_GENERICI = frozenset("""
laboratorio laboratori mostra mostre mercato mercatino mercatini serata serate
gioco giochi giochiamo caccia tesoro lettura letture cinema film proiezione
passeggiata passeggiate camminata concerto concerti spettacolo spettacoli
corso corsi torneo tornei gara gare escursione escursioni visita visite
aperitivo cena cene pranzo pranzi merenda colazione degustazione degustazioni
notte notti giornata giornate pomeriggio mattina mattinata sera serale
estate autunno inverno primavera gennaio febbraio marzo aprile maggio giugno
luglio agosto settembre ottobre novembre dicembre
bambini bambine bambino famiglie famiglia ragazzi ragazze adulti piccoli grandi
apertura chiusura inaugurazione incontro incontri attivita evento eventi
festa feste sagra sagre fiera fiere palio raduno ritrovo appuntamento
piazza piazze centro paese comune parco parchi giardino giardini campo campi
musica musicale ballo danza teatro teatrale animazione intrattenimento
libera libero aperta aperto grande piccola nuovo nuova primo prima
""".split())

# Articoli, preposizioni e congiunzioni: non contano ne' come nome ne' come
# parola generica, semplicemente non pesano.
PAROLE_VUOTE = frozenset("""
il lo la i gli le un uno una dei del della delle degli dal dalla dai dalle
di da a ad in con su per tra fra al allo alla ai agli alle nel nello nella
nei negli nelle sul sullo sulla sui sugli sulle e ed o od che chi cui non
""".split())

# ORGANIZZATORE_RE taglia solo quando l'organizzatore segue un trattino, perche'
# li' serve a ripulire il title. Qui il taglio dev'essere piu' largo: in "Serata
# Giochi - KaM 3841 e Pro Loco Crissolo" l'organizzatore arriva dopo una "e", e
# senza toglierlo era "Crissolo" a far sembrare cercabile un nome che non lo e'.
RUOLO_ORGANIZZATORE_RE = re.compile(
    r'\b(?:Pro\s*Loco|Comitato|Associazione|Circolo|Gruppo|Parrocchia|Oratorio|'
    r'Polisportiva|Comune\s+di|A\.?S\.?D\.?)\b.*$', re.I)


def _parole_nome(nome):
    """Le parole del nome che possono reggere una ricerca: via l'organizzatore,
    via l'anno e il numero di edizione, via articoli e preposizioni."""
    n = RUOLO_ORGANIZZATORE_RE.sub(' ', nome or '').strip(' -–—')
    n = re.sub(r'\b(?:19|20)\d{2}\b', ' ', n)
    n = re.sub(r'(?<!\w)\d+\s*[°ºª^]', ' ', n)
    parole = re.findall(r"[0-9A-Za-zÀ-ÿ']{2,}", n)
    return [p for p in parole if p.lower() not in PAROLE_VUOTE]


def _insieme_parole(nome):
    """Le parole del nome come insieme, per riconoscere due titoli girati.

    Nel foglio capita che lo stesso evento sia inserito due volte con le parole
    in ordine diverso: sono due righe, due slug, ma una cosa sola."""
    return frozenset(p.lower() for p in _parole_nome(nome))


def nome_cercabile(nome):
    """True se nel nome resta qualcosa che si puo' cercare per nome.

    Serve almeno una parola di quattro LETTERE che non sia una testa generica:
    e' quella la parola che qualcuno digita insieme al paese. Le lettere sono
    richieste sul serio, perche' altrimenti "Serata Giochi - KaM 3841" passava
    grazie al numero della sezione, che nessuno ha mai cercato."""
    parole = _parole_nome(nome)
    if len(parole) < 2:
        return False
    return any(sum(c.isalpha() for c in p) >= 4 and p.lower() not in NOMI_GENERICI
               for p in parole)


def ha_pagina(e):
    """True se l'evento merita una pagina dedicata."""
    if (e.get('categoria') or '') == 'Sagra & Festa':
        return True
    nome = e.get('nome') or ''
    if any(w in nome.lower() for w in SAGRA_KW):
        return True
    # Fuori dalle sagre serve tutto: un nome che si cerca E il testo per
    # riempire la pagina. Uno dei due da solo non basta.
    descr = len((e.get('descr') or '').strip())
    if descr >= MIN_DESCR_PAGINA and nome_cercabile(nome):
        return True
    # Gli eventi per bambini entrano con meno testo, ma con lo stesso filtro sul
    # nome. "Per bambini" e' il segnale forte gia' usato altrove: una fascia
    # d'eta' NUMERICA decisa a mano nel foglio, non il flag "Adatto famiglie"
    # che ce l'ha il 93% delle righe e quindi non distingue niente.
    return (descr >= MIN_DESCR_BAMBINI and nome_cercabile(nome)
            and e_per_bambini(e))


# Slug che una pagina evento non puo' prendersi: /eventi/oggi.html e
# /eventi/weekend.html stanno nella stessa cartella, e una sagra che si
# chiamasse "Oggi" sovrascriverebbe la pagina di intenzione senza un errore.
SLUG_RISERVATI = {'oggi', 'weekend'}


# Il numero di edizione esiste anche in numeri romani ("XXVII Sagra delle Trofie
# al Pesto"), e li' le regex in cifre non arrivano. Si toglie SOLO in testa al
# nome, dove sta un numero di edizione: cercarlo dappertutto mangerebbe il "II"
# di "A Calosso Museo e Dintorni - Settembre II", che numero di edizione non e'.
# Maiuscolo obbligatorio e almeno due lettere, se no "Di", "Il", "Mi" sono tutti
# numeri romani validi e ogni nome che comincia con una preposizione ci cascava.
ROMANO_INIZIALE_RE = re.compile(
    r'^\s*(?=[MDCLXVI]{2,}\b)M*(?:C[MD]|D?C*)(?:X[CL]|L?X*)(?:I[XV]|V?I*)\b\s*')


def slug_evento(e):
    """Slug stabile fra un'edizione e l'altra: togliamo l'anno e il numero di
    edizione dal nome ("40ª Sagra del Guanciotto 2026" -> "sagra-del-guanciotto")
    e aggiungiamo la citta'. Cosi' l'edizione 2027 aggiorna la stessa URL invece
    di crearne una nuova che riparte da zero."""
    nome = re.sub(r'\b(?:19|20)\d{2}\b', ' ', e.get('nome') or '')
    # Numero di edizione, in tutte le grafie che compaiono nel foglio: 1°, 3ª,
    # 3^, 40ª, 6º, 3a. Va tolto o l'edizione successiva creerebbe una URL nuova
    # invece di aggiornare questa, che è tutto il punto dello slug evergreen.
    # \b non funziona dopo ° perché non è un carattere di parola.
    nome = re.sub(r'(?<!\w)\d+\s*[°ºª^]', ' ', nome)
    nome = re.sub(r'(?<!\w)\d+a\b', ' ', nome)
    nome = ROMANO_INIZIALE_RE.sub('', nome, count=1)
    base = slugify(nome)
    citta = slugify(e.get('citta') or '')
    if citta and citta not in base:
        base = f"{base}-{citta}"
    base = base.strip('-')[:80].strip('-') or 'evento'
    return f"{base}-evento" if base in SLUG_RISERVATI else base


def pagina_url(e):
    return f"{SITE_URL}/eventi/{slug_evento(e)}.html"


MAX_TITLE = 62  # oltre, Google tronca nello snippet

# Nel foglio il nome porta spesso in coda chi organizza ("… - Pro Loco Ferrere").
# Nel title è spazio sprecato: nessuno cerca la sagra per nome della pro loco, e
# senza sparisce quasi ogni troncamento. Resta per intero nell'H1 e nel corpo.
ORGANIZZATORE_RE = re.compile(
    r'\s*[-–—]\s*(?:Pro\s*Loco|Comune|Comitato|Associazione|Circolo|Gruppo|'
    r'Parrocchia|A\.?S\.?D\.?)\b.*$', re.I)

# Stessa coda, ma catturata: serve a dichiarare organizer nei dati strutturati.
ORGANIZZATORE_NOME_RE = re.compile(
    r'[-–—]\s*((?:Pro\s*Loco|Comune|Comitato|Associazione|Circolo|Gruppo|'
    r'Parrocchia|A\.?S\.?D\.?)\b[^-–—]*)$', re.I)


def organizzatore(nome):
    """Chi organizza, quando il nome nel foglio lo porta in coda. '' altrimenti."""
    m = ORGANIZZATORE_NOME_RE.search((nome or '').strip())
    return re.sub(r'\s+', ' ', m.group(1)).strip(' .') if m else ''


def fascia_eta(testo):
    """typicalAgeRange da 'Età consigliata' quando c'e' un intervallo numerico:
    '3-10 anni' -> '3-10', 'dai 6 anni' -> '6-'. 'Tutte le età' non e' una
    fascia: dichiararla come 0- sarebbe un dato inventato, quindi resta vuota."""
    t = (testo or '').strip()
    if not t:
        return ''
    m = re.search(r'(\d{1,2})\s*(?:-|–|—|a|/)\s*(\d{1,2})', t)
    if m and int(m.group(1)) <= int(m.group(2)):
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r'\b(?:dai|da|oltre i|\+)\s*(\d{1,2})', t, re.I)
    if m:
        return f"{m.group(1)}-"
    return ''


def a_citta(citta):
    """' ad Acqui Terme' ma ' a Novi Ligure': davanti a vocale ci va la d.
    Vale sia per il title sia per la meta description, cioè per le due righe
    che la gente legge davvero: "a Acqui" in pagina dei risultati si nota."""
    if not citta:
        return ""
    return f" ad {citta}" if citta[0].lower() in 'aeiou' else f" a {citta}"


def _scorpora_anno(nome):
    """Il nome senza l'anno, ovunque stia. Serve a rimetterlo dopo, in un posto
    fisso: nel foglio l'anno sta quasi sempre in coda ("Sagra del Cinghiale
    2026") ma non sempre, e due anni nello stesso title sono peggio di zero."""
    return re.sub(r'\s{2,}', ' ', re.sub(r'\s*\b(?:19|20)\d{2}\b', ' ', nome or '')).strip(' -–—')


# Parole che in fondo a un title tagliato non dicono niente: "Apertura Stand
# Gastronomico con I… 2026" si legge male e "con I" non entra in nessuna query.
CODA_VUOTA_RE = re.compile(
    r'[\s,;:.&–—-]*\b(?:e|ed|con|di|da|a|ad|in|per|su|tra|fra|il|lo|la|i|gli|le|'
    r'un|uno|una|del|dello|della|dei|degli|delle|al|allo|alla|ai|agli|alle|'
    r'dal|dallo|dalla|dai|nel|nella|sul|sulla)\s*$', re.I)


def _coda_propria(nome):
    """Le ultime parole del nome, se sono un nome proprio: "… con Shary Band",
    "… con Luigi Gallia", "… con Alex e la Band". '' se non lo sono.

    Serve perche' e' li' che sta la differenza fra una serata e l'altra. A
    Rocchetta Tanaro il foglio ha quattro "Apertura Stand Gastronomico con
    <nome del gruppo>": tagliando dalla fine diventano quattro pagine con lo
    stesso identico title, e due pagine con lo stesso title per Google sono una
    pagina sola. Meglio un buco in mezzo che quattro doppioni."""
    parole = nome.split()
    coda = []
    for p in reversed(parole[1:]):            # la prima parola non e' mai coda
        if len(coda) >= 3 or sum(len(x) + 1 for x in coda) > 20:
            break
        coda.insert(0, p)
        if p[:1].isupper() and not CODA_VUOTA_RE.match(p):
            continue
        if not coda[0][:1].isupper():
            coda.pop(0)
            break
    while coda and not coda[0][:1].isupper():
        coda.pop(0)
    return " ".join(coda) if coda and any(p[:1].isupper() for p in coda) else ''


# Nel foglio il nome e' quasi sempre una collana di pezzi separati da trattino
# o virgola: "<chi suona> - <che gruppo e'> - <la festa in cui suona>".
SEPARATORE_RE = re.compile(r'\s*[-–—|·]\s+|\s*,\s*')


def _frase_sagra(nome):
    """La frase che contiene sagra/festa/fiera/palio, intera. '' se non c'e'.

    E' QUELLA la query. "sagra del peperone costigliole" si cerca, "gianmarco
    bagutti" no, e nel foglio la festa sta spesso in fondo, dopo il nome di chi
    suona quella sera: "Gianmarco Bagutti - Orchestra Italiana - 79° Sagra del
    Peperone". Tagliando dalla coda, _coda_propria si fermava sul "del"
    minuscolo e teneva solo "Peperone" - cioe' la parola meno cercabile delle
    tre, senza il "Sagra del" che la rende una ricerca. In Search Console
    quella pagina ha fatto 289 impressioni allo 0,7% di CTR in tre mesi: e'
    l'unica delle 218 in cui il troncamento perdeva la parola della festa, ma
    e' anche la piu' vista, e il nome "artista - orchestra - sagra" nel foglio
    ricorre a ogni serata di ballo.

    Si ferma al separatore: oltre il trattino comincia un'altra cosa (la pro
    loco, il paese, l'orchestra). Quattro parole al massimo perche' "Sagra del
    Peperone" ne vuole tre e "Festa Patronale di San Rocco" quattro; se la
    quarta e' un articolo la frase si chiude prima, altrimenti resta appesa
    ("Sagra dell'Agnolotto e del")."""
    for pezzo in SEPARATORE_RE.split(nome or ''):
        parole = pezzo.strip(' -–—').split()
        for i, p in enumerate(parole):
            if any(k in p.lower() for k in SAGRA_KW):
                frase = " ".join(parole[i:i + 4])
                prima = None
                while prima != frase:
                    prima = frase
                    frase = CODA_VUOTA_RE.sub('', frase).rstrip(' ,;:.-–—&')
                return frase
    return ''


def _taglia_nome(nome, quanti, evita=''):
    """Il nome accorciato all'ultima parola che vale la pena leggere, tenendo
    la coda quando e' quella a distinguere un evento dall'altro.

    `evita`: la citta'. Nel foglio il nome finisce spesso con il comune
    ("Festeggiamenti Patronali Sant'Agostino - Ferrere"), e tenerla come coda
    darebbe "Festeggiamenti Patronali… Ferrere a Ferrere": due volte la stessa
    parola al posto di quella che manca."""
    nome = (nome or '').strip()
    if len(nome) <= quanti:
        return nome

    def pulisci(s):
        prima = None
        while prima != s:                     # "con i" se ne va in due giri
            prima = s
            s = CODA_VUOTA_RE.sub('', s).rstrip(' ,;:.-–—&')
        return s

    # La festa batte il nome proprio: fra "… Shary Band" e "… Sagra del
    # Peperone" la seconda e' una query e la prima no. Ma solo se il taglio
    # normale la perderebbe davvero: quando la festa e' gia' in testa al nome
    # ("Festa Patronale di San Bartolomeo - …") tenerla anche in coda la scrive
    # due volte nello stesso title.
    sagra = _frase_sagra(nome)
    if sagra and sagra in nome[:quanti]:
        sagra = ''
    coda = sagra or _coda_propria(nome)
    if coda and evita and (_key(coda) in _key(evita) or _key(evita) in _key(coda)):
        coda, sagra = '', ''
    if coda and len(coda) + 14 <= quanti:
        testa = pulisci(nome[:quanti - len(coda) - 2].rsplit(' ', 1)[0])
        # Solo se la testa resta una frase e non due parole monche, e solo se
        # la coda non c'e' gia' dentro (nomi corti, dove il taglio non serve).
        # Con la festa in coda basta una parola intera ("Gianmarco…"): il taglio
        # cade comunque su uno spazio, e li' serve solo a distinguere una serata
        # dall'altra - il resto del title lo fa gia' il nome della sagra.
        if len(testa) >= (9 if sagra else 12) and coda not in testa:
            return f"{testa}… {coda}"
    # Ultima scelta: la festa da sola. Un title corto che contiene la query
    # batte un title pieno che non la contiene.
    if sagra and len(sagra) <= quanti and sagra not in nome[:quanti]:
        return sagra
    corto = pulisci(nome[:quanti].rsplit(' ', 1)[0])
    return f"{corto}…" if corto else trunc(nome, quanti)


def _titolo(nome, citta, anno=None):
    """Title che sta nei limiti senza mai perdere la città, l'anno, né finire a
    metà parola. Ordine di sacrificio: prima il suffisso di brand, poi la coda
    dell'organizzatore, poi il nome della festa.

    L'ANNO NON SI TOCCA, ed è la correzione dell'08/08/2026. Prima arrivava qui
    incollato in fondo al nome ("Sagra del Cinghiale 2026"), quindi era l'ultima
    cosa della stringa: e siccome il taglio parte dalla fine, sui nomi lunghi
    spariva. Erano 47 pagine su 88, cioè più della metà, e l'anno è esattamente
    la parola che in Search Console fa la differenza fra un title che porta
    clic e uno che ne porta zero: "cassinasco festa 2026" batte al 62%,
    "sagra morbello 2026" al 37%, mentre le query senza anno restano a guardare.
    Si accorcia il nome e l'anno resta, non il contrario."""
    nome = (nome or '').strip()
    if anno:
        nome = _scorpora_anno(nome) or nome
    coda = f" {anno}{a_citta(citta)}" if anno else a_citta(citta)
    for base in (nome, ORGANIZZATORE_RE.sub('', nome).strip(' -–—')):
        for suffisso in (" | DAOP", ""):
            t = f"{base}{coda}{suffisso}"
            if len(t) <= MAX_TITLE:
                return t
    corto = ORGANIZZATORE_RE.sub('', nome).strip(' -–—') or nome
    return f"{_taglia_nome(corto, max(MAX_TITLE - len(coda) - 1, 20), citta)}{coda}"


def _dal(giorno):
    """'Dal 7' ma 'Dall'8' e 'Dall'11': l'articolo cambia davanti a vocale."""
    return f"Dall'{giorno}" if giorno in (8, 11) else f"Dal {giorno}"


def data_estesa(d):
    return f"{GIORNI[d.weekday()]} {d.day} {MESI_LUNGHI[d.month - 1]} {d.year}"


def periodo_esteso(rec):
    di, df = rec['d_start'], rec['d_end']
    if di == df:
        return data_estesa(di).capitalize()
    if (di.year, di.month) == (df.year, df.month):
        return f"{_dal(di.day)} al {df.day} {MESI_LUNGHI[df.month - 1]} {df.year}"
    return (f"{_dal(di.day)} {MESI_LUNGHI[di.month - 1]} "
            f"al {df.day} {MESI_LUNGHI[df.month - 1]} {df.year}")


# Quello che la gente cerca non e' il nome della festa: e' quello che ci trova
# dentro. In sette giorni le query sui fuochi d'artificio di Novi Ligure hanno
# fatto 283 impressioni e 1 solo clic, da settima posizione: la pagina c'era e
# rispondeva, ma nello snippet si leggevano solo le date, e la parola stava
# sepolta a meta' descrizione scritta "spettacolo pirotecnico". Chi cerca
# "fuochi d'artificio novi ligure 2026" non riconosceva la risposta.
#
# Qui il richiamo lo tiriamo fuori dal testo e lo mettiamo in testa alla meta
# description, che e' la riga che si legge fra i risultati. Non si inventa
# niente: se la parola non e' nella descrizione del foglio, non esce. L'ordine
# della lista e' l'ordine in cui la gente cerca, e ne teniamo al massimo tre:
# oltre, la riga diventa un elenco della spesa e non la legge nessuno.
RICHIAMI = [
    (r'pirotecnic|fuochi', "fuochi d'artificio"),
    (r'luna\s*park', "luna park"),
    (r'giostr', "giostre"),
    (r'gonfiabil', "gonfiabili"),
    (r'trucca\s*-?\s*bimbi|face\s*painting', "truccabimbi"),
    (r'buratt|marionett', "burattini"),
    (r'laborator', "laboratori per bambini"),
    (r'mercatin|bancarell|banchett|hobbist', "mercatino"),
    (r'street\s*food', "street food"),
    (r'stand\s+gastronomic|cucina\s+apert', "stand gastronomico"),
    (r'degustazion', "degustazioni"),
    (r'process', "processione"),
    (r'rievocazion|medioeval|sbandierator', "rievocazione storica"),
    (r'sfilat|carr\w*\s+allegoric', "sfilata"),
    (r'orchestra|liscio', "ballo con orchestra"),
    (r'\bdj\b', "dj set"),
    (r'musica\s+dal\s+vivo|concerto|tribute|cover\s+band', "musica dal vivo"),
    (r'mongolfier', "mongolfiere"),
]
RICHIAMI = [(re.compile(rx, re.I), etichetta) for rx, etichetta in RICHIAMI]

# Una descrizione che promette una cosa che non c'e' costa molto piu' del clic
# che porta: e' la parola di DAOP che ci va di mezzo. Quindi se il testo la nega
# ("quest'anno senza fuochi", "lo spettacolo pirotecnico e' annullato"), il
# richiamo non esce. La negazione si cerca nella proposizione in cui cade la
# parola, non in una finestra di caratteri: "niente gonfiabili, ma ci sono i
# burattini" deve perdere i gonfiabili e tenere i burattini.
NEGAZIONE_RE = re.compile(
    r'\b(?:senza|niente|nessun\w*|non|salt(?:a|ato|ata|ate)|annullat\w*|'
    r'sospes\w*|rinviat\w*)\b', re.I)
STACCHI = '.;:!?,\n'


def _proposizione(testo, pos):
    """Il pezzo di frase in cui cade pos, fra due segni di punteggiatura."""
    inizio = max(testo.rfind(c, 0, pos) for c in STACCHI) + 1
    fini = [i for i in (testo.find(c, pos) for c in STACCHI) if i != -1]
    return testo[inizio:min(fini) if fini else len(testo)]


def richiami(testo, massimo=3):
    """Le attrazioni davvero citate nella descrizione, pronte da leggere."""
    testo = testo or ''
    trovati = []
    for rx, etichetta in RICHIAMI:
        for m in rx.finditer(testo):
            if NEGAZIONE_RE.search(_proposizione(testo, m.start())):
                continue
            trovati.append(etichetta)
            break
        if len(trovati) >= massimo:
            break
    return trovati


def elenco_it(voci):
    """'a, b e c': l'ultima virgola in italiano non si mette."""
    if len(voci) < 2:
        return voci[0] if voci else ''
    return ", ".join(voci[:-1]) + " e " + voci[-1]


# La stessa regola dei richiami, ma per il TITLE, che e' la riga su cui si
# decide il clic. Mettere il richiamo nella descrizione non e' bastato: la
# pagina della Fiera di Agosto di Novi Ligure ha fatto 1.843 impressioni al
# 2,98% di clic contro il 17% delle pagine evento sorelle, e le query perse
# sono tutte la stessa cosa scritta in quattro modi ("fuochi novi ligure 2026",
# "fuochi d'artificio novi ligure 2026", "novi ligure fuochi d artificio
# 2026"): ~300 impressioni in posizione 6-9 con quasi zero clic. In sesta
# posizione si legge solo il title, e il title diceva "Fiera di Agosto", che
# non e' la cosa che stanno cercando.
#
# Non ci va OGNI richiamo, e la lista e' corta apposta. Un gancio sbagliato
# costa piu' di quanto renda: provata con tutti i richiami, questa regola
# scriveva "Mercatino a Cimaferle 2026" al posto di "Sagra della Fugassetta"
# (nel testo il mercatino e' una riga: "giochi, una lotteria e un mercatino di
# articoli vintage") e "Rievocazione storica ad Asti" al posto del Palio di
# Asti. Il richiamo c'era davvero in tutti e due i casi: quello che manca e'
# che sia LA cosa che si cerca.
#
# Qui stanno solo le attrazioni che sono a loro volta una query, cioe' quelle
# che si cercano SENZA sapere come si chiama la festa - nessuno cerca "sagra
# con mercatino", tutti cercano "fuochi d'artificio novi ligure". L'ordine e'
# la priorita': vince il primo.
GANCI_TITOLO = {
    "fuochi d'artificio": "Fuochi d'artificio",
    "luna park": "Luna park",
    "mongolfiere": "Mongolfiere",
}
RICHIAMO_RE = {etichetta: rx for rx, etichetta in RICHIAMI}


def gancio(nome, descr):
    """Il richiamo da promuovere nel title, o '' se non ce n'e' uno.

    Vale la regola dei richiami: se la parola non e' nella descrizione del
    foglio non esce, e se la proposizione la nega ("quest'anno senza fuochi")
    nemmeno. In piu' non esce quando il nome della festa la dice gia': su
    "Festa della Pizza Margherita" il gancio "street food" ruberebbe il posto
    al nome senza aggiungere una parola nuova."""
    presenti = set(richiami(descr, massimo=len(RICHIAMI)))
    n = (nome or '')
    for etichetta, in_titolo in GANCI_TITOLO.items():
        if etichetta in presenti and not RICHIAMO_RE[etichetta].search(n):
            return in_titolo
    return ''


def _senza_anno(nome):
    """Il nome senza l'anno e senza la coda dell'organizzatore: serve dopo il
    gancio, dove l'anno c'e' gia' e ripeterlo ("… 2026 | Fiera di Agosto
    2026") mangia dieci caratteri per dire due volte la stessa cosa."""
    corto = ORGANIZZATORE_RE.sub('', nome or '').strip(' -–—')
    corto = re.sub(r'\s*\b(?:19|20)\d{2}\b\s*', ' ', corto)
    return re.sub(r'\s{2,}', ' ', corto).strip(' -–—:·') or (nome or '')


def _titolo_evento(nome, citta, anno, gan):
    """Title della pagina evento.

    Con il gancio davanti quando c'e': "Fuochi d'artificio a Novi Ligure 2026 |
    Fiera di Agosto". Le tre cose che la query contiene (cosa, dove, anno)
    stanno tutte prima della barra, e il nome della festa resta comunque nel
    title - non si scambia una query per un'altra, si tengono tutte e due.

    Il nome NON e' sacrificabile: se il gancio non ci sta insieme al nome, il
    gancio salta e resta il title di prima. Un title che dice "Mongolfiere ad
    Alessandria 2026" e non dice piu' "Festa della Birra" ha vinto una query e
    ne ha persa una piu' grossa, che e' il modo piu' facile di peggiorare
    partendo da un'idea giusta."""
    if gan:
        titolo = f"{gan}{a_citta(citta)} {anno} | {_senza_anno(nome)}"
        if len(titolo) <= MAX_TITLE:
            return titolo
    return _titolo(nome, citta, anno)


# ---------------------------------------------------------------------------
# Impaginare la descrizione a valle del dato
# ---------------------------------------------------------------------------
# Nel foglio la Descrizione e' UNA cella, cioe' una stringa sola: al 28/08/2026
# nessuna delle 188 righe contiene un solo "\n". Quindi lo split sui capoversi
# che stava nel template della scheda - re.split(r'\n{2,}') - non trovava mai
# niente da spezzare, e la pagina stampava un blocco unico da 600-1.700
# caratteri con dentro, in fila e separata da punti e virgola, la coda
# "Programma: 18/09 Giorgio Vanni in concerto (22:00); ...".
#
# IL DATO NON SI CAMBIA. Chi compila il foglio continua a scrivere in prosa e
# non deve imparare nessuna sintassi: l'impaginazione si fa qui, e solo dove la
# struttura e' nel testo per davvero.
#
# COSA SI FA, E PERCHE' NON DI PIU'. Il grassetto sta sulla data e sull'ora del
# programma, che sono token riconosciuti da una regex. Sulla prosa NON si mette
# grassetto: sarebbe un giudizio editoriale dato da una stringa - perche'
# "6.500 posti a sedere" e non "31 Pro Loco"? - e soprattutto date, orari,
# prezzo ed eta' stanno gia' nella barra dei fatti tre centimetri sopra. E' la
# regola "l'eta' non si ripete nelle descrizioni" applicata a tutto il resto.
#
# NIENTE DI QUESTO ESCE DALLA PAGINA. meta description, og:description, il
# JSON-LD e i campi del link calendario continuano a leggere descr_txt, cioe'
# il testo piatto: un <ul> dentro una meta description non e' formattazione, e'
# markup che si vede fra i risultati di Google.
#
# Verificato riga per riga sulle 188 del 28/08/2026: il testo visibile resta
# identico parola per parola. La sola cosa che sparisce sono le date ripetute
# che il raggruppamento per giorno accorpa ("29/08 X; 29/08 Y" -> un 29/08).

# "Programma:" apre la coda solo se apre una frase. In mezzo a una ("il
# Programma: vedi sito") non e' un marcatore, e allora la coda resta prosa,
# cioe' esce come prima. Vale per tutto quello che segue: se un domani nel
# foglio si scrive "Programma - ", o le voci si separano con la virgola, il
# parser non riconosce e la descrizione esce come oggi. Degrada, non si rompe.
PROG_MARCA = re.compile(r'(?:^|(?<=[.!?])\s+)Programma:\s*', re.I)

# Una voce: data opzionale in testa, ora opzionale in coda fra parentesi.
# Misurato sulle 235 voci del 28/08/2026: 207 portano la data, le altre 28 o
# continuano il giorno di quella prima - nel foglio la data si scrive una volta
# e non si ripete - o sono di un evento di un giorno solo, che dentro il
# programma la data non ce l'ha proprio. Le due forme dell'ora sono "(21:30)" e
# "(19:00-22:00)"; "(vari)" esiste e vale come le altre.
PROG_VOCE = re.compile(
    r'^(?:(?P<data>\d{1,2}/\d{1,2})\s+)?'
    r'(?P<testo>.*?)'
    r'(?:\s*\((?P<ora>\d{1,2}[:.]\d{2}(?:\s*-\s*\d{1,2}[:.]\d{2})?|vari[ae]?)\))?$',
    re.S)

# Confine di frase: punto (o ! ?) piu' spazio piu' maiuscola. Le due occhiate
# indietro non sono cautela teorica - "6.500 posti" e "ore 18.00" hanno il
# punto fra due cifre, "n. 3" ed "es." sono abbreviazioni di una lettera sola:
# senza, la prosa si spezzerebbe dentro un numero. E il paragrafo nuovo non
# comincia per cifra: una frase che parte con un numero esiste, ma un taglio
# sbagliato costa piu' di un taglio mancato.
FRASE_FINE = re.compile(r'(?<![0-9])(?<!\b[A-Za-z])([.!?])\s+(?=[A-ZÀ-Ü«"(])')

# 230 caratteri: la descrizione mediana ne misura 263, quindi una tipica esce
# in due paragrafi da due-tre frasi. Scendendo verso i 150 si otterrebbe un
# paragrafo per frase, che non e' prosa impaginata, e' un elenco.
PARAG_LUNGH = 230
PARAG_MINIMO = 90    # sotto, un paragrafo non si lascia da solo in coda


def voci_programma(coda):
    """Le voci scritte dopo "Programma:", come (data, testo, ora).

    La data si eredita da quella prima quando manca, perche' e' cosi' che e'
    scritta nel foglio: la si ripete solo quando cambia."""
    voci, ultima = [], ''
    for pezzo in coda.strip().rstrip('.').split(';'):
        pezzo = pezzo.strip()
        if not pezzo:
            continue
        m = PROG_VOCE.match(pezzo)
        data = (m.group('data') or '').strip() or ultima
        ultima = data
        testo = (m.group('testo') or '').strip(' -–—')
        if not testo:          # "18/09;" da sola non e' una voce
            continue
        voci.append((data, testo, (m.group('ora') or '').replace('.', ':').strip()))
    return voci


def _programma_html(voci):
    """Un gruppo per giorno: la data sta in colonna e non si ripete sette
    volte. Su una patronale di quattro giorni sono venti righe in fila che
    diventano quattro blocchi leggibili."""
    if not voci:
        return ''
    gruppi, ultima = [], object()      # object(): nessuna data e' uguale a lui
    for data, testo, ora in voci:
        if data != ultima:
            gruppi.append((data, []))
            ultima = data
        gruppi[-1][1].append((testo, ora))
    blocchi = []
    for data, righe in gruppi:
        vv = ''.join(
            f'<li>{esc(t)}'
            + (f' <span class="ev-prog-o">{esc(o)}</span>' if o else '')
            + '</li>' for t, o in righe)
        etichetta = f'<p class="ev-prog-d">{esc(data)}</p>' if data else ''
        blocchi.append(f'<div class="ev-prog-g">{etichetta}'
                       f'<ul class="ev-prog-v">{vv}</ul></div>')
    # id="programma": ci punta il rimando che l'agenda stampa al posto della
    # coda (descrizione_riga). Un'ancora che non esiste scarica in cima a una
    # pagina lunga, ed e' peggio di nessun link - qui non puo' succedere,
    # perche' chi stampa il rimando e chi stampa questo titolo guardano la
    # stessa descrizione con la stessa funzione.
    return ('<h2 class="ev-prog-h" id="programma">Programma</h2>'
            f'<div class="ev-prog">{"".join(blocchi)}</div>')


def paragrafi(testo):
    """La prosa spezzata in paragrafi ai confini di frase.

    Le frasi si accumulano finche' il paragrafo non passa PARAG_LUNGH, cosi'
    una descrizione corta resta un paragrafo solo - che e' la cosa giusta per
    145 righe su 188."""
    frasi = [f.strip() for f in FRASE_FINE.sub(r'\1\n', testo.strip()).split('\n')
             if f.strip()]
    out = []
    for f in frasi:
        if out and len(out[-1]) < PARAG_LUNGH:
            out[-1] += ' ' + f
        else:
            out.append(f)
    if len(out) > 1 and len(out[-1]) < PARAG_MINIMO:
        coda = out.pop()                     # niente code orfane di mezza riga
        out[-1] += ' ' + coda
    return out


def corpo_descrizione(descr):
    """La descrizione del foglio impaginata: paragrafi, piu' il programma come
    elenco quando c'e'.

    Lo split sui capoversi resta il primo taglio: oggi nel foglio non ce ne
    sono, ma il giorno che qualcuno andra' a capo dentro la cella quella e' una
    divisione voluta da chi scrive, e vince su qualunque euristica."""
    descr = (descr or '').strip()
    if not descr:
        return ''
    blocchi = []
    for capoverso in re.split(r'\n{2,}', descr):
        if not capoverso.strip():
            continue
        pezzi = PROG_MARCA.split(capoverso, maxsplit=1)
        blocchi += [f'<p>{esc(p)}</p>' for p in paragrafi(pezzi[0])]
        if len(pezzi) > 1:
            blocchi.append(_programma_html(voci_programma(pezzi[1])))
    return ''.join(b for b in blocchi if b)


# Quante voci di programma valgono un rimando invece del testo. Sotto tre, la
# coda e' una riga o due: mandare a un'altra pagina costa piu' di quello che
# risparmia, e "1 appuntamento ->" e' un link che si prende in giro da solo.
MIN_VOCI_RIMANDO = 3


def descrizione_riga(e):
    """La descrizione dentro la riga dell'agenda: la prosa impaginata, e il
    programma sostituito da un rimando alla scheda.

    LA RIGA E LA SCHEDA FANNO DUE MESTIERI, e la cella del foglio contiene due
    cose diverse. Misurato sulle 182 righe del 30/08/2026: 55.551 caratteri di
    prosa e 15.990 di code "Programma:", queste ultime su 44 righe sole
    (mediana 282 caratteri, massimo 1.236). La prosa e' la ragione per cui uno
    ha aperto la riga; il programma e' una tabella travestita da frase, ed e'
    lui a fare il muro di testo.

    Quindi: la prosa si impagina qui come sulla scheda - stesso paragrafi(),
    zero byte in piu', sono gli stessi caratteri con dei <p> intorno - e il
    programma esce dalla riga e diventa una riga sola che porta alla scheda.
    Non e' una rinuncia: 43 volte su 44 quel contenuto e' gia' impaginato bene
    tre centimetri piu' in la', e cosi' "Scheda completa" guadagna una ragione
    per essere toccato, cioe' un clic verso le pagine che fanno il 70% del
    traffico. E' quello che le altre liste del sito gia' fanno: le pagine
    comune e le sagre-provincia-* la descrizione non la stampano affatto.

    DOVE LA SCHEDA NON C'E', IL PROGRAMMA RESTA. E' la regola di
    link_luoghi(): quello che non ha un altrove non si toglie. Al 30/08/2026 e'
    un caso solo (SaltimPiazza 2026 a Viarigi, 134 caratteri), e resta prosa e
    non elenco apposta - l'elenco vorrebbe il CSS .ev-prog* dentro lo <style>
    di eventi.html, cioe' un diff su ~260 pagine per una riga.

    QUELLO CHE SI PERDE, ed e' detto prima e non dopo: l'indice della ricerca
    dell'agenda e' il textContent della riga, quindi una parola che sta SOLO
    dentro il programma ("Fiera della Zucca di Piozzo") non si trova piu'
    cercando in eventi.html - sulla scheda si', ed e' la pagina che vince
    quella query. E il link "Aggiungi al calendario" legge .event-desc dal DOM,
    quindi perde il programma: lo tagliava gia' a 900 caratteri a meta' parola.

    Niente di questo esce dalla pagina: JSON-LD, meta description e le schede
    continuano a leggere descr, non il DOM.
    """
    descr = (e.get('descr') or '').strip()
    if not descr:
        return ''
    pezzi = PROG_MARCA.split(descr, maxsplit=1)
    blocchi = [f'<p>{esc(p)}</p>' for p in paragrafi(pezzi[0])]
    coda = pezzi[1].strip() if len(pezzi) > 1 else ''
    voci = voci_programma(coda) if coda else []
    if voci:
        url = f'/eventi/{slug_evento(e)}.html#programma' if ha_pagina(e) else ''
        if url and len(voci) >= MIN_VOCI_RIMANDO:
            # Il numero e non l'etichetta: "12 appuntamenti in 5 giorni" e' una
            # ragione per toccare, "vedi il programma" no. Lezione di
            # link_luoghi().
            gg = len({d for d, _, _ in voci if d})
            quando = f' in {gg} giorni' if gg > 1 else ''
            blocchi.append(f'<p class="ev-prog-rim"><a href="{url}">'
                           f'Il programma completo: {len(voci)} appuntamenti'
                           f'{quando} &rarr;</a></p>')
        else:
            blocchi.append(f'<p>{esc("Programma: " + coda)}</p>')
    # Il ritorno a capo fra i paragrafi non e' formattazione: il link del
    # calendario legge textContent, e senza quel nodo di spazio l'ultima parola
    # di un paragrafo si incollerebbe alla prima del successivo.
    return '\n'.join(blocchi)


def carica_registro():
    if not os.path.exists(REGISTRO_PATH):
        return {}
    try:
        with open(REGISTRO_PATH, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        print(f"[genera_eventi] registro pagine illeggibile ({err}), riparto da vuoto")
        return {}


def completezza(e):
    """Quanto e' completa una riga del foglio. Serve a scegliere fra due righe
    che finiscono sullo stesso slug: capita che lo stesso evento sia inserito
    due volte con dati diversi (Acqui Wine Days: 784 caratteri e fine 09/08 in
    una riga, 991 caratteri e fine 10/08 nell'altra). Prima vinceva l'ultima
    letta, cioe' il caso; ora vince la piu' ricca."""
    return (len((e.get('descr') or '').strip()),
            (e['d_end'] - e['d_start']).days,
            sum(1 for k in ('ora', 'luogo', 'indirizzo', 'loc', 'prezzo', 'eta')
                if (e.get(k) or '').strip()))


def _rif(e):
    """"riga 118", il riferimento da dare a chi deve correggere il foglio.

    Il numero e' quello della colonnina grigia di Google Sheets. Vale finche'
    l'export non e' filtrato: con un filtro attivo le righe nascoste non
    arrivano e la numerazione slitta - lo stesso guaio che controlla_crollo()
    intercetta sui conteggi. Da li' il "riga ?" quando il numero non c'e',
    che capita solo quando si sta girando sull'istantanea locale."""
    n = e.get('riga') or 0
    return f"riga {n:>4}" if n else "riga    ?"


def _ora_inizio(ora):
    """L'ora d'inizio normalizzata, o '' se la riga non ne dichiara una.

    Serve a far combaciare "14:00" e "14:00-18:30", che sono lo stesso inizio
    scritto da due locandine diverse. Lo zero davanti si toglie perche' "9:45"
    e "09:45" arrivano tutti e due dal foglio."""
    m = re.search(r'(\d{1,2})[:.](\d{2})', ora or '')
    return f"{int(m.group(1))}:{m.group(2)}" if m else ''


def segnala_sovrapposizioni(events):
    """Elenca gli eventi che stanno nello stesso posto alla stessa ora.

    PERCHE' ESISTE (10/08/2026). segnala_doppioni() confronta slug e data, cioe'
    riconosce la stessa riga copiata due volte. Ma il doppione che capita
    davvero e' un altro: lo stesso evento raccontato da DUE LOCANDINE diverse -
    il programma generale della Pro Loco e il volantino del singolo
    appuntamento - e quindi entrato nel foglio con due nomi diversi. Per lo
    slug sono due eventi, per un genitore che guarda l'agenda sono due righe
    identiche una sotto l'altra.

    Esempio del giorno in cui e' nato questo controllo, a Crissolo il 16/08
    alle 10:00: "Giochi di Basket - Pro Loco Crissolo" all'Area Pattinaggio e
    "Giochiamo a Basket con Edo - KaM 3841" alla Pista di pattinaggio Il Cervo
    di Ghiaccio. Stesso posto, chiamato in due modi.

    Il criterio e' citta + giorno + ora d'inizio. Non e' una prova: due cose
    diverse possono cominciare alle 21 nello stesso paese durante una festa
    patronale, ed e' giusto che ci siano tutte e due. Quindi anche questo
    SEGNALA e non filtra - e stampa il luogo di ognuna, perche' e' guardando
    quello che si capisce in un secondo se sono la stessa cosa.

    Le righe senza un'ora numerica ("vari", vuoto) restano fuori: senza ora il
    criterio diventa citta + giorno, e in una sagra di paese segnalerebbe
    mezzo programma."""
    # Il comune si confronta NORMALIZZATO, non com'e' scritto: maiuscole,
    # accenti e spazi doppi non fanno due paesi diversi, ma per una stringa
    # grezza si'. Non basta pero' a coprire il caso del 30/08 - vedi
    # segnala_comuni_simili() - perche' "Ceresole Alba" e "Ceresole d'Alba"
    # restano diversi anche normalizzati: li' manca una lettera, non un accento.
    g = collections.defaultdict(list)
    for e in events:
        ora = _ora_inizio(e.get('ora'))
        if ora:
            g[(_key(e.get('citta')), e['d_start'], ora)].append(e)
    coll = {k: v for k, v in g.items() if len(v) > 1}
    if not coll:
        return
    quante = sum(len(v) for v in coll.values())
    print(f"[genera_eventi] ATTENZIONE: {quante} eventi in {len(coll)} sovrapposizioni "
          f"(stessa citta, stesso giorno, stessa ora). Spesso e' lo stesso evento preso "
          f"da due locandine: si uniscono a mano nel foglio, guardando il luogo.")
    for (_c, d, ora), v in sorted(coll.items(), key=lambda kv: (kv[0][1], kv[0][2])):
        citta = (v[0].get('citta') or '').strip()
        print(f"    {d.strftime('%d/%m')} ore {ora} — {citta}:")
        for e in sorted(v, key=lambda e: e.get('riga') or 0):
            print(f"        {_rif(e)}  {(e.get('nome') or '')[:56]}")
            print(f"                 luogo: {(e.get('luogo') or '(vuoto)')[:52]}")


MAX_GIORNI_PLAUSIBILI = 30


def segnala_durate_assurde(events):
    """Elenca gli eventi che durano troppo per essere veri.

    PERCHE' ESISTE (10/08/2026). "Cortemilia Comics & Games 2026" stava sul
    foglio con 01/01/2026 - 31/12/2026: un anno intero. In agenda risultava
    quindi "in corso" TUTTI I GIORNI, in cima a tutto, per dodici mesi - mentre
    la festa vera e' a fine agosto. Se ne e' accorto il partner di Cuneo
    guardando il riquadro sul suo sito, non noi: dall'interno una riga sempre
    presente si legge come una costante del sito e smette di dare nell'occhio.

    Un evento non si puo' pero' bocciare solo perche' e' lungo: una mostra al
    museo che dura due mesi e' legittima e va in agenda tutti quei giorni.
    Quindi qui si SEGNALA e basta, non si filtra: chi guarda decide se e' una
    mostra o una data messa a caso. La soglia e' larga apposta - sopra i trenta
    giorni sono pochissime righe, e vanno guardate a una a una."""
    lunghi = []
    for e in events:
        giorni = (e['d_end'] - e['d_start']).days
        if giorni > MAX_GIORNI_PLAUSIBILI:
            lunghi.append((giorni, e))
    if not lunghi:
        return
    lunghi.sort(key=lambda t: -t[0])
    print(f"[genera_eventi] ATTENZIONE: {len(lunghi)} eventi durano piu' di "
          f"{MAX_GIORNI_PLAUSIBILI} giorni. Se non sono mostre, la data e' sbagliata "
          f"e restano 'in corso' in cima all'agenda finche' non si corregge il foglio:")
    for giorni, e in lunghi:
        print(f"    {_rif(e)}  {giorni:4d} giorni  {e['prov']}  "
              f"{e.get('di')} -> {e.get('df')}  {(e.get('nome') or '')[:46]}")


def _mese_intero(e):
    """La riga copre un mese di calendario esatto: dal primo all'ultimo giorno."""
    d0, d1 = e['d_start'], e['d_end']
    return (d0.day == 1 and d0.month == d1.month and d0.year == d1.year
            and (d1 + datetime.timedelta(days=1)).day == 1)


DATA_IGNOTA = re.compile(r'\bda\s+(definire|destinarsi|confermare|stabilire)\b'
                         r'|\bdata\s+(esatta|precisa)\b', re.I)


def segnala_date_ignote(events):
    """Elenca le righe che dicono "non so quando" scrivendo "tutto il mese".

    PERCHE' ESISTE (28/08/2026). "Festa dello Sport - Evento Finale Plogging
    Smiling Biking" stava sul foglio con 01/09/2026 - 30/09/2026 e la
    descrizione diceva, per esteso, "Data esatta di settembre 2026 da
    definire". Il generatore pero' non ha modo di distinguere *non so quando*
    da *dura trenta giorni*: nel foglio si scrivono uguale. Quindi la scheda
    stampava l'unico dato che aveva ("Dal 1 al 30 settembre 2026") e nel
    calendario copre() la faceva comparire su TUTTI E TRENTA i giorni di
    settembre - qualunque giorno si toccasse, quella riga rispondeva presente
    senza mai dire il suo. E' il guasto di segnala_durate_assurde() in
    piccolo, e quella guardia non lo prende: la sua soglia e' > 30 giorni e un
    mese ne misura 29 o 30.

    LA FIRMA NON E' LA DURATA, E' L'INTERVALLO TONDO. Una mostra vera dura
    quanto le pare ma comincia il 12 marzo e finisce il 4 giugno; una data
    ignota diventa il primo-l'ultimo del mese, perche' e' l'unica cosa che chi
    compila puo' scrivere quando non sa. Da qui il controllo.

    I falsi positivi esistono e vanno bene: "Musei Aperti ad Agosto 2026" e'
    davvero 01/08 - 31/08. Per questo si SEGNALA e basta, come per i doppioni
    e le coordinate mancanti - la riga con la descrizione che ammette di non
    sapere la data porta un <<< e si legge per prima. Si corregge nel foglio:
    la data vera, o un intervallo stretto, o la riga si toglie finche' non si
    sa. Cosi' com'e' occupa trenta caselle di calendario per rispondere boh."""
    tondi = [e for e in events if _mese_intero(e)]
    if not tondi:
        return
    sospetti = sum(1 for e in tondi if DATA_IGNOTA.search(e.get('descr') or ''))
    print(f"[genera_eventi] ATTENZIONE: {len(tondi)} eventi coprono un mese di "
          f"calendario esatto (dal primo all'ultimo giorno), {sospetti} con la data "
          f"dichiarata incerta nella descrizione. Se non sono mostre o musei aperti, "
          f"e' una data che non si sapeva: la riga risponde a tutti i giorni del mese "
          f"e non dice il suo. Si corregge nel foglio:")
    for e in sorted(tondi, key=lambda e: e['d_start']):
        spia = '  <<< la descrizione dice che la data non si sa' \
            if DATA_IGNOTA.search(e.get('descr') or '') else ''
        print(f"    {_rif(e)}  {e.get('di')} -> {e.get('df')}  {e['prov']}  "
              f"{(e.get('citta') or '?')[:16]:16} {(e.get('nome') or '')[:44]}{spia}")


# Il criterio dello slug esatto riconosce la riga COPIATA, non la riga RILETTA:
# il nome nel foglio lo scrive il downloader facendo leggere la locandina a un
# modello, e lo stesso volantino letto due volte esce con due frasi diverse.
# Nel registro del 30/08/2026 ce ne sono cinque coppie, stesso comune e stesso
# identico giorno: "Apertura Stand Gastronomico CON Shary Band" e "... E Shary
# Band" (Rocchetta Tanaro, tre serate, sei pagine per tre eventi), "Casalnoceto
# Kids" con e senza "- Comune di Casalnoceto", "Ciao Ciao Estate! Sorprese per
# Tutti" e "Laboratorio: Ciao Ciao Estate... Sorprese per Tutti!". Sono doppioni
# a tutti gli effetti e segnala_doppioni() non li vedeva, perche' guarda una
# stringa che il modello non ha nessun motivo di ripetere uguale.
#
# Il confronto e' lo stesso del riaggancio (_chiave_nome + soglia), ma qui la
# finestra e' zero giorni: stesso comune e STESSA data di inizio. Con una
# finestra larga prenderebbe le serate diverse della stessa sagra, che doppioni
# non sono.
#
# Si SEGNALA e basta, come per i doppioni esatti e le durate assurde: unire due
# righe e' una decisione editoriale, e si prende nel foglio.
def _doppioni_riscritti(events, gia_visti):
    """Elenca le righe che sono lo stesso evento scritto con parole diverse."""
    per_giorno = collections.defaultdict(list)
    for e in events:
        citta = (e.get('citta') or '').strip().lower()
        if citta:
            per_giorno[(citta, e['d_start'])].append(e)
    coppie = []
    for (citta, giorno), gruppo in per_giorno.items():
        for i, a in enumerate(gruppo):
            for b in gruppo[i + 1:]:
                sa, sb = slug_evento(a), slug_evento(b)
                if sa == sb:
                    continue  # lo prende gia' il criterio esatto
                ka, kb = _chiave_nome(a.get('nome')), _chiave_nome(b.get('nome'))
                unione = ka | kb
                if unione and len(ka & kb) / len(unione) >= SOGLIA_RIAGGANCIO:
                    coppie.append((giorno, a, b))
    if not coppie:
        return
    print(f"[genera_eventi] ATTENZIONE: {len(coppie)} coppie di righe sono lo "
          f"stesso evento scritto in due modi (due pagine per un appuntamento "
          f"solo, si uniscono a mano nel foglio):")
    for giorno, a, b in sorted(coppie, key=lambda c: c[0]):
        print(f"    {giorno.strftime('%d/%m')} {(a.get('citta') or '')[:18]:18} "
              f"{_rif(a)} \"{(a.get('nome') or '')[:40]}\"")
        print(f"                              {_rif(b)} \"{(b.get('nome') or '')[:40]}\"")
# Quanto devono somigliarsi due nomi di comune per sospettare che siano lo
# stesso posto scritto in due modi. Tarato sui 204 comuni visti finora: a 0.92
# escono SOLO i due casi veri (Ceresole Alba / Ceresole d'Alba, 0.96, ed
# Entracque / Entraque, 0.94); il primo falso allarme - Ozzano Monferrato
# contro Ponzano Monferrato, due paesi diversi e distanti - sta a 0.909. Il
# margine e' stretto: se un giorno la soglia si abbassa, questo controllo
# diventa rumore e smette di essere letto.
SOMIGLIANZA_COMUNI = 0.92


def segnala_comuni_simili(events):
    """Elenca i comuni scritti in DUE modi diversi dentro lo stesso foglio.

    PERCHE' ESISTE (30/08/2026). Nel foglio c'erano insieme "Ceresole Alba" e
    "Ceresole d'Alba": lo stesso paese, due grafie. Sembra una sciocchezza da
    correttore di bozze, e invece:

      - lo slug della pagina evento contiene il comune, quindi le due grafie
        producono DUE pagine per lo stesso posto (e il giorno che la si
        corregge, una delle due resta un cartello - vedi render_spostata);
      - la pagina comune si spacca in due, e nessuna delle due arriva alle
        soglie che le darebbero il diritto di esistere;
      - soprattutto, ACCECA segnala_sovrapposizioni(), che raggruppa per
        comune: quel giorno le due grafie hanno nascosto un doppione vero (la
        "Consegna dei Libri" del 06/09 alle 11:00, entrata due volte da due
        locandine) proprio al controllo nato per trovarlo.

    Il confronto e' fra le grafie PRESENTI NEL FOGLIO, non contro un elenco di
    comuni veri: qui non si vuole sapere se un paese esiste - lo sa gia' la
    geocodifica - ma se stiamo chiamando la stessa cosa in due modi. Ed e' per
    questo che si segnala solo quando ci sono tutte e due: una grafia sola,
    anche sbagliata, e' coerente e non spacca niente."""
    per_comune = collections.defaultdict(list)
    for e in events:
        citta = (e.get('citta') or '').strip()
        if citta:
            per_comune[citta].append(e)
    sospetti = []
    for a, b in itertools.combinations(sorted(per_comune), 2):
        ka, kb = _key(a), _key(b)
        if not ka or not kb:
            continue
        somiglianza = difflib.SequenceMatcher(None, ka, kb).ratio()
        if somiglianza >= SOMIGLIANZA_COMUNI:
            sospetti.append((somiglianza, a, b))
    if not sospetti:
        return
    quante = (f"{len(sospetti)} comuni scritti in due modi" if len(sospetti) > 1
              else "un comune scritto in due modi")
    print(f"[genera_eventi] ATTENZIONE: {quante} nel foglio. Se sono lo stesso paese "
          f"vanno unificati a mano, se no il sito ne fa due (pagine, hub e "
          f"controlli separati):")
    for somiglianza, a, b in sorted(sospetti, reverse=True):
        print(f"    {a!r} contro {b!r}  (si somigliano al {somiglianza:.0%})")
        for nome in (a, b):
            righe = per_comune[nome]
            prov = (righe[0].get('prov') or '').upper()
            dove = ", ".join(_rif(x) for x in righe[:6])
            if len(righe) > 6:
                dove += f", e altre {len(righe) - 6}"
            print(f"        {nome} ({prov}): {len(righe)} righe — {dove}")


def segnala_doppioni(events):
    """Elenca gli eventi inseriti piu' volte nel foglio.

    Criterio: stesso evento (slug, che ignora anno e numero di edizione, cosi'
    "3^ Cena Sotto le Stelle" e "3ª Cena sotto le Stelle" si riconoscono) e
    stessa data di inizio. La data di inizio e' quello che distingue un
    doppione da una ricorrenza: "I giovedi' in biblioteca" compare quattro
    volte ma con quattro date, ed e' corretto cosi'.

    Vale su tutti gli eventi, non solo su quelli con pagina dedicata: il
    doppione si vede nell'agenda a prescindere. Si pulisce solo a mano nel
    foglio, quindi va ricordato a ogni run."""
    g = collections.defaultdict(list)
    for e in events:
        g[(slug_evento(e), e['d_start'])].append(e)
    doppi = {k: v for k, v in g.items() if len(v) > 1}
    _doppioni_riscritti(events, doppi)
    if not doppi:
        return
    print(f"[genera_eventi] ATTENZIONE: {len(doppi)} eventi ripetuti nel foglio "
          f"(nell'agenda compaiono doppi, vanno uniti a mano):")
    for (s, d), v in sorted(doppi.items(), key=lambda kv: kv[0][1]):
        print(f"    {len(v)}x  {v[0]['nome'][:44]} — {v[0]['citta']} — dal {d.strftime('%d/%m')}")
        for x in v:
            print(f"          {_rif(x)}  fine {x['df']}  "
                  f"{x['categoria'] or '(senza categoria)':16} "
                  f"{len(x['descr'])} caratteri")


def segnala_senza_coordinate(events):
    """Elenca le righe del foglio senza lat/lon, cioe' invisibili a "vicino a me".

    PERCHE' ESISTE (26/08/2026). Le due colonne si compilano a mano, e una
    riga che le lascia vuote non e' "lontana", e' sconosciuta: con un raggio
    attivo resta fuori, sempre, anche se la festa e' a due chilometri. Non e'
    un difetto del codice - geo_attrs() stampa quello che trova - quindi qui si
    SEGNALA e basta, come per i doppioni e le durate assurde: si corregge nel
    foglio, e va ricordato a ogni run finche' non lo si fa.

    Il conto si stampa sempre, anche a zero mancanti: e' il numero che dice se
    il filtro copre l'agenda o meta' di essa, ed e' l'unico posto in cui si
    legge senza aprire GA4."""
    senza = [e for e in events if not coord(e)]
    tot = len(events)
    if not senza:
        print(f"[genera_eventi] coordinate: {tot}/{tot} righe georiferite")
        return
    print(f"[genera_eventi] ATTENZIONE: {len(senza)} righe su {tot} senza coordinate "
          f"(Lat/Lng vuote o illeggibili). Restano fuori da \"vicino a me\" a "
          f"qualunque raggio: si riempiono a mano nel foglio.")
    for e in sorted(senza, key=lambda e: e['d_start']):
        print(f"    {_rif(e)}  {e['d_start'].strftime('%d/%m')}  "
              f"{(e.get('citta') or '?')[:18]:18} {(e.get('nome') or '')[:44]}")
        print(f"                 luogo: {(e.get('luogo') or '(vuoto)')[:52]}")


# ---------------------------------------------------------------------------
# RIAGGANCIO DELL'EDIZIONE SUCCESSIVA
#
# Lo slug e' evergreen apposta (slug_evento toglie l'anno e il numero di
# edizione), cosi' la sagra del 2027 aggiorna la pagina del 2026 invece di
# fondarne una che riparte da zero. Ma quello slug si ricava dal NOME, e il nome
# lo riscrive ogni anno chi compila il foglio: basta che la coda
# "- Pro Loco Grondona" ci sia un anno e manchi l'altro e l'indirizzo cambia.
# Misurato sul registro del 30/08/2026: 107 nomi su 412 portano quella coda, e
# fra le 40 schede piu' visitate sono 5 - ma dentro ci sono la prima del sito
# (Grondona, 490 clic) e la quarta per impressioni nelle AI features (Belforte,
# 265). Cioe' il difetto non e' raro dove costa.
#
# Quindi il nome non deve tornare IDENTICO: deve tornare RICONOSCIBILE. Un
# evento il cui slug e' nuovo si confronta con le pagine gia' in registro, e se
# ne trova una sola che e' evidentemente la stessa cosa - stesso comune, stesso
# periodo dell'anno, stesse parole - riusa quello slug.
#
# Le tre condizioni non sono intercambiabili, e la piu' importante e' la terza:
#   1. STESSO COMUNE. Sempre: il comune sta gia' dentro lo slug.
#   2. STESSO PERIODO. +/- 30 giorni, circolari (una patronale segue il santo,
#      una sagra il raccolto: si sposta di un weekend, non di una stagione).
#   3. UN SOLO CANDIDATO. Se sono due non si sceglie, ed e' la regola gia'
#      scritta per _erede(): sbagliare aggancio vuol dire scrivere l'edizione di
#      un evento sopra la pagina di un altro, che e' molto peggio di una URL
#      nuova. E il caso ambiguo esiste davvero: a Rocchetta Tanaro cinque
#      "Apertura Stand Gastronomico con <nome della band>" hanno le stesse
#      parole e le stesse date, e nessuna delle cinque va agganciata a caso.
#
# Uno slug gia' preso da un altro evento di QUESTA run non e' un candidato: e'
# la guardia che tiene fuori i sotto-eventi della stessa manifestazione, che
# sono in pagina tutti insieme e non hanno bisogno di nessun riaggancio.
#
# Misurato sul registro vero simulando i nomi del 2027 (numero di edizione
# aumentato e coda dell'organizzatore caduta): su 412 schede, 319 tengono lo
# slug da sole, 84 vengono riagganciate, 9 restano ambigue e ripiegano su una
# URL nuova - cioe' su quello che succederebbe comunque oggi - e gli agganci
# SBAGLIATI sono ZERO. Riscrivendo il nome piu' pesantemente (una parola
# significativa in meno) se ne perdono 171: e' il limite dichiarato, e il modo
# di non arrivarci e' scrivere i nomi nel foglio come l'anno prima.
# ---------------------------------------------------------------------------
SOGLIA_RIAGGANCIO = 0.8   # Jaccard sulle parole che restano
FINESTRA_RIAGGANCIO = 30  # giorni, circolari

# Parole che non distinguono un evento da un altro. Restano dentro "sagra",
# "festa" e "patronale": a parita' di comune e periodo sono proprio quelle a
# separare la sagra dalla festa.
STOP_RIAGGANCIO = {
    'di', 'della', 'del', 'delle', 'dei', 'degli', 'la', 'il', 'lo', 'le', 'i',
    'gli', 'a', 'al', 'alla', 'ai', 'e', 'ed', 'in', 'con', 'per', 'su', 'da',
    'dal', 'un', 'una', 'edizione',
}


def _chiave_nome(nome):
    """Le parole del nome che NON cambiano fra un'edizione e l'altra."""
    n = ORGANIZZATORE_RE.sub(' ', nome or '')
    n = re.sub(r'\b(?:19|20)\d{2}\b', ' ', n)
    n = re.sub(r'(?<!\w)\d+\s*[°ºª^]', ' ', n)
    n = ROMANO_INIZIALE_RE.sub('', n, count=1)
    n = unicodedata.normalize('NFKD', n).encode('ascii', 'ignore').decode().lower()
    return {p for p in re.split(r'[^a-z0-9]+', n) if p and p not in STOP_RIAGGANCIO}


def _giorno_dell_anno(d):
    """1-366 da una data, da 'AAAA-MM-GG' o da 'GG/MM/AAAA'. None se non si legge."""
    if isinstance(d, datetime.datetime):
        d = d.date()
    if isinstance(d, datetime.date):
        return d.timetuple().tm_yday
    for f in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(str(d).strip(), f).date().timetuple().tm_yday
        except (ValueError, TypeError):
            pass
    return None


def _stesso_periodo(g1, g2, giorni=FINESTRA_RIAGGANCIO):
    """Due giorni dell'anno abbastanza vicini. Circolare: il 28 dicembre e il 3
    gennaio distano sei giorni, non trecentocinquantanove."""
    if g1 is None or g2 is None:
        return False
    d = abs(g1 - g2)
    return min(d, 365 - d) <= giorni


def candidati_edizione(e, reg, presi):
    """Gli slug in registro che sono, verosimilmente, l'edizione precedente di
    questo evento. Zero, uno o piu' di uno: la scelta la fa chi chiama."""
    citta = (e.get('citta') or '').strip().lower()
    if not citta:
        return []
    chiave = _chiave_nome(e.get('nome'))
    if not chiave:
        return []
    giorno = _giorno_dell_anno(e.get('d_start') or e.get('di'))
    fuori = []
    for slug, rec in reg.items():
        if slug in presi or not isinstance(rec, dict) or not rec.get('nome'):
            continue
        # Una pagina ritirata o gia' spostata altrove non e' una pagina da
        # aggiornare: la prima si dichiara inattendibile, la seconda e' un
        # cartello che rimanda a un'altra.
        if rec.get('ritirata') or rec.get('spostata'):
            continue
        if (rec.get('citta') or '').strip().lower() != citta:
            continue
        if not _stesso_periodo(giorno, _giorno_dell_anno(rec.get('d_start') or rec.get('di'))):
            continue
        altra = _chiave_nome(rec.get('nome'))
        unione = chiave | altra
        if unione and len(chiave & altra) / len(unione) >= SOGLIA_RIAGGANCIO:
            fuori.append(slug)
    return fuori


def aggiorna_registro(events):
    """Fonde gli eventi correnti nel registro persistente. Non rimuove nulla."""
    reg = carica_registro()
    oggi = datetime.date.today().isoformat()
    nuovi = 0
    # Un solo evento per slug, il piu' completo, prima di toccare il registro.
    migliori = {}
    for e in events:
        if not ha_pagina(e):
            continue
        s = slug_evento(e)
        if s not in migliori or completezza(e) > completezza(migliori[s]):
            migliori[s] = e
    # Uno slug NUOVO puo' essere l'edizione nuova di una pagina che c'e' gia',
    # con il nome scritto un po' diversamente. Si guarda solo qui: se lo slug e'
    # gia' in registro non c'e' niente da riagganciare, ed e' il caso di tre
    # schede su quattro.
    presi = set(migliori)
    riagganci, ambigui = [], []
    for s in sorted(migliori):
        if s in reg:
            continue
        cand = candidati_edizione(migliori[s], reg, presi)
        if len(cand) == 1:
            vecchio = cand[0]
            riagganci.append((s, vecchio, migliori[s].get('nome') or '',
                              reg[vecchio].get('nome') or ''))
            migliori[vecchio] = migliori.pop(s)
            presi.discard(s)
            presi.add(vecchio)
        elif cand:
            ambigui.append((s, cand))
    for s, vecchio, nome_nuovo, nome_vecchio in riagganci:
        print(f"[genera_eventi] riaggancio: \"{nome_nuovo[:44]}\" scrive su "
              f"/eventi/{vecchio}.html (invece di aprire /eventi/{s}.html)")
        print(f"                 l'edizione in registro si chiamava \"{nome_vecchio[:44]}\"")
    for s, cand in ambigui:
        # Non e' un errore: e' la prudenza che funziona, e si stampa perche' un
        # nome scritto meglio nel foglio la toglierebbe di mezzo.
        print(f"[genera_eventi] pagina nuova /eventi/{s}.html: assomiglia a "
              f"{len(cand)} pagine gia' in registro, quindi non si indovina "
              f"({', '.join(cand[:3])})")
    for s, e in migliori.items():
        rec = reg.get(s)
        if rec is None:
            rec, nuovi = {'first_seen': oggi}, nuovi + 1
        rec.update({k: (v.isoformat() if isinstance(v, datetime.date) else v)
                    for k, v in e.items()})
        # Le colonne editoriali vuote non si salvano: otto stringhe vuote per
        # scheda gonfiano il registro e il diff di ogni notte. Vanno tolte, non
        # solo saltate, se no una cella svuotata nel foglio resterebbe qui per
        # sempre.
        for k in dict(CAMPI_DAOP, **CAMPI_EXTRA):
            if not (rec.get(k) or '').strip():
                rec.pop(k, None)
        rec['slug'] = s
        rec['last_seen'] = oggi
        reg[s] = rec
    # Il registro viene scritto da scrivi_pagine(), dopo aver stabilito quali
    # pagine sono davvero cambiate: serve per registrare la data di modifica.
    # Restituiamo anche gli slug visti in QUESTA run: confrontare last_seen con
    # la data odierna non basta, perche' due run nello stesso giorno non si
    # distinguerebbero.
    return reg, nuovi, set(migliori)


def _guscio():
    """CSS, nav e footer presi da eventi.html a ogni run, con i link resi
    root-relative perche' le pagine evento stanno in /eventi/. Estrarli invece
    di duplicarli tiene le sottopagine allineate quando il sito cambia.

    Il CSS va copiato per intero: daop-system.min.css contiene solo i token
    tipografici, mentre le regole di layout (nav, footer, bottoni, griglie)
    stanno in blocchi <style> inline dentro ogni pagina. Linkare solo il file
    lasciava le pagine evento senza stile."""
    s = open(HTML_PATH, encoding="utf-8").read()
    nav = re.search(r'<!-- NAV -->.*?</div>\s*(?=\n<!--|\n<main)', s, re.S)
    foot = re.search(r'<footer>.*?</footer>', s, re.S)
    css = re.findall(r'<style[^>]*>(.*?)</style>', s, re.S)
    if not nav or not foot:
        raise SystemExit("[genera_eventi] nav o footer non trovati in eventi.html")
    if not css:
        raise SystemExit("[genera_eventi] nessun blocco <style> trovato in eventi.html")

    def rooted(html_frag):
        html_frag = re.sub(r'(href|src)="(?!https?://|/|#|mailto:|tel:)',
                           lambda m: f'{m.group(1)}="/', html_frag)
        # I marker della voce stagionale servono solo dove la nav e' scritta a
        # mano: qui la voce e' gia' risolta, e portarseli dietro vorrebbe dire
        # tre commenti in piu' su ~360 pagine per niente.
        # Il pattern e' volutamente LARGO — qualunque marker, non un elenco di
        # nomi. L'elenco e' gia' costato due volte lo stesso difetto: nato coi
        # marker dei centri, ripetuto identico il 21/08/2026 con quelli dei
        # corsi, perche' aggiungere un marker qui non e' un passaggio che
        # qualcuno ricorda. Dentro nav e footer un marker e' per definizione una
        # voce che aggiorna_nav() risolve nelle pagine a mano: nelle generate
        # e' gia' risolta, quindi non ne deve sopravvivere nessuno — compreso
        # quello che nascera' domani.
        html_frag = re.sub(
            r'<!-- [A-Z][A-Z0-9-]*:(?:START|END) -->', '',
            html_frag)
        return html_frag.replace('class="active"', '')

    # Anche le url() del CSS vanno messe alla radice. In eventi.html la texture
    # della .page-hero e' url('assets/images/...') senza slash: da /eventi/ e da
    # /eventi/comune/ diventa /eventi/assets/... e risponde 404. Finche' nessuna
    # pagina generata usava la barra il difetto restava invisibile.
    css_txt = re.sub(r"url\((['\"]?)(?!https?://|/|data:)",
                     lambda m: f"url({m.group(1)}/", "\n".join(css))
    return css_txt, rooted(nav.group(0)), rooted(foot.group(0))


# Il componente Ginetto, tenuto FUORI da PAGINA_CSS perche' dal 04/09/2026
# serve anche a pagine che PAGINA_CSS non ce l'hanno: corsi.html, le pagine
# realta' in corsi/, i tre hub dei centri. Quelle importano solo questo.
#
# Le regole di .info-strip NON stanno qui: arrivano dal <style> di eventi.html
# che _guscio() copia in ogni pagina generata. Ricopiarle sarebbe una seconda
# definizione dello stesso componente, cioe' due card che divergono alla prima
# modifica - la ragione per cui la nav si rilegge invece di essere copiata.
GINETTO_CSS = """
/* Striscia Ginetto: stesso componente .info-strip della home eventi (card
   crema, titolo Playfair, link arancio), con la mascotte al posto dell'icona.
   Sta in fondo, dopo "altri eventi vicino a": e' il punto in cui chi legge non
   ha trovato quello che cercava. */
.ev-ginetto{padding:56px 24px}
.ev-ginetto .info-strip{margin-bottom:0;align-items:center}
/* 96px e non 64: a 64 la mascotte si leggeva come l'icona di un avviso, cioe'
   la cosa che l'occhio salta. Dal 04/09/2026 Ginetto e' l'unica richiesta del
   sito - non divide piu' l'attenzione con l'invito al canale - e puo'
   prendersi lo spazio. Il file nativo e' 500x500, quindi non si sgrana.
   Sul telefono la .info-strip va in colonna e la faccia finisce da sola su
   una riga sua: li' 64px erano persi in mezzo al bianco. */
.ginetto-faccia{width:96px;height:96px;flex-shrink:0;object-fit:contain}
@media(max-width:600px){.ginetto-faccia{width:104px;height:104px}}
@media(max-width:600px){.ev-ginetto{padding:40px 20px}}
/* Lo stesso componente dentro l'articolo invece che in una fascia di pagina:
   in cima a un'edizione conclusa, e - dal 04/09/2026 - nel posto che era
   dell'invito al canale sulle pagine comune e sulle landing. */
.ev-ginetto-alto{margin:34px 0 26px}
/* In cima a una conclusa il margine sopra e' zero: l'avviso "Edizione
   conclusa" ha gia' i suoi 22px sotto, e sommandoli l'aria raddoppia. */
.ev-over + .ev-ginetto-alto{margin-top:0}
.ev-ginetto-alto .info-strip{margin-bottom:0;align-items:center;padding:18px 20px}
"""


PAGINA_CSS = """
/* La nav del sito e' position:fixed: senza spazio in cima gli finisce sotto
   il breadcrumb e mezzo H1. Stessi valori con cui .page-hero la compensa
   nelle altre pagine (148px, 120px sotto i 600px). */
.ev-wrap{max-width:820px;margin:0 auto;padding:148px 20px 40px}
@media(max-width:600px){.ev-wrap{padding:120px 18px 32px}}
/* La barra scura in cima e' la .page-hero delle altre pagine del sito: il CSS
   arriva gia' copiato da eventi.html, qui c'e' solo la variante allineata a
   sinistra e con il titolo piu' contenuto, perche' i nomi degli eventi sono
   lunghi ("Apertura stand gastronomico con i Controcorrente") e a 3.6rem
   riempivano tre righe. Senza barra queste erano le uniche pagine del sito a
   partire dal bianco. */
.ev-hero{padding:148px 24px 56px;text-align:left}
.ev-hero .page-hero-inner{max-width:820px}
.ev-hero .ev-crumb{color:rgba(255,255,255,.62);opacity:1;margin:0 0 12px}
.ev-hero .ev-crumb a{color:rgba(255,255,255,.82)}
.ev-hero h1{font-family:'Playfair Display',serif;font-size:clamp(2rem,4vw,2.9rem);
  font-weight:800;color:#fff;line-height:1.12;margin:0 0 12px;letter-spacing:-.02em}
.ev-hero .ev-when{font-size:1.08rem;font-weight:600;color:var(--gold,#c9a227);margin:0}
.ev-hero .ev-scelto{background:rgba(255,255,255,.14);color:#f6d9b4;margin:0 0 12px}
@media(max-width:600px){.ev-hero{padding:120px 20px 44px}}
/* Con la barra sopra, il corpo non deve piu' compensare la nav fissa. */
.ev-wrap--hero{padding-top:44px}
@media(max-width:600px){.ev-wrap--hero{padding-top:32px}}
/* Il breadcrumb e' un <div role="navigation">, non un <nav>: il CSS del sito
   ha nav{position:fixed;top:0} come selettore di elemento, che rendeva fisso
   anche il breadcrumb piazzandolo sopra la barra. position:static come
   ulteriore difesa se un giorno la regola si allargasse. */
.ev-crumb{position:static;font-size:.85rem;opacity:.7;margin:0 0 10px}
.ev-crumb a{color:inherit}
.ev-scelto{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:700;
  letter-spacing:.02em;text-transform:uppercase;color:#a75b15;background:rgba(232,149,74,.16);
  border-radius:100px;padding:5px 12px;margin:0 0 8px}
/* .ev-when vive nella barra scura: il colore vero e' in .ev-hero .ev-when,
   qui resta la misura come ripiego se un giorno finisse fuori dalla barra. */
.ev-when{font-size:1.05rem;font-weight:600;color:var(--daop-navy,#1b3a5c)}
.ev-facts{list-style:none;padding:0;margin:22px 0;display:grid;gap:10px}
.ev-facts li{display:flex;gap:10px;align-items:flex-start;line-height:1.45}
.ev-facts svg{flex:0 0 auto;margin-top:3px;opacity:.65}
.ev-body{margin:26px 0;line-height:1.7}
.ev-body p{margin:0 0 .9em}
.ev-body p:last-child{margin-bottom:0}
/* Il "Programma:" scritto dentro la descrizione, impaginato da
   corpo_descrizione(): un gruppo per giorno, la data una volta sola in
   colonna, l'ora come pillola. La griglia a 62px sta in una riga sola fino a
   "30/08"; sotto i 520px va in colonna, perche' a due colonne il titolo di una
   voce lunga restava in una gola di 90px. Questo CSS vive in PAGINA_CSS e non
   nello <style> di eventi.html: la descrizione impaginata sta sulle schede, e
   una regola di la' farebbe un diff su ~260 file per pagine che non la usano. */
.ev-prog-h{font-family:'Playfair Display',serif;font-size:1.12rem;font-weight:700;
  margin:1.6em 0 .6em;padding-top:1em;border-top:1px solid rgba(45,74,92,.14)}
.ev-prog{display:grid;gap:14px}
.ev-prog-g{display:grid;grid-template-columns:62px 1fr;gap:12px;align-items:baseline}
/* Un programma senza date - evento di un giorno solo, dove nel foglio la data
   dentro il programma non si scrive - non ha l'etichetta, e senza questa riga
   il suo elenco cadeva nella gola di 62px riservata alla data: misurato 62px
   di larghezza su 17 schede delle 110 che hanno un programma. */
.ev-prog-g > .ev-prog-v:first-child{grid-column:1/-1}
@media(max-width:520px){.ev-prog-g{grid-template-columns:1fr;gap:3px}}
.ev-prog-d{margin:0;font-size:.84rem;font-weight:700;font-variant-numeric:tabular-nums;
  color:#8a6a12;letter-spacing:.02em}
.ev-prog-v{list-style:none;padding:0;margin:0;display:grid;gap:7px}
.ev-prog-v li{line-height:1.45}
.ev-prog-o{display:inline-block;margin-left:6px;font-size:.78rem;font-weight:700;
  font-variant-numeric:tabular-nums;color:#a75b15;background:rgba(232,149,74,.16);
  border-radius:100px;padding:2px 9px;white-space:nowrap}
/* La locandina e' un ritratto 3:4: a tutta larghezza occupava 780x1040px,
   cioe' piu' di uno schermo di scroll prima della descrizione. Sta in colonna,
   non e' la pagina. */
.ev-loc{display:block;width:100%;max-width:420px;height:auto;border-radius:14px;
  margin:22px auto;border:1px solid rgba(45,74,92,.12);box-shadow:0 6px 24px rgba(45,74,92,.10)}
.ev-actions{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:28px 0 8px}
/* Rete di sicurezza: se un .btn restasse senza modificatore non deve mai
   ricadere sul blu di sistema, come e' successo a "Come arrivare". */
.ev-actions .btn{color:#fff}
.ev-back{font-weight:600;color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:3px}
.ev-over{border:1px solid #e5c07b;background:#fdf6e6;border-radius:14px;padding:16px 18px;margin:22px 0}
.ev-over strong{display:block;margin-bottom:4px}
/* Niente regole per il dark mode qui dentro: il sito non ha un tema scuro, il
   body resta crema anche col telefono in dark mode. Quella che stava qui
   dipingeva "Edizione conclusa" di marrone #2e2717 lasciandoci sopra il testo
   navy. Il tema scuro, se arriva, si fa sul body in eventi.html e poi scende. */
/* Il punto di vista DAOP: e' il motivo per cui vale la pena aprire la pagina,
   quindi si vede che e' nostro e non copiato dal volantino. */
.ev-daop{border:1px solid rgba(107,165,168,.45);background:rgba(107,165,168,.09);
  border-radius:16px;padding:20px 22px;margin:28px 0}
.ev-daop>h2{display:flex;align-items:center;gap:8px;font-size:1.1rem;margin:0 0 12px;
  color:var(--navy,#2d4a5c)}
.ev-daop-voce+.ev-daop-voce{margin-top:14px}
.ev-daop-voce h3{font-size:.98rem;margin:0 0 3px;color:var(--navy,#2d4a5c)}
.ev-daop-voce p{margin:0 0 6px;line-height:1.6}
/* "Ci vado con i bambini?": la domanda con cui la gente arriva, dentro il
   corpo della pagina e non nel menu. Colore crema/oro invece del teal del
   punto di vista DAOP: sono due blocchi diversi e non devono sembrare uno. */
.ev-fam{border:1px solid rgba(232,149,74,.42);background:rgba(232,149,74,.08);
  border-radius:16px;padding:20px 22px;margin:28px 0}
.ev-fam>h2{display:flex;align-items:center;gap:8px;font-size:1.1rem;margin:0 0 12px;
  color:var(--navy,#2d4a5c)}
.ev-fam>h2 svg{opacity:.7}
.ev-fam p{margin:0 0 8px;line-height:1.6}
.ev-fam-lab{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em;
  color:#a75b15;margin:16px 0 8px}
.ev-fam-altri{list-style:none;padding:0;margin:0;display:grid;gap:6px}
.ev-fam-altri li{line-height:1.45}
.ev-fam-altri a{font-weight:600;color:var(--navy,#2d4a5c);text-decoration:underline;
  text-underline-offset:3px}
.ev-fam-altri span{font-size:.85rem;opacity:.7}
.ev-fam-piu{margin:10px 0 0}
.ev-fam-tutti{font-weight:600;color:var(--navy,#2d4a5c);text-decoration:underline;
  text-underline-offset:3px}
/* Firma editoriale: chi ha controllato e quando. */
.ev-firma{border-top:2px solid rgba(45,74,92,.14);margin:30px 0 0;padding:16px 0 0;
  font-size:.92rem;line-height:1.6}
.ev-firma-t{display:flex;align-items:center;gap:7px;font-weight:700;margin:0 0 6px;
  color:var(--teal,#6ba5a8)}
.ev-firma p{margin:0 0 6px}
/* Da dove arriva la segnalazione: piu' leggero della firma, piu' presente
   della nota legale sotto - e' un credito, non un disclaimer. */
.ev-fonte{font-size:.88rem;opacity:.85}
.ev-firma-nota{opacity:.78;font-size:.86rem}
.ev-firma a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
/* Altri eventi vicini: link in uscita e motivo per restare sul sito.
   padding:0 e' obbligatorio: e' un <section>, e il CSS del sito ha
   section{padding:100px 24px} come selettore di elemento, che qui dentro
   diventava 100px di vuoto e 24px di rientro rispetto al resto della colonna. */
.ev-vicini{margin:34px 0 0;padding:0}
.ev-vicini h2{font-size:1.15rem;margin:0 0 12px}
.ev-vicini ul{list-style:none;padding:0;margin:0;display:grid;gap:8px}
/* "li a" e non "a": questa e' la riga-scheda dell'elenco, alta e a piena
   larghezza. Quando era .ev-vicini a se la prendevano anche i link di coda
   qui sotto, che diventavano quattro rettangoli impilati - 258px su mobile
   per quattro link. */
.ev-vicini li a{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;
  border:1px solid rgba(45,74,92,.14);border-radius:12px;padding:11px 14px;
  color:inherit;text-decoration:none;transition:border-color .2s,background .2s}
.ev-vicini li a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.08)}
.ev-vic-d{font-size:.8rem;font-weight:700;text-transform:uppercase;letter-spacing:.02em;
  color:var(--teal,#6ba5a8);flex:0 0 auto;min-width:92px}
.ev-vic-n{font-weight:600;flex:1 1 220px}
.ev-vic-c{font-size:.85rem;opacity:.7}
.ev-vic-all{margin:14px 0 0;font-size:.92rem}
.ev-vic-all a{color:var(--navy,#2d4a5c);font-weight:600;text-decoration:underline;text-underline-offset:3px}
/* Le attrazioni sotto il titolo, dentro la barra scura della hero: stessa
   famiglia di .ev-when, mezzo tono piu' acceso perche' e' la riga che conferma
   a chi arriva dalla ricerca di essere nel posto giusto. */
.ev-gancio{margin:6px 0 0;font-size:.95rem;font-weight:600;letter-spacing:.01em;
  opacity:.92}
/* ── La barra delle azioni, e solo sul telefono ─────────────────────────
   PERCHE' ESISTE, e il conto e' misurato il 28/08/2026 a 412px su una scheda
   viva, non stimato. .ev-actions - "Aggiungi al calendario" e "Come arrivare",
   cioe' le due cose che uno viene qui a fare - comincia a 1.725px su una
   pagina alta 4.632: e' interamente in vista solo dopo il 25% dello scroll.
   E il 25% e' la soglia che in GA4 supera circa META' di chi apre la pagina
   (12-18 agosto: 546 scroll_depth al 25% su ~1.070 page_view; al 50% sono
   308, cioe' il 29%). Quindi uno su due non ha mai visto i due bottoni piu'
   cliccati del sito - `click_come_arrivare` e' l'azione numero uno delle
   schede, 33 in sette giorni contro 10 del calendario e 9 del telefono.

   E' lo stesso conto che si faceva sull'invito al canale, con una differenza
   che decide il verso e che vale ora per Ginetto: quello e' una RICHIESTA, e
   in cima chiederebbe qualcosa a chi non ha ancora avuto niente. Questi sono
   SERVIZI - la mappa e la data sono la ragione per cui uno e' arrivato. Un
   servizio si mette davanti, una richiesta no.

   NON sostituisce .ev-actions, che resta dov'e'. La pagina non perde niente
   (li' c'e' anche "Torna all'agenda"), e cosi' la barra si puo' togliere in
   qualunque momento senza lasciare un buco.

   NIENTE JAVASCRIPT, e non e' pigrizia: una barra che compare allo scroll e'
   un terzo ascoltatore su una pagina che ne ha gia' due, e sbaglierebbe
   proprio nel primo istante, che e' quando meta' del pubblico decide. Sta
   ferma. Per lo stesso motivo lo spazio sotto al footer e' un elemento vero
   in flusso e non un padding su body:has(.ev-barra) - :has() non c'e'
   dappertutto, e dove manca il footer finisce sotto la barra in silenzio.

   z-index 60 e non di piu': il banner dei cookie sta a 99999 e DEVE vincere -
   la barra non puo' coprire la richiesta di consenso. Sotto i 600px, cioe'
   dove sta il 90% del pubblico; su desktop i bottoni si vedono senza.

   I clic si contano da soli e senza una riga di JS: daop-track.js ricava il
   nome dell'evento dall'href (nome_evento()), quindi questi tre link mandano
   gli stessi `click_come_arrivare`, `click_telefono`, `aggiungi_calendario`
   dei bottoni nel corpo, con gli stessi parametri. Non c'e' un secondo posto
   da tenere allineato, ed e' il motivo per cui non ne nasce uno. */
.ev-barra,.ev-barra-spazio{display:none}
@media(max-width:600px){
  .ev-barra-spazio{display:block;height:62px}
  /* `top:auto` e' esplicito apposta: la regola di elemento nav{top:0} del
     guscio ha gia' stirato questa barra a tutto schermo una volta. */
  .ev-barra{display:flex;position:fixed;left:0;right:0;bottom:0;top:auto;z-index:60;gap:2px;
    padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px));
    background:rgba(255,255,255,.97);backdrop-filter:blur(12px);
    border-top:1px solid rgba(45,74,92,.14);box-shadow:0 -2px 14px rgba(45,74,92,.09)}
  .ev-barra a{flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;
    justify-content:center;gap:3px;padding:6px 4px;border-radius:12px;text-decoration:none;
    font-size:.72rem;font-weight:700;line-height:1.15;text-align:center;
    color:var(--navy,#2d4a5c);-webkit-tap-highlight-color:transparent}
  .ev-barra a:active{background:rgba(45,74,92,.09)}
  .ev-barra svg{width:19px;height:19px;opacity:.82}
  .ev-barra span{display:block;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
}
"""


PAGINA_CSS += GINETTO_CSS


def blocco_ginetto(citta="", alto=False):
    """Rimando a Ginetto sulle pagine di evento e di comune.

    Non e' un avviso e non e' un popup: e' la .info-strip della home eventi,
    stesso componente, con la mascotte al posto dell'icona. Il comune nel
    titolo lo sappiamo gia', e una domanda che nomina il posto in cui si trova
    chi legge vale piu' di un invito generico.

    IL TESTO (13/08/2026). Prima diceva "l'assistente di DAOP: trova eventi e
    luoghi in base all'eta' dei tuoi figli", che di Ginetto e' la descrizione
    di un filtro, non di quello che e'. Ora dice tre cose che si possono
    dimostrare: che e' un'intelligenza artificiale, che gli si scrive in
    italiano invece di riempire un modulo (con l'esempio, che vale piu' della
    parola "conversazionale"), e che dietro c'e' una selezione fatta a mano.

    "La prima ... per le famiglie di <province>" e non "per le famiglie": un
    primato senza confini non lo possiamo dimostrare, e un superlativo che non
    si dimostra e' esattamente il terreno su cui il Codice del consumo considera
    ingannevole una vanteria. Circoscritto al territorio e' vero, verificabile e
    dice di piu': e' il nostro.

    Le province NON sono scritte a mano: escono da PROVINCE_PUBBLICATE, come i
    filtri e le liste. E' l'unico modo perche' aggiungerne una non lasci indietro
    proprio la frase che dichiara dove arriviamo - il commento in cima a
    eventi.html avverte che "Alessandria e Asti" va cercato a mano in TUTTO il
    file, e questo e' un posto in meno in cui cercarlo.

    `alto` NON e' "in cima": e' il GUSCIO. Vero da' l'<aside> dentro
    l'articolo, falso la fascia a tutta larghezza dopo l'articolo. Il testo e'
    IDENTICO nei due casi, apposta: cambiando insieme posizione e parole non si
    saprebbe quale delle due ha spostato il numero.

    Dove va il guscio stretto, e sono due casi con la stessa ragione:

      - IN CIMA a un'EDIZIONE CONCLUSA (28/08/2026). Li' la regola della coda
        cade: in coda si chiede a chi ha gia' avuto quello che cercava, ma una
        scheda conclusa non ha niente da dare - chi ci arriva da Google ha
        appena scoperto che la festa e' finita, e ha gia' in testa "e allora
        cosa faccio?". Ginetto a quella risponde adesso.
      - NEL POSTO CHE ERA DELL'INVITO AL CANALE sulle pagine comune e sulle
        landing (04/09/2026). Li' Ginetto stava in fondo, sotto altri tre o
        quattro blocchi di coda; l'invito al canale stava piu' in alto, subito
        dopo l'elenco. Tolto il canale quel posto era libero, e lasciarlo
        vuoto per tenere Ginetto piu' in basso sarebbe stato regalare la sola
        cosa che questo cambio guadagna.

    PERCHE' GINETTO E NON UNA TERZA COSA, ed e' misurato non supposto: nella
    settimana 12-18/08 `apri_ginetto` fa 7 clic stando al 71% della pagina,
    mentre l'invito al canale - piu' in alto, al 59% - stava dentro un secchio
    da 4. Era la richiesta che rendeva di piu' del sito, ed era quella messa
    piu' in basso. Dal 04/09/2026 il canale non c'e' piu' e Ginetto e' rimasta
    l'unica richiesta del sito: la regola "due richieste nello stesso punto si
    dimezzano" non ha piu' un secondo termine da bilanciare.

    UNA VOLTA SOLA PER PAGINA, e vale in tutti e due i versi: chi lo riceve in
    cima non lo ritrova in fondo - sarebbe la stessa richiesta fatta due volte
    a chi ha gia' detto di no una volta - e chi ce l'ha in coda non lo ha
    sopra. E' quello che tests/luoghi.js difende."""
    # a_citta() mette la d eufonica: "vicino ad Acqui Terme", non "a Acqui".
    dove = " vicino " + esc(a_citta(citta)) if citta else " con i bambini"
    strip = f"""<div class="info-strip">
      <img class="ginetto-faccia" src="/assets/images/ginetto-esplora.webp" alt="Ginetto, la mascotte di DAOP" width="500" height="500" loading="lazy">
      <div>
        <h3>Cerchi altro da fare{dove}?</h3>
        <p>Chiedilo a <strong>Ginetto AI</strong>, la prima intelligenza artificiale pensata per le famiglie di {province_in_elenco(PROVINCE_PUBBLICATE)}: gli scrivi come parleresti a un amico &mdash; <em>&laquo;dove andiamo domenica con un bimbo di 4 anni?&raquo;</em> &mdash; e ti risponde con luoghi ed eventi veri, scelti a mano. <a href="https://ginettoapp.it" target="_blank" rel="noopener">Apri Ginetto &rarr;</a></p>
      </div>
    </div>"""
    if alto:
        return f"""<aside class="ev-ginetto-alto">
    {strip}
  </aside>
"""
    return f"""<section class="bg-cream ev-ginetto">
  <div class="section-inner">
    {strip}
  </div>
</section>
"""


ORG_ID = f"{SITE_URL}/#organization"
SITE_ID = f"{SITE_URL}/#website"
METODO_URL = f"{SITE_URL}/metodo.html"
ZONE_HREF = "/zone.html"                       # nei link interni delle pagine
ZONE_URL = f"{SITE_URL}{ZONE_HREF}"            # canonical e dati strutturati

PHONE_SVG = ('<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>')

STAR_SVG = ('<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" '
            'aria-hidden="true"><path d="m12 2.6 2.9 5.9 6.5.9-4.7 4.6 1.1 6.4-5.8-3-5.8 3 1.1-6.4L2.6 9.4l6.5-.9z"/></svg>')

ORG_SVG = ('<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" '
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/>'
           '<path d="M10 6h4M10 10h4M10 14h4M10 18h4"/></svg>')
CHECK_SVG = ('<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
             '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="M22 4 12 14.01l-3-3"/></svg>')

# L'ordine e' quello con cui si decide davvero: prima se ci vado, poi se e'
# adatto, poi la logistica.
BLOCCHI_DAOP = (
    ('adatto', 'Adatto davvero ai bambini?'),
    ('eta_consigliata', 'Età consigliata'),
    ('dintorni', 'Cosa fare nei dintorni'),
)


def blocco_daop(e):
    """Il giudizio editoriale: l'unica parte che non sta sul volantino.

    Compare solo per i campi compilati nel foglio. Un titolo senza risposta
    ("Dove parcheggiare" seguito dal vuoto) e' peggio che non averlo."""
    voci = [(t, (e.get(k) or '').strip()) for k, t in BLOCCHI_DAOP
            # "Età consigliata" e' il giudizio nostro: se ripete la colonna Età,
            # che sta gia' nella scheda fra i dati, e' una riga in piu' che dice
            # la stessa cosa.
            if not (k == 'eta_consigliata'
                    and _key(e.get(k)) == _key(e.get('eta')))]
    voci = [(t, v) for t, v in voci if v]
    if not voci:
        return ''
    corpo = "".join(
        f'<div class="ev-daop-voce"><h3>{esc(t)}</h3>'
        + "".join(f"<p>{esc(p)}</p>" for p in re.split(r'\n{2,}', v) if p.strip())
        + '</div>' for t, v in voci)
    return ('<section class="ev-daop" aria-labelledby="daop-consiglio">'
            f'<h2 id="daop-consiglio">{CHECK_SVG} Il punto di vista DAOP</h2>'
            f'{corpo}</section>')


# Le attrazioni della lista RICHIAMI che riguardano i bambini e non gli adulti.
# Servono a distinguere "sagra dove i bambini sono tollerati" da "sagra dove per
# i bambini c'e' qualcosa": la prima ha lo stand gastronomico, la seconda ha i
# gonfiabili. E' una differenza che nel foglio non c'e' come colonna, ma che sta
# scritta nelle descrizioni, e che e' esattamente la domanda di chi legge.
RICHIAMI_BAMBINI = (
    "laboratori per bambini", "gonfiabili", "truccabimbi", "burattini",
    "giostre", "luna park", "mongolfiere",
)

# Sottoinsieme piu' stretto, per decidere se un evento va CONSIGLIATO ad altri
# come "roba per bambini". Il luna park e le mongolfiere restano fuori: sono
# attrazioni che stanno anche nelle feste pensate per gli adulti, e mettere
# "Divina & DJ Pablo" sotto "altro per bambini qui vicino" perche' in paese
# c'e' il luna park e' il genere di scivolone che toglie fiducia alla pagina.
RICHIAMI_BAMBINI_FORTI = (
    "laboratori per bambini", "gonfiabili", "truccabimbi", "burattini", "giostre",
)


def per_bambini(e):
    """Le attrazioni per bambini citate nella descrizione dell'evento."""
    return [v for v in richiami(e.get('descr'), massimo=len(RICHIAMI))
            if v in RICHIAMI_BAMBINI]


def e_per_bambini(e):
    """True se l'evento e' pensato PER i bambini, non solo adatto a portarceli.

    Il segnale forte e' uno dei due: una fascia d'eta' NUMERICA nel foglio
    (qualcuno ha deciso che e' per i 3-10 anni) oppure un'attrazione dedicata ai
    bambini scritta nella descrizione. 'Adatto famiglie: Si' da solo non basta:
    ce l'ha il 93% delle righe, e una parola vera per il 93% dei casi non dice
    niente. Nemmeno 'Tutte le eta'' basta, per lo stesso motivo: e' la risposta
    che si da' quando non si e' deciso niente."""
    return bool(fascia_eta(e.get('eta'))
                or [v for v in per_bambini(e) if v in RICHIAMI_BAMBINI_FORTI])


def blocco_famiglie(rec, events, oggi, hub=None):
    """La riga che risponde alla domanda con cui la gente arriva davvero.

    PERCHE' ESISTE (09/08/2026): l'86% dei clic del sito arriva sulle schede
    evento, e il 93% degli eventi in agenda e' segnato adatto alle famiglie -
    ma sulla scheda non c'era una parola che lo dicesse dentro il testo. Il solo
    aggancio a DAOP era il riquadro Ginetto in fondo, al 71% della pagina.
    Questa e' la stessa cosa detta dove si legge, e con i dati che abbiamo gia'
    nel foglio: niente di inventato, e se non sappiamo niente non compare."""
    adatto = (rec.get('adatto_famiglie') or '').strip()
    eta = (rec.get('eta') or '').strip()
    cosa = per_bambini(rec)
    citta = (rec.get('citta') or '').strip()
    # Il flag non fa piu' da cancello: era "Si" nel 95% delle righe e vuoto in
    # tre, e quelle tre perdevano il riquadro per una cella non compilata, non
    # perche' l'evento fosse un'altra cosa. Quello che apre il riquadro e'
    # avere qualcosa di specifico da dire, il controllo qui sotto.
    # La soglia e' avere qualcosa di SPECIFICO da dire. "Adatto famiglie: Si" +
    # "Tutte le eta'" ce l'ha quasi ogni riga del foglio: un riquadro che
    # ripetesse quello su 99 schede su 100 sarebbe rumore, e la riga "Età" fra i
    # dati lo dice gia'. Serve una fascia numerica o un'attrazione vera.
    fascia = fascia_eta(eta)
    if not (fascia or cosa):
        return ''

    # L'eta' si stampa nel testo del foglio ("3-10 anni"), non normalizzata: e'
    # gia' scritta per essere letta. Ma solo quando e' una fascia vera, se no
    # "Età indicata: Tutte le età" subito dopo "adatto alle famiglie" e' la
    # stessa frase detta due volte.
    # L'eta' NON si ripete qui: sta gia' fra i dati della scheda, nella riga
    # "Età", e in ogni riga degli elenchi. Ripeterla nel riquadro la faceva
    # sembrare un requisito d'ingresso dell'evento ("da 3 a 10 anni") invece
    # dell'indicazione di massima che e'. La fascia resta come condizione per
    # aprire il riquadro - vuol dire che abbiamo qualcosa di specifico da dire
    # - ma la cifra la si legge dove sta gia'.
    righe = []
    # La risposta non viene piu' da una colonna del foglio ma dal criterio con
    # cui l'agenda e' fatta, che vale per ogni scheda pubblicata. Dire "nella
    # scheda DAOP e' segnato adatto alle famiglie" faceva sembrare un giudizio
    # per evento quello che e' la regola d'ingresso, e lasciava intendere che
    # gli altri fossero segnati diversamente.
    #
    # La seconda frase non e' una cautela di rito: la scelta la facciamo sulla
    # locandina, cioe' sulla manifestazione intera, e sotto una patronale
    # stanno il laboratorio del pomeriggio e il ballo di mezzanotte. Su quale
    # sia quale il foglio non ha un giudizio - e non prometterlo e' piu' utile
    # che prometterlo a vuoto.
    righe.append('<p>Sì: in agenda DAOP pubblichiamo solo quello che abbiamo '
                 'scelto <strong>per le famiglie</strong>. Nelle manifestazioni '
                 'con più appuntamenti, l\'orario che fa per i bambini cambia da '
                 'serata a serata: il programma qui sopra è il modo più sicuro '
                 'per scegliere.</p>')
    if _key(adatto) == _key('Da verificare'):
        righe.append('<p>Il programma di questa edizione non ce l\'ha ancora '
                     'confermato l\'organizzatore: i dettagli sono '
                     '<strong>da verificare</strong>, e i recapiti per chiedere '
                     'sono qui sopra.</p>')
    if cosa:
        righe.append(f'<p>Per i più piccoli, nel programma ci sono '
                     f'<strong>{esc(elenco_it(cosa))}</strong>.</p>')

    # Altri eventi PER bambini in zona: stessa citta' prima, poi provincia.
    # Lo slug non basta a riconoscersi: la stessa festa compare nel foglio con
    # le parole girate ("Al dì d'la festa - Casorzo Monferrato" e "Casorzo
    # Monferrato al dì d'la festa"), che fanno due slug diversi. Confrontare
    # l'insieme delle parole li riconosce uguali, che e' quello che sono; senza,
    # la scheda consigliava se stessa come "altro per bambini qui vicino".
    mio = rec['slug']
    prov = (rec.get('prov') or '').upper()
    k_citta = _key(citta)
    miei_slug = {mio, slugify(rec.get('nome') or '')} - {''}
    mie_parole = _insieme_parole(rec.get('nome'))
    cand = []
    for e in events:
        if slug_evento(e) in miei_slug or _insieme_parole(e.get('nome')) == mie_parole:
            continue
        if not e_per_bambini(e):
            continue
        stessa = _key(e.get('citta')) == k_citta
        if not stessa and (e.get('prov') or '').upper() != prov:
            continue
        cand.append((0 if stessa else 1, e['d_start'], (e.get('nome') or ''), e))
    cand.sort(key=lambda t: t[:3])
    if cand:
        voci = []
        for _, _, _, e in cand[:3]:
            voci.append(f'<a href="{_href_evento(e)}">'
                        f'{esc(trunc(e.get("nome") or "", 52))}</a>'
                        f' <span>{esc(e.get("citta") or "")}</span>')
        mio_hub = (hub or {}).get(k_citta)
        tutti = (f'<a class="ev-fam-tutti" href="/eventi/comune/{mio_hub["slug"]}.html">'
                 f'Tutti gli eventi{a_citta(mio_hub["nome"])}</a>' if mio_hub else '')
        righe.append('<p class="ev-fam-lab">Altro per bambini qui vicino</p>'
                     f'<ul class="ev-fam-altri">{"".join(f"<li>{v}</li>" for v in voci)}</ul>'
                     + (f'<p class="ev-fam-piu">{tutti}</p>' if tutti else ''))

    return ('<section class="ev-fam" aria-labelledby="ev-fam-t">'
            f'<h2 id="ev-fam-t">{USER_SVG} Ci vado con i bambini?</h2>'
            + "".join(righe) + '</section>')


def firma_daop(rec, oggi, ritirata=False):
    """Firma editoriale + data dell'ultimo controllo + avvertenza.

    La data e' last_seen, cioe' l'ultima volta che la scheda e' stata
    riscontrata sul foglio DAOP: e' un controllo vero, non la data della run."""
    iso = rec.get('last_seen') or rec.get('updated') or rec.get('first_seen') or oggi.isoformat()
    try:
        d = datetime.date.fromisoformat(iso)
        leggibile = f"{d.day} {MESI_LUNGHI[d.month - 1]} {d.year}"
    except ValueError:
        d, leggibile = oggi, iso
    ogg = urllib.parse.quote(f"Correzione scheda: {(rec.get('nome') or '').strip()}")
    # Da dove arriva la segnalazione. Sta QUI, dentro la firma, e non fra i dati
    # in cima: non e' un'informazione che serve a decidere se andarci, e' la
    # trasparenza su come la scheda e' nata - lo stesso posto in cui diciamo chi
    # l'ha controllata e quando.
    credito = credito_fonte(fonte_provincia(rec.get('prov')), 'Segnalato da',
                            classe='ev-fonte')
    # Scheda RITIRATA: la riga e' stata tolta dal foglio prima della sua data.
    # Qui non si puo' dire "verificata": il 18/08/2026 quella frase e' rimasta in
    # piedi, con tanto di "ultimo controllo", su un evento che avevamo cancellato
    # PROPRIO perche' non doveva esserci (un pranzo sociale in ristorante finito
    # in agenda da un programma di sagra). Restano due cose: il credito alla
    # pagina che l'ha segnalata - la segnalazione c'e' stata davvero - e il
    # mailto, che e' la strada per dirci che abbiamo ritirato per sbaglio.
    if ritirata:
        return (
            '<aside class="ev-firma">'
            '<p class="ev-firma-t">Scheda ritirata da DAOP</p>'
            '<p>Questa scheda non fa piu\' parte dell\'agenda di <strong>DAOP – Dove '
            'Andiamo Oggi Papi</strong>: risultava in programma fino al '
            f'<time datetime="{d.isoformat()}">{leggibile}</time>, poi l\'abbiamo tolta. '
            'Non consideriamo confermato quello che c\'e\' scritto in questa pagina.</p>'
            f'{credito}'
            '<p class="ev-firma-nota">'
            '<a href="/eventi.html">Vai all\'agenda aggiornata</a> · '
            f'<a href="mailto:info@daop.it?subject={ogg}">Segnala una correzione</a></p>'
            '</aside>')
    return (
        '<aside class="ev-firma">'
        f'<p class="ev-firma-t">{CHECK_SVG} Scheda verificata da DAOP</p>'
        '<p>Selezionata e verificata da <strong>DAOP – Dove Andiamo Oggi Papi</strong>, '
        f'l\'associazione delle famiglie di {PROVINCE_TESTO}. Ultimo controllo: '
        f'<time datetime="{d.isoformat()}">{leggibile}</time>.</p>'
        f'{credito}'
        '<p class="ev-firma-nota">Le informazioni possono cambiare. Prima di partire, '
        'controlla eventuali aggiornamenti dell\'organizzatore. '
        '<a href="/metodo.html">Come verifichiamo gli eventi</a> · '
        f'<a href="mailto:info@daop.it?subject={ogg}">Segnala una correzione</a></p>'
        '</aside>')


def barra_azioni(e):
    """I tre gesti della scheda, fermi in fondo allo schermo del telefono.

    Il perche' sta per esteso nel commento di .ev-barra dentro PAGINA_CSS: i
    bottoni del corpo sono in vista solo dopo il 25% dello scroll, e al 25%
    ci arriva meta' del pubblico.

    L'ORDINE E' QUELLO DEI NUMERI, non quello del codice: "Come arrivare" e'
    l'azione piu' cliccata delle schede, quindi sta a sinistra dove cade
    l'occhio; il calendario, che e' un gesto di chi ha gia' deciso, va in
    fondo. Il telefono compare solo dove il foglio ha davvero un numero (62
    schede vive su 173 al 28/08/2026): un bottone "Chiama" che non chiama
    nessuno e' peggio di due bottoni.

    SOTTO I DUE NON SI STAMPA NIENTE. Una barra fissa costa 62px di schermo a
    tutti; per un bottone solo prende piu' di quello che rende, e quel bottone
    sta gia' nel corpo.

    Non si chiama MAI su una scheda conclusa o ritirata, e non e' una svista:
    li' "Come arrivare" e "Aggiungi al calendario" sono esattamente i due
    bottoni dannosi che render_pagina() gia' toglie dal corpo - mandano in
    macchina, e scrivono in agenda, verso un appuntamento che non c'e'."""
    voci = []
    m = maps_url(e)
    if m:
        voci.append((m, PIN_SVG, 'Come arrivare', True))
    tel = primo_telefono(e.get('contatto'))
    if tel:
        voci.append(('tel:' + tel, PHONE_SVG, 'Chiama', False))
    g = gcal_url(e)
    if g:
        voci.append((g, CAL_SVG, 'Calendario', True))
    if len(voci) < 2:
        return ''
    link = []
    for href, ico, testo, fuori in voci:
        extra = ' target="_blank" rel="noopener"' if fuori else ''
        link.append(f'<a href="{esc(href)}"{extra}>{ico}<span>{testo}</span></a>')
    # UN <div> E NON UN <nav>, e non e' una sfumatura di gusto: il <style> di
    # eventi.html - che _guscio() copia in ogni pagina generata - ha la regola
    # di ELEMENTO `nav{position:fixed;top:0;left:0;right:0;z-index:100}` per la
    # barra del sito. Un <nav class="ev-barra"> la eredita e si ritrova top:0
    # E bottom:0 insieme: misurato, la barra veniva alta 915px, cioe' tutto lo
    # schermo, coprendo la pagina. Sono anche azioni e non navigazione, quindi
    # il ruolo giusto e' group.
    return ('<div class="ev-barra-spazio" aria-hidden="true"></div>'
            '<div class="ev-barra" role="group" aria-label="Azioni rapide">'
            + "".join(link) + '</div>')


_INDICE_LUOGHI = None


def indice_luoghi():
    """I comuni che hanno almeno un luogo in /luoghi.html, letti una volta sola.

    Il file lo scrive genera_luoghi.py, che gira DOPO questo script: si legge
    quindi l'indice della notte prima. E' voluto, vedi salva_indice_comuni()
    la'. Se il file non c'e' (prima run, o clone senza la notte precedente) il
    dizionario e' vuoto e i link semplicemente non si stampano: la pagina esce
    come prima, senza rompersi."""
    global _INDICE_LUOGHI
    if _INDICE_LUOGHI is None:
        try:
            with open(INDICE_LUOGHI_PATH, encoding="utf-8") as fh:
                _INDICE_LUOGHI = json.load(fh)
        except (OSError, ValueError):
            _INDICE_LUOGHI = {}
    return _INDICE_LUOGHI


def link_luoghi(citta, prov):
    """Il link ai luoghi del comune, o '' se in quel comune non ce n'e' nessuno.

    E' l'unico ponte fra le due meta' del sito. Le schede evento fanno l'82% dei
    clic e /luoghi.html ne fa zero: non perche' sia peggiore, ma perche' fino a
    oggi ci si arrivava solo dalla nav, e alla nav non ci va nessuno. Chi ha
    appena letto l'orario di una sagra a Ovada e' esattamente la persona a cui
    interessa cos'altro c'e' a Ovada.

    Si stampa solo se l'ancora esiste per davvero (stessa regola dei link alle
    pagine comune): mandare su /luoghi.html senza bersaglio scarica in cima a una
    pagina da 800 righe, cioe' peggio che non linkare. E si stampa il numero,
    perche' "22 luoghi" e' una ragione per toccare e "Luoghi" non lo e'."""
    if not citta:
        return ''
    slug = slugify(citta)
    prov = (prov or '').strip()
    ancora = f"c-{prov.lower()}-{slug}" if prov else f"c-{slug}"
    dati = indice_luoghi().get(ancora)
    if not dati:
        return ''
    n = dati.get('n') or 0
    quanti = "Un posto" if n == 1 else f"{n} posti"
    return (f'<a href="/luoghi.html#{ancora}">{quanti} per famiglie'
            f'{a_citta(esc(dati.get("comune") or citta))}</a>')




# --- Chi organizza, quando ha una pagina sua --------------------------------
#
# IL NOME DELLA SOCIETA' STA IN CODA AL NOME DELL'EVENTO, dopo un trattino
# spaziato: "Sogni d'Oro - CàRezza", "Green Volley Torneo 2VS2 - PGS
# Roccavione". Non e' una convenzione dedotta qui: e' quella che il downloader
# impone al modello quando legge una locandina ("titolo del singolo
# appuntamento - Organizzatore"), ed e' la stessa da cui organizzatore() ricava
# l'organizer del JSON-LD.
#
# IL TAGLIO STA QUI e non in genera_corsi.py, che pure lo usa per l'altro verso
# (gli eventi di una realta' raccolti sulla sua pagina): genera_corsi importa
# questo modulo, non il contrario, e due implementazioni della stessa regola
# divergerebbero al primo ritocco - dando due link che si contraddicono, uno
# per verso. E' la ragione per cui la nav si rilegge da eventi.html invece di
# essere copiata.
CODA_ORG_RE = re.compile(r'\s[-–—]\s+')


def taglia_coda(nome):
    """(titolo, societa') tagliando sull'ULTIMO trattino spaziato.

    L'ultimo e non il primo: "TuteliAMO - Corso Manovre Salvavita Pediatriche -
    CàRezza" ha due trattini, e la societa' e' quella in fondo. Il trattino deve
    avere spazi intorno, se no "Espressione in Gioco! fascia 2-6 anni" si
    spezzerebbe sul 2-6.

    Senza trattino la coda e' vuota, e un evento che non dichiara chi lo
    organizza non si attacca a nessuno: quello che manca non si stampa e non si
    inventa, come in link_luoghi()."""
    testo = (nome or '').strip()
    ultimo = None
    for m in CODA_ORG_RE.finditer(testo):
        ultimo = m
    if not ultimo:
        return testo, ''
    return testo[:ultimo.start()].strip(), testo[ultimo.end():].strip()


def spezza_nome_evento(nome):
    """Lo stesso taglio, in slug: serve a confrontare, non a stampare."""
    testa, coda = taglia_coda(nome)
    return slugify(testa), slugify(coda)


_INDICE_REALTA = None


def indice_realta():
    """Le realta' che hanno una pagina in /corsi/, lette una volta sola.

    Il file lo scrive genera_corsi.py, che gira DOPO questo script: si legge
    quindi l'indice della notte prima. E' lo stesso ritardo di un giro di
    data/luoghi-comuni.json e data/conteggi.json, e per la stessa ragione -
    chiudere il cerchio costerebbe piu' di quello che risolve. Una realta' che
    entra oggi nel foglio resta un giorno senza il link dalle sue schede, e
    sbagliare in quel verso e' gratis; il verso opposto no, perche' un link a
    una pagina che genera_corsi ha appena cancellato e' un 404.

    Se il file non c'e' il dizionario e' vuoto e i link non si stampano: la
    pagina esce come prima, senza rompersi."""
    global _INDICE_REALTA
    if _INDICE_REALTA is None:
        try:
            with open(INDICE_REALTA_PATH, encoding="utf-8") as fh:
                _INDICE_REALTA = json.load(fh)
        except (OSError, ValueError):
            _INDICE_REALTA = {}
    return _INDICE_REALTA


def link_realta(nome_evento):
    """Il link alla pagina di chi organizza, o '' se non ce l'ha.

    E' IL VERSO OPPOSTO del legame che eventi_realta() fa in genera_corsi.py, e
    senza di questo quello e' mezzo: la pagina di CàRezza raccoglieva i suoi
    appuntamenti, ma chi arriva da Google su "Sogni d'Oro Racconigi" trovava
    solo /corsi.html generico e non scopriva che quella realta' ha una pagina
    sua con dentro i suoi corsi.

    Si stampa il NOME e non l'etichetta - "I corsi di CàRezza" e' una ragione
    per toccare, "Organizzatore" no. E' la lezione di link_luoghi(), riusata.

    La coda deve corrispondere a una pagina che esiste davvero: un evento
    firmato da una realta' senza pagina non stampa niente, invece di mandare su
    un 404 o su /corsi.html, che e' dove si andrebbe comunque dalla riga delle
    quattro porte in fondo alla scheda."""
    _, coda = taglia_coda(nome_evento)
    if not coda:
        return ''
    voce = indice_realta().get(slugify(coda))
    if not voce:
        return ''
    return (f'<a href="{voce["url"]}">I corsi di {esc(voce["nome"])}</a>')


# --- Le quattro porte -------------------------------------------------------
#
# Le quattro famiglie del sito sono quattro rapporti col tempo, e non quattro
# argomenti: l'evento ha una data, il centro una settimana, il corso una
# stagione, il luogo nessuno. Non e' una tassonomia per bellezza — e' il
# criterio che decide dove va una scheda nuova senza doverne discutere.
#
# PERCHE' ESISTE QUESTA RIGA. Fino al 20/08/2026 due famiglie su quattro non
# avevano una porta da nessuna parte: la nav ne aveva due (Eventi, Luoghi), il
# footer due DIVERSE (Eventi, Corsi), e nessun posto del sito le conteneva tutte
# e quattro. Misurato lo stesso giorno con grep su tutto il repo:
# centri-invernali.html, centri-pasquali.html e piscine.html ricevevano ZERO
# link dal corpo di qualunque pagina — stavano solo in sitemap.
# E' lo stesso guasto gia' diagnosticato e gia' risolto su luoghi.html il 14/08
# ("alla nav non ci va nessuno": aggiunto il ponte dalle schede evento, le
# impressioni sono passate da 58 a 538 in due giorni). Qui le tre orfane non
# avevano nemmeno la nav.
#
# LE TRE REGOLE, tutte prese da cose gia' provate qui dentro:
#  - COL NUMERO, non l'etichetta. "894 posti per famiglie" e' una ragione per
#    toccare, "Luoghi" no. E' la lezione di link_luoghi(), riusata.
#  - IN CODA AL CORPO, non nell'hero. Stessa regola che valeva per l'invito al
#    canale: in cima chiedi qualcosa a chi non ha ancora avuto niente. E l'hero
#    di eventi.html non si tocca comunque, vale il 30% delle impressioni.
#  - NON SULLE ~300 SCHEDE EVENTO. Quelle hanno gia' blocco_vicini(), il link ai
#    luoghi del comune e la striscia di Ginetto: una quarta riga di link in coda
#    e' la barra che non guarda nessuno. Questa riga sta sui quattro hub e sulle pagine di
#    intenzione: ~40 pagine adulte, non 300. Sulle schede si allarga invece la
#    riga che funziona gia' — vedi link_luoghi().
#
# Il CSS di .eco sta in assets/css/daop-system.css e NON nel <style> di
# eventi.html, che e' la scelta opposta al resto del sito ed e' voluta: la riga
# deve comparire anche su pagine che non passano da _guscio() (i corsi, i
# centri, le rubriche), e il file condiviso le raggiunge tutte senza fare un
# diff su 260 file per una griglia di tre card.
# ---------------------------------------------------------------------------
# La voce dei centri in nav: la scrive il foglio, non il calendario
# ---------------------------------------------------------------------------
# Fino al 21/08/2026 la nav diceva "Centri estivi" tutti i giorni dell'anno, su
# ~360 pagine, cioe' anche a novembre - quando quella pagina risponde
# "iscrizioni non ancora aperte" e chi cerca vuole il campus di Natale. E' anche
# anchor text ripetuto su tutto il sito, quindi non era solo una parola fuori
# posto.
#
# Perche' NON un calendario scritto qui: le finestre si spostano ogni anno. In
# Piemonte il Carnevale 2027 vale cinque giorni (6-10 febbraio) e il ponte di
# Ognissanti 2026 non esiste, perche' l'1 novembre cade di domenica. Una
# tabella di mesi in questo file sbaglierebbe ogni anno; il foglio no - e la
# colonna 'stagione' esiste gia' ed e' gia' piu' forte delle date
# (genera_centri.leggi_centri).
#
# Il patto e' un file, data/centri-stagioni.json, scritto da genera_centri.py e
# letto qui: e' in ritardo di un giro come data/conteggi.json e
# data/luoghi-comuni.json. Se il file manca la voce non si stampa - la stessa
# regola di link_luoghi(): un link verso una pagina vuota e' peggio di nessun
# link, e il footer tiene comunque il collegamento alla famiglia.
STAGIONI_PATH = os.path.join(ROOT, "data", "centri-stagioni.json")


def stagione_centri():
    """La stagione dei centri che ha diritto alla nav, o None.

    Vince quella che sta per cominciare - data di inizio piu' vicina fra i
    centri ancora in piedi. Una stagione GIA' COMINCIATA ha una data nel
    passato, quindi passa davanti: e' quella che sta succedendo adesso, ed e'
    il caso di febbraio, quando il Carnevale e' in corso mentre le iscrizioni
    estive sono appena aperte."""
    try:
        d = json.load(open(STAGIONI_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    vive = [v for v in d.values()
            if isinstance(v, dict) and v.get('attivi')
            and v.get('file') and v.get('voce')
            # Una voce verso una pagina che non esiste su disco scarica in 404
            # da tutto il sito: si controlla, non si suppone.
            and os.path.exists(os.path.join(ROOT, v['file']))]
    if not vive:
        return None
    vive.sort(key=lambda v: (v.get('inizio') is None, v.get('inizio') or '',
                             -v['attivi'], v['file']))
    return vive[0]


def voce_centri(mobile=False, assoluto=False):
    """La voce di nav, vuota se nessuna stagione ha centri.

    Vuota vuol dire una voce in meno in nav, non un buco: e' il comportamento
    giusto, perche' .nav-links e' una flex row senza wrap e sei voci sono il
    massimo che sta in riga sopra i 901px."""
    v = stagione_centri()
    if not v:
        return ''
    href, voce = v['file'], esc(v['voce'])
    if assoluto:
        href = '/' + href
    if mobile:
        return f'<a href="{href}" onclick="closeMobile()">{voce}</a>'
    return f'<li><a href="{href}">{voce}</a></li>'


def riga_centri_hero():
    """La riga di rimando in fondo all'hero dell'agenda.

    Diceva "centri estivi o invernali ... in provincia di Alessandria e Asti":
    l'una e' la stagione sbagliata per nove mesi l'anno, l'altra e' il copy
    rimasto indietro sull'apertura di Cuneo (04/08/2026). Sparisce del tutto
    quando non c'e' nessuna stagione viva: senza centri quella riga chiede di
    andare a vedere una pagina che dice "torna in primavera"."""
    v = stagione_centri()
    if not v:
        return ''
    return (f'<p class="hero-nota">Cerchi un centro per le vacanze dei tuoi '
            f'bambini? Vedi i <a href="/{v["file"]}" style="color:inherit;'
            f'text-decoration:underline;text-underline-offset:3px;">'
            f'{esc(v["voce"].lower())} in provincia di {PROVINCE_TESTO}</a>.</p>')


def voce_corsi(mobile=False, assoluto=False):
    """La voce Corsi in nav, vuota finche' la pagina sta fuori dall'indice.

    Stesso meccanismo di voce_centri() e per la stessa ragione: la nav dice
    cosa c'e' adesso, non cosa esiste. La differenza e' la fonte — li' e' il
    foglio (una stagione ha centri o non ne ha), qui e' una decisione nostra
    scritta in CORSI_IN_INDICE."""
    if not CORSI_IN_INDICE:
        return ''
    href = '/corsi.html' if assoluto else 'corsi.html'
    if mobile:
        return f'<a href="{href}" onclick="closeMobile()">Corsi</a>'
    return f'<li><a href="{href}">Corsi</a></li>'


def aggiorna_nav():
    """Riscrive la voce dei centri dove la nav e' scritta a mano.

    Le ~19 pagine generate la ricevono gratis: _guscio() rilegge nav e footer da
    eventi.html a ogni run e le incolla dappertutto. Le altre dodici no -
    index, ginetto, libri, piattosano, media, rubriche, esploratore, bollino,
    privacy, cookie-policy, 404 - perche' nessun generatore le scrive. Lasciate
    a mano, fra sei mesi direbbero una stagione diversa dal resto del sito: e'
    lo stesso motivo per cui il config di GA4 sta in un file solo.

    Nessun elenco di pagine da tenere aggiornato: si riscrive dove il marker
    c'e'. Una pagina nuova entra mettendoci i marker, e finche' non li ha resta
    fuori invece di prendere una voce sbagliata."""
    def blocco(assoluto=False, inline=False):
        return {
            'NAV-CENTRI': voce_centri(assoluto=assoluto),
            'MM-CENTRI': voce_centri(mobile=True, assoluto=assoluto),
            'HERO-CENTRI': riga_centri_hero(),
            'NAV-CORSI': voce_corsi(assoluto=assoluto),
            'MM-CORSI': voce_corsi(mobile=True, assoluto=assoluto),
            # I profili social: qui 'assoluto' non c'entra - sono URL esterne,
            # quindi la voce e' la stessa in tutte e tre le varianti. Cambia
            # solo la vernice, per index.html che ha gli stili in linea.
            'FOOTER-SOCIAL': blocco_social_footer(inline=inline),
        }
    # 404.html e' l'unica pagina a mano che NON viene servita dal proprio
    # indirizzo: GitHub Pages la restituisce all'URL richiesto, quindi da
    # /eventi/qualcosa-che-non-c-e' un href relativo punta a
    # /eventi/centri-estivi.html e la via d'uscita e' rotta - proprio per chi
    # ci arriva dal 70% del traffico del sito, che sono le schede evento. Li'
    # la voce si scrive assoluta; nelle altre undici resta relativa com'era.
    # index.html e' la terza variante: ripete gli stili del footer negli
    # attributi style invece di usare le classi del <style>, quindi la stessa
    # voce le va data vestita, se no i suoi link social nascono senza colore.
    normali, assolute = blocco(), blocco(assoluto=True)
    inlinate = blocco(inline=True)
    v = stagione_centri()
    tocc = []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        s = open(path, encoding="utf-8").read()
        orig = s
        base = os.path.basename(path)
        voci = (assolute if base == '404.html'
                else inlinate if base == 'index.html' else normali)
        for nome, val in voci.items():
            s = re.sub(rf'(<!-- {nome}:START -->).*?(<!-- {nome}:END -->)',
                       lambda m: m.group(1) + val + m.group(2), s, flags=re.S)
        if s != orig:
            open(path, "w", encoding="utf-8").write(s)
            tocc.append(os.path.basename(path))
    if tocc:
        print(f"[genera_eventi] voce centri in nav: "
              f"{'nessuna (nessuna stagione ha centri)' if not v else v['voce']}"
              f" - riscritte {len(tocc)} pagine a mano ({', '.join(tocc[:4])}"
              f"{'...' if len(tocc) > 4 else ''})")


# I corsi hanno un interruttore, e questa e' la sua unica sede.
#
# PERCHE'. Il 21/08/2026 Giovanni ha chiesto di togliere /corsi.html
# dall'online: la pagina ha cinque corsi di una societa' sola e lui considera
# quei dati non verificati per la stagione 2026/2027. Una pagina indicizzata
# fatta di dati che l'unica persona che li conosce dichiara sbagliati e' un
# doppione debole sul dominio che regge eventi.html.
#
# COSA FA, E COSA NON FA. False vuol dire: robots noindex, fuori dalla sitemap,
# fuori dalla nav (voce assente su ~360 pagine) e fuori dalla riga delle quattro
# porte. La pagina RESTA ONLINE — e' la regola di MIN_LANDING gia' scritta per
# le stagionali e per i centri fuori stagione: i link girati su WhatsApp devono
# continuare a funzionare, e l'anzianita' dell'URL e' l'unico asset che una
# pagina nuova non puo' comprare. Il footer tiene il link, come per i centri:
# il footer e' il catalogo, la nav e' cosa c'e' adesso.
#
# QUANDO SI RIACCENDE. A mano, mettendo True, quando i corsi in pagina sono
# dati verificati. Non c'e' una soglia automatica apposta: il problema non e'
# quanti corsi ci sono, e' che quelli che ci sono vanno confermati da chi li
# organizza. Un numero non sa rispondere a quella domanda.
#
# ACCESO IL 28/08/2026. Giovanni ha dato l'ok: i dati sono verificati. Da qui
# la pagina torna index, rientra in sitemap, riprende la voce in nav su ~360
# pagine e la sua card nella riga delle quattro porte, e l'avviso "Sezione in
# preparazione" sparisce da corsi.html.
#
# Quello che NON cambia, ed e' bene sia scritto perche' sembra la stessa cosa:
# la cella Stato di ogni realta' resta padrona della SUA pagina. Al 28/08 su
# tre realta' una sola e' confermata (carezza), quindi le altre due restano
# noindex anche adesso — e vanno bene cosi'. Le due decisioni sono
# deliberatamente indipendenti: questa e' sulla sezione, quella e' sulla
# singola societa'. Se un domani si volesse indicizzarle tutte, il posto e' la
# colonna Stato del foglio, non questo interruttore.
CORSI_IN_INDICE = True


FAMIGLIE = (
    ('eventi', '/eventi.html', 'Eventi e sagre',
     'cosa si fa oggi e questo weekend'),
    ('luoghi', '/luoghi.html', 'Luoghi per famiglie',
     "dove andare quando non c'è niente in programma"),
    ('centri', '/centri-estivi.html', 'Centri estivi e vacanze',
     'estate, Natale e Pasqua, con le iscrizioni'),
    ('corsi', '/corsi.html', 'Corsi per bambini',
     "l'anno di sport, musica, danza e lingue"),
)

# Sotto questo numero il conteggio scoraggia invece di invitare: "1 corso" e' una
# ragione per NON toccare. Stessa aritmetica di MIN_FILTRI — un comando che non
# dice niente non si stampa. Sopra la soglia parla il numero, sotto la riga.
MIN_CONTEGGIO = 5

CONTEGGI_PATH = os.path.join(ROOT, "data", "conteggi.json")


def conteggio_scrivi(chiave, n):
    """Ogni generatore scrive il proprio numero, e li legge tutti da qui.

    Il registro e' in ritardo di un giro, esattamente come
    data/luoghi-comuni.json, e per la stessa ragione: chiudere il cerchio
    costerebbe piu' di quello che risolve. Un numero di ieri sbaglia di poco e
    sbaglia nel verso gratis; il verso opposto — non stampare la riga — no."""
    try:
        d = json.load(open(CONTEGGI_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if d.get(chiave) == n:
        return
    d[chiave] = n
    with open(CONTEGGI_PATH, "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def conteggi_leggi():
    try:
        return json.load(open(CONTEGGI_PATH, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _eco_riga(chiave, n):
    """Il numero messo in parole. Il conteggio da solo ("894") non dice di cosa,
    e la parola da sola non da' una ragione: servono insieme."""
    return {
        'eventi': f"{n} eventi in agenda, aggiornati ogni notte",
        'luoghi': f"{n} posti scelti a mano, dal parco al museo",
        'centri': f"{n} centri con le date e le iscrizioni",
        'corsi': f"{n} corsi, con l'età e la prova gratuita",
    }.get(chiave, str(n))


def blocco_ecosistema(qui=None):
    """Le famiglie diverse da quella in cui siamo, in coda al corpo.

    'qui' e' la chiave della famiglia della pagina: quella non si linka da se'.
    Con qui=None escono tutte e quattro, ed e' il caso della home — dove non si
    e' dentro nessuna famiglia, quindi non c'e' niente da escludere. Sono i due
    soli casi: tre card in coda a una pagina, quattro sulla home.

    Il titolo pone una domanda invece di dire "vedi anche", che e' la regola
    gia' scritta per il ponte verso i luoghi: da dentro una famiglia la domanda
    vera e' "e se non era un evento quello che cercavo?". Sulla home quella
    domanda non ha senso — nessuno e' ancora dentro niente — e il titolo dice
    che cosa c'e'."""
    n = conteggi_leggi()
    voci = []
    for chiave, href, nome, riga in FAMIGLIE:
        if chiave == qui:
            continue
        # Una porta verso una pagina che abbiamo tolto dall'indice non e' una
        # porta: e' un invito a entrare in una stanza che stiamo chiudendo.
        if chiave == 'corsi' and not CORSI_IN_INDICE:
            continue
        q = n.get(chiave) or 0
        sotto = _eco_riga(chiave, q) if q >= MIN_CONTEGGIO else riga
        voci.append(f'<a class="eco-c" href="{href}">'
                    f'<span class="eco-n">{esc(nome)}</span>'
                    f'<span class="eco-d">{esc(sotto)}</span></a>')
    if not voci:
        return ''
    porte = qui is None
    cls = 'eco eco--porte' if porte else 'eco'
    titolo = ('Cosa trovi su DAOP' if porte else 'Cerchi un&#x27;altra cosa?')
    return (f'<section class="{cls}" aria-labelledby="eco-t">'
            f'<h2 class="eco-t" id="eco-t">{titolo}</h2>'
            f'<div class="eco-g">{"".join(voci)}</div></section>')


def blocco_vicini(rec, events, oggi, limite=6, hub=None):
    """Altri eventi vicini: stessa citta' prima, poi stessa provincia.

    Serve a chi legge (l'evento e' finito, o piove: cosa c'e' invece?) e serve
    alle pagine, che senza questo sono foglie senza link in uscita."""
    citta = _key(rec.get('citta'))
    prov = (rec.get('prov') or '').upper()
    mio = rec['slug']
    cand = []
    for e in events:
        if slug_evento(e) == mio:
            continue
        stessa = _key(e.get('citta')) == citta
        if not stessa and (e.get('prov') or '').upper() != prov:
            continue
        cand.append((0 if stessa else 1, max(e['d_start'], oggi),
                     e['d_start'], (e.get('nome') or ''), e))
    cand.sort(key=lambda t: t[:4])
    righe = []
    for _, _, _, _, e in cand[:limite]:
        href = (f"/eventi/{slug_evento(e)}.html" if ha_pagina(e)
                else f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html")
        # Una mostra iniziata a gennaio e ancora aperta non va etichettata
        # "giovedì 1 gen": per chi legge oggi e' semplicemente in corso.
        if e['d_start'] < oggi:
            quando = "in corso"
        elif e['d_start'] == oggi:
            quando = "oggi"
        elif (e['d_start'] - oggi).days == 1:
            quando = "domani"
        else:
            quando = (data_estesa(e['d_start']).split(' ', 1)[0] + ' '
                      + f"{e['d_start'].day} {MESI[e['d_start'].month - 1]}")
        righe.append(
            f'<li><a href="{href}"><span class="ev-vic-d">{esc(quando)}</span>'
            f'<span class="ev-vic-n">{esc(trunc(e.get("nome") or "", 70))}</span>'
            f'<span class="ev-vic-c">{esc(e.get("citta") or "")}</span></a></li>')
    if righe:
        titolo = (f"Altri eventi vicino a {rec.get('citta')}" if rec.get('citta')
                  else "Altri eventi vicini")
        elenco = f'<ul>{"".join(righe)}</ul>'
    else:
        # Nessun evento vicino in agenda (fuori stagione, o pagina di
        # un'edizione conclusa): la sezione resta lo stesso, perche' i link qui
        # sotto sono l'unico modo in cui questa pagina ne alimenta altre.
        titolo = "Continua a cercare"
        elenco = ''

    # I link di coda. Prima erano due (comune + agenda) e la sezione spariva del
    # tutto quando non c'erano eventi vicini.
    #
    # Il problema che risolvono: le landing - le tre pagine provincia,
    # /eventi/oggi.html e /eventi/weekend.html - all'11/08/2026 ricevevano link
    # interni SOLO da eventi.html e fra loro. Su 241 schede evento, 2 le
    # linkavano. Le schede sono le pagine con l'autorita' vera (posizione 2,7-3,6
    # sulle query per nome), le landing sono quelle che devono sopravvivere alla
    # stagione: "sagre in provincia di Alessandria" ha senso a novembre, "festa
    # d'estate Cassinasco" no. Erano due insiemi che non si toccavano.
    #
    # L'ordine va dal piu' vicino al piu' largo: chi arriva da "festa <comune>"
    # cerca prima il suo comune, poi la sua provincia, e solo dopo "e stasera?".
    #
    # Dal 14/08/2026 nella coda c'e' anche /luoghi.html, ed e' l'unico link che
    # quella pagina riceve dal corpo di qualcosa che ha traffico. Sta subito
    # dopo il comune e prima della provincia perche' risponde alla stessa
    # domanda ("cos'altro c'e' qui?") con l'altra meta' della risposta: non un
    # altro evento, un posto dove andare quando eventi non ce ne sono.
    coda = []
    mio_hub = (hub or {}).get(citta)
    if mio_hub:
        coda.append(f'<a href="/eventi/comune/{mio_hub["slug"]}.html">Tutti gli eventi'
                    f'{a_citta(mio_hub["nome"])}</a>')
    lg = link_luoghi(rec.get('citta'), prov)
    if lg:
        coda.append(lg)
    if prov in PROVINCE_PUBBLICATE:
        nome_prov = PROVINCE_NOMI[prov]
        coda.append(f'<a href="/sagre-provincia-{slugify(nome_prov)}.html">'
                    f'Le sagre in provincia di {esc(nome_prov)}</a>')
        coda.append(f'<a href="{href_eventi_prov(prov)}">Eventi per bambini in '
                    f'provincia di {esc(nome_prov)}</a>')
    coda.append('<a href="/eventi/oggi.html">Cosa c\'è oggi</a>')
    coda.append('<a href="/eventi/weekend.html">Questo weekend</a>')
    coda.append('<a href="/eventi.html">Tutta l\'agenda DAOP</a>')
    return ('<section class="ev-vicini" aria-labelledby="ev-vicini-t">'
            f'<h2 id="ev-vicini-t">{esc(titolo)}</h2>'
            f'{elenco}'
            f'<p class="ev-vic-all">{" · ".join(coda)}</p>'
            '</section>')


def render_pagina(rec, css, nav, foot, oggi, orfano=False, vicini=(), hub=None):
    """HTML completo di una pagina evento.

    orfano: l'evento e' sparito dal foglio pur non essendo ancora passato.
    Vuol dire che e' stato annullato, oppure rinominato - e in quel caso
    esiste gia' un'altra pagina con lo stesso contenuto. In entrambi i casi
    non deve stare in indice.

    Il timbro rec['ritirata'] e' un passo oltre il noindex: la pagina smette di
    descrivere un appuntamento (niente Event, niente firma di verifica, niente
    calendario) e dichiara di essere stata ritirata. Lo mette scrivi_pagine."""
    e = dict(rec)
    e['d_start'] = datetime.date.fromisoformat(rec['d_start'])
    e['d_end'] = datetime.date.fromisoformat(rec['d_end'])
    concluso = e['d_end'] < oggi
    # Orfana e non ancora passata = RITIRATA. Le due cose vanno tenute distinte:
    # una pagina CONCLUSA racconta una cosa che e' avvenuta (il permalink resta, e
    # deve restare), una RITIRATA descrive un appuntamento che non c'e' - o non
    # c'e' mai stato. Fino al 18/08/2026 la ritirata usciva identica a una scheda
    # viva, solo con noindex e fuori dalla sitemap: cioe' invisibile a Google e
    # perfettamente leggibile da chiunque avesse il link, firma "verificata da
    # DAOP" e bottone "Aggiungi al calendario" compresi.
    # RITIRATA la dice il timbro nel registro, e nient'altro. Due ragioni per
    # non dedurla qui dai sintomi (orfana + data futura):
    #  - vince sulla data. Il pranzo sociale del 23/08 era orfano fino al 23 e
    #    dal 24 tornava "Edizione conclusa - Questa edizione si e' svolta
    #    domenica 23 agosto" con la firma di verifica al suo posto: la pagina
    #    avrebbe dichiarato SVOLTO un appuntamento che non e' mai esistito;
    #  - il timbro lo mette scrivi_pagine SOLO se la run ha letto un foglio
    #    credibile. Se la lettura va a meta', le orfane di quel giorno restano
    #    pagine normali in noindex - come prima - invece di riscriversi tutte
    #    "ritirata" e finire cosi' online col push automatico.
    ritirata = bool(rec.get('ritirata'))
    url = f"{SITE_URL}/eventi/{rec['slug']}.html"
    nome = (e.get('nome') or '').strip()
    citta = (e.get('citta') or '').strip()
    anno = e['d_start'].year

    descr_txt = (e.get('descr') or '').strip()

    # Il title si costruisce dal nome verso l'esterno: la città non va mai
    # troncata (è metà della query) e il suffisso " | DAOP" si sacrifica prima
    # del contenuto. Si accorcia solo il nome, e solo se serve davvero.
    # Davanti al nome, quando c'è, va la cosa che la gente cerca davvero: i
    # fuochi d'artificio, il luna park, la rievocazione storica.
    gan = gancio(nome, descr_txt)
    titolo_seo = _titolo_evento(nome, citta, anno, gan)

    # La riga che si legge fra i risultati: prima quando e dove (sono le parole
    # della query, "2026" compreso), poi cosa ci trovi. Prima diceva solo le
    # date e ripeteva l'attacco della descrizione, che quasi sempre le ripete
    # un'altra volta ancora.
    testa = periodo_esteso(e) + a_citta(citta)
    attrazioni = richiami(descr_txt)
    if attrazioni:
        testa += f": {elenco_it(attrazioni)}"
    # Le stesse attrazioni, in pagina sotto il titolo. Non è una ripetizione
    # della descrizione: nella descrizione del foglio "fuochi d'artificio" sta
    # scritto "spettacolo pirotecnico" a metà del sesto rigo, e chi arriva dalla
    # ricerca deve vedere subito che è finito nel posto giusto.
    gancio_html = (f'\n    <p class="ev-gancio">{esc(elenco_it(attrazioni).capitalize())}</p>'
                   if attrazioni else '')
    meta_d = trunc(f"{testa}. {descr_txt}" if descr_txt
                   else f"{nome}{a_citta(citta)}: {periodo_esteso(e)}.", 152)
    # noindex tiene la scheda ritirata fuori da Google, non fuori da WhatsApp:
    # incollato in chat, il link mostra og:title e og:description, e quelli
    # continuavano a pubblicizzare l'evento. Il titolo lo dice subito.
    if ritirata:
        titolo_seo = trunc(f"Scheda ritirata: {nome}", 60) + " | DAOP"
        meta_d = ("Questa scheda non fa più parte dell'agenda DAOP: l'appuntamento è "
                  "stato annullato o corretto. Vai all'agenda per gli eventi confermati.")

    facts = []
    if e.get('ora'):
        facts.append(f'<li>{CLOCK_SVG}<span><strong>Orario:</strong> {esc(e["ora"])}</span></li>')
    luogo = " · ".join(x for x in [(e.get('luogo') or '').strip(),
                                   (e.get('indirizzo') or '').strip()] if x)
    if luogo:
        facts.append(f'<li>{PIN_SVG}<span><strong>Dove:</strong> {esc(luogo)}</span></li>')
    if e.get('prezzo'):
        facts.append(f'<li>{CAL_SVG}<span><strong>Ingresso:</strong> {esc(e["prezzo"])}</span></li>')
    if e.get('eta'):
        facts.append(f'<li>{USER_SVG}<span><strong>Età:</strong> {esc(e["eta"])}</span></li>')

    if e.get('prenotazione'):
        facts.append(f'<li>{CHECK_SVG}<span><strong>Prenotazione:</strong> '
                     f'{esc(e["prenotazione"])}</span></li>')
    # CHI ORGANIZZA, quando ha una pagina sua. Sta fra la prenotazione e i
    # recapiti perche' e' la stessa domanda dei recapiti - "con chi ho a che
    # fare?" - e la risposta piu' larga viene prima del numero di telefono.
    lr = link_realta(e.get('nome'))
    if lr:
        facts.append(f'<li>{ORG_SVG}<span><strong>Organizzatore:</strong> '
                     f'{lr}</span></li>')
    # I recapiti dell'organizzatore sono la cosa piu' utile che possiamo dare a
    # chi deve decidere oggi: nessuna risposta di un assistente te li da'.
    if contatti_html(e.get('contatto')):
        facts.append(f'<li>{PHONE_SVG}<span><strong>Contatti:</strong> '
                     f'{contatti_html(e["contatto"])}</span></li>')

    # Orario, indirizzo, prezzo, prenotazione e locandina sono le istruzioni per
    # andarci: su una scheda ritirata non ci vanno, perche' non ci si deve andare.
    if ritirata:
        facts = []
    loc = loc_path(e.get('loc'))
    img = (f'<img class="ev-loc" src="{esc(loc)}" alt="Locandina di {esc(nome)}" '
           f'loading="lazy" width="900" height="1200">') if loc and not ritirata else ''

    if concluso and not ritirata:
        avviso = ('<div class="ev-over"><strong>Edizione conclusa</strong>'
                  f'Questa edizione si è svolta {periodo_esteso(e).lower()}. '
                  'Se la manifestazione torna, aggiorniamo questa pagina con le nuove date. '
                  'Intanto trovi tutto quello che c\'è in programma nell\'<a href="/eventi.html">agenda DAOP</a>.</div>')
        azioni = '<div class="ev-actions"><a class="btn btn-navy" href="/eventi.html">Vedi gli eventi di oggi</a></div>'
        barra = ''
    elif ritirata:
        avviso = ('<div class="ev-over"><strong>Scheda ritirata</strong>'
                  'Questo appuntamento non è più nell\'agenda DAOP: l\'abbiamo tolto '
                  'perché è stato annullato, è cambiato, oppure perché la scheda era '
                  'sbagliata. Quello che leggi qui sotto non è confermato: per sapere '
                  'cosa c\'è davvero in programma vai all\'<a href="/eventi.html">agenda '
                  'DAOP</a>.</div>')
        # NIENTE "Aggiungi al calendario" e niente "Come arrivare": erano i due
        # bottoni piu' dannosi di tutti - scrivevano in agenda, e mandavano in
        # macchina, verso un appuntamento che non esiste.
        azioni = ('<div class="ev-actions"><a class="btn btn-navy" href="/eventi.html">'
                  'Vedi cosa c\'è in programma</a></div>')
        barra = ''
    else:
        avviso = ''
        # .btn da sola dà solo la forma: senza modificatore l'ancora resta un
        # link blu di sistema. I modificatori che il CSS del sito definisce
        # davvero sono btn-primary, btn-navy e btn-teal.
        bottoni = [f'<a class="btn btn-navy" href="{esc(gcal_url(e))}" target="_blank" rel="noopener">Aggiungi al calendario</a>']
        if maps_url(e):
            bottoni.append(f'<a class="btn btn-teal" href="{esc(maps_url(e))}" target="_blank" rel="noopener">Come arrivare</a>')
        bottoni.append('<a class="ev-back" href="/eventi.html">Torna all\'agenda</a>')
        azioni = '<div class="ev-actions">' + "".join(bottoni) + '</div>'
        barra = barra_azioni(e)

    # CHI sta sotto l'avviso, su un'EDIZIONE CONCLUSA. Quella pagina non ha
    # niente da dare: chi ci arriva da Google ha appena scoperto che la festa
    # e' finita, e "e allora cosa faccio?" non e' una domanda che gli stiamo
    # mettendo in testa noi - ce l'ha gia'. Al 28/08/2026 sono 132 schede su
    # 288, cioe' il 46%, e prendono traffico vero (il 16/08: 1.237 impressioni).
    # In coda, sotto la firma e gli eventi vicini, quel blocco lo vede chi
    # scorre tutto: circa uno su cento.
    #
    # Dal 19/08 il posto era dell'invito al canale WhatsApp; dal 28/08 e' di
    # GINETTO, perche' a parita' di posto rende di piu' (7 clic dal 71% della
    # pagina contro 4 dal 59%, settimana 12-18/08) e risponde alla domanda
    # giusta - lui risponde ADESSO, il canale rispondeva giovedi'.
    #
    # Dal 04/09/2026 il canale non c'e' piu' affatto, e Ginetto e' rimasto
    # l'unica richiesta del sito. La conseguenza da non disfare: qui sotto era
    # l'invito al canale a occupare la coda dell'articolo, un blocco sopra la
    # fascia di Ginetto. Togliendolo la fascia non si e' spostata di posto -
    # ha ereditato il suo, cioe' e' salita di quell'altezza su ogni scheda.
    #
    # Uno solo, e in un posto solo: Ginetto in cima non si ripete in fondo,
    # che sarebbe la stessa richiesta fatta due volte a chi ha gia' detto di
    # no una volta.
    #
    # NON vale per le RITIRATE, che restano come prima: quella pagina dichiara
    # di non essere attendibile e manda all'agenda, e presentare qualcosa di
    # nostro in cima a una scheda che stiamo smentendo e' chiedere fiducia nel
    # punto esatto in cui l'abbiamo appena tolta. Stessa logica per cui li'
    # spariscono i fatti e i due bottoni.
    in_cima = concluso and not ritirata
    ginetto_alto = blocco_ginetto(citta, alto=True) if in_cima else ''
    ginetto_coda = '' if in_cima else blocco_ginetto(citta)

    ev_obj = event_jsonld(e, url)
    ev_obj["@id"] = f"{url}#event"
    if concluso:
        ev_obj["eventStatus"] = "https://schema.org/EventScheduled"
    # La scheda dichiara anche CHI l'ha controllata e QUANDO: e' la traduzione in
    # dati strutturati della firma visibile. lastReviewed/reviewedBy esistono
    # apposta, e chi cita la pagina trova il nome della fonte accanto al dato.
    controllo = rec.get('last_seen') or rec.get('updated') or rec.get('first_seen')
    webpage = {
        "@type": "WebPage",
        "@id": url,
        "url": url,
        "name": titolo_seo,
        "inLanguage": "it-IT",
        "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
        "about": {"@id": f"{url}#event"},
        "publisher": {"@id": ORG_ID},
        "reviewedBy": {"@id": ORG_ID},
    }
    if rec.get('first_seen'):
        webpage["datePublished"] = rec['first_seen']
    if rec.get('updated'):
        webpage["dateModified"] = rec['updated']
    if controllo:
        webpage["lastReviewed"] = controllo
    if ritirata:
        # I dati strutturati sono la stessa promessa dell'HTML in una lingua che
        # leggono le macchine: se la pagina non certifica piu' niente, qui non
        # devono restare ne' il puntatore all'Event (che sparisce dal grafo) ne'
        # la firma di chi l'ha rivista e quando.
        for _k in ("about", "reviewedBy", "lastReviewed"):
            webpage.pop(_k, None)
    organizzazione = {
        "@type": "Organization",
        "@id": ORG_ID,
        "name": "DAOP – Dove Andiamo Oggi Papi",
        "alternateName": "DAOP",
        "url": SITE_URL,
        "logo": f"{SITE_URL}/assets/images/logodaop.png",
        "areaServed": [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE] + ["Piemonte"],
        "description": (f"Associazione delle famiglie di {PROVINCE_TESTO}. Seleziona e "
                        "verifica gli eventi per famiglie del territorio."),
    }
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": nome, "item": url},
        ],
    }
    # Su una scheda ritirata l'Event non entra nel grafo: dichiararlo - anche
    # come "annullato" - vorrebbe dire garantire a un assistente che
    # l'appuntamento e' esistito con quei dati, e nel caso della riga sbagliata
    # non e' vero. WebPage / Organization / BreadcrumbList descrivono la PAGINA,
    # e quelli restano veri.
    grafo = ([webpage, organizzazione, breadcrumb] if ritirata
             else [ev_obj, webpage, organizzazione, breadcrumb])
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)

    corpo = corpo_descrizione(descr_txt)
    famiglie = (blocco_famiglie(rec, vicini, oggi, hub=hub)
                if vicini and not ritirata else '')
    consiglio = '' if ritirata else blocco_daop(e)
    # "Consigliato DAOP" nel foglio e' gia' un giudizio, dato riga per riga:
    # tenerlo dentro il database e non mostrarlo era buttarlo via.
    consigliato_badge = (f'<p class="ev-scelto">{STAR_SVG} Consigliato da DAOP</p>'
                         if si(e.get('consigliato')) and not ritirata else '')
    firma = firma_daop(rec, oggi, ritirata=ritirata)
    altri = blocco_vicini(rec, vicini, oggi, hub=hub) if vicini else ''

    # Una ritirata esce dall'indice, e il perche' e' gia' scritto venti righe
    # piu' su per l'Event: se non dichiariamo a un assistente che quei dati
    # sono veri, non possiamo offrirli a Google come risposta. Fino al
    # 31/08/2026 sei schede ritirate erano index, follow — cioe' pagine che
    # dicono di se stesse di non essere attendibili e che Google poteva
    # mostrare. Erano gia' fuori dalla sitemap: e' l'altro verso dello stesso
    # invariante, e questa riga lo chiude.
    #
    # RESTA ONLINE, come sempre: il cartello serve a chi arriva da un link gia'
    # girato, ed e' proprio quella la persona da avvisare. E' la regola di
    # MIN_LANDING, applicata a una scheda.
    robots = 'noindex, follow' if orfano or ritirata else 'index, follow'

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo_seo)}</title>
<meta name="description" content="{esc(meta_d)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo_seo)}">
<meta property="og:description" content="{esc(meta_d)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{esc(loc_url(e.get('loc')) or DEFAULT_IMG)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(trunc(titolo_seo, 60))}">
<meta name="twitter:description" content="{esc(trunc(meta_d, 120))}">
<meta name="twitter:image" content="{esc(loc_url(e.get('loc')) or DEFAULT_IMG)}">
<meta name="daop:evento" content="{esc(nome)}">
<meta name="daop:citta" content="{esc(citta)}">
<meta name="daop:provincia" content="{esc(e['prov'])}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script src="/assets/js/locandina.js" defer></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>{esc(trunc(nome, 60))}</span>
    </div>
    {consigliato_badge}<h1>{esc(nome)}</h1>
    <p class="ev-when">{esc(periodo_esteso(e))}{' · ' + esc(citta) if citta else ''}</p>{gancio_html}
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  {avviso}{ginetto_alto}
  <ul class="ev-facts">
    {"".join(facts)}
  </ul>
  {img}
  <div class="ev-body">
    {corpo}
  </div>
  {famiglie}
  {consiglio}
  {azioni}
  {firma}
  {altri}
</article>
{ginetto_coda}</main>
{foot}
{barra}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# SCHEDA SPOSTATA: quando una correzione cambia l'INDIRIZZO della pagina
#
# PERCHE' ESISTE (30/08/2026): sul foglio la "27a Sagra dello Gnocco" era segnata
# a Mombarcaro, ma si fa a Bricco de' Faule, frazione di CHERASCO. Corretto il
# comune e rigenerato il sito, la pagina "non si era aggiornata": lo slug
# contiene il comune, quindi la correzione non ha modificato la scheda, ne ha
# fatta NASCERE una nuova all'indirizzo giusto e ha lasciato la vecchia dov'era,
# con dentro il dato sbagliato e una mappa a 40 km da dove si mangia. Fuori
# indice si', ma perfettamente leggibile da chiunque avesse il link - il canale,
# un WhatsApp, un post - cioe' esattamente le persone a cui la correzione
# serviva. E' il difetto della scheda ritirata (18/08) un passo piu' in la':
# li' la pagina restava viva, qui resta viva E smentita da un'altra pagina
# nostra.
#
# RITIRATA e SPOSTATA non sono la stessa cosa e non vanno rese uguali:
#   - RITIRATA = l'appuntamento non c'e' (annullato, o mai esistito). La pagina
#     lo dichiara e manda all'agenda: e' tutto quello che puo' dare.
#   - SPOSTATA = l'appuntamento c'e', e' solo altrove. Qui non c'e' niente da
#     raccontare e niente da smentire: c'e' da portare la persona alla scheda
#     giusta, subito. Tenere "il contesto" (date, luogo, descrizione vecchia)
#     vorrebbe dire tenere in pagina proprio la riga che abbiamo corretto.
#
# Il timbro rec['spostata'] sta nel REGISTRO ed e' permanente come l'altro, e non
# si deduce a ogni run: il 1 settembre la sagra e' finita, la pagina vecchia non
# e' piu' "orfana" (la data e' passata, non manca piu' nessuno dal foglio) e
# senza timbro tornerebbe a stampare per sempre "Edizione conclusa" con il comune
# sbagliato. Si toglie da solo se quello slug ricompare nel foglio, come la
# ritirata: e' il modo di rimediare a un rimando sbagliato.
# ---------------------------------------------------------------------------


def _erede(slug, rec, reg, visti):
    """Lo slug NUOVO di un evento che ha cambiato indirizzo, o None.

    Un evento futuro sparito dal foglio e' stato annullato oppure rinominato: da
    qui si vedono uguali, e a distinguerli e' solo questo: se fra le righe LETTE
    OGGI ce n'e' una che e' lo stesso appuntamento sotto un altro slug, allora
    non e' sparito, si e' spostato.

    "Lo stesso appuntamento" vuol dire stesse date esatte piu' una delle due
    identita' che la correzione non tocca:
      - lo stesso NOME, e allora e' cambiato il comune (il caso della Sagra
        dello Gnocco: Mombarcaro -> Cherasco);
      - la stessa RIGA del foglio E LO STESSO COMUNE, e allora e' cambiato il
        nome, ma la riga corretta e' quella di prima.

    Le date da sole non bastano: a Ferragosto un paese ha cinque righe negli
    stessi identici giorni, e un rimando alla scheda sbagliata e' peggio del
    problema che stiamo risolvendo. Per lo stesso motivo, se i candidati sono
    piu' di uno non si sceglie: si torna alla scheda ritirata, che a nessuno
    promette niente.

    Il comune sul ramo della riga non e' una cautela in piu': senza, quel ramo
    e' sbagliato per costruzione. 'riga' non e' l'identita' di una riga del
    foglio, e' la sua POSIZIONE in un elenco che si riordina ogni notte - la
    Festa del Fungo di Ciglione e' passata da riga 34 a riga 11 restando lo
    stesso evento. Quindi "stessa riga" vuol dire solo "stesso posto in due
    ordinamenti diversi", che di due eventi non dice niente. Il 02/09/2026
    quel ramo aveva mandato il Palio di Asti su una grigliata a Sant'Albano
    Stura e la Fiera di Villaromagnano su una camminata a San Cristoforo:
    due volte su due, e le uniche due volte che ha deciso da solo. Un nome che
    cambia lascia fermo il comune, quindi chiedere tutti e due non toglie
    nessun caso vero e chiude quello falso."""
    # 'riga' nel registro e' un numero, non una stringa: si confronta dopo
    # averlo reso testo, se no ci si scorda sempre un str() da qualche parte.
    d_i, d_f = rec.get('d_start'), rec.get('d_end')
    nome, riga = _key(rec.get('nome')), str(rec.get('riga') or '').strip()
    citta = _key(rec.get('citta'))
    candidati = []
    for s in visti:
        if s == slug:
            continue
        n = reg.get(s) or {}
        if n.get('d_start') != d_i or n.get('d_end') != d_f:
            continue
        stesso_nome = bool(nome) and _key(n.get('nome')) == nome
        stessa_riga = (bool(riga) and str(n.get('riga') or '').strip() == riga
                       and bool(citta) and _key(n.get('citta')) == citta)
        if stesso_nome or stessa_riga:
            candidati.append(s)
    return candidati[0] if len(candidati) == 1 else None


def _destinazione(rec, reg):
    """Dove porta davvero una scheda spostata, seguendo la catena.

    La stessa riga puo' essere corretta due volte (prima il comune, poi il nome):
    senza seguire la catena chi arriva dal link piu' vecchio farebbe due salti, e
    il secondo su una pagina che a sua volta non e' piu' quella buona. La lista
    degli slug gia' visti ferma anche un anello (A -> B -> A), che una coppia di
    correzioni fatte e disfatte puo' produrre - e in fondo a un anello si finisce
    su se stessi, cioe' su una pagina che rimanda a se stessa e che nel browser
    non smette piu' di ricaricarsi. Quella non e' una destinazione: si torna a
    stampare la scheda normale."""
    visto, s, meta = set(), rec.get('spostata'), None
    while s and s in reg and s not in visto:
        visto.add(s)
        meta = s
        s = (reg[s] or {}).get('spostata')
    return meta if meta != rec.get('slug') else None


def render_spostata(rec, nuovo, css, nav, foot):
    """La pagina di una scheda spostata: un cartello, non una scheda.

    Del vecchio resta solo il NOME dell'evento, che serve a chi arriva a capire
    di essere nel posto giusto. Date, luogo, descrizione e locandina no: sono la
    riga che abbiamo appena corretto, e questa e' la pagina che quella riga
    continuava a mostrare a chi aveva il link.

    Due scelte che a occhio non si vedono:

    - il canonical punta alla pagina NUOVA e qui NON si mette noindex. Sono due
      segnali opposti sulla stessa pagina, e un noindex accanto a un canonical
      che indica altrove rischia di far passare il noindex proprio alla pagina
      buona. Fuori dalla sitemap ci va lo stesso: la lista che scrivi_pagine
      restituisce la salta.
    - il refresh a 0 secondi e' il piu' vicino a un 301 che si possa scrivere su
      un sito statico (GitHub Pages serve file, non regole di redirect), e Google
      lo legge come un redirect. Il cartello sotto e' per chi il refresh non ce
      l'ha: le anteprime dei link, i lettori di schermo, chi torna indietro."""
    nome = (rec.get('nome') or '').strip()
    citta = (nuovo.get('citta') or '').strip()
    url = f"{SITE_URL}/eventi/{nuovo['slug']}.html"
    titolo = trunc(f"Scheda spostata: {nome}", 60) + " | DAOP"
    # og:description e' quello che si legge quando il link vecchio viene
    # incollato in chat: deve dire "e' altrove", non ripubblicizzare l'evento.
    meta_d = (f"La scheda di questo appuntamento si è spostata{a_citta(citta)}: "
              "vai alla versione aggiornata sull'agenda DAOP.")
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="0; url={url}">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(meta_d)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(meta_d)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(trunc(titolo, 60))}">
<meta name="twitter:description" content="{esc(trunc(meta_d, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}</style>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>Scheda spostata</span>
    </div>
    <h1>{esc(nome)}</h1>
    <p class="ev-when">Questa scheda si è spostata</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  <div class="ev-over"><strong>Scheda spostata</strong>
  Abbiamo corretto questa scheda, e la correzione le ha cambiato indirizzo:
  quella buona{a_citta(esc(citta))} è <a href="{url}">a questa pagina</a>.
  Ci arrivi da solo in un istante; se non succede, usa il bottone qui sotto.</div>
  <div class="ev-actions">
    <a class="btn btn-navy" href="{url}">Vai alla scheda aggiornata</a>
    <a class="ev-back" href="/eventi.html">Torna all'agenda</a>
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


def scrivi_pagine(events, hub=None):
    """Genera/aggiorna le pagine evento.

    Restituisce {slug: data_ultima_modifica} per la sitemap. La data e' quella
    in cui la pagina e' cambiata davvero, non quella della run: dichiarare 35
    pagine "modificate oggi" a ogni giro e' falso, e Google smette di dare peso
    a <lastmod> quando lo trova inaffidabile."""
    reg, nuovi, visti = aggiorna_registro(events)
    if not reg:
        print("[genera_eventi] nessuna pagina evento da generare")
        return {}
    os.makedirs(PAGINE_DIR, exist_ok=True)
    css, nav, foot = _guscio()
    oggi = datetime.date.today()
    conclusi = cambiate = 0
    orfane = []
    spostate = {}   # slug vecchio -> slug nuovo, per il messaggio e per la sitemap
    # Il timbro e' permanente, quindi si mette solo se la run ha visto un foglio
    # CREDIBILE. Se un giorno la lettura del foglio va a meta' (rete, quota,
    # colonne spostate), senza questa guardia mezzo sito si timbrerebbe ritirato
    # in un colpo, e a mano non si torna indietro. Le pagine di oggi non
    # sparirebbero comunque: restano fuori indice per un giorno e la run dopo le
    # rimette a posto.
    # Il paragone va fatto con quello che il foglio DOVREBBE far vedere OGGI,
    # non col registro intero: il registro non perde mai niente - le edizioni
    # concluse restano, e' tutto il suo scopo - quindi cresce e basta, mentre gli
    # eventi in programma restano sempre un centinaio. Con len(reg) la soglia
    # scavalca il massimo raggiungibile e la guardia si spegne da sola: al
    # 30/08/2026 chiedeva 206 pagine viste su 169 possibili, cioe' era ferma su
    # "run non attendibile", e da li' nessuna scheda veniva piu' timbrata. Gli
    # attesi sono le schede non ancora passate e non gia' timbrate: le altre dal
    # foglio non devono arrivare.
    attesi = sum(1 for r in reg.values()
                 if datetime.date.fromisoformat(r['d_end']) >= oggi
                 and not r.get('ritirata') and not r.get('spostata'))
    sano = len(visti) >= max(20, attesi // 2)
    if not sano:
        print(f"[genera_eventi] ATTENZIONE: solo {len(visti)} eventi con pagina "
              f"su {len(reg)} in registro: run considerata NON attendibile, "
              f"nessuna scheda verra' timbrata come ritirata.")
    for slug, rec in reg.items():
        path = os.path.join(PAGINE_DIR, f"{slug}.html")
        # Un evento ancora futuro che non compare piu' nel foglio e' stato
        # annullato o rinominato. Se rinominato, la pagina nuova esiste gia' e
        # questa e' un doppione: fuori dall'indice e fuori dalla sitemap.
        orfano = slug not in visti and \
            datetime.date.fromisoformat(rec['d_end']) >= oggi
        if slug in visti:
            # Tornata sul foglio: il timbro si toglie da solo. E' anche il modo in
            # cui si rimedia a una ritirata sbagliata - si rimette la riga nel
            # foglio - e la rete di sicurezza se una run legge il foglio a meta'.
            rec.pop('ritirata', None)
            rec.pop('spostata', None)
        elif orfano and sano:
            # Prima di dare per sparito un appuntamento si guarda se e' solo
            # cambiato di indirizzo: correggere il comune o il nome fa nascere la
            # scheda altrove e lascia qui il dato vecchio. Vedi _erede().
            erede = _erede(slug, rec, reg, visti)
            if erede:
                rec['spostata'] = erede
                rec.pop('ritirata', None)
            else:
                rec.setdefault('ritirata', oggi.isoformat())
        # Il rimando vale finche' c'e' il timbro, non solo il giorno della
        # correzione: passata la data questa pagina non e' piu' orfana, e senza
        # timbro tornerebbe a stampare l'edizione conclusa col dato sbagliato.
        dove = _destinazione(rec, reg)
        if dove:
            nuovo = render_spostata(rec, reg[dove], css, nav, foot)
            spostate[slug] = dove
        else:
            nuovo = render_pagina(rec, css, nav, foot, oggi, orfano, vicini=events, hub=hub)
        if orfano and not dove:
            orfane.append(slug)
        if datetime.date.fromisoformat(rec['d_end']) < oggi:
            conclusi += 1
        # riscriviamo solo se cambia: evita commit rumorosi ogni notte
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            rec.setdefault('updated', rec.get('first_seen', oggi.isoformat()))
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        rec['updated'] = oggi.isoformat()
        cambiate += 1
    with open(REGISTRO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_eventi] pagine evento: {len(reg)} totali "
          f"({nuovi} nuove, {cambiate} riscritte, {conclusi} concluse)")
    # Le pagine aperte dal criterio nominale invece che dalla categoria: sono la
    # parte nuova e la piu' facile da sbagliare, e una pagina evento non si
    # cancella piu'. Stamparle per nome e' l'unico modo perche' qualcuno se ne
    # accorga finche' sono poche.
    nominali = [r for r in reg.values()
                if (r.get('categoria') or '') != 'Sagra & Festa'
                and not any(w in (r.get('nome') or '').lower() for w in SAGRA_KW)]
    if nominali:
        print(f"[genera_eventi] di cui {len(nominali)} aperte dal nome proprio "
              f"(non sagre):")
        for r in sorted(nominali, key=lambda r: (r.get('citta') or '', r.get('nome') or '')):
            print(f"[genera_eventi]   {r.get('citta') or '?'} · "
                  f"{(r.get('nome') or '')[:56]} "
                  f"[{r.get('categoria') or '?'}, {len((r.get('descr') or '').strip())} car]")
    # Il valore aggiunto e' l'unica cosa che un assistente non trova altrove:
    # se e' a zero la pagina resta un doppione del volantino, e va detto.
    con_giudizio = sum(1 for r in reg.values()
                       if any((r.get(k) or '').strip() for k in CAMPI_DAOP))
    print(f"[genera_eventi] schede con giudizio DAOP: {con_giudizio}/{len(reg)}")
    # Distinguiamo i due casi: la colonna non c'e' (va aggiunta) oppure c'e' ed
    # e' vuota (va compilata). Dire "aggiungi Età consigliata" quando nel foglio
    # c'e' gia' fa perdere tempo a chi legge.
    vuote = [nomi[0] for campo, nomi in CAMPI_DAOP.items()
             if campo in COLONNE_VISTE
             and not any((r.get(campo) or '').strip() for r in reg.values())]
    if vuote:
        print("[genera_eventi]   colonne presenti ma mai compilate: "
              + ", ".join(f'"{n}"' for n in vuote))
    timbrate = [s_ for s_, r in reg.items() if r.get('ritirata')]
    if timbrate:
        print(f"[genera_eventi] schede ritirate (permanenti): {len(timbrate)}")
    trasferite = [s_ for s_, r in reg.items() if r.get('spostata')]
    if spostate:
        print(f"[genera_eventi] schede SPOSTATE (permanenti): {len(spostate)}. "
              f"L'evento e' stato corretto e la sua pagina e' nata a un altro "
              f"indirizzo: la vecchia resta come RIMANDO, fuori dalla sitemap. "
              + "; ".join(f"{a} -> {b}" for a, b in sorted(spostate.items())))
    if orfane:
        print(f"[genera_eventi] ATTENZIONE: {len(orfane)} pagine di eventi futuri "
              f"spariti dal foglio (annullati o sbagliati; i rinominati diventano "
              f"un rimando e non entrano qui), riscritte come SCHEDA RITIRATA "
              f"(senza Event nei dati strutturati, senza firma "
              f"di verifica, senza calendario), in noindex e fuori dalla sitemap: "
              f"{', '.join(sorted(orfane))}")
    # Fuori dalla sitemap le orfane di oggi E tutte le timbrate: una ritirata non
    # rientra in sitemap il giorno dopo la sua data, quando smette di essere orfana.
    fuori = set(orfane) | set(timbrate) | set(trasferite)
    return {s: r['updated'] for s, r in sorted(reg.items()) if s not in fuori}


# ---------------------------------------------------------------------------
# PAGINA METODO
#
# Perche': un motore o un assistente puo' capire COSA pubblica DAOP dai dati
# strutturati, ma non CHI e' DAOP ne' perche' dovrebbe fidarsi. Questa pagina
# risponde a quello, ed e' il bersaglio del link "Scheda verificata da DAOP"
# che sta su ogni scheda evento.
#
# Viene rigenerata a ogni run come le pagine evento: cosi' i numeri sono veri
# (quante schede, quanti comuni, ultimo aggiornamento) invece di essere una
# frase scritta una volta e diventata falsa il mese dopo.
# ---------------------------------------------------------------------------
METODO_PATH = os.path.join(ROOT, "metodo.html")

METODO_CSS = """
.met-num{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:26px 0}
.met-num div{border:1px solid rgba(45,74,92,.14);border-radius:14px;padding:14px 16px}
.met-num b{display:block;font-size:1.6rem;line-height:1.1;color:var(--teal,#6ba5a8)}
.met-num span{font-size:.88rem;opacity:.78}
.ev-wrap h2{margin:34px 0 10px;font-size:1.3rem}
.ev-wrap h3{margin:20px 0 4px;font-size:1.02rem;color:var(--navy,#2d4a5c)}
/* Il reset del sito azzera i margini dei <p>: senza questo i paragrafi della
   pagina si toccano e sembrano un muro di testo. */
.ev-wrap p{margin:0 0 12px;line-height:1.7}
.ev-wrap li{line-height:1.7}
.ev-wrap p a,.ev-wrap li a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
.met-passi{padding-left:20px;margin:10px 0;display:grid;gap:8px}
.met-passi>li{padding-left:4px}
.met-lim{border:1px solid rgba(45,74,92,.16);border-radius:14px;padding:16px 18px;margin:18px 0}
.met-lim ul{margin:8px 0 0 18px;display:grid;gap:6px}
.met-cta{display:flex;flex-wrap:wrap;gap:12px;margin:22px 0}
"""

METODO_FAQ = [
    ("Chi inserisce gli eventi su DAOP?",
     "Le schede le compilano a mano Patrick Orlando per la provincia di Alessandria e "
     "Alessandra Zaccone per la provincia di Asti, soci fondatori di DAOP. DAOP non "
     "aggrega in automatico da altri siti: ogni scheda passa da una persona prima di "
     "essere pubblicata."),
    ("Da dove arrivano gli eventi?",
     "Da tre strade: le locandine e i canali ufficiali di comuni, pro loco, biblioteche e "
     "associazioni del territorio; le segnalazioni delle famiglie della community DAOP; "
     "e gli organizzatori che ci scrivono direttamente a info@daop.it."),
    ("Come viene verificata una scheda?",
     "I dati vengono dalla comunicazione ufficiale di chi organizza: locandina, pagina o "
     "avviso del comune, della pro loco o dell'associazione. Prima di pubblicare "
     "controlliamo che data, luogo, orario e prezzo ci siano e siano coerenti con quella "
     "fonte. Se un dato non è confermato non lo inventiamo: lo scriviamo come da "
     "verificare. Ogni scheda riporta la data dell'ultimo controllo."),
    ("Ogni quanto vengono aggiornati gli eventi?",
     "L'agenda si rigenera automaticamente ogni notte: gli eventi passati escono, quelli "
     "nuovi entrano e le schede modificate vengono riscritte. La data dell'ultimo "
     "controllo sulla singola scheda è quella dell'ultima volta che l'abbiamo riscontrata, "
     "non quella dell'aggiornamento automatico."),
    ("Che zona copre DAOP?",
     f"Le province di {province_in_elenco(PROVINCE_PUBBLICATE)}, in Piemonte. Fuori da lì "
     "non pubblichiamo: preferiamo coprire bene un territorio che male mezzo Nord Italia."),
    ("Come segnalo un errore o propongo un evento?",
     "Scrivendo a info@daop.it, oppure dai profili social DAOP di Alessandria e Asti. "
     "Le correzioni su un evento già pubblicato hanno la precedenza su tutto il resto."),
]


def scrivi_metodo(events):
    """Genera /metodo.html: chi è DAOP, come verifica, ogni quanto aggiorna."""
    reg = carica_registro()
    oggi = datetime.date.today()
    comuni = len({_key(e.get('citta')) for e in events if (e.get('citta') or '').strip()})
    schede = len(reg)
    # Province ricavate dagli eventi VERI in agenda, non da una costante scritta a
    # mano: il contatore diceva "2 province" ed era rimasto indietro rispetto al
    # filtro dei dati. Cosi' se una provincia resta senza eventi non viene contata.
    prov_agenda = {e.get('prov') for e in events if e.get('prov')}
    n_province = len(prov_agenda)
    nomi_province = province_in_elenco(prov_agenda) or "—"
    url = METODO_URL
    titolo = "Come verifichiamo gli eventi | DAOP"
    descr = ("Chi inserisce gli eventi su DAOP, da dove arrivano, come li verifichiamo e "
             "ogni quanto aggiorniamo le schede per le famiglie di "
             f"{province_in_elenco(PROVINCE_PUBBLICATE)}.")

    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagina metodo saltata: {err}")
        return

    faq = "".join(
        f'<h3>{esc(q)}</h3><p>{esc(a)}</p>' for q, a in METODO_FAQ)

    grafo = [
        {"@type": "AboutPage", "@id": url, "url": url, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID},
         "dateModified": oggi.isoformat()},
        {"@type": "Organization", "@id": ORG_ID,
         "name": "DAOP – Dove Andiamo Oggi Papi", "alternateName": "DAOP", "url": SITE_URL,
         "logo": f"{SITE_URL}/assets/images/logodaop.png", "foundingDate": "2023",
         "description": (f"Associazione delle famiglie di {PROVINCE_TESTO}. Seleziona e "
                         "verifica a mano gli eventi per famiglie del territorio."),
         "areaServed": [PROVINCE_NOMI[c] for c in PROVINCE_PUBBLICATE] + ["Piemonte"],
         "founder": {"@type": "Person", "name": "Patrick Orlando"},
         "member": [{"@type": "Person", "name": "Patrick Orlando"},
                    {"@type": "Person", "name": "Alessandra Zaccone"}],
         "email": "info@daop.it",
         "sameAs": ["https://www.instagram.com/daop_alessandria/",
                    "https://www.instagram.com/daop_asti/",
                    "https://www.facebook.com/daopalessandria/",
                    "https://www.facebook.com/daopasti",
                    "https://www.youtube.com/@DOVEANDIAMOOGGIPAPI"]},
        {"@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in METODO_FAQ]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Come verifichiamo gli eventi",
             "item": url}]},
    ]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)

    html_out = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{METODO_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Come verifichiamo gli eventi</span>
    </div>
    <h1>Come DAOP sceglie e verifica gli eventi</h1>
    <p class="ev-when">Il metodo dietro l'agenda di {nomi_province}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">

  <p>DAOP non è un aggregatore automatico. Ogni evento che leggi sul sito è stato scelto
  e inserito da una persona che vive in questo territorio, con data, luogo, orario,
  prezzo e fascia d'età controllati prima della pubblicazione. Questa pagina spiega chi
  lo fa, come, e ogni quanto.</p>

  <div class="met-num">
    <div><b>{len(events)}</b><span>eventi in agenda adesso</span></div>
    <div><b>{schede}</b><span>schede evento dedicate</span></div>
    <div><b>{comuni}</b><span>comuni coperti</span></div>
    <div><b>{n_province}</b><span>province: {nomi_province}</span></div>
  </div>

  <h2>Chi inserisce gli eventi</h2>
  <p><strong>Patrick Orlando</strong> — fondatore e presidente di DAOP, papà e ingegnere.
  Ha fondato DAOP nel 2023, ha costruito <a href="/ginetto.html">Ginetto AI</a> e
  <a href="/piattosano.html">Il Piatto Sano</a> e ha scritto i
  <a href="/libri.html">libri per famiglie</a> della collana. Cura la provincia di
  Alessandria.</p>
  <p><strong>Alessandra Zaccone</strong> — socia fondatrice e curatrice per la provincia
  di Asti. Seleziona e verifica le proposte della community, aggiorna le pagine DAOP Asti
  e tiene il dialogo con le famiglie del territorio.</p>
  <p>Sono due persone, non una redazione: è il motivo per cui copriamo bene due province
  invece che male mezza regione.</p>

  <h2>Come nasce una scheda</h2>
  <ol class="met-passi">
    <li><strong>Raccolta.</strong> Locandine e canali ufficiali di comuni, pro loco,
    biblioteche e associazioni; segnalazioni delle famiglie della community;
    organizzatori che ci scrivono direttamente.</li>
    <li><strong>Inserimento.</strong> Ogni evento entra nel database DAOP con nome, date,
    orario, luogo e indirizzo, prezzo, fascia d'età e descrizione scritta da noi. Niente
    aggregazione automatica da altri siti: la scheda passa da una persona prima di essere
    pubblicata.</li>
    <li><strong>Controllo.</strong> Data, luogo, orario e prezzo li prendiamo dalla
    comunicazione ufficiale di chi organizza e controlliamo che siano completi e coerenti.
    Quello che non è confermato non viene inventato: resta scritto come
    <em>da verificare</em>.</li>
    <li><strong>Pubblicazione.</strong> L'evento entra nell'agenda e, se è una sagra o una
    festa, riceve una scheda con URL dedicata che resta online anche dopo, così l'anno
    dopo ritrovi la stessa pagina aggiornata.</li>
    <li><strong>Manutenzione.</strong> Gli eventi conclusi escono dall'agenda, le schede
    modificate vengono riscritte e ognuna porta in fondo la data dell'ultimo controllo.</li>
  </ol>

  <h2>Ogni quanto aggiorniamo</h2>
  <p>L'agenda si rigenera <strong>ogni notte</strong>. La data che leggi in fondo a ogni
  scheda ("Ultimo controllo") non è la data della rigenerazione automatica: è l'ultima
  volta che quella scheda è stata riscontrata sui dati DAOP.</p>

  <div class="met-lim">
    <strong>Cosa DAOP non è</strong>
    <ul>
      <li>Non siamo l'organizzatore degli eventi: li raccogliamo e li segnaliamo. Chi
      organizza è indicato nella scheda quando lo conosciamo.</li>
      <li>Non vendiamo biglietti e non gestiamo prenotazioni: per quelle serve
      l'organizzatore.</li>
      <li>Un programma può cambiare o saltare all'ultimo, soprattutto per il meteo. Prima
      di partire, un controllo ai canali dell'organizzatore vale sempre la pena.</li>
    </ul>
  </div>

  <h2>Segnalare un errore o proporre un evento</h2>
  <p>Se trovi un dato sbagliato, scrivici: le correzioni su un evento già pubblicato
  hanno la precedenza su tutto il resto. Se organizzi qualcosa per famiglie in provincia
  di Alessandria o Asti, mandaci locandina, date e contatti.</p>
  <div class="met-cta">
    <a class="btn btn-navy" href="mailto:info@daop.it?subject=Correzione%20su%20un%20evento%20DAOP">Segnala una correzione</a>
    <a class="btn btn-teal" href="mailto:info@daop.it?subject=Proposta%20evento%20per%20DAOP">Proponi un evento</a>
  </div>

  <h2>Domande frequenti</h2>
  {faq}

  <h2>Dove trovi DAOP</h2>
  <p><a href="{ZONE_HREF}">Le pagine della tua zona</a>, una per provincia ·
  <a href="/eventi.html">L'agenda eventi</a> di {nomi_province} ·
  <a href="/ginetto.html">Ginetto AI</a>, l'assistente che risponde alle famiglie ·
  <a href="/index.html#chi-siamo">Chi siamo</a> ·
  <a href="/media.html">Rassegna stampa</a></p>

  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
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
    if os.path.exists(METODO_PATH) and \
            open(METODO_PATH, encoding='utf-8').read() == html_out:
        print("[genera_eventi] metodo.html invariato")
        return
    with open(METODO_PATH, 'w', encoding='utf-8') as fh:
        fh.write(html_out)
    print(f"[genera_eventi] metodo.html aggiornato ({schede} schede, {comuni} comuni)")


# ---------------------------------------------------------------------------
# PAGINA ZONE
#
# Perche': il credito in fondo a ogni scheda dice DA DOVE arriva quell'evento,
# ma non spiega il modello - che DAOP e' una pagina per provincia, e che una di
# quelle pagine non e' nostra. Trenta link sparsi non lo raccontano; una pagina
# sola si'. Serve anche a chi arriva da fuori zona e vuole sapere se lo copriamo.
#
# Rigenerata a ogni run come le altre: i conteggi per provincia sono veri, e una
# provincia senza eventi in agenda lo dice invece di fingere copertura.
# ---------------------------------------------------------------------------
ZONE_PATH = os.path.join(ROOT, "zone.html")

ZONE_CSS = """
.zon-card{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:18px 20px;margin:16px 0}
.zon-card h2{margin:0 0 2px;font-size:1.25rem}
.zon-n{font-size:.88rem;opacity:.75;margin:0 0 10px}
.zon-link{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.zon-link a{display:inline-block;border:1px solid rgba(45,74,92,.2);border-radius:100px;
  padding:7px 15px;font-size:.9rem;font-weight:600;text-decoration:none;
  color:var(--navy,#2d4a5c)}
.zon-link a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.09)}
.zon-part{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.03em;
  text-transform:uppercase;color:#a75b15;background:rgba(232,149,74,.16);
  border-radius:100px;padding:4px 11px;margin:0 0 8px}
/* Le pagine dei comuni su una riga loro, sotto un'etichetta. In fila ai
   pulsanti di Instagram e Facebook sembravano un quarto profilo di qualcun
   altro, e sono invece l'unica cosa di questa scheda che porta dentro il sito. */
.zon-lab{font-size:.74rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
  opacity:.6;margin:16px 0 0}
.zon-com{margin-top:7px}
.zon-com a{border-style:dashed}
"""


def scrivi_zone(events, hub=None):
    """Genera /zone.html: una provincia, una pagina, e chi la segue."""
    oggi = datetime.date.today()
    per_prov = collections.Counter((e.get('prov') or '').upper() for e in events)
    titolo = "Le pagine della tua zona | DAOP"
    descr = ("Le pagine DAOP provincia per provincia: chi segue "
             f"{province_in_elenco(PROVINCE_PUBBLICATE)} e da dove arrivano gli eventi "
             "per famiglie che pubblichiamo.")

    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagina zone saltata: {err}")
        return

    schede = []
    for sigla in PROVINCE_PUBBLICATE:
        f = fonte_provincia(sigla)
        if not f:
            continue
        n = per_prov.get(sigla, 0)
        # Il conteggio e' quello vero di adesso. Una provincia a zero non viene
        # nascosta: "nessun evento in questo momento" e' un'informazione, una
        # provincia che sparisce dall'elenco sembra un errore del sito.
        quanti = (f"{n} eventi in agenda in questo momento" if n > 1 else
                  "1 evento in agenda in questo momento" if n == 1 else
                  "nessun evento in agenda in questo momento")
        if f['nostra']:
            badge = ''
            testo = (f"La pagina DAOP della provincia di {esc(f['provincia'])}. "
                     f"Gli eventi che trovi qui sul sito nascono da lì: li seleziona e "
                     f"li verifica <strong>{esc(f['curatore'])}</strong>, che vive in questo "
                     f"territorio.")
        else:
            badge = '<span class="zon-part">In collaborazione</span>'
            # Il nome proprio al posto del solo handle: e' la differenza fra
            # "arriva da una pagina" e "c'e' una persona che lo fa".
            chi = (f"<strong>{esc(f['curatore'])}</strong>, con la sua pagina "
                   f"@{esc(f['ig'])}" if f.get('curatore') else
                   f"<strong>@{esc(f['ig'])}</strong>")
            testo = (f"La provincia di {esc(f['provincia'])} la segue {chi} — "
                     "una pagina che non è nostra. Gli eventi di questa zona "
                     "arrivano dal suo lavoro: noi li ospitiamo nell'agenda e "
                     "sull'app, e li accreditiamo su ogni scheda. Se cerchi la "
                     "fonte originale, è quella.")
        link = [f'<a href="{f["url"]}" target="_blank" rel="noopener">Instagram @{esc(f["ig"])}</a>']
        if f.get('fb'):
            link.append(f'<a href="{f["fb"]}" target="_blank" rel="noopener">Facebook</a>')
        # Link all'agenda intera, non a un'ancora per provincia: il filtro di
        # eventi.html e' una <select> in JS, non ci sono ancore per provincia e
        # un "#prov-al" inventato qui atterrerebbe in cima alla pagina.
        link.append('<a href="/eventi.html">Vedi l\'agenda</a>')
        # I comuni della provincia che hanno una pagina loro. E' qui che
        # restano attaccati al resto del sito: una pagina raggiungibile solo
        # dalla sitemap e' una pagina che Google tratta come tale. Riga a
        # parte, pero': in fila ai pulsanti social erano indistinguibili da un
        # altro profilo esterno, e sono l'opposto - portano dentro il sito.
        com = [f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
               for d in sorted((hub or {}).values(), key=lambda x: x['nome'])
               if d['prov'] == sigla]
        com_html = ('<p class="zon-lab">Le pagine dei comuni</p>'
                    f'<div class="zon-link zon-com">{"".join(com)}</div>') if com else ''
        schede.append(
            f'<section class="zon-card">{badge}'
            f'<h2>{esc(f["provincia"])}</h2>'
            f'<p class="zon-n">{quanti}</p>'
            f'<p>{testo}</p>'
            f'<div class="zon-link">{"".join(link)}</div>{com_html}'
            '</section>')

    grafo = [
        {"@type": "WebPage", "@id": ZONE_URL, "url": ZONE_URL, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@id": ORG_ID}, "publisher": {"@id": ORG_ID},
         "dateModified": oggi.isoformat()},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Le pagine della tua zona",
             "item": ZONE_URL}]},
    ]
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)

    html_out = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{ZONE_URL}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{ZONE_URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{METODO_CSS}{ZONE_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Le pagine della tua zona</span>
    </div>
    <h1>Le pagine della tua zona</h1>
    <p class="ev-when">Una provincia, una pagina, una persona che la segue</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">

  <p>DAOP non è un calendario unico calato dall'alto: è una pagina per provincia, tenuta
  da chi in quella provincia ci vive. Il sito e l'app le rimettono insieme in un'agenda
  sola, ma ogni evento continua ad arrivare da una pagina precisa — ed è scritto in fondo
  a ogni scheda.</p>

  {"".join(schede)}

  <h2>Perché lo scriviamo</h2>
  <p>Perché una provincia non è coperta allo stesso modo delle altre, e nasconderlo
  sarebbe la cosa sbagliata. Dove c'è un curatore DAOP, gli eventi li scegliamo noi. Dove
  c'è una collaborazione, il lavoro è di qualcun altro e il nome giusto da leggere è il
  loro. In entrambi i casi chi organizza l'evento resta l'organizzatore: noi lo
  segnaliamo, non lo produciamo.</p>

  <h2>Vuoi che arriviamo nella tua provincia?</h2>
  <p>Se segui già gli eventi per famiglie della tua zona — una pagina, un gruppo, un
  blog — il modello è questo: tu continui a fare il tuo lavoro sulla tua pagina, noi lo
  portiamo dentro l'agenda e ti accreditiamo. Scrivici.</p>
  <div class="met-cta">
    <a class="btn btn-navy" href="mailto:info@daop.it?subject=Collaborazione%20per%20la%20mia%20provincia">Proponi la tua zona</a>
    <a class="btn btn-teal" href="/metodo.html">Come verifichiamo gli eventi</a>
  </div>

  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
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
    if os.path.exists(ZONE_PATH) and \
            open(ZONE_PATH, encoding='utf-8').read() == html_out:
        print("[genera_eventi] zone.html invariato")
        return
    with open(ZONE_PATH, 'w', encoding='utf-8') as fh:
        fh.write(html_out)
    print(f"[genera_eventi] zone.html aggiornato ({len(schede)} province)")


# ---------------------------------------------------------------------------
# PAGINE COMUNE
#
# Perche': in Search Console le query di comune ("festa novi ligure oggi",
# "sagre provincia di alessandria oggi") fanno decine di impressioni in nona
# posizione e zero clic, perche' ci arriviamo con l'agenda generica. E' lo
# stesso problema che le pagine evento hanno risolto per le query di singola
# sagra, un piano sopra.
#
# Il rischio qui e' peggiore della pagina magra: una serie di pagine per
# localita', tutte uguali tranne il nome del posto, e' quello che Google chiama
# doorway page, e la penalizzazione non colpisce quelle pagine ma il dominio.
# La differenza fra una doorway page e un hub locale vero e' una sola: la
# pagina deve contenere qualcosa che l'agenda non da'. Qui e' il raggruppamento
# per manifestazione (le 13 serate della patronale sono UNA cosa, non 13), i
# luoghi e le pro loco che ricorrono, e le feste che tornano ogni anno.
#
# Per questo la soglia sta scritta nel codice e non nella testa di chi genera.
# ---------------------------------------------------------------------------
COMUNI_DIR = os.path.join(PAGINE_DIR, "comune")
STORICO_PATH = os.path.join(ROOT, "data", "storico-comuni.json")
REGISTRO_COMUNI = os.path.join(ROOT, "data", "pagine-comune.json")

# Chi prende una pagina lo decidono le soglie qui sotto, e nient'altro. Fino a
# ieri c'era anche una whitelist dei comuni piu' grandi, per paura che un paese
# di 400 abitanti producesse una doorway page. Era la difesa sbagliata al posto
# giusto: teneva fuori Villaromagnano - 9 eventi e 3 manifestazioni diverse -
# per la popolazione, cioe' per un dato che non dice niente su quanto la pagina
# abbia da raccontare. A tenere lontane le pagine vuote bastano il numero e la
# varieta', che guardano il contenuto: ed e' il contenuto, non la taglia del
# comune, la sola cosa che distingue un hub locale da una doorway page.

# Le soglie. Quattro eventi e tre cose diverse: sotto, la pagina non ha niente
# da dire che l'agenda non dica meglio.
MIN_EVENTI_HUB = 4
MIN_VARIETA_HUB = 3
# Quante pillole di comune restano in vista sotto "Vai al comune": vedi
# blocco_comuni(). Otto riempie una riga su un desktop stretto e due sul
# telefono, che e' quanto un indice puo' prendersi stando sopra il primo evento.
MAX_COMUNI_APERTI = 8
FINESTRA_HUB = 365      # giorni di storico che contano per la soglia
MEMORIA_STORICO = 800   # ~2 anni: bastano a dire "torna ogni anno"


def chiavi_gruppo(terne):
    """La chiave di raggruppamento di ogni evento, date le terne
    (manifestazione, nome, slug).

    Chi ha una manifestazione sta con la sua manifestazione. Chi non ce l'ha ma
    si chiama COME una manifestazione presente e' la riga "cappello" del foglio
    (succede: "Alla (Ri)scoperta delle Favole Disney" esiste sia come
    manifestazione sia come riga singola), e va nello stesso gruppo, non in uno
    nuovo con lo stesso identico titolo. Tutti gli altri stanno per conto loro."""
    terne = list(terne)
    manifesti = {_key(m) for m, _, _ in terne if (m or '').strip()}
    out = []
    for m, nome, sl in terne:
        if (m or '').strip():
            out.append(_key(m))
        elif _key(nome) in manifesti:
            out.append(_key(nome))
        else:
            out.append(f'solo::{sl}')
    return out


def varieta(terne):
    """Quante cose DIVERSE succedono in un comune.

    Le 18 serate di San Liberato a Sant'Albano Stura contano 1, non 18. Senza
    questo numero il comune con piu' eventi in assoluto (18) sarebbe il primo
    candidato a una pagina "Eventi a Sant'Albano Stura" che in realta' e' il
    programma di una festa sola, mentre Novi Ligure - 7 eventi, 5 cose diverse,
    e la domanda di ricerca vera - resterebbe fuori."""
    return len(set(chiavi_gruppo(terne)))


def carica_storico():
    if not os.path.exists(STORICO_PATH):
        return {}
    try:
        with open(STORICO_PATH, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError) as err:
        print(f"[genera_eventi] storico comuni illeggibile ({err}), riparto da vuoto")
        return {}


def aggiorna_storico(events, oggi):
    """Archivio leggero comune -> eventi visti, aggiornato a ogni run.

    data/eventi.json tiene solo il futuro: senza archivio, a novembre la pagina
    di un comune sarebbe una pagina vuota, e una pagina vuota non deve
    esistere. Lo slug di slug_evento() e' stabile fra un'edizione e l'altra,
    quindi l'archivio sa da solo quali feste tornano ogni anno - che e' l'unica
    cosa che questa pagina puo' dire e che ne' l'agenda ne' chi copia gli
    eventi da Instagram sa dire."""
    storico = carica_storico()
    for e in events:
        citta = (e.get('citta') or '').strip()
        k = _key(citta)
        if not k:
            continue
        c = storico.setdefault(k, {"nome": citta, "prov": e.get('prov') or '', "eventi": {}})
        c["nome"] = citta or c["nome"]
        c["prov"] = (e.get('prov') or c.get("prov") or '').upper()
        sl = slug_evento(e)
        r = c["eventi"].setdefault(sl, {"anni": []})
        r["nome"] = (e.get('nome') or '').strip()
        r["manifest"] = (e.get('manifest') or '').strip()
        r["luogo"] = (e.get('luogo') or '').strip()
        r["organizza"] = organizzatore(e.get('nome'))
        r["pagina"] = ha_pagina(e)
        r["ultima"] = e['d_start'].isoformat()
        if e['d_start'].year not in r["anni"]:
            r["anni"] = sorted(r["anni"] + [e['d_start'].year])
    # Potatura: quello che non si vede da due anni non torna piu'.
    limite = (oggi - datetime.timedelta(days=MEMORIA_STORICO)).isoformat()
    for k in list(storico):
        c = storico[k]
        c["eventi"] = {sl: r for sl, r in c["eventi"].items()
                       if (r.get("ultima") or '') >= limite}
        if not c["eventi"]:
            del storico[k]
    with open(STORICO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(storico, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return storico


def comuni_hub(events, storico, oggi):
    """{chiave: dati} dei comuni che meritano una pagina, soglie alla mano."""
    limite = (oggi - datetime.timedelta(days=FINESTRA_HUB)).isoformat()
    # Senza whitelist i candidati sono tutti i comuni visti, in agenda o in
    # archivio: a scartare ci pensano le soglie qualche riga piu' sotto.
    chiavi = set(storico) | {_key(e.get('citta')) for e in events
                             if (e.get('citta') or '').strip()}
    hub = {}
    for k in sorted(chiavi):
        futuri = sorted((e for e in events if _key(e.get('citta')) == k),
                        key=lambda e: (e['d_start'], e.get('nome') or ''))
        arch = (storico.get(k) or {}).get('eventi', {})
        visti = {sl: r for sl, r in arch.items() if (r.get('ultima') or '') >= limite}
        # Un evento futuro e' anche in archivio: si contano una volta sola.
        terne = {slug_evento(e): ((e.get('manifest') or ''), (e.get('nome') or ''))
                 for e in futuri}
        for sl, r in visti.items():
            terne.setdefault(sl, (r.get('manifest') or '', r.get('nome') or ''))
        var = varieta((m, nome, sl) for sl, (m, nome) in terne.items())
        if len(terne) < MIN_EVENTI_HUB or var < MIN_VARIETA_HUB:
            continue
        nome = ((futuri[0].get('citta') if futuri
                 else (storico.get(k) or {}).get('nome')) or '').strip()
        # `k` e' una chiave normalizzata ("novillgure"), non un nome da
        # stampare: senza un nome vero la pagina non si puo' scrivere.
        if not nome:
            continue
        hub[k] = {
            'nome': nome,
            'prov': ((futuri[0].get('prov') if futuri else
                      (storico.get(k) or {}).get('prov')) or '').upper(),
            'slug': slugify(nome),
            'futuri': futuri,
            'archivio': visti,
            'eventi': len(terne),
            'varieta': var,
        }
    return hub


def url_comune(dati):
    return f"{SITE_URL}/eventi/comune/{dati['slug']}.html"


def blocco_comuni(hub, oggi):
    """L'elenco delle pagine per comune, per il fondo di eventi.html.

    Le pagine comune esistevano gia' ma le linkavano solo zone.html e le poche
    schede evento di quei comuni: dall'agenda, che e' la pagina piu' forte del
    sito, non arrivava niente. Il conteggio accanto al nome non e' decorazione,
    e' la promessa che dice se vale la pena entrare."""
    # Le pagine di intenzione vanno per prime e ci sono sempre, hub o non hub:
    # sono la risposta alle query generiche su cui l'agenda ranka in settima
    # posizione, e da nessuna parte del sito ci arriverebbe un link. Una pagina
    # che solo la sitemap conosce, Google la tratta come tale.
    scorc = "".join(f'<a href="{href}">{esc(testo)}</a>'
                    for href, testo in link_landing(oggi))
    testa = ('      <div class="ev-scorc-row">'
             '<span class="ev-comuni-lab">Cosa cerchi</span>'
             f'<div class="ev-comuni">{scorc}</div></div>\n')
    if not hub:
        return testa.rstrip('\n')
    voci = [d for d in sorted(hub.values(), key=lambda d: (-len(d['futuri']), d['nome']))
            if d['futuri']]
    if not voci:
        return testa.rstrip('\n')

    # Il numero da solo tiene la pillola corta; "eventi in programma" per
    # esteso sta nell'aria-label, perche' un "12" nudo allo screen reader
    # non dice niente.
    def pillola(d):
        return (f'<a href="/eventi/comune/{d["slug"]}.html" '
                f'aria-label="{esc(d["nome"])}: {len(d["futuri"])} eventi in programma">'
                f'{esc(d["nome"])} <span>{len(d["futuri"])}</span></a>')

    # In alta stagione i comuni con almeno un evento sono venti, cioe' tre file
    # di pillole fra i filtri e il primo evento: l'indice si mangiava la pagina
    # che doveva indicizzare. Se ne mostrano MAX_COMUNI_APERTI - quelli con piu'
    # eventi, che e' gia' l'ordine - e la coda va sotto un "+ altri N".
    #
    # Il taglio e' sul NUMERO di pillole, non sul conteggio degli eventi: il
    # difetto da riparare e' di ingombro, ed e' l'ingombro a dover essere
    # prevedibile. Una soglia tipo "almeno 2 eventi" farebbe ballare la riga fra
    # cinque e quindici pillole secondo la stagione, cioe' non risolverebbe
    # niente a Ferragosto e taglierebbe troppo a novembre.
    #
    # I link della coda restano nell'HTML, dentro un secondo <details> chiuso:
    # e' la stessa ragione per cui il blocco e' un <details> e non JavaScript -
    # Google li vede e li segue lo stesso, che era tutto il punto del blocco.
    # Un "+ altri 1" occuperebbe il posto della pillola che nasconde, quindi
    # sotto le due voci di coda non si taglia niente.
    if len(voci) <= MAX_COMUNI_APERTI + 2:
        primi, resto = voci, []
    else:
        primi, resto = voci[:MAX_COMUNI_APERTI], voci[MAX_COMUNI_APERTI:]
    link = "".join(pillola(d) for d in primi)
    if resto:
        link += ('<details class="ev-comuni-piu">'
                 f'<summary aria-label="Mostra altri {len(resto)} comuni">'
                 f'+ altri {len(resto)}</summary>'
                 f'<div class="ev-comuni">{"".join(pillola(d) for d in resto)}</div>'
                 '</details>')
    # <details> e non piu' una riga aperta: sul telefono questi 10-15 comuni
    # occupavano da soli mezzo schermo fra i filtri e il primo evento, e chi
    # apre l'agenda vuole vedere un evento, non un indice. Aperto di default
    # (senza JS resta com'era e su desktop lo spazio c'e'); l'agenda lo chiude
    # sotto i 600px. I link restano nell'HTML in ogni caso: dentro un details
    # chiuso Google li vede e li segue lo stesso, che era tutto il punto del
    # blocco.
    return (testa
            + '      <details class="ev-comuni-box" open>\n'
            + f'        <summary class="ev-comuni-lab">Vai al comune<span class="ev-comuni-n">{len(voci)}</span></summary>\n'
            + f'        <div class="ev-comuni">{link}</div>\n'
            + '      </details>')


COMUNE_CSS = """
/* L'elenco "cosa c'e' per i bambini": le stesse righe delle altre, ma senza il
   wrapper .com-b - data, titolo e fascia d'eta' stanno tutti e tre in fila.
   flex-wrap perche' sul telefono la pillola dell'eta' deve andare a capo invece
   di strizzare il titolo a due parole per riga. */
.com-kids li{flex-wrap:wrap;align-items:baseline}
.com-kids .com-d{flex:0 0 auto;min-width:118px}
.com-kids .com-go{flex:1 1 220px}
.com-eta{flex:0 0 auto;font-size:.78rem;font-weight:700;letter-spacing:.02em;
  color:#a75b15;background:rgba(232,149,74,.16);border-radius:100px;padding:3px 10px}
@media(max-width:600px){.com-kids .com-d{min-width:0}}
/* Il ritmo verticale. Il reset del sito e' *{margin:0}, e le altre pagine si
   rimettono i margini componente per componente: qui la pagina e' fatta anche
   di prosa - titoletto, paragrafo, riga di link - e senza margini si incollava
   tutta insieme, con l'h2 appiccicato al fondo del paragrafo precedente.
   Il selettore e' figlio diretto apposta: i <p> dentro le schede (.com-per) i
   loro margini ce li hanno gia'. */
.ev-wrap>h2{margin:34px 0 8px;font-size:1.3rem;line-height:1.32}
.ev-wrap>p{margin:0 0 12px;max-width:66ch}
.ev-wrap>p a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
.com-stat{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0 6px;padding:0;list-style:none}
.com-stat li{border:1px solid rgba(45,74,92,.16);border-radius:100px;padding:6px 14px;font-size:.86rem}
.com-grp{position:relative;border:1px solid rgba(45,74,92,.16);border-radius:16px;
  padding:15px 18px;margin:12px 0;background:#fff}
.com-grp h3{margin:0 0 3px;font-size:1.06rem;line-height:1.32}
.com-per{font-size:.85rem;opacity:.72;margin:0 0 2px}
/* La miniatura e' la locandina servita dal bucket Supabase: la stessa che
   l'agenda mostra nelle righe (.ev-thumb), stesse misure e stesso taglio dal
   bordo alto, perche' su una locandina il titolo sta in cima. Dove manca -
   quattro eventi su 257 - resta il segnaposto nel colore della categoria. */
.com-th{width:56px;height:56px;flex:0 0 56px;border-radius:11px;object-fit:cover;
  object-position:top center;background:var(--cream,#fbf7f0);display:block}
.com-th.is-ph{display:flex;align-items:center;justify-content:center;
  background:var(--cat-tint,rgba(126,140,153,.16));color:var(--cat-color,#7e8c99)}
.com-th.is-ph svg{width:22px;height:22px}
/* Il link copre tutta la riga: il bersaglio da toccare e' il rettangolo, non
   le venti lettere del titolo. Vale per la scheda singola e per ogni riga di
   una manifestazione, quindi ::after si aggrappa a .com-grp o a .com-ev li. */
.com-go{color:var(--navy,#2d4a5c);font-weight:600;text-decoration:none}
.com-go::after{content:"";position:absolute;inset:0}
.com-head{display:flex;gap:14px;align-items:center}
/* La locandina del cartellone, una volta sola in cima all'elenco. Il riquadro
   e' fisso (aspect-ratio) e l'immagine sta dentro senza tagli: e' un poster da
   leggere, non un francobollo da riconoscere, e un box fisso non fa saltare la
   pagina quando l'immagine arriva. */
.com-poster{display:flex;gap:16px;align-items:center;margin:14px 0 4px;
  border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:14px 16px;background:#fff}
.com-poster img{width:132px;aspect-ratio:3/4;object-fit:contain;border-radius:10px;
  display:block;background:var(--cream,#fbf7f0)}
.com-poster figcaption{font-size:.9rem;line-height:1.55;opacity:.85}
.com-poster figcaption a{color:var(--navy,#2d4a5c);font-weight:600;
  text-decoration:underline;text-underline-offset:2px}
@media(max-width:520px){
  .com-poster{gap:13px;padding:12px 13px}
  .com-poster img{width:96px}
  .com-poster figcaption{font-size:.86rem}
}
.com-solo{display:flex;gap:14px;align-items:center;padding:13px 16px;
  transition:border-color .15s ease,box-shadow .15s ease}
.com-solo h3{font-size:1rem;margin:0 0 2px}
.com-solo:hover,.com-ev li:hover{border-color:rgba(107,165,168,.55)}
.com-solo:hover{box-shadow:0 2px 14px rgba(45,74,92,.07)}
.com-solo:hover .com-go,.com-ev li:hover .com-go{text-decoration:underline}
.com-ev{list-style:none;margin:11px 0 0;padding:0}
.com-ev li{position:relative;display:flex;gap:12px;align-items:center;
  padding:9px 0;border-top:1px solid rgba(45,74,92,.1)}
.com-ev li:first-child{border-top:0;padding-top:1px}
.com-ev .com-th{width:50px;height:50px;flex-basis:50px;border-radius:10px}
.com-ev .com-th.is-ph svg{width:20px;height:20px}
/* Righe senza francobollo (il poster e' salito in testa al gruppo): la data
   torna a fianco del titolo in colonna fissa, che a schermo largo si scorre
   meglio di due righe impilate. Sul telefono la colonna non ci sta e si
   impila - stessa scelta che fa l'agenda con .ev-line. */
.com-ev.is-nude li{gap:14px;align-items:baseline}
.com-ev.is-nude .com-b{flex-direction:row;gap:14px;align-items:baseline;flex-wrap:wrap}
.com-ev.is-nude .com-d{min-width:132px}
@media(max-width:560px){
  .com-ev.is-nude .com-b{flex-direction:column;gap:2px}
  .com-ev.is-nude .com-d{min-width:0}
}
.com-b{display:flex;flex-direction:column;gap:2px;min-width:0}
/* La data in alto e nel colore della categoria: e' l'unica cosa che si legge
   scorrendo con il pollice, e sta sempre alla stessa distanza dal bordo. */
.com-d{font-weight:700;font-size:.76rem;letter-spacing:.03em;text-transform:uppercase;
  color:var(--cat-ink,#606d7a)}
/* La categoria accanto alla data. Il colore di categoria su queste righe c'era
   gia' (.com-d prende --cat-ink) ma non lo sapeva nessuno: un blu e un verde
   senza etichetta sono due blu e due verdi. Sta in COMUNE_CSS e non in
   LANDING_CSS perche' serve in tutti e due i posti, e le pagine comune
   ricevono solo il primo dei due blocchi. */
.com-cat{color:var(--cat-ink,#606d7a);opacity:.78}
.com-cat::before{content:' · ';opacity:.6}
.com-ev .com-go{font-size:.95rem;line-height:1.34}
/* Le feste che tornano: niente locandina, perche' quella in archivio e'
   dell'edizione passata e prometterebbe una data che non c'e' piu'. */
.com-anni{list-style:none;margin:0;padding:0}
.com-anni li{display:flex;gap:12px;align-items:baseline;padding:7px 0;
  border-top:1px solid rgba(45,74,92,.1);font-size:.94rem}
.com-anni li:first-child{border-top:0}
.com-y{font-weight:700;white-space:nowrap;font-size:.82rem;opacity:.7;min-width:76px;
  font-variant-numeric:tabular-nums}
.com-anni a{text-decoration:none;color:var(--navy,#2d4a5c);font-weight:600}
.com-anni a:hover{text-decoration:underline}
.com-link{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 6px}
.com-link a{display:inline-block;border:1px solid rgba(45,74,92,.2);border-radius:100px;
  padding:7px 15px;font-size:.9rem;font-weight:600;text-decoration:none;color:var(--navy,#2d4a5c)}
.com-link a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.09)}
.com-vuoto{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:16px 18px;
  margin:16px 0;font-size:.95rem}
/* Il credito alla pagina di provenienza: stesso peso che ha sulle schede
   evento (.ev-fonte), con il filo sopra che lo stacca dal corpo della pagina.
   Piu' specifici di .ev-wrap>p, se no vince quello e il filo si attacca. */
.ev-wrap>p.com-fonte{font-size:.88rem;opacity:.85;margin:26px 0 0;padding-top:14px;
  border-top:1px solid rgba(45,74,92,.12);max-width:none}
.com-fonte a{color:var(--navy,#2d4a5c);text-decoration:underline;text-underline-offset:2px}
.ev-wrap>p.ev-firma-nota{margin:8px 0 0;max-width:none}
@media(max-width:600px){
  .com-grp{padding:13px 14px}
  .com-solo{padding:11px 12px;gap:12px}
  .com-th{width:50px;height:50px;flex-basis:50px}
  .com-ev .com-th{width:46px;height:46px;flex-basis:46px}
}
"""


def _com_cat(e, salita=''):
    """(stile con i colori della categoria, miniatura) per una riga di comune.

    `salita` e' la locandina gia' mostrata in cima alla pagina: chi ce l'ha
    uguale non la ripete. Le custom property stanno sulla riga e non
    sull'immagine: il segnaposto e' un figlio, e --cat-tint si eredita."""
    slug, _icona, _lab = bucket(e)
    color, tint, ink = COLORS.get(slug, COLORS['altro'])
    stile = f'--cat-color:{color};--cat-tint:{tint};--cat-ink:{ink}'
    # cover resta l'ORIGINALE perche' e' la chiave del confronto qui sotto:
    # `salita` arriva da _com_poster_pagina(), che ragiona sugli originali. La
    # miniatura e' solo quello che finisce nel src.
    cover = loc_path(e.get('loc'))
    if cover and cover == salita:
        # Gia' in cima alla pagina, grande. Qui sotto sarebbe un doppione, e
        # nemmeno il segnaposto di categoria aiuta: ad Acqui sette schede su
        # dodici sono "Cultura", quindi sarebbero sette quadrati identici.
        return stile, ''
    if cover:
        thumb = (f'<img class="com-th" src="{esc(loc_path(e.get("loc"), mini=True))}" alt="" '
                 f'loading="lazy" decoding="async" width="56" height="56">')
    else:
        # Icona autoconclusiva e non quella di categoria: le icone di categoria
        # sono <use href="#i-party"> e il simbolo vive nello sprite inline di
        # eventi.html, che qui non c'e' - disegnerebbe il vuoto.
        thumb = f'<span class="com-th is-ph" aria-hidden="true">{CAL_SVG}</span>'
    return stile, thumb


def _com_poster_pagina(gruppi):
    """La locandina che vale per (quasi) tutta la pagina, se ce n'e' una.

    E' la stessa regola che dentro una manifestazione fa salire il poster in
    testa al gruppo, applicata un piano sopra. Ad Acqui Terme la locandina e'
    identica su 10 gruppi su 11: non e' il poster di un evento, e' il grafico
    che quella pagina di zona pubblica per l'intero cartellone. Quindi non
    appartiene a nessuna scheda, appartiene alla pagina - e li' va messa, una
    volta sola e grande abbastanza da aprirla. Le schede che la condividono
    restano pulite; quella che ha un poster suo se lo tiene, perche' li' la
    miniatura distingue davvero."""
    quanti = collections.Counter()
    for g in gruppi:
        poster = {loc_path(e.get('loc')) for e in g['eventi']}
        # Un gruppo conta per il suo poster solo se e' uno solo per tutte le
        # serate: se dentro variano, quel gruppo le miniature le usa davvero.
        if len(poster) == 1 and next(iter(poster)):
            quanti[next(iter(poster))] += 1
    if not quanti:
        return ''
    p, n = quanti.most_common(1)[0]
    return p if n > 2 else ''


def _gruppi_comune(futuri):
    """Gli eventi futuri raggruppati per manifestazione.

    E' il motivo per cui questa pagina esiste: nell'agenda le 13 serate della
    patronale sono 13 righe in fila, qui sono una festa con dentro 13 serate.
    Chi cerca "festa novi ligure" vuole la seconda cosa."""
    gruppi = collections.OrderedDict()
    chiavi = chiavi_gruppo(((e.get('manifest') or ''), (e.get('nome') or ''),
                            slug_evento(e)) for e in futuri)
    for e, chiave in zip(futuri, chiavi):
        m = (e.get('manifest') or '').strip()
        g = gruppi.setdefault(chiave, {'titolo': m, 'eventi': []})
        if m and not g['titolo']:
            g['titolo'] = m
        g['eventi'].append(e)
    for g in gruppi.values():
        if not g['titolo']:
            g['titolo'] = (g['eventi'][0].get('nome') or '').strip()
    return list(gruppi.values())


def _href_evento(e):
    if ha_pagina(e):
        return f"/eventi/{slug_evento(e)}.html"
    return f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html"


def _voci_lista(eventi, limite=30):
    """Le voci ItemList di una pagina elenco: SOLO gli eventi con pagina propria.

    Un carosello di Google e' fatto di voci che puntano ognuna a una URL che
    contiene a sua volta il markup Event. Un'ancora dentro l'agenda
    (/eventi.html#ev-...) non e' una pagina a se': Google non la tratta come
    elemento distinto, e le voci che non si risolvono non fanno partire il
    carosello per l'INTERA lista. Su comune/acqui-terme.html erano 8 voci su 10
    a puntare a un'ancora: la lista era lunga e inservibile.

    Meglio una lista corta e vera. Gli eventi senza pagina restano visibili
    nell'HTML della pagina, semplicemente non entrano nei dati strutturati -
    dove non avrebbero comunque una URL da dichiarare.

    Il filtro si stringe da solo man mano che ha_pagina() si allarga: la strada
    per una lista lunga e' dare una pagina agli eventi, non dichiararli qui.
    """
    con_pagina = [e for e in eventi if ha_pagina(e)]
    return [{"@type": "ListItem", "position": i + 1,
             "url": f"{SITE_URL}{_href_evento(e)}",
             "name": (e.get('nome') or '').strip()}
            for i, e in enumerate(con_pagina[:limite])]


def _quando_breve(e, oggi):
    d = e['d_start']
    if d < oggi:
        return "in corso"
    if d == oggi:
        return "oggi"
    if (d - oggi).days == 1:
        return "domani"
    return f"{GIORNI[d.weekday()][:3]} {d.day} {MESI[d.month - 1]}"


def _ricorrenti(archivio):
    """Le feste viste in piu' di un anno: quelle che tornano davvero."""
    out = [(sl, r) for sl, r in archivio.items() if len(r.get('anni') or []) > 1]
    out.sort(key=lambda t: (-len(t[1]['anni']), t[1].get('nome') or ''))
    return out


def _ricorrenze(valori, minimo=2, quante=4):
    """I valori che tornano almeno `minimo` volte, dal piu' frequente."""
    c = collections.Counter(v.strip() for v in valori if (v or '').strip())
    return [(v, n) for v, n in c.most_common(quante) if n >= minimo]


def render_comune(dati, css, nav, foot, oggi, vicini=None):
    citta = dati['nome']
    futuri, archivio = dati['futuri'], dati['archivio']
    url = url_comune(dati)
    prov_nome = PROVINCE_NOMI.get(dati['prov'], dati['prov'])

    # L'anno sta nelle query ("sagre novi ligure 2026") ma non si scrive a mano:
    # e' quello del prossimo evento, o l'anno in corso se non ce n'e' nessuno.
    anno = futuri[0]['d_start'].year if futuri else oggi.year
    # Da dove arrivano gli eventi di questa provincia. Sulle pagine comune non
    # c'era mai stato: finche' esistevano solo comuni della provincia di
    # Alessandria la fonte era la nostra e si poteva sottintendere. Tolto il
    # filtro sui comuni e' nata Crissolo, che sta in provincia di Cuneo - una
    # provincia che segue una pagina non nostra. Una pagina DAOP che elenca il
    # lavoro di qualcun altro senza dirlo e' esattamente quello che non facciamo.
    fonte = fonte_provincia(dati['prov'])
    # "sagre" nel title non si tocca: "sagre <comune> 2026" e' il modello di
    # query che porta i clic, misurato. "per famiglie" si aggiunge, non
    # sostituisce.
    #
    # Prima compariva solo se almeno il 60% degli eventi aveva il flag "Adatto
    # Famiglie" nel foglio, per non promettere quello che la pagina non
    # mantiene. Ma la promessa la mantiene sempre: in agenda ci entra solo
    # quello che abbiamo scelto per le famiglie, e quel flag e' "Si" nel 95%
    # delle righe - la soglia non misurava l'offerta del comune, misurava
    # quanto era stata compilata una colonna. Un comune finiva senza "per
    # famiglie" nel title per tre celle lasciate in bianco.
    bambini = [e for e in futuri if e_per_bambini(e)]
    basi = [f"Eventi e sagre per famiglie{a_citta(citta)} {anno}",
            f"Eventi e sagre{a_citta(citta)} {anno}"]
    titolo = next((t for b in basi for t in (f"{b} | DAOP", b) if len(t) <= MAX_TITLE),
                  trunc(basi[-1], MAX_TITLE))
    h1 = f"Eventi e sagre per famiglie{a_citta(citta)}"
    gruppi = _gruppi_comune(futuri)
    salita = _com_poster_pagina(gruppi)

    # L'attacco si costruisce con i numeri veri: e' quello che rende questa
    # pagina diversa dalla stessa pagina di un altro comune, ed e' anche
    # l'unica cosa onesta da scrivere senza aver visitato il posto.
    if futuri:
        fine = max(e['d_end'] for e in futuri)
        quanti = (f"{len(futuri)} eventi in programma" if len(futuri) > 1
                  else "1 evento in programma")
        cosa = (f"{len(gruppi)} manifestazioni diverse" if len(gruppi) > 1
                else "una manifestazione")
        sotto = f"{quanti}, fino al {fine.day} {MESI_LUNGHI[fine.month - 1]} {fine.year}"
        # "Le controlliamo una per una" si puo' dire solo dove il lavoro e'
        # nostro. Dove la provincia la segue una pagina esterna la frase
        # sarebbe una firma su una cosa fatta da altri.
        chiusa = ("Le schede le controlliamo una per una prima di pubblicarle."
                  if not fonte or fonte['nostra'] else
                  # Tre righe per dire "non e' roba nostra" erano una excusatio
                  # in apertura di pagina. "A cura di" lo dice in tre parole, e
                  # il credito per esteso resta in fondo dov'e' il suo posto.
                  f'A cura di <a href="{fonte["url"]}" target="_blank" '
                  f'rel="noopener">@{esc(fonte["ig"])}</a>.')
        apertura = (f"{quanti}{a_citta(citta)}, in provincia di {prov_nome}: "
                    f"{cosa}, con le date, gli orari e i contatti di chi le organizza. "
                    + chiusa)
    else:
        sotto = "Nessun evento in programma in questo momento"
        apertura = (f"In questo momento{a_citta(citta)} non abbiamo eventi in agenda. "
                    "Qui sotto restano le feste che tornano ogni anno, così sai "
                    "quando aspettarle: appena arrivano le date della prossima "
                    "edizione le trovi in questa pagina.")

    stat = [f"<li>{len(futuri)} in programma</li>" if futuri else "",
            f"<li>{len(gruppi)} manifestazioni</li>" if len(gruppi) > 1 else "",
            f"<li>provincia di {esc(prov_nome)}</li>"]
    blocchi = []
    for g in gruppi:
        ev = g['eventi']
        di, df = min(e['d_start'] for e in ev), max(e['d_end'] for e in ev)
        periodo = (data_estesa(di).capitalize() if di == df else
                   f"{_dal(di.day)} {MESI_LUNGHI[di.month - 1]} al "
                   f"{df.day} {MESI_LUNGHI[df.month - 1]}")
        if len(ev) == 1:
            # Un evento solo: il titolo del gruppo E' l'evento. Ripeterlo sotto
            # come unica riga di elenco riempirebbe la pagina di doppioni, che
            # e' il modo piu' rapido per farla sembrare generata a macchina.
            stile, thumb = _com_cat(ev[0], salita)
            blocchi.append(
                f'<section class="com-grp com-solo" style="{stile}">{thumb}'
                f'<div class="com-b"><h3>'
                f'<a class="com-go" href="{_href_evento(ev[0])}">'
                f'{esc(trunc(g["titolo"], 80))}</a></h3>'
                f'<p class="com-per">{esc(periodo)}</p></div></section>')
            continue
        # Le 13 serate di una patronale hanno quasi sempre LA STESSA locandina,
        # quella della festa. Ripeterla su ogni riga fa una colonna di sette
        # francobolli uguali, che non aiuta a distinguere niente: quando il
        # poster e' uno solo sale in testa al gruppo, dove appartiene, e le
        # righe restano pulite. Se invece ogni serata ha il suo, il poster torna
        # sulla riga: li' distingue davvero.
        stile, _ = _com_cat(ev[0])
        poster = {loc_path(e.get('loc')) for e in ev}
        comune_a_tutti = poster.pop() if len(poster) == 1 else ''
        if comune_a_tutti == salita:
            comune_a_tutti = ''      # sta gia' in cima alla pagina
        righe, nude = "", True
        # La categoria in riga solo se il gruppo ne mescola piu' d'una. Dentro
        # una manifestazione sono quasi sempre tutte uguali, e ripetere
        # "SAGRA & FESTA" su cinque righe di fila e' rumore: li' il colore
        # basta. Nel gruppo senza titolo, che raccoglie quello che resta, le
        # categorie sono davvero diverse ed e' l'unico posto dove il colore da
        # solo non si sa leggere.
        misto = len({bucket(e)[0] for e in ev}) > 1
        for e in ev:
            # L'ora accanto alla data: e' la domanda subito dopo "quando", e
            # nell'agenda ce l'ha ogni riga. Solo se e' un'ora vera, pero': la
            # colonna del foglio a volte dice "vari", e qui, in maiuscoletto,
            # "OGGI · VARI" sembra un'etichetta invece di un orario.
            quando = _quando_breve(e, oggi)
            ora = (e.get('ora') or '').strip()
            if any(c.isdigit() for c in ora):
                quando += ' · ' + trunc(ora, 18)
            riga_stile, thumb = _com_cat(e, salita)
            if comune_a_tutti:
                # Una locandina sola per tutte le date: la miniatura sparisce,
                # sarebbe la stessa immagine venti volte. Il colore invece si
                # appiattisce su quello del gruppo SOLO se il gruppo e' una
                # cosa sola. Dove le categorie si mescolano - la patronale di
                # Sant'Albano ha sagra, spettacolo, sport e laboratorio nella
                # stessa settimana - spegnere il colore contraddirebbe
                # l'etichetta scritta qui accanto: si leggeva "SPETTACOLO"
                # nell'arancione delle sagre.
                thumb = ''
                if not misto:
                    riga_stile = stile
            nude = nude and not thumb
            cat = (f'<span class="com-cat">{esc(bucket(e)[2])}</span>'
                   if misto else '')
            righe += (f'<li style="{riga_stile}">{thumb}<span class="com-b">'
                      f'<span class="com-d">{esc(quando)}{cat}</span>'
                      f'<a class="com-go" href="{_href_evento(e)}">'
                      f'{esc(trunc(e.get("nome") or "", 80))}</a></span></li>')
        testa = (f'<img class="com-th" src="{esc(comune_a_tutti)}" alt="" '
                 f'loading="lazy" decoding="async" width="56" height="56">'
                 if comune_a_tutti else '')
        blocchi.append(
            f'<section class="com-grp" style="{stile}">'
            f'<div class="com-head">{testa}<div class="com-b">'
            f'<h3>{esc(trunc(g["titolo"], 80))}</h3>'
            f'<p class="com-per">{esc(periodo)} · {len(ev)} appuntamenti</p>'
            f'</div></div>'
            f'<ul class="com-ev{" is-nude" if nude else ""}">{righe}</ul>'
            f'</section>')

    # La locandina del cartellone, se ce n'e' una che vale per quasi tutto.
    # Apre l'elenco invece di ripetersi dentro: e' l'immagine che chi segue la
    # zona pubblica per l'intero programma, e a dimensione di francobollo non
    # si legge - qui si apre a grandezza vera con un tocco.
    poster_html = ''
    if salita:
        poster_html = (
            f'<figure class="com-poster">'
            f'<a href="{esc(salita)}" target="_blank" rel="noopener">'
            f'<img src="{esc(salita)}" alt="Locandina degli eventi{a_citta(citta)}" '
            f'loading="lazy" decoding="async"></a>'
            # Quello che si puo' dire davvero: nei nostri dati questa immagine
            # e' legata a tutte queste date. Chi l'abbia disegnata non lo
            # sappiamo, e "chi organizza" sarebbe falso - gli organizzatori di
            # queste undici cose sono undici diversi.
            f'<figcaption>Una sola locandina per tutte queste date, '
            f'così come ci arriva. '
            f'<a href="{esc(salita)}" target="_blank" rel="noopener">Aprila grande</a>'
            f'</figcaption></figure>')

    # Cosa c'e' per i bambini, in chiaro. E' la sezione che questa pagina puo'
    # avere e che l'agenda generale non puo': l'agenda mescola tre province, qui
    # invece "laboratori per bambini a Tortona" e' una riga vera con sotto
    # l'elenco. Compare solo se gli eventi ci sono davvero.
    if bambini:
        voci = "".join(
            f'<li><span class="com-d">{esc(_quando_breve(e, oggi))}</span>'
            f'<a class="com-go" href="{_href_evento(e)}">'
            f'{esc(trunc(e.get("nome") or "", 80))}</a>'
            + (f'<span class="com-eta">{esc((e.get("eta") or "").strip())}</span>'
               if fascia_eta(e.get('eta')) else '')
            + '</li>' for e in bambini[:10])
        quanti_b = (f"{len(bambini)} appuntamenti pensati per i bambini"
                    if len(bambini) > 1 else "Un appuntamento pensato per i bambini")
        blocchi.append(
            f'<h2>Cosa c\'è per i bambini{a_citta(citta)}</h2>'
            f'<p>{quanti_b}: hanno una fascia d\'età dichiarata dagli organizzatori '
            f'oppure laboratori, burattini o giochi scritti nel programma. '
            f'Il resto degli eventi qui sopra è comunque adatto alle famiglie.</p>'
            f'<section class="com-grp"><ul class="com-ev com-kids">{voci}</ul></section>')

    ric = _ricorrenti(archivio)
    if ric:
        righe = "".join(
            f'<li><span class="com-y">{r["anni"][0]}–{r["anni"][-1]}</span>'
            + (f'<a href="/eventi/{sl}.html">{esc(trunc(r.get("nome") or "", 80))}</a>'
               if r.get('pagina') else f'<span>{esc(trunc(r.get("nome") or "", 80))}</span>')
            + '</li>' for sl, r in ric[:8])
        blocchi.append(
            f'<h2>Le feste che tornano ogni anno{a_citta(citta)}</h2>'
            f'<p>Le abbiamo già viste in più di un\'edizione: quando escono le date '
            f'nuove, questa pagina si aggiorna da sola.</p>'
            f'<section class="com-grp"><ul class="com-anni">{righe}</ul></section>')

    # Luoghi e organizzatori ricorrenti: si ricavano contando, non si scrivono.
    tutti_luoghi = [e.get('luogo') or '' for e in futuri] + \
                   [r.get('luogo') or '' for r in archivio.values()]
    tutti_org = [organizzatore(e.get('nome')) for e in futuri] + \
                [r.get('organizza') or '' for r in archivio.values()]
    extra = []
    # "I posti che tornano più spesso: Novi Ligure" non è un'informazione: nel
    # foglio la colonna del luogo a volte ripete il comune. Fuori.
    tutti_luoghi = [v for v in tutti_luoghi if _key(v) and _key(v) != _key(citta)]
    luoghi = _ricorrenze(tutti_luoghi)
    if luoghi:
        extra.append("<p>I posti che tornano più spesso: "
                     + elenco_it([f"<strong>{esc(v)}</strong>" for v, _ in luoghi])
                     + ".</p>")
    org = _ricorrenze(tutti_org)
    if org:
        extra.append("<p>A organizzare sono soprattutto "
                     + elenco_it([f"<strong>{esc(v)}</strong>" for v, _ in org])
                     + ": i recapiti stanno sulla scheda di ogni evento.</p>")
    if extra:
        blocchi.append(f"<h2>Come funziona{a_citta(citta)}</h2>" + "".join(extra))

    altri = [d for k, d in sorted((vicini or {}).items())
             if d['slug'] != dati['slug'] and d['prov'] == dati['prov']][:6]
    link_altri = "".join(f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
                         for d in altri)

    credito = credito_fonte(fonte, f'Gli eventi{a_citta(citta)} arrivano da')

    per_chi = " per famiglie"
    quanti_bimbi = f" {len(bambini)} per bambini." if bambini else ""
    descr = trunc(f"Eventi, sagre e feste{per_chi}{a_citta(citta)}: "
                  f"{sotto.lower()}.{quanti_bimbi} "
                  + ("Date, orari e contatti, controllati uno per uno da DAOP."
                     if not fonte or fonte['nostra'] else
                     "Date, orari e contatti, in collaborazione con chi segue "
                     "la provincia."), 152)

    lista = _voci_lista(futuri)
    grafo = [
        {"@type": "CollectionPage", "@id": url, "url": url, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "about": {"@type": "Place", "name": citta,
                   "address": {"@type": "PostalAddress", "addressLocality": citta,
                               "addressRegion": dati['prov'], "addressCountry": "IT"}},
         "publisher": {"@id": ORG_ID}, "dateModified": oggi.isoformat()},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
            {"@type": "ListItem", "position": 3, "name": citta, "item": url}]},
    ]
    # L'ItemList RIMANDA alle pagine evento, non ripete gli Event: due copie
    # dello stesso evento in due pagine diverse sono due elementi da validare
    # invece di uno, ed e' esattamente il pasticcio del superEvent.
    if lista:
        grafo.append({"@type": "ItemList", "name": f"Eventi{a_citta(citta)}",
                      "numberOfItems": len(lista), "itemListElement": lista})
    jsonld = json.dumps({"@context": "https://schema.org", "@graph": grafo},
                        ensure_ascii=False, indent=2)
    robots = "index, follow" if futuri or ric else "noindex, follow"

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(titolo)}</title>
<meta name="description" content="{esc(descr)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(titolo)}">
<meta property="og:description" content="{esc(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(titolo)}">
<meta name="twitter:description" content="{esc(trunc(descr, 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">
<meta name="daop:citta" content="{esc(citta)}">
<meta name="daop:provincia" content="{esc(dati['prov'])}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{COMUNE_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script src="/assets/js/locandina.js" defer></script>
<script type="application/ld+json">
{jsonld}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › <span>{esc(citta)}</span>
    </div>
    <h1>{esc(h1)}</h1>
    <p class="ev-when">{esc(sotto)}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  <ul class="com-stat">{"".join(stat)}</ul>
  <p>{apertura}</p>

  {'<h2>In programma</h2>' if futuri else ''}
  {poster_html}
  {"".join(blocchi)}

  <div class="com-link">
    {link_luoghi(citta, dati['prov'])}
    <a href="/eventi.html">Tutta l'agenda DAOP</a>
    <a href="/metodo.html">Come verifichiamo gli eventi</a>
  </div>
  {blocco_ginetto(citta, alto=True)}
  {f'<h2>Altri comuni della provincia di {esc(prov_nome)}</h2><div class="com-link">{link_altri}</div>' if link_altri else ''}
  {blocco_ecosistema('eventi')}
  {credito}
  <p class="ev-firma-nota">Pagina aggiornata il {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
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


def scrivi_comuni(hub, oggi):
    """Genera le pagine comune. Restituisce {slug: lastmod} per la sitemap."""
    if not hub:
        print("[genera_eventi] nessun comune sopra soglia: nessuna pagina comune")
        return {}
    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagine comune saltate: {err}")
        return {}
    os.makedirs(COMUNI_DIR, exist_ok=True)
    # Il lastmod e' la data in cui la pagina e' cambiata davvero, non quella
    # della run: e' lo stesso motivo per cui scrivi_pagine() tiene un registro.
    # Dichiarare "modificata oggi" ogni notte e' falso, e Google smette di dare
    # peso a <lastmod> quando lo trova inaffidabile.
    try:
        reg = json.load(open(REGISTRO_COMUNI, encoding='utf-8'))
    except (OSError, ValueError):
        reg = {}
    cambiate = 0
    # Sopra soglia non vuol dire in indice: render_comune mette noindex a un
    # comune che ha abbastanza eventi in archivio ma niente in programma ne' di
    # ricorrente. Quelle pagine vanno tenute FUORI dalla sitemap, se no il sito
    # dice due cose opposte sulla stessa URL.
    #
    # Il conto non si rifa' qui: si legge dall'HTML appena prodotto, cosi' i due
    # posti non possono divergere. E' il difetto che questa riga chiude — fino
    # al 31/08/2026 la sitemap filtrava solo sulla soglia, e cinque pagine in
    # noindex ci restavano dentro (ceresole-alba, entracque, limone-piemonte,
    # ormea, voltaggio). L'invariante e' lo stesso che il blocco CORSI dichiara
    # gia' di se': in sitemap niente noindex, e niente index fuori dalla sitemap.
    senza_indice = []
    for dati in sorted(hub.values(), key=lambda d: d['slug']):
        path = os.path.join(COMUNI_DIR, f"{dati['slug']}.html")
        nuovo = render_comune(dati, css, nav, foot, oggi, vicini=hub)
        if 'content="noindex' in nuovo:
            senza_indice.append(dati['slug'])
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            reg.setdefault(dati['slug'], oggi.isoformat())
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        reg[dati['slug']] = oggi.isoformat()
        cambiate += 1
    # Le pagine dei comuni scesi sotto soglia NON si cancellano: i link che
    # girano restano validi. Vanno pero' in noindex e fuori dalla sitemap,
    # perche' senza abbastanza eventi la pagina non ha piu' niente da dire.
    vivi = {d['slug'] for d in hub.values()}
    orfane = sorted(f[:-5] for f in os.listdir(COMUNI_DIR)
                    if f.endswith('.html') and f[:-5] not in vivi)
    for slug in orfane:
        path = os.path.join(COMUNI_DIR, f"{slug}.html")
        vecchio = open(path, encoding='utf-8').read()
        spento = vecchio.replace('<meta name="robots" content="index, follow">',
                                 '<meta name="robots" content="noindex, follow">')
        if spento != vecchio:
            open(path, 'w', encoding='utf-8').write(spento)
        reg.pop(slug, None)
    with open(REGISTRO_COMUNI, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_eventi] pagine comune: {len(hub)} sopra soglia "
          f"({cambiate} riscritte)" +
          (f", {len(orfane)} sotto soglia in noindex: {', '.join(orfane)}"
           if orfane else "") +
          (f", {len(senza_indice)} sopra soglia ma senza niente in programma, "
           f"quindi fuori sitemap: {', '.join(senza_indice)}"
           if senza_indice else ""))
    for d in sorted(hub.values(), key=lambda d: d['nome']):
        print(f"[genera_eventi]   {d['nome']}: {len(d['futuri'])} in programma, "
              f"{d['varieta']} cose diverse")
    return {s: m for s, m in sorted(reg.items())
            if s in vivi and s not in senza_indice}


# ---------------------------------------------------------------------------
# PAGINE DI INTENZIONE (oggi, weekend, sagre per provincia)
#
# Perche': eventi.html fa 6.866 impressioni al 2,45% di clic. Ranka in
# posizione 7-10 su query che tornano ogni settimana e non dipendono dalla
# stagione - "sagre provincia di alessandria oggi", "eventi provincia
# alessandria weekend", "cosa fare oggi in provincia di alessandria" - e ci
# arriva con l'agenda intera, cioe' con una pagina che risponde a tutte e tre
# insieme e quindi a nessuna per bene. E' lo stesso salto che le pagine evento
# hanno gia' fatto un piano sotto: 61 pagine per singola sagra fanno l'8,9% di
# clic, l'hub il 2,45%.
#
# Il rischio e' identico a quello delle pagine comune, e va detto qui: tre
# pagine ritagliate dallo stesso elenco sono doorway pages se l'unica cosa che
# cambia e' il filtro. Quello che l'agenda non da', e che qui c'e':
#   - "oggi" e "weekend" rispondono alla domanda con un elenco corto e chiuso,
#     mentre l'agenda apre su 250 schede in cui oggi e' una corsia fra tante;
#   - la riga per famiglie, che usa la colonna "Adatto Famiglie" del foglio e
#     nell'agenda non e' filtrabile;
#   - le pagine sagre tengono il calendario mese per mese e le sagre che
#     tornano ogni anno, che stanno nell'archivio e in agenda non ci sono.
# ---------------------------------------------------------------------------
LANDING_REGISTRO = os.path.join(ROOT, "data", "pagine-landing.json")

# Quanto deve avere una pagina sagre per stare in indice: sotto, non ha niente
# da dire piu' dell'agenda e va in noindex come le pagine comune sotto soglia.
# Le sagre che tornano ogni anno contano: sono la parte che regge a novembre,
# quando di sagre in programma non ce n'e' nessuna.
MIN_LANDING = 5

LANDING_CSS = """
/* Il comune sotto il nome dell'evento: qui gli elenchi attraversano la
   provincia, quindi "dove" e' la seconda cosa da sapere dopo "cosa" - nelle
   pagine comune non serve perche' il comune e' la pagina stessa. */
.com-luogo{font-size:.85rem;opacity:.72}
/* La fascia d'eta' accanto al comune, sulle /eventi-provincia-*. Dentro
   .com-luogo e non accanto: vedi il commento in _landing_righe(). L'opacity
   del padre la spegnerebbe insieme al comune, e l'eta' e' il motivo per cui
   quella riga sta nel primo blocco - quindi si rimette a 1. */
.com-luogo .com-eta{display:inline-block;vertical-align:baseline;margin-left:8px;
  opacity:1}
.com-ev.is-nude .com-b .com-luogo{flex:0 0 auto}
/* Le scorciatoie fra una pagina di intenzione e l'altra. */
.lan-alt{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 4px}
.lan-alt a{display:inline-block;border:1px solid rgba(45,74,92,.2);border-radius:100px;
  padding:7px 15px;font-size:.9rem;font-weight:600;text-decoration:none;
  color:var(--navy,#2d4a5c)}
.lan-alt a:hover{border-color:var(--teal,#6ba5a8);background:rgba(107,165,168,.09)}
.lan-vuoto{border:1px solid rgba(45,74,92,.16);border-radius:16px;padding:16px 18px;
  margin:16px 0;font-size:.95rem;line-height:1.6}
/* La barra filtri riusa .ev-toolbar/.ev-search/.ev-select dal CSS dell'agenda.
   Qui cambia solo l'ancoraggio: nelle pagine di intenzione non c'e' la barra
   dei giorni sotto, quindi si ferma direttamente sotto la nav del sito. */
.lan-toolbar{top:68px;margin:18px 0 0;padding:11px 0 10px}
.lan-count{margin:9px 0 0;font-size:.8rem;font-weight:600;color:var(--text-light,#7e8c99);
  min-height:1em}
.lan-nulla{margin-top:14px}
.lan-nulla button{font:inherit;font-weight:700;color:var(--orange-dark,#c97a2e);
  background:none;border:0;padding:0;cursor:pointer;text-decoration:underline}
.com-ev li[hidden],.com-grp[hidden]{display:none}
@media(max-width:600px){
  .lan-toolbar{margin-top:14px}
  /* Stessa ragione dell'agenda: a larghezza uguale le categorie lunghe
     vengono tagliate, a larghezza naturale ci stanno in fila. */
  .lan-toolbar .ev-select{flex:1 1 auto}
}
"""


def in_corso(e, giorno):
    """L'evento e' aperto in quel giorno (anche se e' cominciato prima)."""
    return e['d_start'] <= giorno <= e['d_end']


def _eta_chip(testo):
    """La fascia d'eta' come sta nel chip: il numero, senza la nota.

    Nel foglio la cella e' scritta a mano e a volte e' una frase intera -
    "3-14 anni (bambini e ragazzi, genitori invitati)" - che dentro un chip
    diventa due righe larghe due terzi dello schermo. La parentesi non e'
    l'eta', e' un commento, e sta per intero sulla scheda a un tocco di
    distanza; il numero resta parola per parola quello della locandina, che e'
    la regola scritta per i corsi.

    Il taglio a 24 e' la rete per la cella lunga senza parentesi: nel chip una
    riga sola, sempre."""
    t = (testo or '').strip()
    t = t.split(' (')[0].strip() or t
    return trunc(t, 24)


def _landing_righe(ev, oggi, eta=False, gratis=False):
    """(righe, nude) di un elenco, nel vocabolario delle pagine comune.

    `nude` dice se nessuna riga ha la miniatura: e' la stessa condizione che
    nelle pagine comune accende .is-nude, cioe' la data in colonna fissa a
    fianco del titolo. Con le miniature quella variante non va usata - la
    colonna della data si somma al francobollo e il nome parte a meta' riga."""
    out, nude = "", True
    # La sigla della provincia si stampa solo se in elenco ce n'e' piu' di
    # una. Su una pagina di UNA provincia "(CN)" e' scritto nell'H1 e ripeterlo
    # su 88 righe non aggiunge niente: a 360px - l'Android piu' diffuso -
    # mandava a capo 12 righe su 48 (misurato, non dedotto). Si ricava dai dati
    # e non da un parametro, cosi' vale da sola sulle pagine di una provincia e
    # resta dove serve: /eventi/oggi.html e /eventi/weekend.html mescolano le
    # tre province, e li' la sigla e' l'unica cosa che dice dove sei.
    piu_province = len({(x.get('prov') or '').upper() for x in ev
                        if (x.get('prov') or '').strip()}) > 1
    for e in ev:
        quando = _quando_breve(e, oggi)
        ora = (e.get('ora') or '').strip()
        if any(c.isdigit() for c in ora):
            quando += ' · ' + trunc(ora, 18)
        stile, thumb = _com_cat(e)
        nude = nude and not thumb
        citta = (e.get('citta') or '').strip()
        dove = ((f"{citta} ({e['prov']})" if piu_province else citta) if citta
                else (e.get('prov') or ''))
        # data-province/data-category: sono quello su cui lavora la barra
        # filtri. Stessi valori e stesso vocabolario dell'agenda, cosi' chi
        # legge il JS di una pagina ha gia' letto quello dell'altra.
        slug, _ic, cat = bucket(e)
        # data-start/end e data-free: sono i dati su cui lavorano il filtro
        # "quando" e "solo gratuiti", con gli stessi nomi dell'agenda. Si
        # stampano sempre, anche dove i due controlli non ci sono: ~48 byte per
        # riga (lo stesso ordine di grandezza di geo_attrs, accettato per la
        # stessa ragione) e in cambio non esiste il caso di un filtro presente
        # con il dato assente, che sarebbe un comando che nasconde righe a caso.
        out += (f'<li style="{stile}" data-province="{(e.get("prov") or "").lower()}"'
                f' data-category="{slug}"'
                f' data-start="{e["d_start"].isoformat()}"'
                f' data-end="{e["d_end"].isoformat()}"{free_attr(e)}'
                f'{geo_attrs(e)}>{thumb}<span class="com-b">'
                f'<span class="com-d">{esc(quando)}'
                f'<span class="com-cat">{esc(cat)}</span></span>'
                f'<a class="com-go" href="{_href_evento(e)}">'
                f'{esc(trunc(e.get("nome") or "", 80))}</a>'
                # L'eta' solo dove e' l'asse della pagina (le
                # /eventi-provincia-*), e solo se e' una fascia NUMERICA:
                # "tutte le eta'" e' la risposta che si da' quando non si e'
                # deciso niente, ed e' la ragione per cui e_per_bambini() non
                # la conta. Stampata sarebbe una pillola che non dice niente.
                #
                # Sta DENTRO .com-luogo e non accanto: .com-b e' un flex in
                # colonna con nowrap, quindi un figlio in piu' prende una riga
                # intera e la pillola veniva larga 251px su 375 - una fascia,
                # non un chip. Dentro lo span e' una scatola inline e si
                # dimensiona sul contenuto. Misurato, non dedotto.
                f'<span class="com-luogo">{esc(dove)}'
                + (f'<span class="com-eta">{esc(_eta_chip(e.get("eta")))}</span>'
                   if eta and fascia_eta(e.get('eta')) else '')
                # Solo "Gratuito", non il prezzo: delle righe a pagamento la
                # meta' uscirebbe troncata e meta' dice "a pagamento (da
                # verificare)", cioe' una pillola che non sa niente. Il prezzo
                # intero sta sulla scheda. La classe arriva dal guscio.
                + ('<span class="ev-pill is-free">Gratuito</span>'
                   if gratis and e_gratuito(e) else '')
                + '</span>'
                + '</span></li>')
    return out, nude


# Sotto questo numero di eventi una barra filtri e' arredamento: si scorre
# prima la lista che a decidere cosa scegliere in una tendina.
MIN_FILTRI = 12


def _landing_geo(eventi):
    """Il controllo "Vicino a me" delle pagine di intenzione.

    Stessa soglia dei filtri, e per la stessa ragione: sotto una dozzina di
    eventi si scorre prima la lista. Conta pero' quelli che hanno davvero le
    coordinate, perche' senza quelle il controllo e' un comando che non fa
    niente - ed e' il motivo per cui su /halloween.html (2 eventi a metà
    agosto) non compare.

    Il markup e' identico a quello scritto a mano in eventi.html, ids compresi:
    il modulo li cerca per id, e in una pagina il controllo e' uno solo. Parte
    `hidden` e lo accende il JS, cosi' senza JavaScript non resta un bottone
    che non risponde."""
    if sum(1 for e in eventi if coord(e)) < MIN_FILTRI:
        return ''
    return (
        '<div class="ev-geo" id="ev-geo" hidden>'
        '<button class="ev-geo-btn" id="ev-geo-go" type="button">📍 Vicino a me</button>'
        '<button class="ev-geo-btn is-alt" id="ev-geo-alt" type="button">oppure parti da un comune</button>'
        '<input class="ev-geo-in" id="ev-geo-q" list="ev-geo-list" type="text" hidden'
        ' placeholder="Scrivi un comune…"'
        ' aria-label="Scegli il comune da cui misurare la distanza" autocomplete="off">'
        '<datalist id="ev-geo-list"></datalist>'
        '<span class="ev-geo-from" id="ev-geo-from" hidden></span>'
        '<button class="ev-geo-btn is-clear" id="ev-geo-clear" type="button" hidden'
        ' aria-label="Togli il filtro per distanza">✕</button>'
        '<span class="ev-geo-chips" id="ev-geo-chips"></span>'
        '<p class="ev-geo-note ev-geo-hint" id="ev-geo-hint" role="status"></p>'
        '<p class="ev-geo-note" id="ev-geo-note"></p>'
        '</div>')


def _landing_filtri(eventi, con_prov=True, con_quando=False, con_gratis=False):
    """La barra filtri delle pagine di intenzione.

    Non e' la barra dell'agenda ricopiata: li' i controlli sono quattro fissi,
    qui ognuno compare solo se ha davvero qualcosa da scegliere. "Quando" non
    c'e' mai - queste pagine SONO gia' una risposta a quando (oggi, il weekend)
    e una seconda domanda sul tempo la contraddirebbe. La provincia sparisce
    sulle pagine per provincia, che sono gia' filtrate per definizione. E una
    tendina con una sola voce non si stampa: sarebbe un comando che non fa
    niente."""
    if len(eventi) < MIN_FILTRI:
        return ''
    cats = [f'<option value="{s}">{esc(LABELS[s])}</option>' for s in ORDER
            if any(bucket(e)[0] == s for e in eventi)]
    provs = ([f'<option value="{c.lower()}">Prov. {c}</option>'
              for c in PROVINCE_PUBBLICATE
              if any((e.get('prov') or '').upper() == c for e in eventi)]
             if con_prov else [])
    # "Quando". Spento per default: sulle pagine che SONO una risposta a
    # quando (oggi, weekend, le stagionali) una seconda domanda sul tempo
    # contraddirebbe la pagina. Acceso dove la finestra temporale non c'e'
    # affatto - le /eventi-provincia-* - dove invece risponde alla domanda che
    # l'elenco lascia aperta. I valori sono quelli dell'agenda, identici.
    tendine = ''
    if con_quando:
        tendine += ('<select class="ev-select" id="lan-quando" data-campo="date"'
                    ' aria-label="Filtra per data">'
                    '<option value="all">Sempre</option>'
                    '<option value="oggi">Oggi</option>'
                    '<option value="weekend">Weekend</option>'
                    '<option value="7">7 giorni</option>'
                    '<option value="mese">Nel mese</option>'
                    '</select>')
    if len(provs) > 1:
        tendine += ('<select class="ev-select" id="lan-dove" data-campo="province"'
                    ' aria-label="Filtra per provincia">'
                    '<option value="all">Province</option>' + "".join(provs) + '</select>')
    if len(cats) > 1:
        tendine += ('<select class="ev-select" id="lan-tipo" data-campo="category"'
                    ' aria-label="Filtra per tipo di evento">'
                    '<option value="all">Categorie</option>' + "".join(cats) + '</select>')
    # "Solo gratuiti". Parte hidden e la accende il JS solo se DIVIDE: la
    # soglia e' su quello che il filtro TOGLIE, non sulla lunghezza
    # dell'elenco, ed e' la stessa dell'agenda. Sta nella prima riga accanto
    # alla ricerca, che e' stirata e quindi cede il posto senza far crescere
    # la barra appiccicosa - la ragione per cui "vicino a me" invece sta fuori.
    chk = ('<label class="ev-chk" id="lan-gratis-box" hidden>'
           '<input type="checkbox" id="lan-gratis"> Solo gratuiti</label>'
           if con_gratis else '')
    return ('<div class="ev-toolbar lan-toolbar" id="lan-toolbar">'
            '<div class="ev-search">'
            '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor"'
            ' stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>'
            '<input type="search" id="lan-q" placeholder="Cerca un paese, una sagra…"'
            ' aria-label="Cerca in questo elenco" autocomplete="off"></div>'
            + chk + tendine +
            '</div>'
            # Fuori dalla barra, come nell'agenda: la barra e' appiccicosa e una
            # riga in piu' la farebbe crescere per tutto lo scorrimento.
            + _landing_geo(eventi) +
            '<p class="lan-count" id="lan-count" role="status"></p>'
            '<p class="lan-vuoto lan-nulla" id="lan-nulla" hidden>Con questi filtri non resta '
            'niente. <button type="button" id="lan-reset">Azzera i filtri</button></p>')


def _landing_sezione(titolo, sotto, ev, oggi, eta=False, gratis=False):
    """Un blocco di elenco con la sua intestazione. Vuoto se non c'e' niente:
    un titoletto senza righe sotto e' il modo piu' rapido per far sembrare
    generata a macchina una pagina che non lo e'."""
    if not ev:
        return ''
    testa = f'<h3>{esc(titolo)}</h3>'
    if sotto:
        testa += f'<p class="com-per">{esc(sotto)}</p>'
    righe, nude = _landing_righe(ev, oggi, eta=eta, gratis=gratis)
    return (f'<section class="com-grp"><div class="com-head"><div class="com-b">'
            f'{testa}</div></div>'
            f'<ul class="com-ev{" is-nude" if nude else ""}">{righe}</ul></section>')


def _landing_titolo(candidati):
    """Il primo title che sta nei 62 caratteri. L'elenco delle province cresce
    (CN e' arrivata ad agosto), quindi il title non si puo' scrivere a mano una
    volta: si scrive una scala di versioni e vince la piu' lunga che ci sta."""
    for t in candidati:
        if len(t) <= MAX_TITLE:
            return t
    return trunc(candidati[-1], MAX_TITLE)


def _grafo_landing(url, titolo, descr, eventi, nome_lista, crumb, oggi, padre=None):
    """CollectionPage + briciole + ItemList.

    L'ItemList RIMANDA alle pagine evento e non ripete gli Event, per la stessa
    ragione delle pagine comune: due copie dello stesso evento su due URL sono
    due elementi da validare invece di uno.

    'padre' e' (href, nome) e infila un quarto gradino nelle briciole: lo usano
    le pagine d'incrocio, che stanno sotto /eventi/oggi.html e non accanto."""
    briciole = [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": SITE_URL},
        {"@type": "ListItem", "position": 2, "name": "Eventi", "item": PAGE_URL},
    ]
    if padre:
        briciole.append({"@type": "ListItem", "position": 3, "name": padre[1],
                         "item": f"{SITE_URL}{padre[0]}"})
    briciole.append({"@type": "ListItem", "position": len(briciole) + 1,
                     "name": crumb, "item": url})
    grafo = [
        {"@type": "CollectionPage", "@id": url, "url": url, "name": titolo,
         "description": descr, "inLanguage": "it-IT",
         "isPartOf": {"@type": "WebSite", "@id": SITE_ID, "url": SITE_URL, "name": "DAOP"},
         "publisher": {"@id": ORG_ID}, "dateModified": oggi.isoformat()},
        {"@type": "BreadcrumbList", "itemListElement": briciole},
    ]
    lista = _voci_lista(eventi)
    if lista:
        grafo.append({"@type": "ItemList", "name": nome_lista,
                      "numberOfItems": len(lista), "itemListElement": lista})
    return json.dumps({"@context": "https://schema.org", "@graph": grafo},
                      ensure_ascii=False, indent=2)


def _landing_shell(spec, css, nav, foot, oggi):
    """Il guscio HTML condiviso dalle pagine di intenzione."""
    # Solo le landing provinciali hanno una provincia: /eventi/oggi.html e
    # /eventi/weekend.html sono trasversali e il meta non va stampato vuoto,
    # se no in GA4 quelle pagine riempiono i report di "(not set)".
    prov_meta = (f'\n<meta name="daop:provincia" content="{esc(spec["prov"])}">'
                 if spec.get('prov') else '')
    # Le pagine d'incrocio stanno SOTTO /eventi/oggi.html, non accanto: il
    # quarto gradino lo dice a chi legge, e _grafo_landing() lo ripete in
    # JSON-LD. Senza 'padre' le briciole restano i tre gradini di sempre.
    briciole = '<a href="/">Home</a> › <a href="/eventi.html">Eventi</a> › '
    if spec.get('padre'):
        briciole += f'<a href="{spec["padre"][0]}">{esc(spec["padre"][1])}</a> › '
    briciole += f'<span>{esc(spec["crumb"])}</span>'
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(spec['titolo'])}</title>
<meta name="description" content="{esc(spec['descr'])}">
<meta name="robots" content="{spec['robots']}">
<link rel="canonical" href="{spec['url']}">
<meta property="og:title" content="{esc(spec['titolo'])}">
<meta property="og:description" content="{esc(spec['descr'])}">
<meta property="og:type" content="website">
<meta property="og:url" content="{spec['url']}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{DEFAULT_IMG}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(spec['titolo'])}">
<meta name="twitter:description" content="{esc(trunc(spec['descr'], 120))}">
<meta name="twitter:image" content="{DEFAULT_IMG}">{prov_meta}
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{PAGINA_CSS}{COMUNE_CSS}{LANDING_CSS}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
<script src="/assets/js/locandina.js" defer></script>
<script type="application/ld+json">
{spec['jsonld']}
</script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      {briciole}
    </div>
    <h1>{esc(spec['h1'])}</h1>
    <p class="ev-when">{esc(spec['sotto'])}</p>
  </div>
</header>
<article class="ev-wrap ev-wrap--hero">
  {spec['corpo']}
  {blocco_ginetto(alto=True)}
  <div class="com-link">
    <a href="/eventi.html">Tutta l'agenda DAOP</a>
    <a href="/metodo.html">Come verifichiamo gli eventi</a>
  </div>
  <p class="ev-firma-nota">Pagina rigenerata ogni notte. Ultimo aggiornamento: {oggi.day} {MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>
</article>
</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
{('<script src="/assets/js/daop-vicino.js"></script>' + LANDING_JS) if 'lan-toolbar' in spec['corpo'] else ''}</body>
</html>
"""


# Il filtro delle pagine di intenzione. Non e' quello dell'agenda: li' ci sono
# le giornate, il calendario e le righe che si aprono, qui c'e' un elenco di
# link e basta, quindi riusarlo sarebbe piu' codice da tenere allineato che da
# risparmiare. Quello che si eredita e' l'aspetto - .ev-toolbar e .ev-select
# arrivano dal CSS di eventi.html copiato da _guscio() - e il vocabolario:
# data-province e data-category valgono le stesse cose nei due posti.
LANDING_JS = r"""<script>
(function () {
  var bar = document.getElementById('lan-toolbar');
  if (!bar) return;
  var q = document.getElementById('lan-q');
  var conta = document.getElementById('lan-count');
  var nulla = document.getElementById('lan-nulla');
  var reset = document.getElementById('lan-reset');
  var gratis = document.getElementById('lan-gratis');
  var gratisBox = document.getElementById('lan-gratis-box');
  var sel = [].slice.call(bar.querySelectorAll('.ev-select'));
  var voci = [].slice.call(document.querySelectorAll('.ev-wrap li[data-category]'));
  // Solo i gruppi che contengono voci filtrabili: nelle pagine per provincia
  // c'e' anche l'elenco delle feste che tornano ogni anno (.com-anni), che non
  // ha ne' provincia ne' categoria e non deve sparire quando si filtra.
  var gruppi = [].slice.call(document.querySelectorAll('.ev-wrap .com-grp'))
    .filter(function (g) { return g.querySelector('li[data-category]'); });
  if (!voci.length) return;

  // Il comando si accende solo se DIVIDE, ed e' la stessa soglia dell'agenda
  // applicata a quello che il filtro TOGLIE: sotto una dozzina di righe
  // nascoste si scorre prima la lista che a cercare un comando per non
  // vederle. Misurato il 04/09/2026: toglie 26 righe su Cuneo, 20 su
  // Alessandria, 8 su Asti - dove infatti resta spento da se'.
  var TOLTE_MIN = 12;
  if (gratisBox) {
    var aPagamento = voci.filter(function (l) { return l.dataset.free !== '1'; }).length;
    if (aPagamento >= TOLTE_MIN && aPagamento < voci.length) {
      gratisBox.hidden = false;
      // Solo con la casella accesa la ricerca cede il posto: vedi il CSS del
      // guscio (.ev-toolbar.has-gratis .ev-search).
      bar.classList.add('has-gratis');
    }
  }

  // La finestra di date del filtro "quando", in ISO locale. E' riscritta e
  // non condivisa con l'agenda: e' la decisione scritta in testa a questo
  // blocco (li' ci sono le giornate, il calendario e le righe che si aprono,
  // qui c'e' un elenco di link) e sono venti righe. Quello che NON puo'
  // divergere sono i valori delle opzioni, che sono gli stessi - se no i due
  // filtri si chiamerebbero uguale e farebbero due cose diverse.
  function isoLoc(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
      + '-' + String(d.getDate()).padStart(2, '0');
  }
  function finestra(modo) {
    if (!modo || modo === 'all') return null;
    var ora = new Date(); ora.setHours(0, 0, 0, 0);
    var gs = ora.getDay(); // 0 domenica ... 6 sabato
    if (modo === 'oggi') return [isoLoc(ora), isoLoc(ora)];
    if (modo === 'weekend') {
      var sab = new Date(ora); sab.setDate(ora.getDate() + (gs === 0 ? -1 : 6 - gs));
      var dom = new Date(sab); dom.setDate(sab.getDate() + 1);
      return [isoLoc(sab), isoLoc(dom)];
    }
    if (modo === '7') {
      var f7 = new Date(ora); f7.setDate(ora.getDate() + 7);
      return [isoLoc(ora), isoLoc(f7)];
    }
    if (modo === 'mese') {
      return [isoLoc(ora), isoLoc(new Date(ora.getFullYear(), ora.getMonth() + 1, 0))];
    }
    return null;
  }

  // "Vicino a me". Il modulo sta in /assets/js/daop-vicino.js ed e' lo stesso
  // dell'agenda: qui gli si dice solo dove appendere la distanza dentro una
  // riga (il blocco col comune) e come questa pagina rifa' i suoi filtri.
  var vicino = window.daopVicino ? window.daopVicino.avvia({
    voci: voci,
    riga: function (l) { return l.querySelector('.com-luogo'); },
    alRitocco: function () { testo = null; },
    alCambio: function () { applica(); }
  }) : null;

  // L'indice della ricerca si costruisce alla prima ricerca vera, non al
  // caricamento: stessa ragione che nell'agenda, leggere il testo di tutte le
  // righe e' lavoro che quasi nessun visitatore usa.
  var testo = null;
  function indice() {
    if (!testo) {
      testo = new Map(voci.map(function (l) {
        return [l, l.textContent.toLowerCase().replace(/\s+/g, ' ')];
      }));
    }
    return testo;
  }

  // Un gruppo nascosto lascerebbe in aria il suo titolo, quando il titolo e'
  // un <h2> con il suo paragrafo scritti PRIMA della sezione e fuori da essa.
  // Si risale ai fratelli precedenti saltando i paragrafi: se si arriva a un
  // titolo e' suo e sparisce con lui, se si arriva a qualsiasi altra cosa (o
  // all'inizio) non si tocca niente - cosi' il paragrafo di apertura della
  // pagina, che non ha titolo sopra, resta.
  // Oggi nessuna pagina di intenzione usa piu' quello schema (l'unica che
  // l'aveva era /eventi/oggi.html con "Oggi con i bambini", tolto perche'
  // separava gli eventi adatti alle famiglie dagli altri quando in agenda ci
  // entrano solo i primi). Resta perche' le sezioni si aggiungono e il caso
  // ricapita: costa otto righe e si accorge da solo di quando serve.
  function testaDi(g) {
    var pezzi = [], n = g.previousElementSibling;
    while (n && n.tagName === 'P') { pezzi.push(n); n = n.previousElementSibling; }
    if (n && (n.tagName === 'H2' || n.tagName === 'H3')) { pezzi.push(n); return pezzi; }
    return [];
  }
  var teste = new Map(gruppi.map(function (g) { return [g, testaDi(g)]; }));

  // Tutti i filtri TRANNE la distanza: serve due volte, una per decidere la
  // riga e una per contare quanti eventi ci sarebbero a ogni gradino di
  // distanza. I gradini devono dire quanti se ne vedrebbero davvero.
  function altri(l, f, t) {
    // Sovrapposizione e non inizio: una sagra che parte venerdi' e dura tre
    // giorni e' un evento del weekend anche se e' cominciata prima. Le date
    // sono in ISO, che si confronta come testo. Stessa regola dell'agenda.
    var fin = finestra(f.date);
    return (!f.province || f.province === 'all' || l.dataset.province === f.province) &&
           (!f.category || f.category === 'all' || l.dataset.category === f.category) &&
           (!fin || (l.dataset.start <= fin[1] && l.dataset.end >= fin[0])) &&
           (!f.gratis || l.dataset.free === '1') &&
           (!t || indice().get(l).indexOf(t) > -1);
  }

  function applica() {
    var t = q ? q.value.trim().toLowerCase() : '';
    var f = {};
    sel.forEach(function (s) {
      f[s.dataset.campo] = s.value;
      s.classList.toggle('is-on', s.value !== 'all');
    });
    f.gratis = !!(gratis && gratis.checked && gratisBox && !gratisBox.hidden);
    if (gratisBox) gratisBox.classList.toggle('is-on', f.gratis);
    var visti = 0;
    voci.forEach(function (l) {
      var ok = altri(l, f, t) && (!vicino || vicino.entro(l));
      l.hidden = !ok;
      if (ok) visti++;
    });
    gruppi.forEach(function (g) {
      var vuoto = !g.querySelector('li[data-category]:not([hidden])');
      g.hidden = vuoto;
      teste.get(g).forEach(function (n) { n.hidden = vuoto; });
    });
    if (vicino) {
      vicino.conta(function (l) { return altri(l, f, t); });
    }
    var filtrato = !!t || f.gratis || (vicino && vicino.attivo()) ||
                   sel.some(function (s) { return s.value !== 'all'; });
    // A riposo il conteggio non si scrive: la pagina lo dice gia' nell'occhiello
    // e nel paragrafo di apertura, e ripeterlo una terza volta e' rumore.
    conta.textContent = filtrato
      ? visti + (visti === 1 ? ' evento' : ' eventi') + ' con questi filtri'
      : '';
    if (nulla) nulla.hidden = visti !== 0;
  }

  if (q) q.addEventListener('input', applica);
  sel.forEach(function (s) { s.addEventListener('change', applica); });
  if (gratis) gratis.addEventListener('change', applica);
  if (reset) reset.addEventListener('click', function () {
    if (q) q.value = '';
    sel.forEach(function (s) { s.value = 'all'; });
    if (gratis) gratis.checked = false;
    applica();
    bar.scrollIntoView({ block: 'start' });
  });
  applica();
})();
</script>
"""


def _altre_landing(qui, elenco):
    """La riga di scorciatoie verso le altre pagine di intenzione, e sotto di
    essa la riga delle quattro porte.

    Le due righe stanno insieme e in questo ordine perche' rispondono a due
    domande diverse: le scorciatoie a "un'altra data", le porte a "un'altra
    cosa". Ed e' l'unico punto da toccare per averle su tutte e diciotto le
    pagine di intenzione: ogni spec_* chiama questa funzione in coda al corpo."""
    voci = "".join(f'<a href="{href}">{esc(testo)}</a>'
                   for href, testo in elenco if href != qui)
    scorciatoie = f'<div class="lan-alt">{voci}</div>' if voci else ''
    return scorciatoie + blocco_ecosistema('eventi')


def spec_oggi(events, oggi, altre):
    """/eventi/oggi.html — quello che c'e' adesso, in tutte le province."""
    url = f"{SITE_URL}/eventi/oggi.html"
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    ordina = lambda ev: sorted(ev, key=lambda e: ((e.get('citta') or ''),
                                                  (e.get('nome') or '')))
    adesso = ordina([e for e in events if in_corso(e, oggi)])
    domani = ordina([e for e in events if in_corso(e, oggi + datetime.timedelta(days=1))
                     and not in_corso(e, oggi)])
    prossimi = ordina([e for e in events if e['d_start'] > oggi])[:12] if not adesso else []

    titolo = _landing_titolo([f"Cosa fare oggi in provincia di {prov}",
                              f"Cosa fare oggi: {prov} | DAOP",
                              f"Cosa fare oggi: {prov}"])
    if adesso:
        sotto = (f"{len(adesso)} eventi in corso oggi, {data_estesa(oggi)}"
                 if len(adesso) > 1 else f"1 evento in corso oggi, {data_estesa(oggi)}")
        apertura = (f"<p>Quello che c'è <strong>oggi</strong>, {data_estesa(oggi)}, "
                    f"in provincia di {prov}: {len(adesso)} eventi, sagre e feste comprese, "
                    f"con l'orario, il comune e la scheda di ognuno. "
                    f"Le controlliamo una per una prima di pubblicarle, e questa pagina "
                    f"si rifà da sola ogni notte — quindi qui non trovi cose di ieri.</p>")
    else:
        sotto = f"Oggi, {data_estesa(oggi)}, non c'è niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Oggi in agenda non abbiamo niente, e lo "
                    "scriviamo invece di riempire la pagina: gli eventi che pubblichiamo "
                    "sono quelli che abbiamo verificato, e oggi non ce ne sono. "
                    "Qui sotto trovi i primi che arrivano.</p>")
    descr = trunc(f"Cosa fare oggi, {data_estesa(oggi)}, in provincia di {prov}: "
                  + (f"{len(adesso)} eventi in corso, verificati uno per uno da DAOP. "
                     "Orari, comune e contatti di chi organizza."
                     if adesso else
                     "l'agenda aggiornata ogni notte con i prossimi appuntamenti "
                     "per famiglie, verificati uno per uno."), 152)

    corpo = apertura
    # famiglie e' un sottoinsieme di adesso: negli elenchi si ripete, fra le
    # opzioni del filtro no, se no la stessa provincia comparirebbe due volte.
    corpo += _landing_filtri(adesso + domani + prossimi)
    corpo += _landing_sezione("In corso oggi", None, adesso, oggi)
    corpo += _landing_sezione("I primi in arrivo", "Oggi non c'è niente: questi sono i prossimi",
                              prossimi, oggi)
    # Qui c'era "Oggi con i bambini", un secondo elenco con i soli eventi
    # segnati "Adatto Famiglie" nel foglio. Tolto, per due ragioni che si
    # sommano.
    #
    # La prima: in agenda ci entra solo quello che abbiamo gia' scelto per le
    # famiglie. Un sottoelenco "adatti alle famiglie" dice implicitamente che
    # gli altri non lo sono, cioe' smentisce il criterio con cui la pagina e'
    # fatta - e su una pagina dove il 93% delle righe ha quel flag separava
    # praticamente niente da praticamente tutto.
    #
    # La seconda: quel flag non descrive la riga a cui e' attaccato. Il
    # giudizio lo diamo sulla LOCANDINA - la manifestazione nel suo insieme e'
    # roba da famiglie - ma i sotto-eventi li pubblichiamo tutti, uno per riga,
    # e poi li raggruppiamo per manifestazione. Il verdetto della locandina
    # finisce cosi' timbrato identico su ogni riga, compresi i sotto-eventi che
    # per i bambini non sono: nei dati dell'11/08 le manifestazioni con piu'
    # righe sono 30 e in 26 il flag e' lo stesso su tutte. "San Liberato 2026"
    # sono 19 righe tutte "Si", e dentro ci sono la sagra delle 22:30 e lo
    # spettacolo comico delle 20:45.
    #
    # Filtrare le righe con quel flag non separa quindi i sotto-eventi adatti
    # dagli altri: ripete su ognuno la risposta data alla locandina. Per fare
    # quella cernita servirebbe un giudizio per sotto-evento, che nel foglio
    # non c'e'.
    #
    # Resta la sezione "Cosa c'e' per i bambini" delle pagine comune: quella
    # non usa questo flag ma e_per_bambini(), cioe' una fascia d'eta'
    # dichiarata o laboratori/burattini/giochi scritti nel programma - e dice
    # "pensati PER i bambini", non "adatti", e infatti scrive a chiare lettere
    # che il resto e' comunque adatto alle famiglie.
    corpo += _landing_sezione("Domani", "Da tenere d'occhio", domani, oggi)
    # Da qui in poi questa pagina fa anche da indice delle tre provinciali. E'
    # il mestiere che le resta: sulla query trasversale eventi.html vince
    # comunque - piu' contenuto, piu' autorita', e non gliela togliamo - mentre
    # "oggi in provincia di X" e' l'incrocio che nessuna pagina copriva.
    corpo += (f"<h2>Provincia per provincia</h2>"
              f"<p>Le stesse cose di oggi, divise per provincia: sono le pagine da "
              f"salvare se guardi sempre la stessa zona.</p>"
              + _blocco_incroci('oggi', events, oggi))
    corpo += _altre_landing("/eventi/oggi.html", altre)

    return {
        # Percorso web, non di filesystem: sempre con la barra normale. Con
        # os.path.join() diventava "eventi\oggi.html" su Windows e
        # "eventi/oggi.html" in Actions, cioe' due chiavi diverse per la stessa
        # pagina nel registro, che accumulava voci morte a ogni run. La scrittura
        # su disco fa os.path.join(ROOT, path) e su Windows la barra normale va
        # bene lo stesso.
        'path': "eventi/oggi.html", 'url': url,
        'titolo': titolo, 'descr': descr,
        # L'H1 nomina le province: metà della query e' il posto, e prima
        # stavano solo nel title. Non e' la de-cannibalizzazione di
        # eventi.html - quella non si fa - e' questa pagina che dice cosa
        # copre.
        'h1': f"Cosa fare oggi in provincia di {prov}", 'sotto': sotto, 'crumb': "Oggi",
        'corpo': corpo, 'robots': "index, follow",
        'jsonld': _grafo_landing(url, titolo, descr, adesso or prossimi,
                                 "Eventi di oggi", "Oggi", oggi),
        'eventi': len(adesso),
    }


def spec_weekend(events, oggi, altre):
    """/eventi/weekend.html — sabato e domenica, quelli veri del calendario."""
    sab, dom = weekend_range(oggi)
    url = f"{SITE_URL}/eventi/weekend.html"
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    del_weekend = sorted((e for e in events
                          if e['d_start'] <= dom and e['d_end'] >= sab),
                         key=lambda e: (e['d_start'], (e.get('citta') or '')))
    di_sabato = [e for e in del_weekend if in_corso(e, sab)]
    di_domenica = [e for e in del_weekend if in_corso(e, dom)]
    quando = (f"sabato {sab.day} e domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}"
              if sab.month == dom.month else
              f"sabato {sab.day} {MESI_LUNGHI[sab.month - 1]} e "
              f"domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}")

    titolo = _landing_titolo([f"Eventi del weekend in provincia di {prov}",
                              f"Eventi del weekend: {prov} | DAOP",
                              f"Eventi del weekend: {prov}"])
    if del_weekend:
        sotto = f"{len(del_weekend)} eventi {quando}"
        apertura = (f"<p>Il programma del weekend — {quando} — in provincia di {prov}: "
                    f"{len(di_sabato)} eventi il sabato e {len(di_domenica)} la domenica, "
                    f"con gli orari e il comune di ognuno. Le date le rifacciamo ogni notte, "
                    f"quindi il weekend qui sopra è sempre il prossimo, non quello passato.</p>")
    else:
        sotto = f"Per {quando} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per questo weekend non abbiamo ancora niente "
                    "di verificato in agenda. Le sagre arrivano spesso a ridosso: "
                    "questa pagina si rifà ogni notte, e appena entrano compaiono qui.</p>")
    descr = trunc(f"Eventi, sagre e feste del weekend ({quando}) in provincia di {prov}: "
                  + (f"{len(del_weekend)} appuntamenti verificati da DAOP, con orari e comune."
                     if del_weekend else
                     "l'agenda si aggiorna ogni notte, appena arrivano le date."), 152)

    corpo = apertura
    corpo += _landing_filtri(del_weekend)
    corpo += _landing_sezione(f"Sabato {sab.day} {MESI_LUNGHI[sab.month - 1]}", None,
                              di_sabato, oggi)
    corpo += _landing_sezione(f"Domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}", None,
                              di_domenica, oggi)
    # Qui c'era "Il weekend con i bambini": tolto per le stesse ragioni
    # scritte per esteso in spec_oggi.
    # E qui comincia il mestiere nuovo: indice delle tre provinciali.
    corpo += (f"<h2>Provincia per provincia</h2>"
              f"<p>Lo stesso weekend, diviso per provincia: sono le pagine da salvare "
              f"se guardi sempre la stessa zona.</p>"
              + _blocco_incroci('weekend', events, oggi))
    corpo += _altre_landing("/eventi/weekend.html", altre)

    return {
        'path': "eventi/weekend.html", 'url': url,  # barra normale: vedi spec_oggi()
        'titolo': titolo, 'descr': descr,
        # Le province nell'H1: vedi la nota in spec_oggi.
        'h1': f"Eventi del weekend in provincia di {prov}",
        'sotto': sotto, 'crumb': "Weekend",
        'corpo': corpo, 'robots': "index, follow",
        'jsonld': _grafo_landing(url, titolo, descr, del_weekend,
                                 "Eventi del weekend", "Weekend", oggi),
        'eventi': len(del_weekend),
    }


# ---------------------------------------------------------------------------
# Le pagine d'incrocio: provincia X finestra temporale.
#
# Perche' esistono, misurato sull'export Search Console del 14/08/2026: le
# query generiche chiedono quasi sempre le DUE cose insieme - "sagre provincia
# di alessandria oggi" (372 impressioni), "eventi asti e provincia oggi" (251),
# "eventi provincia di asti questo weekend" (115). Quello che avevamo era o
# l'una o l'altra: le sagre-provincia-* hanno la provincia nell'H1 e nessuna
# finestra, oggi.html e weekend.html hanno la finestra e la provincia solo nel
# title. Nessuna pagina copriva l'incrocio, e infatti li' stiamo tutti in
# posizione 8-10 con un CTR del 2,77% - contro il 9,47% dei nomi propri.
#
# Sono SEI, cioe' un insieme chiuso: 3 province x 2 finestre. Non e' scaled
# content per la stessa ragione per cui non lo sono le 12 pagine comune - il
# numero non cresce con i dati, e la domanda esiste gia' misurata.
#
# Quello che NON si fa per de-cannibalizzare, ed e' scritto in CLAUDE.md: non
# si tocca l'H1 di eventi.html. Vale 13.553 impressioni, il 36% del sito.
INCROCI = (
    ('oggi', "Cosa fare oggi", "/eventi/oggi.html", "Oggi"),
    ('weekend', "Eventi del weekend", "/eventi/weekend.html", "Weekend"),
)

# La finestra su cui si decide se la pagina sta in indice. NON e' il numero di
# eventi di oggi, ed e' la differenza che conta: "oggi in provincia di Cuneo"
# passa da 0 a 6 e torna a 0 nel giro di una settimana, e un robots che cambia
# ogni notte e' peggio di uno sbagliato - Google smette di fidarsi della
# direttiva e la pagina si ricommitta tutti i giorni. Con la finestra larga la
# pagina entra in indice a stagione aperta e ne esce a stagione chiusa, una
# volta sola per verso.
FINESTRA_INCROCIO = 30


def href_incrocio(prov, modo):
    """L'indirizzo della pagina d'incrocio. Slug parlante come le
    sagre-provincia-*, e senza anno: e' la stessa regola di /ferragosto.html,
    l'URL deve invecchiare invece di rinascere ogni stagione."""
    return f"/eventi/{modo}-provincia-{slugify(PROVINCE_NOMI.get(prov, prov))}.html"


def _in_finestra(events, prov, oggi, giorni=FINESTRA_INCROCIO):
    """Gli eventi di quella provincia da oggi ai prossimi `giorni`."""
    fine = oggi + datetime.timedelta(days=giorni)
    return [e for e in events
            if (e.get('prov') or '').upper() == prov
            and e['d_end'] >= oggi and e['d_start'] <= fine]


def _blocco_incroci(modo, events, oggi, qui=None):
    """I link alle tre pagine provinciali di una finestra.

    Sta in fondo alle due pagine trasversali (che da qui in poi fanno anche da
    indice) e in cima a ogni provinciale, che cosi' rimanda alle sorelle. Il
    numero accanto al nome non e' decorazione: e' la promessa che dice se vale
    la pena entrare, come i conteggi accanto ai comuni."""
    voci = []
    for c in PROVINCE_PUBBLICATE:
        href = href_incrocio(c, modo)
        if href == qui:
            continue
        nome = PROVINCE_NOMI.get(c, c)
        quanti = len(_in_finestra(events, c, oggi))
        eti = f"{nome} ({quanti})" if quanti else nome
        voci.append(f'<a href="{href}">{esc(eti)}</a>')
    return f'<div class="com-link">{"".join(voci)}</div>' if voci else ''


def spec_incrocio(prov, modo, events, hub, oggi, altre):
    """/eventi/<oggi|weekend>-provincia-<nome>.html — la provincia E il quando."""
    nome_prov = PROVINCE_NOMI.get(prov, prov)
    href = href_incrocio(prov, modo)
    url = f"{SITE_URL}{href}"
    padre = next((p for m, _t, p, _c in INCROCI if m == modo), "/eventi.html")
    padre_nome = next((c for m, _t, _p, c in INCROCI if m == modo), "Eventi")
    finestra = _in_finestra(events, prov, oggi)
    ordina = lambda ev: sorted(ev, key=lambda e: (e['d_start'], (e.get('citta') or ''),
                                                  (e.get('nome') or '')))
    sagre_href = f"/sagre-provincia-{slugify(nome_prov)}.html"

    if modo == 'oggi':
        adesso = ordina([e for e in events
                         if (e.get('prov') or '').upper() == prov and in_corso(e, oggi)])
        domani = ordina([e for e in events
                         if (e.get('prov') or '').upper() == prov
                         and in_corso(e, oggi + datetime.timedelta(days=1))
                         and not in_corso(e, oggi)])
        prossimi = ordina([e for e in _in_finestra(events, prov, oggi)
                           if e['d_start'] > oggi])[:12] if not adesso else []
        principale = adesso
        # Il title dice "sagre", l'H1 dice "cosa fare": non e' una svista.
        #
        # Search Console 09-15/08/2026: sulle query con dentro "oggi" il sito
        # prende 2.317 impressioni e le converte al 3,58%, il peggiore dei
        # cluster grossi. Guardando quali query sono, il motivo si vede:
        #   "sagre provincia di alessandria oggi"      362 imp,  9 clic, pos 8,4
        #   "eventi provincia alessandria oggi"        108 imp,  3 clic, pos 8,8
        #   "sagre provincia alessandria oggi"          84 imp,  4 clic, pos 8,6
        #   "cosa fare oggi in provincia di alessandria" 92 imp, 5 clic, pos 7,1
        # La query grossa vuole "sagre" E "oggi". Questa pagina aveva "oggi" ma
        # non "sagre"; /sagre-provincia-<x>.html ha "sagre" ma non "oggi".
        # Nessuna delle due matcha la domanda intera, Google ne sceglie una a
        # caso e stanno tutte e due in fondo alla prima pagina: le due landing
        # si cannibalizzano su una query da 446 impressioni.
        #
        # Quindi il title prende le due parole che pesano nelle query - "sagre"
        # (446 imp) ed "eventi" (265) - e lascia andare "cosa fare" (131), che
        # in 62 caratteri non ci sta insieme al resto.
        #
        # L'H1 invece resta "Cosa fare oggi": e' la riga che legge una persona
        # arrivata sulla pagina, non il crawler, e "cosa fare" e' come la
        # domanda se la fa in testa. Title e H1 rispondono a due lettori
        # diversi, e la parola "sagre" in pagina c'e' comunque - nella
        # description, nell'apertura e in meta' dei nomi degli eventi.
        titolo = _landing_titolo([f"Sagre ed eventi di oggi in provincia di {nome_prov} | DAOP",
                                  f"Sagre ed eventi di oggi in provincia di {nome_prov}",
                                  f"Sagre ed eventi oggi: {nome_prov}"])
        h1 = f"Cosa fare oggi in provincia di {nome_prov}"
        crumb = nome_prov
        comuni = len({_key(e.get('citta')) for e in adesso if (e.get('citta') or '').strip()})
        if adesso:
            sotto = (f"{len(adesso)} eventi in corso oggi, {data_estesa(oggi)}"
                     if len(adesso) > 1 else f"1 evento in corso oggi, {data_estesa(oggi)}")
            apertura = (f"<p>Quello che c'è <strong>oggi</strong>, {data_estesa(oggi)}, "
                        f"in provincia di {esc(nome_prov)}: "
                        f"<strong>{len(adesso)} eventi</strong>"
                        + (f" in {comuni} comuni diversi" if comuni > 1 else "")
                        + ", con l'orario, il paese e la scheda di ognuno. Li verifichiamo "
                          "uno per uno prima di pubblicarli, e la pagina si rifà da sola "
                          "ogni notte: qui non trovi cose di ieri.</p>")
        else:
            sotto = f"Oggi, {data_estesa(oggi)}, in provincia di {nome_prov} non c'è niente"
            apertura = (f"<p class=\"lan-vuoto\">Oggi in provincia di {esc(nome_prov)} non "
                        f"abbiamo niente in agenda, e lo scriviamo invece di riempire la "
                        f"pagina con eventi di un'altra provincia: quello che pubblichiamo "
                        f"è quello che abbiamo verificato. Qui sotto trovi i primi in "
                        f"arrivo da queste parti.</p>")
        descr = trunc(f"Cosa fare oggi, {data_estesa(oggi)}, in provincia di {nome_prov}: "
                      + (f"{len(adesso)} eventi in corso, sagre e feste comprese, "
                         "verificati uno per uno da DAOP."
                         if adesso else
                         "i prossimi appuntamenti per famiglie, verificati uno per uno "
                         "da DAOP. L'agenda si rifà ogni notte."), 152)
        corpo = apertura
        corpo += _landing_filtri(adesso + domani + prossimi, con_prov=False)
        corpo += _landing_sezione("In corso oggi", None, adesso, oggi)
        corpo += _landing_sezione("I primi in arrivo",
                                  "Oggi non c'è niente: questi sono i prossimi",
                                  prossimi, oggi)
        corpo += _landing_sezione("Domani", "Da tenere d'occhio", domani, oggi)
        nome_lista = f"Eventi di oggi in provincia di {nome_prov}"
    else:
        sab, dom = weekend_range(oggi)
        del_weekend = ordina([e for e in events
                              if (e.get('prov') or '').upper() == prov
                              and e['d_start'] <= dom and e['d_end'] >= sab])
        di_sabato = [e for e in del_weekend if in_corso(e, sab)]
        di_domenica = [e for e in del_weekend if in_corso(e, dom)]
        principale = del_weekend
        quando = (f"sabato {sab.day} e domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}"
                  if sab.month == dom.month else
                  f"sabato {sab.day} {MESI_LUNGHI[sab.month - 1]} e "
                  f"domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}")
        titolo = _landing_titolo([f"Eventi del weekend in provincia di {nome_prov} | DAOP",
                                  f"Eventi del weekend in provincia di {nome_prov}",
                                  f"Eventi weekend: {nome_prov}"])
        h1 = f"Eventi del weekend in provincia di {nome_prov}"
        crumb = nome_prov
        comuni = len({_key(e.get('citta')) for e in del_weekend
                      if (e.get('citta') or '').strip()})
        if del_weekend:
            sotto = f"{len(del_weekend)} eventi {quando}, in provincia di {nome_prov}"
            apertura = (f"<p>Il programma del weekend — {quando} — in provincia di "
                        f"{esc(nome_prov)}: <strong>{len(del_weekend)} appuntamenti</strong>"
                        + (f" in {comuni} comuni" if comuni > 1 else "")
                        + f", {len(di_sabato)} il sabato e {len(di_domenica)} la domenica, "
                          "con gli orari e il paese di ognuno. Le date le rifacciamo ogni "
                          "notte, quindi il weekend qui sopra è sempre il prossimo.</p>")
        else:
            sotto = f"Per {quando} in provincia di {nome_prov} non c'è ancora niente"
            apertura = (f"<p class=\"lan-vuoto\">Per questo weekend in provincia di "
                        f"{esc(nome_prov)} non abbiamo ancora niente di verificato. Le "
                        f"sagre di paese arrivano spesso a ridosso, e i programmi delle "
                        f"pro loco escono a pochi giorni dalla festa: questa pagina si "
                        f"rifà ogni notte, e appena entrano compaiono qui.</p>")
        descr = trunc(f"Eventi, sagre e feste del weekend ({quando}) in provincia di "
                      f"{nome_prov}: "
                      + (f"{len(del_weekend)} appuntamenti verificati da DAOP, "
                         "con orari e comune."
                         if del_weekend else
                         "l'agenda si aggiorna ogni notte, appena arrivano le date."), 152)
        corpo = apertura
        corpo += _landing_filtri(del_weekend, con_prov=False)
        corpo += _landing_sezione(f"Sabato {sab.day} {MESI_LUNGHI[sab.month - 1]}", None,
                                  di_sabato, oggi)
        corpo += _landing_sezione(f"Domenica {dom.day} {MESI_LUNGHI[dom.month - 1]}", None,
                                  di_domenica, oggi)
        nome_lista = f"Eventi del weekend in provincia di {nome_prov}"

    # I comuni che hanno qualcosa nella finestra larga, non tutti quelli della
    # provincia: qui la pagina risponde a "adesso", e un elenco di paesi dove
    # non c'e' niente e' una promessa che la pagina non mantiene.
    vivi = {_key(e.get('citta')) for e in finestra if (e.get('citta') or '').strip()}
    comuni_link = sorted((d for d in (hub or {}).values()
                          if d['prov'] == prov and _key(d['nome']) in vivi),
                         key=lambda d: -len(d['futuri']))[:12]
    if comuni_link:
        link = "".join(f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
                       for d in comuni_link)
        corpo += (f"<h2>I comuni della provincia di {esc(nome_prov)} con eventi in "
                  f"programma</h2>"
                  f'<div class="com-link">{link}</div>')

    # Il link alla sorella senza finestra temporale: chi arriva qui da "oggi" e
    # non trova niente ha comunque una pagina dove andare, e le due si passano
    # autorita' invece di farsi concorrenza.
    quando_no = "oggi" if modo == 'oggi' else "questo weekend"
    corpo += (f'<p>Se quello che cerchi non è per forza {quando_no}: '
              f'<a href="{sagre_href}">tutte le sagre e le feste della provincia di '
              f'{esc(nome_prov)}</a>, in ordine di data e mese per mese, oppure '
              f'<a href="{href_eventi_prov(prov)}">tutti gli eventi e le attività per '
              f'bambini in provincia di {esc(nome_prov)}</a>, che è l\'agenda '
              f'completa.</p>')

    fonte = fonte_provincia(prov)
    corpo += credito_fonte(
        fonte, f'Gli eventi della provincia di {esc(nome_prov)} arrivano da', breve=True)

    corpo += f'<h2>Le altre province</h2>{_blocco_incroci(modo, events, oggi, qui=href)}'
    corpo += _altre_landing(href, altre)

    return {
        'path': href.lstrip('/'), 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': h1, 'sotto': sotto, 'crumb': crumb,
        'padre': (padre, padre_nome),
        'corpo': corpo,
        # Vedi FINESTRA_INCROCIO: si decide sulla finestra larga, non su oggi.
        'robots': "index, follow" if len(finestra) >= MIN_LANDING else "noindex, follow",
        'prov': prov,
        'jsonld': _grafo_landing(url, titolo, descr, principale, nome_lista, crumb, oggi,
                                 padre=(padre, padre_nome)),
        'eventi': len(principale),
    }


# ===========================================================================
# IL CALENDARIO DELLE STAGIONALI
#
# Le pagine stagionali devono nascere, indicizzarsi, comparire nelle
# scorciatoie, annunciarsi in home e ritirarsi DA SOLE. Il pezzo che lo rende
# possibile e' qui: nessuna data di festa e' scritta a mano da nessuna parte,
# nemmeno quelle che sembrano fisse.
#
# Perche' non basta cablarle: Carnevale e Pasqua si muovono di un mese pieno.
#   2027  Pasqua 28 mar   martedi' grasso  9 feb
#   2028  Pasqua 16 apr   martedi' grasso 29 feb
#   2030  Pasqua 21 apr   martedi' grasso  5 mar
# Una tabella di date andrebbe riempita a mano ogni anno, cioe' esattamente la
# cosa da cui questo modulo deve liberare.
# ===========================================================================

def pasqua(anno):
    """La domenica di Pasqua (computus gregoriano, Meeus/Jones/Butcher).

    Aritmetica pura: nessuna dipendenza, nessuna tabella, vale fino al 4099.
    Da qui derivano Carnevale e Pasqua, e quindi meta' del calendario."""
    a = anno % 19
    b, c = divmod(anno, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ll = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ll) // 451
    mese, giorno = divmod(h + ll - 7 * m + 114, 31)
    return datetime.date(anno, mese, giorno + 1)


# NB rito: il Piemonte e' rito ROMANO, quindi il Carnevale finisce al martedi'
# grasso (Pasqua-47). A Milano - rito ambrosiano - finisce quattro giorni dopo.
# Se un domani si coprisse la provincia di Milano, questo va gestito.
def _finestra_carnevale(anno):
    p = pasqua(anno)
    return (p - datetime.timedelta(days=52),   # giovedi' grasso
            p - datetime.timedelta(days=47),   # martedi' grasso
            p - datetime.timedelta(days=47))


def _finestra_pasqua(anno):
    p = pasqua(anno)
    return (p - datetime.timedelta(days=2),    # venerdi' santo
            p,
            p + datetime.timedelta(days=1))    # pasquetta


# La finestra di Ferragosto e' il 14-16 agosto: la vigilia, il giorno e il
# giorno dopo. NON e' "il weekend piu' vicino al 15", e la differenza non e'
# accademica: nel 2026 il 15 cade di sabato e un weekend coinciderebbe con
# /eventi/weekend.html - due nostre pagine sulla stessa lista, e quella che
# perde e' la nuova; nel 2027 cade di domenica e il 14 resterebbe fuori. Le
# tre date fisse tengono il ponte in tutti e due i casi.
FERRAGOSTO_DA, FERRAGOSTO_A = 14, 16


def _finestra_ferragosto(anno):
    return (datetime.date(anno, 8, FERRAGOSTO_DA),
            datetime.date(anno, 8, 15),
            datetime.date(anno, 8, FERRAGOSTO_A))


def prossima_finestra(calcola, oggi):
    """(inizio, clou, fine) della prossima occorrenza utile di una festa.

    Fino all'ultimo giorno e' quella di quest'anno - la pagina serve ancora a
    chi cerca cosa c'e' oggi - e dal giorno dopo diventa quella dell'anno
    prossimo: la stagionale passa in fuori stagione DA SOLA, senza che nessuno
    se ne ricordi. E' il pezzo che rende inutile segnarsi le date in agenda.

    `calcola(anno)` restituisce la finestra identificata da quell'anno, che e'
    sempre l'anno del giorno CLOU. Per le feste che sforano nell'anno dopo -
    Capodanno: clou 31 dicembre, coda 1° gennaio - questo vuol dire che la
    finestra ancora aperta il 1° gennaio e' quella dell'anno PRECEDENTE.

    Da qui i tre tentativi, e non due: partendo da oggi.year il 1° gennaio si
    saltava la finestra in corso e si andava dritti a quella di dodici mesi
    dopo, lasciando Capodanno scoperto proprio il giorno di Capodanno. Il caso
    si vede solo guardando lo stretto delle feste giorno per giorno."""
    for anno in (oggi.year - 1, oggi.year, oggi.year + 1):
        da, clou, a = calcola(anno)
        if oggi <= a:
            return da, clou, a
    return da, clou, a


def ferragosto_range(oggi):
    """(14, 15, 16 agosto) del prossimo Ferragosto utile."""
    return prossima_finestra(_finestra_ferragosto, oggi)


def spec_ferragosto(st, events, oggi, altre):
    """/ferragosto.html — il 14-16 agosto, la pagina stagionale che invecchia.

    Due cose non ovvie, e sono il motivo per cui la pagina esiste.

    **L'anno non sta nell'indirizzo.** Sta nel title e nell'H1, e li' lo
    riscrive il generatore. Una /ferragosto-2026.html sarebbe una pagina nuova
    ogni agosto: si ricomincerebbe da zero ogni anno proprio sulla query
    stagionale che si vince solo con l'anzianita' dell'URL.

    **Non e' un filtro di date.** Se fosse solo l'elenco del 14-16 sarebbe un
    doppione di /eventi/weekend.html tutte le volte che il 15 cade di sabato o
    domenica - cioe' spesso - e il doppione lo perde la pagina senza autorita'.
    Quello che ha di suo e' la domanda di Ferragosto: come ci si regola quel
    giorno, e dove si mangia. Da qui il blocco che manda a /luoghi.html.
    """
    da, il15, a = ferragosto_range(oggi)
    anno = il15.year
    url = f"{SITE_URL}/ferragosto.html"
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    finestra = sorted((e for e in events if e['d_start'] <= a and e['d_end'] >= da),
                      key=lambda e: (e['d_start'], (e.get('citta') or '')))
    comuni = len({(e.get('citta') or '').strip() for e in finestra if e.get('citta')})
    gratis = sum(1 for e in finestra if e_gratuito(e))

    titolo = _landing_titolo([f"Ferragosto {anno} con i bambini: {prov}",
                              f"Cosa fare a Ferragosto {anno} con i bambini | DAOP",
                              f"Cosa fare a Ferragosto {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi dal 14 al 16 agosto in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento nel ponte di Ferragosto")
        apertura = (
            f"<p>Il <strong>15 agosto {anno}</strong> cade di "
            f"{GIORNI[il15.weekday()]}, e col 14 e il 16 fa un ponte di tre "
            f"giorni. Qui sotto ci sono i <strong>{len(finestra)} eventi</strong> "
            f"che abbiamo verificato uno per uno in {comuni} comuni fra le "
            f"province di {prov}"
            + (f", di cui {gratis} gratuiti" if gratis else "")
            + ". Di ognuno trovi l'orario, il comune e chi lo organizza, e "
              "l'elenco si rifà da solo ogni notte: a Ferragosto i programmi "
              "cambiano fino all'ultimo.</p>")
        descr = trunc(
            f"Cosa fare a Ferragosto {anno} con i bambini in provincia di {prov}: "
            f"{len(finestra)} fra sagre, feste ed eventi dal 14 al 16 agosto, "
            "verificati uno per uno da DAOP.", 152)
    else:
        sotto = f"Per il 14-16 agosto {anno} non c'è ancora niente in agenda"
        apertura = (
            f"<p class=\"lan-vuoto\">Per Ferragosto {anno} in agenda non abbiamo "
            "ancora niente, e lo scriviamo invece di riempire la pagina. Le "
            "sagre d'agosto arrivano tardi: i programmi si chiudono a luglio e "
            "molte pro loco li pubblicano a pochi giorni dalla festa. Questa "
            "pagina si rifà ogni notte, quindi appena entrano compaiono qui.</p>")
        descr = trunc(
            f"Cosa fare a Ferragosto {anno} con i bambini in provincia di {prov}: "
            "sagre, feste ed eventi del 14-16 agosto, verificati uno per uno da "
            "DAOP. L'agenda si aggiorna ogni notte.", 152)

    corpo = apertura
    # Il pezzo che questa pagina ha e /eventi/weekend.html no. Sono le due
    # domande che a Ferragosto si fanno tutti e a cui un elenco di eventi non
    # risponde: come ci si regola quel giorno, e dove si mangia. Il secondo e'
    # anche l'unico link a /luoghi.html che parta dal CORPO di una pagina e non
    # dalla nav - finora ne arrivavano zero, ed e' la ragione per cui quella
    # pagina non prende traffico.
    corpo += (
        '<p>Ferragosto in zona non è una cosa sola: la mattina ci sono le '
        'processioni e i mercatini, il pomeriggio i giochi d\'acqua e i '
        'laboratori, la sera lo stand gastronomico e i fuochi. Alle sagre di '
        'paese di solito non si prenota e si paga alla cassa, quindi con i '
        'bambini si arriva presto e si decide sul posto. Il <strong>pranzo del '
        '15</strong> invece si prenota, e va prenotato con giorni di anticipo: '
        'gli <a href="/luoghi.html">agriturismi e i posti dove si mangia con i '
        'bambini</a> stanno nel catalogo dei luoghi, con telefono e indirizzo. '
        'Se il 15 piove, la stessa pagina dice quali sono al coperto.</p>')
    corpo += _landing_filtri(finestra)
    for giorno in (da, il15, a):
        del_giorno = [e for e in finestra if in_corso(e, giorno)]
        corpo += _landing_sezione(
            f"{GIORNI[giorno.weekday()].capitalize()} {giorno.day} "
            f"{MESI_LUNGHI[giorno.month - 1]}",
            "Ferragosto" if giorno == il15 else None, del_giorno, oggi)
    corpo += _altre_landing("/ferragosto.html", altre)

    return {
        'path': "ferragosto.html", 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': f"Cosa fare a Ferragosto {anno}", 'sotto': sotto, 'crumb': "Ferragosto",
        'corpo': corpo,
        # Stessa regola di sagre-provincia-*: sotto soglia la pagina resta
        # online ma esce dall'indice. E' quello che la tiene sana i mesi in cui
        # e' vuota, senza mai cambiare indirizzo.
        'robots': "index, follow" if len(finestra) >= MIN_LANDING else "noindex, follow",
        'jsonld': _grafo_landing(url, titolo, descr, finestra,
                                 f"Eventi di Ferragosto {anno}", "Ferragosto", oggi),
        'eventi': len(finestra),
    }


# ---------------------------------------------------------------------------
# /halloween.html — la seconda pagina stagionale, e la prima in cui il fossato
# NON ci aiuta.
#
# Le sagre di paese le vinciamo sul nome proprio: "festa cassinasco 2026" fa
# CTR 31% perche' non le pubblica nessun altro. Halloween e' l'opposto - query
# nazionale e generica, cioe' la colonna in cui stiamo in posizione 8-10 col
# 2,77% - e i concorrenti fanno "Halloween in Italia" da dieci anni. La pagina
# si fa lo stesso, ma quello che puo' prendere sono le code lunghe con dentro
# un nome proprio ("halloween castello di <paese>"), non la query secca.
#
# Da qui la data di nascita: creata a settembre, cioe' con due mesi di
# anticipo, e in noindex finche' non ha eventi. E' l'unico rimpianto di
# /ferragosto.html, nata due giorni prima: su una stagionale l'asset e'
# l'anzianita' dell'URL, ed e' anche il motivo per cui l'anno non ci sta
# dentro.
#
# La finestra e' fissa, 25 ottobre - 2 novembre: prende il weekend prima
# comunque cada, la notte del 31 e Ognissanti, che in Italia e' festa e sposta
# le gite. Stessa ragione del 14-16 di Ferragosto: "il weekend piu' vicino"
# coinciderebbe con /eventi/weekend.html un anno su due.
HALLOWEEN_DA = (10, 25)
HALLOWEEN_A = (11, 2)


def _finestra_halloween(anno):
    return (datetime.date(anno, *HALLOWEEN_DA),
            datetime.date(anno, 10, 31),
            datetime.date(anno, *HALLOWEEN_A))


def halloween_range(oggi):
    """(25 ottobre, 31 ottobre, 2 novembre) del prossimo Halloween utile."""
    return prossima_finestra(_finestra_halloween, oggi)


# Le finestre delle altre, tutte identificate dall'anno del giorno CLOU.
#
# LE FESTE DI DICEMBRE SONO TRE PAGINE, NON UNA. Il periodo e' un continuo
# dall'Immacolata all'Epifania, ma le domande sono tre e diverse:
#   "mercatini di natale <paese>"     -> /natale.html      1 - 26 dicembre
#   "capodanno con bambini <paese>"   -> /capodanno.html  27 dic - 1 gennaio
#   "calza della befana <paese>"      -> /befana.html      2 -  6 gennaio
# Su un URL solo si farebbero concorrenza fra loro: e' lo stesso errore che
# avevamo fra oggi-provincia-* e sagre-provincia-*, dove nessuna delle due
# rispondeva alla domanda intera e stavano tutte e due in fondo alla prima
# pagina. Tagliate cosi' coprono tutto lo stretto delle feste senza buchi e
# restano DISGIUNTE, che e' l'invariante su cui si regge blocco_stagione():
# "la prima che risponde vince". Lo verifica _controlla_stagioni().
def _finestra_natale(anno):
    return (datetime.date(anno, 12, 1),
            datetime.date(anno, 12, 25),
            datetime.date(anno, 12, 26))


def _finestra_capodanno(anno):
    # L'anno e' quello del CLOU, cioe' del 31 dicembre: la finestra sfora nel
    # successivo. Il giorno clou e' il 31 e non il 1° perche' e' li' che stanno
    # gli eventi — il 1° gennaio in zona e' quasi tutto chiuso.
    return (datetime.date(anno, 12, 27),
            datetime.date(anno, 12, 31),
            datetime.date(anno + 1, 1, 1))


def _finestra_befana(anno):
    return (datetime.date(anno, 1, 2),
            datetime.date(anno, 1, 6),
            datetime.date(anno, 1, 6))


def spec_halloween(st, events, oggi, altre):
    """/halloween.html — il 25 ottobre-2 novembre, con la domanda vera in cima.

    **Non e' un filtro di date.** Se fosse solo l'elenco della finestra sarebbe
    /eventi/weekend.html con un altro titolo, e il doppione lo perde la pagina
    senza autorita'. Quello che ha di suo e' la domanda che a Halloween si
    fanno tutti i genitori e a cui un elenco non risponde: **fa paura o no?**
    Un bambino di quattro anni e uno di dodici cercano la stessa parola e
    vogliono due cose opposte, e l'eta' e' l'unico dato che abbiamo e i siti
    nazionali no.

    Quello che NON si fa, ed e' la trappola: una sezione "questi fanno paura",
    dedotta da parole tipo horror/brivido nel programma. Sarebbe un giudizio
    nostro su una riga altrui, ricavato da un titolo, e sbagliarlo vuol dire
    mandare un bambino di quattro anni in una casa infestata o togliere
    pubblico a un evento che paura non fa. Si fa come per "ci vado con i
    bambini?" nelle pagine comune: si da' la regola per leggere la pagina -
    dove l'eta' e' dichiarata la stampiamo, se non c'e' si legge il programma -
    e si mette in evidenza solo il gruppo su cui il dato c'e' davvero,
    e_per_bambini(), che dice "pensati PER i bambini" e non "adatti".
    """
    da, notte, a = halloween_range(oggi)
    anno = notte.year
    url = f"{SITE_URL}/halloween.html"
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    finestra = sorted((e for e in events if e['d_start'] <= a and e['d_end'] >= da),
                      key=lambda e: (e['d_start'], (e.get('citta') or '')))
    piccoli = [e for e in finestra if e_per_bambini(e)]
    comuni = len({_key(e.get('citta')) for e in finestra if (e.get('citta') or '').strip()})

    titolo = _landing_titolo([f"Halloween {anno} con i bambini: {prov}",
                              f"Cosa fare a Halloween {anno} con i bambini | DAOP",
                              f"Cosa fare a Halloween {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi dal 25 ottobre al 2 novembre in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento nella settimana di Halloween")
        apertura = (f"<p>La notte del <strong>31 ottobre {anno}</strong> cade di "
                    f"{GIORNI[notte.weekday()]}, e col fine settimana prima e Ognissanti "
                    f"dopo diventa una decina di giorni di feste. Qui sotto ci sono i "
                    f"<strong>{len(finestra)} eventi</strong> che abbiamo verificato uno "
                    f"per uno in {comuni} comuni fra le province di {prov}, con l'orario, "
                    f"il paese e chi li organizza.</p>")
        descr = trunc(f"Cosa fare a Halloween {anno} con i bambini in provincia di {prov}: "
                      f"{len(finestra)} eventi dal 25 ottobre al 2 novembre, verificati "
                      "uno per uno da DAOP.", 152)
    else:
        sotto = f"Per Halloween {anno} non c'è ancora niente in agenda"
        apertura = (f"<p class=\"lan-vuoto\">Per Halloween {anno} in agenda non abbiamo "
                    f"ancora niente, e lo scriviamo invece di riempire la pagina. I "
                    f"programmi di fine ottobre escono tardi: castelli e pro loco li "
                    f"pubblicano spesso a due settimane dalla data. Questa pagina si rifà "
                    f"ogni notte, quindi appena entrano compaiono qui.</p>")
        descr = trunc(f"Cosa fare a Halloween {anno} con i bambini in provincia di {prov}: "
                      "feste, laboratori e castelli dal 25 ottobre al 2 novembre, "
                      "verificati uno per uno da DAOP.", 152)

    corpo = apertura
    # Il pezzo che un elenco di date non ha. Due domande, e la seconda e'
    # l'unico link a /luoghi.html che parta dal corpo di una pagina: la prima
    # l'ha aperta /ferragosto.html, e questa e' la seconda superficie.
    corpo += (
        '<h2>Fa paura o no?</h2>'
        '<p>È la domanda vera di Halloween, e la risposta cambia dello stesso '
        'evento a seconda di chi porti: la caccia ai dolcetti in piazza e la '
        'casa infestata nel castello finiscono nello stesso elenco. Noi non '
        'dividiamo le due cose a naso — sarebbe un giudizio nostro su una festa '
        'altrui, ricavato dal titolo. Facciamo l\'unica cosa che si può fare '
        'onestamente: <strong>dove l\'età è dichiarata la trovi scritta in '
        'riga</strong>, e dove non c\'è conviene aprire la scheda e leggere il '
        'programma, che riportiamo per intero. Qui sotto mettiamo in evidenza '
        'quelli <strong>pensati per i più piccoli</strong>: laboratori, zucche, '
        'giochi, dolcetto o scherzetto. Il resto della pagina è tutto il '
        'programma, senza cernite.</p>'
        '<p>La seconda domanda è dove. Halloween in zona si fa nei <strong>'
        'castelli, nelle cascine e nei borghi</strong>, e quasi sempre si '
        'prenota: gli <a href="/luoghi.html">agriturismi, i castelli e i posti '
        'da visitare con i bambini</a> stanno nel catalogo dei luoghi, con '
        'telefono e indirizzo. Se quel giorno piove, la stessa pagina dice '
        'quali sono al coperto.</p>')
    corpo += _landing_filtri(finestra)
    corpo += _landing_sezione(
        "Pensati per i più piccoli",
        "Laboratori, zucche e giochi: qui l'età è dichiarata o il programma la dice",
        piccoli, oggi)
    # Poi tutto il programma, giorno per giorno e senza escludere niente: la
    # sezione qui sopra e' un'evidenza, non una selezione che declassa il resto.
    for giorno in [da + datetime.timedelta(days=i) for i in range((a - da).days + 1)]:
        del_giorno = [e for e in finestra if in_corso(e, giorno)]
        corpo += _landing_sezione(
            f"{GIORNI[giorno.weekday()].capitalize()} {giorno.day} "
            f"{MESI_LUNGHI[giorno.month - 1]}",
            "La notte di Halloween" if giorno == notte else
            ("Ognissanti" if (giorno.month, giorno.day) == (11, 1) else None),
            del_giorno, oggi)
    corpo += _altre_landing("/halloween.html", altre)

    return {
        'path': "halloween.html", 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': f"Cosa fare a Halloween {anno} con i bambini",
        'sotto': sotto, 'crumb': "Halloween",
        'corpo': corpo,
        # Fuori stagione resta online - i link girati su WhatsApp devono
        # continuare a funzionare - ma esce dall'indice: una pagina vuota
        # indicizzata per cinquanta settimane e' contenuto sottile proprio
        # sull'URL che stiamo facendo invecchiare.
        'robots': "index, follow" if len(finestra) >= MIN_LANDING else "noindex, follow",
        'jsonld': _grafo_landing(url, titolo, descr, finestra,
                                 f"Eventi di Halloween {anno}", "Halloween", oggi),
        'eventi': len(finestra),
    }


# ---------------------------------------------------------------------------
# Le altre quattro stagionali. La struttura e' identica per tutte - finestra,
# conteggi, filtri, elenchi, scorciatoie - e sta nei due aiutanti qui sotto.
# Quello che NON si fattorizza e' l'angolo editoriale: e' scritto per esteso in
# ogni spec_*, ed e' l'unica ragione per cui queste pagine non sono un doppione
# di /eventi/weekend.html con un titolo diverso (vedi il commento su
# spec_halloween). Una stagionale senza la sua domanda propria la perde.
# ---------------------------------------------------------------------------

def _stagione_dati(st, events, oggi):
    """I conti che servono a tutte: finestra, elenco in finestra, comuni."""
    da, clou, a = prossima_finestra(st.finestra, oggi)
    finestra = sorted((e for e in events if e['d_start'] <= a and e['d_end'] >= da),
                      key=lambda e: (e['d_start'], (e.get('citta') or '')))
    comuni = len({_key(e.get('citta')) for e in finestra
                  if (e.get('citta') or '').strip()})
    return da, clou, a, finestra, comuni


def _stagione_out(st, oggi, finestra, titolo, descr, h1, sotto, corpo, nome_lista):
    """Il dizionario di spec. Il noindex sotto soglia e' la regola che tiene
    sana la pagina i mesi in cui e' vuota, senza mai cambiare indirizzo."""
    url = f"{SITE_URL}{st.href}"
    return {
        'path': st.href.lstrip('/'), 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': h1, 'sotto': sotto, 'crumb': st.crumb,
        'corpo': corpo,
        'robots': "index, follow" if len(finestra) >= MIN_LANDING else "noindex, follow",
        'jsonld': _grafo_landing(url, titolo, descr, finestra, nome_lista,
                                 st.crumb, oggi),
        'eventi': len(finestra),
    }


def _giorno_per_giorno(finestra, da, a, oggi, etichette=None):
    """Un blocco per giorno. I giorni vuoti spariscono da soli
    (_landing_sezione torna '' senza righe), quindi si puo' ciclare su tutta
    la finestra senza controllare prima se c'e' qualcosa."""
    etichette = etichette or {}
    fuori = ''
    for i in range((a - da).days + 1):
        g = da + datetime.timedelta(days=i)
        fuori += _landing_sezione(
            f"{GIORNI[g.weekday()].capitalize()} {g.day} {MESI_LUNGHI[g.month - 1]}",
            etichette.get((g.month, g.day)),
            [e for e in finestra if in_corso(e, g)], oggi)
    return fuori


def spec_natale(st, events, oggi, altre):
    """/natale.html — dal 1° al 26 dicembre.

    La domanda vera di dicembre non e' "che eventi ci sono": e' **dove sono i
    mercatini e i presepi**, e soprattutto **quali si fanno al coperto**. A
    dicembre il tempo decide la giornata piu' di qualsiasi programma, ed e'
    l'unica cosa che un elenco di date non dice.

    La finestra si ferma il 26 e non arriva all'Epifania: dal 27 prende
    /befana.html. Vedi il commento sulle finestre di Natale e Befana."""
    da, clou, a, finestra, comuni = _stagione_dati(st, events, oggi)
    anno = clou.year
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    gratis = sum(1 for e in finestra if e_gratuito(e))

    titolo = _landing_titolo([f"Natale {anno} con i bambini: {prov}",
                              f"Mercatini e presepi di Natale {anno} | DAOP",
                              f"Natale {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi di dicembre in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento in programma a dicembre")
        apertura = (f"<p>Il <strong>Natale {anno}</strong> in zona comincia "
                    f"con l'Immacolata e va avanti fino a Santo Stefano. Qui "
                    f"sotto ci sono i <strong>{len(finestra)} eventi</strong> "
                    f"che abbiamo verificato uno per uno in {comuni} comuni fra "
                    f"le province di {prov}"
                    + (f", di cui {gratis} gratuiti" if gratis else "")
                    + ", con la data, il paese e chi li organizza.</p>")
        descr = trunc(f"Mercatini, presepi ed eventi di Natale {anno} con i bambini "
                      f"in provincia di {prov}: "
                      + (f"{len(finestra)} appuntamenti" if len(finestra) > 1
                         else "1 appuntamento")
                      + " in dicembre, verificati uno per uno da DAOP.", 152)
    else:
        sotto = f"Per il Natale {anno} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per dicembre in agenda non abbiamo "
                    "ancora niente, e lo scriviamo invece di riempire la pagina. "
                    "I mercatini di paese si decidono tardi: molte pro loco "
                    "pubblicano il programma a fine novembre. Questa pagina si "
                    "rifà ogni notte, quindi appena entrano compaiono qui.</p>")
        descr = trunc(f"Mercatini, presepi ed eventi di Natale {anno} con i bambini "
                      f"in provincia di {prov}, verificati uno per uno da DAOP. "
                      "L'agenda si aggiorna ogni notte.", 152)

    corpo = apertura
    corpo += (
        '<h2>Al coperto o all\'aperto?</h2>'
        '<p>A dicembre è <em>la</em> domanda, e cambia la giornata più del '
        'programma: un mercatino in piazza con quattro gradi e la pioggia non è '
        'la stessa cosa di un presepe vivente sotto i portici. Dove lo sappiamo '
        'lo scriviamo nella scheda, ma la regola pratica è più semplice: i '
        '<strong>mercatini e i presepi viventi</strong> sono quasi sempre '
        'all\'aperto e si fanno lo stesso, quindi si va coperti e si mette in '
        'conto di stare poco; le <strong>tombole, i laboratori e gli spettacoli '
        'di Natale</strong> stanno in oratorio, in biblioteca o in teatro, e '
        'reggono qualsiasi tempo.</p>'
        '<p>La seconda domanda è <strong>Babbo Natale a che ora</strong>. Quando '
        'c\'è un orario preciso lo trovi in riga: è la differenza fra arrivare e '
        'trovarlo, e arrivare e trovare una piazza che si smonta. Se invece '
        'cercate un posto dove stare al caldo tutto il pomeriggio, gli <a '
        'href="/luoghi.html">agriturismi, i musei e i posti al coperto per '
        'bambini</a> stanno nel catalogo dei luoghi, con telefono e indirizzo.</p>')
    corpo += _landing_filtri(finestra)
    # A settimane e non giorno per giorno: la finestra e' lunga 26 giorni, e
    # ventisei titoletti - la meta' dei quali vuoti - fanno sembrare generata a
    # macchina una pagina che non lo e'.
    for testa, coda, etichetta in ((1, 7, None),
                                   (8, 14, "C'è l'Immacolata"),
                                   (15, 21, None),
                                   (22, 26, "Vigilia, Natale e Santo Stefano")):
        d1 = datetime.date(anno, 12, testa)
        d2 = datetime.date(anno, 12, coda)
        corpo += _landing_sezione(
            f"Dal {testa} al {coda} dicembre" if testa != 22 else "Dal 22 al 26 dicembre",
            etichetta,
            [e for e in finestra if e['d_start'] <= d2 and e['d_end'] >= d1], oggi)
    corpo += _altre_landing(st.href, altre)
    return _stagione_out(st, oggi, finestra, titolo, descr,
                         f"Natale {anno} con i bambini", sotto, corpo,
                         f"Eventi di Natale {anno}")


def spec_capodanno(st, events, oggi, altre):
    """/capodanno.html — dal 27 dicembre al 1° gennaio.

    Pagina sua e non un pezzo di /natale.html: "capodanno con bambini" e
    "mercatini di natale" sono due query diverse, e in mezzo ci sono i giorni
    morti fra Natale e Capodanno, che sono proprio quelli in cui un genitore
    cerca qualcosa da fare.

    La domanda propria e' UN PROBLEMA DI ORARIO, ed e' molto concreto: **i
    bambini a mezzanotte non ci arrivano.** Il veglione non e' una risposta per
    chi ha cinque anni, e la cosa che la gente cerca davvero e' il countdown
    anticipato — le feste che fanno scoccare la mezzanotte alle sei o alle otto
    di sera. Un elenco di eventi del 31 dicembre questa distinzione non la fa,
    e senza di quella la pagina non serve a niente."""
    da, clou, a, finestra, comuni = _stagione_dati(st, events, oggi)
    anno = clou.year
    prov = province_in_elenco(PROVINCE_PUBBLICATE)

    titolo = _landing_titolo([f"Capodanno {anno + 1} con i bambini: {prov}",
                              f"Capodanno {anno + 1} con i bambini | DAOP",
                              f"Capodanno {anno + 1} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi fra Natale e Capodanno in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento fra Natale e Capodanno")
        apertura = (f"<p>I giorni fra <strong>Natale e Capodanno</strong> sono "
                    f"quelli in cui la scuola è chiusa e non si sa mai cosa fare. "
                    f"Qui sotto i <strong>{len(finestra)} eventi</strong> "
                    f"verificati uno per uno in {comuni} comuni fra le province "
                    f"di {prov}, dal 27 dicembre al 1° gennaio, con l'orario, il "
                    f"paese e chi li organizza.</p>")
        descr = trunc(f"Capodanno {anno + 1} con i bambini in provincia di {prov}: "
                      + (f"{len(finestra)} eventi" if len(finestra) > 1 else "1 evento")
                      + " dal 27 dicembre al 1° gennaio, verificati uno per uno "
                        "da DAOP.", 152)
    else:
        sotto = f"Per il Capodanno {anno + 1} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per i giorni fra Natale e Capodanno in "
                    "agenda non abbiamo ancora niente, e lo scriviamo invece di "
                    "riempire la pagina. Le feste di fine anno si annunciano "
                    "tardissimo, spesso dopo Natale. Questa pagina si rifà ogni "
                    "notte, quindi appena entrano compaiono qui.</p>")
        descr = trunc(f"Capodanno {anno + 1} con i bambini in provincia di {prov}: "
                      "feste, countdown anticipati ed eventi dal 27 dicembre al 1° "
                      "gennaio, verificati uno per uno da DAOP.", 152)

    corpo = apertura
    corpo += (
        '<h2>I bambini a mezzanotte non ci arrivano</h2>'
        '<p>È il problema vero del Capodanno in famiglia, e nessun elenco di '
        'eventi lo risolve da solo. Il <strong>veglione</strong> comincia quando '
        'i piccoli crollano, e alle due di notte si torna a casa con un bambino '
        'in braccio. La risposta che cercano in tanti — e che spesso non sanno '
        'nemmeno di poter cercare — è il <strong>countdown anticipato</strong>: '
        'le feste che fanno scoccare la mezzanotte alle sei o alle otto di sera, '
        'con i brindisi analcolici e i coriandoli, e poi tutti a casa. Dove il '
        'programma lo dice, l\'orario lo trovi scritto in riga: è la prima cosa '
        'da guardare su questa pagina.</p>'
        '<p>L\'altra metà sono <strong>i giorni prima</strong>, il 27, il 28, il '
        '29. La scuola è chiusa, le feste vere non sono ancora cominciate e sono '
        'esattamente le giornate in cui non si sa cosa fare: restano aperti i '
        'presepi, e i musei e le ludoteche fanno le aperture straordinarie. Il '
        '<strong>1° gennaio</strong> invece in zona è quasi tutto chiuso, e se '
        'qualcosa c\'è è il pranzo — che si prenota prima di Natale, non dopo. '
        'Gli <a href="/luoghi.html">agriturismi, i musei e i posti al coperto per '
        'bambini</a> stanno nel catalogo dei luoghi, con telefono e indirizzo.</p>')
    corpo += _landing_filtri(finestra)
    corpo += _giorno_per_giorno(finestra, da, a, oggi,
                                {(12, 31): "San Silvestro",
                                 (1, 1): "Capodanno"})
    corpo += _altre_landing(st.href, altre)
    return _stagione_out(st, oggi, finestra, titolo, descr,
                         f"Capodanno {anno + 1} con i bambini", sotto, corpo,
                         f"Eventi di Capodanno {anno + 1}")


def spec_befana(st, events, oggi, altre):
    """/befana.html — dal 2 al 6 gennaio.

    Pagina separata da /natale.html e da /capodanno.html apposta: "calza della
    befana <paese>" e' una query sua, e su un URL condiviso si perderebbe.

    La domanda propria e' l'ORARIO. La Befana che scende dal campanile e' un
    evento di dieci minuti, non una giornata: arrivare mezz'ora dopo vuol dire
    non averla vista. E' l'unica stagionale in cui l'ora conta piu' del posto."""
    da, clou, a, finestra, comuni = _stagione_dati(st, events, oggi)
    anno = clou.year
    prov = province_in_elenco(PROVINCE_PUBBLICATE)

    titolo = _landing_titolo([f"Befana {anno} con i bambini: {prov}",
                              f"Cosa fare per la Befana {anno} | DAOP",
                              f"Befana {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi dell'Epifania in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento per l'Epifania")
        apertura = (f"<p>Gli ultimi giorni delle vacanze, dal <strong>2 al 6 "
                    f"gennaio</strong>: le calze in piazza, i presepi ancora "
                    f"aperti e la Befana. Qui sotto i <strong>{len(finestra)} "
                    f"eventi</strong> verificati uno per uno in {comuni} comuni "
                    f"fra le province di {prov}, con l'orario, il paese e chi li "
                    f"organizza.</p>")
        descr = trunc(f"Cosa fare per la Befana {anno} con i bambini in provincia di "
                      f"{prov}: "
                      + (f"{len(finestra)} eventi" if len(finestra) > 1 else "1 evento")
                      + " dal 2 al 6 gennaio, verificati uno per uno da DAOP.", 152)
    else:
        sotto = f"Per l'Epifania {anno} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per i giorni dell'Epifania in agenda "
                    "non abbiamo ancora niente, e lo scriviamo invece di riempire "
                    "la pagina. Le calze in piazza si annunciano tardi, spesso "
                    "dopo Capodanno. Questa pagina si rifà ogni notte, quindi "
                    "appena entrano compaiono qui.</p>")
        descr = trunc(f"Cosa fare per la Befana {anno} con i bambini in provincia di "
                      f"{prov}: calze in piazza, presepi ed eventi dell'Epifania, "
                      "verificati uno per uno da DAOP.", 152)

    corpo = apertura
    corpo += (
        '<h2>A che ora arriva?</h2>'
        '<p>È la domanda che conta, e su questa pagina più che su tutte le altre. '
        'La Befana che scende dal campanile o arriva in piazza è un evento di '
        '<strong>dieci minuti</strong>, non una giornata: arrivare mezz\'ora dopo '
        'vuol dire trovare la piazza che si svuota. Dove l\'orario è dichiarato '
        'lo trovi scritto in riga, e dove non c\'è conviene aprire la scheda e '
        'leggere il programma, che riportiamo per intero — oppure chiamare chi '
        'organizza, che indichiamo sempre.</p>'
        '<p>L\'altra cosa da sapere è che in questi giorni <strong>i presepi '
        'restano aperti</strong> anche quando gli eventi finiscono: i presepi '
        'viventi e quelli meccanici di solito vanno avanti fino al 6 gennaio, ed '
        'è la cosa più semplice da fare con i bambini in una giornata vuota di '
        'inizio gennaio, quando le feste sono finite e la scuola non è ancora '
        'ricominciata. Quelli che conosciamo stanno nel <a '
        'href="/luoghi.html">catalogo dei luoghi</a>, con orari e telefono.</p>')
    corpo += _landing_filtri(finestra)
    corpo += _giorno_per_giorno(finestra, da, a, oggi, {(1, 6): "L'Epifania"})
    corpo += _altre_landing(st.href, altre)
    return _stagione_out(st, oggi, finestra, titolo, descr,
                         f"Cosa fare per la Befana {anno}", sotto, corpo,
                         f"Eventi della Befana {anno}")


def spec_carnevale(st, events, oggi, altre):
    """/carnevale.html — dal giovedi' al martedi' grasso.

    Le date le calcola pasqua(): il Carnevale si sposta di un mese pieno da un
    anno all'altro (martedi' grasso 2027 il 9 febbraio, 2030 il 5 marzo), quindi
    e' proprio la pagina che a mano ci si dimenticherebbe di aggiornare.

    La domanda propria: **sfilata o festa al chiuso?** Sono due cose diverse -
    una la si guarda per strada al freddo, l'altra si fa in palestra - e con i
    bambini cambia tutto, il costume compreso."""
    da, clou, a, finestra, comuni = _stagione_dati(st, events, oggi)
    anno = clou.year
    prov = province_in_elenco(PROVINCE_PUBBLICATE)

    titolo = _landing_titolo([f"Carnevale {anno} con i bambini: {prov}",
                              f"Sfilate e feste di Carnevale {anno} | DAOP",
                              f"Carnevale {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi di Carnevale in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento di Carnevale")
        apertura = (f"<p>Nel {anno} il <strong>martedì grasso</strong> è il "
                    f"{clou.day} {MESI_LUNGHI[clou.month - 1]}, e il Carnevale "
                    f"comincia il giovedì prima. Qui sotto i <strong>"
                    f"{len(finestra)} eventi</strong> verificati uno per uno in "
                    f"{comuni} comuni fra le province di {prov}, con la data, il "
                    f"paese e chi li organizza.</p>")
        descr = trunc(f"Sfilate e feste di Carnevale {anno} con i bambini in provincia "
                      f"di {prov}: "
                      + (f"{len(finestra)} appuntamenti" if len(finestra) > 1
                         else "1 appuntamento")
                      + " fino al martedì grasso, verificati uno per uno da DAOP.", 152)
    else:
        sotto = f"Per il Carnevale {anno} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per il Carnevale in agenda non abbiamo "
                    "ancora niente, e lo scriviamo invece di riempire la pagina. I "
                    "programmi dei carri escono tardi, spesso a gennaio inoltrato. "
                    "Questa pagina si rifà ogni notte, quindi appena entrano "
                    "compaiono qui.</p>")
        descr = trunc(f"Sfilate e feste di Carnevale {anno} con i bambini in provincia "
                      f"di {prov}: carri, coriandoli e feste in maschera, "
                      "verificati uno per uno da DAOP.", 152)

    corpo = apertura
    corpo += (
        '<h2>Sfilata o festa al chiuso?</h2>'
        '<p>Sono due Carnevali diversi e conviene sapere quale si sta scegliendo. '
        'La <strong>sfilata dei carri</strong> si guarda per strada, dura un paio '
        'd\'ore, è gratis e a febbraio fa freddo: con i piccoli si sta sul '
        'percorso e non alla partenza, e i coriandoli finiscono ovunque. La '
        '<strong>festa in maschera</strong> — palestra, oratorio, salone della '
        'pro loco — è al chiuso, spesso con merenda e animazione, di solito si '
        'paga poco all\'ingresso e regge anche se piove.</p>'
        '<p>Sul <strong>costume</strong>: alle sfilate non serve, alle feste in '
        'maschera praticamente sì, e in diversi paesi c\'è la premiazione della '
        'maschera più bella. Dove il programma lo dice lo riportiamo per intero '
        'nella scheda. Ultima cosa che vale la pena sapere: nelle nostre zone il '
        'Carnevale è <strong>rito romano</strong>, quindi finisce al martedì '
        'grasso — non alla domenica dopo come a Milano.</p>')
    corpo += _landing_filtri(finestra)
    corpo += _giorno_per_giorno(finestra, da, a, oggi,
                                {(da.month, da.day): "Giovedì grasso",
                                 (clou.month, clou.day): "Martedì grasso"})
    corpo += _altre_landing(st.href, altre)
    return _stagione_out(st, oggi, finestra, titolo, descr,
                         f"Carnevale {anno} con i bambini", sotto, corpo,
                         f"Eventi di Carnevale {anno}")


def spec_pasqua(st, events, oggi, altre):
    """/pasqua.html — dal venerdi' santo alla pasquetta.

    Come il Carnevale, le date le calcola pasqua(): fra il 2027 e il 2030 la
    domenica si sposta dal 28 marzo al 21 aprile.

    La domanda propria: **Pasqua o Pasquetta?** Sono due giornate opposte - la
    domenica e' il pranzo, il lunedi' e' la gita - e chi cerca "cosa fare a
    Pasqua con i bambini" quasi sempre intende il lunedi'."""
    da, clou, a, finestra, comuni = _stagione_dati(st, events, oggi)
    anno = clou.year
    prov = province_in_elenco(PROVINCE_PUBBLICATE)
    pasquetta = clou + datetime.timedelta(days=1)

    titolo = _landing_titolo([f"Pasqua e Pasquetta {anno} con i bambini: {prov}",
                              f"Pasqua e Pasquetta {anno} con i bambini | DAOP",
                              f"Pasqua e Pasquetta {anno} con i bambini"])
    if finestra:
        sotto = (f"{len(finestra)} eventi fra Pasqua e Pasquetta in {comuni} comuni"
                 if len(finestra) > 1 else "1 evento fra Pasqua e Pasquetta")
        apertura = (f"<p>Nel {anno} <strong>Pasqua</strong> è il {clou.day} "
                    f"{MESI_LUNGHI[clou.month - 1]} e la <strong>Pasquetta</strong> "
                    f"il {pasquetta.day}. Qui sotto i <strong>{len(finestra)} "
                    f"eventi</strong> verificati uno per uno in {comuni} comuni fra "
                    f"le province di {prov}, con l'orario, il paese e chi li "
                    f"organizza.</p>")
        descr = trunc(f"Cosa fare a Pasqua e Pasquetta {anno} con i bambini in "
                      f"provincia di {prov}: "
                      + (f"{len(finestra)} eventi verificati" if len(finestra) > 1
                         else "1 evento verificato")
                      + " uno per uno da DAOP, con orari e comune.", 152)
    else:
        sotto = f"Per la Pasqua {anno} non c'è ancora niente in agenda"
        apertura = ("<p class=\"lan-vuoto\">Per Pasqua e Pasquetta in agenda non "
                    "abbiamo ancora niente, e lo scriviamo invece di riempire la "
                    "pagina. Le sagre di Pasquetta si annunciano tardi e molte "
                    "dipendono dal tempo. Questa pagina si rifà ogni notte, quindi "
                    "appena entrano compaiono qui.</p>")
        descr = trunc(f"Cosa fare a Pasqua e Pasquetta {anno} con i bambini in "
                      f"provincia di {prov}: sagre, gite e feste verificate uno per "
                      "uno da DAOP. L'agenda si aggiorna ogni notte.", 152)

    corpo = apertura
    corpo += (
        '<h2>Pasqua o Pasquetta?</h2>'
        '<p>Sono due giornate opposte, e chi cerca "cosa fare a Pasqua con i '
        'bambini" quasi sempre intende <strong>il lunedì</strong>. La '
        '<strong>domenica</strong> in zona è il pranzo: quasi tutto è chiuso o su '
        'prenotazione, e gli eventi sono pochi e spesso legati alle funzioni. Il '
        '<strong>lunedì dell\'Angelo</strong> è l\'opposto — è la giornata della '
        'gita fuori porta, e le pro loco ci mettono le sagre, le grigliate e i '
        'giochi in cascina.</p>'
        '<p>La cosa da mettere in conto è <strong>il tempo</strong>: a Pasquetta '
        'piove abbastanza spesso da rovinare il programma, e molte sagre di paese '
        'annullano o spostano al coperto la mattina stessa. Dove c\'è un contatto '
        'lo pubblichiamo apposta, e vale una telefonata prima di mettersi in '
        'macchina. Per il pranzo della domenica, gli <a href="/luoghi.html">'
        'agriturismi e i posti dove si mangia con i bambini</a> stanno nel '
        'catalogo dei luoghi: lì si prenota con settimane di anticipo, non '
        'giorni.</p>')
    corpo += _landing_filtri(finestra)
    corpo += _giorno_per_giorno(finestra, da, a, oggi,
                                {(da.month, da.day): "Venerdì Santo",
                                 (clou.month, clou.day): "Pasqua",
                                 (pasquetta.month, pasquetta.day): "Pasquetta"})
    corpo += _altre_landing(st.href, altre)
    return _stagione_out(st, oggi, finestra, titolo, descr,
                         f"Pasqua e Pasquetta {anno}", sotto, corpo,
                         f"Eventi di Pasqua {anno}")


def _sagre_ricorrenti(storico, prov, quante=12):
    """Le sagre di quella provincia viste in piu' di un'edizione.

    E' la parte della pagina che non dipende dalla stagione: a novembre di
    sagre in programma non ce n'e' nessuna, ma "quando c'e' la sagra del
    tartufo" si continua a cercarlo tutto l'anno."""
    out = []
    for c in storico.values():
        if (c.get('prov') or '').upper() != prov:
            continue
        for sl, r in (c.get('eventi') or {}).items():
            nome = (r.get('nome') or '').strip()
            if len(r.get('anni') or []) < 2:
                continue
            if not any(w in nome.lower() for w in SAGRA_KW):
                continue
            out.append((sl, r, c.get('nome') or ''))
    out.sort(key=lambda t: (-len(t[1]['anni']), t[1].get('nome') or ''))
    return out[:quante]


def href_eventi_prov(prov):
    """L'indirizzo della pagina provinciale senza finestra temporale.

    Scritto qui e non nei quattro posti che lo usano - la sorella delle sagre,
    le due d'incrocio, la coda delle schede - per la stessa ragione di
    href_incrocio(): un indirizzo ripetuto e' un indirizzo che un giorno
    cambia in tre punti su quattro."""
    return f"/eventi-provincia-{slugify(PROVINCE_NOMI.get(prov, prov))}.html"


def spec_sagre(prov, events, hub, storico, oggi, altre):
    """/sagre-provincia-<nome>.html — le sagre di una provincia, mese per mese."""
    nome_prov = PROVINCE_NOMI.get(prov, prov)
    slug = f"sagre-provincia-{slugify(nome_prov)}"
    url = f"{SITE_URL}/{slug}.html"
    href = f"/{slug}.html"
    sagre = sorted((e for e in events
                    if (e.get('prov') or '').upper() == prov and bucket(e)[0] == 'feste'),
                   key=lambda e: (e['d_start'], (e.get('citta') or '')))
    # Tutto il RESTO dell'agenda di quella provincia: laboratori, cultura,
    # spettacoli, musica, sport. Non cambia cos'e' questa pagina - il title,
    # l'H1 e il canonical restano quelli delle sagre, che sono la query che
    # vince - ma la mette dove il pubblico c'e' gia'.
    #
    # Il conto che l'ha decisa (export GSC 26/08/2026, tre mesi):
    #   /sagre-provincia-cuneo.html      405 clic, 4.503 impressioni, pos 6,86
    #   /eventi/weekend-provincia-cuneo    32 clic,   604 impressioni
    #   /eventi/oggi-provincia-cuneo       16 clic,   855 impressioni
    # e in agenda a Cuneo su 79 eventi le sagre sono 16: l'80% del lavoro del
    # curatore stava sulle due pagine che insieme fanno 48 clic in tre mesi.
    #
    # Perche' NON e' invece nata una /eventi-provincia-<nome>.html, che e' la
    # cosa che viene in mente per prima: nello stesso export le query
    # provinciali senza finestra temporale ("eventi in provincia di X") fanno
    # 19 query, 511 impressioni e 8 clic in tre mesi, contro le 4.953
    # impressioni delle stesse query con "oggi"/"weekend" dentro, che hanno
    # gia' le loro sei pagine. E le categorie qui sotto non hanno una domanda
    # propria: "laboratori", "teatro", "musei" fanno ZERO impressioni. Una
    # pagina nuova sarebbe una terza provinciale a contendersi le query delle
    # altre due - lo stesso nodo gia' descritto in spec_incrocio - per una
    # domanda che non c'e'.
    altri_ev = sorted((e for e in events
                       if (e.get('prov') or '').upper() == prov
                       and bucket(e)[0] != 'feste'),
                      key=lambda e: (e['d_start'], (e.get('citta') or '')))
    ric = _sagre_ricorrenti(storico, prov)
    anno = sagre[0]['d_start'].year if sagre else oggi.year

    titolo = _landing_titolo([f"Sagre e feste in provincia di {nome_prov} {anno} | DAOP",
                              f"Sagre e feste in provincia di {nome_prov} {anno}",
                              f"Sagre in provincia di {nome_prov} {anno}"])
    comuni = sorted((d for d in (hub or {}).values() if d['prov'] == prov),
                    key=lambda d: -len(d['futuri']))
    fonte = fonte_provincia(prov)

    if sagre:
        fine = max(e['d_end'] for e in sagre)
        paesi = len({_key(e.get('citta')) for e in sagre if (e.get('citta') or '').strip()})
        sotto = (f"{len(sagre)} sagre e feste in programma, fino al {fine.day} "
                 f"{MESI_LUNGHI[fine.month - 1]} {fine.year}")
        apertura = (f"<p>Le sagre, le feste patronali, le fiere e le pro loco in provincia "
                    f"di {esc(nome_prov)}: <strong>{len(sagre)} appuntamenti</strong> in "
                    f"{paesi} comuni diversi, con le date, gli orari e i contatti di chi "
                    f"le organizza. L'elenco è in ordine di data e si rifà ogni notte: "
                    f"quello che è passato esce da solo.</p>")
    else:
        sotto = f"Nessuna sagra in programma in provincia di {nome_prov} in questo momento"
        apertura = (f"<p class=\"lan-vuoto\">In provincia di {esc(nome_prov)} in questo "
                    f"momento non abbiamo sagre in agenda: è normale fuori stagione. "
                    f"Qui sotto restano quelle che tornano ogni anno, così sai quando "
                    f"aspettarle — appena escono le date della prossima edizione le trovi "
                    f"in questa pagina.</p>")
    descr = trunc(f"Sagre e feste in provincia di {nome_prov} {anno}: "
                  + (f"{len(sagre)} appuntamenti in programma, con date, orari e comune. "
                     "Verificati uno per uno da DAOP."
                     if sagre else
                     "il calendario delle sagre che tornano ogni anno e le date "
                     "della prossima edizione, appena escono."), 152)

    corpo = apertura
    # Niente tendina provincia: la pagina E' una provincia. Resta la ricerca
    # (il paese) e la categoria, che qui non sono solo sagre - e da quando in
    # fondo c'e' anche il resto dell'agenda, la tendina DEVE vederlo: la
    # costruisce _landing_filtri dall'elenco che riceve, e con le sole sagre
    # avrebbe avuto una voce sola, cioe' non si sarebbe stampata affatto
    # mentre in pagina c'erano cinque categorie da separare.
    corpo += _landing_filtri(sagre + altri_ev, con_prov=False)
    # Mese per mese: e' il modo in cui si guarda un calendario di sagre, e in
    # agenda non esiste perche' li' i mesi sono mischiati fra le province.
    per_mese = collections.OrderedDict()
    for e in sagre:
        per_mese.setdefault((e['d_start'].year, e['d_start'].month), []).append(e)
    for (y, m), ev in per_mese.items():
        corpo += _landing_sezione(f"{MESI_LUNGHI[m - 1].capitalize()} {y}",
                                  f"{len(ev)} sagre e feste" if len(ev) > 1 else "1 sagra",
                                  ev, oggi)
    if ric:
        righe = "".join(
            f'<li><span class="com-y">{r["anni"][0]}–{r["anni"][-1]}</span>'
            + (f'<a href="/eventi/{sl}.html">{esc(trunc(r.get("nome") or "", 70))}</a>'
               if r.get('pagina') else f'<span>{esc(trunc(r.get("nome") or "", 70))}</span>')
            + f'<span class="com-luogo">{esc(citta)}</span></li>'
            for sl, r, citta in ric)
        corpo += (f"<h2>Le sagre che tornano ogni anno in provincia di {esc(nome_prov)}</h2>"
                  f"<p>Le abbiamo viste in più di un'edizione: sono quelle su cui si può "
                  f"contare anche quando le date della prossima non sono ancora uscite.</p>"
                  f'<section class="com-grp"><ul class="com-anni">{righe}</ul></section>')
    if altri_ev:
        # Le categorie si NOMINANO solo se ci sono davvero, come per i filtri:
        # una riga d'apertura che promette "spettacoli" a una provincia che
        # questo mese non ne ha e' la stessa cosa dell'occhiello dei corsi che
        # prometteva i costi. 'altro' resta fuori dalla frase e dentro l'elenco.
        presenti = [LABELS_PROSA[s_] for s_ in ORDER
                    if s_ in LABELS_PROSA and any(bucket(e)[0] == s_ for e in altri_ev)]
        # Chi ha gia' una "e" dentro passa davanti, se no elenco_it lo mette in
        # coda e viene fuori "sport e cultura e natura".
        presenti.sort(key=lambda n: ' e ' not in n)
        quali = elenco_it(presenti).capitalize() if presenti else "Il resto dell'agenda"
        # Sezione senza intestazione propria: il titolo e' l'<h2> qui sopra, ed
        # e' quello che il JS dei filtri fa sparire insieme al gruppo quando un
        # filtro lo svuota (testaDi()). Un <h3> dentro il gruppo direbbe due
        # volte la stessa cosa.
        righe, nude = _landing_righe(altri_ev, oggi)
        corpo += (f"<h2>Non solo sagre: gli altri appuntamenti in provincia di "
                  f"{esc(nome_prov)}</h2>"
                  f"<p>{esc(quali)}: <strong>{len(altri_ev)} appuntamenti</strong> in "
                  f"provincia di {esc(nome_prov)} che non sono sagre di paese. Stessa "
                  f"agenda e stessa verifica, uno per uno, e anche questo elenco si rifà "
                  f"ogni notte.</p>"
                  f'<section class="com-grp"><ul class="com-ev'
                  f'{" is-nude" if nude else ""}">{righe}</ul></section>')
    if comuni:
        link = "".join(f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
                       for d in comuni)
        corpo += (f"<h2>I comuni della provincia di {esc(nome_prov)}</h2>"
                  f'<div class="com-link">{link}</div>')
    # Le sorelle con la finestra temporale. Questa pagina risponde a "dove",
    # quelle a "dove e quando": chi cerca l'una spesso vuole l'altra, ed e' il
    # link che le tiene insieme invece di lasciarle competere.
    corpo += (f"<h2>Cosa c'è adesso in provincia di {esc(nome_prov)}</h2>"
              f'<p>Questa pagina è il calendario delle sagre. Se cerchi '
              f'<a href="{href_eventi_prov(prov)}">tutti gli eventi e le attività per '
              f'bambini della provincia</a> — sagre comprese, divisi per età — sono in '
              f'una pagina sola. Se invece la domanda è '
              f'"e stasera?": <a href="{href_incrocio(prov, "oggi")}">cosa fare oggi</a> '
              f'oppure <a href="{href_incrocio(prov, "weekend")}">gli eventi del '
              f'weekend</a> in provincia di {esc(nome_prov)}.</p>')
    corpo += credito_fonte(
        fonte, f'Le sagre della provincia di {esc(nome_prov)} arrivano da', breve=True)
    corpo += _altre_landing(href, altre)

    # Sotto soglia la pagina resta (i link che girano non si rompono) ma esce
    # dall'indice e dalla sitemap: la stessa regola delle pagine comune.
    robots = "index, follow" if len(sagre) + len(ric) >= MIN_LANDING else "noindex, follow"
    return {
        'path': f"{slug}.html", 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': f"Sagre e feste in provincia di {nome_prov}",
        'sotto': sotto, 'crumb': f"Sagre {nome_prov}",
        'corpo': corpo, 'robots': robots,
        # Serve solo al tracciamento: i clic in uscita da questa pagina
        # portano con se' la provincia, cosi' "quanti aprono le mappe delle
        # sagre astigiane" si legge senza incrociare a mano gli URL.
        'prov': prov,
        'jsonld': _grafo_landing(url, titolo, descr, sagre,
                                 f"Sagre in provincia di {nome_prov}",
                                 f"Sagre in provincia di {nome_prov}", oggi),
        # Resta il numero delle SAGRE, non il totale in pagina: e' il numero su
        # cui si decide il robots ed e' quello che dice se questa pagina sta
        # facendo il suo mestiere. Gli altri si stampano a parte nel log.
        'eventi': len(sagre),
        'altri': len(altri_ev),
    }


def spec_eventi_prov(prov, events, hub, oggi, altre):
    """/eventi-provincia-<nome>.html — la provincia SENZA finestra temporale.

    PERCHE' ESISTE, visto che spec_sagre dice a chiare lettere di non farla.
    Quel commento (29/08/2026) la scartava su due argomenti. Il primo era la
    domanda: "le query provinciali senza finestra temporale fanno 19 query,
    511 impressioni e 8 clic in tre mesi". Quel numero viene dal NOSTRO Search
    Console, che conta solo le query dove GIA' compariamo: su una query dove
    non rankiamo le impressioni sono zero per costruzione, quindi era un
    pavimento e non una misura della domanda. La SERP di "eventi e attivita'
    per bambini provincia di cuneo" (04/09/2026) lo dice da sola: annunci
    shopping e un blocco "Le persone hanno chiesto anche" da quattro voci non
    li mette su una query da venti ricerche al mese.

    Il secondo argomento era la cannibalizzazione, "una terza provinciale a
    contendersi le query delle altre due". Regge meno di quanto sembrava,
    perche' le altre due sono ENTRAMBE temporali:

        /eventi/oggi-provincia-<x>       provincia x oggi
        /eventi/weekend-provincia-<x>    provincia x weekend
        /sagre-provincia-<x>             provincia x sagre
        questa                           provincia, senza finestra, per eta'

    Il taglio e' sullo stesso asse che spec_incrocio aveva gia' individuato
    (provincia x finestra) e la cella senza finestra era l'unica vuota. E' anche
    la meno stagionale delle quattro: conta TUTTA l'agenda e non le sole sagre,
    quindi non scende sotto MIN_LANDING nei mesi in cui le sagre finiscono.

    Il pezzo che ha fatto cambiare la risposta, e che il 29/08 non si sapeva:
    su quella query il secondo risultato di Google e' eventiperbambinicuneo.it,
    il sito del curatore di Cuneo, che il 21/08 si e' deciso di chiudere
    inglobando tutto in DAOP. Cioe' stavamo per spegnere l'unica superficie che
    la vince, senza avere una pagina su cui portarla: il 301 di quel dominio ha
    bisogno di un atterraggio che risponda alla stessa domanda, e mandarlo su
    /sagre-provincia-cuneo.html vuol dire mandarlo su un titolo di sagre.
    L'insieme resta chiuso e non cresce coi dati - una per provincia
    pubblicata, come le sagre - che e' la garanzia di sempre contro lo
    scaled content.

    COSA NON SI TOCCA. Il title e l'H1 di /sagre-provincia-<x>.html restano
    quelli delle sagre: quella pagina fa 405 clic e 4.503 impressioni sulle
    query di sagre (export 26/08, Cuneo) ed e' la quinta del sito. Allargarne
    il titolo per coprire anche questa domanda e' la stessa aritmetica dell'H1
    di eventi.html, che non si tocca per la stagione.

    L'ASSE E' L'ETA', NON LA CATEGORIA, e non e' una preferenza estetica.
    La categoria e' gia' la tendina dei filtri ed e' scritta in ogni riga
    (.com-cat): come principio di raggruppamento sarebbe la seconda volta che
    si dice la stessa cosa, e ordinando per categoria con le sagre davanti
    questa pagina uscirebbe uguale alla sorella. L'eta' invece e' il dato che
    nessun altro sito ha, ed e' letteralmente la parola della query. E divide
    per davvero: e_per_bambini() e' vero su 48 righe di 88 a Cuneo, 21 di 89 ad
    Alessandria, 9 di 33 ad Asti - non e' il 93% di 'Adatto Famiglie', che per
    quel motivo non si usa e qui non si usa.

    I due blocchi sono COMPLEMENTARI, non uno dentro l'altro: nessuna scheda
    compare sopra e sotto insieme. E' l'invariante che tests/landing.js ha
    imparato a chiedere sulla sezione "Non solo sagre" dopo aver preteso, per
    sbaglio, che ogni href comparisse una volta sola in tutta la pagina.

    E il secondo blocco NON si intitola "adatti alle famiglie": sarebbe la riga
    che dice implicitamente che gli altri non lo sono, cioe' smentire il
    criterio con cui l'agenda e' fatta. Dice quello che e' vero - che li' la
    fascia d'eta' non e' dichiarata - e da' la regola per leggerli, come fa
    /halloween.html con la paura."""
    nome_prov = PROVINCE_NOMI.get(prov, prov)
    href = href_eventi_prov(prov)
    slug = href.strip('/')[:-5]
    url = f"{SITE_URL}{href}"
    tutti = sorted((e for e in events if (e.get('prov') or '').upper() == prov),
                   key=lambda e: (e['d_start'], (e.get('citta') or ''),
                                  (e.get('nome') or '')))
    bimbi = [e for e in tutti if e_per_bambini(e)]
    resto = [e for e in tutti if not e_per_bambini(e)]
    paesi = len({_key(e.get('citta')) for e in tutti if (e.get('citta') or '').strip()})

    titolo = _landing_titolo([
        f"Eventi e attività per bambini in provincia di {nome_prov} | DAOP",
        f"Eventi e attività per bambini in provincia di {nome_prov}",
        f"Eventi per bambini in provincia di {nome_prov}"])
    h1 = f"Eventi e attività per bambini in provincia di {nome_prov}"
    crumb = f"Eventi per bambini {nome_prov}"
    sagre_href = f"/sagre-provincia-{slugify(nome_prov)}.html"

    if tutti:
        sotto = (f"{len(tutti)} eventi e attività in programma in {paesi} "
                 f"comun{'i' if paesi != 1 else 'e'}")
        # Le categorie si nominano solo se ci sono davvero: e' la regola
        # dell'occhiello dei corsi, che aveva smesso di promettere i costi.
        presenti = [LABELS_PROSA[s_] for s_ in ORDER
                    if s_ in LABELS_PROSA and any(bucket(e)[0] == s_ for e in tutti)]
        presenti.sort(key=lambda n: ' e ' not in n)
        quali = elenco_it(presenti)
        apertura = (f"<p>Tutto quello che c'è in programma per bambini e famiglie in "
                    f"provincia di {esc(nome_prov)}: <strong>{len(tutti)} appuntamenti"
                    f"</strong> in {paesi} comuni"
                    + (f", fra sagre, {esc(quali)}" if presenti else "")
                    # La coda "e si rifa' ogni notte" e' detta di nuovo in fondo
                    # alla pagina, quindi qui e' l'unica frase che non aggiunge
                    # niente: a 360px valeva due righe. Quello che resta e'
                    # l'identita' contro le tre sorelle temporali.
                    + f". Non è il programma di un weekend: è l'agenda intera, in "
                    f"ordine di data.</p>")
    else:
        sotto = f"Nessun evento in programma in provincia di {nome_prov} in questo momento"
        apertura = (f"<p class=\"lan-vuoto\">In provincia di {esc(nome_prov)} in questo "
                    f"momento non abbiamo niente in agenda. Appena arrivano le date lo "
                    f"trovi qui: la pagina si rifà ogni notte.</p>")
    descr = trunc(f"Eventi e attività per bambini in provincia di {nome_prov}: "
                  + (f"{len(tutti)} appuntamenti in {paesi} comuni, con l'età, la data e "
                     "il comune. Verificati uno per uno da DAOP."
                     if tutti else
                     "l'agenda si aggiorna ogni notte, appena arrivano le date."), 152)

    corpo = apertura
    corpo += _landing_filtri(tutti, con_prov=False, con_quando=True,
                             con_gratis=True)
    if bimbi:
        corpo += _landing_sezione(
            "Pensati per i bambini",
            f"{len(bimbi)} appuntamenti con la fascia d'età dichiarata, o con "
            f"laboratori e giochi nel programma",
            bimbi, oggi, eta=True, gratis=True)
    if resto:
        corpo += _landing_sezione(
            f"Gli altri appuntamenti in provincia di {nome_prov}",
            f"{len(resto)} eventi senza una fascia d'età dichiarata: l'età si "
            f"capisce dal programma, dentro la scheda",
            resto, oggi, eta=True, gratis=True)

    comuni = sorted((d for d in (hub or {}).values() if d['prov'] == prov),
                    key=lambda d: -len(d['futuri']))
    if comuni:
        link = "".join(f'<a href="/eventi/comune/{d["slug"]}.html">{esc(d["nome"])}</a>'
                       for d in comuni)
        corpo += (f"<h2>I comuni della provincia di {esc(nome_prov)}</h2>"
                  f'<div class="com-link">{link}</div>')

    # Le tre sorelle. E' lo stesso link che ogni pagina d'incrocio ha verso le
    # sagre, e serve a passarsi autorita' invece di farsi concorrenza: ognuna
    # nomina la SUA domanda, non "vedi anche".
    corpo += (f"<h2>Se la domanda è un'altra</h2>"
              f"<p>Questa pagina è l'agenda completa della provincia. Se cerchi "
              f'<a href="{sagre_href}">solo le sagre e le feste di paese</a> le trovi '
              f'in ordine di mese, con anche quelle che tornano ogni anno; se invece '
              f'la domanda è "e adesso?", <a href="{href_incrocio(prov, "oggi")}">cosa '
              f'fare oggi</a> oppure <a href="{href_incrocio(prov, "weekend")}">gli '
              f'eventi del weekend</a> in provincia di {esc(nome_prov)}.</p>')

    fonte = fonte_provincia(prov)
    corpo += credito_fonte(
        fonte, f'Gli eventi della provincia di {esc(nome_prov)} arrivano da', breve=True)
    corpo += _altre_landing(href, altre)

    # Su TUTTA l'agenda della provincia, non su un sottoinsieme: e' la ragione
    # per cui questa e' la meno stagionale delle quattro. Sotto soglia la
    # pagina resta online ed esce dall'indice, come le sagre e le stagionali.
    robots = "index, follow" if len(tutti) >= MIN_LANDING else "noindex, follow"
    return {
        'path': f"{slug}.html", 'url': url,
        'titolo': titolo, 'descr': descr,
        'h1': h1, 'sotto': sotto, 'crumb': crumb,
        'corpo': corpo, 'robots': robots,
        'prov': prov,
        'jsonld': _grafo_landing(url, titolo, descr, tutti,
                                 f"Eventi per bambini in provincia di {nome_prov}",
                                 crumb, oggi),
        'eventi': len(tutti),
        'nota': f"{len(bimbi)} pensati per i bambini",
    }


def link_landing(oggi=None):
    """(href, testo) delle pagine di intenzione. Una lista sola, usata dalle
    scorciatoie in fondo alle pagine e dal blocco in cima all'agenda: se
    cambia un indirizzo non deve cambiare in due posti.

    'oggi' serve alle stagionali: ognuna entra in elenco nella sua finestra
    (piu' i giorni di `apre`), il resto dell'anno resta online ma non la
    linkiamo da 290 pagine. Senza 'oggi' l'elenco e' quello di sempre.

    Il ciclo su STAGIONI e' il motivo per cui aggiungere una festa non obbliga
    a ricordarsi anche di questa funzione."""
    voci = [("/eventi/oggi.html", "Cosa c'è oggi"),
            ("/eventi/weekend.html", "Questo weekend")]
    if oggi is not None:
        voci += [(st.href, st.nome) for st in STAGIONI if in_stagione(st, oggi)]
    for c in PROVINCE_PUBBLICATE:
        nome = PROVINCE_NOMI.get(c, c)
        voci.append((f"/sagre-provincia-{slugify(nome)}.html", f"Sagre {nome}"))
    return voci


def scrivi_landing(events, hub, storico, oggi):
    """Genera le pagine di intenzione. Restituisce {path: lastmod} per la
    sitemap, gia' senza quelle finite in noindex."""
    try:
        css, nav, foot = _guscio()
    except SystemExit as err:
        print(f"[genera_eventi] pagine di intenzione saltate: {err}")
        return {}
    altre = link_landing(oggi)
    specs = [spec_oggi(events, oggi, altre), spec_weekend(events, oggi, altre)]
    # Tutte le stagionali, dalla tabella. Girano SEMPRE, anche fuori stagione:
    # la pagina deve esistere mesi prima per invecchiare (sotto MIN_LANDING resta
    # in noindex e fuori sitemap da sola). E' il rimpianto scritto su
    # spec_halloween — "su una stagionale l'asset e' l'anzianita' dell'URL".
    specs += [st.spec(st, events, oggi, altre) for st in STAGIONI]
    specs += [spec_sagre(c, events, hub, storico, oggi, altre) for c in PROVINCE_PUBBLICATE]
    # La provincia senza finestra temporale: la quarta cella dell'asse
    # provincia x finestra, che era l'unica vuota. Vedi spec_eventi_prov.
    specs += [spec_eventi_prov(c, events, hub, oggi, altre)
              for c in PROVINCE_PUBBLICATE]
    # Le sei d'incrocio: provincia x finestra. Vedi il commento su INCROCI.
    specs += [spec_incrocio(c, modo, events, hub, oggi, altre)
              for modo, _t, _p, _c in INCROCI for c in PROVINCE_PUBBLICATE]

    try:
        reg = json.load(open(LANDING_REGISTRO, encoding='utf-8'))
    except (OSError, ValueError):
        reg = {}
    cambiate, fuori = 0, []
    for spec in specs:
        path = os.path.join(ROOT, spec['path'])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        nuovo = _landing_shell(spec, css, nav, foot, oggi)
        if spec['robots'].startswith('noindex'):
            fuori.append(spec['path'])
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            reg.setdefault(spec['path'], oggi.isoformat())
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        reg[spec['path']] = oggi.isoformat()
        cambiate += 1
    with open(LANDING_REGISTRO, 'w', encoding='utf-8') as fh:
        json.dump(reg, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_eventi] pagine di intenzione: {len(specs)} ({cambiate} riscritte)"
          + (f", {len(fuori)} in noindex sotto soglia: {', '.join(fuori)}" if fuori else ""))
    for spec in specs:
        extra = (f" + {spec['altri']} non-sagre" if spec.get('altri') else "")
        extra += (f" ({spec['nota']})" if spec.get('nota') else "")
        print(f"[genera_eventi]   {spec['path']}: {spec['eventi']} eventi{extra}")
    return {p: m for p, m in sorted(reg.items())
            if p in {s['path'] for s in specs} and p not in fuori}


def opzioni_provincia(events):
    """Opzioni del filtro provincia, ricavate dagli eventi in agenda.

    Erano HTML statico FUORI dai marker (solo "Prov. AL" e "Prov. AT"), quindi
    aprire il filtro dei dati a CN non bastava: gli eventi di Cuneo comparivano in
    elenco ma non c'era modo di filtrarli. Ora l'elenco si genera da solo e non
    puo' piu' restare indietro. I value sono minuscoli perche' e' quello che il JS
    confronta con data-province sulle schede.
    """
    presenti = {e.get('prov') for e in events if e.get('prov')}
    righe = ['        <option value="all">Province</option>']
    for c in PROVINCE_PUBBLICATE:
        if c in presenti:
            righe.append(f'        <option value="{c.lower()}">Prov. {c}</option>')
    return "\n".join(righe)


# Sotto questa soglia, nei prossimi 30 giorni, la stagione delle sagre e'
# finita e l'hero smette di prometterle. Tre e non una: con una sola sagra
# rimasta l'H1 ballerebbe da un giorno all'altro, e eventi.html si ricommitta
# ogni volta che cambia di un carattere.
MIN_SAGRE_HERO = 3
FINESTRA_HERO = 30


# ===========================================================================
# LE STAGIONI — l'unico posto in cui si dichiara una pagina stagionale.
#
# Aggiungerne una = AGGIUNGERE UNA RIGA QUI (+ la sua spec_*, che e' la parte
# editoriale, vedi sotto). Prima erano cinque punti sparsi nel file - costanti,
# range(), in_stagione(), un `if` in link_landing() e una chiamata in
# scrivi_landing() - ed e' esattamente il genere di cosa che ci si dimentica.
#
# `apre` e `avviso` sono GIORNI PRIMA dell'inizio della finestra, non date sul
# calendario. Due motivi, e il secondo e' un baco vero che c'era:
#   1. per Carnevale e Pasqua una data fissa non esiste (si spostano di un mese);
#   2. il vecchio confronto fra tuple (mese, giorno) NON REGGE le finestre che
#      scavalcano capodanno: per la Befana "(12,27) <= oggi <= (1,6)" e' falso
#      sempre, e la pagina non sarebbe MAI entrata in stagione. Contando i
#      giorni si fa aritmetica sulle date vere e il problema sparisce.
#
# `apre`   = da quando entra nelle scorciatoie in fondo alle altre pagine.
# `avviso` = da quando compare la riga in evidenza in home e in cima all'agenda.
#            Parte piu' tardi apposta: una riga in evidenza per cinque settimane
#            e' un banner che la gente impara a non vedere, e "fra sei settimane"
#            non e' una notizia.
# ===========================================================================
Stagione = collections.namedtuple(
    'Stagione', 'chiave nome href crumb finestra apre avviso quale spec')

STAGIONI = (
    Stagione('befana', "Befana", "/befana.html", "Befana",
             _finestra_befana, apre=18, avviso=0,
             quale="dal 2 al 6 gennaio", spec=spec_befana),
    Stagione('capodanno', "Capodanno", "/capodanno.html", "Capodanno",
             _finestra_capodanno, apre=20, avviso=0,
             quale="dal 27 dicembre al 1° gennaio", spec=spec_capodanno),
    Stagione('carnevale', "Carnevale", "/carnevale.html", "Carnevale",
             _finestra_carnevale, apre=25, avviso=7,
             quale="dal giovedì al martedì grasso", spec=spec_carnevale),
    Stagione('pasqua', "Pasqua", "/pasqua.html", "Pasqua",
             _finestra_pasqua, apre=25, avviso=7,
             quale="di Pasqua e Pasquetta", spec=spec_pasqua),
    Stagione('ferragosto', "Ferragosto", "/ferragosto.html", "Ferragosto",
             _finestra_ferragosto, apre=35, avviso=9,
             quale="del 14-16 agosto", spec=spec_ferragosto),
    Stagione('halloween', "Halloween", "/halloween.html", "Halloween",
             _finestra_halloween, apre=24, avviso=5,
             quale="dal 25 ottobre al 2 novembre", spec=spec_halloween),
    Stagione('natale', "Natale", "/natale.html", "Natale",
             _finestra_natale, apre=16, avviso=0,
             quale="dal 1° al 26 dicembre", spec=spec_natale),
)


def in_stagione(st, oggi):
    """Se la pagina di `st` va linkata dalle altre e indicizzata.

    Fuori da qui resta ONLINE - i link girati su WhatsApp devono continuare a
    funzionare - ma non la si annuncia e (sotto MIN_LANDING) non la si indicizza:
    una pagina vuota in indice per cinquanta settimane e' contenuto sottile
    proprio sull'URL che stiamo facendo invecchiare."""
    da, _clou, a = prossima_finestra(st.finestra, oggi)
    return da - datetime.timedelta(days=st.apre) <= oggi <= a


def _controlla_stagioni():
    """Le finestre NON si devono toccare: blocco_stagione() sceglie "la prima
    che risponde" e con due stagioni attive insieme l'avviso in home diventa
    arbitrario. Con Carnevale e Pasqua mobili non basta guardarle a occhio, e
    aggiungendo una festa e' facile sovrapporsi senza accorgersene: qui si
    controllano dieci anni veri e si fallisce SUBITO, non in produzione."""
    for anno in range(2026, 2036):
        viste = []
        for st in STAGIONI:
            da, _clou, a = st.finestra(anno)
            # L'avviso e' la finestra che conta: e' quella per cui blocco_stagione
            # deve poter scegliere senza ambiguita'.
            viste.append((da - datetime.timedelta(days=st.avviso), a, st.nome))
        viste.sort()
        for (_d1, a1, n1), (d2, _a2, n2) in zip(viste, viste[1:]):
            if d2 <= a1:
                raise SystemExit(
                    f"[genera_eventi] stagioni sovrapposte nel {anno}: "
                    f"{n1} finisce il {a1} e {n2} comincia il {d2}. "
                    f"Le finestre devono restare disgiunte — vedi STAGIONI.")


_controlla_stagioni()


def blocco_stagione(events, oggi):
    """La riga "c'è Ferragosto" (o Halloween) per la home e per l'hero, o ''.

    Serve a due posti e sta scritta una volta: sono le uniche due superfici da
    cui una pagina stagionale si raggiunge senza essere gia' dentro una pagina
    di intenzione. Fuori finestra torna stringa vuota, quindi non c'e' niente
    da togliere a settembre.

    L'avviso parte piu' tardi del link nelle scorciatoie apposta: una riga in
    evidenza per cinque settimane e' un banner che si impara a non vedere.

    Il conteggio non e' decorazione: "62 eventi" e' la promessa che dice se
    vale la pena entrare, esattamente come i numeri accanto ai comuni."""
    for st in STAGIONI:
        da, centro, a = prossima_finestra(st.finestra, oggi)
        if not (da - datetime.timedelta(days=st.avviso) <= oggi <= a):
            continue
        href, nome, quale = st.href, st.nome, st.quale
        quanti = sum(1 for e in events if e['d_start'] <= a and e['d_end'] >= da)
        if quanti < MIN_LANDING:
            return ''
        manca = (centro - oggi).days
        if manca > 1:
            quando = f"fra {manca} giorni"
        elif manca == 1:
            quando = "domani"
        elif manca == 0:
            quando = "è oggi"
        else:
            quando = "è in corso"
        return (f'<a href="{href}">{nome} {quando}: i {quanti} eventi '
                f'{quale} →</a>')
    return ''


def blocco_hero(events, oggi):
    """H1 e occhiello dell'agenda, scritti sulla stagione che c'e' davvero.

    Erano HTML fisso, ed e' un problema che si vede solo a novembre: "Sagre ed
    eventi oggi e questo weekend" quando di sagre non ce n'e' nessuna promette
    una cosa che la pagina non ha. E' la stessa regola che le landing seguono
    gia' con lan-vuoto - si scrive quello che c'e', non quello che vorremmo -
    solo che qui il testo non lo generava nessuno.

    Fuori stagione l'H1 non perde l'intento ("oggi e questo weekend" vale tutto
    l'anno): perde la parola sagre, che a dicembre non porta nessuno."""
    limite = oggi + datetime.timedelta(days=FINESTRA_HERO)
    sagre = sum(1 for e in events
                if bucket(e)[0] == 'feste' and e['d_end'] >= oggi and e['d_start'] <= limite)
    if sagre >= MIN_SAGRE_HERO:
        h1 = "<em>Sagre ed eventi</em> oggi e questo weekend"
        occhiello = ("Tutte le sagre, le feste patronali, le fiere, i laboratori e gli "
                     "spettacoli di oggi e del weekend nelle province di Alessandria, "
                     "Asti e Cuneo. Agenda aggiornata ogni notte, selezionata per le "
                     "famiglie e verificata evento per evento.")
    else:
        h1 = "<em>Eventi per famiglie</em> oggi e questo weekend"
        occhiello = ("Laboratori, spettacoli e appuntamenti per famiglie di oggi e del "
                     "weekend nelle province di Alessandria, Asti e Cuneo. Agenda "
                     "aggiornata ogni notte e verificata evento per evento: fuori "
                     "stagione le sagre non ci sono, e non le scriviamo.")
    # L'avviso di Ferragosto e' un <p> in piu', NON un H1 diverso: l'H1 di
    # eventi.html e' l'asset piu' forte del sito e riscriverlo per dieci giorni
    # su una festa vuol dire toglierlo per dieci giorni dalle query su cui
    # ranka tutto l'anno. Niente classe nuova, cosi' non tocchiamo il <style>
    # che _guscio() ricopia in ~260 file per una riga stagionale.
    stagione = blocco_stagione(events, oggi)
    coda = f"\n    <p>{stagione}</p>" if stagione else ""
    return f"    <h1>{h1}</h1>\n    <p>{occhiello}</p>{coda}"


def inject(tipo_opts, lista, jsonld, prov_opts=None, comuni_html=None, hero=None):
    s = open(HTML_PATH, encoding="utf-8").read()
    s, n1 = re.subn(r'(<!-- EVENTI-TIPO:START -->\n).*?(\n *<!-- EVENTI-TIPO:END -->)',
                    lambda m: m.group(1) + tipo_opts + m.group(2), s, count=1, flags=re.S)
    s, n2 = re.subn(r'(<!-- EVENTI-LISTA:START -->\n).*?(\n *<!-- EVENTI-LISTA:END -->)',
                    lambda m: m.group(1) + lista + m.group(2), s, count=1, flags=re.S)
    # Il JSON-LD non viene sostituito dov'e': viene tolto e riscritto in fondo
    # al body. Stava nel <head>, cioe' ~520 KB (62 KB gzip, il 30% del
    # trasferito) che il browser doveva scaricare PRIMA del primo byte di
    # contenuto visibile. Con l'88% del traffico da smartphone e' il primo costo
    # da togliere dalla strada. Per Google e' indifferente: legge i dati
    # strutturati ovunque stiano nel documento.
    #
    # Togliamo anche la riga vuota che il vecchio blocco si lasciava dietro,
    # altrimenti a ogni run la pagina ne accumula una.
    s, n3 = re.subn(r'<script type="application/ld\+json" id="eventi-jsonld">.*?</script>\n?',
                    '', s, count=1, flags=re.S)
    if n3 == 1:
        # lambda e non stringa: il payload JSON contiene \" e \u..., che come
        # replacement letterale re li interpreterebbe come escape ("bad escape").
        s, n3 = re.subn(r'(?=</body>)', lambda _: jsonld + '\n', s, count=1)
    # Il blocco province e' opzionale: se i marker non ci sono (eventi.html piu'
    # vecchio del deploy) si va avanti con un avviso invece di far fallire tutto.
    n4 = 1
    if prov_opts is not None:
        s, n4 = re.subn(r'(<!-- EVENTI-PROV:START -->\n).*?(\n *<!-- EVENTI-PROV:END -->)',
                        lambda m: m.group(1) + prov_opts + m.group(2), s, count=1, flags=re.S)
        if n4 != 1:
            print("[genera_eventi] ATTENZIONE: marker EVENTI-PROV non trovati in "
                  "eventi.html: il filtro provincia resta quello scritto a mano")
    # Anche questo blocco e' opzionale, stessa ragione: un eventi.html piu'
    # vecchio del deploy non deve far fallire tutta la generazione.
    if comuni_html is not None:
        s, n5 = re.subn(r'(<!-- EVENTI-COMUNI:START -->\n).*?(\n *<!-- EVENTI-COMUNI:END -->)',
                        lambda m: m.group(1) + comuni_html + m.group(2), s, count=1, flags=re.S)
        if n5 != 1:
            print("[genera_eventi] ATTENZIONE: marker EVENTI-COMUNI non trovati in "
                  "eventi.html: l'elenco delle pagine comune non viene scritto")
    # Opzionale come gli altri due: se i marker non ci sono resta l'hero scritto
    # a mano, che e' sbagliato solo fuori stagione - non vale far fallire il run.
    if hero is not None:
        s, n6 = re.subn(r'(<!-- EVENTI-HERO:START -->\n).*?(\n *<!-- EVENTI-HERO:END -->)',
                        lambda m: m.group(1) + hero + m.group(2), s, count=1, flags=re.S)
        if n6 != 1:
            print("[genera_eventi] ATTENZIONE: marker EVENTI-HERO non trovati in "
                  "eventi.html: titolo e occhiello restano quelli scritti a mano")
    # La riga delle quattro porte. Opzionale come gli altri tre blocchi, e per
    # la stessa ragione: un eventi.html piu' vecchio del deploy non deve far
    # fallire tutta la generazione.
    s, n7 = re.subn(r'(<!-- EVENTI-ECO:START -->\n).*?(\n *<!-- EVENTI-ECO:END -->)',
                    lambda m: m.group(1) + blocco_ecosistema('eventi') + m.group(2),
                    s, count=1, flags=re.S)
    if n7 != 1:
        print("[genera_eventi] ATTENZIONE: marker EVENTI-ECO non trovati in "
              "eventi.html: la riga delle quattro porte non viene scritta")
    if n1 != 1 or n2 != 1 or n3 != 1:
        raise SystemExit(f"Ancoraggi non trovati in eventi.html (tipo={n1}, lista={n2}, json-ld={n3})")
    open(HTML_PATH, "w", encoding="utf-8").write(s)


MIN_HOME_NUMERI = 12


def blocco_numeri(events):
    """La riga di numeri sotto il carosello della home, o ''.

    Non e' un contatore di visite, ed e' una scelta presa apposta: il pubblico
    che GA4 ci misura e' circa un terzo di quello vero (il banner consenso), e
    il traffico e' stagionale al punto che il 79% dei clic del trimestre sta in
    otto giorni di agosto. Un numero pubblico che ogni novembre scende e' peggio
    di nessun numero. Questi invece dicono quanto lavoro c'e' dentro — non
    quanti ci guardano — li conosce gia' il generatore e non hanno bisogno di
    nessuno script in piu'.

    Sotto MIN_HOME_NUMERI non si stampa niente, che e' la stessa regola al
    contrario: con l'agenda magra la riga direbbe il vero e suonerebbe male.

    L'ultima voce non e' un numero ma il link a /metodo.html: e' la risposta
    alla domanda che i numeri fanno venire ("chi li ha controllati?"), ed e'
    anche l'unico link a quella pagina che parte dal corpo della home invece
    che dalla nav."""
    if len(events) < MIN_HOME_NUMERI:
        return ''
    comuni = len({_key(e.get('citta')) for e in events if (e.get('citta') or '').strip()})
    prov = {e.get('prov') for e in events if e.get('prov')}
    voci = [f"<b>{len(events)}</b> eventi in agenda"]
    if comuni:
        voci.append(f"<b>{comuni}</b> comuni")
    if prov:
        voci.append(f"<b>{len(prov)}</b> " + ("province" if len(prov) > 1 else "provincia"))
    voci.append('<a href="/metodo.html">verificati uno per uno</a>')
    return '<p class="he-num">' + ''.join(f"<span>{v}</span>" for v in voci) + '</p>'


def inject_home(cards_html, stagione='', numeri=''):
    """Sostituisce le card del carosello in index.html tra i marker HOME-EVENTI,
    la riga stagionale tra i marker HOME-STAGIONE e i numeri tra HOME-NUMERI.
    Se la home o i marker mancano, salta senza errore."""
    if not os.path.exists(HOME_PATH):
        print("[genera_eventi] index.html non trovato, salto carosello home")
        return
    s = open(HOME_PATH, encoding="utf-8").read()
    block = "<!-- HOME-EVENTI:START -->\n" + cards_html + "\n      <!-- HOME-EVENTI:END -->"
    s, n = re.subn(r'<!-- HOME-EVENTI:START -->.*?<!-- HOME-EVENTI:END -->',
                   lambda _: block, s, count=1, flags=re.S)
    if n != 1:
        print("[genera_eventi] marker HOME-EVENTI non trovati in index.html, salto carosello home")
        return
    # La riga sta FUORI da .he-track: dentro sarebbe un elemento della striscia
    # orizzontale delle card, cioe' una scheda finta larga quanto le altre.
    riga = f'<p class="he-stagione">{stagione}</p>' if stagione else ''
    s, ns = re.subn(r'<!-- HOME-STAGIONE:START -->.*?<!-- HOME-STAGIONE:END -->',
                    lambda _: f'<!-- HOME-STAGIONE:START -->{riga}<!-- HOME-STAGIONE:END -->',
                    s, count=1, flags=re.S)
    s, nn = re.subn(r'<!-- HOME-NUMERI:START -->.*?<!-- HOME-NUMERI:END -->',
                    lambda _: f'<!-- HOME-NUMERI:START -->{numeri}<!-- HOME-NUMERI:END -->',
                    s, count=1, flags=re.S)
    # Le quattro porte. Qui si passa qui=None: sulla home non si e' dentro
    # nessuna famiglia, quindi escono tutte e quattro.
    porte = blocco_ecosistema()
    s, np_ = re.subn(r'<!-- HOME-PORTE:START -->.*?<!-- HOME-PORTE:END -->',
                     lambda _: f'<!-- HOME-PORTE:START -->{porte}<!-- HOME-PORTE:END -->',
                     s, count=1, flags=re.S)
    open(HOME_PATH, "w", encoding="utf-8").write(s)
    print("[genera_eventi] carosello eventi aggiornato in index.html"
          + (f", riga stagionale: {'sì' if stagione else 'no'}" if ns else
             ", marker HOME-STAGIONE non trovati")
          + (f", numeri: {'sì' if numeri else 'no'}" if nn else
             ", marker HOME-NUMERI non trovati")
          + ("" if np_ else ", marker HOME-PORTE non trovati"))


def update_sitemap(slugs=(), comuni=(), landing=()):
    """Porta il <lastmod> di eventi.html nella sitemap alla data odierna e
    rigenera il blocco delle pagine evento.
    Il commit avviene (dal workflow) solo se eventi.html è davvero cambiato,
    così la data riflette una modifica reale dei contenuti."""
    if not os.path.exists(SITEMAP_PATH):
        return
    today = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()

    if slugs:
        blocco = "\n".join(
            f"  <url>\n    <loc>{SITE_URL}/eventi/{sl}.html</loc>\n"
            f"    <lastmod>{mod}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>"
            for sl, mod in slugs.items())
        s, nb = re.subn(
            r'(<!-- PAGINE-EVENTO:START.*?-->).*?( *<!-- PAGINE-EVENTO:END -->)',
            lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
        if nb == 1:
            print(f"[genera_eventi] sitemap: {len(slugs)} pagine evento")
        else:
            print("[genera_eventi] sitemap: marker PAGINE-EVENTO non trovati, salto")

    if comuni:
        # priority piu' alta delle pagine evento: una pagina comune vale tutto
        # l'anno, una pagina evento vale fino alla domenica della sagra.
        blocco = "\n".join(
            f"  <url>\n    <loc>{SITE_URL}/eventi/comune/{sl}.html</loc>\n"
            f"    <lastmod>{mod}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>"
            for sl, mod in comuni.items())
        s, nb = re.subn(
            r'(<!-- PAGINE-COMUNE:START.*?-->).*?( *<!-- PAGINE-COMUNE:END -->)',
            lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
        if nb == 1:
            print(f"[genera_eventi] sitemap: {len(comuni)} pagine comune")
        else:
            print("[genera_eventi] sitemap: marker PAGINE-COMUNE non trovati, salto")

    if landing:
        # priority 0.9 come l'agenda: "cosa fare oggi" e "sagre in provincia di"
        # sono query permanenti, non legate a una singola edizione. changefreq
        # daily perche' e' vero: il contenuto di /eventi/oggi.html cambia ogni
        # notte per costruzione.
        blocco = "\n".join(
            f"  <url>\n    <loc>{SITE_URL}/{p.replace(os.sep, '/')}</loc>\n"
            f"    <lastmod>{mod}</lastmod>\n"
            f"    <changefreq>daily</changefreq>\n    <priority>0.9</priority>\n  </url>"
            for p, mod in landing.items())
        s, nb = re.subn(
            r'(<!-- PAGINE-LANDING:START.*?-->).*?( *<!-- PAGINE-LANDING:END -->)',
            lambda m: f"{m.group(1)}\n{blocco}\n{m.group(2)}", s, count=1, flags=re.S)
        if nb == 1:
            print(f"[genera_eventi] sitemap: {len(landing)} pagine di intenzione")
        else:
            print("[genera_eventi] sitemap: marker PAGINE-LANDING non trovati, salto")

    s, n = re.subn(
        r'(<loc>https://www\.daop\.it/eventi\.html</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + today + m.group(2), s, count=1)
    print(f"[genera_eventi] sitemap: lastmod eventi.html -> {today}" if n == 1
          else "[genera_eventi] sitemap: blocco eventi.html non trovato, salto")
    # Una sola scrittura alla fine: se il lastmod non matcha non dobbiamo
    # comunque perdere il blocco delle pagine evento appena rigenerato.
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)


def controlla_crollo(events):
    """Blocca la rigenerazione se gli eventi sono crollati rispetto all'ultima volta.

    PERCHE' ESISTE (05/08/2026): l'export CSV di Google **rispetta i filtri** del
    foglio. Con un filtro attivo sul tab Eventi l'export restituisce solo le righe
    visibili: quel giorno erano 26 invece di 193. Rigenerare in quello stato
    pubblica un sito con un decimo degli eventi, la sitemap che crolla, e decine di
    pagine messe in noindex - tutto senza un errore, quindi senza che nessuno se ne
    accorga. Il workflow notturno gira non presidiato: e' proprio lo scenario in cui
    un guasto silenzioso fa danno.

    Il confronto e' con data/eventi.json, l'istantanea committata dell'ultimo run
    buono. Se il calo e' oltre la soglia si esce con codice 1: il workflow FALLISCE
    in modo visibile invece di pubblicare. Per un calo legittimo (fine stagione) si
    forza con la variabile d'ambiente ACCETTA_CALO=1.
    """
    if os.environ.get("ACCETTA_CALO"):
        print("[genera_eventi] ACCETTA_CALO attivo: nessun controllo sul crollo.")
        return
    try:
        with open(JSON_PATH, encoding="utf-8") as fh:
            precedenti = len(json.load(fh))
    except Exception:
        return          # prima esecuzione o snapshot illeggibile: niente con cui confrontare

    if precedenti < 20:
        return          # troppo pochi per un confronto sensato

    soglia = int(precedenti * 0.6)
    if len(events) >= soglia:
        return

    print()
    print("=" * 68)
    print("  BLOCCATO: gli eventi sono CROLLATI, non rigenero il sito.")
    print("=" * 68)
    print(f"  letti ora        : {len(events)}")
    print(f"  ultimo run buono : {precedenti}   (soglia di allarme: {soglia})")
    print()
    print("  Causa piu' probabile: un FILTRO attivo sul tab Eventi del foglio.")
    print("  L'export CSV rispetta i filtri, quindi le righe nascoste non arrivano.")
    print("  Togli il filtro (Dati -> Rimuovi filtro) e rilancia.")
    print()
    print("  Se il calo e' vero (fine stagione), forza con:  ACCETTA_CALO=1")
    print("=" * 68)
    sys.exit(1)


BOX_DIR = os.path.join(ROOT, "eventi")

# TUTTA l'agenda della provincia, non una finestra (11/08/2026).
#
# La storia di questo taglio in due righe, perche' e' istruttiva: la prima
# versione fermava il riquadro a 12 righe fisse, e con i cinque eventi al
# giorno che ha Cuneo si fermava al giovedi', cioe' prima del weekend. La
# seconda l'ha sostituito con una finestra di 10 giorni, che il weekend lo
# teneva sempre dentro ma spostava il problema piu' in la': il partner
# pubblicava 21 eventi su 59, e per chi guardava il suo sito settembre non
# esisteva.
#
# Con i filtri qui sotto la lista lunga smette di essere una cosa da contenere
# e diventa il magazzino da cui i filtri pescano. Sessanta voci che si
# restringono a "Cuneo, questo weekend" in due clic servono piu' di ventuno che
# non si restringono affatto.
#
# Resta solo un paracadute molto alto: se un giorno il foglio esplode, meglio un
# riquadro troncato che un file da megabyte dentro la pagina di qualcun altro.
BOX_MAX = 400

# Sotto questa soglia la barra dei filtri non si disegna: con sei eventi in
# elenco tre menu a tendina sono piu' ingombro che aiuto.
BOX_MIN_FILTRI = 8


def _box_cerca(e):
    """Il testo su cui morde la casella di ricerca, gia' pronto per il confronto.

    Senza accenti e in minuscolo, perche' chi cerca scrive "citta" e "perche'"
    come gli viene: il confronto lo fa il generatore una volta, non il browser a
    ogni tasto premuto. Dentro ci va anche quello che NON si vede nella riga -
    il luogo e il nome della manifestazione - cosi' "biblioteca" o "sagra del
    raviolo" trovano anche gli eventi che nel titolo non li nominano.
    """
    pezzi = [e.get('nome'), e.get('citta'), e.get('luogo'),
             e.get('manifest'), e.get('categoria')]
    s = ' '.join(p for p in pezzi if p)
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'\s+', ' ', s).strip().lower()


def _box_riga(e, oggi):
    quando = _quando_breve(e, oggi)
    ora = (e.get('ora') or '').strip()
    if any(c.isdigit() for c in ora):
        quando += ' · ' + trunc(ora, 12)
    citta = (e.get('citta') or '').strip()
    # data-s/data-e sono le date VERE, non l'etichetta: "oggi" e "questo
    # weekend" li decide il browser con l'orologio di chi guarda, non con
    # quello che aveva il generatore stanotte. Servono entrambe perche' una
    # sagra di tre giorni deve comparire sotto "oggi" anche il secondo giorno.
    return (f'<li data-c="{esc(citta)}" data-k="{esc(e.get("categoria") or "")}"'
            f' data-s="{e["d_start"].isoformat()}" data-e="{e["d_end"].isoformat()}"'
            f' data-t="{esc(_box_cerca(e))}">'
            f'<span class="q">{esc(quando)}</span>'
            f'<a href="{SITE_URL}{_href_evento(e)}">'
            f'{esc(trunc(e.get("nome") or "", 70))}</a>'
            + (f'<span class="dv">{esc(citta)}</span>' if citta else '')
            + '</li>')


def _box_filtri(ev):
    """La barra dei filtri. Stringa vuota se non c'e' abbastanza da filtrare."""
    if len(ev) < BOX_MIN_FILTRI:
        return ''
    comuni = sorted({(x.get('citta') or '').strip() for x in ev} - {''},
                    key=lambda s: s.lower())
    categorie = sorted({(x.get('categoria') or '').strip() for x in ev} - {''},
                       key=lambda s: s.lower())
    # In ordine alfabetico e non per frequenza: una tendina si legge cercando un
    # nome, e un nome lo si cerca dove l'alfabeto dice che sta.
    opz_c = ''.join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in comuni)
    opz_k = ''.join(f'<option value="{esc(k)}">{esc(k)}</option>' for k in categorie)
    sel_c = (f'<select id="fc" aria-label="Filtra per comune">'
             f'<option value="">Tutti i comuni</option>{opz_c}</select>'
             if len(comuni) > 1 else '')
    sel_k = (f'<select id="fk" aria-label="Filtra per categoria">'
             f'<option value="">Tutte le categorie</option>{opz_k}</select>'
             if len(categorie) > 1 else '')
    return f'''<div class="fx">
<div class="fw" role="group" aria-label="Filtra per data">
<button type="button" data-w="oggi">Oggi</button>
<button type="button" data-w="weekend">Weekend</button>
<button type="button" data-w="tutti" class="on" aria-pressed="true">Tutti</button>
</div>
{sel_c}{sel_k}
<input id="fq" type="search" placeholder="Cerca…" aria-label="Cerca tra gli eventi">
<button type="button" id="fz" class="fz" hidden>Azzera</button>
<span id="nc" class="nc"></span>
</div>'''


def _box_html(prov, ev, oggi):
    nome = PROVINCE_NOMI.get(prov, prov)
    righe = ''.join(_box_riga(e, oggi) for e in ev)
    filtri = _box_filtri(ev)
    if not righe:
        righe = ('<li class="vuoto">Nessun evento in agenda in questo momento. '
                 'Torna a trovarci fra qualche giorno.</li>')
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Eventi per bambini in provincia di {esc(nome)} | DAOP</title>
<meta name="robots" content="noindex, follow">
<base target="_blank">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
/* Il body resta TRASPARENTE e la scheda bianca sta dentro: cosi' il riquadro
   si appoggia sul colore del sito che lo ospita invece di stamparci sopra un
   rettangolo bianco che non c'entra niente. (La pagina di Cuneo ha lo sfondo
   #f3f4f9: con body bianco si vedeva la toppa.) */
body{{background:transparent;color:#1a2d3a;
 font:400 15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased;padding:4px}}
.card{{background:#fff;border:1px solid rgba(45,74,92,.10);border-radius:14px;
 box-shadow:0 1px 2px rgba(45,74,92,.05),0 6px 18px rgba(45,74,92,.06);
 padding:12px 14px 14px;overflow:hidden}}
/* La testata: marchio a sinistra, due righe di testo a destra. Compatta di
   proposito - dentro un iframe alto 560px ogni riga di intestazione e' una
   riga di eventi in meno, e gli eventi sono il motivo per cui uno guarda. */
.hd{{display:flex;align-items:center;gap:10px;padding-bottom:10px;
 border-bottom:1px solid rgba(45,74,92,.12)}}
.hd img{{width:38px;height:38px;border-radius:50%;flex:none;
 border:1px solid rgba(45,74,92,.12);background:#fff}}
.tt{{font-size:12.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
 color:#6ba5a8;line-height:1.25}}
.st{{font-size:12.5px;color:#627588;line-height:1.3}}
.st b{{color:#2d4a5c;font-weight:600}}
ul{{list-style:none}}
li{{display:grid;grid-template-columns:88px 1fr;gap:2px 12px;align-items:baseline;
 padding:10px 0;border-top:1px solid rgba(45,74,92,.14)}}
/* [hidden] della UA perde contro `li{{display:grid}}`: senza questa riga i
   filtri nascondono e non si vede nessun effetto. */
li[hidden]{{display:none}}
/* Il filo sopra lo toglie il JS alla prima riga VISIBILE, che dopo un filtro
   non e' quasi mai la prima figlia. */
li:first-child,li.p{{border-top:0}}
/* Sticky dentro la scheda, quindi il fondo bianco pieno e' quello giusto: sotto
   c'e' la scheda, non la pagina del partner. */
/* Sticky dentro la scheda, quindi il fondo bianco pieno e' quello giusto: sotto
   c'e' la scheda, non la pagina del partner.
   Compatta per forza: l'iframe del partner e' alto 560px fissi, e ogni riga in
   cui la barra va a capo e' un evento in meno che si vede senza scorrere. Con i
   controlli elastici (flex-basis piccola) su 343px stanno in due righe invece
   di quattro: 125px di barra erano diventati cinque eventi visibili su
   novantanove. */
.fx{{position:sticky;top:0;z-index:2;display:flex;flex-wrap:wrap;gap:5px;
 align-items:center;padding:8px 0;background:#fff}}
.fx select,.fx input{{font:inherit;font-size:12.5px;color:#2d4a5c;
 border:1px solid rgba(45,74,92,.22);border-radius:7px;padding:4px 6px;
 background:#fff;max-width:100%}}
.fx select{{flex:1 1 104px;min-width:0}}
.fx input{{min-width:0;flex:1 1 86px}}
.fx select:focus-visible,.fx input:focus-visible,.fx button:focus-visible{{
 outline:2px solid #6ba5a8;outline-offset:1px}}
.fw{{display:flex;border:1px solid rgba(45,74,92,.22);border-radius:7px;
 overflow:hidden}}
.fw button{{font:inherit;font-size:12.5px;color:#2d4a5c;background:#fff;border:0;
 border-left:1px solid rgba(45,74,92,.16);padding:4px 8px;cursor:pointer}}
.fw button:first-child{{border-left:0}}
.fw button:hover{{background:rgba(107,165,168,.12)}}
.fw button.on{{background:#6ba5a8;color:#fff}}
.fz{{font:inherit;font-size:13px;color:#627588;background:none;border:0;
 padding:5px 2px;cursor:pointer;text-decoration:underline}}
.fz:hover{{color:#d4793a}}
.nc{{font-size:12.5px;color:#627588;margin-left:auto}}
.nn{{padding:14px 0;color:#627588;font-size:14px}}
.q{{grid-row:span 2;font-size:12px;font-weight:700;color:#e8954a;text-transform:uppercase;
 letter-spacing:.03em;padding-top:2px}}
li a{{color:#2d4a5c;font-weight:600;text-decoration:none}}
li a:hover,li a:focus{{color:#d4793a;text-decoration:underline}}
.dv{{font-size:13px;color:#627588}}
.vuoto{{grid-template-columns:1fr;color:#627588;font-size:14px}}
.fn{{margin-top:12px;padding-top:10px;border-top:1px solid rgba(45,74,92,.14);
 font-size:12.5px;color:#627588;display:flex;flex-wrap:wrap;gap:4px 10px;
 align-items:baseline;justify-content:space-between}}
.fn a{{color:#2d4a5c;font-weight:600;text-decoration:none}}
.fn a:hover{{text-decoration:underline}}
.fn .vt{{color:#d4793a}}
@media (max-width:420px){{
 li{{grid-template-columns:1fr}}
 .q{{grid-row:auto}}
}}
/* POCA ALTEZZA: il riquadro si stringe da solo.
   Dentro un iframe una media query sui pixel misura il RIQUADRO, non lo
   schermo: qui dentro `max-height` vuol dire "il partner mi ha dato poco
   spazio". E allora se lo prende il contenuto, invece di chiedere a lui di
   cambiare una cifra sul suo sito - che e' una modifica che dipende da una
   persona, cioe' una modifica che meta' delle volte non si fa.
   Sparisce la riga "a cura di DAOP - Dove Andiamo Oggi Papi": il logo e il
   credito in fondo il marchio lo dicono lo stesso, e a 560px un evento in piu'
   vale piu' di una riga di firma. */
@media (max-height:620px){{
 .card{{padding:8px 12px 10px}}
 .hd{{padding-bottom:7px;gap:8px}}
 .hd img{{width:28px;height:28px}}
 .st{{display:none}}
 .fx{{padding:6px 0}}
 li{{padding:7px 0}}
 .fn{{margin-top:8px;padding-top:7px}}
}}
</style>
</head>
<body>
<div class="card">
<div class="hd">
<img src="{SITE_URL}/assets/images/logodaop.webp" alt="DAOP" width="38" height="38">
<div>
<p class="tt">Eventi per bambini · {esc(nome)}</p>
<p class="st">a cura di <b>DAOP</b> &ndash; Dove Andiamo Oggi Papi</p>
</div>
</div>
{filtri}
<ul id="ls">{righe}</ul>
<p id="nn" class="nn" hidden>Nessun evento con questi filtri.</p>
<p class="fn"><span>Agenda aggiornata ogni giorno da
<a href="{SITE_URL}/eventi.html">daop.it</a></span>
<a class="vt" href="{SITE_URL}/eventi.html">Vedi tutti gli eventi &rarr;</a></p>
</div>
<script>
// L'iframe non si ridimensiona da solo. Chi vuole il riquadro sempre alto
// quanto serve aggiunge tre righe sul suo sito e ascolta questo messaggio;
// chi non lo fa tiene l'altezza fissa e la lista scorre. Nessuna delle due
// strade richiede che il partner sappia programmare.
(function () {{
  function avvisa() {{
    parent.postMessage({{daopBox: true, altezza: document.body.scrollHeight}}, '*');
  }}
  addEventListener('load', avvisa);
  addEventListener('resize', avvisa);

  // --- filtri ---------------------------------------------------------
  // Tutto quello che serve e' gia' nel documento: i filtri mostrano e
  // nascondono righe, non chiedono niente a nessuno. Il riquadro resta un file
  // solo, senza chiamate di rete, e continua a funzionare identico dentro
  // WordPress, Wix o una pagina scritta a mano.
  var lista = document.getElementById('ls');
  var barra = document.querySelector('.fx');
  if (!lista || !barra) return;

  var voci = [].slice.call(lista.querySelectorAll('li[data-s]'));
  var selC = document.getElementById('fc');
  var selK = document.getElementById('fk');
  var cerca = document.getElementById('fq');
  var azzera = document.getElementById('fz');
  var conta = document.getElementById('nc');
  var niente = document.getElementById('nn');
  var giorni = [].slice.call(barra.querySelectorAll('.fw button'));
  var quando = 'tutti';

  function iso(d) {{
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2)
                           + '-' + ('0' + d.getDate()).slice(-2);
  }}
  function norm(s) {{
    return (s || '').toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}
  // L'intervallo lo si calcola con l'orologio di CHI GUARDA, non con quello del
  // generatore: la pagina puo' restare in cache nel browser o nella CDN del
  // partner, e un "oggi" congelato a stanotte sarebbe una bugia il giorno dopo.
  function intervallo() {{
    var d = new Date(); d.setHours(0, 0, 0, 0);
    if (quando === 'oggi') return [iso(d), iso(d)];
    var g = d.getDay();                          // 0 = domenica
    if (g === 0) return [iso(d), iso(d)];        // di domenica il weekend finisce oggi
    var sab = new Date(d); sab.setDate(d.getDate() + ((6 - g) % 7));
    var dom = new Date(sab); dom.setDate(sab.getDate() + 1);
    return [iso(sab), iso(dom)];
  }}

  function filtra() {{
    var c = selC ? selC.value : '';
    var k = selK ? selK.value : '';
    var q = norm(cerca ? cerca.value : '').trim();
    var r = quando === 'tutti' ? null : intervallo();
    var n = 0, primo = null;
    voci.forEach(function (li) {{
      // Sulle date si confronta la SOVRAPPOSIZIONE, non l'inizio: una sagra
      // che parte venerdi' e dura tre giorni e' un evento del weekend anche se
      // e' cominciata prima.
      var ok = (!c || li.getAttribute('data-c') === c)
            && (!k || li.getAttribute('data-k') === k)
            && (!q || li.getAttribute('data-t').indexOf(q) > -1)
            && (!r || (li.getAttribute('data-s') <= r[1]
                       && li.getAttribute('data-e') >= r[0]));
      li.hidden = !ok;
      li.classList.remove('p');
      if (ok) {{ n++; if (!primo) primo = li; }}
    }});
    if (primo) primo.classList.add('p');
    if (niente) niente.hidden = n > 0;
    if (conta) conta.textContent = n === 0 ? '' : (n === 1 ? '1 evento' : n + ' eventi');
    var attivo = !!(c || k || q || quando !== 'tutti');
    if (azzera) azzera.hidden = !attivo;
    avvisa();
  }}

  giorni.forEach(function (b) {{
    b.addEventListener('click', function () {{
      quando = b.getAttribute('data-w');
      giorni.forEach(function (x) {{
        var on = x === b;
        x.classList.toggle('on', on);
        x.setAttribute('aria-pressed', on ? 'true' : 'false');
      }});
      filtra();
    }});
  }});
  if (selC) selC.addEventListener('change', filtra);
  if (selK) selK.addEventListener('change', filtra);
  if (cerca) cerca.addEventListener('input', filtra);
  if (azzera) azzera.addEventListener('click', function () {{
    if (selC) selC.value = '';
    if (selK) selK.value = '';
    if (cerca) cerca.value = '';
    giorni.forEach(function (x) {{
      var on = x.getAttribute('data-w') === 'tutti';
      x.classList.toggle('on', on);
      x.setAttribute('aria-pressed', on ? 'true' : 'false');
    }});
    quando = 'tutti';
    filtra();
  }});
  filtra();
}})();
</script>
</body>
</html>
"""


def scrivi_box(events, oggi):
    """Il riquadro che un partner territoriale incolla sul proprio sito.

    PERCHE' ESISTE (10/08/2026). Il patto con i partner di provincia e' che gli
    eventi si regalano e le schede dei luoghi no: un evento scade e condividerlo
    non costa niente, una scheda luogo resta e vale per anni. Ma "ti do gli
    eventi" a un partner che non programma non vuol dire niente finche' non
    esiste una cosa che possa incollare. Questa e' quella cosa.

    E' una pagina spogliata - niente menu, niente header, niente footer - che il
    partner mette dentro un <iframe> di una riga. Funziona su WordPress, Wix,
    Squarespace e su qualsiasi cosa accetti dell'HTML, che e' l'unico requisito
    che si puo' dare a qualcuno di cui non conosci il sito.

    TRE SCELTE CHE SEMBRANO DETTAGLI E NON LO SONO:

    1. `noindex`. Questa pagina e' l'agenda ridetta a un'altra URL. Lasciarla
       indicizzare vorrebbe dire mettere in concorrenza con eventi.html una sua
       copia sbiadita e senza navigazione.

    2. `<base target="_blank">`. Dentro un iframe un link normale aprirebbe
       daop.it INTERO nel riquadro da 600 pixel del partner. Con il base ogni
       link esce in una scheda nuova, che e' anche quello che vuole lui: il
       visitatore non lascia il suo sito.

    3. CSS scritto qui dentro, senza il foglio di stile del sito. Il riquadro
       carica dentro la pagina di qualcun altro: deve pesare poco e non puo'
       dipendere dal guscio, che porterebbe con se' font, header e regole sul
       body che li' non hanno senso.

    4. I filtri (comune, quando, categoria, parole) lavorano SUL DOCUMENTO che
       e' gia' arrivato: mostrano e nascondono righe, non chiedono niente alla
       rete. Un filtro che interroga un server sarebbe una dipendenza in piu'
       dentro la pagina di qualcun altro, e la prima cosa che si rompe in
       silenzio il giorno che il server non risponde. Cosi' invece il peggio
       che puo' capitare e' un riquadro fermo a ieri.

    Un file per provincia e non ?prov=CN, perche' il sito e' statico: un
    parametro nella URL non cambierebbe niente senza JavaScript.
    """
    os.makedirs(BOX_DIR, exist_ok=True)
    scritti = []
    for prov in PROVINCE_PUBBLICATE:
        # `d_end >= oggi` e non `d_start`: senza finestra superiore un evento
        # gia' finito non ha piu' niente che lo tenga fuori, e una sagra di tre
        # giorni deve restare in elenco anche il suo ultimo giorno.
        ev = sorted((e for e in events
                     if e.get('prov') == prov and e['d_end'] >= oggi),
                    key=lambda e: (e['d_start'], (e.get('nome') or '')))[:BOX_MAX]
        path = os.path.join(BOX_DIR, f"box-{prov.lower()}.html")
        nuovo = _box_html(prov, ev, oggi)
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            scritti.append((prov, len(ev), False))
            continue
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(nuovo)
        scritti.append((prov, len(ev), True))
    detta = ', '.join(f"{p} {n}{'*' if w else ''}" for p, n, w in scritti)
    print(f"[genera_eventi] riquadri da incorporare: {detta}  (* riscritto)")


def main():
    events = normalize(fetch_rows())
    controlla_crollo(events)
    segnala_doppioni(events)
    segnala_sovrapposizioni(events)
    segnala_comuni_simili(events)
    segnala_durate_assurde(events)
    segnala_date_ignote(events)
    segnala_senza_coordinate(events)
    assegna_ancore(events)
    # Il proprio numero si scrive PRIMA di generare qualunque pagina: la riga
    # delle quattro porte lo rilegge, e scritto dopo mostrerebbe quello di ieri
    # anche sulle pagine di stanotte.
    conteggio_scrivi('eventi', len(events))
    # hub va calcolato PRIMA di render(): l'agenda linka le pagine comune sia
    # nelle schede sia nel blocco in fondo, e senza non saprebbe quali esistono.
    oggi = datetime.date.today()
    storico = aggiorna_storico(events, oggi)
    hub = comuni_hub(events, storico, oggi)
    # Prima di render() e di qualunque _guscio(): la nav di eventi.html e' la
    # sorgente da cui ~360 pagine copiano la loro, quindi va messa a posto
    # adesso, se no le generate di stanotte portano la stagione di ieri.
    aggiorna_nav()
    tipo_opts, lista = render(events, hub)
    jsonld = render_jsonld(events)
    inject(tipo_opts, lista, jsonld, opzioni_provincia(events), blocco_comuni(hub, oggi),
           blocco_hero(events, oggi))
    inject_home(render_home(events), blocco_stagione(events, oggi),
                blocco_numeri(events))
    slugs = scrivi_pagine(events, hub)
    comuni = scrivi_comuni(hub, oggi)
    landing = scrivi_landing(events, hub, storico, oggi)
    scrivi_metodo(events)
    scrivi_zone(events, hub)
    scrivi_box(events, oggi)
    # aggiorna l'istantanea committata
    # 'riga' resta fuori dall'istantanea: e' la posizione nel foglio, cambia a
    # ogni inserimento e sporcherebbe il diff di data/eventi.json a ogni run.
    rec = [{k: (v.isoformat() if isinstance(v, datetime.date) else v)
            for k, v in e.items()
            if k != 'riga' and (k not in CAMPI_DAOP and k not in CAMPI_EXTRA
                                or (v or '').strip())} for e in events]
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    update_sitemap(slugs, comuni, landing)
    print(f"[genera_eventi] {len(events)} eventi futuri scritti in eventi.html")


if __name__ == "__main__":
    main()
