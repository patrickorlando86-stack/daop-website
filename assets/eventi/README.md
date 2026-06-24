# Locandine eventi

Le immagini delle locandine degli eventi vanno qui.

Flusso:
1. Scarica la locandina (es. con il "daop downloader").
2. Copia il file in questa cartella, es. `sagra-conzano-2026.jpg`.
3. Nel Google Sheet "luoghi", tab **Eventi**, scrivi quel nome file nella colonna **Locandina**.
4. Commit + push: la notte dopo `scripts/genera_eventi.py` aggiorna la pagina da solo.

Note:
- Nella colonna `Locandina` puoi mettere il **nome file** (cercato qui in `/assets/eventi/`)
  oppure un **URL completo** (`https://...`) se la locandina è ospitata altrove.
- Se la colonna è vuota, l'evento resta com'è ora (nessuna copertina; nel JSON-LD si usa
  l'immagine generica `headerdaop.jpg`).
- Consigliato: JPG/PNG, lato lungo ~1000px, sotto i ~300 KB.
