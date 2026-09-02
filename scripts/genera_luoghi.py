#!/usr/bin/env python3
"""
Genera /luoghi.html: l'elenco filtrabile dei posti dove le famiglie ci vanno.

PERCHE' UNA PAGINA SOLA E NON UNA SCHEDA PER LUOGO
--------------------------------------------------
La domanda di partenza era "800 luoghi, faccio 800 schede?". No, e non per
pigrizia: il sitemap ha 270 URL, e 800 pagine su template identico con il nome
del posto scambiato sarebbero i tre quarti del sito fatti delle pagine piu'
deboli che abbiamo. E' la definizione che Google da' dello scaled content abuse,
e la penalizzazione non resta sulle pagine nuove: si porta dietro il dominio,
cioe' eventi.html, che e' la pagina che regge il traffico.

Quindi: **una pagina, tante righe, i filtri**. Esattamente come l'agenda, che di
schede ne tiene 294 in un file solo. Una scheda propria (/luoghi/<slug>.html) la
si scrive quando c'e' qualcosa da dire che sta solo li' - foto nostre, orari
verificati, dov'e' l'ombra ad agosto, dove si cambia il pannolino - e quel
momento coincide quasi sempre con il luogo che diventa premium, perche' e' il
gestore a darci il materiale.

DA DOVE ARRIVANO I LUOGHI
-------------------------
Due sorgenti, e non pesano uguale:

1. **Il catalogo** - il tab "Luoghi" dello stesso foglio Google degli eventi,
   con ripiego su `data/luoghi.json` quando la rete non c'e' (stessa regola di
   genera_eventi.py: senza rete si va avanti con l'istantanea, non ci si ferma).
   E' questo l'elenco vero.

2. **L'agenda** - `data/eventi.json` e `data/storico-comuni.json`. Serve a
   sapere **cosa c'e' in programma** in un posto del catalogo, che e' il dato
   per cui questa pagina non e' una directory come le altre: nessun altro puo'
   scrivere "qui DAOP ha seguito 7 eventi per famiglie, il prossimo e' sabato".

Fuori da AL, AT e CN non si pubblica: il foglio raccoglie anche gite oltre le
tre province, ma la tendina non sa dire "una gita fuori" - vedi
`solo_province_nostre()`.

I posti che stanno SOLO nell'agenda (le piazze e le vie in cui passa una sagra)
entrano come righe proprie soltanto finche' il catalogo e' piccolo - vedi
SOGLIA_CATALOGO. Con 800 luoghi scelti a mano, aggiungerne 170 dedotti da "qui
e' passata una festa" diluirebbe l'elenco invece di arricchirlo, e la domanda
"dove si fanno le cose" ha gia' una pagina migliore: eventi.html.

IL PREMIUM: AGGIUNGE, NON RIORDINA
----------------------------------
La regola editoriale e' la stessa gia' presa su "Adatto Famiglie": un elenco non
si spacca in due quando la separazione smentisce il criterio con cui e' fatto. Se
la riga di chi paga stesse piu' in alto, il resto diventerebbe la serie B di una
selezione che abbiamo fatto noi. Quindi la scheda premium **aggiunge** (foto,
descrizione lunga, orari, contatti) e sta nel suo posto in ordine alfabetico,
dentro il suo comune, come tutte.

L'unico spazio in cui la posizione si compra e' il blocco "In evidenza" in cima,
che e' separato, dichiarato e non toglie la riga dall'elenco. Ed e' anche un
obbligo, non una scelta di stile: art. 22 comma 4-bis del Codice del consumo -
in una lista ricercabile i parametri di ordinamento vanno dichiarati, e omettere
che una posizione e' stata pagata sta nella lista nera delle pratiche ingannevoli
"in ogni caso". Da qui il blocco #come-ordiniamo, che non e' decorativo.

"Consigliato DAOP" e' un'altra cosa e non si compra: e' il giudizio nostro, lo
stesso flag che gia' esiste in agenda. Le due pillole restano distinte apposta.

Uso:
    python3 scripts/genera_luoghi.py        # funziona offline, DOPO genera_eventi.py
"""
import os
import re
import io
import csv
import json
import datetime
import collections
import html
import urllib.request
import urllib.parse

import genera_eventi as G

ROOT = G.ROOT
OUT_PATH = os.path.join(ROOT, "luoghi.html")
JSON_PATH = os.path.join(ROOT, "data", "luoghi.json")
INDICE_COMUNI = G.INDICE_LUOGHI_PATH
EVENTI_JSON = G.JSON_PATH
STORICO_JSON = os.path.join(ROOT, "data", "storico-comuni.json")
SITEMAP_PATH = G.SITEMAP_PATH

PAGE_URL = f"{G.SITE_URL}/luoghi.html"
DEFAULT_CSV = (f"https://docs.google.com/spreadsheets/d/{G.SHEET_ID}"
               "/gviz/tq?tqx=out:csv&sheet=Luoghi")
SUPABASE_FOTO = "https://aaseyjdsldgjerjqlumu.supabase.co"

# Quanti eventi passati bastano perche' un posto della sola agenda entri in
# elenco (cioe' solo quando il catalogo non c'e' per niente). A 1 entrerebbero
# anche le vie in cui e' passata una sfilata una volta: sono indirizzi, non
# luoghi dove si va.
MIN_EVENTI_AGENDA = 2

# Le categorie del foglio, indovinate dal nome. Serve SOLO ai luoghi dedotti
# dall'agenda, che una categoria non ce l'hanno: si riusano gli stessi slug del
# catalogo, cosi' colori, icone e filtro restano una cosa sola invece di due
# tassonomie da tenere allineate. Prima parola che vince, in quest'ordine.
INDOVINA_CAT = [
    ('acqua-mare', ('piscina', 'lido', 'spiaggia', 'lago', 'bagni ')),
    ('cultura-istruzione', ('museo', 'biblioteca', 'teatro', 'palazzo', 'castello',
                            'rocca', 'chiesa', 'santuario', 'oratorio', 'chiostro',
                            'villa ', 'cinema', 'auditorium', 'pinacoteca', 'torre ')),
    ('natura-aria-aperta', ('parco', 'giardin', 'bosco', 'sentiero', 'oasi',
                            'area verde', 'pineta', 'riserva')),
    ('fattorie-didattiche', ('fattoria', 'cascina', 'agrituris', 'azienda agricola',
                             'maneggio', 'centro equestre')),
    ('sport', ('campo', 'palestra', 'stadio', 'centro sportivo', 'polisportiv',
               'bocciofil', 'tennis', 'pista', 'palazzetto', 'sferisterio')),
    ('divertimento-avventura', ('luna park', 'area giochi', 'area feste', 'pro loco',
                                'circolo', 'ludoteca')),
]


def indovina_categoria(nome):
    n = ' ' + (nome or '').lower() + ' '
    for slug, chiavi in INDOVINA_CAT:
        if any(k in n for k in chiavi):
            return slug
    return 'altro'

NON_LUOGHI = re.compile(
    r'^(centro citt|centro storico|vie del (paese|centro)|vie e piazze|'
    r'varie (sedi|location)|tutto il paese|piu\' sedi|da definire|'
    r'sede da definire|vari luoghi|in paese|stand gastronomic|'
    r'sede della manifestazione)', re.I)
FRAZIONE = re.compile(r'\bfraz(\.|ione\b)', re.I)


# ── Le colonne del tab "Luoghi" ──────────────────────────────────────────────
#
# I nomi sono tollerati in piu' grafie perche' il foglio lo scrivono due persone
# e perche' una colonna rinominata non deve far uscire una pagina monca in
# silenzio. La prima grafia e' quella vera del foglio al 12/08/2026.
#
# Passaporto* e CircuitoNome si leggono ma NON si stampano: sono un'altra
# funzione (il passaporto dell'Esploratore), oggi vuota su tutte le righe, e
# inventarle un'interfaccia qui vorrebbe dire indovinare come funziona.
COLONNE = {
    'codice': ('codice', 'id'),
    'nome': ('nome', 'luogo', 'denominazione'),
    'icona': ('icona', 'emoji'),
    'categoria': ('categoria', 'tipo', 'tipologia'),
    'servizi': ('servizi', 'attività', 'attivita'),
    'tag': ('tag', 'tags', 'etichette'),
    'indirizzo': ('indirizzo', 'via', 'indirizzo completo'),
    'comune': ('città', 'citta', 'comune', 'paese'),
    'cap': ('cap',),
    'prov': ('provincia', 'prov', 'sigla'),
    'regione': ('regione',),
    'descr': ('descrizione', 'descr'),
    'descr_premium': ('descrizione premium',),
    'lat': ('lat', 'latitudine'),
    'lon': ('lng', 'lon', 'longitudine'),
    'premium': ('premium',),
    'premium_dal': ('premium_dal', 'premium dal'),
    'consigliato': ('consigliato daop', 'consigliato'),
    'evidenza': ('in evidenza', 'evidenza', 'vetrina'),
    'gratuito': ('gratuito', 'gratis'),
    'passaporto': ('passaportoesploratore', 'passaporto esploratore'),
    'passaporto_codice': ('codicepassaporto', 'codice passaporto'),
    'passaporto_demo': ('passaportodemo', 'passaporto demo'),
    'circuito': ('circuitonome', 'circuito'),
    'orari': ('orari', 'orario', 'apertura'),
    'prezzo': ('prezzo', 'costo', 'ingresso'),
    'sito': ('website', 'sito', 'sito web', 'link'),
    'tel': ('telefono', 'tel'),
    'email': ('email', 'mail'),
    'foto1': ('foto_1', 'foto 1', 'foto'),
    'foto2': ('foto_2', 'foto 2'),
    'foto3': ('foto_3', 'foto 3'),
    'foto4': ('foto_4', 'foto 4'),
    'foto5': ('foto_5', 'foto 5'),
    'eta_min': ('eta_min', 'età min', 'eta min'),
    'eta_max': ('eta_max', 'età max', 'eta max'),
    # Dal 02/09/2026, in fondo al foglio. `place_id` non si legge qui: e' un
    # dato per riprendere la foto, non da stampare.
    'foto_autore': ('fotoautore', 'foto autore', 'autore foto'),
}


def _norm_head(s):
    return re.sub(r"\s+", " ", (s or '').strip().lower())


def si(v):
    return str(v or '').strip().lower() in ('si', 'sì', 'x', 'true', '1', 'vero')


# ── Il credito della foto ────────────────────────────────────────────────────
#
# Le foto dei luoghi vengono da Google Places, e i termini chiedono due cose:
# non conservarle (noi le ri-ospitiamo: e' il PASSO 3 del TODO, aperto) e
# **citare l'autore accanto alla foto**. Questa e' la seconda, e non ha zone
# grigie: vale comunque, dovunque la foto sia ospitata.
#
# La colonna `FotoAutore` contiene HTML SCRITTO DA GOOGLE, per esempio:
#   <a href="https://maps.google.com/maps/contrib/1034.../">Mario Rossi</a>
# Metterlo in pagina cosi' com'e' vorrebbe dire far scrivere HTML nel sito a
# una terza parte, dentro una stringa che passa per un foglio Google che
# scrivono in due persone. Quindi NON si stampa: si smonta, si tiene solo cio'
# che serve (nome e link), e il tag lo scriviamo noi.
#
# Il link si conserva quando c'e' - Google chiede che l'attribuzione resti
# cliccabile - ma solo verso Google: un href verso qualsiasi altro host e'
# un dato che non ci aspettiamo, e in quel caso resta il solo nome.
_RE_A = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                   re.I | re.S)
_HOST_OK = re.compile(r'^(?:[a-z0-9-]+\.)*google\.com$', re.I)


def credito_foto(grezzo):
    """Da HTML di Google a (nome, link) ripuliti. Senza nome torna ('', '').

    Il nome e' l'unica cosa obbligatoria: se il link non e' di Google si cita
    l'autore e basta, perche' non citarlo affatto e' l'unico esito sbagliato.
    """
    grezzo = (grezzo or '').strip()
    if not grezzo:
        return '', ''
    m = _RE_A.search(grezzo)
    if m:
        href, testo = m.group(1).strip(), m.group(2)
    else:
        # Capita che la colonna contenga il solo nome (riempita a mano, o un
        # domani in cui Google cambia formato): non e' un errore.
        href, testo = '', grezzo
    nome = html.unescape(re.sub(r'<[^>]+>', '', testo)).strip()
    nome = re.sub(r'\s+', ' ', nome)
    if not nome:
        return '', ''
    link = ''
    if href:
        href = html.unescape(href)
        try:
            u = urllib.parse.urlparse(href)
        except ValueError:
            u = None
        if u and u.scheme in ('http', 'https') and _HOST_OK.match(u.hostname or ''):
            link = href
    return nome, link


def html_credito_foto(grezzo):
    """Il paragrafo da mettere SOTTO la foto, o '' se l'autore non lo sappiamo.

    Vuoto e' il caso normale sulle 712 righe vecchie: la foto c'e' ma l'autore
    l'avevamo scartato, e il PASSO 3 del TODO decide se ricomprarlo. Meglio
    niente che un "autore sconosciuto" scritto sotto ogni foto del sito.
    """
    nome, link = credito_foto(grezzo)
    if not nome:
        return ''
    chi = (f'<a href="{G.esc(link)}" target="_blank" rel="noopener nofollow">'
           f'{G.esc(nome)}</a>') if link else G.esc(nome)
    return f'<p class="lg-credito">Foto: {chi} · Google Maps</p>'


# ── La tassonomia ────────────────────────────────────────────────────────────
#
# Le categorie del foglio sono gerarchiche e scritte col separatore "›":
# "Sport › Arti marziali", "Cultura & Istruzione › Biblioteche". Il primo
# livello regge il filtro e il colore, il secondo si scrive in riga - ed e'
# quello che dice davvero cos'e' il posto ("Arti marziali" vale piu' di "Sport").
#
# NON si tiene un elenco fisso di categorie: il foglio ne aggiungera' altre e un
# elenco scritto a mano resterebbe indietro senza che nessuno se ne accorga.
# Colori e icone hanno un ripiego deterministico per le sconosciute, cosi' una
# categoria nuova esce colorata e distinta invece che grigia.
SEP_CAT = '›'

COLORI_NOTI = {
    'sport': ('#e8954a', 'rgba(232,149,74,0.15)', '#a75b15'),
    'cultura-istruzione': ('#6c63a6', 'rgba(108,99,166,0.14)', '#5c5493'),
    'fattorie-didattiche': ('#5c9a4a', 'rgba(92,154,74,0.14)', '#487a3a'),
    'acqua-mare': ('#3d8fc4', 'rgba(61,143,196,0.14)', '#2f7099'),
    'divertimento-avventura': ('#c9a227', 'rgba(201,162,39,0.16)', '#846a1a'),
    'servizi-per-bambini-famiglie': ('#6ba5a8', 'rgba(107,165,168,0.16)', '#467477'),
    'natura-aria-aperta': ('#188663', 'rgba(24,134,99,0.14)', '#146c51'),
    'mangiare': ('#c2704f', 'rgba(194,112,79,0.15)', '#96543a'),
    'altro': ('#7e8c99', 'rgba(126,140,153,0.16)', '#606d7a'),
}
# Ripiego per le categorie che il foglio aggiungera' dopo di noi. Non e' casuale:
# si sceglie con la somma dei caratteri dello slug, quindi la stessa categoria
# prende sempre lo stesso colore e il CSS non balla da una run all'altra.
PALETTE = [
    ('#a9793f', 'rgba(169,121,63,0.15)', '#8a6132'),
    ('#8a7f9b', 'rgba(138,127,155,0.16)', '#6f6580'),
    ('#4a90b9', 'rgba(74,144,185,0.14)', '#397293'),
    ('#b06a86', 'rgba(176,106,134,0.15)', '#8d5069'),
    ('#7d9a3c', 'rgba(125,154,60,0.15)', '#5f7630'),
]

ICONE_NOTE = {
    'sport': '⚽', 'cultura-istruzione': '📚', 'fattorie-didattiche': '🐮',
    'acqua-mare': '🌊', 'divertimento-avventura': '🎡',
    'servizi-per-bambini-famiglie': '👶', 'natura-aria-aperta': '🌳',
    'mangiare': '🍽️',
}


def spacca_categoria(testo):
    """(primo livello, secondo livello) dalla stringa del foglio."""
    t = (testo or '').replace('>', SEP_CAT)
    pezzi = [p.strip() for p in t.split(SEP_CAT) if p.strip()]
    if not pezzi:
        return ('Altro', '')
    return (pezzi[0], pezzi[1] if len(pezzi) > 1 else '')


def colore_cat(slug):
    if slug in COLORI_NOTI:
        return COLORI_NOTI[slug]
    return PALETTE[sum(map(ord, slug)) % len(PALETTE)]


def etichetta_filtro(primo):
    """Il nome corto della categoria, per la tendina.

    Chrome dimensiona una <select> sull'opzione PIU' LUNGA, non su quella
    scelta: con "Servizi per Bambini & Famiglie" dentro, la tendina da sola
    chiedeva mezzo schermo del telefono. In riga il nome resta per esteso -
    li' descrive un posto e ci sta."""
    t = (primo or '').split(' & ')[0].split(' per ')[0].strip()
    if len(t) > 14 and ' ' in t:
        t = t.split()[0]
    return t or 'Altro'


# ── "Se piove" ───────────────────────────────────────────────────────────────
#
# Non c'e' una colonna: sta dentro Tag, che e' una stringa a trattini scritta a
# mano ("biblioteca-...-al-coperto-tutto-anno", "fattoria-...-parcheggio-all-aperto").
# L'ordine dei controlli conta: "all-aperto" contiene "aperto" e
# "parcheggio-coperto" contiene "coperto", quindi si guarda prima la forma piu'
# lunga e piu' specifica.
RIPARO_DA_CAT = {
    'cultura-istruzione': 'chiuso', 'servizi-per-bambini-famiglie': 'chiuso',
    'fattorie-didattiche': 'aperto', 'natura-aria-aperta': 'aperto',
}


def riparo_da_tag(tag, primo_slug):
    t = (tag or '').lower()
    if 'meteo-pioggia' in t or 'al-coperto' in t:
        return 'chiuso'
    if 'all-aperto' in t:
        return 'aperto'
    if 'coperto' in t:
        return 'chiuso'
    if re.search(r'(^|-)aperto(-|$)', t):
        return 'aperto'
    # Senza indizi si va per categoria, e nel dubbio "misto": un misto compare
    # in tutte e due le risposte del filtro, quindi sbagliare qui nasconde meno
    # di quanto nasconderebbe scegliere.
    return RIPARO_DA_CAT.get(primo_slug, 'misto')


# Le poche etichette pratiche che vale la pena tirare fuori dal campo Tag. Il
# Tag e' lungo e ripete quello che Servizi dice meglio: qui si tiene solo quello
# che Servizi NON dice - il parcheggio, la carrozzina, i cani, la prenotazione.
# Cioe' le cose che fanno decidere se partire.
ETICHETTE_TAG = {
    'meteo-pioggia': 'Va bene se piove',
    'carrozzina': 'Passa la carrozzina',
    'disabili': 'Accessibile',
    'parcheggio': 'Parcheggio',
    'cani-ammessi': 'Cani ammessi',
    'prenotazione': 'Su prenotazione',
    'senza-glutine': 'Senza glutine',
    'compleanno': 'Feste di compleanno',
    'centri-estivi': 'Centri estivi',
    'picnic': 'Picnic',
}


def servizi_pratici(tag):
    t = (tag or '').lower()
    return [testo for chiave, testo in ETICHETTE_TAG.items() if chiave in t]


def _key(nome, comune):
    """Chiave di fusione fra catalogo e agenda.

    Sta tutta nel normalizzare: nel foglio eventi lo stesso posto si scrive
    "P.zza Garibaldi", "Piazza Garibaldi" e "piazza garibaldi" nella stessa
    settimana, e senza questo passaggio uscirebbero tre righe."""
    t = (nome or '').lower()
    t = t.replace("p.zza", "piazza").replace("p.za", "piazza").replace("pza ", "piazza ")
    t = t.replace("v.le", "viale").replace("c.so", "corso").replace("s.", "san ")
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    # Le sigle puntate si riattaccano: "A.S.D. Karate" e "ASD Karate" sono lo
    # stesso posto, e senza questo passaggio sono due righe.
    t = re.sub(r"\b(?:[a-z] )+[a-z]\b", lambda m: m.group(0).replace(" ", ""), t)
    return f"{t}|{G.slugify(comune or '')}"


def _alfabetico(s):
    """La chiave con cui si ordina, cioe' l'ordine alfabetico come lo legge una
    persona: senza accenti e senza punteggiatura, non con i trattini di slugify.

    Non e' un dettaglio da niente: slugify trasforma "A.S.D." in "a-s-d" e il
    trattino viene prima di ogni lettera, quindi l'elenco usciva in un ordine
    che a chi legge sembra sbagliato. E l'ordine alfabetico qui e' una promessa
    scritta in #come-ordiniamo, non una preferenza."""
    t = (s or '').lower()
    for a, b in (('à', 'a'), ('á', 'a'), ('è', 'e'), ('é', 'e'), ('ì', 'i'),
                 ('í', 'i'), ('ò', 'o'), ('ó', 'o'), ('ù', 'u'), ('ú', 'u')):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9 ]", "", t)


# ── I nomi ───────────────────────────────────────────────────────────────────
#
# Nel foglio 126 nomi su 823 sono scritti TUTTI IN MAIUSCOLO, e in elenco
# stonano: "SCUOLA PARITARIA SACRO CUORE" sopra "Studio Danza My Balance" sembra
# un errore o un grido. Si normalizzano quelli, e SOLO quelli - un nome che ha
# gia' una minuscola e' scritto come lo vuole chi lo porta ("ToBE Together",
# "iPlay"), e riscriverlo sarebbe peggio del disordine.
#
# Non si sceglie il minuscolo (sui nomi propri e' sbagliato) e non si sceglie il
# maiuscolo (urla, e a Ctrl+F non cambia niente): si sceglie la maiuscola per
# parola, che e' come sono gia' scritti gli altri 697.

# Parole che restano minuscole quando non aprono il nome.
MINUSCOLE = {
    'di', 'da', 'de', 'del', 'dello', 'della', 'dei', 'degli', 'delle', 'dal',
    'dalla', 'dallo', 'dai', 'e', 'ed', 'il', 'lo', 'la', 'i', 'gli', 'le',
    'un', 'una', 'in', 'con', 'su', 'per', 'tra', 'fra', 'a', 'al', 'allo',
    'alla', 'ai', 'agli', 'alle', 'sul', 'sulla', 'che', 'non', 'nel', 'nella',
    'ad', 'od', 'o',
}
# Sigle che restano come sono. Il controllo automatico (parola corta senza
# vocali) prende SSD, MTB, SMS ma non ASD o SPA, che una vocale ce l'hanno.
ACRONIMI = {
    'ASD', 'SSD', 'ARL', 'SRL', 'SNC', 'SAS', 'SPA', 'MTB', 'GAG', 'SOMS',
    'SMS', 'CISA', 'FC', 'AC', 'US', 'AS', 'CAI', 'AVIS', 'CRI', 'GS', 'PGS',
    'CSI', 'UISP', 'ACLI', 'ARCI', 'ONLUS', 'APS', 'ODV', 'ANFFAS', 'AICS',
    'CONI', 'ANA', 'AIDO', 'TV', 'DJ', 'BB', 'SC', 'AC.', 'PMI', 'ITIS', 'IIS',
    'IC', 'IPSIA', 'CFP', 'CPIA', 'ATL', 'PRO',
}
# Numeri romani VERI, non "una parola fatta di I V X L C": con la forma larga
# anche "IL" passava per numero romano e restava maiuscolo in mezzo ai nomi.
ROMANI = re.compile(r'^(?=[IVXLCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})'
                    r'(IX|IV|V?I{0,3})[°ªº]?$')
# Forme elise che nel foglio hanno perso l'apostrofo ("SCUOLA DELL INFANZIA").
# Sono tutte parole che in italiano NON esistono da sole, quindi riattaccarle
# non puo' essere sbagliato.
ELISE = {'l', 'd', 'c', 'dell', 'all', 'nell', 'dall', 'sull', 'quell', 'un',
         'sant', 'grand', 'bell', 'anch'}


def _e_sigla(p):
    """Sigle da lasciare come sono: quelle elencate, quelle puntate (A.S.D.) e
    quelle corte senza vocali (SSD, MTB, SMS)."""
    if not p:
        return False
    nudo = p.strip('.,;:()«»"\'')
    return bool(nudo.upper() in ACRONIMI or '.' in p[:-1]
                or (2 <= len(nudo) <= 5 and not re.search(r'[AEIOUaeiou]', nudo)))


def _parola(p, prima):
    if not p:
        return p
    nudo = p.strip('.,;:()«»"\'')
    # Le parole comuni si controllano PRIMA dei numeri romani, perche' in
    # numeri romani "DI" vale 501 e "MI" 1001: senza questa riga usciva
    # "Il Giardino DI Peter Pan".
    if not prima and p.lower() in MINUSCOLE:
        return p.lower()
    if _e_sigla(p) or ROMANI.match(nudo):
        return p
    b = p.lower()
    if not prima and b in MINUSCOLE:
        return b
    # L'apostrofo gia' presente: "DELL'INFANZIA" e' un articolo eliso attaccato a
    # un nome, quindi vanno trattate come due parole - se no usciva
    # "Dell'infanzia", con la maiuscola sull'articolo e la minuscola sul nome.
    if "'" in b:
        testa, _, coda = b.partition("'")
        if testa in ELISE and coda:
            return (testa.capitalize() if prima else testa) + "'" + _alza(coda)
    # Il trattino: si alza solo la prima parte ("Micro-nidi", non "Micro-Nidi").
    return _alza(b)


def _alza(b):
    """Maiuscola alla prima LETTERA, non al primo carattere: un nome che comincia
    con un trattino o una virgoletta resterebbe tutto minuscolo."""
    for i, c in enumerate(b):
        if c.isalpha():
            return b[:i] + c.upper() + b[i + 1:]
    return b


def pulisci_nome(nome):
    """Spazi normalizzati sempre; maiuscole sistemate solo se il nome grida."""
    t = re.sub(r'\s+', ' ', (nome or '').strip())
    if not t or re.search(r'[a-zàèéìòùáíóú]', t):
        return t
    parole = t.split(' ')
    fuori, apre = [], True
    i = 0
    while i < len(parole):
        p = parole[i]
        # Apostrofo perduto: "DELL INFANZIA" -> "dell'Infanzia", "L ISOLA" ->
        # "L'Isola". "C E" diventa "c'è": e' l'unica lettura sensata, "c" da
        # sola non e' una parola e "c'e" senza accento resterebbe sbagliato.
        if p.lower() in ELISE and i + 1 < len(parole):
            testa = p.lower()
            coda = parole[i + 1]
            if testa == 'c' and coda.lower() == 'e':
                fuori.append("c'è")
                i += 2
                apre = False
                continue
            testa = testa.capitalize() if apre else testa
            fuori.append(testa + "'" + _parola(coda, True))
            i += 2
            apre = False
            continue
        fuori.append(_parola(p, apre))
        # Dopo una sigla di forma giuridica il nome VERO ricomincia, quindi
        # l'articolo che segue si tratta come primo: "ASD MTB I Cinghiali" e non
        # "ASD MTB i Cinghiali". Vale solo dopo una sigla, cosi' "L'Albero e le
        # Stelle" e "G. e V. Navone" restano com'e' giusto che siano.
        apre = _e_sigla(p)
        i += 1
    return ' '.join(fuori)


def _eta(v, ripiego):
    try:
        return max(0, min(99, int(str(v).strip())))
    except (TypeError, ValueError):
        return ripiego


# ── Sorgente 1: il catalogo ──────────────────────────────────────────────────

def _righe_grezze():
    """Le righe del tab "Luoghi" come dict con le intestazioni del foglio, o
    l'istantanea locale, o niente.

    "O niente" e' un esito normale, non un errore: finche' il tab non esiste la
    pagina si regge sull'agenda. L'istantanea e' salvata con le STESSE chiavi
    del foglio, cosi' i due percorsi passano dallo stesso normalizzatore e non
    c'e' un secondo formato da tenere allineato quando una colonna cambia nome.

    Il secondo valore dice se le righe sono FRESCHE (dal foglio): solo in quel
    caso ha senso riscrivere l'istantanea."""
    base = os.environ.get("LUOGHI_CSV_URL") or DEFAULT_CSV
    sep = '&' if '?' in base else '?'
    url = f"{base}{sep}_cb={int(datetime.datetime.now().timestamp())}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "daop-luoghi-bot", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=30) as r:
            testo = r.read().decode("utf-8", "replace")
        lettore = list(csv.reader(io.StringIO(testo)))
        head = [_norm_head(c) for c in lettore[0]] if lettore else []
        if any(h in COLONNE['nome'] for h in head) and any(h in COLONNE['categoria'] for h in head):
            righe = [dict(zip(head, r)) for r in lettore[1:] if any(c.strip() for c in r)]
            print(f"[genera_luoghi] {len(righe)} righe lette dal tab Luoghi")
            return righe, True
        # Il tab non c'e': gviz risponde comunque, col primo foglio o con una
        # pagina d'errore. Meglio accorgersene qui che pubblicare un elenco di
        # eventi travestito da elenco di luoghi.
        print("[genera_luoghi] il tab Luoghi non risponde con le colonne attese")
    except Exception as e:
        print(f"[genera_luoghi] tab Luoghi non raggiungibile ({e})")

    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, encoding="utf-8") as fh:
            snap = json.load(fh)
        print(f"[genera_luoghi] uso l'istantanea {os.path.basename(JSON_PATH)}: {len(snap)} righe")
        return [{_norm_head(k): v for k, v in r.items()} for r in snap], False
    print("[genera_luoghi] nessun catalogo: la pagina si regge sull'agenda")
    return [], False


def leggi_catalogo():
    righe, fresco = _righe_grezze()
    fuori = []
    for r in righe:
        d = {}
        for campo, nomi in COLONNE.items():
            d[campo] = ''
            for n in nomi:
                if (r.get(n) or '').strip():
                    d[campo] = r[n].strip()
                    break
        if not d['nome'] or not d['comune']:
            continue
        primo, secondo = spacca_categoria(d['categoria'])
        slug_cat = G.slugify(primo) or 'altro'
        premium = si(d['premium'])
        fuori.append({
            'nome': pulisci_nome(d['nome']),
            'comune': re.sub(r'\s+', ' ', d['comune'].strip()),
            'prov': d['prov'].upper(),
            'regione': d['regione'], 'cap': d['cap'],
            'cat': slug_cat, 'cat_nome': primo, 'cat_sotto': secondo,
            'cat_filtro': etichetta_filtro(primo),
            'icona': d['icona'] or ICONE_NOTE.get(slug_cat, '📍'),
            'colore': colore_cat(slug_cat),
            'servizi': [s.strip() for s in d['servizi'].split(',') if s.strip()],
            'pratici': servizi_pratici(d['tag']),
            'riparo': riparo_da_tag(d['tag'], slug_cat),
            'indirizzo': d['indirizzo'], 'lat': d['lat'], 'lon': d['lon'],
            'descr': d['descr'], 'descr_premium': d['descr_premium'],
            'orari': d['orari'], 'prezzo': d['prezzo'], 'gratuito': si(d['gratuito']),
            'sito': d['sito'], 'tel': d['tel'], 'email': d['email'],
            'foto': [d[f'foto{i}'] for i in range(1, 6) if d[f'foto{i}']],
            # L'attribuzione riguarda la SOLA Foto_1: e' quella che esce da
            # Places (`photos[0]`), le altre le abbiamo messe noi. Citare
            # l'autore sbagliato sarebbe peggio che non citarne nessuno.
            'foto_autore': d['foto_autore'],
            'eta_min': _eta(d['eta_min'], 0), 'eta_max': _eta(d['eta_max'], 99),
            'premium': premium, 'premium_dal': d['premium_dal'],
            'consigliato': si(d['consigliato']),
            # La vetrina la decide una COLONNA del foglio, non una regola
            # inventata qui. Per un giorno e' stata `premium and consigliato`,
            # e il risultato e' che il blocco non compariva mai: le quattro
            # schede a pagamento hanno tutte "Consigliato DAOP = no", perche'
            # sono due giudizi diversi - uno lo dà il cliente, l'altro lo diamo
            # noi - ed era stato tenuto separato apposta tre righe piu' su.
            # Una condizione che spegne in silenzio uno spazio venduto e' un
            # difetto, non una cautela. Serve comunque il premium: la posizione
            # in cima si compra, e chi non l'ha comprata non ci finisce.
            'evidenza': premium and si(d['evidenza']),
            'codice': d['codice'],
            'n_eventi': 0, 'ultimo': '', 'prossimi': [], 'fonte': 'catalogo',
            '_grezzo': r if fresco else None,
        })
    return fuori


def solo_province_nostre(catalogo):
    """Fuori da AL, AT e CN la riga non si pubblica.

    Il foglio raccoglie anche posti oltre le tre province - l'Acquario di
    Genova, un parco a Voghera, qualche gita in Valle d'Aosta - e per un po'
    sono stati pubblicati apposta, con l'idea che "gita da Alessandria" li
    vuole. La pagina pero' e' l'elenco di un territorio dichiarato, lo stesso
    dell'agenda: una tendina che offre "Prov. GE" accanto a "Prov. AL" promette
    una copertura della Liguria che non c'e' (quattordici righe contro
    quattrocentosettantotto), e un elenco che dice di essere di Alessandria,
    Asti e Cuneo non si smentisce da solo alla prima riga.

    Si scartano qui e non nel foglio: la colonna resta, le righe restano, e
    riaprire una provincia domani vuol dire aggiungere una sigla a
    PROVINCE_PUBBLICATE - che e' la stessa da cui passa l'agenda, cosi' le due
    superfici non possono divergere in silenzio.

    L'istantanea NON si pota: `salva_istantanea()` riceve il catalogo intero,
    perche' e' lo specchio del foglio e non della pagina. Sara' il filtro a
    rifare il taglio anche quando si gira offline."""
    dentro = [l for l in catalogo if l['prov'] in G.PROVINCE_PUBBLICATE]
    fuori = collections.Counter(l['prov'] or '—' for l in catalogo
                                if l['prov'] not in G.PROVINCE_PUBBLICATE)
    if fuori:
        dettaglio = ", ".join(f"{p} {n}" for p, n in fuori.most_common())
        print(f"[genera_luoghi] {sum(fuori.values())} luoghi fuori da "
              f"{'/'.join(G.PROVINCE_PUBBLICATE)} non pubblicati ({dettaglio})")
    return dentro


# ── Sorgente 2: l'agenda ─────────────────────────────────────────────────────

def leggi_agenda():
    """I luoghi che l'agenda conosce, con il conto degli eventi e i prossimi."""
    oggi = datetime.date.today()
    luoghi = {}

    def tocca(nome, comune, prov, **extra):
        if not nome or NON_LUOGHI.match(nome.strip()) or FRAZIONE.search(nome):
            return None
        if G.slugify(nome) == G.slugify(comune or ''):
            return None
        k = _key(nome, comune)
        d = luoghi.setdefault(k, {
            'nome': nome.strip(), 'comune': (comune or '').strip(),
            'prov': (prov or '').strip().upper(),
            'indirizzo': '', 'lat': '', 'lon': '',
            'n_eventi': 0, 'ultimo': '', 'prossimi': [],
        })
        for campo, val in extra.items():
            if val and not d.get(campo):
                d[campo] = val
        return d

    if os.path.exists(STORICO_JSON):
        with open(STORICO_JSON, encoding="utf-8") as fh:
            storico = json.load(fh)
        for _slug, com in storico.items():
            for _k, ev in com.get('eventi', {}).items():
                d = tocca(ev.get('luogo'), com.get('nome'), com.get('prov'))
                if d is None:
                    continue
                d['n_eventi'] += 1
                if (ev.get('ultima') or '') > d['ultimo']:
                    d['ultimo'] = ev.get('ultima') or ''

    if os.path.exists(EVENTI_JSON):
        with open(EVENTI_JSON, encoding="utf-8") as fh:
            eventi = json.load(fh)
        for e in eventi:
            d = tocca(e.get('luogo'), e.get('citta'), e.get('prov'),
                      indirizzo=e.get('indirizzo', ''),
                      lat=e.get('lat', ''), lon=e.get('lon', ''))
            if d is None:
                continue
            if e.get('d_end', '') >= oggi.isoformat():
                d['prossimi'].append({
                    'nome': e.get('nome', ''), 'd': e.get('d_start', ''),
                    'href': f"/eventi.html#{e['anchor']}" if e.get('anchor') else "/eventi.html",
                })
            if (e.get('d_end') or '') > d['ultimo']:
                d['ultimo'] = e.get('d_end') or ''

    for d in luoghi.values():
        d['prossimi'].sort(key=lambda p: p['d'])
        # Il conteggio non deve mai essere piu' piccolo di quello che la riga
        # elenca sotto, se no si legge "1 evento" con tre link in fila.
        d['n_eventi'] = max(d['n_eventi'], len(d['prossimi']))
    return luoghi


def unisci(catalogo, agenda):
    """Catalogo + agenda in un elenco solo, ordinato per provincia, comune, nome."""
    fuori = {_key(l['nome'], l['comune']): l for l in catalogo}
    innestati = 0

    for k, a in agenda.items():
        if k in fuori:
            d = fuori[k]
            d['n_eventi'], d['ultimo'], d['prossimi'] = a['n_eventi'], a['ultimo'], a['prossimi']
            for campo in ('indirizzo', 'lat', 'lon'):
                if not d.get(campo):
                    d[campo] = a.get(campo, '')
            innestati += 1
            continue
        # Il catalogo, quando c'e', E' l'elenco: i posti dedotti dall'agenda non
        # entrano come righe proprie, restano solo ad arricchire le righe del
        # catalogo con "cosa c'e' in programma qui". Con 800 luoghi scelti a
        # mano, aggiungerne 170 dedotti da "qui e' passata una festa" li
        # diluirebbe - e "dove si fanno le cose" ha gia' una pagina migliore,
        # che e' eventi.html. Riempiono la pagina soltanto finche' un catalogo
        # non c'e' per niente, cioe' perche' non nasca vuota.
        if catalogo:
            continue
        if a['n_eventi'] < MIN_EVENTI_AGENDA and not a['prossimi']:
            continue
        slug_cat = indovina_categoria(a['nome'])
        fuori[k] = dict(
            a, cat=slug_cat, cat_nome='Luogo', cat_sotto='',
            cat_filtro=etichetta_filtro(slug_cat.split('-')[0].capitalize()),
            icona=ICONE_NOTE.get(slug_cat, '📍'), colore=colore_cat(slug_cat),
            servizi=[], pratici=[],
            riparo=RIPARO_DA_CAT.get(slug_cat, 'misto'),
            regione='', cap='', descr='', descr_premium='',
            orari='', prezzo='', gratuito=False, sito='', tel='', email='',
            foto=[], foto_autore='', eta_min=0, eta_max=99, premium=False, premium_dal='',
            consigliato=False, evidenza=False, codice='', fonte='agenda', _grezzo=None)

    elenco = [d for d in fuori.values() if d['nome'] and d['comune']]

    # Un comune scritto in due modi e' due comuni. Nel foglio convivono
    # "Montegrosso d'Asti" e "Montegrosso D'Asti": in pagina uscivano due gruppi
    # separati, e - peggio - due <h2> con lo STESSO id (c-montegrosso-d-asti),
    # che e' HTML non valido e manda l'ancora sul primo dei due. Si tiene la
    # grafia piu' usata; a pari merito la prima in ordine alfabetico, cosi' la
    # scelta non cambia da una run all'altra.
    grafie = collections.defaultdict(collections.Counter)
    for d in elenco:
        grafie[(d['prov'], G.slugify(d['comune']))][d['comune']] += 1
    unificati = 0
    for d in elenco:
        chiave = (d['prov'], G.slugify(d['comune']))
        if len(grafie[chiave]) > 1:
            buona = sorted(grafie[chiave].items(), key=lambda x: (-x[1], x[0]))[0][0]
            if d['comune'] != buona:
                unificati += 1
            d['comune'] = buona
    if unificati:
        print(f"[genera_luoghi] {unificati} righe avevano il comune scritto in un'altra grafia")

    for d in elenco:
        d['slug'] = 'lg-' + G.slugify(f"{d['nome']} {d['comune']}")[:70]
    # Slug duplicati: non dovrebbero esistere dopo _key(), ma un'ancora ripetuta
    # rompe i link in silenzio.
    visti = collections.Counter()
    for d in elenco:
        visti[d['slug']] += 1
        if visti[d['slug']] > 1:
            d['slug'] = f"{d['slug']}-{visti[d['slug']]}"
    elenco.sort(key=lambda d: (d['prov'], _alfabetico(d['comune']), _alfabetico(d['nome'])))
    if innestati:
        print(f"[genera_luoghi] {innestati} luoghi del catalogo hanno eventi in agenda")
    return elenco


# ── CSS e JS ─────────────────────────────────────────────────────────────────

LUOGHI_CSS = """
/* Il padding in alto NON e' decorativo: e' l'unica pagina generata che non usa
   .ev-wrap, e .ev-wrap--hero mette 44px fra la fascia scura e il primo elemento.
   Senza, il corpo partiva incollato al bordo dell'hero (misurato: 329px la fine
   dell'hero, 329px l'inizio del primo paragrafo) e la fascia sembrava tagliata. */
.lg-wrap{max-width:940px;margin:0 auto;padding:40px 20px 40px}
@media(max-width:600px){.lg-wrap{padding:30px 20px 32px}}

/* L'hero e il corpo devono cominciare dalla STESSA x. Il guscio da' all'hero un
   inner da 820px (`.ev-hero .page-hero-inner`) e qui la colonna dell'elenco e'
   larga 900: l'H1 partiva 40px piu' a destra del primo comune, ed era il difetto
   che si vedeva senza saperlo nominare. Si allarga l'inner solo su questa pagina
   - toccare la regola nel guscio sposterebbe l'hero di 290 file. Sul telefono
   sono allineati dal padding: 20px l'hero, 20px .lg-wrap. */
.lg-hero .page-hero-inner{max-width:900px}
/* La frase che dice di cosa e' fatto l'elenco sta DENTRO l'hero, sotto
   l'occhiello d'oro: e' la stessa impaginazione dell'hero di eventi.html (titolo,
   riga di contesto, paragrafo). In fondo alla fascia, da sola sul crema, era un
   paragrafo grigio senza niente che lo tenesse su - e larga 900px passava i 100
   caratteri per riga, il doppio della misura usata in tutto il resto del sito.
   `.page-hero p` la centrerebbe (max-width 520 + margin auto): serve margin:0,
   perche' questo hero e' allineato a sinistra. */
.lg-hero .lg-intro{max-width:60ch;margin:12px 0 0;font-size:1.02rem;line-height:1.62;
  color:rgba(255,255,255,.72)}
/* Chrome dimensiona una <select> sull'opzione PIU' LUNGA: con dentro
   "Castelceriolo (Alessandria)" la tendina dei comuni da sola chiedeva mezza
   barra. Si limita e si taglia con i puntini - il valore scelto resta
   leggibile, e l'elenco aperto lo disegna il browser alla sua larghezza (sul
   telefono e' un pannello a tutto schermo). */
/* I filtri NON si allungano per riempire la riga. Con il flex-grow che eredita
   dall'agenda, l'ultimo rimasto da solo sulla seconda riga si stirava a tutta
   larghezza: "Età" diventava una pillola da 380px per una parola di tre lettere,
   e sembrava un campo di ricerca invece di un menu. Larghezza naturale, e la
   riga finisce dove finiscono i controlli. */
#lg-toolbar .ev-select{flex:0 1 auto}

/* Il campo comune e' un <input>, non una <select>: veste la stessa pillola ma
   gli servono le cose che .ev-select da' per scontate su un menu. */
input.ev-select.is-comune{max-width:150px;text-overflow:ellipsis;cursor:text;
  -webkit-appearance:none;appearance:none}
input.ev-select.is-comune::placeholder{color:var(--text-mid);opacity:1;font-weight:600}
input.ev-select.is-comune.is-on::placeholder{color:rgba(255,255,255,.75)}
/* La ✕ per svuotare e la freccetta dei suggerimenti le disegna il browser in
   scuro: sulla pillola attiva, che e' blu notte, sparivano. */
input.ev-select.is-comune.is-on::-webkit-search-cancel-button,
input.ev-select.is-comune.is-on::-webkit-calendar-picker-indicator{filter:invert(1) brightness(1.8)}
@media(max-width:600px){input.ev-select.is-comune{max-width:126px}}
.lg-count{font-size:0.8rem;font-weight:600;color:var(--text-light);margin:10px 0 0;min-height:1em}
.lg-reset{font-family:'DM Sans',sans-serif;font-size:0.8rem;font-weight:600;color:var(--text-mid);
  background:none;border:0;border-bottom:1px solid rgba(45,74,92,0.25);padding:0 0 1px;cursor:pointer}
.lg-reset:hover{color:var(--orange-ink,#a05714);border-color:currentColor}

/* padding:0 NON e' di troppo: il foglio di stile del sito ha una regola
   `section{padding:100px 24px}` (72px 20px sotto i 600px) pensata per le fasce
   della home, e il gruppo comune e' un <section> perche' ha un suo <h2>. Il
   risultato erano 72px di vuoto sopra e 72 sotto ogni comune: senza filtri non
   si notavano, perche' le sezioni sono alte; filtrando restano una o due righe
   e quei 144px diventano il buco che si vede fra un comune e l'altro. */
.lg-grp{margin:26px 0 0;padding:0}
.lg-grp-h{display:flex;align-items:baseline;gap:10px;margin:0 0 6px;padding:0 0 6px;
  border-bottom:1px solid rgba(45,74,92,0.10)}
.lg-grp-h h2{font-family:'Playfair Display',serif;font-size:1.24rem;font-weight:800;
  color:var(--navy);margin:0}
.lg-grp-h span{font-size:0.78rem;font-weight:600;color:var(--text-light)}
.lg-grp-h a{font-size:0.78rem;font-weight:600;color:var(--text-mid);margin-left:auto;white-space:nowrap}

/* ── La riga ──────────────────────────────────────────────────────────────
   E' un <details>, non una riga con del JS sopra: senza JavaScript si apre lo
   stesso, la tastiera la governa da sola e Ctrl+F la trova anche chiusa.
   content-visibility come nell'agenda - a centinaia di righe e' la voce piu'
   pesante della pagina, e il testo resta comunque nel DOM. */
.lg-row{content-visibility:auto;contain-intrinsic-size:auto 74px;
  border-left:3px solid var(--cat-color,#7e8c99);border-bottom:1px solid rgba(45,74,92,0.07);
  background:white;transition:background .18s ease}
.lg-row:hover{background:var(--cat-tint,rgba(45,74,92,0.04))}
/* Aperta la riga prende il crema neutro, non la tinta di categoria: quella e'
   pensata per una pillola da 36px, e stesa su mezzo schermo di scheda faceva
   un fondo lilla su cui il testo si legge peggio. Il colore della categoria
   resta dov'e' leggibile - il bordo a sinistra e il quadratino dell'icona. */
.lg-row[open]{background:var(--cream,#fdf8f0)}
.lg-row > summary{display:flex;align-items:center;gap:12px;padding:13px 14px;cursor:pointer;
  list-style:none;min-height:48px}
.lg-row > summary::-webkit-details-marker{display:none}
.lg-row > summary::marker{content:''}
.lg-row > summary:focus-visible{outline:2px solid var(--orange);outline-offset:-2px}
.lg-ico{flex:0 0 auto;width:36px;height:36px;border-radius:10px;display:flex;
  align-items:center;justify-content:center;font-size:1.15rem;line-height:1;
  background:var(--cat-tint,rgba(45,74,92,0.08))}
.lg-txt{min-width:0;flex:1 1 auto}
.lg-nome{display:block;font-size:0.99rem;font-weight:700;color:var(--navy);line-height:1.3}
.lg-meta{display:block;font-size:0.79rem;color:var(--text-light);margin-top:2px}
/* La categoria si scrive, non solo si colora: un verde e un blu senza etichetta
   sono due colori. Stessa regola delle pagine comune. */
.lg-cat{font-weight:700;color:var(--cat-ink,#606d7a)}
.lg-pills{flex:0 0 auto;display:flex;gap:5px;align-items:center}
/* inline-block e NON inline-flex: in un contenitore flex lo spazio in testa a
   un elemento figlio viene mangiato, e "2 eventi in programma" usciva
   "2EVENTI IN PROGRAMMA".
   Lo spazio sta dentro l'<i> apposta - cosi' se ne va insieme alla parola
   quando sul telefono resta il solo numero - ma serve un contesto in cui
   contenga davvero. */
.lg-tag{font-size:0.68rem;font-weight:700;letter-spacing:0.03em;text-transform:uppercase;
  border-radius:100px;padding:4px 9px;white-space:nowrap;display:inline-block;
  line-height:1.5;text-align:center}
.lg-tag i{font-style:normal}
.lg-tag.is-ev{background:rgba(24,134,99,0.12);color:#146c51}
.lg-tag.is-free{background:rgba(24,134,99,0.10);color:#167859}
.lg-tag.is-daop{background:rgba(232,149,74,0.16);color:#a75b15}
.lg-tag.is-prem{background:rgba(201,162,39,0.20);color:#846a1a}
.lg-chev{flex:0 0 auto;width:17px;height:17px;fill:none;stroke:var(--text-light);
  stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;transition:transform .18s ease}
.lg-row[open] .lg-chev{transform:rotate(180deg)}
@media(max-width:600px){
  .lg-row > summary{padding:12px 8px;gap:10px}
  .lg-nome{font-size:0.94rem}
  /* Sul telefono resta il segno, non la parola: senza pillole le righe erano
     tutte identiche, con le parole intere tre pillole mangiavano il nome.
     La riga aperta ha spazio e riprende le parole. */
  .lg-tag i{display:none}
  .lg-tag{padding:4px 7px;min-width:24px}
  .lg-pills .lg-tag:nth-child(n+3){display:none}
  .lg-row[open] .lg-tag i{display:inline}
  .lg-row[open] .lg-pills .lg-tag:nth-child(n+3){display:inline-flex}
}

/* ── Il corpo aperto ─────────────────────────────────────────────────────── */
.lg-body{padding:2px 14px 18px 62px;font-size:0.9rem;line-height:1.62;color:var(--text-mid)}
@media(max-width:600px){.lg-body{padding:2px 8px 16px 8px}}
.lg-facts{list-style:none;margin:0 0 12px;padding:0;display:grid;gap:6px}
.lg-facts li{display:flex;gap:8px}
.lg-facts b{font-weight:700;color:var(--text-dark);flex:0 0 auto}
.lg-serv{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 12px;padding:0;list-style:none}
.lg-serv li{font-size:0.78rem;color:var(--text-mid);background:var(--cream);
  border-radius:100px;padding:4px 11px}
.lg-serv li.is-pratico{background:rgba(24,134,99,0.09);color:#146c51;font-weight:600}
.lg-next{margin:12px 0 0;padding:12px 14px;background:var(--cream);border-radius:12px}
.lg-next p{margin:0 0 7px;font-size:0.8rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.04em;color:var(--text-light)}
.lg-next ul{list-style:none;margin:0;padding:0;display:grid;gap:5px}
.lg-next a{color:var(--navy);font-weight:600}
.lg-act{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0 0}
.lg-act a{display:inline-flex;align-items:center;gap:6px;font-size:0.83rem;font-weight:600;
  color:var(--text-mid);background:white;border:1px solid rgba(45,74,92,0.14);
  border-radius:100px;padding:9px 15px;min-height:40px;transition:var(--transition)}
.lg-act a:hover{border-color:var(--orange);color:var(--orange-ink,#a05714)}
.lg-manca{margin:12px 0 0;font-size:0.83rem;color:var(--text-light)}
.lg-manca a{color:var(--text-mid);text-decoration:underline}
/* La foto sta DENTRO la riga chiusa, quindi non viene scaricata finche' non si
   apre: con loading="lazy" il browser non carica le immagini di un sottoalbero
   che non disegna. E' la ragione per cui 800 foto su Supabase non diventano
   800 richieste - lo stesso conto di banda gia' sbagliato una volta con le
   locandine, quando il bucket passo' da 10 a 250 MB al giorno. */
.lg-foto{display:block;width:100%;max-width:360px;height:auto;aspect-ratio:4/3;object-fit:cover;
  border-radius:12px;margin:0 0 12px;background:var(--cream)}
/* Il credito della foto: obbligatorio, quindi si legge, ma e' una didascalia e
   non un contenuto - piccolo, chiaro, attaccato all'immagine. Il margine sopra
   e' NEGATIVO e non si tocca quello di .lg-foto: il credito ce l'ha solo una
   riga su tre (le 712 vecchie non hanno l'autore), e ridurre il margine della
   foto avrebbe stretto la scheda anche a chi il paragrafo non ce l'ha.
   Senza il recupero il nome dell'autore galleggiava a mezza strada fra la foto
   e la descrizione, e non si capiva a quale delle due appartenesse. */
.lg-credito{max-width:360px;margin:-8px 0 12px;font-size:0.72rem;line-height:1.4;
  color:var(--text-light)}
.lg-credito a{color:var(--text-light);text-decoration:underline}
.lg-credito a:hover{color:var(--text-mid)}
.lg-galleria{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}
.lg-galleria img{width:104px;height:78px;object-fit:cover;border-radius:8px;background:var(--cream)}
.lg-cura{margin:10px 0 0;font-size:0.76rem;color:var(--text-light)}

/* ── In evidenza: l'unico posto in cui la posizione si compra, e si dice ──── */
.lg-vetrina{margin:22px 0 0;padding:16px 16px 6px;border:1px solid rgba(201,162,39,0.35);
  border-radius:var(--radius-lg,16px);background:rgba(201,162,39,0.05)}
.lg-vetrina > p{margin:0 0 4px;font-size:0.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.05em;color:#846a1a}
.lg-vetrina > p span{font-weight:600;text-transform:none;letter-spacing:0;color:var(--text-light)}
.lg-vetrina .lg-row{background:transparent}

.lg-ordine{margin:30px 0 0;padding:16px 18px;background:var(--cream);border-radius:14px;
  font-size:0.85rem;line-height:1.65;color:var(--text-mid)}
.lg-ordine h2{font-family:'DM Sans',sans-serif;font-size:0.82rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;color:var(--text-light);margin:0 0 8px}
.lg-ordine p{margin:0 0 8px}
.lg-ordine p:last-child{margin:0}

.lg-vuoto{margin:26px 0;padding:26px 20px;text-align:center;background:var(--cream);
  border-radius:14px;color:var(--text-mid)}
.lg-vuoto b{display:block;color:var(--navy);margin-bottom:4px}
"""

LUOGHI_JS = r"""<script>
(function () {
  var bar = document.getElementById('lg-toolbar');
  if (!bar) return;
  var q = document.getElementById('lg-q');
  var conta = document.getElementById('lg-count');
  var vuoto = document.getElementById('lg-vuoto');
  var reset = document.getElementById('lg-reset');
  var sel = [].slice.call(bar.querySelectorAll('select.ev-select'));
  var inpCom = bar.querySelector('input[data-campo="comune"]');
  var listaCom = document.getElementById('lg-comuni');
  var comuniTutti = listaCom
    ? [].map.call(listaCom.options, function (o) { return { v: o.value, p: o.dataset.prov }; })
    : [];
  var righe = [].slice.call(document.querySelectorAll('.lg-row[data-cat]'));

  // Lo stesso slug che il generatore mette in data-comune, rifatto in JS: cosi'
  // "Novi" scritto a mano trova "novi-ligure" senza dover scrivere tutto, e
  // "Città" trova "citta".
  function slugifica(s) {
    return (s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
  }
  var gruppi = [].slice.call(document.querySelectorAll('.lg-grp'));
  if (!righe.length) return;

  // L'indice si costruisce alla PRIMA ricerca, non al caricamento: leggere il
  // testo di centinaia di righe e' lavoro che quasi nessun visitatore usa.
  // Si legge il <details> INTERO e non la sola intestazione, cosi' la ricerca
  // trova anche i servizi ("compleanno", "centro estivo", "carrozzina") che
  // stanno nel corpo. content-visibility non e' un ostacolo: nasconde il
  // disegno, non il testo.
  var testo = null;
  function indice() {
    if (!testo) {
      testo = new Map(righe.map(function (r) {
        return [r, r.textContent.toLowerCase().replace(/\s+/g, ' ')];
      }));
    }
    return testo;
  }

  function applica() {
    var t = q ? q.value.trim().toLowerCase() : '';
    var f = {};
    sel.forEach(function (s) {
      f[s.dataset.campo] = s.value;
      s.classList.toggle('is-on', s.value !== 'all');
    });
    var eta = f.eta && f.eta !== 'all' ? parseInt(f.eta, 10) : null;
    var com = inpCom ? slugifica(inpCom.value) : '';
    if (inpCom) inpCom.classList.toggle('is-on', !!inpCom.value.trim());
    var visti = 0;
    righe.forEach(function (r) {
      var ok = (!f.prov || f.prov === 'all' || r.dataset.prov === f.prov) &&
               (!com || (r.dataset.comune || '').indexOf(com) > -1) &&
               (!f.cat || f.cat === 'all' || r.dataset.cat === f.cat) &&
               (eta === null || (eta >= +r.dataset.etamin && eta <= +r.dataset.etamax)) &&
               (!t || indice().get(r).indexOf(t) > -1);
      r.hidden = !ok;
      if (ok) visti++;
    });
    // Un gruppo svuotato dai filtri si porta via la sua intestazione: se no
    // resta in pagina il nome di un comune con niente sotto. E' il guasto che
    // si vede solo filtrando, quindi va scritto adesso.
    gruppi.forEach(function (g) {
      g.hidden = !g.querySelector('.lg-row[data-cat]:not([hidden])');
    });
    var filtrato = !!t || !!com || sel.some(function (s) { return s.value !== 'all'; });
    conta.textContent = filtrato
      ? visti + (visti === 1 ? ' luogo' : ' luoghi') + ' con questi filtri'
      : '';
    if (vuoto) vuoto.hidden = visti !== 0;
  }

  // La tendina dei comuni segue quella delle province: scegliendo "Prov. AL"
  // restano i comuni di AL. Senza, si poteva scegliere "Prov. AT" + un comune
  // di Alessandria e ottenere un elenco vuoto senza capire perche' - due
  // filtri che si contraddicono sono peggio di un filtro in meno. Se il comune
  // gia' scelto non appartiene piu' alla provincia, si azzera invece di
  // restare selezionato e invisibile.
  var selProv = bar.querySelector('select[data-campo="prov"]');
  function accordaComuni() {
    if (!selProv || !listaCom) return;
    var p = selProv.value;
    var buoni = comuniTutti.filter(function (c) { return p === 'all' || c.p === p; });
    listaCom.innerHTML = buoni.map(function (c) {
      return '<option value="' + c.v.replace(/"/g, '&quot;') + '"></option>';
    }).join('');
    // Un comune scritto che non sta piu' nella provincia scelta si cancella:
    // due filtri che si contraddicono danno un elenco vuoto senza spiegare
    // perche', ed e' peggio di un filtro in meno.
    if (inpCom && inpCom.value.trim()) {
      var scritto = slugifica(inpCom.value);
      var resta = buoni.some(function (c) { return slugifica(c.v).indexOf(scritto) > -1; });
      if (!resta) inpCom.value = '';
    }
  }
  if (selProv) selProv.addEventListener('change', accordaComuni);
  accordaComuni();

  if (q) q.addEventListener('input', applica);
  if (inpCom) {
    inpCom.addEventListener('input', applica);
    inpCom.addEventListener('change', applica);
  }
  sel.forEach(function (s) { s.addEventListener('change', applica); });
  if (reset) reset.addEventListener('click', function () {
    if (q) q.value = '';
    if (inpCom) inpCom.value = '';
    sel.forEach(function (s) { s.value = 'all'; });
    accordaComuni();
    applica();
    bar.scrollIntoView({ block: 'start' });
  });
  applica();

  // Link diretto a un luogo (/luoghi.html#lg-...). Un <details> non si apre da
  // solo quando e' il bersaglio dell'ancora, e se un filtro attivo lo tiene
  // nascosto il browser scrollerebbe nel vuoto: si azzera tutto, si apre, si va.
  function vaiAncora() {
    var id = (location.hash || '').slice(1);
    if (!id) return;
    var r = document.getElementById(id);
    if (!r || !r.classList.contains('lg-row')) return;
    if (r.hidden) {
      if (q) q.value = '';
      sel.forEach(function (s) { s.value = 'all'; });
      applica();
    }
    r.open = true;
    r.scrollIntoView({ block: 'center' });
  }
  window.addEventListener('hashchange', vaiAncora);
  vaiAncora();
})();
</script>
"""


# ── Render ───────────────────────────────────────────────────────────────────

CHEV = ('<svg class="lg-chev" viewBox="0 0 24 24" aria-hidden="true">'
        '<polyline points="6 9 12 15 18 9"/></svg>')
RIPARO_LABEL = {'chiuso': 'Al chiuso', 'aperto': "All'aperto", 'misto': 'Chiuso e aperto'}


def maps_href(l):
    if l.get('lat') and l.get('lon'):
        return f"https://www.google.com/maps/search/?api=1&query={l['lat']},{l['lon']}"
    query = ", ".join(x for x in (l['nome'], l['comune'], l['prov']) if x)
    return "https://www.google.com/maps/search/?api=1&query=" + G.urllib.parse.quote(query)


def data_lunga(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    return f"{d.day} {G.MESI_LUNGHI[d.month - 1]} {d.year}"


def data_breve(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ''
    return f"{d.day} {G.MESI[d.month - 1]}"


def eta_testo(l):
    """La fascia d'eta' scritta una volta sola, e solo se dice qualcosa.

    0-99 vuol dire "tutte le eta'": stamparlo e' rumore. E la fascia NON si
    ripete dentro la descrizione - e' gia' successo con gli eventi, dove una
    cifra scritta due volte faceva sembrare l'indicazione un requisito
    d'ingresso invece che di massima."""
    a, b = l.get('eta_min', 0), l.get('eta_max', 99)
    if a <= 0 and b >= 99:
        return ''
    if b >= 99:
        return f"da {a} anni"
    if a <= 0:
        return f"fino a {b} anni"
    return f"da {a} a {b} anni"


def _indirizzo_utile(l):
    """L'indirizzo si stampa solo se aggiunge qualcosa al nome e al comune."""
    ind = (l.get('indirizzo') or '').strip()
    if not ind:
        return False
    resto = ind.lower()
    for pezzo in (l['nome'], l['comune'], f"({l['prov']})", l['prov']):
        if pezzo:
            resto = resto.replace(pezzo.lower(), ' ')
    return len(re.sub(r'[^a-z0-9]+', '', resto)) >= 4


def riga(l, oggi):
    """Una riga dell'elenco. Chiusa dice cos'e' e dov'e'; aperta dice il resto.

    Niente immagine nell'INTESTAZIONE: al posto della miniatura c'e' l'emoji del
    foglio, che si legge meglio a 36px e non costa una richiesta. La foto vera
    sta nel corpo, cioe' non viene scaricata finche' la riga resta chiusa."""
    e = G.esc
    prossimi = l.get('prossimi') or []

    # L'ordine delle pillole non e' casuale: sul telefono si vedono solo le
    # prime due, quindi davanti sta quello che chi legge non puo' dedurre
    # dall'elenco.
    pillole = []
    if l.get('premium'):
        pillole.append('<span class="lg-tag is-prem">★<i> Scheda curata</i></span>')
    if l.get('consigliato'):
        pillole.append('<span class="lg-tag is-daop">♥<i> Scelto da DAOP</i></span>')
    if prossimi:
        # "1 evento in programma" e non "1 in programma": la pillola deve dire
        # di CHE COSA e' il numero. Senza il sostantivo la frase e' la sola
        # spiegazione di un dato mai nominato, e si legge come se fosse il
        # posto a essere "in programma". Le parole spariscono comunque sul
        # telefono (.lg-tag i), dove resta il solo numero: la riga non si
        # allunga dove lo spazio manca.
        n_ev = len(prossimi)
        pillole.append(f'<span class="lg-tag is-ev"><b>{n_ev}</b>'
                       f'<i> {"evento" if n_ev == 1 else "eventi"} in programma</i>'
                       f'</span>')
    elif l.get('gratuito'):
        pillole.append('<span class="lg-tag is-free">€<i> Gratis</i></span>')

    # ── corpo ──
    corpo = []
    foto = l.get('foto') or []
    if foto:
        corpo.append(f'<img class="lg-foto" src="{e(foto[0])}" alt="{e(l["nome"])}, '
                     f'{e(l["comune"])}" loading="lazy" decoding="async" width="360" height="270">')
        # Il credito va ATTACCATO alla foto, non in fondo alla scheda: i termini
        # di Places chiedono l'attribuzione vicino all'immagine, e il paragrafo
        # subito sotto e' il posto in cui si legge come una didascalia. Riguarda
        # la sola foto[0]; la galleria premium sotto non ne ha (vedi commento in
        # leggi_catalogo).
        corpo.append(html_credito_foto(l.get('foto_autore')))
    if l.get('premium') and len(foto) > 1:
        corpo.append('<div class="lg-galleria">' + "".join(
            f'<img src="{e(u)}" alt="" loading="lazy" decoding="async" width="104" height="78">'
            for u in foto[1:5]) + '</div>')

    testo = (l.get('descr_premium') if l.get('premium') and l.get('descr_premium')
             else l.get('descr'))
    if testo:
        corpo.append(f"<p>{e(G.trunc(testo, 600 if l.get('premium') else 400))}</p>")

    pratici = l.get('pratici') or []
    voci = [f'<li class="is-pratico">{e(p)}</li>' for p in pratici]
    # I servizi sono testo libero del foglio e i pratici escono dai Tag: la
    # stessa cosa e' spesso scritta in tutt'e due le colonne, e la scheda la
    # mostrava due volte di fila - verde e poi grigia. Misurato il 18/08/2026:
    # 89 schede su 894, quasi tutte "Parcheggio" (58) e "Picnic" (49).
    gia_detto = {x.strip().lower() for x in pratici}
    voci += [f'<li>{e(s)}</li>' for s in (l.get('servizi') or [])[:12]
             if s.strip().lower() not in gia_detto]
    if voci:
        corpo.append(f'<ul class="lg-serv">{"".join(voci)}</ul>')

    fatti = []
    if _indirizzo_utile(l):
        fatti.append(f"<li><b>Dove:</b> <span>{e(G.trunc(l['indirizzo'], 90))}</span></li>")
    fatti.append(f'<li><b>Se piove:</b> <span>{RIPARO_LABEL[l["riparo"]]}</span></li>')
    if l.get('orari'):
        fatti.append(f"<li><b>Orari:</b> <span>{e(G.trunc(l['orari'], 200))}</span></li>")
    if l.get('prezzo'):
        fatti.append(f"<li><b>Ingresso:</b> <span>{e(G.trunc(l['prezzo'], 90))}</span></li>")
    elif l.get('gratuito'):
        fatti.append('<li><b>Ingresso:</b> <span>Gratuito</span></li>')
    et = eta_testo(l)
    if et:
        fatti.append(f"<li><b>Età:</b> <span>{et}</span></li>")
    if l.get('tel'):
        num = re.sub(r'[^0-9+]', '', l['tel'])
        fatti.append(f'<li><b>Telefono:</b> <a href="tel:{e(num)}">{e(l["tel"])}</a></li>')
    corpo.append(f'<ul class="lg-facts">{"".join(fatti)}</ul>')

    # La memoria dell'agenda: e' il dato che questa pagina ha e le altre no.
    if l['n_eventi']:
        quanti = ("1 evento per famiglie" if l['n_eventi'] == 1
                  else f"{l['n_eventi']} eventi per famiglie")
        quando = f", l'ultimo il {data_lunga(l['ultimo'])}" if l.get('ultimo') else ""
        corpo.append(f'<p class="lg-manca">Qui DAOP ha seguito {quanti}{quando}.</p>')

    if prossimi:
        elenco = "".join(
            f'<li><a href="{p["href"]}">{e(G.trunc(p["nome"], 70))}</a> '
            f'<span>· {data_breve(p["d"])}</span></li>' for p in prossimi[:5])
        corpo.append(f'<div class="lg-next"><p>In programma qui</p><ul>{elenco}</ul></div>')

    azioni = [f'<a href="{maps_href(l)}" target="_blank" rel="noopener">Apri nelle mappe</a>']
    if l.get('sito'):
        sito = l['sito'] if l['sito'].startswith('http') else 'https://' + l['sito']
        # Un link verso il sito di chi ci paga e' un link commerciale, e le
        # policy di Google chiedono `rel="sponsored"` (o almeno `nofollow`): un
        # link a pagamento che passa PageRank e' uno schema di link, e si paga
        # con un'azione manuale sul dominio - cioe' su eventi.html. `nofollow`
        # basterebbe, ma dice solo "non seguire"; `sponsored` dice cos'e', ed e'
        # la parola giusta proprio sui quattro link che qualcuno potrebbe
        # guardare. Le righe non a pagamento restano `nofollow`: sono
        # segnalazioni nostre, non rapporti commerciali.
        rel = 'sponsored' if l.get('premium') else 'nofollow'
        azioni.append(f'<a href="{e(sito)}" target="_blank" rel="noopener {rel}">Sito del luogo</a>')
    if l.get('email'):
        azioni.append(f'<a href="mailto:{e(l["email"])}">Scrivi al luogo</a>')
    corpo.append(f'<div class="lg-act">{"".join(azioni)}</div>')

    # Il bollino si nomina dove sta il cuore, cioe' nella riga che ce l'ha: un
    # link in fondo alla pagina lo vedrebbe solo chi e' gia' arrivato in fondo,
    # e chi apre la scheda di una biblioteca col cuore arancione la domanda se
    # la fa proprio li'.
    if l.get('consigliato'):
        corpo.append('<p class="lg-manca">♥ Questo posto ha il '
                     '<a href="/bollino.html">bollino Family Friendly</a> di DAOP.</p>')

    if l.get('premium'):
        corpo.append('<p class="lg-cura">Scheda curata da chi gestisce il luogo · '
                     'spazio a pagamento, <a href="#come-ordiniamo">come funziona</a>.</p>')
    else:
        corpo.append('<p class="lg-manca">Manca qualcosa o è cambiato? '
                     '<a href="/index.html#social">Scrivicelo</a>.</p>')

    sigla = f' ({l["prov"]})' if l['prov'] else ''
    etichetta = l.get('cat_sotto') or l.get('cat_nome') or 'Luogo'
    classe = f'lg-row cat-{l["cat"]}' + (' is-prem' if l.get('premium') else '')
    return (
        f'<details class="{classe}" id="{l["slug"]}" data-cat="{l["cat"]}" '
        f'data-prov="{l["prov"].lower()}" data-comune="{G.slugify(l["comune"])}" '
        f'data-etamin="{l.get("eta_min", 0)}" data-etamax="{l.get("eta_max", 99)}">'
        f'<summary>'
        f'<span class="lg-ico" aria-hidden="true">{e(l.get("icona") or "📍")}</span>'
        f'<span class="lg-txt"><span class="lg-nome">{e(l["nome"])}</span>'
        f'<span class="lg-meta"><span class="lg-cat">{e(etichetta)}</span> · '
        f'{e(l["comune"])}{sigla}</span></span>'
        f'<span class="lg-pills">{"".join(pillole)}</span>{CHEV}</summary>'
        f'<div class="lg-body">{"".join(corpo)}</div></details>'
    )


# Le fasce del filtro eta'. Non sono intervalli da scegliere: sono UN'eta',
# quella del bambino che si ha in mente, e la riga passa se la sua fascia la
# contiene. E' la domanda che si fa davvero ("ho un bimbo di 4 anni, dove lo
# porto?") ed evita di dover spiegare cosa succede quando due fasce si
# sovrappongono.
FASCE_ETA = [(1, 'Fino a 2 anni'), (4, '3-5 anni'), (7, '6-9 anni'),
             (11, '10-13 anni'), (15, 'Dai 14 anni')]


def filtri(elenco):
    """La barra dei filtri. Sotto MIN_FILTRI non si stampa niente (si scorre
    prima l'elenco che una tendina), e una tendina senza una scelta da fare non
    si stampa mai - e' un comando che non fa niente.

    Sono quattro, e sul telefono vanno a capo su due righe. E' il contrario
    della scelta fatta quando la pagina aveva 173 righe dedotte dall'agenda, e
    il motivo e' che il dato e' cambiato: con centinaia di luoghi scelti a mano
    l'elenco NON si scorre, si filtra, e i 47px di barra in piu' si ripagano
    alla prima ricerca. Le etichette restano corte lo stesso: Chrome dimensiona
    una <select> sull'opzione piu' lunga."""
    if len(elenco) < G.MIN_FILTRI:
        return ''
    campi = []

    prov = sorted({l['prov'] for l in elenco if l['prov']})
    if len(prov) > 1:
        opts = "".join(f'<option value="{p.lower()}">Prov. {p}</option>' for p in prov)
        campi.append('<select class="ev-select" data-campo="prov" aria-label="Filtra per provincia">'
                     f'<option value="all">Prov.</option>{opts}</select>')

    # Il comune NON e' una <select>, ed e' una scelta obbligata. Con 297 voci il
    # selettore nativo di Android diventa un pannello che copre quasi tutto lo
    # schermo, senza un pulsante per chiuderlo: chi non vuole scegliere niente
    # deve indovinare che si esce toccando fuori o col tasto indietro. Quel
    # pannello lo disegna il sistema operativo e non si puo' vestire, quindi
    # l'unico modo di non averlo e' non usare una <select>.
    #
    # Al suo posto un campo di testo con <datalist>: si scrive "novi" e i
    # suggerimenti compaiono sotto, in linea, senza coprire niente; si svuota
    # con la ✕ del campo. Resta un controllo nativo - niente finestre finte da
    # tenere in piedi con il JavaScript - e senza JS e' comunque un campo che si
    # puo' leggere. Il confronto e' per pezzo di slug, quindi "novi" trova
    # "Novi Ligure" senza dover scrivere tutto.
    per_prov = collections.OrderedDict()
    for l in elenco:
        per_prov.setdefault(l['prov'], {}).setdefault(G.slugify(l['comune']), l['comune'])
    tutti = sum(len(v) for v in per_prov.values())
    if tutti > 1:
        voci = []
        for p in sorted(per_prov):
            for _s, n in sorted(per_prov[p].items(), key=lambda x: _alfabetico(x[1])):
                voci.append(f'<option value="{G.esc(n)}" data-prov="{p.lower()}"></option>')
        campi.append(
            '<input class="ev-select is-comune" type="search" data-campo="comune" '
            'id="lg-comune" list="lg-comuni" placeholder="Comune" '
            'aria-label="Filtra per comune" autocomplete="off">'
            f'<datalist id="lg-comuni">{"".join(voci)}</datalist>')

    cats = {}
    for l in elenco:
        cats.setdefault(l['cat'], l.get('cat_filtro') or l.get('cat_nome') or 'Altro')
    if len(cats) > 1:
        opts = "".join(f'<option value="{c}">{G.esc(n)}</option>'
                       for c, n in sorted(cats.items(), key=lambda x: _alfabetico(x[1])))
        campi.append('<select class="ev-select" data-campo="cat" aria-label="Filtra per tipo di luogo">'
                     f'<option value="all">Tipo</option>{opts}</select>')

    # NON c'e' la tendina "se piove", tolta il 13/08/2026. Non perche' non
    # dividesse - divideva benissimo, 52% al chiuso contro 47% all'aperto - ma
    # perche' rispondeva male alla domanda che ha in testa chi la usa. Con
    # "Al chiuso" restavano dentro le gelaterie, i nidi e le scuole di lingue:
    # tutti al coperto, nessuno un posto dove passi il pomeriggio di pioggia.
    # Il dato resta scritto nella riga aperta, dove e' un'informazione e non una
    # promessa; se un giorno serve di nuovo come filtro, qui bastano cinque
    # righe e in riga_() torna un data-riparo.

    # L'eta' entra solo se le righe la dichiarano davvero: con tutte 0-99 la
    # tendina non toglierebbe mai niente, cioe' sarebbe un comando che non fa
    # niente con cinque voci invece che con una.
    if sum(1 for l in elenco if eta_testo(l)) >= G.MIN_FILTRI:
        opts = "".join(f'<option value="{v}">{t}</option>' for v, t in FASCE_ETA)
        campi.append('<select class="ev-select" data-campo="eta" aria-label="Filtra per età del bambino">'
                     f'<option value="all">Età</option>{opts}</select>')

    if not campi:
        return ''
    return f"""    <div class="ev-toolbar" id="lg-toolbar">
      <div class="ev-search">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
        <input type="search" id="lg-q" placeholder="Cerca un posto, un paese, un'attività…" aria-label="Cerca fra i luoghi" autocomplete="off">
      </div>
{chr(10).join("      " + c for c in campi)}
    </div>
    <div class="ev-viewbar">
      <p class="lg-count" id="lg-count" role="status" aria-live="polite"></p>
      <button type="button" class="lg-reset" id="lg-reset" style="margin-left:auto">Azzera i filtri</button>
    </div>"""


def _per_comune(elenco):
    ordinati = collections.OrderedDict()
    for l in elenco:
        ordinati.setdefault((l['prov'], l['comune']), []).append(l)
    return list(ordinati.items())


def ancora_comune(prov, comune):
    """L'id dell'<h2> del gruppo comune, cioe' il bersaglio dei link in arrivo.

    La provincia sta NELL'id, non solo nel testo: "Ronco Scrivia" compare in AL e
    in GE (nel foglio uno dei due e' un refuso, ma non tocca a noi indovinare
    quale), e due <h2> con lo stesso id sono HTML non valido - l'ancora
    porterebbe sempre al primo dei due.

    Sta in una funzione perche' la usano in due: chi disegna la pagina e chi
    scrive l'indice che le altre pagine leggono per linkarla. Se le due
    divergessero, i link arriverebbero su un'ancora che non esiste."""
    pag = G.slugify(comune)
    return f"c-{prov.lower()}-{pag}" if prov else f"c-{pag}"


def gruppi_comune(elenco, oggi):
    """Le righe raggruppate per comune. Il raggruppamento e' anche la risposta a
    "con che ordine sono messi": comune in ordine alfabetico, luoghi in ordine
    alfabetico dentro. Nessun criterio che si compra."""
    fuori = []
    for (prov, comune), righe in _per_comune(elenco):
        n = len(righe)
        pag = G.slugify(comune)
        # Il link alla pagina comune solo se la pagina esiste davvero: un
        # collegamento a una 404 vale meno di nessun collegamento.
        link = ''
        if os.path.exists(os.path.join(ROOT, 'eventi', 'comune', f'{pag}.html')):
            link = f'<a href="/eventi/comune/{pag}.html">Eventi a {G.esc(comune)} →</a>'
        ancora = ancora_comune(prov, comune)
        fuori.append(
            f'<section class="lg-grp">'
            f'<div class="lg-grp-h"><h2 id="{ancora}">{G.esc(comune)}</h2>'
            f'<span>{prov} · {n} {"luogo" if n == 1 else "luoghi"}</span>{link}</div>'
            + "".join(riga(l, oggi) for l in righe) + '</section>')
    return "\n".join(fuori)


def vetrina(elenco, oggi):
    """Il blocco "In evidenza". Esiste solo se qualcuno l'ha comprato, e lo dice
    in chiaro nella prima riga: e' l'unico punto della pagina in cui la
    posizione non dipende dall'ordine alfabetico."""
    scelti = [l for l in elenco if l.get('evidenza') and l.get('premium')][:3]
    if not scelti:
        return ''
    righe = "".join(riga(dict(l, slug=l['slug'] + '-ev'), oggi) for l in scelti)
    return (f'<div class="lg-vetrina"><p>In evidenza '
            f'<span>· spazi a pagamento, <a href="#come-ordiniamo">come funziona</a></span></p>'
            f'{righe}</div>')


# Tre righe, non quattro paragrafi. Cancellarlo del tutto non si puo': l'art. 22
# comma 4-bis del Codice del consumo chiede che i parametri di ordinamento siano
# dichiarati in una sezione raggiungibile dai risultati, e tacere che una
# posizione e' pagata sta nella lista nera delle pratiche ingannevoli in ogni
# caso. Ma l'obbligo e' dire la cosa, non scriverci sopra un tema: quello che
# serve e' l'ordine (alfabetico), cosa cambia pagare (il contenuto, non il
# posto) e dov'e' l'unica posizione comprabile. Il resto era prosa.
COME_ORDINIAMO = """    <section class="lg-ordine" id="come-ordiniamo">
      <h2>Come è ordinato questo elenco</h2>
      <p>Per comune, in ordine alfabetico. I filtri restringono l'elenco, non lo riordinano.</p>
      <p>Le schede <b>★ curate</b> sono scritte da chi gestisce il luogo e paga questo
      spazio: cambia <em>cosa</em> c'è dentro, non <em>dove</em> sta la riga. L'unica
      posizione a pagamento è il blocco “In evidenza” in cima, che lo dichiara.</p>
      <p>Il <b>♥ bollino</b> <a href="/bollino.html">Family Friendly</a> è un'altra cosa:
      si merita, non si compra.</p>
      <p>Un luogo descritto male, o che ha chiuso?
      <a href="/index.html#social">Scrivicelo</a>.</p>
    </section>"""


def jsonld(elenco):
    """ItemList delle voci + Place completo SOLO per le schede curate.

    Un Place per ognuno degli 800 luoghi sarebbe mezzo mega di dati strutturati
    che non produce nessun rich result: Google non ha un risultato ricco per un
    "luogo" generico. Le schede curate hanno orari, telefono e foto dati da chi
    gestisce il posto: quelle si possono dichiarare, e sono poche."""
    voci = [{"@type": "ListItem", "position": i, "name": l['nome'],
             "url": f"{PAGE_URL}#{l['slug']}"} for i, l in enumerate(elenco, 1)]
    grafo = [{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "@id": PAGE_URL,
        "url": PAGE_URL,
        "name": "Dove andare con i bambini",
        "isPartOf": {"@type": "WebSite", "name": "DAOP", "url": G.SITE_URL},
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(elenco),
                       "itemListOrder": "https://schema.org/ItemListUnordered",
                       "itemListElement": voci},
    }]
    for l in elenco:
        if not l.get('premium'):
            continue
        p = {"@context": "https://schema.org", "@type": "Place",
             "@id": f"{PAGE_URL}#{l['slug']}", "name": l['nome'],
             "address": {"@type": "PostalAddress", "addressLocality": l['comune'],
                         "addressRegion": l.get('regione') or l['prov'] or "Piemonte",
                         "addressCountry": "IT"}}
        if l.get('indirizzo'):
            p['address']['streetAddress'] = l['indirizzo']
        if l.get('cap'):
            p['address']['postalCode'] = l['cap']
        if l.get('lat') and l.get('lon'):
            p['geo'] = {"@type": "GeoCoordinates", "latitude": l['lat'], "longitude": l['lon']}
        testo = l.get('descr_premium') or l.get('descr')
        for valore, chiave in ((testo, 'description'), (l.get('sito'), 'url'),
                               (l.get('tel'), 'telephone'), (l.get('orari'), 'openingHours')):
            if valore:
                p[chiave] = valore
        if l.get('foto'):
            p['image'] = l['foto'][:3]
        grafo.append(p)
    return "\n".join(
        '<script type="application/ld+json">\n' + json.dumps(g, ensure_ascii=False, indent=1)
        + '\n</script>' for g in grafo)


def dove_siamo(elenco):
    """"Alessandria, Asti e Cuneo", e solo le province che hanno righe davvero.

    Qui c'era la logica opposta - "e dintorni" per le province di contorno -
    perche' il catalogo usciva dalla regione. Da quando `solo_province_nostre()`
    pota tutto quello che non e' AL/AT/CN quel ramo non era piu' irraggiungibile
    e basta: era diventato sbagliato, perche' con una provincia sotto il 5% delle
    righe avrebbe chiamato Cuneo "dintorni".

    Si nominano solo le presenti perche' questa funzione serve anche a un
    sottoinsieme (le piscine), dove una provincia puo' non avere niente."""
    presenti = {l['prov'] for l in elenco if l['prov']}
    dentro = [p for p in G.PROVINCE_PUBBLICATE if p in presenti]
    if not dentro:
        return "Piemonte"
    return G.province_in_elenco(dentro)


def _css_categorie(elenco):
    """Le tinte stanno in classi, non in uno style= sulla riga: 800 righe per
    ~90 byte di custom property sarebbero 70 KB di attributi ripetuti, che e'
    esattamente il difetto tolto dall'agenda con i link del calendario."""
    visti = {}
    for l in elenco:
        visti.setdefault(l['cat'], l.get('colore') or colore_cat(l['cat']))
    return "\n" + "\n".join(
        f".cat-{slug}{{--cat-color:{c};--cat-tint:{t};--cat-ink:{i}}}"
        for slug, (c, t, i) in sorted(visti.items())) + "\n"


def render(elenco, oggi):
    css, nav, foot = G._guscio()
    e = G.esc
    n = len(elenco)
    comuni = len({(l['prov'], l['comune']) for l in elenco})
    zona = dove_siamo(elenco)

    # Senza "| DAOP" in coda, come le pagine di intenzione: il nome del sito sta
    # gia' in og:site_name, e in SERP quei sette caratteri sono quelli che fanno
    # tagliare il titolo.
    titolo = f"Dove andare con i bambini in {zona}"
    descr = (f"{n} luoghi per famiglie in {comuni} comuni: parchi, fattorie didattiche, "
             "musei, piscine, sport e spazi al chiuso. Si filtra per provincia, tipo, "
             "età e se piove.")

    # Corta apposta. Il conteggio e la zona stanno gia' due righe sopra,
    # nell'occhiello, e i filtri si vedono subito sotto: elencarli a parole era
    # spiegare una cosa che si tocca. Qui resta solo quello che l'intestazione
    # non dice - di che roba e' fatto l'elenco, e cosa succede se apri una riga.
    # L'elenco degli esempi e' scritto a mano e non dedotto dai numeri. Provato:
    # ordinando per quantita' la frase cominciava con "Nidi e Micro-nidi", che e'
    # la categoria piu' numerosa (123) e la meno invitante su una pagina che si
    # intitola "Dove andare con i bambini". I nidi ci sono e restano nominati -
    # chi li cerca li trova - ma dopo le cose per cui si esce di casa.
    # Niente coda "in N c'e' gia' un evento in programma": il numero e' piccolo
    # (9 su 823) e prometteva poco a costo di una riga in piu'. Chi ha un evento
    # lo dice gia' da solo, con la pillola verde sulla riga.
    # Sta nell'HERO, non in cima al corpo: sotto la fascia scura era un paragrafo
    # grigio appoggiato sul crema senza niente che lo tenesse su, e la sua CSS
    # spiega perche' (vedi .lg-hero .lg-intro). Nell'hero e' il terzo gradino di
    # una scala che si legge: titolo, dove e quanti, di cosa e' fatto.
    intro = ('    <p class="lg-intro">Fattorie didattiche, musei, parchi e panchine giganti, '
             'piscine, gelaterie, biblioteche e nidi: scelti uno per uno. '
             'Apri una riga per orari, prezzi e contatti.</p>')

    vuoto = ('<div class="lg-vuoto" id="lg-vuoto" hidden><b>Nessun luogo con questi filtri.</b>'
             'Prova a togliere la provincia o il tipo di luogo.</div>')

    corpo = "\n".join(x for x in [
        '  <div class="lg-wrap">',
        filtri(elenco),
        vetrina(elenco, oggi),
        vuoto,
        gruppi_comune(elenco, oggi),
        COME_ORDINIAMO,
        # Il ponte verso /piscine.html, che fino al 20/08/2026 non ce l'aveva:
        # misurato con grep, quella pagina riceveva ZERO link dal corpo di
        # qualunque pagina del sito e non sta nemmeno in nav — cioe' esisteva
        # solo in sitemap. E' il difetto gia' visto su luoghi.html il 14/08.
        # Si stampa con la stessa soglia con cui la pagina entra in indice (5):
        # sotto quel numero /piscine.html va in noindex, e linkare dal corpo una
        # pagina che diciamo a Google di ignorare e' un segnale contro l'altro.
        # E porta il numero, per la ragione di sempre: "32 piscine" e' un motivo
        # per toccare, "Piscine" no.
        _link_piscine(elenco),
        _link_idee(),
        '    <div class="com-link"><a href="/bollino.html">Il bollino Family Friendly</a>'
        '<a href="/metodo.html">Come verifichiamo</a>'
        '<a href="/zone.html">Le zone</a></div>',
        # "Tutta l'agenda DAOP" era qui e adesso sta nella riga delle quattro
        # porte, col numero degli eventi attaccato: due link alla stessa pagina
        # a quattro centimetri di distanza sono uno di troppo, e quello che
        # sopravvive e' quello che dice quanti eventi ci sono.
        G.blocco_ecosistema('luoghi'),
        f'    <p class="ev-firma-nota">Pagina rigenerata ogni notte. Ultimo aggiornamento: '
        f'{oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>',
        '  </div>',
    ] if x)

    alt_og = ("Illustrazione: un adulto e un bambino camminano mano nella mano su un "
              "sentiero fra le colline, sotto un arcobaleno")
    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/genera_luoghi.py: le modifiche scritte a mano
     qui dentro spariscono alla run successiva, senza avvisare. Si tocca il
     generatore. Il CSS della nav, del footer e dei componenti comuni arriva da
     eventi.html tramite _guscio(): anche quello non si modifica qui. -->
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titolo)}</title>
<meta name="description" content="{e(descr)}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{PAGE_URL}">
<meta property="og:title" content="{e(titolo)}">
<meta property="og:description" content="{e(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{PAGE_URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.DEFAULT_IMG}">
<!-- Misure e alt dell'immagine sociale: senza, WhatsApp e Facebook devono
     scaricarla per sapere come impaginarla, e finche' non ci riescono mostrano
     l'anteprima senza figura. Sono i valori veri di headerdaop.jpg. -->
<meta property="og:image:width" content="1600">
<meta property="og:image:height" content="960">
<meta property="og:image:alt" content="{alt_og}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(titolo)}">
<meta name="twitter:description" content="{e(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{G.DEFAULT_IMG}">
<meta name="twitter:image:alt" content="{alt_og}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<!-- Le foto dei luoghi stanno su Supabase: il preconnect apre la connessione
     mentre la pagina si disegna, cosi' la prima riga che si apre non paga DNS
     e handshake TLS. Non scarica niente: le immagini restano ferme finche' una
     riga non viene aperta. -->
<link rel="preconnect" href="{SUPABASE_FOTO}" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<!-- COMUNE_CSS serve per .com-link, la riga di link in fondo: senza, i tre
     link uscivano attaccati ("Tutta l'agenda DAOPCome verifichiamoLe zone")
     perche' quella regola vive li' e non nel guscio. Si include invece di
     ricopiarla, come fanno le pagine di intenzione: la regola sta in un posto
     solo. Nessun selettore generico dentro, quindi non tocca le classi lg-*. -->
<style>{css}{G.PAGINA_CSS}{G.COMUNE_CSS}{LUOGHI_CSS}{_css_categorie(elenco)}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero lg-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <span>Luoghi</span>
    </div>
    <h1>Dove andare <em>con i bambini</em></h1>
    <p class="ev-when">{e(zona)} · {n} luoghi in {comuni} comuni</p>
{intro}
  </div>
</header>
{corpo}
{G.blocco_ginetto()}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
{LUOGHI_JS}
{jsonld(elenco)}
</body>
</html>
"""


PISCINE_URL = f"{G.SITE_URL}/piscine.html"
PISCINE_PATH = os.path.join(ROOT, "piscine.html")
# Le due sottocategorie che finiscono in pagina. `riparo` (aperto/chiuso) e'
# gia' calcolato dai tag e fa da solo il taglio fra le due meta'.
PISCINE_SOTTO = ('Piscine & Parchi Acquatici', 'Nuoto')


def _link_piscine(elenco):
    """La riga che manda a /piscine.html, o '' se la pagina non e' in indice.

    Sta in un blocco suo e non nella riga dei link di servizio perche' e' un
    'vedi anche' di contenuto: le piscine sono una fetta tematica del catalogo,
    cioe' la prima delle pagine di incrocio, non un link istituzionale come il
    bollino o il metodo."""
    n = len(le_piscine(elenco))
    if n < 5:
        return ''
    return ('    <div class="com-link"><a href="/piscine.html">'
            f'{n} piscine per bambini</a></div>')


def _link_idee():
    """I 'vedi anche' verso le pagine /idee/, o ''.

    Le idee sono cinque posti scelti a mano (vedi scripts/genera_idee.py), e
    senza un link dal CORPO di una pagina nascono orfane: e' esattamente il
    motivo per cui /piscine.html non prendeva niente, misurato il 14/08/2026.

    Si linka solo quello che ESISTE gia' su disco: un link a una 404 vale meno
    di nessun link. Quindi una pagina appena decisa compare qui il giro dopo -
    lo stesso ritardo di un giro che si accetta gia' per l'indice dei comuni, e
    per la stessa ragione: sbaglia dalla parte buona.

    Il file si legge qui invece di importare genera_idee, che a sua volta
    importa questo modulo: l'import girerebbe in tondo. Quello che serve sono
    due campi, non la logica.
    """
    percorso = os.path.join(ROOT, "data", "idee.json")
    try:
        with open(percorso, encoding="utf-8") as fh:
            idee = json.load(fh).get("idee") or []
    except Exception:
        return ''
    voci = []
    for idea in idee:
        slug = (idea.get('slug') or '').strip()
        titolo = (idea.get('titolo_corto') or idea.get('briciola')
                  or idea.get('titolo') or '').strip()
        if not slug or not titolo:
            continue
        if not os.path.exists(os.path.join(ROOT, 'idee', f'{slug}.html')):
            continue
        voci.append(f'<a href="/idee/{slug}.html">{G.esc(titolo)}</a>')
    if not voci:
        return ''
    return '    <div class="com-link">' + "".join(voci) + '</div>'


def le_piscine(elenco):
    return [l for l in elenco if (l.get('cat_sotto') or '') in PISCINE_SOTTO]


def render_piscine(elenco, oggi):
    """/piscine.html — UNA pagina, scritta a mano, non la prima di trenta.

    ⚠️ LEGGERE IL PRIMO COMMENTO DEL FILE PRIMA DI COPIARE QUESTA FUNZIONE PER
    UN'ALTRA CATEGORIA. Il motivo per cui gli 891 luoghi stanno in una pagina
    sola e' che 800 pagine su template identico sono la definizione di scaled
    content abuse, e la penalizzazione se la porta dietro il dominio. Trenta
    pagine "<categoria> per bambini" sfornate da un ciclo sarebbero la stessa
    cosa in piccolo. Questa esiste perche' ha una domanda sua a cui l'elenco
    generale non risponde, ed e' l'unica condizione che ne giustifichi un'altra.

    LA DOMANDA. Sotto la parola "piscina" ci sono due posti che si cercano in due
    momenti diversi dell'anno e non si sostituiscono: quella all'aperto dove si
    porta il bambino a fare il bagno a luglio (23 su 33), e la vasca coperta dove
    lo si iscrive al corso a settembre (10). Chi cerca una non vuole l'altra, e
    in un elenco unico ordinato per comune finiscono mescolate.

    ⚠️ ONESTA' SUI NUMERI: al 17/08/2026 questa pagina nasce SENZA evidenza di
    domanda. Nell'export Search Console 09-15/08 le query con dentro "piscina"
    fanno 4 query, 5 impressioni e ZERO clic. E' una scommessa strutturale -
    luoghi.html fa 538 impressioni e 3 clic, cioe' lo 0,56%, il peggior CTR del
    sito, e il sospetto e' che sia perche' parla di tutto - non la risposta a una
    domanda misurata. Se fra sei mesi non prende niente, la mossa giusta e'
    toglierla, non moltiplicarla.
    """
    css, nav, foot = G._guscio()
    e = G.esc
    piscine = le_piscine(elenco)
    aperte = [l for l in piscine if l.get('riparo') == 'aperto']
    coperte = [l for l in piscine if l.get('riparo') != 'aperto']
    n = len(piscine)
    comuni = len({(l['prov'], l['comune']) for l in piscine})
    zona = dove_siamo(piscine)

    titolo = G.trunc(f"Piscine per bambini in {zona}", 62)
    descr = (f"{n} piscine per bambini in {comuni} comuni: quelle all'aperto per il "
             "bagno d'estate e quelle coperte per i corsi di nuoto, con orari e "
             "contatti. Verificate una per una.")
    intro = ('    <p class="lg-intro">Le piscine all\'aperto dove si va a fare il bagno '
             'e le vasche coperte dove si fa il corso: sono due cose diverse, e qui '
             'stanno divise. Apri una riga per orari, prezzi e contatti.</p>')

    editoriale = (
        '    <section class="lg-ordine">'
        '<h2>Per il bagno o per il corso?</h2>'
        '<p>È la prima cosa da chiarire, perché sotto la stessa parola ci sono due '
        'posti che non si sostituiscono. La <strong>piscina all\'aperto</strong> è '
        'una gita: si va a giugno, luglio e agosto, si sta un pomeriggio, spesso '
        'c\'è il prato e il bar, e quello che conta è se c\'è una <strong>vasca '
        'piccola</strong> per chi non tocca e quanta ombra c\'è nelle ore centrali. '
        'La <strong>vasca coperta</strong> è un impegno annuale: ci si iscrive a '
        'settembre, si va una o due volte a settimana, e quello che conta è '
        'l\'orario del corso e quanti bambini ci sono per istruttore.</p>'
        '<p>Sui <strong>prezzi</strong> conviene essere espliciti: quasi nessuno li '
        'pubblica, e quelli che circolano invecchiano in una stagione. Dove il '
        'gestore ce li ha dati li trovi nella riga; dove non ci sono, il telefono '
        'c\'è e una chiamata risolve. Vale anche per gli <strong>ingressi '
        'ridotti</strong> per i più piccoli e per l\'abbonamento a dieci ingressi: '
        'quasi sempre esistono e quasi mai sono scritti da qualche parte.</p>'
        '<p>Due avvertenze pratiche. Le piscine estive <strong>aprono e chiudono '
        'con il tempo</strong>, non con il calendario: a giugno e a settembre '
        'conviene chiamare prima di mettersi in macchina. E per i corsi, i posti '
        'nelle fasce del tardo pomeriggio — le uniche compatibili con la scuola — '
        'finiscono entro le prime due settimane di settembre.</p>'
        '</section>')

    def blocco(titoletto, sotto, lista):
        if not lista:
            return ''
        return (f'    <section class="com-grp"><div class="com-head"><div class="com-b">'
                f'<h3>{e(titoletto)}</h3><p class="com-per">{e(sotto)}</p></div></div>'
                f'</section>' + gruppi_comune(lista, oggi))

    corpo = "\n".join(x for x in [
        '  <div class="lg-wrap">',
        filtri(piscine),
        editoriale,
        blocco("All'aperto, per il bagno",
               f"{len(aperte)} piscine estive: si va per la giornata, da giugno a settembre",
               aperte),
        blocco("Coperte, per i corsi",
               f"{len(coperte)} vasche al chiuso: scuole nuoto e corsi tutto l'anno",
               coperte),
        '    <div class="com-link"><a href="/luoghi.html">Tutti i luoghi per famiglie</a>'
        '<a href="/metodo.html">Come verifichiamo</a></div>',
        # Questa pagina appartiene alla famiglia Luoghi, quindi la riga porta le
        # altre tre: 'luoghi' e' la famiglia, non l'URL. Il link a /luoghi.html
        # resta sopra ed e' un'altra cosa — quello e' il padre, questi i cugini.
        G.blocco_ecosistema('luoghi'),
        f'    <p class="ev-firma-nota">Pagina rigenerata ogni notte. Ultimo aggiornamento: '
        f'{oggi.day} {G.MESI_LUNGHI[oggi.month - 1]} {oggi.year}.</p>',
        '  </div>',
    ] if x)

    return f"""<!DOCTYPE html>
<!-- PAGINA GENERATA da scripts/genera_luoghi.py: le modifiche scritte a mano
     qui dentro spariscono alla run successiva. Si tocca il generatore. -->
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{e(titolo)}</title>
<meta name="description" content="{e(descr)}">
<meta name="robots" content="{'index, follow' if n >= 5 else 'noindex, follow'}">
<link rel="canonical" href="{PISCINE_URL}">
<meta property="og:title" content="{e(titolo)}">
<meta property="og:description" content="{e(descr)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{PISCINE_URL}">
<meta property="og:locale" content="it_IT">
<meta property="og:site_name" content="DAOP">
<meta property="og:image" content="{G.DEFAULT_IMG}">
<meta property="og:image:width" content="1600">
<meta property="og:image:height" content="960">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(titolo)}">
<meta name="twitter:description" content="{e(G.trunc(descr, 120))}">
<meta name="twitter:image" content="{G.DEFAULT_IMG}">
<link rel="icon" href="/assets/images/favicon-96.png" type="image/png" sizes="96x96">
<link rel="apple-touch-icon" href="/assets/images/apple-touch-icon.png">
<link rel="preload" href="/assets/fonts/dm-sans-normal-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preconnect" href="{SUPABASE_FOTO}" crossorigin>
<link rel="stylesheet" href="/assets/css/daop-system.min.css">
<style>{css}{G.PAGINA_CSS}{G.COMUNE_CSS}{LUOGHI_CSS}{_css_categorie(piscine)}</style>
<script src="/assets/js/cookie-consent.js"></script>
<script src="/assets/js/daop-track.js" defer></script>
</head>
<body>
{nav}
<main id="contenuto">
<header class="page-hero ev-hero lg-hero">
  <div class="page-hero-inner">
    <div class="ev-crumb" role="navigation" aria-label="Percorso">
      <a href="/">Home</a> › <a href="/luoghi.html">Luoghi</a> › <span>Piscine</span>
    </div>
    <h1>Piscine <em>per bambini</em></h1>
    <p class="ev-when">{e(zona)} · {n} piscine in {comuni} comuni</p>
{intro}
  </div>
</header>
{corpo}
{G.blocco_ginetto()}</main>
{foot}
<script>
function toggleMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.toggle('open');}}
function closeMobile(){{var m=document.getElementById('mobile-menu');if(m)m.classList.remove('open');}}
</script>
{LUOGHI_JS}
{jsonld(piscine)}
</body>
</html>
"""


def salva_istantanea(elenco):
    """L'istantanea che fa da ripiego quando il foglio non risponde.

    Si salvano le righe GREZZE del foglio, con le sue intestazioni: cosi' il
    ripiego e il CSV passano dallo stesso normalizzatore e non c'e' un secondo
    formato da tenere allineato quando una colonna cambia nome. Si scrive solo
    se le righe arrivano davvero dal foglio: rigenerare l'istantanea da se'
    stessa non aggiunge niente e la farebbe ricommittare ogni notte."""
    # L'ordine e' quello della pagina (provincia, comune, nome) e non quello del
    # foglio: da qui passa un file committato ogni notte, e un ordinamento che
    # segue le righe del foglio farebbe un diff di 16.000 righe la prima volta
    # che qualcuno riordina il tab.
    grezzi = [l['_grezzo'] for l in sorted(
        elenco, key=lambda d: (d['prov'], _alfabetico(d['comune']), _alfabetico(d['nome'])))
        if l.get('_grezzo')]
    if not grezzi:
        return
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(grezzi, fh, ensure_ascii=False, indent=1)
    print(f"[genera_luoghi] istantanea aggiornata: {len(grezzi)} righe di catalogo")


def salva_indice_comuni(elenco):
    """L'indice dei comuni con almeno un luogo, per chi vuole linkare qui dentro.

    Nasce il 14/08/2026 per un problema misurato: `luoghi.html` e' nella nav di
    292 pagine e in nessun CORPO di pagina (a parte le due stagionali), ed e' il
    motivo per cui non prende traffico mentre le schede evento ne fanno l'82%.
    Il link dalla scheda al proprio comune usa questo file.

    Perche' un file e non un controllo al volo: chi linka deve sapere se
    l'ancora esiste DAVVERO, come gia' si fa qui per le pagine comune
    (`os.path.exists`) - un link a un'ancora che non c'e' scarica in cima a una
    pagina da 800 righe, che e' peggio di nessun link. Riscriverne la logica in
    `genera_eventi.py` vorrebbe dire duplicare la normalizzazione del foglio (le
    grafie doppie, il dedup) e vederla divergere alla prima colonna che cambia
    nome.

    Si accetta un giro di ritardo: `genera_eventi.py` gira PRIMA di questo (deve,
    vedi CLAUDE.md), quindi legge l'indice della notte prima. Su un catalogo in
    cui un comune nuovo compare una volta ogni tanto e' un prezzo giusto, e
    sbaglia dalla parte buona: un comune appena nato resta senza link per un
    giorno, invece di avere un link rotto subito."""
    indice = {ancora_comune(prov, comune): {'comune': comune, 'prov': prov,
                                            'n': len(righe)}
              for (prov, comune), righe in _per_comune(elenco)}
    with open(INDICE_COMUNI, "w", encoding="utf-8") as fh:
        json.dump(indice, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"[genera_luoghi] indice comuni: {len(indice)} comuni con almeno un luogo")


def update_sitemap(n, url=None):
    """Aggiunge (o aggiorna) la voce di una pagina luoghi nella sitemap.

    priority 0.8 come le pagine comune: e' una pagina che vale tutto l'anno.
    changefreq weekly e non daily - i posti non cambiano ogni notte, cambiano i
    riquadri "in programma" che ci stanno dentro."""
    url = url or PAGE_URL
    nome = url.rsplit('/', 1)[-1]
    if not os.path.exists(SITEMAP_PATH) or not n:
        return
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    voce = (f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{oggi}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>")
    if f"<loc>{url}</loc>" in s:
        s = re.sub(r'  <url>\s*<loc>' + re.escape(url) + r'</loc>.*?</url>',
                   lambda _: voce, s, count=1, flags=re.S)
    else:
        s, k = re.subn(r'(?=  <url>\s*<loc>https://www\.daop\.it/eventi\.html</loc>)',
                       lambda _: voce + "\n", s, count=1)
        if k != 1:
            print(f"[genera_luoghi] sitemap: non trovo dove inserire {nome}, salto")
            return
    open(SITEMAP_PATH, "w", encoding="utf-8").write(s)
    print(f"[genera_luoghi] sitemap: {nome} -> {oggi}")


def controlla_crollo(catalogo):
    """Blocca la rigenerazione se il catalogo e' crollato rispetto all'istantanea.

    E' lo stesso guasto gia' visto sugli eventi il 05/08/2026: l'export CSV di
    Google **rispetta i filtri** del foglio, e con un filtro attivo sul tab
    restituisce solo le righe visibili. Quel giorno erano 26 invece di 193.
    Qui vorrebbe dire pubblicare 40 luoghi al posto di 800, con la pagina
    dimezzata e nessun errore da nessuna parte - il tipo di guasto che si
    scopre tre settimane dopo guardando un grafico piatto.

    Si confronta solo con righe FRESCHE: se stiamo gia' usando l'istantanea non
    c'e' niente da proteggere, e' lei il riferimento."""
    if not os.path.exists(JSON_PATH):
        return True
    fresche = [l for l in catalogo if l.get('_grezzo')]
    if not fresche:
        return True
    with open(JSON_PATH, encoding="utf-8") as fh:
        prima = len(json.load(fh))
    if prima >= 20 and len(fresche) < prima * 0.6:
        print(f"[genera_luoghi] ATTENZIONE: il tab Luoghi da' {len(fresche)} righe "
              f"contro le {prima} dell'ultima volta. Sembra un filtro attivo sul "
              f"foglio, non una potatura: lascio la pagina com'è.")
        return False
    return True


def main():
    oggi = datetime.date.today()
    foglio = leggi_catalogo()
    # Il crollo si controlla sulle righe del FOGLIO, prima di potare: se il
    # taglio per provincia venisse prima, un filtro rimasto attivo che lascia
    # fuori solo AL/AT/CN darebbe zero righe fresche e la guardia lo leggerebbe
    # come "sto girando sull'istantanea", cioe' tacerebbe.
    if not controlla_crollo(foglio):
        raise SystemExit(1)
    catalogo = solo_province_nostre(foglio)
    agenda = leggi_agenda()
    elenco = unisci(catalogo, agenda)
    if not elenco:
        print("[genera_luoghi] nessun luogo: lascio la pagina com'è")
        return
    da_cat = sum(1 for l in elenco if l.get('fonte') == 'catalogo')
    premium = sum(1 for l in elenco if l.get('premium'))
    consigliati = sum(1 for l in elenco if l.get('consigliato'))
    in_vetrina = sum(1 for l in elenco if l.get('evidenza') and l.get('premium'))
    # Se ci sono schede a pagamento e la vetrina resta vuota, lo si dice: e' il
    # tipo di cosa che non si vede guardando la pagina (manca un blocco, non
    # compare un errore) e che costa a chi ha pagato.
    if premium and not in_vetrina:
        print('[genera_luoghi] nessuno in vetrina: la colonna "In evidenza" del '
              'foglio è vuota su tutte le schede a pagamento')
    # Il proprio numero prima di scrivere: la riga delle quattro porte lo
    # rilegge, e le altre pagine lo vedranno alla loro run — cioe' domani. E' lo
    # stesso ritardo di un giro di data/luoghi-comuni.json, e va bene per la
    # stessa ragione: un numero di ieri sbaglia di poco e sbaglia gratis.
    G.conteggio_scrivi('luoghi', len(elenco))
    open(OUT_PATH, "w", encoding="utf-8").write(render(elenco, oggi))
    salva_istantanea(foglio)
    salva_indice_comuni(elenco)
    update_sitemap(len(elenco))
    # /piscine.html — sotto le 5 righe si scrive lo stesso ma esce in noindex e
    # fuori sitemap, come le pagine di intenzione: la pagina resta raggiungibile
    # e non promette un elenco che non ha.
    piscine = le_piscine(elenco)
    open(PISCINE_PATH, "w", encoding="utf-8").write(render_piscine(elenco, oggi))
    if len(piscine) >= 5:
        update_sitemap(len(piscine), PISCINE_URL)
    aperte = sum(1 for l in piscine if l.get('riparo') == 'aperto')
    print(f"[genera_luoghi] piscine.html: {len(piscine)} piscine "
          f"({aperte} all'aperto, {len(piscine) - aperte} coperte)"
          + ("" if len(piscine) >= 5 else " — sotto soglia, noindex"))
    peso = os.path.getsize(OUT_PATH) / 1024
    print(f"[genera_luoghi] luoghi.html: {len(elenco)} luoghi "
          f"({da_cat} da catalogo, {len(elenco) - da_cat} dall'agenda), "
          f"{premium} schede curate ({in_vetrina} in vetrina), "
          f"{consigliati} scelti da DAOP, {peso:.0f} KB")


if __name__ == "__main__":
    main()
