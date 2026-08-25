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

# Le province si prendono da genera_eventi e non si riscrivono qui.
# PROVINCE_TESTO e' derivata da PROVINCE_PUBBLICATE, quindi il giorno che se ne
# apre una quarta questi tre titoli si allargano da soli.
#
# Fino al 20/08/2026 erano nove stringhe scritte a mano che dicevano
# "Alessandria e Asti" — titoli, descrizioni, H1, occhiello e perfino il
# JSON-LD — e Cuneo era aperta dal 4 agosto: e' esattamente il difetto che il
# commento su PROVINCE_TESTO descrive ("e' proprio il copy a restare
# indietro"), ripetuto in un altro file dove nessuno lo cercava.
#
# QUI LA COPERTURA E' DICHIARATA, NON DEDOTTA DAI DATI, al contrario di
# genera_corsi.zona(), e la differenza ha una ragione: fuori stagione l'elenco
# dei centri e' vuoto. Un titolo dedotto dalle righe diventerebbe "in Piemonte"
# a settembre e tornerebbe indietro a marzo, cioe' oscillerebbe due volte
# l'anno sulla pagina il cui unico asset e' l'anzianita' dell'URL. Un <title>
# che balla e' peggio di uno largo: e' la stessa aritmetica per cui il robots
# delle pagine d'incrocio si decide su trenta giorni e non su oggi.
# Sui corsi invece la copertura non e' dichiarata (il catalogo si costruisce
# una societa' alla volta) e li' il dato deve comandare.
ZONA = G.PROVINCE_TESTO
ETICHETTA = ' · '.join([G.PROVINCE_NOMI[c] for c in G.PROVINCE_PUBBLICATE]
                       + ['Famiglie'])

# Una voce per stagione. Aggiungere gli invernali significa aggiungere una
# riga qui: il resto del codice non cambia.
STAGIONI = {
    'estivi': {
        'file': 'centri-estivi.html',
        'tab': 'Centri Est/Inv',
        'h1': 'Centri Estivi',
        # parte in corsivo oro dell'H1, come "Oggi" nell'hero degli eventi
        'h1_em': ZONA,
        'singolare': 'centro estivo',
        'titolo': f'Centri Estivi {ZONA} | DAOP',
        'descr': (f'Centri estivi per bambini in {ZONA}: '
                  'elenco con età, orari e costi, e la guida per scegliere e '
                  'iscriversi in tempo.'),
        'periodo': 'giugno, luglio e agosto',
        'breve': "d'estate",
        'iscrizioni': 'fra marzo e maggio',
        'quando_riaprono': 'in primavera',
        'parole': ('estiv', 'estat', 'summer'),
        'p_iscrizioni': """<p>Le iscrizioni si aprono di solito fra marzo e
  maggio, cioè con mesi di anticipo. I posti nelle strutture più richieste
  finiscono nelle prime settimane, quindi conviene informarsi presto anche
  senza aver deciso: quasi tutti i gestori permettono di prenotare le settimane
  singolarmente e chiedono un acconto per bloccarle. Se lavorate entrambi,
  partite dal calendario delle vostre ferie e non da quello dei centri.</p>""",
        'p_primo_giorno': """<p>Per i più piccoli, o alla prima esperienza fuori
  casa, chiedete se è possibile un inserimento graduale: su tre mesi c'è tutto
  il tempo, ed è la cosa che fa la differenza fra una bella estate e due
  settimane di pianti. Nello zaino l'essenziale: cambio completo, borraccia,
  cappellino, crema solare, e tutto marcato con nome e cognome.</p>""",
        # Le due domande della guida che d'estate hanno una risposta e nelle
        # altre stagioni un'altra. Vedi il commento su `specifico`.
        'b_giornata': ('Una giornata tipo dice più di un volantino: quanto tempo '
                       'all\'aperto, quante uscite, se c\'è la piscina e come ci '
                       'si arriva.'),
        'b_meteo': ('<strong>In caso di maltempo.</strong> Dove si sta e cosa si '
                    'fa quando non si può uscire: è la differenza fra una bella '
                    'settimana e una lunga.'),
        'specifico': """
  <h3>Tre mesi non si comprano tutti insieme</h3>
  <p>L'estate è lunga e quasi nessuno la copre per intero: si mettono insieme
  due settimane qui, una là, i nonni, le ferie. Conviene ragionare a blocchi e
  partire da quelli che <em>devono</em> essere coperti — le settimane in cui
  lavorate entrambi e non c'è nessun altro — e riempire il resto dopo.</p>
  <p>L'altra cosa che d'estate conta più che in ogni altra stagione è
  <strong>il caldo</strong>. Chiedete dove stanno i bambini fra le due e le
  quattro del pomeriggio, se ci sono spazi ombreggiati o climatizzati, e quanta
  acqua è prevista. Un centro tutto all'aperto a luglio in pianura è una cosa
  diversa da uno con la palestra e il cortile alberato.</p>""",
    },
    'invernali': {
        'file': 'centri-invernali.html',
        'tab': 'Centri Est/Inv',
        'h1': 'Centri Invernali',
        'h1_em': ZONA,
        'singolare': 'centro invernale',
        'titolo': f'Centri Invernali e Vacanze di Natale {ZONA} | DAOP',
        'descr': ('Centri invernali e attività per bambini durante le vacanze di Natale '
                  f'in {ZONA}: elenco, età, orari e costi, '
                  'con la guida per scegliere.'),
        'periodo': 'le vacanze di Natale e le chiusure scolastiche invernali',
        'breve': 'a Natale',
        'iscrizioni': 'fra ottobre e novembre',
        'quando_riaprono': 'in autunno',
        'parole': ('invern', 'natal', 'winter', 'befana'),
        'p_iscrizioni': """<p>Qui il calendario è stretto: le proposte escono
  fra ottobre e novembre e si riempiono in fretta, perché sono poche e i posti
  pochi. Non aspettate il volantino — a ottobre conviene chiedere direttamente
  all'oratorio, alla ludoteca e all'ufficio scuola del Comune se organizzano
  qualcosa durante le vacanze, perché spesso si decide tardi e si annuncia solo
  su un gruppo WhatsApp o una bacheca.</p>""",
        'p_primo_giorno': """<p>Su una o due settimane l'inserimento graduale non
  esiste: si comincia e basta, e se il bambino non conosce nessuno vale la pena
  saperlo prima. Chiedete se il gruppo è lo stesso dell'estate — spesso sì, ed è
  un vantaggio — e preparate lo zaino per stare al chiuso: cambio, scarpe da
  ginnastica pulite da usare dentro, e qualcosa di caldo per gli spostamenti.</p>""",
        'b_giornata': ('D\'inverno si sta dentro quasi sempre: chiedete in che '
                       'spazi, quanto sono grandi e se si esce comunque, anche '
                       'solo per andare in biblioteca o in piscina coperta.'),
        'b_meteo': ('<strong>Se nevica o la struttura chiude.</strong> A dicembre '
                    'e gennaio capita: chiedete se avvisano la sera prima, se '
                    'recuperano la giornata e chi tiene i bambini se chiudono '
                    'all\'improvviso.'),
        'specifico': """
  <h3>Qui il problema non è scegliere, è trovare</h3>
  <p>È la differenza vera con l'estate, e conviene dirla subito: i centri
  invernali sono <strong>pochi</strong>. La scuola chiude per due settimane, i
  genitori lavorano quasi tutti fino al 24 e ricominciano il 7, e le strutture
  che aprono in quei giorni si contano sulle dita. Non è una scelta fra dieci
  proposte come a giugno: è prendere quello che c'è, vicino a casa, e
  iscriversi appena esce.</p>
  <p>Da qui la cosa più importante: <strong>guardate quali giorni coprono
  davvero</strong>. Quasi nessuno fa tutte e due le settimane. Molti si fermano
  il 23 e riprendono il 7, cioè coprono esattamente i giorni in cui la scuola
  era già aperta; altri fanno solo la settimana fra Natale e l'Epifania, che è
  quella scoperta ma anche quella in cui più gente è in ferie. Il calendario
  preciso è il primo dato da chiedere, prima ancora del prezzo.</p>
  <p>Sugli <strong>orari</strong> vale lo stesso avvertimento: d'inverno molti
  centri fanno solo la mattina, dalle 8 alle 13, senza mensa. Se lavorate a
  tempo pieno una mattina non risolve la giornata, e conviene saperlo prima di
  contare su quel posto.</p>""",
    },
    # I centri pasquali sono la stagione piu' corta e la piu' incerta: la
    # vacanza dura pochi giorni e molti gestori la saltano del tutto. La pagina
    # esiste lo stesso perche' chi cerca cerca proprio quella - e perche' se un
    # anno non apre nessuno, dirlo e' un'informazione utile quanto un elenco.
    'pasquali': {
        'file': 'centri-pasquali.html',
        'tab': 'Centri Est/Inv',
        'h1': 'Centri Pasquali',
        'h1_em': ZONA,
        'singolare': 'centro per le vacanze di Pasqua',
        'titolo': f'Centri per le Vacanze di Pasqua {ZONA} | DAOP',
        'descr': ('Centri e attività per bambini durante le vacanze di Pasqua in '
                  f'{ZONA}: elenco con età, orari e costi, '
                  'e la guida per scegliere.'),
        'periodo': 'le vacanze di Pasqua',
        'breve': 'a Pasqua',
        'iscrizioni': 'fra febbraio e marzo',
        'quando_riaprono': 'a fine inverno',
        'parole': ('pasqu', 'easter'),
        'p_iscrizioni': """<p>Quando qualcosa apre, si annuncia con due o tre
  settimane di preavviso e si riempie in pochi giorni: è troppo corto perché i
  gestori facciano campagne, e troppo corto perché i genitori se lo organizzino
  con calma. L'unica strada che funziona è chiedere prima — a febbraio, al
  proprio Comune e all'oratorio — invece di aspettare che esca qualcosa.</p>""",
        'p_primo_giorno': """<p>Su quattro giorni non c'è inserimento che tenga,
  quindi la domanda utile è un'altra: <strong>chi altro c'è</strong>. Se il
  gruppo è quello dell'oratorio o della scuola il bambino entra e basta; se non
  conosce nessuno, quattro giorni sono pochi per ambientarsi e tanti per stare
  scomodo. Nello zaino serve poco: cambio, merenda e una giacca, perché ad
  aprile il tempo cambia due volte al giorno.</p>""",
        'b_giornata': ('Sono pochi giorni, quindi chiedete il programma per '
                       'esteso: a Pasqua si fa spesso un laboratorio unico che '
                       'dura tutta la settimana, e o piace o sono giornate '
                       'lunghe.'),
        'b_meteo': ('<strong>Se piove.</strong> Ad aprile il programma all\'aperto '
                    'salta facilmente: chiedete cosa succede allora, perché su '
                    'quattro giorni una giornata storta pesa molto più che a '
                    'luglio.'),
        'specifico': """
  <h3>Quattro giorni, e non è detto che ci siano</h3>
  <p>Le vacanze di Pasqua durano pochi giorni — di norma dal giovedì al martedì
  dopo Pasquetta — e questo cambia tutto. Molti gestori <strong>non aprono
  affatto</strong>: per una manciata di giorni, con due festivi in mezzo, non
  vale la pena mettere in piedi l'organizzazione. Se questa pagina è vuota non è
  perché non abbiamo cercato: è che quell'anno non ha aperto nessuno, e
  preferiamo scriverlo.</p>
  <p>Quando invece qualcosa c'è, la domanda da fare è <strong>esattamente quali
  giorni</strong>. La settimana è spezzata dai festivi e ogni gestore la taglia
  a modo suo: c'è chi fa solo i giorni feriali prima di Pasqua, chi solo quelli
  dopo Pasquetta, chi due giorni in tutto. Un calendario che sembra coprire la
  vacanza spesso ne copre metà.</p>
  <p>Ultima cosa, pratica: essendo così corti, questi centri <strong>si
  riempiono in pochi giorni</strong> e spesso si annunciano con due o tre
  settimane di preavviso. Vale la pena chiedere al proprio Comune e all'oratorio
  già a febbraio, senza aspettare che esca un volantino.</p>""",
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
# Una voce per ogni chiave di STAGIONI: aggiungerne una la' e dimenticarla qui
# fermava tutta la run notturna (KeyError: 'pasquali', 18/08/2026) - e non solo
# i centri, perche' il passo che committa viene dopo. Da allora la lettura e'
# .get(): una stagione senza mesi si fida della sola colonna del foglio, che e'
# un elenco povero, non un sito fermo.
# I pasquali stanno in marzo-aprile perche' la Pasqua cade fra il 22 marzo e il
# 25 aprile: nessun mese si sovrappone alle altre due stagioni.
MESI_STAGIONE = {
    'estivi': (5, 6, 7, 8, 9),
    'invernali': (11, 12, 1, 2),
    'pasquali': (3, 4),
}

# Tutte le parole riconosciute, di tutte le stagioni. Serve a distinguere due
# casi che prima finivano nello stesso silenzio: una riga di UN'ALTRA stagione
# (giusto scartarla, la prendera' la sua pagina) e una riga con una stagione che
# NON ESISTE - "carnevale", "ponte", "settimana bianca". La seconda non la
# pubblica nessuno, e il foglio non ha modo di accorgersene: finiva nel
# conteggio "N di altra stagione" e via. Il calendario scolastico piemontese
# 2026/27 dice quanto e' concreto il caso: il Carnevale vale cinque giorni
# (6-10 febbraio 2027) e il ponte di Ognissanti quest'anno non esiste, perche'
# l'1 novembre cade di domenica. Le finestre cambiano ogni anno: e' la ragione
# per cui decide il foglio e non una tabella qui dentro.
PAROLE_NOTE = tuple(w for cfg in STAGIONI.values() for w in cfg['parole'])

# Una stagione ignota si annuncia una volta per run, non una per stagione: il
# ciclo di main() chiama leggi_centri() tre volte sulla stessa tab.
_IGNOTE_VISTE = set()


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

    parole = STAGIONI[chiave]['parole']
    mesi = MESI_STAGIONE.get(chiave, ())
    out, scartati = [], 0
    ignote = {}
    # Quante righe le decide la COLONNA e quante il mese di inizio. Serve a
    # rispondere alla domanda che si fa dopo aver aggiunto la colonna al foglio:
    # "la sta usando?". Una colonna che esiste ma e' vuota si comporta
    # identica a una colonna che non c'e', e dal log non si distingueva.
    da_colonna = da_mese = 0
    for r in righe[hi + 1:]:
        def val(campo):
            i = idx.get(campo)
            return (r[i].strip() if i is not None and i < len(r) else '')
        if not val('nome'):
            continue
        prov = val('prov').upper()
        # La lista era scritta a mano ('AL', 'AT') ed e' rimasta ferma quando
        # Cuneo e' stata aperta (04/08/2026): i titoli di queste pagine dicevano
        # gia' "Alessandria, Asti e Cuneo" - ZONA e' derivata da
        # PROVINCE_PUBBLICATE - mentre un centro a Cuneo veniva buttato via qui
        # senza un avviso da nessuna parte. Ora la lista e' una sola, la stessa
        # dell'agenda: le due superfici non possono divergere in silenzio.
        if prov and prov not in G.PROVINCE_PUBBLICATE:
            continue
        c = {campo: val(campo) for campo in COLONNE}
        c['d_start'] = G.pdate(c['di'])
        c['d_end'] = G.pdate(c['df']) or c['d_start']

        # La colonna stagione, se c'e' ed e' compilata, ha la precedenza.
        # Altrimenti decide il mese di inizio, che e' il dato piu' affidabile.
        st = c['stagione'].lower()
        if st:
            da_colonna += 1
            se = any(w in st for w in parole)
            if not se and not any(w in st for w in PAROLE_NOTE):
                ignote[st] = ignote.get(st, 0) + 1
        elif c['d_start']:
            da_mese += 1
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
    for st, n in sorted(ignote.items()):
        if st in _IGNOTE_VISTE:
            continue
        _IGNOTE_VISTE.add(st)
        print(f"[genera_centri] ATTENZIONE: {n} righe con stagione '{st}', che "
              f"non ha una pagina: NON SONO PUBBLICATE DA NESSUNA PARTE. "
              f"Stagioni riconosciute: {', '.join(sorted(STAGIONI))}.")
    if da_colonna or da_mese:
        print(f"[genera_centri] la stagione l'ha decisa la colonna su "
              f"{da_colonna} righe, il mese di inizio su {da_mese}")
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
/* Il richiamo alla guida in PDF. <div> e non <section>: section{padding:100px
   24px} arriva dal CSS di sistema e qui varrebbe 200px di vuoto. */
.ce-guidapdf{margin:2.6em 0 0;padding:20px 22px;border:1px solid rgba(0,0,0,.12);
  border-radius:14px;background:rgba(0,0,0,.02)}
.ce-guidapdf h2{margin:0 0 .4em;font-size:1.15rem}
.ce-guidapdf p{margin:0 0 12px;line-height:1.6}
.ce-guidapdf .btn{color:#fff}
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
    # verde di primavera per i pasquali: senza la sua voce la pagina ripiegava
    # sull'arancio degli estivi, cioe' due stagioni diverse con la stessa tinta.
    'pasquali': ('#6f9e4e', 'rgba(111,158,78,0.14)', '#4a6d2e'),
}
# Le etichette del filtro provincia: da genera_eventi, non riscritte qui.
# Scritte a mano conoscevano solo AL e AT, quindi un centro a Cuneo avrebbe
# messo "CN" nella tendina — il .get(p, p) lo nascondeva invece di dirlo.
PROV_LABEL = G.PROVINCE_NOMI


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
    nove mesi su dodici, cioe' contenuto magro.

    ⚠️ `specifico` NON e' un abbellimento, e' la ragione per cui esiste piu' di
    una di queste pagine. Con la sola guida generica cambiata nei riferimenti di
    stagione, estivi e invernali risultavano IDENTICI AL 97,7% - contenuto
    duplicato, e il doppione lo perde la pagina piu' debole. E' lo stesso motivo
    per cui una stagionale degli eventi non puo' essere solo un filtro di date
    (vedi spec_halloween in genera_eventi.py).

    Il blocco `specifico` sta in cima apposta: e' la prima cosa che legge chi
    arriva ed e' la prima che indicizza Google. Le due voci `b_giornata` e
    `b_meteo` sono le domande dell'elenco che in stagioni diverse hanno risposte
    diverse: d'estate "quanto si sta fuori", d'inverno "cosa si fa dentro"."""
    return f"""
<section class="ce-guide">
  <h2>Come scegliere un {cfg['singolare']}</h2>
  <p>La scelta si gioca su poche cose concrete, e quasi tutte si chiariscono con
  una telefonata prima di iscrivere. Ecco cosa conviene chiedere.</p>
{cfg['specifico']}

  <h3>Quando ci si iscrive</h3>
  {cfg['p_iscrizioni']}

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
    <li><strong>Cosa si fa davvero.</strong> {cfg['b_giornata']}</li>
    <li>{cfg['b_meteo']}</li>
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
  {cfg['p_primo_giorno']}
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
            "name": f"{cfg['h1']} in {ZONA}",
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


def sorelle(chiave):
    """Le altre due stagioni dei centri.

    E' il ponte che a queste pagine mancava del tutto. Misurato il 20/08/2026
    con grep su tutto il repo: centri-invernali.html e centri-pasquali.html
    ricevevano ZERO link dal corpo di qualunque pagina — stavano solo in
    sitemap — e centri-estivi.html ne aveva uno, la riga nell'hero dell'agenda.
    Una famiglia intera senza porte, cioe' lo stesso guasto gia' diagnosticato
    e gia' risolto su luoghi.html il 14/08 ("alla nav non ci va nessuno": messo
    il ponte dalle schede evento, 58 -> 538 impressioni in due giorni).

    Il link porta il periodo e non solo il nome, per la stessa ragione per cui
    link_luoghi() porta il numero: "Centri invernali" e' un'etichetta, "a
    Natale" e' una ragione per toccare. E serve soprattutto a dicembre, quando
    chi cerca atterra sugli estivi perche' e' la pagina forte della famiglia:
    li' quel link e' la cosa piu' utile che la pagina ha da dargli."""
    voci = [f'<a href="/{cfg["file"]}">{G.esc(cfg["h1"])} {G.esc(cfg["breve"])}</a>'
            for k, cfg in STAGIONI.items() if k != chiave]
    if not voci:
        return ''
    return ('<h2>Le altre vacanze</h2>'
            f'<div class="com-link">{"".join(voci)}</div>')


GUIDE_PATH = os.path.join(ROOT, 'data', 'guide.json')


def _guide():
    """Quali guide in PDF esistono davvero, scritte da genera_pdf.py.

    In ritardo di un giro, come data/luoghi-comuni.json e data/conteggi.json:
    il PDF di stanotte lo linka la run di domani. Chiudere il cerchio (stampare
    prima, generare dopo) vorrebbe dire far girare due volte genera_centri per
    un link che arriva un giorno prima.

    Se il file manca il link non si stampa e basta - regola di link_luoghi().
    Un link a un PDF che non c'e' e' peggio di nessun link: qui non c'e'
    nemmeno una pagina 404 nostra a raccoglierlo."""
    try:
        with open(GUIDE_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def link_guida(chiave):
    """L'invito a scaricare la guida, in coda al corpo.

    In coda e non in cima, per la stessa ragione dell'invito al canale: chiedere
    qualcosa prima di aver dato qualcosa non funziona. Qui la pagina ha appena
    dato la guida intera - il PDF e' la stessa cosa da portare via, e si dice
    cosi'."""
    g = _guide().get(chiave)
    if not g:
        return ''
    # Il peso si scrive: su un telefono con la linea del paese, "PDF, 240 kB"
    # e' la differenza fra toccare e non toccare.
    kb = max(1, int(g.get('byte', 0) / 1024))
    peso = f'{kb} kB' if kb < 1024 else f'{kb / 1024:.1f} MB'
    return (
        f'  <div class="ce-guidapdf">\n'
        f'    <h2>Portala con te</h2>\n'
        f'    <p>La stessa guida in un foglio solo, con l\'elenco completo e le '
        f'date: da stampare o da guardare insieme, anche senza connessione.</p>\n'
        f'    <p><a class="btn btn-teal" href="/{g["file"]}" '
        f'data-guida="{G.esc(chiave)}">Scarica la guida {G.esc(g["anno"])} '
        f'(PDF, {peso})</a></p>\n'
        f'  </div>')


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

    # Fuori dall'indice quando non c'e' un centro ne' in corso ne' in arrivo.
    # E' la regola di MIN_LANDING (halloween.html, le sagre-provincia-*): la
    # pagina resta online - i link girati su WhatsApp devono funzionare e l'URL
    # deve continuare a invecchiare - ma una pagina che risponde "iscrizioni non
    # ancora aperte" non va offerta a chi cerca.
    #
    # Non e' il robots che cambia ogni notte di cui parla CLAUDE.md: 'attivi'
    # comprende anche i centri FUTURI, quindi zero vuol dire che nel foglio non
    # c'e' niente all'orizzonte. Nell'anno gira due volte per stagione - il
    # giorno dopo l'ultimo centro, e il giorno che arriva la prima riga nuova -
    # non ogni notte.
    robots = 'index, follow' if attivi else 'noindex, follow'

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
<meta name="robots" content="{robots}">
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
<!-- COMUNE_CSS serve per .com-link, la riga "Le altre vacanze" in fondo:
     senza, i due link uscivano attaccati ("Centri Invernali a NataleCentri
     Pasquali a Pasqua") perche' quella regola vive li' e non nel guscio. Si
     include invece di ricopiarla, come gia' fa genera_luoghi.py: la regola
     sta in un posto solo. -->
<style>{css}{G.COMUNE_CSS}{CSS}</style>
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
    <span class="section-label">{ETICHETTA}</span>
    <h1>{G.esc(cfg['h1'])} <em>{cfg['h1_em']}</em></h1>
    <p>I centri per bambini attivi durante {cfg['periodo']} in {ZONA}, con età,
    orari e costi. Sotto, la guida per scegliere:
    quando ci si iscrive, cosa chiedere prima e quali documenti servono.</p>
    <p style="margin-top:14px;font-size:0.95rem;opacity:0.9;">Cerchi qualcosa per oggi? Vedi le <a href="/eventi.html" style="color:inherit;text-decoration:underline;text-underline-offset:3px;">sagre e gli eventi in {ZONA}</a>.</p>
  </div>
</header>
<article class="ce-wrap">
  {avviso}
  <!-- GUIDA-PDF:START — quello che sta qui dentro finisce anche nel PDF di
       guide/. Lo estrae scripts/genera_pdf.py per stringa, quindi i due marker
       non si tolgono e non si annidano. Fuori restano nav, footer, filtri di
       stagione e i bottoni: in una guida stampata non servono a niente. -->
  {elenco}
  {guida(cfg)}
  <!-- GUIDA-PDF:END -->
  {link_guida(chiave)}
  {sorelle(chiave)}
  {G.blocco_ecosistema('centri')}
  <div class="ce-actions">
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


STATO_PATH = os.path.join(ROOT, 'data', 'centri-stagioni.json')


def voce_nav(cfg):
    """L'etichetta in nav: "Centri estivi", non "Centri Estivi".

    Derivata dall'H1 invece di essere un campo in piu': un campo si dimentica,
    e una stagione nuova nascerebbe con l'etichetta vuota."""
    h1 = cfg['h1']
    return h1[:1] + h1[1:].lower()


def scrivi_stato(stato):
    """Quali stagioni sono vive, per la nav di tutto il sito.

    Il sito non puo' chiederlo a questo script: genera_eventi.py gira PRIMA
    (senza rete se serve) e la nav che stampa finisce, via _guscio(), su ~360
    pagine. Quindi la comunicazione passa da un file, ed e' in ritardo di un
    giro come data/conteggi.json e data/luoghi-comuni.json - accettato per la
    stessa ragione: una voce di ieri sbaglia di poco e sbaglia nel verso gratis.

    Si FONDE con quello che c'e' gia', non lo sostituisce. Se il foglio non si
    legge, di quella stagione non sappiamo niente e il valore di ieri resta:
    e' la stessa regola per cui in quel caso la pagina non viene riscritta.
    Riscrivendo il file da zero, un timeout di Google avrebbe spento una voce
    di nav su tutto il sito."""
    if not stato:
        return
    try:
        d = json.load(open(STATO_PATH, encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    if not isinstance(d, dict):
        d = {}
    prima = json.dumps(d, sort_keys=True)
    d.update(stato)
    if json.dumps(d, sort_keys=True) == prima:
        return
    with open(STATO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    vive = [k for k, v in sorted(d.items()) if (v or {}).get('attivi')]
    print(f"[genera_centri] stagioni vive: {', '.join(vive) if vive else 'nessuna'} "
          f"(la nav del sito le segue dalla run di stanotte)")


def aggiorna_sitemap(cambiate, indicizzabili=None):
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
    files, visti, fuori = [], set(), []
    for cfg in STAGIONI.values():
        f = cfg['file']
        path = os.path.join(ROOT, f)
        if f in visti or not os.path.exists(path):
            continue
        visti.add(f)
        # Una pagina in noindex non va in sitemap: sono due direttive che si
        # contraddicono, ed e' la coppia che halloween.html tiene insieme.
        # Delle stagioni che questa run non ha riscritto non sappiamo niente:
        # lo si chiede alla pagina su disco invece di indovinare.
        dentro = (indicizzabili.get(f) if indicizzabili and f in indicizzabili
                  else 'noindex' not in open(path, encoding='utf-8').read()[:4000])
        (files if dentro else fuori).append(f)
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
          f"({len(cambiate & set(files))} con lastmod aggiornato)"
          + (f", {len(fuori)} fuori perche' in noindex: {', '.join(fuori)}"
             if fuori else ""))


# Stagioni generate senza argomenti.
#
# Gli invernali sono rimasti fuori a lungo, e per una ragione giusta: con la sola
# guida generica cambiata nei riferimenti di stagione le due pagine risultavano
# identiche al 97,7%, cioe' contenuto duplicato. Il blocco che mancava e' stato
# scritto (`specifico` in STAGIONI, piu' le due voci b_giornata/b_meteo), quindi
# ora ognuna dice una cosa sua: d'estate "tre mesi non si comprano tutti
# insieme", d'inverno "il problema non e' scegliere, e' trovare", a Pasqua
# "quattro giorni, e non e' detto che ci siano".
#
# Sotto soglia le pagine restano comunque oneste: senza centri in stagione
# escono con la guida e lo dicono, invece di riempirsi con quelli di un'altra
# stagione. Una singola stagione si rigenera a mano con
# "python3 scripts/genera_centri.py invernali".
ATTIVE = ['estivi', 'invernali', 'pasquali']


def main(argv):
    chiavi = argv or ATTIVE
    ignote = [k for k in chiavi if k not in STAGIONI]
    if ignote:
        raise SystemExit(f"[genera_centri] stagione sconosciuta: {', '.join(ignote)}")
    css, nav, foot = G._guscio()
    cambiate = set()   # solo le pagine riscritte davvero: guidano il lastmod
    # Il numero per la riga delle quattro porte. Non e' la somma delle tre
    # stagioni — leggono la stessa tab, quindi sommarle conterebbe lo stesso
    # centro tre volte — ed e' il MASSIMO fra loro, cioe' la stagione che in
    # questo momento ha qualcosa: fuori stagione le altre due sono a zero e la
    # somma direbbe il vero senza dire niente.
    attivi_max = 0
    stato = {}
    indicizzabili = {}
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
        oggi = datetime.date.today()
        attivi = [c for c in centri if not c['d_end'] or c['d_end'] >= oggi]
        attivi_max = max(attivi_max, len(attivi))
        # 'inizio' e' la data piu' vicina fra i centri ancora in piedi, e serve
        # a scegliere quale stagione parla in nav quando ne sono vive due (a
        # febbraio: Carnevale in corso e iscrizioni estive aperte). Una stagione
        # gia' cominciata ha una data nel passato, quindi vince - ed e' giusto,
        # e' quella che sta succedendo adesso.
        # Chi ha diritto di voto sulla nav: una riga senza NESSUNA data non sa
        # dire se la stagione e' adesso. Restano in pagina - togliere una
        # scheda perche' il foglio e' incompleto sarebbe peggio - ma non tengono
        # viva una stagione: al 21/08/2026 sono due righe estive senza date, e
        # da sole avrebbero fatto dire "Centri estivi" alla nav anche a
        # novembre, cioe' esattamente il difetto che questo meccanismo chiude.
        # 'attivi' qui e' quindi un numero diverso da quello che la pagina
        # mostra, ed e' voluto: quello sta in data/conteggi.json.
        votanti = [c for c in attivi if c['d_start'] or c['d_end']]
        date = sorted(c['d_start'] for c in votanti if c['d_start'])
        stato[chiave] = {
            'file': cfg['file'],
            'voce': voce_nav(cfg),
            'attivi': len(votanti),
            'inizio': date[0].isoformat() if date else None,
        }
        indicizzabili[cfg['file']] = bool(attivi)
        nuovo = render(chiave, cfg, centri, css, nav, foot)
        if os.path.exists(path) and open(path, encoding='utf-8').read() == nuovo:
            print(f"[genera_centri] {cfg['file']}: invariata")
        else:
            open(path, 'w', encoding='utf-8').write(nuovo)
            print(f"[genera_centri] {cfg['file']}: scritta ({len(centri)} centri)")
            cambiate.add(cfg['file'])
    # Scritto in fondo e non in cima: le pagine di questa run usano il numero di
    # ieri. E' lo stesso ritardo di un giro di data/luoghi-comuni.json, ed e'
    # accettato per la stessa ragione — un conteggio di ieri sbaglia di poco e
    # sbaglia nel verso gratis.
    G.conteggio_scrivi('centri', attivi_max)
    scrivi_stato(stato)
    aggiorna_sitemap(cambiate, indicizzabili)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
