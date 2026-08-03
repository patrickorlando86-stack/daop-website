# Pubblicazione automatica sui social

Quando esce un articolo delle rubriche sul sito, un post con il link parte da
solo sulle pagine Facebook di DAOP. Il meccanismo sta in
`scripts/pubblica_facebook.py`, gira col workflow `.github/workflows/pubblica-social.yml`
alle 09:30 italiane, e si configura in `data/social.json`.

Finché in `data/social.json` c'è `"attiva": false` non parte niente: il
workflow gira, non trova il permesso e si ferma. È lo stato in cui è adesso.

---

## Cosa serve (una volta sola, ~20 minuti)

Serve un'app Meta che faccia da tramite fra il sito e le pagine. **Non serve
la revisione di Meta** (l'App Review, quella lenta): finché l'app resta in
modalità sviluppo e chi genera il token è amministratore sia dell'app sia
della pagina, si può pubblicare sulle proprie pagine senza passare da nessuna
approvazione.

### 1. Crea l'app

Su [developers.facebook.com](https://developers.facebook.com) → *Le mie app* →
*Crea un'app* → tipo **Business**. Nome: qualcosa come "DAOP Sito".
Dentro l'app, aggiungi il prodotto **Facebook Login**.

Segnati **ID app** e **Chiave segreta dell'app** (in *Impostazioni → Di base*).

### 2. Prendi un token utente

Vai su [Esplora API Graph](https://developers.facebook.com/tools/explorer/),
seleziona in alto la tua app, poi *Genera token di accesso* e concedi questi
tre permessi:

- `pages_show_list`
- `pages_manage_posts`
- `pages_read_engagement`

Ottieni un token **a breve durata** (dura un'ora). Va allungato.

### 3. Allungalo a 60 giorni

Incolla nel browser, sostituendo le tre parti in maiuscolo:

```
https://graph.facebook.com/v23.0/oauth/access_token?grant_type=fb_exchange_token&client_id=ID_APP&client_secret=CHIAVE_SEGRETA&fb_exchange_token=TOKEN_BREVE
```

La risposta contiene un token utente **a lunga durata** (60 giorni).

### 4. Ricava i token di pagina — questi non scadono mai

È il passaggio che conta: un token di *pagina* derivato da un token utente a
lunga durata **non ha scadenza**. Si genera una volta e non ci si pensa più
(salvo cambio password Facebook o revoca dei permessi).

Nella cartella del sito:

```bash
FB_USER_TOKEN=IL_TOKEN_LUNGO python scripts/pubblica_facebook.py --pagine --con-token
```

Stampa nome, ID e token di ogni pagina che amministri.

### 5. Metti gli ID nel repository e i token nei secret

Gli **ID** delle pagine vanno in `data/social.json`, campo `page_id`: sono
informazioni pubbliche, stanno benissimo nel repository.

I **token** vanno solo nei secret di GitHub — mai in un file del repository.
Su github.com, nel repository del sito: *Settings → Secrets and variables →
Actions → New repository secret*. Servono due secret, con questi nomi esatti:

| Nome del secret | Contenuto |
|---|---|
| `FB_TOKEN_ALESSANDRIA` | token della pagina DAOP Alessandria |
| `FB_TOKEN_ASTI` | token della pagina DAOP Asti |

### 6. Copri l'arretrato, poi accendi

Sul sito ci sono già una dozzina di articoli pubblicati. Senza questo
passaggio, alla prima run partirebbero tutti insieme. Con gli ID già scritti
in `data/social.json`:

```bash
python scripts/pubblica_facebook.py --segna-tutti
```

Marca tutto quello che è online come "già uscito" senza postare nulla. Da lì
in avanti escono solo i nuovi. Committa `data/social-pubblicati.json`.

Poi porta `"attiva": true` in `data/social.json`, committa, e lancia una volta
il workflow a mano (*Actions → Pubblica sui social → Run workflow*) per
vedere che non dia errori.

---

## Come si comporta

**Cosa esce.** Un post per articolo, uguale su entrambe le pagine: titolo,
sommario, firma della rubrica, hashtag presi dal campo `tag` del `.md`, e il
link. L'anteprima (immagine, titolo, descrizione) la costruisce Facebook dai
meta Open Graph già presenti nelle pagine articolo.

**Quando esce.** L'articolo compare sul sito alle 04:00 del giorno indicato
nel suo `data:`; il post parte alle 09:30 dello stesso giorno. I due momenti
sono separati apposta: Facebook, appena riceve un link, va a leggerlo per
costruire l'anteprima e si tiene in cache quello che trova. Se postassimo
subito dopo la generazione, la pagina non sarebbe ancora online e
nell'anteprima resterebbe un 404 per giorni.

**Niente doppioni.** `data/social-pubblicati.json` registra ogni post uscito,
per articolo e per pagina. Un articolo esce una volta sola. Come seconda rete,
si guardano solo gli articoli degli ultimi 7 giorni (`finestra_giorni`): se il
registro sparisse, non ripartirebbe comunque tutto l'archivio.

**Gli articoli con dati da confermare restano fuori.** I `.md` che hanno ancora
voci nel campo `verificare:` — le cifre di Pillole Fiscali in attesa di
conferma da Stefania — non vengono postati. Restano sul sito, ma non li si
spinge: un post su Facebook, una volta condiviso, è molto più difficile da
correggere di una pagina del sito. Quando i dati sono confermati, si toglie la
riga `verificare:` dal `.md` e l'articolo torna postabile (se è ancora dentro
la finestra dei 7 giorni).

## Comandi utili

Vedere i post che uscirebbero, senza chiamare Facebook:

```bash
python scripts/pubblica_facebook.py --prova
```

Spegnere tutto in fretta: `"attiva": false` in `data/social.json`. Per una
pagina sola, `"attiva": false` dentro la sua voce in `pagine`.

Se un token smette di funzionare (cambio password, permessi revocati), il
workflow diventa rosso e il messaggio d'errore di Facebook finisce nel log del
job. Si rifà il giro dal punto 2.

## Instagram

Non è coperto qui. Instagram non pubblica link cliccabili nei post: un post IG
è un'immagine con una didascalia in cui l'URL resta testo morto. Per farlo con
senso servirebbe generare un'immagine per articolo (titolo su fondo DAOP) e
pubblicarla via Instagram Graph API, che richiede l'account IG convertito in
Business e collegato alla pagina Facebook. È un lavoro a sé, da fare quando la
parte Facebook è rodata.
