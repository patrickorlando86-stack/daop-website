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
    print(f"{SRC.name} {len(css) / 1024:.1f} KB -> {OUT.name} {len(mini) / 1024:.1f} KB "
          f"(-{100 * (len(css) - len(mini)) / len(css):.0f}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
