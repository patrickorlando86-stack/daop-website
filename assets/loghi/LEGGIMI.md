# I loghi delle società — misure e regole

Qui dentro stanno i marchi delle società che tengono i corsi. Uno per società,
e il nome del file **è** lo slug della società: `crome-in-movimento-aps.webp`,
lo stesso pezzo che c'è nell'indirizzo della sua pagina
(`/corsi/crome-in-movimento-aps.html`).

**Normalmente non ci metti le mani.** Il file lo scrive il downloader quando
qualcuno carica un logo dalla finestra: lo rimpicciolisce, lo converte, lo salva
qui e scrive il nome nella colonna `Logo` della tab **Realta** del foglio. Questo
LEGGIMI serve per le due volte all'anno in cui lo fai a mano, e per sapere che
misure chiedere a una società che te lo manda.

## Che misure deve avere il logo che ti mandano

| | |
|---|---|
| **Formato** | PNG, JPG o WEBP. Il PNG con lo sfondo trasparente è il migliore. |
| **Lato lungo** | **almeno 400 px.** Sotto questa misura il downloader lo rifiuta e ti dice perché: non lo ingrandisce, perché un logo stirato in pagina si vede peggio di come si vedrebbe piccolo. |
| **Ideale** | 600–1200 px sul lato lungo. Più grande non serve. |
| **Sfondo** | trasparente, o bianco. Un logo ritagliato male, con un pezzo della carta intestata intorno, in pagina si vede tutto. |

## Che misure ha il file che esce

Il downloader lo riscrive sempre così, e non è modificabile dalla finestra:

- **WEBP**, qualità 82, con la trasparenza conservata;
- **rimpicciolito dentro 600×600**, mantenendo le proporzioni (non si ingrandisce
  mai niente);
- **imbottito di trasparente** se dopo il rimpicciolimento un lato è sotto i
  **200 px**. Serve solo all'anteprima: sotto 200×200 Facebook e WhatsApp
  ignorano l'immagine di condivisione, e la pagina della società uscirebbe senza
  niente. L'imbottitura è trasparente, quindi nell'`<img>` non la vede nessuno —
  allarga la tela, non il disegno. Il caso tipico è la scritta larga e bassa
  (1200×150), che è un logo normalissimo.

Ne viene fuori un file da 15–40 KB.

## Dove si vede

In due posti, e li disegna `logo_path()` in
[scripts/genera_corsi.py](../../scripts/genera_corsi.py):

- la **scheda della società** in fondo a [corsi.html](../../corsi.html): una
  tessera da 52 px **accanto al nome**;
- la **pagina della società** (`/corsi/<slug>.html`): una tessera bianca da 96 px
  (116 su desktop) **nell'intestazione, sopra il nome**. Fino all'11/09/2026 stava
  sotto l'intestazione in un blocco suo da 150 px, e alle società non piaceva:
  staccava da tutto. La tessera è bianca perché quasi tutti i loghi arrivano col
  fondo bianco pieno, e sul blu dell'intestazione un quadrato bianco nudo sembra
  un buco. Da lì il
  logo è anche l'`og:image` dell'anteprima e il `logo` dei dati strutturati —
  cioè quello che si vede quando qualcuno manda il link su WhatsApp. È il motivo
  dei 200 px qui sopra.

## Perché in git e non nel bucket

Perché è la stessa cosa delle miniature. Un logo compare in un **elenco** — su
corsi.html ci sono tutte le società insieme — quindi una visita sola se li scarica
tutti, ed è la forma di traffico che l'08/08/2026 ha portato il bucket Supabase da
~10 a ~250 MB al giorno contro un tetto di 5 GB.

E poi il bucket delle locandine viene **potato ogni notte** da una funzione che
dei loghi non sa niente: una società messa in `bozza` esce dalla pagina, il suo
marchio non è più citato da nessun HTML e sette giorni dopo non c'è più.
Rimettere `confermata` restituirebbe una pagina col logo rotto. Qui non lo pota
nessuno.

Il conto che aveva fatto uscire le locandine dal repo (~340 MB l'anno di blob in
`.git`) qui non si ripresenta: i loghi sono uno per **società**, non uno per
evento, e cambiano quasi mai.

## Se metti un file a mano

Due cose, e la seconda si dimentica:

1. il file qui dentro, chiamato **come lo slug** della società;
2. il **nome del file** — solo il nome, non un indirizzo — nella colonna `Logo`
   della tab **Realta**.

Senza la seconda non si vede niente: il generatore stampa quello che dice il
foglio. E se scrivi nella colonna il nome di un file che qui non c'è, non esce un
rettangolo rotto — non esce **niente**, e l'anteprima torna al banner di DAOP. È
voluto: una cella con un refuso è più facile da vedere di un `<img>` che risponde
404 dentro una pagina che nessuno apre.
