// Le quattro porte: eventi, luoghi, centri, corsi.
//
// Cosa difende questa prova, e perche' e' nata. Fino al 20/08/2026 due famiglie
// su quattro non avevano una porta da nessuna parte — la nav ne aveva due
// (Eventi, Luoghi), il footer due DIVERSE (Eventi, Corsi) — e tre pagine
// ricevevano ZERO link dal corpo di qualunque altra pagina: centri-invernali,
// centri-pasquali e piscine stavano solo in sitemap. E' lo stesso guasto gia'
// diagnosticato e gia' risolto su luoghi.html il 14/08 ("alla nav non ci va
// nessuno"), che li' era costato tutto il traffico della pagina.
//
// Sono difetti che non fanno rumore: nessuna pagina si rompe, nessun
// generatore fallisce, e si vedono solo contando i link a mano. Per questo
// stanno in una prova e non in un commento.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

// La famiglia, il suo hub, e la chiave che quell'hub NON deve linkare (se
// stesso). L'ordine e' quello della nav: prima "cosa si fa in una data", poi
// "dove si va", poi le due a iscrizione.
const HUB = [
  ['eventi', 'eventi.html', '/eventi.html'],
  ['luoghi', 'luoghi.html', '/luoghi.html'],
  ['centri', 'centri-estivi.html', '/centri-estivi.html'],
  ['corsi', 'corsi.html', '/corsi.html'],
];

// Le tre pagine che erano orfane. Il conteggio dei link entranti dice qualcosa
// SOLO perche' nav e footer non le nominano: se un giorno una di queste entra
// in nav, questa prova diventa verde per il motivo sbagliato e va rifatta
// guardando il corpo invece del file intero.
const EX_ORFANE = ['centri-invernali.html', 'centri-pasquali.html', 'piscine.html'];

function html(f) {
  return fs.readFileSync(path.join(RADICE, f), 'utf8');
}

// Tutti gli .html del repo, per contare i link entranti.
function tutte() {
  const out = [];
  (function giu(dir) {
    for (const v of fs.readdirSync(path.join(RADICE, dir), { withFileTypes: true })) {
      if (v.name === 'node_modules' || v.name === '.git') continue;
      const rel = dir ? path.join(dir, v.name) : v.name;
      if (v.isDirectory()) giu(rel);
      else if (v.name.endsWith('.html')) out.push(rel);
    }
  })('');
  return out;
}

module.exports = async function porte(browser) {
  const r = esito();
  r.titolo('Le quattro porte — la riga in coda ai quattro hub');

  const conteggi = JSON.parse(html('data/conteggi.json'));

  for (const [chiave, file, proprio] of HUB) {
    const s = html(file);
    const blocco = s.match(/<section class="eco[^"]*"[\s\S]*?<\/section>/);
    r.ok(!!blocco, blocco
      ? `${file}: la riga c'è`
      : `${file}: la riga delle quattro porte NON c'è`);
    if (!blocco) continue;
    // Una pagina che linka se stessa in una riga di "altre cose" e' un link
    // che non porta da nessuna parte, ed e' l'errore piu' facile da fare
    // passando la chiave sbagliata a blocco_ecosistema().
    r.ok(!blocco[0].includes(`href="${proprio}"`),
      `${file}: la riga non linka se stessa (${chiave})`);
    const card = (blocco[0].match(/class="eco-c"/g) || []).length;
    r.ok(card === 3, card === 3 ? `${file}: tre card`
      : `${file}: ${card} card invece di tre`);
  }

  // Sulla home non si e' dentro nessuna famiglia, quindi escono tutte e
  // quattro: e' il solo posto in cui la riga ne ha quattro.
  const home = html('index.html');
  const fascia = home.match(/<section class="eco eco--porte"[\s\S]*?<\/section>/);
  r.ok(!!fascia, fascia ? 'index.html: la fascia c\'è' : 'index.html: la fascia NON c\'è');
  if (fascia) {
    const card = (fascia[0].match(/class="eco-c"/g) || []).length;
    r.ok(card === 4, card === 4 ? 'index.html: quattro porte'
      : `index.html: ${card} porte invece di quattro`);
    for (const [chiave, , proprio] of HUB) {
      r.ok(fascia[0].includes(`href="${proprio}"`),
        `index.html: la fascia porta a ${chiave}`);
    }
  }

  r.titolo('Le quattro porte — il numero, non l\'etichetta');

  // "894 posti per famiglie" e' una ragione per toccare, "Luoghi" no: e' la
  // regola di link_luoghi(), e qui si controlla che il numero arrivi davvero
  // in pagina. Sotto MIN_CONTEGGIO (5) il generatore stampa apposta la riga
  // descrittiva invece del conteggio, quindi si guardano solo le famiglie che
  // stanno sopra soglia.
  const MIN = 5;
  const eventi = html('eventi.html');
  for (const [chiave] of HUB) {
    const n = conteggi[chiave] || 0;
    if (chiave === 'eventi' || n < MIN) continue;
    r.ok(eventi.includes(`>${n} `),
      `eventi.html: il conteggio di ${chiave} (${n}) è in pagina`);
  }

  r.titolo('Le quattro porte — nessuna pagina resta orfana');

  const files = tutte();
  for (const orfana of EX_ORFANE) {
    const da = files.filter((f) => f !== orfana && html(f).includes(`/${orfana}`));
    r.ok(da.length > 0, da.length
      ? `${orfana}: ${da.length} pagine la linkano (es. ${da[0]})`
      : `${orfana}: ZERO link entranti, è tornata orfana`);
  }

  r.titolo('Le quattro porte — la nav e il cassetto del telefono');

  // La nav di eventi.html e' il guscio di ~350 pagine (_guscio la rilegge a
  // ogni run): se le porte sparissero da qui sparirebbero da tutto il sito.
  const nav = eventi.match(/<ul class="nav-links">[\s\S]*?<\/ul>/);
  r.ok(!!nav, nav ? 'eventi.html: la nav c\'è' : 'eventi.html: nav non trovata');
  if (nav) {
    const ordine = HUB.map(([, f]) => nav[0].indexOf(`href="${f}"`));
    r.ok(ordine.every((i) => i >= 0), 'la nav porta tutte e quattro le porte');
    r.ok(ordine.every((v, i) => i === 0 || v > ordine[i - 1]),
      'e nell\'ordine giusto: eventi, luoghi, centri, corsi');
    // La nav a nove voci era gia' tagliata a destra sopra i 901px, che e' il
    // motivo per cui le porte non ci stavano: se qualcuno la riallunga, questa
    // prova lo dice prima dello screenshot.
    const voci = (nav[0].match(/<li>/g) || []).length;
    r.ok(voci <= 7, `nav di ${voci} voci: sopra le sette si taglia sul desktop`);
  }

  // Sul telefono il cassetto e' l'unica nav che esiste (il 90% del traffico):
  // li' non si toglie niente, si mette in ordine — le quattro porte davanti,
  // il resto sotto l'etichetta.
  const mob = eventi.match(/<div class="mobile-menu"[\s\S]*?\n<\/div>/);
  r.ok(!!mob, mob ? 'eventi.html: il cassetto c\'è' : 'cassetto del telefono non trovato');
  if (mob) {
    const sep = mob[0].indexOf('class="mm-sep"');
    r.ok(sep > 0, 'il cassetto separa le porte dal resto');
    const dopo = HUB.filter(([, f]) => mob[0].indexOf(`href="${f}"`) > sep);
    r.ok(dopo.length === 0, dopo.length
      ? `nel cassetto ${dopo.length} porte stanno sotto il separatore`
      : 'le quattro porte stanno tutte prima del separatore');
  }

  // Una prova nel browser, perche' il resto e' lettura di file: la riga deve
  // essere davvero visibile e cliccabile, non solo presente nell'HTML. Una
  // regola di CSS sbagliata (un display:none ereditato, un contenitore a
  // altezza zero) non si vede leggendo il sorgente.
  const { ctx, page } = await apri(browser, 'corsi.html', 412);
  const card = page.locator('.eco .eco-c');
  r.ok(await card.count() === 3, 'corsi.html a 412px: tre card nel DOM');
  r.ok(await card.first().isVisible(), 'e la prima è visibile');
  const alto = await card.first().evaluate((el) => el.getBoundingClientRect().height);
  r.ok(alto >= 44, `l'area toccabile è alta ${Math.round(alto)}px (minimo 44)`);
  // Sotto i 700px le tre card vanno in pila: affiancate sarebbero tre colonne
  // da un centimetro.
  const x = await card.evaluateAll((els) =>
    els.map((e) => Math.round(e.getBoundingClientRect().left)));
  r.ok(new Set(x).size === 1, `sul telefono le card sono in pila (x: ${x.join(', ')})`);

  await ctx.close();
  return r;
};
