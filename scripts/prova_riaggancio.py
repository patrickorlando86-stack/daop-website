#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla il RIAGGANCIO DELL'EDIZIONE: che la sagra dell'anno prossimo aggiorni
la pagina di quest'anno invece di aprirne una nuova che riparte da zero.

PERCHE' ESISTE (30/08/2026). Lo slug e' evergreen apposta - slug_evento toglie
l'anno e il numero di edizione - ma si ricava dal NOME, e il nome lo riscrive
ogni anno chi compila il foglio. Basta che la coda "- Pro Loco Grondona" ci sia
un anno e manchi l'altro, e l'indirizzo cambia: sul registro del 30/08/2026 sono
107 nomi su 412 a portare quella coda, e fra le 40 schede piu' visitate sono 5 -
ma dentro ci sono la prima pagina del sito (Grondona, 490 clic) e la quarta per
impressioni nelle AI features (Belforte, 265). C'era anche un buco in cifre: il
numero di edizione in numeri ROMANI ("XXVII Sagra delle Trofie al Pesto") non
veniva tolto affatto.

Le sette cose che questo script tiene ferme:
  1. il ROMANO in testa al nome esce dallo slug, e la XXVIII aggiorna la XXVII;
  2. un romano che NON e' un numero di edizione resta ("Settembre II"), e cosi'
     le preposizioni che sono romani validi ("Il", "Di", "Mi");
  3. il RIAGGANCIO: nome scritto diversamente, stesso comune, stesso periodo ->
     stessa pagina;
  4. la PRUDENZA: due candidati non si scelgono, si apre una pagina nuova (che
     e' quello che succederebbe comunque senza tutto questo);
  5. il CONFINE: un evento diverso nello stesso comune non viene mai
     agganciato, e nemmeno lo stesso nome a sei mesi di distanza;
  6. la PRECEDENZA: uno slug gia' preso da un altro evento della stessa run non
     si ruba - e' la guardia sui sotto-eventi della stessa manifestazione;
  7. l'INVARIANTE SUL REGISTRO VERO: simulando i nomi del 2027 su tutte le
     schede, gli agganci SBAGLIATI devono essere ZERO. E' l'unica proprieta'
     che conta davvero: una URL nuova e' una perdita, una pagina scritta sopra
     quella di un altro evento e' un danno.

Uso:
    python scripts/prova_riaggancio.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca il sito: il
registro vero si legge e basta.
"""
import datetime
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as g

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

errori = []


def ok(cond, testo, extra=""):
    print(("  ok  " if cond else "  NO  ") + testo + (f"   [{extra}]" if extra and not cond else ""))
    if not cond:
        errori.append(testo)


def rec(nome, citta, di, **kw):
    d = datetime.datetime.strptime(di, "%d/%m/%Y").date()
    r = {'nome': nome, 'citta': citta, 'di': di, 'd_start': d.isoformat()}
    r.update(kw)
    return r


def ev(nome, citta, di):
    return {'nome': nome, 'citta': citta, 'd_start': datetime.datetime.strptime(di, "%d/%m/%Y").date()}


print("\n1. Il numero di edizione romano esce dallo slug")
s26 = g.slug_evento(ev("XXVII Sagra delle Trofie al Pesto", "Belforte Monferrato", "26/08/2026"))
s27 = g.slug_evento(ev("XXVIII Sagra delle Trofie al Pesto", "Belforte Monferrato", "25/08/2027"))
ok(s26 == s27, "XXVII e XXVIII danno lo stesso slug", f"{s26} != {s27}")
ok("xxvii" not in s26, "il numero romano non finisce nell'indirizzo", s26)

print("\n2. Un romano che non e' un numero di edizione resta dov'e'")
for nome, pezzo in [("A Calosso Museo e Dintorni - Settembre II", "settembre-ii"),
                    ("Il Borgo Diventa Osteria", "il-borgo"),
                    ("Di Vino in Vino", "di-vino"),
                    ("Mi Ci Vedo", "mi-ci-vedo")]:
    sl = g.slug_evento(ev(nome, "Calosso", "05/09/2026"))
    ok(pezzo in sl, f"\"{nome}\" tiene il suo inizio", sl)

print("\n3. Il riaggancio riconosce l'edizione dopo col nome riscritto")
reg = {
    "sagra-della-capra-e-della-fersulla-pro-loco-grondo-grondona":
        rec("Sagra della Capra e della Fersulla - Pro Loco Grondona", "Grondona", "22/08/2026"),
}
nuovo = ev("41ª Sagra della Capra e della Fersulla 2027", "Grondona", "21/08/2027")
cand = g.candidati_edizione(nuovo, reg, set())
ok(cand == ["sagra-della-capra-e-della-fersulla-pro-loco-grondo-grondona"],
   "senza la coda dell'organizzatore ritrova la sua pagina", str(cand))

print("\n4. Due candidati: non si sceglie")
reg_amb = {
    "apertura-stand-gastronomico-con-shary-band-rocchetta-tanaro":
        rec("Apertura Stand Gastronomico con Shary Band", "Rocchetta Tanaro", "14/08/2026"),
    "apertura-stand-gastronomico-e-shary-band-rocchetta-tanaro":
        rec("Apertura Stand Gastronomico e Shary Band", "Rocchetta Tanaro", "14/08/2026"),
}
cand = g.candidati_edizione(ev("Apertura Stand Gastronomico con Shary Band 2027",
                               "Rocchetta Tanaro", "13/08/2027"), reg_amb, set())
ok(len(cand) == 2, "i due candidati si vedono tutti e due", str(cand))

print("\n5. Il confine: cosa NON si aggancia")
reg_altro = {
    "sagra-della-trippa-novi-ligure": rec("Sagra della Trippa", "Novi Ligure", "20/08/2026"),
    "sagra-della-zucca-castelletto-monferrato": rec("Sagra della Zucca", "Castelletto Monferrato", "20/08/2026"),
}
ok(g.candidati_edizione(ev("Sagra del Raviolo", "Novi Ligure", "20/08/2027"), reg_altro, set()) == [],
   "un evento diverso nello stesso comune non si aggancia")
ok(g.candidati_edizione(ev("Sagra della Trippa", "Castelletto Monferrato", "20/08/2027"), reg_altro, set()) == [],
   "lo stesso nome in un altro comune non si aggancia")
ok(g.candidati_edizione(ev("Sagra della Trippa", "Novi Ligure", "20/02/2027"), reg_altro, set()) == [],
   "lo stesso nome a sei mesi di distanza non si aggancia")
ok(g.candidati_edizione(ev("Sagra della Trippa", "Novi Ligure", "28/08/2027"), reg_altro, set()) != [],
   "ma un weekend piu' in la' si")
reg_rit = {"x": rec("Sagra della Trippa", "Novi Ligure", "20/08/2026", ritirata=True),
           "y": rec("Sagra del Bollito", "Novi Ligure", "20/08/2026", spostata="z")}
ok(g.candidati_edizione(ev("Sagra della Trippa", "Novi Ligure", "20/08/2027"), reg_rit, set()) == [],
   "una pagina ritirata o spostata non si riusa")

print("\n6. Uno slug gia' preso in questa run non si ruba")
cand = g.candidati_edizione(ev("41ª Sagra della Capra e della Fersulla 2027", "Grondona", "21/08/2027"),
                            reg, {"sagra-della-capra-e-della-fersulla-pro-loco-grondo-grondona"})
ok(cand == [], "lo slug rivendicato da un altro evento resta suo", str(cand))

print("\n7. Sul registro vero: zero agganci sbagliati coi nomi del 2027")
ROOT = g.ROOT
vero = json.load(open(os.path.join(ROOT, "data", "pagine-evento.json"), encoding="utf-8"))
# Le pagine ritirate e quelle spostate restano fuori dalla simulazione, come
# restano fuori dai candidati: non sono pagine da aggiornare, sono cartelli. Ed
# e' un caso vero, non teorico - il foglio ha avuto due righe per lo stesso
# laboratorio a Crissolo, una delle due ritirata: la sua edizione 2027 va sulla
# gemella viva, ed e' la cosa giusta, non un aggancio sbagliato.
schede = {s: r for s, r in vero.items()
          if isinstance(r, dict) and r.get('nome') and r.get('di')
          and not r.get('ritirata') and not r.get('spostata')}


def nome_2027(n):
    n = re.sub(r'\b2026\b', '2027', n)
    n = re.sub(r'(?<!\w)(\d+)\s*([°ºª^])', lambda m: f"{int(m.group(1)) + 1}{m.group(2)}", n)
    return g.ORGANIZZATORE_RE.sub('', n).strip(' -–—')


uguali = giusti = ambigui = sbagliati = persi = 0
esempi_sbagliati = []
for slug, r in schede.items():
    n2 = nome_2027(r['nome'])
    d = datetime.datetime.strptime(r['di'], "%d/%m/%Y").date()
    try:
        d2 = d.replace(year=d.year + 1) + datetime.timedelta(days=4)
    except ValueError:
        continue
    e2 = {'nome': n2, 'citta': r.get('citta'), 'd_start': d2}
    if g.slug_evento(e2) == slug:
        uguali += 1
        continue
    cand = g.candidati_edizione(e2, schede, set())
    if len(cand) == 1 and cand[0] == slug:
        giusti += 1
    elif len(cand) == 1:
        sbagliati += 1
        esempi_sbagliati.append((r['nome'], cand[0]))
    elif cand:
        ambigui += 1
    else:
        persi += 1
print(f"     {len(schede)} schede: slug identico {uguali}, riagganciate {giusti}, "
      f"ambigue {ambigui}, pagina nuova {persi}, SBAGLIATE {sbagliati}")
for n, c in esempi_sbagliati[:5]:
    print(f"       \"{n[:44]}\" -> {c}")
ok(sbagliati == 0, "nessuna edizione scrive sulla pagina di un altro evento")
ok(uguali + giusti >= 0.9 * len(schede),
   "almeno il 90% delle schede sopravvive a un nome riscritto",
   f"{uguali + giusti}/{len(schede)}")

print()
if errori:
    print(f"{len(errori)} controlli falliti:")
    for e in errori:
        print("   -", e)
    sys.exit(1)
print("Tutto a posto.")
