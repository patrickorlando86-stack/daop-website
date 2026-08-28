# Ginetto l'Esploratore — copertine e materiali

Qui dentro stanno i file della pagina **[/esploratore](https://www.daop.it/esploratore)**,
quella puntata dai **QR code stampati dentro i libri**.

    copertine/    le copertine dei volumi (JPG)
    materiali/    i PDF da stampare (diploma, checklist)

## Come funziona

I nomi dei file non stanno nell'HTML: stanno in **`data/ginetto-collana.json`**.
Dopo aver caricato o sostituito un file:

```
python scripts/genera_ginetto.py
```

Lo script rigenera `esploratore.html` e stampa l'elenco di quello che manca ancora.

Due cose che fa da solo, e che quindi **non vanno scritte a mano nel JSON**:

- **Il peso dei PDF** lo legge dal file vero (`PDF A4 · 320 KB`). Sostituisci un
  PDF e rilanci lo script: il peso si aggiorna. Non può diventare obsoleto.
- **I file che non esistono ancora** non diventano link rotti: il materiale
  compare come *"In preparazione"* e la copertina come segnaposto disegnato.
  Su una pagina raggiunta da un QR stampato su carta, un download che dà 404
  è molto peggio di un materiale dichiarato non ancora pronto.

## File attesi

Copertine — **JPG quadrato (1:1), ~980×980 px, sotto i ~200 KB** (i libri
della collana sono quadrati):

- [x] `copertine/vol-1-casale-monferrato.webp`  ← estratta dal PDF del libro
- [x] `copertine/vol-2-castelnuovo-scrivia.webp`  ← ripresa dalla scheda Amazon
- [ ] `copertine/vol-3-garbagna.webp`
- [ ] `copertine/vol-4-ovada.webp`

> I volumi **3 (Garbagna)** e **4 (Ovada)** sono in pagina dal 28/08/2026 ma
> senza copertina e senza link Amazon diretto: finche' i due file non ci sono
> la pagina disegna il segnaposto, e il bottone manda alla pagina autore invece
> che alla scheda del libro. Sono le due sole cose che mancano — appena
> arrivano, basta rilanciare lo script.

Materiali — **PDF in formato A4 verticale**, pensati per la stampa in bianco e
nero su una stampante di casa o di scuola:

- [ ] `materiali/vol-1-casale-monferrato-diploma.pdf`
- [ ] `materiali/vol-1-casale-monferrato-checklist.pdf`

> I **disegni da colorare** sono stati tolti dalla pagina: le illustrazioni del
> libro sono a colori, non c'è line-art pronto. Per riaggiungerli, crea le
> versioni in bianco e nero, rimetti il blocco in `data/ginetto-collana.json`
> e rilancia lo script.

I materiali del **volume 2** non servono ancora: finché nel JSON il volume ha
`"stato": "in-arrivo"` la pagina non li nomina nemmeno. I loro nomi sono già
scritti nel JSON e torneranno da soli quando il volume passerà a `"pubblicato"`.

Puoi cambiare i nomi: basta aggiornarli nel JSON. Il QR non punta mai a un PDF,
quindi rinominare un file non rompe niente di stampato.

## Aggiungere un volume

1. Metti copertina e PDF nelle due cartelle qui sopra.
2. In `data/ginetto-collana.json` porta a `true` il campo `visibile` del volume
   `prossimo-paese` (c'è già, disattivato), oppure copia un blocco esistente.
3. `python scripts/genera_ginetto.py`, poi commit e push.

L'HTML non si tocca mai.
