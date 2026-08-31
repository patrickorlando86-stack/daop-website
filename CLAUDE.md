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

#### Il footer non sta in un posto: sta in quindici, e nessuno lo compone

Scoperto il 31/08/2026 andando ad aggiungere `@daop_cuneo`, che **mancava da
tutto il sito**. Cuneo è aperta dal 04/08 ed è una pagina DAOP come le altre due
dal 26/08, con Giovanni curatore: il codice lo sapeva — sta in `PROVINCE_IG`,
col curatore accanto — e il footer no, su ~470 pagine.

Il motivo è che **il footer è l'unico pezzo del guscio che nessun generatore
compone.** `_guscio()` lo *copia*, non lo *costruisce*: legge quello che trova
in `eventi.html` e lo incolla. Finché una cosa si copia e basta, l'unico posto
che la sa è quello scritto a mano.

E i posti scritti a mano non erano uno. Sono **quindici**:

| dove | quante | perché |
|---|---|---|
| `eventi.html` | 1 | la sorgente di `_guscio()`, cioè ~470 pagine |
| `rubriche.html` | 1 | `genera_rubriche.py` ha un guscio suo e legge **da lì** |
| pagine scritte a mano | 13 | `index`, `ginetto`, `libri`, `media`, `piattosano`, `bollino`, `404`, le due legali, `esploratore`, le tre di prova |

La quindicesima grafia dello stesso guasto già documentato per `ferragosto.html`
e per i marker delle rubriche, con una differenza: **qui non lo prende nessuna
rete di sicurezza**, perché non è un file che resta indietro — è un file che
nessuno ha mai avuto il compito di aggiornare.

Da qui due cose, e la seconda vale più della prima:

- **Toccando il footer si toccano `eventi.html`, `rubriche.html` e le tredici a
  mano.** Il grep che lo verifica è `grep -rl "Instagram AT" --include=*.html`
  incrociato col nuovo valore: se una pagina ha il vecchio blocco e non il
  nuovo, è rimasta indietro.
- **È il punto fragile per una provincia nuova, e non è il codice.** Aprire la
  quarta provincia costa 3-4 righe per eventi e luoghi — `PROVINCE_PUBBLICATE`
  fa il resto da solo — e poi quindici modifiche a mano che nessuna prova
  chiede. Se un giorno vale la pena chiuderlo davvero, il modo è comporre quella
  colonna da `PROVINCE_IG`, che è già l'unico posto dove i profili vivono
  (`fonte_provincia()`), e non da una lista nuova.

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

| giorno | clic da Google | utenti GA4 | copertura |
|---|---|---|---|
| 8 ago | 603 (il picco vero) | ~30 | ~5% |
| 11 ago | 270 | ~30 | ~11% |
| 12 ago (fix alle 14:53) | 311 | ~120 | mezza giornata |
| 13 ago | **582** | ~220 | **~38%** |

Prima del fix GA4 misurava circa il **5%** della realtà, dopo circa il **38%**.
Il resto è il banner di consenso, ed è fisiologico: **non si arriverà mai in pari
con Search Console**, e il criterio di successo è che il divario si stringa, non
che si chiuda. Il `+793%` settimanale dello screenshot del 15/08 (697 utenti
attivi, 839 sessioni, 1.531 visualizzazioni, contro una settimana precedente
misurata al 5%) è quindi quasi tutto recupero di misurazione: non usarlo come
numero di crescita con nessuno.

**Quel 38% ha sostituito un 70% scritto qui il 14/08, e come ci si è sbagliati
conta più della cifra.** La copertura del 13 agosto era stata calcolata dividendo
gli utenti GA4 del **13** per i clic Search Console del **12**, perché l'export di
quel giorno arrivava solo fino al 12. Il 13 ha poi fatto 582 clic invece di 311,
cioè il denominatore era quasi la metà del vero. Da qui la regola: **Search
Console ha due-tre giorni di ritardo, e un rapporto GA4/SC si calcola solo su
giorni in cui esistono tutti e due i numeri.** Nel dubbio si aspetta l'export
dopo, non si stima.

Nemmeno il 38% è una misura pulita, ed è bene saperlo prima di citarlo: gli
utenti GA4 e i clic SC non sono la stessa unità — chi apre due schede dalla
stessa ricerca è un utente e due clic — quindi il rapporto vero sta un po' più in
alto. Serve a dire l'ordine di grandezza (un terzo, non tre quarti), non a fare
percentuali di precisione.

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

Vale anche **fra GA4 e Search Console**, e in un modo che inganna. Nell'export
GA4 delle pagine su 18/07-14/08 `eventi.html` fa il 28,9% delle visualizzazioni e
le schede il 40,9%; in Search Console sui tre mesi `eventi.html` fa l'11,5% dei
clic e le schede il 76%. Sembra una contraddizione da spiegare: è solo che
**venticinque di quei ventotto giorni sono pre-fix**, e in quei giorni le uniche
pagine che mandavano `page_view` erano `eventi.html` e la home. Il dato
interessante è il rovescio — le schede fanno già il 41% delle visualizzazioni
*avendo misurato tre giorni su ventotto*.

Cosa manca ancora, ed è il pezzo che trasforma il tracciamento in argomento di
vendita: **il conteggio delle aperture di scheda su `luoghi.html`** (vedi
"Vendere uno spazio"). GA4 registra i clic *dalla* scheda, non le aperture.

#### Che non ci sia un `page_view` doppio è stato verificato, non supposto

Il sospetto era ragionevole: dopo un fix del genere il difetto tipico è una
pagina rimasta con il suo `gtag` inline *più* `cookie-consent.js`, cioè due
inizializzazioni e due `page_view` per visita. L'indizio erano i 6,8 eventi per
sessione dello screenshot del 15/08.

Non c'è, e il numero che lo dice è **`page_view` 1.997 contro `session_start`
1.037 = 1,93 pagine per sessione** (GA4, 18/07-14/08). Con una doppia
inizializzazione sarebbe ~3,9. Il resto del conteggio si spiega tutto senza
misteri:

| evento | conteggio | |
|---|---|---|
| `user_engagement` | 2.224 | automatico |
| `page_view` | 1.997 | |
| `scroll_depth` | 1.403 | **nostro**, fino a 4 per pagina |
| `session_start` + `first_visit` | 1.843 | automatici |

Sono 7.467 su 7.676 totali. **Il numero alto di eventi per sessione è il nostro
`scroll_depth` a quattro soglie, non un difetto**: se un giorno risalta di nuovo,
la verifica è questa e non serve rifare l'indagine.

Una pulizia che resta da fare: `scroll` (106 eventi) è l'evento **automatico** di
GA4 e duplica il nostro. Il commento in `daop-track.js` lo prevedeva già —
Amministratore → Flussi di dati → il flusso web → **Misurazione avanzata** →
togliere "Scorrimenti". Meno rumore, e meno benzina per gli avvisi "anomalia".

#### Le dimensioni personalizzate sono undici, e sono tutte registrate

**Fatto: non c'è niente da fare qui.** Le quattro dei corsi — `organizer_id`,
`organizer_name`, `course_id`, `course_name`, ambito **Evento** — sono state
create il **21/08/2026**, verificate a schermo nell'elenco. Con la storica
`categoria_nome` fanno **dodici righe su cinquanta slot**: lo spazio non è, e
non sarà, il vincolo.

Ne segue la sola cosa che conta ricordare: **rispondono dal 21/08 e non prima.**
Una domanda su chi ha guardato i corsi in luglio non ha risposta, e non è un
problema di query.

**Sulle sette di prima non c'è niente da fare.** Verificato il 19/08/2026 in
Amministratore → Proprietà → **Definizioni personalizzate**: tutte e sette
esistono con ambito **Evento**, le quattro del 12 agosto e le tre nate col
"vicino a me" il 15. Questo paragrafo fino a quel giorno le dava come da
registrare ed era una cosa da fare inseguita per sbaglio due volte — se ti serve
sapere se una dimensione c'è, l'unico posto che lo sa è quell'elenco, non questo
file.

C'è anche un'ottava, **`categoria_nome`**, marcata "storica, non più raccolta
dal 2025": era il vecchio tracciamento dei filtri dell'agenda. Si lascia dov'è.
Archiviarla libererebbe uno slot su cinquanta — cioè niente — e farebbe sparire
dai report lo storico che ha raccolto.

`daop-track.js` manda questi sette parametri, col nome scritto identico alla
dimensione:

| parametro | su quali eventi | cosa risponde |
|---|---|---|
| `event_city` | tutti | **in quali comuni è il pubblico** |
| `event_province` | tutti | idem, per provincia |
| `event_title` | tutti | quale scheda genera azioni, non solo visite |
| `metodo_posizione` | `vicino_a_me` | gps / comune / gradino |
| `raggio_km` | `vicino_a_me` | 10, 20, 30, 50 — **dimensione, non metrica** |
| `percent_scroll` | `scroll_depth` | 25/50/75/100 |
| `destination_url` | i clic | dove se ne vanno |
| `organizer_id` | tutti, su `corsi.html` | **a quale realtà va questo clic** |
| `organizer_name` | idem | la stessa cosa, leggibile in un report |
| `course_id` | idem, se il clic parte da un corso | quale corso, con l'id stabile |
| `course_name` | idem | quale corso, leggibile |

Il limite sono 50 dimensioni evento: se un domani ne nasce una vera in più, si
registra e basta, non c'è niente da scegliere.

**Le prime due valgono più delle altre cinque insieme, e non per il "vicino a
me".** `event_city` è la risposta alla domanda che farà ogni cliente di
`luoghi.html`: oggi si può dire "il sito fa 4.878 clic in tre mesi", con quella
dimensione si dice a un posto di Ovada *quanti dei lettori guardano cose a
Ovada*. È il primo pezzo di evidenza vendibile, e **il dato c'è dal 12 agosto**:
non è più una cosa da preparare, è una cosa da leggere.

**Non sono retroattive**, ed è il motivo per cui la data di creazione conta più
della dimensione stessa: quello raccolto prima resta invisibile per sempre.
Quindi `event_city`, `event_province`, `event_title` e `destination_url`
rispondono **dal 12/08**, `percent_scroll`, `metodo_posizione`, `raggio_km`
**dal 15/08**, e le quattro dei corsi **dal 21/08**. Sotto quelle date non c'è niente e non ci sarà mai: una domanda
sul comportamento di luglio non ha risposta, e non è un problema di query.

Nei report compaiono dopo 24-48 ore dalla creazione; in DebugView subito, ed è
così che si verifica di aver scritto bene un nome senza aspettare due giorni.

#### Sopra 2,5 visualizzazioni per utente, stai guardando te stesso

Nel primo export GA4 delle pagine `luoghi.html` risultava con 41 visualizzazioni,
che sembravano un inizio di pubblico. Erano **5 utenti con 8,2 pagine a testa e
2:40 di media**: chi la stava costruendo. Stessa firma su `/rubriche.html` (7,7
per utente), `/ginetto.html` (4,75), la home (157 visualizzazioni da 25 utenti).

Il traffico vero ha la firma opposta, ed è visibile nello stesso export:
`/ferragosto.html` fa 87 visualizzazioni da **72 utenti distinti**, cioè 1,2 a
testa, perché chi arriva da Google guarda una pagina ed esce. **Su una pagina che
non è l'agenda, un rapporto visualizzazioni/utenti sopra 2,5 è navigazione
interna, non pubblico** — e su una pagina nuova, che è quando si è più impazienti
di vedere un numero salire, è quasi sempre così.

## Far girare i generatori

```bash
python3 scripts/genera_eventi.py      # funziona offline
python3 scripts/genera_luoghi.py      # funziona offline, DOPO genera_eventi.py
python3 scripts/genera_centri.py      # richiede rete
python3 scripts/genera_corsi.py       # richiede rete
python3 scripts/genera_rubriche.py    # legge contenuti/rubriche/
python3 scripts/genera_ginetto.py     # offline, DOPO genera_eventi.py (tocca la sitemap)
python3 scripts/genera_idee.py        # offline, DOPO genera_luoghi.py (importa il catalogo)
python3 scripts/genera_pdf.py         # ultimo di tutti, serve Chromium
```

`genera_luoghi.py` va **dopo** `genera_eventi.py`, non prima: legge
`data/eventi.json` e `data/storico-comuni.json` appena riscritti per sapere cosa
c'è in programma in ogni posto. Girando prima scriverebbe "in programma" su
eventi già passati.

C'è però una dipendenza anche nel verso opposto, e **è voluto che sia in
ritardo di un giro**: `genera_luoghi.py` scrive `data/luoghi-comuni.json`
(quali comuni hanno almeno un luogo, con l'ancora del loro gruppo) e
`genera_eventi.py` lo legge per linkare ogni scheda evento ai luoghi del suo
comune. Girando in quest'ordine le schede usano l'indice della notte prima.
Chiudere il cerchio — leggere il foglio Luoghi anche qui, o girare tre volte —
costerebbe più di quello che risolve: un comune che entra oggi nel catalogo
resta senza link per un giorno, e sbagliare in quel verso è gratis. Il verso
opposto no: un link a un'ancora che non esiste scarica in cima a una pagina da
800 righe, ed è peggio di nessun link. Se il file manca, i link non si stampano
e basta.

`genera_eventi.py` legge il foglio Google e, se non lo raggiunge, ripiega da
solo su `data/eventi.json` (l'istantanea committata) e va avanti. Gli altri no:
senza rete `genera_centri.py` stampa "lascio la pagina com'è" e non riscrive
niente — non è un errore, ma vuol dire che le tue modifiche al CSS lì non si
vedono finché non gira in CI.

Il workflow `.github/workflows/aggiorna-eventi.yml` li gira **tutti e nove**
alle 02:00 UTC, committa da solo su `main`, poi passa i controlli (vedi in
fondo).

### Due generatori giravano solo a mano, e non se ne accorgeva nessuno

Fino al 31/08/2026 il workflow ne girava **sette su nove**: `genera_ginetto.py`
(che scrive `esploratore.html`) e `genera_idee.py` (che scrive `/idee/`) non
c'erano, e nemmeno i loro file nell'elenco di quelli committati. Quelle due
pagine si aggiornavano solo se qualcuno lanciava lo script a mano.

È il guasto già pagato nove volte con le stagionali — un file riscritto nel
runner e buttato via con lui — ma **peggiore in un modo preciso**: là il file
era tracciato, quindi la rete di sicurezza in fondo al workflow ("Nessun file
generato resta indietro") faceva diventare rossa la run. Qui il generatore non
girava proprio, quindi non c'era nessun file modificato da notare: **il difetto
non era che qualcosa restasse indietro, era che nessuno ci andava.**

L'ordine non è indifferente e sta nel workflow:

- `genera_ginetto.py` **dopo `genera_eventi.py`**, perché tocca `sitemap.xml`,
  che quello riscrive per blocchi: girando prima, il suo `lastmod` verrebbe
  sovrascritto.
- `genera_idee.py` **dopo `genera_luoghi.py`**, perché importa `genera_luoghi`
  per il catalogo e per il suo CSS, e prende i cinque posti per `CODICE`.
  Girando prima userebbe l'istantanea di ieri.

Nell'elenco dei file committati c'è `esploratore.html` e la **cartella**
`idee/`, non un elenco di file: una pagina idea nuova nasce untracked, e
`git status --untracked-files=no` non la vedrebbe. È la ragione già scritta per
`corsi/` e `guide/`.

## Il canale WhatsApp

Aperto il 14/08/2026. `CANALE_WA` in `genera_eventi.py` è l'unico posto in cui
sta l'indirizzo: **vuoto vuol dire che l'invito non si stampa da nessuna
parte**, che è il comportamento giusto se un giorno il canale si chiude.
`blocco_canale()` compare sulle schede evento, sulle pagine comune e sulle
landing — **323 pagine** al 19/08/2026, tutte tranne i tre `eventi/box-*.html`.
Quelli vivono dentro l'iframe di siti altrui, e chiedere lì un'iscrizione vuol
dire usare lo spazio di qualcun altro per portargli via il pubblico: stessa
ragione per cui non chiedono il consenso ai cookie. `tests/luoghi.js` controlla
che l'invito ci sia su tutte e che non sia mai doppio. Sta in coda dappertutto
in coda **dappertutto, senza eccezioni**: quella sulle edizioni concluse è
durata dal 19 al 28/08/2026, e il perché è finita è due paragrafi più sotto.

**Sta in coda e non in cima**, e il testo dice per prima cosa *quanto spesso si
scrive*: la paura di chi si iscrive a un canale non è il contenuto, è il
diluvio. Niente promesse in più ("contenuti esclusivi") che poi non
manteniamo.

### L'eccezione alla coda è durata nove giorni, e il posto è passato a Ginetto

Dal 19/08/2026 su una scheda di **edizione conclusa** l'invito al canale saliva
sotto l'avviso "Edizione conclusa". **Dal 28/08/2026 non più**: l'invito è
tornato in coda su tutte le schede, senza eccezioni, e quel posto è di Ginetto.

**Il ragionamento del 19/08 regge, quello che è cambiato è l'inquilino.** Lì la
premessa della regola cade: "in cima chiede qualcosa a chi non ha ancora avuto
niente" vale finché la pagina ha qualcosa da dare, e una scheda conclusa non ce
l'ha. Non è un caso di nicchia — al 28/08 sono **211 schede su 419** (il 50%), e
prendono traffico vero: il 16/08 le schede di eventi conclusi hanno fatto 1.237
impressioni.

Due ragioni per Ginetto, e la seconda conta più della prima.

**È misurato più forte, a parità di posto.** Nella settimana 12-18/08
`apri_ginetto` fa **7 clic stando al 71%** della pagina; l'invito al canale, più
in alto al 59%, sta dentro un secchio da 4. Era la richiesta che rendeva di più
del sito, ed era quella messa più in basso.

**Risponde alla domanda giusta.** Chi arriva da Google su una scheda conclusa ha
appena scoperto che la festa è finita e si chiede *e allora cosa faccio?*.
Ginetto risponde **adesso**; il canale risponde giovedì. In coda quella domanda
non è più la sua: chi ha scorso tutta la pagina l'ha già passata.

**Non si affiancano.** Due richieste nello stesso punto si dimezzano, e
misurandole insieme non si saprebbe più quale delle due ha mosso il numero. Per
la stessa ragione **Ginetto in cima non si ripete in fondo**: sarebbe la stessa
richiesta fatta due volte a chi ha già detto di no una volta.

**Le schede ritirate restano com'erano.** Quella pagina dichiara di non essere
attendibile e manda all'agenda: presentare qualcosa di nostro in cima a una
scheda che stiamo smentendo è chiedere fiducia nel punto esatto in cui l'abbiamo
appena tolta. È la stessa logica per cui lì spariscono i fatti e i due bottoni.

**Il testo è identico nelle due posizioni, apposta** — vale per Ginetto come
valeva per il canale. Cambiando insieme posizione e parole non si saprebbe quale
delle due ha spostato il numero. Cambia solo il guscio: in cima un `<aside
class="ev-ginetto-alto">` dentro l'articolo, in fondo la fascia a tutta
larghezza.

Quanto vale lo spostamento è misurato a 412px, non stimato: su
`2-cuori-2-capanne-alessandria.html` Ginetto passa dal **68,5%** della pagina al
**11,9%**, cioè da sotto la piega a **540px, dentro la prima schermata**. Il
canale in coda resta al 72,9%.

`tests/luoghi.js` difende quattro cose: che l'invito al canale stia in coda su
tutte le pagine, che ogni conclusa abbia Ginetto in cima, che non l'abbia anche
in fondo, e che nessuna pagina viva ce l'abbia in cima. Verificate rosse tutte e
quattro rimettendo il difetto, non supposte. Attenzione se si tocca quella
prova: i nomi `ev-ginetto-alto` e `ev-ginetto` stanno anche nel `<style>` di
ogni pagina (`PAGINA_CSS` è incollata dappertutto), quindi si cerca l'attributo
intero (`class="ev-ginetto-alto"`, `class="bg-cream ev-ginetto"`) — un
`includes` sul nome secco direbbe "in cima" su tutte e 446 le pagine e la prova
passerebbe sempre.

#### Perché non una bolla, e perché non in cima all'agenda

La proposta di partenza era **far vedere Ginetto su `eventi.html`**, che è la
pagina singola più forte del sito. Due cose l'hanno spostata altrove.

**`eventi.html` non è dove sta il pubblico.** Nei 28 giorni al 22/08 fa 629 clic
(il 7,7%), le schede evento ne fanno 5.742 (il 69,8%) — nove volte tanto. E su
quelle Ginetto **c'era già**, in fondo. La copertura non era da creare, era da
spostare.

**Una bolla fissa in basso a destra è da non fare.** Non per la SEO — la soglia
dell'*interstitial penalty* è il 15-25% del viewport e una bolla ci sta
abbondantemente sotto — ma perché è la forma più riconoscibile come pubblicità
che esista sul web (NN/g, *banner blindness*). I benchmark che si trovano sui
widget a bolla (5-15%) sono chat di assistenza su siti commerciali, dove chi
scrive ha un problema e cerca aiuto: non sono confrontabili. Il numero
confrontabile è in casa ed è lo 0,3% dell'invito al canale.

**Una barra fissa nemmeno.** Ginetto da solo è un bottone solo, e vale la regola
già scritta per `.ev-barra`: una barra fissa costa 62px di schermo a tutti, e
per un'azione sola prende più di quello che rende. "Vicino a me" non è la
seconda azione che la giustifica — è già a 795px, cioè nella prima schermata.

**E soprattutto vale la distinzione del 28/08**: un servizio si mette davanti,
una richiesta no. Su una scheda viva o in cima all'agenda Ginetto è una
richiesta, e per giunta porta fuori dal sito prima che la pagina abbia dato
qualcosa. Sta dalla parte dell'invito al canale, non dalla parte di "Come
arrivare".

#### Lo stato vuoto dell'agenda: l'unico posto in cui Ginetto è una risposta

Fatto lo stesso giorno. Quando la ricerca non trova niente, `eventi.html`
diceva solo «Nessun evento con questi filtri. Prova ad allargare la ricerca.»
Adesso sotto c'è Ginetto.

È l'unico momento in cui **la pagina ha fallito e lui risponde meglio di lei** —
cioè l'unico punto dell'agenda in cui non è una richiesta ma una risposta. E
**costa zero pixel a chi trova quello che cerca**, che è la ragione per cui sta
lì e non in cima. Misurato: scorrendo alla barra dei filtri e cercando una
parola che non esiste, il blocco è a 501px dal bordo alto dello schermo, cioè
interamente in vista.

Le decisioni che non si ricavano dal diff:

- **Il link va su `ginettoapp.it`, non su `/ginetto.html`.** Lì chi legge vuole
  una risposta adesso, non una pagina che gli spieghi cos'è Ginetto — e così
  `daop-track.js` riconosce il dominio e conta **`apri_ginetto` da sé**, senza
  una riga in più da nessuna parte.
- **Il blocco in fondo a `eventi.html` resta dov'è e com'è**, e continua a
  puntare a `/ginetto.html`. Sono due imbuti diversi apposta: quello manda alla
  landing che esiste per vendere Ginetto (FAQ, JSON-LD, Play Store), ed è
  l'unico link interno di peso che quella pagina riceve dalla più forte del
  sito. Che non produca un evento con un nome suo **non vuol dire che non si
  misura**: è navigazione interna, e `daop-track.js` dice in testa perché non si
  traccia — ogni pagina manda già un `page_view`, e il percorso si legge con
  un'esplorazione.
- **`apri_ginetto` su `/eventi.html` scatta anche dal footer**, e i due non si
  distinguono. Va bene: al footer arriva circa uno su cento, quindi la baseline
  è quasi zero e il delta è tutto dello stato vuoto. **Va segnato il numero di
  oggi prima di leggere quello di domani.**
- **Il `<p>` interno tiene l'id `events-empty`**, perché il JS ci scrive dentro
  con `textContent` e cancellerebbe qualunque markup: Ginetto sta in un
  fratello, e quello che si accende e si spegne è il contenitore
  `#events-vuoto`.
- **Il margine fra i due paragrafi sta su `p+p`** e non su `.events-empty-g`:
  `.events-empty p` ha specificità 0,1,1 e batterebbe una regola di sola classe.
  È lo stesso inciampo del crumb dei corsi (`.co-crumb a{color:inherit}` che
  vinceva su `.page-hero a`), e si evita guardando la specificità, non il nome.

**Il numero da guardare fra un mese** è `apri_ginetto` ogni mille `page_view`
sulle schede, letto contro la baseline di 7 clic in 7 giorni. E vale
l'avvertenza di sempre sulle soglie di scroll citate qui sopra: sono misurate
col filtro `/eventi/`, che **esclude `eventi.html`** — la stessa trappola già
documentata per `vicino_a_me`. L'ordine di grandezza regge, il numero non è di
quella pagina.

### Il clic sull'invito ha un nome suo

Fino al 19/08/2026 cadeva nel ramo generico di `nome_evento()` in
`daop-track.js` e finiva in **`click_sito_organizzatore`**, insieme ai clic
verso il sito di chi organizza. Non era rotto — `destination_url` c'era — ma
l'unica domanda che il canale pone (*quanti si iscrivono ogni mille visite*) si
poteva rispondere solo filtrando a mano, cioè mai: non era una conversione, non
si leggeva in trend.

Ora l'evento è **`iscrizione_canale`**. Il confronto è su
`whatsapp.com/channel` e non su `whatsapp`: un `wa.me/...` nei recapiti è il
numero dell'organizzatore, non noi.

**Il numero da guardare non è il totale degli iscritti**, ed è la trappola di
questo periodo: si parte il 19 agosto, con il 79% dei clic del trimestre
concentrato negli otto giorni appena passati. Un tasso misurato da qui a metà
settembre misurerebbe il crollo dell'onda stagionale, non l'invito. Si guarda
**`iscrizione_canale` ogni mille `page_view` sulle schede**, e lo si legge
contro il 15 settembre che è già la data del verdetto per tutto il resto.

#### Quanti lo vedevano, e quanti lo toccavano

Misurato il 19/08/2026 su GA4, finestra **12-18 agosto**, filtro percorso
`/eventi/` (che prende schede, pagine comune, `oggi`, `weekend` e le sei
d'incrocio, **non** `eventi.html`, che è `/eventi.html` senza barra). È la
lettura che ha fatto spostare l'invito, e va rifatta prima di spostarlo ancora.

**Primo pezzo: a che altezza sta l'invito.** Non in fondo — sotto ci sono il
blocco di Ginetto e il footer, che valgono l'ultimo 40% della pagina. Misurato
con Playwright a 412px su 40 schede: su una scheda **viva** l'invito è
interamente in vista al **59% dello scroll** (mediana; range 45-66%), e comincia
a entrare intorno al 41%. Fra il 19 e il 28/08 su una **conclusa** stava allo
**0%**; da lì in poi quel posto è di Ginetto e l'invito è tornato al 59% anche
lì (vedi "L'eccezione alla coda è durata nove giorni").

Da qui una cosa da non rifare: **la soglia da leggere è 50, non 100.** Chi arriva
al 100% non è "chi ha visto l'invito", è chi ha letto anche il footer.

**Secondo pezzo: dove si fermano.** `page_view` 2.160, `scroll_depth` 1.993 (di
cui 998 il 12-14, senza dettaglio perché `percent_scroll` nasce il 15). Sul
15-18: 25% → 546, 50% → 308, 75% → 133, 100% → 8. Cioè, su cento che aprono una
pagina: **~51 cominciano a scorrere, ~29 arrivano dove l'invito è a schermo, ~12
passano il 75%, ~1 vede il footer.**

La coda ripida non è un difetto di misura — ci si era pensato. L'evento
automatico `scroll` di GA4, che scatta al 90%, fa 50 in sette giorni: coerente
con i nostri 8 al 100% in quattro. Sotto l'invito non ci va nessuno perché sotto
l'invito non c'è niente da leggere.

**Terzo pezzo, ed è quello che conta.** In sette giorni l'invito è stato visto
**~600 volte** e `click_sito_organizzatore` — il secchio che lo conteneva fino
al 19/08, insieme ai clic verso i siti degli organizzatori — fa **4**. Quindi il
canale converte **fra lo 0 e lo 0,6%**, verosimilmente ~0,3%. Nella stessa
settimana, sulle stesse pagine: `click_come_arrivare` 33, `aggiungi_calendario`
10, `click_telefono` 9, `apri_ginetto` 7.

**Non era (solo) la posizione, ed è la conclusione da non semplificare.** La
posizione costava un fattore 3,5 — 29 su 100 lo vedevano invece di 100 su 100 —
e quel fattore lo spostamento sulle concluse te lo restituisce. Ma anche fra chi
lo vedeva non lo toccava quasi nessuno, mentre le altre azioni della stessa
pagina funzionano benissimo. Se lo 0,3% è il tetto dell'*ask*, da ~600 viste a
settimana si passa a ~2.000 e da 2 iscritti a 6-7: meglio, non risolutivo.

**Il corollario per la newsletter**, che è la domanda da cui è partito tutto: su
quella stessa pagina un modulo email chiede *più* attrito (nome, indirizzo,
conferma) allo stesso pubblico che oggi non tocca un bottone da un tocco solo.
Se lo 0,3% è il tetto dell'ask lì, la newsletter lì sotto farà peggio, non
meglio. Il pezzo non ancora provato è **il testo**, non il canale.

**Come si rifà la lettura.** Esplora → Esplorazione a forma libera; nei report
standard quella scomposizione non c'è. Righe `percent` (è `percent_scroll`, il
nome visualizzato in GA4 è scritto male), valori Conteggio eventi, filtri
`Nome evento` = `scroll_depth` e `Percorso pagina` contiene `/eventi/`. Per il
denominatore si toglie il filtro sul nome evento e si mettono i nomi in riga.
Attenzione al periodo: `percent_scroll` esiste dal 15/08, quindi una finestra
che parte prima mescola quattro giorni di dettaglio con giorni di `(not set)` e
il rapporto esce sbagliato — la riga `(not set)` è il campanello.

Due eventi automatici di GA4 sporcano questa tabella e sono gli stessi di cui si
parla più sopra: **`scroll`** (50) e **`click`** (46, i "clic in uscita", che
duplicano in parte i nostri `click_*`). Si spengono da Amministratore → Flussi
di dati → il flusso web → **Misurazione avanzata**.

Il messaggio del giovedì lo scrive il generatore in `data/messaggio-canale.txt`
(`messaggio_canale()`): **WhatsApp non ha API pubbliche per pubblicare sui
canali**, quindi il copia-incolla resta a mano per forza, ma scegliere gli
eventi e scrivere no. È la differenza fra due minuti a settimana e mezz'ora, ed
è la ragione per cui i canali si abbandonano alla seconda settimana.

Tre regole della selezione, tutte nate guardando l'output vero:

- **davanti chi comincia in quei due giorni.** Ordinando per data di inizio il
  primo messaggio era fatto di dieci mostre: sono aperte da settimane, quindi
  vincono l'ordinamento. "Cosa c'è questo weekend" non vuol dire "cosa è ancora
  aperto".
- **due tetti, non uno**: per comune e per manifestazione. Fermano due monopoli
  diversi — una patronale da 19 sotto-eventi concentra un paese, "Castelli
  Aperti" è un'iniziativa in quindici paesi e il tetto per comune non la vede.
- **ordine mescolato con seme la data del weekend.** Con l'alfabetico Acqui e
  Alfiano c'erano sempre e Vesime e Voltaggio mai: è una distorsione che non si
  vede in un messaggio, si vede in quattro settimane. Il seme fisso serve a non
  ricommittare il file a ogni run notturna.

Cosa il canale **non** dà, e non va promesso a nessuno: niente statistiche
oltre a iscritti/copertura, niente esportazione della lista (è di Meta, non
nostra), niente segmentazione per età. Il "98% di open rate" che si trova in
rete è dei messaggi 1-a-1 della Business API, **non dei canali**. Quando
servirà una lista di proprietà e misurabile, quella è l'email — e il posto dove
chiederla sarà il canale stesso.

### La barra delle azioni sulle schede: un servizio si mette davanti

Fatta il 28/08/2026. Sul telefono, in fondo a ogni **scheda viva**, una barra
fissa con "Come arrivare", "Chiama" (dove il foglio ha un numero) e
"Calendario". Sono 165 schede su 173 al 28/08 — le otto che restano fuori non
hanno un indirizzo mappabile, quindi avrebbero una sola azione.

**Il conto e' misurato a 412px, non stimato.** `.ev-actions` — cioe' le due
cose che uno viene qui a fare — comincia a **1.725px** su una pagina alta
4.632, ed e' interamente in vista solo **dopo il 25% dello scroll**. E il 25%
e' la soglia che in GA4 supera **circa meta'** di chi apre la pagina (12-18
agosto: 546 `scroll_depth` al 25% su ~1.070 `page_view`; al 50% sono 308,
cioe' il 29%). Uno su due non ha mai visto i due bottoni piu' cliccati del
sito: `click_come_arrivare` e' l'azione numero uno delle schede, 33 in sette
giorni contro 10 del calendario e 9 del telefono.

**E' lo stesso conto dell'invito al canale, ma il verso e' opposto, ed e' la
cosa da non confondere.** Quello e' una *richiesta*: in cima chiederebbe
qualcosa a chi non ha ancora avuto niente, e infatti converte allo 0,3%.
Questi sono *servizi* — la mappa e la data sono la ragione per cui uno e'
arrivato. Un servizio si mette davanti, una richiesta no.

Le decisioni che non si ricavano dal diff:

- **Non sostituisce `.ev-actions`**, che resta dov'e'. La pagina non perde
  niente (li' c'e' anche "Torna all'agenda"), e cosi' la barra si puo'
  togliere in qualunque momento senza lasciare un buco.
- **Niente JavaScript**, e non e' pigrizia: una barra che compare allo scroll
  e' un terzo ascoltatore su una pagina che ne ha gia' due, e sbaglierebbe
  proprio nel primo istante, che e' quando meta' del pubblico decide.
- **Mai su una scheda conclusa o ritirata.** Li' "Come arrivare" e "Aggiungi
  al calendario" sono esattamente i due bottoni dannosi che `render_pagina()`
  gia' toglie dal corpo — mandano in macchina, e scrivono in agenda, verso un
  appuntamento che non c'e'. Rimetterli *fissi* sarebbe peggio di prima.
- **Sotto le due azioni non si stampa niente.** Una barra fissa costa 62px di
  schermo a tutti; per un bottone solo prende piu' di quello che rende.
- **Lo spazio sotto il footer e' un elemento vero in flusso**, non un
  `padding` su `body:has(.ev-barra)`: `:has()` non c'e' dappertutto, e dove
  manca il footer finirebbe sotto la barra in silenzio.
- **`z-index:60` e non di piu'**: il banner dei cookie sta a 99999 e **deve**
  vincere — una barra non puo' coprire la richiesta di consenso.

**I clic si contano da soli, e questo e' il punto che risponde alla domanda
sull'uniformita' di GA4.** `daop-track.js` ricava il nome dell'evento
**dall'href** (`nome_evento()`), quindi la barra manda gli stessi
`click_come_arrivare` / `click_telefono` / `aggiungi_calendario` del corpo,
con gli stessi parametri, senza una riga di codice in piu'. Non nasce un
secondo posto da tenere allineato — e `tests/luoghi.js` prova proprio quello:
ogni href della barra deve esistere identico nel corpo.

**Un guasto preso per strada, che solo una misura nel browser vede.** Il
`<style>` del guscio ha la regola di **elemento**
`nav{position:fixed;top:0;left:0;right:0;z-index:100}` per la barra del sito.
La barra delle azioni era un `<nav>`: si ritrovava `top:0` **e** `bottom:0`
insieme, cioe' **alta 915px, tutto lo schermo**, con l'HTML perfettamente
giusto. Ora e' un `<div role="group">` — sono azioni, non navigazione — e la
prova misura l'altezza renderizzata, non l'HTML. Se un domani nasce un altro
elemento fisso dentro una pagina generata, e' la prima cosa da ricordare.

### Le corsie: una riga che non si vede e che evita di perdere il lettore

`overscroll-behavior-x:contain` su `.ev-rail`, e basta. Su Android, quando una
corsia arriva al suo primo elemento lo scorrimento continua a propagarsi alla
pagina e il gesto diventa il **"torna indietro" del browser**. Con dodici card
e lo snap obbligatorio, tornare all'inizio e' un gesto normale — e chi lo fa
esce dal sito senza aver toccato niente. Il resto della corsia era gia' fatto
bene (`scroll-snap-align:start` sulle card, 1,56 card in vista a 412px, cioe'
la sbirciatina che dice che ce n'e' un'altra): non c'era altro da toccare.

### Quello che invece era gia' a posto, e non va "risistemato"

Verificato nel browser il 28/08/2026 a 412px, perche' torna come proposta ogni
volta che qualcuno guarda il sito sul telefono:

| | stato |
|---|---|
| barra filtri appiccicata allo scorrimento | **gia' cosi'**: `.ev-toolbar` sta a `top:68px` sotto la nav a qualunque profondita', provato fino a 15.000px |
| filtri nella prima schermata | **gia' cosi'**: 676px su un viewport da 915 |
| "Vicino a me" nella prima schermata | **gia' cosi'**: 795px |
| "Cosa c'e' oggi" / "Questo weekend" | **933px, cioe' 18px sotto la piega** |

Quei 18px **non si sono presi**, ed e' una decisione: sopra le scorciatoie non
c'e' spazio morto, ci sono i margini di ritmo fra la barra dei filtri, il
conteggio e le pillole. Toglierli e' cambiare stile per un guadagno che vale
su un solo viewport — su un telefono con la barra dell'indirizzo aperta
(~750px) quelle pillole restano sotto comunque. L'unica correzione vera
sarebbe **riordinare** i blocchi, che e' strutturale. E le due voci sono
comunque sempre raggiungibili dalla nav, che e' fissa.

**Non si mettono nella barra appiccicosa**, ed e' gia' scritto per "vicino a
me": quella e' a ~109px sul telefono e una riga in piu' la farebbe ricrescere
**per tutto lo scorrimento**, cioe' si pagherebbe su ogni schermata quello che
si guadagna su una.

## Le guide stagionali: la prima cosa che ci si porta via

Deciso il 24/08/2026. Fino a qui il sito è un posto dove si **arriva** — da
Google, si legge l'orario della sagra, si esce. Una guida è la prima cosa che si
**porta via**, ed è un rapporto diverso con chi legge.

**Il testo della guida esiste già**: `guida(cfg)` in `genera_centri.py` scrive
"Come scegliere un centro estivo" da mesi — cosa chiedere al telefono, quando ci
si iscrive, cosa mettere nello zaino. Quello che mancava non era la prosa, era
**l'oggetto con una scadenza**. Il pezzo nuovo è quindi solo il pacchetto:
`scripts/genera_pdf.py` e un file in `guide/`.

### La guida NON è una pagina nuova

È la prima cosa che verrebbe in mente e sarebbe la più costosa. Vale parola per
parola quello che è già scritto per i centri: «`centri-estivi.html` è l'hub della
famiglia, non nasce un `/centri.html`; un hub nuovo sarebbe una pagina senza una
query sua, e si metterebbe in mezzo a quella che la vince». Una
`/guida-centri-estivi.html` mangerebbe la query `centri estivi alessandria` alla
pagina che se l'è già presa.

Quindi: **la guida è una sezione dell'hub che c'è già, più un PDF.** Niente URL
nuove nell'indice.

### L'anno: fuori dallo slug di una pagina, DENTRO al nome di un file

È l'unico posto del sito dove la regola di `/ferragosto.html` si ribalta, e il
motivo è che le due cose hanno un mestiere opposto:

| | anno nel nome | perché |
|---|---|---|
| una **pagina** | mai | deve invecchiare: l'anzianità dell'URL è l'asset |
| un **PDF** | sempre | è un'istantanea: senza data mente |

`guide/centri-estivi-2027.pdf`. I vecchi **non si cancellano**: uno per anno, e
un'istantanea datata resta onesta anche quando è vecchia.

**`Disallow: /guide/` in `robots.txt`, il giorno zero.** Un PDF indicizzato
compete con la pagina HTML che stiamo facendo invecchiare, e su GitHub Pages non
si può mandare un `X-Robots-Tag`: `robots.txt` è l'unica leva che c'è. Questo è
il difetto che si scopre sei mesi dopo guardando perché l'hub ha perso posizioni.

### L'insieme è chiuso, e non si fa il prodotto cartesiano

Quattro guide, che sono le quattro pagine che esistono già. **L'insieme non
cresce coi dati** — è la stessa garanzia contro lo *scaled content* delle sei
pagine d'incrocio e delle dodici pagine comune.

La tentazione da rifiutare per iscritto: "Guida centri estivi Alessandria / Asti
/ Cuneo", o per età, o per disciplina. Sono 3 × 4 × N, cioè le 800 pagine su
template identico da cui `luoghi.html` è nata per scappare.

### Il calendario, che è cosa decide tutto il resto

Cercato in rete il 24/08/2026, non dedotto. Le date sono quelle vere del
**calendario scolastico Piemonte 2026-2027**: lezioni dal 14/09/2026 al
10/06/2027, Natale 23/12-6/01, **Carnevale 6-10 febbraio** (cinque giorni),
Pasqua 25-30 marzo, ponte dell'Immacolata 7-8 dicembre.

| guida | la domanda si accende | online entro | cosa la muove |
|---|---|---|---|
| **Corsi e attività** | fine agosto | **~20 agosto** | open day di settembre, "posti limitati" |
| **Centri natalizi** | fine novembre | ~15 novembre | due settimane di chiusura |
| **Centri di Carnevale** | metà gennaio | ~15 gennaio | cinque giorni scoperti |
| **Centri estivi** | fine febbraio | **~1 marzo** | iscrizioni comunali marzo-aprile |
| **Centri pasquali** | inizio marzo | ~1 marzo | sei giorni scoperti |

Due cose che questo calendario dice e che non si ricavano dai dati nostri:

- **La guida deve esistere PRIMA che aprano le iscrizioni, non durante.** A
  Torino le iscrizioni ai centri estivi comunali 2026 sono state 13-30 aprile, a
  Milano 19 marzo-7 aprile: un genitore comincia a cercare **a febbraio**. Una
  guida pubblicata ad aprile arriva a cose fatte. È la scommessa di
  `/halloween.html` — settantadue giorni d'anticipo apposta — applicata a una
  cosa che si vende.
- **Carnevale 2027 vale cinque giorni scoperti e non ha una pagina.** `STAGIONI`
  ha estivi, invernali e pasquali. Il Carnevale è già citato in questo file come
  il caso che dimostra perché il calendario non si scrive nel codice, ma nessuno
  ha poi aggiunto la voce. Cinque giorni feriali a febbraio sono un problema vero
  per due genitori che lavorano, ed è la finestra più scoperta dell'anno.
  Aggiungerla è una voce in `STAGIONI` col suo testo, una volta.

**Aprile-maggio e giugno restano vuoti apposta**: lì la domanda è "cosa faccio
questo weekend", e ha già la pagina che la vince, che è l'agenda.

### Come si genera, e la dipendenza che NON si aggiunge

`scripts/genera_pdf.py`, che gira **dopo** gli altri e non riscrive nessun
contenuto: legge le pagine **già generate** fra i marker
`<!-- GUIDA-PDF:START/END -->`, ci mette intorno il proprio CSS di stampa e
stampa. Il PDF non può divergere da quello che il sito pubblica, perché è
letteralmente quello — è la regola di `_dati_realta()` («i dati si scrivono in un
posto solo») applicata a un secondo formato.

**Niente Playwright, niente libreria PDF.** Chromium sa già stampare da solo:

```
chrome --headless --no-pdf-header-footer --print-to-pdf=… file://…
```

Aggiungere `playwright` come dipendenza del workflow per una cosa che il binario
già installato fa con un argomento sarebbe un costo permanente per un comodo di
un giorno. I `<details>` chiusi si aprono **testualmente** (`<details` →
`<details open`) prima di stampare: niente JS da far girare, niente attesa.

Le decisioni dentro, che non si ricavano dal diff:

- **Senza materiale non nasce nessuna guida.** La condizione è `inizio` in
  `data/centri-stagioni.json`: se la stagione non ha nemmeno una data, il PDF non
  si scrive. È `MIN_LANDING` applicata a un file — con la differenza che una
  pagina vuota resta online e un PDF vuoto no, perché un PDF **gira** e non lo
  puoi correggere dopo.
- **L'anno del PDF è l'anno di `inizio`**, cioè dell'edizione che la pagina sta
  mostrando in questo momento. Non "l'anno prossimo": il PDF è l'istantanea di
  quella pagina, e deve dire la stessa cosa che dice lei.
- **Senza Chromium lascia il PDF di ieri** e lo scrive nel log, come
  `genera_centri.py` lascia la pagina com'è quando non legge il foglio. Un PDF
  vecchio di un giorno è meglio di nessun PDF, e molto meglio di uno vuoto.
- **Le locandine ci sono, ma ridotte e incorporate.** Il 24/08 erano state
  lasciate fuori per paura della banda Supabase; il conto vero è ~24 richieste a
  notte, cioè il 3% del tetto mensile — la paura era mal riposta. Il problema
  vero è un altro, ed è misurato: **Chromium non ridimensiona quando stampa.**
  Le stesse immagini disegnate a 35 mm e a 120 mm danno un PDF identico di 8,4
  MB. Quindi la riduzione va fatta prima (`LOC_LATO` = 480px, che a 300 dpi
  copre una miniatura da 32 mm), e si incorporano come data URI: un PDF che
  punta a un'immagine in rete la riscarica a ogni apertura e mostra un buco a
  chi legge offline, che è metà del motivo per cui uno si scarica una guida.
  **Pillow non è una dipendenza nuova** — il workflow lo installa già per
  `genera_miniature.py` — e se manca, le locandine si saltano e la guida esce
  lo stesso. `LOC_BUDGET` (3 MB) è il tetto che protegge dal foglio con
  duecento righe, non da quello di oggi.
- **Tre trasformazioni di impaginazione, e nessuna tocca la pagina online.** I
  `<details>` si aprono testualmente; la locandina esce dal `<button>` (un
  bottone non lascia che il testo giri intorno a un float al suo interno) e
  quel `<button>` diventa uno `<span>` (una scatola atomica non si spezza, e
  accanto a un float scende sotto). Le due ultime vanno **insieme**: la prima
  da sola sposta il buco invece di toglierlo. Trovate guardando la pagina
  stampata, non leggendo il codice.
- **Il link al PDF si stampa in ritardo di un giro.** `genera_pdf.py` scrive
  `data/guide.json`, `genera_centri.py` lo legge alla run dopo. Stesso ritardo di
  `data/luoghi-comuni.json`, `data/conteggi.json` e `data/centri-stagioni.json`, e
  per la stessa ragione: chiudere il cerchio costa più di quello che risolve, e
  un giorno senza link è un errore gratis. **Se il file manca, il link non si
  stampa** — la regola di `link_luoghi()`.
- **`guide/` va nell'elenco del workflow come cartella e non come file**, per lo
  stesso motivo di `corsi/`: un PDF nuovo nasce untracked e
  `git status --untracked-files=no` non lo vede.

### L'email non si chiede al primo giro, ed è misurato

L'istinto è "il PDF in cambio dell'indirizzo". È la mossa giusta al momento
sbagliato, e il numero che lo dice è già in questo file: l'invito al canale
WhatsApp — **un tocco solo, zero campi da compilare** — converte allo **0,3%**.
Un modulo email chiede di più allo stesso pubblico sulle stesse pagine.

C'è però una differenza vera, ed è l'unica cosa non ancora provata: quello è un
*ask* che non dà niente in cambio, questo dà un oggetto. È esattamente «il pezzo
non ancora provato è il testo, non il canale».

Quindi in due tempi, e il primo non è una mezza misura:

1. **Download libero, misurato.** Evento `scarica_guida` in `daop-track.js` (un
   posto solo, come tutto il resto) col parametro `stagione`, e la dimensione
   registrata in GA4 **prima** di pubblicare — non è retroattiva, e una guida
   scaricata a marzo senza dimensione è un dato perso per sempre.
2. **Il gate email solo se il primo giro mostra domanda.** Costruire una lista
   per un download che nessuno prende è il modo più veloce di buttare via due
   settimane, e lascerebbe in giro una promessa ("ti mando la guida") da
   mantenere a mano.

### Perché questo è il pezzo commerciale che mancava

Nella lista delle cose che mancano per vendere, la numero 2 è «`Premium_al`, la
data di scadenza. Niente si spegne da solo. È un problema di cassa: nessun
innesco per il rinnovo».

**Una guida stagionale è quell'innesco**, e non c'è niente di commerciale da
inventare: «la Guida centri estivi 2027 chiude il 28 febbraio, la tua scheda c'è
dentro?» è una telefonata **con una data**, che è l'unica specie di telefonata
che si fa pagare. Sui corsi non si pone nemmeno il problema: dal 21/08 la
presenza è una sola ed è già pagata, quindi l'inventario della guida esiste già.

E vale la regola di sempre, che qui è più facile da rompere perché un PDF ha una
copertina: **dentro la guida l'ordine non si vende.** Alfabetico come in
`luoghi.html`, e "In evidenza" resta il blocco separato che si dichiara.

### Cosa era bloccato, e non dal codice — **sbloccato il 28/08/2026**

**La guida la cui stagione è aperta adesso è quella dei corsi**, e fino al
27/08/2026 non si faceva: `corsi.html` era `noindex` perché Giovanni considerava
i dati PGS non verificati per la 2026/2027, e stampare in un PDF dei dati che
l'unica persona che li conosce dichiara sbagliati è peggio che non stamparli —
**un PDF gira e non si corregge dopo**, mentre una pagina la riscrive la run di
stanotte.

Il 28/08 Giovanni ha dato l'ok e `CORSI_IN_INDICE` è tornato `True`: **il blocco
editoriale è caduto.** Quello che resta è lavoro, non una decisione — i corsi non
hanno ancora i marker `GUIDA-PDF` in pagina, e `genera_pdf.py` legge solo
`data/centri-stagioni.json`, che è dei centri. Cioè la guida dei corsi ora si
*può* fare e non è ancora fatta: sono due stati diversi e vanno tenuti distinti,
perché il primo si chiude con una telefonata e il secondo con del codice.

Attenzione a una cosa che l'ok di Giovanni **non** ha spostato: la sua finestra.
La tabella qui sopra dà i corsi online entro **~20 agosto**, che è già passato —
la stagione 2026/2027 è cominciata. Una guida dei corsi fatta adesso arriva a
open day in corso, che è l'errore descritto sopra («la guida deve esistere PRIMA
che aprano le iscrizioni, non durante»). Vale come rodaggio dell'impianto, non
come la scommessa: quella è la 2027/2028, e la data da segnare è **~20 agosto
2027**.

L'impianto quindi si costruisce comunque sui **centri estivi**, la cui finestra
apre a gennaio: quattro mesi di margine, che è il lusso che non si è mai avuto.

## Le quattro porte: eventi, luoghi, centri, corsi

Fatto il 20/08/2026. Le quattro famiglie sono **quattro rapporti col tempo**, ed
è il criterio che decide dove va una scheda nuova:

| famiglia | tempo | hub |
|---|---|---|
| **Eventi** | una data | `eventi.html` |
| **Luoghi** | nessuno, è sempre lì | `luoghi.html` |
| **Centri** | una settimana, con iscrizione | `centri-estivi.html` |
| **Corsi** | una stagione, con iscrizione | `corsi.html` |

**Non sono nate pagine nuove**: c'erano già tutte. Mancavano i collegamenti —
la nav aveva due porte, il footer due *diverse*, e `centri-invernali.html`,
`centri-pasquali.html` e `piscine.html` ricevevano **zero** link dal corpo di
qualunque pagina (misurato con `grep`). Stesso guasto già risolto su
`luoghi.html` il 14/08: «alla nav non ci va nessuno».

Le decisioni da non rifare al contrario:

- **`centri-estivi.html` è l'hub della famiglia, non nasce un `/centri.html`.**
  Chi cerca scrive «centri estivi»: un hub nuovo sarebbe una pagina senza una
  query sua, e si metterebbe in mezzo a quella che la vince. Il ponte fra le tre
  stagioni lo fa `sorelle()`.
- **Centri e corsi non si fondono**: due picchi stagionali diversi sulla stessa
  URL si cannibalizzano.
- **`corsi-provincia-*` si spacca quando una provincia arriva a una dozzina di
  corsi**, non prima.
- **La nav sta in sei voci.** A nove era già tagliata sopra i 901px
  (`.nav-links` è una flex row senza `wrap`); con Centri e Corsi sarebbero state
  undici. Il resto è sceso nel footer, dove c'era già. Sul telefono non si è
  tolto niente: le quattro porte davanti, poi `.mm-sep` e sotto tutto il resto.
- **`blocco_ecosistema()` in `genera_eventi.py`** stampa la riga con le altre
  tre famiglie, **col numero e non l'etichetta** (lezione di `link_luoghi()`),
  **in coda al corpo** (regola dell'invito al canale) e **non sulle ~300 schede
  evento**, che in coda hanno già tre blocchi. I conteggi stanno in
  `data/conteggi.json`, dove ogni generatore scrive il suo — in ritardo di un
  giro, come `data/luoghi-comuni.json`. Sotto `MIN_CONTEGGIO` (5) parla la riga
  descrittiva: «1 corso» è una ragione per non toccare.
- **Il CSS di `.eco` e `.mm-sep` sta in `assets/css/daop-system.css`**, non nel
  `<style>` di `eventi.html`: la riga compare anche su pagine che non passano da
  `_guscio()` (corsi, centri, rubriche).
- **Nei centri la copertura è dichiarata** (`ZONA = G.PROVINCE_TESTO`, così una
  provincia nuova allarga i title da sola), **nei corsi è dedotta dai dati**
  (`zona()`). La differenza è voluta: fuori stagione i centri sono zero, e un
  title dedotto oscillerebbe due volte l'anno.
- **Sui corsi la disciplina si scrive**: in riga se la realtà ne mescola più di
  una, altrimenti una volta sola nell'intestazione del gruppo. È la regola già
  scritta per le pagine comune.

### La voce dei centri la scrive il foglio, non il calendario

Fatto il 21/08/2026. Fino a quel giorno la nav diceva **«Centri estivi» tutti i
giorni dell'anno**, su ~360 pagine: anche a novembre, quando quella pagina
risponde «iscrizioni non ancora aperte» e chi cerca vuole il campus di Natale.
Non era solo una parola fuori posto — quella voce e' **anchor text ripetuto su
tutto il sito**.

**Perche' non c'e' un calendario scritto nel codice.** Le finestre si spostano
ogni anno, e non di poco: in Piemonte il Carnevale 2027 vale **cinque giorni**
(6-10 febbraio) mentre il ponte di Ognissanti 2026 **non esiste**, perche' l'1
novembre cade di domenica. Una tabella di mesi qui dentro sbaglierebbe ogni
anno. Il foglio no — e la colonna `stagione` esisteva gia', ed era gia' piu'
forte delle date (`leggi_centri`).

Il patto e' un file: `genera_centri.py` scrive `data/centri-stagioni.json`
(quali stagioni hanno centri, l'etichetta, la data di inizio piu' vicina) e
`genera_eventi.py` lo legge per stampare la voce. **In ritardo di un giro**,
come `data/conteggi.json` e `data/luoghi-comuni.json`, e per la stessa ragione.

Le decisioni dentro, che non si ricavano dal diff:

- **Vince la stagione che sta per cominciare.** Una gia' cominciata ha la data
  nel passato, quindi passa davanti: e' il caso di febbraio, col Carnevale in
  corso e le iscrizioni estive appena aperte.
- **Zero stagioni con centri: la voce non c'e' affatto**, e la nav sta in cinque
  voci. Spariscono anche la riga di rimando in coda all'hero dell'agenda. Non e'
  un buco: chiedere di andare a vedere una pagina che dice «torna in primavera»
  e' peggio di non chiedere niente.
- **Una riga senza nessuna data non vota.** Resta in pagina — togliere una
  scheda perche' il foglio e' incompleto sarebbe peggio — ma non tiene viva una
  stagione. Al 21/08/2026 sono due righe estive senza date («Estate ragazzi
  2026», «Oratorio Aperto Settembre 2026») e da sole avrebbero fatto dire
  «Centri estivi» alla nav anche a novembre, cioe' il difetto che tutto questo
  chiude. Quindi `attivi` in `centri-stagioni.json` (14) e' un numero **diverso**
  da quello che la pagina mostra (16), che sta in `data/conteggi.json`.
- **Lo stato si FONDE, non si sostituisce.** Se il foglio non si legge, di quella
  stagione non sappiamo niente e il valore di ieri resta. Riscrivendo il file da
  zero, **un timeout di Google avrebbe spento una voce di nav su tutto il
  sito**. Se il file manca del tutto la voce non si stampa, come `link_luoghi()`.
- **Footer e riga delle quattro porte restano su `centri-estivi.html`.** Il
  footer e' il catalogo, la nav e' cosa c'e' adesso: cosi' l'hub della famiglia
  — la pagina che vince la query — non perde mai il suo link su tutto il sito.
- **`noindex, follow` e fuori sitemap quando una stagione e' a zero**, ma la
  pagina **resta online**: e' la regola di `MIN_LANDING`. E non e' il «robots che
  cambia ogni notte» di cui si parla per le pagine d'incrocio — `attivi`
  comprende anche i centri **futuri**, quindi zero vuol dire che nel foglio non
  c'e' niente all'orizzonte, e nell'anno gira due volte per stagione.
- **Le dodici pagine con la nav a mano hanno i marker** `NAV-CENTRI`,
  `MM-CENTRI`, `HERO-CENTRI`; `aggiorna_nav()` riscrive **dove trova il
  marker**, quindi non c'e' nessun elenco di pagine da tenere aggiornato. Le
  ~19 generate la ricevono da `_guscio()`, che i marker li **toglie**: se no
  sarebbero tre commenti in piu' su ~360 pagine.
- **`aggiorna_nav()` va chiamata prima di qualunque `_guscio()`**, perche' la nav
  di `eventi.html` e' la sorgente da cui copiano tutte le altre.

Due cose operative, che valgono piu' del codice.

**Nel foglio la colonna `Stagione` oggi NON C'E'.** Verificato il 21/08/2026: le
colonne riconosciute nella tab `Centri Est/Inv` sono quattordici e quella non
c'e', quindi la stagione la deduce il **mese di inizio** (`MESI_STAGIONE`). Il
sito segue il foglio comunque, ma per **decidere a mano** — che era la richiesta
— va aggiunta una colonna chiamata `Stagione` (o `Tipo`, `Tipologia`, `Est/Inv`:
`COLONNE` ne tollera piu' grafie). Le parole riconosciute sono `estiv`,
`estat`, `summer` · `invern`, `natal`, `winter`, `befana` · `pasqu`, `easter`.
Prima era **una sola per stagione** (`estiv`, `invern`, `pasqu`): scrivere
«Natale» faceva sparire la riga in silenzio. Ora una parola sconosciuta —
«carnevale», «settimana bianca» — **urla nel log** invece di finire nel
conteggio «N di altra stagione».

**Una stagione nuova non nasce dal foglio da sola, e non e' pigrizia.** Quello
che tiene in piedi quelle pagine nei mesi vuoti e' la **guida scritta a mano**
(`p_iscrizioni`, `specifico`, `b_giornata`, `b_meteo`: ~50 righe di prosa per
stagione, scritte perche' senza quelle le pagine risultavano identiche al
97,7%). Una riga con `stagione = carnevale` non se la puo' inventare: si
aggiunge una voce a `STAGIONI` col suo testo, una volta, e da quel momento
appare e sparisce da sola col foglio.

Due difetti trovati dalle prove il 21/08/2026, entrambi in pagine che nessuno
guardava. **`genera_rubriche.py` ha un guscio suo**, che legge nav e footer da
`rubriche.html` invece di `eventi.html`: si portava dietro i marker, e le 15
pagine in `rubriche/` sono uscite con tre commenti HTML dentro la nav. La riga
che li toglie sta adesso in tutti e due i gusci — se un domani nasce un terzo
generatore con un guscio suo, e' la cosa da ricordare. E **la prova del
conteggio nella riga delle quattro porte confrontava il numero esatto** con
`data/conteggi.json`: era rossa ogni volta che un conteggio cambiava, perche'
dentro la stessa run `genera_eventi` gira prima di `genera_luoghi` (830 nel
registro, 825 in pagina, e avevano ragione entrambi). Ora controlla che ci sia
**un numero**, e il disallineamento lo stampa come nota.

**Bug trovato per strada, e non piccolo:** il filtro province di
`genera_centri.py` era la lista scritta a mano `('AL', 'AT')` ed era rimasta
ferma all'apertura di Cuneo (04/08/2026). I titoli di quelle pagine dicevano
gia' «Alessandria, Asti e Cuneo» — `ZONA` e' derivata da `PROVINCE_PUBBLICATE` —
mentre **un centro a Cuneo veniva buttato via senza un avviso da nessuna
parte**. Ora la lista e' una sola, la stessa dell'agenda.

`tests/porte.js` difende tutto questo. Su Windows le prove ora caricano davvero
il JavaScript delle pagine: `_aiuto.js` non toglieva il `/C:` dal percorso e
metà degli script andava in 404, con le prove verdi.

```bash
cd tests && CHROMIUM_PATH="C:/Program Files/Google/Chrome/Application/chrome.exe" npm test
```

### I corsi: la presenza si paga, e l'elenco è dei corsi non delle società

Rifatto il 21/08/2026 sul documento di feedback di Giovanni (Cuneo). Sono tre
decisioni, e la prima è quella che regge le altre due.

**Non esiste più una scheda gratis e una a pagamento.** C'erano due livelli —
riga in elenco per tutti, `Premium = si` per descrizione lunga, locandina e
pillola «★ Scheda completa». Giovanni ha fatto notare il difetto: dando tanto
nella versione gratuita non si fa percepire il valore di quella a pagamento, e
si finisce a vendere una differenza che il lettore non vede. Quindi **una
presenza sola, uguale per tutti, e si paga**. In pagina vuol dire: niente
pillola, `descr_premium` vince se c'è (non più se il flag c'è), locandina a
tutti, e `rel="sponsored"` su **tutti** i link in uscita — non c'è più una metà
«nostra segnalazione» da distinguere con `nofollow`.

Ne segue l'invito in coda: **non dice più «la scheda è gratuita»**. Non dice
nemmeno un prezzo — si tratta caso per caso — e dice invece *cosa comprende*,
che è quello che una società deve sapere prima di scrivere. E dice **a chi**
scrivere: `collabora@eventiperbambinicuneo.it` per Cuneo, `info@daop.it` per
Alessandria e Asti (`MAIL_PROV` in `genera_corsi.py`). La riga si compone dai
dati, non da un testo fisso: finché i corsi sono tutti di Cuneo si legge un
indirizzo solo, e il secondo compare da sé con la prima società di Alessandria.
Un testo scritto a mano con due indirizzi direbbe oggi una cosa non vera.

**L'elenco non è più raggruppato per società.** Ogni realtà aveva il suo `<h2>`
coi suoi corsi sotto: si leggeva bene e obbligava a scegliere prima la società e
poi il corso, che è l'ordine inverso a quello in cui ragiona un genitore
(«in questa pagina mi interessa che compaiano i corsi e io genitore possa
sceglierli avendo visione di tutti»). Coi filtri in cima era anche il modo più
sicuro di renderli inutili: filtrando «Musica» restavano intestazioni sparse
sopra il vuoto. Ora è un elenco piatto ordinato per **disciplina → età →
comune**: due corsi di pallavolo di due società diverse stanno vicini, che è
quello che serve a chi confronta.

**Le società non spariscono, scendono.** In fondo c'è una scheda per ognuna —
`#r-pgs-roccavione`, il link che si manda su WhatsApp, **la stessa ancora di
prima**, quindi nessun link già in giro si rompe — e da ogni corso ci si arriva
dalla riga «Organizzatore» del dettaglio. Un filtro che spegne tutti i corsi di
una società spegne anche la sua scheda: se no la sezione in fondo smentirebbe il
filtro appena usato.

**La riga chiusa porta tre dati, e sono i tre dei filtri**: disciplina, età,
comune. Quello che *non* ci sta è altrettanto deciso, ed è la parte che qualcuno
rimetterebbe pensando di aggiungere informazione — **i giorni e gli orari** (il
dato più lungo e più fragile, e serve a chi ha già scelto: sta nel dettaglio) e
**il nome della società** (qui si sceglie un corso). La disciplina invece si
scrive **sempre**, e ribalta la regola scritta per le pagine comune: lì
ripeterla dentro una manifestazione uniforme è rumore, qui la riga sopra può
essere un corso di musica.

**Via «Iscrizioni aperte/chiuse».** È un dato che scade in silenzio e che nessuno
viene ad aggiornare: alla pallavolo si entra quasi sempre, a un corso di teatro
quasi mai, e la risposta vera ce l'ha la società — che ha il suo numero due
righe sotto. Una riga che dice «Aperte» a gennaio è peggio di nessuna riga.

I **referenti restano nomi senza numeri**, e qui il feedback chiedeva il
contrario («molti mettono il whatsapp, è bello sapere con chi parli»). Non è
stato fatto: sulla locandina di partenza erano cinque cellulari di volontarie e,
a confronto con la stagione prima, erano cambiati quasi tutti — un numero
personale dentro un archivio consultabile non è la stessa cosa dello stesso
numero stampato su un manifesto. `tests/corsi.js` lo difende da sempre. **È un
punto aperto**, non chiuso: se si decide di pubblicarli, va cambiata anche
quella prova.

#### La tab `Realta` non esiste ancora, e la scheda funziona lo stesso

La scheda della società vuole logo, descrizione, indirizzo, sito, contatti. Nella
tab `Attivita` **non c'è niente di tutto questo** (verificato il 21/08: 24
colonne, nessuna a livello organizzatore — e mancano anche `Sito`, `OpenDay` e
`Descrizione PREMIUM`, che il generatore legge già e il foglio non ha). Non ci
deve nemmeno stare: sarebbero lo stesso logo e la stessa descrizione ricopiati su
cinque righe, cioè il modo più sicuro di farli divergere.

Quindi `leggi_realta()` cerca una tab **`Realta`** e, se non la trova, **ricava
la scheda dai corsi** (comuni, discipline, sede, sito, contatto): meno ricca, mai
vuota, mai rotta. È la regola di `link_luoghi()` — quello che manca non si
stampa, non si inventa. Le colonne da creare sono `Organizzatore`, `Descrizione`,
`Logo`, `Comune`, `Indirizzo`, `Sito`, `Telefono`, `Email`, e
`REALTA_DEMO` in `prova_corsi.py` fa vedere com'è la scheda quando ci sono.

**Il terzo airbag contro gviz.** Una tab che non esiste non dà errore: gviz
risponde col **primo foglio del documento**, che è Luoghi — è il guasto del
20/08 che ha pubblicato 895 agriturismi al posto di 5 corsi. Qui le difese sono
tre: `headers=1`, una colonna che si chiami `Organizzatore` (Luoghi ha `Nome`,
`Descrizione`, `Indirizzo`, `Città`, `Website`, `Telefono`, `Email` — ma non
quella), e soprattutto **una riga che non corrisponde a una società già in
pagina viene buttata via**. Con l'ultima, un foglio sbagliato non entra comunque.

#### `CORSI_IN_INDICE`: spento il 21/08/2026, **riacceso il 28/08**

`corsi.html` è **in indice dal 28/08/2026**. Era fuori dal 21/08 perché Giovanni
considerava i dati PGS non verificati per la 2026/2027, e una pagina indicizzata
fatta di dati che l'unica persona che li conosce dichiara sbagliati è un doppione
debole sul dominio che regge `eventi.html`. Il 28/08 ha dato l'ok: i dati sono
verificati, e l'interruttore è tornato a `True`.

L'interruttore è **uno solo**, `CORSI_IN_INDICE` in `genera_eventi.py`, e governa
quattro cose insieme: `robots`, la sitemap, la nav (marker `NAV-CORSI` /
`MM-CORSI`, stesso meccanismo della stagione dei centri) e la riga delle quattro
porte. **Il footer tiene il link in tutti e due gli stati**, come per i centri:
il footer è il catalogo, la nav è cosa c'è adesso — ed è per questo che nella
settimana di `noindex` il footer è rimasto l'**unica** via d'accesso alla pagina.

**Girarlo è un comando solo, ma i file li riscrivono i generatori**, e sono due —
`genera_eventi.py` per la nav e la riga delle porte su ~470 pagine,
`genera_corsi.py` per il `robots`, l'avviso e la sitemap di `corsi.html`. Girato
l'interruttore senza farli girare tutti e due, il sito resta a metà: è
esattamente lo stato che `tests/porte.js` è scritto per far diventare rosso.

**Con lo spento la pagina restava online**, ed è la regola di `MIN_LANDING` già
scritta per le stagionali: i link girati devono continuare a funzionare, e
l'anzianità dell'URL è l'unico asset che una pagina nuova non può comprare.
Stampava anche un avviso **visibile** ("Sezione in preparazione"), non solo il
meta: chi ci arrivava da un link doveva sapere che l'elenco non era finito,
invece di dedurlo dal fatto che c'era una società sola. Acceso, quell'avviso
sparisce da sé — resta in pagina solo la sua regola CSS, che è inerte.

**Si gira a mano**, e non c'è una soglia automatica apposta: il problema non è
quanti corsi ci sono, è che quelli che ci sono vanno confermati da chi li
organizza — e un numero non sa rispondere a quella domanda. Vale in tutti e due i
versi: se un domani i dati tornassero incerti, si rimette `False` e si rifanno
girare i due generatori.

**Quello che l'interruttore NON governa, ed è la confusione facile:** la cella
`Stato` di ogni realtà resta padrona della **sua** pagina. Al 28/08 su tre realtà
una sola è confermata (`carezza`), quindi `crome-in-movimento-aps` e
`pgs-roccavione` sono rimaste `noindex` anche dopo l'accensione, e va bene così.
Sono due decisioni deliberatamente indipendenti — una sulla sezione, una sulla
singola società — ed è la stessa distinzione che il 28/08 aveva già fatto
diventare rossa una prova invecchiata (vedi "L'età si legge con la sua unità").

`tests/porte.js` legge lo stato **da `corsi.html`**, non dal generatore: così
quello che prova è che il sito sia d'accordo con se stesso, e un interruttore
girato a metà (noindex ma ancora in nav) diventa rosso. Le porte diventano tre o
quattro di conseguenza — è lo stesso adattamento già fatto per la stagione dei
centri, e per la stessa ragione: una prova che ne pretende quattro sarebbe rossa
proprio quando il sito fa la cosa giusta.

**Il guscio di `genera_rubriche.py` ha ripreso lo stesso difetto sul secondo
marker**: toglieva solo `*-CENTRI`, quindi le 15 pagine in `rubriche/` sono uscite
coi commenti `NAV-CORSI` dentro la nav. È il difetto già trovato il 21/08 sui
centri, ripetuto identico — la riga che li toglie sta in tutti e due i gusci, e
se nasce un terzo generatore con un guscio suo è quella da ricordare.

#### `CORSI_ZONA_ATTESA`: non congela il titolo, lo fa gridare

Fatto il 31/08/2026. `zona()` ricava la copertura **dai dati**, e fa bene: oggi
i corsi sono di una provincia sola, e un H1 che ne promettesse tre sarebbe
falso. Ma quella stessa bontà ha un lato pericoloso, ed è di struttura, non di
testo: **al primo corso di Asti, title e H1 di `corsi.html` diventano da soli
"nelle province di Asti e Cuneo"**, e in quel momento va presa una decisione di
architettura — se spaccare in `/corsi-provincia-<p>.html`, come già fanno sagre,
oggi e weekend. Quella decisione verrebbe **scavalcata da una run notturna**,
in silenzio.

La cosa che viene in mente per prima — congelare il titolo con una costante,
come `CORSI_IN_INDICE` — **è da non fare**, ed è utile che sia scritto perché
sembra la mossa ovvia. Congelato, `corsi.html` direbbe "in provincia di Cuneo"
con dentro un corso di Asti: cioè esattamente la bugia che `zona()` esiste per
evitare, e per giunta su una pagina che chi arriva da Google smonta in due
secondi.

Quindi `CORSI_ZONA_ATTESA = ('CN',)` **non cambia una virgola di quello che
esce.** Serve a una cosa sola: `_controlla_zona()` confronta le province viste
nei dati con quelle attese e, se sono cambiate, stampa un avviso che dice
*anche cosa fare*. La pagina resta sempre vera, e il cambiamento smette di
essere silenzioso.

```
[genera_corsi] ATTENZIONE: corsi in province non attese (Asti). title e H1 di
corsi.html si allargano da soli, e questo e' il momento di decidere se serve
una pagina /corsi-provincia-<p>.html per provincia. Deciso questo, aggiorna
CORSI_ZONA_ATTESA.
```

**Quando suona, si aggiorna la riga DOPO aver deciso**, non prima. Aggiornarla
per far tacere il log è l'unico modo di usarla male — ed è la stessa disciplina
di `REALTA_NASCOSTE`, che si riempie per un giorno e si svuota.

**Perché la forma consigliata è `/corsi-provincia-<nome>.html`** e non
`/corsi-bambini-cuneo.html` né `/cuneo/corsi-bambini/`, il giorno che servirà:
è la grammatica che le altre tre famiglie provinciali usano già, quindi non se
ne inventa una quarta; `cuneo` senza `provincia` è ambiguo, e
`/eventi/comune/cuneo.html` — il capoluogo — **esiste già**; e una cartella per
provincia introdurrebbe una gerarchia territoriale che nessun'altra parte del
sito usa, cioè due tassonomie in concorrenza su un sito dove il 301 non esiste.
`/corsi.html` **non si sposta**: ha 514 link entranti e vince la query generica,
e diventa l'indice delle province come `/eventi/oggi.html` è diventato l'indice
delle sue tre.

**Non si fa quando i corsi sono tanti, si fa quando sono di più province.** Al
31/08/2026 sono 12 in due comuni, tutti cuneesi: tre pagine provinciali adesso
vorrebbe dire farne nascere due vuote.

#### Tre stati e non due: "non confermata" non è "in bozza"

Fatto il 28/08/2026 per la PGS Roccavione, che andava tolta dalla pagina senza
perderne i dati. Prima la cella `Stato` sapeva dire una cosa sola — sì o non
ancora — e l'unico modo di far sparire una società era **cancellarne le righe
dal foglio**, cioè buttare via il lavoro fatto per doverlo riscrivere a mano il
giorno che quella società dice di sì.

Adesso la stessa cella copre tre esiti, e la scala è la cosa da non appiattire:

| `Stato` | cosa succede |
|---|---|
| `confermata`, `pubblicata`, `fatturata` | in pagina, in Google, in sitemap |
| vuoto, o `inviata`/`in attesa`/`contattata` | **in pagina, ma `noindex`**: chi ha il link la vede, Google no |
| **`bozza`**, `sospesa`, `nascosta`, `ritirata` | **non si vede affatto** |
| riga cancellata dal foglio | come sopra, ma i dati non ci sono più |

**Il gradino di mezzo non è un ritiro, ed è tutta la ragione del terzo
insieme.** Il silenzio vale "non ancora confermata" — la regola dei luoghi,
«senza un sì umano non si genera niente» — e una pagina online e `noindex` è la
cosa giusta mentre una trattativa è aperta: il link si può mandare alla
società perché guardi la propria scheda. `bozza` è un'altra affermazione, ed è
attiva: *questi dati non si pubblicano*.

Con `bozza` spariscono insieme, e da un taglio solo (`togli_nascoste()`, sui
corsi, prima di tutto il resto): le righe dall'elenco, la scheda in fondo a
`corsi.html`, la pagina in `corsi/` — che `scrivi_realta()` **cancella** da sé,
non trovandola più fra le vive — la voce in `data/realta-pagine.json`, e di
conseguenza la riga «Organizzatore: I corsi di …" sulle schede evento, al giro
dopo. Tagliare nei quattro posti che usano i corsi vorrebbe dire quattro
occasioni di divergere, e la peggiore sarebbe la più silenziosa: una pagina in
`corsi/` rimasta online per una società uscita dalla guida.

**`REALTA_NASCOSTE` sta vuota apposta.** È la leva d'emergenza per il giorno in
cui una società va tolta subito e il foglio non è raggiungibile; è sempre il
secondo posto in cui vive un fatto che ne ha già uno, quindi si riempie per un
giorno e si svuota. Il 28/08 c'è finita dentro `pgs-roccavione` per mezz'ora,
prima di accorgersi che **nel foglio la cella diceva già `bozza`**: la lista non
serviva, bastava far girare il generatore. È il caso tipico — la si riempie
credendo che il foglio non sappia, e il foglio sa. Se le due porte divergono
(la lista dice "fuori", il foglio dice "confermata") `nascosta()` lo urla nel
log, invece di lasciarlo scoprire fra sei mesi a chi si chiede perché una
società che ha pagato non compare da nessuna parte.

**Il registro degli stati si stampa a ogni run, anche quando non nasconde
niente**, ed è il pezzo che rende la cosa governabile da chi non tocca il
codice: la cella la scrive Giovanni a Cuneo, la pagina la fa una run notturna,
e in mezzo non c'era nessuna conferma che le due cose si fossero parlate.

```
[genera_corsi]   CàRezza: Stato 'pubblicata' -> in pagina, in Google
[genera_corsi]   Crome in Movimento APS: Stato 'inviata' -> in pagina, ma noindex
[genera_corsi]   PGS Roccavione: Stato 'bozza' -> fuori dalla pagina (5 corsi)
```

**`STATI_ATTESA` esiste per una ragione sola: perché il log non gridi al
refuso.** Una parola non riconosciuta vale "non confermata" — ripiego prudente,
ma non è quello che ha in testa chi l'ha scritta: chi digita `bozz` o `sospesq`
lascia la società online e non se ne accorge. Quindi le parole ignote si
stampano. Ma `inviata` è un gradino vero della trattativa, scritto giusto, e
senza quel terzo insieme finirebbe fra i refusi **tutte le notti**: un avviso
che suona sempre smette di essere un avviso.

E la cella si legge in **un posto solo** (`_stato_e()`): confronto sul primo
pezzo *e* sulla cella intera, perché chi scrive a mano aggiunge le date
(`confermata 26/08`) ma esistono anche stati di due parole (`in attesa`), dove
il primo pezzo da solo direbbe `in`. Tre parsing della stessa cella
divergerebbero al primo ritocco.

##### La stessa parola voleva dire due cose opposte nei due repo

Trovato la sera stessa, andando a verificare l'unico dubbio rimasto aperto
(«`avanza_stati_realta` non è in questo repo, va controllato che non sovrascriva
un `bozza`»). Quella funzione è a posto — muove solo le righe il cui primo pezzo
sta in `STATI_REALTA_CONFERMATI`, e `bozza` non c'è. Ma nel downloader c'era
questo:

```python
STATO_REALTA_NUOVA = "bozza"      # daop_pipeline.py, riga 632
#   bozza   la scrive il programma quando nasce la scheda.
#           Pagina online ma fuori da Google.
```

**`bozza` era il default di ogni scheda appena compilata**, e il commento
accanto gli dava esattamente il significato che qui ha il *vuoto*. Due decisioni
prese in due repo diversi si erano incontrate sulla stessa parola con i due
significati opposti: «appena nata, mostrala fuori da Google» contro «toglila
dalla pagina».

Chi ci sarebbe cascato è Giovanni, **proprio facendo il lavoro giusto**: compila
la scheda di una società, il downloader scrive `bozza`, e la notte dopo i corsi
di quella società escono dall'elenco. Nessun errore da nessuna parte, e il
gradino successivo — mandare alla società il link della sua pagina perché la
controlli — chiede un link che non esiste più. Il meccanismo si rompeva al primo
passo, e a romperlo era l'aver fatto il lavoro. Non era ancora scattato solo
perché le due schede compilate finora erano già state mosse oltre il default.

Il default è diventato **`da inviare`** — che questo repo riconosce già in
`STATI_ATTESA`, quindi stesso effetto del vuoto e nessun avviso di refuso nel log
notturno. È anche più onesto: dice a che punto è la trattativa, non com'è fatto
il file. Ora `bozza` è **solo** la leva che nasconde.

Nel downloader sono cambiate altre due cose, e sono la stessa idea da due lati:
la domanda «te l'hanno confermata?» **non si fa più** per una società
parcheggiata (`STATI_REALTA_NASCOSTI`, copia di `STATI_BOZZA`), e se un verdetto
arriva comunque in ritardo — la cassetta è asincrona, un file depositato ieri non
sa cosa è stato deciso stanotte — `applica_conferme()` lo rifiuta e lo dice. Il
motivo è che quel sì/no è **sui dati**, ma finiva scritto nella stessa cella che
tiene nascosta la società: rispondendo di sì, Giovanni l'avrebbe rimessa online
senza sapere di averlo fatto. Misurato sul foglio vero prima della correzione:

```
PRIMA (cosa sarebbe partito stanotte):   cuneo  PGS Roccavione      stato='bozza'
                                         cuneo  Crome in Movimento  stato='inviata'
DOPO:                                    cuneo  Crome in Movimento  stato='inviata'
```

La prova sta in `prova_schede_realta.py` (punto 7) e legge **questo** file
sorgente: verifica che il default del downloader non sia una parola che qui
nasconde, che sia una che qui si riconosce, e che i due elenchi di parole-che-
nascondono siano identici. È la stessa forma del punto 6 (le colonne), con una
differenza: lì due liste divergono e un dato non arriva in pagina, qui due liste
si **sovrappongono** e la stessa parola vuol dire due cose opposte. Verificata
rossa sul valore di ieri prima di scriverla.

**Nessuna prova nomina la PGS**, e non è una dimenticanza: sarebbe rossa il
giorno che quella società conferma, cioè quando il sito fa la cosa giusta — la
quinta volta che quel tipo di prova si sarebbe rotta da sé. Quello che difende
il meccanismo è l'invariante che c'era già: *nessuna scheda evento rimanda a una
pagina realtà che non esiste*.

#### L'età si legge con la sua unità, e il robots di una realtà non è quello dell'hub

Due prove rosse trovate il 28/08/2026 facendo girare la suite. Nessuna delle due
era un falso allarme e nessuna delle due era dov'era il sintomo.

**Il primo era un difetto vero, e sarebbe ricomparso.** Il corso «Accarezzami —
massaggio infantile» ha età `0-12 mesi`: `eta_da_testo()` leggeva due numeri e
basta, quindi il filtro lo metteva nella fascia **0-12 anni** e il massaggio ai
lattanti compariva a chi cerca per un dodicenne. La riga in pagina diceva «mesi»,
il filtro contava anni — cioè le due cose che questa pagina non può permettersi
di far divergere. Ora `_eta_numeri()` legge **l'unità scritta dopo il numero**, e
chi non ce l'ha eredita quella del primo che la porta: in `0-12 mesi` è il 12 a
dirlo e lo zero lo eredita, in `da 6 mesi a 3 anni` ognuno ha la sua. I mesi si
troncano all'anno (12 mesi = 1 anno, 6 mesi = 0): una fascia d'età non è un
compleanno, e un corso per lattanti sta nell'anno zero. **La riga continua a
stampare quello che dice la locandina** (`0-12 mesi`), che è l'unica cosa vera da
scrivere lì — è `eta_testo()` e non si tocca. Oggi è un corso su diciassette, ma
baby yoga, pre-parto e nido si scrivono tutti in mesi.

`eta_range()` non è toccata, ed è la ragione per cui il gemello `_attivitaEtaRange`
in `app.js` (repo `daop-mobile`) non va allineato: l'unità vive nel **ripiego**
scritto a parole, che di là non c'è ancora.

**Il secondo era una prova invecchiata.** `tests/corsi.js` pretendeva che una
pagina realtà avesse lo **stesso robots dell'hub** — regola giusta fino al
26/08/2026, quando `confermata()` ha reso quella decisione della singola società
(la cella `Stato`) e ha lasciato `CORSI_IN_INDICE` padrone del solo `corsi.html`.
Sono due decisioni deliberatamente indipendenti, una sulla sezione e una sulla
realtà: la prova diventava rossa **alla prima società che confermava**, cioè
esattamente quando il sito faceva la cosa giusta. È la terza volta che capita
(la copertura delle coordinate, il conteggio delle quattro porte), e la forma è
sempre la stessa: *una prova che pretende un'uniformità che il sito ha smesso di
volere*. Ora controlla l'invariante che `aggiorna_sitemap()` dichiara di sé —
**nessuna URL in sitemap con `noindex`** — che regge in tutti e due i versi.

**E da qui è uscito il terzo pezzo, che era mezzo passo mancante.**
`corsi/carezza.html` era `index, follow` perché la società ha confermato, e
stava **fuori dalla sitemap**: il blocco `CORSI:*` si spegneva tutto insieme con
`CORSI_IN_INDICE`, quindi la sola regola della sezione teneva fuori proprio le
pagine confermate, cioè quelle pagate.

Non era una contraddizione — restavano raggiungibili dall'hub, che è `noindex,
**follow**` e quindi i link li fa seguire lo stesso. Ma **un `noindex` di lunga
durata Google finisce per trattarlo come un `nofollow`**, e il giro promesso
(«confermano → indicizziamo → fatturiamo») si sarebbe spento da solo dopo
qualche mese, senza un errore da nessuna parte: il difetto che si scopre a marzo
guardando perché una pagina venduta non ha mai preso un'impressione.

Ora nel blocco l'hub entra se `CORSI_IN_INDICE`, ogni realtà entra se la **sua**
cella `Stato` dice confermata, e se non ci finisce dentro niente il blocco si
toglie. **Il blocco resta uno**: due marker in `sitemap.xml` da tenere allineati
per una distinzione che qui è una riga di codice sarebbero un costo permanente.

**Accendere `CORSI_IN_INDICE` non era l'alternativa**, ed è bene resti scritto
anche adesso che è acceso: quel giorno era spento per una ragione editoriale, e
un interruttore non si gira per far comparire una URL in una sitemap. Che il
28/08 sia poi stato acceso *per la sua ragione* — Giovanni ha verificato i dati —
non riabilita l'altra: il difetto della sitemap andava chiuso lo stesso, ed è
stato chiuso prima e indipendentemente.

L'invariante ora vale **in tutti e due i versi** — in sitemap niente `noindex`, e
niente `index` fuori dalla sitemap — e `tests/corsi.js` la controlla così. Era il
verso nuovo, quello che mancava: la vecchia prova guardava solo che non entrasse
un `noindex`, e una pagina pagata che nessuno annuncia le passava sotto il naso.

#### Restituire i numeri a ogni realtà: l'attribuzione è nel DOM

Fatto il 21/08/2026, chiesto da Giovanni in vista del lancio: poter dire a una
società *scheda aperta → clic al sito → telefono → email → social* senza
ricostruire ogni volta l'organizzatore da `destination_url`.

Il legame **non è un elenco da tenere allineato**: è un attributo. Il
generatore stampa `data-org` (lo slug, cioè la stessa ancora `#r-pgs-roccavione`
che si manda su WhatsApp), `data-org-nome` e `data-codice` sulla card del corso
e sulla scheda della realtà; `contesto_riga()` in `daop-track.js` risale
l'albero con `closest()` e aggiunge quattro parametri a **ogni** evento di clic:
`organizer_id`, `organizer_name`, `course_id`, `course_name`.

La conseguenza voluta è anche il contrario: **un link che non sta dentro una di
quelle scatole non prende l'attribuzione di nessuno** — l'invito alle società in
coda, il footer. `tests/corsi.js` prova tutte e due le direzioni, con uno stub al
posto di `gtag`.

Le decisioni, che è quello che non si ricava dal diff:

- **`organizer_id` è lo slug e non deve mai cambiare.** È già l'ancora che gira
  nei messaggi, quindi cambiarlo rompe due cose insieme; in GA4 un id nuovo vuol
  dire una serie storica che riparte da zero. Per lo stesso motivo `course_id` è
  il **CODICE del foglio** quando c'è, e ripiega sull'id-slug: un corso che si
  rinomina da "Volley Under 8 M/F" a "Volley U8" non perde il suo storico.
- **`organizer_name` sta in un attributo, non si deduce dal DOM.** In riga il
  nome della società non c'è (decisione del 21/08: qui si sceglie un corso), e
  ricostruirlo dallo slug darebbe "pgs-roccavione" dentro un report che deve
  leggere una persona.
- **`apri_corso` è il denominatore, ed è il pezzo che mancava davvero.**
  `corsi.html` è **una pagina sola**: il suo `page_view` dice "qualcuno ha aperto
  l'elenco", non "qualcuno ha guardato i corsi della PGS Roccavione". Senza,
  a una realtà si potrebbe dire "3 clic al tuo sito" ma non *su quante volte* —
  che è lo stesso identico buco già elencato come lavoro mancante per
  `luoghi.html`, con la differenza che qui c'era già un gesto deliberato da
  contare (il `<details>` della riga). Si conta solo l'**apertura**: al momento
  del capture `aria-expanded` ha ancora il valore vecchio, quindi `"false"`
  vuol dire che sta aprendo, e richiudere non è un secondo interessamento.
- **Il selettore chiede `data-org`**, che oggi stampa il solo `genera_corsi.py`.
  Le ~300 schede evento hanno le stesse `.ev-row`: contarle qui vorrebbe dire
  moltiplicare gli eventi su tutto il sito per una domanda che lì nessuno ha
  fatto — e dare benzina agli avvisi "anomalia".

**Due tappe del percorso erano rotte a monte, e non era un problema di GA4.** Il
telefono era stampato come **testo**: un numero non cliccabile non produce un
clic, quindi quella colonna sarebbe restata vuota per sempre (ora passa da
`G.contatti_html()`, la stessa delle schede evento — e si chiama, che su un
telefono è il punto). I **social** non avevano proprio una colonna: ora
`COLONNE_REALTA` ha `instagram` e `facebook`, due colonne separate perché una
"Social" sola diventa `"ig: @tizio, fb: pagina"`, cioè un testo da cui non si
ricava un link. `daop-track.js` riconosce già quei due domini da sé.

**Quello che si restituisce a una realtà è una sottostima, e va detto a loro.**
Vale la copertura di ~38% contro Search Console: quello che GA4 vede è circa un
terzo. Un report che dice "47" senza dire "almeno" è una promessa che il primo
cliente sveglio smonta. E attenzione alle **soglie sui dati** di GA4: con Google
Signals attivo le righe con pochi utenti spariscono, cioè proprio il caso della
società piccola con dodici clic al mese — è la prima cosa da verificare quando
un report esce vuoto.

**Le quattro dimensioni vanno registrate in GA4 prima del lancio**, e non è una
formalità: non sono retroattive. Vedi "Le dimensioni personalizzate" più sopra.

#### Il breadcrumb invisibile, e perché il sintomo era il colore sbagliato

Trovato il 28/08/2026 guardando la pagina, non il codice. Sull'hero scuro di
`corsi.html` la riga `Home › Corsi per bambini` era **testo `rgb(26,45,58)` sopra
un gradiente che parte da `rgb(30,51,66)`: contrasto 1,07:1.** Non "poco
leggibile" — lo stesso colore dello sfondo.

**Il sintomo mentiva, ed è la parte da ricordare.** A occhio "Home" sembrava un
link blu slavato, quindi la diagnosi naturale è "il colore del link è sbagliato".
Non era il colore del link, era che *tutto* il crumb non ne aveva uno. `.page-hero`
veste `h1`, `p`, `.section-label` e `a` — cioè nessuno dei due elementi che ci
sono lì dentro. Il crumb è un `<div>`, quindi ereditava il colore del `body`.

E la regola che avrebbe dovuto salvare almeno il link lo affondava:

| | specificità | |
|---|---|---|
| `.page-hero a{color:var(--gold)}` | 0,1,1 | arriva prima |
| `.co-crumb a{color:inherit}` | 0,1,1 | **arriva dopo, quindi vince** |

`color:inherit` riportava il link nel buio lasciandogli solo la sottolineatura —
da cui l'aspetto di link blu, che era il dettaglio da non inseguire.

**I valori non sono nuovi**, e non andavano inventati: `.ev-hero` risolve lo
stesso inciampo sulle schede evento da sempre — `.62` la traccia, `.82` il link,
`opacity` rimessa a `1` perché l'alfa ora sta nel colore. Il crumb dei corsi non
aveva mai ricevuto quel trattamento. Resi: **6,02:1** e **9,31:1**, contro il
4,5:1 di WCAG AA. Le regole sono *scoped* su `.page-hero`, così la regola base
continua a valere se un domani il crumb finisce su fondo chiaro.

**Sono due classi, e vanno sistemate tutte e due**: `.co-crumb` (l'hub) e
`.cr-crumb` (le pagine realtà), che è nata copiando la prima e ne ha ereditato il
difetto. Controllarne una sola sarebbe come non controllarne nessuna.

**La prova misura il reso, non legge il CSS** (`tests/corsi.js`): prende il
colore calcolato, moltiplica l'alfa per ogni `opacity` da lì all'hero — che è il
modo in cui un difetto così si nasconde, colore chiaro ma padre trasparente — e
lo fonde con la **prima** tappa del gradiente, che è la più scura, cioè il caso
peggiore. Pretende `AA` e in più che il link stacchi dalla traccia: un link che
ha lo stesso contrasto del testo intorno è testo che sembra testo. Rimettendo il
difetto la prova torna rossa dicendo `1,07:1`, cioè la cifra esatta misurata a
mano — verificato, non supposto.

È lo stesso genere di guasto della barra delle azioni alta 915px: **HTML
corretto, CSS che a leggerlo sembra a posto, e nessuna prova che se ne accorge.**
Quando una cosa "si vede male", la misura sta nel browser.

#### Il testo non promette quello che il foglio non garantisce

Terza tornata di feedback, 21/08/2026. L'hero diceva «Le attività che durano
tutto l'anno — sport, musica, danza, lingue — con le età, i giorni, i costi e le
prove gratuite di settembre», e l'intro «comincia a settembre e finisce a
primavera… che età prende, che giorni». Due problemi, e sono lo stesso problema:

- **«i giorni e i costi» sono colonne facoltative.** Prometterli in cima
  obbliga a compilarle su ogni riga, e la riga che non le ha smentisce la
  pagina. Giovanni: «ci impegna anche a scrivere giorni e costi che io continuo
  a insistere di tenere facoltativi».
- **«dura tutto l'anno» non è vero per tutti**: ci sono corsi da uno o due mesi
  e percorsi di poche lezioni.

Ora l'hero promette solo quello che il generatore **calcola o ha sempre**: la
disciplina, l'età (che si ricava da annate + stagione, non si copia), il comune,
e la prova «dove c'è». E l'intro dice come si sceglie — «per disciplina, per età
del bambino e per comune» — che sono i tre filtri veri, invece di elencare dati
che potrebbero mancare. È la stessa regola già scritta per l'agenda: una pagina
non annuncia un dato che la riga sotto può non avere.

#### L'open day è un evento, la prova è un attributo

La scheda aperta mostrava **due calendari per la stessa cosa**: la riga «Open
day» prendeva le date dalla tab Eventi, e subito sotto un paragrafo «Prova»
mostrava le date scritte a mano dentro la colonna `Prova` del foglio («Gratuita ·
open day 10, 17 e 24 settembre»). Giovanni l'ha chiamato «un po' di casino con le
date», ed era esatto.

La divisione, da tenere:

| | cos'è | dove vive | cosa mostra |
|---|---|---|---|
| **Open day** | un evento | tab Eventi, agganciato dalla colonna `OpenDay` | una data sola, e il link alla sua locandina |
| **Prova** | un attributo del corso | colonna `Prova` | *se* si può provare — sotto Periodo e Giorni, insieme agli altri dati |

**Nel foglio la colonna `Prova` non dovrebbe portare date.** Se ne porta, sono
date che nessuno viene ad aggiornare e che contraddicono quelle dell'evento. La
pillola «Prova gratuita» resta in riga: è un simbolo, e Giovanni l'aveva
approvata («penso sia molto utile»).

**Il segnaposto dell'open day sulla pagina di prova era doppiamente sbagliato** e
vale la pena saperlo prima di rimetterne uno: era una manifestazione lunga un
mese (quindi si leggeva «Dal 1 al 30 settembre») e puntava all'evento di un'altra
realtà. Adesso è **uno solo**, su un evento di **un giorno**, e la fascia in cima
dice apertamente che è un esempio. Qualunque segnaposto sarà sempre «l'evento di
qualcun altro»: l'unica difesa è dirlo.

#### La pagina della realtà: quando una pagina per cliente non è scaled content

Giovanni: «mi ero immaginato che ci fosse proprio una pagina organizzatori, non
solo la scheda nella pagina generale, in modo da poterci mettere dentro gli
eventi organizzati da quell'organizzatore lì, con locandina e tutto». Fatta:
`/corsi/<slug>.html`.

**Perché adesso si può, visto che per i luoghi si era detto di no.** Il rischio
dello *scaled content abuse* è di **volume** — erano le 800 pagine su template
identico col nome scambiato a essere il problema, non quaranta pagine con dentro
materiale vero. È già scritto sopra, ed è la ragione per cui le pagine dedicate
dei luoghi si fanno «per i clienti che pagano, una alla volta». Qui la condizione
è soddisfatta **per costruzione**: dal 21/08 la presenza nella guida è una sola
ed è pagata, quindi ogni organizzatore con una pagina *è* un cliente con del
materiale. E gli organizzatori sono decine, non centinaia.

**La soglia non è un numero di corsi, è il materiale.** Servono due cose
insieme: una riga nella tab `Realta` (l'atto deliberato — nessuno ci finisce per
sbaglio) **e** una descrizione di almeno `MIN_DESCR_REALTA` = 120 caratteri.
Senza, resta la scheda in fondo a `corsi.html` e basta. Il motivo è aritmetico:
una società con otto squadre e nessuna descrizione farebbe una pagina **più
povera del proprio riassunto**, cioè un doppione più debole di sé stessa.

Le decisioni che non si ricavano dal diff:

- **La scheda in fondo a `corsi.html` non sparisce quando nasce la pagina**, e
  l'ancora `#r-pgs-roccavione` resta dov'è: gira nei messaggi da prima che le
  pagine esistessero. Guadagna un link («La pagina di … →») e la descrizione si
  accorcia a 220 caratteri, perché il resto è la ragione per andare sulla pagina.
- **Il link «Organizzatore» nel dettaglio di un corso** va alla pagina se c'è,
  all'ancora se no. Sulla **propria** pagina quella riga non si stampa affatto:
  sarebbe un link all'intestazione che si sta leggendo.
- **I dati della realtà si scrivono in un posto solo** (`_dati_realta()`): li
  usano la scheda e la pagina, e un secondo elenco scritto a mano divergerebbe
  al primo campo aggiunto. Stessa ragione per cui la nav si rilegge da
  `eventi.html` invece di essere copiata.
- **La pagina si CANCELLA quando la realtà non ha più materiale**, ed è
  l'unica cosa del sito che si cancella. Ovunque le pagine restano — una scheda
  evento diventa «edizione conclusa» — perché l'anzianità dell'URL non si
  ricompra. Qui no: questa pagina è **uno spazio pagato**, e continuare a
  pubblicarla quando la presenza finisce vuol dire pubblicare una realtà che non
  è più nella guida. È il problema che per i luoghi è ancora aperto
  (`Premium_al`, «niente si spegne da solo») risolto nel verso giusto.
- **Le pagine di prova non vanno in `/corsi/`.** `prova_corsi.py` sposta
  `DIR_REALTA` su `corsi-prova/`: una scheda inventata dei Santibriganti in
  mezzo ai clienti veri è esattamente il danno che quella pagina esiste per
  evitare.
- **Nella sitemap stanno nello stesso blocco dell'hub**, così `CORSI_IN_INDICE`
  le spegne insieme. Con due blocchi, spegnere i corsi lascerebbe in sitemap
  proprio le pagine che senza l'hub non hanno più un posto da cui si arriva.

#### Gli eventi di una realtà: il legame è il nome, non una colonna nuova

Chiuso il 28/08/2026. Fino a quel giorno gli eventi sulla pagina di una società
erano **solo** quelli agganciati dai corsi con la colonna `OpenDay`, e si vedeva:
**CàRezza aveva nove appuntamenti in agenda e zero sulla sua pagina** — la
sezione non si stampava nemmeno. Idem PGS Roccavione col suo torneo del 29
agosto. L'unica che funzionava era Crome in Movimento, per un motivo solo: il
suo evento si chiama letteralmente «Open Day Corsi di Musica».

La causa non era un difetto, era una porta sola. `OpenDay` la riempie
`collega_openday()` nel downloader, che pretende `"open day"` dentro il nome
dell'evento — e fa bene, se no il saggio di fine anno diventerebbe un open day.
Ma essendo l'**unica** strada, tutto quello che open day non è restava fuori.

**Qui era scritto che serviva una colonna `Organizzatore` nella tab Eventi. Non
serviva**, ed è la parte da ricordare: il dato c'era già, scritto in coda al nome
di ogni evento — «Sogni d'Oro **- CàRezza**», «Green Volley Torneo 2VS2 **- PGS
Roccavione**». È la convenzione che il prompt di visione del downloader impone da
sempre (`"titolo del singolo appuntamento - Organizzatore"`), la stessa da cui
`organizzatore()` in `genera_eventi.py` ricava l'organizer del JSON-LD. Una
colonna nuova sarebbe stata un secondo posto da compilare per un'informazione già
presente.

**Due strade che si sommano, e rispondono a due domande diverse:**

| | la domanda | dove finisce |
|---|---|---|
| `OpenDay` (dal corso all'evento) | «vieni a provare **questo corso**» | nella riga del corso, **e** nella sezione in fondo |
| il nome in coda (dall'evento alla società) | «questa realtà fa **anche** questo» | **solo** nella sezione in fondo |

Le decisioni che non si ricavano dal diff:

- **Gli eventi non appartengono ai corsi, e non si attaccano a nessun corso.**
  Verificato sui dati, non supposto: i sei corsi di CàRezza e i suoi sette
  eventi **non hanno un nome in comune**. L'open day resta l'unico evento legato
  a un corso preciso, ed è per questo che è l'unico che si stampa dentro la riga
  di un corso.
- **Il confronto è solo sulla CODA del nome**, dopo l'ultimo trattino spaziato.
  Cercare il nome della società dentro tutto il titolo prenderebbe di più e
  sbaglierebbe, ed è la stessa cautela con cui `collega_openday()` pretende tre
  condizioni invece di una. Il trattino **deve** avere spazi intorno, se no
  «Espressione in Gioco! fascia 2-6 anni» si spezza sul `2-6`.
- **Il confronto è a pezzi interi, non per sottostringa**, e il caso che lo
  impone è vero: lo slug del corso «Accarezzami» *contiene* la parola
  «carezza», quindi per sottostringa un corso di CàRezza si sarebbe attaccato
  la propria società addosso.
- **Quello che assomiglia ma non torna si stampa nel log, non si indovina.** Se
  un domani la convenzione dei nomi cambia nel foglio, lo si legge nella run
  invece di scoprire una sezione che ha smesso di riempirsi senza dirlo.
- **Un evento ritirato resta fuori**: quella pagina dichiara di non essere
  attendibile, e annunciarla dalla pagina di chi la organizza vorrebbe dire
  mandare i suoi lettori a una nostra smentita. Un evento **concluso** pure: è
  la regola di `openday()`, «un invito a una porta chiusa».
- **Il nome della società non si ripete su ogni card.** Sulla pagina *di*
  CàRezza ogni riga diceva «… - CàRezza» sotto un titolo che dice già «eventi di
  CàRezza»: è la stessa ripetizione che le pagine comune tolgono quando un
  gruppo è tutto della stessa categoria. Si taglia **solo** se la coda è
  davvero la sua — un evento fatto insieme a un'altra realtà tiene il nome per
  intero, perché lì quella parola non è una ripetizione, è l'altro nome.

**Due incontri non fanno un corso** (Giovanni, 28/08/2026, sul caso vero:
«Coccoliamo-ci» costa *15 euro a incontro* e ha due date). Quindi restano
eventi, ed è dove sono. Ma sono a una locandina di distanza dal diventare
**anche** una riga di corso, e allora la stessa cosa comparirebbe due volte
sulla stessa pagina con due vocabolari diversi: quando il nome di un evento
coincide con quello di un corso della stessa società, `eventi_realta()` **lo
stampa e basta**. Il verdetto lo dà una persona guardando la locandina, non una
regola — è `segnala_senza_coordinate()` applicata a un altro dubbio.

`tests/corsi.js` difende tre cose, e la prima **non rifà il confronto del
generatore**, deliberatamente: un secondo posto dove si decide chi si aggancia a
chi divergerebbe al primo ritocco. Chiede una cosa più debole e che per
costruzione non può divergere — *se in registro c'è qualcosa di ovviamente suo e
ancora da fare, in pagina non ci può essere il vuoto* — cioè la regressione
vera, la sezione che sparisce, non l'algoritmo. Rimettendo il difetto le prove
tornano rosse dicendo «6 eventi a suo nome in registro, 0 in pagina»: verificato,
non supposto.

**E il verso opposto, fatto lo stesso giorno.** Sulla scheda di un evento, fra la
prenotazione e i recapiti, c'è la riga **«Organizzatore: I corsi di CàRezza →»**
(`link_realta()` in `genera_eventi.py`). Senza, il legame era mezzo: la pagina di
CàRezza raccoglieva i suoi appuntamenti, ma chi arriva da Google su «Sogni d'Oro
Racconigi» trovava solo `/corsi.html` generico e non scopriva che quella realtà
ha una pagina sua. Al 28/08/2026 sono **8 schede su ~400**.

- **Il taglio del nome sta in `genera_eventi.py`** (`taglia_coda()`), non in
  `genera_corsi.py` che pure lo usa: quel modulo importa questo, non il
  contrario, e due implementazioni della stessa regola darebbero due link che si
  contraddicono, uno per verso.
- **Il patto è un file**, `data/realta-pagine.json`: lo scrive `genera_corsi.py`
  (che sa quali pagine esistono davvero) e lo legge `genera_eventi.py` **al giro
  dopo** — nel workflow gira prima lui. Stesso ritardo di
  `data/luoghi-comuni.json`, e per la stessa ragione: una realtà nuova resta un
  giorno senza il link dalle sue schede, e sbagliare in quel verso è gratis; il
  verso opposto no, perché un link a una pagina appena cancellata è un 404.
- **Il registro si riscrive sempre, anche vuoto**, ed è il contrario del patto
  di `centri-stagioni.json`, che invece *fonde*. Là un foglio non letto non deve
  spegnere una voce di nav; qui la verità è cosa c'è su disco, e
  `scrivi_realta()` l'ha appena stabilita: una realtà che perde la pagina deve
  perdere anche i link che ci puntano.
- **Sulla riga si scrive il nome, non l'etichetta.** «I corsi di CàRezza» è una
  ragione per toccare, «Organizzatore» no — è la lezione di `link_luoghi()`.
- **Niente su una scheda ritirata**: lo garantisce `facts = []` in
  `render_pagina()`, ed è la stessa ragione per cui lì spariscono i due bottoni.
  Quella pagina si dichiara inattendibile, e non è il posto da cui presentare
  una realtà.

La prova in `tests/corsi.js` guarda **solo il verso pericoloso** — nessun rimando
verso una pagina che non esiste — e legge i file invece di aprirli col browser,
che su ~400 schede costerebbe più di tutta la suite. La simmetrica («ogni realtà
con eventi riceve il link dalle sue schede») **non si scrive**: sarebbe rossa per
un giro ogni volta che nasce una realtà nuova, cioè proprio quando il sito fa la
cosa giusta. È la quarta volta che quel tipo di prova si sarebbe rotta da sé —
dopo la copertura delle coordinate, il conteggio delle quattro porte e il robots
delle pagine realtà.

**Cosa manca ancora.** Un evento **senza** il trattino in coda non si aggancia a
nessuno, in nessuno dei due versi: è la regola di `link_luoghi()` — quello che
manca non si stampa e non si inventa — ma vuol dire che una locandina letta male
resta muta, e lo si vede solo nel log della run.

**Due file generati non erano nell'elenco del workflow**, ed è la tredicesima e
quattordicesima ripetizione dello stesso guasto già documentato per
`ferragosto.html`. `data/centri-stagioni.json` (nato il 21/08, quello che decide
la voce dei centri in nav su ~360 pagine) è tracciato, quindi la rete di
sicurezza in fondo al workflow avrebbe fatto diventare rossa la run notturna. Le
pagine in `corsi/` no: nascono **untracked**, quando una società nuova entra
nella tab `Realta`, ed è l'unico caso in cui quella rete **non** protegge —
`git status --untracked-files=no` non le vede. Per questo nell'elenco c'è la
cartella `corsi/` e non un elenco di file. Se un domani si vuole chiudere anche
quel buco, il posto è il flag di quel `git status`.

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

Nata il 13/08/2026, cioè **due giorni prima**. Qui c'era scritto "quest'anno non
si posiziona, la resa da Google arriva nel 2027": **è andata diversamente, e molto
più in meglio di quanto scritto al primo giro.**

| export | giorni di vita | clic | impressioni | CTR | pos |
|---|---|---|---|---|---|
| 15/08 (chiude 13/08) | 1 | 36 | 554 | 6,50% | 6,06 |
| **17/08 (chiude 15/08)** | **4** | **187** | **6.161** | 3,04% | 6,54 |

**187 clic in quattro giorni è il 3,8% del trimestre**, cioè quanto una
`sagre-provincia-*` che sta online da mesi — quinta pagina del sito. Più le schede
a tema che ha trainato: Acqui Terme 45 clic, Limone Piemonte 35, Eco Park 26.

Il CTR scende dal 6,50% al 3,04% e **non è un peggioramento della pagina**: al 13
agosto vedeva solo chi cercava presto e con intenzione, il 14-15 è arrivata la
domanda generica di massa dove stiamo in posizione 6-7. È lo stesso meccanismo del
CTR del sito quei due giorni. Con 6.161 impressioni al 3,04% è comunque diventata
**la seconda perdita del sito dopo `eventi.html`** — e non c'è niente da fare
adesso, perché dal 17 agosto va in `noindex` da sola.

**Il `noindex` automatico ha funzionato, e si vede in un numero.** Nell'export del
24/08 la pagina chiude a 219 clic e 7.191 impressioni: fra il 16 e il 21 agosto ha
aggiunto **32 clic e 1.030 impressioni**, cioè ~170 impressioni al giorno contro le
~1.540 di media dei suoi primi quattro giorni. Si è spenta da sola, senza che
nessuno la toccasse, ed è la prova che `MIN_LANDING` fa quello che promette. L'URL resta
online e invecchia per il 2027, che era tutto il punto.

Non cambia nessuna delle decisioni sopra, e soprattutto **non è un argomento per
fare le stagionali all'ultimo**: una pagina che parte da posizione 6 in
ventiquattr'ore su un dominio già forte partirebbe da più su con due mesi di
anzianità, che è esattamente la scommessa di Halloween. Quello che cambia è
l'aspettativa, e adesso si può dire più forte: una stagionale nuova rende **quanto
una pagina consolidata** già l'anno zero, quindi vale la pena farla anche quando è
tardi — non "tanto è per l'anno prossimo".

### `/halloween.html`: fatta con due mesi e mezzo d'anticipo, apposta

Stessa impalcatura di Ferragosto (`spec_halloween()`, finestra fissa **25
ottobre - 2 novembre**, l'anno nel title e non nell'indirizzo), ma nata il
**14/08/2026** — cioè con 72 giorni d'anticipo invece di due.

Non è zelo, è l'unica correzione possibile all'unico errore di
`/ferragosto.html`. Su una pagina stagionale l'asset **è l'anzianità dell'URL**:
è lo stesso motivo per cui l'anno sta fuori dallo slug. Una pagina che esiste da
agosto e sta in `noindex` finché non ha eventi non costa niente — è la stessa
regola `MIN_LANDING` delle `sagre-provincia-*` — e arriva a ottobre con due mesi
di vita. Creata il 25 ottobre ripartirebbe da zero, esattamente come farebbe
`/halloween-2026.html`. Al 14/08 ha già 2 eventi in agenda, quindi è in
`noindex` e fuori sitemap: è il comportamento giusto, non un difetto.

**La finestra è fissa e larga nove giorni** perché Halloween non è un giorno:
prende il fine settimana prima comunque cada, la notte del 31 e **Ognissanti**,
che in Italia è festa e sposta le gite. "Il weekend più vicino" coinciderebbe
con `/eventi/weekend.html` un anno su due, che è la ragione già scritta per il
14-16 agosto.

#### Qui il fossato non ci aiuta, ed è la prima volta

Le sagre di paese le vinciamo sul **nome proprio**: `festa cassinasco 2026`,
CTR 31%, nessun concorrente. Halloween è l'opposto — query **nazionale e
generica**, cioè la colonna in cui stiamo in posizione 8-10 col 2,86% di CTR, e
di fronte ci sono siti che fanno "Halloween in Italia" da dieci anni. La pagina
si fa lo stesso, ma quello che può realisticamente prendere sono le **code
lunghe con dentro un nome proprio** (`halloween castello di <paese> 2026`), non
la query secca. Non aspettarti i numeri di Cassinasco e non giudicarla su
quelli.

Sul metro giusto — quanto è lontana la domanda — al 13/08 la parola "halloween"
compariva nell'export con **3 impressioni in tutto**, tutte su una scheda (San
Marzano Oliveto); nell'export del 17/08 **non compare per niente**, e
`halloween.html` non ha nessuna impressione. È il comportamento previsto e non
dice niente sulla pagina: la domanda di Halloween si accende a ottobre. Il numero
da guardare è quello di inizio ottobre, ed è anche il promemoria del perché le
schede stagionali vanno
raccolte apposta (vedi la tabella delle scadenze in fondo a "Quello che cambia in
autunno").

#### Cosa ha di suo, e la cernita che non si fa

Se fosse solo l'elenco del 25/10-2/11 sarebbe `/eventi/weekend.html` con un
altro titolo, e il doppione lo perde la pagina senza autorità. Quello che ha di
suo è la domanda che a Halloween si fanno tutti i genitori e a cui un elenco non
risponde: **fa paura o no?** La caccia ai dolcetti in piazza e la casa infestata
nel castello finiscono nello stesso elenco, e un bambino di quattro anni e uno
di dodici cercano la stessa parola volendo due cose opposte. L'età è l'unico
dato che abbiamo e i siti nazionali no.

**Non si deduce la paura dal titolo.** Una sezione "questi fanno paura" ricavata
da parole tipo *horror*, *brivido*, *notte nera* sarebbe un giudizio nostro su
una festa altrui, ricavato da una stringa: sbagliarlo vuol dire mandare un
bambino di quattro anni in una casa infestata, o togliere pubblico a un evento
che paura non fa. Si fa come per "ci vado con i bambini?" nelle pagine comune —
si dà la regola per leggere la pagina (dove l'età è dichiarata è scritta in
riga, dove non c'è si apre la scheda e si legge il programma) e si mette in
evidenza **solo** il gruppo su cui il dato esiste davvero: `e_per_bambini()`,
che dice "pensati **per** i bambini" e non "adatti". Il flag `Adatto Famiglie`
resta fuori, per le ragioni di sempre. `tests/landing.js` controlla che nessuna
sezione etichetti gli eventi come spaventosi.

Il secondo pezzo è il **dove** — castelli, cascine, borghi — e manda a
`luoghi.html`. È la seconda superficie che linka quella pagina dal corpo di
un'altra: la prima è Ferragosto, e prima ne aveva zero.

#### Non generalizzare a Natale, Carnevale e Pasqua

La tentazione ovvia è scrivere una funzione stagionale e istanziarla quattro
volte. È da non fare, ed è la stessa aritmetica dello *scaled content*: quello
che rende utile una stagionale è proprio il blocco che ogni stagione ha di
**diverso** — a Halloween "fa paura?", a Natale "quale mercatino, e si mangia?".
Generalizzando adesso verrebbero quattro pagine identiche con una parola
scambiata. Halloween si fa su misura come Ferragosto; se dalla terza emerge del
codice comune, si estrae allora.

Quello che invece è già condiviso è **come ci si arriva**: `blocco_stagione()`
legge la tabella `STAGIONI` e stampa la riga in home e in cima all'agenda per la
stagione attiva (Ferragosto dal 5 agosto, Halloween dal 20 ottobre). Le finestre
non si sovrappongono, quindi la prima che risponde vince e non c'è nessuna
precedenza da decidere. `link_landing()` invece apre prima — dal 1° ottobre per
Halloween — perché una voce in una riga di scorciatoie costa meno di una riga in
evidenza.

### Il traffico sono le schede, e i loro URL non scadono

Misurato sull'export di Search Console del 17/08/2026 (tre mesi, 16/05–15/08):
**4.878 clic, 64.819 impressioni, CTR 7,53%, 90% dei clic da telefono.** Dove
vanno:

| | clic | quota | CTR | posizione |
|---|---|---|---|---|
| le 245 **schede** `/eventi/*.html` | 3.482 | **71%** | 9,63% | 5,48 |
| `eventi.html` | 488 | 10,0% | 2,49% | 8,18 |
| `sagre-provincia-*` | 527 | 10,8% | 8,42% | 6,64 |
| `/ferragosto.html` (**quattro** giorni di vita) | 187 | 3,8% | 3,04% | 6,54 |
| le sei pagine d'**incrocio** (due giorni di vita) | 111 | 2,3% | 6,36% | 7,01 |
| home | 83 | 1,7% | 17,18% | 5,61 |
| `oggi.html` + `weekend.html` | **1** | 0% | — | — |
| `luoghi.html` (tre giorni di vita) | 3 | 0,1% | 0,56% | 8,63 |

Le posizioni sono pesate sulle impressioni, che è la media onesta: pesandole sui
clic le schede stanno a 4,44 e sembra meglio di com'è.

Da qui la prima cosa da non fraintendere: **come pagina singola `eventi.html`
resta la più forte del sito, ma come sistema il sito sono le schede.** Ed erano
esattamente loro a non mandare `page_view` fino al 12/08 — il divario fra clic da
Google e utenti GA4 non era un mistero, erano i tre quarti del traffico.

La seconda è dove sta il buco più grosso: **`eventi.html` incassa 19.563
impressioni — il 30% di tutto il sito — e le converte al 2,49%.** Le stesse
persone che sulle schede cliccano al 10% lì non cliccano, e non è un difetto
della pagina: è la posizione 8,18 sulle query generiche. È il problema che le sei
pagine d'incrocio provano ad aggredire (vedi la sezione sulla cannibalizzazione),
non uno da risolvere riscrivendo l'H1. La quota è scesa dal 38% al 30% solo perché
il resto del sito è cresciuto: in valore assoluto il buco si è allargato di 3.255
impressioni in due giorni.

Terza, ed è nuova: **le tre `sagre-provincia-*` sono la seconda famiglia del
sito**, e dentro comanda Cuneo — 231 clic su 2.487 impressioni al 9,29% — cioè
una provincia aperta il 04/08. Asti 216 (7,46%), Alessandria 80 (9,11%). Cuneo da
sola batte tutte e sei le pagine d'incrocio insieme.

#### Le stesse quote a 28 giorni, e una famiglia che mancava all'appello

Export del 24/08 (25/07-21/08, **7.399 clic e 101.492 impressioni** sul foglio
Pagine — che non somma come Grafico, e va bene così: è l'anonimizzazione per
dimensione già descritta più sotto).

| | pagine | clic | quota | impressioni | CTR | pos |
|---|---|---|---|---|---|---|
| **schede** `/eventi/*.html` | 279 | 5.098 | **68,9%** | 50.968 | 10,00% | — |
| `sagre-provincia-*` | 3 | 947 | 12,8% | 10.608 | 8,93% | 6,7 |
| `eventi.html` | 1 | 562 | 7,6% | **20.973** | 2,68% | 8,02 |
| **pagine comune** | 15 | **274** | **3,7%** | 4.664 | 5,87% | — |
| `ferragosto.html` | 1 | 219 | 3,0% | 7.191 | 3,05% | 6,50 |
| `weekend-provincia-*` | 3 | 178 | 2,4% | 2.273 | 7,83% | — |
| `oggi-provincia-*` | 3 | 41 | 0,6% | 1.787 | 2,29% | — |
| home | 1 | 29 | 0,4% | 224 | 12,95% | 6,44 |
| `luoghi.html` | 1 | 24 | 0,3% | 1.804 | 1,33% | 8,43 |
| `oggi.html` + `weekend.html` | 2 | 3 | 0,0% | 76 | — | — |

Le quote reggono: le schede restano circa il 70%, `eventi.html` circa un decimo.
Quattro cose sono nuove.

**Le pagine comune sono una famiglia, e non erano mai state contate.** 274 clic,
il 3,7% del sito, più delle sei pagine d'incrocio messe insieme — e
`/eventi/comune/novi-ligure.html` da sola fa 113 clic, cioè è la **tredicesima
pagina del sito**. Erano nate come destinazione dei link interni; prendono
traffico da Google per conto loro. Quindici pagine su ventitré hanno impressioni.

**Il buco di `eventi.html` si è allargato ancora**: 20.973 impressioni al 2,68%,
cioè il 20,7% delle impressioni del sito su una pagina sola. In tre mesi erano
19.563: in quattro settimane ne fa più che nel trimestre precedente. Resta la
pagina che perde più pubblico del sito, e resta vero che **non si tocca l'H1**
per rimediare.

**Dentro le provinciali il primato è cambiato**: Asti 376 clic (4.584 impr,
8,20%, pos 6,58), Cuneo 359 (3.755, 9,56%), Alessandria 212 (2.269, 9,34%). Sul
trimestre chiuso al 15/08 comandava Cuneo. Non è un sorpasso da spiegare, è la
stagione delle patronali astigiane — ma vuol dire che **la classifica fra le tre
province non è una proprietà del sito**, e non va citata come tale a nessuno.

**`oggi.html` è scivolata a posizione 21,72**, da ~8. Non è un guasto ed è anzi
la conferma della decisione del 14/08: Google l'ha smessa di considerare una
risposta e la tratta per quello che è diventata, cioè un indice. `weekend.html`
resta a 7,91 con 33 impressioni.

**L'onda di agosto non è la stagione delle sagre: sono le schede.** Il `first_seen`
in `data/pagine-evento.json` dice che il sistema è nato il **02/08/2026**, e la
rampa è questa:

| | giorni | clic/giorno | quota dei clic del trimestre |
|---|---|---|---|
| 16/05-30/06 | 46 | 1,3 | 1,3% |
| luglio | 31 | 5,5 | 3,5% |
| 1-2 agosto | 2 | 12,5 | 0,5% |
| 3-7 agosto | 5 | 153,2 | 15,7% |
| **8-15 agosto** | 8 | **482,0** | **79,0%** |

La **posizione media scende da 7,66 a ~6,0** mentre le impressioni fanno ×20 —
di solito succede il contrario, cioè arrivano impressioni su query lontane e la
media peggiora. Le stesse sagre erano già in agenda a luglio, quando il sito
faceva cinque clic al giorno: il picco di Ferragosto ha amplificato, non causato.

**E l'8 agosto non era il picco, per la seconda volta.** L'export del 15/08 aveva
già corretto "picco l'8 con la coda in discesa" in "il 13 risale"; quello del
17/08 corregge anche quello, e la lezione è che **con una stagione in corso il
picco non si dichiara mai sull'ultimo giorno disponibile**:

| | clic (export 17/08) | clic (export 24/08) | impressioni | CTR | pos |
|---|---|---|---|---|---|
| 8 ago (sab) | 603 | 603 | 6.112 | 9,87% | 6,0 |
| 13 ago (gio) | 582 | **594** | 5.859 | 10,14% | 5,6 |
| **14 ago (ven)** | 682 | **752** | 10.306 | 7,30% | 6,1 |
| **15 ago (sab)** | 708 | **787** | 11.685 | 6,74% | 6,2 |

Il 14 e il 15 valgono **1.539 clic**, cioè il 21% delle ultime quattro settimane
in due giorni. Il picco vero è il **15**, non il 14.

**E c'è una seconda ragione per non dichiarare il picco sull'ultimo giorno, che
non è l'incompletezza della finestra: gli ultimi giorni di un export sono
sottostimati.** Le due colonne qui sopra sono gli *stessi giorni* riletti a una
settimana di distanza. L'8 agosto non si muove di un clic; il 13 sale del 2%; il
14 e il 15 — che nel primo export erano gli ultimi due giorni — salgono del
**10-11%**. Search Console consolida all'indietro, e la regola operativa è:
**gli ultimi due giorni di qualunque export valgono circa il 10% in più di
quello che dicono.** Non si confrontano con giorni consolidati, e non si
riscrive niente guardandoli.

**Sul CTR di quei due giorni non si apre un'indagine**: le impressioni
raddoppiano e i clic crescono del 17%, quindi il rapporto scende per forza. È la
domanda generica di Ferragosto che arriva in massa dove stiamo in posizione 7-9,
e si vede in due voci: `ferragosto.html` da sola prende 6.161 impressioni al
3,04%, e l'estero sale a 5.202 impressioni per 41 clic. Segmentando Italia il CTR
del trimestre è **8,11%** invece di 7,53%.

Dove sono imbattibili: **nomi propri di feste di paese.** `festa cassinasco 2026`
in posizione 1,16 con CTR 31%, `cassinasco festa 2026` con CTR **72%**. Nessun
altro pubblica i sotto-eventi di una patronale di 800 abitanti. Le query che
contengono un nome di posto fanno il **77% dei clic visibili**; quelle senza,
niente da fare.

Due numeri per tenere la testa a posto: le prime 10 schede fanno il **45%** dei
clic delle schede e il 32% del sito, `festa-d-estate-cassinasco.html` da sola il
6,2%; e il foglio `Query` copre solo 1.063 dei 4.878 clic, perché Google
anonimizza le query troppo rare. **Il 78% del traffico arriva da ricerche che non
possiamo vedere.** È il fossato (nessuno ci compete) e la fragilità (non c'è una
query da difendere) nello stesso dato.

#### In quali comuni siamo forti: la mappa che serve a chi vende

Fatta il 24/08/2026, incrociando il foglio Pagine con `data/pagine-evento.json`
(ogni scheda porta il suo comune, quindi l'attribuzione è esatta: 5.098 clic su
5.101 finiscono in un comune). È la prima volta che il traffico si legge per
posto invece che per famiglia di pagine, ed è **il numero che un cliente locale
compra**: non "il sito fa 7.300 clic", ma "a Ovada quanti".

| comune | prov | schede | clic | quota | CTR |
|---|---|---|---|---|---|
| Carpeneto | AL | 1 | 316 | 6,2% | **17,61%** |
| Grondona | AL | 1 | 309 | 6,1% | 12,88% |
| Cassinasco | AT | 1 | 301 | 5,9% | **22,18%** |
| Novi Ligure | AL | 8 | 288 | 5,6% | 7,13% |
| Castel Boglione | AT | 1 | 280 | 5,5% | **28,87%** |
| Celle Enomondo | AT | 1 | 203 | 4,0% | 24,34% |
| Ponzone | AL | 3 | 157 | 3,1% | 13,88% |
| Mornese | AL | 1 | 156 | 3,1% | 21,46% |
| Tassarolo | AL | 1 | 151 | 3,0% | 21,39% |
| Casalnoceto | AL | 3 | 127 | 2,5% | 11,49% |

**Tredici comuni su 143 fanno metà dei clic delle schede; trentasette ne fanno
l'80%.** La concentrazione è scesa — le prime dieci schede erano il 45% dei clic
delle schede sul trimestre, adesso sono il 40,2% — ma resta il fatto già scritto
per la vendita: **a un cliente di Ovada non serve il traffico di Cassinasco**, e
adesso si può dire con una cifra invece che con un'intuizione.

**Il fossato ha una misura, ed è controintuitiva.** Raggruppando i comuni per
quante schede hanno preso impressioni:

| | comuni | clic | impressioni | CTR |
|---|---|---|---|---|
| **1 scheda** | 94 | 3.108 | 22.981 | **13,52%** |
| 2-4 schede | 38 | 1.333 | 16.461 | 8,10% |
| **5+ schede** | 10 | 657 | 11.526 | **5,70%** |

Il paese con una sola scheda converte **due volte e mezzo** la città con cinque o
più. Non è cannibalizzazione fra le nostre pagine — è composizione: un comune di
800 abitanti entra nell'export solo quando ha *la* festa dell'anno, con un nome
proprio che nessun altro pubblica, mentre gli eventi di Novi Ligure o
Alessandria si chiamano "Sagra della trippa" e competono con tutti. **Il fossato
non è "le sagre": è il nome proprio in un posto piccolo.**

Ne segue la cosa da non dedurre: che convenga smettere di coprire le città.
Novi Ligure fa 288 clic con le schede più la sua pagina comune da 113, cioè
**401 clic in totale ed è il posto più forte del sito** — ci arriva con otto
schede al 7% invece che con una al 22%. Sono due meccaniche diverse che vanno
tenute tutte e due.

**Per provincia**, sulle sole schede: AL 2.819 clic da 57 comuni (CTR 9,93%),
AT 1.580 da 39 comuni (**12,90%**), CN 699 da 47 comuni (6,76%). Asti fa un
terzo dei clic con il CTR più alto delle tre; Cuneo, aperta il 04/08, ha già più
comuni di Asti e converte alla metà — è l'anzianità delle sue schede, e va
riguardato fra un mese prima di trarne qualunque conclusione sulla provincia.

#### Le query da recuperare sono i nomi propri in posizione 9, non le generiche

Sulle generiche siamo deboli per costruzione e il rimedio sono le pagine
d'incrocio. Ma nell'export ci sono anche nomi propri con molte impressioni e zero
clic, che è l'unico caso in cui manca solo la copertura:

| clic | impr | pos | query |
|---|---|---|---|
| 0 | 124 | 9,65 | `sagra del cinghiale morbello 2026` |
| 0 | 119 | 7,87 | `alecomics 2026` |
| 1 | 139 | 10,04 | `fuochi novi ligure 2026` |
| 0 | 73 | 5,64 | `festa fubine 2026` |
| 0 | 63 | 9,98 | `san sebastiano curone eventi` |

Il primo dice tutto: `sagra morbello 2026` fa 18 clic a posizione 5,78, la
variante col nome del piatto zero clic a 9,65. **Stessa festa, due query, e la
seconda non è coperta perché il piatto non è nel titolo della riga del foglio.**
Non è un lavoro di codice: è come vengono scritti i nomi in agenda.

Una curiosità che serve a non spaventarsi: `gianmarco bagutti età` fa **201
impressioni e zero clic** in posizione 9,58. È il nome di un artista che suona a
una festa in programma, ed è la query con più impressioni senza comune di tutto
l'export. Impressioni così non sono nostro pubblico e non c'è niente da
ottimizzare.

#### Il verdetto non è agosto, è il 15 settembre

Tutto quello che sappiamo viene da tredici giorni di alta stagione, su un sito che
non ha mai vissuto un ottobre — e l'**79% dei clic del trimestre sta in otto
giorni**, il che rende ogni media a tre mesi un numero che non descrive nessun
giorno vero. Ad agosto qualunque sito di sagre piemontesi fa numeri, quindi **la
domanda "andiamo bene?" non ha una risposta onesta prima di metà settembre**,
quando si vede dove si ferma la discesa:

| clic/giorno a metà settembre | cosa vuol dire |
|---|---|
| sotto 20 | agosto era la stagione, il sistema non si regge da solo |
| 50-100 | il sistema regge: è il sito, non il calendario |
| sopra 150 | non c'è più una stagione da temere |

**Una risposta parziale c'è già, ed è nella sezione qui sotto** ("La discesa dopo
Ferragosto"): il pavimento feriale del 18-20 agosto è 271 clic al giorno, cioè
-5% rispetto alla settimana prima del picco. Non chiude la scommessa — il 18
agosto è ancora agosto — ma sposta l'aspettativa verso la terza riga della
tabella invece che verso la prima.

**E con il 22 agosto dentro la risposta parziale si rafforza** ("Un giorno dopo:
il sabato senza feste batte Ferragosto"): la settimana 16-22 agosto fa 471,9 clic
al giorno, cioè -3,2% dalla settimana di Ferragosto, con un sabato qualunque che
segna il record del sito. Resta agosto, quindi resta una risposta parziale — ma
il numero da temere il 15 settembre continua a scendere, e la riga della tabella
verso cui punta è sempre la terza.

La scommessa ragionevole è la seconda — 245 schede indicizzate che non si
cancellano mai, e l'autunno piemontese ha il nome del paese attaccato a ogni
evento — ma è una scommessa, e questa è la data in cui si riscuote. Il numero da
segnare adesso, per non ricostruirlo dopo: **la baseline pre-schede è 5,5 clic al
giorno** (luglio 2026).

E i segnali d'autunno nell'export **non aiutano a rispondere in anticipo**: al
15/08 le query di stagione (zucca, castagne, tartufo, mercatini, presepi) sono
**6 query per 24 impressioni in tutto**. Non è un cattivo segno, è l'imbuto da
dieci giorni della fonte: a metà agosto non può esserci altro. Chi guarda quel
numero cercando un presagio sta guardando la cosa sbagliata.

#### La discesa dopo Ferragosto: il pavimento non si è mosso

Export del 24/08/2026, finestra **25/07-21/08** (28 giorni; la finestra sta nel
foglio `Filtri`, il giorno di chiusura nell'ultima riga di `Grafico` — sempre e
solo lì). Totale: **7.328 clic, 91.556 impressioni, CTR 8,00%, posizione 6,13.**
È il primo export che contiene la discesa, ed è la prima risposta parziale alla
domanda del 15 settembre.

| fascia | giorni | clic/giorno | impr/giorno | CTR | pos |
|---|---|---|---|---|---|
| pre-onda (25/7-2/8) | 9 | **7,9** | 269 | 2,93% | 7,39 |
| rampa (3-12/8) | 10 | 265,0 | 3.047 | 8,70% | 6,06 |
| picco (13-17/8) | 5 | **643,6** | 8.029 | 8,02% | 6,09 |
| dopo (18-21/8) | 4 | 347,2 | 4.628 | 7,50% | 6,22 |
| dopo, feriali (18-20/8) | 3 | **270,7** | 3.961 | 6,83% | 6,40 |

**Il numero da leggere è l'ultima riga, e va confrontato con la settimana prima
del picco, non col picco.** Dal 787 del 15 agosto al 259 del 18 c'è un -67% che
non vuol dire niente: è la fine di una festa. Il confronto onesto è fra giorni
della stessa specie —

| | lun-mer 10-12/8 | mar-gio 18-20/8 |
|---|---|---|
| clic/giorno | 284,7 | **270,7** |

**-5%.** Il picco di Ferragosto è stato una punta *sopra* un pavimento feriale
che è rimasto dov'era. Chi guarda solo il grafico vede un crollo; chi confronta
i martedì vede una riga piatta.

**È comparsa la settimana**, e prima non si vedeva perché i numeri erano troppo
piccoli: venerdì 21 agosto fa **577 clic**, cioè 2,1 volte il pavimento
feriale di quella stessa settimana. Il ritmo è mercoledì-basso → venerdì-sabato-
alto, che è quando si decide cosa fare nel fine settimana. Ne segue una regola di
lettura da usare da qui in avanti: **un giorno si confronta col suo giorno della
settimana**, se no si legge il calendario e non il sito.

**Cosa dice e cosa non dice sulla scommessa del 15 settembre.** Le soglie
scritte sopra sono su clic/giorno: 270 feriali e 577 il venerdì stanno molto
sopra la fascia "sopra 150 = non c'è più una stagione da temere". **Non basta a
riscuotere**, e per una ragione sola: il 18-21 agosto è ancora agosto, con 89
eventi in agenda quel mese. La cosa che il dato aggiunge davvero è che **la
discesa non è verticale**: il sistema perde il picco, non la base. La data resta
il 15 settembre, ma il numero da temere adesso è più basso di quanto sembrasse.

**Segnali d'autunno: ancora niente, come previsto.** Su 1.000 query visibili,
`halloween` compare **zero** volte, `castagn`, `presep`, `natal`, `vendemmi`,
`fungh` zero, `zucca` 3 query per 114 impressioni, `tartufo` 1 per 7. È l'imbuto
da dieci giorni della fonte, non un presagio — la stessa lettura del 15/08 e con
lo stesso valore, cioè nessuno.

#### Un giorno dopo: il sabato senza feste batte Ferragosto

Export scaricato lo stesso 24/08 ma con la finestra spostata di un giorno,
**26/07-22/08**. Un solo giorno in più, e cambia la risposta alla domanda "quanti
clic al mese" — motivo per cui vale la pena tenere le due letture separate invece
di sovrascrivere quella sopra.

Totale: **8.151 clic, 102.706 impressioni, CTR 7,94%, posizione 6,13.** Italia
sola 8,44% (il Regno Unito da solo fa 2.922 impressioni e 4 clic, cioè lo 0,14%:
è il solito motore che ci mostra a chi cerca in inglese).

| finestra | giorni | clic/giorno | run rate mensile |
|---|---|---|---|
| pre-infrastruttura (26/7-2/8) | 8 | **8,1** | 244 |
| rampa (3-8/8) | 6 | 228,2 | 6.845 |
| settimana di Ferragosto (9-15/8) | 7 | 487,7 | 14.631 |
| **settimana dopo (16-22/8)** | 7 | **471,9** | **14.156** |

**La settimana dopo Ferragosto sta a -3,2% dalla settimana di Ferragosto**, e
sabato 22 agosto — nessuna festa comandata — fa **829 clic**, record assoluto,
sopra i 787 del sabato di Ferragosto e i 603 dell'8. È la prima prova che il
sistema non è la stagione, ed è più forte del pavimento feriale citato sopra.

**Qui era scritto ~10-11.000 clic/mese, ed era una sottostima.** La stima si
reggeva sul solo confronto fra feriali omologhi (270,7 contro 284,7, -5%), che è
il metodo giusto per sapere se il pavimento tiene e quello sbagliato per sapere
quanto fa il sito: **il pavimento non è più dove sta la crescita.** Il ritmo si è
irrigidito su base settimanale — feriali fermi intorno a 270, venerdì e sabato
che raddoppiano — quindi una media va presa su settimane intere, mai su una
fascia di giorni scelta.

**Il 22 agosto è l'ultimo giorno dell'export, quindi vale probabilmente ~10% in
più.** Attenzione però a una cosa che si sarebbe potuta dedurre male: i giorni in
comune fra questo export e quello che chiude al 21/08 sono **identici clic per
clic** (13/8 594, 14/8 752, 15/8 787, 20/8 281, 21/8 577). Non smentisce la
regola del consolidamento all'indietro — i due file sono scaricati lo stesso
giorno, cioè sono la stessa istantanea — ma vuol dire che **la revisione non si
osserva a un giorno di distanza**: quella misurata valeva a una settimana.

Le quote per famiglia non si muovono, ed è il dato che dice che la struttura
regge:

| famiglia | pagine | clic | quota | impressioni | CTR |
|---|---|---|---|---|---|
| schede `/eventi/*` | 289 | 5.742 | **69,8%** | 58.185 | 9,87% |
| `sagre-provincia-*` | 3 | 1.027 | 12,5% | 11.679 | 8,79% |
| `eventi.html` | 1 | 629 | 7,7% | **22.847** | **2,75%** |
| pagine comune | 16 | 290 | 3,5% | 5.332 | 5,44% |
| `ferragosto.html` | 1 | 219 | 2,7% | 7.247 | 3,02% |
| `weekend-provincia-*` | 3 | 180 | 2,2% | 2.328 | 7,73% |
| `oggi-provincia-*` | 3 | 47 | 0,6% | 2.276 | 2,07% |
| `luoghi.html` | 1 | 27 | 0,3% | 2.043 | 1,32% |

**Il buco di `eventi.html` cresce di circa duemila impressioni a export**: 19.563
(trimestre al 15/08) → 20.973 (28 giorni al 21/08) → **22.847** qui, sempre
intorno al 2,7% di CTR e al 20% delle impressioni del sito. Non è una cosa da
riparare toccando l'H1, è la ragione per cui esistono le pagine d'incrocio.

##### Il brand è a zero, e questa è la risposta alla domanda sulle famiglie

Su 1.000 query visibili (2.077 clic, cioè un quarto del traffico — il resto
Google lo anonimizza):

| | query | clic | impressioni |
|---|---|---|---|
| `daop` | 1 | 4 | **7** |
| contengono "bambin*" | 14 | 4 | 75 |
| contengono "weekend" | 30 | 46 | 1.553 |
| contengono "oggi" | 213 | 224 | 6.538 |

**Sette impressioni di brand su 102.706.** Il sito è il riferimento per "che
sagra c'è a Grondona", non ancora per "dove porto i bambini": la porta funziona,
la casa dietro la porta non la conosce nessuno. È il KPI del cavallo di Troia
(vedi la memoria omonima) e va riletto a ogni export — **la curva delle query
brand, non i clic**. Oggi la curva è piatta a zero, e non è un difetto: è il
punto di partenza, misurato per la prima volta.

Non se ne ricava che vada aggiunta una superficie "per famiglie": le tre pagine
`weekend-provincia-*` sono già quella cosa e vincono le loro query. Quello che
manca è la ragione per tornare **senza passare da Google**, che è la sola cosa
che le query brand misurano.

**Segnali d'autunno: ancora zero**, come nei due export precedenti — `halloween`,
`castagn`, `presep`, `natal`, `vendemm`, `fungh` non compaiono affatto; `zucca` 3
query per 173 impressioni, `tartufo` 1 per 7. E il sito gira a 14.000 clic al
mese **su un mese che ha 89 eventi in agenda**, mentre ottobre ne ha 6: la
sezione qui sotto resta l'unica cosa urgente di tutto questo export.

#### Il 28 agosto rompe i mille, ed è un venerdì

Export del 30/08/2026, finestra **01-28/08** (28 giorni): **11.823 clic, 151.851
impressioni, CTR 7,79%, posizione 6,13**. Il giorno è questo:

| giorno | clic | impressioni | CTR | pos |
|---|---|---|---|---|
| sab 8/8 | 603 | 6.112 | 9,87% | 6,0 |
| sab 15/8 (Ferragosto) | 787 | 11.685 | 6,74% | 6,2 |
| sab 22/8 (vecchio record) | 829 | 11.493 | 7,21% | 6,1 |
| **ven 28/8** | **1.015** | **11.831** | **8,58%** | **6,0** |

Primo giorno a quattro cifre, **+22% sul record precedente e +76% sul venerdì
prima** (577). E vale la regola del consolidamento all'indietro già scritta:
il 28 è l'ultimo giorno dell'export, quindi **vale probabilmente ~10% in più**
di quello che dice — il record vero sta intorno a 1.100.

**Il sabato non è ancora nell'export**, ed è la domanda che viene subito dopo.
Search Console ha due-tre giorni di ritardo, quindi il 29 si legge il 1°
settembre e non prima. Quello che si può dire adesso: in quattro settimane il
sabato ha battuto il proprio venerdì **tre volte su tre** (8>7, 15>14, 22>21),
con rapporti fra 1,05 e 2,24. Applicati a 1.015 danno una forchetta larghissima
— 1.070-2.200 — cioè **non si stima, si aspetta l'export**. La sola cosa che il
dato dice è la direzione.

**La notizia però non è il picco, è il pavimento: la settimana feriale è
raddoppiata.** Confronto fra giorni omologhi, l'unico onesto:

| | 17-21/08 | 24-28/08 |
|---|---|---|
| lun-ven | 1.821 | **3.062** (+68%) |
| mar-mer-gio | 812 | **1.652** (+103%) |

Il 21/08 qui era scritto che il pavimento feriale «non si era mosso» (-5% sui
martedì). Adesso si è mosso, e in su. **Questa è la risposta alla scommessa del
15 settembre**, con due settimane d'anticipo: la tabella delle soglie dà «sopra
150 clic/giorno = non c'è più una stagione da temere» e i feriali del 25-27
agosto fanno 513, 521 e 618. La riga è la terza, con un margine di tre volte.

E non è più agosto a spiegarlo: in agenda al 30/08 restano **50 eventi in agosto
contro 122 a settembre**. Il picco del 28 arriva mentre la stagione delle sagre
sta finendo, non nel suo mezzo.

Le quote per famiglia non si muovono di nulla (schede 74,6%, `sagre-provincia-*`
11,3%, `eventi.html` 6,1%), e **il buco di `eventi.html` cresce ancora**: 26.797
impressioni al 2,71%. È la quarta lettura consecutiva in crescita — 19.563 →
20.973 → 22.847 → **26.797** — sempre intorno al 2,7%.

##### Le AI features: 11,7% delle impressioni, e l'export non dice i clic

Prima lettura del file **Prestazioni su Funzionalità AI generativa** (stesso
giorno, stessa finestra). La cosa da sapere prima di citarlo: **porta solo le
impressioni, non i clic.** Quindi la domanda che tutti fanno — «le AI Overviews
ci rubano il traffico?» — in questo file **non ha risposta**, e chi la trova
l'ha dedotta.

**17.717 impressioni su 151.851, cioè l'11,7%**, quasi tutte italiane (17.504) e
di telefono (15.265). La quota **sale**: 8,4% il 15 agosto, 13,6% il 28.

L'indizio indiretto è che non stanno facendo danno, ed è controintuitivo: **le
schede con la quota AI più alta hanno il CTR più alto del sito.**

| scheda | quota AI | CTR |
|---|---|---|
| Belforte Monferrato | 29,6% | 14,12% |
| Castel Boglione | 26,6% | **27,30%** |
| Carpeneto | 26,3% | 16,98% |
| `/eventi.html` | **6,9%** | 2,71% |

L'ultima riga è la più interessante: la pagina più esposta alle query generiche
è **la meno presa** dalle AI features. Cioè le funzionalità AI seguono il nome
proprio, come tutto il resto del sito — e il fossato regge anche lì. Non è una
prova (senza i clic non lo può essere), è l'unica cosa che il file permette di
dire, e va detta con quella cautela.

##### La zucca si accende, e il brand raddoppia da niente

Sulle 1.000 query visibili (3.237 clic, il 27% del traffico): `halloween`,
`castagn`, `presep`, `natal`, `fungh` **zero**, come nei tre export precedenti.
Ma `zucca` fa **6 query per 622 impressioni** (era 3 per 173 il 24/08), `vendemm`
2 per 55, `tartufo` 1 per 17. **È il primo segnale d'autunno che si muove**, ed
è puntuale rispetto alla tabella delle scadenze: la domanda si accende prima
dell'evento, e le schede devono esserci prima della domanda.

Il brand: **`daop` fa 10 clic su 14 impressioni**, contro 4 su 7 dell'export
precedente. Raddoppia e resta niente in assoluto — ma la curva che il 24/08 era
«piatta a zero» ha smesso di esserlo. Si rilegge a ogni export, come già scritto:
è il KPI del cavallo di Troia, e si guarda la curva, non il valore.

#### L'imbuto si è accorciato, e ottobre è vuoto

Questo sì è un allarme, ed è l'unico di questo export. Al 24/08 l'agenda viva ha
**89 eventi in agosto, 87 a settembre, 6 a ottobre, 1 a novembre, 1 a dicembre**.
Settembre si è riempito (era 59 il 14/08, +28 in dieci giorni); **ottobre no**:
era 4, adesso è 6.

E il preavviso della fonte si è **accorciato**: sulle 203 schede nate dal 10/08
la mediana fra comparsa della riga e data dell'evento è **7 giorni** (p90 26),
contro i 10,5 misurati sul backfill. Sette giorni di preavviso contro la tabella
delle scadenze già scritta qui sopra — *schede di Halloween entro il ~10
ottobre* — vuol dire che **il ritmo naturale della fonte non ci arriva**, e non
di poco: porterebbe le righe verso il 24 ottobre.

Non è un problema di codice e non si risolve nel generatore: è raccolta, e va
fatta apposta. La finestra utile per non perdere Halloween 2026 si apre **adesso**
e si chiude a inizio ottobre.

**Al 30/08 non è cambiato niente, e sono sei giorni in meno.** L'agenda viva ha
**50 eventi in agosto, 122 a settembre, 7 a ottobre**, 1 a novembre, 1 a
dicembre: settembre ha preso altre 35 righe in sei giorni, ottobre **una**. Nel
frattempo l'export dice che la domanda d'autunno comincia ad accendersi (`zucca`
622 impressioni). È l'unica cosa urgente di questi export, per la terza volta di
fila, e la scadenza del ~10 ottobre è più vicina di sei giorni.

#### Il CTR del giorno dopo una festa non è il CTR del sito

Il 16/08/2026 il sito fa 551 clic su 8.725 impressioni, CTR 6,32%, cioè due punti
sotto l'8,09% dei tre mesi. Sembra un peggioramento e non lo è: quello che si
misura il giorno dopo Ferragosto è in buona parte **la coda di impressioni degli
eventi appena finiti**. Incrociando le pagine dell'export con le date in
`data/pagine-evento.json`:

| | clic | impressioni | CTR |
|---|---|---|---|
| schede di eventi **già conclusi** | 68 | 1.237 | **5,50%** |
| schede **in corso o futuri** | 199 | 1.563 | **12,73%** |

Più di due volte il CTR, a parità di template e di sito. Sommando `ferragosto.html`
fanno **2.551 impressioni su 9.294 (il 27%) per 90 clic su 558**: un quarto delle
impressioni della giornata è gente che cerca cose che non ci sono più.

**Non è un difetto da riparare**, ed è importante saperlo prima di provarci: la
description di ogni scheda stampa la data ("Mercoledì 12 agosto 2026 ad
Entracque"), quindi chi cerca il 16 legge il giorno e non clicca. Il CTR basso lì
è il sistema che funziona. Le tre serate del Food Village di Entracque — 12, 13 e
14 agosto, tre sotto-eventi con tributi diversi — sommano 443 impressioni e 9
clic per questo motivo, e non perché si cannibalizzino: sono già differenziate nel
title e nella description, e Google mette in cima quella dal nome generico sulla
query generica, che è la cosa giusta.

Da qui la regola di lettura: **il CTR aggregato del giorno dopo un picco
stagionale non si confronta con niente.** Se serve un numero confrontabile, si
segmenta per data di fine evento come sopra, oppure si aspetta una settimana. E
non si riscrive un title guardandolo: `ferragosto.html` crolla a 1,67% quel
giorno con lo **stesso** title che tre giorni prima faceva 6,50% alla stessa
posizione — e dal 17 agosto va comunque in `noindex` da sola.

**Quella segmentazione non si rifà su un export a tre mesi.** Ripetuta sul
trimestre 16/05-15/08 dà 8,99% per gli eventi conclusi contro 11,01% per quelli
in corso o futuri: due punti, non i sette del singolo giorno. Non è una smentita,
è che su tre mesi i clic di un evento oggi concluso sono stati quasi tutti
raccolti quando era ancora futuro, quindi finiscono nella colonna sbagliata. **La
prova vale su una finestra corta e su niente altro**; se un giorno il numero
sembra ridimensionato, è questo, non un cambio di comportamento.

Due cose sull'export in sé, che fanno sbagliare i conti. **I fogli non sommano
uguale**: nello stesso file Grafico, Paesi e Dispositivi danno 551/8.725, Pagine
dà 558/9.294 e Query 122/2.212, perché l'anonimizzazione lavora per dimensione.
Il totale del sito è quello dei primi tre; una percentuale che mescola due fogli
è sbagliata. E **il traffico estero è il 10% delle impressioni**, non solo il
Regno Unito: 856 impressioni per 5 clic fra UK (407), Paesi Bassi (151), Germania
(90), Stati Uniti (38). Togliendolo il CTR italiano è **6,94%** invece di 6,32%.
Non c'è niente da fare — si segmenta per Italia quando il CTR serve a decidere.

Sul trimestre chiuso al 15/08 l'estero è **5.202 impressioni per 41 clic**, l'8%
delle impressioni (UK 2.170, Paesi Bassi 1.060, Germania 627, USA 328): quasi
niente clic e in crescita rapida, quindi si mangia sempre più CTR aggregato.
Italia sola: **8,11%** invece di 7,53%.

Sulle quattro settimane al 21/08 è **6.749 impressioni per 60 clic**, il 7,4%
delle impressioni — e dentro c'è una voce sola che vale la pena conoscere: il
**Regno Unito fa 2.927 impressioni e 4 clic, cioè lo 0,14% di CTR**, da solo il
3,2% delle impressioni del sito. Non è pubblico e non lo diventerà: è un motore
che ci mostra a chi cerca in inglese qualcosa che assomiglia ai nostri nomi.
Italia sola: CTR **8,57%** invece dell'8,00% aggregato. Quando il CTR serve a
decidere qualcosa, si segmenta — e il divario fra i due numeri cresce ogni mese.


Un avviso sui file, che è costato mezz'ora: **il nome dell'export non dice la
finestra.** Il file scaricato il 16/08 e citato qui sopra come "24 ore" non è
quello che sta in `Downloads` con quella data — quello è un tre mesi da 92 giorni
che chiude al 14/08 (4.170 clic). La finestra si legge **solo nel foglio
`Filtri`**, e il giorno di chiusura solo nell'ultima riga di `Grafico`. Si
guardano quei due prima di confrontare due export.

#### Le schede passano il giudizio di Google, e si vede in un numero solo

Il rapporto **Indicizzazione → Pagine** di Search Console (export del 15/08, che
chiude al **7 agosto**: ha otto giorni di ritardo contro i due-tre delle
Prestazioni) dice 112 pagine indicizzate e 19 no. Le 19:

| | pagine | |
|---|---|---|
| Rilevata, ma non ancora indicizzata | 7 | coda di scansione |
| **Scansionata, ma non indicizzata** | **10** | le ha lette e non le pubblica |
| Non trovata (404) | 1 | vedi sotto |
| Pagina alternativa con canonical | 1 | normale |

**Le dieci "scansionate ma non indicizzate" sono il termometro dello *scaled
content*, ed è il numero da guardare a ogni export.** Quella riga è il modo in
cui Google dice che ha letto la pagina e non gli è sembrata utile: su un sito che
pubblica centinaia di pagine su template identico ce ne starebbero centinaia.
Dieci su 131 vuol dire che il giudizio sulle schede una-per-evento è **positivo**
— ed è la prima misura, invece che un ragionamento, a sostegno della decisione di
`luoghi.html` (una pagina filtrabile invece di 800 schede). Se un giorno quel
numero cresce di decine, il posto dove si è esagerato è quello.

Due cose da sapere prima di rileggerlo. Chiudendo al 7 agosto **non dice ancora
niente** su `luoghi.html`, `halloween.html` e le sei d'incrocio, tutte nate fra
il 12 e il 14: vanno guardate dal 22-25 agosto. E c'è uno scarto non spiegato del
tutto — 112 indicizzate al 7 agosto contro **264 pagine con impressioni**
nell'export Prestazioni, che il ritardo giustifica solo in parte (il conteggio
cresce a scalini: 9 → 86 il 25 luglio → 112 il 6 agosto). Le impressioni
coincidono fra i due export, quindi non è un allarme, ma è la prima cosa da
riguardare al giro dopo. Nota: quel salto a 86 è del **25 luglio**, una settimana
prima del 02/08 che questo file dà come nascita del sistema — una delle due date
è imprecisa, e `data/pagine-evento.json` è l'unico posto per verificarlo.

**Il 404 è `/ilpiattosano.html`, ed era già a posto.** Lo stub di redirect verso
`/piattosano.html` esiste nel repo (`noindex, follow`, meta refresh e
`location.replace`), ma l'ultima scansione di Google è del **12 luglio**: la
pagina si era spostata il 16 giugno e lo stub è arrivato dopo, quindi Googlebot è
passato proprio nella finestra in cui il 404 c'era davvero. Non c'è niente da
riparare nel generatore — si chiede la **convalida della correzione** in Search
Console e Google ripassa.

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

##### Ma lo slug si ricava dal nome, e il nome lo scrive un modello

Chiuso il 30/08/2026, partendo da una domanda di Patrick: *«dobbiamo beccare lo
stesso nome per aggiornare la pagina — riusciremo?»*. Era la domanda giusta, e
la risposta misurata era **no**.

`slug_evento()` toglieva l'anno e il numero di edizione in cifre, ma lo slug
resta una funzione del **nome scritto nel foglio**, e quel nome non lo batte una
persona: lo scrive `daop_pipeline.py` facendo **leggere la locandina a un
modello**. Cambia due cose, e vanno tenute distinte:

- **la deriva è correlata, non sparsa.** La coda `- Organizzatore` non compare a
  caso: è la convenzione che il prompt di visione impone (`"titolo del singolo
  appuntamento - Organizzatore"`). Quindi o c'è su tutte o non c'è su nessuna, e
  il giorno che il prompt o il modello cambiano si spostano **107 indirizzi
  insieme**. È lo scenario peggiore, ed è per questo che la misura qui sotto è
  fatta proprio su quello — tutte le code che cadono nello stesso momento.
- **la leva vera è a monte, e non è in questo repo.** Un nome che torna uguale
  si ottiene dal prompt, o passandogli il nome dell'edizione precedente. Il
  downloader gira sul PC di Patrick: da qui non si tocca, e il riaggancio è
  quello che si può fare da questa parte.

Due buchi, misurati sul registro:

| | quante | il caso che costa |
|---|---|---|
| coda dell'organizzatore nel nome (`- Pro Loco Grondona`) | **107 su 412** | Grondona, **490 clic, la prima pagina del sito** |
| numero di edizione in **numeri romani** (`XXVII`) | 1 su 412 | Belforte, 265 clic, quarta per impressioni AI |

Uno su quattro dei nomi in registro, e fra le 40 schede più visitate sono cinque
— ma dentro ci sono la prima e la quarta. **Il difetto è raro ovunque tranne che
dove costa.**

**La correzione non è irrigidire il nome, è smettere di pretenderlo identico.**
Il nome non deve tornare *uguale*, deve tornare *riconoscibile*: un evento il cui
slug è nuovo si confronta con le pagine già in registro (`candidati_edizione()`),
e se ne trova **una sola** che è evidentemente la stessa cosa, riusa quel
vecchio slug. Le tre condizioni, e la terza è quella che regge tutto:

1. **stesso comune** — sta già dentro lo slug;
2. **stesso periodo dell'anno**, ±30 giorni circolari: una patronale segue il
   santo e una sagra il raccolto, si spostano di un weekend, non di una stagione;
3. **un solo candidato.** Se sono due non si sceglie — è la regola già scritta
   per `_erede()`, e il caso ambiguo esiste davvero: a Rocchetta Tanaro cinque
   «Apertura Stand Gastronomico con \<nome della band\>» hanno le stesse parole e
   le stesse date. Sbagliare aggancio vuol dire **scrivere l'edizione di un
   evento sopra la pagina di un altro**, che è molto peggio di una URL nuova.

Uno slug già rivendicato da un altro evento **della stessa run** non è un
candidato: è la guardia che tiene fuori i sotto-eventi di una manifestazione,
che stanno in pagina tutti insieme e non hanno niente da riagganciare.

**Nessuna URL si sposta, e questa è la parte da non rifare al contrario.** La
prima idea era normalizzare di più lo slug — togliere anche la coda
dell'organizzatore — e migrare le 107 pagine con il timbro `spostata`. È
sbagliata: per riparare un difetto che colpisce fra dodici mesi, sposterebbe
**oggi** 107 indirizzi indicizzati, cioè farebbe di sicuro il danno che vuole
evitare. Il riaggancio lo fa a costo zero, una volta l'anno, e solo dove serve.
Belforte tiene il suo `xxvii-` per sempre — un numero sbagliato in una URL non
si vede e non pesa, l'anzianità sì. Il romano si toglie **solo dalle pagine che
nascono da domani**, e solo in testa al nome: cercarlo dappertutto mangerebbe il
`II` di «A Calosso Museo e Dintorni - Settembre II», e senza il vincolo del
maiuscolo `Il`, `Di` e `Mi` sono tutti numeri romani validi.

**Quanto regge, misurato sul registro vero simulando i nomi del 2027** (numero di
edizione aumentato e coda dell'organizzatore caduta):

| | schede |
|---|---|
| tengono lo slug da sole | 306 |
| **riagganciate** | **78** |
| ambigue → pagina nuova, come oggi | 6 |
| **agganci sbagliati** | **0** |

Riscrivendo il nome più pesantemente — una parola significativa in meno — se ne
perdono 171 su 390: **è il limite dichiarato**, e il modo di non arrivarci è
scrivere i nomi nel foglio come l'anno prima. Il ripiego quando il riaggancio non
scatta non è un guasto: è una URL nuova, cioè esattamente quello che sarebbe
successo comunque.

**La prova gira ogni notte in CI anche se la cosa che difende capita una volta
l'anno**, ed è l'unica del repo fatta per un guasto che si vedrebbe fra dodici
mesi: `scripts/prova_riaggancio.py`, offline, due secondi, dopo il commit come
`valida_pdf.py` — quindi non può fermare il deploy. Una prova a mano, qui, sarebbe
marcita prima di servire. L'invariante che difende non è «riaggancia tutto», è
**«nessuna edizione scrive sulla pagina di un altro evento»**: la prima è una
percentuale che può scendere senza che niente sia rotto, la seconda è un danno.

**E non è un problema del 2027: succede gia' adesso.** Se lo stesso volantino
viene letto due volte, esce con due frasi diverse — nel registro del 30/08/2026
sono **cinque coppie**, stesso comune e stesso identico giorno: «Apertura Stand
Gastronomico **con** Shary Band» e «… **e** Shary Band» (Rocchetta Tanaro, tre
serate, cioè **sei pagine per tre eventi**, e tutte e sei vive), «Casalnoceto
Kids» con e senza «- Comune di Casalnoceto», «Ciao Ciao Estate! Sorprese per
Tutti» e «Laboratorio: Ciao Ciao Estate… Sorprese per Tutti!».

`segnala_doppioni()` non le vedeva, e per una ragione precisa: **confronta lo
slug esatto**, cioè riconosce la riga *copiata* e non la riga *riletta*. Ora
`_doppioni_riscritti()` fa lo stesso confronto del riaggancio (`_chiave_nome` +
soglia) ma con la finestra a **zero giorni** — stesso comune e stessa data di
inizio. Con una finestra larga prenderebbe le serate diverse della stessa sagra,
che doppioni non sono. Si **segnala e basta**, come per i doppioni esatti: unire
due righe è una decisione editoriale e si prende nel foglio.

La prova su questo **non conta le coppie di oggi**: sarebbe rossa il giorno che
Patrick pulisce il foglio, cioè quando il sito fa la cosa giusta — è la sesta
volta che quel tipo di prova si sarebbe rotta da sé. Controlla il
comportamento: due letture dello stesso volantino sono un avviso, due eventi
diversi nello stesso giorno no, una ricorrenza no, due serate della stessa sagra
no.

Un caso vero trovato scrivendola, che sembrava un aggancio sbagliato e non lo
era: nel foglio lo stesso laboratorio di Crissolo è finito su **due righe**, una
poi ritirata. L'edizione 2027 di quella ritirata va sulla gemella viva — ed è la
cosa giusta, perché una pagina ritirata è un cartello, non una pagina da
aggiornare. Per questo le ritirate e le spostate stanno fuori **sia** dai
candidati **sia** dalla simulazione della prova.

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

E la domanda d'autunno non è un'ipotesi, è già nell'export — query
stagionali con impressioni mesi prima dell'evento: `sagra della zucca castelletto
monferrato` in posizione 3,5, il grappolo `sagra zucchino rivalta bormida` (sette
varianti, 16 impressioni) fra 4,0 e 8,3, `fiera del tartufo san sebastiano curone
2026`, `fiere e mercatini in provincia di cuneo domani` in posizione 1. Zero
clic perché l'evento è lontano, ma Google ci ha già messi lì. Ottobre e novembre
in Piemonte sono castagne, funghi, tartufo, vendemmia, Halloween nei castelli,
mercatini, presepi viventi: **il sito non va in letargo, e non è la stagione la
cosa da temere.**

#### Quello che cambia in autunno è il tipo di query, non il calendario

Sulle 1.000 query visibili dell'export a tre mesi (che sono il 21% dei clic, il
resto Google lo anonimizza):

| | query | clic | CTR |
|---|---|---|---|
| **nome proprio** (`festa cassinasco 2026`) | 535 | 610 | **9,71%** |
| **generiche** (`sagre provincia alessandria oggi`) | 465 | 121 | 2,86% |

L'83% dei clic visibili viene dai nomi propri, a tre volte e mezzo il CTR. È lì
che non abbiamo concorrenza, e **il fossato si porta dietro quasi tutto
l'autunno**: carnevali, presepi viventi, sagre della castagna e del tartufo hanno
tutti il nome del paese attaccato, cioè sono la stessa partita di agosto.

Rifatta sull'export del 17/08 la proporzione tiene — **77% dei clic dalle query
che contengono un nome di posto** — ma il conto è stato fatto cercando i comuni
noti nella query, non a mano, quindi frazioni e nomi di piatto (`sagra merella`,
`sagra del cinghiale`) cadono nella colonna sbagliata e il vero valore è più alto.
**Le due cifre non si confrontano fra loro**: dicono la stessa cosa con due metri
diversi.

Si porta dietro molto meno **Halloween** e **"mercatini di Natale in Piemonte"**:
lì la query è nazionale e generica, cioè la colonna in cui stiamo in posizione
8-10 al 2,86%. Il rischio d'autunno non è che manchino gli eventi, è che una
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

Il sintomo sembra un guasto: in **tre mesi** `/eventi/oggi.html` ha preso 12
impressioni e 1 clic, `/eventi/weekend.html` 16 impressioni e **zero** clic —
mentre le query di quell'intenzione esistono e sono grosse (`sagre provincia di
alessandria oggi` da sola: 410 impressioni, 11 clic, posizione 8,26). Non è un
guasto: sono `index, follow`, con canonical proprio, in sitemap, linkate dalla
nav di 266 pagine. Un clic in novantadue giorni non è una pagina debole, è una
pagina che Google ha deciso di non mostrare.

La causa è che **`eventi.html` rivendica già quell'intenzione, e la rivendica
meglio**: title `Eventi e Sagre Oggi in Provincia di Alessandria, Asti, Cuneo`,
H1 `Sagre ed eventi oggi e questo weekend`, 286 `Event` in JSON-LD, 1,4 MB di
contenuto, tutta l'autorità del sito. Google consolida su di lei, e fa la cosa
giusta.

**La scorciatoia da non prendere è togliere "oggi" e "weekend" dall'H1 o dal
title di `eventi.html` per de-cannibalizzare.** È la stessa regola già scritta per
la riga stagionale, con la stessa aritmetica: quell'H1 vale 19.563 impressioni,
cioè il **30%** delle impressioni del sito, e si rinuncerebbe a un asset provato
per sbloccare due pagine che in tre mesi ne fanno 39. Nemmeno una prova A/B lo
giustifica: il rischio è asimmetrico.

Il problema che resta non è *quale* pagina ranka, è che **qualunque pagina ranki,
ranka in posizione 8-10**. Le query generiche sono il 40% delle impressioni
visibili e solo il 17% dei clic, con CTR 2,86%. Ed è la domanda che **non scade
mai**: torna ogni weekend, tutto l'anno, Halloween e Natale compresi. Ed è anche
quella su cui `eventi.html` lascia sul tavolo 19.563 impressioni al 2,49%.

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

#### Le sei pagine d'incrocio, e perché `oggi.html` è diventata un indice

Fatte il 14/08/2026. `spec_incrocio()` genera
`/eventi/oggi-provincia-<nome>.html` e `/eventi/weekend-provincia-<nome>.html`
per le tre province: **sei pagine, insieme chiuso**. Non è *scaled content* per
la stessa ragione delle 12 pagine comune — il numero non cresce coi dati — e a
differenza delle pagine d'incrocio ipotizzate per `luoghi.html` qui la domanda
era già misurata prima di scrivere una riga.

Le decisioni dentro, che è quello che non si ricava dal diff:

- **`oggi.html` e `weekend.html` non sono state assorbite: sono diventate
  l'indice delle sei.** Sopprimerle avrebbe voluto dire cancellare due URL in
  sitemap e nella nav di 266 pagine per guadagnare niente — su GitHub Pages un
  redirect è un `<meta refresh>`, cioè il peggiore dei mondi. Come indice hanno
  un mestiere che non si sovrappone a nessuno: la query trasversale la vince
  `eventi.html` comunque, e non gliela togliamo.
- **L'H1 ora nomina le province** su tutte e otto. Era il punto 3 della vecchia
  lista ed era bloccato finché non si decideva il destino delle due madri: metà
  della query è il posto, e prima stava solo nel `<title>`.
- **`robots` si decide sulla finestra di 30 giorni, non sugli eventi di oggi**
  (`FINESTRA_INCROCIO`). È la parte che sembra un dettaglio e non lo è: "oggi in
  provincia di Cuneo" passa da 0 a 6 e torna a 0 nel giro di una settimana, e un
  `robots` che cambia ogni notte è peggio di uno sbagliato — Google smette di
  fidarsi della direttiva e la pagina si ricommitta tutti i giorni. Con la
  finestra larga entra in indice a stagione aperta e ne esce a stagione chiusa,
  una volta sola per verso. Il contenuto invece resta quello di oggi, e quando
  oggi è vuoto la pagina lo scrive e mostra i primi in arrivo.
- **Niente tendina provincia** (`con_prov=False`): la pagina *è* una provincia,
  come le `sagre-provincia-*`.
- **Le briciole hanno un quarto gradino** — queste pagine stanno *sotto*
  `/eventi/oggi.html`, non accanto — e non entrano in `link_landing()`: quella
  riga si stampa su ~290 pagine e sei voci in più la trasformerebbero in una
  barra che non guarda nessuno. I link arrivano dalle due madri, dalle sorelle,
  e dalla `sagre-provincia-*` della stessa provincia.

**Come si sa se hanno funzionato, e quando.** Il metro non era "quanti clic fanno
le sei": era se **la somma incrocio + `oggi` + `weekend` superasse le 28
impressioni in tre mesi** che facevano le due madri da sole. Se le sei prendevano
impressioni e le madri restavano a zero, voleva dire che il problema era
l'incrocio mancante e non l'intenzione; se restavano tutte a zero, che Google
consolida su `eventi.html` qualunque cosa si scriva, e allora il lavoro si
spostava sul CTR di quella pagina invece che su nuove URL.

#### Verdetto: ha funzionato, e di due ordini di grandezza

Export del 16/08/2026, finestra 15/08 18:00 → 16/08 17:00 (24 ore):

| | clic | impressioni |
|---|---|---|
| le tre `weekend-provincia-*` | 90 | 1.003 |
| le tre `oggi-provincia-*` | 9 | 504 |
| **totale incrocio** | **99** | **1.507** |
| `oggi.html` (madre, ora indice) | 0 | 3 |
| `weekend.html` (madre, ora indice) | 0 | 0 |

**1.507 impressioni in ventiquattr'ore** contro le 28 in tre mesi delle due madri:
~54× la baseline trimestrale in un giorno solo. Le madri restano a zero e fanno
l'indice, che è il ruolo che gli era stato dato. L'esperimento si chiude qui: il
buco era l'incrocio provincia × finestra, non l'intenzione.

**La trappola nel leggere questo numero**, ed è quella in cui si è quasi caduti:
le `oggi-` sembrano "rotte" rispetto alle `weekend-` — 1,79% di CTR contro 8,97%,
cinque volte meno. Non lo sono, ed è un divario di **posizione**, non di snippet:

| provincia | `oggi-` | `weekend-` |
|---|---|---|
| Alessandria | pos 8,25 → 2,78% | pos 5,78 → 12,14% |
| Asti | pos 8,10 → 1,46% | pos 5,89 → 9,15% |
| Cuneo | pos 10,74 → 1,91% | pos 7,56 → 5,90% |

Su mobile la curva dà ~2% a posizione 9-10 e ~7-9% a posizione 6: sono **tutte e
sei sulla curva**. Prima di dare la colpa a un title, si guarda la posizione — e
qui il title la data ce l'ha già, la stampa `data_estesa(oggi)` dentro `descr`,
e la pagina si rigenera ogni notte. "Contenuto stantio" è escluso dal codice, non
da un'impressione.

E il 15-16 agosto è **sabato e domenica**: nel weekend "oggi" e "weekend" sono la
stessa intenzione e vince la pagina che copre due giorni. È il giorno peggiore
dell'anno per confrontare quelle due famiglie di pagine. Se un giorno si vuole
misurare davvero il divario, si prende un mercoledì.

**Confermato su giorni interi, e il verdetto non cambia.** L'export a tre mesi del
17/08 (16/05-15/08) contiene le sei pagine per i loro primi due giorni interi, 14
e 15 agosto:

| | clic | impressioni | CTR | pos |
|---|---|---|---|---|
| `weekend-provincia-alessandria` | 52 | 568 | 9,15% | 6,09 |
| `weekend-provincia-cuneo` | 29 | 336 | 8,63% | 6,63 |
| `weekend-provincia-asti` | 19 | 271 | 7,01% | 6,18 |
| `oggi-provincia-alessandria` | 6 | 158 | 3,80% | 8,27 |
| `oggi-provincia-asti` | 4 | 292 | 1,37% | 7,79 |
| `oggi-provincia-cuneo` | 1 | 120 | 0,83% | 10,78 |
| **totale incrocio** | **111** | **1.745** | 6,36% | 7,01 |
| le due madri | 1 | 39 | | |

Il divario `oggi-`/`weekend-` sembrava di nuovo tutto di posizione, e il
**mercoledì mancava**: il 14 è venerdì e il 15 sabato, quindi anche quella misura
cadeva nel giorno peggiore.

##### Coi feriali dentro, un pezzo di divario resta e non è la posizione

Export del 24/08 (25/07-21/08): le sei pagine hanno otto giorni interi, e stavolta
dentro ci sono martedì, mercoledì e giovedì.

| | clic | impressioni | CTR | pos |
|---|---|---|---|---|
| `weekend-provincia-alessandria` | 100 | 1.114 | 8,98% | 6,42 |
| `weekend-provincia-asti` | 46 | 576 | 7,99% | 6,25 |
| `weekend-provincia-cuneo` | 32 | 583 | **5,49%** | **8,67** |
| `oggi-provincia-asti` | 20 | 960 | **2,08%** | **8,21** |
| `oggi-provincia-alessandria` | 7 | 246 | **2,85%** | **8,90** |
| `oggi-provincia-cuneo` | 14 | 581 | 2,41% | 10,70 |
| **totale incrocio** | **219** | **4.060** | 5,39% | — |
| le due madri | 3 | 76 | | |

Le tre righe in grassetto sono il punto: stanno **alla stessa posizione**, fra
8,21 e 8,90, e la `weekend-` converte al 5,49% mentre le due `oggi-` fanno 2,08%
e 2,85%. **Circa il doppio, a parità di posizione.** La spiegazione "è tutto
posizione" scritta il 17/08 andava bene finché la misura era fatta su un venerdì e
un sabato; coi feriali dentro non basta più.

Non se ne ricava però il rimedio, e la scorciatoia da non prendere è riscrivere il
title. L'ipotesi più economica è che la promessa sia diversa: "oggi" impegna a
avere qualcosa **stasera**, e di martedì spesso non c'è — chi legge lo snippet lo
sa prima di cliccare. Se è così il divario è onesto e non si chiude con le parole.
Prima di toccare qualcosa serve la sola misura che manca ancora: **il CTR di
quelle pagine in un giorno feriale isolato**, che questo export aggrega e non
mostra. Fino ad allora, quello che si può dire è che il divario esiste ed è più
grande di quanto la curva delle posizioni giustifichi.

Quello che **non** cambia è il verdetto sull'esperimento: 219 clic e 4.060
impressioni in otto giorni contro le 28 impressioni in tre mesi delle due madri.
Il buco era l'incrocio provincia × finestra, e le madri fanno l'indice.

### Le `sagre-provincia-*` mostrano anche quello che sagra non è

Fatto il 29/08/2026, partendo da un'obiezione di Giovanni: «dovremmo fare delle
pagine di provincia» — quelle ci sono, ma sono **filtrate per sagre**, e aveva
ragione lui. `spec_sagre()` tiene solo `bucket(e)[0] == 'feste'`, e a Cuneo
quel filtro butta via l'80% dell'agenda: su 74 eventi le sagre sono 16, il
resto sono laboratori (23), cultura (19), sport, musica, spettacoli — cioè quasi
tutto il lavoro del curatore.

**La cosa che veniva in mente per prima — una `/eventi-provincia-<nome>.html` —
non si fa**, e il motivo sta nell'export GSC del 26/08/2026 (tre mesi):

| query provinciali | query | clic | impressioni |
|---|---|---|---|
| con dentro "oggi" / "weekend" | 107 | 148 | **4.953** |
| **senza finestra temporale** | 19 | 8 | **511** |

Le prime hanno già le sei pagine d'incrocio. Le seconde — cioè tutto quello che
una pagina nuova andrebbe a prendere — valgono 170 impressioni al mese. E le
categorie che oggi restano fuori **non hanno una domanda propria**: `laborator`,
`teatro`, `musei`, `sport`, `natura`, `gita` fanno **zero** impressioni
nell'export; `bambin` ne fa 74 in tre mesi. È la stessa cosa già scritta nella
memoria del cavallo di Troia, misurata di nuovo un anno dopo.

Una terza pagina provinciale sarebbe quindi una URL nuova che si contende le
query delle altre due — lo stesso nodo già descritto in `spec_incrocio()` fra
`oggi-provincia-*` e `sagre-provincia-*` — per una domanda che non c'è. In rete
quella query ce l'ha già un dominio a corrispondenza esatta
(`eventiinprovinciadicuneo.it`), più Cuneodice e Virgilio: è la partita
generica, quella che perdiamo, non quella del nome proprio.

**Quello che si è fatto invece è distribuzione, non una pagina.** In coda a
`sagre-provincia-*`, dopo il calendario delle sagre e le ricorrenti, c'è
«Non solo sagre: gli altri appuntamenti in provincia di X» con il resto
dell'agenda di quella provincia. Il conto che l'ha decisa:

| pagina | clic | impressioni | pos |
|---|---|---|---|
| `/sagre-provincia-cuneo.html` | **405** | 4.503 | 6,86 |
| `/eventi/weekend-provincia-cuneo.html` | 32 | 604 | 8,73 |
| `/eventi/oggi-provincia-cuneo.html` | 16 | 855 | 10,36 |

I 58 eventi non-sagra di Cuneo stavano sulle due pagine che insieme fanno 48
clic in tre mesi. Adesso stanno anche su quella che ne fa 405.

Le decisioni dentro, che non si ricavano dal diff:

- **Title, H1, canonical e `descr` non si toccano.** Sono la query che la
  pagina vince: il blocco aggiunge contenuto, non riscrive l'identità della
  pagina. È la stessa regola dell'H1 di `eventi.html` che non si tocca per la
  stagione, e la tentazione da fermare è «già che ci siamo chiamiamola
  `eventi-provincia-`».
- **Sta in coda, sotto le sagre.** Sopra ci va quello per cui la gente è
  arrivata. Stessa aritmetica dell'invito al canale, verso opposto.
- **Il `robots` continua a decidersi sulle sole sagre** (`len(sagre) + len(ric)`
  contro `MIN_LANDING`): una provincia con zero sagre e venti laboratori non è
  una pagina di sagre da indicizzare. Per lo stesso motivo il JSON-LD e il
  numero nel log restano quelli delle sagre — `'altri'` si stampa a parte.
- **La tendina delle categorie riceve `sagre + altri_ev`, ed è la regressione
  vera.** Con le sole sagre avrebbe **una voce sola**, quindi `_landing_filtri()`
  non la stamperebbe affatto: il filtro sparirebbe con settanta righe in pagina
  e cinque categorie da separare. Non si vede leggendo l'HTML — si vede solo
  confrontando le `<option>` con i `data-category` delle righe, ed è quello che
  fa la prova.
- **La riga d'apertura nomina solo le categorie che ci sono davvero**
  (`LABELS_PROSA`, ordinate mettendo davanti quelle che hanno già una "e"
  dentro, se no viene fuori «sport e cultura e natura»). È la regola
  dell'occhiello dei corsi: una pagina non promette un dato che la riga sotto
  può non avere. `altro` resta fuori dalla frase e dentro l'elenco.
- **La sezione non ha un `<h3>` suo**: il titolo è l'`<h2>` sopra, ed è quello
  che il JS dei filtri fa sparire insieme al gruppo quando un filtro lo svuota
  (`testaDi()`). Quel meccanismo esisteva da mesi senza nessuna pagina che lo
  usasse — il commento nel codice diceva «costa otto righe e si accorge da solo
  di quando serve»: questo è il caso.

`tests/landing.js` difende cinque cose su Alessandria e su Cuneo, e una delle
prove è nata **sbagliata**: pretendeva che ogni href comparisse una volta sola,
ed è diventata rossa subito — perché una manifestazione di tre giorni ha tre
righe che puntano alla stessa scheda, e il calendario delle sagre fa così da
sempre. L'invariante giusta è più stretta e non può divergere: **nessuna scheda
compare sopra e sotto insieme**, cioè i due elenchi restano complementari. È la
quinta volta che una prova pretende un'uniformità che il sito non ha mai avuto.

Resta aperto un punto solo della vecchia lista: **`Event` in JSON-LD sulle
pagine aggregate.** `oggi.html`, `weekend.html`, le tre provinciali e ora le sei
d'incrocio hanno tutte `CollectionPage` + `ItemList` che *rimanda* alle schede,
e zero `Event`: i rich result eventi li prende solo `eventi.html`, che ne ha 286.
Prima di cambiarlo va verificato che moltiplicare la stessa entità su nove URL
non diluisca invece di aggiungere — è la ragione per cui non è stato fatto
insieme al resto.

**Un foglio "Aspetto nella ricerca" vuoto non è quella verifica**, ed è
l'equivoco da cui questo punto è stato riaperto per sbaglio il 16/08/2026. Non
dice niente sul markup, e infatti il markup sta in piedi — `valida_jsonld.py`
conta 527 `Event` con zero errori, e l'`Event` di una scheda ha `name`,
`startDate`, `location` con `PostalAddress` completo e `geo`, `image`,
`description`, `offers`: è idoneo ai rich result, non uno scheletro.

Qui c'era scritto che un export a **tre mesi** popola quel foglio. **Non è vero**:
è vuoto in *tutti* gli export su disco, compresi i tre mesi dell'11/08, del 16/08
e del 17/08. Non è la finestra corta a spegnerlo — **l'export xlsx non porta
quella dimensione, punto**, e non c'è nessun export che risponda alla domanda.
L'unico posto dove si guarda è il report **Miglioramenti → Eventi** in Search
Console. Finché non c'è quello, "Google non riconosce lo schema" non è una
diagnosi.

Cosa **non** si è fatto per de-cannibalizzare, e non si farà: toccare l'H1 di
`eventi.html`. Vedi sopra, vale 19.563 impressioni.

### "Vicino a me": il raggio filtra, e la posizione non si chiede mai da soli

Fatto il 15/08/2026. La logica sta in **`assets/js/daop-vicino.js`** (15 KB) e
non dentro le pagine: il JS in fondo a `eventi.html` non passa da `_guscio()`
(che copia solo `<style>`, nav e footer), quindi le pagine generate non lo
vedevano, e ricopiarlo nei template sarebbe stato tredici copie da tenere
allineate — la stessa ragione per cui `daop-track.js` è un file solo.

**Dove c'è, e sono 13 pagine**: `eventi.html`, `oggi`, `weekend`, le sei
d'incrocio, le tre `sagre-provincia-*`, `ferragosto`. **Halloween no**, ed è il
comportamento giusto: `_landing_geo()` conta gli eventi *con coordinate* e sotto
`MIN_FILTRI` non stampa niente — a metà agosto quella pagina ne ha 2. Le pagine
comune restano fuori apposta: lì sei già in un comune.

Il modulo **non sa come si nasconde una riga** — l'agenda usa una classe, le
pagine di intenzione l'attributo `hidden` — quindi espone `entro(voce)` e la
pagina lo somma ai propri filtri. Riceve `alCambio` (rifà i filtri della
pagina), `riga` (dove appendere la distanza) e `alRitocco` (l'indice di ricerca
è il `textContent`, che con un centro impostato contiene anche "a 12 km").

Va incluso **senza `defer`**, in coda al body: uno script differito girerebbe
*dopo* i blocchi inline, che invece hanno bisogno di `window.daopVicino`
subito. In `eventi.html` il percorso è relativo come gli altri script suoi,
nelle generate è assoluto.

Il CSS invece si propaga come sempre in ~260 file — sono ~1,5 KB di regole che
usano in 13, ed è il prezzo noto del guscio.

**Il motivo non è "ce l'ha Ginetto": è che il filtro provincia non risponde a
"vicino".** Misurato prendendo Alessandria come punto: dei 128 eventi in
provincia di AL la mediana sta a 25 km e il massimo a **55**, con 23 oltre i 30
km; e **14 eventi entro 25 km sono in provincia di Asti** (Castelnuovo Belbo,
Rocchetta Tanaro, Viarigi, Montemagno). La tendina attuale include il lontano ed
esclude il vicino, in tutti e due i versi. Il raggio non è una funzione in più
accanto a quella: è quella fatta bene.

I dati c'erano già: **278 eventi su 278 hanno lat/lon valide**, e sono le
coordinate del posto, non il centroide del comune (Alessandria ha 6 punti
distinti, Novi Ligure 4). `geo_attrs()` le stampa sulla riga: ~45 byte per riga,
**+18,8 KB su 1,4 MB**. È la lezione dei link calendario al contrario — quelli
erano 490 byte per riga e si sono tolti — ma il rapporto è dodici volte più
basso e senza quelle la funzione non può esistere, perché la distanza non si
deduce dal testo.

Le decisioni, che è quello che non si ricava dal diff:

- **Il raggio filtra, non riordina.** L'agenda è un calendario e l'ordine di un
  calendario è la data: stessa regola già presa per l'app ("su un calendario
  l'ordine non si compra"). `tests/agenda.js` controlla che le righe rimaste
  siano una sottosequenza dell'ordine del generatore — non dell'ordine per data,
  perché le righe "in corso" stanno in cima per gruppo e non per data.
- **La posizione non si chiede mai al caricamento**, solo dopo un tocco. È la
  prassi indicata da W3C e da Chrome, che ha un controllo Lighthouse apposta
  (*Requests the geolocation permission on page load*), e il motivo pratico è
  che **un rifiuto è per sempre**: il browser non ripropone l'avviso, e una
  richiesta sprecata all'arrivo brucia l'unica occasione che c'è. Una prova
  spia `getCurrentPosition` e pretende **zero** chiamate finché nessuno tocca.
- **La sveglia dei 10 secondi non è una cautela, è obbligatoria.** Il `timeout`
  della Geolocation API misura solo l'aggancio della posizione, **non l'attesa
  del permesso**: se l'avviso del browser resta lì senza risposta — il caso più
  comune, non un caso limite — non arriva né successo né errore, e il bottone
  resterebbe "Cerco…" per sempre. Provato, succedeva. Un "consenti" tardivo vale
  comunque: la risposta buona non si butta perché la sveglia era già suonata.
- **`enableHighAccuracy: false`**, e `maximumAge` di 5 minuti. Il gradino più
  stretto è 10 km: un aggancio GPS non aggiunge niente e costa attesa e
  batteria, e una posizione di cinque minuti fa va benissimo — le sagre non si
  spostano.
- **Gradini fissi col conteggio, non uno slider.** Scegliere fra "20 km" e "30
  km" senza sapere che sono 26 e 135 eventi è scegliere al buio. Un gradino
  vuoto resta visibile ma spento: dice che lì non c'è niente, che è una
  risposta, invece di sparire e far ballare la barra.
- **Il raggio di partenza si sceglie sui dati**, non a priori: il primo gradino
  con almeno 5 eventi. Da Cuneo entro 10 km ce ne sono 4 e la pagina nascerebbe
  vuota — è il difetto tipico di questi filtri nelle zone rade, ed è anche il
  motivo per cui a zero risultati la pagina scrive dove guardare ("Niente entro
  10 km. Entro 30 km ce ne sono 40.") invece di lasciare il vuoto.
- **Il ripiego vale più del GPS.** "Parti da un comune" funziona su desktop, per
  chi ha negato il permesso e per chi vuole vedere cosa c'è dove andrà. L'elenco
  si ricava **dalle righe** alla prima apertura — non c'è un marker nuovo e non
  c'è HTML in più per tutti — e il punto di un comune è la media dei suoi
  eventi, che per una misura in linea d'aria basta.
- **Il campo del comune non si chiude quando trova.** La ricerca è viva: chi
  scrive "novi" ha già un centro su un prefisso mentre sta ancora battendo, e
  chiudergli il campo sotto le dita lo lascia con un comune che non ha scelto.
  Svuotare il campo disdice; un comune che in agenda non c'è lo dice, invece di
  restare muto (il catalogo è la pagina, non l'anagrafe — e su una provinciale
  contiene solo i comuni di quella provincia, che è giusto così).
- **I gradini contano dentro gli altri filtri**, non sul totale: la pagina passa
  al modulo il predicato dei suoi filtri, così "30 km (6)" vuol dire sei eventi
  che si vedrebbero davvero, categoria e ricerca comprese.
- **Le distanze sono in linea d'aria e la pagina lo scrive**, insieme al fatto
  che la posizione resta nel browser. Nessuno qui sa quanto gira la strada, e
  far credere il contrario è peggio che non dare la distanza.
- **Una riga senza coordinate non è "lontana", è sconosciuta**: con un raggio
  attivo resta fuori. Il foglio si compila a mano, quindi succede: il 26/08/2026
  erano 2 righe su 188 (Pornassio, Mondovì). `segnala_senza_coordinate()` le
  elenca a ogni run con il numero di riga, accanto ai doppioni e alle durate
  assurde — si riempiono nel foglio, non nel codice.
- **La prova NON pretende il 100%, e il perché conta.** Fino al 26/08/2026
  `tests/agenda.js` e `tests/landing.js` chiedevano che *ogni* riga portasse le
  coordinate, e la run notturna è diventata rossa alla prima cella vuota
  (186/188) mentre il sito faceva esattamente la cosa giusta: `geo_attrs()`
  stampa quello che trova e la riga scoperta resta fuori dal raggio. È lo stesso
  difetto già corretto il 21/08 sulla prova del conteggio nelle quattro porte —
  **una prova che pretende un dato compilato a mano è rossa quando manca il dato,
  non quando c'è un difetto.** Ora la soglia è il **95% delle righe** e le
  scoperte si stampano come nota: la regressione vera — `geo_attrs()` che smette
  di stampare — fa crollare la copertura, non scendere di due righe.
- **Sta fuori dalla barra appiccicosa.** Quella è scesa a ~109px sul telefono e
  una riga in più la farebbe ricrescere per tutto lo scorrimento.

#### Come sta in pagina, e i quattro difetti che aveva

Sistemato il 15/08/2026 guardando gli screenshot a 412px, non il codice. Da
fermo è **una riga sola da 40px**; con un raggio attivo era 176px ed è scesa a
**110px sul telefono e 66px su desktop**. Cosa lo gonfiava, tutto correggibile:

- **Due pillole identiche affiancate** ("Vicino a me" e "Parti da un comune")
  obbligavano a scegliere prima di aver capito. Il ripiego non è un secondo
  comando pari al primo: ora è un testo (`.is-alt`), quindi resta raggiungibile
  senza competere. Attenzione se lo si ritocca: `.ev-geo-btn:hover` ha
  specificità maggiore di `.ev-geo-btn.is-alt`, quindi il bordo va spento anche
  nello stato `:hover`, se no ricompare al passaggio del dito.
- **"da Acqui Terme" accanto a un campo che diceva già "Acqui Terme".** Adesso
  l'etichetta si stampa solo quando il posto non si legge altrove, cioè col GPS.
- **La ✕ cadeva da sola su una terza riga**, perché stava *dopo* i gradini nel
  DOM. Ora sta subito dopo il campo, e i gradini vanno a capo per conto loro
  (`.ev-geo-chips` a `flex-basis:100%` **solo sotto i 600px**: su desktop ci
  stanno in fila e una riga piena sarebbe 40px di vuoto).
- **La nota prometteva che "la posizione resta nel browser" anche a chi aveva
  solo scelto un comune da un elenco** — cioè a chi non aveva ceduto nessun
  dato. Ora quella frase esce solo col GPS; per il comune si dice da dove si
  misura.

I quattro gradini stanno in fila su 372px perché le pillole sono strette
(`padding:7px 9px`, `0.76rem`): a 12px il quarto cadeva da solo, e un gradino
isolato sembra un'altra cosa. Sotto i ~360px tornano su due righe, ed è giusto
così.

**Non porta un clic da Google e non va confusa con le sei pagine d'incrocio:**
Googlebot non concede la posizione. Zero rischio SEO (non tocca H1, title,
canonical, JSON-LD) e zero resa SEO. Serve a chi è già arrivato — cioè risponde
nei giorni in cui uno non sta cercando il nome di una sagra — ed è il ponte
naturale verso Ginetto.

#### Si misura, e la posizione non esce dal browser

`daop-vicino.js` **non chiama `gtag`**: emette un evento DOM `daop:vicino`, e
`daop-track.js` lo raccoglie. Così gtag resta scritto in un posto solo, come
`cookie-consent.js` è l'unico posto in cui GA4 si inizializza — se un domani
nasce un'altra funzione da misurare, si fa allo stesso modo.

L'evento è **`vicino_a_me`**, con due parametri e basta:

| parametro | valori |
|---|---|
| `metodo_posizione` | `gps`, `comune`, `gradino` |
| `raggio_km` | 10, 20, 30, 50 |

**Le coordinate non partono mai**, ed è un vincolo, non una dimenticanza: la
pagina promette a chi la usa che la posizione resta nel browser, e mandarla a
GA4 renderebbe quella riga una bugia. Se un giorno serve sapere *da dove*
cercano, la risposta è `metodo_posizione` più il `page_path`, non le coordinate.

**Quanto viene usato, al 19/08/2026: pochissimo.** `vicino_a_me` fa **2 eventi
in sette giorni** (12-18 agosto). Il numero però è quasi inutile e va detto
perché non lo si prenda per un verdetto: quella misura è filtrata su `/eventi/`,
che **esclude `eventi.html`** — cioè proprio la pagina dove la funzione è più in
evidenza e che da sola fa il 10% dei clic del sito. Prima di concludere
qualunque cosa la lettura va rifatta senza quel filtro. Il posto giusto per
guardarla è comunque metà settembre, come tutto il resto.

C'è l'antirimbalzo degli 800 ms già usato per i clic: chi prova tre gradini di
fila è una persona che sta scegliendo, non tre eventi. E `impostaCentro()`
scarta un centro identico a quello attivo — scrivere in un campo scatena
`input` *e* `change`, che altrimenti erano due eventi e due calcoli di 278
distanze.

**In GA4 sono già registrate** — `metodo_posizione` e `raggio_km` con ambito
evento, create il 15/08/2026 insieme alla funzione. Non c'era scelta: senza,
l'evento si conta ma i parametri restano invisibili fuori da DebugView. Il
corollario è che **quei due rispondono dal 15/08 e non prima**, perché le
dimensioni non sono retroattive. La lista completa e le date stanno in "Le
dimensioni personalizzate sono sette" più sopra. Vedi "Misurare, non stimare"
per come provarlo in locale.

`raggio_km` va **come dimensione, non come metrica**: GA4 lo propone anche come
metrica perché è un numero, ma sommare i chilometri non vuol dire niente — serve
sapere *quante volte* è stato scelto il gradino 30, cioè raggruppare per valore.

### I gruppi dell'agenda sono per data di INIZIO, e il calendario chiede altro

`eventi.html` raggruppa per giorno di partenza: una sagra dal 16 al 23 agosto sta
nel gruppo del 16, e se era già cominciata ieri sta in "Già iniziati, ancora in
corso". È giusto per l'agenda, che si scorre in avanti.

La vista calendario fa un'altra domanda. Toccare il 30 filtra le schede che
**coprono** il 30 — cioè anche quella del 27 — ma le intestazioni restavano quelle
dei gruppi: chi chiedeva il 30 leggeva "giovedì 27 agosto" e "Oggi · venerdì 28",
e concludeva che il 30 non c'era. Il filtro era corretto, i titoli sopra le
righe no.

L'agenda **non si riordina** per rispondere (spostare i nodi di ~290 schede è il
layout più caro della pagina). Con un giorno scelto: le intestazioni dei gruppi si
spengono (`.events-list.is-giorno`), il gruppo di quel giorno sale in cima con
`order`, e le due che si leggono le scrive il JS — *domenica 30 agosto* per quello
che comincia, *Già iniziati, ancora in corso* per quello che continua. Due frasi
vere in entrambi i posti, e nessuna scheda toccata. Il secondo capo compare solo
se c'è roba in tutti e due: due titoli di cui uno a zero sono una divisione
annunciata e non fatta.

Toccando un giorno la pagina **scorre** al primo capo: prima restava ferma sul
calendario, e sul telefono fra la griglia e la prima riga ci sono la nav dei
comuni e le corsie, cioè due schermate di niente prima della risposta.

**Questo pezzo è stato scritto il 13/08/2026 e è rimasto fuori da `main` fino al
28/08.** Il commit `8d013eac` stava sul ramo
`claude/mobile-calendar-event-order-vihwb8`, mai unito: il ramo era su GitHub, la
run notturna committava su `main` tutte le notti, e nessuno dei due sapeva
dell'altro. Il difetto è tornato in produzione per quindici giorni senza che
niente diventasse rosso, perché **anche le prove che lo difendevano erano su quel
ramo**. Da qui la cosa da guardare quando una funzione "sparisce": non il
generatore che riscrive i file, ma `git log --all --oneline -- eventi.html` e i
rami avanti rispetto a `main` — il generatore non tocca il `<style>` né il JS in
fondo, quindi quello che sparisce da lì non l'ha riscritto lui.

Il conteggio accanto al giorno è un'altra storia e **non va rimesso da quel
commit**: la stessa bugia (`18` sopra una riga sola con un filtro attivo) è stata
poi corretta su `main` dentro `notaGiorno()`, che tiene il totale della notte in
`dataset.tot` e riscrive solo quando si filtra. È la versione buona: reintrodurre
quella del ramo vorrebbe dire due pezzi di codice che si contendono lo stesso
numero.

L'app Android non ha questo problema: `daop-mobile/app.js` **clona** gli eventi
brevi su ogni loro giorno invece di raggrupparli per inizio, e i lunghi li mette
nei gruppi "Vieni quando vuoi" / "Solo in certi giorni".

### L'età non si ripete nelle descrizioni

La fascia d'età è già nella riga `Età:` dei dati della scheda e in ogni riga
degli elenchi. Riscriverla dentro un testo la fa sembrare un requisito
d'ingresso ("da 3 a 10 anni") invece dell'indicazione di massima che è. Può
restare come *condizione* per mostrare o no un blocco; non come cifra stampata
una seconda volta.

### La descrizione si impagina a valle del dato, e il grassetto no

Fatto il 28/08/2026. Nel foglio la `Descrizione` è **una cella**, cioè una
stringa sola: al 28/08 nessuna delle 188 righe conteneva un solo `\n`. Il
template della scheda spezzava sui capoversi (`re.split(r'\n{2,}')`) e quindi
non trovava mai niente da spezzare: usciva un blocco unico da 600-1.700
caratteri con dentro, in fila e separata da punti e virgola, la coda
`Programma: 18/09 Giorgio Vanni in concerto (22:00); …`.

**Il dato non si cambia.** Chi compila il foglio continua a scrivere in prosa e
non deve imparare nessuna sintassi. L'impaginazione la fa `corpo_descrizione()`
in `genera_eventi.py`, e solo dove la struttura è nel testo per davvero.

Cosa riconosce, e sono numeri misurati non stimati:

| | |
|---|---|
| righe con `Programma:` | 47 su 188 — e sono le manifestazioni lunghe, cioè le schede che prendono traffico |
| voci, separate da `;` | 235, riconosciute **235 su 235** |
| con `DD/MM` in testa | 207; le altre 28 ereditano il giorno di quella prima, o sono di un evento di un giorno solo |
| schede che ne escono impaginate | **112 su ~400** (una manifestazione stampa il suo programma su ogni sotto-evento) |
| paragrafi | 145 righe restano un paragrafo, 42 ne prendono due, 1 tre |

**Il grassetto sta sulla data e sull'ora del programma, e su niente altro.**
Sulla prosa sarebbe un giudizio editoriale dato da una regex — perché "6.500
posti a sedere" e non "31 Pro Loco"? — e soprattutto date, orari, prezzo ed età
stanno già nella barra dei fatti tre centimetri sopra: è la regola dell'età che
non si ripete, applicata a tutto il resto.

Le altre decisioni, che non si ricavano dal diff:

- **Niente esce dalla pagina.** `meta description`, `og:description`, il JSON-LD
  e i campi del link calendario continuano a leggere `descr_txt`, cioè il testo
  piatto. Un `<ul>` dentro una meta description non è formattazione, è markup
  che si vede fra i risultati di Google.
- **Lo split sui capoversi resta il primo taglio**, anche se oggi nel foglio non
  ce ne sono: il giorno che qualcuno andrà a capo dentro la cella, quella è una
  divisione voluta da chi scrive e vince su qualunque euristica.
- **Il confine di frase ha due occhiate indietro, e servono:** "6.500 posti" e
  "ore 18.00" hanno il punto fra due cifre, "n. 3" ed "es." sono abbreviazioni
  di una lettera sola. E un paragrafo nuovo non comincia per cifra — una frase
  che parte con un numero esiste, ma un taglio sbagliato costa più di un taglio
  mancato.
- **`PARAG_LUNGH` è 230** perché la descrizione mediana ne misura 263, quindi
  una tipica esce in due paragrafi da due-tre frasi. Verso i 150 si otterrebbe
  un paragrafo per frase, che non è prosa impaginata, è un elenco.
- **La data si scrive una volta per giorno.** Su una patronale di quattro giorni
  sono venti righe in fila che diventano quattro blocchi. È l'unica cosa che si
  perde rispetto al foglio, ed è una ripetizione.
- **Il CSS sta in `PAGINA_CSS`, non nello `<style>` di `eventi.html`.** La
  descrizione impaginata vive sulle schede: una regola di là farebbe un diff su
  ~260 file per pagine che non la usano.
- **Se il foglio cambia grammatica, degrada e non si rompe.** `Programma:` apre
  la coda solo quando apre una frase; scritto `Programma - `, o con le voci
  separate da virgole, non viene riconosciuto e la descrizione esce come prima.

**Il difetto che ha avuto nascendo non si vedeva nell'HTML**, ed è il motivo per
cui `tests/scheda.js` misura anche le larghezze: un programma **senza date** —
evento di un giorno solo, dove nel foglio la data dentro il programma non si
scrive — non ha l'etichetta, e il suo elenco cadeva nella gola di 62px riservata
alla data. 62px di larghezza su **17 schede delle 112**, con l'HTML corretto e
le prove verdi. La riga che lo chiude è
`.ev-prog-g > .ev-prog-v:first-child{grid-column:1/-1}`.

`tests/scheda.js` difende quattro cose, e la prima è quella che conta: che
l'impaginazione **non perda né aggiunga una parola**. Confronta le parole del
`.ev-body` con la `descr` del registro su tutte le schede, ammettendo come sola
perdita le date accorpate — e controllando che di date non ne sia comparsa
nessuna in più, che sarebbe il difetto peggiore di tutti. Al 28/08/2026:
**407 schede su 407, nessuna discordanza.**

#### E nella riga dell'agenda la prosa resta, il programma no

Fatto il 30/08/2026. L'impaginazione del 28/08 stava solo su `render_pagina()`:
`riga()` continuava a rovesciare in pagina la cella del foglio così com'era, e
sull'agenda si leggeva il muro di testo con dentro, in fila e separata da punti
e virgola, la coda `Programma: 27/08 …; 28/08 …`.

**La cella però contiene due cose diverse, e vanno da due parti diverse.**
Misurato sulle 182 righe del 30/08: **55.551 caratteri di prosa** e **15.990 di
code `Programma:`**, queste ultime su **44 righe** sole (mediana 282 caratteri,
massimo 1.236). La prosa è la ragione per cui uno ha aperto la riga; il
programma è una tabella travestita da frase, ed è lui a fare la pappardella.

Quindi `descrizione_riga()`: la prosa si impagina con lo stesso `paragrafi()`
della scheda — **zero byte in più**, sono gli stessi caratteri con dei `<p>`
intorno — e il programma esce e diventa una riga sola che porta alla scheda.
La riga aperta di Cherasco passa da un muro a **380px su desktop e 692 sul
telefono**, e `eventi.html` perde **8,3 KB**.

Le decisioni che non si ricavano dal diff:

- **Non è una rinuncia, perché quel contenuto ha già una casa**: 43 righe su 44
  hanno la scheda, e lì il programma è impaginato per giorno dal 28/08. Così
  "Scheda completa" guadagna una ragione per essere toccato, cioè un clic verso
  le pagine che fanno il 70% del traffico. **È quello che le altre liste del
  sito già fanno**: le pagine comune e le `sagre-provincia-*` la descrizione non
  la stampano affatto — l'agenda era l'unica a rovesciare la cella intera.
- **Dove la scheda non c'è, il programma resta.** È la regola di
  `link_luoghi()`: quello che non ha un altrove non si toglie. Al 30/08 è un
  caso solo (*SaltimPiazza 2026* a Viarigi, 134 caratteri), e resta **prosa e
  non elenco** apposta: l'elenco vorrebbe il CSS `.ev-prog*` dentro lo `<style>`
  di `eventi.html`, cioè un diff su ~260 pagine per una riga.
- **Sotto tre voci la coda resta in riga** (`MIN_VOCI_RIMANDO`). Sono 10 righe,
  tutte da 98-173 caratteri: mandare a un'altra pagina costa più di quello che
  risparmia, e «1 appuntamento →» è un link che si prende in giro da solo.
- **Il rimando porta il numero e non l'etichetta** — «Il programma completo: 6
  appuntamenti in 5 giorni →» — ed è la lezione di `link_luoghi()`. I giorni
  sono quelli **distinti**, non i gruppi che la scheda stampa.
- **L'ancora è `#programma`**, e l'`<h2>` della scheda ha ora quell'`id`: un
  rimando che scarica in cima a una pagina lunga è peggio di nessun rimando.
  Non può divergere, perché chi stampa il rimando e chi stampa quel titolo
  guardano la stessa descrizione con la stessa funzione.
- **`.event-desc` resta la classe del contenitore, ed è un vincolo del JS.**
  `preparaCal()` legge da lì la descrizione del link calendario, e
  `tests/agenda.js` confronta le due cose. Per la stessa ragione i paragrafi si
  stampano **separati da un ritorno a capo**: senza quel nodo di spazio,
  `textContent` incollerebbe l'ultima parola di un paragrafo alla prima del
  successivo.

**Quello che si perde, ed è detto prima e non dopo.** L'indice della ricerca
dell'agenda è il `textContent` della riga, quindi una parola che sta **solo**
dentro il programma («Fiera della Zucca di Piozzo») non si trova più cercando in
`eventi.html` — sulla scheda sì, ed è la pagina che vince quella query. E il
link del calendario perde il programma: lo tagliava comunque a 900 caratteri a
metà parola.

Le prove stanno in `tests/scheda.js`, insieme a quelle della scheda perché
l'invariante è la stessa su due superfici, e **nessuna rifà il lavoro del
generatore**: che la prosa non perda né aggiunga una parola (confronto con
`data/eventi.json`, riga per riga), che nessuna riga stampi rimando e coda
insieme, che ogni rimando cada sull'ancora della sua scheda, e che **il numero
promesso dalla riga sia quello che la scheda consegna** — se no la riga mente su
una pagina che chi legge non ha ancora aperto. Verificate rosse tutte e tre
rimettendo i difetti, non supposte.

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

#### "Solo gratuiti": una pagina sola su quattro se lo guadagna

Fatto il 28/08/2026. La domanda era «il filtro gratuito sulle pagine dove ha
senso farlo?», e la risposta l'hanno data i dati, non il gusto: **c'e' solo in
`eventi.html`.** Il criterio non e' nuovo — e' quello scritto nella barra dei
corsi, «un comando si stampa quando DIVIDE» — con una precisazione che qui serve:
la soglia si applica a quello che il filtro **toglie**, non a quanto e' lungo
l'elenco.

| | il dato | verdetto |
|---|---|---|
| **agenda** | prezzo dichiarato su **216 righe su 216**, gratis 170 (79%) | **si'**: toglie 46 righe |
| pagine di intenzione | idem, ma toglierebbe **2-11 righe** per pagina | no, vedi sotto |
| pagine comune | 0-20 eventi, nessun filtro per definizione | no |
| **corsi** | colonna Prezzo **vuota su tutte e 17 le righe** | no |
| **luoghi** | 167 gratuiti, 138 con prezzo, **561 righe senza niente** su 866 | no |

**Sui corsi non si fa, e non e' una questione di dati mancanti.** Un corso di
pallavolo che dura una stagione non e' gratis, quindi quel filtro cercherebbe una
cosa che non esiste; e la colonna Prezzo e' facoltativa **per decisione di
Giovanni**, cioe' accendere un filtro sopra di essa vorrebbe dire obbligare a
compilarla su ogni riga — lo stesso motivo per cui l'occhiello non promette piu'
«i giorni e i costi». C'e' anche il precedente esatto, del 26/08: «solo con
prova» e' stato **tolto** perche' provare si puo' quasi sempre. Quello che su
quella pagina divide e' l'open day, ed e' gia' li'.

**Su `luoghi.html` il problema e' il foglio, non la domanda.** Due terzi delle
righe non dicono niente sul prezzo — le Fattorie Didattiche sono **103 su 103**
senza dato — quindi «solo gratuiti» nasconderebbe centinaia di posti che sono
gratis e che nessuno ha ancora marcato, cioe' mentirebbe nel verso peggiore: un
parco pubblico che sparisce. Si riparla quando la colonna e' piena, e nel
frattempo il dato resta dove e' oggi, nella riga aperta.

**Sulle pagine di intenzione non e' una bocciatura, e' un ordine di lavori.**
Oggi la soglia le tiene fuori da se' (`sagre-provincia-alessandria` toglierebbe
2 righe su 37, `oggi-provincia-asti` zero). Ma prima di accenderlo li' va fatta
un'altra cosa: **in quelle righe il prezzo non e' scritto**, e un filtro che
lavora su un dato che la riga non mostra fa sparire delle voci senza dire
perche'. Nell'agenda invece il cartellino «Gratuito» e' in riga da sempre, cioe'
il filtro e la riga dicono la stessa cosa.

Le decisioni dentro, che non si ricavano dal diff:

- **L'attributo `data-free` e' POSITIVO, e non per stile.** Nel foglio 22 righe
  su 46 dicono «a pagamento (da verificare)»: «gratuito» e' un fatto dichiarato,
  «a pagamento» no. Un filtro non nasconde righe basandosi su una cella che si
  dichiara incerta, e per la stessa ragione non esiste il verso opposto («solo a
  pagamento»), che sarebbe un elenco costruito su 22 forse.
- **Il prezzo si legge in un posto solo** (`e_gratuito()`): lo usano il
  cartellino della riga, la card della home, il JSON-LD e l'attributo. Due
  letture della stessa colonna che divergono vorrebbero dire una riga col
  cartellino «Gratuito» che il filtro nasconde, cioe' la pagina che smentisce il
  proprio comando. `tests/agenda.js` prova esattamente quello: **ogni riga
  rimasta deve portare il cartellino.**
- **Sta nella PRIMA riga della barra, accanto alla ricerca, e costa zero
  pixel.** Misurato a 412px: le tre tendine occupano 105+101+152 piu' i due
  spazi, cioe' 372px **esatti**, quindi un quarto controllo li' dentro avrebbe
  fatto ricrescere la barra appiccicosa di 47px **per tutto lo scorrimento** —
  la ragione per cui anche «vicino a me» sta fuori. Nella prima riga lo spazio
  c'era: la ricerca la prende tutta perche' e' stirata, non perche' le serva.
  Con la casella accesa la barra resta **109px** e il primo evento a **1.083px**,
  cioe' dov'era.
- **La classe `has-gratis` la mette il JS**, e serve solo a far cedere quei
  130px alla ricerca. Senza di essa il ripiego e' il layout di prima, che e' il
  comportamento giusto nei mesi in cui la casella non c'e'.
- **E' una casella e non una tendina da due voci**: un tocco invece di tre, ed e'
  lo stesso vocabolario del «Solo con open day» dei corsi.
- **`?gratis=1` entra fra i parametri del link condivisibile** (anche
  `?gratis=si`), e vale la regola numero uno dei preset: si imposta solo se in
  quel momento la casella c'e'. Se no il link lascerebbe attivo un filtro il cui
  comando e' invisibile.

**Il difetto che ha avuto nascendo non si vedeva nell'HTML**, ed e' la terza
volta che capita su questa pagina: `.ev-chk{display:inline-flex}` batte il
`display:none` che il browser da' a `[hidden]`, quindi fuori stagione la casella
si sarebbe vista comunque — e, spingendo le tendine su tre righe, avrebbe fatto
crescere la barra appiccicosa a **157px** proprio nei mesi in cui non serve. Con
l'HTML perfettamente giusto. L'ha trovata la prova che **misura l'altezza
renderizzata** con e senza la casella, come per la barra delle azioni che veniva
alta 915px: la riga che la chiude e' `.ev-chk[hidden]{display:none}`.

### Un link con i filtri gia' messi, e perche' NON diventa una pagina

Fatto il 25/08/2026, chiesto da Giovanni: un link agli eventi della sua
provincia da mandare in giro. `eventi.html` legge quattro parametri —
`?prov=`, `?cat=`, `?quando=`, `?q=` — e imposta le tendine prima del primo
`apply()`. Sta nel JS in fondo alla pagina, cioe' nella parte scritta a mano:
`_guscio()` copia solo `<style>`, nav e footer, quindi le altre pagine non lo
prendono e non c'e' niente da tenere allineato.

Tre decisioni che non si ricavano dal diff:

- **Si scrive solo un valore che esiste nella tendina.** `?prov=to` non lascia
  un filtro attivo che chi legge non sa da dove togliere: si ignora e la pagina
  apre intera. Valgono anche gli alias comodi da scrivere a mano in un
  messaggio (`cuneo`→`cn`, `sagre`→`feste`).
- **Nessun link INTERNO usa questa forma.** Il canonical non porta parametri,
  quindi `?prov=cn` non e' un doppione in indice — ma le pagine di intenzione
  (`sagre-provincia-cuneo.html`, `weekend-provincia-cuneo.html`,
  `/eventi/comune/*`) hanno un H1 e un title loro e **vincono le loro query**.
  Questo e' un link da mandare a qualcuno, non una pagina da far indicizzare:
  se serve una superficie che prenda traffico, si fa una pagina, non un
  parametro.
- **La querystring si modifica, non si riscrive.** Il primo giro la rifaceva
  da zero e cancellava gli `utm_*` di chi arriva da una newsletter — mezzo
  secondo dopo il caricamento, cioe' quasi sempre **prima** che il banner dei
  cookie sia stato toccato e GA4 abbia mandato il `page_view`. L'attribuzione
  della campagna sarebbe sparita in silenzio. Si toccano solo `prov`, `cat`,
  `quando` e `q`; tutto il resto resta dov'e'.
- **L'URL segue i filtri**, cosi' il link si costruisce toccando le tendine
  invece di scriverlo a mano — ed e' il modo in cui lo usera' chi non ricorda i
  nomi dei parametri. `replaceState` e non `pushState`: con `pushState` il tasto
  indietro ripercorrerebbe un passo per ogni tocco. Il raggio di "vicino a me"
  resta **fuori** dall'URL: la pagina promette che la posizione non esce dal
  browser, e un link con le coordinate dentro sarebbe lo stesso che mandarle
  via — con l'aggravante che quel link poi gira. Fuori anche la vista
  calendario. L'hash si conserva, perche' e' la riga aperta e `apriDaHash()` ci
  conta.
- **Con un preset attivo si scende all'agenda**, e dopo `load` non a un `rAF`:
  con le locandine delle corsie ancora in arrivo la pagina cresce sotto i
  piedi e uno scroll calcolato prima finisce nel posto sbagliato (provato).
  Senza lo scroll si atterra sull'hero, che parla di tutte e tre le province,
  e l'unica cosa che dice che il filtro c'e' sta uno schermo piu' giu'.

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

### Le province della pagina sono tre, come in agenda

`solo_province_nostre()` scarta tutto quello che non è **AL, AT o CN**: al
20/08/2026 sono **69 righe su 894** (GE 14, TO 11, SV 9, PV 8, BI 5, MI 5, VB 5,
IM 4, NO 3, VC 3, AO 1, VA 1), e in pagina restano 825 luoghi in 287 comuni.

Fino a quel giorno qui c'era scritto il contrario — "le province **non si
filtrano**, chi cerca 'gita da Alessandria' quelle le vuole proprio" — e il
motivo per cui è cambiato non è il gusto: **la tendina non sa dire "una gita
fuori".** Offrendo "Prov. GE" accanto a "Prov. AL" promette una copertura della
Liguria che sono quattordici righe contro quattrocentosettantotto, e un elenco
che si intitola alle tre province si smentisce alla prima voce del filtro. Il
posto giusto per una gita fuori zona è un blocco che la dichiara tale, non una
sigla in mezzo alle nostre.

Tre cose da sapere prima di rimetterci mano:

- **La sigla si aggiunge a `PROVINCE_PUBBLICATE` in `genera_eventi.py`**, che è
  la stessa da cui passa l'agenda: le due superfici non possono divergere in
  silenzio, e riaprire una provincia è una riga sola.
- **`data/luoghi.json` non si pota.** `salva_istantanea()` riceve il catalogo
  intero — è lo specchio del foglio, non della pagina — e il taglio lo rifà il
  filtro anche quando si gira offline. Quindi il conteggio dell'istantanea (894)
  non coincide con quello della pagina (825), ed è voluto.
- **Il crollo si controlla prima di potare.** `controlla_crollo()` guarda le
  righe fresche del foglio: mettendo il filtro davanti, un filtro rimasto attivo
  sul tab che lasciasse fuori proprio AL/AT/CN darebbe zero righe fresche, e la
  guardia leggerebbe quello zero come "sto già girando sull'istantanea", cioè
  tacerebbe.

`dove_siamo()` di conseguenza non dice più "e dintorni": nomina le province di
`PROVINCE_PUBBLICATE` che hanno davvero delle righe — la sfumatura serve ancora,
perché la stessa funzione scrive anche l'intestazione di `/piscine.html`, che è
un sottoinsieme e può non toccarle tutte e tre.

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

**Oggi la pagina è entrata in indice e basta.** Nata il 12/08/2026: nell'export del
15/08 aveva 58 impressioni e 1 clic con un giorno e mezzo di vita; in quello del
17/08 ha **538 impressioni, 3 clic, CTR 0,56%, posizione 8,63**. Le impressioni
fanno ×9 in due giorni, cioè la pagina ha smesso di essere invisibile — ma **3 clic
non sono un pubblico e non ci si vende niente.**

Due cose da non concludere da quel ×9. Non è dimostrato che sia il ponte interno:
i link dalle schede sono partiti il 14/08 e due giorni sono pochi perché si
trasformino in impressioni, quindi la spiegazione è plausibile ma resta
un'ipotesi. E **il ponte non si misura qui**: quello che deve provare è che chi
legge una scheda evento tocchi il link, cioè un clic *interno*, che sta in GA4 e
non in Search Console. Il numero da guardare per il ponte è quello, non queste
impressioni.

Il problema successivo è già visibile e non è il traffico: **0,56% di CTR a
posizione 8,63.** Google la mostra e nessuno la tocca.

**Dodici giorni dopo quel CTR si è mosso, e la posizione no.** Export del 24/08
(25/07-21/08): `luoghi.html` fa **1.804 impressioni, 24 clic, CTR 1,33%,
posizione 8,43**. Le impressioni ×3,4, i clic ×8, **il CTR ×2,4 a posizione
ferma** — che è la sola parte interessante, perché un CTR che sale mentre la
posizione sta dov'era vuol dire che sono cambiate le query, non il ranking:
Google ha smesso di mostrarla su domande a cui non risponde. Resta comunque
**l'1,33% contro il 10% delle schede**, cioè il problema di prima ridotto di due
terzi e non risolto.

E resta soprattutto vero che **24 clic non sono un pubblico**: non cambia niente
di quello che si può promettere a un cliente, cambia la direzione della curva.

Il numero che conta per chi vende è un altro: il sito fa **4.878 clic in tre
mesi** e **il 71% va alle schede evento, il 10% a `eventi.html` e lo 0,06% a
`luoghi.html`**. Quel traffico è gente che cerca il nome di una sagra, non un
posto dove andare. I primi clienti non stanno comprando un pubblico: stanno
comprando una scommessa. Non promettere numeri che non puoi mostrare, e tienili a
un prezzo da pionieri.

Il ponte verso quel traffico è partito il **14/08** — 193 schede evento e 204
pagine comune che linkano i luoghi del proprio comune. Il metro era basso apposta
("bastano poche decine di impressioni") ed è stato superato di dieci volte: 538
impressioni contro 58. Ma i clic sono 3, e **l'export non dice se il merito è del
ponte**: quello si misura in GA4, coi clic interni. Vedi sopra.

(La cifra "1.932 clic al mese di `eventi.html`" che stava qui era sbagliata due
volte: era il totale del sito, non di quella pagina, ed è invecchiata in tre
giorni. `eventi.html` da sola fa 488 clic su 19.563 impressioni in tre mesi.)

#### Tre numeri, cercati in rete il 13/08/2026

Servono a tenere le aspettative in scala, non a fare un piano industriale.

| | |
|---|---|
| conversione tipica gratis → pagante (freemium) | **2-5%** → sulle 823 righe fa **16-41 clienti** a regime |
| ricavo di una directory di nicchia piccola | **100-500 $/mese**, cioè qualche migliaio di euro l'anno |
| traffico da cui si comincia a poter vendere | **3.000-5.000 visite/mese** |

Il terzo è quello che conta adesso, ed è stato superato con ampio margine: fra
l'8 e il 15 agosto il sito ha fatto **3.856 clic in otto giorni**, cioè 482 al
giorno, cioè oltre il doppio delle 5.000 visite al mese. Non cambia la
conclusione, ne cambia il tono: la soglia da cui "si comincia a poter vendere"
non è più una scadenza lontana.

Prima di brindare, però, tre cose — e la prima è peggiorata, non migliorata. Il
**79% di tutti i clic dei tre mesi sta in otto giorni** di alta stagione, e il
sito non ha mai vissuto un ottobre: il numero vero si legge a metà settembre (vedi
"Il verdetto non è agosto"). Va alle **schede evento**, non a `luoghi.html`, che è
quello che si sta vendendo. E le prime 10 schede fanno il 45% dei clic delle
schede — un pubblico concentrato su poche feste non è lo stesso che un pubblico
diffuso, e a un cliente di Ovada non serve il traffico di Cassinasco.

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
Fino al 14/08/2026 `luoghi.html` era linkata dalla nav di 292 pagine e da
**nessun corpo di pagina** tranne le due stagionali — ed è tutta lì la ragione
per cui non prendeva traffico: alla nav non ci va nessuno. Da quella data ogni
scheda evento manda ai luoghi del proprio comune, in coda a `blocco_vicini()`
(`link_luoghi()`): **193 schede su 279**, cioè le pagine che fanno il 76% dei
clic del sito. Il link si stampa solo se il comune ha davvero un'ancora in
pagina, e porta il numero — "22 posti per famiglie a Ovada" è una ragione per
toccare, "Luoghi" no. `tests/luoghi.js` controlla tutte e due le cose: che il
ponte esista ancora e che nessuna ancora linkata sia inventata.

Stessa cosa sulle **pagine comune**, in coda a `.com-link`: quella di Acqui
Terme diceva "Tutta l'agenda DAOP" e non che ad Acqui ci sono 25 luoghi. Ora lo
dice, con quelle parole lì. In tutto **204 pagine su 293** portano il link.

Le landing (`oggi`, `weekend`, le provinciali, le sei d'incrocio, le stagionali)
restano fuori apposta: non sono di un comune, quindi non c'è un'ancora sola a cui
mandarle. Il loro ponte verso `luoghi.html` esiste già ed è di altra natura — il
blocco "dove si mangia" di Ferragosto e Halloween.

Fuori dai generatori restano le due pagine scritte a mano, ed è lì che il link
si scrive **a mano una volta e basta**: in `eventi.html` sta in coda al blocco
"TESTO DI ZONA", che è già l'elenco dei link interni e sta **sotto** la lista —
non nell'hero, che è l'asset da non toccare; in `index.html` sta nel `path-alt`
della card "Sei un genitore", l'unica delle tre che parla a chi cerca un posto.
Nessuna delle due passa dai marker, quindi `genera_eventi.py` non le riscrive.

La domanda che quel link deve porre è sempre la stessa, e non è "vedi anche":
**non un evento, un posto** — cioè la cosa che serve nei giorni in cui in agenda
non c'è niente. Se un giorno diventa un "scopri di più", ha smesso di funzionare.

E le pagine di incrocio ("piscine per bambini in provincia di Alessandria",
"dove andare con la pioggia a Casale") non esistono ancora: sono 30-50 pagine
che rispondono a ricerche vere, e sono l'inventario che poi si rivende.

Cosa manca, in ordine di resa:

1. **Il conteggio delle aperture di scheda.** GA4 registra i clic *dalla* scheda
   (mappe, telefono, sito) ma non le aperture: al rinnovo puoi dire "47 hanno
   chiesto le indicazioni" e non su quante volte. È il momento in cui smetti di
   vendere fiducia e cominci a vendere evidenza.
   Che la metà buona funzioni è già misurato, ed è il modello da copiare: nei
   primi tre giorni post-fix gli eventi ci sono — `click_come_arrivare` 14,
   `apri_ginetto` 11, `click_locandina` 9, `aggiungi_calendario` 6. **Su un
   evento si sa già quante persone hanno detto "ci vado"; su un luogo non si sa
   nemmeno quante volte la scheda è stata aperta.**
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

### Quanto si scorre prima di vedere un evento, e dov'è davvero il grasso

Misurato il 15/08/2026 a 412px, perché è la domanda che torna ogni volta che si
guarda la pagina sul telefono. Il primo contenuto-evento (la corsia "in
evidenza") sta a **1.215 px**, cioè 1,3 schermate. Non due: le corsie *sono*
eventi, con la locandina.

Com'è fatto quel tratto, e qui sta la cosa da non sbagliare:

| | |
|---|---|
| hero | **602 px**, di cui **412 di testo** |
| intestazione "Prossimi Eventi" | 160 px, di cui 128 di testo |
| barra filtri | 109 px |
| conteggio + Agenda/Calendario | 44 px |
| "Vicino a me" | 40 px |
| "COSA CERCHI" + "VAI AL COMUNE" | 154 px |

**L'hero non è spazio vuoto, è testo** — un paragrafo di cinque righe da 174 px
più la riga sui centri estivi da 75. Ci si casca facilmente misurando solo gli
elementi contenitore: i paragrafi senza link dentro spariscono dal conto e
sembra che ci siano 400 px di aria da recuperare. Non ci sono.

Lo spazio vero recuperabile senza toccare una parola era **72 px**, ed è stato
preso il 15/08/2026: il padding dell'hero sul telefono era tarato sul desktop
(120 px sopra per una barra fissa alta 69), l'intestazione e lo stacco
`.bg-white` erano larghi. Oltre quei 72 px **non esiste una scorciatoia
tecnica**: quello che resta è testo.

Sul testo si è deciso così, sempre il 15/08/2026, arrivando a **1.111 px** (da
1.287, cioè 176 in meno e la barra filtri dentro la prima schermata):

- **Il sottotitolo di "Prossimi Eventi" perde la prima frase.** Diceva
  "Selezionati e verificati dalla community DAOP, giorno per giorno", che è
  quello che l'hero ha appena detto tre centimetri sopra ("selezionata per le
  famiglie e verificata evento per evento"). Resta la sola frase che l'hero
  **non** dice, cioè come si usano i controlli lì sotto: "Cerca un paese,
  scegli quando e scopri cosa fare con i tuoi figli."
- **La riga sui centri estivi si alleggerisce ma non sparisce** (`.hero-nota`,
  0.88rem sul telefono). È un rimando laterale, non il messaggio della pagina —
  ma è anche un link interno che parte dalla pagina più forte del sito, e
  quelli non si buttano per venti pixel. Gli stili erano in linea, quindi non
  si potevano ritoccare da una media query: ora è una classe.
- **Il paragrafo lungo dell'hero non si tocca**, solo il corpo scende a 1.02rem
  sul telefono (da cinque righe a quattro). Quell'elenco — *sagre, feste
  patronali, fiere, laboratori, spettacoli* — è copertura di parole chiave
  sulla pagina che regge il 12% dei clic, ed è anche la descrizione per chi
  arriva da Google senza sapere cos'è DAOP. **Sta dentro i marker
  `EVENTI-HERO`**: si cambia in `genera_eventi.py`, non a mano.

#### "Vai al comune" si ferma a otto pillole

Fatto il 21/08/2026. In alta stagione i comuni con almeno un evento in programma
sono diciannove, cioè tre file di pillole fra i filtri e il primo evento:
l'indice si mangiava la pagina che doveva indicizzare. Ne restano in vista otto
— quelli con più eventi, che è già l'ordine — e la coda sta sotto un
`+ altri N`.

| a 1280px | prima | dopo |
|---|---|---|
| il blocco "Vai al comune" | 169 px | **84 px**, una riga sola |
| con sopra la riga "Cosa cerchi" | 216 px | 130 px |

Sul telefono lo stesso taglio vale 390 → 228 px, ma si vede solo a blocco
aperto: sotto i 600px l'agenda lo chiude da sola, ed era già così.

Le decisioni, che è quello che non si ricava dal diff:

- **Il taglio è sul NUMERO di pillole, non sul conteggio degli eventi.** La
  soglia che viene in mente per prima — "almeno due eventi" — sembra più
  intelligente e non risolve niente: farebbe ballare la riga fra cinque e
  quindici pillole secondo la stagione, cioè taglierebbe troppo a novembre e
  niente a Ferragosto, che è l'unico giorno in cui il difetto si vede. Il guasto
  da riparare è di ingombro, ed è l'ingombro a dover essere prevedibile.
  `MAX_COMUNI_APERTI = 8` sta in `genera_eventi.py`, accanto a `MIN_EVENTI_HUB`.
- **Otto e non sei**: a 1280px otto pillole riempiono esattamente una riga, e
  una riga piena a metà è spazio speso peggio di una riga piena. Sul telefono
  sono tre righe, ma lì il blocco parte chiuso.
- **I link della coda restano tutti nell'HTML**, dentro un secondo `<details>`
  chiuso: è la stessa ragione per cui il blocco grande è un `<details>` e non
  JavaScript — dentro un details chiuso Google li vede e li segue lo stesso, che
  era tutto il punto del blocco. Le pagine comune ricevono diciannove link
  entranti prima e diciannove dopo.
- **Sotto le due voci di coda non si taglia niente**
  (`len(voci) <= MAX_COMUNI_APERTI + 2`): un "+ altri 1" occuperebbe il posto
  della pillola che nasconde.
- **La pillola `+ altri N` ha il bordo tratteggiato**, non pieno: è un comando,
  non una destinazione come le pillole delle scorciatoie, e il pieno lì è già
  preso. Sta *dentro* `.ev-comuni`, quindi è un elemento flex come le altre e
  chiude la riga invece di aprirsene una sua; da aperta prende tutta la
  larghezza e le nascoste vanno sotto.

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
  **Dentro `tests/` non è più così**: dal 15/08/2026 `_aiuto.js` rimappa le
  richieste `file:///assets/…` sul repo, quindi le prove caricano gli stessi
  script che vanno online. Vale per la suite, non per una pagina aperta a mano.
- **La geolocalizzazione vuole un contesto sicuro** e in Playwright il permesso
  si concede dal contesto (`permissions: ['geolocation']`, `geolocation: {…}`)
  su `http://localhost`, non da `file://`. In headless senza permesso l'avviso
  non compare e `getCurrentPosition` **non risponde mai**: è esattamente il caso
  che la sveglia dei 10 secondi copre, ed è così che è saltato fuori.

## L'invariante fra robots e sitemap vale su tutto il sito

Chiuso il 31/08/2026. La regola era già scritta — sta per esteso nel blocco
`CORSI` (vedi "L'età si legge con la sua unità") — e diceva questo:

> **In sitemap niente `noindex`, e niente `index` fuori dalla sitemap.**

Il punto è che **la applicava una sezione sola**. Undici pagine dicevano il
contrario del proprio robots, in tutti e due i versi, e nessuna delle due cose
si vede guardando una pagina: si vede solo incrociando cinquecento file con la
sitemap.

**Cinque pagine comune in `noindex` stavano dentro la sitemap.** La causa non
era dove sembrava: `scrivi_pagine_comune()` filtrava sulla **soglia degli
eventi** (`MIN_EVENTI_HUB`), e una pagina *sopra* soglia ma senza niente in
programma né di ricorrente va in `noindex` lo stesso — lo decide `render_comune`
con una condizione sua. Due posti che decidevano la stessa cosa, e uno dei due
non sapeva dell'altro.

Il rimedio **non rifà il conto**: legge `content="noindex` dall'HTML appena
prodotto, che la funzione ha già in mano. Non è pigrizia, è l'unico modo perché
i due non possano divergere — è la regola di `_dati_realta()` e di
`e_gratuito()` applicata a un'altra decisione. E il log adesso lo dice: `"5
sopra soglia ma senza niente in programma, quindi fuori sitemap: …"`.

**Sei schede ritirate erano `index, follow`.** Erano già fuori dalla sitemap:
era l'altro verso, rotto in silenzio. La ragione per correggerlo era già scritta
venti righe più su nello stesso file, per l'`Event`: *dichiararlo vorrebbe dire
garantire a un assistente che l'appuntamento è esistito con quei dati, e nel
caso della riga sbagliata non è vero*. Vale identica per Google — **se non lo
diciamo a un assistente, non possiamo offrirlo come risposta.** Ora è
`noindex, follow` se `orfano or ritirata`.

**Restano fuori apposta le cinque "spostata"**, che non hanno affatto il meta
robots: è deliberato e commentato nel generatore — un `noindex` accanto a un
canonical che punta altrove rischia di propagarsi alla pagina di destinazione.
Sono rimandi, non pagine.

### `tests/sitemap.js` — perché una prova sola e non due

Non sono due difetti: sono i due lati di un'affermazione unica, *la sitemap è
l'elenco delle pagine che chiediamo a Google di indicizzare*. Separarli
vorrebbe dire due file che possono divergere, e il verso B — quello dimenticato
— è proprio il più facile da non scrivere.

**Non asserisce nessun numero, ed è la parte che le impedisce di marcire.** Non
"27 pagine comune", non "sei ritirate", non "467 URL": ognuno di quei numeri
sarebbe rosso la notte in cui una sagra finisce, cioè quando il sito fa il suo
mestiere. È l'inciampo già pagato **sei volte** in questo repo — la copertura
delle coordinate, il conteggio delle quattro porte, il robots delle pagine
realtà, i doppioni riscritti. Qui si controlla il *rapporto* fra due elenchi,
che non ha una taglia giusta.

Due dettagli che sembrano cavilli e non lo sono:

- **Il verso B confronta la dichiarazione esplicita `index`**, non l'assenza di
  `noindex`. Con la seconda forma le cinque "spostata" diventerebbero rosse, cioè
  la prova pretenderebbe il difetto. Per lo stesso motivo restano fuori lo sprite
  delle icone e il file di verifica di Search Console, che non hanno nemmeno un
  titolo.
- **Il terzo controllo è che ogni URL in sitemap esista su disco.** Una pagina
  cancellata e non tolta dal suo blocco è un 404 annunciato a Google, ed è il
  modo più rapido di fargli smettere di dare peso alla sitemap — lo stesso
  motivo per cui il `<lastmod>` non si scrive "oggi" a ogni run.

Verificata rossa **rimettendo i due difetti uno alla volta**, non supposta.

## Verifiche prima di pubblicare

Girano tutti in CI **dopo** il commit: il sito si aggiorna comunque e la run
diventa rossa. È una scelta, non una svista — il sito fermo un giorno con gli
eventi di ieri è peggio di una pagina con un difetto.

```bash
python3 scripts/valida_jsonld.py                    # dati strutturati
python3 scripts/valida_pdf.py                       # le guide in PDF
python3 scripts/prova_riaggancio.py                 # l'edizione dell'anno prossimo
python3 scripts/prova_comuni_simili.py              # due grafie, un paese solo
cd tests && npm install && npm test                 # prove di fumo (Playwright)
```

`valida_pdf.py` è il terzo, ed è nato il 24/08/2026 perché **il PDF è l'unico
artefatto del sito che non si corregge dopo**: una pagina sbagliata la riscrive
la run di stanotte, un file scaricato su un telefono ci resta. I due difetti che
la guida ha avuto nascendo erano tutti e due silenziosi — il file c'era, pesava,
si apriva — e il secondo mescolava **otto centri già conclusi fra quelli
aperti**, cancellando l'avviso che li dichiarava tali.

Non serve né rete né Chromium: la parte grossa prova le trasformazioni di stampa
su una pagina finta scritta dentro lo script, quindi gira anche nei giorni in cui
il foglio non si legge. Poi guarda i PDF veri, se ci sono — e che manchino non è
un errore: senza date nel foglio nessuna guida nasce, ed è voluto.

`valida_jsonld.py` legge l'HTML: vede i dati strutturati, non il JavaScript.
Riferimento all'11/08/2026: 289 pagine, 532 Event, 8 avvisi noti, 0 errori.

`tests/` copre proprio quello che l'altro non vede — apertura righe, link
calendario ricostruito al volo, filtri, ricerca, stato vuoto, ancore `#ev-` e
`#lg-`, più le convenzioni che qualcuno smonterebbe per distrazione
(`content-visibility`, l'href del calendario che resta la sola base, e su
`luoghi.html` l'ordine alfabetico che il premium non deve scavalcare). Gira sui
file veri appena generati: non c'è un ambiente di prova. In un ambiente che ha
già un Chromium, `CHROMIUM_PATH=/percorso/chrome npm test` evita lo scaricamento.

Le suite sono otto, in `tests/run.js`: `agenda`, `landing`, `scheda`, `luoghi`,
`corsi`, `porte`, `guide`, `sitemap`. Al 31/08/2026 sono **371 prove**.
`sitemap.js` è l'unica che non apre il browser — legge i file e li incrocia con
`sitemap.xml`, perché quello che difende non si vede su nessuna pagina.

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
