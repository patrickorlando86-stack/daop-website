"""prova_doppioni_registro.py - due pagine per un evento solo, dopo la data.

Quello che si difende NON e' "il registro e' pulito": quello e' un dato, e una
prova che lo pretende diventa rossa il giorno che entra una coppia nuova, cioe'
quando l'avviso sta facendo il suo mestiere. E' l'inciampo gia' pagato sette
volte in questo repo. Qui si prova il COMPORTAMENTO, su un registro finto.

Il caso vero da cui nasce (12/09/2026): quattro coppie nate in agosto e rimaste
invisibili per settimane, perche' `_doppioni_riscritti()` guarda le righe lette
oggi e quelle erano gia' state tolte dal foglio dalla pulizia degli scaduti.

Gira offline, due secondi, e non tocca niente.
"""
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_eventi as G


def _cattura(reg, events):
    """Fa girare il controllo e torna quello che ha stampato."""
    vecchio, buf = sys.stdout, io.StringIO()
    sys.stdout = buf
    try:
        G.segnala_doppioni_registro(reg, events)
    finally:
        sys.stdout = vecchio
    return buf.getvalue()


def _pag(nome, citta='Rocchetta Tanaro', giorno='2026-08-14', **extra):
    d = {'nome': nome, 'citta': citta, 'd_start': giorno, 'd_end': giorno,
         'last_seen': '2026-08-07', 'riga': None}
    d.update(extra)
    return d


def _riga(nome, citta='Rocchetta Tanaro', giorno='2026-08-14'):
    g = datetime.date.fromisoformat(giorno)
    return {'nome': nome, 'citta': citta, 'd_start': g, 'd_end': g}


CASI = []


def caso(titolo, reg, events, atteso):
    CASI.append((titolo, reg, events, atteso))


# 1. il caso vero: stessa serata, stesse parole, una congiunzione di differenza,
#    e nessuna delle due e' piu' sul foglio.
caso('la coppia riscritta si segnala',
     {'a': _pag('Apertura Stand Gastronomico con Shary Band - Pro Loco Rocchetta Tanaro'),
      'b': _pag('Apertura Stand Gastronomico e Shary Band - Pro Loco Rocchetta Tanaro')},
     [], True)

# 2. due eventi VERI e distinti nello stesso paese lo stesso giorno: e' il caso
#    che la soglia esiste per non prendere (a Ferragosto un paese ne ha cinque).
caso('due eventi diversi nello stesso giorno non si segnalano',
     {'a': _pag('Gara di Bocce Notturna'),
      'b': _pag('Concerto della Banda Musicale')},
     [], False)

# 3. una delle due e' gia' stata unita: il cartello non e' una pagina da unire
#    di nuovo, se no l'avviso non si spegne mai e si impara a saltarlo.
caso("una coppia gia' risolta non si ripropone",
     {'a': _pag('Apertura Stand Gastronomico con Shary Band'),
      'b': dict(_pag('Apertura Stand Gastronomico e Shary Band'), spostata='a')},
     [], False)

# 4. una ritirata dichiara di non essere attendibile: non e' una URL da salvare.
caso('una ritirata non fa coppia',
     {'a': _pag('Apertura Stand Gastronomico con Shary Band'),
      'b': dict(_pag('Apertura Stand Gastronomico e Shary Band'), ritirata='2026-08-20')},
     [], False)

# 5. se sono ancora TUTTE E DUE sul foglio la coppia la grida gia'
#    _doppioni_riscritti(): due avvisi per la stessa cosa sono un avviso che
#    si impara a saltare.
_a = 'Apertura Stand Gastronomico con Shary Band - Pro Loco Rocchetta Tanaro'
_b = 'Apertura Stand Gastronomico e Shary Band - Pro Loco Rocchetta Tanaro'
caso("se sono entrambe ancora sul foglio tace (lo dice l'altro controllo)",
     {G.slug_evento(_riga(_a)): _pag(_a), G.slug_evento(_riga(_b)): _pag(_b)},
     [_riga(_a), _riga(_b)], False)

# 6. ma se ne resta UNA sul foglio, la coppia e' ancora un danno vivo: la pagina
#    vecchia si prende le impressioni di quella che verra' aggiornata.
caso('se ne resta una sola sul foglio si segnala lo stesso',
     {G.slug_evento(_riga(_a)): _pag(_a), 'vecchia': _pag(_b)},
     [_riga(_a)], True)

# 7. la stessa manifestazione in due giorni diversi NON e' un doppione: e' una
#    sagra di tre sere, ed e' il caso piu' facile da prendere per sbaglio.
caso('due serate della stessa sagra non sono un doppione',
     {'a': _pag('Apertura Stand Gastronomico con Shary Band', giorno='2026-08-14'),
      'b': _pag('Apertura Stand Gastronomico con Shary Band', giorno='2026-08-15')},
     [], False)

# 8. comuni diversi: "Festa di Paese" ce n'e' una per campanile.
caso("lo stesso nome in due comuni non e' un doppione",
     {'a': _pag('Festa Patronale', citta='Rocchetta Tanaro'),
      'b': _pag('Festa Patronale', citta='Entracque')},
     [], False)


# 9. IL CONFINE, ed e' una prova che difende un NO. La coppia di Entracque sta
#    sotto la soglia (0,40 contro 0,80: condividono "aspettando" e "fiera", non
#    "patata"/"patate"/"entracque") e questo controllo NON la prende. E' voluto:
#    abbassare la soglia farebbe gridare l'avviso sulle serate diverse della
#    stessa sagra, e un avviso che grida sempre non si legge piu'. Quella coppia
#    l'aveva gia' presa filtra_doppioni nel downloader, con ~81 punti, mentre la
#    riga nasceva. Se un domani qualcuno abbassa la soglia, questa diventa rossa
#    e gli ricorda il patto.
caso("la coppia di Entracque resta sotto soglia, ed e' deliberato",
     {'a': _pag('Aspettando la 28° Fiera della Patata', citta='Entracque',
                giorno='2026-08-29'),
      'b': _pag('Aspettando la 28ª Fiera Patate di Entracque', citta='Entracque',
                giorno='2026-08-29')},
     [], False)


def main():
    falliti = []
    for titolo, reg, events, atteso in CASI:
        uscita = _cattura(reg, events)
        visto = 'ATTENZIONE' in uscita
        if visto == atteso:
            print(f"  OK  {titolo}")
        else:
            falliti.append(titolo)
            print(f"  FALLITO  {titolo}: atteso "
                  f"{'un avviso' if atteso else 'silenzio'}, ottenuto "
                  f"{'un avviso' if visto else 'silenzio'}")

    # E il messaggio deve portare i due dati con cui si decide: senza last_seen
    # e la riga, chi legge l'avviso non sa quale delle due tenere e apre Search
    # Console per una cosa che il registro gli direbbe da solo.
    uscita = _cattura(CASI[0][1], CASI[0][2])
    for pezzo in ('vista fino al', 'riga ', 'spostata'):
        if pezzo in uscita:
            print(f"  OK  l'avviso dice «{pezzo.strip()}»")
        else:
            falliti.append(f"l'avviso non dice «{pezzo.strip()}»")
            print(f"  FALLITO  l'avviso non dice «{pezzo.strip()}»")

    if falliti:
        print(f"\nROSSO: {len(falliti)} controlli falliti")
        return 1
    print(f"\nOK: {len(CASI)} casi piu' il contenuto dell'avviso")
    return 0


if __name__ == '__main__':
    sys.exit(main())
