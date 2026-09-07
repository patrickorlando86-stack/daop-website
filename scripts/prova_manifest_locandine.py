#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla data/locandine-usate.json: il manifest con cui il sito dice quali
locandine sta mostrando.

PERCHE' ESISTE (07/09/2026). Quel file e' l'unica cosa che tiene in vita le
locandine nel bucket: la pulizia notturna del repo mobile cancella quello che
non e' nel manifest ne' nel foglio. Un difetto qui non si vede - il sito esce
identico - e si scopre sette giorni dopo, guardando le pagine col punto
interrogativo azzurro al posto della locandina. E' lo stesso guasto che il
07/09 aveva ucciso 238 immagini su 393.

Le tre cose che difende, e sono tutte cose che a occhio non si vedono:

  1. UN NOME CITATO NELLA PAGINA FINISCE NEL MANIFEST. In tutte le forme in cui
     una locandina compare: <img>, og:image, twitter:image, "image" dei dati
     strutturati. Se una sola di quelle forme sfuggisse, quel file verrebbe
     cancellato mentre la pagina lo mostra.

  2. IL NOME ESCE COME STA NEL BUCKET. In pagina passa per l'escape HTML e per
     il quoting dell'URL; dall'altra parte si confronta col nome vero
     dell'oggetto. Un file con uno spazio nel nome scritto "%20" nel manifest
     risulterebbe non citato, e verrebbe cancellato PROPRIO perche' era citato.
     E il foglio ne ha (le locandine che arrivano da WhatsApp).

  3. UN MANIFEST VUOTO NON SI SCRIVE. Zero locandine non e' un sito senza
     locandine, e' un guasto - e dall'altra parte vale "cancella tutto".
     Se il conto e' zero si tiene quello di ieri, che al massimo protegge
     qualche file di troppo. E' il ripiego a porta chiusa, la stessa scelta di
     leggi_corsi() quando il foglio non risponde.

Offline e in un secondo: scrive in una cartella temporanea e non tocca il sito.
Poi guarda il manifest VERO, se c'e'.
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")

import genera_manifest_locandine as M  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
esito = True


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


# ── una pagina finta con la locandina in tutte le forme in cui compare ──────
BASE = "https://aaseyjdsldgjerjqlumu.supabase.co/storage/v1/object/public/locandine"
PAGINA = f"""<!doctype html><html><head>
<meta property="og:image" content="{BASE}/og_uno.webp">
<meta name="twitter:image" content="{BASE}/tw_due.webp">
<script type="application/ld+json">{{"image": ["{BASE}/ld_tre.webp"]}}</script>
</head><body>
<img class="ev-loc" src="{BASE}/img_quattro.webp" alt="Locandina">
<a href="{BASE}/link_cinque.webp">apri</a>
<img src="/assets/miniature/mini_sei.webp" alt="miniatura in git">
</body></html>"""

tmp = tempfile.mkdtemp(prefix="daop_manifest_")
os.makedirs(os.path.join(tmp, "eventi"), exist_ok=True)
with open(os.path.join(tmp, "eventi", "una.html"), "w", encoding="utf-8") as f:
    f.write(PAGINA)

print("\n── un nome citato dalla pagina finisce nel manifest ──")
nomi, pagine = M.nomi_dalle_pagine(tmp)
ok("l'<img> della scheda", "img_quattro.webp" in nomi)
ok("og:image", "og_uno.webp" in nomi)
ok("twitter:image", "tw_due.webp" in nomi)
ok('l\'"image" dei dati strutturati', "ld_tre.webp" in nomi)
ok("il link del visualizzatore", "link_cinque.webp" in nomi)
ok("la miniatura in git NON c'entra (non la cancella nessuno)",
   "mini_sei.webp" not in nomi and not any("mini" in n for n in nomi))
ok(f"cinque nomi, non uno di piu' (trovati {len(nomi)})", len(nomi) == 5)
ok("le pagine lette si contano", pagine == 1)

print("\n── il nome esce come sta nel bucket ──")
ok("l'escape HTML si disfa (&amp; -> &)",
   M.nome_pulito("Locandina&amp;Co.webp") == "Locandina&Co.webp")
ok("il quoting dell'URL si disfa (%20 -> spazio)",
   M.nome_pulito("WhatsApp%20Image%202026.webp") == "WhatsApp Image 2026.webp")
ok("gli spazi intorno si tolgono",
   M.nome_pulito("  x.webp  ") == "x.webp")
with open(os.path.join(tmp, "spazio.html"), "w", encoding="utf-8") as f:
    f.write(f'<img src="{BASE}/Con%20Spazio_01.webp">')
nomi2, _ = M.nomi_dalle_pagine(tmp)
ok("e vale sulla pagina vera, non solo sulla funzione",
   "Con Spazio_01.webp" in nomi2)

print("\n── un manifest vuoto non si scrive ──")
vuoto = os.path.join(tmp, "dati", "locandine-usate.json")
ok("zero nomi: non scrive niente e lo dice", M.scrivi(set(), 0, vuoto) is False)
ok("e infatti il file non nasce", not os.path.exists(vuoto))
M.scrivi({"c.webp", "a.webp"}, 3, vuoto)
ok("con dei nomi invece scrive", os.path.exists(vuoto))
d = json.load(open(vuoto, encoding="utf-8"))
ok("i nomi sono in ordine (diff leggibili nei commit)",
   d["nomi"] == ["a.webp", "c.webp"])
ok("porta il conto", d["quante"] == 2 and d["pagine_lette"] == 3)
ok("porta la data", bool(d.get("generato")))
M.scrivi(set(), 0, vuoto)
ok("e su zero nomi il manifest di prima RESTA (non si azzera)",
   json.load(open(vuoto, encoding="utf-8"))["quante"] == 2)

print("\n── il manifest vero del sito ──")
vero = os.path.join(ROOT, "data", "locandine-usate.json")
if not os.path.exists(vero):
    print("  -- non c'e' ancora: lo scrive la prima run del generatore")
else:
    d = json.load(open(vero, encoding="utf-8"))
    ok("non e' vuoto", d.get("quante", 0) > 0)
    ok("i nomi sono nomi di file e non URL",
       all("/" not in n and n for n in d["nomi"]))
    ok("nessun %-encoding rimasto", not any("%2" in n for n in d["nomi"]))
    # Il manifest deve coprire quello che le pagine mostrano ADESSO: se ci
    # fosse rimasto indietro, i nomi nuovi non sarebbero protetti.
    adesso, _p = M.nomi_dalle_pagine(ROOT)
    fuori = sorted(adesso - set(d["nomi"]))
    ok(f"copre tutto quello che le pagine citano oggi"
       + (f" (fuori: {fuori[:3]})" if fuori else ""), not fuori)

print()
sys.exit(0 if esito else 1)
