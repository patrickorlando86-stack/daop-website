#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Controlla il CREDITO SOTTO LA FOTO dei luoghi: che ci sia quando l'autore si
sa, che non ci sia quando non si sa, e - la parte che conta - che l'HTML
scritto da terzi non finisca in pagina cosi' com'e'.

PERCHE' ESISTE (02/09/2026, PASSO 2 del TODO "Copyright foto"): le foto vengono
da DUE parti e tutt'e due vogliono il credito - Google Places chiede di citare
l'autore accanto alla foto, Wikimedia Commons vuole autore E licenza. Le due
attribuzioni ci arrivano come HTML di terzi dentro le colonne `FotoAutore` e
`FotoLicenza`. Quelle stringhe fanno un giro lungo prima della pagina - la
fonte, uno script, un foglio Google che scrivono in due persone, gviz - e
stamparle senza smontarle vorrebbe dire lasciare scrivere HTML nel sito a chi
sta in fondo a quel giro.

Il valore da difendere e' che da quelle colonne escano SOLO due cose: un nome
(testo) e, se l'host e' uno che ci aspettiamo, un link. Tutto il resto si butta.

Qui dentro:
  1. il caso normale: nome e link di Google diventano il paragrafo;
  2. autore mancante = nessun paragrafo (e' il caso delle righe non riempite);
  3. l'HTML di terzi non passa: ne' tag, ne' href verso altri host;
  4. il paragrafo sta ATTACCATO alla foto dentro la riga del luogo;
  5. le foto di Commons portano anche la LICENZA, e dicono di essere di
     Commons e non di Google Maps.

Uso:
    python scripts/prova_credito_foto.py

Esce 0 se tutto torna, 1 al primo controllo che salta. Non tocca niente.
"""
import datetime
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genera_luoghi as L

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

esito = True
OGGI = datetime.date.today()

# L'attribuzione vera come la manda Google (presa dalla sua documentazione).
VERA = '<a href="https://maps.google.com/maps/contrib/117453394308242254922">Mario Rossi</a>'


def ok(etichetta, condizione):
    global esito
    esito &= bool(condizione)
    print(f"  {'OK ' if condizione else 'NO '} {etichetta}")


def luogo(autore, con_foto=True, licenza=''):
    """Una riga di catalogo col minimo indispensabile per disegnarla."""
    return {
        'nome': 'Museo di Prova', 'comune': 'Alessandria', 'prov': 'AL',
        'cat': 'musei', 'cat_nome': 'Musei', 'cat_sotto': '', 'cat_filtro': 'Musei',
        'icona': '🏛', 'colore': '#888', 'servizi': [], 'pratici': [], 'riparo': 'aperto',
        'indirizzo': 'Via Prova 1', 'lat': '44.9', 'lon': '8.6',
        'descr': 'Un museo per la prova.', 'descr_premium': '',
        'orari': '', 'prezzo': '', 'gratuito': False,
        'sito': '', 'tel': '', 'email': '',
        'foto': ['https://esempio.invalid/foto.jpg'] if con_foto else [],
        'foto_autore': autore, 'foto_licenza': licenza,
        'eta_min': 0, 'eta_max': 99, 'premium': False, 'premium_dal': '',
        'consigliato': False, 'evidenza': False, 'codice': 'X1',
        'slug': 'lg-museo-di-prova-alessandria', 'comune_slug': 'alessandria',
        'n_eventi': 0, 'ultimo': '', 'prossimi': [], 'fonte': 'catalogo',
        '_grezzo': None,
    }


print("=== 1) il caso normale: il credito compare, col nome e col link ===")
p = L.html_credito_foto(VERA)
ok("il paragrafo c'e'", 'class="lg-credito"' in p)
ok("dice il nome dell'autore", 'Mario Rossi' in p)
ok("dice da dove viene la foto", 'Google Maps' in p)
ok("il link all'autore resta cliccabile",
   'href="https://maps.google.com/maps/contrib/117453394308242254922"' in p)
ok("il link non si porta dietro il nostro ranking (nofollow) ne' la finestra",
   'rel="noopener nofollow"' in p and 'target="_blank"' in p)

print()
print("=== 2) autore che non sappiamo = nessun paragrafo ===")
# E' il caso delle 712 righe vecchie: la foto c'e', l'autore l'avevamo
# scartato. Meglio niente che un "autore sconosciuto" sotto ogni foto.
for vuoto in ['', None, '   ', '<a href="https://maps.google.com/x"></a>', '<b></b>']:
    ok(f"{vuoto!r} -> niente", L.html_credito_foto(vuoto) == '')

print()
print("=== 3) l'HTML di terzi non entra in pagina ===")
casi = [
    ('uno script attaccato al nome',
     '<a href="https://maps.google.com/maps/contrib/1">Tizio<script>alert(1)</script></a>'),
    ('un onerror dentro il tag',
     '<a href="https://maps.google.com/maps/contrib/1" onerror="alert(1)">Tizio</a>'),
    ('un tag img in mezzo',
     '<a href="https://maps.google.com/maps/contrib/1">Ti<img src=x>zio</a>'),
]
for etichetta, grezzo in casi:
    p = L.html_credito_foto(grezzo)
    ok(f"{etichetta}: niente tag di loro",
       '<script' not in p and '<img' not in p and 'onerror' not in p)
    ok(f"{etichetta}: il nome si legge ancora", 'Tizio' in p or 'Ti zio' in p)

# L'href e' l'unico dato di quella stringa che finisce in un attributo, quindi
# e' l'unico posto in cui un valore inatteso conta davvero: fuori da Google si
# tiene il NOME e si butta il link. Citare l'autore senza link e' comunque
# meglio che non citarlo, ed e' l'esito peggiore ammesso.
print()
print("    ...e un href che non e' di Google si butta, tenendo il nome:")
for cattivo in ['https://cattivo.invalid/x', 'javascript:alert(1)',
                'https://google.com.cattivo.invalid/x', 'data:text/html,<b>x</b>',
                'https://notgoogle.com/x']:
    p = L.html_credito_foto(f'<a href="{cattivo}">Tizio</a>')
    ok(f"{cattivo[:44]}", 'Tizio' in p and '<a ' not in p)

print()
print("    ...mentre i domini Google veri passano:")
for buono in ['https://maps.google.com/maps/contrib/1',
              'https://www.google.com/maps/contrib/1',
              'http://google.com/maps/contrib/1']:
    p = L.html_credito_foto(f'<a href="{buono}">Tizio</a>')
    ok(f"{buono}", f'href="{buono}"' in p)

print()
print("=== 4) dentro la riga del luogo, il credito sta SOTTO la foto ===")
riga = L.riga(luogo(VERA), OGGI)
i_foto, i_cred = riga.find('class="lg-foto"'), riga.find('class="lg-credito"')
ok("la foto c'e'", i_foto > 0)
ok("il credito c'e'", i_cred > 0)
ok("e viene dopo la foto, non prima", 0 < i_foto < i_cred)
# Non "dopo" e basta: SUBITO dopo. Fra la foto e il suo credito non deve
# entrare la descrizione, altrimenti il nome dell'autore si legge come una
# didascalia di quel testo - e i termini chiedono l'attribuzione ACCANTO
# all'immagine, non piu' in giu' nella scheda.
ok("attaccato: fra il tag della foto e quello del credito non c'e' nient'altro",
   riga[riga.index('>', i_foto) + 1:i_cred].strip('< ') == 'p')
ok("senza foto non c'e' nemmeno il credito",
   'lg-credito' not in L.riga(luogo(VERA, con_foto=False), OGGI))
ok("con la foto ma senza autore la riga resta come prima",
   'lg-credito' not in L.riga(luogo(''), OGGI))
ok("il CSS del credito viene pubblicato", '.lg-credito{' in L.LUOGHI_CSS)

print()
print("=== 5) le foto di Wikimedia Commons: autore + LICENZA + fonte giusta ===")
# Le `comune-<paese>.jpg` sono 203 righe su 941 e vengono da Commons, non da
# Places. Passano per le stesse due colonne e si distinguono da sole: la
# licenza ce l'ha solo Commons, e l'host del link dice da dove viene la foto.
# Senza la licenza il credito sarebbe incompleto - li' "pulita" non vuol dire
# "libera", e Creative Commons vuole autore, licenza e link al materiale.
COMMONS = ('<a href="https://commons.wikimedia.org/wiki/File:Canelli-panorama.jpg">'
           'Davide Papalini</a>')
CC = '<a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>'
p = L.html_credito_foto(COMMONS, CC)
ok("dice il nome dell'autore", 'Davide Papalini' in p)
ok("dice la licenza", 'CC BY-SA 3.0' in p)
ok("dice Wikimedia Commons e NON Google Maps",
   'Wikimedia Commons' in p and 'Google Maps' not in p)
ok("il link porta alla pagina del file su Commons",
   'href="https://commons.wikimedia.org/wiki/File:Canelli-panorama.jpg"' in p)
ok("il link della licenza porta al testo della licenza",
   'href="https://creativecommons.org/licenses/by-sa/3.0"' in p)

# Public domain e CC0 su Commons non hanno un `LicenseUrl`: non c'e' un testo
# da linkare, e il nome da solo e' esatto.
p = L.html_credito_foto(COMMONS, 'Public domain')
ok("una licenza senza link resta scritta lo stesso", 'Public domain' in p)
ok("...e senza inventarsi un link", p.count('<a ') == 1)

# La licenza e' un dato in piu', non una scusa per allentare la guardia: e'
# l'altra stringa di terzi che finisce in un attributo.
for cattivo in ['https://cattivo.invalid/x', 'javascript:alert(1)',
                'https://creativecommons.org.cattivo.invalid/x']:
    p = L.html_credito_foto(COMMONS, f'<a href="{cattivo}">CC BY-SA 3.0</a>')
    ok(f"licenza con href {cattivo[:34]}: si tiene il nome, si butta il link",
       'CC BY-SA 3.0' in p and p.count('<a ') == 1)

# Le due fonti non si contaminano: una foto di Places non deve mai uscire con
# una licenza addosso, e senza licenza una foto di Commons resta di Commons.
p = L.html_credito_foto(VERA, '')
ok("Places senza licenza: resta 'Google Maps' e basta",
   'Google Maps' in p and 'CC ' not in p)
p = L.html_credito_foto(COMMONS, '')
ok("Commons senza licenza: la fonte e' comunque Commons",
   'Wikimedia Commons' in p)

print()
print("    ...e nella riga del luogo il credito completo esce attaccato alla foto:")
riga = L.riga(luogo(COMMONS, licenza=CC), OGGI)
i_foto, i_cred = riga.find('class="lg-foto"'), riga.find('class="lg-credito"')
ok("il credito c'e' e sta dopo la foto", 0 < i_foto < i_cred)
ok("la licenza e' arrivata fino in pagina", 'CC BY-SA 3.0' in riga)

print()
print("=== 6) le colonne del foglio si leggono ===")
ok("'fotoautore' e' fra le grafie ammesse",
   'fotoautore' in L.COLONNE['foto_autore'])
ok("'fotolicenza' e' fra le grafie ammesse",
   'fotolicenza' in L.COLONNE['foto_licenza'])

print()
print("ESITO:", "tutto come previsto" if esito else "*** QUALCOSA NON TORNA ***")
sys.exit(0 if esito else 1)
