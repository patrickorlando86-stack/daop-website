// La scheda evento: la descrizione impaginata a valle del dato.
//
// Nel foglio la Descrizione e' una cella sola e non contiene mai un "\n":
// paragrafi ed elenco li fa corpo_descrizione() leggendo la struttura che nel
// testo c'e' per davvero (i punti di fine frase, il "Programma:" e i suoi
// punti e virgola). Quello che si prova qui non e' "la pagina si apre", sono
// le quattro cose che si rompono in silenzio:
//
//   1. l'impaginazione non perde ne' aggiunge una parola;
//   2. il grassetto non finisce sulla prosa, che sarebbe un giudizio
//      editoriale dato da una regex;
//   3. il testo piatto resta piatto dove serve - meta description, og e
//      JSON-LD leggono descr_txt, non l'HTML;
//   4. un programma senza date occupa la larghezza piena.
//
// La quarta e' la sola che non si vede nell'HTML: senza la regola
// `.ev-prog-g > .ev-prog-v:first-child{grid-column:1/-1}` l'elenco cade nella
// gola di 62px riservata alla data, ed e' capitato su 17 schede su 110 senza
// che niente diventasse rosso.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

const REG = path.join(RADICE, 'data', 'pagine-evento.json');
const CORPO = /<div class="ev-body">([\s\S]*?)\n {2}<\/div>/;
const SOLO_DATA = /^\d{1,2}\/\d{1,2}$/;

// Il testo visibile, cioe' quello che legge una persona: via i tag, sciolte le
// entita'. Le parole si spezzano tenendo dentro la barra, se no "18/09"
// diventerebbe due token e il confronto sulle date non direbbe niente.
const parole = (html) => html
  .replace(/<[^>]+>/g, ' ')
  .replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
  .match(/[\wÀ-ÿ/]+/g) || [];

module.exports = async function scheda(browser) {
  const r = esito();
  const registro = JSON.parse(fs.readFileSync(REG, 'utf8'));

  // ── 1-3. sull'HTML vero di tutte le schede ────────────────────────────
  r.titolo('eventi/*.html — la descrizione impaginata');
  const file = fs.readdirSync(path.join(RADICE, 'eventi'))
    // I tre box-*.html vivono dentro l'iframe di siti altrui e non sono schede.
    .filter((f) => f.endsWith('.html') && !f.startsWith('box-'));

  let controllate = 0, conProgramma = 0, senzaData = null, conData = null;
  const perse = [], grassetto = [], marcatore = [], sporche = [];

  for (const f of file) {
    const slug = f.slice(0, -5);
    const descr = ((registro[slug] || {}).descr || '').trim();
    if (!descr) continue;
    const html = fs.readFileSync(path.join(RADICE, 'eventi', f), 'utf8');
    const m = CORPO.exec(html);
    if (!m) { perse.push(`${f}: nessun .ev-body`); continue; }
    controllate++;
    const corpo = m[1];

    // 1. stesse parole. L'unica perdita ammessa sono le date ripetute che il
    // raggruppamento per giorno accorpa: "29/08 X; 29/08 Y" -> un 29/08 solo.
    // Quindi si confrontano le parole SENZA le date, che devono coincidere in
    // pieno, e poi si controlla che di date non ne sia comparsa nessuna in
    // piu' - una data inventata sarebbe il difetto peggiore di tutti.
    const a = parole(descr), b = parole(corpo);
    const testo = (t) => t.filter((x) => !SOLO_DATA.test(x)).join(' ');
    const date = (t) => t.filter((x) => SOLO_DATA.test(x)).length;
    if (testo(a) !== testo(b) || date(b) > date(a)) perse.push(f);

    // 2. niente grassetto sulla prosa: sta solo sulla data del programma, e
    // quello e' un <p class="ev-prog-d"> messo in grassetto dal CSS.
    const prosa = corpo.split('<h2 class="ev-prog-h">')[0];
    if (/<(strong|b|em)\b/i.test(prosa)) grassetto.push(f);

    if (corpo.includes('class="ev-prog"')) {
      conProgramma++;
      // 3. il marcatore diventa l'intestazione: se resta scritto "Programma:"
      // in mezzo al testo vuol dire che una parte non e' stata riconosciuta.
      if (/Programma:/i.test(corpo)) marcatore.push(f);
      if (/<div class="ev-prog-g">\s*<ul/.test(corpo)) senzaData = senzaData || f;
      else conData = conData || f;
    }

    // 3bis. meta e dati strutturati leggono il testo piatto: un <ul> dentro
    // una meta description non e' formattazione, e' markup che si vede fra i
    // risultati di Google.
    const teste = html.slice(0, html.indexOf('</head>'));
    if (/(?:name="description"|property="og:description")[^>]*content="[^"]*(?:&lt;|ev-prog)/
      .test(teste) || /"description": "[^"]*(?:<|ev-prog)/.test(teste)) sporche.push(f);
  }

  r.ok(controllate > 100, `${controllate} schede con una descrizione nel registro`);
  r.ok(conProgramma > 0, `${conProgramma} schede hanno il "Programma:" impaginato come elenco`);
  r.ok(perse.length === 0, perse.length
    ? `${perse.length} schede perdono o aggiungono parole: ${perse.slice(0, 3).join(', ')}`
    : 'nessuna scheda perde o aggiunge una parola');
  r.ok(grassetto.length === 0, grassetto.length
    ? `${grassetto.length} schede mettono grassetto sulla prosa: ${grassetto.slice(0, 3).join(', ')}`
    : 'nessun grassetto sulla prosa');
  r.ok(marcatore.length === 0, marcatore.length
    ? `${marcatore.length} schede tengono "Programma:" nel testo: ${marcatore.slice(0, 3).join(', ')}`
    : 'il marcatore "Programma:" diventa sempre l\'intestazione');
  r.ok(sporche.length === 0, sporche.length
    ? `${sporche.length} schede hanno markup nelle meta: ${sporche.slice(0, 3).join(', ')}`
    : 'meta description, og e JSON-LD restano testo piatto');

  // ── 4. la larghezza, che nell'HTML non si vede ────────────────────────
  if (conData) {
    r.titolo(`eventi/${conData} — il programma con le date`);
    const { ctx, page } = await apri(browser, `eventi/${conData}`, 1280);
    const misura = await page.evaluate(() => {
      const g = [...document.querySelectorAll('.ev-prog-g')];
      return {
        gruppi: g.length,
        date: g.filter((x) => x.querySelector('.ev-prog-d')).length,
        larghe: g.every((x) => x.querySelector('.ev-prog-v').offsetWidth > 200),
        corpo: document.querySelector('.ev-body').offsetWidth,
      };
    });
    r.ok(misura.gruppi > 0 && misura.date === misura.gruppi,
      `${misura.gruppi} gruppi, tutti con la loro data in colonna`);
    r.ok(misura.larghe, 'nessun elenco schiacciato nella gola della data');
    await ctx.close();
  }

  if (senzaData) {
    r.titolo(`eventi/${senzaData} — il programma senza date`);
    const { ctx, page } = await apri(browser, `eventi/${senzaData}`, 1280);
    const piena = await page.evaluate(() => {
      const g = document.querySelector('.ev-prog-g');
      const ul = g.querySelector('.ev-prog-v');
      return { ul: ul.offsetWidth, corpo: document.querySelector('.ev-body').offsetWidth };
    });
    r.ok(piena.ul === piena.corpo,
      `senza data l'elenco prende la larghezza piena (${piena.ul}/${piena.corpo}px)`);
    await ctx.close();
  }

  // Sul telefono, dove sta il 90% del pubblico: la pagina non deve scorrere
  // di lato. Le voci del programma sono righe lunghe con una pillola in coda,
  // che e' il modo classico di sfondare la larghezza.
  if (conData) {
    r.titolo(`eventi/${conData} — telefono 412px`);
    const { ctx, page } = await apri(browser, `eventi/${conData}`, 412);
    r.ok(await page.evaluate(() =>
      document.documentElement.scrollWidth <= document.documentElement.clientWidth),
      'niente scorrimento orizzontale');
    r.ok(await page.evaluate(() => {
      const g = document.querySelector('.ev-prog-g');
      return getComputedStyle(g).gridTemplateColumns.split(' ').length === 1;
    }), 'sotto i 520px la data va sopra le voci, non accanto');
    await ctx.close();
  }

  return r;
};
