# Locandine eventi

Le immagini delle locandine degli eventi vanno qui.

Di norma **ci pensa il "daop downloader" da solo**: estrae gli eventi dalla
locandina, scrive la colonna `Locandina` nel foglio, copia il file qui e fa
commit+push da solo (`AUTO_PUSH_SITO`). La notte dopo `scripts/genera_eventi.py`
(azione GitHub) rigenera la pagina con la copertina. Tu non devi fare nulla.

Se invece aggiungi una locandina **a mano**:
1. Copia il file in questa cartella, es. `sagra-conzano-2026.jpg`.
2. Nel Google Sheet "luoghi", tab **Eventi**, scrivi quel nome file nella colonna **Locandina**.
3. Commit + push di questa cartella.

Note:
- Nella colonna `Locandina` puoi mettere il **nome file** (cercato qui in `/assets/eventi/`)
  oppure un **URL completo** (`https://...`) se la locandina è ospitata altrove.
- Se la colonna è vuota, l'evento resta com'è ora (nessuna copertina; nel JSON-LD si usa
  l'immagine generica `headerdaop.jpg`).
- Consigliato: JPG/PNG, lato lungo ~1000px, sotto i ~300 KB.
