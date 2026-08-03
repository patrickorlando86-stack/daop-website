#!/usr/bin/env python3
"""
Pubblica sulle pagine Facebook di DAOP gli articoli delle rubriche appena usciti.

Come si incastra col resto
--------------------------
Gli articoli escono da soli: genera_rubriche.py pubblica solo quelli con la
`data` gia' passata, e la run notturna li fa comparire sul sito. Questo script
gira DOPO, a giorno fatto (workflow pubblica-social.yml), e posta sulle pagine
il link degli articoli usciti di recente.

Perche' dopo e non nella stessa run: quando Facebook riceve un link va a
leggerlo subito per costruire l'anteprima, e si tiene in cache quello che
trova. Se postassimo un istante dopo il commit, la pagina non sarebbe ancora
online e nell'anteprima resterebbe un 404 per giorni.

Fonte dati
  - data/rubriche.json + contenuti/rubriche/**.md   gli stessi testi del sito
  - data/social.json                                pagine, finestra, versione API
  - data/social-pubblicati.json                     registro di cosa e' gia' uscito

Il registro e' cio' che impedisce i doppioni: un articolo viene postato una
volta sola per pagina, per sempre. La finestra in giorni e' la seconda rete di
sicurezza: se il registro si perdesse, non ripartirebbero comunque dodici post
di arretrati.

Uso
    python scripts/pubblica_facebook.py            pubblica davvero
    python scripts/pubblica_facebook.py --prova    stampa i post e non chiama Facebook
    python scripts/pubblica_facebook.py --segna-tutti
                                                   marca come gia' usciti tutti gli
                                                   articoli online (da fare una volta,
                                                   prima di accendere l'automatismo)
    python scripts/pubblica_facebook.py --pagine   elenca le pagine e i loro ID
                                                   partendo da FB_USER_TOKEN

I token stanno solo nelle variabili d'ambiente indicate da `token_env` in
data/social.json (nei secret del repository su GitHub). Nel repository non
finisce mai un token.
"""
import os, re, sys, json, argparse, datetime, unicodedata
import urllib.request, urllib.parse, urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_rubriche as gr

# Il terminale Windows e' a cp1252: un titolo con un carattere fuori tabella
# farebbe morire lo script su una print. Su GitHub Actions e' utf-8 e non
# cambia nulla.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')

ROOT = gr.ROOT
CONFIG_PATH = os.path.join(ROOT, "data", "social.json")
REGISTRO_PATH = os.path.join(ROOT, "data", "social-pubblicati.json")
SITE_URL = gr.SITE_URL


# ------------------------------------------------------------------ config

def carica_config():
    if not os.path.exists(CONFIG_PATH):
        raise SystemExit(f"[facebook] manca {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding='utf-8') as fh:
        cfg = json.load(fh).get('facebook', {})
    cfg.setdefault('attiva', False)
    cfg.setdefault('api_version', 'v23.0')
    cfg.setdefault('finestra_giorni', 7)
    cfg.setdefault('pagine', [])
    return cfg


def carica_registro():
    if not os.path.exists(REGISTRO_PATH):
        return {}
    with open(REGISTRO_PATH, encoding='utf-8') as fh:
        return json.load(fh).get('facebook', {})


def salva_registro(reg):
    payload = {
        "_nota": ("Registro dei post gia' usciti su Facebook, scritto da "
                  "scripts/pubblica_facebook.py. Serve a non pubblicare due volte "
                  "lo stesso articolo: se lo cancelli, gli articoli dentro la "
                  "finestra di giorni tornano a essere postabili."),
        "facebook": reg,
    }
    with open(REGISTRO_PATH, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write('\n')


# -------------------------------------------------------------- testo post

def hashtag(tag):
    """'educazione alimentare' -> '#educazionealimentare'. Niente accenti e
    niente maiuscole: su Facebook gli hashtag con caratteri accentati si
    spezzano a meta'."""
    t = unicodedata.normalize('NFKD', tag).encode('ascii', 'ignore').decode()
    return '#' + re.sub(r'[^a-z0-9]', '', t.lower())


def testo_post(a, rub, aut):
    """Titolo in cima perche' Facebook taglia dopo poche righe con 'Altro':
    quello che convince a espandere deve stare nelle prime due."""
    tag = [hashtag(t) for t in a['tag'][:4]]
    tag = [t for t in tag if len(t) > 3]
    if '#daop' not in tag:
        tag.append('#daop')
    firma = f"{rub['nome']} — la rubrica di {aut['nome']}, {aut['titolo'].lower()}"
    return "\n".join([
        a['titolo'],
        "",
        a['sommario'],
        "",
        firma,
        "",
        " ".join(tag),
    ])


def url_articolo(a):
    return f"{SITE_URL}/rubriche/{a['slug']}.html"


# ------------------------------------------------------------------- graph

def graph(cfg, path, params, metodo='GET'):
    base = f"https://graph.facebook.com/{cfg['api_version']}/{path}"
    dati = urllib.parse.urlencode(params).encode()
    req = (urllib.request.Request(base, data=dati, method='POST') if metodo == 'POST'
           else urllib.request.Request(f"{base}?{dati}"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        # Il corpo dell'errore di Facebook dice sempre cosa manca (permesso,
        # token scaduto, versione API ritirata): senza, si resta a indovinare.
        corpo = e.read().decode('utf-8', 'replace')
        try:
            msg = json.loads(corpo)['error']['message']
        except Exception:
            msg = corpo[:400]
        raise RuntimeError(f"HTTP {e.code} — {msg}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"rete non raggiungibile: {e.reason}")


def elenca_pagine(cfg, con_token=False):
    """Stampa nome e ID delle pagine amministrate, per riempire data/social.json.

    Con --con-token stampa anche il token di pagina: se FB_USER_TOKEN e' un
    token utente a lunga durata, quello di pagina che ne deriva non scade ed
    e' esattamente il valore da mettere nei secret. Sta dietro a un flag
    apposta: e' un segreto, non deve finire in un log per sbaglio."""
    token = os.environ.get('FB_USER_TOKEN', '').strip()
    if not token:
        raise SystemExit("[facebook] serve FB_USER_TOKEN (token utente) in ambiente")
    campi = 'name,id,access_token' if con_token else 'name,id'
    res = graph(cfg, 'me/accounts', {'fields': campi, 'limit': 100,
                                     'access_token': token})
    print("[facebook] pagine amministrate da questo utente:")
    for p in res.get('data', []):
        print(f"    {p['id']}   {p['name']}")
        if con_token and p.get('access_token'):
            print(f"        token: {p['access_token']}")
    if not res.get('data'):
        print("    nessuna: il token non ha il permesso pages_show_list "
              "o l'utente non amministra pagine")


# -------------------------------------------------------------------- main

def articoli_da_postare(cfg, oggi, tutti=False, anche_da_verificare=False):
    _cfg, rubriche, autori, articoli = gr.carica()
    pubblicati = [a for a in articoli if a['data'] <= oggi]
    if not tutti:
        limite = oggi - datetime.timedelta(days=cfg['finestra_giorni'])
        pubblicati = [a for a in pubblicati if a['data'] >= limite]
    fuori = []
    if not anche_da_verificare:
        # Pillole Fiscali ha cifre marcate 'verificare:' in attesa di conferma
        # dall'autrice. Un post su Facebook e' molto piu' difficile da
        # correggere di una pagina del sito: finche' il dato non e' confermato
        # l'articolo resta online ma non lo si spinge.
        fuori = [a for a in pubblicati if a['verificare']]
        pubblicati = [a for a in pubblicati if not a['verificare']]
    return rubriche, autori, pubblicati, fuori


def main():
    ap = argparse.ArgumentParser(description="Pubblica su Facebook gli articoli delle rubriche")
    ap.add_argument('--prova', action='store_true',
                    help="stampa i post senza chiamare Facebook")
    ap.add_argument('--segna-tutti', action='store_true',
                    help="segna come gia' usciti tutti gli articoli online, senza postare")
    ap.add_argument('--pagine', action='store_true',
                    help="elenca le pagine e i loro ID partendo da FB_USER_TOKEN")
    ap.add_argument('--con-token', action='store_true',
                    help="con --pagine, stampa anche il token di pagina da mettere nei secret")
    ap.add_argument('--anche-da-verificare', action='store_true',
                    help="posta anche gli articoli con dati non ancora confermati")
    args = ap.parse_args()

    cfg = carica_config()
    if args.pagine:
        elenca_pagine(cfg, con_token=args.con_token)
        return 0

    oggi = datetime.date.today()
    registro = carica_registro()

    # --segna-tutti non guarda la finestra: serve proprio a coprire l'arretrato
    rubriche, autori, candidati, fuori = articoli_da_postare(
        cfg, oggi, tutti=args.segna_tutti,
        anche_da_verificare=args.anche_da_verificare)

    pagine = [p for p in cfg['pagine'] if p.get('attiva', True)]

    if args.segna_tutti:
        # Il registro e' indicizzato per page_id: senza gli ID scriverebbe
        # voci vuote, buone a niente, e domani ripartirebbe l'arretrato.
        if any(not str(p.get('page_id') or '').strip() for p in pagine):
            raise SystemExit("[facebook] prima riempi page_id in data/social.json "
                             "(li trovi con --pagine): il registro si indicizza su quelli")
        for a in candidati:
            voce = registro.setdefault(a['slug'], {})
            for p in pagine:
                voce.setdefault(str(p['page_id']), {
                    'pagina': p['nome'],
                    'post_id': None,
                    'quando': None,
                    'nota': 'segnato a mano, mai postato',
                })
        salva_registro(registro)
        print(f"[facebook] segnati come gia' usciti {len(candidati)} articoli "
              f"su {len(pagine)} pagine. Da ora escono solo i nuovi.")
        return 0

    if not cfg['attiva'] and not args.prova:
        print("[facebook] pubblicazione disattivata in data/social.json "
              "(\"attiva\": false). Niente da fare.")
        return 0

    if not pagine:
        print("[facebook] nessuna pagina configurata in data/social.json.")
        return 0

    if fuori:
        print(f"[facebook] {len(fuori)} articoli non postati: hanno ancora dati "
              f"da far confermare all'autrice")
        for a in fuori:
            print(f"    {a['data']}  {gr.trunc(a['titolo'], 60)}")

    errori = 0
    postati = 0
    cambiato = False

    for a in sorted(candidati, key=lambda x: x['data']):
        rub = rubriche[a['rubrica']]
        aut = autori[rub['autore']]
        messaggio = testo_post(a, rub, aut)
        link = url_articolo(a)

        if args.prova:
            # Il post e' identico su tutte le pagine: si stampa una volta sola,
            # con l'elenco di chi lo riceverebbe (chi l'ha gia' avuto e' fuori).
            restanti = [p for p in pagine
                        if not registro.get(a['slug'], {}).get(str(p.get('page_id') or ''))]
            if not restanti:
                continue
            print(f"\n--- {a['data']}  {a['slug']}  ->  "
                  f"{', '.join(p['nome'] for p in restanti)} " + "-" * 12)
            for riga in (messaggio + "\n\n" + link).split('\n'):
                print(f"| {riga}" if riga else "|")
            print("-" * 74)
            continue

        for p in pagine:
            page_id = str(p.get('page_id') or '').strip()
            if not page_id:
                print(f"[facebook] {p['nome']}: manca page_id in data/social.json, salto "
                      f"(prendilo con --pagine)")
                continue
            if registro.get(a['slug'], {}).get(page_id):
                continue

            token = os.environ.get(p.get('token_env', ''), '').strip()
            if not token:
                print(f"[facebook] {p['nome']}: manca il token nella variabile "
                      f"{p.get('token_env')}, salto")
                continue

            try:
                res = graph(cfg, f"{page_id}/feed",
                            {'message': messaggio, 'link': link,
                             'access_token': token}, metodo='POST')
            except RuntimeError as e:
                print(f"[facebook] ERRORE su {p['nome']} · {a['slug']}: {e}")
                errori += 1
                continue

            registro.setdefault(a['slug'], {})[page_id] = {
                'pagina': p['nome'],
                'post_id': res.get('id'),
                'quando': datetime.datetime.now(datetime.timezone.utc)
                          .replace(microsecond=0).isoformat(),
            }
            cambiato = True
            postati += 1
            print(f"[facebook] pubblicato su {p['nome']}: {gr.trunc(a['titolo'], 56)} "
                  f"({res.get('id')})")

    if cambiato:
        salva_registro(registro)

    if not postati and not errori and not args.prova:
        print("[facebook] nessun articolo nuovo da pubblicare.")

    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
