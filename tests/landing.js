// Pagine di intenzione: /eventi/oggi.html, /eventi/weekend.html e le
// sagre-provincia-*. Filtri, e le due trappole che il filtro deve gestire
// (titoli orfani e blocchi che non si filtrano).
'use strict';

const { apri, esito } = require('./_aiuto');

const visibili = (page) => page.locator('.ev-wrap li[data-category]:not([hidden])').count();

module.exports = async function landing(browser) {
  const r = esito();

  // ── oggi ──────────────────────────────────────────────────────────────
  r.titolo('eventi/oggi.html — telefono 412px');
  let { ctx, page } = await apri(browser, 'eventi/oggi.html', 412);
  const tot = await page.locator('.ev-wrap li[data-category]').count();

  if (!(await page.locator('#lan-toolbar').count())) {
    // Sotto MIN_FILTRI la barra non si stampa: e' voluto, non un guasto.
    r.ok(tot < 12, `niente barra filtri con ${tot} eventi (sotto la soglia)`);
    await ctx.close();
    return r;
  }

  r.ok(await visibili(page) === tot, `a riposo si vedono tutti: ${tot}`);
  r.ok((await page.textContent('#lan-count')).trim() === '', 'a riposo il conteggio resta muto');

  if (await page.locator('#lan-tipo').count()) {
    const cat = await page.$eval('#lan-tipo', (s) => s.options[1].value);
    await page.selectOption('#lan-tipo', cat);
    await page.waitForTimeout(250);
    const n = await visibili(page);
    r.ok(n > 0 && n < tot, `filtro categoria "${cat}": ${n}/${tot}`);
    r.ok(await page.evaluate((c) =>
      [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')]
        .every((l) => l.dataset.category === c), cat), 'restano solo le righe della categoria scelta');
    r.ok(/\d+ eventi? con questi filtri/.test(await page.textContent('#lan-count')),
      'il conteggio compare quando si filtra');
    r.ok(await page.$eval('#lan-tipo', (s) => s.classList.contains('is-on')),
      'la tendina attiva si evidenzia');

    // Un gruppo svuotato sparisce, e con lui il suo titolo: su queste pagine i
    // titoli stanno PRIMA della sezione e fuori da essa, quindi resterebbero
    // sospesi sopra il vuoto.
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap .com-grp')]
        .filter((g) => g.querySelector('li[data-category]'))
        .every((g) => g.hidden === !g.querySelector('li[data-category]:not([hidden])'))),
      'i gruppi rimasti vuoti spariscono');
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap h2')].every((h) => {
        if (h.hidden) return true;
        let n = h.nextElementSibling;
        while (n && n.tagName === 'P') n = n.nextElementSibling;
        return !n || !n.classList.contains('com-grp') || !n.hidden;
      })), 'nessun titolo resta orfano sopra un gruppo nascosto');
    r.ok(await page.evaluate(() => {
      const p = document.querySelector('.ev-wrap > p');
      return p && !p.hidden;
    }), 'il paragrafo di apertura non viene mai nascosto');

    if (await page.locator('#lan-dove').count()) {
      const pr = await page.$eval('#lan-dove', (s) => s.options[1].value);
      await page.selectOption('#lan-dove', pr);
      await page.waitForTimeout(250);
      r.ok(await page.evaluate((a) =>
        [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')]
          .every((l) => l.dataset.category === a.c && l.dataset.province === a.p),
        { c: cat, p: pr }), 'i due filtri si sommano');
      await page.selectOption('#lan-dove', 'all');
    }
    await page.selectOption('#lan-tipo', 'all');
    await page.waitForTimeout(200);
  }

  await page.fill('#lan-q', 'zzzznientedeltutto');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === 0, 'ricerca senza risultati: nessuna riga');
  r.ok(!(await page.locator('#lan-nulla').evaluate((n) => n.hidden)),
    'compare il messaggio "non resta niente"');
  await page.click('#lan-reset');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === tot, '"azzera i filtri" le fa tornare tutte');
  r.ok(await page.locator('#lan-nulla').evaluate((n) => n.hidden), 'il messaggio sparisce');

  r.ok((await page.locator('.com-cat').first().textContent()).trim().length > 0,
    'la categoria si legge in riga');
  r.ok(await page.locator('#lan-toolbar').evaluate((b) => b.offsetHeight) <= 120,
    'la barra filtri sta compatta sul telefono');
  await ctx.close();

  // ── weekend ───────────────────────────────────────────────────────────
  r.titolo('eventi/weekend.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'eventi/weekend.html', 412));
  const totW = await page.locator('.ev-wrap li[data-category]').count();
  if (await page.locator('#lan-dove').count()) {
    const pr = await page.$eval('#lan-dove', (s) => s.options[1].value);
    await page.selectOption('#lan-dove', pr);
    await page.waitForTimeout(250);
    const n = await visibili(page);
    r.ok(n > 0 && n < totW, `filtro provincia "${pr}": ${n}/${totW}`);
  } else {
    r.ok(true, 'nessuna tendina provincia da provare su questa pagina');
  }
  await ctx.close();

  // ── sagre per provincia ───────────────────────────────────────────────
  r.titolo('sagre-provincia-alessandria.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'sagre-provincia-alessandria.html', 412));
  if (await page.locator('#lan-toolbar').count()) {
    r.ok(await page.locator('#lan-dove').count() === 0,
      'niente tendina provincia: la pagina E\' una provincia');
    const totS = await page.locator('.ev-wrap li[data-category]').count();
    await page.fill('#lan-q', 'acqui');
    await page.waitForTimeout(300);
    const n = await visibili(page);
    r.ok(n > 0 && n < totS, `ricerca per paese: ${n}/${totS}`);
    // L'elenco delle feste che tornano ogni anno non ha provincia ne'
    // categoria: filtrando non deve sparire.
    const anni = await page.locator('.com-anni li').count();
    if (anni) {
      r.ok(await page.locator('.com-anni li:not([hidden])').count() === anni,
        `le ${anni} feste ricorrenti restano visibili`);
    }
  }
  await ctx.close();

  // ── ferragosto ────────────────────────────────────────────────────────
  // Pagina stagionale: le prove qui sotto difendono le due cose che si
  // smontano per distrazione, e che si pagano un anno dopo.
  r.titolo('ferragosto.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'ferragosto.html', 412));

  // 1) L'anno non sta nell'indirizzo. Se qualcuno ci mettesse /ferragosto-2027
  //    la pagina ripartirebbe da zero proprio sulla query che si vince solo
  //    con l'anzianita' dell'URL.
  const canon = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
  r.ok(/\/ferragosto\.html$/.test(canon), `canonical senza anno: ${canon}`);
  r.ok(!/\d{4}/.test(new URL(canon).pathname), 'nessun anno nel percorso');
  // L'anno pero' DEVE stare nel titolo, se no la pagina non dice di quale
  // Ferragosto parla.
  r.ok(/\b20\d{2}\b/.test(await page.title()), 'l\'anno sta nel <title>');

  // 2) Non e' un filtro di date. Quando il 15 cade di sabato o domenica
  //    l'elenco coincide con /eventi/weekend.html: quello che tiene le due
  //    pagine distinte e' il blocco su come ci si regola e dove si mangia,
  //    che manda a /luoghi.html. Toglierlo la trasforma in un doppione.
  r.ok(await page.locator('.ev-wrap p a[href="/luoghi.html"]').count() > 0,
    'il corpo manda a /luoghi.html (e non solo la nav)');

  const totF = await page.locator('.ev-wrap li[data-category]').count();
  const giorni = await page.locator('.ev-wrap .com-grp').count();
  if (totF) {
    r.ok(giorni > 0 && giorni <= 3, `il ponte sta in ${giorni} giorni (max 14-16)`);
    r.ok((await page.locator('.com-per').allTextContents()).some((t) => /Ferragosto/i.test(t)),
      'il 15 e\' etichettato "Ferragosto"');
    r.ok((await page.$eval('meta[name=robots]', (m) => m.content)).startsWith('index'),
      `con ${totF} eventi la pagina e' indicizzata`);
  } else {
    // Fuori stagione resta online - i link girati devono funzionare - ma
    // esce dall'indice invece di restare una pagina vuota indicizzata.
    r.ok((await page.$eval('meta[name=robots]', (m) => m.content)).startsWith('noindex'),
      'a vuoto la pagina e\' in noindex, follow');
  }
  await ctx.close();

  // ── halloween ─────────────────────────────────────────────────────────
  // Seconda pagina stagionale. Le prove sono quelle di ferragosto.html - un
  // URL che invecchia, e il blocco che la tiene distinta da un filtro di date
  // - piu' quella che vale solo qui: la pagina non deve mai dire da sola
  // quali eventi fanno paura.
  r.titolo('halloween.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'halloween.html', 412));

  const canonH = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
  r.ok(/\/halloween\.html$/.test(canonH), `canonical senza anno: ${canonH}`);
  r.ok(!/\d/.test(new URL(canonH).pathname), 'nessuna cifra nel percorso');
  r.ok(/\b20\d{2}\b/.test(await page.title()), 'l\'anno sta nel <title>');

  // Il pezzo che un elenco di date non ha: la domanda "fa paura o no?" e il
  // rimando a /luoghi.html per il dove. Toglierli la rende un doppione di
  // /eventi/weekend.html, e a perdere sarebbe lei.
  r.ok((await page.locator('.ev-wrap h2').allTextContents())
    .some((t) => /fa paura/i.test(t)), 'il blocco "fa paura o no?" c\'è');
  r.ok(await page.locator('.ev-wrap p a[href="/luoghi.html"]').count() > 0,
    'il corpo manda a /luoghi.html (e non solo la nav)');

  const totH = await page.locator('.ev-wrap li[data-category]').count();
  const robotsH = await page.$eval('meta[name=robots]', (m) => m.content);
  if (totH) {
    // Le sezioni sono giorni della finestra 25/10-2/11: mai altri mesi.
    const mesi = (await page.locator('.ev-wrap .com-grp h3').allTextContents())
      .filter((t) => /\d/.test(t));
    r.ok(mesi.every((t) => /ottobre|novembre/i.test(t)),
      `la finestra resta 25 ottobre-2 novembre: ${mesi.join(' / ')}`);
  } else {
    r.ok(robotsH.startsWith('noindex'),
      'a vuoto la pagina è in noindex, follow: resta online ma fuori indice');
  }

  // La cernita che NON si fa: l'evidenza è "pensati per i più piccoli",
  // ricavata da e_per_bambini(). Una sezione che dichiari quali fanno paura
  // sarebbe un giudizio nostro su una festa altrui, dedotto dal titolo.
  const titoli = await page.locator('.ev-wrap .com-grp h3').allTextContents();
  r.ok(!titoli.some((t) => /paura|horror|brivid|spavent/i.test(t)),
    'nessuna sezione etichetta gli eventi come spaventosi');
  await ctx.close();

  // ── le sei pagine d'incrocio ──────────────────────────────────────────
  // Provincia X finestra temporale. Le prove qui difendono le tre cose per
  // cui esistono: la provincia nell'H1 (non solo nel title, che e' il difetto
  // di oggi.html/weekend.html), l'indirizzo senza data, e il fatto che dentro
  // ci sia davvero solo quella provincia - se no la pagina promette una cosa
  // e ne mostra un'altra.
  for (const [modo, prov, sigla] of [['oggi', 'alessandria', 'al'],
                                     ['weekend', 'asti', 'at'],
                                     ['oggi', 'cuneo', 'cn']]) {
    const file = `eventi/${modo}-provincia-${prov}.html`;
    r.titolo(`${file} — telefono 412px`);
    ({ ctx, page } = await apri(browser, file, 412));

    const h1 = (await page.textContent('h1')).trim();
    r.ok(new RegExp(`provincia di ${prov}`, 'i').test(h1),
      `la provincia sta nell'H1, non solo nel title: "${h1}"`);
    r.ok(/oggi|weekend/i.test(h1), 'e con lei la finestra temporale');

    // Stessa regola di /ferragosto.html: l'anno - e qualsiasi data - fuori
    // dall'indirizzo, se no la pagina riparte da zero a ogni stagione.
    const c = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
    r.ok(!/\d/.test(new URL(c).pathname), `nessuna cifra nel percorso: ${c}`);

    const righe = await page.locator('.ev-wrap li[data-category]').count();
    if (righe) {
      r.ok(await page.evaluate((p) =>
        [...document.querySelectorAll('.ev-wrap li[data-province]')]
          .every((l) => l.dataset.province === p), sigla),
        `tutte le ${righe} righe sono della provincia ${sigla.toUpperCase()}`);
    }
    if (await page.locator('#lan-toolbar').count()) {
      r.ok(await page.locator('#lan-dove').count() === 0,
        'niente tendina provincia: la pagina E\' una provincia');
    }

    // Il robots si decide sulla finestra larga, non sugli eventi di oggi: e'
    // quello che evita a "oggi in provincia di Cuneo" di entrare e uscire
    // dall'indice ogni notte. Quello che si puo' controllare dal DOM e' il
    // patto che ne discende: indicizzata solo se ha qualcosa da mostrare.
    const robots = await page.$eval('meta[name=robots]', (m) => m.content);
    if (robots.startsWith('index')) {
      r.ok(righe > 0, `indicizzata e non vuota (${righe} righe)`);
    } else {
      r.ok(robots.startsWith('noindex'), 'fuori stagione: noindex, follow');
    }

    // Le briciole hanno il gradino in piu': queste pagine stanno SOTTO
    // /eventi/oggi.html, non accanto.
    r.ok(await page.locator(`.ev-crumb a[href="/eventi/${modo}.html"]`).count() > 0,
      'le briciole passano dalla pagina madre');

    // L'anello fra le tre sorelle, e nessun link a se stessa.
    const altre = await page.$$eval('.com-link a[href*="-provincia-"]',
      (a) => a.map((x) => x.getAttribute('href')));
    r.ok(altre.length >= 2, `rimanda alle altre province (${altre.length})`);
    r.ok(!altre.some((h) => h.endsWith(`${modo}-provincia-${prov}.html`)),
      'e non a se stessa');
    await ctx.close();
  }

  // Le due pagine trasversali fanno da indice: se questo blocco sparisce, le
  // sei nascono orfane e non le trova nessuno.
  for (const modo of ['oggi', 'weekend']) {
    r.titolo(`eventi/${modo}.html — indice delle provinciali`);
    ({ ctx, page } = await apri(browser, `eventi/${modo}.html`, 412));
    const giu = await page.$$eval('.com-link a[href*="-provincia-"]',
      (a) => a.map((x) => x.getAttribute('href')));
    r.ok(giu.length === 3, `linka tutte e tre le provinciali (${giu.length})`);
    r.ok(giu.every((h) => h.includes(`${modo}-provincia-`)),
      'e sono quelle della sua finestra temporale');
    // Meta' della query e' il posto: prima le province stavano solo nel title.
    r.ok(/provincia di/i.test(await page.textContent('h1')),
      'l\'H1 nomina le province');
    await ctx.close();
  }

  return r;
};
