#!/usr/bin/env python3
"""Rigenera assets/css/daop-system.min.css dal sorgente.

Le pagine caricano la versione .min.css. Se modifichi daop-system.css devi
rilanciare questo script, altrimenti la modifica non arriva sul sito:

    python3 scripts/build_css.py

Il sorgente resta la fonte di verita' (commenti inclusi); il .min.css e' un
artefatto, committato solo perche' GitHub Pages non ha una fase di build.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets/css/daop-system.css"
OUT = ROOT / "assets/css/daop-system.min.css"


def minify(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)      # via i commenti
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)        # spazi attorno ai simboli
    css = re.sub(r"\s+", " ", css)                       # spazi ripetuti
    return css.replace(";}", "}").strip()


# LA VERSIONE NEL LINK (06/11/2026). Il riquadro delle feste e' uscito senza stile sul
# telefono di Patrick: l'HTML nuovo era arrivato, il .min.css no - il browser (e la cache di
# GitHub Pages, 10 minuti) teneva quello di prima, perche' l'indirizzo era lo stesso. Nelle
# pagine che usano per prime una regola nuova il link porta ?v=<impronta del file>: cambia il
# CSS, cambia l'indirizzo, e il browser lo riscarica. Si fa qui perche' e' l'unico momento in
# cui il CSS cambia. Le altre pagine restano col link nudo: le regole che usano non cambiano.
VERSIONATE = ("eventi.html", "index.html")


def versiona(mini: str) -> None:
    import hashlib
    v = hashlib.sha1(mini.encode("utf-8")).hexdigest()[:8]
    for nome in VERSIONATE:
        f = ROOT / nome
        if not f.exists():
            continue
        html = f.read_text(encoding="utf-8")
        nuovo = re.sub(r'(/assets/css/daop-system\.min\.css)(\?v=[0-9a-f]+)?"', rf'\1?v={v}"', html)
        if nuovo != html:
            f.write_text(nuovo, encoding="utf-8")
            print(f"{nome}: daop-system.min.css?v={v}")


def main() -> int:
    if not SRC.exists():
        print(f"sorgente mancante: {SRC}", file=sys.stderr)
        return 1
    css = SRC.read_text(encoding="utf-8")
    mini = minify(css) + "\n"

    # --check: fallisce se il .min.css e' disallineato (utile in CI)
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != mini:
            print("daop-system.min.css non e' aggiornato: "
                  "lancia python3 scripts/build_css.py", file=sys.stderr)
            return 1
        print("daop-system.min.css aggiornato")
        return 0

    OUT.write_text(mini, encoding="utf-8")
    versiona(mini)
    print(f"{SRC.name} {len(css) / 1024:.1f} KB -> {OUT.name} {len(mini) / 1024:.1f} KB "
          f"(-{100 * (len(css) - len(mini)) / len(css):.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
