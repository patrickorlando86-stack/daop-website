# Locandine eventi

**Le immagini non stanno più qui: stanno nel bucket Supabase `locandine`.**
Questa cartella resta solo come archivio locale (è in `.gitignore`, non viene
pubblicata e non finisce più nel repo).

Perché: ogni locandina pesa ~190 KB e committandola entrava nei blob di git per
sempre — ~340 MB l'anno che non si recuperano. La stessa immagine sta già nel
bucket, ottimizzata a ~95 KB, ed è quella che legge sia l'app Ginetto sia il
sito. Una copia sola, la più economica.

Di norma **ci pensa il "daop downloader" da solo**: estrae gli eventi dalla
locandina, carica l'immagine nel bucket, scrive il nome file nella colonna
`Locandina` del foglio. La pagina si rigenera da sé (subito col push del
downloader, e comunque ogni notte con l'azione GitHub). Tu non devi fare nulla.

Se invece aggiungi una locandina **a mano**:
1. Carica il file nel bucket `locandine` dal pannello Supabase (Storage →
   `locandine` → Upload). Tienilo sotto ~1000px di lato lungo e ~150 KB.
2. Nel Google Sheet "luoghi", tab **Eventi**, scrivi quel nome file nella
   colonna **Locandina**.

Note:
- Nella colonna `Locandina` puoi mettere il **nome file** (che diventa
  `https://aaseyjdsldgjerjqlumu.supabase.co/storage/v1/object/public/locandine/<nome>`)
  oppure un **URL completo** (`https://...`) se la locandina è ospitata altrove.
- Il prefisso lo mette `loc_path()` in `scripts/genera_eventi.py`: è l'unico
  punto da cambiare se un giorno il bucket cambia indirizzo.
- Se la colonna è vuota, l'evento resta senza copertina (nel JSON-LD si usa
  l'immagine generica `headerdaop.jpg`).
- I centri estivi hanno un controllo in più: se il nome scritto nel foglio non
  esiste nel bucket, la scheda esce senza immagine invece che con una foto rotta.
