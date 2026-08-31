// L'invariante fra robots e sitemap, nei DUE versi.
//
// Cosa difende. Il sito dichiara questa regola nel codice — sta scritta per
// esteso nel blocco CORSI di genera_corsi.py — ma fino al 31/08/2026 la
// applicava una sezione sola. Le altre no, e si vedeva:
//
//   . cinque pagine comune in noindex erano dentro la sitemap. Il blocco
//     PAGINE-COMUNE filtrava sulla soglia degli eventi, non sul robots, e una
//     pagina sopra soglia ma senza niente in programma va in noindex lo stesso.
//   . sei schede "ritirata" erano index, follow. Erano gia' fuori dalla
//     sitemap: era l'altro verso della stessa regola, rotto in silenzio.
//
// Nessuno dei due si vede guardando una pagina: si vede solo incrociando
// cinquecento file con la sitemap, che e' esattamente il lavoro che una prova
// deve fare al posto di una persona.
//
// PERCHE' UNA PROVA SOLA E NON DUE. Non sono due difetti, sono i due versi di
// un'affermazione unica: "la sitemap e' l'elenco delle pagine che chiediamo a
// Google di indicizzare". Separarli vorrebbe dire due file che possono
// divergere, e il verso B — quello dimenticato — e' proprio il piu' facile da
// non scrivere.
//
// QUELLO CHE LA PROVA NON PRETENDE, ed e' la parte che le impedisce di
// marcire. Non conta niente: non "27 pagine comune", non "sei ritirate", non
// "467 URL". Ogni numero scritto qui dentro sarebbe rosso la notte in cui una
// sagra finisce, cioe' quando il sito fa il suo mestiere. E' l'inciampo gia'
// pagato sei volte in questo repo — la copertura delle coordinate, il
// conteggio delle quattro porte, il robots delle pagine realta'. Qui si
// controlla il RAPPORTO fra due elenchi, che non ha una taglia giusta.
'use strict';

const fs = require('fs');
const path = require('path');
const { esito, RADICE } = require('./_aiuto');

const SITE = 'https://www.daop.it';

// Cartelle che non sono il sito: sorgenti, dati, dipendenze delle prove.
const FUORI = ['.git', 'tests', 'scripts', 'contenuti', 'data', 'assets', 'node_modules'];

function pagine(dir = RADICE, base = '') {
  const out = [];
  for (const voce of fs.readdirSync(dir, { withFileTypes: true })) {
    if (FUORI.includes(voce.name)) continue;
    const rel = base ? `${base}/${voce.name}` : voce.name;
    if (voce.isDirectory()) out.push(...pagine(path.join(dir, voce.name), rel));
    else if (voce.name.endsWith('.html')) out.push(rel);
  }
  return out;
}

// L'URL pubblica di un file. La home e' servita da "/" e in sitemap sta cosi'.
const urlDi = (rel) => (rel === 'index.html' ? '/' : '/' + rel);

const robotsDi = (html) => {
  const m = html.match(/<meta\s+name="robots"\s+content="([^"]+)"/i);
  return m ? m[1].toLowerCase() : null;
};

module.exports = async function () {
  const st = esito();
  st.titolo("Sitemap e robots — l'invariante nei due versi");

  const xml = path.join(RADICE, 'sitemap.xml');
  if (!fs.existsSync(xml)) {
    st.ok(false, 'sitemap.xml esiste');
    return st;
  }
  const inSitemap = new Set(
    [...fs.readFileSync(xml, 'utf8').matchAll(/<loc>([^<]+)<\/loc>/g)]
      .map((m) => m[1].trim().replace(SITE, '')),
  );
  st.ok(inSitemap.size > 0, `sitemap.xml elenca ${inSitemap.size} URL`);

  const tutte = pagine();
  const meta = new Map();
  for (const rel of tutte) {
    meta.set(rel, robotsDi(fs.readFileSync(path.join(RADICE, rel), 'utf8').slice(0, 6000)));
  }

  // VERSO A — niente di escluso dentro l'elenco che diamo a Google.
  const dentroMaEscluse = tutte.filter(
    (r) => inSitemap.has(urlDi(r)) && (meta.get(r) || '').includes('noindex'),
  );
  st.ok(
    dentroMaEscluse.length === 0,
    'nessuna pagina noindex sta in sitemap' +
      (dentroMaEscluse.length ? ` — ${dentroMaEscluse.join(', ')}` : ''),
  );

  // VERSO B — tutto quello che si dichiara indicizzabile e' annunciato.
  //
  // Il confronto e' sulla dichiarazione ESPLICITA "index", non sull'assenza di
  // "noindex", e la differenza non e' un cavillo: le schede "spostata" non
  // hanno affatto il meta robots, ed e' deliberato (il commento nel generatore
  // dice perche': un noindex accanto a un canonical che punta altrove rischia
  // di propagarsi alla pagina di destinazione). Sono rimandi, non pagine, e
  // pretenderle in sitemap sarebbe pretendere il difetto. Fuori dal confronto
  // per lo stesso motivo lo sprite delle icone e il file di verifica di Search
  // Console, che non hanno nemmeno un titolo.
  const indexMaFuori = tutte.filter(
    (r) => (meta.get(r) || '').includes('index') &&
      !(meta.get(r) || '').includes('noindex') && !inSitemap.has(urlDi(r)),
  );
  st.ok(
    indexMaFuori.length === 0,
    'nessuna pagina index, follow resta fuori dalla sitemap' +
      (indexMaFuori.length ? ` — ${indexMaFuori.join(', ')}` : ''),
  );

  // E il corollario che tiene onesto l'elenco: una URL in sitemap deve esistere
  // su disco. Una pagina cancellata e non tolta dal suo blocco e' un 404
  // annunciato a Google, cioe' il modo piu' rapido di far smettere Google di
  // fidarsi della sitemap.
  const vive = new Set(tutte.map(urlDi));
  const fantasmi = [...inSitemap].filter((u) => !vive.has(u));
  st.ok(
    fantasmi.length === 0,
    'ogni URL in sitemap corrisponde a un file che esiste' +
      (fantasmi.length ? ` — ${fantasmi.join(', ')}` : ''),
  );

  // Non e' un'asserzione, e' il numero che rende leggibile il verde: se un
  // domani scende di colpo, e' li' che si guarda.
  const idx = tutte.filter((r) => (meta.get(r) || '').includes('index') &&
    !(meta.get(r) || '').includes('noindex')).length;
  console.log(`  --   ${tutte.length} pagine sul disco, ${idx} si dichiarano indicizzabili, ` +
    `${inSitemap.size} annunciate in sitemap`);

  return st;
};
