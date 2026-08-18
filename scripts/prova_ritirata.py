#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla la SCHEDA RITIRATA: cosa esce quando una riga sparisce dal foglio
prima della sua data.

PERCHE' ESISTE (18/08/2026): Giovanni ha segnalato in agenda un "Pranzo Sociale"
preso dal programma della Festa di San Bartolomeo di Rocca de' Baldi - un pranzo
per soci in un ristorante di un altro paese, che non doveva starci. La riga e'
stata cancellata dal foglio, ma il link della pagina evento funzionava ancora, e
la pagina continuava a dichiararsi "Scheda verificata da DAOP - Ultimo controllo:
18 agosto 2026", con Event nei dati strutturati e il bottone "Aggiungi al
calendario". Il noindex la nascondeva a Google, non a chi aveva il link.

Da qui il TIMBRO rec['ritirata'] nel registro: la pagina resta (i permalink non
si rompono) ma smette di descrivere un appuntamento. Le quattro cose che questo
script tiene ferme, e che a occhio non si vedono:
  1. la resa: niente Event, niente firma di verifica, niente calendario, niente
     locandina, niente orario/indirizzo/prezzo;
  2. la PERMANENZA: passata la data la scheda ritirata NON deve diventare
     "Edizione conclusa - questa edizione si e' svolta...", che dichiarerebbe
     avvenuto un appuntamento mai esistito;
  3. il rientro: se la riga torna sul foglio il timbro si toglie da solo (e' il
     modo di rimediare a una ritirata sbagliata);
  4. la rete di sicurezza: una run che legge il foglio a meta' non deve timbrare
     mezzo sito - il timbro e' permanente e a mano non si torna indietro.

Uso:
    python scripts/prova_ritirata.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca il sito:
registro e pagine di prova vanno in una cartella temporanea.
"""
import datetime
import io
import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as g

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = g.ROOT
CAVIA_PREFERITA = "pranzo-sociale-piozzo"   # il caso vero; se non c'e' piu', se ne prende un'altra

reg_vero = json.load(open(os.path.join(ROOT, "data", "pagine-evento.json"), encoding="utf-8"))
if not reg_vero:
    print("registro pagine-evento vuoto: niente da provare")
    sys.exit(0)

OUT = os.path.join(tempfile.gettempdir(), "daop_prova_ritirata")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
g.PAGINE_DIR = os.path.join(OUT, "eventi")
g.REGISTRO_PATH = os.path.join(OUT, "registro.json")

css, nav, foot = g._guscio()
OGGI = datetime.date.today()
esito = True

CAVIA = CAVIA_PREFERITA if CAVIA_PREFERITA in reg_vero else next(iter(reg_vero))
tutti = list(reg_vero)[:60]
if CAVIA not in tutti:
    tutti.append(CAVIA)
altri = [s for s in tutti if s != CAVIA]


def come_evento(rec):
    """Il record del registro rimesso nella forma in cui arriva dal foglio."""
    e = {k: v for k, v in rec.items()
         if k not in ("first_seen", "last_seen", "updated", "slug", "ritirata")}
    for k in ("d_start", "d_end"):
        e[k] = datetime.date.fromisoformat(rec[k])
    return e


def scrivi_registro(slugs, ritirate=()):
    reg = {s: dict(reg_vero[s]) for s in slugs}
    for s in ritirate:
        reg[s]["ritirata"] = OGGI.isoformat()
    json.dump(reg, open(g.REGISTRO_PATH, "w", encoding="utf-8"), ensure_ascii=False)


def gira(slugs_sul_foglio):
    """scrivi_pagine() come la chiama il generatore, ma zitta."""
    vero = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return g.scrivi_pagine([come_evento(reg_vero[s]) for s in slugs_sul_foglio], hub=None)
    finally:
        sys.stdout = vero


def registro():
    return json.load(open(g.REGISTRO_PATH, encoding="utf-8"))


def leggi(slug):
    """La pagina generata, senza il CSS inline: dentro il CSS ci sono commenti
    che citano "Come arrivare" e la classe .ev-loc, e cercarli nel file intero
    darebbe falsi allarmi."""
    p = os.path.join(g.PAGINE_DIR, f"{slug}.html")
    html = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return re.sub(r"<style>.*?</style>", "", html, flags=re.S)


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


print("=== 1) run sana, la riga non e' piu' sul foglio -> timbro + pagina ritirata ===")
scrivi_registro(tutti)
sitemap = gira(altri)
h = leggi(CAVIA)
ok("timbro 'ritirata' scritto nel registro", registro()[CAVIA].get("ritirata"))
ok("box 'Scheda ritirata'", "<strong>Scheda ritirata</strong>" in h)
ok("titolo 'Scheda ritirata:'", "<title>Scheda ritirata:" in h)
ok("firma 'Scheda ritirata da DAOP'", "Scheda ritirata da DAOP" in h)
ok("mailto per la correzione", "mailto:info@daop.it" in h)
ok("niente 'Aggiungi al calendario'", "Aggiungi al calendario" not in h)
ok("niente 'Come arrivare'", "Come arrivare" not in h)
ok("niente 'Scheda verificata da DAOP'", "Scheda verificata da DAOP" not in h)
ok("niente 'Ultimo controllo'", "Ultimo controllo" not in h)
ok("niente locandina", 'class="ev-loc"' not in h)
ok("niente riga 'Dove:'", "<strong>Dove:</strong>" not in h)
ok("noindex", 'content="noindex, follow"' in h)
ok("fuori dalla sitemap", CAVIA not in sitemap)
grafo = json.loads(re.search(r'ld\+json">\n(.*?)\n</script>', h, re.S).group(1))["@graph"]
nodi = [n.get("@type") for n in grafo]
ok(f"dati strutturati senza Event: {nodi}", "Event" not in nodi)
ok("niente lastReviewed / reviewedBy", "lastReviewed" not in h and "reviewedBy" not in h)
ok("le altre pagine restano normali", "Scheda verificata da DAOP" in leggi(altri[0]))

print("\n=== 2) passata la data, la ritirata NON diventa 'edizione conclusa' ===")
rec = dict(reg_vero[CAVIA], ritirata=OGGI.isoformat(), slug=CAVIA)
rec["d_start"] = rec["d_end"] = (OGGI - datetime.timedelta(days=30)).isoformat()
h = re.sub(r"<style>.*?</style>", "",
           g.render_pagina(rec, css, nav, foot, OGGI, orfano=False), flags=re.S)
ok("resta 'Scheda ritirata'", "<strong>Scheda ritirata</strong>" in h)
ok("niente 'Edizione conclusa'", "Edizione conclusa" not in h)
ok("niente firma di verifica", "Scheda verificata da DAOP" not in h)
ok("niente Event nei dati strutturati", '"@type": "Event"' not in h)

print("\n=== 3) la riga torna sul foglio -> il timbro si toglie ===")
scrivi_registro(tutti, ritirate=[CAVIA])
gira(tutti)
ok("timbro rimosso", not registro()[CAVIA].get("ritirata"))
ok("pagina di nuovo verificata", "Scheda verificata da DAOP" in leggi(CAVIA))

print(f"\n=== 4) run cieca (3 eventi su {len(tutti)}): nessun timbro, nessuna ritirata ===")
scrivi_registro(tutti)
gira(altri[:3])
timbrate = [s for s, r in registro().items() if r.get("ritirata")]
a_video = [s for s in tutti if "<strong>Scheda ritirata</strong>" in leggi(s)]
ok(f"zero timbri (trovati {len(timbrate)})", not timbrate)
ok(f"zero pagine ritirate a video (trovate {len(a_video)})", not a_video)
ok("la cavia resta una pagina normale, solo in noindex",
   'content="noindex, follow"' in leggi(CAVIA)
   and "Scheda verificata da DAOP" in leggi(CAVIA))

shutil.rmtree(OUT, ignore_errors=True)
print("\nESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
