#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Le illustrazioni del francobollo dei corsi: da un disegno grande a un file
da mettere in pagina.

PERCHE' ESISTE (08/09/2026). Il francobollo di ogni corso su corsi.html era un
disegno a linea da 24px in mezzo a un quadrato da 60. Nella stessa posizione
l'agenda mostra la miniatura della locandina, che il quadrato lo riempie: 155
righe su 156. Quindi la cosa fuori posto era l'icona, non l'illustrazione - e
si e' deciso di passare a disegni veri.

Un disegno vero pero' arriva come lo sputa fuori un generatore di immagini:
PNG, 1024x1024, un megabyte. Quello in pagina non ci va - sono ~10-30 file, e
finirebbero in git e dentro un francobollo da 60px. E' lo stesso conto di
genera_miniature.py, e la divisione del lavoro e' identica: qui si normalizza,
genera_corsi.py si limita a guardare se il file c'e'.

    assets/icone/sorgenti/movimento.png   <- il disegno come te lo danno
    assets/icone/movimento.webp           <- quello che va in pagina

I SORGENTI SI TENGONO IN GIT, e non e' per abitudine: un'illustrazione persa si
rifa' generandola un'altra volta, e la seconda volta lo STILE NON TORNA - che e'
l'unica cosa capace di rovinare un set intero. Costa ~1 MB di blob per file,
una volta sola, e vale quel prezzo.

LA RETE DI SICUREZZA: un raster trovato direttamente in assets/icone/ viene
SPOSTATO in sorgenti/ e lo si dice nel log. Cosi' l'unica cosa da ricordare
resta quella scritta nel LEGGIMI - "butta il file in quella cartella" - e chi
si dimentica la sottocartella non resta con un PNG da un megabyte servito ai
lettori.

    python3 scripts/genera_icone.py
    python3 scripts/genera_icone.py --rifai        # rigenera anche i gia' fatti
    python3 scripts/genera_icone.py --sfondo-via   # vedi _senza_sfondo()

Senza Pillow non fa niente e lo dice: i .webp di ieri restano dove sono. E' la
regola di genera_centri.py quando non legge il foglio - meglio la cosa di ieri
che nessuna cosa.
"""
import argparse
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CARTELLA = os.path.join(ROOT, 'assets', 'icone')
SORGENTI = os.path.join(CARTELLA, 'sorgenti')

# Il lato del file che va in pagina. Il quadrato e' 60px (52 sul telefono), e
# 256 copre uno schermo a 4x senza pensarci: su un disegno piatto la differenza
# fra 180 e 256 e' qualche centinaio di byte, quindi si sta larghi una volta e
# non si torna piu' sull'argomento.
LATO = 256
QUALITA = 82

# I formati che si accettano come sorgente. Il .webp c'e' perche' qualche
# generatore di immagini lo esporta cosi': viene normalizzato come gli altri,
# non passa liscio per il fatto di avere gia' l'estensione giusta.
SORGENTI_OK = ('.png', '.webp', '.jpg', '.jpeg')

# Quanto puo' scostarsi un pixel dal colore dell'angolo e valere ancora
# "sfondo", con --sfondo-via. 40 su 255 tiene dentro le sfumature di un bianco
# che non e' proprio bianco senza mangiare il disegno.
TOLLERANZA = 40


def vocabolario():
    """I nomi di file che genera_corsi.py sa cercare, o None se non si leggono.

    Si LEGGONO DA LUI e non si riscrivono qui: due elenchi delle stesse parole
    divergono al primo ritocco, e la forma in cui divergono e' un'icona
    disegnata, pagata, messa in cartella, e che non compare da nessuna parte
    perche' si chiama in un modo che il generatore non guarda."""
    try:
        import genera_corsi as C
    except Exception as e:                                   # pragma: no cover
        print(f"[genera_icone] non riesco a leggere il dizionario dei nomi "
              f"({e}): salto il controllo sui nomi")
        return None
    return set(C.DISCIPLINE_ICONA.values()) | set(C.ICONE_CAT) | {'altro'}


def ricovera_sperse():
    """Sposta in sorgenti/ i raster buttati direttamente in assets/icone/.

    Non tocca i .svg, che in quella cartella ci stanno di diritto: sono i
    disegni a linea, e vanno in pagina cosi' come sono."""
    mossi = 0
    for f in sorted(os.listdir(CARTELLA)):
        pieno = os.path.join(CARTELLA, f)
        if not os.path.isfile(pieno):
            continue
        nome, est = os.path.splitext(f)
        if est.lower() not in SORGENTI_OK:
            continue
        # Il .webp che produciamo noi vive qui e non e' un file sperso: si
        # riconosce perche' in sorgenti/ c'e' il suo originale.
        if est.lower() == '.webp' and any(
                os.path.exists(os.path.join(SORGENTI, nome + e))
                for e in SORGENTI_OK):
            continue
        os.makedirs(SORGENTI, exist_ok=True)
        shutil.move(pieno, os.path.join(SORGENTI, f))
        print(f"[genera_icone] {f} era in assets/icone/: l'ho spostato in "
              f"sorgenti/ (li' ci va il disegno grande, non quello di pagina)")
        mossi += 1
    return mossi


def senza_sfondo(im, ImageDraw):
    """Toglie uno sfondo UNIFORME partendo dai quattro angoli, o lascia stare.

    Serve per il caso che capitera' di sicuro: si chiede un PNG con lo sfondo
    trasparente e arriva col fondo bianco. Un rettangolo bianco dentro il
    quadrato colorato della categoria si vede, ed e' brutto.

    Non e' magia e non pretende di esserlo: prende solo il fondo ATTACCATO agli
    angoli, quindi un buco chiuso (fra il braccio e il corpo) resta pieno, e
    sul bordo del disegno puo' restare un alone di antialiasing. La cura vera
    e' un sorgente trasparente; questo e' il ripiego, ed e' per questo che si
    chiede a mano con --sfondo-via invece di farlo sempre."""
    angoli = [(0, 0), (im.width - 1, 0), (0, im.height - 1),
              (im.width - 1, im.height - 1)]
    tinte = [im.getpixel(a) for a in angoli]
    base = tinte[0]
    if any(max(abs(t[i] - base[i]) for i in range(3)) > TOLLERANZA
           for t in tinte):
        print("[genera_icone]   i quattro angoli non hanno lo stesso colore: "
              "non e' uno sfondo uniforme, lo lascio com'e'")
        return im
    for a in angoli:
        ImageDraw.floodfill(im, a, (0, 0, 0, 0), thresh=TOLLERANZA)
    return im


def quadra(im, Image):
    """Mette il disegno dentro un quadrato trasparente.

    Cosi' il file ha sempre proporzione 1:1, che e' quella dichiarata
    nell'<img width="60" height="60"> di genera_corsi.py: un file 4:3 non
    romperebbe niente (object-fit: contain lo centra), ma con il quadrato la
    misura scritta in pagina e quella del file dicono la stessa cosa, e c'e'
    una cosa in meno che puo' andare storta."""
    if im.width == im.height:
        return im
    lato = max(im.width, im.height)
    tela = Image.new('RGBA', (lato, lato), (0, 0, 0, 0))
    tela.paste(im, ((lato - im.width) // 2, (lato - im.height) // 2))
    return tela


def scrivi(im, fuori):
    """Salva in webp scegliendo fra con perdita e senza, e tiene il piu' piccolo.

    Su un disegno piatto - pochi colori, campiture larghe - il senza perdita
    spesso VINCE anche in peso, oltre a non sgranare i contorni. Su un disegno
    con sfumature vince l'altro. Provarli tutti e due costa un decimo di
    secondo e toglie la domanda a chiunque la rifaccia."""
    prove = {}
    for etichetta, opzioni in (('con perdita', dict(quality=QUALITA, method=4)),
                               ('senza perdita', dict(lossless=True, method=4))):
        buf = io.BytesIO()
        im.save(buf, 'WEBP', **opzioni)
        prove[etichetta] = buf.getvalue()
    scelta = min(prove, key=lambda k: len(prove[k]))
    with open(fuori, 'wb') as fh:
        fh.write(prove[scelta])
    return scelta, len(prove[scelta])


def main():
    ap = argparse.ArgumentParser(
        description='Normalizza le illustrazioni del francobollo dei corsi.')
    ap.add_argument('--rifai', action='store_true',
                    help='rigenera anche le illustrazioni gia\' pronte')
    ap.add_argument('--sfondo-via', action='store_true',
                    help='prova a togliere uno sfondo pieno e uniforme')
    args = ap.parse_args()

    if not os.path.isdir(CARTELLA):
        print(f"[genera_icone] non c'e' {CARTELLA}: niente da fare")
        return 0

    ricovera_sperse()

    if not os.path.isdir(SORGENTI):
        print("[genera_icone] nessun disegno in assets/icone/sorgenti/: "
              "niente da fare")
        return 0

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[genera_icone] Pillow non c'e': lascio le icone come stanno "
              "(pip install Pillow)")
        return 0

    noti = vocabolario()
    fatti = saltati = 0
    for f in sorted(os.listdir(SORGENTI)):
        nome, est = os.path.splitext(f)
        if est.lower() not in SORGENTI_OK:
            continue
        dentro = os.path.join(SORGENTI, f)
        fuori = os.path.join(CARTELLA, f'{nome}.webp')

        if noti is not None and nome not in noti:
            print(f"[genera_icone] ATTENZIONE: '{nome}' non e' un nome che il "
                  f"generatore cerca, quindi questa illustrazione non "
                  f"comparira' in nessuna pagina. I nomi buoni stanno in "
                  f"assets/icone/LEGGIMI.md")

        if not args.rifai and os.path.exists(fuori) and \
                os.path.getmtime(fuori) >= os.path.getmtime(dentro):
            saltati += 1
            continue

        try:
            im = Image.open(dentro)
            im.load()
            im = im.convert('RGBA')
        except Exception as e:
            print(f"[genera_icone] {f} illeggibile ({e}): lascio quella di prima")
            continue

        if args.sfondo_via:
            im = senza_sfondo(im, ImageDraw)

        # L'avviso che serve davvero. Il quadrato del francobollo ha lo sfondo
        # del colore della categoria e si deve vedere attraverso il disegno: un
        # PNG opaco ci mette dentro un rettangolo, e in pagina si legge come un
        # errore. Lo si dice adesso, non lo si scopre guardando corsi.html.
        if im.getchannel('A').getextrema()[0] == 255:
            print(f"[genera_icone] ATTENZIONE: {f} non ha nessuna trasparenza. "
                  f"Nel francobollo si vedra' un rettangolo di sfondo dentro il "
                  f"quadrato colorato. Rigenera il disegno con lo sfondo "
                  f"trasparente, oppure riprova con --sfondo-via")

        # La misura del SORGENTE, presa prima di quadrare: se no il log
        # racconterebbe il quadrato che abbiamo appena fatto noi invece del
        # file che e' arrivato.
        prima = im.size
        im = quadra(im, Image)
        im.thumbnail((LATO, LATO), Image.LANCZOS)
        modo, peso = scrivi(im, fuori)
        print(f"[genera_icone] {f} {prima[0]}x{prima[1]} -> {nome}.webp "
              f"{im.width}x{im.height} {peso / 1024:.1f} KB ({modo})")
        fatti += 1

    print(f"[genera_icone] {fatti} illustrazioni scritte, "
          f"{saltati} gia' a posto")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
