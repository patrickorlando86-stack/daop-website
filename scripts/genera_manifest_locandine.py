#!/usr/bin/env python3
"""
data/locandine-usate.json: l'elenco delle locandine che il sito STA MOSTRANDO.

PERCHE' ESISTE (07/09/2026). Le locandine vivono in un bucket Supabase, e a
tenerlo pulito c'e' una funzione notturna nel repo mobile
(netlify/functions/sync-catalogo.js): elenca il bucket e cancella i file che
"non serve piu' a nessuno". Fino a oggi decideva guardando SOLO la colonna
Locandina di due tab del foglio - Eventi e Centri - e da quella lista
ricavava che tutto il resto era spazzatura.

Sono due liste diverse, e la differenza si e' pagata due volte:

  1. I CORSI (tab "Attivita") non erano nell'elenco. Quindi ogni locandina di
     un corso veniva cancellata 7 giorni dopo il caricamento, mentre la sua
     riga era viva sul foglio e la sua card viva su corsi.html. Misurato il
     07/09: 9 locandine su 21 gia' morte (CàRezza e Crome in Movimento), e le
     12 vive erano solo quelle caricate da meno di una settimana.

  2. Gli EVENTI FINITI. Quando un evento scade la sua riga esce dal foglio
     (pulisci_eventi_passati nel downloader) ma la sua PAGINA resta online per
     sempre, ed e' un pezzo grosso del traffico. Per la pulizia quella riga non
     esiste piu', quindi la locandina era orfana e sparivano insieme l'<img>,
     og:image e l'"image" dei dati strutturati. Misurato il 07/09: 238 immagini
     morte su 393 citate, 307 pagine evento col punto interrogativo.

La causa comune non e' un elenco incompleto: e' che la pulizia chiedeva al
FOGLIO una cosa che sa solo il SITO. Il foglio dice cosa e' in programma; il
sito dice cosa sta mostrando, e le pagine che mostra sopravvivono alle righe.

Quindi il sito lo DICHIARA, e la pulizia unisce le due liste. Questo file legge
gli HTML VERI appena generati - non il foglio, non i JSON intermedi: quello che
c'e' scritto dentro le pagine pubblicate - e scrive i nomi dei file citati.
Cosi' vale da sola anche per le pagine che nasceranno: se un domani una pagina
nuova cita una locandina, entra nel manifest senza che nessuno si ricordi di
aggiungere una tab da qualche parte.

DALL'ALTRA PARTE SI FIDA A PORTA CHIUSA: un manifest che non si scarica, o che
esce vuoto, vale "non lo so" e blocca la cancellazione. Sbagliare tenendo un
file di troppo costa qualche KB; sbagliare cancellandolo costa un'immagine che
non torna. Vedi lib/locandine-orfane.js nel repo mobile.

DEVE GIRARE PER ULTIMO, dopo tutti i generatori: legge le pagine che scrivono
loro. Nel workflow notturno sta appena prima del commit; nel downloader e'
l'ultimo di SCRIPT_SITO_DOPO.

Uso:
    python3 scripts/genera_manifest_locandine.py
"""
import datetime
import html
import json
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USCITA = os.path.join(ROOT, "data", "locandine-usate.json")

# Le cartelle che NON sono il sito pubblicato: la storia di git, le dipendenze
# delle prove e i pacchetti. Dentro node_modules ci sono HTML di esempio a
# migliaia, e leggerli tutti per niente costerebbe piu' del lavoro vero.
SALTA = {".git", "node_modules", ".github", "__pycache__"}

# Il bucket pubblico delle locandine. Si cercano i nomi file che vengono DOPO
# questo pezzo di URL: e' l'unica forma con cui una locandina finisce in pagina
# (img, og:image, twitter:image, "image" dei dati strutturati, href del
# visualizzatore). Le MINIATURE non c'entrano: quelle stanno in git sotto
# assets/miniature e non le cancella nessuna pulizia.
DENTRO_URL = re.compile(
    r'storage/v1/object/public/locandine/([^"\'\s\\<>)]+)')


def nome_pulito(grezzo):
    """Il nome come sta nel bucket: senza escape HTML e senza %-encoding.

    In pagina il nome ci arriva passato per due macinini: l'escape HTML degli
    attributi (`&amp;`) e il quoting dell'URL (`%20`). La pulizia dall'altra
    parte confronta col nome VERO dell'oggetto su Supabase, quindi qui si
    disfano tutti e due - altrimenti un file con uno spazio nel nome
    risulterebbe "non citato da nessuno" e verrebbe cancellato proprio perche'
    era citato.
    """
    return urllib.parse.unquote(html.unescape(grezzo)).strip()


def nomi_dalle_pagine(radice=ROOT):
    """Tutti i nomi di locandina citati dagli HTML del sito, senza doppioni."""
    nomi, pagine = set(), 0
    for cartella, sotto, file in os.walk(radice):
        sotto[:] = [d for d in sotto if d not in SALTA]
        for f in file:
            if not f.endswith(".html"):
                continue
            pagine += 1
            percorso = os.path.join(cartella, f)
            try:
                with open(percorso, encoding="utf-8", errors="ignore") as fh:
                    testo = fh.read()
            except OSError as e:
                # Una pagina illeggibile non deve produrre un manifest CORTO:
                # un nome che manca qui e' un file che dall'altra parte viene
                # cancellato. Meglio fermarsi e non riscrivere niente.
                raise SystemExit(f"! non riesco a leggere {percorso}: {e}")
            for grezzo in DENTRO_URL.findall(testo):
                pulito = nome_pulito(grezzo)
                if pulito:
                    nomi.add(pulito)
    return nomi, pagine


def scrivi(nomi, pagine, dove=USCITA):
    """Scrive il manifest. Non lo scrive VUOTO: un elenco a zero non e' un
    sito senza locandine, e' un guasto - e dall'altra parte varrebbe "cancella
    tutto". Se il conto e' zero si lascia in piedi il manifest di ieri, che al
    massimo protegge qualche file di troppo."""
    if not nomi:
        vecchio = os.path.exists(dove)
        print("! ZERO locandine trovate nelle pagine: NON riscrivo il manifest"
              + (" (resta quello di prima)" if vecchio else " (e non ce n'e' uno)"))
        return False
    os.makedirs(os.path.dirname(dove), exist_ok=True)
    with open(dove, "w", encoding="utf-8") as fh:
        json.dump({
            "generato": datetime.datetime.now(
                datetime.timezone.utc).isoformat(timespec="seconds"),
            "quante": len(nomi),
            "pagine_lette": pagine,
            "nomi": sorted(nomi),
        }, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return True


def main():
    nomi, pagine = nomi_dalle_pagine()
    print(f"  {pagine} pagine lette, {len(nomi)} locandine citate")
    if not scrivi(nomi, pagine):
        return 1
    print(f"  scritto {os.path.relpath(USCITA, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
