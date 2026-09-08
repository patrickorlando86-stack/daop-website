# I disegni grandi

Qui stanno le **illustrazioni come arrivano** — il PNG da 1024×1024 che sputa
fuori un generatore di immagini. In pagina non ci vanno: `genera_icone.py`
legge questa cartella e scrive il `.webp` da 256px una cartella sopra, che è
quello che i lettori scaricano.

```bash
python scripts/genera_icone.py
```

**Non si cancellano.** Un'illustrazione persa si potrebbe rigenerare, ma la
seconda volta **lo stile non torna** — ed è l'unica cosa capace di rovinare un
set intero. Costa ~1 MB in git per file, una volta sola, e vale quel prezzo.

Il file lo puoi anche buttare nella cartella sopra: lo script lo sposta qui da
sé e te lo scrive nel log.

Le regole su come deve essere il disegno stanno in
[../LEGGIMI.md](../LEGGIMI.md).
