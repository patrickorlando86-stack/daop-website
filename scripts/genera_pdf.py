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

import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

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
    },
    'invernali': {
        'pagina': 'centri-invernali.html',
        'titolo': 'Guida ai centri invernali',
        'occhiello': 'Centri invernali e natalizi in provincia di Alessandria, Asti e Cuneo',
    },
    'pasquali': {
        'pagina': 'centri-pasquali.html',
        'titolo': 'Guida ai centri pasquali',
        'occhiello': 'Centri pasquali in provincia di Alessandria, Asti e Cuneo',
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
.g-testa{border-bottom:2px solid #0f766e;padding-bottom:4mm;margin-bottom:6mm}
.g-occhiello{font-size:9pt;letter-spacing:.08em;text-transform:uppercase;
  color:#0f766e;margin:0 0 1.5mm;font-weight:600}
.g-sotto{font-size:9.5pt;color:#555;margin:2mm 0 0}
.g-piede{margin-top:8mm;padding-top:3mm;border-top:1px solid #ddd;
  font-size:8.5pt;color:#666}
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
.ev-row{background:none;border:0;padding:0;text-align:left;font:inherit;
  font-weight:600;font-size:11pt;color:inherit;width:100%}
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
    corpo = re.sub(r'<img\b[^>]*>', '', corpo)
    quando = oggi.strftime('%d/%m/%Y')
    return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="utf-8">
<title>{cfg['titolo']} {anno} — DAOP</title>
<style>{CSS_STAMPA}</style></head><body>
<div class="g-testa">
  <p class="g-occhiello">{cfg['occhiello']}</p>
  <h1>{cfg['titolo']} {anno}</h1>
  <p class="g-sotto">Guida DAOP · aggiornata al {quando} · daop.it</p>
</div>
{corpo}
<div class="g-piede">
  <p><strong>Le date e i prezzi cambiano.</strong> Questa guida è
  un'istantanea del {quando}: prima di contare su un posto, verifica sempre con
  chi organizza. L'elenco aggiornato è su daop.it.</p>
  <p>DAOP — l'agenda delle famiglie in provincia di Alessandria, Asti e Cuneo.</p>
</div>
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
