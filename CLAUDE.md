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

**Oggi la pagina non ha ancora traffico.** È nata il 12/08/2026; `eventi.html` fa
1.932 clic al mese da Search Console, `luoghi.html` parte da zero. I primi
clienti non stanno comprando un pubblico: stanno comprando una scommessa. Non
promettere numeri che non puoi mostrare, e tienili a un prezzo da pionieri.

#### Tre numeri, cercati in rete il 13/08/2026

Servono a tenere le aspettative in scala, non a fare un piano industriale.

| | |
|---|---|
| conversione tipica gratis → pagante (freemium) | **2-5%** → sulle 823 righe fa **16-41 clienti** a regime |
| ricavo di una directory di nicchia piccola | **100-500 $/mese**, cioè qualche migliaio di euro l'anno |
| traffico da cui si comincia a poter vendere | **3.000-5.000 visite/mese** |

Il terzo è quello che conta adesso: tutto il sito sta **sotto** quella soglia. Non
è un problema, è una scadenza — dice che la leva non è vendere di più, è far
crescere la pagina, e conferma l'ordine dei lavori qui sotto.

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
