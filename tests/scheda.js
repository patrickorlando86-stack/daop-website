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
    // Le schede SPOSTATE non hanno un corpo, ed e' voluto: una correzione (il
    // comune, il nome) ha cambiato l'indirizzo della pagina, e questa e'
    // rimasta come cartello verso quella nuova. Il registro conserva la
    // descrizione vecchia - che e' proprio quella che non deve piu' stare in
    // pagina - quindi senza questa riga la prova cercherebbe qui il testo che
    // abbiamo tolto apposta.
    if ((registro[slug] || {}).spostata) continue;
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

  // ── 5. la riga dell'agenda: la stessa prosa, il programma no ──────────
  // eventi.html e' l'altra meta' di questa decisione. La riga impagina la
  // prosa esattamente come la scheda, ma la coda "Programma:" esce e diventa
  // un rimando (descrizione_riga in genera_eventi.py): la riga si scorre, la
  // scheda si legge.
  //
  // Le prove sono due e nessuna rifa' il lavoro del generatore. La prima e' la
  // stessa del punto 1 sull'altra superficie: la prosa non perde ne' aggiunge
  // una parola. La seconda e' quella che il generatore da solo non puo'
  // garantire - il numero promesso dalla riga dev'essere quello che la scheda
  // consegna, se no la riga mente su una pagina che chi legge non ha ancora
  // aperto - e con lei l'ancora #programma: un'ancora che non esiste scarica
  // in cima a una pagina lunga, che e' peggio di nessun link.
  r.titolo('eventi.html — la descrizione dentro la riga');
  const agenda = fs.readFileSync(path.join(RADICE, 'eventi.html'), 'utf8');
  const feed = JSON.parse(fs.readFileSync(path.join(RADICE, 'data', 'eventi.json'), 'utf8'));
  const perAncora = new Map(feed.map((e) => [e.anchor, e]));
  // Lo stesso marcatore di PROG_MARCA: "Programma:" vale solo se apre una
  // frase. Riscritto qui perche' e' il confine del confronto, non la logica.
  const MARCA = /(?:^|(?<=[.!?])\s+)Programma:\s*/i;
  const RIGA = /<article class="event-card[^>]*id="([^"]+)"[\s\S]*?<div class="event-desc">([\s\S]*?)<\/div>/g;
  const RIM = /<p class="ev-prog-rim"><a href="([^"]+)">([^<]*)<\/a><\/p>/;

  let righe = 0, rimandi = 0, inline = 0;
  const diverse = [], rotte = [], bugie = [], doppie = [];

  for (const m of agenda.matchAll(RIGA)) {
    const e = perAncora.get(m[1]);
    if (!e || !(e.descr || '').trim()) continue;
    righe++;
    const corpo = m[2];
    const rim = RIM.exec(corpo);
    if (rim) rimandi++;
    if (/<p>Programma: /.test(corpo)) inline++;
    // Rimando E coda insieme vorrebbe dire la stessa cosa detta due volte, una
    // per intero e una per riassunto.
    if (rim && /<p>Programma: /.test(corpo)) doppie.push(m[1]);

    const prosa = corpo.replace(RIM, '');
    const attesa = rim ? (e.descr || '').split(MARCA)[0] : (e.descr || '');
    if (parole(attesa).join(' ') !== parole(prosa).join(' ')) diverse.push(m[1]);

    if (!rim) continue;
    const [via, ancora] = rim[1].split('#');
    const dove = path.join(RADICE, via.replace(/^\//, ''));
    if (ancora !== 'programma' || !fs.existsSync(dove)) { rotte.push(rim[1]); continue; }
    const sch = fs.readFileSync(dove, 'utf8');
    if (!sch.includes('id="programma"')) { rotte.push(rim[1]); continue; }
    // Il conto: un <li> per voce dentro gli <ul class="ev-prog-v">, un
    // <p class="ev-prog-d"> per giorno. I giorni promessi sono quelli
    // DISTINTI, quindi non possono essere piu' dei gruppi che la scheda mostra.
    const voci = (sch.match(/<ul class="ev-prog-v">[\s\S]*?<\/ul>/g) || [])
      .reduce((n, u) => n + (u.match(/<li>/g) || []).length, 0);
    const giorni = (sch.match(/<p class="ev-prog-d">/g) || []).length;
    const p = /(\d+) appuntamenti(?: in (\d+) giorni)?/.exec(rim[2]);
    if (!p || Number(p[1]) !== voci || (p[2] && Number(p[2]) > giorni)) {
      bugie.push(`${m[1]}: la riga dice "${rim[2].trim()}", la scheda ha ${voci} voci in ${giorni} giorni`);
    }
  }

  r.ok(righe > 100, `${righe} righe dell'agenda con una descrizione nel feed`);
  r.ok(rimandi > 0, `${rimandi} righe mandano il programma alla scheda, ${inline} lo tengono in riga`);
  r.ok(diverse.length === 0, diverse.length
    ? `${diverse.length} righe perdono o aggiungono parole nella prosa: ${diverse.slice(0, 3).join(', ')}`
    : 'nessuna riga perde o aggiunge una parola di prosa');
  r.ok(doppie.length === 0, doppie.length
    ? `${doppie.length} righe hanno rimando e coda insieme: ${doppie.slice(0, 3).join(', ')}`
    : 'nessuna riga stampa il rimando e la coda insieme');
  r.ok(rotte.length === 0, rotte.length
    ? `${rotte.length} rimandi puntano a un'ancora che non c'e': ${rotte.slice(0, 3).join(', ')}`
    : 'ogni rimando cade sul "Programma" della sua scheda');
  r.ok(bugie.length === 0, bugie.length
    ? `${bugie.length} righe promettono un numero che la scheda non ha: ${bugie.slice(0, 2).join(' | ')}`
    : 'il numero promesso dalla riga e\' quello che la scheda consegna');

  return r;
};
