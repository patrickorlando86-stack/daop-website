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

Il workflow `.github/workflows/aggiorna-eventi.yml` gira tutti e tre alle 02:00
UTC, committa da solo su `main`, poi passa i controlli (vedi in fondo).

## Il canale WhatsApp

Aperto il 14/08/2026. `CANALE_WA` in `genera_eventi.py` è l'unico posto in cui
sta l'indirizzo: **vuoto vuol dire che l'invito non si stampa da nessuna
parte**, che è il comportamento giusto se un giorno il canale si chiude.
`blocco_canale()` compare in coda alle schede evento, alle pagine comune e alle
landing — **290 pagine**, tutte tranne i tre `eventi/box-*.html`. Quelli vivono
dentro l'iframe di siti altrui, e chiedere lì un'iscrizione vuol dire usare lo
spazio di qualcun altro per portargli via il pubblico: stessa ragione per cui
non chiedono il consenso ai cookie. `tests/luoghi.js` controlla che l'invito ci
sia su tutte e che non sia mai doppio.

**Sta in coda e non in cima**, e il testo dice per prima cosa *quanto spesso si
scrive*: la paura di chi si iscrive a un canale non è il contenuto, è il
diluvio. Niente promesse in più ("contenuti esclusivi") che poi non
manteniamo.

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
si posiziona, la resa da Google arriva nel 2027": **è andata diversamente, e in
meglio.** L'export Search Console del 15/08 (tre mesi, chiude il 13) le dà 36
clic, 554 impressioni, CTR 6,50%, **posizione media 6,06** — e sono tutti di un
giorno solo, perché la pagina è nata quel giorno. Più le schede a tema che ha
trainato: Acqui Terme 45 clic, Limone Piemonte 35, Eco Park 26.

Non cambia nessuna delle decisioni sopra, e soprattutto **non è un argomento per
fare le stagionali all'ultimo**: una pagina che parte da posizione 6 in
ventiquattr'ore su un dominio già forte partirebbe da più su con due mesi di
anzianità, che è esattamente la scommessa di Halloween. Quello che cambia è
l'aspettativa: una stagionale nuova rende **qualcosa** già l'anno zero, quindi
vale la pena farla anche quando è tardi — non "tanto è per l'anno prossimo".

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
compare nell'export con **3 impressioni in tutto**, tutte su una scheda (San
Marzano Oliveto). È il comportamento previsto e non dice niente sulla pagina: la
domanda di Halloween si accende a ottobre. Il numero da guardare è quello di
inizio ottobre, ed è anche il promemoria del perché le schede stagionali vanno
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

Misurato sull'export di Search Console del 15/08/2026 (tre mesi, 14/05–13/08):
**3.491 clic, 43.168 impressioni, CTR 8,09%, 88% da telefono.** Dove vanno:

| | clic | quota | CTR | posizione |
|---|---|---|---|---|
| le 229 **schede** `/eventi/*.html` | 2.688 | **76%** | 10,30% | ~3 |
| `eventi.html` | 404 | 11,5% | 2,48% | 8,15 |
| `sagre-provincia-*` | 264 | 7,5% | 9,68% | ~6,4 |
| home | 82 | 2,3% | 17,41% | 5,58 |
| `/ferragosto.html` (un giorno di vita) | 36 | 1% | 6,50% | 6,06 |
| `oggi.html` + `weekend.html` | **1** | 0% | — | — |
| `luoghi.html` (un giorno di vita) | 1 | 0% | 1,72% | 7,98 |

Da qui la prima cosa da non fraintendere: **come pagina singola `eventi.html`
resta la più forte del sito, ma come sistema il sito sono le schede.** Ed erano
esattamente loro a non mandare `page_view` fino al 12/08 — il divario fra clic da
Google e utenti GA4 non era un mistero, erano i tre quarti del traffico.

La seconda è dove sta il buco più grosso: **`eventi.html` incassa 16.308
impressioni — il 38% di tutto il sito — e le converte al 2,48%.** Le stesse
persone che sulle schede cliccano al 10% lì non cliccano, e non è un difetto
della pagina: è la posizione 8,15 sulle query generiche. È il problema che le sei
pagine d'incrocio provano ad aggredire (vedi la sezione sulla cannibalizzazione),
non uno da risolvere riscrivendo l'H1.

**L'onda di agosto non è la stagione delle sagre: sono le schede.** Il `first_seen`
in `data/pagine-evento.json` dice che il sistema è nato il **02/08/2026**, e la
rampa è questa:

| | clic al giorno |
|---|---|
| maggio-giugno | 1,3 |
| luglio | 5,5 |
| 1-2 agosto | 12,5 |
| **3-13 agosto** | **293,8** |

Cinquantatré volte in undici giorni, con la **posizione media che scende da 7,66
a 6,00** mentre le impressioni fanno ×20 — di solito succede il contrario, cioè
arrivano impressioni su query lontane e la media peggiora. Le stesse sagre erano
già in agenda a luglio, quando il sito faceva cinque clic al giorno: il picco di
Ferragosto ha amplificato, non causato.

E l'8 agosto non era il picco con la coda in discesa, come sembrava dall'export
precedente: `603 → 427 → 273 → 270 → 311 → 582`. Il 13 risale al secondo
giorno migliore di sempre. In sei giorni (8-13) il sito ha fatto 2.466 clic, cioè
il **71% di tutti i clic dei tre mesi**.

Dove sono imbattibili: **nomi propri di feste di paese.** `festa cassinasco 2026`
in posizione 1,13 con CTR 31%, `cassinasco festa 2026` con CTR **72%**. Nessun
altro pubblica i sotto-eventi di una patronale di 800 abitanti. Le query che
contengono `2026` fanno il 59% dei clic misurati con CTR **11,25% contro 4,50%**
delle altre: **la gente scrive l'anno**, e i title ce l'hanno — è la ragione per
cui `_titolo_evento()` lo stampa.

Due numeri per tenere la testa a posto: le prime 10 schede fanno il **49%** dei
clic delle schede e `festa-d-estate-cassinasco.html` da sola l'8,6% del sito; e
il foglio `Query` copre solo 731 dei 3.491 clic, perché Google anonimizza le
query troppo rare. **Il 79% del traffico arriva da ricerche che non possiamo
vedere.** È il fossato (nessuno ci compete) e la fragilità (non c'è una query da
difendere) nello stesso dato.

#### Il verdetto non è agosto, è il 15 settembre

Tutto quello che sappiamo viene da dodici giorni di alta stagione, su un sito che
non ha mai vissuto un ottobre. Ad agosto qualunque sito di sagre piemontesi fa
numeri, quindi **la domanda "andiamo bene?" non ha una risposta onesta prima di
metà settembre**, quando si vede dove si ferma la discesa:

| clic/giorno a metà settembre | cosa vuol dire |
|---|---|
| sotto 20 | agosto era la stagione, il sistema non si regge da solo |
| 50-100 | il sistema regge: è il sito, non il calendario |
| sopra 150 | non c'è più una stagione da temere |

La scommessa ragionevole è la seconda — 229 schede indicizzate che non si
cancellano mai, e l'autunno piemontese ha il nome del paese attaccato a ogni
evento — ma è una scommessa, e questa è la data in cui si riscuote. Il numero da
segnare adesso, per non ricostruirlo dopo: **la baseline pre-schede è 5,5 clic al
giorno** (luglio 2026).

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
la riga stagionale, con la stessa aritmetica: quell'H1 vale 16.308 impressioni,
cioè il **38%** delle impressioni del sito, e si rinuncerebbe a un asset provato
per sbloccare due pagine che in tre mesi ne fanno 28. Nemmeno una prova A/B lo
giustifica: il rischio è asimmetrico.

Il problema che resta non è *quale* pagina ranka, è che **qualunque pagina ranki,
ranka in posizione 8-10**. Le query generiche sono il 40% delle impressioni
visibili e solo il 17% dei clic, con CTR 2,86%. Ed è la domanda che **non scade
mai**: torna ogni weekend, tutto l'anno, Halloween e Natale compresi. Ed è anche
quella su cui `eventi.html` lascia sul tavolo 16.308 impressioni al 2,48%.

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

**Come si sa se hanno funzionato, e quando.** Sono nate il 14/08 e Search Console
ha due-tre giorni di ritardo, quindi il primo dato utile è l'export del **21-22
agosto**. Il metro non è "quanti clic fanno le sei": è se **la somma
incrocio + `oggi` + `weekend` supera le 28 impressioni in tre mesi** che facevano
le due madri da sole. Se le sei prendono impressioni e le madri restano a zero,
ha funzionato: vuol dire che il problema era l'incrocio mancante, non
l'intenzione. Se restano tutte a zero, la conclusione è che Google consolida su
`eventi.html` qualunque cosa si scriva, e allora il lavoro si sposta sul CTR di
quella pagina invece che su nuove URL. È l'unico esperimento in corso con una
previsione falsificabile: non lasciarlo senza verdetto.

Resta aperto un punto solo della vecchia lista: **`Event` in JSON-LD sulle
pagine aggregate.** `oggi.html`, `weekend.html`, le tre provinciali e ora le sei
d'incrocio hanno tutte `CollectionPage` + `ItemList` che *rimanda* alle schede,
e zero `Event`: i rich result eventi li prende solo `eventi.html`, che ne ha 286.
Prima di cambiarlo va verificato che moltiplicare la stessa entità su nove URL
non diluisca invece di aggiungere — è la ragione per cui non è stato fatto
insieme al resto.

Cosa **non** si è fatto per de-cannibalizzare, e non si farà: toccare l'H1 di
`eventi.html`. Vedi sopra, vale 16.308 impressioni.

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
  attivo resta fuori. Oggi sono zero su 278, ma il foglio si compila a mano.
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

C'è l'antirimbalzo degli 800 ms già usato per i clic: chi prova tre gradini di
fila è una persona che sta scegliendo, non tre eventi. E `impostaCentro()`
scarta un centro identico a quello attivo — scrivere in un campo scatena
`input` *e* `change`, che altrimenti erano due eventi e due calcoli di 278
distanze.

**Cosa registrare in GA4** perché quei parametri si vedano nei report: due
dimensioni personalizzate con ambito evento (`metodo_posizione`, `raggio_km`).
Senza, l'evento si conta ma i parametri restano invisibili fuori da DebugView.
Vedi "Misurare, non stimare" per come provarlo in locale.

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

**Oggi la pagina è entrata in indice e basta.** Nata il 12/08/2026, nell'export
del 15/08 ha **58 impressioni, 1 clic, posizione 7,98** — ed è un giorno e mezzo
di vita, perché i dati chiudono il 13. Non è traffico e non ci si vende niente,
ma non è più zero.

Il numero che conta per chi vende è un altro: il sito fa **3.491 clic in tre
mesi** e **il 76% va alle schede evento, l'11,5% a `eventi.html` e lo 0,03% a
`luoghi.html`**. Quel traffico è gente che cerca il nome di una sagra, non un
posto dove andare. I primi clienti non stanno comprando un pubblico: stanno
comprando una scommessa. Non promettere numeri che non puoi mostrare, e tienili a
un prezzo da pionieri.

Il ponte verso quel traffico è partito il **14/08** — 193 schede evento e 204
pagine comune che linkano i luoghi del proprio comune — quindi al 13 non aveva
ancora prodotto niente per definizione. **È la prima cosa da guardare
nell'export successivo**, e il metro è basso apposta: bastano poche decine di
impressioni per dire che il ponte porta acqua, perché il confronto è con 58.

(La cifra "1.932 clic al mese di `eventi.html`" che stava qui era sbagliata due
volte: era il totale del sito, non di quella pagina, ed è invecchiata in tre
giorni. `eventi.html` da sola fa 404 clic su 16.308 impressioni in tre mesi.)

#### Tre numeri, cercati in rete il 13/08/2026

Servono a tenere le aspettative in scala, non a fare un piano industriale.

| | |
|---|---|
| conversione tipica gratis → pagante (freemium) | **2-5%** → sulle 823 righe fa **16-41 clienti** a regime |
| ricavo di una directory di nicchia piccola | **100-500 $/mese**, cioè qualche migliaio di euro l'anno |
| traffico da cui si comincia a poter vendere | **3.000-5.000 visite/mese** |

Il terzo è quello che conta adesso, ed è stato superato in due giorni: fra l'8 e
il 13 agosto il sito ha fatto **2.466 clic in sei giorni**, cioè viaggia sopra le
5.000 visite al mese. Non cambia la conclusione, ne cambia il tono: la soglia da
cui "si comincia a poter vendere" non è più una scadenza lontana.

Prima di brindare, però, tre cose. Il **71% di tutti i clic dei tre mesi sta in
sei giorni** di alta stagione, e il sito non ha mai vissuto un ottobre: il numero
vero si legge a metà settembre (vedi "Il verdetto non è agosto"). Va alle
**schede evento**, non a `luoghi.html`, che è quello che si sta vendendo. E le
prime 10 schede fanno metà dei clic delle schede — un pubblico concentrato su
poche feste non è lo stesso che un pubblico diffuso, e a un cliente di Ovada non
serve il traffico di Cassinasco.

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
