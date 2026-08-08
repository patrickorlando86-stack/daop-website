#!/usr/bin/env python3
"""
Controlla i dati strutturati di tutte le pagine generate, con le regole con cui
li legge Google.

PERCHE' ESISTE (08/08/2026): in Search Console la scheda "Aspetto nella ricerca"
era completamente vuota - nessun rich result attribuito al sito, nemmeno Event,
su un sito che di Event ne dichiara 250. Il JSON-LD c'era ed era sintatticamente
valido: a rompere tutto bastava UN campo sbagliato. La pagina "Ferragosto 2026 -
Family Eco Park" aveva ora "10:00-00:00" nel foglio, cioe' una serata che
finisce dopo mezzanotte, e le date uscivano cosi':

    startDate 2026-08-15T10:00+02:00
    endDate   2026-08-15T00:00+02:00      <- prima dell'inizio

Per Google e' un errore critico: l'elemento non e' valido, e una pagina senza
Event valido perde in SERP proprio le date e il badge evento, cioe' le due cose
che alzano il CTR. Un errore del genere non si vede rileggendo il codice e non
fa fallire niente: si vede solo controllando l'output, ed e' quello che fa
questo script.

Uso:
    python scripts/valida_jsonld.py          # tutte le pagine generate
    python scripts/valida_jsonld.py eventi/fiera-di-agosto-novi-ligure.html

Esce con codice 1 se trova ERRORI (l'elemento non e' valido per Google), 0 se
trova solo AVVISI (l'elemento e' valido ma incompleto). Gira nel workflow subito
dopo la generazione: il posto giusto per accorgersene e' prima del commit, non
tre settimane dopo guardando un grafico piatto.
"""
import os, re, sys, json, glob, datetime, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCCO_RE = re.compile(
    r'<script type="application/ld\+json"[^>]*>\s*(\{.*?\})\s*</script>', re.S)
# ISO 8601: data, o data + ora con fuso. Google rifiuta un startDate senza fuso
# quando c'e' l'ora, perche' "le 21" senza fuso non e' un istante.
DATA_RE = re.compile(r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?([+-]\d{2}:\d{2}|Z))?$')

# I campi che Google richiede per un Event: senza, l'elemento non e' valido.
# https://developers.google.com/search/docs/appearance/structured-data/event
EVENT_OBBLIGATORI = ('name', 'startDate', 'location')
# Consigliati: l'elemento resta valido ma il rich result esce piu' povero.
EVENT_CONSIGLIATI = ('endDate', 'description', 'image', 'url', 'eventStatus',
                     'eventAttendanceMode')


def _quando(v):
    """La stringa di data, se e' una data ISO leggibile; None altrimenti."""
    if not isinstance(v, str) or not DATA_RE.match(v):
        return None
    return v


def _confrontabili(a, b):
    """Le due date rese confrontabili: una data nuda vale mezzanotte."""
    def norm(s):
        return s if 'T' in s else s + 'T00:00+02:00'
    try:
        return (datetime.datetime.fromisoformat(norm(a).replace('Z', '+00:00')),
                datetime.datetime.fromisoformat(norm(b).replace('Z', '+00:00')))
    except ValueError:
        return None, None


def controlla_event(ev, dove, err, avv):
    nome = (ev.get('name') or '(senza nome)')[:48]
    for k in EVENT_OBBLIGATORI:
        if not ev.get(k):
            err.append((dove, f"Event senza {k}", nome))
    for k in EVENT_CONSIGLIATI:
        if not ev.get(k):
            avv.append((dove, f"Event senza {k}", nome))

    inizio, fine = ev.get('startDate'), ev.get('endDate')
    if inizio and not _quando(inizio):
        err.append((dove, f"startDate non ISO 8601: {inizio!r}", nome))
    if fine and not _quando(fine):
        err.append((dove, f"endDate non ISO 8601: {fine!r}", nome))
    if _quando(inizio) and _quando(fine):
        a, b = _confrontabili(inizio, fine)
        if a and b and b < a:
            err.append((dove, f"endDate PRIMA di startDate ({inizio} -> {fine})", nome))

    loc = ev.get('location') or {}
    if loc and not (loc.get('address') or loc.get('name')):
        err.append((dove, "location senza address né name", nome))
    ind = loc.get('address') if isinstance(loc.get('address'), dict) else {}
    if ind and not ind.get('addressLocality'):
        avv.append((dove, "address senza addressLocality", nome))

    img = ev.get('image')
    if isinstance(img, list):
        if not img or not all(isinstance(u, str) and u.startswith('http') for u in img):
            err.append((dove, "image non è una lista di URL assoluti", nome))
    elif isinstance(img, str) and not img.startswith('http'):
        err.append((dove, "image non è un URL assoluto", nome))

    of = ev.get('offers')
    if isinstance(of, dict):
        # Un'offerta incompleta e' la causa piu' comune degli avvisi di Search
        # Console: o e' completa o e' meglio non dichiararla.
        for k in ('price', 'priceCurrency', 'url'):
            if not of.get(k) and of.get('price') != "0":
                avv.append((dove, f"offers senza {k}", nome))


def controlla_file(path, err, avv):
    dove = os.path.relpath(path, ROOT)
    testo = open(path, encoding='utf-8').read()
    blocchi = BLOCCO_RE.findall(testo)
    if not blocchi:
        avv.append((dove, "nessun blocco JSON-LD", ''))
        return 0
    quanti = 0
    for grezzo in blocchi:
        try:
            dati = json.loads(grezzo)
        except ValueError as e:
            err.append((dove, f"JSON-LD illeggibile: {e}", ''))
            continue
        nodi = dati.get('@graph') or [dati]
        # Un @id ripetuto dentro la stessa pagina fa fondere due nodi diversi in
        # uno solo: e' un errore che non si vede finche' non manca un campo.
        visti = collections.Counter(n.get('@id') for n in nodi if n.get('@id'))
        for k, n in visti.items():
            if n > 1:
                err.append((dove, f"@id ripetuto {n} volte: {k}", ''))
        for n in nodi:
            if n.get('@type') == 'Event':
                controlla_event(n, dove, err, avv)
                quanti += 1
    return quanti


def bersagli(argomenti):
    if argomenti:
        return [os.path.join(ROOT, a) for a in argomenti]
    fuori = {'404.html', 'cookypolicy.html', 'google530a563f75bb4d81.html'}
    files = sorted(glob.glob(os.path.join(ROOT, '*.html')))
    files += sorted(glob.glob(os.path.join(ROOT, 'eventi', '**', '*.html'), recursive=True))
    files += sorted(glob.glob(os.path.join(ROOT, 'rubriche', '*.html')))
    return [f for f in files if os.path.basename(f) not in fuori]


def main(argomenti):
    err, avv = [], []
    files = bersagli(argomenti)
    eventi = sum(controlla_file(f, err, avv) for f in files if os.path.exists(f))

    print(f"[valida_jsonld] {len(files)} pagine, {eventi} Event dichiarati")
    if avv:
        # Gli avvisi si contano per tipo: 250 righe "Event senza description"
        # non si leggono, "250x Event senza description" si'.
        print(f"[valida_jsonld] {len(avv)} avvisi (l'elemento resta valido):")
        for motivo, n in collections.Counter(m for _, m, _ in avv).most_common():
            esempio = next(d for d, m, _ in avv if m == motivo)
            print(f"    {n:5}x  {motivo}   (es. {esempio})")
    if err:
        print(f"[valida_jsonld] {len(err)} ERRORI (per Google l'elemento NON è valido):")
        for dove, motivo, nome in err:
            print(f"    {dove}: {motivo}" + (f"  [{nome}]" if nome else ""))
        print("[valida_jsonld] un Event non valido fa perdere alla pagina le date "
              "e il badge evento in SERP: va sistemato prima di pubblicare.")
        return 1
    print("[valida_jsonld] nessun errore.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
