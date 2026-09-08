# Le icone dei corsi — buttale qui

Questa cartella è il posto delle icone che si vedono nel francobollo di ogni
corso su [corsi.html](../../corsi.html). **Metti un file, compare. Togli il
file, torna quella di prima.** Non c'è codice da toccare.

Nata il 07/09/2026 con i soli disegni a linea, e il motivo era un difetto vero:
l'icona della famiglia "Movimento" era una **bicicletta**, e sui 22 corsi
dell'ASD Atletica Mondovì usciva il francobollo del ciclismo.

Dall'08/09/2026 si può anche mettere **un'illustrazione**, ed è la strada
principale.

## Due specie di icona, e la differenza si vede

| | com'è fatta | come si vede |
|---|---|---|
| **illustrazione** | un disegno colorato (PNG) | **riempie** il quadrato da 60px |
| **disegno a linea** | un SVG di contorno | sta in mezzo, 24px, e prende il colore della categoria |

L'illustrazione è la strada principale perché nella stessa posizione, sulla
pagina degli eventi, il quadrato è **pieno**: 155 righe su 156 portano la
locandina. Un simbolino dentro un quadratino colorato era la cosa fuori posto.

Il disegno a linea resta e serve ancora: quando un'illustrazione non c'è, è il
gradino dopo, e si prende gratis dal set che il sito già usa
([Lucide](https://lucide.dev)).

## Un'illustrazione: dove si mette e com'è

**Butta il PNG in questa cartella e lancia lo script.** Fa tutto lui: mette il
file al posto giusto, lo rimpicciolisce e ne scrive la versione da pagina.

```bash
python scripts/genera_icone.py
```

Il disegno grande finisce in `sorgenti/` e ci **resta** (serve a poterlo
ritoccare: rigenerandolo da zero lo stile non torna). In pagina va il `.webp`
che lo script scrive qui accanto, ~2-3 KB.

Come deve essere il disegno:

- **quadrato**, e con lo **sfondo trasparente**. Lo sfondo è quello che conta:
  il quadrato del francobollo ha già il suo colore, e un PNG col fondo bianco
  ci mette dentro un rettangolo che si vede. Se ti arriva col fondo pieno lo
  script te lo dice, e puoi provare a togliertelo con
  `python scripts/genera_icone.py --sfondo-via`
- il soggetto occupa circa l'**85%** del quadrato, centrato
- **niente testo, niente ombre, niente cornici**
- deve restare riconoscibile a **50 px**: forme grandi, pochi dettagli
- la misura del file che dai non conta (1024×1024 va benissimo): al peso e alle
  proporzioni ci pensa lo script

**Per tenere lo stile uguale fra un'icona e l'altra: generale tutte nella
stessa chat**, chiedendo «stesso stile, stessa palette, stesso spessore dei
contorni dell'immagine precedente». Cambiando chat, lo stile cambia — ed è
l'unica cosa capace di rovinare il set intero.

## Un disegno a linea: com'è fatto il file

**SVG**, e solo SVG — perché in pagina prende il colore della sua categoria, e
un'immagine il colore non lo prende.

- `viewBox="0 0 24 24"` — se ne usi un altro va bene, lo legge dal file
- il disegno sta in un'area di **20×20** dentro il riquadro da 24 (~2px di
  margine): è quello che fanno le icone già in pagina
- `fill="none"`, `stroke="currentColor"`, `stroke-width="1.75"`,
  `stroke-linecap="round"`, `stroke-linejoin="round"`
- **niente colori dentro il disegno**: se ce ne sono li riscrivo io in "prendi
  il colore del testo"
- **linea o pieno, vanno bene tutti e due**. Se disegni a linea, però, il
  tratto va **dichiarato** (`stroke` o `stroke-width`, sul tag `<svg>` o sui
  tracciati): senza, lo prendo per un disegno a campiture e giro la regola del
  colore. Se è a campiture per davvero, me ne accorgo da solo e va bene così
- deve reggere da **15px a 44px**
- niente `<script>`, `<style>`, `<image>`: li tolgo, e te lo scrivo nel log

Se un file è illeggibile o non ha un `<svg>` dentro, **non si rompe niente**:
si ripiega sul gradino dopo e il giro lo dice nel log.

## Come si chiama il file

Il nome del file **è** quello che decide dove va l'icona, e vale identico per
le due specie (`atletica.webp` o `atletica.svg`). Due possibilità:

**1. Una DISCIPLINA** — vince sulla famiglia, e si vede solo sui corsi di
quella disciplina:

```
atletica     nuoto       calcio      basket      pallavolo
tennis       judo        equitazione arrampicata pattinaggio
ciclismo     ginnastica  psicomotricita  yoga    triathlon
coro         orchestra   strumento   inglese
```

Questi nomi non sono liberi: sono l'elenco `DISCIPLINE_ICONA` in
[scripts/genera_corsi.py](../../scripts/genera_corsi.py), che tiene anche i
sinonimi (una riga scritta "Pallacanestro" o "Minibasket" prende `basket`).
I termini vengono dal vocabolario dei luoghi, `_TAG_DIZIONARIO.md` nel repo
mobile, così i due database parlano la stessa lingua. **Vuoi una disciplina che
non c'è?** Serve una riga in quell'elenco: chiedila, è una riga.

**2. Una FAMIGLIA** — vale per tutti i corsi che non hanno l'icona della loro
disciplina:

```
movimento  musica  danza    teatro     lingue
arte       studio  natura   benessere  altro
```

Un nome che non sta in nessuno dei due elenchi non compare in nessuna pagina.
Lo script te lo dice quando lo converte, e la prova
`scripts/prova_icone_corsi.py` diventa rossa.

## L'ordine, quando ci sono più file

Dal più specifico al più generico, e **dentro ogni gradino l'illustrazione
batte il disegno a linea**:

1. `<disciplina>.webp` — l'illustrazione della disciplina
2. `<disciplina>.svg`
3. `<famiglia>.webp`
4. `<famiglia>.svg`
5. il disegno scritto nel codice (`ICONE_CAT`)
6. e per una famiglia che il codice non conosce, quello di scorta

Quindi `atletica.svg` batte `movimento.webp`: **la disciplina giusta conta più
del formato.** È l'unico ordine in cui aggiungere un'icona di famiglia non può
peggiorare una riga che aveva già la sua.

`movimento.webp` da solo sistema **18 righe su 32** (atletica, psicomotricità e
yoga, che oggi mostrano tutte la bicicletta); `atletica.webp` ne rende precise
16.

## Se un giorno diventano tante

I disegni a linea vengono incollati dentro ogni card che li usa. Va bene per
una pagina con qualche decina di corsi; se un domani gli stessi servissero su
molte pagine, il posto giusto è lo sprite già esistente
([assets/icons.svg.html](../icons.svg.html), set Lucide inline con i `<use>`).
Le illustrazioni no: quelle sono file, e un file lo si scarica una volta e
resta in cache.
