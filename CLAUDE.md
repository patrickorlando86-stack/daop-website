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

`genera_centri.py` importa `genera_eventi` e usa lo stesso guscio: se cambi il
CSS, `centri-estivi.html` si allinea solo quando gira **anche** quello script.

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
python3 scripts/genera_centri.py      # richiede rete
python3 scripts/genera_rubriche.py    # legge contenuti/rubriche/
```

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

### La categoria si scrive, non solo si colora

Le righe portano `--cat-color/--cat-tint/--cat-ink`, ma un blu e un verde senza
etichetta sono due blu e due verdi. Dove il colore deve dire qualcosa, mettici
il nome (`.com-cat`). Sulle pagine comune l'etichetta compare **solo se il
gruppo mescola più categorie**: dentro una manifestazione uniforme ripetere
"SAGRA & FESTA" su cinque righe è rumore.

Se metti l'etichetta, il colore della riga deve essere il suo: quei gruppi
appiattivano il colore su quello del gruppo e si leggeva "SPETTACOLO" scritto
nell'arancione delle sagre.

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
calendario ricostruito al volo, filtri, ricerca, stato vuoto, ancore `#ev-`,
più due convenzioni di prestazione che qualcuno smonterebbe per distrazione
(`content-visibility`, l'href del calendario che resta la sola base). Gira sui
file veri appena generati: non c'è un ambiente di prova. In un ambiente che ha
già un Chromium, `CHROMIUM_PATH=/percorso/chrome npm test` evita lo scaricamento.

Quando aggiungi una sezione che un filtro può nascondere, controlla che non
resti in aria il titolo che sta **prima** di essa e fuori da essa: è già
successo, ed è il tipo di guasto che si vede solo filtrando.

## Git

Il workflow committa da solo su `main`. Prima di lavorare, `git pull origin
main`: la run notturna ha quasi sempre spostato la testa.
