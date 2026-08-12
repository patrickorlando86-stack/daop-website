#!/usr/bin/env python3
"""Miniature delle locandine, in git, per gli elenchi del sito.

PERCHE' ESISTE (12/08/2026): l'08/08 le locandine sono passate da git al bucket
Supabase. Giusto - a ~190 KB l'una committarle costava ~340 MB l'anno di blob
che non si recuperano piu' - ma ha spostato TUTTA la banda immagini del sito
sul piano gratuito di Supabase, che ha un tetto di 5 GB al mese. Il traffico in
uscita e' passato da ~10 a ~250 MB al giorno: a quel ritmo il tetto si tocca
verso il 26 del mese, e quando succede non si rompe una pagina - si spengono
insieme tutte le locandine del sito, senza preavviso.

La cura non e' pagare: e' smettere di mandare un'immagine da 95 KB dentro un
francobollo da 52 px. Negli elenchi (agenda, corsie, pagine comune, pagine di
intenzione) l'immagine sta in 50-262 px, e li' basta una miniatura da ~25 KB.
Quelle stanno in git senza rimorsi - il conto che aveva fatto uscire le
locandine, a un settimo del peso, non torna - e le serve GitHub Pages, che non
ha tetto. Su Supabase resta la locandina grande della SCHEDA evento, che e' una
per pagina e va vista com'e'.

Cosa fa: per ogni locandina citata nel foglio scarica l'originale dal bucket,
lo rimpicciolita a LATO px e lo salva in assets/miniature/<nome>.webp. Salta
quelle che ci sono gia', quindi da CI ogni notte lavora solo sulle nuove; alla
prima run recupera tutto l'arretrato.

Se un'immagine non si scarica non e' un errore fatale: loc_path() ripiega da
solo sull'originale e la pagina esce comunque, con una locandina pesante invece
che con un buco.

    python3 scripts/genera_miniature.py
    python3 scripts/genera_miniature.py --rifai     # rigenera anche le esistenti
"""

import argparse
import concurrent.futures
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import genera_eventi as G  # noqa: E402  (ROOT deve stare nel path prima)

# Lato lungo della miniatura. 400 e' un compromesso misurato sui due usi:
# il francobollo dell'agenda sta in 52-60 px (400 e' abbondante, ma il file e'
# gia' piccolo e non vale la pena avere due tagli da mantenere) e la copertina
# delle corsie sta in 262 px, dove 400 regge. Su schermi molto densi la
# copertina si ammorbidisce: e' il prezzo per restare sotto il tetto, e sono
# ritagli decorativi dietro al testo, non la locandina che si va a leggere.
LATO = 400
QUALITA = 72
# method: quanto si impegna il codificatore WebP. Il 6 e' il massimo e sul
# primo giro vero e' costato caro - 300 immagini erano ancora in lavorazione
# dopo 13 minuti. Il 4 produce file praticamente uguali in una frazione del
# tempo, e qui stiamo comprimendo francobolli, non stampe.
METODO = 4

DEST = os.path.join(ROOT, "assets", "miniature")
# Per singola immagine. Era 30: troppo, perche' moltiplicato per le immagini
# che non rispondono diventa il tempo di tutta la run.
TIMEOUT = 12
# Quante scaricare insieme. Il costo dominante e' l'attesa della rete, non la
# CPU: in parallelo il primo giro passa da una decina di minuti a meno di due.
PARALLELE = 8
# Tetto di tempo per l'intero passo. Lo script e' idempotente e riprende da
# dove ha lasciato, quindi se le immagini arretrate sono tante si spalmano su
# piu' run invece di tenere fermo l'aggiornamento del sito. Nel frattempo
# loc_path() ripiega sugli originali: le pagine escono comunque.
BUDGET_SECONDI = 300


def locandine_citate():
    """I nomi file delle locandine nominate dai dati committati.

    Si legge da data/eventi.json e non dal foglio: e' l'istantanea che il
    generatore ha appena scritto, quindi qui vediamo esattamente le locandine
    che finiranno nelle pagine. Gli URL completi restano fuori - sono immagini
    ospitate altrove, non nostre da ridimensionare."""
    nomi = {}
    for percorso in (os.path.join(ROOT, "data", "eventi.json"),):
        try:
            with open(percorso, encoding="utf-8") as fh:
                righe = json.load(fh)
        except (OSError, ValueError):
            continue
        for e in righe:
            loc = (e.get("loc") or "").strip()
            mini = G.nome_miniatura(loc)
            if mini:
                nomi[mini] = loc
    return nomi


def scarica(loc):
    url = G.loc_path(loc)
    req = urllib.request.Request(url, headers={"User-Agent": "daop-miniature"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def rimpicciolisci(dati):
    """Ridimensiona mantenendo le proporzioni e salva in WebP.

    Import di Pillow qui dentro e non in cima: senza la libreria lo script
    deve dire cosa manca ed uscire pulito, non morire su un ImportError a
    meta' di un workflow."""
    from PIL import Image

    im = Image.open(io.BytesIO(dati))
    # Le locandine arrivano da Instagram e alcune hanno l'orientamento nei dati
    # EXIF invece che nei pixel: senza questa riga escono ruotate.
    try:
        from PIL import ImageOps
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGB")
    im.thumbnail((LATO, LATO), Image.LANCZOS)
    fuori = io.BytesIO()
    im.save(fuori, "WEBP", quality=QUALITA, method=METODO)
    return fuori.getvalue()


def una(voce):
    """Scarica e rimpicciolisce una sola locandina. Torna (nome, dati, errore).

    Gira dentro un thread: qui non si stampa e non si scrive su disco, cosi'
    l'ordine dell'output resta quello del thread principale."""
    mini, loc = voce
    try:
        originale = scarica(loc)
        return mini, originale, rimpicciolisci(originale), None
    except Exception as err:  # rete, immagine corrotta, formato sconosciuto
        return mini, None, None, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rifai", action="store_true",
                    help="rigenera anche le miniature che esistono gia'")
    args = ap.parse_args()

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("[miniature] Pillow non installato: pip install Pillow")
        return 1

    os.makedirs(DEST, exist_ok=True)
    citate = locandine_citate()
    if not citate:
        print("[miniature] nessuna locandina nei dati: non c'e' niente da fare")
        return 0

    saltate = [m for m in citate if os.path.exists(os.path.join(DEST, m))
               and not args.rifai]
    da_fare = sorted((m, l) for m, l in citate.items() if m not in set(saltate))

    fatte = fallite = 0
    byte_prima = byte_dopo = 0
    scaduto = False
    inizio = time.monotonic()
    if da_fare:
        print(f"[miniature] {len(da_fare)} da generare, {PARALLELE} alla volta")
        with concurrent.futures.ThreadPoolExecutor(max_workers=PARALLELE) as pool:
            futuri = {pool.submit(una, v): v[0] for v in da_fare}
            try:
                for f in concurrent.futures.as_completed(futuri):
                    mini, originale, piccola, err = f.result()
                    if err:
                        # Non alziamo: una miniatura che manca fa ripiegare
                        # loc_path() sull'originale, pesante ma funzionante.
                        print(f"[miniature] salto {mini}: {err}")
                        fallite += 1
                        continue
                    with open(os.path.join(DEST, mini), "wb") as fh:
                        fh.write(piccola)
                    byte_prima += len(originale)
                    byte_dopo += len(piccola)
                    fatte += 1
                    if time.monotonic() - inizio > BUDGET_SECONDI:
                        scaduto = True
                        break
            finally:
                if scaduto:
                    # Le rimaste le fa la run successiva: lo script riparte da
                    # dove ha lasciato, e intanto il sito si aggiorna lo stesso.
                    for f in futuri:
                        f.cancel()
    if scaduto:
        print(f"[miniature] tempo scaduto dopo {BUDGET_SECONDI}s: le rimanenti "
              "alla prossima run (nel frattempo le pagine usano gli originali)")
    saltate = len(saltate)

    # Le locandine sparite dal foglio: la miniatura non serve piu'. Non le
    # cancelliamo - le pagine evento restano online anche a edizione conclusa,
    # e cancellarle vorrebbe dire riscaricarle l'anno dopo.
    presenti = len([f for f in os.listdir(DEST) if f.endswith('.webp')])

    print(f"[miniature] {fatte} nuove, {saltate} gia' presenti, {fallite} non riuscite"
          f"  ({presenti} in tutto in assets/miniature/)")
    if fatte:
        print(f"[miniature] {byte_prima // 1024} KB di originali -> "
              f"{byte_dopo // 1024} KB di miniature "
              f"({100 - byte_dopo * 100 // max(byte_prima, 1)}% in meno)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
