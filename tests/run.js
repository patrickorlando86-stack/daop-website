// Prove di fumo del sito generato. Si lanciano DOPO i generatori, sui file
// veri: non c'e' un ambiente di prova, quello che si controlla e' esattamente
// quello che va online.
//
//   cd tests && npm install && npm test
//
// In un ambiente che ha gia' un Chromium pronto:
//   CHROMIUM_PATH=/percorso/chrome npm test
'use strict';

const { avvia } = require('./_aiuto');

(async () => {
  const browser = await avvia();
  let passati = 0;
  const falliti = [];
  try {
    for (const suite of [require('./agenda'), require('./landing'), require('./scheda'),
                         require('./luoghi'), require('./corsi'), require('./porte'),
                         require('./guide'), require('./sitemap'), require('./faq')]) {
      const r = await suite(browser);
      passati += r.passati;
      falliti.push(...r.falliti);
    }
  } finally {
    await browser.close();
  }
  console.log(`\n${passati} prove passate, ${falliti.length} fallite`);
  if (falliti.length) {
    falliti.forEach((f) => console.log('  - ' + f));
    process.exit(1);
  }
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
