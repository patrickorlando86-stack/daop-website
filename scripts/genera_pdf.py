#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le guide stagionali in PDF: `guide/<stagione>-<anno>.pdf`.

Gira DOPO gli altri generatori e non scrive nessun contenuto suo. Prende quello
che la pagina gia' pubblica — il pezzo fra i marker `<!-- GUIDA-PDF:START/END -->`
— ci mette intorno un CSS di stampa e lo manda a Chromium. Il PDF non puo'
divergere da quello che si legge sul sito, perche' *e'* quello: e' la regola di
`_dati_realta()` in genera_corsi.py («i dati si scrivono in un posto solo»)
applicata a un secondo formato.

Perche' non Playwright. Chromium sa gia' stampare da solo
(`--headless --print-to-pdf`), e aggiungere una libreria al workflow per una
cosa che il binario gia' installato fa con un argomento e' un costo permanente
per un comodo di un giorno. Stessa ragione per cui qui non c'e' un parser HTML:
i marker sono gia' l'idioma del repo (vedi EVENTI-* in eventi.html).

Cosa NON fa, e sono decisioni:

- **Niente immagini.** Le locandine stanno su Supabase, che ha un tetto di banda
  mensile e in CI puo' non rispondere: una guida da 8 MB che ogni tanto esce coi
  riquadri grigi e' peggio di una guida di solo testo. E' lo stesso conto che ha
  fatto uscire le locandine da git.
- **Niente guida senza materiale.** Se la stagione non ha nemmeno una data in
  data/centri-stagioni.json, il PDF non si scrive. E' MIN_LANDING applicata a un
  file, con una differenza che conta: una pagina vuota resta online e la
  riscrive la run di stanotte, un PDF vuoto invece **gira** e non lo correggi
  piu'.
- **Niente PDF svuotato se Chromium manca.** Lascia quello di ieri e lo dice nel
  log, come genera_centri.py lascia la pagina com'e' quando non legge il foglio.

Scrive `data/guide.json`, che genera_centri.py legge alla run DOPO per stampare
il link. Il ritardo di un giro e' voluto ed e' lo stesso di
data/luoghi-comuni.json e data/conteggi.json.

    python3 scripts/genera_pdf.py            # tutte le guide possibili
    python3 scripts/genera_pdf.py estivi     # una sola
"""

import base64
import datetime
import glob
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_GUIDE = os.path.join(ROOT, 'guide')
STATO_PATH = os.path.join(ROOT, 'data', 'centri-stagioni.json')
GUIDE_PATH = os.path.join(ROOT, 'data', 'guide.json')

# L'insieme e' CHIUSO e non cresce coi dati: sono le pagine che esistono gia'.
# La riga che non va aggiunta qui e' "estivi-alessandria", "estivi-6-10-anni" e
# compagnia: sarebbero 3 x 4 x N pagine su template identico, cioe' lo scaled
# content da cui luoghi.html e' nata per scappare. Vedi CLAUDE.md.
GUIDE = {
    'estivi': {
        'pagina': 'centri-estivi.html',
        'titolo': 'Guida ai centri estivi',
        'occhiello': 'Centri estivi in provincia di Alessandria, Asti e Cuneo',
        'sottotitolo': 'Come scegliere, cosa chiedere e chi organizza, '
                       'paese per paese.',
        'quando': 'Le iscrizioni si aprono fra marzo e maggio. Nei comuni più '
                  'grandi i posti finiscono nelle prime due settimane.',
    },
    'invernali': {
        'pagina': 'centri-invernali.html',
        'titolo': 'Guida ai centri invernali',
        'occhiello': 'Centri invernali e natalizi in provincia di Alessandria, Asti e Cuneo',
        'sottotitolo': 'Le due settimane di chiusura scolastica, '
                       'e chi le copre in zona.',
        'quando': 'Le iscrizioni si aprono di solito a novembre, e le settimane '
                  'coperte sono poche: si decide in fretta.',
    },
    'pasquali': {
        'pagina': 'centri-pasquali.html',
        'titolo': 'Guida ai centri pasquali',
        'occhiello': 'Centri pasquali in provincia di Alessandria, Asti e Cuneo',
        'sottotitolo': 'I giorni di vacanza di primavera, '
                       'e chi organizza qualcosa.',
        'quando': 'È la finestra più corta dell\'anno: pochi giorni, e le '
                  'iscrizioni si aprono appena dopo Carnevale.',
    },
}

# Dove sta Chromium. In CI e nell'ambiente di sviluppo e' sotto /opt/pw-browsers
# (lo stesso che usano le prove in tests/), ma la variabile ha la precedenza:
# su una macchina qualunque basta CHROMIUM_PATH=/usr/bin/chromium.
CANDIDATI = [
    os.environ.get('CHROMIUM_PATH'),
    '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
]

# A chi scrive un gestore che vuole entrare nell'edizione dell'anno prossimo.
# Uno solo: i centri non hanno la divisione per provincia che hanno i corsi
# (MAIL_PROV in genera_corsi.py), e inventarne una qui vorrebbe dire scrivere
# in un PDF un indirizzo che nessuno legge.
MAIL_GUIDA = 'info@daop.it'

# --- Le locandine ---------------------------------------------------------
# Chromium NON ridimensiona quando stampa: misurato il 24/08/2026, le stesse
# immagini disegnate a 35mm e a 120mm danno un PDF identico (8,4 MB in tutti e
# due i casi). Quindi la riduzione va fatta PRIMA, o la guida passa da 180 kB a
# quattro-cinque megabyte per un pollice di figurina.
#
# Pillow non e' una dipendenza nuova: il workflow gia' fa `pip install Pillow`
# per genera_miniature.py. Se pero' manca, le locandine si saltano e la guida
# esce lo stesso — la regola di tutto il resto di questo file.
#
# 480px e' la misura giusta per come le stampiamo: una miniatura da 32mm a
# 300dpi vuole ~380px, quindi 480 copre anche chi ingrandisce a schermo.
LOC_LATO = 480
LOC_QUALITA = 80
# Tetto duro sul totale incorporato. Non e' la paura di oggi (24 centri fanno
# ~1,2 MB) ma di un domani con duecento righe nel foglio: una guida da 15 MB
# non la scarica nessuno da un telefono in un paese, e il difetto si
# scoprirebbe solo dal fatto che i download smettono di crescere.
LOC_BUDGET = 3 * 1024 * 1024
# Quanto si aspetta una singola locandina. Corto apposta: sono ~24 richieste
# di fila dentro una run notturna, e una che non risponde non deve tenere in
# ostaggio le altre.
LOC_TIMEOUT = 12

MARK_START = '<!-- GUIDA-PDF:START'
MARK_END = '<!-- GUIDA-PDF:END -->'

# CSS di stampa. Sta qui e non in daop-system.css apposta: non serve a nessuna
# pagina del sito, serve solo dentro il documento temporaneo che si stampa.
# Metterlo nel CSS condiviso lo spedirebbe a ~360 pagine per usarlo in tre.
CSS_STAMPA = """
@page{size:A4;margin:16mm 14mm 18mm}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font:11pt/1.5 "DM Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
  Helvetica,Arial,sans-serif;color:#1c1c1e;margin:0}
h1{font-size:22pt;margin:0 0 2mm;line-height:1.15}
h2{font-size:13pt;margin:7mm 0 2mm;page-break-after:avoid}
h3{font-size:11.5pt;margin:5mm 0 1.5mm;page-break-after:avoid}
p,li{line-height:1.5;margin:0 0 2.5mm}
ul{padding-left:5mm;margin:0 0 3mm}
a{color:inherit;text-decoration:none}
.g-occhiello{font-size:9pt;letter-spacing:.08em;text-transform:uppercase;
  color:#0f766e;margin:0 0 1.5mm;font-weight:600}

/* --- Copertina -------------------------------------------------------
   Niente immagini (stanno su Supabase, vedi il docstring), quindi la
   copertina la fanno il tipo e il colore. La banda in alto e' l'unico
   elemento grafico e costa zero byte. */
.g-cover{page-break-after:always;display:flex;flex-direction:column;
  min-height:245mm}
.g-cover-banda{height:6mm;background:#0f766e;margin:-16mm -14mm 14mm}
.g-cover h1{font-size:34pt;line-height:1.05;margin:0 0 4mm;letter-spacing:-.5pt}
.g-cover .g-anno{color:#0f766e}
.g-cover-sub{font-size:13pt;line-height:1.4;color:#444;margin:0 0 10mm;
  max-width:120mm}
/* I numeri: dicono in una riga quanto e' grosso il lavoro che c'e' dentro,
   ed e' la sola prova di serieta' che una copertina senza foto puo' dare. */
.g-numeri{display:flex;gap:12mm;margin:0 0 12mm}
.g-num b{display:block;font-size:26pt;line-height:1;color:#0f766e}
.g-num span{font-size:9pt;text-transform:uppercase;letter-spacing:.06em;
  color:#666}
.g-quando{border-left:3px solid #0f766e;padding:1mm 0 1mm 5mm;margin:0 0 10mm;
  max-width:125mm}
.g-quando b{display:block;font-size:10pt;margin-bottom:1mm}
.g-quando p{font-size:10pt;color:#444;margin:0}
.g-cover-fondo{margin-top:auto;border-top:1px solid #ddd;padding-top:4mm;
  font-size:9.5pt;color:#666}
.g-cover-fondo b{color:#1c1c1e}

/* --- Indice ----------------------------------------------------------
   Senza numeri di pagina, e non per pigrizia: i numeri di pagina in un
   indice si fanno con target-counter() dei Paged Media, che Chromium NON
   implementa (li fanno Prince e WeasyPrint, cioe' una dipendenza in piu').
   Le voci pero' sono link veri: nel PDF diventano annotazioni /Link con
   destinazione interna, provato. Su carta restano un sommario, che e'
   quello che serve a decidere se leggere tutto o saltare. */
.g-toc{page-break-after:always}
.g-toc h2{font-size:16pt;margin:0 0 6mm;padding-bottom:3mm;
  border-bottom:2px solid #0f766e}
.g-toc ol{list-style:none;padding:0;margin:0;counter-reset:voce}
.g-toc li{padding:2.5mm 0;border-bottom:1px dotted #ccc}
.g-toc li.liv2{padding-left:9mm;border-bottom:0;padding-top:1mm;
  padding-bottom:1mm}
.g-toc a{display:block;font-size:11.5pt;font-weight:600}
.g-toc li.liv2 a{font-size:10pt;font-weight:400;color:#555}
.g-toc li.liv1 a::before{counter-increment:voce;content:counter(voce) ". ";
  color:#0f766e}
.g-toc-nota{margin-top:8mm;font-size:9.5pt;color:#666;border-left:3px solid #eee;
  padding-left:4mm}

/* --- Chiusura --------------------------------------------------------
   Ultima pagina intera. Le tre cose che deve fare: dire che questa e' una
   fotografia e va verificata, dire dove sta la versione sempre aggiornata,
   e aprire la porta a chi organizza — che e' l'unico invito commerciale
   del documento e sta qui, in fondo, come l'invito al canale sulle pagine. */
.g-fine{page-break-before:always}
.g-fine h2{font-size:16pt;margin:0 0 6mm;padding-bottom:3mm;
  border-bottom:2px solid #0f766e}
.g-fine h3{font-size:11.5pt;margin:6mm 0 1.5mm}
.g-box{border:1px solid #0f766e;border-radius:3mm;padding:5mm 6mm;margin:6mm 0}
.g-box h3{margin-top:0}
.g-firma{margin-top:10mm;padding-top:4mm;border-top:1px solid #ddd;
  font-size:9.5pt;color:#666}

.g-h-elenco{font-size:16pt;margin:0 0 5mm;padding-bottom:3mm;
  border-bottom:2px solid #0f766e}
/* Il titolo del paese. Deve staccare piu' di un h3 qualunque — e' l'appiglio
   con cui si sfoglia — e non deve mai restare solo in fondo a una pagina con
   le sue schede di la' (page-break-after:avoid arriva dalla regola h3). */
.g-comune{font-size:12.5pt;margin:7mm 0 2.5mm;padding:1.5mm 0 1.5mm 4mm;
  border-left:3px solid #0f766e;background:#f4f8f7;text-transform:uppercase;
  letter-spacing:.04em}
.g-comune:first-of-type{margin-top:2mm}
/* Ogni centro e' una scheda: non si spezza a meta' fra due pagine. */
.event-card,.ce-card{page-break-inside:avoid;break-inside:avoid;
  border:1px solid #e3e3e3;border-radius:3mm;padding:3mm 4mm;margin:0 0 3mm}
summary{list-style:none;font-weight:600;font-size:11pt;margin:0 0 1.5mm}
summary::-webkit-details-marker{display:none}
/* Il dettaglio di una scheda centri e' un <div class="ev-det" hidden>, non un
   <details>: `hidden` e' solo display:none messo dal browser, e su carta va
   annullato. Senza questa riga il PDF esce con le sole righe di intestazione,
   cioe' senza orari, costi e contatti — che sono la ragione per cui uno se la
   stampa. Il bottone .ev-row invece resta ma perde il suo aspetto da comando. */
.ev-det[hidden]{display:block !important}
.ev-row{font-weight:600;font-size:11pt}
/* Titolo e riga dei dati su due righe distinte. Online sono due span che si
   attaccano e il comune in testa alla seconda faceva da stacco; tolto quello
   (lo dice il titolo del gruppo) "Nuova Saves" e "dal 11 giugno" finivano
   appiccicati. Separarli e' comunque piu' leggibile su carta, dove non c'e'
   il colore a distinguerli. */
.ev-main{display:block}
.ev-name{display:block;font-size:11.5pt;font-weight:700;margin:0 0 1mm}
.ev-line{display:block;font-weight:400;font-size:9.5pt;color:#555;margin:0 0 2mm}
.ev-tags{display:block;margin:0 0 1mm}
/* Le pillole (prezzo, "Consigliato DAOP") restano etichette anche su carta:
   senza bordo diventavano una riga in grassetto sotto il titolo, cioe'
   sembravano un sottotitolo invece che un dato. */
.ev-pill{display:inline-block;font-size:8.5pt;font-weight:600;
  padding:.5mm 2mm;border:1px solid #cfe0dd;border-radius:1.5mm;
  color:#0f766e;background:#f4f8f7;margin:0 1.5mm 1mm 0}
.ev-row .ev-chev,.ev-chev{display:none !important}
dl{margin:0}
dt{font-weight:600;font-size:9pt;color:#555;margin-top:1.5mm}
dd{margin:0 0 1mm}
/* Quello che in una guida stampata non serve, o che non puo' funzionare:
   i comandi (non si clicca su un foglio), le immagini (vedi il docstring),
   i blocchi che rimandano ad altre pagine del sito. */
.ev-toolbar,.ev-viewbar,.events-count,.events-empty,.ce-actions,.ce-guidapdf,
.eco,.ev-canale,.ev-geo,svg,input,select,.co-loc
{display:none !important}
/* La locandina. Sta a destra e il testo le gira intorno: messa a tutta
   larghezza farebbe una scheda per pagina e la guida diventerebbe uno
   sfogliabile invece che una cosa da consultare. 32mm e' la misura in cui si
   riconosce il manifesto senza doverlo leggere — leggerlo e' compito dei dati
   qui accanto, che ci sono tutti.
   Il segnaposto (.is-ph, il sole di chi non ha locandina) sparisce: su carta
   un buco decorato e' peggio di un buco. */
.ev-thumb{float:right;width:32mm;margin:0 0 3mm 5mm;border-radius:2mm;
  border:1px solid #e3e3e3}
.ev-thumb.is-ph{display:none !important}
.event-card{overflow:hidden}
/* I tre link in fondo a una scheda non valgono uguale su carta. "Come arrivare"
   e "Locandina" sono gesti (aprono mappe e un'immagine): su un foglio sono due
   parole morte e si tolgono. "Informazioni e iscrizioni" e' invece l'unico modo
   che ha un genitore di arrivare a chi organizza — il sito non compare da
   nessun'altra parte nella scheda, mentre telefono e mail si' — quindi resta e
   l'indirizzo si STAMPA: un link su carta senza la sua URL non e' un link. */
.event-act[href*="google.com/maps"],.event-act[href*="supabase.co"]
{display:none !important}
.event-act{display:block;font-size:9pt;margin-top:2mm;color:#0f766e}
.event-act::after{content:" — " attr(href);color:#666;word-break:break-all}
"""


def chromium():
    for c in CANDIDATI:
        if c and os.path.exists(c):
            return c
    trovato = shutil.which('chromium') or shutil.which('google-chrome')
    return trovato


def stato():
    """Le stagioni con del materiale, scritte da genera_centri.py."""
    try:
        with open(STATO_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def estrai(html):
    """Il pezzo di pagina che va nella guida, fra i due marker.

    Per stringa e non con un parser: i marker sono l'idioma gia' usato in
    eventi.html, non si annidano e li scrive un generatore, non una persona.
    Se non ci sono, torna None e la guida non si fa — meglio nessuna guida che
    una guida con dentro la nav e il footer."""
    i = html.find(MARK_START)
    j = html.find(MARK_END)
    if i < 0 or j < 0 or j < i:
        return None
    # Il commento di apertura e' multiriga: si taglia dopo la sua chiusura.
    k = html.find('-->', i)
    if k < 0 or k > j:
        return None
    return html[k + 3:j].strip()


def _scarica(url):
    """I byte di una locandina, o None. Non alza mai."""
    try:
        if url.startswith('file://') or url.startswith('/'):
            # Comodo per provare in locale senza rete.
            percorso = url[7:] if url.startswith('file://') else url
            with open(percorso, 'rb') as f:
                return f.read()
        req = urllib.request.Request(url, headers={'User-Agent': 'daop-guide/1'})
        with urllib.request.urlopen(req, timeout=LOC_TIMEOUT) as r:
            return r.read()
    except Exception:
        return None


def _riduci(dati):
    """Da locandina a miniatura per la stampa, come data URI. None se non si
    puo' — e non si puo' succede spesso: Pillow assente, immagine corrotta,
    formato che non conosciamo. In tutti quei casi la scheda esce senza figura,
    che e' molto meglio di un riquadro grigio."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(io.BytesIO(dati))
        im.thumbnail((LOC_LATO, LOC_LATO))
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=LOC_QUALITA, optimize=True)
        return base64.b64encode(buf.getvalue()).decode('ascii')
    except Exception:
        return None


def locandine(corpo):
    """Incorpora le locandine come data URI e toglie tutte le altre immagini.

    Perche' incorporate e non linkate: un PDF che punta a un'immagine in rete
    la ricarica ogni volta che si apre, cioe' consuma banda Supabase per
    sempre e mostra un buco a chi lo legge offline — che e' meta' del motivo
    per cui uno si scarica una guida.

    Perche' si toglie tutto il resto: il logo e le icone sono decorazione di
    pagina, e in un documento che ha gia' la sua copertina fanno solo rumore.

    Il tetto (LOC_BUDGET) si controlla man mano, non alla fine: superarlo e poi
    buttare via vorrebbe dire aver gia' scaricato tutto. Le prime schede hanno
    la figura e le ultime no, il che e' asimmetrico ma onesto — e il log lo
    dice, cosi' se un giorno succede si vede invece di scoprirlo dal peso."""
    urls = re.findall(r'<img[^>]*class="ev-thumb"[^>]*src="([^"]+)"', corpo)
    fatte, saltate, peso = {}, 0, 0
    for u in dict.fromkeys(urls):          # senza ripetere la stessa due volte
        if peso >= LOC_BUDGET:
            saltate += 1
            continue
        dati = _scarica(u)
        mini = _riduci(dati) if dati else None
        if not mini:
            saltate += 1
            continue
        fatte[u] = mini
        peso += len(mini)
    if fatte or saltate:
        print(f"[genera_pdf]   locandine: {len(fatte)} incorporate "
              f"({peso // 1024} kB), {saltate} saltate")

    def sostituisci(m):
        tag = m.group(0)
        src = re.search(r'src="([^"]+)"', tag)
        if 'ev-thumb' in tag and src and src.group(1) in fatte:
            dato = fatte[src.group(1)]
            return re.sub(r'src="[^"]+"', f'src="data:image/jpeg;base64,{dato}"',
                          tag)
        return ''      # tutte le altre immagini, e le locandine non riuscite

    corpo = re.sub(r'<img\b[^>]*>', sostituisci, corpo)

    # La locandina esce dal <button> e diventa figlia della scheda.
    #
    # Non e' estetica: un <button> non lascia che il testo giri intorno a un
    # float al suo interno — si comporta da contenitore chiuso — quindi la riga
    # del titolo diventava alta quanto l'immagine e sotto restava un buco di
    # tre centimetri. Spostata di un livello, il float funziona e la
    # descrizione le gira accanto. Online il bottone deve restare com'e' (e'
    # il comando che apre la scheda), quindi la modifica sta qui e non nel
    # generatore della pagina.
    # Due trasformazioni di impaginazione, e vanno insieme.
    #
    # 1. La locandina esce dal <button> e diventa figlia della scheda: un
    #    <button> non lascia che il testo giri intorno a un float al suo
    #    interno, quindi la riga del titolo diventava alta quanto l'immagine e
    #    sotto restava un buco di tre centimetri.
    # 2. Il <button> diventa uno <span>. Da solo il punto 1 peggiora le cose:
    #    un bottone e' una scatola atomica, non si spezza, e se non ci sta
    #    accanto al float scende sotto — il titolo finiva sotto la locandina.
    #    Uno <span> e' testo vero e gira intorno all'immagine come deve.
    #    Su carta un comando che apre e chiude non ha nessun senso comunque.
    #
    # Online il bottone resta quello che e' (e' il comando che apre la scheda):
    # queste due righe valgono solo per il documento che si stampa.
    corpo = re.sub(r'(<h4 class="ev-h"><button[^>]*>)\s*(<img class="ev-thumb"[^>]*>)',
                   r'\2\1', corpo)
    corpo = re.sub(r'<button class="ev-row"[^>]*>', '<span class="ev-row">', corpo)
    return corpo.replace('</button></h4>', '</span></h4>')


def _chiude_div(html, i):
    """Indice subito dopo il </div> che chiude il <div> che comincia a `i`.

    Serve contare l'annidamento e non basta cercare il primo </div>: dentro la
    lista ogni scheda ha il suo <div class="ev-det">. Nemmeno l'ULTIMO
    </article> va bene, ed e' il difetto che questa funzione ha avuto per
    dieci minuti: sotto la lista dei centri aperti c'e' quella delle edizioni
    CONCLUSE, quindi il taglio arrivava fin li' e otto centri finiti venivano
    presentati come se fossero aperti — con l'avviso che lo diceva cancellato
    insieme al resto. Su una pagina si correggerebbe stanotte; in un PDF che
    gira, no."""
    j = html.find('>', i)
    if j < 0:
        return -1
    j += 1
    liv = 1
    while liv:
        apre = html.find('<div', j)
        chiude = html.find('</div>', j)
        if chiude < 0:
            return -1
        if 0 <= apre < chiude:
            liv += 1
            j = apre + 4
        else:
            liv -= 1
            j = chiude + 6
    return j


def raggruppa(corpo):
    """Spezza l'elenco per comune, con un titolo per paese.

    Online l'elenco e' piatto e si filtra con la tendina: e' giusto li', dove
    un filtro costa un tocco. Su carta non c'e' nessuna tendina, e una lista
    unica di ventiquattro schede si scorre tutta ogni volta che cerchi il tuo
    paese. Raggruppare e' il modo in cui la stessa domanda si risolve senza
    interazione — ed e' anche come e' fatta luoghi.html, che quel problema
    l'aveva gia' risolto cosi'.

    **L'ordine resta alfabetico, dentro e fuori i gruppi.** Non e' pigrizia:
    e' la regola di #come-ordiniamo, che qui e' piu' facile da rompere perche'
    su carta un gruppo in cima sembra una classifica. Nessun comune passa
    avanti per nessuna ragione.

    Se qualcosa non torna — nessuna scheda, nessun comune leggibile — si
    restituisce il corpo com'era. Un raggruppamento a meta' e' peggio di
    nessun raggruppamento."""
    # I confini della lista NON si prendono con un match annidato: le schede
    # contengono a loro volta dei <div> (il dettaglio), quindi un `.*?</div>`
    # si ferma al primo di quelli e taglia via ventitre schede su ventiquattro.
    # E' il difetto che questa funzione ha avuto per cinque minuti.
    # Si ancora invece a due punti certi: il div che apre la lista, e il
    # </div> che segue l'ultima scheda.
    i = corpo.find('<div class="events-list" id="ce-active">')
    k = _chiude_div(corpo, i)
    if k < 0:
        return corpo
    # Cintura: la sezione delle edizioni CONCLUSE deve restare fuori dal
    # taglio. Il matcher qui sopra lo garantisce gia' per costruzione, ma il
    # difetto che questo controllo descrive e' costato otto centri finiti
    # presentati come aperti, e su un PDF non lo si corregge dopo. Se un
    # domani la struttura della pagina cambia, meglio nessun raggruppamento
    # che un raggruppamento che mente.
    passati = corpo.find('<h2 class="ce-past-h"')
    if 0 <= passati < k:
        print("[genera_pdf]   raggruppamento saltato: la sezione delle "
              "edizioni concluse cadrebbe dentro l'elenco")
        return corpo
    schede = re.findall(r'<article class="event-card".*?</article>',
                        corpo[i:k], re.S)
    if len(schede) < 2:
        return corpo

    gruppi = {}
    for sch in schede:
        # Il nome leggibile sta in testa alla riga di contesto ("Ovada (AL) ·
        # dal 1 luglio..."), non in data-city, che e' uno slug: "castell-alfero"
        # stampato come titolo di gruppo sarebbe brutto e sbagliato.
        riga = re.search(r'<span class="ev-line">([^·<]+)', sch)
        nome = riga.group(1).strip() if riga else ''
        if not nome:
            return corpo
        gruppi.setdefault(nome, []).append(sch)

    fuori = []
    for nome in sorted(gruppi, key=lambda x: x.lower()):
        # Dentro il gruppo il comune non si ripete su ogni riga: il titolo
        # sopra lo dice gia'. E' la regola gia' scritta per le pagine comune
        # ("dentro una manifestazione uniforme ripetere SAGRA & FESTA su
        # cinque righe e' rumore"), e qui vale il doppio perche' su carta lo
        # spazio della riga e' conteso dalla locandina.
        # Si toglie SOLO se dopo resta qualcosa: una riga che porta il solo
        # comune diventerebbe vuota, e una riga vuota e' peggio di una
        # ripetizione.
        pulite = [re.sub(r'(<span class="ev-line">)' + re.escape(nome) + r'\s*·\s*',
                         r'\1', sch)
                  for sch in gruppi[nome]]
        fuori.append(f'<h3 class="g-comune">{nome}</h3>')
        fuori.append('<div class="events-list">'
                     + "\n".join(pulite) + '</div>')
    return corpo[:i] + "\n".join(fuori) + corpo[k:]


def numeri(corpo):
    """Quanti centri, quanti comuni, quante province — contati sul corpo vero.

    Si contano qui e non si leggono da data/conteggi.json apposta: quel file
    dice quanti ne ha il sito, questo deve dire quanti ne ha IL PDF. Se un
    giorno i due numeri divergono (un filtro, una potatura), la copertina deve
    restare d'accordo con le pagine che ha dietro, non col registro."""
    n = corpo.count('class="event-card"')
    comuni = len(set(re.findall(r'data-city="([^"]+)"', corpo)))
    prov = len(set(re.findall(r'data-province="([^"]+)"', corpo)))
    return n, comuni, prov


def sezioni(corpo):
    """Mette un id su ogni h2/h3 del corpo e torna l'indice da stampare.

    Gli id li mettiamo qui e non nella pagina: servono solo al PDF, e
    aggiungerli in pagina vorrebbe dire un diff su tutte le pagine centri per
    una cosa che online non si vede. Se un'intestazione ha gia' un id suo, si
    rispetta — un id inventato sopra uno esistente romperebbe un'ancora che
    qualcuno potrebbe avere in giro."""
    voci = []
    n = [0]

    def marca(m):
        liv, attr, testo = m.group(1), m.group(2), m.group(3)
        gia = re.search(r'\sid="([^"]+)"', attr)
        if gia:
            ident = gia.group(1)
        else:
            n[0] += 1
            ident = f'g-s{n[0]}'
            attr = f' id="{ident}"' + attr
        # Il testo dell'intestazione puo' contenere marcatura (un <em>): per
        # l'indice serve il testo nudo.
        pulito = re.sub(r'<[^>]+>', '', testo).strip()
        if pulito:
            voci.append((int(liv), ident, pulito))
        return f'<h{liv}{attr}>{testo}</h{liv}>'

    corpo = re.sub(r'<h([23])([^>]*)>(.*?)</h\1>', marca, corpo, flags=re.S)
    return corpo, voci


def copertina(cfg, anno, oggi, conta):
    n, comuni, prov = conta
    plurale = 'centri' if n != 1 else 'centro'
    return f"""<section class="g-cover">
  <div class="g-cover-banda"></div>
  <p class="g-occhiello">Guida DAOP</p>
  <h1>{cfg['titolo'].replace('Guida ai ', '').capitalize()}
    <span class="g-anno">{anno}</span></h1>
  <p class="g-cover-sub">{cfg['sottotitolo']}</p>
  <div class="g-numeri">
    <div class="g-num"><b>{n}</b><span>{plurale}</span></div>
    <div class="g-num"><b>{comuni}</b><span>comuni</span></div>
    <div class="g-num"><b>{prov}</b><span>province</span></div>
  </div>
  <div class="g-quando">
    <b>Quando ci si iscrive</b>
    <p>{cfg['quando']}</p>
  </div>
  <div class="g-cover-fondo">
    <p><b>DAOP</b> — l'agenda delle famiglie in provincia di Alessandria, Asti
    e Cuneo. Aggiornata al {oggi.strftime('%d/%m/%Y')} · daop.it</p>
  </div>
</section>"""


def indice(voci):
    """L'indice. Torna stringa vuota se non c'e' niente da indicizzare: due
    voci non sono un indice, sono una pagina sprecata."""
    if len(voci) < 3:
        return ''
    righe = []
    for liv, ident, testo in voci:
        cls = 'liv1' if liv == 2 else 'liv2'
        righe.append(f'    <li class="{cls}"><a href="#{ident}">{testo}</a></li>')
    return ("""<section class="g-toc">
  <h2>Cosa c'è dentro</h2>
  <ol>
""" + "\n".join(righe) + """
  </ol>
  <p class="g-toc-nota">Le voci sono cliccabili se leggi questa guida sul
  telefono o sul computer. L'elenco dei centri è in ordine alfabetico: la
  posizione non si compra, e chi paga uno spazio su DAOP non passa avanti
  agli altri.</p>
</section>""")


def chiusura(cfg, oggi, pagina):
    return f"""<section class="g-fine">
  <h2>Prima di chiudere</h2>

  <h3>Questa guida è una fotografia</h3>
  <p>È stata generata il {oggi.strftime('%d/%m/%Y')} dai dati che i gestori ci
  hanno comunicato. Date, orari e tariffe cambiano: <strong>prima di contare su
  un posto, verifica sempre con chi organizza</strong>, ai recapiti che trovi in
  ogni scheda.</p>

  <h3>La versione sempre aggiornata</h3>
  <p>L'elenco online si riscrive ogni notte, e questa guida con lui. Se l'hai
  scaricata qualche settimana fa, la copia più recente è sempre qui:
  <strong>daop.it/{pagina}</strong></p>

  <div class="g-box">
    <h3>Organizzi un centro e non sei in questa guida?</h3>
    <p>L'edizione dell'anno prossimo si chiude prima che aprano le iscrizioni,
    perché è allora che i genitori scelgono. Scrivici a
    <strong>{MAIL_GUIDA}</strong> con date, età, orari e costi: entri
    nell'elenco online subito e nella guida alla prima edizione utile.</p>
  </div>

  <h3>Cos'è DAOP</h3>
  <p>Un'associazione che tiene l'agenda di quello che c'è da fare con i bambini
  in provincia di Alessandria, Asti e Cuneo: sagre, feste, laboratori,
  spettacoli, centri estivi e corsi. Ogni proposta viene guardata una per una
  prima di finire in elenco — non è un aggregatore automatico.</p>

  <div class="g-firma">
    <p><strong>daop.it</strong> — sagre ed eventi per famiglie, giorno per
    giorno.</p>
  </div>
</section>"""


def documento(chiave, cfg, corpo, anno, oggi):
    """Il file temporaneo che Chromium stampa.

    Due cose si fanno per stringa, e vale la pena sapere perche'.

    **I <details> si aprono qui e non con uno script.** In pagina sono chiusi
    apposta (una scheda per riga, si apre quella che interessa); su carta non si
    apre niente, quindi quello che resta chiuso e' semplicemente perso. Un
    `replace` fa la stessa cosa prima ancora che il browser parta. I centri non
    ne hanno — il loro dettaglio e' un <div hidden>, che riapre il CSS di stampa
    — ma i corsi si', ed e' la stessa riga per tutti e due.

    **Le <img> si TOLGONO, non si nascondono.** `display:none` non impedisce a
    Chromium di scaricare l'immagine: le locandine stanno su Supabase, piano
    gratuito con un tetto di banda mensile, e una ventina di richieste a ogni
    stampa notturna sono esattamente il conto che ha gia' spento le locandine
    una volta. Toglierle dall'HTML e' l'unico modo di garantire zero richieste,
    e ha il vantaggio di non dipendere dalla rete per fare un PDF."""
    corpo = corpo.replace('<details', '<details open')
    corpo = locandine(corpo)
    conta = numeri(corpo)
    corpo = raggruppa(corpo)

    # L'intestazione dell'elenco non esiste online — la pagina non ne ha
    # bisogno, l'elenco e' la prima cosa che si vede. Su carta invece serve:
    # senza, l'indice non puo' nominare la meta' piu' lunga del documento. E'
    # un'etichetta di impaginazione, come la copertina: non aggiunge un dato
    # che il sito non pubblichi.
    corpo = ('<h2 id="g-elenco" class="g-h-elenco">I centri, uno per uno</h2>\n'
             + corpo)
    corpo, voci = sezioni(corpo)

    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>{cfg['titolo']} {anno} — DAOP</title>
<style>{CSS_STAMPA}</style></head><body>
{copertina(cfg, anno, oggi, conta)}
{indice(voci)}
{corpo}
{chiusura(cfg, oggi, cfg['pagina'])}
</body></html>
"""


def stampa(exe, sorgente, destinazione):
    """Chromium headless. Torna True se il PDF e' uscito e ha senso.

    Il codice di uscita non basta: Chromium esce 0 anche quando scrive un file
    vuoto o troncato. Si controlla che cominci con %PDF e che non sia ridicolo —
    sotto i 2 kB non c'e' dentro una guida, c'e' dentro un errore."""
    cmd = [
        exe, '--headless', '--disable-gpu', '--no-sandbox',
        '--no-pdf-header-footer', '--run-all-compositor-stages-before-draw',
        '--virtual-time-budget=5000',
        f'--print-to-pdf={destinazione}', sorgente,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"[genera_pdf] Chromium non ha risposto: {e}")
        return False
    if not os.path.exists(destinazione):
        return False
    with open(destinazione, 'rb') as f:
        testa = f.read(5)
    if testa[:4] != b'%PDF' or os.path.getsize(destinazione) < 2048:
        os.remove(destinazione)
        return False
    return True


def una_guida(chiave, cfg, st, exe, oggi):
    """Torna la voce per data/guide.json, o None se la guida non si fa."""
    pagina = os.path.join(ROOT, cfg['pagina'])
    if not os.path.exists(pagina):
        print(f"[genera_pdf] {chiave}: {cfg['pagina']} non c'e', salto")
        return None

    # Senza materiale non nasce nessuna guida. 'inizio' e' None quando nel
    # foglio non c'e' una sola data per quella stagione: una pagina in quello
    # stato dice "iscrizioni non ancora aperte", ed e' una cosa giusta da dire
    # su una pagina e una cosa che non ha senso mandare in giro come PDF.
    inizio = (st.get(chiave) or {}).get('inizio')
    if not inizio:
        print(f"[genera_pdf] {chiave}: nessun centro con date, niente guida")
        return None
    anno = inizio[:4]

    corpo = estrai(open(pagina, encoding='utf-8').read())
    if corpo is None:
        print(f"[genera_pdf] {chiave}: marker GUIDA-PDF assenti in "
              f"{cfg['pagina']}, salto")
        return None

    nome = f"{chiave}-{anno}.pdf"
    dest = os.path.join(DIR_GUIDE, nome)
    os.makedirs(DIR_GUIDE, exist_ok=True)

    if not exe:
        # Senza Chromium non si svuota niente: se il PDF dell'altra volta c'e',
        # resta e si continua a linkarlo.
        if os.path.exists(dest):
            print(f"[genera_pdf] {chiave}: Chromium assente, tengo {nome}")
            return {'file': f'guide/{nome}', 'anno': anno,
                    'byte': os.path.getsize(dest)}
        print(f"[genera_pdf] {chiave}: Chromium assente e nessun PDF, salto")
        return None

    with tempfile.NamedTemporaryFile('w', suffix='.html', encoding='utf-8',
                                     delete=False) as f:
        f.write(documento(chiave, cfg, corpo, anno, oggi))
        tmp = f.name
    # Si stampa su un file a parte e si sostituisce solo a cosa fatta: una
    # stampa interrotta a meta' non deve lasciare in guide/ un PDF troncato che
    # la pagina continua a linkare.
    parziale = dest + '.tmp'
    try:
        ok = stampa(exe, f'file://{tmp}', parziale)
    finally:
        os.unlink(tmp)
    if not ok:
        if os.path.exists(parziale):
            os.remove(parziale)
        if os.path.exists(dest):
            print(f"[genera_pdf] {chiave}: stampa fallita, tengo {nome}")
            return {'file': f'guide/{nome}', 'anno': anno,
                    'byte': os.path.getsize(dest)}
        print(f"[genera_pdf] {chiave}: stampa fallita e nessun PDF, salto")
        return None

    vecchio = os.path.getsize(dest) if os.path.exists(dest) else 0
    os.replace(parziale, dest)
    peso = os.path.getsize(dest)
    stato_txt = 'invariata' if peso == vecchio else 'scritta'
    print(f"[genera_pdf] {nome}: {stato_txt} ({peso // 1024} kB)")
    return {'file': f'guide/{nome}', 'anno': anno, 'byte': peso}


def pota(tenute):
    """Le edizioni vecchie restano, quelle di un anno che non esiste piu' no.

    Un PDF datato invecchia bene — 'centri-estivi-2026.pdf' e' onesto anche nel
    2028 — quindi NON si cancella niente per anzianita'. Si toglie solo un
    file rimasto di una stagione che non e' piu' nell'insieme GUIDE, che
    altrimenti resterebbe in giro senza che nessuna pagina lo nomini."""
    for f in sorted(glob.glob(os.path.join(DIR_GUIDE, '*.pdf'))):
        chiave = os.path.basename(f).rsplit('-', 1)[0]
        if chiave not in GUIDE:
            os.remove(f)
            print(f"[genera_pdf] tolto {os.path.basename(f)}: stagione ignota")
        elif os.path.basename(f) not in tenute:
            print(f"[genera_pdf] {os.path.basename(f)}: edizione vecchia, resta")


def main(argv):
    chiavi = argv or list(GUIDE)
    ignote = [k for k in chiavi if k not in GUIDE]
    if ignote:
        raise SystemExit(f"[genera_pdf] guida sconosciuta: {', '.join(ignote)}")

    exe = chromium()
    if not exe:
        print("[genera_pdf] Chromium non trovato. Con CHROMIUM_PATH=/percorso "
              "si indica a mano; senza, le guide gia' fatte restano dove sono.")

    oggi = datetime.date.today()
    st = stato()
    registro = {}
    tenute = set()
    for chiave in chiavi:
        voce = una_guida(chiave, GUIDE[chiave], st, exe, oggi)
        if voce:
            registro[chiave] = voce
            tenute.add(os.path.basename(voce['file']))
    if os.path.isdir(DIR_GUIDE):
        pota(tenute)

    # Scritto sempre, anche vuoto: un registro assente e uno vuoto vogliono dire
    # la stessa cosa a genera_centri.py (nessun link), ma il file vuoto dice che
    # questo script e' girato davvero.
    os.makedirs(os.path.dirname(GUIDE_PATH), exist_ok=True)
    with open(GUIDE_PATH, 'w', encoding='utf-8') as f:
        json.dump(registro, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    print(f"[genera_pdf] data/guide.json: {len(registro)} guide")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
