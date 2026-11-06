"""Le stagionali prendono la festa dal nome dell'evento, non dal nome del posto.

Nata il 10/10/2026: «Un Mondo di Mattoncini - Centro per le Famiglie Villa
Zucca» finiva su /halloween.html e su /halloween-provincia-alessandria.html,
perche' la zucca nel titolo vale Halloween (TEMI_SOLO_TITOLO) e Villa Zucca e'
un posto di Arquata Scrivia. Qui si prova in_tema() nei due versi: il posto
non basta, la zucca vera si'. Offline, nessun dato del foglio.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as G  # noqa: E402

esito = True


def verifica(cosa, ok):
    global esito
    print(("  OK  " if ok else "  NO  ") + cosa)
    esito = esito and ok


def ev(nome, descr=''):
    return {'nome': nome, 'descr': descr}


print("── il nome di un posto non e' la festa ──")
for nome in ("Un Mondo di Mattoncini - Centro per le Famiglie Villa Zucca",
             "Sicurezza e Benessere Neonato - Centro per le Famiglie Villa Zucca / CSP Arquata Scrivia",
             "Pranzo in Cascina Zucca",
             "Mercato di Piazza Zucca"):
    verifica(f"fuori: {nome}", not G.in_tema(ev(nome), 'halloween'))

print("\n── la zucca come tema resta ──")
for nome in ("Ciaurin - L'Orto delle Zucche",
             "Zucche in Fuga - Az. Agricola La Cascinetta",
             "Sale in Zucca - Pro Loco di Sale",
             "Laboratorio: intaglia la tua zucca"):
    verifica(f"dentro: {nome}", G.in_tema(ev(nome), 'halloween'))

print("\n── Villa Zucca con Halloween scritto resta Halloween ──")
verifica("la festa di Halloween a Villa Zucca entra",
         G.in_tema(ev("Festa di Halloween - Centro per le Famiglie Villa Zucca"),
                   'halloween'))

print("\n── le pagine delle feste prendono solo la festa ──")
# /natale.html diceva «22 eventi di dicembre» e di Natale ce n'erano due: il
# resto erano laboratori settimanali con una data in dicembre.
import datetime  # noqa: E402

stagioni = {s.chiave: s for s in G.STAGIONI}
oggi = datetime.date(2026, 10, 10)


def riga(nome, giorno, descr=''):
    return {'nome': nome, 'descr': descr, 'citta': 'Bra',
            'd_start': giorno, 'd_end': giorno}


dic = datetime.date(2026, 12, 12)
eventi = [riga("Magic English - Playing & Learning", dic),
          riga("Bibliobebè con Floriana", dic),
          riga("Arriva Babbo Natale in piazza", dic),
          riga("Presepe vivente", dic)]
nomi = {e['nome'] for e in G._stagione_dati(stagioni['natale'], eventi, oggi)[3]}
verifica(f"Natale: solo le feste di Natale ({sorted(nomi)})",
         nomi == {"Arriva Babbo Natale in piazza", "Presepe vivente"})

cap = datetime.date(2026, 12, 29)
eventi = [riga("Laboratorio di pittura", cap),
          riga("Presepe vivente", cap),
          riga("Countdown dei bambini", datetime.date(2026, 12, 31))]
nomi = {e['nome'] for e in G._stagione_dati(stagioni['capodanno'], eventi, oggi)[3]}
verifica(f"Capodanno: la sua festa e i presepi ancora aperti ({sorted(nomi)})",
         nomi == {"Presepe vivente", "Countdown dei bambini"})

ago = datetime.date(2027, 8, 15)
eventi = [riga("Laboratorio di pittura", ago)]
verifica("Ferragosto resta un filtro di date",
         len(G._stagione_dati(stagioni['ferragosto'], eventi, oggi)[3]) == 1)

# ---- La colonna Festa, scritta dal modello nel downloader (06/11/2026) ----
cris = riga("Mercatini sotto il Monviso - Comune di Crissolo", datetime.date(2026, 11, 29),
            "Mercatini di Natale tra le strade di Crissolo")
cris['festa'] = 'mercatino di natale'
verifica("Festa = mercatino di natale: e' un mercatino e un evento di Natale",
         G.e_mercatino_natale(cris) and G.in_tema(cris, 'natale'))
ceci = riga("Festa dei Ceci & Shopping", datetime.date(2026, 11, 15), "shopping natalizio")
ceci['festa'] = 'nessuna'
verifica("Festa = nessuna vince sulle parole («natalizio» nel programma)", not G.in_tema(ceci, 'natale'))
pres = riga("Rassegna", datetime.date(2026, 12, 8), "")
pres['festa'] = 'Presepe '
verifica("Festa = presepe (maiuscole e spazi non contano): sta nel Natale, non fra i mercatini",
         G.in_tema(pres, 'natale') and not G.e_mercatino_natale(pres))
vuota = riga("Arriva Babbo Natale in piazza", dic)
verifica("cella vuota: decidono le parole come prima", G.in_tema(vuota, 'natale'))
strana = riga("Arriva Babbo Natale in piazza", dic)
strana['festa'] = 'natalle'
verifica("valore sconosciuto (refuso): decidono le parole", G.in_tema(strana, 'natale'))

# ---- La riga di Natale in cima all'agenda (06/11/2026) ----
def merc(citta, prov, g, festa='mercatino di natale'):
    e = riga(f"Mercatino di {citta}", g)
    e.update(citta=citta, prov=prov, festa=festa)
    return e
nov = datetime.date(2026, 11, 6)
ev = ([merc(f"C{i}", 'CN', datetime.date(2026, 11, 21 + i)) for i in range(3)]
      + [merc("A1", 'AT', datetime.date(2026, 11, 29))]
      + [dict(riga(f"Natale {i}", datetime.date(2026, 12, 2 + i)), festa='natale', prov='AL')
         for i in range(5)])
r = G.blocco_stagione(ev, nov)
verifica("riga di Natale: i mercatini della provincia in indice, col numero", 'mercatini-di-natale-provincia-cuneo.html">Cuneo (3)' in r)
verifica("…non la provincia sotto soglia (Asti, 1 mercatino)", 'provincia-asti' not in r)
verifica("…«dal 21 novembre» prima che comincino", 'dal 21 novembre' in r)
verifica("…e /natale.html col numero della sua pagina",
         'href="/natale.html">Tutto il Natale: i 5 eventi' in r)
verifica("prima del 6 novembre la riga non c'e'", G.blocco_stagione(ev, datetime.date(2026, 11, 5)) == '')

print("\nTUTTO OK" if esito else "\nQUALCOSA NON VA")
sys.exit(0 if esito else 1)
