# Le icone dei corsi — buttale qui

Questa cartella è il posto dove metti le icone che si vedono nel francobollo di
ogni corso su [corsi.html](../../corsi.html). **Metti un file, compare. Togli il
file, torna quella di prima.** Non c'è codice da toccare.

Nata il 07/09/2026, e il motivo è un difetto vero: l'icona della famiglia
"Movimento" era una **bicicletta**, e sui 22 corsi dell'ASD Atletica Mondovì
usciva il francobollo del ciclismo.

## Come si chiama il file

Il nome del file **è** quello che decide dove va l'icona. Due possibilità:

**1. Una DISCIPLINA** — vince sulla famiglia, e si vede solo sui corsi di quella
disciplina:

```
atletica.svg   nuoto.svg      calcio.svg     basket.svg     pallavolo.svg
tennis.svg     judo.svg       equitazione.svg  arrampicata.svg
pattinaggio.svg  ciclismo.svg  ginnastica.svg  psicomotricita.svg
yoga.svg       triathlon.svg  coro.svg       orchestra.svg
strumento.svg  inglese.svg
```

Questi nomi non sono liberi: sono l'elenco `DISCIPLINE_ICONA` in
[scripts/genera_corsi.py](../../scripts/genera_corsi.py), che tiene anche i
sinonimi (una riga scritta "Pallacanestro" o "Minibasket" prende `basket.svg`).
I termini vengono dal vocabolario dei luoghi, `_TAG_DIZIONARIO.md` nel repo
mobile, così i due database parlano la stessa lingua. **Vuoi una disciplina che
non c'è?** Serve una riga in quell'elenco: chiedila, è una riga.

**2. Una FAMIGLIA** — vale per tutti i corsi che non hanno l'icona della loro
disciplina:

```
movimento.svg  musica.svg  danza.svg    teatro.svg     lingue.svg
arte.svg       studio.svg  natura.svg   benessere.svg  altro.svg
```

L'ordine è: **disciplina → famiglia → il disegno scritto nel codice**. Quindi
`atletica.svg` da solo sistema 22 righe su 41 e non tocca niente altro.

## Com'è fatto il file

**SVG**, e solo SVG. Un PNG o un JPG non funziona, e non è una pignoleria: in
pagina l'icona **prende il colore della sua categoria** (blu il movimento, un
altro colore la musica…), e un'immagine il colore non lo prende.

- `viewBox="0 0 24 24"` — se ne usi un altro va bene, lo legge dal file
- **niente colori dentro il disegno**: se ce ne sono li riscrivo io in
  "prendi il colore del testo". Un nero scritto dentro resterebbe nero su tutte
  le categorie
- **linea o pieno, vanno bene tutti e due**: le icone del sito sono a linea
  (contorno, spessore 1,75, angoli tondi). Se il tuo disegno è a campiture — come
  esce di solito da un programma di grafica — me ne accorgo da solo e giro la
  regola del colore, così non esce un quadratino vuoto
- **deve reggere da 15px a 44px**: niente dettagli fini, niente testo dentro,
  niente ombre
- niente `<script>`, `<style>`, `<image>`: li tolgo, e te lo scrivo nel log

Se un file è illeggibile o non ha un `<svg>` dentro, **non si rompe niente**: si
ripiega sul gradino successivo e il giro lo dice nel log.

## Se un giorno diventano tante

Qui ogni icona viene incollata dentro ogni card che la usa. Va bene per una
pagina con qualche decina di corsi; se un domani le stesse icone servissero su
molte pagine, il posto giusto è lo sprite già esistente
([assets/icons.svg.html](../icons.svg.html), set Lucide inline con i `<use>`).
Non serve adesso: le icone dei corsi stavano incollate nelle card anche prima.
