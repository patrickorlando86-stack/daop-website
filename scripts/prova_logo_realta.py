#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Il logo di una realta': dalla cella del foglio ai quattro posti in cui compare.

PERCHE' ESISTE (07/09/2026). La colonna "Logo" della tab Realta esisteva dal
25/08 e nessuno l'aveva mai riempita: il suo valore finiva GREZZO dentro src=,
dentro og:image, dentro twitter:image e dentro i dati strutturati. Finche' la
colonna era vuota non si vedeva; dal giorno in cui il downloader ha cominciato a
scriverci un nome di file, quei quattro punti volevano quattro forme diverse
dello stesso indirizzo.

Le tre decisioni difese qui:

  1. IL PUNTO E' UNO SOLO. logo_path() e' l'unico posto in cui il valore della
     cella diventa un indirizzo, come loc_path() per le locandine. Un f-string
     ricopiato in quattro punti e' un logo che si vede nella scheda e non
     nell'anteprima di WhatsApp il giorno che la cartella cambia nome.

  2. RELATIVO DOVE SERVE, ASSOLUTO DOVE SERVE. og:image con un indirizzo che
     comincia per "/" viene scartato da chi genera l'anteprima, e schema.org
     vuole URL assoluti: sono i due punti in cui il valore andava grezzo.

  3. SE IL FILE NON C'E', NON SI STAMPA NIENTE. Stessa regola di loc_path dopo
     il 07/09: una cella con un refuso fa una pagina senza marchio, non una
     pagina con un rettangolo rotto in cima. E' anche l'unico modo perche' una
     cella scritta a mano si accorga di essere sbagliata.

Offline: crea due file finti dentro assets/loghi e li toglie alla fine.
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import genera_corsi as C  # noqa: E402

esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


CARTELLA = os.path.join(C.ROOT, C.DIR_LOGHI)
FINTI = ["prova-logo-realta.webp", "prova logo con spazio.webp"]
os.makedirs(CARTELLA, exist_ok=True)
nati = []
for f in FINTI:
    p = os.path.join(CARTELLA, f)
    if not os.path.exists(p):
        with open(p, "wb") as fh:
            fh.write(b"RIFF")          # non e' un webp vero: qui conta esistere
        nati.append(p)

try:
    print("\n── un nome di file diventa un indirizzo ──")
    ok("il nome diventa un indirizzo sotto assets/loghi",
       C.logo_path("prova-logo-realta.webp")
       == "/assets/loghi/prova-logo-realta.webp")
    ok("uno spazio nel nome viene codificato (se no spezza il src)",
       C.logo_path("prova logo con spazio.webp")
       == "/assets/loghi/prova%20logo%20con%20spazio.webp")
    ok("una cartella scritta davanti non conta: vale il nome",
       C.logo_path("assets/loghi/prova-logo-realta.webp")
       == "/assets/loghi/prova-logo-realta.webp")

    print("\n── se il file non c'e', non si stampa niente ──")
    ok("un nome che non esiste non diventa un <img> rotto",
       C.logo_path("questo-non-esiste-di-sicuro.webp") == "")
    ok("...e nemmeno un og:image rotto",
       C.logo_url("questo-non-esiste-di-sicuro.webp") == "")
    ok("una cella vuota resta vuota",
       C.logo_path("") == "" and C.logo_path(None) == ""
       and C.logo_url("") == "")

    print("\n── og:image e dati strutturati: assoluto ──")
    ok("logo_url mette il dominio davanti",
       C.logo_url("prova-logo-realta.webp")
       == f"{C.SITE_URL}/assets/loghi/prova-logo-realta.webp")
    ok("...e comincia per http, che e' cio' che chiede chi fa l'anteprima",
       C.logo_url("prova-logo-realta.webp").startswith("http"))

    print("\n── gli indirizzi scritti a mano non si toccano ──")
    # La colonna si compila anche a mano, e chi ci ha incollato l'URL del logo
    # sul proprio sito non deve vederselo cancellare da un controllo che
    # riguarda i NOSTRI file.
    ok("un URL intero passa com'e'",
       C.logo_path("https://esempio.it/logo.png") == "https://esempio.it/logo.png")
    ok("...e resta lui anche in forma assoluta",
       C.logo_url("https://esempio.it/logo.png") == "https://esempio.it/logo.png")
    ok("un percorso che comincia per / passa com'e'",
       C.logo_path("/assets/images/logodaop.png") == "/assets/images/logodaop.png")
    ok("...e in forma assoluta prende il dominio",
       C.logo_url("/assets/images/logodaop.png")
       == f"{C.SITE_URL}/assets/images/logodaop.png")

    print("\n── i quattro posti in pagina ──")
    # Non si guarda il codice: si guarda l'HTML che esce. E' l'unico modo per
    # accorgersi che il quinto punto, il giorno che nascera', e' stato scordato.
    # Il corso si costruisce dalle COLONNE che il modulo dichiara, non da un
    # elenco scritto a mano: un campo in piu' la' e questa prova morirebbe con
    # un KeyError che non c'entra niente col logo.
    corso = {campo: "" for campo in C.COLONNE}
    corso.update({"nome": "Corso di prova", "organizzatore": "Prova Logo",
                  "citta": "Cuneo", "categoria": "Movimento > danza"})
    info = {"nome": "Prova Logo", "logo": "prova-logo-realta.webp",
            "descr": "Una descrizione lunga a sufficienza perche' la pagina "
                     "dedicata nasca davvero, e non meno di centoventi "
                     "caratteri come chiede MIN_DESCR_REALTA.",
            "stato": "confermata", "citta": "Cuneo"}
    try:
        pagina = C.pagina_realta("Prova Logo", [corso], info, "", "", "")
    except Exception as e:
        pagina = ""
        print(f"  (pagina_realta non generabile in questa prova: "
              f"{type(e).__name__}: {e})")
    if pagina:
        rel = "/assets/loghi/prova-logo-realta.webp"
        ass = f"{C.SITE_URL}{rel}"
        ok("l'<img> della pagina usa l'indirizzo relativo",
           f'src="{rel}"' in pagina)
        ok("og:image usa quello assoluto",
           f'property="og:image" content="{ass}"' in pagina)
        ok("twitter:image usa quello assoluto",
           f'name="twitter:image" content="{ass}"' in pagina)
        ok("i dati strutturati usano quello assoluto", f'"{ass}"' in pagina)
        # E il caso che conta: una cella con un refuso non deve lasciare in
        # pagina ne' un <img> rotto ne' un'anteprima rotta - l'anteprima torna
        # al banner di DAOP, che e' un'immagine che esiste.
        rotta = dict(info, logo="non-esiste-per-niente.webp")
        p2 = C.pagina_realta("Prova Logo", [corso], rotta, "", "", "")
        ok("con un nome sbagliato non esce nessun <img> di logo",
           'class="cr-logo"' not in p2)
        ok("...e l'anteprima torna al banner di DAOP",
           f'property="og:image" content="{C.G.esc(C.G.DEFAULT_IMG)}"' in p2)
finally:
    for p in nati:
        try:
            os.remove(p)
        except OSError:
            pass

print()
sys.exit(0 if esito else 1)
