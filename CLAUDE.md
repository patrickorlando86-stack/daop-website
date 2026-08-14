# DAOP — daop.it

Sito statico su GitHub Pages (`main` → daop.it). Niente build, niente framework:
HTML in chiaro nel repo, CSS inline nelle pagine, JS inline o in `assets/js/`.

## La regola che viene prima delle altre

**Le pagine con eventi non si modificano a mano: si modifica il generatore.**

`scripts/genera_eventi.py` riscrive ogni notte `eventi.html`, le ~240 schede in
`eventi/`, le 12 pagine comune, le 5 pagine di intenzione, `zone.html`,
`metodo.html`, `index.html` e la sitemap. Una modifica scritta a mano nei file
generati sparisce alla run successiva, senza avvisare.

Cosa si tocca a mano e cosa no, dentro `eventi.html`:

| zona | chi la scrive |
|---|---|
| fra i marker `<!-- EVENTI-*:START/END -->` | il generatore |
| il `<style>` inline, il JS in fondo, nav e footer | a mano |

I marker sono `EVENTI-TIPO`, `EVENTI-PROV`, `EVENTI-LISTA`, `EVENTI-COMUNI`,
`EVENTI-HERO` in `eventi.html` e `HOME-EVENTI` in `index.html`.

### Il CSS di eventi.html è il CSS di mezzo sito

`_guscio()` rilegge a ogni run il `<style>`, la nav e il footer **da
`eventi.html`** e li incolla in tutte le pagine generate. Quindi una regola
aggiunta lì compare in ~260 file al primo `python3 scripts/genera_eventi.py`:
è voluto, ma spiega perché un diff di due righe di CSS tocca l'intero repo.
Non duplicare quelle regole altrove.

`genera_centri.py` e `genera_luoghi.py` importano `genera_eventi` e usano lo
stesso guscio: se cambi il CSS, `centri-estivi.html` e `luoghi.html` si allineano
solo quando girano **anche** quegli script.

`luoghi.html` non ha marker: è generato **per intero**, come le pagine comune e
le pagine di intenzione. Non c'è nessuna zona scritta a mano da salvare, quindi
non se ne cerca una: si tocca `scripts/genera_luoghi.py`.

### GA4 si inizializza in un posto solo

`assets/js/cookie-consent.js` è **l'unico** punto in cui si scrive
`gtag('config', ...)`. Chi include quel file è tracciato; non c'è una seconda
lista da aggiornare quando nasce una pagina.

Fino al 12/08/2026 non era così, ed era un buco silenzioso: il `config` stava
copiato a mano in dodici pagine e `cookie-consent.js` caricava `gtag.js` senza
dirgli mai quale proprietà misurare. Le ~280 pagine generate — tutte le schede
`/eventi/`, le pagine comune, `oggi`, `weekend`, le provinciali, `zone`,
`metodo`, i centri estivi — scaricavano la libreria e non mandavano **nessun**
`page_view`. In GA4 si vedeva `/eventi.html` (scritta a mano, quindi col blocco
inline) e non si vedeva nessuna scheda: 1.932 clic da Search Console contro 215
utenti. Il sintomo sembrava "manca il tag nel template", ma il tag c'era: gli
mancava l'inizializzazione.

Da qui due regole:

- **Non riaggiungere un blocco `gtag` inline in una pagina.** Sarebbe una
  seconda inizializzazione, cioè due `page_view` per visita.
- **Una pagina nuova si tracciava già da sola**, purché includa
  `cookie-consent.js`: i sei template in `genera_eventi.py` e quelli di
  `genera_centri.py` / `genera_rubriche.py` lo fanno.

Restano fuori apposta: i due stub di redirect (`cookypolicy.html`,
`ilpiattosano.html`), il file di verifica di Search Console, lo sprite
`assets/icons.svg.html` e i tre `eventi/box-*.html`, che sono `noindex` e
vivono dentro l'iframe di siti altrui — lì il consenso non è nostro da chiedere.

I clic stanno in `assets/js/daop-track.js`, anche quello uno solo, e leggono
`daop:evento` / `daop:citta` / `daop:provincia` dai meta che stampano i
generatori. Nessuno dei due script manda niente prima del consenso:
`window.daopConsensoAnalytics` è la condizione, e `typeof gtag === 'function'`
non basta — lo stub che accoda in `dataLayer` esiste da sempre.

#### Il buco è chiuso, e si misura con Search Console non con GA4

Il fix è andato in produzione il 12/08/2026 alle 14:53. GA4 ha reagito subito, e
in due modi che vanno letti bene, perché **entrambi sembrano quello che non
sono**.

Il primo è un avviso "anomalia nel conteggio eventi" il 12 agosto: 904 eventi
contro un massimo previsto di 821. Non è traffico, è misurazione — e la prova sta
fuori da GA4, nell'export di Search Console. Il giorno di traffico più grosso del
mese è l'**8 agosto**, con 603 clic da Google: GA4 quel giorno ha visto ~30
utenti. Se il salto del 12-13 fosse crescita reale, il massimo sarebbe stato
l'8.

| giorno | clic da Google | utenti GA4 |
|---|---|---|
| 8 ago | 603 (il picco vero) | ~30 |
| 11 ago | 270 | ~30 |
| 12 ago (fix alle 14:53) | 311 | ~120 |
| 13 ago | — | ~220 |

Prima del fix GA4 misurava circa il **5%** della realtà, dopo circa il **70%**.
Il resto è il banner di consenso, ed è fisiologico: **non si arriverà mai in pari
con Search Console**, e il criterio di successo è che il divario si stringa, non
che si chiuda. Il `+608%` settimanale (62 → 439 utenti attivi) è quindi quasi
tutto recupero di misurazione: non usarlo come numero di crescita con nessuno.

Il secondo è la durata media, scesa del 53% (2:12 → 1:02). **Non è un
peggioramento, è composizione.** Prima l'unica popolazione misurata erano le
pagine scritte a mano — `eventi.html`, la home — cioè gente che naviga; ora
dentro c'è la massa che atterra da Google su una singola scheda, legge l'orario
della sagra ed esce. È una visita a pagina singola, che GA4 sottostima per
costruzione. Non inseguirla.

Ne segue la regola di lettura: **nessun confronto che attraversi il 12/08/2026 ha
senso** — non mese-su-mese, non anno-su-anno. Se GA4 permette un'annotazione su
quella data, mettila. E aspettati altri avvisi "anomalia" per qualche giorno,
mentre il modello previsionale reimpara: sono rumore.

Cosa manca ancora, ed è il pezzo che trasforma il tracciamento in argomento di
vendita: **il conteggio delle aperture di scheda su `luoghi.html`** (vedi
"Vendere uno spazio"). GA4 registra i clic *dalla* scheda, non le aperture.

## Far girare i generatori

```bash
python3 scripts/genera_eventi.py      # funziona offline
python3 scripts/genera_luoghi.py      # funziona offline, DOPO genera_eventi.py
python3 scripts/genera_centri.py      # richiede rete
python3 scripts/genera_rubriche.py    # legge contenuti/rubriche/
```

`genera_luoghi.py` va **dopo** `genera_eventi.py`, non prima: legge
`data/eventi.json` e `data/storico-comuni.json` appena riscritti per sapere cosa
c'è in programma in ogni posto. Girando prima scriverebbe "in programma" su
eventi già passati.

`genera_eventi.py` legge il foglio Google e, se non lo raggiunge, ripiega da
solo su `data/eventi.json` (l'istantanea committata) e va avanti. Gli altri no:
senza rete `genera_centri.py` stampa "lascio la pagina com'è" e non riscrive
niente — non è un errore, ma vuol dire che le tue modifiche al CSS lì non si
vedono finché non gira in CI.

Il workflow `.github/workflows/aggiorna-eventi.yml` gira tutti e tre alle 02:00
UTC, committa da solo su `main`, poi passa i controlli (vedi in fondo).

## Decisioni editoriali da non rifare al contrario

### "Adatto Famiglie" non è una discriminante pubblica

In agenda entra **solo** quello che DAOP ha già scelto per le famiglie. Il
criterio sta a monte: la colonna `Adatto Famiglie` del foglio non aggiunge quel
giudizio, lo ripete (11/08/2026: `Si` su 281 righe di 294, `Da verificare` su
10, vuota su 3).

Non usarla per separare, filtrare o intitolare. Un elenco "adatti alle
famiglie" dice implicitamente che gli altri non lo sono, cioè smentisce il
criterio con cui la pagina è fatta — e separa il 95% dal 5%.

C'è una seconda ragione, indipendente: **quel flag non descrive la riga a cui è
attaccato.** Il giudizio si dà sulla *locandina*, cioè sulla manifestazione
intera; i sotto-eventi si pubblicano tutti, uno per riga, e si raggruppano dopo
per `Manifestazione`. Il verdetto della locandina finisce timbrato identico su
ogni riga (26 manifestazioni su 30 hanno il flag uguale su tutte le righe).
"San Liberato 2026" sono 19 righe tutte `Si`, e dentro ci sono la sagra delle
22:30 e lo spettacolo comico delle 20:45. Un giudizio per sotto-evento nel
foglio non c'è, e non vale la pena inventarlo.

Dove serve rispondere "ci vado con i bambini?", si risponde con la regola
d'ingresso e si manda a leggere il programma — non si promette una cernita che
non esiste.

**Diverso è `e_per_bambini()`**: fascia d'età dichiarata *oppure*
laboratori/burattini/giochi scritti nel programma. Quello è un dato per riga e
dice "pensati **per** i bambini", non "adatti". Si può usare, e infatti regge la
sezione "Cosa c'è per i bambini" delle pagine comune.

### Una pagina stagionale non porta l'anno nell'indirizzo

`/ferragosto.html`, non `/ferragosto-2026.html`. L'anno sta nel `<title>` e
nell'H1 e lì lo riscrive `spec_ferragosto()` a ogni run.

È la decisione che regge tutta la pagina: una query stagionale si vince con
l'anzianità dell'URL, e un indirizzo nuovo ogni agosto riparte da zero ogni
agosto. `tests/landing.js` controlla che il canonical non contenga cifre e che
il title invece l'anno ce l'abbia.

Da qui il resto:

- **La finestra è il 14-16 agosto fisso**, non "il weekend più vicino al 15".
  Nel 2026 il 15 cade di sabato: un weekend coinciderebbe con
  `/eventi/weekend.html`, cioè due nostre pagine sulla stessa lista, e a perdere
  sarebbe la nuova. Nel 2027 cade di domenica e il 14 resterebbe fuori.
- **Non è un filtro di date.** Se fosse solo l'elenco del 14-16 sarebbe un
  doppione di `weekend.html` ogni volta che il 15 cade nel fine settimana. Quello
  che ha di suo è il blocco sulle due domande di Ferragosto a cui un elenco non
  risponde — come ci si regola quel giorno, dove si mangia — e da lì manda a
  `luoghi.html`. È anche **il primo link a quella pagina che parte dal corpo di
  un'altra** e non dalla nav: finora ne riceveva zero, ed è il motivo per cui non
  prendeva traffico. Togliere quel blocco non alleggerisce la pagina, la
  trasforma in un doppione.
- **Fuori stagione resta online ma esce dall'indice**: `noindex, follow` sotto
  `MIN_LANDING`, come le `sagre-provincia-*`. I link girati su WhatsApp devono
  continuare a funzionare, ma una pagina vuota indicizzata per cinquanta
  settimane è contenuto sottile sull'URL che stiamo facendo invecchiare.
- **Si gira da sola all'anno dopo**: dal 17 agosto `ferragosto_range()` punta al
  Ferragosto successivo, e `link_landing(oggi)` la linka dalle altre pagine solo
  dal 10 luglio al 16 agosto. Nessuna data da ricordare a mano.

Come ci si arriva, e la cosa da non fare per dargli più risalto: `blocco_stagione()`
scrive **una riga sola**, in home (marker `HOME-STAGIONE`) e in coda all'hero
dell'agenda, dal **5 agosto** — più tardi del link nelle scorciatoie, perché una
riga in evidenza per cinque settimane è un banner che si impara a non vedere.

**L'H1 di `eventi.html` non si tocca per la stagione.** È la scorciatoia che
viene in mente per prima ed è un pessimo affare: quell'H1 è l'asset più forte del
sito e riscriverlo per dieci giorni lo toglie per dieci giorni dalle query su cui
ranka tutto l'anno. L'avviso è un `<p>` in più, e la sua CSS sta nel `<style>` di
`index.html` — che è suo e non passa da `_guscio()`, quindi non fa un diff su 260
file per una riga stagionale.

Nata il 13/08/2026, cioè **due giorni prima**: quest'anno non si posiziona e non
è per quello che esiste: la resa 2026 arriva da push, WhatsApp e social, quella
da Google arriva nel 2027. Non giudicarla dai numeri di agosto 2026.

### Il traffico sono le schede, e i loro URL non scadono

Misurato sull'export di Search Console del 14/08/2026 (28 giorni, 16/07–12/08):
**2.777 clic, 35.122 impressioni, CTR 7,91%, 90% da telefono.** Dove vanno:

| | clic | quota |
|---|---|---|
| le ~200 **schede** `/eventi/*.html` | 2.303 | **82%** |
| `eventi.html` | 331 | 12% |
| `sagre-provincia-*` | 127 | 5% |
| tutto il resto (home, rubriche, centri estivi, `piattosano`) | ~40 | 1% |

Da qui la prima cosa da non fraintendere: **come pagina singola `eventi.html`
resta la più forte del sito, ma come sistema il sito sono le schede.** Ed erano
esattamente loro a non mandare `page_view` fino al 12/08 — il divario 1.932 clic
contro 215 utenti non era un mistero, era l'82% del traffico.

**L'onda di agosto non è la stagione delle sagre: sono le schede.** Il `first_seen`
in `data/pagine-evento.json` dice che il sistema è nato il **02/08/2026**, e i
clic partono il 3: `5-15 al giorno in luglio → 69 → 118 → 140 → 170 → 269 → 603
→ 427 → 273 → 270 → 311`. Le stesse sagre erano già in agenda a luglio, quando il
sito faceva undici clic al giorno. Il picco di Ferragosto ha amplificato, non
causato.

Dove sono imbattibili: **nomi propri di feste di paese.** `festa cassinasco 2026`
in posizione 1,13 con CTR 31%, `cassinasco festa 2026` con CTR **72%**. Nessun
altro pubblica i sotto-eventi di una patronale di 800 abitanti. Le query che
contengono `2026` fanno il 60% dei clic misurati con CTR 11,1% contro 4,4% delle
altre: **la gente scrive l'anno**, e i title ce l'hanno — è la ragione per cui
`_titolo_evento()` lo stampa.

Due numeri per tenere la testa a posto: le prime 10 schede fanno il 53% dei clic
delle schede e `festa-d-estate-cassinasco.html` da sola l'11% del sito; e il
foglio `Query` copre solo 610 dei 2.777 clic, perché Google anonimizza le query
troppo rare. **Il 78% del traffico arriva da ricerche che non possiamo vedere.**
È il fossato (nessuno ci compete) e la fragilità (non c'è una query da difendere)
nello stesso dato.

#### Perché "poi arriva Halloween" non è un problema

Perché lo slug non porta l'anno né il numero di edizione — è la stessa decisione
di `/ferragosto.html`, applicata ~200 volte invece di una. `slug_evento()` toglie
`2026` e `40ª` dal nome, quindi l'edizione 2027 **aggiorna la stessa URL** invece
di crearne una che riparte da zero. E le pagine **non si cancellano mai**: quando
l'evento passa, `normalize()` lo scarta dal feed ma il registro
`data/pagine-evento.json` conserva i dati e la pagina resta online marcata
"edizione conclusa" (al 14/08/2026: 70 edizioni concluse su 259 conservate).

Quindi quello che scade sono **le query di questo agosto**, non gli URL. Nel 2027
`festa cassinasco 2027` si posiziona su un indirizzo che ha un anno di vita e sta
già in prima posizione. Il 2026 è l'anno zero di ogni stagione; dal 2027 ogni
stagione erediterà i propri URL invecchiati.

E prendere una stagione nuova è **veloce**: la scheda di Cassinasco è nata il 2-3
agosto ed era in posizione 1,13 entro l'8. Cinque giorni, perché su quelle query
non c'è concorrenza.

#### Il calendario vuoto di novembre non è un allarme: la fonte ha 10 giorni di preavviso

Al 14/08/2026 l'agenda ha 220 eventi in agosto, 59 a settembre, **4** a ottobre,
**1** a novembre, **1** a dicembre, e lo storico dice lo stesso (421 archiviati:
340 in agosto, 74 a settembre, 3 in ottobre, 1 a dicembre, **0** a novembre).

**Quei numeri non prevedono niente.** Misurato su `data/pagine-evento.json`, 224
schede nate dopo il backfill del 02/08: fra la comparsa della riga e la data
dell'evento passano **10,5 giorni di mediana**, p90 28 giorni, e 21 righe su 224
sono arrivate a evento già iniziato. Un imbuto da dieci giorni **deve** avere
quasi zero a tre mesi di distanza: guardare a metà agosto quanti eventi ci sono
per novembre è come pesare la spesa di dicembre guardando il frigo di agosto. Il
numero da guardare è quanti ce ne sono per novembre **a fine ottobre**.

E la domanda d'autunno non è un'ipotesi, è già nell'export del 14/08 — query
stagionali con impressioni mesi prima dell'evento: `sagra della zucca castelletto
monferrato` in posizione 3,67, il grappolo `sagra zucchino rivalta bormida` fra
4,0 e 8,3, `fiere e mercatini in provincia di cuneo domani` in posizione 1. Zero
clic perché l'evento è lontano, ma Google ci ha già messi lì. Ottobre e novembre
in Piemonte sono castagne, funghi, tartufo, vendemmia, Halloween nei castelli,
mercatini, presepi viventi: **il sito non va in letargo, e non è la stagione la
cosa da temere.**

#### Quello che cambia in autunno è il tipo di query, non il calendario

Sulle 873 query visibili dell'export (che sono il 22% dei clic, il resto Google
lo anonimizza):

| | query | clic | CTR | posizione |
|---|---|---|---|---|
| **nome proprio** (`festa cassinasco 2026`) | 539 | 515 | **9,47%** | 6,21 |
| **generiche** (`sagre provincia alessandria oggi`) | 334 | 95 | 2,77% | 8,42 |

L'84% dei clic visibili viene dai nomi propri, a tre volte e mezzo il CTR. È lì
che non abbiamo concorrenza, e **il fossato si porta dietro quasi tutto
l'autunno**: carnevali, presepi viventi, sagre della castagna e del tartufo hanno
tutti il nome del paese attaccato, cioè sono la stessa partita di agosto.

Si porta dietro molto meno **Halloween** e **"mercatini di Natale in Piemonte"**:
lì la query è nazionale e generica, cioè la colonna in cui stiamo in posizione
8-10 al 2,77%. Il rischio d'autunno non è che manchino gli eventi, è che una
fetta più grossa della domanda cada dove siamo deboli — ed è l'argomento più
forte per le sei pagine d'incrocio: in agosto sarebbero un miglioramento, a Natale
sono la differenza fra prendere quella domanda e guardarla passare.

Resta una cosa che il ritmo naturale della fonte **non** copre da solo. Le query
di stagione si cercano prima dell'evento, e con cinque giorni di rampa servono
schede molto più in anticipo dei 10 giorni di mediana: per Halloween del 31
ottobre il ritmo normale porterebbe la riga verso il 21, cioè tardi. Le stagionali
vanno raccolte **apposta**, prima delle altre:

| stagione | le schede devono esistere entro |
|---|---|
| Halloween | **~10 ottobre** |
| mercatini, presepi viventi, Natale | **~1 novembre** |
| Carnevale | **~10 gennaio** |
| Pasqua | ~1 marzo |

### `eventi.html` cannibalizza `oggi` e `weekend`, e non si risolve indebolendola

Il sintomo sembra un guasto: in 28 giorni `/eventi/oggi.html` ha preso **10
impressioni** e `/eventi/weekend.html` **13**, mentre le query di quell'intenzione
esistono e sono grosse (`sagre provincia di alessandria oggi`, 372 impressioni;
`eventi asti e provincia oggi`, 251). Non è un guasto: sono `index, follow`, con
canonical proprio, in sitemap, linkate dalla nav di 266 pagine.

La causa è che **`eventi.html` rivendica già quell'intenzione, e la rivendica
meglio**: title `Eventi e Sagre Oggi in Provincia di Alessandria, Asti, Cuneo`,
H1 `Sagre ed eventi oggi e questo weekend`, 286 `Event` in JSON-LD, 1,4 MB di
contenuto, tutta l'autorità del sito. Google consolida su di lei, e fa la cosa
giusta.

**La scorciatoia da non prendere è togliere "oggi" e "weekend" dall'H1 o dal
title di `eventi.html` per de-cannibalizzare.** È la stessa regola già scritta per
la riga stagionale, con la stessa aritmetica: quell'H1 vale 13.553 impressioni,
cioè il 36% delle impressioni del sito, e si rinuncerebbe a un asset provato per
sbloccare due pagine che oggi ne fanno 23 in un mese. Nemmeno una prova A/B lo
giustifica: il rischio è asimmetrico.

Il problema che resta non è *quale* pagina ranka, è che **qualunque pagina ranki,
ranka in posizione 8-10**. Le query generiche sono il 39% delle impressioni e solo
il 16% dei clic, con CTR 2,78% e posizione media 9,4. Ed è la domanda che **non
scade mai**: torna ogni weekend, tutto l'anno, Halloween e Natale compresi.

Guardando le query per quello che chiedono, il buco si vede: **chiedono tutte
provincia _e_ finestra temporale insieme** — "sagre provincia di alessandria
oggi", "eventi provincia di asti questo weekend". Quello che esiste è o l'una o
l'altra:

| pagina | provincia | quando | CTR |
|---|---|---|---|
| `sagre-provincia-*` | sì (H1) | **no** | 5,7-13,3% |
| `oggi.html` / `weekend.html` | **no** (solo nel title) | sì (H1) | invisibili |
| `eventi.html` | solo nel title | sì (H1) | 2,4% a pos. 8,08 |

Le provinciali convertono 2-5 volte meglio di `eventi.html` per impressione e
prendono 25 volte meno impressioni. **Nessuna pagina copre l'incrocio**, che è
esattamente quello che si digita. Sono le stesse "pagine di incrocio" già
elencate come lavoro mancante per `luoghi.html`, e qui la domanda è già misurata
invece che supposta.

Cosa manca, in ordine di resa — **nessuna di queste è ancora decisa**:

1. **Le 6 pagine d'incrocio** (3 province × oggi/weekend). Insieme di dimensione
   chiusa, quindi non è *scaled content*: la domanda esiste, la risposta no. Da
   decidere se nascono così o se assorbono `oggi.html`/`weekend.html`, che a quel
   punto non avrebbero più un mestiere.
2. **`Event` in JSON-LD sulle pagine aggregate.** `oggi.html` elenca 28 eventi,
   `weekend.html` 73, le tre provinciali il loro, e **tutte e cinque hanno zero
   `Event`**: i rich result eventi li prende solo `eventi.html`, che ne ha 286.
   Da verificare prima di farlo, però, che moltiplicare la stessa entità su più
   pagine non diluisca invece di aggiungere.
3. **L'H1 di `oggi.html` e `weekend.html` non nomina le province**, mentre il
   title sì (`Cosa fare oggi` contro *"Cosa fare oggi in provincia di
   Alessandria, Asti e Cuneo"*). È la più economica delle tre — metà della query
   è il posto — ma ha senso solo se quelle due pagine restano, cioè va decisa
   dopo il punto 1, non prima.

### L'età non si ripete nelle descrizioni

La fascia d'età è già nella riga `Età:` dei dati della scheda e in ogni riga
degli elenchi. Riscriverla dentro un testo la fa sembrare un requisito
d'ingresso ("da 3 a 10 anni") invece dell'indicazione di massima che è. Può
restare come *condizione* per mostrare o no un blocco; non come cifra stampata
una seconda volta.

### I filtri solo dove si guadagnano il posto

`MIN_FILTRI = 12`: sotto quel numero di eventi si scorre prima la lista che a
decidere in una tendina. E una tendina con una voce sola non si stampa — è un
comando che non fa niente.

Per questo le pagine comune (0-20 eventi, provincia fissa) non hanno filtri, e
le pagine `sagre-provincia-*` hanno solo la ricerca: lì gli eventi sono tutti
"Sagre & Feste". Sulle pagine di intenzione non c'è mai il filtro "quando":
quelle pagine *sono* già una risposta a quando.

Su `luoghi.html` i filtri sono quattro — provincia, comune, tipo, età — e sul
telefono vanno a capo su due righe (156px). Le etichette restano corte perché
**Chrome dimensiona una `<select>` sull'opzione più lunga**, non su quella
scelta: è per questo che l'etichetta del filtro ("Servizi") non è quella della
riga ("Servizi per Bambini & Famiglie").

**Il comune non è una `<select>`, ed è una scelta obbligata.** Con 297 voci il
selettore nativo di Android diventa un pannello che copre quasi tutto lo schermo,
senza un pulsante per chiuderlo: chi non vuole scegliere niente deve indovinare
che si esce toccando fuori. Quel pannello lo disegna il sistema operativo e non
si può vestire, quindi l'unico modo di non averlo è non usare una `<select>`. Al
suo posto un `<input>` con `<datalist>`: si scrive "novi" e i suggerimenti
compaiono in linea, si svuota con la ✕ del campo, e resta un controllo nativo —
niente finestre finte da tenere in piedi col JavaScript. Il confronto è per pezzo
di slug, quindi basta un pezzo di nome.

Due filtri sono stati provati e tolti, per ragioni diverse:

- **"solo dove c'è qualcosa in programma"**: è la domanda a cui risponde
  `eventi.html`, che la fa meglio perché lì l'evento *è* la riga.
- **"se piove"** (tolto il 13/08/2026): divideva benissimo — 52% al chiuso, 47%
  all'aperto — ma rispondeva male alla domanda che ha in testa chi lo usa. Con
  "Al chiuso" restavano dentro gelaterie, nidi e scuole di lingue: tutti al
  coperto, nessuno un posto dove passi il pomeriggio di pioggia. Il dato resta
  nella riga aperta, dove è un'informazione e non una promessa. **Un filtro che
  divide non è per forza un filtro che risponde.**

### La categoria si scrive, non solo si colora

Le righe portano `--cat-color/--cat-tint/--cat-ink`, ma un blu e un verde senza
etichetta sono due blu e due verdi. Dove il colore deve dire qualcosa, mettici
il nome (`.com-cat`). Sulle pagine comune l'etichetta compare **solo se il
gruppo mescola più categorie**: dentro una manifestazione uniforme ripetere
"SAGRA & FESTA" su cinque righe è rumore.

Se metti l'etichetta, il colore della riga deve essere il suo: quei gruppi
appiattivano il colore su quello del gruppo e si leggeva "SPETTACOLO" scritto
nell'arancione delle sagre.

### `luoghi.html`: una pagina, non 800 schede

La domanda di partenza era "800 luoghi, faccio 800 schede?". No. Il sitemap ha
270 URL: 800 pagine su template identico col nome del posto scambiato sarebbero i
tre quarti del sito fatti delle pagine più deboli che abbiamo, cioè la
definizione che Google dà dello *scaled content abuse*. E la penalizzazione non
resta lì: si porta dietro il dominio, cioè `eventi.html`.

Quindi una pagina sola con i filtri, come l'agenda.

**Le pagine dedicate (`/luoghi/<slug>.html`) si fanno per i clienti che pagano,
quando ci saranno.** Deciso il 13/08/2026, ed è una decisione editoriale, non una
regola automatica: nessuna soglia, nessun flag che le generi in massa. Si scrive
la pagina di quel cliente, una alla volta, e finisce lì.

Regge perché il rischio dello *scaled content abuse* è **di volume**: erano le
800 pagine su template identico a essere un problema, non quattro o quaranta
pagine con dentro materiale vero. Quello che resta da guardare non è quante sono,
è **quanto c'è dentro ognuna**: essendo un lavoro a mano, lo si vede scrivendola.

Era stata proposta una soglia automatica (descrizione ≥ 600 caratteri, ≥ 3 foto)
e scartata. Utile però il motivo per cui non avrebbe funzionato, misurato sul
catalogo vero:

| | descrizione (mediana) | foto (media) | con orari |
|---|---|---|---|
| le 4 premium | 320 car. | 2,0 | 1 su 4 |
| le 10 col bollino | 259 car. | 1,3 | 6 su 10 |
| le altre 809 | 148 car. | 1,0 | 265 |

Chi paga ha in effetti il doppio di testo degli altri, ma **il doppio di poco è
ancora poco**: 320 caratteri sono tre righe. E in tutto il catalogo solo **3
righe su 823 hanno almeno tre foto** — con quella soglia oggi non nascerebbe
nessuna pagina, nemmeno per il cliente più fornito (5 foto ma 553 caratteri).

Quindi la cosa da chiedere a un cliente non sono i soldi, sono **le foto e mezza
cartella di testo**: è quello che manca per riempire una pagina, e vale come lista
della spesa per il modulo dei materiali.

Da sapere, se un giorno l'elenco sembrasse strano: ai bordi *pagare* e *avere
materiale* non coincidono. Le descrizioni più lunghe del catalogo (una da 990
caratteri, due sopra i 600) sono di posti che non pagano e non hanno il bollino.

Due sorgenti, e **non pesano uguale**:

| sorgente | cosa porta |
|---|---|
| tab `Luoghi` del foglio (ripiego: `data/luoghi.json`) | il catalogo. **È questo l'elenco.** |
| `data/eventi.json` + `data/storico-comuni.json` | solo l'innesto: **quanti eventi** ci sono passati e **cosa c'è in programma** |

I posti che stanno **solo** nell'agenda — le piazze e le vie in cui passa una
sagra — riempiono la pagina soltanto quando un catalogo non c'è per niente,
perché non nasca vuota. Appena il tab esiste, spariscono: con 800 luoghi scelti a
mano, aggiungerne 170 dedotti da "qui è passata una festa" diluisce invece di
arricchire, e "dove si fanno le cose" ha già una pagina migliore, che è
`eventi.html`. L'innesto invece resta sempre, ed è il motivo per cui questa
pagina non è una directory come le altre: nessun altro può scrivere "qui DAOP ha
seguito 7 eventi per famiglie, il prossimo è sabato".

Colonne del tab (i nomi sono tollerati in più grafie, vedi `COLONNE`): `CODICE`,
`Nome`, `Icona`, `Categoria`, `Servizi`, `Tag`, `Indirizzo`, `Città`, `CAP`,
`Provincia`, `Regione`, `Descrizione`, `Descrizione PREMIUM`, `Lat`, `Lng`,
`Premium`, `Premium_dal`, `Consigliato DAOP`, `Gratuito`, `Orari`, `Prezzo`,
`Website`, `Telefono`, `Email`, `Foto_1…5`, `Eta_min`, `Eta_max`.

Quattro cose di quel foglio che non sono ovvie:

- **`Categoria` è gerarchica**, col separatore `›`: "Sport › Arti marziali". Il
  primo livello regge filtro e colore, il secondo si scrive in riga — ed è quello
  che dice davvero cos'è il posto ("Arti marziali" vale più di "Sport"). L'elenco
  delle categorie **non si scrive a mano** da nessuna parte: il foglio ne
  aggiungerà, e colori e icone hanno un ripiego deterministico per le sconosciute.
- **"Se piove" non ha una colonna**: sta dentro `Tag`, che è una stringa a
  trattini. L'ordine dei controlli conta — `all-aperto` contiene `aperto` e
  `parcheggio-coperto` contiene `coperto`, quindi si guarda prima la forma più
  lunga. Nel dubbio "misto", che compare in tutte e due le risposte del filtro.
- **`Icona` è un'emoji**, e sostituisce la miniatura nell'intestazione: si legge
  meglio a 36px e non costa una richiesta.
- **`PassaportoEsploratore`, `CodicePassaporto`, `PassaportoDemo`,
  `CircuitoNome`** si leggono ma non si stampano: sono un'altra funzione, oggi
  vuota su tutte le righe. Inventarle un'interfaccia qui vorrebbe dire indovinare
  come funziona.

Il catalogo esce dal Piemonte (l'Acquario di Genova, un parco a Voghera) e le
province **non si filtrano** su AL/AT/CN come in agenda: chi cerca "gita da
Alessandria" quelle le vuole proprio. Da qui `dove_siamo()`, che nomina le
province che pesano e dice "e dintorni" per le altre.

Come `genera_eventi.py`, c'è un `controlla_crollo()`: l'export CSV di Google
**rispetta i filtri** del foglio, e un filtro rimasto attivo pubblicherebbe 40
luoghi al posto di 800 senza un errore da nessuna parte.

### Il premium aggiunge, non riordina

È la stessa regola già presa su "Adatto Famiglie": un elenco non si spacca in due
quando la separazione smentisce il criterio con cui è fatto. Se la riga di chi
paga stesse più in alto, il resto diventerebbe la serie B di una selezione che
abbiamo fatto noi.

Quindi la scheda premium cambia **cosa** c'è dentro (`Descrizione PREMIUM`, tutte
e cinque le foto, contatti) e non **dove** sta la riga: resta al suo posto
alfabetico, nel suo comune. L'unico spazio in cui la posizione si compra è il
blocco "In evidenza" in cima, che è separato e lo dichiara — e le stesse schede
restano comunque nell'elenco sotto.

**"Consigliato DAOP" è un'altra cosa e non si compra**: è il bollino Family
Friendly (`bollino.html`), lo stesso giudizio che esiste già in agenda. Le due
pillole restano distinte apposta, e `#come-ordiniamo` lo dice a chi legge.

La vetrina la decide **una colonna del foglio** (`In evidenza`), non una regola
dedotta. Per un giorno è stata `premium and consigliato`, e il risultato era che
il blocco non compariva mai: le quattro schede a pagamento hanno tutte
`Consigliato DAOP = no`, ed è giusto così — sono due giudizi diversi, uno lo dà
il cliente e l'altro lo diamo noi. **Una condizione che spegne in silenzio uno
spazio venduto è un difetto, non una cautela.** Serve comunque il premium: la
posizione in cima si compra, e chi non l'ha comprata non ci finisce.

Non è solo stile: **art. 22 comma 4-bis del Codice del consumo** (Omnibus, D.Lgs.
26/2023) impone di dichiarare i parametri di ordinamento di una lista
ricercabile, e omettere che una posizione è stata pagata sta nella lista nera
delle pratiche ingannevoli *in ogni caso*. Da qui il blocco `#come-ordiniamo`,
che non è decorativo: se cambi l'ordinamento, cambia anche quel testo.
`tests/luoghi.js` controlla l'ordine alfabetico proprio per questo — se un giorno
qualcuno ordinasse "premium prima", quella prova diventa rossa.

### Sull'app la posizione si compra. Sul sito no. È voluto

Le due superfici di DAOP hanno **regole di ordinamento diverse, e vanno tenute
diverse** — non è un'incoerenza da sanare, è una scelta per ciascun mezzo.

| | ordine | dove lo dice |
|---|---|---|
| `luoghi.html` (sito) | alfabetico per comune, **la posizione non si vende** | `#come-ordiniamo` |
| Ginetto (repo `daop-mobile`) | **Premium sempre primo, ha pagato**, poi distanza | badge `✦ Sponsorizzato` su ogni card + sezione "Come ordino i risultati" |

Nell'app, `_tier()` in `app.js`: 0 = Premium, 1 = Consigliato DAOP *solo se non si
conosce la posizione*, 2 = il resto. Con il GPS attivo comanda la distanza e il
bollino torna a essere solo un'etichetta, così un consigliato lontano non
scavalca un posto perfetto vicino. Gli **eventi** invece restano in ordine di
data anche per chi paga: su un calendario l'ordine non si compra.

Perché la differenza regge: in un elenco di 823 righe l'ordine lo interpreta chi
legge, e alfabetico è l'unica promessa che possiamo mantenere. In una risposta che
nomina due o tre posti l'ordine *è* il consiglio — e proprio per questo lì la
dichiarazione deve stare attaccata alla voce, che è quello che fa il badge.

Nel repo dell'app c'è anche una suite di prove chiamata *"onestà
dell'ordinamento dichiarato"*: nata dai log del 4-6/08/2026, quando due risposte
su dieci promettevano "in ordine di vicinanza" mentre in cima stava il tier a
pagamento. Ora il prompt obbliga Gemini a dichiarare l'ordine vero e gli vieta
di inventarne altri. **Se un giorno si cambia `_tier()`, va cambiato anche il
testo della sezione nell'app**, se no la sezione diventa una bugia.

### Vendere uno spazio: il limite non è il numero, è il dislivello

Ragionato il 13/08/2026, quando le schede a pagamento erano 4 su 823. Qui stanno
le decisioni; quello che manca ancora è elencato in fondo.

**Si vendono due cose, e una terza non è in vendita.**

| | scarsità | note |
|---|---|---|
| la riga in elenco | infinita | ce l'hanno tutti e 823, gratis |
| la **scheda curata ★** | infinita | costo marginale ~zero: descrizione lunga, 5 foto, orari, contatti |
| **"In evidenza"** in cima | **3 posti** | l'unica scarsità vera, l'unica posizione che si compra |
| il **bollino ♥** | — | **non si vende mai**, a nessun prezzo |

**Non c'è un tetto al numero di schede a pagamento**, ed è stato deciso dopo
averne proposto uno e averlo scartato. Il timore veniva dalle directory in cui
*pagare compra la posizione*: lì il numero conta, perché ogni riga comprata
spinge giù una riga scelta e l'ordine mente. Qui l'ordine è alfabetico e c'è una
prova che lo difende, quindi cento schede a pagamento vogliono dire cento posti
con **più informazioni vere** — il lettore ci guadagna.

Quello che può rompersi non è quante righe pagano, è **quanto diventa povera una
riga che non paga**. Da qui la regola vera:

> **Il pavimento della riga gratis non si abbassa mai per far risaltare quella a
> pagamento.** Categoria, comune, descrizione, servizi, età e mappa restano su
> ogni riga. Se un giorno la riga gratis diventasse nome + comune, basterebbero
> dieci schede curate a far sembrare rotto tutto il resto.

È un vincolo su cosa **non** togliere, non su quanto vendere: lascia crescere il
business quanto vuole.

I due limiti che restano non sono editoriali. **"In evidenza" ha 3 posti**, e non
c'è ancora una regola per il quarto cliente che li compra (rotazione? i più
recenti? si alza il numero?) — va decisa **prima** di venderne il quarto, perché
deciderla con un cliente che ha già pagato vuol dire deciderla male. E il secondo
limite è **il tempo**: ogni scheda curata costa raccolta materiali più revisione,
e cento clienti sono decine di ore. Non è una policy, è aritmetica, e si alza
solo con un modulo che raccolga i materiali al posto tuo.

**La revisione editoriale non è pignoleria.** Chi paga scriverà "il parco più
bello del Piemonte". Se le schede a pagamento suonano come volantini, il lettore
smette di fidarsi anche delle altre 819 — e a quel punto non vale più niente
neanche quello che vendi.

**Oggi la pagina non ha ancora traffico.** È nata il 12/08/2026 e nell'export del
14/08 ha **zero impressioni** — normale, i dati arrivano fino al 12. Intanto il
sito fa 2.777 clic in 28 giorni, ma **l'82% va alle schede evento e solo il 12% a
`eventi.html`**: quel traffico è gente che cerca il nome di una sagra, non un
posto dove andare. I primi clienti non stanno comprando un pubblico: stanno
comprando una scommessa. Non promettere numeri che non puoi mostrare, e tienili a
un prezzo da pionieri.

(La cifra "1.932 clic al mese di `eventi.html`" che stava qui era sbagliata due
volte: era il totale del sito, non di quella pagina, ed è invecchiata in tre
giorni. `eventi.html` da sola fa 331 clic su 13.553 impressioni.)

#### Tre numeri, cercati in rete il 13/08/2026

Servono a tenere le aspettative in scala, non a fare un piano industriale.

| | |
|---|---|
| conversione tipica gratis → pagante (freemium) | **2-5%** → sulle 823 righe fa **16-41 clienti** a regime |
| ricavo di una directory di nicchia piccola | **100-500 $/mese**, cioè qualche migliaio di euro l'anno |
| traffico da cui si comincia a poter vendere | **3.000-5.000 visite/mese** |

Il terzo è quello che conta adesso, e nei tre giorni fra questa ricerca e
l'export del 14/08 è cambiato: il sito ha fatto **2.777 clic in 28 giorni**, cioè
è arrivato *al bordo* di quella soglia invece di stare molto sotto. Non
cambia la conclusione, ne cambia il tono: la leva resta far crescere le pagine,
ma non è più una scadenza lontana. Attenzione a due cose prima di brindare —
quel numero è concentrato al 95% negli ultimi dieci giorni, e va alle schede
evento, non a `luoghi.html`, che è quello che si sta vendendo.

I primi due numeri vengono in buona parte da blog di aziende che vendono
software per directory: hanno interesse a far sembrare il business migliore di
com'è. Vanno letti come ordine di grandezza, non come promessa.

La ricerca ha anche confermato che **non mettere un tetto è la norma**: nessuno
limita il numero di schede a pagamento, e il modello standard è a livelli. Quello
che tutti vendono e **noi no** è la *priority placement*, cioè la posizione in
classifica. Restiamo più severi del mercato apposta: è la cosa che ci tiene fuori
dal tiro dell'art. 22 ed è una cosa che gli altri non possono dire.

#### I link in uscita di chi paga vanno qualificati

Un link verso il sito di un cliente è un link commerciale, e le policy di Google
chiedono `rel="sponsored"` (o almeno `nofollow`): un link a pagamento che passa
PageRank è uno **schema di link**, e si paga con un'azione manuale **sul
dominio** — cioè su `eventi.html`, che è la pagina che regge il traffico. Il
rischio non resta sulla pagina che l'ha causato.

In `riga()`: `sponsored` sulle schede a pagamento, `nofollow` sulle altre, che
sono segnalazioni nostre e non rapporti commerciali. `tests/luoghi.js` lo
controlla. Se un giorno nasce un altro spazio venduto — un banner, una scheda
sponsorizzata in agenda — la regola vale anche lì.

**Far crescere la pagina e far valere di più lo spazio sono lo stesso lavoro.**
`luoghi.html` è linkata dalla nav di 292 pagine ma da nessun corpo di pagina: la
pagina comune di Acqui Terme parla di eventi e non dice che ad Acqui ci sono 25
luoghi. E le pagine di incrocio ("piscine per bambini in provincia di
Alessandria", "dove andare con la pioggia a Casale") non esistono ancora: sono
30-50 pagine che rispondono a ricerche vere, e sono l'inventario che poi si
rivende.

Cosa manca, in ordine di resa:

1. **Il conteggio delle aperture di scheda.** GA4 registra i clic *dalla* scheda
   (mappe, telefono, sito) ma non le aperture: al rinnovo puoi dire "47 hanno
   chiesto le indicazioni" e non su quante volte. È il momento in cui smetti di
   vendere fiducia e cominci a vendere evidenza.
2. **`Premium_al`, la data di scadenza.** Nel foglio c'è solo `Premium_dal`:
   **niente si spegne da solo**. È un problema di cassa (nessun innesco per il
   rinnovo) e di correttezza (continui a pubblicare uno spazio non più pagato).
3. **Un modulo per i materiali** che scriva nel foglio. Il collo di bottiglia non
   è vendere: è che i contenuti non arrivano mai.

Ultima cosa, fuori dal nostro mestiere: **DAOP è un'associazione e vendere spazi
pubblicitari è attività commerciale**, con conseguenze fiscali che cambiano
secondo l'inquadramento (APS, ASD, regime 398/91). Da sentire col commercialista
prima della prima fattura.

### Le locandine: due misure, due posti

Le immagini stanno nel bucket Supabase, **piano gratuito, tetto 5 GB di traffico
al mese**. L'08/08/2026 sono uscite da git ed è successo questo: il traffico è
passato da ~10 a ~250 MB al giorno, cioè una proiezione a ~6,4 GB — le
locandine si sarebbero spente da sole verso il 26 del mese, tutte insieme e
senza che niente diventasse rosso.

Da qui la regola: **negli elenchi va la miniatura, l'originale solo dove
l'immagine si guarda.**

| dove | cosa | perché |
|---|---|---|
| righe di agenda, comune, landing (50-60px) | `/assets/miniature/*.webp` | ~100 per sessione |
| copertine delle corsie (262px) | `/assets/miniature/*.webp` | sono le prime 4 immagini della pagina |
| link "Locandina", scheda evento, JSON-LD | originale su Supabase | lì si legge davvero |

Le miniature stanno **in git** (~25 KB l'una): il conto che aveva fatto uscire
le locandine — 190 KB × ~1800 l'anno = 340 MB — a un settimo del peso non si
ripresenta, e GitHub Pages non ha tetto di banda.

`loc_path(loc, mini=True)` guarda se il file esiste su disco e **ripiega
sull'originale** se non c'è: una locandina arrivata stanotte non ha ancora la
sua miniatura e la pagina esce comunque. `scripts/genera_miniature.py` le
genera (serve Pillow e la rete), gira in CI prima di `genera_eventi.py` e
lavora solo sulle nuove.

`centri-estivi.html` non le usa ancora: ha un generatore suo e le sue locandine
non passano da `data/eventi.json`.

`luoghi.html` ha le foto su un altro bucket (`luoghi-foto`) e non mette **nessuna
immagine nell'intestazione della riga**: al suo posto c'è l'emoji della colonna
`Icona`. La foto sta nel corpo, cioè dentro un `<details>` chiuso, che il browser
non disegna: con `loading="lazy"` non parte nessuna richiesta finché la riga non
si apre. Misurato, non supposto — scorrendo tutta la pagina partono **zero**
richieste, aprendo una riga ne parte **una**, e `tests/luoghi.js` lo ricontrolla
a ogni run. È la differenza fra 800 foto per sessione e una manciata.

## Prestazioni: `eventi.html` è il caso difficile

294 schede, ~11.000 nodi, 1,4 MB. Convenzioni misurate (Chromium, viewport
Pixel 6, CPU 4x), da non smontare per distrazione:

- **`content-visibility:auto` + `contain-intrinsic-size`** su `.event-card` e
  `.ev-hl-block`. È la voce più pesante della pagina. Il testo resta nel DOM:
  ricerca interna, Ctrl+F e motori lo vedono lo stesso.
- **Non forzare il layout al caricamento.** `offsetHeight` su un documento da
  11.000 nodi costava 590 ms in un colpo solo. Se serve misurare, fallo dopo il
  primo disegno (`requestAnimationFrame`) e scrivi la custom property **solo se
  il valore è cambiato**: scriverla su `<html>` invalida lo stile dell'intero
  documento, e su Android la barra dell'indirizzo che si ritira è un `resize`.
- **Gli indici di ricerca si costruiscono alla prima ricerca**, non al
  caricamento: leggere il `textContent` di 294 righe è lavoro che quasi nessuno
  usa.
- **Niente dati lunghi negli attributi ripetuti.** I link "Aggiungi al
  calendario" portavano nome, date e descrizione in percent-encoding dentro
  l'`href`: 490 byte per riga, 144 KB. Ora l'HTML ha la sola base e i campi si
  riempiono all'apertura della riga, leggendo dal DOM. Senza JS il link apre
  Calendar col modulo vuoto invece di essere rotto.

Il JSON-LD in fondo (~405 KB) **si lascia**: toglierlo vale ~50 ms misurati e
costa i rich result eventi sulla pagina più forte del sito.

## Misurare, non stimare

C'è Chromium in `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` e
`playwright-core` si installa in un minuto. Due avvertenze imparate a spese
proprie:

- **La macchina è rumorosa.** Misurare due versioni in sessioni separate dava
  differenze del 40% fra un giro e l'altro dello *stesso* file. Le varianti
  vanno alternate dentro lo stesso processo, ~10 giri per parte, e si confronta
  la mediana.
- **Le locandine sono su Supabase e l'ambiente di sviluppo le blocca.** Gli
  screenshot vengono con i riquadri grigi: va bene per confrontare il layout,
  non per giudicare le immagini.
- **GA4 non si prova da `file://`.** Le pagine generate linkano gli script alla
  radice (`/assets/js/cookie-consent.js`), che da `file://` diventa
  `file:///assets/...` e risponde 404: `window.daopConsensoAnalytics` resta
  `undefined` e sembra che il tracciamento sia rotto. Non lo è — le pagine
  scritte a mano usano percorsi relativi e "funzionano", il che rende il
  confronto ancora più ingannevole. Per provarlo davvero serve un server:
  `python3 -m http.server 8899` e si apre `http://localhost:8899/…`.

## Verifiche prima di pubblicare

Due controlli, e girano tutti e due in CI **dopo** il commit: il sito si
aggiorna comunque e la run diventa rossa. È una scelta, non una svista — il
sito fermo un giorno con gli eventi di ieri è peggio di una pagina con un
difetto.

```bash
python3 scripts/valida_jsonld.py                    # dati strutturati
cd tests && npm install && npm test                 # prove di fumo (Playwright)
```

`valida_jsonld.py` legge l'HTML: vede i dati strutturati, non il JavaScript.
Riferimento all'11/08/2026: 289 pagine, 532 Event, 8 avvisi noti, 0 errori.

`tests/` copre proprio quello che l'altro non vede — apertura righe, link
calendario ricostruito al volo, filtri, ricerca, stato vuoto, ancore `#ev-` e
`#lg-`, più le convenzioni che qualcuno smonterebbe per distrazione
(`content-visibility`, l'href del calendario che resta la sola base, e su
`luoghi.html` l'ordine alfabetico che il premium non deve scavalcare). Gira sui
file veri appena generati: non c'è un ambiente di prova. In un ambiente che ha
già un Chromium, `CHROMIUM_PATH=/percorso/chrome npm test` evita lo scaricamento.

### Un `<section>` non è un contenitore neutro

`assets/css/daop-system.min.css` ha `section{padding:100px 24px}` — pensata per
le fasce a tutta larghezza della home. Vale per **ogni** `<section>` che non
dichiara il suo padding, quindi anche per un gruppo di righe dentro un elenco.

Su `luoghi.html` ogni comune si portava dietro 72px di vuoto sopra e 72 sotto.
Senza filtri non si vedeva, perché le sezioni sono alte; **filtrando** restava
una riga in mezzo a 144px di niente, e sembrava un difetto del filtro. Non lo
era: il difetto c'era sempre, il filtro lo rendeva visibile.

Da qui due cose: `.lg-grp{padding:0}`, e una prova che confronta l'altezza di
ogni gruppo con quella del suo contenuto. Se usi `<section>` per raggruppare
qualcosa dentro una pagina, azzera il padding — o usa un `<div>`.

Quando aggiungi una sezione che un filtro può nascondere, controlla che non
resti in aria il titolo che sta **prima** di essa e fuori da essa: è già
successo, ed è il tipo di guasto che si vede solo filtrando.

## Git

Il workflow committa da solo su `main`. Prima di lavorare, `git pull origin
main`: la run notturna ha quasi sempre spostato la testa.
