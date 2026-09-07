#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla che una locandina che NON c'e' piu' non venga stampata da nessuna
parte - e che una che c'e' non sparisca per un capriccio di rete.

PERCHE' ESISTE (07/09/2026). Il sito stampava l'<img>, l'og:image e l'"image"
dei dati strutturati per qualunque nome ci fosse nella colonna Locandina, senza
sapere se dietro quel nome ci fosse un file. Quando la pulizia notturna del
bucket ha cominciato a cancellare cose che il sito mostrava ancora, il risultato
sono stati 1222 riferimenti rotti su 310 pagine: il punto interrogativo azzurro
al posto della locandina, e per Google un Event con un'immagine che da' 404.

Le tre cose difese qui, e sono tre decisioni, non tre dettagli:

  1. IL PUNTO E' UNO SOLO. Il controllo sta dentro loc_path(), l'unico posto in
     cui un nome diventa un indirizzo: cosi' l'immagine, l'anteprima social e i
     dati strutturati sparISCONO INSIEME. Se qualcuno ne aggiunge un quarto, non
     deve doversi ricordare di niente.

  2. LA MINIATURA RESTA. Sta in git, quindi funziona anche quando l'originale
     nel bucket e' sparito - e in un elenco un francobollo e' meglio di un buco.
     Tutte e nove le locandine cancellate il 07/09 avevano la loro miniatura.

  3. SI SBAGLIA STAMPANDO, NON TOGLIENDO. Solo una risposta chiara (400/404)
     toglie un'immagine. Un 429 o un timeout NON la toglie: se un intoppo di
     rete facesse risultare morte tutte le locandine, il sito uscirebbe senza
     nemmeno un'immagine e lo rimetterebbe in piedi solo la run di domani.
     Ma prima di rinunciare si RIPROVA, e le rinunce si CONTANO: il 07/09 la
     prima versione contava un 429 come "l'immagine c'e'", e 67 pagine sono
     state riscritte tenendosi un'immagine che non esisteva.

Offline: urlopen e' sostituito da una finta. Non tocca la rete e non riscrive
nessuna pagina.
"""
import io
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import genera_eventi as G  # noqa: E402

esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


class FintoUrlopen:
    """Risponde come deciso da `esiti`: True = c'e', un int = codice HTTP,
    'timeout' = eccezione qualunque. Conta i tentativi per nome."""
    def __init__(self, esiti):
        self.esiti, self.tentativi = esiti, {}

    def __call__(self, req, timeout=None):
        nome = req.full_url.rsplit('/', 1)[-1].split('?')[0]
        self.tentativi[nome] = self.tentativi.get(nome, 0) + 1
        e = self.esiti.get(nome, True)
        if e is True:
            class R:
                status = 200
                def __enter__(self_): return self_
                def __exit__(self_, *a): return False
            return R()
        if e == 'timeout':
            raise TimeoutError("finta")
        raise urllib.error.HTTPError(req.full_url, e, "finto", {}, None)


def scalda(esiti, nomi):
    vero = urllib.request.urlopen
    urllib.request.urlopen = finto = FintoUrlopen(esiti)
    G._LOC_MORTE.clear()
    try:
        morte = G.scalda_locandine(nomi, quanti_insieme=2)
    finally:
        urllib.request.urlopen = vero
    return morte, finto


VIVA, MORTA = "viva.webp", "morta.webp"

print("\n── una locandina che non c'e' non si stampa ──")
morte, _f = scalda({MORTA: 404}, [VIVA, MORTA])
ok("il 404 la dichiara morta", morte == {MORTA})
ok("loc_path la salta (via l'<img>)", G.loc_path(MORTA) == '')
ok("e loc_url con lei (via og:image e i dati strutturati)",
   G.loc_url(MORTA) == '')
ok("quella viva esce normalmente", G.loc_path(VIVA).endswith(VIVA))

# Supabase, sull'URL pubblico, risponde 400 con un corpo che dice 404: sono
# tutt'e due "non c'e'", e valgono uguale.
morte, _f = scalda({MORTA: 400}, [MORTA])
ok("e anche il 400 di Supabase, che dentro dice 404", G.loc_path(MORTA) == '')

print("\n── la miniatura in git resta ──")
# Una miniatura vera fra quelle committate: e' il caso di tutte e nove le
# locandine cancellate il 07/09, che la miniatura ce l'avevano.
mini = next((f for f in sorted(os.listdir(G.MINIATURE_DIR))
             if f.endswith('.webp')), None)
if not mini:
    print("  -- nessuna miniatura su disco, salto")
else:
    nome_grande = mini[:-5] + ".jpg"
    morte, _f = scalda({nome_grande: 404}, [nome_grande])
    ok("negli elenchi il francobollo si stampa lo stesso",
       G.loc_path(nome_grande, mini=True).startswith(G.MINIATURE_HREF))
    ok("ma sulla scheda, dove serve la grande, non si stampa niente",
       G.loc_path(nome_grande) == '')

print("\n── si sbaglia stampando, non togliendo ──")
morte, finto = scalda({MORTA: 429}, [MORTA])
ok("un 429 NON toglie l'immagine", morte == set() and G.loc_path(MORTA) != '')
ok("ma prima di rinunciare riprova tre volte",
   finto.tentativi.get(MORTA) == 3)
morte, finto = scalda({MORTA: 'timeout'}, [MORTA])
ok("e un timeout si comporta uguale",
   morte == set() and finto.tentativi.get(MORTA) == 3)
morte, finto = scalda({MORTA: 500}, [MORTA])
ok("come un 500 (il bucket che fa i capricci non spoglia il sito)",
   morte == set())

print("\n── chi non e' stato controllato e' vivo ──")
G._LOC_MORTE.clear()
ok("un nome che nessuno ha guardato si stampa",
   G.loc_path("mai_controllata.webp").endswith("mai_controllata.webp"))
ok("e senza nome non si stampa niente, come sempre",
   G.loc_path("") == '' and G.loc_path(None) == '')

print("\n── gli indirizzi esterni non si toccano ──")
G._LOC_MORTE.add("https://esempio.it/x.jpg")
ok("un URL intero passa comunque (non e' roba del bucket)",
   G.loc_path("https://esempio.it/x.jpg") == "https://esempio.it/x.jpg")
morte, finto = scalda({}, ["https://esempio.it/x.jpg"])
ok("e non lo si va nemmeno a controllare", not finto.tentativi)

print()
sys.exit(0 if esito else 1)
