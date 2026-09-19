# -*- coding: utf-8 -*-
"""prova_iscrizioni.py - «come ci si iscrive» adesso si legge in pagina.

IL BUCO CHE CHIUDE (19/09/2026). La colonna `Iscrizioni` della tab Attivita
stava in COLONNE dal primo giorno e non usciva da nessuna parte - ne' qui ne'
nell'app. L'unico posto in cui finiva era il cartellino "Iscrizioni
aperte/chiuse", tolto il 21/08/2026 su richiesta di Giovanni: ma quello era uno
STATO che invecchia, e insieme a lui e' uscito il TESTO, che e' un'altra cosa.
Intanto nel modulo con cui il partner corregge un corso il campo era rimasto, si
chiama «Come ci si iscrive» ed e' alto due righe: cioe' invitava a scrivere
qualcosa che non leggeva nessuno.

I NUMERI, contati sul foglio il 19/09: la cella e' piena su 19 righe su 97, e su
SEI di quelle il Contatto e' vuoto - li' dentro c'era l'unica indicazione su
come si entra in quel corso ("Iscriversi tramite WhatsApp al 3398550332", il
link del modulo di Teacher Noemi) e in pagina non compariva.

LE TRE REGOLE DIFESE QUI:
  1. la cella si STAMPA, fra la quota e i contatti: quanto costa, cosa devo
     fare, chi chiamo;
  2. i recapiti restano cliccabili, e l'INDIRIZZO WEB pure - un modulo
     d'iscrizione stampato come testo non ci porta nessuno. I numeri e le mail
     passano da contatti_html, la stessa della riga "Contatti": due
     riconoscimenti diversi per la stessa cosa divergono al primo caso storto;
  3. LA LEZIONE DEL 21/08 NON SI RIAPRE: una cella che porta una data passata
     si toglie, come la Prova. Si toglie la CELLA, non la riga.

Niente rete: `_scarica` e' finto e il "foglio" e' una stringa CSV qui dentro.
"""
import datetime
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import genera_corsi as C

esito = True


def verifica(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


# ── PARTE 1: come si compone la cella ─────────────────────────────────────
print()
print("=" * 70)
print("  LA CELLA, da testo a pagina")
print("=" * 70)

html = C.iscrizioni_html("Iscriversi tramite WhatsApp al 3398550332")
print("   ", html)
verifica("il numero diventa un link per chiamare", 'href="tel:3398550332"' in html)
verifica("...e il testo intorno resta com'e'",
         html.startswith("Iscriversi tramite WhatsApp al "))

html = C.iscrizioni_html("Prenota il posto: saluzzese@helendoron.com - 348.9598293")
verifica("la mail diventa mailto", 'href="mailto:saluzzese@helendoron.com"' in html)
verifica("...e il numero col punto pure", 'href="tel:3489598293"' in html)

html = C.iscrizioni_html("https://teachernoemi.my.canva.site/corsi")
print("   ", html)
verifica("un modulo d'iscrizione diventa un link",
         'href="https://teachernoemi.my.canva.site/corsi"' in html)
verifica("...sponsored, come «Scopri il corso»", 'rel="sponsored noopener"' in html)
verifica("...e si apre in una scheda nuova", 'target="_blank"' in html)

html = C.iscrizioni_html("Modulo qui https://esempio.it/iscrizioni entro venerdi")
print("   ", html)
verifica("il link in mezzo a una frase non mangia gli spazi",
         "Modulo qui <a" in html and "</a> entro venerdi" in html)

verifica("una cella senza recapiti resta testo",
         C.iscrizioni_html("Corso a numero chiuso") == "Corso a numero chiuso")
verifica("una cella vuota non stampa niente", C.iscrizioni_html("") == "")
verifica("...e nemmeno se e' fatta di spazi", C.iscrizioni_html("   ") == "")
# Il testo del foglio lo scrivono le persone: un "<" li' dentro non deve
# diventare un pezzo di pagina.
verifica("il testo si scherma",
         "&lt;" in C.iscrizioni_html("Si iscrive <chi vuole>"))

# ── PARTE 2: che finisca DAVVERO nella scheda ─────────────────────────────
#
# La meta' che conta: una funzione giusta che nessuno chiama e' una funzione che
# non c'e'. E la posizione e' parte della regola - quanto costa, cosa devo fare,
# chi chiamo.
print()
print("=" * 70)
print("  NELLA SCHEDA DEL CORSO")
print("=" * 70)

VUOTI = {k: "" for k in C.COLONNE}
corso = dict(VUOTI, codice="A006", nome="Coro Voci Bianche",
             org="Crome in Movimento APS", cat="Musica › Coro",
             citta="Vezza d'Alba", eta="6-10 anni", prezzo="90 euro",
             iscrizioni="Iscriversi tramite WhatsApp al 3398550332",
             contatto="0173 123456", stagione=f"{C.stagione_avvio()}/"
             f"{C.stagione_avvio() + 1}")
scheda = C.card(corso, 0)
print("   ", [r for r in scheda.splitlines() if "Iscrizioni" in r][:1])
verifica("la riga «Iscrizioni» c'e'", "<dt>Iscrizioni</dt>" in scheda)
verifica("...col numero cliccabile", 'href="tel:3398550332"' in scheda)
verifica("...dopo la Quota", scheda.index("<dt>Quota</dt>")
         < scheda.index("<dt>Iscrizioni</dt>"))
verifica("...e prima dei Contatti", scheda.index("<dt>Iscrizioni</dt>")
         < scheda.index("<dt>Contatti</dt>"))
# In RIGA non ci va: li' stanno disciplina, eta' e comune, ed e' la decisione
# del 21/08 su cosa si legge scorrendo.
riga = scheda.split('<div class="ev-det"')[0]
verifica("in riga NON compare (si legge aprendo)", "Iscriversi" not in riga)

senza = C.card(dict(corso, iscrizioni=""), 1)
verifica("un corso senza quella cella non stampa la riga vuota",
         "<dt>Iscrizioni</dt>" not in senza)

# ── PARTE 2b: lo STATO delle iscrizioni resta fuori ───────────────────────
#
# La meta' della decisione del 21/08/2026 che NON si tocca. Quel giorno e'
# uscito un cartellino "Iscrizioni aperte/chiuse" perche' e' un dato che scade
# in silenzio: "alla pallavolo si entra quasi sempre, a un corso di teatro quasi
# mai, e la risposta vera ce l'ha la societa'". Quello che dal 19/09 torna in
# pagina e' l'ISTRUZIONE, non lo stato - e quando la cella porta lo stato, vince
# la regola vecchia.
print()
print("=" * 70)
print("  APERTO/CHIUSO: la cella si toglie")
print("=" * 70)

FUORI = [
    ("iscrizioni aperte", "Iscrizioni aperte fino al 30 settembre"),
    ("iscrizioni chiuse", "Iscrizioni chiuse"),
    ("scritto al contrario", "Le iscrizioni non sono ancora aperte"),
    ("il numero chiuso e' uno stato", "Corso a numero chiuso"),
    ("i posti esauriti pure", "Posti esauriti"),
    ("e anche in inglese", "Sold out"),
]
for etichetta, cella in FUORI:
    verifica(f"SI TOGLIE - {etichetta}", C.stato_iscrizioni(cella))

DENTRO = [
    ("come si fa, non se si puo'", "Iscriversi tramite WhatsApp al 3398550332"),
    ("un termine non e' uno stato", "Iscrizioni entro il 30 settembre"),
    ("posti limitati e' una condizione, non un cartello",
     "Prenotazione obbligatoria, posti limitati"),
    ("il modulo", "https://teachernoemi.my.canva.site/corsi"),
    ("la segreteria", "Informazioni e prenotazione presso Roberta Ronco"),
]
for etichetta, cella in DENTRO:
    verifica(f"RESTA - {etichetta}", not C.stato_iscrizioni(cella))

# Il filtro sta in leggi_corsi, cioe' PRIMA della scheda: una cella cosi' non
# arriva mai a card(). Lo si prova dal foglio, nella parte 3 - qui ci sarebbe
# solo una verifica sempre verde.

# ── PARTE 3: la data passata, come per la Prova ───────────────────────────
print()
print("=" * 70)
print("  DAL FOGLIO: una cella che nomina un termine finito")
print("=" * 70)

OGGI = datetime.date.today()
IERI = OGGI - datetime.timedelta(days=1)
DOMANI = OGGI + datetime.timedelta(days=1)
STAGIONE = f"{C.stagione_avvio()}/{C.stagione_avvio() + 1}"


def a_parole(d):
    return f"{d.day} {C.G.MESI_LUNGHI[d.month - 1]}"


RIGHE = [
    ("A001", "Iscrizioni vuote", ""),
    ("A002", "Termine di ieri", f"Iscrizioni entro il {a_parole(IERI)}"),
    ("A003", "Termine di domani", f"Iscrizioni entro il {a_parole(DOMANI)}"),
    ("A004", "Senza termine", "Iscriversi tramite WhatsApp, posti limitati"),
    ("A005", "Dichiara lo stato", "Iscrizioni aperte, scrivere in segreteria"),
]


def foglio():
    righe = ["CODICE,Nome,Organizzatore,Annate,Stagione,Iscrizioni"]
    for cod, nome, iscr in RIGHE:
        # Fra virgolette: e' testo libero e la virgola dentro ci sta.
        righe.append(f'{cod},{nome},PGS Roccavione,2015-2020,{STAGIONE},"{iscr}"')
    return "\n".join(righe) + "\n"


vero = C._scarica
C._scarica = lambda tab: foglio()
try:
    corsi = C.leggi_corsi()
finally:
    C._scarica = vero

verifica("il foglio si legge", corsi is not None)
per_nome = {c["nome"]: c for c in (corsi or [])}
# LA COSA PIU' IMPORTANTE: nessun corso e' sparito. Quello che scade e' il
# termine, non il corso.
verifica("restano tutti e cinque i corsi (si toglie la cella, non la riga)",
         len(corsi or []) == 5)
verifica("il termine di IERI e' stato svuotato",
         per_nome.get("Termine di ieri", {}).get("iscrizioni") == "")
verifica("quello di DOMANI e' intatto",
         per_nome.get("Termine di domani", {}).get("iscrizioni", "").startswith(
             "Iscrizioni entro"))
verifica("la cella senza date non si tocca",
         per_nome.get("Senza termine", {}).get("iscrizioni") ==
         "Iscriversi tramite WhatsApp, posti limitati")
verifica("quella gia' vuota resta vuota",
         per_nome.get("Iscrizioni vuote", {}).get("iscrizioni") == "")
verifica("e la cella che dichiara APERTO non arriva in pagina",
         per_nome.get("Dichiara lo stato", {}).get("iscrizioni") == "")

print()
print("=" * 70)
print("  ESITO:", "TUTTO A POSTO" if esito else "QUALCOSA NON VA")
print("=" * 70)
print()
sys.exit(0 if esito else 1)
