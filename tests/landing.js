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

  return r;
};
