#!/usr/bin/env python3
"""
Genera le sezioni dinamiche di esploratore.html (la pagina della collana
"Ginetto l'Esploratore", puntata dai QR code stampati dentro i libri)
a partire da data/ginetto-collana.json.

Rigenera SOLO i blocchi tra le ancore GINETTO:*:START / GINETTO:*:END.
Tutto il resto della pagina (nav, footer, stili, testi fissi) resta intatto,
esattamente come fa scripts/genera_eventi.py con eventi.html.

Due cose che lo script fa apposta, e che e' bene non "semplificare":

  1. Il PESO dei PDF viene letto dal file vero, non dal JSON. Cosi' la riga
     "PDF A4 - 320 KB" non puo' mai mentire dopo che un file viene sostituito.

  2. Se un PDF o una copertina NON esistono ancora nel repo, il link NON viene
     generato: la voce compare come "in preparazione" e la copertina come
     segnaposto disegnato. Su una pagina raggiunta da QR stampato un download
     rotto e' molto peggio di un materiale dichiarato non ancora pronto.

Uso:
    python scripts/genera_ginetto.py
"""
import os, re, json, html, datetime, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "data", "ginetto-collana.json")
HTML_PATH = os.path.join(ROOT, "esploratore.html")
SITEMAP_PATH = os.path.join(ROOT, "sitemap.xml")

PAGE_URL = "https://www.daop.it/esploratore"
AMAZON_AUTORE = "https://www.amazon.it/stores/Patrick-Orlando/author/B0F8B95YG5"

mancanti = []   # file citati dal JSON ma non presenti nel repo


def e(s):
    """Escape HTML di un valore proveniente dal JSON."""
    return html.escape(str(s or ""), quote=True)


def peso(path_rel):
    """Peso leggibile del file, o None se il file non c'e'."""
    p = os.path.join(ROOT, path_rel.replace("/", os.sep))
    if not path_rel or not os.path.isfile(p):
        return None
    b = os.path.getsize(p)
    if b < 1024:
        return f"{b} B"
    if b < 1024 * 1024:
        return f"{round(b / 1024)} KB"
    return f"{b / 1024 / 1024:.1f}".replace(".", ",") + " MB"


def esiste(path_rel):
    return bool(path_rel) and os.path.isfile(
        os.path.join(ROOT, path_rel.replace("/", os.sep)))


# ─────────────────────────── copertine ───────────────────────────

def copertina(v):
    """<img> se la copertina esiste, altrimenti un segnaposto disegnato con
    le stesse proporzioni (1:1: i libri della collana sono quadrati), cosi'
    il layout non balla quando arrivera' il file vero."""
    src, alt = v.get("copertina", ""), v.get("copertina_alt", "")
    if esiste(src):
        return (f'<img src="{e(src)}" alt="{e(alt)}" width="980" height="980" '
                f'loading="lazy" decoding="async">')
    mancanti.append(src or f"(copertina del volume {v.get('numero')})")
    etichetta = "In arrivo" if v.get("stato") == "in-arrivo" else "Copertina in arrivo"
    return (
        '<div class="vol-placeholder" role="img" aria-label="' + e(alt) + '">'
        '<svg viewBox="0 0 800 800" aria-hidden="true" focusable="false">'
        '<rect width="800" height="800" fill="#2d4a5c"/>'
        # Ago di bussola, non una croce: con due semplici linee il segnaposto
        # sembrava un pulsante "+" (aggiungi) invece di un volume in arrivo.
        '<circle cx="400" cy="330" r="132" fill="none" stroke="#c9a227" stroke-width="9"/>'
        '<g transform="rotate(32 400 330)">'
        '<path d="M400 228 L426 330 L400 330 Z" fill="#c9a227"/>'
        '<path d="M400 228 L374 330 L400 330 Z" fill="#a8871f"/>'
        '<path d="M400 432 L426 330 L400 330 Z" fill="rgba(255,255,255,0.32)"/>'
        '<path d="M400 432 L374 330 L400 330 Z" fill="rgba(255,255,255,0.17)"/>'
        '</g><circle cx="400" cy="330" r="11" fill="#2d4a5c"/>'
        f'<text x="400" y="572" text-anchor="middle" fill="#ffffff" '
        f'font-family="Georgia,serif" font-size="72" font-weight="700">Vol. {e(v.get("numero"))}</text>'
        f'<text x="400" y="650" text-anchor="middle" fill="rgba(255,255,255,0.62)" '
        f'font-family="Helvetica,Arial,sans-serif" font-size="42">{e(etichetta)}</text>'
        '</svg></div>')


# ─────────────────────────── volumi ───────────────────────────

def render_volumi(volumi):
    out = []
    for v in volumi:
        in_arrivo = v.get("stato") == "in-arrivo"
        classi = "vol-card" + (" is-soon" if in_arrivo else "")
        out.append(f'      <article class="{classi}">')
        out.append(f'        <div class="vol-cover">{copertina(v)}</div>')
        out.append('        <div class="vol-body">')
        out.append(f'          <p class="vol-num">Volume {e(v.get("numero"))}</p>')
        out.append(f'          <h3>{e(v.get("titolo"))}</h3>')
        # Il luogo si mostra anche per un volume non ancora uscito (Castelnuovo
        # e' un paese vero); si omette solo per lo slot generico "prossimo
        # paese", che infatti ha "paese" vuoto nel JSON.
        if v.get("paese"):
            out.append(
                '          <p class="vol-luogo">'
                '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                '<path d="M12 21s7-5.6 7-11a7 7 0 1 0-14 0c0 5.4 7 11 7 11z"/>'
                '<circle cx="12" cy="10" r="2.6"/></svg>'
                f'<span>{e(v.get("paese"))} <span class="vol-prov">({e(v.get("provincia"))})</span></span></p>')
        out.append(f'          <p class="vol-desc">{e(v.get("descrizione"))}</p>')

        if in_arrivo:
            out.append('          <p class="vol-soon">In preparazione</p>')
        else:
            link = v.get("amazon") or AMAZON_AUTORE
            etichetta = "Vedi su Amazon" if v.get("amazon") else "Cerca su Amazon"
            if not v.get("amazon"):
                mancanti.append(f'(link Amazon diretto del volume {v.get("numero")} '
                                f'- ora punta alla pagina autore)')
            out.append(
                f'          <a class="vol-link" href="{e(link)}" target="_blank" rel="noopener" '
                f'aria-label="{e(etichetta)}: {e(v.get("titolo"))}">{e(etichetta)}'
                '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                '<path d="M5 12h13M12 5l7 7-7 7"/></svg></a>')
        out.append('        </div>')
        out.append('      </article>')
    return "\n".join(out)


# ─────────────────────────── materiali ───────────────────────────

def render_materiali(volumi):
    out = []
    for v in volumi:
        mats = v.get("materiali") or []
        # I materiali di un volume non ancora uscito non si annunciano: il
        # diploma di un libro che non esiste non e' "in preparazione", e'
        # una promessa che il lettore non puo' verificare.
        if not mats or v.get("stato") == "in-arrivo":
            continue
        out.append('      <div class="mat-group">')
        # Lo spazio dopo </span> non e' cosmetico: senza, uno screen reader
        # legge "Vol. 1Casale Monferrato" tutto attaccato.
        out.append('        <h3 class="mat-group-title">'
                   f'<span class="mat-group-num">Vol. {e(v.get("numero"))}</span> '
                   f'{e(v.get("paese"))}</h3>')
        out.append('        <ul class="mat-list">')
        for m in mats:
            f = m.get("file", "")
            kb = peso(f)
            meta = f'{e(m.get("formato", "PDF"))} &middot; {e(kb)}' if kb else "In preparazione"
            if kb:
                out.append(
                    f'          <li class="mat-item"><a class="mat-link" href="{e(f)}" download '
                    f'type="application/pdf" '
                    f'aria-label="Scarica {e(m.get("titolo"))} del volume {e(v.get("numero"))}, '
                    f'{e(v.get("paese"))} - {e(m.get("formato", "PDF"))}, {e(kb)}">')
            else:
                mancanti.append(f)
                out.append('          <li class="mat-item is-soon"><div class="mat-link">')
            out.append('            <span class="mat-ico" aria-hidden="true">'
                       '<svg viewBox="0 0 24 24" focusable="false">'
                       '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5"/>'
                       '<path d="M5 18.5h14"/></svg></span>')
            out.append('            <span class="mat-text">'
                       f'<span class="mat-titolo">{e(m.get("titolo"))}</span>'
                       f'<span class="mat-desc">{e(m.get("descrizione"))}</span>'
                       f'<span class="mat-meta">{meta}</span></span>')
            out.append('          </a></li>' if kb else '          </div></li>')
        out.append('        </ul>')
        out.append('      </div>')
    return "\n".join(out)


# ─────────────────────────── dati strutturati ───────────────────────────

def render_jsonld(volumi):
    libri = []
    for v in volumi:
        if v.get("stato") == "in-arrivo":
            continue
        libri.append({
            "@type": "Book",
            "position": v.get("numero"),
            "name": v.get("titolo"),
            "bookEdition": f"Volume {v.get('numero')}",
            "inLanguage": "it",
            "author": {"@type": "Person", "name": "Patrick Orlando"},
            "publisher": {"@type": "Organization", "name": "DAOP APS"},
            "about": {"@type": "Place", "name": v.get("paese"),
                      "address": {"@type": "PostalAddress",
                                  "addressLocality": v.get("paese"),
                                  "addressRegion": v.get("provincia"),
                                  "addressCountry": "IT"}},
            "url": v.get("amazon") or AMAZON_AUTORE,
        })
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "BookSeries",
             "name": "Ginetto l'Esploratore",
             "url": PAGE_URL,
             "inLanguage": "it",
             "author": {"@type": "Person", "name": "Patrick Orlando"},
             "publisher": {"@type": "Organization", "name": "DAOP APS",
                           "url": "https://www.daop.it"},
             "hasPart": libri},
            {"@type": "WebPage",
             "name": "Ginetto l'Esploratore - la collana",
             "url": PAGE_URL,
             "isPartOf": {"@type": "WebSite", "name": "DAOP APS",
                          "url": "https://www.daop.it"}},
        ],
    }
    return ('<script type="application/ld+json">\n'
            + json.dumps(data, ensure_ascii=False, indent=2)
            + '\n</script>')


# ─────────────────────────── iniezione ───────────────────────────

def inject(pagina, blocchi):
    for nome, contenuto in blocchi.items():
        pattern = (r'(<!-- GINETTO:' + nome + r':START -->)(.*?)(<!-- GINETTO:'
                   + nome + r':END -->)')
        pagina, n = re.subn(pattern,
                            lambda m: m.group(1) + "\n" + contenuto + "\n" + m.group(3),
                            pagina, flags=re.S)
        if n != 1:
            sys.exit(f"[genera_ginetto] ERRORE: ancora GINETTO:{nome} non trovata "
                     f"(o duplicata) in esploratore.html")
    return pagina


def update_sitemap():
    if not os.path.exists(SITEMAP_PATH):
        return
    oggi = datetime.date.today().isoformat()
    s = open(SITEMAP_PATH, encoding="utf-8").read()
    s, n = re.subn(
        r'(<loc>https://www\.daop\.it/esploratore</loc>\s*<lastmod>)\d{4}-\d{2}-\d{2}(</lastmod>)',
        lambda m: m.group(1) + oggi + m.group(2), s, count=1)
    if n == 1:
        open(SITEMAP_PATH, "w", encoding="utf-8").write(s)
        print(f"[genera_ginetto] sitemap: lastmod /esploratore -> {oggi}")
    else:
        print("[genera_ginetto] sitemap: blocco esploratore.html non trovato, salto")


def main():
    dati = json.load(open(JSON_PATH, encoding="utf-8"))
    volumi = [v for v in dati.get("volumi", []) if v.get("visibile")]
    if not volumi:
        sys.exit("[genera_ginetto] ERRORE: nessun volume visibile nel JSON")

    pagina = open(HTML_PATH, encoding="utf-8").read()
    pagina = inject(pagina, {
        "INTRO": '      <p class="intro-testo">'
                 + e(dati.get("collana", {}).get("intro", "")) + '</p>',
        "VOLUMI": render_volumi(volumi),
        "MATERIALI": render_materiali(volumi),
        "JSONLD": render_jsonld(volumi),
    })
    open(HTML_PATH, "w", encoding="utf-8").write(pagina)
    update_sitemap()

    pubblicati = sum(1 for v in volumi if v.get("stato") != "in-arrivo")
    scaricabili = sum(1 for v in volumi for m in (v.get("materiali") or [])
                      if esiste(m.get("file", "")))
    print(f"[genera_ginetto] esploratore.html aggiornata: {pubblicati} volumi, "
          f"{scaricabili} materiali scaricabili")
    if mancanti:
        print("\n[genera_ginetto] DA CARICARE (per ora mostrati come segnaposto "
              "o 'in preparazione'):")
        for m in dict.fromkeys(mancanti):
            print("  - " + m)


if __name__ == "__main__":
    main()
