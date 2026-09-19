// Lancia UNA suite sola, per diagnosi. Usa-e-getta.
'use strict';
const { avvia } = require('./_aiuto');
(async () => {
  const nome = process.argv[2];
  const browser = await avvia();
  try {
    const r = await require('./' + nome)(browser);
    console.log(`\n${nome}: ${r.passati} passate, ${r.falliti.length} fallite`);
    r.falliti.forEach((f) => console.log('  - ' + f));
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exit(1); });
