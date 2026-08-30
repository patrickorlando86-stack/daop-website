#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla la SCHEDA SPOSTATA: cosa esce quando una correzione sul foglio cambia
l'INDIRIZZO della pagina invece del suo contenuto.

PERCHE' ESISTE (30/08/2026): la "27a Sagra dello Gnocco" era segnata a
Mombarcaro ed e' a Bricco de' Faule, frazione di CHERASCO. Corretto il comune e
rigenerato il sito, la pagina "non si era aggiornata": lo slug contiene il
comune, quindi la correzione non ha modificato la scheda, ne ha fatta nascere
una nuova all'indirizzo giusto e ha lasciato la vecchia dov'era - con dentro il
dato sbagliato e una mappa a 40 km da dove si mangia. Fuori indice, ma
perfettamente leggibile da chiunque avesse il link: cioe' proprio le persone a
cui la correzione serviva.

Le sei cose che questo script tiene ferme, e che a occhio non si vedono:
  1. il RICONOSCIMENTO: stesse date piu' stesso nome (o stessa riga di foglio)
     sotto un altro slug non e' una scheda sparita, e' una scheda spostata;
  2. la RESA: la pagina vecchia diventa un cartello - refresh, canonical sulla
     nuova, e nessun dato vecchio in pagina;
  3. la PRUDENZA: se i candidati sono piu' di uno non si indovina, si torna
     alla scheda ritirata (un rimando alla pagina sbagliata e' peggio del
     problema che stiamo risolvendo);
  4. la PERMANENZA: passata la data la pagina vecchia resta un rimando, e non
     torna a stampare "Edizione conclusa" con il comune sbagliato;
  5. il RIENTRO: se lo slug vecchio ricompare sul foglio il timbro si toglie da
     solo, come per la ritirata;
  6. la CATENA: due correzioni di fila (prima il comune, poi il nome) non fanno
     fare due salti a chi arriva dal link piu' vecchio.

Uso:
    python scripts/prova_spostata.py

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
# Quante righe vere si mettono "sul foglio". Servono per far passare la guardia
# di credibilita' (sano): sotto le 20 pagine viste ogni run e' non attendibile e
# nessun timbro viene messo - ed e' giusto, ma qui provo l'altro ramo.
QUANTE = 40

reg_vero = json.load(open(os.path.join(ROOT, "data", "pagine-evento.json"), encoding="utf-8"))
OUT = os.path.join(tempfile.gettempdir(), "daop_prova_spostata")
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT, exist_ok=True)
g.PAGINE_DIR = os.path.join(OUT, "eventi")
g.REGISTRO_PATH = os.path.join(OUT, "registro.json")

css, nav, foot = g._guscio()
OGGI = datetime.date.today()
esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def come_evento(rec):
    """Il record del registro rimesso nella forma in cui arriva dal foglio."""
    e = {k: v for k, v in rec.items()
         if k not in ("first_seen", "last_seen", "updated", "slug",
                      "ritirata", "spostata")}
    for k in ("d_start", "d_end"):
        e[k] = datetime.date.fromisoformat(rec[k])
    return e


def futura(rec):
    return (rec.get('d_end') or '') >= OGGI.isoformat() and not rec.get('ritirata')


FUTURI = [s for s in reg_vero if futura(reg_vero[s])][:QUANTE]
if len(FUTURI) < 21:
    print(f"solo {len(FUTURI)} eventi futuri in registro: niente da provare")
    sys.exit(0)


def gemello(slug, pool):
    """C'e' gia' un'altra riga che somiglia a questa quanto basta?

    Serve a scegliere una cavia pulita: se il foglio contiene DAVVERO due righe
    con stesse date e stesso nome, il rimando non si deve fare (prova 3), e una
    cavia cosi' renderebbe la prova 1 verde per il motivo sbagliato."""
    r = reg_vero[slug]
    riga = str(r.get('riga') or '').strip()
    for altro in pool:
        if altro == slug:
            continue
        a = reg_vero[altro]
        if a.get('d_start') != r.get('d_start') or a.get('d_end') != r.get('d_end'):
            continue
        if (g._key(a.get('nome')) == g._key(r.get('nome'))
                or (riga and str(a.get('riga') or '').strip() == riga)):
            return True
    return False


CAVIA = next((s for s in FUTURI if not gemello(s, FUTURI)), None)
if CAVIA is None:
    print("nessuna cavia senza gemelli nel registro: niente da provare")
    sys.exit(0)
ALTRI = [s for s in FUTURI if s != CAVIA]


def scrivi_registro(slugs, extra=None):
    """Il registro di partenza: le righe vere, senza i timbri veri."""
    reg = {s: {k: v for k, v in reg_vero[s].items()
               if k not in ("ritirata", "spostata")} for s in slugs}
    reg.update(extra or {})
    json.dump(reg, open(g.REGISTRO_PATH, "w", encoding="utf-8"), ensure_ascii=False)


def gira(eventi):
    """scrivi_pagine() come la chiama il generatore, ma zitta."""
    vero = sys.stdout
    sys.stdout = io.StringIO()
    try:
        return g.scrivi_pagine(eventi, hub=None)
    finally:
        sys.stdout = vero


def registro():
    return json.load(open(g.REGISTRO_PATH, encoding="utf-8"))


def leggi(slug):
    """La pagina generata, senza il CSS inline: dentro il CSS ci sono commenti
    che citano le stesse cose che qui si cercano, e darebbero falsi allarmi."""
    p = os.path.join(g.PAGINE_DIR, f"{slug}.html")
    html = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return re.sub(r"<style>.*?</style>", "", html, flags=re.S)


def foglio(cambi=None):
    """Gli eventi come li leggerebbe il generatore dal foglio, con la cavia
    corretta: `cambi` sono le celle modificate a mano (il comune, il nome)."""
    eventi = [come_evento(reg_vero[s]) for s in ALTRI]
    cavia = come_evento(reg_vero[CAVIA])
    cavia.update(cambi or {})
    return eventi + [cavia], g.slug_evento(cavia)


NUOVO_COMUNE = "Cherasco Prova"

print(f"cavia: {CAVIA}")
print("=== 1) il comune viene corretto -> la pagina vecchia diventa un rimando ===")
scrivi_registro(FUTURI)
eventi, NUOVO = foglio({"citta": NUOVO_COMUNE})
sitemap = gira(eventi)
ok(f"lo slug nuovo e' un altro ({NUOVO})", NUOVO != CAVIA)
ok("timbro 'spostata' nel registro, verso lo slug nuovo",
   registro().get(CAVIA, {}).get("spostata") == NUOVO)
ok("niente timbro 'ritirata'", not registro().get(CAVIA, {}).get("ritirata"))
vecchia = leggi(CAVIA)
url_nuova = f"{g.SITE_URL}/eventi/{NUOVO}.html"
ok("refresh verso la pagina nuova", f'content="0; url={url_nuova}"' in vecchia)
ok("canonical sulla pagina nuova", f'<link rel="canonical" href="{url_nuova}">' in vecchia)
ok("bottone 'Vai alla scheda aggiornata'", "Vai alla scheda aggiornata" in vecchia)
# esc() fa strip(), quindi esc(a_citta(x)) si mangia lo spazio davanti e stampa
# "quella buonaa Cherasco". Si vede solo leggendo la frase, ed e' il genere di
# difetto che nessuno guarda piu' dopo il primo giorno.
ok(f"la frase e' scritta in italiano (a {NUOVO_COMUNE})",
   f"quella buona a {NUOVO_COMUNE}" in vecchia)
# noindex + canonical altrove sono due segnali opposti sulla stessa pagina, e il
# rischio non e' teorico: il noindex puo' passare alla pagina buona.
ok("NIENTE noindex", "noindex" not in vecchia)
ok("fuori dalla sitemap", CAVIA not in sitemap)
# Il dato vecchio non deve restare "per contesto": e' esattamente la riga che
# abbiamo corretto, ed e' quello che chi apre il link vecchio non deve leggere.
vecchia_citta = (reg_vero[CAVIA].get("citta") or "").strip()
ok(f"il comune sbagliato ({vecchia_citta}) non compare piu'",
   vecchia_citta.lower() not in vecchia.lower())
descr = (reg_vero[CAVIA].get("descr") or "").strip()
ok("niente descrizione vecchia", not descr or descr[:60] not in vecchia)
ok("niente locandina", 'class="ev-loc"' not in vecchia)
ok("niente 'Aggiungi al calendario'", "Aggiungi al calendario" not in vecchia)
ok("niente 'Scheda verificata da DAOP'", "Scheda verificata da DAOP" not in vecchia)
ok("niente 'Scheda ritirata'", "Scheda ritirata" not in vecchia)
ok("niente Event nei dati strutturati", '"@type": "Event"' not in vecchia)
nuova = leggi(NUOVO)
ok("la pagina NUOVA e' una scheda normale e verificata",
   "Scheda verificata da DAOP" in nuova and NUOVO_COMUNE in nuova)
ok("la pagina nuova e' in sitemap", NUOVO in sitemap)
ok("le altre pagine restano normali", "Scheda verificata da DAOP" in leggi(ALTRI[0]))

print()
print("=== 2) il NOME viene corretto (stessa riga del foglio) -> stesso rimando ===")
scrivi_registro(FUTURI)
eventi, NUOVO2 = foglio({"nome": "Nome Corretto A Mano Per La Prova"})
gira(eventi)
ok(f"riconosciuto dalla riga di foglio ({reg_vero[CAVIA].get('riga')})",
   registro().get(CAVIA, {}).get("spostata") == NUOVO2)

print()
print("=== 3) due candidati uguali -> nessun rimando, scheda ritirata ===")
scrivi_registro(FUTURI)
eventi, _ = foglio({"citta": NUOVO_COMUNE})
# Una terza riga identica in un altro comune: adesso di eredi ce ne sono due, e
# indovinare quale sia "quella giusta" non e' un compito del codice.
sosia = come_evento(reg_vero[CAVIA])
sosia["citta"] = "Altro Comune Prova"
gira(eventi + [sosia])
ok("nessun rimando", not registro().get(CAVIA, {}).get("spostata"))
ok("timbro 'ritirata' al suo posto", registro().get(CAVIA, {}).get("ritirata"))
ok("la pagina dice 'Scheda ritirata'", "<strong>Scheda ritirata</strong>" in leggi(CAVIA))

print()
print("=== 4) passata la data, il rimando resta un rimando ===")
rec = dict(reg_vero[CAVIA], slug=CAVIA, spostata="destinazione-prova")
rec["d_start"] = rec["d_end"] = (OGGI - datetime.timedelta(days=30)).isoformat()
finto_reg = {CAVIA: rec, "destinazione-prova": dict(reg_vero[CAVIA], slug="destinazione-prova",
                                                    citta=NUOVO_COMUNE)}
dove = g._destinazione(rec, finto_reg)
pagina = re.sub(r"<style>.*?</style>", "",
                g.render_spostata(rec, finto_reg[dove], css, nav, foot), flags=re.S)
ok("la destinazione si trova ancora", dove == "destinazione-prova")
ok("resta il cartello 'Questa scheda si è spostata'",
   "Questa scheda si è spostata" in pagina)
ok("niente 'Edizione conclusa'", "Edizione conclusa" not in pagina)

print()
print("=== 5) lo slug vecchio torna sul foglio -> il timbro si toglie ===")
scrivi_registro(FUTURI)
eventi, _ = foglio({"citta": NUOVO_COMUNE})
gira(eventi)
gira([come_evento(reg_vero[s]) for s in FUTURI])
ok("timbro rimosso", not registro().get(CAVIA, {}).get("spostata"))
ok("pagina di nuovo verificata", "Scheda verificata da DAOP" in leggi(CAVIA))

print()
print("=== 6) due correzioni di fila -> un salto solo, fino all'ultima ===")
scrivi_registro(FUTURI)
eventi, PRIMA = foglio({"citta": NUOVO_COMUNE})
gira(eventi)
eventi, SECONDA = foglio({"citta": "Terzo Comune Prova"})
gira(eventi)
r = registro()
ok("la seconda correzione sposta anche la prima pagina nuova",
   r.get(PRIMA, {}).get("spostata") == SECONDA)
url_ultima = f"{g.SITE_URL}/eventi/{SECONDA}.html"
# Finche' l'evento e' futuro il rimando si ricalcola a ogni run, quindi la
# pagina piu' vecchia punta gia' da sola all'ultima senza passare dalla catena.
# La catena serve dopo: dalla data in poi la pagina non e' piu' orfana, _erede
# non gira e il timbro resta quello del giorno della prima correzione.
ok("la pagina piu' vecchia punta direttamente all'ultima",
   f'content="0; url={url_ultima}"' in leggi(CAVIA))
catena = {CAVIA: dict(r[CAVIA], spostata=PRIMA), PRIMA: r[PRIMA], SECONDA: r[SECONDA]}
ok("col timbro rimasto indietro, il rimando segue la catena fino in fondo",
   g._destinazione(catena[CAVIA], catena) == SECONDA)
# A -> B -> A: due correzioni fatte e disfatte. In fondo all'anello c'e' la
# pagina stessa, e una pagina che rimanda a se stessa, nel browser, non smette
# piu' di ricaricarsi.
anello = {"a-prova": {"slug": "a-prova", "spostata": "b-prova"},
          "b-prova": {"slug": "b-prova", "spostata": "a-prova"}}
ok("un anello non produce una pagina che rimanda a se stessa",
   g._destinazione(anello["a-prova"], anello) is None)

print()
print(f"=== 7) run cieca (3 eventi su {len(FUTURI)}): nessun rimando ===")
scrivi_registro(FUTURI)
eventi, _ = foglio({"citta": NUOVO_COMUNE})
gira(eventi[:3])
ok("nessuno spostamento deciso da una run non attendibile",
   not [s for s, v in registro().items() if v.get("spostata")])

shutil.rmtree(OUT, ignore_errors=True)
print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
